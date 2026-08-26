#!/usr/bin/env python3
"""Shared helpers for stage 7 `maps` (piece-03, spec Revision 3).

Pure, fixture-testable pieces of the derived-map-geometry layer:

  * dump.cs parsers — GridCoord constants + EPlotTileType palette (M1,
    parsed NEVER hardcoded) and the generic `<LoadAssets>d__NN` iterator
    read behind maps/loadassets_read.json;
  * the closed four-generation bundle vocabulary (R4: no canonical
    generation exists for buildId 20226581 — variants ride as first-class
    variantOf rows);
  * the M3 PPtr resolution seams (definition index, cab lookup,
    corroboration classifier);
  * the M5 HARD GATE (in-stage pre-write assertion shared verbatim with
    the AC11 audit rule);
  * the seven pinned imagery predicates (M7, literal patterns);
  * sort/dedup helpers implementing the per-family identity laws (M2).

Every constant that came from a measurement is a DRIFT-checked SEED:
fresh numbers win, never a silent stale pin.
"""
from __future__ import annotations

import json
import re
from bisect import bisect_left
from pathlib import Path

import tpc_common as tc


# ---------------------------------------------------------------------------
# Coordinate-law parsing (M1) — constants are READ from dump.cs every run

_GRID_DECL_RE = re.compile(r"^public (?:struct|class) GridCoord\b")
_ENUM_DECL_RE = re.compile(r"^public enum EPlotTileType\b")
_CONST_FLOAT_RE = re.compile(r"public const float (\w+) = (-?[\d.eE+]+);")
_ENUM_VALUE_RE = re.compile(r"public const EPlotTileType (\w+) = (-?\d+);")

# Embedded expectations (F7). Movement prints a DRIFT line; the PARSED
# value always wins in output.
EXPECTED_GRID = {"CellSize": 2.0, "CellSizeSq": 4.0,
                 "CellSizeInv": 0.5, "CellSizeHalf": 1.0}
EXPECTED_PALETTE = {"None": -1, "Invalid": 0, "Default": 1,
                    "Unbuildable": 2, "NoNavigation": 3}


def _type_block(lines, decl_idx):
    """Lines of the type declaration starting at `decl_idx` (0-based) up to
    and including its depth-0 closing brace, as [(lineno(1-based), text)]."""
    out = []
    depth = 0
    opened = False
    for j in range(decl_idx, len(lines)):
        ln = lines[j]
        out.append((j + 1, ln))
        depth += ln.count("{") - ln.count("}")
        if "{" in ln:
            opened = True
        if opened and depth <= 0:
            break
    return out


def _find_decl(lines, rx):
    for i, ln in enumerate(lines):
        if rx.match(ln):
            return i
    return -1


class CoordinateLawError(tc.StageError):
    """Unparseable GridCoord / EPlotTileType declaration — loud exit 1."""

    def __init__(self, what):
        super().__init__(
            f"coordinate law unparseable: {what} — every downstream unit "
            "statement depends on this declaration, silence would be a "
            "silent lie (piece-03 M1)", exit_code=1)


def parse_grid_constants(lines):
    """GridCoord block → {constants, sourceLine}. Raises CoordinateLawError
    when the declaration or any of the four CellSize* constants is absent."""
    idx = _find_decl(lines, _GRID_DECL_RE)
    if idx < 0:
        raise CoordinateLawError("no 'public struct GridCoord' declaration")
    block = _type_block(lines, idx)
    consts = {}
    for _lineno, ln in block:
        m = _CONST_FLOAT_RE.search(ln)
        if m:
            consts[m.group(1)] = float(m.group(2))
    missing = [k for k in EXPECTED_GRID if k not in consts]
    if missing:
        raise CoordinateLawError(
            f"GridCoord block at dump.cs:{idx + 1} lacks constant(s) "
            f"{missing}")
    return {"constants": consts, "sourceLine": idx + 1,
            "blockLines": len(block)}


def parse_tile_palette(lines):
    """EPlotTileType block → {values, sourceLine}. Raises on absence."""
    idx = _find_decl(lines, _ENUM_DECL_RE)
    if idx < 0:
        raise CoordinateLawError("no 'public enum EPlotTileType' declaration")
    block = _type_block(lines, idx)
    values = {}
    for _lineno, ln in block:
        m = _ENUM_VALUE_RE.search(ln)
        if m:
            values[m.group(1)] = int(m.group(2))
    if not values:
        raise CoordinateLawError(
            f"EPlotTileType block at dump.cs:{idx + 1} carries no values")
    return {"values": values, "sourceLine": idx + 1}


