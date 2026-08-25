#!/usr/bin/env python3
"""Stage 6 — relink (piece-02).

Derives the complete ordered-pair relation matrix over the 10-node universe
(9 stub kinds + scene) plus every extended relation family the client data
carries, deterministically and from committed artifacts:

  R1 bridges        — cab_index.jsonl + container_index.jsonl (identity
                      passes over the roster bundles; first emitters of the
                      CAB→bundle/object mapping, scout gap F11)
  R2 matrix + pairs — PPtr walker over stub payloads → <src>_<dst>.jsonl
                      pair datasets, scene attribution, cross-file
                      resolution through externals + cab index,
                      _unresolved_pptrs.jsonl ledger
  R3 GUID bridge    — entity_asset_guid.jsonl, GUID-resolved second rows
                      into kind-pair files, guid_bridge_report.json,
                      _dangling_guids.jsonl
  R4 locale join v2 — i2_term_registry.jsonl, entity_locale.jsonl (the
                      AUTHORITATIVE entity-granular locale relation),
                      locale_term_entity.jsonl, locale_join_report.json.
                      Stage 5 KEEPS sole ownership of
                      locale_availability.jsonl — this stage never writes it.
  R5 UI-link map    — ui_link_coverage.jsonl (bar 2)
  R6 competitor     — consumes data/sources/competitor/<id>/model.jsonl
                      bytes deterministically; overlays + application
                      ledger (bar 3). Absent inputs read FLOOR-UNMET,
                      never exit 3.
  R7 assembly       — matrix.json (100 cells) + regenerated RELATIONS.md

Exit codes (piece-1 contract verbatim): 0 all 100 cells shipped AND no
unresolved-open dangling GUIDs AND registryMisses == 0 AND competitor floor
met · 1 schema/validation failure · 2 completed-with-ledger (EXPECTED
steady state until the ledgers close) · 3 environment/gate refusal.

Determinism: byte-identical reruns (EXTRACTION-LOG/.stage-stamps/
.pipeline-meta excluded); UTF-8 + LF everywhere; atomic renames.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import log_util
import relink_util as ru
import tpc_common as tc
import unitypy_util as uu

# Piece-02 §3 pins relink_util as stage 6's shared helper layer; re-export
# the seam vocabulary here so consumers resolving THIS stage module (the
# suite's impl adapter loads stage scripts by name) see the whole surface.
from relink_util import (  # noqa: E402,F401
    assemble_matrix,
    build_cab_index,
    build_container_index,
    build_i2_term_registry,
    emit_entity_locale,
    render_relations_md,
    resolve_cross_file,
    run_guid_bridge,
    walk_pptr_refs,
)

I2_SOURCE_DIR = ("harvest/monobehaviours/localisation_assets_localisation/"
                 "I2.Loc.LanguageSourceAsset")

# Scout-time reconciliation seeds (piece-02 §2 facts F7/F8/F9). Drift prints
# a DRIFT: line and the fresh numbers win — never a silent stale constant.
F7_ROWS, F7_KEYS = 15_675, 15_672
F8_KNOWN_UNRESOLVED_IDS = 5
F9_REFS, F9_DISTINCT, F9_DANGLING = 20_042, 5_548, 1_137

SCENE_SRC_UNBLOCK = ru.SCENE_SRC_UNBLOCK
PROBE_UNLOCKABLE_LEVEL_UNBLOCK = (
    "probe cell: scanned unlockable payloads for Levels[] / LevelFilters / "
    "level-name segments matching campus-level ids — no measured carrier on "
    "this corpus; re-check after cross-file PPtr resolution growth")
PROBE_METAGAME_COURSE_TMPL = (
    "needs-probe cell: .references.NNNN.data.Course PPtrs resolve through "
    "the R1 bridges; {dangling} still dangle against non-stub (scene/"
    "prefab-resident) objects — owner: scene-dump walk (maps piece)")


# ---------------------------------------------------------------------------
# Input loading

def load_catalog_guid_index(catalog_path: Path) -> dict[str, list[dict]]:
    """catalog-GUID→address index: keys with kind == 'guid' →
    guid → [{address, bundle}] (duplicate-guid keys are legal Addressables
    and ship as a list; bundle may be null — address-only resolution then)."""
    data = json.loads(catalog_path.read_text(encoding="utf-8"))
    index: dict[str, list[dict]] = {}
    for key in data.get("keys") or []:
        if key.get("kind") != "guid":
            continue
        index.setdefault(str(key["key"]), []).append({
            "address": key.get("address"),
            "bundle": key.get("bundle"),
        })
    for rows in index.values():
        rows.sort(key=lambda r: (str(r.get("address")),
                                 str(r.get("bundle"))))
    return index


def load_manifest_class_counts(manifest_path: Path) -> Counter:
    counts: Counter = Counter()
    with open(manifest_path, "r", encoding="utf-8", newline="\n") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            counts[json.loads(line)["class"]] += 1
    return counts


# ---------------------------------------------------------------------------
# Sub-passes

def run_bridges(game_root: Path, extracted_root: Path, roster: list[dict],
                build_id) -> tuple[ru.BridgeIndexes, list[str]]:
    """R1 — two identity passes' worth of metadata in ONE light pass over
    every roster bundle (same fallback-version seeding as stage 3). Emits
    bridges/cab_index.jsonl + bridges/container_index.jsonl streamed in
    sorted order."""
    UnityPy, _unitypy_source = uu.ensure_unitypy()
    seeds = uu.FallbackVersionSeeder(extracted_root, UnityPy)
    paths = tc.game_paths(game_root)
    bridges = ru.BridgeIndexes(build_id)
    cab_out = extracted_root / "relinks" / "bridges" / "cab_index.jsonl"
    cont_out = extracted_root / "relinks" / "bridges" / "container_index.jsonl"

    def _stream(path):
        import os
        import tempfile
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp",
                                   dir=str(path.parent))
        fh = os.fdopen(fd, "w", encoding="utf-8", newline="\n")
        return tmp, fh

    tmp_c, fh_c = _stream(cab_out)
    tmp_k, fh_k = _stream(cont_out)
    # Emitted `bundle` values are bare filenames (the piece-02 evidence
    # spelling; basenames are unique across the roster), so the pass visits
    # bundles in BASENAME order — per-bundle sorted appends then keep both
    # files globally sorted by their pinned (bundle, cab) / (bundle, address)
    # keys without buffering the ~2M-object index in memory.
    ordered_roster = sorted(
        roster, key=lambda r: ru.bundle_base(r["relpath"]))
    try:
        for row in ordered_roster:
            rel = row["relpath"]
            abspath = paths["root"] / rel
            seeded = seeds.seed_if_needed(abspath, rel)
            try:
                env = UnityPy.load(str(abspath))
            except Exception as exc:  # noqa: BLE001 — ledgered incompleteness
                bridges.unreadable.append(
                    (rel, f"{type(exc).__name__}: {exc}"))
                continue
            cab_objects = []
            container_entries = []
            for f in uu.iter_environment_files(env):
                if getattr(f, "is_dependency", False):
                    continue
                objs = []
                for o in uu.iter_objects_sorted(f):
                    cls = getattr(getattr(o, "type", None), "name", "Unknown")
                    objs.append((int(o.path_id), str(cls)))
                cab_objects.append(((getattr(f, "name", "") or ""),
                                    objs))
                container_entries.extend(ru.extract_container_entries(f))
            cab_rows, cont_rows = bridges.add_bundle(
                rel, cab_objects, container_entries, seeded)
            for r in cab_rows:
                fh_c.write(log_util.dump_jsonl_row(r) + "\n")
            for r in cont_rows:
                fh_k.write(log_util.dump_jsonl_row(r) + "\n")
            del env
        fh_c.close()
        fh_k.close()
        os_posix_replace(tmp_c, cab_out)
        os_posix_replace(tmp_k, cont_out)
    except BaseException:
        for fh in (fh_c, fh_k):
            try:
                fh.close()
            except OSError:
                pass
        for tmp in (tmp_c, tmp_k):
            try:
                import os
                os.unlink(tmp)
            except OSError:
                pass
        raise
    note = seeds.run_section_note(len(roster)) \
        + f"; unitypyVersion: {getattr(UnityPy, '__version__', 'unknown')}"
    return bridges, [note]


def os_posix_replace(tmp: str, final: Path) -> None:
    import os
    os.replace(tmp, str(final))


def walk_stub_payloads(stubs: ru.StubIndex, bridges: ru.BridgeIndexes,
                       resolver: ru.CrossFileResolver, build_id):
    """R2 walkers. Returns (edges, unresolved_rows, counters, raw_by_cell).
    Raw refs counted per resolved cell feed evidence.topFields; unresolved
    refs land only in the ledger + per-sourceKind counters."""
    edges = ru.EdgeAccumulator(build_id=build_id)
    unresolved: list[dict] = []
    raw_by_cell: dict[tuple[str, str], Counter] = {}
    c = {"sameFileResolved": 0, "crossFileResolved": 0,
         "sceneAttributedEdges": 0, "unresolvedCrossFile": 0,
         "builtinExternalsSkipped": 0, "twinEndpointEdges": 0,
         "unresolvedSameFile": 0}

    def _count_raw(cell, fp):
        raw_by_cell.setdefault(cell, Counter())[fp] += 1

    for kind in ru.STUB_KINDS:
        for row in sorted(stubs.rows_by_kind[kind], key=lambda r: str(r["id"])):
            src_id = str(row["id"])
            src = row.get("source") or {}
            bundle = str(src.get("bundle"))
            src_pid = int(src.get("pathId"))
            src_cab = bridges.cab_of(bundle, src_pid)
            fields = row.get("fields") or {}
            for _leaf_key, raw_path, fid, pid in ru.walk_pptr_leaves(fields):
                fp = ru.normalize_field_path(raw_path)
                if fid == 0:
                    target = resolver.same_file_target(bundle, pid)
                    if target is None:
                        c["unresolvedSameFile"] += 1
                        unresolved.append({
                            "srcKind": kind, "srcId": src_id,
                            "fieldPath": fp, "extFileId": 0, "extPath": "",
                            "m_PathID": pid,
                            "reason": "same-file pathId is not an emitted "
                                      "stub entity and the bundle carries "
                                      "no scene flag",
                            "buildId": build_id})
                        continue
                    dst_kind = target["kind"] if target["status"] == "stub" \
                        else ru.SCENE_NODE
                    dst_id = target["id"] if target["status"] == "stub" \
                        else target["relpath"]
                    evidence = {"fieldPath": fp,
                                "srcBundle": ru.bundle_base(bundle),
                                "srcPathId": src_pid,
                                "dstBundle": ru.bundle_base(bundle),
                                "dstPathId": pid}
                    edges.add(kind, src_id, dst_kind, dst_id,
                              ru.METHOD_PTR_SAME, fp, evidence, False)
                    _count_raw((kind, dst_kind), fp)
                    c["sameFileResolved"] += 1
                    if target["status"] == "scene":
                        c["sceneAttributedEdges"] += 1
                    if "@" in src_id or "@" in dst_id:
                        c["twinEndpointEdges"] += 1
                else:
                    out = resolver.resolve(bundle, src_cab, fid, pid)
                    if out["status"] == "stub":
                        evidence = {"fieldPath": fp,
                                    "srcBundle": ru.bundle_base(bundle),
                                    "srcPathId": src_pid,
                                    "dstBundle": ru.bundle_base(out["bundle"]),
                                    "dstPathId": pid,
                                    "extFileId": fid, "dstCab": out["cab"],
                                    "resolvedVia": ru.RESOLVED_VIA_BRIDGE}
                        edges.add(kind, src_id, out["kind"], out["id"],
                                  ru.METHOD_PTR_CROSS, fp, evidence, False)
                        _count_raw((kind, out["kind"]), fp)
                        c["crossFileResolved"] += 1
                        if "@" in src_id or "@" in out["id"]:
                            c["twinEndpointEdges"] += 1
                    elif out["status"] == "scene":
                        evidence = {"fieldPath": fp,
                                    "srcBundle": ru.bundle_base(bundle),
                                    "srcPathId": src_pid,
                                    "dstBundle": ru.bundle_base(out["bundle"]),
                                    "dstPathId": pid,
                                    "extFileId": fid, "dstCab": out["cab"],
                                    "resolvedVia": ru.RESOLVED_VIA_BRIDGE}
                        edges.add(kind, src_id, ru.SCENE_NODE,
                                  out["relpath"], ru.METHOD_PTR_CROSS, fp,
                                  evidence, False)
                        _count_raw((kind, ru.SCENE_NODE), fp)
                        c["crossFileResolved"] += 1
                        c["sceneAttributedEdges"] += 1
                        if "@" in src_id:
                            c["twinEndpointEdges"] += 1
                    elif out["status"] == "builtin":
                        c["builtinExternalsSkipped"] += 1
                        unresolved.append({
                            "srcKind": kind, "srcId": src_id,
                            "fieldPath": fp, "extFileId": fid,
                            "extPath": out["extPath"], "m_PathID": pid,
                            "reason": out["reason"], "buildId": build_id})
                    else:
                        c["unresolvedCrossFile"] += 1
                        unresolved.append({
                            "srcKind": kind, "srcId": src_id,
                            "fieldPath": fp, "extFileId": fid,
                            "extPath": out.get("extPath", ""),
                            "m_PathID": pid,
                            "reason": out["reason"], "buildId": build_id})
    unresolved.sort(key=lambda r: (r["srcKind"], r["srcId"], r["fieldPath"],
                                   r["extPath"], r["m_PathID"]))
    return edges, unresolved, c, raw_by_cell


def probe_unlockable_levels(stubs: ru.StubIndex, edges: ru.EdgeAccumulator,
                            raw_by_cell, counters: dict) -> int:
    """Seeded probe cell `unlockable_campus-level`: scan unlockable payloads
    for Levels[] / LevelFilters / level-name segments whose string value is
    verbatim a campus-level id. Convention-carried (inferred:true)."""
    level_ids = stubs.ids_by_kind["campus-level"]
    # matched against the NORMALIZED path (indexes collapsed) so list
    # spellings like `Levels[2].Name` hit the same shapes as `Levels[].Name`
    shape = re.compile(r"levels?(\[\])?([.]|$)|levelfilters?", re.IGNORECASE)
    found = 0
    for row in sorted(stubs.rows_by_kind["unlockable"],
                      key=lambda r: str(r["id"])):
        src_id = str(row["id"])
        for path, value in _iter_string_fields(row.get("fields") or {}):
            fp = ru.normalize_field_path(path)
            if value in level_ids and shape.search(fp):
                edges.add("unlockable", src_id, "campus-level", value,
                          "name-convention:unlockable-level-name", fp,
                          {"fieldPath": fp}, True, mechanism="inferred")
                raw_by_cell.setdefault(("unlockable", "campus-level"),
                                       Counter())[fp] += 1
                found += 1
    counters["probeUnlockableLevelRefs"] = found
    return found


def _iter_string_fields(node, path=""):
    stack = [(path, node)]
    while stack:
        p, n = stack.pop()
        if isinstance(n, dict):
            prefix = f"{p}." if p else ""
            for k, v in n.items():
                if isinstance(v, str):
                    yield (prefix + k), v
                else:
                    stack.append((prefix + k, v))
        elif isinstance(n, list):
            for i, v in enumerate(n):
                stack.append((f"{p}[{i}]", v))


# node spellings with separators stripped, for leaf-key matching only
_KIND_BY_LEAF = {re.sub(r"[^a-z0-9]", "", k): k for k in ru.NODE_UNIVERSE}


def _leaf_named_kind(field_path: str):
    """The node-universe kind a field path's leaf key NAMES, or None — the
    `.references.NNNN.data.Course` probe rule generalized to every source
    kind (arbiter F1). Match is exact on the separator-stripped lowercased
    leaf against the node spellings: plurals (`Items`) and compounds
    (`BalanceConfig`, `OverrideAnims`) never match."""
    leaf = field_path.rsplit(".", 1)[-1]
    cut = leaf.find("[")
    if cut >= 0:
        leaf = leaf[:cut]
    return _KIND_BY_LEAF.get(re.sub(r"[^a-z0-9]", "", leaf.lower()))


def attribute_unresolved_residue(unresolved, stubs: ru.StubIndex,
                                 bridges: ru.BridgeIndexes,
                                 resolver: ru.CrossFileResolver):
    """Destination-derived attribution of ledgered PPtr residue (piece-02 §3
    R7, arbiter F1). A cell's `evidence.unresolvedRefs` — and the `partial`
    flip it triggers — may count only refs attributed to THAT cell's
    destination, never a whole srcKind's field-sharing cohort:

    1. R1 ladder — each ref's target is resolved as far as the bridges
       allow (same-file membership / externals + cab index, the same ladder
       `tooltip_target_classes` walks). A target that lands on an emitted
       entity or scene-flagged bundle charges exactly the cell whose
       destination id space it landed in. Walker output cannot reach these
       statuses today (stub/scene landings emit edges, not ledger rows), so
       this branch pins defensive correctness for upstream growth.
    2. Leaf-key naming — otherwise a leaf key that NAMES a destination kind
       (`…data.Course` → course) charges that one cell.
    3. Everything else — engine-class targets (AnimationClip, components),
       built-in externals, unresolvable extPaths — inflates NO cell; it
       stays visible in `relinks/_unresolved_pptrs.jsonl` and the R2
       `unresolvedCrossFile` counter only.

    Returns (charges, tally): `{(srcKind, dstKind): n}` plus a Counter of
    landed / leafKeyNamed / nonEntity / unresolvable dispositions for the
    run log."""
    src_meta: dict[tuple[str, str], tuple[str, int]] = {}
    for kind, rows in stubs.rows_by_kind.items():
        for row in rows:
            src = row.get("source") or {}
            if src.get("bundle") is not None \
                    and src.get("pathId") is not None:
                src_meta[(kind, str(row["id"]))] = (
                    str(src["bundle"]), int(src["pathId"]))
    charges: dict[tuple[str, str], int] = {}
    tally: Counter = Counter()

    def _charge(cell):
        charges[cell] = charges.get(cell, 0) + 1

    for u in unresolved:
        sk = u["srcKind"]
        fp = str(u["fieldPath"])
        fid = int(u["extFileId"])
        pid = int(u["m_PathID"])
        landing = None
        disposition = "unresolvable"
        meta = src_meta.get((sk, str(u["srcId"])))
        if meta is not None:
            bundle, src_pid = meta
            if fid == 0:
                t = resolver.same_file_target(bundle, pid)
                if t is not None:
                    landing = t["kind"] if t["status"] == "stub" \
                        else ru.SCENE_NODE
                    disposition = "landed"
                elif _same_file_object_present(bridges, bundle, src_pid, pid):
                    disposition = "nonEntity"   # e.g. an AnimationClip
            else:
                out = resolver.resolve(
                    bundle, bridges.cab_of(bundle, src_pid), fid, pid)
                st_status = out["status"]
                if st_status == "stub":
                    landing, disposition = out["kind"], "landed"
                elif st_status == "scene":
                    landing, disposition = ru.SCENE_NODE, "landed"
                elif st_status == "builtin" or (
                        st_status == "unresolved"
                        and _external_object_present(bridges, out, pid)):
                    disposition = "nonEntity"
        if landing is not None:
            _charge((sk, landing))
            tally["landed"] += 1
            continue
        named = _leaf_named_kind(fp)
        if named is not None:
            _charge((sk, named))
            tally["leafKeyNamed"] += 1
        else:
            tally[disposition] += 1
    return charges, tally


def _same_file_object_present(bridges: ru.BridgeIndexes, bundle: str,
                              src_pid: int, pid: int) -> bool:
    """True when the same-file target exists as an indexed object (its class
    is recoverable) without being an emitted entity."""
    cab = bridges.cab_of(bundle, src_pid)
    tbl = bridges.cabs.get((bundle, cab)) if cab is not None else None
    return tbl is not None and tbl.has(pid)


def _external_object_present(bridges: ru.BridgeIndexes, out: dict,
                             pid: int) -> bool:
    """The cab_owners hop of tooltip_target_classes: True when the
    unresolved external's owning serialized file holds the pathId (its
    engine class identifies a non-entity target such as AnimationClip)."""
    ext_path = str(out.get("extPath") or "")
    if not ext_path:
        return False
    for b, cab in bridges.cab_owners.get(ext_path, ()):
        tbl = bridges.cabs.get((b, cab))
        if tbl is not None and tbl.has(pid):
            return True
    return False


def run_guid_bridge_pass(stubs: ru.StubIndex, bridges: ru.BridgeIndexes,
                         guid_index: dict, edges: ru.EdgeAccumulator,
                         raw_by_cell, scene_bundles: dict, build_id):
    """R3 stage pass — catalog-guid → address → object → entity/scene/
    address termination over the loaded stub + bridge indexes. (`relink_
    util.run_guid_bridge` is the pure-data seam with the same ladder for
    raw-row callers.) `scene_bundles` is the roster relpath → sceneFlag map
    (explicit parameter — no hidden module state). Returns
    (asset_rows, dangling_rows, report, counters)."""
    refs_total = 0
    distinct: set[str] = set()
    resolved_addr_refs = 0
    resolved_stub_refs = 0
    asset_rows_dedup: dict[tuple, dict] = {}
    dangling_samples: dict[str, list] = {}
    scene_guid_edges = 0

    for kind in ru.STUB_KINDS:
        for row in sorted(stubs.rows_by_kind[kind], key=lambda r: str(r["id"])):
            src_id = str(row["id"])
            for raw_path, guid, sub in ru.walk_guid_refs(
                    row.get("fields") or {}):
                refs_total += 1
                distinct.add(guid)
                fp = ru.normalize_field_path(raw_path)
                entries = guid_index.get(guid)
                if not entries:
                    samples = dangling_samples.setdefault(guid, [])
                    if len(samples) < 5:
                        samples.append({"srcKind": kind, "srcId": src_id,
                                        "fieldPath": fp})
                    continue
                resolved_addr_refs += 1
                addresses = sorted({str(e.get("address")) for e in entries})
                hit_stub = False
                for address in addresses:
                    key = (kind, src_id, fp, address)
                    if key not in asset_rows_dedup:
                        ev = {"fieldPath": fp, "assetGuid": guid,
                              "resolvedVia": "catalog-guid+container-index"}
                        if sub:
                            ev["subObjectName"] = sub
                        asset_rows_dedup[key] = {
                            "srcKind": kind, "srcId": src_id,
                            "dstKind": "asset", "dstId": address,
                            "mechanism": "hard", "method": ru.METHOD_GUID,
                            "inferred": False, "evidence": ev,
                            "buildId": build_id}
                    # uniform candidate rows (bundle, cab, pathId, classIdx);
                    # container_exact returns (cab, pathId, classIdx) so it is
                    # re-wrapped with its bundle here
                    candidates = []
                    bundles = {str(e.get("bundle")) for e in entries
                               if e.get("address") == address
                               and e.get("bundle")}
                    for b in sorted(bundles):
                        got = bridges.container_exact(b, address)
                        if got:
                            cab, pidv, ci = got
                            candidates.append((b, cab, pidv, ci))
                    if not candidates:
                        candidates.extend(bridges.container_by_address(address))
                    candidates.sort(key=lambda t: (t[0], t[2]))
                    # pass 1 — stub-entity targets win across ALL candidates;
                    # pass 2 — otherwise the first scene-flagged bundle takes
                    # the edge (the R2 attribution rule, R3 step 3b)
                    for b, _cab, pidv, _ci in candidates:
                        hit = stubs.at(b, pidv)
                        if hit is not None:
                            hit_stub = True
                            edges.add(kind, src_id, hit[0], hit[1],
                                      ru.METHOD_GUID, fp,
                                      {"fieldPath": fp, "assetGuid": guid,
                                       "catalogAddress": address}, False)
                            raw_by_cell.setdefault((kind, hit[0]),
                                                   Counter())[fp] += 1
                            break
                    if not hit_stub:
                        for b, _cab, _pidv, _ci in candidates:
                            if b in scene_bundles:
                                edges.add(kind, src_id, ru.SCENE_NODE, b,
                                          ru.METHOD_GUID, fp,
                                          {"fieldPath": fp,
                                           "assetGuid": guid,
                                           "catalogAddress": address},
                                          False)
                                raw_by_cell.setdefault(
                                    (kind, ru.SCENE_NODE), Counter())[fp] += 1
                                scene_guid_edges += 1
                                break
                if hit_stub:
                    resolved_stub_refs += 1
    asset_rows = sorted(asset_rows_dedup.values(),
                        key=lambda r: (r["srcKind"], r["srcId"],
                                       r["evidence"]["fieldPath"],
                                       r["dstId"]))
    dangling_rows = [{
        "assetGuid": g,
        "sampleRefs": dangling_samples[g],
        "verdict": "unresolved-open",
        "unblock": "bounded deterministic probe against scene dumps + "
                   "census — no committed scene-object inventory exists on "
                   "this tree yet; verdict upgrades belong to the maps/"
                   "scene-dump piece",
        "buildId": build_id,
    } for g in sorted(dangling_samples)]
    report = {
        "guidRefsTotal": refs_total,
        "distinctGuids": len(distinct),
        "resolvedToAddress": resolved_addr_refs,
        "resolvedToStub": resolved_stub_refs,
        "danglingDistinctGuids": len(dangling_samples),
        "resolveRateAddress": (resolved_addr_refs / refs_total)
        if refs_total else 0.0,
        "resolveRateStub": (resolved_stub_refs / refs_total)
        if refs_total else 0.0,
        "buildId": build_id,
    }
    counters = {"sceneGuidEdges": scene_guid_edges}
    return asset_rows, dangling_rows, report, counters


def run_locale_join(stubs: ru.StubIndex, i2_dir: Path, matrix_keys: set,
                    build_id):
    """R4 — term-ID path. Returns (registry_rows, loc_rows, reverse_rows,
    report, drift_lines, stats, matrix_key_diff)."""
    dumps = sorted(i2_dir.glob("*.json"))
    registry_rows, stats = ru.build_i2_registry(dumps, build_id)
    registry = ru.TermRegistry(registry_rows)
    diff = len(registry.keys - matrix_keys) + len(matrix_keys - registry.keys)

    loc_rows, reverse_rows, report = ru.build_entity_locale(
        ru.iter_stub_localised(stubs), registry, build_id)

    drift = []
    if stats["registryRows"] != F7_ROWS or \
            stats["registryDistinctKeys"] != F7_KEYS or diff != 0:
        drift.append(
            f"DRIFT: I2 registry measures {stats['registryRows']} rows / "
            f"{stats['registryDistinctKeys']} distinct keys / "
            f"matrixKeyDiff={diff} against seed F7 "
            f"({F7_ROWS}/{F7_KEYS}/diff 0) — fresh numbers win")
    n_unresolved = len(report["unresolvedIds"])
    if n_unresolved != F8_KNOWN_UNRESOLVED_IDS:
        drift.append(
            f"DRIFT: {n_unresolved} unresolved term IDs vs the "
            f"{F8_KNOWN_UNRESOLVED_IDS} known 2026-08-25 (F8) — fresh wins")

    code_ref_path = None
    code_ref_terms = 0
    for path in dumps:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if str(payload.get("m_Name") or "") == "I2LS_CodeRef":
            code_ref_path = path
            code_ref_terms = len(
                (payload.get("mSource") or {}).get("mTerms") or [])
            break
    if code_ref_path is not None:
        report["codeRefTerms"] = {
            "note": f"I2LS_CodeRef source audited in place: "
                    f"{code_ref_terms} runtime-created code-ref terms; their "
                    "term IDs join through the same registry",
            "auditPath": code_ref_path.as_posix()}
    else:
        report["codeRefTerms"] = {
            "note": "I2LS_CodeRef source absent from the LanguageSource "
                    "dumps on this tree — runtime-created code-ref terms "
                    "cannot be audited here (~586 expected per scout G4)",
            "auditPath": None}
    return registry_rows, loc_rows, reverse_rows, report, drift, stats, diff


# ---------------------------------------------------------------------------
# R5 — UI-link coverage

_FLOOR_PATTERNS = ("*Menu*", "*UI*", "*Inspector*")


def _floor_class(cls: str) -> bool:
    return any(fnmatch.fnmatchcase(cls, pat) for pat in _FLOOR_PATTERNS)


_SEEDED_SURFACES = [
    {"surfaceId": "course-management-requirements",
     "uiClassPrefixes": ["TPC.CourseManagementMenu_Requirements",
                         "TPC.CourseManagementMenu_RequirementsFull"],
     "definitionClassPrefixes": ["TPC.CourseModuleDefinition",
                                 "TPC.CourseDefinition",
                                 "TPC.SelfStudyDefinition"],
     "impliedFamilies": ["course-room-item-requirements"],
     "joins": ["course_config", "config_item", "config_room", "room_item"]},
    {"surfaceId": "inspector-room-course-item",
     "uiClassPrefixes": ["TPC.InspectorRoomCourseItem"],
     "definitionClassPrefixes": ["TPC.RoomDefinition", "TPC.RoomLiteDefinition",
                                 "TPC.FloorAreaDefinition"],
     "impliedFamilies": ["room-item-needs", "room-config-permissions"],
     "joins": ["room_item", "room_config"]},
    {"surfaceId": "training-menu-qualification",
     "uiClassPrefixes": ["TPC.TrainingMenu_Qualification",
                         "TPC.OverviewMenu_QualificationInspector"],
     "definitionClassPrefixes": ["TPC.QualificationDefinition",
                                 "TPC.QualificationLiteDefinition"],
     "impliedFamilies": ["staff-qualification-course"],
     "joins": ["staff_config", "course_config"]},
    {"surfaceId": "research-project-inspector",
     "uiClassPrefixes": ["TPC.ResearchProjectInspector", "TPC.ResearchBaseUI"],
     "definitionClassPrefixes": ["TPC.ResearchProjectDefinition",
                                 "TPC.ResearchProjectLiteDefinition"],
     "impliedFamilies": ["metagame-node-unlock-tree"],
     "joins": ["metagame-node_config", "config_item", "config_course"]},
    {"surfaceId": "staff-job-assignment",
     "uiClassPrefixes": ["TPC.StaffJobAssignmentUI"],
     "definitionClassPrefixes": ["TPC.StaffJobDefinition"],
     "impliedFamilies": ["staff-job-roomtype"],
     "joins": ["staff_config", "config_room"]},
    {"surfaceId": "campus-event-menu",
     "uiClassPrefixes": ["TPC.CampusEventMenu"],
     "definitionClassPrefixes": ["TPC.CampusEventDefinition",
                                 "TPC.CampusEventLiteDefinition",
                                 "TPC.CampusEventType"],
     "impliedFamilies": ["event-room-item-date"],
     "joins": ["config_room", "config_item", "config_metagame-node"]},
    {"surfaceId": "inbox-personal-goal",
     "uiClassPrefixes": ["TPC.InboxMenuMessageUI_PersonalGoalRequest",
                         "TPC.WidgetPersonalGoal"],
     "definitionClassPrefixes": ["TPC.PersonalGoal_ItemDefinition",
                                 "TPC.PersonalGoal_RoomDefinition",
                                 "TPC.PersonalGoal_EventDefinition",
                                 "TPC.PersonalGoal_JobDefinition",
                                 "TPC.PersonalGoal_TrainingDefinition",
                                 "TPC.PersonalGoal_EnvironmentDefinition"],
     "impliedFamilies": ["student-wants-entity"],
     "joins": ["student-type_config", "item_config", "room_config"]},
    {"surfaceId": "objective-status-effects",
     "uiClassPrefixes": ["TPC.ObjectiveView", "TPC.ObjectiveTaskCheckBox"],
     "definitionClassPrefixes": ["TPC.ObjectiveDefinition",
                                 "TPC.CharacterStatusEffect",
                                 "TPC.InteractionDefinition"],
     "impliedFamilies": ["entity-effect", "need-satisfaction"],
     "joins": ["room_config", "student-type_config", "item_config"]},
]


def _count_matching(counts: Counter, prefix: str) -> tuple[int, list]:
    total = sum(n for cls, n in counts.items() if cls.startswith(prefix))
    members = sorted(cls for cls in counts if cls.startswith(prefix))
    return total, members


def _script_class_for_target(monobehaviours_dir: Path, bundle_rel: str,
                             pid: int):
    """The `_scriptClass` a harvested dump carries in-band for object
    `(bundle_rel, pid)` — stage-3 embeds script identity on every MonoBehaviour
    payload while the dump FILENAME spells `<bundle-stem>_<signed-pathId>`
    under the bundle's own subdirectory. None when the object has no harvested
    dump (engine-side targets: AnimationClip, Transforms, …)."""
    stem = ru.bundle_base(bundle_rel)
    if stem.endswith(".bundle"):
        stem = stem[:-len(".bundle")]
    d = monobehaviours_dir / stem
    if not d.is_dir():
        return None
    for path in sorted(d.rglob(f"{stem}_{pid}.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        sc = payload.get("_scriptClass")
        if isinstance(sc, str) and sc:
            return sc
    return None


def tooltip_target_classes(monobehaviours_dir: Path, bridges,
                           resolver: ru.CrossFileResolver,
                           stem_to_rel: dict) -> dict:
    """The TooltipSpawner anchor census, split by meaningfulness (arbiter F3).

    Returns {"scriptClasses": [...], "genericContainerClasses": [...]}:
    script classes come from one more hop than the bare ladder — a resolved
    target's OWN harvested dump carries `_scriptClass` in-band — while
    generic container classes are the Unity engine names the cab tables give
    for targets without dumps (AnimationClip, Transform, …). Dump
    provenance: stage-3 embeds `_sourceFile` (the owning serialized file's
    lowered CAB name) on each payload while the dump FILENAME carries
    `<bundle-stem>_<signed-pathId>` — the owning bundle comes from the
    stem→roster-relpath map and the pair is verified against the bridge
    before any lookup (m_Script/m_GameObject leaves are excluded upstream by
    walk_pptr_leaves — script identity ships in-band)."""
    script: set[str] = set()
    generic: set[str] = set()
    hop_memo: dict[tuple[str, int], str | None] = {}
    dumps = sorted(monobehaviours_dir.rglob("*/*.json"))
    for path in dumps:
        parts = path.as_posix().replace("\\", "/").split("/")
        if len(parts) < 2 or parts[-2] != "TPC.TooltipSpawner":
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            continue
        src_cab = str(payload.get("_sourceFile") or "").lower()
        parsed = tc.parse_harvest_stem(path.stem)
        if not src_cab or parsed is None:
            continue
        bundle = stem_to_rel.get(parsed[0])
        if bundle is None or (bundle, src_cab) not in bridges.cabs:
            continue
        table = bridges.cabs[(bundle, src_cab)]

        def _note(b, pid):
            key = (str(b), int(pid))
            if key not in hop_memo:
                hop_memo[key] = _script_class_for_target(
                    monobehaviours_dir, key[0], key[1])
            sc = hop_memo[key]
            if sc is not None:
                script.add(sc)
                return
            ci = _lookup_class_any(bridges, b, pid)
            if ci is not None:
                generic.add(bridges.class_name(ci))

        for _leaf_key, _raw_path, fid, pid in ru.walk_pptr_leaves(payload):
            if fid == 0:
                if table.has(pid):
                    _note(bundle, pid)
                else:
                    ci = table.class_of(pid)
                    if ci is not None:
                        generic.add(bridges.class_name(ci))
                continue
            out = resolver.resolve(bundle, src_cab, fid, pid)
            if out["status"] in ("stub", "scene"):
                _note(out.get("bundle"), pid)
            elif out["status"] == "unresolved" and out.get("extPath"):
                for b, cab in bridges.cab_owners.get(out["extPath"], ()):
                    tbl = bridges.cabs.get((b, cab))
                    if tbl is not None and tbl.has(pid):
                        _note(b, pid)
                        break
    return {"scriptClasses": sorted(script),
            "genericContainerClasses": sorted(generic)}


def _lookup_class_any(bridges, bundle, pid):
    if not bundle:
        return None
    for cab in bridges.bundle_cabs.get(bundle, ()):
        tbl = bridges.cabs.get((bundle, cab))
        if tbl is not None and tbl.has(pid):
            return tbl.class_of(pid)
    return None


def build_ui_coverage(manifest_counts: Counter, unmapped_classes: set,
                      measured_cells: set, tooltip_census: dict,
                      kind_classes: dict, localize_count: int, build_id):
    """R5 rows: nine seeded surfaces + the mechanical discovery floor
    (`*Menu*|*UI*|*Inspector*`) + the Localize binding census row. Every
    floor class lands mapped or gapped; every tooltip target class sits in
    the tooltip-spawner mapped row's definitionClasses (anchor partition).

    The tooltip-spawner row ships only MEANINGFUL classes in
    definitionClasses — script identities recovered from the targets' own
    dumps (arbiter F3). Unity-generic container classes are noted separately
    in genericContainerClasses and never justify a mapped row; joins derive
    from the pair-dataset cells of the kinds those script classes belong to
    (via `kind_classes`: kind → stub-corpus source classes), never from an
    unrelated all-cells sweep."""
    rows: list[dict] = []

    def row(surface_id, ui_class, exported, def_members, families, status,
            joins, gap_reason=None, unblock=None, extra=None):
        r = {
            "surfaceId": surface_id, "uiClass": ui_class,
            "exportedCount": exported,
            "definitionClasses": [{"class": c,
                                   "corpusCount": manifest_counts.get(c, 0)}
                                  for c in def_members],
            "impliedFamilies": families, "status": status, "joins": joins,
            "gapReason": gap_reason, "unblock": unblock,
            "buildId": build_id}
        if extra:
            r.update(extra)
        rows.append(r)

    covered: set[str] = set()

    # seeded surfaces
    for spec in _SEEDED_SURFACES:
        exported = 0
        ui_members: list[str] = []
        for prefix in spec["uiClassPrefixes"]:
            n, members = _count_matching(manifest_counts, prefix)
            exported += n
            ui_members.extend(members)
        def_members: list[str] = []
        for prefix in spec["definitionClassPrefixes"]:
            _n, members = _count_matching(manifest_counts, prefix)
            def_members.extend(members)
        joins = [j for j in spec["joins"] if tuple(j.split("_", 1)) in
                 measured_cells]
        status = "mapped-schema" if joins else "documented-gap"
        row(spec["surfaceId"], "+".join(spec["uiClassPrefixes"]), exported,
            def_members, spec["impliedFamilies"], status, joins,
            None if status == "mapped-schema" else
            "seeded surface with no measured pair-dataset cell yet",
            None if status == "mapped-schema" else
            "decode the surface's prefab bindings (PPtr/Localize walk) and "
            "re-run; piece-02 §R5")
        covered.update(ui_members)
        covered.update(def_members)

    # tooltip-spawner anchor row — definitionClasses carry the SCRIPT-class
    # census only. Status is honest about how it was derived: Unity-generic
    # containers never count as definitions (arbiter F3), and a gap names
    # the monoScript-hop unblock with NO joins (the XOR contract).
    script_classes = list(tooltip_census.get("scriptClasses") or ())
    generic_classes = sorted(tooltip_census.get("genericContainerClasses")
                             or ())
    admitted_kinds = sorted(
        k for k, cs in (kind_classes or {}).items()
        if cs and set(script_classes) & cs)
    tooltip_joins = sorted({f"{s}_{d}" for (s, d) in measured_cells
                            if s in admitted_kinds or d in admitted_kinds})
    if script_classes and tooltip_joins:
        t_status, t_gap, t_unblock = "mapped-schema", None, None
    elif not script_classes:
        t_status = "documented-gap"
        t_gap = ("tooltip target MonoBehaviours' script identity not "
                 "recoverable: resolved targets carry no harvested dump "
                 "(monoScript hop empty) on this corpus")
        t_unblock = ("extend stage-3 harvesting to the spawner targets' "
                     "bundles so their dumps carry _scriptClass, then "
                     "re-run; piece-02 §R5")
    else:
        t_status = "documented-gap"
        t_gap = ("tooltip target script classes resolve but admit no "
                 "measured pair-dataset cell yet")
        t_unblock = ("grow cross-file PPtr resolution until one of the "
                     "targets' kinds carries edges; piece-02 §R5")
    extra = {"genericContainerClasses": generic_classes} \
        if generic_classes else None
    row("tooltip-spawner", "TPC.TooltipSpawner",
        manifest_counts.get("TPC.TooltipSpawner", 0),
        script_classes,
        ["entity-cross-link-renderer"],
        t_status, tooltip_joins, t_gap, t_unblock, extra)
    covered.add("TPC.TooltipSpawner")
    covered.update(script_classes)

    # I2.Loc.Localize binding census — the UI-localization surface
    row("i2-localize-bindings", "I2.Loc.Localize", localize_count, [],
        ["entity-localization-bindings"], "mapped-schema",
        ["entity_locale"] if True else [],
        None, None)
    covered.add("I2.Loc.Localize")

    # discovery floor: everything else matching the pattern documents a gap
    universe = set(manifest_counts) | set(unmapped_classes)
    gaps = 0
    for cls in sorted(universe):
        if not _floor_class(cls) or cls in covered:
            continue
        row(_slug(cls), cls, manifest_counts.get(cls, 0), [], [],
            "documented-gap", [],
            "harvested UI-pattern class with no decoded relationship "
            "surface yet (component/prefab class outside the seeded "
            "surfaces)",
            "decode the class's prefab bindings (tooltip/Localize/PPtr "
            "walk) and re-run; piece-02 §R5 discovery floor")
        gaps += 1
    rows.sort(key=lambda r: r["surfaceId"])
    counters = {
        "surfacesTotal": len(rows),
        "mappedSchema": sum(1 for r in rows if r["status"] == "mapped-schema"),
        "documentedGaps": sum(1 for r in rows
                              if r["status"] == "documented-gap"),
        "tooltipTargetClasses": len(script_classes),
        "tooltipGenericContainers": len(generic_classes),
        "localizeBindings": localize_count,
    }
    return rows, counters


def _slug(cls: str) -> str:
    leaf = cls.rsplit(".", 1)[-1]
    return re.sub(r"[^a-z0-9]+", "-", leaf.lower()).strip("-")[:80]


# ---------------------------------------------------------------------------
# Entry

def run(game_root: Path, extracted_root: Path) -> int:
    problems: list[str] = []
    drift_lines: list[str] = []

    # -- upstream gate (exit 3 names what is missing) ------------------------
    required = [
        extracted_root / "identity.json",
        extracted_root / "stubs",
        extracted_root / "stubs" / "_absences.jsonl",
        extracted_root / "stubs" / "_unmapped-families.jsonl",
        extracted_root / "harvest" / "export-manifest.jsonl",
        extracted_root / "harvest" / "externals.jsonl",
        extracted_root / "harvest" / "monobehaviours",
        extracted_root / I2_SOURCE_DIR,
        extracted_root / "addressables" / "catalog.json",
        extracted_root / "locales" / "locale-matrix.json",
        extracted_root / "decompiled" / "structural" /
        "class-hierarchy.jsonl",
        extracted_root / "bundle-roster.jsonl",
    ]
    missing = [p for p in required if not p.exists()]
    if missing:
        raise tc.StageError(
            f"stage 'relink' is missing upstream artifacts "
            f"({', '.join(p.as_posix() for p in missing)}) — prepare the "
            "tree first (client mode: run the pipeline without this stage; "
            "hostless smoke: tests/build_fixture_tree.py --stage relink)",
            exit_code=3)

    identity = json.loads(
        (extracted_root / "identity.json").read_text(encoding="utf-8"))
    build_id = identity.get("buildId")

    roster = tc.load_roster(extracted_root)
    scene_bundles = {r["relpath"]: r["sceneFlag"] for r in roster
                     if r.get("sceneFlag", "none") != "none"}

    # bare bundle filename / dump stem → roster relpath. Stub rows spell
    # source.bundle as the bare filename WITH extension (measured:
    # `configs_assets_all.bundle`) while harvest dump STEMS drop it — both
    # spellings must canonicalize onto the ONE relpath key every resolver
    # downstream shares (bridges, externals sidecar), with basenames spelled
    # back into evidence via relink_util.bundle_base.
    stem_to_rel: dict[str, str] = {}
    basename_to_rel: dict[str, str] = {}
    stem_collisions: list[str] = []
    for r in roster:
        name = r["relpath"].replace("\\", "/").rsplit("/", 1)[-1]
        stem = name[:-len(".bundle")] if name.endswith(".bundle") else name
        prev = basename_to_rel.setdefault(name, r["relpath"])
        if prev != r["relpath"]:
            stem_collisions.append(name)
        prev_stem = stem_to_rel.setdefault(stem, r["relpath"])
        if prev_stem != r["relpath"]:
            stem_collisions.append(stem)
    if stem_collisions:
        # basename↔relpath mapping must be unique or every bundle-keyed join
        # is ambiguous — a schema/validation failure, not a ledger row
        problems.append(
            "roster bundle basenames collide (join keys ambiguous): "
            f"{sorted(set(stem_collisions))[:5]}")

    stubs = ru.load_stubs(extracted_root / "stubs",
                          bundle_map=basename_to_rel)
    externals = ru.load_externals(
        extracted_root / "harvest" / "externals.jsonl")
    manifest_counts = load_manifest_class_counts(
        extracted_root / "harvest" / "export-manifest.jsonl")
    unmapped_classes = set()
    with open(extracted_root / "stubs" / "_unmapped-families.jsonl",
              encoding="utf-8", newline="\n") as fh:
        for line in fh:
            line = line.strip()
            if line:
                unmapped_classes.add(json.loads(line)["class"])
    matrix_doc = json.loads(
        (extracted_root / "locales" / "locale-matrix.json")
        .read_text(encoding="utf-8"))
    matrix_keys = set(matrix_doc.get("keys") or {})
    hier_rows = sum(1 for line in
                    open(extracted_root / "decompiled" / "structural" /
                         "class-hierarchy.jsonl", encoding="utf-8")
                    if line.strip())
    competitor_root = tc.resolve_pack_dir() / "data" / "sources" / "competitor"

    ru.clear_owned_outputs(extracted_root / "relinks")

    # -- R1 ------------------------------------------------------------------
    bridges, r1_notes = run_bridges(game_root, extracted_root, roster,
                                    build_id)

    # -- R2 ------------------------------------------------------------------
    resolver = ru.CrossFileResolver(bridges, externals, stubs, scene_bundles)
    edges, unresolved, r2c, raw_by_cell = walk_stub_payloads(
        stubs, bridges, resolver, build_id)
    probe_found = probe_unlockable_levels(stubs, edges, raw_by_cell, r2c)

    # -- R3 ------------------------------------------------------------------
    guid_index = load_catalog_guid_index(
        extracted_root / "addressables" / "catalog.json")
    asset_rows, dangling_rows, guid_report, r3_extra = run_guid_bridge_pass(
        stubs, bridges, guid_index, edges, raw_by_cell, scene_bundles,
        build_id)
    if guid_report["guidRefsTotal"] != F9_REFS \
            or guid_report["distinctGuids"] != F9_DISTINCT \
            or guid_report["danglingDistinctGuids"] != F9_DANGLING:
        drift_lines.append(
            f"DRIFT: GUID bridge measures {guid_report['guidRefsTotal']} "
            f"refs / {guid_report['distinctGuids']} distinct / "
            f"{guid_report['danglingDistinctGuids']} dangling against seed "
            f"F9 ({F9_REFS}/{F9_DISTINCT}/{F9_DANGLING}) — fresh wins")

    # -- write pair datasets (client rows only; overlays come later) --------
    relinks = extracted_root / "relinks"
    client_cells = edges.by_cell()
    pair_files_emitted = 0
    edges_emitted = 0
    twin_endpoint_edges = r2c["twinEndpointEdges"]
    for (sk, dk), group in sorted(client_cells.items()):
        rows = edges.rows_for_cell(sk, dk)
        rows = ru.attach_source_axes(rows, stubs)
        for r in rows:
            if r["method"] == ru.METHOD_GUID:
                # refCount is PPtr repeat-collapse semantics (§R2); the GUID
                # evidence contract is exactly {fieldPath, assetGuid,
                # catalogAddress} — the accumulator's bookkeeping key leaves
                # with it
                r["evidence"].pop("refCount", None)
            ru.validate_pair_row(r)
        log_util.write_jsonl(relinks / f"{sk}_{dk}.jsonl", rows)
        pair_files_emitted += 1
        edges_emitted += len(rows)

    log_util.write_jsonl(relinks / "_unresolved_pptrs.jsonl", unresolved)
    log_util.write_jsonl(relinks / "entity_asset_guid.jsonl", asset_rows)
    for r in asset_rows:
        ru.validate_guid_asset_row(r)
    log_util.write_jsonl(relinks / "_dangling_guids.jsonl", dangling_rows)
    log_util.write_json(relinks / "guid_bridge_report.json", guid_report)

    # -- R4 ------------------------------------------------------------------
    i2_dir = extracted_root / I2_SOURCE_DIR
    (registry_rows, loc_rows, reverse_rows, locale_report, r4_drift,
     r4_stats, matrix_key_diff) = run_locale_join(
        stubs, i2_dir, matrix_keys, build_id)
    drift_lines.extend(r4_drift)
    locale_report["matrixKeyDiff"] = matrix_key_diff
    log_util.write_jsonl(relinks / "i2_term_registry.jsonl", registry_rows)
    log_util.write_jsonl(relinks / "entity_locale.jsonl", loc_rows)
    log_util.write_jsonl(relinks / "locale_term_entity.jsonl", reverse_rows)
    log_util.write_json(relinks / "locale_join_report.json", locale_report)

    # -- R5 ------------------------------------------------------------------
    tooltip_census = tooltip_target_classes(
        extracted_root / "harvest" / "monobehaviours", bridges, resolver,
        stem_to_rel)
    measured_cells = {(sk, dk) for (sk, dk) in client_cells}
    kind_classes = {
        k: {str((r.get("source") or {}).get("class") or "")
            for r in rows} - {""}
        for k, rows in stubs.rows_by_kind.items()}
    coverage_rows, r5c = build_ui_coverage(
        manifest_counts, unmapped_classes, measured_cells, tooltip_census,
        kind_classes, manifest_counts.get("I2.Loc.Localize", 0), build_id)

    def _target_covered(cls: str) -> bool:
        """Anchor-rule membership: the class appears in some mapped row's
        definitionClasses, or owns a coverage row outright."""
        for r in coverage_rows:
            if r.get("uiClass") == cls:
                return True
            if r.get("status") == "mapped-schema" and any(
                    d.get("class") == cls
                    for d in r.get("definitionClasses") or ()):
                return True
        return False

    uncovered_targets = [c for c in tooltip_census.get("scriptClasses") or ()
                         if c != "TPC.TooltipSpawner"
                         and not _target_covered(c)]
    if uncovered_targets:
        problems.append(
            f"tooltip anchor partition violated: {len(uncovered_targets)} "
            f"target classes uncovered e.g. {uncovered_targets[:3]}")
    log_util.write_jsonl(relinks / "ui_link_coverage.jsonl", coverage_rows)

    # -- R6 ------------------------------------------------------------------
    measured_edge_ids = {(g["srcKind"], g["srcId"], g["dstKind"], g["dstId"])
                         for g in edges.groups.values()}
    ledger_rows, overlay_edges, r6c, floor_met = ru.apply_competitor_sources(
        competitor_root, stubs, measured_edge_ids, build_id)
    overlays_by_cell: dict[tuple[str, str], list[dict]] = {}
    for g in overlay_edges.groups.values():
        overlays_by_cell.setdefault((g["srcKind"], g["dstKind"]), []).append(
            overlay_edges.finalize(g))
    overlay_files = 0
    for (sk, dk), rows in sorted(overlays_by_cell.items()):
        rows.sort(key=lambda r: (r["srcKind"], r["srcId"], r["dstKind"],
                                 r["dstId"], r["method"],
                                 r["evidence"]["fieldPath"]))
        for r in rows:
            ru.validate_pair_row(r)
        log_util.write_jsonl(relinks / f"{sk}_{dk}.competitor.jsonl", rows)
        overlay_files += 1
    log_util.write_jsonl(relinks / "competitor_applied.jsonl", ledger_rows)
    sources_applied = sum(
        1 for r in ledger_rows
        if any(v for v in r.get("dispositions", {}).values()))

    # -- R7 ------------------------------------------------------------------
    cell_states: dict[tuple[str, str], ru.CellState] = {}
    for (sk, dk), group in client_cells.items():
        st = ru.CellState()
        st.edges = len(group)
        st.methods = {g["method"] for g in group}
        st.src_entities = {g["srcId"] for g in group}
        st.raw_by_field = raw_by_cell.get((sk, dk), Counter())
        cell_states[(sk, dk)] = st
    # destination-derived residue attribution (arbiter F1): only refs whose
    # target demonstrably lands in a cell's destination id space (R1 ladder)
    # or whose leaf key names it may charge that cell — field-sharing across
    # a srcKind is gone (it wrote e.g. 368 AnimationClip danglers onto
    # config_unlockable's single true edge)
    attr_charges, attr_tally = attribute_unresolved_residue(
        unresolved, stubs, bridges, resolver)
    for cell, n in sorted(attr_charges.items()):
        cell_states.setdefault(cell, ru.CellState()).unresolved_shared += n
    # the needs-probe text counts .Course-named dangles specifically — the
    # same population the leaf-key rule charges onto metagame-node_course
    course_dangling = sum(
        1 for u in unresolved
        if u["srcKind"] == "metagame-node"
        and _leaf_named_kind(str(u["fieldPath"])) == "course")

    probe_cells = {}
    if ("unlockable", "campus-level") not in cell_states:
        probe_cells[("unlockable", "campus-level")] = \
            PROBE_UNLOCKABLE_LEVEL_UNBLOCK
    # always named: it overrides the partial-unblock text when the cell ends
    # up partial (dangling Course PPtrs), and seeds the needs-probe note when
    # nothing resolved at all
    probe_cells[("metagame-node", "course")] = \
        PROBE_METAGAME_COURSE_TMPL.format(dangling=course_dangling)

    matrix = ru.assemble_cell_matrix(cell_states, SCENE_SRC_UNBLOCK,
                                     probe_cells, build_id)
    ru.validate_matrix(matrix)
    log_util.write_json(relinks / "matrix.json", matrix)

    relations_lines = _relations_lines(
        matrix, unresolved, dangling_rows, locale_report, coverage_rows,
        r5c, ledger_rows, r6c, floor_met, pair_files_emitted, edges_emitted,
        registry_rows, loc_rows)
    relations_md = ru.render_relations_md(matrix, relations_lines, build_id)
    log_util.atomic_write_text(extracted_root / "RELATIONS.md", relations_md)

    # -- exit-code contract ---------------------------------------------------
    statuses = Counter(p["status"] for p in matrix["pairs"])
    contributors = []
    open_dangles = sum(1 for d in dangling_rows
                       if d["verdict"] == "unresolved-open")
    if open_dangles:
        contributors.append(f"_dangling_guids.jsonl unresolved-open: "
                            f"{open_dangles}")
    if locale_report["registryMisses"]:
        contributors.append(f"registryMisses: "
                            f"{locale_report['registryMisses']}")
    if not floor_met:
        contributors.append("competitor floor unmet "
                            "(<3 applied sources; terminal ledger row ~floor)")
    if bridges.unreadable:
        contributors.append(f"bridge-unreadable bundles: "
                            f"{len(bridges.unreadable)}")
    lines = [
        "- exitCode: 0" if not problems and not contributors
        else ("- exitCode: 2 (completed-with-ledger)" if not problems
              else f"- exitCode: 1 ({'; '.join(problems)})"),
        f"- R1: bundlesBridged={len(roster) - len(bridges.unreadable)} "
        f"cabRows={sum(len(v.pids) for v in bridges.cabs.values())} "
        f"containerRows={len(bridges.container)} "
        f"fallbackVersionUsedBundles={len(bridges.fallback_bundles)} "
        f"containerAddressCollisions={bridges.container_collisions}",
        * [f"- R1-note: {n}" for n in r1_notes],
        f"- R2: cellsTotal=100 cellsModeled={statuses['modeled']} "
        f"cellsPartial={statuses['partial']} "
        f"cellsMissing={statuses['missing']} "
        f"pairFilesEmitted={pair_files_emitted} "
        f"edgesEmitted={edges_emitted} "
        f"sameFileResolved={r2c['sameFileResolved']} "
        f"crossFileResolved={r2c['crossFileResolved']} "
        f"sceneAttributedEdges={r2c['sceneAttributedEdges']} "
        f"unresolvedCrossFile={r2c['unresolvedCrossFile']} "
        f"builtinExternalsSkipped={r2c['builtinExternalsSkipped']} "
        f"twinEndpointEdges={twin_endpoint_edges} "
        f"unresolvedSameFile={r2c['unresolvedSameFile']} "
        f"probeUnlockableLevelRefs={probe_found}",
        f"- R2-ledger: _unresolved_pptrs rows={len(unresolved)} "
        f"(sorted by (srcKind, srcId, fieldPath, extPath, m_PathID))",
        f"- R2-attribution: chargedCells={len(attr_charges)} "
        f"chargedRefs={sum(attr_charges.values())} "
        f"landed={attr_tally['landed']} "
        f"leafKeyNamed={attr_tally['leafKeyNamed']} "
        f"nonEntityTargets={attr_tally['nonEntity']} "
        f"unresolvable={attr_tally['unresolvable']}",
        f"- R3: guidRefsTotal={guid_report['guidRefsTotal']} "
        f"distinctGuids={guid_report['distinctGuids']} "
        f"resolvedToAddress={guid_report['resolvedToAddress']} "
        f"resolvedToStub={guid_report['resolvedToStub']} "
        f"danglingDistinctGuids={guid_report['danglingDistinctGuids']} "
        f"danglingVerdicts={{'unresolved-open': {open_dangles}}} "
        f"resolveRateAddress={guid_report['resolveRateAddress']:.4f} "
        f"resolveRateStub={guid_report['resolveRateStub']:.4f} "
        f"sceneGuidEdges={r3_extra['sceneGuidEdges']}",
        f"- R4: languageSourcesRead={r4_stats['sourcesRead']} "
        f"registryRows={len(registry_rows)} "
        f"registryDistinctKeys={r4_stats['registryDistinctKeys']} "
        f"matrixKeyDiff={matrix_key_diff} "
        f"instancesTotal={locale_report['instancesTotal']} "
        f"sentinelZero={locale_report['sentinelZero']} "
        f"registryHits={locale_report['registryHits']} "
        f"registryMisses={locale_report['registryMisses']} "
        f"coverageOnNonEmpty="
        f"{locale_report['coverageOnNonEmpty']:.4f} "
        f"entityLocaleRows={len(loc_rows)} reverseRows={len(reverse_rows)}",
        f"- R5: surfacesTotal={r5c['surfacesTotal']} "
        f"mappedSchema={r5c['mappedSchema']} "
        f"documentedGaps={r5c['documentedGaps']} "
        f"tooltipTargetClasses={r5c['tooltipTargetClasses']} "
        f"tooltipGenericContainers={r5c['tooltipGenericContainers']} "
        f"localizeBindings={r5c['localizeBindings']} "
        f"hierarchyRowsRead={hier_rows}",
        f"- R6: sourcesRead={r6c['sourcesRead']} "
        f"sourcesApplied={sources_applied} floorMet={floor_met} "
        f"confirmsHard={r6c['confirmsHard']} "
        f"addsDerived={r6c['addsDerived']} "
        f"flagsMissing={r6c['flagsMissing']} "
        f"wallsRecorded={r6c['wallsRecorded']} "
        f"overlayFiles={overlay_files}",
        f"- R7: relationsMdBytes={len(relations_md.encode('utf-8'))} "
        f"generatedFrom={{\"edgesEmitted\": {edges_emitted}, "
        f"\"registryRows\": {len(registry_rows)}, "
        f"\"guidRefsTotal\": {guid_report['guidRefsTotal']}, "
        f"\"coverageRows\": {len(coverage_rows)}, "
        f"\"competitorLedgerRows\": {len(ledger_rows)}}}",
        * [f"- {d}" for d in drift_lines],
    ]
    if contributors:
        lines.append("- LEDGER-CONTRIBUTORS (exit 2): " + "; ".join(contributors))
    if bridges.unreadable:
        lines += [f"- PROBLEM: bridge pass could not open {rel}: {reason}"
                  for rel, reason in bridges.unreadable]
    lines += [f"- PROBLEM: {p}" for p in problems]
    log_util.append_run_section(extracted_root, "relink", lines)

    print(f"[relink] matrix cells modeled/partial/missing="
          f"{statuses['modeled']}/{statuses['partial']}/"
          f"{statuses['missing']} pairFiles={pair_files_emitted} "
          f"edges={edges_emitted} unresolvedPptr={len(unresolved)}")
    print(f"[relink] guidBridge refs={guid_report['guidRefsTotal']} "
          f"distinct={guid_report['distinctGuids']} "
          f"addrRate={guid_report['resolveRateAddress']:.4f} "
          f"dangling={guid_report['danglingDistinctGuids']}")
    print(f"[relink] locale registry={len(registry_rows)} rows / "
          f"{r4_stats['registryDistinctKeys']} keys diff={matrix_key_diff} "
          f"entityLocaleRows={len(loc_rows)} sentinelZero="
          f"{locale_report['sentinelZero']} misses="
          f"{locale_report['registryMisses']}")
    print(f"[relink] uiCoverage surfaces={r5c['surfacesTotal']} "
          f"mapped={r5c['mappedSchema']} gaps={r5c['documentedGaps']} "
          f"tooltipTargets={r5c['tooltipTargetClasses']}")
    print(f"[relink] competitor sources={r6c['sourcesRead']} applied="
          f"{sources_applied} floorMet={floor_met}")
    for d in drift_lines:
        print(f"[relink] {d}", file=sys.stderr)
    for p in problems:
        print(f"[relink] PROBLEM: {p}", file=sys.stderr)
    if problems:
        return 1
    if contributors:
        return 2
    return 0


def _relations_lines(matrix, unresolved, dangling_rows, locale_report,
                     coverage_rows, r5c, ledger_rows, r6c, floor_met,
                     pair_files, edges_emitted, registry_rows, loc_rows):
    """Fixed-order RELATIONS.md body sections (after the matrix table)."""
    by_status = Counter(p["status"] for p in matrix["pairs"])
    lines = [
        "",
        "## Locale-join ownership routing",
        "",
        "- `relinks/locale_availability.jsonl` stays STAGE-5 SOLE PROPERTY "
        "(piece-02 §R4 pin; v1 procedure frozen at hardJoins: 0).",
        "- The authoritative entity-granular locale relation is "
        "`relinks/entity_locale.jsonl` "
        f"({len(loc_rows)} rows; mechanism "
        f"`LocalisedString(_termID)->I2-termID->Term-key`, hard).",
        "- Registry: `relinks/i2_term_registry.jsonl` "
        f"({len(registry_rows)} rows, canonical-on-key); reverse index "
        "`relinks/locale_term_entity.jsonl`.",
        "",
        "## Ledgers (gapped resolution is data, never silence)",
        "",
        f"- `_unresolved_pptrs.jsonl`: {len(unresolved)} rows "
        "(cross-file misses, built-in externals, same-file non-entity "
        "targets; per-cell residue feeds matrix `evidence.unresolvedRefs`)",
        f"- `_dangling_guids.jsonl`: {len(dangling_rows)} rows, verdicts: "
        + json.dumps({"unresolved-open": sum(
            1 for d in dangling_rows
            if d["verdict"] == "unresolved-open")}, sort_keys=True),
        f"- `locale_join_report.json`: registryMisses="
        f"{locale_report['registryMisses']} "
        f"({', '.join('termId ' + str(u['termId']) for u in locale_report['unresolvedIds'])})"
        if locale_report["unresolvedIds"] else
        f"- `locale_join_report.json`: registryMisses=0",
        "",
        "## Proven-absent / unreachable relations (this corpus)",
        "",
    ]
    for cell in matrix["pairs"]:
        if cell["status"] in ("partial", "missing"):
            lines.append(
                f"- `{cell['srcKind']}->{cell['dstKind']}` "
                f"[{cell['status']}] {cell['unblock']}")
    lines += [
        "",
        "## UI-link coverage (bar 2)",
        "",
        f"- surfaces: {r5c['surfacesTotal']} "
        f"(mapped-schema {r5c['mappedSchema']} / documented-gap "
        f"{r5c['documentedGaps']}); tooltip target census "
        f"{r5c['tooltipTargetClasses']} classes fully partitioned; "
        f"I2.Loc.Localize bindings {r5c['localizeBindings']} route text "
        "lookups to `entity_locale.jsonl`",
        "",
        "## Competitor application (bar 3)",
        "",
        f"- sourcesRead={r6c['sourcesRead']} confirms-hard="
        f"{r6c['confirmsHard']} adds-derived={r6c['addsDerived']} "
        f"flags-missing={r6c['flagsMissing']} walls="
        f"{r6c['wallsRecorded']}; floor "
        f"{'MET' if floor_met else 'UNMET'} (≥3 applied sources required)",
    ]
    for r in ledger_rows:
        if r.get("sourceId") == "~floor":
            lines.append(f"- TERMINAL: {r['unblock']}")
        else:
            d = r.get("dispositions", {})
            lines.append(
                f"- {r.get('sourceId')}: confirms-hard={d.get('confirms-hard', 0)} "
                f"adds-derived={d.get('adds-derived', 0)} "
                f"flags-missing={d.get('flags-missing', 0)}")
    return lines


def main(argv=None) -> int:
    log_util.bootstrap_console()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("game_dir", nargs="?", default=None)
    parser.add_argument("--extracted-root", default=None)
    args = parser.parse_args(argv)
    root = None
    try:
        pack_dir = tc.resolve_pack_dir()
        root = tc.resolve_extracted_root(pack_dir)
        if args.extracted_root:
            root = Path(args.extracted_root).resolve()
        game_root = tc.resolve_game_root(args.game_dir)
        return run(game_root, root)
    except tc.StageError as exc:
        if root is not None:
            log_util.append_failure_section(root, "relink", exc.exit_code,
                                            [str(exc)])
        print(f"[relink] ERROR: {exc}", file=sys.stderr)
        return exc.exit_code


if __name__ == "__main__":
    sys.exit(main())
