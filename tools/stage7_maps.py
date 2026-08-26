#!/usr/bin/env python3
"""Stage 7 — maps (piece-03, derived map geometry, spec Revision 3).

ONE additive stage reproducing the derived map geometry layer from the
landed corpus — no new game probing beyond reading already-harvested
dumps, already-built bridges, and the already-decoded catalog:

  M1 coordinate-law artifact   — GridCoord/EPlotTileType parsed from
                                 dump.cs EVERY RUN (never hardcoded) +
                                 WorldBounds/SpawnPoint rows + projection
                                 law + loadassets_read.json (R4 evidence;
                                 honest inconclusive-from-dumpcs state,
                                 terminal policy for this buildId)
  M2 scenario emission         — levels/scenarios/plots/rooms/tiles/
                                 placements/students/staff JSONL with
                                 verbatim coordinates and per-row
                                 provenance; closed four-generation enum;
                                 R4 binding: NO canonical generation,
                                 twins ride variantOf as first-class rows
  M3 definition resolution     — PPtr-authoritative join (the PPtr is the
                                 KEY, `_id` corroborates); externals→CAB
                                 ladder mandatory for cross-file refs;
                                 measured, not speculative, widening
  M4 landscape layer           — layers index + verbatim LandscapeRecord
                                 maps + terrain value-semantics decode
                                 attempt (G7; blocked is legal + ledgered)
  M5 doors partial-data        — validators verbatim, substring-predicate
                                 placement projection, dual id-space sweeps
                                 + the HARD GATE (in-stage pre-write
                                 assertion shared verbatim with the AC11
                                 audit rule)
  M6 named plots               — localized display-name rows through the
                                 EXISTING i2 registry (no parallel locale
                                 layer — single-writer discipline)
  M7 imagery candidates        — seven literal predicates over catalog
                                 ADDRESSES only; zero decoded bytes (G9)
  M8 assembly                  — _manifest.sha256, self-naming ledgers,
                                 EXTRACTION-LOG run section

Exit codes (piece-1 contract): 0 success · 1 stage failure · 2
completed-with-ledger (EXPECTED steady state until the §5 ledgers close)
· 3 environment/gate refusal. Single-writer discipline: this stage writes
ONLY under extracted/maps/ plus its EXTRACTION-LOG run section — it READS
the relink bridges and registry, never writes them.

Determinism: byte-identical reruns; UTF-8 + LF; sorted enumeration +
sorted JSON keys; floats serialize by shortest-round-trip repr; atomic
temp+rename writes; no wall-clock timestamps inside outputs.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import log_util
import maps_util as mu
import relink_util as ru
import tpc_common as tc

STAGE_ID = "maps"

# ---------------------------------------------------------------------------
# Reconciliation seeds (piece-03 §2 fact table + arbiter probes). Every one
# is drift-checked: movement prints a DRIFT line and the FRESH measurement
# wins — never a silent stale constant. No campus/DLC/level-name literal is
# hardcoded anywhere in this stage (axis openness, AC10).

SEED_SCENARIOS_READ = 51
SEED_LEVELS_ROWS = 28
SEED_LEVEL_GENERATION_SPLIT = {"levels-prefabs": 13, "configs-assets-all": 9,
                               "dlc-space-configs": 4, "dlc-ghost-configs": 2}
SEED_PLOTS = 1031
SEED_ROOMS = 5188
SEED_PLACEMENT_FAMILIES = {"room": 22878, "arrival": 86, "nonArea": 7,
                           "waypoint": 25, "plotActivation": 8}
SEED_PLACEMENTS_TOTAL = sum(SEED_PLACEMENT_FAMILIES.values())
SEED_STUDENTS = 20
SEED_STAFF = 32
SEED_LANDSCAPE_LAYERS = 4082
SEED_ZERO_DIM_LAYERS = 12
SEED_BRUSH_DATABASES = 3
SEED_BRUSH_DEFINITIONS = 170
SEED_VALIDATORS = 54
SEED_VALIDATOR_REFS = 71
SEED_DOOR_PLACEMENTS = 1261
SEED_DOOR_KINDS = 55
SEED_SLIDING_DOOR_COMPONENTS = 37
SEED_INTEGER_SWEEP_BEST_MATCH = 13
SEED_NAMED_PLOTS = 12
SEED_INDEX_ENTRIES = 3779
SEED_INDEX_BUNDLES = 7
SEED_RESOLVED = 22210
SEED_RESOLVE_RATE = 0.9658
SEED_RESIDUE = 786
SEED_RESIDUE_CROSS_FILE = 771
SEED_RESIDUE_SAME_FILE_MISS = 15
SEED_CORROBORATION = {"match": 22200, "twinMismatch": 0, "absent": 10}
SEED_ADDRESSES_SCANNED = 56331
SEED_PREDICATE_COUNTS = {
    "metamap-case-sensitive": 1094,
    "metamap-case-insensitive": 1140,
    "loadingscreen-images": 117,
    "imagelevel-strict-prefix": 42,
    "imagelevel-family": 66,
    "level-image-icon-screenshot": 66,
    "minimap-any-spelling": 0,
}

DOOR_SUBSTRING = "Item_Door_"          # case-sensitive SUBSTRING (F16 rule)

DECLARED_OUTPUTS = [
    "coordinate_law.json",
    "loadassets_read.json",
    "levels.jsonl",
    "scenarios.jsonl",
    "plots.jsonl",
    "plots_tiletypes.jsonl",
    "rooms.jsonl",
    "rooms_tiles.jsonl",
    "item_placements.jsonl",
    "students.jsonl",
    "staff_records.jsonl",
    "landscape_layers.jsonl",
    "landscape_maps.jsonl",
    "terrain_decode.json",
    "door_validators.jsonl",
    "door_placement_index.jsonl",
    "door_id_space.json",
    "named_plots.jsonl",
    "imagery_candidates.jsonl",
    "imagery_predicates.json",
    "join_report.json",
    "_absences.jsonl",
    "_unresolved_placements.jsonl",
]


# ---------------------------------------------------------------------------
# Small helpers

def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def vec3(node):
    """Verbatim {x,y,z} copy (None-preserving) of a Vector3-shaped dict."""
    if not isinstance(node, dict):
        return None
    return {"x": node.get("x"), "y": node.get("y"), "z": node.get("z")}


def strip_private(row: dict) -> dict:
    return {k: v for k, v in row.items() if not k.startswith("_")}


def asset_stem(address):
    if not address:
        return None
    leaf = str(address).replace("\\", "/").rsplit("/", 1)[-1]
    for ext in (".asset", ".prefab", ".unity", ".png", ".tga"):
        if leaf.endswith(ext):
            return leaf[: -len(ext)]
    return leaf or None


def campaign_part(address):
    if not address:
        return None
    for seg in str(address).replace("\\", "/").split("/"):
        if CAMPAIGN_PART_RE.match(seg):
            return seg
    return None


CAMPAIGN_PART_RE = re.compile(r"^Part\d+")


def point_in_bounds(pos, center, extent) -> bool:
    if not isinstance(pos, dict) or not isinstance(center, dict) \
            or not isinstance(extent, dict):
        return False
    try:
        return all(abs(pos[k] - center[k]) <= extent[k]
                   for k in ("x", "y", "z"))
    except TypeError:
        return False


def manifest_key(path: Path) -> str | None:
    """export-manifest `outRelPath` spelling for a dump under the extracted
    root (`harvest/monobehaviours/…`)."""
    rel = str(path).replace("\\", "/")
    cut = rel.find("harvest/")
    if cut < 0:
        # synthetic trees may hand us absolute paths under another root —
        # fall back to the tail after the monobehaviours segment
        cut = rel.find("monobehaviours/")
        if cut >= 0:
            return "harvest/" + rel[cut:]
        return rel
    return rel[cut:]


def drift(seed, fresh, what):
    if seed != fresh:
        return (f"DRIFT: {what} measures {fresh} against seed {seed} — "
                "fresh wins")
    return None


# ---------------------------------------------------------------------------
# Upstream gate — every §3 input; a missing artifact exits 3 NAMING it

def check_inputs(extracted_root: Path) -> dict:
    mono = extracted_root / "harvest" / "monobehaviours"
    required_files = [
        extracted_root / "identity.json",
        extracted_root / "bundle-roster.jsonl",
        extracted_root / "harvest" / "export-manifest.jsonl",
        extracted_root / "harvest" / "externals.jsonl",
        extracted_root / "relinks" / "bridges" / "cab_index.jsonl",
        extracted_root / "relinks" / "bridges" / "container_index.jsonl",
        extracted_root / "relinks" / "i2_term_registry.jsonl",
        extracted_root / "addressables" / "catalog.json",
        extracted_root / "decompiled" / "il2cppdumper" / "dump.cs",
    ]
    missing = [p for p in required_files if not p.is_file()]
    if not mono.is_dir():
        missing.append(mono)

    def class_dirs(cls):
        return sorted(mono.glob(f"*/{cls}")) if mono.is_dir() else []

    gates = {
        "mono": mono,
        "scenario_dirs": class_dirs("TPC.LevelScenarioV2"),
        "level_dirs": class_dirs("TPC.LevelConfig"),
        "validator_dirs": class_dirs("TPC.ItemValidator_Door"),
        "brush_db_dirs": class_dirs("TPC.LandscapeBrushDatabase"),
        "brush_def_dirs": class_dirs("TPC.LandscapeBrushDefinition"),
    }
    named_globs = [
        ("harvest/monobehaviours/**/TPC.LevelScenarioV2/*.json",
         gates["scenario_dirs"]),
        ("harvest/monobehaviours/**/TPC.LevelConfig/*.json",
         gates["level_dirs"]),
        ("harvest/monobehaviours/**/TPC.ItemValidator_Door/*.json",
         gates["validator_dirs"]),
        ("harvest/monobehaviours/**/TPC.LandscapeBrushDatabase/*.json",
         gates["brush_db_dirs"]),
        ("harvest/monobehaviours/**/TPC.LandscapeBrushDefinition/*.json",
         gates["brush_def_dirs"]),
    ]
    for glob_name, dirs in named_globs:
        if not dirs:
            missing.append(extracted_root / glob_name)
    if missing:
        raise tc.StageError(
            f"stage '{STAGE_ID}' is missing upstream artifacts "
            f"({', '.join(p.as_posix() for p in missing)}) — prepare the "
            "tree first (client mode: run the pipeline without this stage; "
            "hostless smoke: tests/build_fixture_tree.py --stage maps)",
            exit_code=3)
    return gates


def load_roster_maps(extracted_root: Path):
    bare_to_rel = {}
    for row in tc.load_roster(extracted_root):
        bare = mu.bundle_basename(row["relpath"])
        prev = bare_to_rel.setdefault(bare, row["relpath"])
        if prev != row["relpath"]:
            raise tc.StageError(
                f"roster bundle basenames collide ({bare}) — join keys "
                "ambiguous", exit_code=1)
    return bare_to_rel


def load_manifest_indexes(extracted_root: Path):
    """export-manifest.jsonl → (out_index, loc_index, def_index, n_rows).

    out_index : outRelPath → {bundle, pathId, class}
    loc_index : (bundleRel, pathId) → (class, outRelPath)
    def_index : (bundleRel, pathId) → outRelPath (GameItem{,Lite,Variation})
    """
    out_index = {}
    loc_index = {}
    def_index = {}
    def_classes = set(mu.DEFINITION_CLASSES)
    n_rows = 0
    with open(extracted_root / "harvest" / "export-manifest.jsonl",
              encoding="utf-8", newline="\n") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            n_rows += 1
            out_rel = row["outRelPath"]
            bundle = row["sourceBundle"]
            pid = int(row["pathId"])
            cls = str(row["class"])
            out_index[out_rel] = {"bundle": bundle, "pathId": pid,
                                  "class": cls}
            loc_index[(bundle, pid)] = (cls, out_rel)
            if cls in def_classes:
                def_index[(bundle, pid)] = out_rel
    return out_index, loc_index, def_index, n_rows


def widen_definition_index(extracted_root: Path, classes, def_index):
    """Measured widening (M3 step 1): add EVERY dump of each widening class
    to the index — one extra manifest stream, classes sorted."""
    want = set(classes)
    added = 0
    with open(extracted_root / "harvest" / "export-manifest.jsonl",
              encoding="utf-8", newline="\n") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row["class"] in want:
                def_index[(row["sourceBundle"], int(row["pathId"]))] = \
                    row["outRelPath"]
                added += 1
    return added


class TargetCache:
    """Loaded target dumps with a bounded cache (corroboration + names).
    Manifest `outRelPath` values are relative to the extraction root and
    are resolved against it here, so the caller's cwd never matters."""

    def __init__(self, extracted_root: Path, limit=4096):
        self.extracted_root = extracted_root
        self.limit = limit
        self._cache = {}
        self.loads = 0

    def load(self, out_rel: str):
        hit = self._cache.get(out_rel)
        if hit is not None:
            return hit
        self.loads += 1
        path = Path(out_rel)
        if not path.is_absolute():
            path = self.extracted_root / path
        payload = load_json(path)
        if len(self._cache) >= self.limit:
            self._cache.clear()
        self._cache[out_rel] = payload
        return payload