# ---------------------------------------------------------------------------
# LoadAssets iterator read (M1 loadassets_read.json) — generic d__NN emitter

_METHOD_DECL_RE = re.compile(r"^\s*public IEnumerator LoadAssets\(\) \{ \}\s*$")
_CLASS_DECL_RE = re.compile(
    r"^public (?:(?:sealed |abstract |static )*)class (?P<name>[\w.<>]+)"
    r"(?:\s*:\s*(?P<bases>[^/]+?))?\s*// TypeDefIndex: (?P<tdi>\d+)\s*$")
_NAMESPACE_RE = re.compile(r"^// Namespace: (?P<ns>.*)$")
_ITERATOR_RE = re.compile(
    r"^private sealed class [\w.]*<(?P<method>\w+)>d__(?P<num>\d+) : "
    r"(?P<ifaces>[^/]+?) // TypeDefIndex: (?P<tdi>\d+)\s*$")
_RVA_RE = re.compile(
    r"^// RVA: (?P<rva>0x[0-9A-Fa-f]+) Offset: (?P<offset>0x[0-9A-Fa-f]+) "
    r"VA: (?P<va>0x[0-9A-Fa-f]+)")


def find_loadassets(lines):
    """Generic `<LoadAssets>d__NN` read over dump.cs lines → dict shaped like
    the loadassets_read.json `declaration` block, or None when the method
    declaration cannot be found (caller decides how loud to be).

    il2cppdumper emits declarations, not bodies — so the read establishes
    what dump.cs CAN say; `methodBodyAvailable` stays False and the caller
    records readStatus honestly ('inconclusive-from-dumpcs' unless outside
    evidence ever supplies an instantiated generation)."""
    decl_idx = -1
    for i, ln in enumerate(lines):
        if _METHOD_DECL_RE.match(ln):
            decl_idx = i
            break
    if decl_idx < 0:
        return None

    enc_idx = -1
    enclosing = None
    for j in range(decl_idx, -1, -1):
        m = _CLASS_DECL_RE.match(lines[j])
        if m:
            enc_idx, enclosing = j, m
            break
    if enclosing is None:
        return None
    namespace = ""
    for j in range(enc_idx - 1, max(-1, enc_idx - 6), -1):
        nm = _NAMESPACE_RE.match(lines[j])
        if nm:
            namespace = nm.group("ns").strip()
            break
        if lines[j].strip() == "}":
            break
    enc_leaf = enclosing.group("name").rsplit(".", 1)[-1]
    enc_bases = (enclosing.group("bases") or "").strip()
    full_name = f"{namespace}.{enc_leaf}" if namespace \
        else enclosing.group("name")
    enclosing_class = f"{full_name} : {enc_bases}" if enc_bases else full_name

    # compiler-generated iterator state machine — dump.cs emits the nested
    # `<Method>d__NN` type BEFORE its containing class, so scan the file;
    # prefer spellings prefixed by the enclosing leaf (`LevelConfig.<…>`)
    # and, among those, the declaration nearest the enclosing class
    candidates = []
    for j, ln in enumerate(lines):
        m = _ITERATOR_RE.match(ln)
        if m and m.group("method") == "LoadAssets":
            candidates.append((j, m, ln))
    if not candidates:
        return None
    prefixed = [(j, m) for j, m, ln in candidates
                if ln.startswith(f"private sealed class {enc_leaf}.<")]
    pool = prefixed or [(j, m) for j, m, _ln in candidates]
    iter_idx, iter_m = min(pool, key=lambda jm: abs(jm[0] - enc_idx))
    iter_block = _type_block(lines, iter_idx)

    def _member(decl_rx):
        for k, (lineno, ln) in enumerate(iter_block):
            if decl_rx.search(ln):
                rva = offset = va = None
                for back in range(k - 1, -1, -1):
                    bln = iter_block[back][1]
                    rm = _RVA_RE.match(bln.strip())
                    if rm:
                        rva, offset, va = (rm.group("rva"), rm.group("offset"),
                                           rm.group("va"))
                        rva_line = iter_block[back][0]
                        break
                    if bln.strip().startswith("// Methods"):
                        break
                return {"line": lineno, "rva": rva, "offset": offset,
                        "va": va, "rvaLine": rva_line}
        return None

    ctor = _member(re.compile(r"public void \.ctor\("))
    dispose = _member(re.compile(r"(?:private|public) void "
                                 r"System\.IDisposable\.Dispose\(\)"))
    move_next = _member(re.compile(r"(?:private|public) bool MoveNext\(\)"))

    num = iter_m.group("num")
    members = {
        "ctorRva": ctor["rva"] if ctor else None,
        "ctorLine": ctor["line"] if ctor else None,
        "disposeRva": dispose["rva"] if dispose else None,
        "disposeLine": dispose["line"] if dispose else None,
        "moveNextRva": move_next["rva"] if move_next else None,
        "moveNextOffset": move_next["offset"] if move_next else None,
        "moveNextVa": move_next["va"] if move_next else None,
        "moveNextLines": ([move_next["rvaLine"], move_next["line"]]
                          if move_next and move_next.get("rvaLine") else []),
    }
    return {
        "methodDeclaration": lines[decl_idx].strip(),
        "methodDumpCsLine": decl_idx + 1,
        "enclosingClass": enclosing_class,
        "enclosingTypeDefIndex": int(enclosing.group("tdi")),
        "iteratorShape": f"compiler-generated iterator state machine "
                         f"<LoadAssets>d__{num} : {iter_m.group('ifaces')}",
        "iteratorDumpCsLine": iter_idx + 1,
        "iteratorTypeDefIndex": int(iter_m.group("tdi")),
        "members": members,
        "methodBodyAvailable": False,
        "note": "il2cppdumper emits declarations, not bodies",
        "_iteratorNum": num,
    }


