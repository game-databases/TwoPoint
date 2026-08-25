#!/usr/bin/env python3
"""Stage 5 — emit-stub-datasets.

Canonical JSONL skeletons per entity family from the MonoBehaviour dumps —
rows land contract-pinned even where fields are only partially understood
(stub data in place rather than absent). SOLE OWNER of
`extracted/relinks/locale_availability.jsonl` (entity-granular,
regenerated on EVERY run — arbiter-001 R3).

Hard-read vs derived (arbiter-001 R8): ids/GUIDs/path_ids/loc keys and RAW
FIELD VALUES copied from dumps are HARD-READ (never flagged `inferred`);
the `inferred` flag + `method` carry only the DERIVED planes: seeded-kind
assignment and convention-derived associations.

Entity identity policy (Revision 6), applied before any row is emitted and
counted decision-by-decision in the run section:
  1. COMPONENT EXCLUSION — only scriptable DEFINITIONS become entities; the
     resolved `_scriptClass` discriminates (hierarchy base chains reach
     ScriptableObject vs MonoBehaviour), and unresolved-generic dumps stay
     census rows.
  2. ID RESOLUTION — identifier-less candidates land in `_absences.jsonl`
     counted + sampled, never emitted.
  3. DUPLICATE POLICY — identical-id rows merge on equal payload hash into
     ONE row carrying `axes:[…]`; differing payloads disambiguate via
     `<id>@<contentHash8>` with the verbatim id preserved inside `fields`.
  4. POST-POLICY UNIQUENESS — asserted after exclusion + merge/disambiguate.

Harvest stems parse SIGNED path_ids (`<bundle-stem>_<signed-int64>`,
Revision 6) through tpc_common.parse_harvest_stem — loaders and the
byte-match checker alike; zero unparsed stems is asserted against the
export-manifest universe.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import log_util
import tpc_common as tc

# pinned kind VALUE ↔ FILENAME map (spec §3 stage 5)
KIND_FILES = {
    "item": "items.jsonl",
    "unlockable": "unlockables.jsonl",
    "room": "rooms.jsonl",
    "campus-level": "campus-levels.jsonl",
    "course": "courses.jsonl",
    "config": "configs.jsonl",
    "staff": "staff.jsonl",
    "metagame-node": "metagame-nodes.jsonl",
    "student-type": "student-types.jsonl",
}
KINDS = list(KIND_FILES)

# seeded-kind assignment heuristics (family hints from spec.md entities;
# class-name hints are the sharper signal when present — GameItem*,
# UnlockableConfig and ResearchProject* are MEASURED client class spellings
# from the Revision-6 harvest)
KIND_CLASS_HINTS = {
    "item": ["ItemConfig", "ItemDefinition", "ItemData", "GameItemDefinition",
             "GameItemLiteDefinition", "GameItemVariationDefinition"],
    "room": ["RoomConfig", "RoomDefinition", "RoomData"],
    "course": ["CourseConfig", "CourseDefinition", "CourseData"],
    "staff": ["StaffConfig", "StaffDefinition", "StaffData", "StaffTraits"],
    "student-type": ["StudentConfig", "StudentType", "StudentArchetype",
                     "StudentData"],
    "unlockable": ["UnlockableConfig", "UnlockDefinition", "UnlockableData"],
    "campus-level": ["LevelDatabase", "CampusLevelConfig", "LevelConfig"],
    "config": ["GameConfig", "ConfigAsset", "BalanceConfig", "GlobalConfig"],
    "metagame-node": ["ResearchNode", "MetagameNode", "ProgressionNode",
                      "MetaNode", "ResearchProject"],
}
KIND_FAMILY_HINTS = {
    "item": ("items-",),
    "room": ("rooms",),
    "course": ("items-courses-", "animations-character-courses"),
    "staff": ("character-shared", "staff"),
    "student-type": ("character-",),
    "unlockable": ("unlockables",),
    "campus-level": ("scenes_scenes_config_level_databases",
                     "configs-levels-prefabs"),
    "config": ("configs",),
    "metagame-node": ("configs-metagame",),
}
ID_FIELD_PRIORITY = ("m_ID", "m_id", "id", "Id", "ID", "m_key", "m_Key",
                     "key", "GUID", "guid", "m_Guid", "m_GUID",
                     "m_name", "m_Name", "name")
DISCRIMINATOR_FIELDS = ("kind", "m_kind", "entityKind", "m_entityKind",
                        "entityType")
NAMED_FIELD_RE = re.compile(r"name|title|display", re.IGNORECASE)

GENERIC_SCRIPT_CLASS = "MonoBehaviour"
_ENGINE_NS_RE = re.compile(r"^(UnityEngine\.|TMPro\.|UnityEditor\.)")
ABSENCE_SAMPLE_CAP = 25


# ---------------------------------------------------------------------------
# Component-exclusion discriminator (Rev 6 rule 1)

class DefinitionGate:
    """Classifies a resolved `_scriptClass` into definition | component |
    unknown off the stage-1 structural hierarchy: walking the transitive
    base chain, a class reaching ScriptableObject(-derived) is a scriptable
    DEFINITION; one reaching UnityEngine.MonoBehaviour first is an engine
    COMPONENT and never becomes an entity row. Types absent from the
    hierarchy fall to the engine-namespace shape check."""

    def __init__(self, structural_dir: Path | None):
        self.bases: dict[str, str] = {}
        self.loaded = False
        if structural_dir is not None:
            hier = structural_dir / "class-hierarchy.jsonl"
            if hier.is_file():
                with open(hier, "r", encoding="utf-8", newline="\n") as fh:
                    for line in fh:
                        line = line.strip()
                        if not line:
                            continue
                        row = json.loads(line)
                        ns, nm = row.get("namespace"), row.get("name")
                        full = f"{ns}.{nm}" if ns else nm
                        base = row.get("baseType")
                        if full and base:
                            self.bases[full] = base
                self.loaded = True

    def classify(self, fullname: str) -> str:
        cur = fullname
        seen: set[str] = set()
        while cur and cur not in seen:
            seen.add(cur)
            last = cur.rsplit(".", 1)[-1]
            if "ScriptableObject" in last:
                return "definition"
            if last == "MonoBehaviour" and cur.startswith("UnityEngine."):
                return "component"
            nxt = self.bases.get(cur)
            if nxt is None:
                return "unknown"
            cur = nxt
        return "unknown"


def gate_candidate(cls: str | None, gate: DefinitionGate) -> tuple[bool, str]:
    """(is_entity_candidate, evidence) for one dump's resolved class."""
    if not cls or cls == GENERIC_SCRIPT_CLASS:
        return False, ("unresolved-generic dump (m_Script never resolved) — "
                       "census row, not an entity")
    # engine namespaces are never game entities — even when the chain
    # reaches ScriptableObject (measured: UnityEngine.InputSystem
    # InputActionReference is an SO-derived engine asset)
    if _ENGINE_NS_RE.match(cls):
        return False, "engine/primitive component namespace"
    verdict = gate.classify(cls)
    if verdict == "component":
        return False, ("component MonoBehaviour (MonoBehaviour-derived "
                       "chain) — never an entity")
    if verdict == "definition":
        return True, ""
    return True, ""