class PlacementResolver:
    """M3 ladder: (a) same-file index hit · (b) fileId ≥ 1 through
    externals → CAB (mandatory leg — Unity pathIds are per-serialized-file
    and bundles carry several, so (bundle, pathId) alone under-determines a
    target) → index · (c) structured miss carrying extFileId/dstCab."""

    def __init__(self, loc_index, def_index, externals, cab_lookup):
        self.loc_index = loc_index
        self.def_index = def_index
        self.externals = externals
        self.cab_lookup = cab_lookup

    def locate(self, src_bundle, src_source_file, pptr):
        fid, pid = pptr
        if fid == 0:
            if (src_bundle, pid) in self.def_index:
                return {"kind": "index", "bundle": src_bundle, "pathId": pid,
                        "method": "pptr-export-index", "extFileId": 0,
                        "dstCab": ""}
            cls_out = self.loc_index.get((src_bundle, pid))
            if cls_out is not None:
                return {"kind": "widened", "bundle": src_bundle,
                        "pathId": pid, "method": "pptr-export-index",
                        "extFileId": 0, "dstCab": "",
                        "candidateClass": cls_out[0]}
            return {"kind": "missing",
                    "reason": "same-file pathId is neither an indexed "
                              "definition dump nor any exported object",
                    "extFileId": 0, "dstCab": ""}
        exts = self.externals.get((src_bundle,
                                   str(src_source_file or "").lower()))
        if exts is None:
            return {"kind": "missing",
                    "reason": "owning serialized file unknown for source "
                              "dump",
                    "extFileId": fid, "dstCab": ""}
        path = exts.get(fid)
        if path is None:
            return {"kind": "missing",
                    "reason": f"external fileId {fid} not in the serialized "
                              "file's externals table",
                    "extFileId": fid, "dstCab": ""}
        if ru.builtin_external(path):
            return {"kind": "missing",
                    "reason": f"built-in external is not an entity target: "
                              f"{path}",
                    "extFileId": fid, "dstCab": str(path)}
        cab = ru.simplify_external_path(path)
        homes = self.cab_lookup.bundles_for(cab, pid)
        for bundle in homes:
            if (bundle, pid) in self.def_index:
                return {"kind": "index", "bundle": bundle, "pathId": pid,
                        "method": "pptr-externals-cab", "extFileId": fid,
                        "dstCab": cab}
        for bundle in homes:
            cls_out = self.loc_index.get((bundle, pid))
            if cls_out is not None:
                return {"kind": "widened", "bundle": bundle, "pathId": pid,
                        "method": "pptr-externals-cab", "extFileId": fid,
                        "dstCab": cab, "candidateClass": cls_out[0]}
        return {"kind": "missing",
                "reason": "external CAB/pathId not found in any indexed "
                          "serialized file",
                "extFileId": fid, "dstCab": cab}

    def target_payload(self, located, targets: TargetCache):
        out_rel = self.def_index.get((located["bundle"], located["pathId"]))
        if out_rel is None:
            return None
        return targets.load(out_rel)


# ---------------------------------------------------------------------------
# Catalog / registry readers

def load_catalog_guid_index(catalog_path: Path):
    data = load_json(catalog_path)
    guid_index = {}
    addresses = []
    addr_bundles = {}
    for key in data.get("keys") or []:
        addr = key.get("address")
        if not addr:
            continue
        addresses.append(addr)
        bundle = key.get("bundle")
        bare = mu.bundle_basename(bundle) if bundle else None
        addr_bundles.setdefault(addr, set())
        if bare:
            addr_bundles[addr].add(bare)
        if key.get("kind") != "guid":
            continue
        g = key.get("key")
        if isinstance(g, str) and g:
            guid_index.setdefault(g, []).append({"address": addr,
                                                 "bundle": bare})
    for rows in guid_index.values():
        rows.sort(key=lambda r: (str(r["address"]), str(r["bundle"])))
    return guid_index, addresses, addr_bundles


def _first_address(guid_index, guid):
    if not guid:
        return None
    entries = guid_index.get(guid)
    return entries[0]["address"] if entries else None


def _guid_of(ref):
    if isinstance(ref, dict):
        g = ref.get("m_AssetGUID")
        if isinstance(g, str) and g:
            return g
    return None


def load_term_registry(path: Path) -> dict[int, str]:
    """termId → Term key (canonical-on-key; ties broken lexicographically
    so reruns stay byte-stable)."""
    best: dict[int, tuple[str, str]] = {}
    with open(path, "r", encoding="utf-8", newline="\n") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            tid = row.get("termId")
            key = row.get("termKey")
            if not isinstance(tid, int) or not isinstance(key, str):
                continue
            rank = (0 if row.get("canonical") else 1, key)
            prev = best.get(tid)
            if prev is None or rank < prev[0]:
                best[tid] = (rank, key)
    return {tid: v[1] for tid, v in best.items()}


def load_matrix_locales(path: Path | None) -> dict[str, list]:
    if path is None or not path.is_file():
        return {}
    data = load_json(path)
    out = {}
    for key, val in (data.get("keys") or {}).items():
        if isinstance(val, dict) and isinstance(val.get("locales"), list):
            out[key] = sorted(str(x) for x in val["locales"])
    return out


def load_media_catalogue_names(path: Path | None):
    """(bare bundle, name) → {classes} — the M7 cross-reference surface."""
    idx = {}
    if path is None or not path.is_file():
        return idx
    with open(path, "r", encoding="utf-8", newline="\n") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            bundle = row.get("bundle")
            name = row.get("name")
            if not bundle or not name:
                continue
            idx.setdefault((mu.bundle_basename(bundle), str(name)),
                           set()).add(str(row.get("class")))
    return idx


# ---------------------------------------------------------------------------
# M1 — coordinate-law artifact

def run_m1(dump_cs_path: Path, level_rows, build_id):
    text = dump_cs_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    grid = mu.parse_grid_constants(lines)
    palette = mu.parse_tile_palette(lines)

    drift_lines = []
    for name, expected in mu.EXPECTED_GRID.items():
        got = grid["constants"].get(name)
        if got != expected:
            drift_lines.append(
                f"DRIFT: GridCoord.{name} parses {got!r} against embedded "
                f"expectation {expected!r} — the parsed constant wins")
    for name, expected in mu.EXPECTED_PALETTE.items():
        got = palette["values"].get(name)
        if got != expected:
            drift_lines.append(
                f"DRIFT: EPlotTileType.{name} parses {got!r} against "
                f"embedded expectation {expected!r} — the parsed value wins")

    # spawn deviants are MEASURED against the modal SpawnPoint — deviants
    # are DATA rows, never errors, and never name-keyed
    spawn_counter = Counter(
        (r["spawnPoint"]["x"], r["spawnPoint"]["y"], r["spawnPoint"]["z"])
        for r in level_rows if r["spawnPoint"])
    modal = min(spawn_counter.items(),
                key=lambda kv: (-kv[1], repr(kv[0])))[0] \
        if spawn_counter else None

    world_bounds = []
    spawn_points = []
    for r in sorted(level_rows,
                    key=lambda r: (r["levelId"], r["source"]["pathId"])):
        world_bounds.append({
            "levelName": r["levelId"],
            "center": dict(r["worldBounds"]["center"]),
            "extent": dict(r["worldBounds"]["extent"]),
            "source": dict(r["source"]),
        })
        sp = r["spawnPoint"]
        spawn_points.append({
            "levelName": r["levelId"],
            "value": dict(sp),
            "variant": bool(spawn_counter) and
            (sp["x"], sp["y"], sp["z"]) != modal,
            "source": dict(r["source"]),
        })
    variants = sum(1 for s in spawn_points if s["variant"])

    # the derivation stated in `projection`, COMPUTED from the parsed
    # constants over the modal bounds — never pasted numbers
    numeric_extents = [
        (r["worldBounds"]["extent"]["x"], r["worldBounds"]["extent"]["y"],
         r["worldBounds"]["extent"]["z"])
        for r in level_rows
        if isinstance(r["worldBounds"]["extent"], dict)
        and isinstance(r["worldBounds"]["extent"].get("x"), (int, float))
        and isinstance(r["worldBounds"]["extent"].get("z"), (int, float))]
    modal_extent = max(numeric_extents, key=lambda e: e[0] * e[2]) \
        if numeric_extents else {"x": 0, "y": 0, "z": 0}
    cell_inv = grid["constants"]["CellSizeInv"]
    footprint = {k: modal_extent[i] * 2
                 for i, k in enumerate(("x", "y", "z"))} \
        if isinstance(modal_extent, tuple) else dict(modal_extent)
    cells = {k: footprint[k] * cell_inv for k in footprint}

    doc = {
        "grid": {
            "type": "GridCoord",
            "sourceLine": grid["sourceLine"],
            "cellSize": grid["constants"]["CellSize"],
            "cellSizeSq": grid["constants"]["CellSizeSq"],
            "cellSizeInv": grid["constants"]["CellSizeInv"],
            "cellSizeHalf": grid["constants"]["CellSizeHalf"],
            "parsedFrom": "decompiled/il2cppdumper/dump.cs",
        },
        "plotTilePalette": {
            "type": "EPlotTileType",
            "sourceLine": palette["sourceLine"],
            "values": dict(palette["values"]),
        },
        "worldBounds": world_bounds,
        "spawnPoints": spawn_points,
        "projection": {
            "law": "map_px = (world_xz - campus_min) * scale",
            "frame": "single shared world frame per campus",
            "cellsPerWorldUnit": cell_inv,
            "derivation": {
                "method": "modal-worldbounds-extent x2 x CellSizeInv",
                "worldFootprint": footprint,
                "campusCells": cells,
            },
        },
        "buildId": build_id,
    }
    load_doc = build_loadassets_read(lines, build_id)
    counters = {
        "gridConstParsed": len(grid["constants"]),
        "gridDrift": len(drift_lines),
        "boundsRows": len(world_bounds),
        "spawnRows": len(spawn_points),
        "spawnVariants": variants,
        "loadassetsReadStatus": load_doc["readStatus"],
    }
    return doc, load_doc, counters, drift_lines


def build_loadassets_read(lines, build_id):
    info = mu.find_loadassets(lines)
    if info is None:
        raise tc.StageError(
            "loadassets_read emitter could not find the 'public IEnumerator "
            "LoadAssets() { }' declaration or its compiler-generated "
            "iterator state machine in decompiled/il2cppdumper/dump.cs — "
            "loud failure beats a silent guess", exit_code=1)
    num = info.pop("_iteratorNum")
    members = info["members"]
    doc = {
        "subject": "TPC.LevelConfig.LoadAssets",
        "declaration": info,
        # R4.1: inconclusive-from-dumpcs is TERMINAL policy for buildId
        # 20226581 — no canonical flag anywhere; both generations ride
        # variantOf as first-class rows. The body-read below is OPTIONAL
        # corroboration routed OUTSIDE stage maps.
        "readStatus": "inconclusive-from-dumpcs",
        "instantiatedGeneration": None,
        "evidence": [],
        "unblock": (
            f"OPTIONAL corroboration only (R4.1): decompile "
            f"d__{num}.MoveNext (RVA {members['moveNextRva']} / VA "
            f"{members['moveNextVa']}) via Ghidra/IDA over GameAssembly.dll "
            "— routes to the orchestrator as an out-of-stage follow-up; "
            "emission never depends on it"),
        "buildId": build_id,
    }
    return doc


# ---------------------------------------------------------------------------
# M2 — LevelConfig walk (levels.jsonl rows + coordinate-law inputs)