# ---------------------------------------------------------------------------
# Generation vocabulary (closed four-family enum, R4.2)

GENERATION_LEVELS_PREFABS = "levels-prefabs"
GENERATION_CONFIGS_ASSETS_ALL = "configs-assets-all"
GENERATION_DLC_SPACE = "dlc-space-configs"
GENERATION_DLC_GHOST = "dlc-ghost-configs"
GENERATIONS = (
    GENERATION_LEVELS_PREFABS,
    GENERATION_CONFIGS_ASSETS_ALL,
    GENERATION_DLC_SPACE,
    GENERATION_DLC_GHOST,
)

_GENERATION_BY_STEM = {
    "configs-levels-prefabs": GENERATION_LEVELS_PREFABS,
    "configs": GENERATION_CONFIGS_ASSETS_ALL,
    "dlc-space-configs": GENERATION_DLC_SPACE,
    "dlc-ghost-configs": GENERATION_DLC_GHOST,
}


def bundle_basename(bundle_rel: str) -> str:
    name = str(bundle_rel).replace("\\", "/").rsplit("/", 1)[-1]
    return name


def generation_for_bundle(bundle_name: str) -> str:
    """Bundle filename/relpath → generation label. Closed vocabulary: an
    unseen family is a schema-revision event (DRIFT + failure), never an
    invented value (piece-03 M2)."""
    stem = bundle_basename(bundle_name)
    if stem.endswith(".bundle"):
        stem = stem[:-len(".bundle")]
    for suf in ("_assets_all", "_all"):
        if stem.endswith(suf) and len(stem) > len(suf):
            stem = stem[:-len(suf)]
            break
    gen = _GENERATION_BY_STEM.get(stem)
    if gen is None:
        raise tc.StageError(
            f"DRIFT: LevelConfig source bundle '{bundle_name}' does not map "
            f"onto the closed four-generation vocabulary {list(GENERATIONS)} "
            "— a fifth config family requires a schema revision, never an "
            "invented value (piece-03 M2 / R4.2)",
            exit_code=1)
    return gen


def axis_for_bundle(bundle_name: str) -> str:
    """contentAxis per the piece-1 family rule (filename tag)."""
    return tc.axis_for_bundle_name(bundle_basename(bundle_name))


# ---------------------------------------------------------------------------
# PPtr + payload seams

PLACEMENT_FAMILIES = ("room", "arrival", "nonArea", "waypoint", "plotActivation")
ROOM_FAMILY = "room"

DEFINITION_CLASSES = ("TPC.GameItemDefinition", "TPC.GameItemLiteDefinition",
                      "TPC.GameItemVariationDefinition")


