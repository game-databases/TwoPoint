#!/usr/bin/env python3
"""Stage 1 — decompile.

Runs the staged compiled Il2CppDumper headless over GameAssembly.dll +
global-metadata.dat (IL2CPP → dummy managed assemblies + dump.cs /
script.json / stringliteral.json), then builds the structural artifacts via
tools/build_structural.py. Escalation to Cpp2IL is declared, never
automatic (spec §3 stage 1).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import log_util
import tpc_common as tc

DUMP_TIMEOUT_SECONDS = 3600
_BANNER_RE = re.compile(r"Il2CppDumper\s+v?(\d[\w.\-]*)", re.IGNORECASE)


def resolve_tool(extracted_root: Path, pack_dir: Path, override: str | None) -> Path:
    if override:
        p = Path(override)
        if not p.is_file():
            raise tc.StageError(f"--tool-path does not exist: {p}", exit_code=3)
        return p.resolve()
    defaults = log_util.read_stage_defaults(extracted_root) or {}
    candidates = list((defaults.get("il2cppdumper") or {}).get("candidates")
                      or tc.IL2CPP_DUMPER_CANDIDATES)
    repo_root = tc.resolve_repo_root(pack_dir)
    for cand in candidates:
        p = Path(cand)
        resolved = p if p.is_absolute() else repo_root / cand
        if resolved.is_file():
            return resolved.resolve()
    raise tc.StageError(
        "no staged Il2CppDumper found; tried:\n  " + "\n  ".join(candidates)
        + "\nresolve with --tool-path or the stage-defaults block",
        exit_code=3)


def _run_dumper(tool: Path, game_assembly: Path, metadata: Path,
                out_dir: Path) -> tuple[int, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [str(tool), str(game_assembly), str(metadata), str(out_dir)],
        cwd=str(tool.parent),
        stdin=subprocess.DEVNULL,
        capture_output=True, text=True,
        timeout=DUMP_TIMEOUT_SECONDS, env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    output = (proc.stdout or "") + "\n" + (proc.stderr or "")
    return proc.returncode, output


def run(game_root: Path, extracted_root: Path, tool_override: str | None = None) -> int:
    paths = tc.game_paths(game_root)
    for p in (paths["game_assembly"], paths["metadata"],
              paths["scripting_assemblies"]):
        if not p.is_file():
            raise tc.StageError(f"missing required decompile input: {p}",
                                exit_code=3)
    pack_dir = tc.resolve_pack_dir()
    tool = resolve_tool(extracted_root, pack_dir, tool_override)

    out_dir = extracted_root / "decompiled" / "il2cppdumper"
    exit_code, output = _run_dumper(tool, paths["game_assembly"],
                                    paths["metadata"], out_dir)
    banner = _BANNER_RE.search(output or "")
    tool_version = banner.group(1) if banner else "unknown"

    # loud defect detection: a blocking prompt instead of argv/stdin handling
    # surfaces here as a timeout (subprocess.TimeoutExpired) or empty outputs.
    dummy_dll = out_dir / "DummyDll"
    dump_cs = out_dir / "dump.cs"
    script_json = out_dir / "script.json"
    stringliteral = out_dir / "stringliteral.json"

    problems = []
    if exit_code != 0:
        problems.append(f"dumper exited {exit_code}")
    if not (dummy_dll / "Assembly-CSharp.dll").is_file():
        problems.append("DummyDll/Assembly-CSharp.dll missing")
    if not dump_cs.is_file() or dump_cs.stat().st_size == 0:
        problems.append("dump.cs missing or empty")
    for jf in (script_json, stringliteral):
        if not jf.is_file():
            problems.append(f"{jf.name} missing")
            continue
        try:
            json.loads(jf.read_text(encoding="utf-8"))
        except ValueError as exc:
            problems.append(f"{jf.name} does not parse: {exc}")

    structural_summary = {}
    if not problems:
        import build_structural as bs
        try:
            structural_summary = bs.run(out_dir, paths["scripting_assemblies"],
                                        extracted_root)
        except tc.StageError:
            raise
        except Exception as exc:  # noqa: BLE001 — stage failure with context
            raise tc.StageError(
                f"structural artifact build failed: "
                f"{type(exc).__name__}: {exc}; escalation is DECLARED, not "
                f"automatic — {tc.CPP2IL_ESCALATION_MESSAGE}") from exc

    lines = [
        "- exitCode: 0" if not problems else f"- exitCode: 1 ({'; '.join(problems)})",
        f"- tool: Il2CppDumper v{tool_version} at {tool}",
        f"- inputs: GameAssembly.dll {paths['game_assembly'].stat().st_size} B, "
        f"global-metadata.dat {paths['metadata'].stat().st_size} B",
    ]
    lines += [f"- {k}: {v}" for k, v in sorted(structural_summary.items())]
    if problems:
        lines.append(f"- escalationTrigger: {tc.CPP2IL_ESCALATION_MESSAGE}")
    log_util.append_run_section(extracted_root, "decompile", lines)

    print(f"[decompile] tool=Il2CppDumper v{tool_version} "
          f"hierarchyRows={structural_summary.get('hierarchyRowCount')} "
          f"hierarchySource={structural_summary.get('hierarchySource')}")
    if problems:
        for p in problems:
            print(f"[decompile] PROBLEM: {p}", file=sys.stderr)
        return 1
    return 0


def main(argv=None) -> int:
    log_util.bootstrap_console()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("game_dir", nargs="?", default=None)
    parser.add_argument("--extracted-root", default=None)
    parser.add_argument("--tool-path", default=None,
                        help="explicit Il2CppDumper.exe path")
    args = parser.parse_args(argv)
    try:
        pack_dir = tc.resolve_pack_dir()
        root = tc.resolve_extracted_root(pack_dir)
        if args.extracted_root:
            root = Path(args.extracted_root).resolve()
        game_root = tc.resolve_game_root(args.game_dir)
        return run(game_root, root, args.tool_path)
    except tc.StageError as exc:
        print(f"[decompile] ERROR: {exc}", file=sys.stderr)
        return exc.exit_code
    except subprocess.TimeoutExpired:
        print(f"[decompile] DEFECT: dumper blocked past "
              f"{DUMP_TIMEOUT_SECONDS}s instead of honoring argv/stdin — fix "
              "this stage's invocation, do not retry silently", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
