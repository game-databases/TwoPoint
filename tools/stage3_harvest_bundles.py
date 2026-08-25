#!/usr/bin/env python3
"""Stage 3 — harvest-bundles.

Raw asset export over ALL roster bundles (158 aa + 18 DLC), grouped by
bundle family. Media carve-out [DR-2026-08-18-media-scope] + arbiter-001 R1:
Texture2D/Sprite are CATALOGUE-ONLY in piece 1 and audio/video/mesh/
animation/shader/font land as catalogue rows — ZERO decoded media bytes
under extracted/. Icon/sprite byte export is an owner pick taken on
MEDIA-CATALOGUE after piece 1; the AssetStudioModCLI cross-check stays
dormant until that pass.

Fallback-version seeding (Revision 4): content bundles' UnityFS headers read
literally `0.0.0` (catalog.bundle alone reports the true engine version), so
before every open the stage seeds UnityPy's FALLBACK_UNITY_VERSION from
identity.json's unityVersion when the header is 0.0.0/unparseable, marks the
bundle census `fallbackVersionUsed:true` and totals the usage in the run
section.

Bundle identity is embedded in EVERY harvest filename
(`<bundle-stem>_<signed-int64 pathId>` — path_ids are int64 and NEGATIVE on
this client, Revision 6): path_ids are unique only WITHIN a bundle while
families span bundles. Stage 5's loaders and checkers parse the sign via
tpc_common.parse_harvest_stem.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
from collections import Counter
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import aa_catalog
import log_util
import tpc_common as tc
import unitypy_util as uu

EXPORT_CLASSES = {"TextAsset", "MonoBehaviour"}
_UNSAFE_CHARS_RE = re.compile(r'[<>:"|?*\x00-\x1f]')
_EXT_RE = re.compile(r"\.[A-Za-z0-9]{1,5}$")


def _safe(seg: str) -> str:
    return _UNSAFE_CHARS_RE.sub("_", seg)


def _textasset_bytes(value) -> bytes:
    if isinstance(value, str):
        return value.encode("utf-8")
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    return str(value).encode("utf-8")


def _name_ext(asset_name: str, fallback: str) -> str:
    if asset_name and _EXT_RE.search(asset_name):
        return _EXT_RE.search(asset_name).group(0)
    return fallback


# ---------------------------------------------------------------------------
# Mechanical acceptance math (pure functions over the stage's own row shapes)

def reconcile_counts(censuses, manifest_rows, catalogue_rows) -> tuple[bool, list[str]]:
    """Σ objectsByClass over per-bundle censuses == export-manifest rows +
    media-catalogue rows + error rows + census-only residual (classes neither
    exported nor carved out — GameObject/Transform/manager plumbing).
    Returns (ok, problem messages)."""
    class_totals: dict[str, int] = {}
    error_total = 0
    for c in censuses:
        for cls_name, n in (c.get("objectsByClass") or {}).items():
            class_totals[cls_name] = class_totals.get(cls_name, 0) + n
        error_total += len(c.get("errors") or [])
    census_objects = sum(class_totals.values())
    accounted = len(manifest_rows) + len(catalogue_rows) + error_total
    residual = sum(n for cls_name, n in class_totals.items()
                   if cls_name not in EXPORT_CLASSES
                   and cls_name not in tc.CARVE_OUT_CLASSES)
    if census_objects != accounted + residual:
        return False, [f"census reconciliation failed: {census_objects} objects "
                       f"vs {accounted}+{residual} accounted"]
    return True, []


def check_carveout_completeness(censuses, catalogue_rows) -> tuple[bool, list[str]]:
    """Every carved-out class's census count must equal its media-catalogue
    row count. Returns (ok, problem messages)."""
    carved_class_totals: dict[str, int] = {}
    for c in censuses:
        for cls_name, n in (c.get("objectsByClass") or {}).items():
            if cls_name in tc.CARVE_OUT_CLASSES:
                carved_class_totals[cls_name] = \
                    carved_class_totals.get(cls_name, 0) + n
    problems: list[str] = []
    for cls_name in sorted(tc.CARVE_OUT_CLASSES):
        want = carved_class_totals.get(cls_name, 0)
        got = sum(1 for r in catalogue_rows if r["class"] == cls_name)
        if want != got:
            problems.append(f"carve-out completeness failed for {cls_name}: "
                            f"census={want} catalogue={got}")
    return (not problems), problems


def run(game_root: Path, extracted_root: Path,
        only_relpaths: list[str] | None = None) -> int:
    roster = tc.load_roster(extracted_root)
    if only_relpaths is not None:
        wanted = set(only_relpaths)
        roster = [r for r in roster if r["relpath"] in wanted]
    paths = tc.game_paths(game_root)

    build_id = None
    identity_path = extracted_root / "identity.json"
    if identity_path.is_file():
        build_id = json.loads(identity_path.read_text(encoding="utf-8")).get("buildId")

    dump_cs = extracted_root / "decompiled" / "il2cppdumper" / "dump.cs"
    index = uu.DumpCsIndex(dump_cs) if dump_cs.is_file() else None
    synth = uu.TypetreeSynthesizer(index) if index is not None else None
    UnityPy, unitypy_source = uu.ensure_unitypy()
    # Revision 4: content bundles ship `0.0.0` UnityFS headers — seed the
    # fallback version from identity.json before any open, count each use.
    seeds = uu.FallbackVersionSeeder(extracted_root, UnityPy)

    # Revision 6 fix lane: MonoBehaviour m_Script PPtrs point into SEPARATE
    # monoscript bundles, so class names resolve only through a cross-bundle
    # index built BEFORE the export pass. Phase A scans every roster bundle
    # for MonoScript objects (the seeding dedup keeps fallback counts honest);
    # phase B exports against the finished table.
    script_index = uu.MonoScriptIndex()
    for row in roster:
        abspath_a = paths["root"] / row["relpath"]
        seeds.seed_if_needed(abspath_a, row["relpath"])
        try:
            env_a = UnityPy.load(str(abspath_a))
            script_index.index_environment(env_a, row["relpath"])
            del env_a
        except Exception:  # noqa: BLE001 — phase B ledgers unreadable bundles
            continue

    # rerun convergence: the whole harvest plane is rebuilt from scratch
    harvest_dir = extracted_root / "harvest"
    if harvest_dir.exists():
        shutil.rmtree(harvest_dir)
    census_bundles_dir = harvest_dir / "census" / "bundles"
    textassets_dir = harvest_dir / "textassets"
    monobehaviours_dir = harvest_dir / "monobehaviours"
    for d in (census_bundles_dir, textassets_dir, monobehaviours_dir):
        d.mkdir(parents=True, exist_ok=True)
    for stale in ("media-catalogue.jsonl", "MEDIA-CATALOGUE.md",
                  Path("harvest") / "export-manifest.jsonl",
                  Path("harvest") / "census" / "unreadable.jsonl"):
        p = extracted_root / stale
        if p.is_file():
            p.unlink()

    manifest_rows: list[dict] = []
    catalogue_rows: list[dict] = []
    unreadable_rows: list[dict] = []
    censuses: list[dict] = []
    census_error_total = 0
    class_totals: dict[str, int] = {}
    carved_class_totals: dict[str, int] = {}
    mb_resolved = 0       # MonoBehaviours with a cross-bundle-resolved script
    mb_unresolved = 0     # m_Script PPtr unresolved → generic MonoBehaviour
    # F4 acceptance: per-decode-route counts surface in the run section so a
    # 100%-raw run is visible as such (Rev 6 note-only binding sentence)
    mb_decoded_embedded = 0   # route 1 — the bundle's own typetree
    mb_synthesized = 0        # route 2 — dump.cs synthesized typetree
    mb_residue = 0            # route 3 — raw typed dumps (typetreeDecoded:false)

    for row in roster:
        rel = row["relpath"]
        abspath = paths["root"] / rel
        bundle_name = Path(rel).name
        stem = bundle_name[:-len(".bundle")] if bundle_name.endswith(".bundle") else bundle_name
        family, axis, _hash_named = tc.split_family(bundle_name, row["dirClass"])
        seeded = seeds.seed_if_needed(abspath, rel)
        census = {"objectsByClass": {}, "bytesByClass": {}, "errors": [],
                  "fallbackVersionUsed": seeded}

        objects: list = []
        try:
            env = UnityPy.load(str(abspath))
            # UnityPy.load is LAZY: a truncated/corrupt container can parse
            # at load time and only fail (or yield nothing) here.
            for f in uu.iter_environment_files(env):
                objects.extend(uu.iter_objects_sorted(f))
        except Exception as exc:  # noqa: BLE001 — ledgered incompleteness
            unreadable_rows.append({
                "relpath": rel, "dirClass": row["dirClass"],
                "fallbackVersionUsed": seeded,
                "reason": f"{type(exc).__name__}: {exc}"})
            continue
        if not objects:
            unreadable_rows.append({
                "relpath": rel, "dirClass": row["dirClass"],
                "fallbackVersionUsed": seeded,
                "reason": "no readable serialized objects in container"})
            continue
        objects.sort(key=lambda o: o.path_id)

        for obj in objects:
            cls_name = getattr(getattr(obj, "type", None), "name", "Unknown")
            census["objectsByClass"][cls_name] = \
                census["objectsByClass"].get(cls_name, 0) + 1
            census["bytesByClass"][cls_name] = \
                census["bytesByClass"].get(cls_name, 0) + int(getattr(obj, "byte_size", 0) or 0)

            if cls_name in tc.CARVE_OUT_CLASSES:
                name = ""
                try:
                    name = getattr(obj.read(), "m_Name", "") or ""
                except Exception:  # noqa: BLE001 — catalogue keeps counting
                    pass
                catalogue_rows.append({
                    "class": cls_name,
                    "bundle": rel,
                    "name": name,
                    "pathId": obj.path_id,
                    "bytesEstimate": int(getattr(obj, "byte_size", 0) or 0),
                    "contentAxis": axis,
                })
                continue
            if cls_name not in EXPORT_CLASSES:
                continue  # census-only plumbing (GameObject/Transform/…)
            try:
                if cls_name == "TextAsset":
                    asset = obj.read()
                    raw = _textasset_bytes(getattr(asset, "m_Script", ""))
                    ext = _name_ext(getattr(asset, "m_Name", ""), ".txt")
                    fname = _safe(f"{stem}_{obj.path_id}{ext}")
                    out_path = textassets_dir / _safe(family) / fname
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    log_util.atomic_write_bytes(out_path, raw)
                    manifest_rows.append({
                        "sourceBundle": rel, "pathId": obj.path_id,
                        "class": cls_name,
                        "outRelPath": out_path.relative_to(extracted_root).as_posix(),
                        "bytes": len(raw)})
                else:
                    payload, decoded, method = uu.decode_monobehaviour(
                        obj, synth, script_index=script_index)
                    if method == "embedded-typetree":
                        mb_decoded_embedded += 1
                    elif decoded:
                        mb_synthesized += 1
                    else:
                        mb_residue += 1
                    script_class = payload.get("_scriptClass") or "MonoBehaviour"
                    if script_class != "MonoBehaviour":
                        mb_resolved += 1
                    else:
                        mb_unresolved += 1
                    payload["_scriptClass"] = script_class
                    out_path = (monobehaviours_dir / _safe(family)
                                / _safe(script_class)
                                / _safe(f"{stem}_{obj.path_id}.json"))
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    log_util.write_json(out_path, payload)
                    manifest_rows.append({
                        "sourceBundle": rel, "pathId": obj.path_id,
                        "class": script_class,
                        "outRelPath": out_path.relative_to(extracted_root).as_posix(),
                        "bytes": int(getattr(obj, "byte_size", 0) or 0)})
            except Exception as exc:  # noqa: BLE001 — census errors stay loud
                census["errors"].append(
                    f"pathId {obj.path_id} [{cls_name}]: "
                    f"{type(exc).__name__}: {exc}")

        census_error_total += len(census["errors"])
        for cls_name, n in census["objectsByClass"].items():
            class_totals[cls_name] = class_totals.get(cls_name, 0) + n
            if cls_name in tc.CARVE_OUT_CLASSES:
                carved_class_totals[cls_name] = \
                    carved_class_totals.get(cls_name, 0) + n
        log_util.write_json(census_bundles_dir / (_safe(bundle_name) + ".json"),
                            census)
        censuses.append(census)

    # -- ledgers -----------------------------------------------------------------
    unreadable_rows.sort(key=lambda r: r["relpath"])
    log_util.write_jsonl(harvest_dir / "census" / "unreadable.jsonl",
                         unreadable_rows)
    manifest_rows.sort(key=lambda r: r["outRelPath"])
    log_util.write_jsonl(harvest_dir / "export-manifest.jsonl", manifest_rows)
    catalogue_rows.sort(key=lambda r: (r["bundle"], r["pathId"]))
    log_util.write_jsonl(extracted_root / "media-catalogue.jsonl", catalogue_rows)

    _write_media_rollup(extracted_root, catalogue_rows, build_id, unitypy_source)

    # -- mechanical acceptance checks ---------------------------------------------
    problems: list[str] = []

    out_paths = [r["outRelPath"] for r in manifest_rows]
    duplicates = {p for p, n in Counter(out_paths).items() if n > 1}
    if duplicates:
        problems.append(f"duplicate outRelPath values: {sorted(duplicates)[:5]}")

    # log-line scalars (the acceptance helpers re-derive these from the
    # per-bundle censuses for the comparisons below)
    census_objects = sum(class_totals.values())
    accounted = (len(manifest_rows) + len(catalogue_rows) + census_error_total)
    residual = sum(n for cls_name, n in class_totals.items()
                   if cls_name not in EXPORT_CLASSES
                   and cls_name not in tc.CARVE_OUT_CLASSES)

    _ok, recon_problems = reconcile_counts(censuses, manifest_rows,
                                           catalogue_rows)
    problems.extend(recon_problems)

    _ok, carve_problems = check_carveout_completeness(censuses, catalogue_rows)
    problems.extend(carve_problems)

    lines = [
        "- exitCode: 0" if not problems and not unreadable_rows else
        ("- exitCode: 2 (completed-with-ledger)" if not problems else
         f"- exitCode: 1 ({'; '.join(problems)})"),
        f"- unitypySource: {unitypy_source}",
        f"- bundlesAttempted: {len(roster)}; unreadableBundles: "
        f"{len(unreadable_rows)}",
        f"- censusObjectsTotal: {census_objects}; exports: {len(manifest_rows)}; "
        f"catalogueRows: {len(catalogue_rows)}; objectErrors: "
        f"{census_error_total}; censusOnlyResidual: {residual}",
        f"- carvedClassCensus: {dict(sorted(carved_class_totals.items()))}",
        f"- monoScriptIndex: {script_index.stats()}; monobehaviourScriptClass: "
        f"resolved={mb_resolved} unresolved(generic)={mb_unresolved}; "
        f"decodeRoutes: embedded={mb_decoded_embedded} "
        f"synthesis={mb_synthesized} residue={mb_residue}",
        f"- {seeds.run_section_note(len(roster))}",
    ]
    lines += [f"- PROBLEM: {p}" for p in problems]
    log_util.append_run_section(extracted_root, "harvest-bundles", lines)

    print(f"[harvest-bundles] bundles={len(roster)} "
          f"unreadable={len(unreadable_rows)} exports={len(manifest_rows)} "
          f"catalogue={len(catalogue_rows)} objectErrors={census_error_total} "
          f"fallbackVersioned={seeds.seeded_count} "
          f"mbScriptResolved={mb_resolved}/{mb_resolved + mb_unresolved} "
          f"decodeRoutes=embedded:{mb_decoded_embedded}"
          f"/synthesis:{mb_synthesized}/residue:{mb_residue}")
    for p in problems:
        print(f"[harvest-bundles] PROBLEM: {p}", file=sys.stderr)
    if problems:
        return 1
    if unreadable_rows or census_error_total:
        return 2
    return 0


def _write_media_rollup(extracted_root: Path, rows: list[dict],
                        build_id, unitypy_source: str) -> None:
    per_class: dict[str, dict] = {}
    per_family: dict[str, dict] = {}
    family_axis: dict[str, str] = {}
    for r in rows:
        c = per_class.setdefault(r["class"], {"count": 0, "bytes": 0})
        c["count"] += 1
        c["bytes"] += r["bytesEstimate"]
        fam, axis, _hn = tc.split_family(Path(r["bundle"]).name, r["contentAxis"])
        family_axis[fam] = axis
        f = per_family.setdefault(fam, {"count": 0, "bytes": 0})
        f["count"] += 1
        f["bytes"] += r["bytesEstimate"]

    lines = [
        "# Media Catalogue",
        "",
        f"- buildId: {build_id}",
        f"- unitypySource: {unitypy_source}",
        "- scope: catalogue-only rows ([DR-2026-08-18-media-scope]; "
        "arbiter-001 R1 lane) — textures AND audio/video/mesh/animation/"
        "shader/font. Zero decoded media bytes live under extracted/ in "
        "piece 1.",
        f"- totalRows: {len(rows)}; totalBytesEstimate: "
        f"{sum(r['bytesEstimate'] for r in rows)}",
        "",
        "## Per class",
        "",
        "| class | objects | bytesEstimate |",
        "|---|---|---|",
    ]
    for cls in sorted(per_class):
        v = per_class[cls]
        lines.append(f"| {cls} | {v['count']} | {v['bytes']} |")
    lines += ["", "## Per family", "",
              "| family | contentAxis | objects | bytesEstimate |",
              "|---|---|---|---|"]
    for fam in sorted(per_family):
        v = per_family[fam]
        lines.append(f"| {fam} | {family_axis[fam]} | {v['count']} | {v['bytes']} |")
    log_util.atomic_write_text(extracted_root / "MEDIA-CATALOGUE.md",
                               "\n".join(lines) + "\n")


def main(argv=None) -> int:
    log_util.bootstrap_console()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("game_dir", nargs="?", default=None)
    parser.add_argument("--extracted-root", default=None)
    args = parser.parse_args(argv)
    try:
        pack_dir = tc.resolve_pack_dir()
        root = tc.resolve_extracted_root(pack_dir)
        if args.extracted_root:
            root = Path(args.extracted_root).resolve()
        game_root = tc.resolve_game_root(args.game_dir)
        return run(game_root, root)
    except aa_catalog.CatalogDecodeError as exc:
        print(f"[harvest-bundles] DECODE FAILURE: {exc}", file=sys.stderr)
        return 1
    except tc.StageError as exc:
        print(f"[harvest-bundles] ERROR: {exc}", file=sys.stderr)
        return exc.exit_code


if __name__ == "__main__":
    sys.exit(main())