def pptr_of(node):
    """{"m_FileID": n, "m_PathID": p} → (fileId, pathId); None otherwise."""
    if not isinstance(node, dict):
        return None
    fid = node.get("m_FileID")
    pid = node.get("m_PathID")
    if fid is None or pid is None:
        return None
    try:
        return int(fid), int(pid)
    except (TypeError, ValueError):
        return None


def classify_corroboration(target_payload, definition_id):
    """M3 step 3 — `_id` CORROBORATES, never joins (F9/F17).
    Returns (corroboration, definitionName, targetId):
      match        — target `_id` equals the record's DefinitionID;
      twin-mismatch— resolvable target whose `_id` diverges (legal data);
      absent       — target payload exposes no readable `_id` (the measured
                     cause: `_raw`-only undecoded dumps)."""
    if not isinstance(target_payload, dict):
        return "absent", None, None
    tid = target_payload.get("_id")
    name = target_payload.get("m_Name")
    if not isinstance(tid, int):
        return "absent", (name if isinstance(name, str) else None), None
    corr = "match" if tid == definition_id else "twin-mismatch"
    return corr, (name if isinstance(name, str) else None), tid


# ---------------------------------------------------------------------------
# Cab lookup over relinks/bridges/cab_index.jsonl (READ-ONLY consumption)

class CabLookup:
    """(cab_lower, pathId) → bundles holding it, from the stage-6 bridge.
    Unity pathIds are per-serialized-file while bundles carry several, so
    resolution goes THROUGH THE CAB (piece-02 R2 rule inherited verbatim)."""

    def __init__(self):
        self._by_key = {}     # (relpath, cab_lower) -> sorted array('q')
        self._owners = {}     # cab_lower -> set(relpath)

    def add_row(self, row, bare_to_rel):
        cab = str(row.get("cab") or "").lower()
        rel = bare_to_rel.get(str(row.get("bundle")), str(row.get("bundle")))
        pids = sorted(int(o["pathId"]) for o in row.get("objects") or [])
        self._by_key[(rel, cab)] = pids
        self._owners.setdefault(cab, set()).add(rel)

    def bundles_for(self, cab_lower, path_id):
        """Sorted roster relpaths of bundles whose serialized file `cab`
        contains `path_id`."""
        out = []
        for rel in sorted(self._owners.get(cab_lower, ())):
            pids = self._by_key.get((rel, cab_lower))
            if pids is None:
                continue
            i = bisect_left(pids, path_id)
            if i < len(pids) and pids[i] == path_id:
                out.append(rel)
        return out


def load_cab_lookup(path: Path, bare_to_rel) -> CabLookup:
    lookup = CabLookup()
    with open(path, "r", encoding="utf-8", newline="\n") as fh:
        for line in fh:
            line = line.strip()
            if line:
                lookup.add_row(json.loads(line), bare_to_rel)
    return lookup


class ContainerReverse:
    """(bare bundle filename, pathId) → catalog address(es) — the reverse
    container_index lookup behind levels.assetAddress / validator
    catalogAddress. Collisions keep every address; readers take the
    lexicographically smallest so reruns stay byte-stable."""

    def __init__(self):
        self._by_loc = {}

    def add_row(self, row):
        addr = row.get("address")
        pid = row.get("pathId")
        bundle = row.get("bundle")
        if addr is None or pid is None or bundle is None:
            return
        if int(pid) == -1:
            return   # bridge spells -1 for an unknown pathId, never data
        key = (str(bundle), int(pid))
        lst = self._by_loc.setdefault(key, [])
        if addr not in lst:
            lst.append(addr)

    def address(self, bundle_bare, path_id):
        lst = self._by_loc.get((str(bundle_bare), int(path_id)))
        return min(lst) if lst else None


def load_container_reverse(path: Path) -> ContainerReverse:
    rev = ContainerReverse()
    with open(path, "r", encoding="utf-8", newline="\n") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rev.add_row(json.loads(line))
    return rev