# ---------------------------------------------------------------------------
# Kind assignment + identifier resolution

def match_family(family: str) -> str | None:
    fam = family.lower()
    for kind in KINDS:
        if any(fam.startswith(h.lower()) or h.lower() in fam
               for h in KIND_FAMILY_HINTS[kind]):
            return kind
    return None


def match_class(cls: str) -> str | None:
    base = cls.split(".")[-1].split("+")[-1]
    low = base.lower()
    for kind in KINDS:
        for hint in KIND_CLASS_HINTS[kind]:
            h = hint.lower()
            if low == h or low.startswith(h) or low.endswith(h):
                return kind
    return None


def extract_id(fields: dict):
    """Verbatim identifier off a dump's field block, or None. An
    empty/whitespace string is NO identifier (Rev 6 rule 2: `id=''` rows
    swept whole families last run) — priority scanning continues past it."""
    for k in ID_FIELD_PRIORITY:
        v = fields.get(k) if isinstance(fields, dict) else None
        if isinstance(v, bool):        # bool is an int subclass — never an id
            continue
        if isinstance(v, int):
            return v
        if isinstance(v, str) and v.strip():
            return v
    return None


def assign_kind(cls: str, family: str, fields: dict) -> tuple[str | None, bool, str]:
    """(kind, joinInferred-style inferred flag, method)."""
    for k in DISCRIMINATOR_FIELDS:
        v = fields.get(k)
        if isinstance(v, str) and v in KINDS:
            return v, False, f"in-dump-discriminator:{k}"
    by_class = match_class(cls)
    if by_class:
        return by_class, True, "seeded-class-heuristic"
    by_family = match_family(family)
    if by_family:
        return by_family, True, "seeded-family-heuristic"
    return None, True, ""


