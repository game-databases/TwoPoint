#!/usr/bin/env python3
"""Two Point Campus — piece-1 extraction pipeline entrypoint.

Reproduces the harvest → decompile → relink-ready raw layers from the game
install ([DR-2026-08-18-pipeline]; spec:
docs/specs/piece-01-extraction-pipeline.mdx incl. Revision 2).

Usage:
    python run_all.py <game-dir>              # run every stage in order
    python run_all.py <game-dir> --only <id>  # one stage in isolation
    python run_all.py <game-dir> --skip a,b   # skip listed stages
    python run_all.py --force                 # ignore up-to-date stamps
    python run_all.py --list                  # enumerate stages

The game directory may be the install root or its TPC_Data child.
Env knobs: TPC_GAME_DIR / TPC_PACK_DIR / TPC_EXTRACTED_ROOT. Defaults
(tool paths, versions) are read from the stage-defaults JSON block in
extracted/EXTRACTION-LOG.md with embedded fallback pins — the log is the
source of truth per doctrine.

Exit codes: 0 success · 1 stage failure · 2 completed-with-ledger ·
3 environment/gate refusal.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "tools"))

import log_util
import tpc_common as tc

# per-stage declared upstream artifacts (runner pre-check → exit 3 naming
# what is missing); stages re-check internally too
UPSTREAMS = {
    "verify-client": [],
    "decompile": [],
    "harvest-catalog": ["bundle-roster.jsonl"],
    "harvest-bundles": ["bundle-roster.jsonl"],
    "localisation": ["bundle-roster.jsonl"],
    "emit-stub-datasets": ["harvest/monobehaviours",
                           "addressables/catalog.json",
                           "decompiled/structural",
                           "locales/locale-matrix.json"],
    # piece-01 Revision 7 §5.2: stage-6 prepared-tree upstream set (+ the
    # game dir — the R1 bridge passes open the roster bundles read-only)
    "relink": ["stubs",
               "harvest/export-manifest.jsonl",
               "harvest/externals.jsonl",
               "harvest/monobehaviours/localisation_assets_localisation/"
               "I2.Loc.LanguageSourceAsset",
               "addressables/catalog.json",
               "locales/locale-matrix.json",
               "decompiled/structural",
               "bundle-roster.jsonl"],
    # piece-03 §3 maps upstream set — committed artifacts only; the stage
    # opens ZERO asset bundles and needs NO game dir. The per-family dump
    # globs (TPC.LevelScenarioV2 / TPC.LevelConfig / TPC.ItemValidator_Door
    # / TPC.LandscapeBrush*) are re-gated INSIDE the stage, which exits 3
    # naming the exact missing glob; the runner pre-check names the coarse
    # roots.
    "maps": [
        "identity.json",
        "bundle-roster.jsonl",
        "harvest/export-manifest.jsonl",
        "harvest/externals.jsonl",
        "relinks/bridges/cab_index.jsonl",
        "relinks/bridges/container_index.jsonl",
        "relinks/i2_term_registry.jsonl",
        "addressables/catalog.json",
        "decompiled/il2cppdumper/dump.cs",
        "harvest/monobehaviours",
    ],
    # piece-07 §4: locale-proof upstream set — committed flat artifacts
    # only (purely derived; no game dir). The per-locale tables ARE part of
    # the pinned §4 gate set ("locales/<locale>.jsonl x13"), so they are
    # declared here BOTH for the runner pre-check (ANY missing => exit 3
    # naming it) and so a table edit invalidates the stage stamp (AC10's
    # rerun-the-tripwire leg re-executes without --force). The OPTIONAL
    # alias input (data/sources/derived/course-name-aliases.jsonl) is not a
    # gate: absence is a ledger row, never a refusal.
    "locale-proof": [
        "identity.json",
        "bundle-roster.jsonl",
        "locales/de.jsonl", "locales/en.jsonl", "locales/es.jsonl",
        "locales/fr.jsonl", "locales/it.jsonl", "locales/ja.jsonl",
        "locales/ko.jsonl", "locales/pl.jsonl", "locales/pt-BR.jsonl",
        "locales/ru.jsonl", "locales/tr.jsonl", "locales/zh-Hans.jsonl",
        "locales/zh-Hant.jsonl",
        "locales/base-overlay.jsonl",
        "locales/base-overlay-report.json",
        "locales/locale-matrix.json",
        "stubs/items.jsonl", "stubs/unlockables.jsonl", "stubs/rooms.jsonl",
        "stubs/campus-levels.jsonl", "stubs/courses.jsonl",
        "stubs/configs.jsonl", "stubs/staff.jsonl",
        "stubs/metagame-nodes.jsonl", "stubs/student-types.jsonl",
        "relinks/entity_locale.jsonl",
        "relinks/i2_term_registry.jsonl",
        "relinks/locale_term_entity.jsonl",
        "relinks/locale_join_report.json",
    ],
    # piece-05 check-contracts (canonical index 10): pure-read validator
    # suite over the emitted corpus. The heavy-artifact policy requires the
    # PERSISTED sidecar (absent ⇒ exit 3 naming it; --scan-catalog is the
    # stage's own bootstrap/audit lane). The RED-1 ledger
    # `_uncontained_addresses.jsonl` is deliberately NOT required — its
    # absence IS the registered EXPECTED-RED state until the amendment
    # lands.
    "check-contracts": [
        "identity.json",
        "EXTRACTION-LOG.md",
        "bundle-roster.jsonl",
        "addressables/catalog-mini-report.json",
        "addressables/catalog-coverage.json",
        "harvest/export-manifest.jsonl",
        "harvest/externals.jsonl",
        "media-catalogue.jsonl",
        "locales/base-overlay-report.json",
        "locales/locale-matrix.json",
        "stubs/_absences.jsonl",
        "stubs/_unmapped-families.jsonl",
        "relinks/matrix.json",
        "relinks/entity_asset_guid.jsonl",
        "relinks/guid_bridge_report.json",
        "relinks/_dangling_guids.jsonl",
        "relinks/_unresolved_pptrs.jsonl",
        "relinks/i2_term_registry.jsonl",
        "relinks/entity_locale.jsonl",
        "relinks/locale_term_entity.jsonl",
        "relinks/locale_join_report.json",
        "relinks/ui_link_coverage.jsonl",
        "relinks/competitor_applied.jsonl",
        "relinks/bridges/cab_index.jsonl",
        "relinks/bridges/container_index.jsonl",
    ],
    # piece-08 search-corpus (canonical index 12): committed flat artifacts
    # PLUS the two consumed stage stamps — a changed relink/localisation
    # stamp identity IS the declared rebuild trigger (spec §S5.3). The
    # per-locale tables are NOT enumerated here: the REQUIRED table set
    # resolves inside the stage from locales/*.jsonl (a hostless mini
    # fixture names fewer than 13). OPTIONAL inputs — the item-item pair
    # scan and the curated alias table — are ledger-degraded, never gates.
    "search-corpus": [
        "identity.json",
        ".stage-stamps/relink.json",
        ".stage-stamps/localisation.json",
        "locales/locale-matrix.json",
        "stubs/items.jsonl", "stubs/unlockables.jsonl", "stubs/rooms.jsonl",
        "stubs/campus-levels.jsonl", "stubs/courses.jsonl",
        "stubs/configs.jsonl", "stubs/staff.jsonl",
        "stubs/metagame-nodes.jsonl", "stubs/student-types.jsonl",
        "relinks/entity_locale.jsonl",
        "relinks/i2_term_registry.jsonl",
        "relinks/locale_term_entity.jsonl",
        "relinks/matrix.json",
        "relinks/guid_bridge_report.json",
        "relinks/locale_join_report.json",
    ],
}

STAGE_TOOLS = {
    "verify-client": "stdlib",
    "decompile": "Il2CppDumper (staged)",
    "harvest-catalog": "UnityPy",
    "harvest-bundles": "UnityPy",
    "localisation": "UnityPy",
    "emit-stub-datasets": "stdlib",
    "relink": "UnityPy",
    # piece-03: purely derived — committed artifacts in, maps datasets out
    # (stdlib; opens zero bundles, needs no game dir)
    "maps": "stdlib",
    # piece-07: purely derived — committed artifacts in, proof artifacts out
    "locale-proof": "stdlib",
    # piece-05: pure-read validator suite (stdlib; zero-write over extracted/)
    "check-contracts": "stdlib",
    # piece-08: purely derived — committed artifacts + stamps in,
    # search shards/manifest out (stdlib; opens zero bundles)
    "search-corpus": "stdlib",
}


def _reexec_into_venv(pack_dir: Path) -> None:
    """Stages 2–5 need UnityPy from the pack .venv; upgrade transparently."""
    if os.environ.get("TPC_VENV_REEXEC") == "1":
        return
    venv_python = (pack_dir / ".venv" / "Scripts" / "python.exe" if os.name == "nt"
                   else pack_dir / ".venv" / "bin" / "python")
    if not venv_python.is_file():
        return
    try:
        if Path(sys.executable).resolve() == venv_python.resolve():
            return
    except OSError:
        return
    env = {**os.environ, "TPC_VENV_REEXEC": "1"}
    raise SystemExit(subprocess.call([str(venv_python), str(Path(__file__).resolve()),
                                      *sys.argv[1:]], env=env))


def _script_hashes(pack_dir: Path, deps: list[str]) -> dict[str, str]:
    out = {}
    tools_dir = pack_dir / "tools"
    for dep in deps:
        p = tools_dir / dep
        out[dep] = log_util.sha256_file(p) if p.is_file() else "missing"
    return out


def _upstream_identity(extracted_root: Path, stage_id: str,
                       paths: dict | None) -> dict:
    upstream: dict[str, str] = {}
    for rel in UPSTREAMS[stage_id]:
        p = extracted_root / rel
        if p.is_file():
            upstream[rel] = log_util.sha256_file(p)
        elif p.is_dir():
            entries = sorted(x.relative_to(extracted_root).as_posix()
                             for x in p.rglob("*") if x.is_file())
            digest_src = "\n".join(entries).encode("utf-8")
            upstream[rel] = f"{len(entries)} files:" \
                            f"{log_util.sha256_bytes(digest_src)}"
    if stage_id == "verify-client":
        manifest = tc.find_appmanifest(paths["root"]) if paths else None
        if manifest is not None:
            upstream["appmanifest"] = json_safe_fp(manifest)
        metadata = paths["metadata"] if paths else None
        if metadata is not None and metadata.is_file():
            upstream["global-metadata.dat"] = json_safe_fp(metadata)
    if stage_id == "decompile" and paths is not None:
        ga = paths["game_assembly"]
        if ga.is_file():
            upstream["GameAssembly.dll"] = json_safe_fp(ga)
    return upstream


def json_safe_fp(path: Path) -> str:
    fp = log_util.file_fingerprint(path)
    return f"{fp['size']}B@{fp['mtimeNs']}"


def compute_stage_identity(pack_dir: Path, extracted_root: Path,
                           stage_id: str, game_root: Path | None) -> str:
    entry = next((e for e in tc.STAGES if e[0] == stage_id), None)
    deps = entry[2] if entry else []
    payload = {
        "stage": stage_id,
        "scripts": _script_hashes(pack_dir, deps),
        "config": {
            "extractedRoot": str(extracted_root),
            "gameRoot": str(game_root) if game_root else None,
        },
        "upstream": _upstream_identity(extracted_root, stage_id,
                                       tc.game_paths(game_root)
                                       if game_root else None),
    }
    return log_util.identity_hash(payload)


def check_upstreams(extracted_root: Path, stage_id: str) -> None:
    missing = [rel for rel in UPSTREAMS[stage_id]
               if not (extracted_root / rel).exists()]
    if missing:
        raise tc.StageError(
            f"stage '{stage_id}' is missing upstream artifacts "
            f"({', '.join(missing)}) — prepare the tree first "
            "(client mode: run the pipeline without this stage; hostless "
            "smoke: tests/build_fixture_tree.py --stage "
            f"{stage_id})", exit_code=3)


def invoke_stage(stage_id: str, script: Path, game_root: Path | None,
                 extracted_root: Path, extra_args: list[str]) -> int:
    argv = [sys.executable, str(script)]
    if game_root is not None:
        argv.append(str(game_root))
    argv += ["--extracted-root", str(extracted_root), *extra_args]
    proc = subprocess.run(argv)
    return proc.returncode


def stage_status(extracted_root: Path, stage_id: str, identity: str) -> str:
    stamp = log_util.load_stamp(extracted_root, stage_id)
    if stamp is None:
        return "not-run"
    if stamp.get("identity") != identity:
        return "stale"
    if stamp.get("exitCode") not in (0, 2):
        return f"needs-rerun(last-exit={stamp.get('exitCode')})"
    # a surviving stamp is only up-to-date while its declared outputs do too
    return ("up-to-date" if log_util.outputs_current(extracted_root,
                                                     stage_id, stamp)
            else "stale")


def print_list(pack_dir: Path, extracted_root: Path, game_root: Path | None) -> None:
    print(f"{'stage':<20} {'script':<34} {'tool':<24} {'version':<16} status")
    for stage_id, script_rel, _deps in tc.STAGES:
        identity = compute_stage_identity(pack_dir, extracted_root,
                                          stage_id, game_root)
        status = stage_status(extracted_root, stage_id, identity)
        tool = STAGE_TOOLS[stage_id]
        version = "-"
        if tool == "UnityPy":
            version = resolve_unitypy_pin(extracted_root)
            tool = f"UnityPy ~={version}"
        elif tool.startswith("Il2CppDumper"):
            version = resolve_il2cppdumper_version(extracted_root) or "-"
        print(f"{stage_id:<20} {script_rel:<34} {tool:<24} {version:<16} {status}")
    print()
    print("order: " + ", ".join(tc.STAGE_IDS))
    print("exit codes: 0 success · 1 failure · 2 completed-with-ledger · "
          "3 environment/gate refusal")


# same shape as the decompile stage's own banner regex — requires a leading
# digit, so an "unknown" tool version never matches
_IL2CPP_BANNER_RE = re.compile(r"Il2CppDumper\s+v?(\d[\w.\-]*)", re.IGNORECASE)


def resolve_il2cppdumper_version(extracted_root: Path) -> str | None:
    """Last-measured Il2CppDumper banner version stamped in
    EXTRACTION-LOG.md — the stage-defaults `il2cppdumper.version` key when
    present, else the last decompile run-section banner. None (never a
    guess) while the log carries no stamp."""
    defaults = log_util.read_stage_defaults(extracted_root) or {}
    pinned = (defaults.get("il2cppdumper") or {}).get("version")
    if pinned:
        return str(pinned)
    path = log_util.log_path(extracted_root)
    if not path.is_file():
        return None
    stamps = _IL2CPP_BANNER_RE.findall(path.read_text(encoding="utf-8"))
    return stamps[-1] if stamps else None


def resolve_unitypy_pin(extracted_root: Path) -> str:
    defaults = log_util.read_stage_defaults(extracted_root) or {}
    return str(defaults.get("unitypyVersion") or tc.UNITYPY_PIN)


def main(argv=None) -> int:
    log_util.bootstrap_console()
    parser = argparse.ArgumentParser(
        prog="run_all.py",
        description="Two Point Campus extraction pipeline (piece 1)")
    parser.add_argument("game_dir", nargs="?",
                        help="install root or TPC_Data child "
                             "(default $TPC_GAME_DIR)")
    parser.add_argument("--only", metavar="STAGE",
                        help="run ONE stage in isolation")
    parser.add_argument("--skip", metavar="A,B",
                        help="comma-separated stage ids to skip")
    parser.add_argument("--force", action="store_true",
                        help="ignore up-to-date stamps")
    parser.add_argument("--extracted-root", default=None,
                        help="override the extraction root ($TPC_EXTRACTED_ROOT)")
    parser.add_argument("--tool-path", default=None,
                        help="decompile stage: explicit Il2CppDumper.exe path")
    parser.add_argument("--list", action="store_true",
                        help="enumerate stages with tool/version/status")
    parser.add_argument("--print-unitypy-pin", action="store_true",
                        help="print the pinned UnityPy version (make setup)")
    args = parser.parse_args(argv)

    pack_dir = tc.resolve_pack_dir()
    extracted_root = tc.resolve_extracted_root(pack_dir)
    if args.extracted_root:
        extracted_root = Path(args.extracted_root).resolve()

    if args.print_unitypy_pin:
        print(resolve_unitypy_pin(extracted_root))
        return 0

    _reexec_into_venv(pack_dir)

    game_root = None
    try:
        if args.game_dir or os.environ.get("TPC_GAME_DIR"):
            game_root = tc.resolve_game_root(args.game_dir)
    except tc.StageError as exc:
        if args.list:
            print(f"(--list without a resolvable game dir: {exc})")
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
            return exc.exit_code

    if args.list:
        print_list(pack_dir, extracted_root, game_root)
        return 0

    if not game_root:
        print("ERROR: no game directory given (positional arg or TPC_GAME_DIR)",
              file=sys.stderr)
        return 3

    stage_ids = list(tc.STAGE_IDS)
    if args.only:
        if args.only not in stage_ids:
            print(f"ERROR: unknown stage '{args.only}'; known: "
                  f"{', '.join(stage_ids)}", file=sys.stderr)
            return 3
        selected = [args.only]
    else:
        skipped = set(filter(None, (s.strip() for s in
                                    (args.skip or "").split(","))))
        unknown = sorted(skipped - set(stage_ids))
        if unknown:
            print(f"ERROR: --skip names unknown stage(s): "
                  f"{', '.join(unknown)}", file=sys.stderr)
            return 3
        selected = [s for s in stage_ids if s not in skipped]

    overall = 0
    executed: list[dict] = []
    for stage_id in selected:
        identity = compute_stage_identity(pack_dir, extracted_root,
                                          stage_id, game_root)
        if not args.force and log_util.is_up_to_date(extracted_root,
                                                     stage_id, identity):
            print(f"[{stage_id}] up-to-date (stamp matches; --force to rerun)")
            continue
        try:
            check_upstreams(extracted_root, stage_id)
            script = pack_dir / next(s for sid, s, _d in tc.STAGES
                                     if sid == stage_id)
            extra = ["--tool-path", args.tool_path] if (
                args.tool_path and stage_id == "decompile") else []
            print(f"[{stage_id}] running …")
            code = invoke_stage(stage_id, script, game_root, extracted_root,
                                extra)
        except tc.StageError as exc:
            print(f"[{stage_id}] ERROR: {exc}", file=sys.stderr)
            # runner-level refusals append the run section too (Revision 4):
            # the ledger never depends on a stage reaching its own logging
            log_util.append_failure_section(extracted_root, stage_id,
                                            exc.exit_code, [str(exc)])
            log_util.save_stamp(extracted_root, stage_id, identity,
                                exc.exit_code)
            executed.append({"stage": stage_id, "exitCode": exc.exit_code,
                             "refused": True})
            overall = exc.exit_code
            break
        log_util.save_stamp(extracted_root, stage_id, identity, code)
        executed.append({"stage": stage_id, "exitCode": code})
        print(f"[{stage_id}] exit {code}")

        if code == 1 or code == 3:
            overall = code
            break
        if code == 2:
            overall = 2  # ledgered incompleteness: keep going, report at end

    log_util.write_pipeline_meta(extracted_root, {
        "lastRunAt": log_util.utc_now_iso(),
        "gameDir": str(game_root),
        "extractedRoot": str(extracted_root),
        "packDir": str(pack_dir),
        "selectedStages": selected,
        "executed": executed,
        "overallExit": overall,
    })
    return overall


if __name__ == "__main__":
    sys.exit(main())