# ---------------------------------------------------------------------------
# M5 HARD GATE — validator-ref → room-instance edges only
#
# Detection rule pinned mechanically in piece-03 §M5 (shared verbatim by
# this in-stage assertion and the AC11 post-hoc audit): a row is GATED when
# it contains BOTH
#   (a) any field whose name references a validator ref from
#       door_validators.jsonl (`validatorId`, `entranceToRooms`,
#       `exitToRooms`, `entranceRef`, `exitRef`), AND
#   (b) a room-instance reference (`owningRoomUniqueId`, `roomUniqueId`, or
#       a value resolving against the rooms.jsonl uniqueId set of the same
#       scenario),
# EXCEPT where the reference is placement containment via `owningRoomId`
# on a placement-family row.

VALIDATOR_REF_KEYS = frozenset({
    "validatorId", "entranceToRooms", "exitToRooms",
    "entranceRef", "exitRef",
})
ROOM_INSTANCE_KEYS = frozenset({"owningRoomUniqueId", "roomUniqueId"})


class DoorGate:
    """In-stage pre-write assertion state. Closed until
    door_id_space.reconciliation == "agreed" AND measured instanceLinks > 0
    — which never co-occur on this corpus (expected steady state)."""

    def __init__(self, reconciliation, instance_links_measured,
                 room_unique_ids_by_scenario):
        self.reconciliation = reconciliation
        self.instance_links_measured = instance_links_measured
        self.room_ids = room_unique_ids_by_scenario or {}
        self.open = bool(reconciliation == "agreed"
                         and instance_links_measured
                         and instance_links_measured > 0)

    @classmethod
    def closed(cls, room_unique_ids_by_scenario=None):
        return cls("divergent", 0, room_unique_ids_by_scenario)

    @staticmethod
    def _scalars(node):
        stack = [node]
        while stack:
            n = stack.pop()
            if isinstance(n, dict):
                stack.extend(n.values())
            elif isinstance(n, list):
                stack.extend(n)
            elif isinstance(n, bool):
                continue
            elif isinstance(n, int):
                yield n

    def _containment_exception(self, row):
        if "owningRoomUniqueId" in row or "roomUniqueId" in row:
            return False
        return "owningRoomId" in row and \
            row.get("recordFamily") in PLACEMENT_FAMILIES

    def violation(self, row, emitter):
        """Reason string when the row must not be written, else None."""
        if self.open:
            return None
        ref_keys = VALIDATOR_REF_KEYS.intersection(row.keys())
        if not ref_keys:
            return None
        inst_keys = ROOM_INSTANCE_KEYS.intersection(row.keys())
        if inst_keys:
            if self._containment_exception(row):
                return None
            return (f"emitter={emitter}: gated row combines validator-ref "
                    f"field(s) {sorted(ref_keys)} with room-instance "
                    f"field(s) {sorted(inst_keys)} while the door id-space "
                    f"gate is closed (reconciliation="
                    f"{self.reconciliation!r}, instanceLinks.measured="
                    f"{self.instance_links_measured})")
        ids = self.room_ids.get(row.get("scenarioName"))
        if ids:
            for v in self._scalars({k: row[k] for k in row
                                    if k != "source"}):
                if v in ids:
                    if self._containment_exception(row):
                        return None
                    return (f"emitter={emitter}: gated row combines "
                            f"validator-ref field(s) {sorted(ref_keys)} "
                            f"with value {v} resolving against the "
                            f"rooms.jsonl uniqueId set of scenario "
                            f"{row.get('scenarioName')!r} while the door "
                            "id-space gate is closed")
        return None

    def assert_row_allowed(self, row, emitter):
        v = self.violation(row, emitter)
        if v is not None:
            raise tc.StageError(
                f"HARD GATE violated ({v}) — validator-ref → room-instance "
                "edges stay DERIVED-ONLY until one id-space reconciliation "
                "pass closes the gate (piece-03 M5)", exit_code=1)


# ---------------------------------------------------------------------------
# M7 imagery predicates — literal patterns pinned by piece-03 §M7