def load_monobehaviour_dumps(monobehaviours_dir: Path):
    r"""Yield (family, class, bundle, pathId, payload, relpath) sorted by
    relpath — deterministic enumeration. Stems parse SIGNED path_ids
    (Revision 6): `_(|-)\d+$` via tpc_common.parse_harvest_stem; a stem that
    yields no signed decimal surfaces as pathId=None for the caller's
    assert-zero-unparsed gate."""
    root = monobehaviours_dir
    for path in sorted(root.rglob("*.json"), key=lambda p: p.as_posix()):
        rel = path.relative_to(root)
        parts = rel.parts
        family = parts[0] if len(parts) >= 3 else ""
        cls_dir = parts[1] if len(parts) >= 3 else ""
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            continue
        parsed = tc.parse_harvest_stem(path.stem)
        if parsed is None:
            bundle, path_id = path.stem + ".bundle", None
        else:
            bundle_stem, path_id = parsed
            # roster-style basename: restore the .bundle extension so
            # source.bundle / unmapped bundles[] join roster basenames
            bundle = bundle_stem + ".bundle"
        cls = payload.get("_scriptClass") or cls_dir
        yield family, cls, bundle, path_id, payload, path


def index_monobehaviour_dumps(monobehaviours_dir: Path) -> dict:
    """(bundle, pathId) → payload for every parseable dump, keyed for exact
    provenance lookups (a bare pathId collides across bundles — negative
    int64s collide loudly). Used by callers holding only the directory."""
    index: dict = {}
    for _family, _cls, bundle, path_id, payload, _path in \
            load_monobehaviour_dumps(monobehaviours_dir):
        if path_id is not None:
            index.setdefault((bundle, path_id), payload)
    return index


def payload_fields(payload: dict) -> dict:
    """The dump's field block: fixtures wrap fields under `fields`; real
    harvest dumps are flat payloads. Both shapes read identically here."""
    block = payload.get("fields", payload)
    return block if isinstance(block, dict) else {}


def verbatim_id_of(row: dict) -> str:
    """The verbatim identifier a row stands for: disambiguated rows
    (`<id>@<contentHash8>`) preserve the original inside fields.id."""
    f = row.get("fields")
    if isinstance(f, dict) and f.get("id") is not None:
        return str(f["id"])
    return str(row["id"])


def payload_hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False,
                           default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def sample_for_check(ids: list[str]) -> list[str]:
    """ALL ids when the family has <=1,000 rows, else a deterministic sorted
    sample of 500 (spec §3 stage 5 acceptance)."""
    if len(ids) <= 1000:
        return ids
    ordered = sorted(ids)
    rng = random.Random(hashlib.sha256(b"tpc-piece1-id-sample").digest())
    return sorted(rng.sample(ordered, 500))


def validate_row(row: dict) -> None:
    for req in ("id", "kind", "slug", "fields", "source", "provisional",
                "inferred", "method", "buildId"):
        if req not in row:
            raise tc.StageError(f"stub row missing required field '{req}' "
                                f"(id={row.get('id')!r})", exit_code=1)
    if not isinstance(row["fields"], dict):
        raise tc.StageError(f"stub row 'fields' must be an object (id="
                            f"{row['id']!r})", exit_code=1)
    src = row["source"]
    for req in ("bundle", "pathId", "class"):
        if req not in src:
            raise tc.StageError(f"stub row source missing '{req}'", exit_code=1)