def walk_level_configs(paths, out_index, guid_index, container_reverse,
                       build_id, problems):
    rows = []
    university_dumps = []
    # sibling level-config classes (measured: TPC.UniversityLevelConfig et
    # al.) are OUT OF SCOPE for this stage — counted into _absences.jsonl,
    # never silently skipped
    for d in sorted(paths["mono"].glob("*/TPC.*LevelConfig")):
        if d.name == "TPC.LevelConfig" or not d.is_dir():
            continue
        for path in sorted(d.glob("*.json")):
            payload_class = None
            try:
                payload_class = str(load_json(path).get("_scriptClass"))
            except ValueError:
                continue
            university_dumps.append({"class": payload_class,
                                     "dump": path.name})
    for d in paths["level_dirs"]:
        for path in sorted(d.glob("*.json")):
            meta = out_index.get(manifest_key(path))
            if meta is None:
                problems.append(
                    f"LevelConfig dump {path.name} is absent from harvest/"
                    "export-manifest.jsonl — provenance unresolved")
                continue
            payload = load_json(path)
            cls = str(payload.get("_scriptClass"))
            if cls != "TPC.LevelConfig":
                # TPC.UniversityLevelConfig and any future sibling config
                # class: counted into _absences.jsonl as
                # out-of-scope-for-this-stage, never silently skipped
                university_dumps.append({"class": cls, "dump": path.name})
                continue
            bare = mu.bundle_basename(meta["bundle"])
            pid = int(meta["pathId"])
            level_scene = payload.get("LevelScene")
            if not isinstance(level_scene, str) or not level_scene:
                problems.append(
                    f"LevelConfig dump {path.name} carries an empty "
                    "LevelScene — the F14 identity law (levelId := "
                    "LevelScene verbatim; m_Name never carries identity) "
                    "cannot hold")
                continue
            wb = payload.get("WorldBounds") or {}
            sp = payload.get("SpawnPoint") or {}
            icon_cfg = payload.get("GameItemIconConfig") or {}
            scen_ref = payload.get("_ScenarioV2")
            guid = _guid_of(scen_ref) if isinstance(scen_ref, dict) else None
            asset_address = container_reverse.address(bare, pid)
            generation = mu.generation_for_bundle(bare)
            rows.append({
                "levelId": level_scene,
                "contentAxis": mu.axis_for_bundle(bare),
                "worldBounds": {"center": vec3(wb.get("m_Center")),
                                "extent": vec3(wb.get("m_Extent"))},
                "spawnPoint": vec3(sp),
                "plotCount": {"value": payload.get("PlotCount"),
                              "generation": generation,
                              "variantOf": None},
                "sceneNames": {
                    "levelScene": payload.get("LevelScene"),
                    "optimized": payload.get("LevelScene_Optimized"),
                    "hud": payload.get("LevelHUDScene"),
                    "databaseScene": payload.get("LevelDatabaseScene"),
                },
                "scenarioGuid": guid,
                "scenarioAddress": _first_address(guid_index, guid),
                "campaignPart": None,
                "assetAddress": asset_address,
                "assetNameStem": None,
                "imagery": {
                    "loadingScreenBackground": _first_address(
                        guid_index, _guid_of(payload.get(
                            "LoadingScreenBackgroundAssetReference"))),
                    "sandboxScreenshot": _first_address(
                        guid_index, _guid_of(payload.get(
                            "SandboxLevelScreenshot"))),
                    "sandboxContainerScreenshot": _first_address(
                        guid_index, _guid_of(payload.get(
                            "SandboxLevelContainerScreenshot"))),
                    "levelIcon": _first_address(
                        guid_index, _guid_of(payload.get("LevelIcon"))),
                },
                "iconRenderCamera": {
                    "cameraDistance": icon_cfg.get("CameraDistance"),
                    "cameraFov": icon_cfg.get("CameraFOV"),
                    "cameraRotation": vec3(icon_cfg.get("CameraRotation")),
                    "textureSize": icon_cfg.get("TextureSize"),
                },
                "source": {"bundle": bare, "pathId": pid},
                "buildId": build_id,
            })

    # derived planes — campaignPart from the resolved scenario address,
    # assetNameStem from the reverse-container asset address
    for row in rows:
        row["campaignPart"] = campaign_part(row["scenarioAddress"])
        row["assetNameStem"] = asset_stem(row["assetAddress"])

    # variantOf links twins sharing levelId (R4.2: BOTH rows stay
    # first-class in the closed enum; PlotCount agreement is NOT required
    # for the link, and disagreement collapses neither row)
    by_level = {}
    for row in rows:
        by_level.setdefault(row["levelId"], []).append(row)
    for group in by_level.values():
        if len(group) < 2:
            continue
        ordered = sorted(group, key=lambda r: (r["plotCount"]["generation"],
                                               r["source"]["pathId"]))
        for row in group:
            row["plotCount"]["variantOf"] = [
                {"generation": other["plotCount"]["generation"],
                 "pathId": other["source"]["pathId"]}
                for other in ordered if other is not row]
    return rows, university_dumps


# ---------------------------------------------------------------------------
# M2 — scenario walk

class ScenarioWalk:
    """One scenario payload → every M2/M4 row family. Placements resolve
    inline; landscape_maps rows buffer PER SCENARIO so the HARD GATE sees
    complete per-scenario room-id sets before any row streams."""

    def __init__(self):
        self.scenario_rows = []
        self.plot_rows = []
        self.room_rows = []
        self.placement_rows = []
        self.student_rows = []
        self.staff_rows = []
        self.layer_rows = []
        self.named_candidates = []
        self.landscape_pending = {}     # scenarioName → [rows]
        self.room_ids_by_scenario = {}
        self.terrain_cells = Counter()
        self.terrain_scenarios = set()
        self.frame_check = {fam: {"checked": 0, "inside": 0}
                            for fam in mu.PLACEMENT_FAMILIES
                            if fam != mu.ROOM_FAMILY}
        self.unusable_scenarios = []

    # -- main -------------------------------------------------------------
    def walk(self, path: Path, payload: dict, meta: dict, build_id,
             resolver: PlacementResolver, targets: TargetCache):
        bare = mu.bundle_basename(meta["bundle"])
        pid = int(meta["pathId"])
        axis = mu.axis_for_bundle(bare)
        name = payload.get("m_Name")
        source_file = str(payload.get("_sourceFile") or "")
        lr = payload.get("_levelRecord")
        if not isinstance(lr, dict):
            lr = {}
        source = {"bundle": bare, "pathId": pid}

        plots = lr.get("PlotRecords") or []
        rooms = lr.get("RoomRecords") or []
        arrivals = lr.get("ArrivalItemRecords") or []
        non_area = lr.get("NonAreaItemRecords") or []
        waypoints = lr.get("NavPlotWaypointRecords") or []
        students = lr.get("StudentRecords") or []
        staff_gen = lr.get("StaffGenerationRecord")
        staff = (staff_gen or {}).get("StaffRecords") or []

        items_by_family = {
            "room": sum(len(r.get("ItemRecords") or []) for r in rooms),
            "arrival": len(arrivals),
            "nonArea": len(non_area),
            "waypoint": len(waypoints),
            "plotActivation": sum(
                len(r.get("PlotActivationItemRecords") or []) for r in plots),
        }
        self.scenario_rows.append({
            "scenarioName": name,
            "levelRecordName": lr.get("ScenarioName"),
            "contentAxis": axis,
            "version": lr.get("Version"),
            "nextPlotUniqueId": lr.get("NextPlotUniqueId"),
            "counts": {
                "plots": len(plots),
                "rooms": len(rooms),
                "itemsByFamily": items_by_family,
                "itemsTotal": sum(items_by_family.values()),
                "students": len(students),
                "staff": len(staff),
            },
            "source": dict(source),
            "buildId": build_id,
        })

        # ---- plots FIRST: bounds feed the OQ2 cross-check and the
        # derived-block arithmetic downstream
        plot_bounds = []
        for rec_i, pr in enumerate(plots):
            uid = pr.get("PlotUniqueId")
            b = pr.get("Bounds") or {}
            center = vec3(b.get("m_Center"))
            extent = vec3(b.get("m_Extent"))
            plot_bounds.append((uid, center, extent))
            disp = pr.get("DisplayName")
            disp = disp if isinstance(disp, dict) else {}
            term_id = disp.get("_termID")
            use_named = bool(pr.get("UsePlotDisplayName"))
            tt = pr.get("TileTypes")
            tt = tt if isinstance(tt, dict) else None
            activation = pr.get("PlotActivationItemRecords") or []
            prow = {
                "scenarioName": name,
                "plotUniqueId": uid,
                "persistentName": pr.get("PersistentName"),
                "definitionId": pr.get("DefinitionID"),
                "definitionPptr": _pptr_json(pr.get("Definition")),
                "bounds": {"center": center, "extent": extent},
                "locked": pr.get("Locked"),
                "initiallyBuilt": pr.get("InitiallyBuilt"),
                "buildCost": pr.get("BuildCost"),
                "ignoreForCameraBounds": pr.get("IgnoreForCameraBounds"),
                "usePlotDisplayName": 1 if use_named else 0,
                "displayNameTermId":
                    term_id if isinstance(term_id, int) and term_id != 0
                    else None,
                "tileTypes": {"width": tt.get("_width"),
                              "height": tt.get("_height")}
                if tt is not None else None,
                "tilesRef": {"artifact": "plots_tiletypes.jsonl",
                             "key": [name, uid]},
                "layerCount": len(pr.get("PlotLayerRecords") or []),
                "plotActivationCount": len(activation),
                "source": {"bundle": bare, "pathId": pid,
                           "recordIndex": rec_i},
                "buildId": build_id,
            }
            prow["_tilesRow"] = {
                "scenarioName": name,
                "plotUniqueId": uid,
                "tileTypes": _verbatim_map(tt),
                "source": {"bundle": bare, "pathId": pid,
                           "recordIndex": rec_i},
                "buildId": build_id,
            }
            self.plot_rows.append(prow)
            if use_named:
                self.named_candidates.append({
                    "scenarioName": name,
                    "plotUniqueId": uid,
                    "persistentName": pr.get("PersistentName"),
                    "displayNameTermId": prow["displayNameTermId"],
                    "source": {"bundle": bare, "pathId": pid,
                               "recordIndex": rec_i},
                })

        # ---- landscape layers (+ per-scenario verbatim-map buffers)
        land_rows = []
        for rec_i, pr in enumerate(plots):
            uid = pr.get("PlotUniqueId")
            for li, layerrec in enumerate(pr.get("PlotLayerRecords") or []):
                lsc = layerrec.get("LandscapeRecord")
                lsc = lsc if isinstance(lsc, dict) else {}
                terrain = lsc.get("TerrainMap")
                objmap = lsc.get("LandscapeObjectMap")
                attrmap = lsc.get("AttributeMap")
                hist_t = _histogram(terrain)
                hist_o = _histogram(objmap)
                for v, n in hist_t.items():
                    self.terrain_cells[v] += n
                if hist_t:
                    self.terrain_scenarios.add(name)
                self.layer_rows.append({
                    "scenarioName": name,
                    "plotUniqueId": uid,
                    "layerIndex": li,
                    "plotLayerFlags": layerrec.get("PlotLayerFlags"),
                    "roomRecordId": layerrec.get("RoomRecordID"),
                    "dims": {"terrain": _dims(terrain),
                             "object": _dims(objmap),
                             "attribute": _dims(attrmap)},
                    "valueHistograms": {"terrain": hist_t, "object": hist_o},
                    "source": {"bundle": bare, "pathId": pid,
                               "recordIndex": rec_i, "layerIndex": li},
                    "buildId": build_id,
                })
                land_rows.append({
                    "scenarioName": name,
                    "plotUniqueId": uid,
                    "layerIndex": li,
                    "terrainMap": _verbatim_map(terrain),
                    "landscapeObjectMap": _verbatim_map(objmap),
                    "attributeMap": attrmap,
                    "buildId": build_id,
                })
        self.landscape_pending.setdefault(name, []).extend(land_rows)

        # ---- rooms
        room_world = {}
        for rec_i, rr in enumerate(rooms):
            uid = rr.get("UniqueID")
            wp = vec3(rr.get("WorldPosition"))
            room_world[id(rr)] = wp
            tiles = rr.get("Tiles")
            tiles = tiles if isinstance(tiles, dict) else None
            rrow = {
                "scenarioName": name,
                "uniqueId": uid,
                "anchor": _grid_anchor(rr.get("Anchor")),
                "worldPosition": wp,
                "definitionId": rr.get("DefinitionID"),
                "definitionPptr": _pptr_json(rr.get("Definition")),
                "tiles": {"width": tiles.get("_width"),
                          "height": tiles.get("_height")}
                if tiles is not None else None,
                "tilesRef": {"artifact": "rooms_tiles.jsonl",
                             "key": [name, uid]},
                "plotLayer": rr.get("PlotLayer"),
                "childRoomRecordIds": list(rr.get("ChildRoomRecordIDs")
                                           or []),
                "itemCount": len(rr.get("ItemRecords") or []),
                "source": {"bundle": bare, "pathId": pid,
                           "recordIndex": rec_i},
                "buildId": build_id,
            }
            rrow["_tilesRow"] = {
                "scenarioName": name,
                "uniqueId": uid,
                "tiles": _verbatim_map(tiles),
                "source": {"bundle": bare, "pathId": pid,
                           "recordIndex": rec_i},
                "buildId": build_id,
            }
            self.room_rows.append(rrow)
        uids = self.room_ids_by_scenario.setdefault(name, set())
        uids.update(r["uniqueId"] for r in self.room_rows
                    if r["scenarioName"] == name)

        # ---- placements (ALL five families, ONE file)
        new_rows: list[dict] = []

        def make_item_row(family, rec, *, room_rec=None, room_uid=None,
                          plot_uid=None, room_index=None, plot_index=None,
                          item_index=None):
            wp = room_world.get(id(room_rec)) if room_rec is not None \
                else None
            local = vec3(rec.get("LocalPosition"))
            derived = None
            if family == mu.ROOM_FAMILY and wp is not None \
                    and local is not None:
                derived = {
                    "world": {"x": wp["x"] + local["x"],
                              "y": wp["y"] + local["y"],
                              "z": wp["z"] + local["z"]},
                    "method": "roomWorldPlusLocal",
                }
            if family == mu.ROOM_FAMILY:
                src = {"bundle": bare, "pathId": pid,
                       "roomIndex": room_index, "itemIndex": item_index}
            elif family == "plotActivation":
                src = {"bundle": bare, "pathId": pid,
                       "plotIndex": plot_index, "itemIndex": item_index}
            else:
                src = {"bundle": bare, "pathId": pid,
                       "itemIndex": item_index}
            row = {
                "scenarioName": name,
                "recordFamily": family,
                "owningRoomId": room_uid,
                "plotUniqueId": plot_uid,
                "definitionId": rec.get("DefinitionID"),
                "definitionPptr": _pptr_json(rec.get("Definition")),
                "localPosition": local,
                "localRotation": rec.get("LocalRotation"),
                "generalParamInt1": rec.get("GeneralParamInt1"),
                "customisationSwatchIndex": rec.get(
                    "CustomisationSwatchIndex"),
                "itemFlags": rec.get("ItemFlags"),
                "plotLayer": rec.get("PlotLayer"),
                "resolution": None,
                "derived": derived,
                "source": src,
                "buildId": build_id,
                "_locateCtx": (meta["bundle"], source_file),   # RELPATH: resolver keys are roster relpaths
            }
            new_rows.append(row)
            return row

        for rec_i, rr in enumerate(rooms):
            uid = rr.get("UniqueID")
            for it_i, rec in enumerate(rr.get("ItemRecords") or []):
                make_item_row(mu.ROOM_FAMILY, rec, room_rec=rr, room_uid=uid,
                              room_index=rec_i, item_index=it_i)
        for it_i, rec in enumerate(arrivals):
            make_item_row("arrival", rec, item_index=it_i)
        for it_i, rec in enumerate(non_area):
            make_item_row("nonArea", rec, item_index=it_i)
        for it_i, rec in enumerate(waypoints):
            make_item_row("waypoint", rec, item_index=it_i)
        for rec_i, pr in enumerate(plots):
            uid = pr.get("PlotUniqueId")
            for it_i, rec in enumerate(
                    pr.get("PlotActivationItemRecords") or []):
                make_item_row("plotActivation", rec, plot_uid=uid,
                              plot_index=rec_i, item_index=it_i)
        self.placement_rows.extend(new_rows)

        # non-room reference-frame cross-check (OQ2 EVIDENCE ONLY — the
        # frame itself stays UNVERIFIED; point-in-bounds coincidence is not
        # proof of a reference frame)
        for family in ("arrival", "nonArea", "waypoint", "plotActivation"):
            stats = self.frame_check[family]
            for row in new_rows:
                if row["recordFamily"] != family:
                    continue
                stats["checked"] += 1
                for _uid, center, extent in plot_bounds:
                    if point_in_bounds(row["localPosition"], center, extent):
                        stats["inside"] += 1
                        break

        # ---- people
        for st_i, st in enumerate(students):
            first = st.get("FirstName") if isinstance(st.get("FirstName"),
                                                      dict) else {}
            last = st.get("LastName") if isinstance(st.get("LastName"),
                                                    dict) else {}
            apptr = _pptr_json(st.get("Archetype"))
            arch_id = _resolved_target_id(resolver, targets,
                                          meta["bundle"], source_file, apptr)
            self.student_rows.append({
                "scenarioName": name,
                "studentIndex": st_i,
                "archetypePptr": apptr,
                "archetypeDefinitionId": arch_id,
                "firstNameDev": first.get("_dev"),
                "firstNameTermId": first.get("_termID"),
                "lastNameDev": last.get("_dev"),
                "lastNameTermId": last.get("_termID"),
                "learningRate": st.get("LearningRate"),
                "sex": st.get("Sex"),
                "source": {"bundle": bare, "pathId": pid,
                           "studentIndex": st_i},
                "buildId": build_id,
            })
        for sf_i, sf in enumerate(staff):
            dptr = _pptr_json(sf.get("Definition"))
            def_id = _resolved_target_id(resolver, targets,
                                         meta["bundle"], source_file, dptr)
            self.staff_rows.append({
                "scenarioName": name,
                "staffIndex": sf_i,
                "definitionPptr": dptr,
                "definitionId": def_id,
                "qualifications": list(sf.get("Qualifications") or []),
                "qualificationLevels": list(sf.get("QualificationLevels")
                                            or []),
                "rank": sf.get("Rank"),
                "source": {"bundle": bare, "pathId": pid,
                           "staffIndex": sf_i},
                "buildId": build_id,
            })

        # resolve THIS scenario's placements while the payload context lives
        for row in new_rows:
            row["resolution"] = _resolve_placement(resolver, targets, row)


