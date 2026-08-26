#!/usr/bin/env python3
"""Stage 0 — verify-client.

Pins install identity, gates the dumper choice against the measured IL2CPP
metadata version, emits the bundle roster (the pipeline's first artifact)
and seeds extracted/EXTRACTION-LOG.md + the §4 directory skeleton when
absent. Read-only against the game client.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import log_util
import tpc_common as tc


SKELETON_PLACEHOLDERS: dict[str, str] = {
    "VALIDATION-REPORT.md": (
        "# Validation Report — PIECE-1 PLACEHOLDER\n\n"
        "Derived mechanically in a later piece from the stage censuses "
        "(stage censuses live beside this file: `harvest/census/`, "
        "`addressables/catalog-coverage.json`, `locales/locale-matrix.json`, "
        "`stubs/_absences.jsonl`). This placeholder only fixes the path "
        "contract.\n"),
    "PROOF.md": (
        "# PROOF — PLACEHOLDER POINTER ONLY\n\n"
        "Completeness is proven, not claimed (extraction-doctrine Principle "
        "two). A later piece reconciles coverage and writes the real proof "
        "here; piece 1 only pins this path.\n"),
    "RELATIONS.md": (
        "# Relations — PLACEHOLDER POINTER ONLY\n\n"
        "A later piece catalogs every relation, mechanism and coverage gap "
        "here ([DR-2026-08-17-relink]). Piece 1 ships only "
        "`relinks/locale_availability.jsonl`, owned since the piece-07 §5 "
        "amendment solely by stage 9 `locale-proof` (arbiter-piece07 R4).\n"),
    "protocol/README.md": (
        "# Protocol layer — observed surface (single-player inventory)\n\n"
        "No gameplay client↔server plane exists. The owed protocol section "
        "inventories what the shipped plugins expose:\n\n"
        "- `steam_api64` — Steamworks achievements / DLC checks / overlay / "
        "cloud-saves\n"
        "- `BacktraceCrashpad` (`BacktraceCrashpadWindows.dll` + "
        "`crashpad_handler`) — crash telemetry\n"
        "- NVIDIA Ansel capture (`AnselPlugin64` / `AnselSDK64`)\n\n"
        "Inventory + no-surface proof land here in a later piece; piece 1 "
        "fixes the directory contract only.\n"),
    "logic/.gitkeep": "",
    "maps/.gitkeep": "",
}


def _read_manifest(paths: dict) -> dict:
    manifest = tc.find_appmanifest(paths["root"])
    if manifest is None:
        raise tc.StageError(
            "appmanifest_1649080.acf not found walking up <=4 levels from "
            f"{paths['root']}", exit_code=3)
    acf = tc.parse_acf(manifest.read_text(encoding="utf-8", errors="replace"))
    app = acf.get("AppState", {}) or {}
    buildid = app.get("buildid")
    target = app.get("TargetBuildID")

    def find_first(node: dict, key: str):
        """First occurrence of `key` anywhere in the ACF tree (`language`
        appears twice — install setting, not a capability row)."""
        if isinstance(node, dict):
            if key in node:
                return node[key]
            for v in node.values():
                found = find_first(v, key)
                if found is not None:
                    return found
        return None

    language = find_first(acf, "language")
    if buildid is None or target is None:
        raise tc.StageError(
            f"{manifest.name} lacks buildid/TargetBuildID", exit_code=3)
    return {"path": manifest, "buildId": int(buildid), "targetBuildId": int(target),
            "languageSetting": language or ""}


def run(game_root: Path, extracted_root: Path) -> int:
    paths = tc.game_paths(game_root)

    # -- inputs present + readable (exit 3 otherwise) ------------------------
    required = [paths["game_assembly"], paths["metadata"],
                paths["globalgamemanagers"], paths["version_txt"],
                paths["aa"], paths["aa_bundles"]]
    for p in required:
        if not p.exists():
            raise tc.StageError(f"missing required input: {p}", exit_code=3)
    for d in (paths["dlc_space"], paths["dlc_ghost"]):
        if not d.is_dir():
            raise tc.StageError(f"missing required DLC dir: {d}", exit_code=3)

    manifest = _read_manifest(paths)
    version_string = paths["version_txt"].read_text(encoding="utf-8",
                                                    errors="replace").strip()
    unity_version = tc.read_unity_version(paths["globalgamemanagers"])
    sanity, metadata_version = tc.read_metadata_header(paths["metadata"])
    if sanity != tc.METADATA_SANITY:
        raise tc.StageError(
            f"unexpected metadata sanity word {sanity:#010x} "
            f"(expected {tc.METADATA_SANITY:#010x}) — not a readable IL2CPP "
            "metadata file", exit_code=3)

    settings = {}
    if paths["settings_json"].is_file():
        try:
            settings = __import__("json").loads(
                paths["settings_json"].read_text(encoding="utf-8"))
        except ValueError:
            settings = {}

    # -- dumper gate ----------------------------------------------------------
    if metadata_version >= tc.METADATA_VERSION_WALL:
        raise tc.StageError(tc.CPP2IL_ESCALATION_MESSAGE, exit_code=3)
    dumper = "il2cppdumper"

    # -- roster -----------------------------------------------------------------
    bundles = tc.enumerate_bundle_files(paths)
    roster_rows = []
    for rel, cls, abspath in bundles:
        name = Path(rel).name
        roster_rows.append({
            "relpath": rel,
            "dirClass": cls,
            "bytes": abspath.stat().st_size,
            "sceneFlag": tc.scene_flag_for(name),
            "localeFlag": tc.locale_for_bundle(name),
            "buildId": manifest["buildId"],
        })
    assert len(roster_rows) == len(bundles), "roster row count != enumeration"

    # live counts per dirClass; the spec's expectedBundles pins 'aa' for the
    # base axis — compare through the alias below
    live_by_class = {k: 0 for k in tc.DIR_CLASSES}
    for row in roster_rows:
        live_by_class[row["dirClass"]] += 1
    live_counts = {"aa": live_by_class[tc.AXIS_BASE],
                   "dlc-space": live_by_class[tc.AXIS_DLC_SPACE],
                   "dlc-ghost": live_by_class[tc.AXIS_DLC_GHOST]}
    locale_rows = tc.roster_locale_rows(roster_rows)

    # acceptance: when the full set of named localisation bundles is present,
    # their resolved flags MUST equal exactly EMITTED_LOCALES — same failure
    # class as the row-count acceptance (exit 1), so flag corruption (e.g. a
    # suffix-separator mismatch surfacing as `unknown:_english`) can never
    # pass a count-only check again.
    named_locale_rows = [r for r in roster_rows
                         if r["localeFlag"] not in (None, tc.BASE_OVERLAY_NAME)]
    if len(named_locale_rows) >= len(tc.EMITTED_LOCALES):
        resolved_flags = sorted({r["localeFlag"] for r in named_locale_rows})
        expected_flags = sorted(tc.EMITTED_LOCALES)
        if resolved_flags != expected_flags:
            offending = [f"{r['relpath']} -> {r['localeFlag']!r}"
                         for r in named_locale_rows
                         if r["localeFlag"] not in tc.EMITTED_LOCALES]
            unresolved = [loc for loc in tc.EMITTED_LOCALES
                          if loc not in resolved_flags]
            raise tc.StageError(
                "localisation bundle localeFlags do not resolve to exactly "
                f"EMITTED_LOCALES {expected_flags}; offending rows: "
                f"{offending}; unresolved locales: {unresolved}", exit_code=1)
    strict_base = sum(1 for r in roster_rows
                      if r["dirClass"] == "base" and r["sceneFlag"] == ".unity")
    seasonal_base = sum(1 for r in roster_rows
                        if r["dirClass"] == "base"
                        and r["sceneFlag"] == "seasonal-scenes")
    strict_install = sum(1 for r in roster_rows if r["sceneFlag"] == ".unity")
    scene_carrying_install = strict_install + sum(
        1 for r in roster_rows if r["sceneFlag"] == "seasonal-scenes")

    identity = {
        "appid": tc.APPID,
        "buildId": manifest["buildId"],
        "targetBuildId": manifest["targetBuildId"],
        "versionString": version_string,
        "unityVersion": unity_version,
        "metadataVersion": metadata_version,
        "dumper": dumper,
        "addressablesVersion": settings.get("m_AddressablesVersion"),
        "settingsHash": settings.get("m_SettingsHash"),
        "languageSetting": manifest["languageSetting"],
        "expectedBundles": dict(tc.EXPECTED_BUNDLES),
        "localeBundleCount": tc.EXPECTED_LOCALE_ROWS,
        "sceneCounts": {
            "strictUnityBase": strict_base,
            "seasonalSceneCarryingBase": strict_base + seasonal_base,
            "strictUnityInstall": strict_install,
            "sceneCarryingInstall": scene_carrying_install,
        },
    }

    # -- outputs ---------------------------------------------------------------
    extracted_root.mkdir(parents=True, exist_ok=True)
    log_util.write_json(extracted_root / "identity.json", identity)
    log_util.write_jsonl(extracted_root / "bundle-roster.jsonl", roster_rows)
    for rel, body in SKELETON_PLACEHOLDERS.items():
        log_util.atomic_write_text(extracted_root / rel, body)

    seeded = log_util.seed_extraction_log(
        extracted_root,
        header_pins={
            "appid": tc.APPID,
            "buildId": identity["buildId"],
            "targetBuildId": identity["targetBuildId"],
            "versionString": version_string,
            "unityVersion": unity_version,
            "metadataVersion": metadata_version,
        },
        defaults={
            "il2cppdumper": {"candidates": list(tc.IL2CPP_DUMPER_CANDIDATES)},
            "unitypyVersion": tc.UNITYPY_PIN,
        })

    # -- drift lines (warnings, never failures) --------------------------------
    drift = []
    for axis, live in live_counts.items():
        exp = tc.EXPECTED_BUNDLES.get(axis)
        if live != exp:
            drift.append(f"DRIFT: {axis} bundle count live={live} expected={exp}")
    if len(locale_rows) != tc.EXPECTED_LOCALE_ROWS:
        drift.append(f"DRIFT: localisation bundles live={len(locale_rows)} "
                     f"expected={tc.EXPECTED_LOCALE_ROWS}")
    expected_scenes = {"strictUnityBase": 21, "seasonalSceneCarryingBase": 22,
                       "strictUnityInstall": 25, "sceneCarryingInstall": 26}
    for key, exp in expected_scenes.items():
        live = identity["sceneCounts"][key]
        if live != exp:
            drift.append(f"DRIFT: sceneCounts.{key} live={live} expected={exp}")
    if manifest["buildId"] != manifest["targetBuildId"]:
        drift.append(f"DRIFT: patched install — buildid={manifest['buildId']} "
                     f"TargetBuildID={manifest['targetBuildId']}")

    lines = [
        f"- exitCode: 0",
        f"- buildId: {identity['buildId']} (TargetBuildID "
        f"{identity['targetBuildId']})",
        f"- metadataVersion: {metadata_version}; dumper: {dumper}",
        f"- unityVersion: {unity_version}; versionString: `{version_string}`",
        f"- addressablesVersion: {identity['addressablesVersion']}; "
        f"settingsHash: {identity['settingsHash']}",
        f"- rosterRows: {len(roster_rows)} "
        f"(by class: {sorted(live_by_class.items())}); localeFlagged: "
        f"{len(locale_rows)}",
        f"- sceneCounts: {identity['sceneCounts']}",
        f"- extractionLogSeeded: {seeded}",
    ]
    lines += [f"- {d}" for d in drift]
    log_util.append_run_section(extracted_root, "verify-client", lines)

    print(f"[verify-client] buildId={identity['buildId']} "
          f"bundles={len(roster_rows)} localeFlagged={len(locale_rows)} "
          f"scenes={identity['sceneCounts']['sceneCarryingInstall']} "
          f"log_seeded={seeded}")
    for d in drift:
        print(d)
    return 0


def main(argv=None) -> int:
    log_util.bootstrap_console()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("game_dir", nargs="?",
                        help="install root (or TPC_Data child); default $TPC_GAME_DIR")
    parser.add_argument("--extracted-root", default=None,
                        help="override the extraction root ($TPC_EXTRACTED_ROOT)")
    args = parser.parse_args(argv)

    try:
        pack_dir = tc.resolve_pack_dir()
        root = tc.resolve_extracted_root(pack_dir)
        if args.extracted_root:
            root = Path(args.extracted_root).resolve()
        game_root = tc.resolve_game_root(args.game_dir)
        return run(game_root, root)
    except tc.StageError as exc:
        log_util.append_failure_section(root, "verify-client", exc.exit_code,
                                        [str(exc)])
        print(f"[verify-client] ERROR: {exc}", file=sys.stderr)
        return exc.exit_code
    except OSError as exc:
        log_util.append_failure_section(root, "verify-client", 3,
                                        [f"environment error: {exc}"])
        print(f"[verify-client] environment error: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