def build_locale_availability(rows_by_kind: dict[str, list[dict]],
                              matrix_keys: dict[str, dict],
                              dumps_source,
                              build_id,
                              stats_out: dict | None = None) -> list[dict]:
    """Entity-granular availability via the PINNED join procedure:
    1. collect the entity dump's string-valued fields;
    2. exact-equal to a locale-matrix key → HARD join;
    3. `<entityId>_<role>` convention corroborated by the matrix → INFERRED;
    4. no other association path exists.

    `dumps_source` is the (bundle, pathId) → payload index built during the
    load pass; a monobehaviours directory is also accepted (indexed once).
    Availability is evidence-based (fail-closed): only HARD-joined keys grant
    locale coverage — availableLocales is the intersection of their matrix
    locale sets, and fieldPresence lists the granting fields per locale.
    Convention joins record joinMethod/joinInferred but claim no locales,
    because their keys are not observed in any locale bundle yet.
    Disambiguated rows join through their VERBATIM id (fields.id).

    When `stats_out` is a dict it receives mechanical scan evidence
    ({entitiesScanned, payloadsResolved, hardJoins, conventionJoins}) so a
    zero-row result is provably 'no join surface', never silent starvation."""
    if isinstance(dumps_source, Path):
        dumps_source = index_monobehaviour_dumps(dumps_source)
    availability: list[dict] = []
    join_stats = {"entitiesScanned": 0, "payloadsResolved": 0,
                  "hardJoins": 0, "conventionJoins": 0}
    all_prefixes = set()
    for key in matrix_keys:
        if isinstance(key, str) and "_" in key:
            all_prefixes.add(key.rsplit("_", 1)[0])

    for kind, rows in sorted(rows_by_kind.items()):
        seen_ids: set = set()
        for row in rows:
            eid = row["id"]
            marker = (kind, verbatim_id_of(row))
            if marker in seen_ids:
                continue
            seen_ids.add(marker)
            join_stats["entitiesScanned"] += 1
            payload: dict | None = None
            # locate the source dump from the in-memory index (no re-walk,
            # no re-read); the exact provenance key hits directly, and the
            # identifier byte-match still guards it
            src = row["source"]
            cand_payload = dumps_source.get((src.get("bundle"),
                                             src.get("pathId")))
            verbatim = verbatim_id_of(row)
            if cand_payload is not None:
                cand_id = extract_id(payload_fields(cand_payload))
                if cand_id is None or str(cand_id) == verbatim \
                        or str(cand_id) == str(eid):
                    payload = cand_payload
            if payload is None:
                continue
            join_stats["payloadsResolved"] += 1
            fields_block = payload_fields(payload)
            hard_fields: dict[str, str] = {}
            conv_fields: dict[str, str] = {}
            for fname, fval in fields_block.items():
                if not isinstance(fval, str) or fname.startswith("_"):
                    continue
                if fval in matrix_keys:
                    hard_fields[fname] = fval
                elif isinstance(verbatim, str) and verbatim \
                        and fval.startswith(verbatim + "_"):
                    prefix_ok = fval.rsplit("_", 1)[0] in all_prefixes \
                        or fval in all_prefixes
                    if matrix_keys and (prefix_ok or not all_prefixes):
                        conv_fields[fname] = fval
            joins = dict(hard_fields)
            joins.update(conv_fields)
            if not joins:
                continue
            join_stats["hardJoins"] += len(hard_fields)
            join_stats["conventionJoins"] += len(conv_fields)
            locales_per_field: dict[str, set[str]] = {
                f: set(matrix_keys[key]["locales"])
                for f, key in joins.items() if key in matrix_keys}
            available = set.intersection(*locales_per_field.values()) \
                if locales_per_field else set()
            # named-field coverage claims only HARD-joined keys (fail-closed):
            # a convention-only named field records joinMethod but no locales,
            # so this domain is locales_per_field — never `joins` (a
            # convention-only named field would KeyError here)
            named_fields = [f for f in locales_per_field
                            if NAMED_FIELD_RE.search(f)]
            named_pool = {f: locales_per_field[f] for f in named_fields} \
                if named_fields else locales_per_field
            named = set.union(*named_pool.values()) if named_pool else set()
            field_presence = {
                loc: sorted(f for f, locs in locales_per_field.items() if loc in locs)
                for loc in sorted(available)}
            availability.append({
                "kind": kind,
                "id": eid,
                "availableLocales": sorted(available),
                "namedLocales": sorted(named & available),
                "fieldPresence": field_presence,
                "joinInferred": len(hard_fields) == 0,
                "joinMethod": "; ".join(sorted(
                    ([f"exact-match:{f}" for f in hard_fields]
                     + [f"convention:{f}=<entityId>_<role>" for f in conv_fields]))),
                "buildId": build_id,
            })
    availability.sort(key=lambda r: (r["kind"], str(r["id"])))
    if stats_out is not None:
        stats_out.update(join_stats)
    return availability