def _grid_anchor(node):
    if not isinstance(node, dict):
        return None
    return {"x": node.get("X"), "y": node.get("Y")}


def _pptr_json(node):
    pp = mu.pptr_of(node)
    if pp is None:
        return {"fileId": None, "pathId": None}
    return {"fileId": pp[0], "pathId": pp[1]}


def _verbatim_map(m):
    if not isinstance(m, dict):
        return None
    data = m.get("_saveData")
    return {"_width": m.get("_width"), "_height": m.get("_height"),
            "_saveData": list(data) if isinstance(data, list) else data}


def _dims(m):
    if not isinstance(m, dict):
        return None
    return [m.get("_width"), m.get("_height")]


def _histogram(m):
    hist = Counter()
    if isinstance(m, dict):
        data = m.get("_saveData")
        if isinstance(data, list):
            for v in data:
                if isinstance(v, bool):
                    continue
                if isinstance(v, int):
                    hist[v] += 1
    return dict(sorted(hist.items()))


def _resolve_placement(resolver: PlacementResolver, targets: TargetCache,
                       row):
    pptr = (row["definitionPptr"].get("fileId"),
            row["definitionPptr"].get("pathId"))
    if pptr[1] is None:
        return {"status": "unresolved"}
    out = resolver.locate(row["_locateCtx"][0], row["_locateCtx"][1], pptr)
    if out["kind"] == "missing":
        return {"status": "unresolved", "_miss": out}
    if out["kind"] == "widened":
        return {"status": "unresolved", "_pendingWiden": out}
    payload = resolver.target_payload(out, targets)
    corr, def_name, _tid = mu.classify_corroboration(payload,
                                                     row["definitionId"])
    block = {
        "status": "resolved",
        "definitionId": row["definitionId"],
        "definitionName": def_name,
        "corroboration": corr,
        "method": out["method"],
    }
    if out["method"] == "pptr-externals-cab":
        block["extFileId"] = out["extFileId"]
        block["dstCab"] = out["dstCab"]
    block["_located"] = {"bundle": out["bundle"], "pathId": out["pathId"]}
    return block


def _resolved_target_id(resolver, targets, bundle_rel, source_file,
                        pptr_json):
    if pptr_json.get("pathId") is None:
        return None
    out = resolver.locate(bundle_rel, source_file,
                          (pptr_json["fileId"], pptr_json["pathId"]))
    if out["kind"] != "index":
        return None
    payload = resolver.target_payload(out, targets)
    tid = payload.get("_id") if isinstance(payload, dict) else None
    return tid if isinstance(tid, int) else None


def placement_sort_key(row):
    """Global SORT tuple: (scenarioName, recordFamily, owningRoomId,
    plotUniqueId, itemIndex), nulls first — total order over all families."""
    return (
        mu.nulls_first(row["scenarioName"]),
        mu.nulls_first(row["recordFamily"]),
        mu.nulls_first(row["owningRoomId"]),
        mu.nulls_first(row["plotUniqueId"]),
        mu.nulls_first(row["source"].get("itemIndex")),
    )


# ---------------------------------------------------------------------------
# Identity demotions (additive composites; never merges)

def apply_identity_demotions(walk: ScenarioWalk):
    total_collisions = 0
    samples = []

    def record(n, s):
        nonlocal total_collisions
        total_collisions += n
        samples.extend(s)

    # plots: identity (scenarioName, plotUniqueId)
    for row in walk.plot_rows:
        row["_key"] = (row["scenarioName"], row["plotUniqueId"])
        row["_base"] = row["plotUniqueId"]
        row["_ridx"] = row["source"]["recordIndex"]
        row["_pid"] = row["source"]["pathId"]
    n, s = _demote(walk.plot_rows)
    for row in walk.plot_rows:
        comp = row.pop("_compositeId", None)
        if comp is not None:
            row["plotUniqueId"] = comp
            row["tilesRef"]["key"][1] = comp
        row["_tilesRow"]["plotUniqueId"] = row["plotUniqueId"]
        row["_tilesRow"].pop("_compositeId", None)
        row.pop("_key", None)
    record(n, s)

    # rooms: identity (scenarioName, uniqueId)
    for row in walk.room_rows:
        row["_key"] = (row["scenarioName"], row["uniqueId"])
        row["_base"] = row["uniqueId"]
        row["_ridx"] = row["source"]["recordIndex"]
        row["_pid"] = row["source"]["pathId"]
    n, s = _demote(walk.room_rows)
    for row in walk.room_rows:
        comp = row.pop("_compositeId", None)
        if comp is not None:
            row["uniqueId"] = comp
            row["tilesRef"]["key"][1] = comp
        row["_tilesRow"]["uniqueId"] = row["uniqueId"]
        row["_tilesRow"].pop("_compositeId", None)
        row.pop("_key", None)
    record(n, s)

    # placements: identity keyed PER FAMILY (reviewer F7 — itemIndex
    # restarts inside every per-record array)
    fam_key_col = {"room": "owningRoomId", "plotActivation": "plotUniqueId",
                   "arrival": "itemIndexCol", "nonArea": "itemIndexCol",
                   "waypoint": "itemIndexCol"}
    for row in walk.placement_rows:
        col = fam_key_col[row["recordFamily"]]
        base = row["source"].get("itemIndex") \
            if col == "itemIndexCol" else row[col]
        row["_key"] = (row["scenarioName"], row["recordFamily"],
                       row["owningRoomId"], row["plotUniqueId"],
                       row["source"].get("itemIndex"))
        row["_base"] = base
        row["_col"] = col
        row["_ridx"] = row["source"].get("itemIndex")
        row["_pid"] = row["source"].get("pathId")
    n, s = _demote(walk.placement_rows)
    for row in walk.placement_rows:
        comp = row.pop("_compositeId", None)
        col = row.pop("_col", None)
        if comp is not None:
            if col == "itemIndexCol":
                row["source"]["itemIndex"] = comp
            else:
                row[col] = comp
        row.pop("_key", None)
    record(n, s)
    return total_collisions, samples[:10]