PREDICATES = [
    {
        "id": "metamap-case-sensitive",
        "pattern": "/MetaMap/|/Metamap/",
        "patternKind": "substring-any-exact-case",
        "alternatives": ["/MetaMap/", "/Metamap/"],
        "casefold": False,
        "regex": None,
        "seed": 1094,
        "annotation": "verifyA snapshot 10.2 measured 909 under exact case "
                      "on its catalog snapshot — divergence annotated, "
                      "DRIFT-expected",
    },
    {
        "id": "metamap-case-insensitive",
        "pattern": "metamap",
        "patternKind": "casefold-substring",
        "alternatives": ["metamap"],
        "casefold": True,
        "regex": None,
        "seed": 1140,
    },
    {
        "id": "loadingscreen-images",
        "pattern": "loadingscreen",
        "patternKind": "casefold-substring",
        "alternatives": ["loadingscreen"],
        "casefold": True,
        "regex": None,
        "seed": 117,
        "secondaryProjection": {
            "pattern": "\\.(png|tga|jpg|jpeg)$",
            "patternKind": "casefold-regex-search",
            "seed": 101,
        },
    },
    {
        "id": "imagelevel-strict-prefix",
        "pattern": "UI_Sandbox_T_imageLevel_",
        "patternKind": "substring-exact-case",
        "alternatives": ["UI_Sandbox_T_imageLevel_"],
        "casefold": False,
        "regex": None,
        "seed": 42,
    },
    {
        "id": "imagelevel-family",
        "pattern": "imagelevel",
        "patternKind": "casefold-substring",
        "alternatives": ["imagelevel"],
        "casefold": True,
        "regex": None,
        "seed": 66,
    },
    {
        "id": "level-image-icon-screenshot",
        "pattern": "level.*(image|icon|screenshot)",
        "patternKind": "casefold-regex-search",
        "alternatives": [],
        "casefold": True,
        "regex": re.compile(r"level.*(image|icon|screenshot)"),
        "seed": 66,
        "annotation": "the scout's 125 under its prose predicate remains "
                      "UNREPRODUCED (verifyA 10.4 / verifyB #21) — carried "
                      "as annotation, never as a count",
    },
    {
        "id": "minimap-any-spelling",
        "pattern": "minimap, mini-map, mini_map, compass, worldmap",
        "patternKind": "casefold-substring-any",
        "alternatives": ["minimap", "mini-map", "mini_map", "compass",
                          "worldmap"],
        "casefold": True,
        "regex": None,
        "seed": 0,
        "annotation": "zero-hit negative preserved as first-class data "
                      "(verifyA 10.1 / verifyB A1b) — keeps paths A/B dead",
    },
]

IMAGE_SUFFIX_RE = re.compile(r"\.(png|tga|jpg|jpeg)$", re.IGNORECASE)


def predicate_matches(pred, address: str) -> bool:
    hay = address.casefold() if pred["casefold"] else address
    if pred["regex"] is not None:
        rx = pred["regex"]
        return bool(rx.search(hay))
    for alt in pred["alternatives"]:
        needle = alt.casefold() if pred["casefold"] else alt
        if needle in hay:
            return True
    return False


# ---------------------------------------------------------------------------
# Sort / identity helpers (per-family identity laws, M2)

def nulls_first(v):
    """Total-order component sending None before any value, numbers before
    strings, so mixed identity tuples sort deterministically."""
    if v is None:
        return (0, 0, "")
    if isinstance(v, bool):
        return (1, int(v), "")
    if isinstance(v, (int, float)):
        return (1, v, "")
    return (2, 0, str(v))


def demote_identity_collisions(rows, key_of, base_id_of, record_index_of,
                               source_path_id_of):
    """Per-family uniqueness with the additive composite fallback: colliding
    rows get `<baseId>@r<recordIndex>`; should even the composites collide
    (measured on this corpus: three dumps share scenarioName
    'LevelScenarioV2_All_Buildings', each carrying recordIndex 0), the dump
    pathId leg extends the suffix — additive, never a merge.

    Returns (collisions, samples): rows are annotated in place via their
    '_compositeId' key; callers copy it onto their id column."""
    seen = {}
    collisions = 0
    samples = []
    for row in rows:
        key = key_of(row)
        seen.setdefault(key, []).append(row)
    for key, group in seen.items():
        if len(group) < 2:
            continue
        collisions += 1
        if len(samples) < 10:
            samples.append({"identity": [str(k) for k in key],
                            "rows": len(group)})
        composites = {}
        for row in group:
            comp = f"{base_id_of(row)}@r{record_index_of(row)}"
            composites.setdefault(comp, []).append(row)
        for comp, cgroup in composites.items():
            if len(cgroup) == 1:
                cgroup[0]["_compositeId"] = comp
                continue
            for row in cgroup:
                pid = source_path_id_of(row)
                row["_compositeId"] = f"{comp}@p{pid}"
    return collisions, samples
