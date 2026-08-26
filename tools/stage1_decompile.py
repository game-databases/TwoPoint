#!/usr/bin/env python3
"""Stage 1 — decompile.

Runs the staged compiled Il2CppDumper headless over GameAssembly.dll +
global-metadata.dat (IL2CPP → dummy managed assemblies + dump.cs /
script.json / stringliteral.json), then builds the structural artifacts via
tools/build_structural.py. Escalation to Cpp2IL is declared, never
automatic, and its trigger text fires ONLY off the MEASURED metadata
version (>= 38) — never canned onto unrelated failures (spec §3 stage 1,
Revision 4).

The success gate is MULTI-IMAGE (spec §3 stage 1, Revision 4): the DummyDll
set must be non-empty and every ScriptingAssemblies.json entry classified
present-or-absent-with-marker with at least one `dummy-present` entry backed
by a real image. `DummyDll/Assembly-CSharp.dll` is NOT required — this
client ships none (game code lives in TPS.Game.dll / TPS.Core*.dll), so the
structural hierarchy is built over ALL present game-code images.
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
    # the seeded stage-defaults block wins for ORDER, but the embedded
    # candidates are always appended after it (first-occurrence dedup): a
    # stale seeded block naming dead paths must never shadow the corrected
    # in-repo entries
    log_candidates = list((defaults.get("il2cppdumper") or {}).get("candidates") or [])
    candidates = log_candidates + [c for c in tc.IL2CPP_DUMPER_CANDIDATES
                                   if c not in log_candidates]
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


def _multi_image_gate(structural_dir: Path, dummy_dll: Path) -> list[str]:
    """Multi-image success gate (spec §3 stage 1 acceptance, Revision 4):
    every ScriptingAssemblies.json entry must appear in assembly-index.json
    classified present-or-absent-with-marker, with at least one
    `dummy-present` entry backed by a real DummyDll image on disk.
    Assembly-CSharp.dll is deliberately NOT required."""
    idx_path = structural_dir / "assembly-index.json"
    try:
        obj = json.loads(idx_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [f"assembly-index.json unreadable — cannot evaluate the "
                f"multi-image gate: {exc}"]
    rows = obj.get("assemblies") if isinstance(obj, dict) else obj
    if not isinstance(rows, list) or not rows:
        return ["assembly-index.json carries no assembly rows"]
    problems: list[str] = []
    unclassified = sorted(str(r.get("assembly")) for r in rows
                          if r.get("status") not in
                          ("dummy-present", "dummy-absent(stripped)"))
    if unclassified:
        problems.append(f"{len(unclassified)} ScriptingAssemblies entries "
                        f"unclassified in assembly-index.json: "
                        f"{unclassified[:8]}")
    present_unbacked = sorted(
        str(r.get("assembly")) for r in rows
        if r.get("status") == "dummy-present"
        and not (dummy_dll / f"{r.get('assembly')}.dll").is_file())
    if present_unbacked:
        problems.append(f"{len(present_unbacked)} dummy-present entries lack a "
                        f"backing image: {present_unbacked[:8]}")
    has_backed_present = any(
        r.get("status") == "dummy-present"
        and (dummy_dll / f"{r.get('assembly')}.dll").is_file() for r in rows)
    if not has_backed_present:
        problems.append("no dummy-present assembly backed by a real image "
                        "(multi-image gate)")
    return problems


def run(game_root: Path, extracted_root: Path, tool_override: str | None = None) -> int:
    paths = tc.game_paths(game_root)
    for p in (paths["game_assembly"], paths["metadata"],
              paths["scripting_assemblies"]):
        if not p.is_file():
            raise tc.StageError(f"missing required decompile input: {p}",
                                exit_code=3)
    pack_dir = tc.resolve_pack_dir()
    tool = resolve_tool(extracted_root, pack_dir, tool_override)
    # the MEASURED metadata version — the ONLY thing allowed to trip the
    # Cpp2IL escalation text (Revision 4 item 4: no canned trigger on
    # unrelated failures)
    _sanity, metadata_version = tc.read_metadata_header(paths["metadata"])

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
    dummy_count = len(sorted(dummy_dll.glob("*.dll"))) if dummy_dll.is_dir() else 0
    if dummy_count == 0:
        problems.append("DummyDll set is EMPTY — no managed images emitted "
                        "(multi-image gate)")
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
                f"{type(exc).__name__}: {exc}") from exc
        # the multi-image gate evaluates the freshly written assembly-index
        problems.extend(_multi_image_gate(
            extracted_root / "decompiled" / "structural", dummy_dll))

    lines = [
        "- exitCode: 0" if not problems else f"- exitCode: 1 ({'; '.join(problems)})",
        f"- tool: Il2CppDumper v{tool_version} at {tool}",
        f"- inputs: GameAssembly.dll {paths['game_assembly'].stat().st_size} B, "
        f"global-metadata.dat {paths['metadata'].stat().st_size} B",
        f"- measuredMetadataVersion: {metadata_version}",
        f"- dummyDllImages: {dummy_count} (gate: non-empty set; "
        "Assembly-CSharp.dll not required)",
    ]
    for key, value in sorted(structural_summary.items()):
        if key == "registryCount":
            # piece-05 §6 item 2 (RED-3): the counter's unit is inline —
            # covered CLASSES vs the id-registries DIRECTORY's FILES.
            lines.append(
                f"- registryCount(covered classes; "
                f"files = {structural_summary.get('registryFiles', '?')}): "
                f"{value}")
        elif key == "registryFiles":
            continue
        else:
            lines.append(f"- {key}: {value}")
    if metadata_version >= tc.METADATA_VERSION_WALL:
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
        log_util.append_failure_section(root, "decompile", exc.exit_code,
                                        [str(exc)])
        print(f"[decompile] ERROR: {exc}", file=sys.stderr)
        return exc.exit_code
    except subprocess.TimeoutExpired:
        problem = (f"dumper blocked past {DUMP_TIMEOUT_SECONDS}s instead of "
                   "honoring argv/stdin — fix this stage's invocation, do "
                   "not retry silently")
        log_util.append_failure_section(root, "decompile", 1,
                                        [f"DEFECT: {problem}"])
        print(f"[decompile] DEFECT: {problem}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