# ---------------------------------------------------------------------------
# Duplicate policy (Rev 6 rule 3)

def apply_duplicate_policy(kind: str, candidates: list[dict],
                           counters: dict) -> list[dict]:
    """candidates: [{row, hash, bundle, pathId, axis}] sharing ONE verbatim
    id within a family. Returns the emitted rows.

    - identical payload hashes MERGE into one row carrying `axes:[…]`
      (legitimate cross-bundle definition copies);
    - differing payloads stay DISTINCT via `<id>@<contentHash8>` on the
      emitted id, the verbatim id preserved inside `fields`.
    Determinism: contributors sort by (bundle, pathId); subgroups sort by
    hash; the lowest-hash subgroup keeps the bare id when disambiguation
    fires, so scan order never changes the outcome."""
    groups: dict[str, list[dict]] = {}
    for c in candidates:
        groups.setdefault(c["hash"], []).append(c)

    subgroups = [sorted(g, key=lambda c: (c["bundle"], c["pathId"]))
                 for h, g in sorted(groups.items())]

    if len(subgroups) == 1:
        members = subgroups[0]
        if len(members) == 1:
            return [members[0]["row"]]
        counters["mergedDuplicates"] += len(members) - 1
        carrier = members[0]["row"]
        carrier["axes"] = sorted({m["axis"] for m in members})
        return [carrier]

    # differing payloads: every subgroup emits its own row; the lowest-hash
    # subgroup keeps the bare verbatim id, the rest take @<contentHash8>
    subgroups.sort(key=lambda g: (g[0]["hash"], g[0]["bundle"], g[0]["pathId"]))
    emitted: list[dict] = []
    for gi, members in enumerate(subgroups):
        if len(members) > 1:
            counters["mergedDuplicates"] += len(members) - 1
        carrier = members[0]["row"]
        axes = sorted({m["axis"] for m in members})
        if len(axes) > 1 or any(m["axis"] != axes[0] for m in members) \
                or len(members) > 1:
            carrier["axes"] = axes
        if gi > 0:
            suffix = members[0]["hash"][:8]
            f = carrier.get("fields")
            if isinstance(f, dict) and f.get("id") is None:
                f["id"] = carrier["id"]          # verbatim preserved (Principle one)
            carrier["id"] = f"{carrier['id']}@{suffix}"
            counters["disambiguatedDuplicates"] += 1
        emitted.append(carrier)
    return emitted


# ---------------------------------------------------------------------------
# Stage entrypoint