def _demote(rows):
    """Group rows by `_key`; groups ≥2 receive `<base>@r<recordIndex>` in
    `_compositeId`, extended additively with the dump pathId leg when even
    the composites collide. Returns (#colliding groups, samples)."""
    groups = {}
    for row in rows:
        groups.setdefault(row["_key"], []).append(row)
    collisions = 0
    samples = []
    for key, group in groups.items():
        if len(group) < 2:
            continue
        collisions += 1
        if len(samples) < 10:
            samples.append({"identity": [str(k) for k in key],
                            "rows": len(group)})
        composites = {}
        for row in group:
            comp = f"{row['_base']}@r{row['_ridx']}"
            composites.setdefault(comp, []).append(row)
        for comp, cgroup in composites.items():
            if len(cgroup) == 1:
                cgroup[0]["_compositeId"] = comp
                continue
            for row in cgroup:
                row["_compositeId"] = f"{comp}@p{row['_pid']}"
    return collisions, samples


# ---------------------------------------------------------------------------
# M3 — widening + join report

def widen_and_resolve(placement_rows, resolver: PlacementResolver,
                      targets: TargetCache, extracted_root: Path):
    pendings = [r for r in placement_rows
                if isinstance(r["resolution"], dict)
                and r["resolution"].get("_pendingWiden")]
    if not pendings:
        return []
    classes = sorted({r["resolution"]["_pendingWiden"]["candidateClass"]
                      for r in pendings})
    widen_definition_index(extracted_root, classes, resolver.def_index)
    resolved_classes = set()
    for row in pendings:
        res = row["resolution"]
        out = res.pop("_pendingWiden")
        if (out["bundle"], out["pathId"]) not in resolver.def_index:
            # widening class did not actually cover this residual PPtr —
            # it stays a structured miss with its exact serialized file
            row["resolution"] = {
                "status": "unresolved",
                "_miss": {"reason": "residual PPtr not covered even after "
                                    "the widening sweep",
                          "extFileId": out["extFileId"],
                          "dstCab": out["dstCab"]},
            }
            continue
        payload = resolver.target_payload({"bundle": out["bundle"],
                                           "pathId": out["pathId"]}, targets)
        corr, def_name, _tid = mu.classify_corroboration(
            payload, row["definitionId"])
        block = {
            "status": "resolved",
            "definitionId": row["definitionId"],
            "definitionName": def_name,
            "corroboration": corr,
            "method": out["method"],
            "widenedClass": out["candidateClass"],
        }
        if out["method"] == "pptr-externals-cab":
            block["extFileId"] = out["extFileId"]
            block["dstCab"] = out["dstCab"]
        block["_located"] = {"bundle": out["bundle"],
                             "pathId": out["pathId"]}
        cls = resolver.loc_index.get((out["bundle"], out["pathId"]))
        if cls is not None:
            resolved_classes.add(cls[0])
        row["resolution"] = block
    # widening is MEASURED, not speculative: only classes that resolved a
    # real residual PPtr enter widenedClasses[]
    return sorted(resolved_classes)


def finalize_and_report(placement_rows, def_index_size, index_bundles,
                        widened_classes, build_id, drift_lines):
    """Finalize resolution blocks (strip internals), assemble the
    unresolved-placements ledger + join_report.json."""
    denom_rows = 0
    resolved = 0
    residue = 0
    residue_cross_file = 0
    residue_same_file_miss = 0
    residue_by_scenario = Counter()
    corroboration = Counter()
    act_total = act_resolved = act_unresolved = 0
    resolved_same_file = resolved_cross_file = 0
    ledger = []
    for row in placement_rows:
        res = row["resolution"]
        res = res if isinstance(res, dict) else {"status": "unresolved"}
        miss = res.pop("_miss", None)
        res.pop("_pendingWiden", None)
        located = res.pop("_located", None)
        row["resolution"] = {k: v for k, v in sorted(res.items())}
        family = row["recordFamily"]
        activation = family == "plotActivation"
        if activation:
            act_total += 1
        else:
            denom_rows += 1
        is_resolved = res.get("status") == "resolved"
        if activation and is_resolved:
            act_resolved += 1
        elif activation:
            act_unresolved += 1
        if not activation and is_resolved:
            corroboration[res.get("corroboration")] += 1
            resolved += 1
            if res.get("method") == "pptr-externals-cab":
                resolved_cross_file += 1
            else:
                resolved_same_file += 1
        elif not activation:
            residue += 1
            residue_by_scenario[row["scenarioName"]] += 1
            ext_fid = (miss or {}).get("extFileId", res.get("extFileId"))
            if located is not None or (ext_fid is not None
                                       and int(ext_fid) >= 1):
                residue_cross_file += 1
            else:
                residue_same_file_miss += 1
            ledger.append({
                "scenarioName": row["scenarioName"],
                "recordFamily": family,
                "owningRoomId": row["owningRoomId"],
                "plotUniqueId": row["plotUniqueId"],
                "itemIndex": row["source"].get("itemIndex"),
                "extFileId": (miss or {}).get("extFileId",
                                              res.get("extFileId")),
                "dstCab": (miss or {}).get("dstCab", res.get("dstCab", "")),
                "reason": (miss or {}).get(
                    "reason",
                    "cross-file target carries no indexed definition dump"),
                "buildId": build_id,
            })
    rate = (resolved / denom_rows) if denom_rows else 0.0
    residue_sorted = [{"scenarioName": n, "count": c} for n, c in
                      sorted(residue_by_scenario.items(),
                             key=lambda kv: (-kv[1], kv[0]))]
    report = {
        "denominator": {
            "measuredSet": denom_rows,
            "note": "room+arrival+nonArea+waypoint; plotActivation counted "
                    "separately below",
        },
        "resolved": resolved,
        "resolveRate": rate,
        "residue": residue,
        "residueByScenario": residue_sorted,
        "residueCrossFile": residue_cross_file,
        "residueSameFileMiss": residue_same_file_miss,
        "widenedClasses": list(widened_classes),
        "plotActivationFamily": {"total": act_total,
                                 "resolved": act_resolved,
                                 "unresolved": act_unresolved},
        "corroboration": {
            "match": corroboration.get("match", 0),
            "twinMismatch": corroboration.get("twin-mismatch", 0),
            "absent": corroboration.get("absent", 0),
            "cause": (
                f"{corroboration.get('absent', 0)} resolved targets expose "
                "no readable `_id` — payloads failed decode ({_raw,"
                " _scriptClass, _sourceFile} only)"
                if corroboration.get("absent") else None),
        },
        "indexEntries": def_index_size,
        "indexBundles": index_bundles,
        "buildId": build_id,
    }
    for seed_val, fresh_val, what in [
        (SEED_RESOLVED, resolved, "join resolved"),
        (SEED_RESIDUE, residue, "join residue"),
        (SEED_RESIDUE_CROSS_FILE, residue_cross_file,
         "cross-file residue"),
        (SEED_RESIDUE_SAME_FILE_MISS, residue_same_file_miss,
         "same-file-miss residue"),
        (SEED_CORROBORATION["match"], report["corroboration"]["match"],
         "corroboration match"),
        (SEED_CORROBORATION["twinMismatch"],
         report["corroboration"]["twinMismatch"], "twin mismatches"),
        (SEED_CORROBORATION["absent"], report["corroboration"]["absent"],
         "corroboration absent"),
        (SEED_INDEX_ENTRIES, def_index_size, "definition-index entries"),
        (SEED_INDEX_BUNDLES, index_bundles, "definition-index bundles"),
    ]:
        line = drift(seed_val, fresh_val, what)
        if line:
            drift_lines.append(line)
    if residue_sorted and residue_sorted[0]["scenarioName"] and \
            SEED_RESOLVED != resolved:
        head = residue_sorted[0]
        drift_lines.append(
            f"DRIFT: residue head {head['scenarioName']}={head['count']} "
            "(seed names the dominant scenario) — fresh wins")
    counters = {
        "indexEntries": def_index_size,
        "resolvedSameFile": resolved_same_file,
        "resolvedCrossFile": resolved_cross_file,
        "unresolved": residue,
        "widenedClassCount": len(widened_classes),
        "corroborationMatch": report["corroboration"]["match"],
        "corroborationTwinMismatch": report["corroboration"][
            "twinMismatch"],
    }
    ledger.sort(key=lambda r: (
        mu.nulls_first(r["scenarioName"]),
        mu.nulls_first(r["recordFamily"]),
        mu.nulls_first(r["owningRoomId"]),
        mu.nulls_first(r["plotUniqueId"]),
        mu.nulls_first(r["itemIndex"]),
    ))
    return report, counters, ledger


# ---------------------------------------------------------------------------
# M4 — brushes + terrain decode attempt (G7)

def analyze_brushes(paths, out_index, resolver: PlacementResolver,
                    targets: TargetCache, problems):
    dbs = []
    for d in paths["brush_db_dirs"]:
        dbs.extend(sorted(d.glob("*.json")))
    definitions = {}
    db_count = 0
    for path in dbs:
        payload = load_json(path)
        meta = out_index.get(manifest_key(path))
        if meta is None:
            problems.append(
                f"LandscapeBrushDatabase dump {path.name} is absent from "
                "harvest/export-manifest.jsonl — provenance unresolved")
            continue
        db_count += 1
        for refnode in payload.get("_definitions") or []:
            pp = mu.pptr_of(refnode)
            if pp is None:
                continue
            out = resolver.locate(meta["bundle"],
                                  str(payload.get("_sourceFile") or ""),
                                  pp)
            if out["kind"] == "missing":
                continue
            # brush definitions resolve through the LOCATION index (any
            # dumped object), not the GameItem definition index
            loc = resolver.loc_index.get((out["bundle"], out["pathId"]))
            payload_def = targets.load(loc[1]) if loc else None
            if not isinstance(payload_def, dict):
                continue
            tid = payload_def.get("_id")
            if isinstance(tid, int):
                definitions[tid] = payload_def
    return {"databases": db_count, "definitions": len(definitions),
            "byId": definitions}


def build_terrain_decode(terrain_cells: Counter, terrain_scenarios: set,
                         brushes: dict, build_id, drift_lines):
    values = sorted(terrain_cells.keys())
    brush_ids = set(brushes["byId"].keys())
    cells_sampled = sum(terrain_cells.values())
    legend = []
    proven = 0
    correlated = 0
    for v in values:
        if v in brush_ids:
            confidence = "correlated"   # id-space coincidence, never proof
            correlated += 1
        else:
            confidence = "unproven"
        legend.append({"value": v,
                       "brushId": v if v in brush_ids else None,
                       "confidence": confidence})
    if not values or not brush_ids:
        status = "blocked"
        blocked_reason = (
            "terrain value-semantics decode has no ground to stand on: "
            f"{len(values)} distinct TerrainMap values observed vs "
            f"{len(brush_ids)} readable LandscapeBrushDefinition _ids and "
            "no paint-path evidence in the decompiled tree")
    elif correlated == 0:
        status = "blocked"
        blocked_reason = (
            "no TerrainMap value intersects the LandscapeBrushDefinition "
            f"_id space ({len(values)} distinct values vs "
            f"{len(brush_ids)} brush ids) and no paint-path code-read "
            "exists — an UNPROVEN legend never renders as fact anywhere "
            "downstream")
    else:
        status = "partial"
        blocked_reason = None
    doc = {
        "status": status,
        "brushDatabases": brushes["databases"],
        "brushDefinitions": brushes["definitions"],
        "valueLegend": legend,
        "evidence": {
            "scenariosCorrelated": sorted(terrain_scenarios),
            "cellsSampled": cells_sampled,
            "distinctValues": len(values),
            "valueSpaceIntersectsBrushIds": correlated,
        },
        "blockedReason": blocked_reason,
        "unblock": "code-read LandscapeBrushDatabase paint path + "
                   "one-scenario correlation; then upgrade confidence "
                   "values",
        "buildId": build_id,
    }
    for seed_val, fresh_val, what in [
        (SEED_BRUSH_DATABASES, brushes["databases"], "brush databases read"),
        (SEED_BRUSH_DEFINITIONS, brushes["definitions"],
         "brush definitions read"),
    ]:
        line = drift(seed_val, fresh_val, what)
        if line:
            drift_lines.append(line)
    counters = {
        "layersTotal": None,       # filled by caller
        "dimsMin": None,
        "dimsMax": None,
        "brushDatabasesRead": brushes["databases"],
        "brushDefinitionsRead": brushes["definitions"],
        "legendValuesProven": proven,
        "terrainDecodeStatus": status,
    }
    return doc, counters


# ---------------------------------------------------------------------------
# M5 — doors

