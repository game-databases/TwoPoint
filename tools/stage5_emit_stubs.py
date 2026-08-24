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
# class-name hints are the sharper signal when present)
KIND_CLASS_HINTS = {
    "item": ["ItemConfig", "ItemDefinition", "ItemData"],
    "room": ["RoomConfig", "RoomDefinition", "RoomData"],
    "course": ["CourseConfig", "CourseDefinition", "CourseData"],
    "staff": ["StaffConfig", "StaffDefinition", "StaffData", "StaffTraits"],
    "student-type": ["StudentConfig", "StudentType", "StudentArchetype",
                     "StudentData"],
    "unlockable": ["UnlockableConfig", "UnlockDefinition", "UnlockableData"],
    "campus-level": ["LevelDatabase", "CampusLevelConfig", "LevelConfig"],
    "config": ["GameConfig", "ConfigAsset", "BalanceConfig", "GlobalConfig"],
    "metagame-node": ["ResearchNode", "MetagameNode", "ProgressionNode",
                      "MetaNode"],
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
    for k in ID_FIELD_PRIORITY:
        if k in fields and isinstance(fields[k], (str, int)) \
                and not isinstance(fields[k], bool):
            return fields[k]
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
    """Yield (family, class, bundle, pathId, payload, relpath) sorted by
    relpath — deterministic enumeration."""
    root = monobehaviours_dir
    for path in sorted(root.rglob("*.json"), key=lambda p: p.as_posix()):
        rel = path.relative_to(root)
        parts = rel.parts
        family = parts[0] if len(parts) >= 3 else ""
        cls_dir = parts[1] if len(parts) >= 3 else ""
        stem = path.stem
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            continue
        bundle, path_id = stem, None
        m = re.search(r"_(\d+)$", stem)
        if m:
            path_id = int(m.group(1))
            # roster-style basename: the dump filename embeds
            # `<bundle-stem>_<pathId>`; restore the .bundle extension so
            # source.bundle / unmapped bundles[] join roster basenames
            bundle = stem[: m.start()] + ".bundle"
        cls = payload.get("_scriptClass") or cls_dir
        yield family, cls, bundle, path_id, payload, path


def index_monobehaviour_dumps(monobehaviours_dir: Path) -> dict:
    """pathId → [(bundle, payload)] for every parseable dump, in the
    deterministic scan order. The run() load pass builds this same index
    inline while payloads are already in hand — this walker exists for
    callers that only hold the directory."""
    index: dict = {}
    for _family, _cls, bundle, path_id, payload, _path in \
            load_monobehaviour_dumps(monobehaviours_dir):
        if path_id is not None:
            index.setdefault(path_id, []).append((bundle, payload))
    return index


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
                              build_id) -> list[dict]:
    """Entity-granular availability via the PINNED join procedure:
    1. collect the entity dump's string-valued fields;
    2. exact-equal to a locale-matrix key → HARD join;
    3. `<entityId>_<role>` convention corroborated by the matrix → INFERRED;
    4. no other association path exists.

    `dumps_source` is the pathId → [(bundle, payload)] index built during the
    load pass; a monobehaviours directory is also accepted (indexed once).
    Availability is evidence-based (fail-closed): only HARD-joined keys grant
    locale coverage — availableLocales is the intersection of their matrix
    locale sets, and fieldPresence lists the granting fields per locale.
    Convention joins record joinMethod/joinInferred but claim no locales,
    because their keys are not observed in any locale bundle yet."""
    if isinstance(dumps_source, Path):
        dumps_source = index_monobehaviour_dumps(dumps_source)
    availability: list[dict] = []
    all_prefixes = set()
    for key in matrix_keys:
        if isinstance(key, str) and "_" in key:
            all_prefixes.add(key.rsplit("_", 1)[0])

    for kind, rows in sorted(rows_by_kind.items()):
        seen_ids: set = set()
        for row in rows:
            eid = row["id"]
            if eid in seen_ids:
                continue
            seen_ids.add(eid)
            payload: dict | None = None
            # locate the source dump from the in-memory index (no re-walk,
            # no re-read); the first indexed candidate whose identifier
            # byte-matches wins, as before
            src = row["source"]
            for _bundle, cand_payload in dumps_source.get(src.get("pathId"), []):
                if extract_id(cand_payload.get("fields", {})) == eid \
                        or extract_id(cand_payload) == eid:
                    payload = cand_payload
                    break
            if payload is None:
                continue
            fields_block = payload.get("fields", payload)
            hard_fields: dict[str, str] = {}
            conv_fields: dict[str, str] = {}
            for fname, fval in fields_block.items():
                if not isinstance(fval, str) or fname.startswith("_"):
                    continue
                if fval in matrix_keys:
                    hard_fields[fname] = fval
                elif isinstance(eid, str) and eid \
                        and fval.startswith(eid + "_"):
                    prefix_ok = fval.rsplit("_", 1)[0] in all_prefixes \
                        or fval in all_prefixes
                    if matrix_keys and (prefix_ok or not all_prefixes):
                        conv_fields[fname] = fval
            joins = dict(hard_fields)
            joins.update(conv_fields)
            if not joins:
                continue
            locales_per_field: dict[str, set[str]] = {
                f: set(matrix_keys[key]["locales"])
                for f, key in joins.items() if key in matrix_keys}
            available = set.intersection(*locales_per_field.values()) \
                if locales_per_field else set()
            # named-field coverage claims only HARD-joined keys (fail-closed):
            # a convention-shaped named join records joinMethod but no locales,
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
    return availability


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

    stubs_dir = extracted_root / "stubs"
    relinks_dir = extracted_root / "relinks"
    for d in (stubs_dir, relinks_dir):
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True, exist_ok=True)

    rows_by_kind: dict[str, list[dict]] = {k: [] for k in KINDS}
    scan_scope: dict[str, dict] = {k: {"bundles": set(), "classes": set()}
                                   for k in KINDS}
    # every family's scan walks the WHOLE dump tree; this is the actual
    # universe a zero-candidate family scanned (absence rows must name it,
    # never empty lists)
    scan_universe: dict[str, set] = {"bundles": set(), "classes": set()}
    unmapped: dict[str, dict] = {}
    dump_index: dict = {}

    for family, cls, bundle, path_id, payload, path in load_monobehaviour_dumps(
            monobehaviours_dir):
        scan_universe["bundles"].add(bundle)
        scan_universe["classes"].add(cls)
        if path_id is not None:
            dump_index.setdefault(path_id, []).append((bundle, payload))
        fields = payload.get("fields", payload)
        if not isinstance(fields, dict):
            fields = {}
        kind, inferred, method = assign_kind(cls, family, fields)
        if kind is not None:
            # record the scan scope BEFORE the identifier gate: a family whose
            # candidates all matched the kind but yielded no identifier must
            # still report the bundles/classes actually scanned (spec §3
            # stage-5 absence rows name the scan scope)
            scan_scope[kind]["bundles"].add(bundle)
            scan_scope[kind]["classes"].add(cls)
        eid = extract_id(fields)
        if kind is None or eid is None:
            # truthful per-cause evidence (ledgered absence is factual)
            evidence = ("no seeded kind covers this class" if kind is None
                        else "seeded kind matched but no identifier field found")
            entry = unmapped.setdefault(cls, {
                "class": cls, "bundles": [], "objectCount": 0,
                "evidence": evidence})
            if bundle not in entry["bundles"]:
                entry["bundles"].append(bundle)
            entry["objectCount"] += 1
            continue
        raw_fields = {k: v for k, v in fields.items()
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
        rows_by_kind[kind].append(row)

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
    absences.sort(key=lambda r: r["kind"])
    log_util.write_jsonl(stubs_dir / "_absences.jsonl", absences)
    unmapped_rows = sorted(unmapped.values(), key=lambda r: r["class"])
    log_util.write_jsonl(stubs_dir / "_unmapped-families.jsonl", unmapped_rows)

    availability = build_locale_availability(rows_by_kind, matrix_keys,
                                             dump_index, build_id)
    log_util.write_jsonl(relinks_dir / "locale_availability.jsonl", availability)

    # -- mechanical acceptance checks ---------------------------------------------
    problems: list[str] = []
    for kind in KINDS:
        rows = rows_by_kind[kind]
        if not rows and not any(a["kind"] == kind for a in absences):
            problems.append(f"family '{kind}' empty without absence ledger")
        ids = [r["id"] for r in rows]
        if len(set(map(str, ids))) != len(ids):
            problems.append(f"duplicate ids within family '{kind}'")
        bad_build = sum(1 for r in rows if r["buildId"] != build_id)
        if bad_build:
            problems.append(f"{bad_build} rows in '{kind}' carry wrong buildId")
    for r in availability:
        for req in ("availableLocales", "namedLocales", "fieldPresence"):
            if req not in r:
                problems.append(f"availability row missing '{req}'")

    # identifier preservation: byte-match against source dumps
    checked = mismatched = 0
    for kind in KINDS:
        rows = rows_by_kind[kind]
        picks = {(str(r["id"]), r["source"]["pathId"]) for r in rows}
        target = sample_for_check(sorted({str(i) for i, _p in picks}))
        want = set(target)
        for family_cls_dir in sorted(monobehaviours_dir.glob("*/*/*.json")):
            try:
                data = json.loads(family_cls_dir.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                continue
            eid = extract_id(data.get("fields", {}))
            if eid is not None and str(eid) in want:
                checked += 1
                pid = re.search(r"_(\d+)\.json$", family_cls_dir.name)
                if (str(eid), int(pid.group(1)) if pid else None) not in picks:
                    mismatched += 1

    distinct_entities = len({(r["kind"], str(r["id"])) for r in availability})
    lines = [
        "- exitCode: 0" if not problems else f"- exitCode: 1 ({'; '.join(problems)})",
        "- stubRowsByKind: "
        + json.dumps({k: len(rows_by_kind[k]) for k in KINDS}, sort_keys=True),
        f"- absences: {len(absences)}; unmappedClasses: {len(unmapped_rows)}",
        f"- localeAvailabilityRows: {len(availability)} "
        f"(distinctJoinedEntities: {distinct_entities}); regenerated this run",
        f"- identifierByteMatch: checked={checked} mismatches={mismatched}",
        f"- structuralInputs: {structural_inputs}",
    ]
    lines += [f"- PROBLEM: {p}" for p in problems]
    log_util.append_run_section(extracted_root, "emit-stub-datasets", lines)

    print(f"[emit-stub-datasets] stubs="
          f"{json.dumps({k: len(rows_by_kind[k]) for k in KINDS}, sort_keys=True)} "
          f"unmapped={len(unmapped_rows)} availability={len(availability)}")
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
        print(f"[emit-stub-datasets] ERROR: {exc}", file=sys.stderr)
        return exc.exit_code


if __name__ == "__main__":
    sys.exit(main())