def run(game_root: Path, extracted_root: Path) -> int:
    monobehaviours_dir = extracted_root / "harvest" / "monobehaviours"
    catalog_path = extracted_root / "addressables" / "catalog.json"
    matrix_path = extracted_root / "locales" / "locale-matrix.json"
    structural = extracted_root / "decompiled" / "structural"
    for p in (monobehaviours_dir, catalog_path, matrix_path):
        if not p.exists():
            raise tc.StageError(
                f"missing upstream artifact {p} — run the upstream stages "
                "first (--skip/--only per the prepared-tree procedure)",
                exit_code=3)

    identity_path = extracted_root / "identity.json"
    build_id = json.loads(identity_path.read_text(encoding="utf-8")).get("buildId") \
        if identity_path.is_file() else None
    matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    matrix_keys = matrix.get("keys", {})
    structural_inputs = sorted(p.name for p in structural.iterdir()) \
        if structural.is_dir() else []
    gate = DefinitionGate(structural if structural.is_dir() else None)

    stubs_dir = extracted_root / "stubs"
    relinks_dir = extracted_root / "relinks"
    for d in (stubs_dir, relinks_dir):
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True, exist_ok=True)

    # policy state -----------------------------------------------------------------
    candidates_by_kind: dict[str, dict[str, list[dict]]] = {k: {} for k in KINDS}
    scan_scope: dict[str, dict] = {k: {"bundles": set(), "classes": set()}
                                   for k in KINDS}
    scan_universe: dict[str, set] = {"bundles": set(), "classes": set()}
    unmapped: dict[str, dict] = {}
    id_absences: dict[str, dict] = {}
    payload_index: dict = {}
    counters = {"componentExcluded": 0, "mergedDuplicates": 0,
                "disambiguatedDuplicates": 0, "identifierLess": 0}
    unparsed_stems = 0
    resolved_classes = 0
    generic_classes = 0

    # -- load pass: exclusion → kind assignment → id resolution --------------------
    for family, cls, bundle, path_id, payload, path in load_monobehaviour_dumps(
            monobehaviours_dir):
        scan_universe["bundles"].add(bundle)
        scan_universe["classes"].add(cls)
        if path_id is None:
            unparsed_stems += 1
        else:
            payload_index[(bundle, path_id)] = payload
        if cls and cls != GENERIC_SCRIPT_CLASS:
            resolved_classes += 1
        else:
            generic_classes += 1

        is_candidate, why_not = gate_candidate(cls, gate)
        if not is_candidate:
            counters["componentExcluded"] += 1
            entry = unmapped.setdefault(cls or GENERIC_SCRIPT_CLASS, {
                "class": cls or GENERIC_SCRIPT_CLASS, "bundles": [],
                "objectCount": 0, "evidence": why_not})
            if bundle not in entry["bundles"]:
                entry["bundles"].append(bundle)
            entry["objectCount"] += 1
            continue

        fields_block = payload_fields(payload)
        kind, inferred, method = assign_kind(cls, family, fields_block)
        eid = extract_id(fields_block)
        if kind is None:
            # truthful per-cause evidence (ledgered absence is factual)
            evidence = "no seeded kind covers this class"
            entry = unmapped.setdefault(cls, {
                "class": cls, "bundles": [], "objectCount": 0,
                "evidence": evidence})
            if bundle not in entry["bundles"]:
                entry["bundles"].append(bundle)
            entry["objectCount"] += 1
            continue
        # record the scan scope BEFORE the identifier gate: a family whose
        # candidates all matched the kind but yielded no identifier must
        # still report the bundles/classes actually scanned (spec §3
        # stage-5 absence rows name the scan scope)
        scan_scope[kind]["bundles"].add(bundle)
        scan_scope[kind]["classes"].add(cls)
        if eid is None:
            counters["identifierLess"] += 1
            agg = id_absences.setdefault(kind, {
                "kind": kind, "absenceType": "no-identifier",
                "scannedBundles": set(), "scannedClasses": set(),
                "count": 0, "samples": []})
            agg["scannedBundles"].add(bundle)
            agg["scannedClasses"].add(cls)
            agg["count"] += 1
            if len(agg["samples"]) < ABSENCE_SAMPLE_CAP:
                sample = {"bundle": bundle, "pathId": path_id, "class": cls}
                nm = fields_block.get("m_Name")
                if isinstance(nm, str) and nm:
                    sample["dumpName"] = nm
                agg["samples"].append(sample)
            continue

        raw_fields = {k: v for k, v in fields_block.items()
                      if not k.startswith("_")}
        row = {
            "id": eid,
            "kind": kind,
            "slug": None,
            "fields": raw_fields,
            "source": {"bundle": bundle, "pathId": path_id, "class": cls},
            "provisional": True,
            "inferred": inferred,
            "method": method,
            "buildId": build_id,
        }
        validate_row(row)
        bucket = candidates_by_kind[kind].setdefault(str(eid), [])
        bucket.append({
            "row": row, "hash": payload_hash(payload),
            "bundle": bundle, "pathId": path_id,
            "axis": tc.axis_for_bundle_name(bundle)})

    # -- duplicate policy + final rows ---------------------------------------------
    rows_by_kind: dict[str, list[dict]] = {}
    for kind in KINDS:
        final: list[dict] = []
        for eid_key in sorted(candidates_by_kind[kind]):
            final.extend(apply_duplicate_policy(
                kind, candidates_by_kind[kind][eid_key], counters))
        final.sort(key=lambda r: str(r["id"]))
        rows_by_kind[kind] = final

    # -- write stubs + ledgers ---------------------------------------------------
    absences = []
    for kind in KINDS:
        rows = rows_by_kind[kind]
        if rows:
            # empty data files are never emitted: a family with zero rows is
            # represented by its absence row alone (spec §3 stage-5 XOR), and
            # an empty <kind>.jsonl final is indistinguishable from a partial
            # write after an interrupted run
            log_util.write_jsonl(stubs_dir / KIND_FILES[kind], rows)
        else:
            scope = scan_scope[kind]
            bundles = sorted(scope["bundles"]) or sorted(scan_universe["bundles"])
            classes = sorted(scope["classes"]) or sorted(scan_universe["classes"])
            absences.append({
                "kind": kind,
                "buildId": build_id,
                "scannedBundles": bundles,
                "scannedClasses": classes,
                "evidence": "no identifiable rows after scanning the "
                            "monobehaviour dumps",
            })
    for kind in sorted(id_absences):
        agg = id_absences[kind]
        absences.append({
            "kind": kind,
            "absenceType": agg["absenceType"],
            "count": agg["count"],
            "samples": agg["samples"],
            "scannedBundles": sorted(agg["scannedBundles"]),
            "scannedClasses": sorted(agg["scannedClasses"]),
            "evidence": "candidates matched the seeded kind but carried no "
                        "resolvable identifier — ledgered, never emitted "
                        "(Revision 6 rule 2)",
            "buildId": build_id,
        })
    absences.sort(key=lambda r: (r["kind"], r.get("absenceType", "")))
    log_util.write_jsonl(stubs_dir / "_absences.jsonl", absences)
    unmapped_rows = sorted(unmapped.values(), key=lambda r: r["class"])
    log_util.write_jsonl(stubs_dir / "_unmapped-families.jsonl", unmapped_rows)

    join_stats: dict = {}
    availability = build_locale_availability(rows_by_kind, matrix_keys,
                                             payload_index, build_id,
                                             stats_out=join_stats)
    log_util.write_jsonl(relinks_dir / "locale_availability.jsonl", availability)

    # -- mechanical acceptance checks ---------------------------------------------
    problems: list[str] = []
    for kind in KINDS:
        rows = rows_by_kind[kind]
        if not rows and not any(a["kind"] == kind and "absenceType" not in a
                                for a in absences):
            problems.append(f"family '{kind}' empty without absence ledger")
        ids = [str(r["id"]) for r in rows]
        if len(set(ids)) != len(ids):
            problems.append(f"duplicate ids within family '{kind}' "
                            "(post-policy uniqueness violated)")
        bad_build = sum(1 for r in rows if r["buildId"] != build_id)
        if bad_build:
            problems.append(f"{bad_build} rows in '{kind}' carry wrong buildId")
    for r in availability:
        for req in ("availableLocales", "namedLocales", "fieldPresence"):
            if req not in r:
                problems.append(f"availability row missing '{req}'")

    # signed-stem contract: recover source.pathId + full bundle name for ALL
    # export-manifest rows (Revision 6 amendment 2 — assert 0 unparsed stems)
    manifest_path = extracted_root / "harvest" / "export-manifest.jsonl"
    manifest_checked = manifest_unparsed = manifest_mismatched = 0
    manifest_examples: list[str] = []
    if manifest_path.is_file():
        with open(manifest_path, "r", encoding="utf-8", newline="\n") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                mrow = json.loads(line)
                manifest_checked += 1
                parsed = tc.parse_harvest_stem(Path(mrow["outRelPath"]).name)
                if parsed is None:
                    manifest_unparsed += 1
                    if len(manifest_examples) < 5:
                        manifest_examples.append(
                            f"unparsed stem: {mrow['outRelPath']}")
                    continue
                base, pid = parsed
                sb = Path(mrow["sourceBundle"]).name
                want_base = sb[:-len(".bundle")] if sb.endswith(".bundle") else sb
                if base != want_base or pid != mrow["pathId"]:
                    manifest_mismatched += 1
                    if len(manifest_examples) < 5:
                        manifest_examples.append(
                            f"{mrow['outRelPath']} parsed ({base}, {pid}) vs "
                            f"manifest ({want_base}, {mrow['pathId']})")
    if manifest_unparsed or manifest_mismatched:
        problems.append(
            f"signed-stem contract violated on export-manifest: "
            f"unparsed={manifest_unparsed} mismatched={manifest_mismatched}")
    if unparsed_stems:
        problems.append(f"{unparsed_stems} monobehaviour dump stems did not "
                        "parse as <bundle-stem>_<signed-pathId>")

    # identifier preservation: byte-match against source dumps, REAL shapes
    checked = mismatched = 0
    mismatch_examples: list[str] = []
    for kind in KINDS:
        rows = rows_by_kind[kind]
        target = set(sample_for_check(sorted({str(r["id"]) for r in rows})))
        for r in rows:
            if str(r["id"]) not in target:
                continue
            payload = payload_index.get((r["source"]["bundle"],
                                         r["source"]["pathId"]))
            if payload is None:
                mismatched += 1
                if len(mismatch_examples) < 5:
                    mismatch_examples.append(
                        f"{kind}/{r['id']}: source dump not found at "
                        f"{r['source']['bundle']}#{r['source']['pathId']}")
                continue
            src_id = extract_id(payload_fields(payload))
            checked += 1
            if src_id is None or str(src_id) != verbatim_id_of(r):
                mismatched += 1
                if len(mismatch_examples) < 5:
                    mismatch_examples.append(
                        f"{kind}/{r['id']}: dump id={src_id!r} vs emitted "
                        f"verbatim={verbatim_id_of(r)!r}")
    if checked == 0:
        # Revision 6 amendment 3: a checked=0 run fails its own gate
        problems.append("identifierByteMatch checked=0 — the verifier "
                        "validated nothing against real dump shapes")

    distinct_entities = len({(r["kind"], str(r["id"])) for r in availability})
    lines = [
        "- exitCode: 0" if not problems else f"- exitCode: 1 ({'; '.join(problems)})",
        "- stubRowsByKind: "
        + json.dumps({k: len(rows_by_kind[k]) for k in KINDS}, sort_keys=True),
        f"- identityPolicy: componentExcluded={counters['componentExcluded']}; "
        f"identifierLess={counters['identifierLess']} (ledgered+sampled); "
        f"mergedDuplicates={counters['mergedDuplicates']}; "
        f"disambiguatedDuplicates={counters['disambiguatedDuplicates']}",
        f"- scriptClassResolution: resolved={resolved_classes} "
        f"generic/unresolved={generic_classes}",
        f"- absences: {len(absences)}; unmappedClasses: {len(unmapped_rows)}",
        f"- localeAvailabilityRows: {len(availability)} "
        f"(distinctJoinedEntities: {distinct_entities}); regenerated this run; "
        f"joinEvidence: {json.dumps(join_stats, sort_keys=True)}",
        "- identifierByteMatch: "
        + (f"checked={checked} mismatches={mismatched}" if not mismatch_examples
           else f"checked={checked} mismatches={mismatched}; e.g. "
                + "; ".join(mismatch_examples)),
        f"- manifestStemContract: rows={manifest_checked} "
        f"unparsed={manifest_unparsed} mismatched={manifest_mismatched}",
        f"- structuralInputs: {structural_inputs}",
    ]
    lines += [f"- PROBLEM: {p}" for p in problems]
    log_util.append_run_section(extracted_root, "emit-stub-datasets", lines)

    print(f"[emit-stub-datasets] stubs="
          f"{json.dumps({k: len(rows_by_kind[k]) for k in KINDS}, sort_keys=True)} "
          f"unmapped={len(unmapped_rows)} availability={len(availability)}")
    print(f"[emit-stub-datasets] policy: componentExcluded="
          f"{counters['componentExcluded']} identifierLess="
          f"{counters['identifierLess']} merged="
          f"{counters['mergedDuplicates']} disambiguated="
          f"{counters['disambiguatedDuplicates']} byteMatch={checked}/{mismatched}")
    for p in problems:
        print(f"[emit-stub-datasets] PROBLEM: {p}", file=sys.stderr)
    if problems:
        return 1
    return 0


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
    except tc.StageError as exc:
        log_util.append_failure_section(root, "emit-stub-datasets",
                                        exc.exit_code, [str(exc)])
        print(f"[emit-stub-datasets] ERROR: {exc}", file=sys.stderr)
        return exc.exit_code


if __name__ == "__main__":
    sys.exit(main())