def sweep_class_id_spaces(mono_dir: Path) -> dict:
    """Every dumped SCRIPT CLASS carrying integer `_id` → its id space.
    Class identity is the per-class subdirectory under each bundle-family
    dir (`harvest/monobehaviours/<family>/<ScriptClass>/*.json` — stage-3's
    export layout). Mechanical full-corpus walk with a raw-byte pre-filter
    (files whose bytes never spell '"_id"' cannot carry the key)."""
    spaces: dict[str, set] = {}
    class_dirs = sorted(p for p in mono_dir.glob("*/*") if p.is_dir())
    for d in class_dirs:
        cls = d.name
        space = spaces.setdefault(cls, set())
        for path in sorted(d.glob("*.json")):
            try:
                if b'"_id"' not in _bytes_with_needle(path):
                    continue
                payload = load_json(path)
            except (OSError, ValueError):
                continue
            tid = payload.get("_id")
            if isinstance(tid, int):
                space.add(tid)
    return spaces


def _bytes_with_needle(path: Path) -> bytes:
    """Whole-file bytes (small dumps dominate; big scenario payloads are
    re-parsed once more here than elsewhere — accepted for honesty)."""
    return path.read_bytes()


def analyze_doors(paths, out_index, container_reverse, build_id, id_spaces,
                  drift_lines):
    validators = []
    refs = set()
    ent_refs = set()
    exit_refs = set()
    for d in paths["validator_dirs"]:
        for path in sorted(d.glob("*.json")):
            payload = load_json(path)
            meta = out_index.get(manifest_key(path))
            if meta is None:
                meta = {"bundle": _dir_fallback_bundle(path),
                        "pathId": _path_pid(path)}
            meta_pid = int(meta["pathId"])
            bare = mu.bundle_basename(meta["bundle"])
            vid = payload.get("_id")
            ent = list(payload.get("_entranceToRooms") or [])
            exi = list(payload.get("_exitToRooms") or [])
            refs.update(int(x) for x in ent)
            refs.update(int(x) for x in exi)
            ent_refs.update(int(x) for x in ent)
            exit_refs.update(int(x) for x in exi)
            row = {
                "validatorId": vid,
                "entranceToRooms": ent,
                "exitToRooms": exi,
                "allowEntranceInAnyBuilding":
                    payload.get("_allowEntranceInAnyBuilding"),
                "allowEntranceInAnyRoom":
                    payload.get("_allowEntranceInAnyRoom"),
                "allowExitToAnyBuilding":
                    payload.get("_allowExitToAnyBuilding"),
                "allowExitToAnyRoom": payload.get("_allowExitToAnyRoom"),
                "catalogAddress": container_reverse.address(bare, meta_pid),
                "source": {"bundle": bare, "pathId": meta_pid},
                "buildId": build_id,
            }
            for key, field in (("invalidEntranceMessage",
                                "InvalidEntranceMessage"),
                               ("invalidExitMessage", "InvalidExitMessage"),
                               ("invalidMessage", "InvalidMessage")):
                if field in payload:
                    row[key] = payload[field]      # optional: emitted when
                    # present, omitted without failure otherwise
            validators.append(row)
    validators.sort(key=lambda r: mu.nulls_first(r["validatorId"]))

    sliding = 0
    for d in paths["mono"].glob("*/TPC.AutomaticSlidingDoorsComponent"):
        sliding += sum(1 for _p in d.glob("*.json"))

    # full-space sweep: every dumped config-class with integer _id
    matched = {}
    for cls in sorted(id_spaces):
        space = id_spaces[cls]
        if not space:
            continue
        covered = len(refs & space)
        if covered:
            matched[cls] = covered
    union_all = set()
    for space in id_spaces.values():
        union_all |= space
    coverage_union = len(refs & union_all)
    room_instance_ids = set()
    floor_area_ids = set()
    roomtype_ids = set()
    for cls, space in id_spaces.items():
        if "RoomDefinition" in cls:
            room_instance_ids |= space
        if "FloorArea" in cls:
            floor_area_ids |= space
        if cls.startswith("TPC.RoomType"):
            roomtype_ids |= space
    instance_links = len(refs & room_instance_ids)

    # verifier narrower integer sweep, re-run mechanically: the EXIT-ref
    # list space only, against the RoomType-family dump _id union
    integer_best = len(exit_refs & roomtype_ids)

    agreed = coverage_union == len(refs) and integer_best == len(refs)
    reconciliation = "agreed" if agreed else "divergent"

    for seed_val, fresh_val, what in [
        (SEED_VALIDATORS, len(validators), "door validator dumps"),
        (SEED_VALIDATOR_REFS, len(refs), "distinct validator refs"),
        (SEED_SLIDING_DOOR_COMPONENTS, sliding,
         "AutomaticSlidingDoorsComponent dumps"),
        (SEED_INTEGER_SWEEP_BEST_MATCH, integer_best,
         "narrower integer sweep best match"),
    ]:
        line = drift(seed_val, fresh_val, what)
        if line:
            drift_lines.append(line)

    door = {
        "validators": validators,
        "refs": refs,
        "matched": matched,
        "roomInstanceIntersection": len(refs & room_instance_ids),
        "floorAreaIntersection": len(refs & floor_area_ids),
        "coverageUnion": coverage_union,
        "integerBest": integer_best,
        "sliding": sliding,
        "instanceLinksMeasured": instance_links,
        "reconciliation": reconciliation,
        "roomInstanceIdsCount": len(room_instance_ids),
        "floorAreaIdsCount": len(floor_area_ids),
    }
    return door


def _path_pid(path: Path) -> int:
    parsed = tc.parse_harvest_stem(path.stem)
    return int(parsed[1]) if parsed else 0


def _dir_fallback_bundle(path: Path) -> str:
    """Deterministic fallback when a dump is absent from the manifest: the
    parent family dir spelled as a bundle filename (provenance stays
    attributable; the missing-manifest problem is raised by callers)."""
    return path.parent.parent.name + "_assets_all.bundle"


def build_door_id_space(door, build_id):
    return {
        "refsTotal": len(door["refs"]),
        "sweeps": {
            "fullSpaceSweep": {
                "method": "all config-class dumps with integer _id",
                "matched": dict(door["matched"]),
                "coverageUnion": door["coverageUnion"],
                "roomInstanceIntersection": door["roomInstanceIntersection"],
                "floorAreaIntersection": door["floorAreaIntersection"],
            },
            "integerSweep": {
                "method": "verifier narrower integer sweep, re-run: the "
                          "exit-ref list space only, against the "
                          "RoomType-family dump _id union",
                "bestMatch": door["integerBest"],
            },
        },
        "reconciliation": door["reconciliation"],
        "slidingDoorComponents": door["sliding"],
        "instanceLinks": {
            "measured": door["instanceLinksMeasured"],
            "note": "seed expected 0 — links validator refs to rooms.jsonl "
                    "uniqueIds; drift-checked like every seed, never a "
                    "constant",
        },
        "adjacencyStatus": "DERIVED-ONLY",
        "verdict": "validators gate by room TYPE; room-instance door graph "
                   "unresolved pending id-space decode + G1 transforms",
        "unblock": "one id-space reconciliation pass (RoomType ids <-> "
                   "room instances) then emit a door_* relink family in "
                   "the piece that owns relinks/",
        "buildId": build_id,
    }


# ---------------------------------------------------------------------------
# M6 — named plots

def build_named_plots(candidates, registry: dict, matrix_locales: dict,
                      build_id):
    rows = []
    misses = []
    resolved_keys = 0
    for cand in candidates:
        term_id = cand["displayNameTermId"]
        term_key = registry.get(term_id) if term_id is not None else None
        locales = list(matrix_locales.get(term_key, [])) if term_key \
            else []
        if term_key is not None:
            resolved_keys += 1
        else:
            misses.append({
                "termId": term_id,
                "scenarioName": cand["scenarioName"],
                "plotUniqueId": cand["plotUniqueId"],
            })
        rows.append({
            "scenarioName": cand["scenarioName"],
            "plotUniqueId": cand["plotUniqueId"],
            "persistentName": cand["persistentName"],
            "displayNameTermId": term_id,
            "resolvedTermKey": term_key,
            "locales": locales,
            "method": "i2-termid-registry",
            "inferred": False,
            "source": dict(cand["source"]),
            "buildId": build_id,
        })
    rows.sort(key=lambda r: (mu.nulls_first(r["scenarioName"]),
                             mu.nulls_first(r["plotUniqueId"])))
    counters = {
        "namedPlots": len(rows),
        "resolvedTermKeys": resolved_keys,
        "unresolvedTermIds": len(misses),
    }
    return rows, counters, misses


# ---------------------------------------------------------------------------
# M7 — imagery candidates (addresses only; zero decoded bytes)

def build_imagery(guid_index, addresses, addr_bundles, media_catalogue_idx,
                  build_id):
    counts = {}
    hits = {pred["id"]: set() for pred in mu.PREDICATES}
    secondary_hits = Counter()   # occurrence-counted like every predicate
    ls_pred = next(p for p in mu.PREDICATES
                   if p["id"] == "loadingscreen-images")
    for addr in addresses:
        for pred in mu.PREDICATES:
            if mu.predicate_matches(pred, addr):
                counts[pred["id"]] = counts.get(pred["id"], 0) + 1
                hits[pred["id"]].add(addr)
        if mu.IMAGE_SUFFIX_RE.search(addr.casefold()) and \
                mu.predicate_matches(ls_pred, addr):
            secondary_hits[addr] += 1

    candidate_addresses = sorted(set().union(*hits.values())) if hits else []
    rows = []
    for addr in candidate_addresses:
        bundles = sorted(addr_bundles.get(addr) or [])
        name_guess = addr.replace("\\", "/").rsplit("/", 1)[-1]
        for ext in (".png", ".tga", ".jpg", ".jpeg"):
            if name_guess.lower().endswith(ext):
                name_guess = name_guess[: -len(ext)]
                break
        classes = set()
        for bundle in bundles:
            classes |= media_catalogue_idx.get((bundle, name_guess), set())
        rows.append({
            "address": addr,
            "bundle": bundles[0] if bundles else None,
            "matchedPredicates": sorted(
                pid for pid, addr_set in hits.items() if addr in addr_set),
            "mediaCatalogueClasses": sorted(classes),
            "buildId": build_id,
        })

    predicates_doc = []
    drift_lines = []
    for pred in mu.PREDICATES:
        fresh = counts.get(pred["id"], 0)
        entry = {
            "id": pred["id"],
            "pattern": pred["pattern"],
            "patternKind": pred["patternKind"],
            "alternatives": pred["alternatives"],
            "casefold": bool(pred["casefold"]),
            "regex": pred["regex"].pattern if pred["regex"] else None,
            "freshCount": fresh,
            "seed": pred["seed"],
        }
        line = drift(pred["seed"], fresh, f"imagery predicate {pred['id']}")
        if line:
            drift_lines.append(line)
        if pred.get("annotation"):
            entry["annotation"] = pred["annotation"]
        if "secondaryProjection" in pred:
            sec = pred["secondaryProjection"]
            projection_count = sum(secondary_hits.values())
            entry["secondaryProjection"] = {
                "pattern": sec["pattern"],
                "patternKind": sec["patternKind"],
                "freshCount": projection_count,
                "seed": sec["seed"],
            }
            line = drift(sec["seed"], projection_count,
                         "loadingscreen image-extension projection")
            if line:
                drift_lines.append(line)
        predicates_doc.append(entry)

    doc = {
        "addressesScanned": len(addresses),
        "predicates": predicates_doc,
        "candidateRows": len(rows),
        "note": "metadata only — no texture is opened, decoded, or copied "
                "(G9 stays owner-gated)",
        "buildId": build_id,
    }
    line = drift(SEED_ADDRESSES_SCANNED, len(addresses),
                 "catalog addresses scanned")
    if line:
        drift_lines.append(line)
    counters = {
        "addressesScanned": len(addresses),
        "predicateCounts": {k: counts.get(k, 0)
                            for k in sorted(p["id"] for p in mu.PREDICATES)},
        "candidateRows": len(rows),
    }
    return rows, doc, counters, drift_lines


# ---------------------------------------------------------------------------
# Writers

def write_rows(path: Path, rows, gate: mu.DoorGate, emitter: str,
               sort_key=None):
    if sort_key is not None:
        rows.sort(key=sort_key)
    out = []
    for raw in rows:
        clean = strip_private(raw)
        gate.assert_row_allowed(clean, emitter)
        out.append(clean)
    log_util.write_jsonl(path, out)


# ---------------------------------------------------------------------------
# Entry

def run(game_root: Path | None, extracted_root: Path) -> int:
    problems: list[str] = []
    drift_lines: list[str] = []

    paths = check_inputs(extracted_root)
    identity = load_json(extracted_root / "identity.json")
    build_id = identity.get("buildId")
    maps_dir = extracted_root / "maps"
    maps_dir.mkdir(parents=True, exist_ok=True)

    bare_to_rel = load_roster_maps(extracted_root)
    out_index, loc_index, def_index, manifest_rows = \
        load_manifest_indexes(extracted_root)
    externals = ru.load_externals(
        extracted_root / "harvest" / "externals.jsonl")
    cab_lookup = mu.load_cab_lookup(
        extracted_root / "relinks" / "bridges" / "cab_index.jsonl",
        bare_to_rel)
    container_reverse = mu.load_container_reverse(
        extracted_root / "relinks" / "bridges" / "container_index.jsonl")
    resolver = PlacementResolver(loc_index, def_index, externals, cab_lookup)
    targets = TargetCache(extracted_root)
    del bare_to_rel, manifest_rows

    guid_index, addresses, addr_bundles = load_catalog_guid_index(
        extracted_root / "addressables" / "catalog.json")
    registry = load_term_registry(
        extracted_root / "relinks" / "i2_term_registry.jsonl")
    matrix_locales = load_matrix_locales(
        extracted_root / "locales" / "locale-matrix.json")
    media_catalogue_idx = load_media_catalogue_names(
        extracted_root / "media-catalogue.jsonl")

    # ------------------------------------------------------------------
    # M5 analysis FIRST — HARD-GATE state must exist before ANY row write
    id_spaces = sweep_class_id_spaces(paths["mono"])
    door = analyze_doors(paths, out_index, container_reverse, build_id,
                         id_spaces, drift_lines)

    # ------------------------------------------------------------------
    # M1 + M2 walks
    level_rows, university_dumps = walk_level_configs(
        paths, out_index, guid_index, container_reverse, build_id, problems)
    coord_doc, load_doc, m1_counters, m1_drift = run_m1(
        extracted_root / "decompiled" / "il2cppdumper" / "dump.cs",
        level_rows, build_id)
    drift_lines.extend(m1_drift)
    line = drift(SEED_LEVELS_ROWS, len(level_rows), "levels.jsonl rows")
    if line:
        drift_lines.append(line)
    gen_counts = Counter(r["plotCount"]["generation"] for r in level_rows)
    for gen, seed_n in sorted(SEED_LEVEL_GENERATION_SPLIT.items()):
        line = drift(seed_n, gen_counts.get(gen, 0),
                     f"generation split {gen}")
        if line:
            drift_lines.append(line)

    walk = ScenarioWalk()
    scenario_files = []
    for d in paths["scenario_dirs"]:
        for path in sorted(d.glob("*.json")):
            meta = out_index.get(manifest_key(path))
            if meta is None:
                problems.append(
                    f"scenario dump {path.name} is absent from harvest/"
                    "export-manifest.jsonl — provenance unresolved")
                continue
            scenario_files.append((path, meta))
    seen_names = Counter()
    scenarios_read = 0
    for path, meta in sorted(scenario_files,
                             key=lambda t: (str(t[0]), t[1]["pathId"])):
        scenarios_read += 1
        payload = load_json(path)
        name = payload.get("m_Name")
        if not isinstance(name, str) or not name:
            problems.append(
                f"scenario dump {path.name} carries an unusable m_Name — "
                "scenarios.jsonl identity depends on it")
            continue
        seen_names[name] += 1
        walk.walk(path, payload, meta, build_id, resolver, targets)
        del payload

    # ------------------------------------------------------------------
    # M3 — measured widening + join report
    widened_classes = widen_and_resolve(walk.placement_rows, resolver,
                                        targets, extracted_root)
    index_bundles = len({bundle for (bundle, _pid) in def_index})
    join_report, m3_counters, unresolved_ledger = finalize_and_report(
        walk.placement_rows, len(def_index), index_bundles, widened_classes,
        build_id, drift_lines)

    collisions, collision_samples = apply_identity_demotions(walk)

    family_counts = Counter(r["recordFamily"] for r in walk.placement_rows)
    for fam, seed_n in sorted(SEED_PLACEMENT_FAMILIES.items()):
        line = drift(seed_n, family_counts.get(fam, 0),
                     f"placement family {fam}")
        if line:
            drift_lines.append(line)
    line = drift(SEED_PLACEMENTS_TOTAL, len(walk.placement_rows),
                 "total placements")
    if line:
        drift_lines.append(line)
    for seed_val, fresh_val, what in [
        (SEED_SCENARIOS_READ, scenarios_read, "scenario dumps read"),
        (SEED_PLOTS, len(walk.plot_rows), "plots.jsonl rows"),
        (SEED_ROOMS, len(walk.room_rows), "rooms.jsonl rows"),
        (SEED_STUDENTS, len(walk.student_rows), "student rows"),
        (SEED_STAFF, len(walk.staff_rows), "staff rows"),
    ]:
        line = drift(seed_val, fresh_val, what)
        if line:
            drift_lines.append(line)
    items_sum = sum(s["counts"]["itemsTotal"] for s in walk.scenario_rows)
    if items_sum != sum(family_counts.values()):
        problems.append(
            "per-scenario itemsByFamily sums do not decompose the emitted "
            f"placement census ({items_sum} vs {sum(family_counts.values())})"
            " — F2 decomposition broken")
    for s in walk.scenario_rows:
        by_family = s["counts"]["itemsByFamily"]
        if sum(by_family.values()) != s["counts"]["itemsTotal"]:
            problems.append(
                f"scenario {s['scenarioName']!r}: itemsByFamily cells "
                f"{by_family} do not sum to itemsTotal "
                f"{s['counts']['itemsTotal']} — F2 decomposition broken")

    # ------------------------------------------------------------------
    # M4 — terrain decode attempt + layer extremes
    brushes = analyze_brushes(paths, out_index, resolver, targets, problems)
    terrain_doc, m4_counters = build_terrain_decode(
        walk.terrain_cells, walk.terrain_scenarios, brushes, build_id,
        drift_lines)
    layers_total = len(walk.layer_rows)
    zero_dim = sum(
        1 for r in walk.layer_rows
        if not r["dims"]["terrain"] or 0 in (r["dims"]["terrain"][0],
                                             r["dims"]["terrain"][1]))
    sized = [r["dims"]["terrain"] for r in walk.layer_rows
             if r["dims"]["terrain"]
             and r["dims"]["terrain"][0] and r["dims"]["terrain"][1]]
    dims_min = min(sized, key=lambda d: (d[0] * d[1], d)) if sized else None
    dims_max = max(sized, key=lambda d: (d[0] * d[1], d)) if sized else None
    widest = max((d[0] for d in sized), default=None)
    tallest_h = max((d[1] for d in sized), default=None)
    m4_counters["layersTotal"] = layers_total
    m4_counters["dimsMin"] = dims_min
    m4_counters["dimsMax"] = dims_max
    line = drift(SEED_LANDSCAPE_LAYERS, layers_total, "landscape layers")
    if line:
        drift_lines.append(line)
    line = drift(SEED_ZERO_DIM_LAYERS, zero_dim, "zero-dim layers")
    if line:
        drift_lines.append(line)

    # ------------------------------------------------------------------
    # M5 — HARD GATE construction + door artifacts
    gate = mu.DoorGate(door["reconciliation"], door["instanceLinksMeasured"],
                       walk.room_ids_by_scenario)
    door_projection = []
    door_kinds = set()
    for row in walk.placement_rows:
        res = row["resolution"]
        name = res.get("definitionName") if isinstance(res, dict) else None
        if isinstance(name, str) and DOOR_SUBSTRING in name:
            door_kinds.add(name)
            door_projection.append({
                "scenarioName": row["scenarioName"],
                "recordFamily": row["recordFamily"],
                "owningRoomId": row["owningRoomId"],
                "itemIndex": row["source"].get("itemIndex"),
                "definitionName": name,
                "source": dict(row["source"]),
                "buildId": build_id,
            })
    line = drift(SEED_DOOR_PLACEMENTS, len(door_projection),
                 "door placements under the substring predicate")
    if line:
        drift_lines.append(line)
    line = drift(SEED_DOOR_KINDS, len(door_kinds), "door kinds")
    if line:
        drift_lines.append(line)
    door_id_space_doc = build_door_id_space(door, build_id)

    # ------------------------------------------------------------------
    # M6 — named plots
    named_rows, m6_counters, term_misses = build_named_plots(
        walk.named_candidates, registry, matrix_locales, build_id)
    line = drift(SEED_NAMED_PLOTS, m6_counters["namedPlots"], "named plots")
    if line:
        drift_lines.append(line)
    generic_plots = len(walk.plot_rows) - len(walk.named_candidates)

    # ------------------------------------------------------------------
    # M7 — imagery candidates
    imagery_rows, imagery_doc, m7_counters, m7_drift = build_imagery(
        guid_index, addresses, addr_bundles, media_catalogue_idx, build_id)
    drift_lines.extend(m7_drift)

    # ------------------------------------------------------------------
    # Absence ledger (every seeded class; conditions recorded honestly)
    absences = []
    if university_dumps:
        absences.append({
            "class": "university-level-config-out-of-scope",
            "scope": "harvest/monobehaviours/**/TPC.UniversityLevelConfig "
                     "(and any future sibling level-config class)",
            "evidence": {"dumps": len(university_dumps),
                         "classes": sorted({u["class"]
                                            for u in university_dumps})},
            "unblock": "a follow-up revision widens the level-family glob "
                       "if the arbiter requires it",
            "buildId": build_id,
        })
    non_room_checked = sum(v["checked"] for v in walk.frame_check.values())
    if any(family_counts[f] for f in walk.frame_check):
        absences.append({
            "class": "non-room-position-frame-unverified",
            "scope": "item_placements arrival/nonArea/waypoint/"
                     "plotActivation LocalPosition space (OQ2)",
            "evidence": {
                "perFamily": walk.frame_check,
                "note": "bounds cross-check measured "
                        f"{sum(v['inside'] for v in walk.frame_check.values())}"
                        f"/{non_room_checked} placements inside some plot's "
                        "world bounds — coincidence is not proof of a "
                        "reference frame; rows stay verbatim-only",
            },
            "unblock": "prove the frame against plot bounds during M3 and "
                       "revise the spec before emitting derived worlds for "
                       "these families",
            "buildId": build_id,
        })
    for miss in term_misses:
        absences.append({
            "class": "plot-display-name-unresolved",
            "scope": f"named_plots scenarioName="
                     f"{miss['scenarioName']!r}",
            "evidence": {"termId": miss["termId"],
                         "plotUniqueId": miss["plotUniqueId"]},
            "unblock": "resolve the termID through the i2 registry once it "
                       "carries it; never guessed",
            "buildId": build_id,
        })
    if collisions:
        absences.append({
            "class": "identity-collisions",
            "scope": "plots/rooms/placements per-family identity keys",
            "evidence": {"collisions": collisions,
                         "samples": collision_samples,
                         "policy": "BOTH colliding rows demoted to "
                                   "additive composite ids "
                                   "(<id>@r<recordIndex>, extended with "
                                   "@p<pathId> when even composites "
                                   "collide) — never a silent merge"},
            "unblock": "upstream identity disambiguation (piece-1 R6 / "
                       "piece-2 F10 additive-suffix precedent)",
            "buildId": build_id,
        })
    absences.append({
        "class": "scene-transforms-deferred",
        "scope": "scene Transform/GameObject layers (G1, ruling R2)",
        "evidence": "Transform objects are census-counted across the 26 "
                    "scene bundles and never dumped; calibration rests on "
                    "WorldBounds + SpawnPoints + plot bounds",
        "unblock": "extend stage 3 to decode engine-native "
                   "Transform/GameObject for the 26 scene bundles; reopen "
                   "on cartography↔substrate calibration drift or a "
                   "planner requirement for environment-art placement",
        "buildId": build_id,
    })

    # ------------------------------------------------------------------
    # WRITE everything (single final state on disk; temp+rename everywhere;
    # HARD-GATE pre-write assertion across ALL emitters)
    log_util.write_json(maps_dir / "coordinate_law.json", coord_doc)
    log_util.write_json(maps_dir / "loadassets_read.json", load_doc)
    write_rows(maps_dir / "levels.jsonl", level_rows, gate, "m2-levels",
               sort_key=lambda r: (r["plotCount"]["generation"],
                                   r["levelId"], r["source"]["pathId"]))
    write_rows(maps_dir / "scenarios.jsonl", walk.scenario_rows, gate,
               "m2-scenarios",
               sort_key=lambda r: mu.nulls_first(r["scenarioName"]))
    plot_sort = lambda r: (mu.nulls_first(r["scenarioName"]),
                           mu.nulls_first(r["plotUniqueId"]),
                           r["source"]["recordIndex"])
    tile_plot_rows = [p["_tilesRow"] for p in walk.plot_rows]
    write_rows(maps_dir / "plots.jsonl", walk.plot_rows, gate, "m2-plots",
               sort_key=plot_sort)
    write_rows(maps_dir / "plots_tiletypes.jsonl", tile_plot_rows, gate,
               "m2-plot-tiletypes", sort_key=plot_sort)
    room_sort = lambda r: (mu.nulls_first(r["scenarioName"]),
                           mu.nulls_first(r["uniqueId"]),
                           r["source"]["recordIndex"])
    tile_room_rows = [r["_tilesRow"] for r in walk.room_rows]
    write_rows(maps_dir / "rooms.jsonl", walk.room_rows, gate, "m2-rooms",
               sort_key=room_sort)
    write_rows(maps_dir / "rooms_tiles.jsonl", tile_room_rows, gate,
               "m2-room-tiles", sort_key=room_sort)
    write_rows(maps_dir / "item_placements.jsonl", walk.placement_rows, gate,
               "m2-placements", sort_key=placement_sort_key)
    write_rows(maps_dir / "students.jsonl", walk.student_rows, gate,
               "m2-students",
               sort_key=lambda r: (mu.nulls_first(r["scenarioName"]),
                                   r["studentIndex"]))
    write_rows(maps_dir / "staff_records.jsonl", walk.staff_rows, gate,
               "m2-staff",
               sort_key=lambda r: (mu.nulls_first(r["scenarioName"]),
                                   r["staffIndex"]))
    layer_sort = lambda r: (mu.nulls_first(r["scenarioName"]),
                            mu.nulls_first(r["plotUniqueId"]),
                            r["layerIndex"])
    write_rows(maps_dir / "landscape_layers.jsonl", walk.layer_rows, gate,
               "m4-layers", sort_key=layer_sort)

    # landscape_maps streams scenario-major through the gate so the whole
    # substrate never sits in one memory buffer
    merged_land = {}
    for name, rows in walk.landscape_pending.items():
        merged_land.setdefault(name, []).extend(rows)
    fd, tmp = tempfile.mkstemp(prefix=".landscape_maps.", suffix=".tmp",
                               dir=str(maps_dir))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            for name in sorted(merged_land, key=mu.nulls_first):
                rows = merged_land[name]
                rows.sort(key=lambda r: (mu.nulls_first(r["plotUniqueId"]),
                                         r["layerIndex"]))
                for raw in rows:
                    clean = strip_private(raw)
                    gate.assert_row_allowed(clean, "m4-landscape-maps")
                    fh.write(log_util.dump_jsonl_row(clean) + "\n")
        os.replace(tmp, str(maps_dir / "landscape_maps.jsonl"))
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise

    log_util.write_json(maps_dir / "terrain_decode.json", terrain_doc)
    write_rows(maps_dir / "door_validators.jsonl", door["validators"], gate,
               "m5-validators",
               sort_key=lambda r: mu.nulls_first(r["validatorId"]))
    write_rows(maps_dir / "door_placement_index.jsonl", door_projection,
               gate, "m5-door-projection",
               sort_key=lambda r: (
                   mu.nulls_first(r["scenarioName"]),
                   mu.nulls_first(r["recordFamily"]),
                   mu.nulls_first(r["owningRoomId"]),
                   mu.nulls_first(r["itemIndex"])))
    log_util.write_json(maps_dir / "door_id_space.json", door_id_space_doc)
    write_rows(maps_dir / "named_plots.jsonl", named_rows, gate, "m6-named")
    write_rows(maps_dir / "imagery_candidates.jsonl", imagery_rows, gate,
               "m7-imagery", sort_key=lambda r: r["address"])
    log_util.write_json(maps_dir / "imagery_predicates.json", imagery_doc)
    log_util.write_json(maps_dir / "join_report.json", join_report)
    write_rows(maps_dir / "_absences.jsonl", absences, gate, "m8-absences",
               sort_key=lambda r: r["class"])
    write_rows(maps_dir / "_unresolved_placements.jsonl", unresolved_ledger,
               gate, "m3-unresolved",
               sort_key=lambda r: (
                   mu.nulls_first(r["scenarioName"]),
                   mu.nulls_first(r["recordFamily"]),
                   mu.nulls_first(r["owningRoomId"]),
                   mu.nulls_first(r["plotUniqueId"]),
                   mu.nulls_first(r["itemIndex"])))

    # _manifest.sha256 — one line per declared output, sorted by relPath
    manifest_lines = []
    missing_outputs = []
    for rel in sorted(DECLARED_OUTPUTS):
        p = maps_dir / rel
        if not p.is_file():
            missing_outputs.append(rel)
            continue
        manifest_lines.append(f"{log_util.sha256_file(p)}  {rel}\n")
    if missing_outputs:
        problems.append(
            "declared outputs missing from disk after emission: "
            f"{missing_outputs} — an artifact absent from disk is a stage "
            "failure, not an absence (AC8)")
    log_util.atomic_write_text(maps_dir / "_manifest.sha256",
                               "".join(manifest_lines))

    # ------------------------------------------------------------------
    # Exit-code contract (AC9): 1 schema/validation breakage · 2 iff any
    # ledger is non-empty, contributors named with sizes · 0 only when ALL
    # close
    contributors = []
    if terrain_doc["status"] != "decoded":
        contributors.append(
            f"terrain decode not proven-complete: "
            f"status={terrain_doc['status']} "
            f"legendValuesProven={m4_counters['legendValuesProven']}")
    if gate.open is False:
        contributors.append(
            "door id-space gate closed: reconciliation="
            f"{door['reconciliation']} instanceLinks.measured="
            f"{door['instanceLinksMeasured']}")
    if any(family_counts[f] for f in walk.frame_check):
        contributors.append(
            "non-room position frame unverified (OQ2): "
            f"{non_room_checked} placements verbatim-only")
    contributors.append(
        "scene transforms deferred (G1/R2): census-only Transforms across "
        "26 scene bundles")
    if unresolved_ledger:
        contributors.append(
            f"unresolved placements: {len(unresolved_ledger)} rows in "
            "_unresolved_placements.jsonl")
    contributors.append(
        "imagery byte-decode absent (G9 owner-gated): "
        f"{len(imagery_rows)} metadata-only candidate rows")
    if collisions:
        contributors.append(f"identity-collisions: {collisions} groups "
                            "demoted to composites")
    if term_misses:
        contributors.append(f"plot-display-name-unresolved: "
                            f"{len(term_misses)}")

    scenario_axis = {s["scenarioName"]: s["contentAxis"]
                     for s in walk.scenario_rows}
    axis_counts = {
        "levels": dict(sorted(Counter(r["contentAxis"]
                                      for r in level_rows).items())),
        "scenarios": dict(sorted(Counter(
            s["contentAxis"] for s in walk.scenario_rows).items())),
        "plots": dict(sorted(Counter(
            scenario_axis.get(r["scenarioName"]) for r in
            walk.plot_rows).items())),
        "itemPlacements": dict(sorted(Counter(
            scenario_axis.get(r["scenarioName"]) for r in
            walk.placement_rows).items())),
    }

    run_lines = [
        "- exitCode: "
        + ("1" if problems else ("2" if contributors else "0"))
        + ("" if not problems else f" ({'; '.join(problems)})"),
        f"- M1: gridConstParsed={m1_counters['gridConstParsed']} "
        f"gridDrift={m1_counters['gridDrift']} "
        f"boundsRows={m1_counters['boundsRows']} "
        f"spawnRows={m1_counters['spawnRows']} "
        f"spawnVariants={m1_counters['spawnVariants']} "
        f"loadassetsReadStatus={m1_counters['loadassetsReadStatus']}",
        f"- M2: scenariosRead={scenarios_read} "
        f"plotRows={len(walk.plot_rows)} "
        f"roomRows={len(walk.room_rows)} "
        f"roomTilesRows={len(tile_room_rows)} "
        f"plotTileTypesRows={len(tile_plot_rows)} "
        f"placementRows={len(walk.placement_rows)} "
        f"studentRows={len(walk.student_rows)} "
        f"staffRows={len(walk.staff_rows)} "
        f"identityCollisions={collisions} "
        f"axisCounts={{levels: {axis_counts['levels']}, "
        f"scenarios: {axis_counts['scenarios']}, "
        f"itemPlacements: {axis_counts['itemPlacements']}}}",
        f"- M3: indexEntries={m3_counters['indexEntries']} "
        f"resolvedSameFile={m3_counters['resolvedSameFile']} "
        f"resolvedCrossFile={m3_counters['resolvedCrossFile']} "
        f"unresolved={m3_counters['unresolved']} "
        f"widenedClassCount={m3_counters['widenedClassCount']} "
        f"corroborationMatch={m3_counters['corroborationMatch']} "
        f"corroborationTwinMismatch={m3_counters['corroborationTwinMismatch']}"
        f" resolveRate={join_report['resolveRate']:.4f}",
        f"- M4: layersTotal={m4_counters['layersTotal']} "
        f"dimsMin={m4_counters['dimsMin']} "
        f"dimsMax={m4_counters['dimsMax']} "
        f"widestSingleWidth={widest} tallestSingleHeight={tallest_h} "
        f"zeroDimLayers={zero_dim} "
        f"brushDatabasesRead={m4_counters['brushDatabasesRead']} "
        f"brushDefinitionsRead={m4_counters['brushDefinitionsRead']} "
        f"legendValuesProven={m4_counters['legendValuesProven']} "
        f"terrainDecodeStatus={m4_counters['terrainDecodeStatus']}",
        f"- M5: validatorsEmitted={len(door['validators'])} "
        f"validatorRefs={len(door['refs'])} "
        f"doorPlacements={len(door_projection)} "
        f"doorKinds={len(door_kinds)} "
        f"slidingDoorComponents={door['sliding']} "
        f"reconciliation={door['reconciliation']}",
        f"- M6: namedPlots={m6_counters['namedPlots']} "
        f"resolvedTermKeys={m6_counters['resolvedTermKeys']} "
        f"unresolvedTermIds={m6_counters['unresolvedTermIds']} "
        f"genericPlots={generic_plots}",
        f"- M7: addressesScanned={m7_counters['addressesScanned']} "
        "predicateCounts="
        + json.dumps(m7_counters["predicateCounts"], sort_keys=True)
        + f" candidateRows={m7_counters['candidateRows']}",
        "- LEDGER-SIZES: "
        f"_absences.jsonl={len(absences)} "
        f"_unresolved_placements.jsonl={len(unresolved_ledger)}",
        *sorted(drift_lines),
    ]
    if contributors:
        run_lines.append("- LEDGER-CONTRIBUTORS (exit 2): "
                         + "; ".join(contributors))
    run_lines += [f"- PROBLEM: {p}" for p in problems]
    log_util.append_run_section(extracted_root, STAGE_ID, run_lines)

    print(f"[maps] levels={len(level_rows)} scenarios={scenarios_read} "
          f"plots={len(walk.plot_rows)} rooms={len(walk.room_rows)} "
          f"placements={len(walk.placement_rows)} "
          f"layers={layers_total} validators={len(door['validators'])} "
          f"doors={len(door_projection)} named={m6_counters['namedPlots']}")
    print(f"[maps] join resolved={join_report['resolved']}/"
          f"{join_report['denominator']['measuredSet']} "
          f"rate={join_report['resolveRate']:.4f} "
          f"residue={join_report['residue']} "
          f"widened={len(widened_classes)}")
    print(f"[maps] terrainDecode={terrain_doc['status']} "
          f"doorGate={'OPEN' if gate.open else 'closed'} "
          f"reconciliation={door['reconciliation']}")
    for d in drift_lines:
        print(f"[maps] {d}", file=sys.stderr)
    for p in problems:
        print(f"[maps] PROBLEM: {p}", file=sys.stderr)
    if problems:
        return 1
    if contributors:
        return 2
    return 0


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
        game_root = Path(args.game_dir).resolve() if args.game_dir else None
        return run(game_root, root)
    except tc.StageError as exc:
        if root is not None:
            log_util.append_failure_section(root, STAGE_ID, exc.exit_code,
                                            [str(exc)])
        print(f"[{STAGE_ID}] ERROR: {exc}", file=sys.stderr)
        return exc.exit_code


if __name__ == "__main__":
    sys.exit(main())
