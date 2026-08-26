#!/usr/bin/env python3
"""Stage 12 — search-corpus (piece-08, spec Revision 3).

Turns the verified entity/locale corpus into the search DATA layer — a
purely derived, disposable, rebuilt-from-committed-inputs artifact set
under extracted/search/ (spec §1/§4/§5):

  S1 dual-universe resolution  — narrow 7,178 (asserted, pinned recipe) +
                                 expanded planning floor 10,200 (computed,
                                 DRIFT-tracked) with per-seed-basis
                                 components (arbiter RF-B);
  S2 per-locale shards         — 13 route-coded document shards +
                                 13 titles projections ({kind,id,t});
  S3 alias layer               — id tokens (lowercased rule, arbiter RF-A),
                                 name variants, dev strings, course-name
                                 resolution ladder + collision truth;
  S4 tokenization              — frozen 13-entry analyzer table + vocab
                                 census + typo budget;
  S5 assembly                  — manifest.json + hashes.json + _ledger.jsonl,
                                 rebuild hook with THE exit-2 discrimination
                                 rule (tolerate relink's declared steady
                                 state; never mask a real regression).

PURELY DERIVED stage: opens NO bundles, imports NO UnityPy, needs NO game
dir. Upstream set = committed extracted/ artifacts + two consumed stamps;
OPTIONAL inputs (item-title join edges, curated course alias table)
ledger-degrade loudly instead of failing (pre-rulings 2 and 4).

Exit codes (piece-1 contract): 0 success · 1 stage failure (schema/
self-validation breakage OR same-buildId UPSTREAM REGRESSION — artifacts
NOT written) · 2 completed-with-ledger (the EXPECTED steady state on this
corpus) · 3 environment/gate refusal (missing upstream, named).

Determinism: byte-stable reruns (sorted enumeration + sorted JSON keys,
UTF-8 LF, temp-file + atomic-rename, no wall-clock timestamps in outputs);
seeds reconcile with `DRIFT:` lines — the fresh measurement wins.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import log_util
import search_util as su
import tpc_common as tc

STAGE_ID = "search-corpus"
SEARCH_DIR = "search"

SCRIPT_DEPS = ["stage12_search_corpus.py", "search_util.py",
               "tpc_common.py", "log_util.py"]

# ---------------------------------------------------------------------------
# Spec §2 seeds — reconcile, never trust: divergence prints `DRIFT:` and the
# fresh measurement wins. Hard EQUALITY asserts fire only at the seed
# buildId (bounds REBASE across builds — piece-07 L6 precedent), because a
# hostless mini fixture measures its own smaller truths.

SEED_BUILDID = 20226581

SEEDS = {
    "stubRows": 13_443,
    "stubRowsPerKind": {"campus-level": 17, "config": 8_430, "course": 69,
                        "item": 3_885, "metagame-node": 454, "room": 116,
                        "staff": 3, "student-type": 54, "unlockable": 415},
    "localeEdgePairs": 5_850,
    "narrowCarriers": 4_298,
    "universeNarrow": 7_178,
    "narrowPerKind": {"campus-level": 13, "config": 3_856, "course": 41,
                      "item": 2_649, "metagame-node": 406, "room": 107,
                      "staff": 3, "student-type": 54, "unlockable": 49},
    "plainNameLiterals": {"total": 1_456, "perKind": {
        "campus-level": 13, "config": 1_402, "unlockable": 41}},
    "configLocalisedNameInstances": 552,
    "titleCarrierInstances": 730,          # DRIFT-tracked, NEVER asserted
    "displayNameAllClass": 193,            # provenance data beside
    "displayNameBrushScoped": 170,
    "roomNamePresence": 49,
    "roomNameTextBearing": 48,
    "unlockableMTermRows": 55,
    "unlockableMTermResolvedEn": 53,
    "unlockableDescriptiveName": 27,
    "joinCeilings": {"variationRefs": 353, "twinEdges": 1_652,
                     "total": 2_005},
    "idTokens": 3_166,
    "idTokensCaseSensitiveSuperset": 3_224,
    "caseFoldCollisions": 58,
    "devStringRows": 3_874,
    "g4DevOnlyNames": {"config": 718, "item": 779, "metagame-node": 46},
    "narrowTitleEdges": 2_993,
    "narrowTitleKeys": 2_059,
    "narrowTitleEnResolvePct": "100",
    "expandedWalkerKeys": 2_748,           # UNVERIFIED doc-probe seed (vB
    # saw 2,655 over its superset) — carried, reconciled fresh, never
    # load-bearing, never asserted (reviewer F10).
    "cleanedEmptyDropped": 23,
    "collisionSeed": {
        "collidingPairs": 264,
        "topPairs": [{"count": 53, "kind": "config", "title": "Lab Work"},
                     {"count": 51, "kind": "config",
                      "title": "Specialist Book Report"}],
        "ignoreKindCollisions": 320,
        "withinLocaleDuplicateTexts": {"en": 1_570, "ko": 1_702,
                                       "tr": 1_625, "zh-Hans": 1_668},
    },
    "courseFamilyCounts": {"courses-courses": 18, "courses-dlc": 9,
                           "marketing-courses": 24, "qualification": 28,
                           "research-courses": 4},
    "courseDefsMechanicalNoMap": 19,       # staging-dependent intermediate
    "courseDefsWithTokenMap": 23,
    "uniformResolved": 62,
    "marketingResolved": 37,
    "planningFloor": 10_200,
    "planningFloorShare": "75.9%",
    "vocabEndpoints": {"en": 11_897, "ko": 28_594, "tr": 23_445},
    "koCjkBearingRows": 15_213,
    "registryRows": 15_675,
    "referencedTerms": 6_526,
    "uiChromeTerms": 9_146,
    "boneStringsConfigs": 139_847,
    "planesBytes": 23_107_394,
    "entityRelevantBytes": 9_454_777,
    "f14TitleTextBytes": {"en": 34_044, "ru": 62_286, "zh-Hant": 29_645},
    # §S5.3 steady-state bounds — ALL INCLUSIVE (eight members sit ON their
    # bounds today; exclusive comparisons fail day one, reviewer F9).
    "bounds": {
        "statusCounts.missing": ("<=", 73),
        "statusCounts.modeled": (">=", 24),
        "danglingDistinctGuids": ("<=", 1_137),
        "registryMisses": ("<=", 5),
        "entityLocaleRows": (">=", 10_964),
        "registryRows": (">=", 15_675),
        "referencedTerms": (">=", 6_526),
        "localeRowsWindow": ([15_371, 15_665]),
    },
}

LEDGER_UNBLOCK = {
    "item-title-joins-absent":
        "emit the variation->Lite and definition->_Lite twin name edges "
        "from the relink stage (piece-02 family work; AGENTS rule 8)",
    "course-name-open":
        "author a curated row in data/sources/derived/"
        "course-name-aliases.jsonl ({courseId, termKey, method, "
        "inferred:true, sourceRefs[]})",
    "alias-input-absent":
        "commit data/sources/derived/course-name-aliases.jsonl (shared "
        "with piece-07; Documentator-authored prepared input)",
    "dev-only-names":
        "acceptable declared fallback — site lane merges the en shard as a "
        "SECONDARY corpus when it wants dev-named entities searchable",
    "mt-unresolved":
        "DisplayName.mTerm walker extension is a relink amendment "
        "candidate (G7, owner-routed); consumed read-only here",
    "campus-level-scope":
        "flip the visibility roster (one pinned list) to publish internal "
        "levels — arbiter-piece08 R3",
}

# course-name-open reasons (scout F20 genuinely-nameless set)
COURSE_OPEN_REASONS = {
    "Course_Archaeology_Easter_23": "seasonal event course, no name family",
    "Course_SpaceExplorer": "unreferenced — no _Name key in any family",
    "Course_SummerSchool": "seasonal/unreferenced — no _Name key anywhere",
    "Course_KnightSchool_LordBlaggard": "dev-superceded — shares Knight "
                                        "School with Course_KnightSchool",
    "Course_PerformingArts": "rename — qualification chain spells it Music",
}


def drift_note(entity_id: str) -> str:
    return COURSE_OPEN_REASONS.get(entity_id, "unresolved — no name family "
                                              "and no curated row")


# ---------------------------------------------------------------------------
# Inputs (upstream gate — ANY missing required input ⇒ exit 3 naming it)

REQUIRED_INPUTS = [
    "identity.json",
    ".stage-stamps/relink.json",
    ".stage-stamps/localisation.json",
    "locales/locale-matrix.json",
    "relinks/entity_locale.jsonl",
    "relinks/i2_term_registry.jsonl",
    "relinks/locale_term_entity.jsonl",
    "relinks/matrix.json",
    "relinks/guid_bridge_report.json",
    "relinks/locale_join_report.json",
] + [f"stubs/{f}" for f in su.KIND_FILES.values()]
# per-locale tables resolve inside load_inputs (a hostless mini fixture
# names fewer than 13); the OPTIONAL pair-scan + curated alias inputs are
# ledger-degraded, never gates.


class Drift:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def check(self, label: str, seed, measured) -> None:
        if seed is not None and measured != seed:
            self.lines.append(
                f"DRIFT: {label} seed {seed!r} vs measured {measured!r} "
                "— fresh wins")

    def note(self, line: str) -> None:
        self.lines.append(line)


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with open(path, "r", encoding="utf-8", newline="\n") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def pct(num: int, den: int) -> str:
    if den <= 0:
        return "0.00%"
    return f"{num * 100 / den:.2f}%"


def precheck_inputs(extracted_root: Path) -> None:
    missing = [rel for rel in REQUIRED_INPUTS
               if not (extracted_root / rel).is_file()]
    if missing:
        raise tc.StageError(
            f"stage '{STAGE_ID}' is missing upstream artifacts "
            f"({', '.join(missing)}) — prepare the tree first "
            "(client mode: run the pipeline without this stage; hostless "
            "smoke: tests/build_fixture_tree.py --stage search-corpus)",
            exit_code=3)


def load_inputs(extracted_root: Path, drift: Drift) -> dict:
    inputs: dict = {}
    identity = json.loads((extracted_root / "identity.json")
                          .read_text(encoding="utf-8"))
    inputs["build_id"] = identity["buildId"]

    for name in ("relink", "localisation"):
        stamp = log_util.load_stamp(extracted_root, name)
        if stamp is None:
            raise tc.StageError(
                f"consumed stage stamp .stage-stamps/{name}.json is absent "
                f"— run the {name} stage first", exit_code=3)
        code = stamp.get("exitCode")
        if name == "relink" and code not in (0, 2):
            raise tc.StageError(
                f"consumed stamp .stage-stamps/relink.json carries "
                f"exitCode={code!r} outside the declared set {{0, 2}} "
                "(exit 2 is relink's DECLARED steady state — anything else "
                "is a refusal)", exit_code=3)
        if name == "localisation" and code != 0:
            raise tc.StageError(
                f"consumed stamp .stage-stamps/localisation.json carries "
                f"exitCode={code!r}; localisation must complete cleanly",
                exit_code=3)
        inputs[f"{name}_stamp"] = stamp

    tables: dict[str, dict[str, str]] = {}
    named: list[str] = []
    for p in sorted((extracted_root / "locales").glob("*.jsonl")):
        loc = p.stem
        if loc == "base-overlay" or loc not in tc.EMITTED_LOCALES:
            continue
        tables[loc] = {r["id"]: (r.get("text") or "")
                       for r in load_jsonl(p)}
        named.append(loc)
    if su.PIVOT not in tables:
        raise tc.StageError(
            "pivot locale table locales/en.jsonl is absent — the shard set "
            "is undefined without it", exit_code=3)
    unknown = sorted(set(tables) - set(tc.EMITTED_LOCALES))
    if unknown:
        raise tc.StageError(
            f"locale tables outside the pinned BCP-47 universe: {unknown}",
            exit_code=1)
    inputs["tables"] = tables
    inputs["locales"] = sorted(tables)

    inputs["stubs"] = {kind: load_jsonl(extracted_root /
                                        f"stubs/{su.KIND_FILES[kind]}")
                       for kind in su.KINDS}
    inputs["edges"] = load_jsonl(extracted_root /
                                 "relinks/entity_locale.jsonl")
    inputs["registry"] = load_jsonl(extracted_root /
                                    "relinks/i2_term_registry.jsonl")
    inputs["reverse"] = load_jsonl(extracted_root /
                                   "relinks/locale_term_entity.jsonl")
    inputs["matrix"] = json.loads((extracted_root / "relinks/matrix.json")
                                  .read_text(encoding="utf-8"))
    inputs["guid_report"] = json.loads(
        (extracted_root / "relinks/guid_bridge_report.json")
        .read_text(encoding="utf-8"))
    inputs["join_report"] = json.loads(
        (extracted_root / "relinks/locale_join_report.json")
        .read_text(encoding="utf-8"))
    return inputs


def validate_structure(inputs: dict) -> None:
    """Structural validity leg (§S5.3): violations are exit 1 regardless of
    buildId — these are schema invariants, not steady-state bounds."""
    mx = inputs["matrix"]
    cells = mx.get("pairs")
    if not isinstance(cells, list) or len(cells) != 100:
        raise tc.StageError(
            f"relinks/matrix.json must hold cellsTotal == 100 ordered "
            f"cells (measured {len(cells) if isinstance(cells, list) else '!list'})",
            exit_code=1)
    statuses = {"modeled", "missing", "partial"}
    for cell in cells:
        if cell.get("status") not in statuses:
            raise tc.StageError(
                f"matrix cell {cell.get('srcKind')}->{cell.get('dstKind')} "
                f"carries status {cell.get('status')!r} outside "
                f"{sorted(statuses)}", exit_code=1)
    for rel, rows_key, req in (
            ("relinks/entity_locale.jsonl", "edges",
             ("srcKind", "srcId", "dstId")),
            ("relinks/i2_term_registry.jsonl", "registry", ("termKey",)),
            ("relinks/locale_term_entity.jsonl", "reverse",
             ("termKey", "usages"))):
        for i, row in enumerate(inputs[rows_key]):
            for k in req:
                if k not in row:
                    raise tc.StageError(
                        f"{rel} row {i} misses required key {k!r} "
                        "(core relation schema-invalid)", exit_code=1)
    if not inputs["edges"] or not inputs["registry"]:
        raise tc.StageError(
            "core relations are empty (entity_locale / i2_term_registry)",
            exit_code=1)
    if not inputs["tables"][su.PIVOT]:
        raise tc.StageError("pivot locale table is empty", exit_code=1)


# ---------------------------------------------------------------------------
# Upstream health classification (§S5.3 — THE exit-2 discrimination rule)

def classify_upstream(inputs: dict, drift: Drift) -> tuple[str, list[str]]:
    """Returns (verdict, problem-lines). verdict ∈ steady-state |
    drift-rebased | regression. At the seed buildId every INCLUSIVE bound
    breach is a REAL regression (deterministic reruns reproduce identical
    upstream counts, so any movement is an upstream change); across builds
    bounds REBASE — fresh wins, never a cross-build regression verdict."""
    build_id = inputs["build_id"]
    mx_status = Counter(c["status"] for c in inputs["matrix"]["pairs"])
    measured = {
        "statusCounts.missing": mx_status.get("missing", 0),
        "statusCounts.modeled": mx_status.get("modeled", 0),
        "danglingDistinctGuids":
            int(inputs["guid_report"].get("danglingDistinctGuids") or 0),
        "registryMisses": int(inputs["join_report"].get("registryMisses")
                              or len(inputs["join_report"]
                                     .get("unresolvedIds") or [])),
        "entityLocaleRows": len(inputs["edges"]),
        "registryRows": len(inputs["registry"]),
        "referencedTerms": len({r["termKey"] for r in inputs["reverse"]}),
    }
    for loc in inputs["locales"]:
        measured[f"localeRows.{loc}"] = len(inputs["tables"][loc])

    problems: list[str] = []
    if build_id != SEED_BUILDID:
        for member in sorted(measured):
            if member.startswith("localeRows."):
                continue
            bound = SEEDS["bounds"].get(member)
            seed = bound[1] if isinstance(bound, tuple) else None
            if seed is not None and measured[member] != seed:
                drift.note(
                    f"DRIFT: {member} seed-build {seed} vs measured "
                    f"{measured[member]} (buildId {SEED_BUILDID}->{build_id})"
                    " — bounds rebased, fresh wins")
        for loc in inputs["locales"]:
            lo, hi = SEEDS["bounds"]["localeRowsWindow"]
            v = measured[f"localeRows.{loc}"]
            if v < lo or v > hi:
                drift.note(
                    f"DRIFT: localeRows.{loc} seed-window [{lo}, {hi}] vs "
                    f"measured {v} (buildId moved) — rebased, fresh wins")
        return "drift-rebased", problems

    breached: list[str] = []
    improved: list[str] = []
    for member, (op, bound) in ((m, b) for m, b in SEEDS["bounds"].items()
                                if m != "localeRowsWindow"):
        v = measured[member]
        ok = (v <= bound) if op == "<=" else (v >= bound)
        if not ok:
            breached.append(f"RELINK-REGRESSION: {member} bound{op}{bound} "
                            f"measured{v}")
        elif v != bound:
            improved.append(
                f"DRIFT: {member} improved seed{bound} -> measured{v} — "
                "fresh value becomes the new seed")
    lo, hi = SEEDS["bounds"]["localeRowsWindow"]
    for loc in inputs["locales"]:
        v = measured[f"localeRows.{loc}"]
        if v < lo or v > hi:
            breached.append(
                f"RELINK-REGRESSION: localeRows.{loc} bound[{lo},{hi}] "
                f"measured{v}")
        elif v in (lo, hi):
            improved.append(
                f"DRIFT: localeRows.{loc} sits ON its inclusive bound ({v})")
    problems.extend(breached)
    for line in improved:
        drift.note(line)
    return ("regression" if breached else "steady-state"), problems


# ---------------------------------------------------------------------------
# §S1.4 pending-relink-edge consumption

_PAIR_NAME_RE = re.compile(r"^[a-z][a-z0-9-]*_[a-z][a-z0-9-]*$")


def scan_item_joins(extracted_root: Path, drift: Drift) -> dict:
    """Scan EVERY relinks/<src>_<dst>.jsonl pair file for item->item rows;
    classify evidence.fieldPath == 'GameItem' as variation->Lite edges and
    method `name-convention:*` payloads as definition->_Lite twin edges.
    NEVER derives the edges — counting candidates for the ceiling
    diagnostic is measurement; emitting them is relink's job."""
    variation_refs = 0
    twin_edges = 0
    inheritance: dict[str, str] = {}
    relinks = extracted_root / "relinks"
    pair_files = []
    if relinks.is_dir():
        for p in sorted(relinks.glob("*.jsonl")):
            stem = p.name[:-len(".jsonl")]
            if stem.endswith(".competitor") or stem.startswith("_"):
                continue
            parts = stem.split("_")
            if len(parts) != 2 or not _PAIR_NAME_RE.match(stem):
                continue
            pair_files.append(p)
    scanned_files = 0
    for p in pair_files:
        scanned_files += 1
        for row in load_jsonl(p):
            if row.get("srcKind") != "item" or row.get("dstKind") != "item":
                continue
            ev = row.get("evidence") or {}
            fp = str(ev.get("fieldPath") or "")
            method = str(row.get("method") or "")
            src = str(row.get("srcId"))
            dst = str(row.get("dstId"))
            if fp == "GameItem":
                variation_refs += 1
                inheritance.setdefault(src, dst)
            elif method.startswith("name-convention:") and (
                    dst.endswith("_Lite") or src.endswith("_Lite")):
                twin_edges += 1
                lite = dst if dst.endswith("_Lite") else src
                full = src if dst.endswith("_Lite") else dst
                inheritance.setdefault(full, lite)
    ceilings = SEEDS["joinCeilings"]
    emitted = (variation_refs >= ceilings["variationRefs"]
               and twin_edges >= ceilings["twinEdges"])
    state = "emitted" if emitted else "pending"
    pending = max(0, ceilings["total"] - variation_refs - twin_edges)
    if not emitted:
        drift.note(
            f"DEGRADED-UNIVERSE: item titles short by {pending} of "
            f"{ceilings['total']} — relink emission owed (piece-02 family)")
    return {"state": state, "variationRefs": variation_refs,
            "twinEdges": twin_edges, "pendingJoinCandidates": pending,
            "inheritance": inheritance, "pairFilesScanned": scanned_files}


# ---------------------------------------------------------------------------
# S1 — universe resolution

def collect_universes(inputs: dict, drift: Drift) -> dict:
    """One deterministic pass over the 9 stub files: narrow carriers,
    expanded components on their PINNED bases, and the per-entity fact
    record the doc emitter consumes."""
    tables = inputs["tables"]
    en = tables[su.PIVOT]
    stubs = inputs["stubs"]

    carriers: set[tuple[str, str]] = set()
    literals: dict[str, set[str]] = {k: set() for k in su.KINDS}
    cfg_locname_rows = 0
    title_carrier_rows = 0
    dn_all_instances = 0
    dn_brush_instances = 0
    brush_rows = 0
    room_presence = 0
    room_text = 0
    mt_rows = 0
    mt_resolved = 0
    mt_open_ids: list[str] = []
    descriptive = 0
    bone_strings = 0
    blacklist_hits = 0
    sprite_carriers = 0
    dev_rows = 0

    facts: dict[tuple[str, str], dict] = {}

    for kind in su.KINDS:
        for row in stubs[kind]:
            eid = str(row["id"])
            fields = row.get("fields") if isinstance(
                row.get("fields"), dict) else {}
            rec: dict = {}
            if su.narrow_carrier(kind, fields):
                carriers.add((kind, eid))
            # plain-string Name literal (any kind; top-level name-class)
            nv = fields.get("Name")
            if isinstance(nv, str) and su.clean_text(nv):
                literals[kind].add(eid)
                rec["literal"] = su.clean_text(nv)
            if kind == "config":
                cls = (row.get("source") or {}).get("class") or ""
                walked = su.walk_stub_fields(fields)
                cfg_locname_rows += walked["rootKeys"].get("LocalisedName", 0)
                title_carrier_rows += walked["rootKeys"].get("Title", 0)
                dn_all_instances += walked["rootKeys"].get("DisplayName", 0)
                bone_strings += walked["boneStrings"]
                blacklist_hits += walked["blacklistHits"]
                if cls == "TPC.LandscapeBrushDefinition":
                    brush_rows += 1
                    dn_brush_instances += walked["rootKeys"].get(
                        "DisplayName", 0)
                rec["roots"] = dict(walked["rootKeys"])
            if kind == "room":
                rv = fields.get("Name")
                if su.is_locstr(rv):
                    room_presence += 1
                    if su.locstr_bears_text(rv):
                        room_text += 1
            if kind == "unlockable":
                dv = fields.get("DescriptiveName")
                if isinstance(dv, str) and su.clean_text(dv):
                    descriptive += 1
                dn = fields.get("DisplayName")
                if isinstance(dn, dict) and dn.get("mTerm"):
                    mt_rows += 1
                    key = str(dn["mTerm"])
                    rec["mterm"] = key
                    if en.get(key) and su.clean_text(en[key]):
                        mt_resolved += 1
                    else:
                        mt_open_ids.append(eid)
            icon = fields.get("IconReference")
            if isinstance(icon, dict):
                sub = str(icon.get("m_SubObjectName") or "") or None
                guid = str(icon.get("m_AssetGUID") or "") or None
                if sub:
                    sprite_carriers += 1
                rec["icon"] = {"subObjectName": sub, "guid": guid}
            # name-field facts for the doc emitter
            locstrs = {}
            for p in su.NAME_CLASS_FIELDS[kind]:
                v = fields.get(p)
                if su.is_locstr(v):
                    locstrs[p] = v
            if locstrs:
                rec["locstrs"] = locstrs
            dev = None
            dev_hit = False
            for p in sorted(locstrs):
                # F11 basis: ANY non-empty `_dev` on a §S1.1 member spelling,
                # ROW basis, raw whitespace-strip only (3,874 — localized
                # rows carry their English source as the fallback too).
                d = str(locstrs[p].get("_dev") or "").strip()
                if d:
                    dev_hit = True
                    if dev is None:
                        dev = d
            if dev_hit:
                dev_rows += 1
            if dev:
                rec["dev"] = dev
            if rec:
                facts[(kind, eid)] = rec
            elif kind == "config":
                # config rows can contribute expanded components without
                # any name-field fact (Title/DisplayName presence rows)
                facts.setdefault((kind, eid), {})

    drift.check("stubRows", SEEDS["stubRows"],
                sum(len(v) for v in stubs.values()))
    drift.check("stubRowsPerKind", SEEDS["stubRowsPerKind"],
                {k: len(v) for k, v in sorted(stubs.items())})
    drift.check("plainNameLiterals.perKind",
                SEEDS["plainNameLiterals"]["perKind"],
                {k: len(v) for k, v in sorted(literals.items()) if v})
    drift.check("configLocalisedNameInstances",
                SEEDS["configLocalisedNameInstances"], cfg_locname_rows)
    drift.check("titleCarrierInstances", SEEDS["titleCarrierInstances"],
                title_carrier_rows)
    drift.check("displayNameAllClass", SEEDS["displayNameAllClass"],
                dn_all_instances)
    drift.check("displayNameBrushScoped", SEEDS["displayNameBrushScoped"],
                dn_brush_instances)
    drift.check("roomNamePresence", SEEDS["roomNamePresence"], room_presence)
    drift.check("roomNameTextBearing", SEEDS["roomNameTextBearing"],
                room_text)
    drift.check("unlockableMTermRows", SEEDS["unlockableMTermRows"], mt_rows)
    drift.check("unlockableMTermResolvedEn",
                SEEDS["unlockableMTermResolvedEn"], mt_resolved)
    drift.check("unlockableDescriptiveName",
                SEEDS["unlockableDescriptiveName"], descriptive)
    drift.check("devStringRows", SEEDS["devStringRows"], dev_rows)
    census = {"boneStrings": bone_strings, "blacklistHits": blacklist_hits,
              "spriteNameCarriers": sprite_carriers,
              "devStringRows": dev_rows}
    components = {
        "narrowCarriers": len(carriers),
        "plainStringNameLiterals": {
            "total": sum(len(v) for v in literals.values()),
            "perKind": {k: len(literals[k]) for k in sorted(literals)
                        if literals[k]},
        },
        "configLocalisedNamePresenceInstances": cfg_locname_rows,
        "titleCarrierInstances": title_carrier_rows,
        "configDisplayName": {
            "landscapeBrushScoped": dn_brush_instances,
            "allClassTotal": dn_all_instances,
            "brushRows": brush_rows,
        },
        "roomNameLocstr": {"presence": room_presence, "textBearing": room_text},
        "unlockableMTerm": {"rows": mt_rows, "resolvingInEn": mt_resolved,
                            "openIds": sorted(mt_open_ids)},
        "unlockableDescriptiveNameNonEmpty": descriptive,
        "devStringNameFieldRows": dev_rows,
    }
    return {"carriers": carriers, "literals": literals,
            "components": components, "facts": facts, "census": census}


# ---------------------------------------------------------------------------
# S3 — course resolution + alias volumes

def resolve_courses(inputs: dict, drift: Drift, curated_map: dict | None):
    en = inputs["tables"][su.PIVOT]
    fams = su.build_course_family_index(en)
    fam_counts = {}
    for name, matcher, tail_fn in su.COURSE_FAMILIES:
        fam_counts[name] = sum(1 for k in en
                               if matcher(k) and en[k])
    for name in sorted(fam_counts):
        drift.check(f"courseFamilyCounts[{name}]",
                    SEEDS["courseFamilyCounts"].get(name), fam_counts[name])
    registry_keys = {r["termKey"] for r in inputs["registry"]}
    if curated_map:
        dangling = sorted(cid for cid, row in curated_map.items()
                          if str(row.get("termKey")) not in registry_keys
                          or str(row.get("termKey")) not in en)
        if dangling:
            raise tc.StageError(
                "curated course-alias rows carry dangling termKeys "
                f"{dangling} — bad data is louder than missing data "
                "(spec §S3.3)", exit_code=1)

    courses = inputs["stubs"]["course"]
    defs_ids = [str(r["id"]) for r in courses
                if (r.get("source") or {}).get("class")
                == "TPC.CourseDefinition"]
    marketing_ids = [str(r["id"]) for r in courses
                     if (r.get("source") or {}).get("class")
                     == "TPC.MarketingCourseDefinition"]

    res_no_map = {c: su.resolve_course(c, fams, use_token_map=False)
                  for c in defs_ids}
    res_map = {c: su.resolve_course(c, fams, use_token_map=True)
               for c in defs_ids}
    res_seeded = {c: su.resolve_course(c, fams, use_token_map=True,
                                       curated=curated_map)
                  for c in defs_ids}
    uniform = {}
    for r in courses:
        cid = str(r["id"])
        uniform[cid] = su.resolve_course(cid, fams, use_token_map=True,
                                         curated=curated_map)

    mech_no_map = sum(1 for v in res_no_map.values() if v)
    with_map = sum(1 for v in res_map.values() if v)
    seeded = sum(1 for v in res_seeded.values() if v)
    uni_ok = sorted(c for c, v in uniform.items() if v)
    mk_ok = [c for c in uni_ok if c.startswith("Marketing")]

    # Gates (AC5): seeded >= 24/28 with the seed table present; degraded
    # mechanical floor >= 16/28 when the alias input is ABSENT. Corpus-
    # gated like every pinned figure: a hostless mini fixture measures its
    # own resolution truth, so the bound binds only at the seed buildId.
    if inputs["build_id"] == SEED_BUILDID:
        if curated_map is not None:
            if seeded < 24:
                raise tc.StageError(
                    f"course resolution gate breached: seeded {seeded}/28 "
                    "< 24 (measured 25/28 under the pinned union staging)",
                    exit_code=1)
        elif mech_no_map < 16:
            raise tc.StageError(
                f"degraded mechanical floor breached: {mech_no_map}/28 < 16 "
                "(holds under every tried reading)", exit_code=1)

    drift.check("courseDefsMechanicalNoMap",
                SEEDS["courseDefsMechanicalNoMap"], mech_no_map)
    drift.check("courseDefsWithTokenMap", SEEDS["courseDefsWithTokenMap"],
                with_map)
    drift.check("uniformResolved", SEEDS["uniformResolved"], len(uni_ok))
    drift.check("marketingResolved", SEEDS["marketingResolved"], len(mk_ok))

    open_defs = [c for c in defs_ids if not res_seeded[c]]
    methods = {}
    resolutions = {}
    for r in courses:
        cid = str(r["id"])
        hit = uniform[cid]
        if hit:
            methods[cid] = hit["method"]
            resolutions[cid] = hit
    block = {
        "staging": "union-set (pinned, reviewer F12)",
        "familyCounts": dict(sorted(fam_counts.items())),
        "tokenMap": [{"from": a, "to": b} for a, b in su.COURSE_TOKEN_MAP],
        "courseDefinitions": {
            "defs": len(defs_ids),
            "mechanicalNoMap": mech_no_map,
            "withTokenMap": with_map,
            "withSeedTable": seeded if curated_map is not None else None,
            "open": [{"courseId": c, "reason": drift_note(c)}
                     for c in sorted(open_defs)],
            "gate": ">=24/28 with the seed table; degraded floor >=16/28 "
                    "when the alias input is absent",
        },
        "uniformResolver": {
            "coursesTotal": len(courses),
            "resolved": len(uni_ok),
            "marketingResolved": len(mk_ok),
            "marketingOpen": sorted(set(marketing_ids) - set(mk_ok)),
            "methodsByCourse": dict(sorted(methods.items())),
            "inferredSemantics": "every convention/token-map/curated "
                                 "resolution is inferred:true — never "
                                 "faked to hard",
        },
        "curatedInputPresent": curated_map is not None,
        "curatedRows": len(curated_map or {}),
    }
    return {"block": block, "resolutions": resolutions,
            "defsOpen": sorted(open_defs), "counts": {
                "mechanicalNoMap": mech_no_map, "withMap": with_map,
                "seeded": seeded, "uniform": len(uni_ok),
                "marketing": len(mk_ok)}}


def alias_volumes(inputs: dict, drift: Drift, facts: dict,
                  census: dict) -> dict:
    tok_lo: set[str] = set()
    tok_cs: set[str] = set()
    for kind in su.KINDS:
        for row in inputs["stubs"][kind]:
            parts = [p for p in su.NON_ALNUM_RE.split(str(row["id"]))
                     if len(p) >= 2 and not p.isdigit()]
            tok_lo.update(p.lower() for p in parts)
            tok_cs.update(parts)
    drift.check("idTokens", SEEDS["idTokens"], len(tok_lo))
    drift.check("idTokensCaseSensitiveSuperset",
                SEEDS["idTokensCaseSensitiveSuperset"], len(tok_cs))
    drift.check("caseFoldCollisions", SEEDS["caseFoldCollisions"],
                len(tok_cs) - len(tok_lo))
    dev_rows = int(census.get("devStringRows") or 0)
    mt_total = sum(1 for rec in facts.values() if rec.get("mterm"))
    en = inputs["tables"][su.PIVOT]
    mt_res = sum(1 for rec in facts.values()
                 if rec.get("mterm") and en.get(rec["mterm"])
                 and su.clean_text(en[rec["mterm"]]))
    return {"idTokens": len(tok_lo),
            "idTokensCaseSensitiveSuperset": len(tok_cs),
            "caseFoldCollisions": len(tok_cs) - len(tok_lo),
            "devStrings": dev_rows, "mTermRows": mt_total,
            "mTermResolved": mt_res}


# ---------------------------------------------------------------------------
# S2 — per-locale document shards

def build_name_pools(inputs: dict) -> tuple[dict, int, int, set, int]:
    """Group entity_locale edges per entity into name / variant /
    description pools (pinned path classes).

    The DOC name pool honors the §S2 override (student-type names resolve
    through LocalisedNameF; LocalisedNameM rides as variant), while the
    NARROW TITLE census (titleKeySets.narrow + collision pairs) runs over
    the FULL §S1.1 member sets — the verifier-reproduced 2,993-edge /
    2,059-key triple counts both student-type spellings.

    Returns (pools, cleanedEmptyDropped, narrowEdgeCount, narrowKeySet,
    narrowUnresolvedAtPivot): the drop counter runs over the narrow
    name-class EDGE candidates at the pivot (keys present with raw
    non-empty text that clean to empty — expect 23, F9)."""
    grouped: dict[tuple, list] = defaultdict(list)
    en = inputs["tables"][su.PIVOT]
    dropped = 0
    narrow_edge_count = 0
    narrow_key_set: set[str] = set()
    narrow_unresolved = 0
    for e in inputs["edges"]:
        grouped[(e["srcKind"], str(e["srcId"]))].append(e)
    pools: dict[tuple, dict] = {}
    for key in sorted(grouped):
        kind, eid = key
        edges = grouped[key]
        edges.sort(key=lambda e: (
            str((e.get("evidence") or {}).get("fieldPath") or ""),
            str(e.get("dstId") or "")))
        member_cls = set(su.NAME_CLASS_FIELDS.get(kind, ()))
        name_cls = ({"LocalisedNameF"} if kind == "student-type"
                    else member_cls)
        var_paths = set(su.VARIANT_EDGE_PATHS.get(kind, ()))
        desc_paths = set(su.DESCRIPTION_EDGE_PATHS.get(kind, ()))
        names: list[str] = []
        variants: list[tuple[str, str]] = []
        descs: list[tuple[str, str]] = []
        for e in edges:
            fp = str((e.get("evidence") or {}).get("fieldPath") or "")
            dst = str(e.get("dstId") or "")
            if fp in member_cls:
                # narrow-title census basis (full member set)
                narrow_edge_count += 1
                narrow_key_set.add(dst)
                if not en.get(dst):
                    narrow_unresolved += 1
                raw = en.get(dst)
                if raw is not None and raw and not su.clean_text(raw):
                    dropped += 1
            if fp in name_cls:
                names.append(dst)
            elif fp in var_paths:
                variants.append((fp, dst))
            elif fp in desc_paths:
                descs.append((fp, dst))
        pools[key] = {
            "ownNames": sorted(set(names)),
            "variants": sorted(set(variants)),
            "descs": sorted(set(descs)),
            "inherited": [],
        }
    return pools, dropped, narrow_edge_count, narrow_key_set, \
        narrow_unresolved


def apply_join_inheritance(pools: dict, joins: dict) -> None:
    """Consume the pending relink edges IF emitted (pre-ruling 4): a joined
    item inherits its Lite target's name pool. Pending state adds nothing —
    ledger-degraded, never re-derived from stubs here."""
    if joins["state"] != "emitted":
        return
    for src, lite in sorted(joins["inheritance"].items()):
        target = pools.get(("item", lite))
        if not target:
            continue
        pool = pools.setdefault(("item", src),
                                {"ownNames": [], "variants": [],
                                 "descs": [], "inherited": []})
        merged = sorted(set(pool["inherited"]) | set(target["ownNames"])
                        | set(target["inherited"]))
        pool["inherited"] = [k for k in merged
                             if k not in set(pool["ownNames"])]


def doc_entities(pools: dict, facts: dict, course_resolutions: dict) -> list:
    """Every (kind,id) with ANY possible name path across all locales."""
    ents = set(pools)
    for key, rec in facts.items():
        if rec.get("mterm") or rec.get("literal") or rec.get("dev"):
            ents.add(key)
    for cid in course_resolutions:
        ents.add(("course", cid))
    return sorted(ents)


def resolve_name(key: tuple, rec: dict, pool: dict, table: dict,
                 locale: str, course_resolutions: dict):
    """Name resolution priority (§S2, pinned): localized edge > mTerm >
    plain literal > dev fallback (pivot only) > convention/curated.
    Returns {text, termKey, basis} or None (membership miss in L)."""
    for k in list(pool["ownNames"]) + list(pool["inherited"]):
        t = table.get(k)
        if t and su.clean_text(t):
            return {"text": su.clean_text(t), "termKey": k,
                    "basis": "localized"}
    mt = rec.get("mterm")
    if mt:
        t = table.get(mt)
        if t and su.clean_text(t):
            return {"text": su.clean_text(t), "termKey": mt,
                    "basis": "mterm"}
    if locale == su.PIVOT:
        if rec.get("literal"):
            return {"text": rec["literal"], "termKey": None,
                    "basis": "literal"}
        if rec.get("dev"):
            d = su.clean_text(rec["dev"])
            if d:
                return {"text": d, "termKey": None, "basis": "dev-fallback"}
    res = course_resolutions.get(key[1]) if key[0] == "course" else None
    if res:
        t = table.get(res["termKey"])
        if t and su.clean_text(t):
            basis = ("curated" if str(res["method"]) == "curated"
                     else "convention")
            return {"text": su.clean_text(t), "termKey": res["termKey"],
                    "basis": basis}
    return None


def build_doc(key: tuple, rec: dict, pool: dict, table: dict, locale: str,
              name: dict, build_id: int) -> dict:
    kind, eid = key
    aliases = [{"class": "id-token", "text": t}
               for t in su.id_tokens(eid)]
    for _fp, vk in pool["variants"]:
        t = table.get(vk)
        c = su.clean_text(t) if t else ""
        if c:
            aliases.append({"class": "name-variant", "text": c})
    if locale == su.PIVOT and rec.get("dev") \
            and name["basis"] in ("localized", "mterm"):
        d = su.clean_text(rec["dev"])
        if d:
            aliases.append({"class": "dev-string", "text": d})
    deduped = sorted({(a["class"], a["text"]): a for a in aliases}.values(),
                     key=lambda a: (a["class"], a["text"]))
    descs: dict[str, str] = {}
    for _fp, dk in pool["descs"]:
        t = table.get(dk)
        c = su.clean_text(t) if t else ""
        if c:
            descs[dk] = c
    visibility = "public"
    if kind == "campus-level" and name["text"] in su.VISIBILITY_INTERNAL_ROSTER:
        visibility = "internal"
    icon = rec.get("icon") or {"subObjectName": None, "guid": None}
    doc = {
        "kind": kind,
        "id": eid,
        "slug": None,
        "visibility": visibility,
        "weight": su.KIND_WEIGHTS[kind],
        "name": {"text": name["text"], "termKey": name["termKey"],
                 "basis": name["basis"]},
        "aliases": deduped,
        "descriptions": [{"text": v, "termKey": k}
                         for k, v in sorted(descs.items())],
        "icon": {"subObjectName": icon.get("subObjectName"),
                 "guid": icon.get("guid")},
        "buildId": build_id,
    }
    su.validate_document(doc)
    return doc


def build_shard_payloads(inputs: dict, pools: dict, facts: dict,
                         course_resolutions: dict, joins: dict,
                         drift: Drift) -> dict:
    """Serialize every shard + titles projection IN MEMORY; ratio bands are
    checked BEFORE anything is written (a band breach must leave no
    artifacts). Returns {locale: {"docs": [doc...], "full": str,
    "titles": str}}."""
    ents = doc_entities(pools, facts, course_resolutions)
    payloads: dict[str, dict] = {}
    dev_only_per_kind: Counter = Counter()
    named_entities: set[tuple] = set()
    for locale in inputs["locales"]:
        table = inputs["tables"][locale]
        docs = []
        for key in ents:
            rec = facts.get(key) or {}
            pool = pools.get(key) or {"ownNames": [], "variants": [],
                                      "descs": [], "inherited": []}
            name = resolve_name(key, rec, pool, table, locale,
                                course_resolutions)
            if name is None:
                continue
            docs.append(build_doc(key, rec, pool, table, locale, name,
                                  inputs["build_id"]))
            named_entities.add(key)
            if name["basis"] == "dev-fallback":
                dev_only_per_kind[key[0]] += 1
        docs.sort(key=lambda d: (d["kind"], d["id"]))
        full = "".join(su.serialize_doc(d) + "\n" for d in docs)
        titles = "".join(
            json.dumps({"kind": d["kind"], "id": d["id"],
                        "t": d["name"]["text"]}, ensure_ascii=False,
                       sort_keys=True, separators=(",", ":")) + "\n"
            for d in docs)
        payloads[locale] = {"docs": docs, "full": full, "titles": titles}
    # AC4 gates over each emitter's own denominators
    for locale, p in payloads.items():
        n = len(p["docs"])
        fb = len(p["full"].encode("utf-8"))
        tb = len(p["titles"].encode("utf-8"))
        try:
            su.ratio_band_check(locale, n, fb, tb)
        except ValueError as exc:
            raise tc.StageError(str(exc), exit_code=1)
    # titles derived strictly from the same run's shards, row-for-row
    for locale, p in payloads.items():
        want = [su.serialize_title_row(d) + "\n" for d in p["docs"]]
        got = p["titles"].splitlines(keepends=True)
        if want != got:
            raise tc.StageError(
                f"titles projection for {locale} is not row-for-row "
                "derived from its shard", exit_code=1)
    return {"payloads": payloads, "namedEntities": named_entities,
            "devOnlyPerKind": dict(sorted(dev_only_per_kind.items()))}


# ---------------------------------------------------------------------------
# S4 + S5 assembly

def analyzer_block(inputs: dict, drift: Drift) -> tuple[dict, dict]:
    analyzers = {}
    stats_by_locale = {}
    for loc in inputs["locales"]:
        st = su.analyze_locale_table(inputs["tables"][loc])
        entry = {"tokenizer": su.tokenizer_for(loc), **su.ANALYZER_COMMON,
                 "stats": st}
        analyzers[loc] = entry
        stats_by_locale[loc] = st
    assignments = {loc: analyzers[loc]["tokenizer"]
                   for loc in sorted(analyzers)}
    drift.check("koCjkBearingRows", SEEDS["koCjkBearingRows"],
                stats_by_locale.get("ko", {}).get("cjkBearingRows"))
    for loc in ("en", "tr", "ko"):
        drift.check(f"vocabEndpoints[{loc}]",
                    SEEDS["vocabEndpoints"].get(loc),
                    stats_by_locale.get(loc, {}).get("vocabDistinctTokens"))
    return analyzers, stats_by_locale


def collision_counters(inputs: dict, drift: Drift) -> dict:
    """F9 truth over the title surface: narrow name-class edges PLUS config
    Title/DisplayName (the surface whose distinct-KIND cross-check the
    arbiter pinned at 67). Pair counting uses RAW pivot texts at EDGE
    multiplicity (reproduces 264 / x53 / x51 / 1,895); the ignore-kind
    counter uses the PINNED definition on CLEANED titles (what shards
    actually carry)."""
    en = inputs["tables"][su.PIVOT]
    member: dict[str, set] = {k: set(v)
                              for k, v in su.NAME_CLASS_FIELDS.items()}
    narrow_pairs_raw = []   # collidingPairs / topPairs surface (F9 exact)
    wide_pairs_clean = []   # ignore-kind surface (narrow + Title/DisplayName)

    def add_edge(kind: str, sid: str, dst: str, wide: bool) -> None:
        raw = en.get(dst) or ""
        if not raw.strip():
            return
        c = su.clean_text(raw)
        if wide:
            if c:
                wide_pairs_clean.append((kind, sid, c))
            return
        narrow_pairs_raw.append((kind, sid, raw))

    for e in inputs["edges"]:
        kind = e["srcKind"]
        fp = str((e.get("evidence") or {}).get("fieldPath") or "")
        if fp in member.get(kind, ()):
            add_edge(kind, str(e["srcId"]), str(e["dstId"]), wide=False)
            add_edge(kind, str(e["srcId"]), str(e["dstId"]), wide=True)
        elif kind == "config" and fp in ("Title", "DisplayName"):
            add_edge(kind, str(e["srcId"]), str(e["dstId"]), wide=True)
    dup_texts = {}
    for loc, table in inputs["tables"].items():
        cnt = Counter(v for v in table.values() if v)
        dup_texts[loc] = sum(1 for v in cnt.values() if v > 1)
    block_pair = su.collision_block(narrow_pairs_raw, {})
    block_kind = su.collision_block(wide_pairs_clean, dup_texts)
    block = {
        "collidingPairs": block_pair["collidingPairs"],
        "topPairs": block_pair["topPairs"],
        "ignoreKindCollisions": block_kind["ignoreKindCollisions"],
        "distinctKindTexts": block_kind["distinctKindTexts"],
        "withinLocaleDuplicateTexts":
            block_kind["withinLocaleDuplicateTexts"],
        "countingBasis": "collidingPairs = (kind,title) PAIRS with "
                         "multiplicity >1 over RAW pivot texts; "
                         "ignoreKindCollisions = DISTINCT TITLE TEXTS "
                         "carried by more than one ENTITY ignoring kind "
                         "(arbiter RF-C); distinctKindTexts carried beside",
    }
    seed = SEEDS["collisionSeed"]
    drift.check("collidingPairs", seed["collidingPairs"],
                block["collidingPairs"])
    drift.check("topPairs", seed["topPairs"], block["topPairs"][:2])
    drift.check("ignoreKindCollisions", seed["ignoreKindCollisions"],
                block["ignoreKindCollisions"])
    seeded_dups = {k: v for k, v in block["withinLocaleDuplicateTexts"].items()
                   if k in seed["withinLocaleDuplicateTexts"]}
    drift.check("withinLocaleDuplicateTexts",
                seed["withinLocaleDuplicateTexts"], seeded_dups)
    return block


def load_curated_alias_input(pack_dir: Path) -> dict | None:
    path = pack_dir / "data" / "sources" / "derived" / \
        "course-name-aliases.jsonl"
    if not path.is_file():
        return None
    rows = load_jsonl(path)
    out: dict = {}
    seen_dup = False
    for r in rows:
        cid = str(r.get("courseId"))
        if cid in out:
            seen_dup = True
        out[cid] = r
    if seen_dup:
        raise tc.StageError(
            f"{path.as_posix()} carries duplicate courseId rows — curated "
            "input must be one row per course", exit_code=1)
    for cid, row in out.items():
        if "termKey" not in row or "method" not in row:
            raise tc.StageError(
                f"curated alias row {cid} misses termKey/method "
                f"(row shape {{courseId, termKey, method, inferred:true, "
                "sourceRefs[]}})", exit_code=1)
    return out


def script_hashes(pack_dir: Path) -> dict:
    out = {}
    for dep in SCRIPT_DEPS:
        p = pack_dir / "tools" / dep
        out[dep] = log_util.sha256_file(p) if p.is_file() else "missing"
    return out


def rebuild_trigger(extracted_root: Path, pack_dir: Path,
                    inputs: dict) -> dict:
    mpath = extracted_root / SEARCH_DIR / "manifest.json"
    if not mpath.is_file():
        return {"reason": "first-run"}
    try:
        prev = json.loads(mpath.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"reason": "manifest-unreadable"}
    meta = prev.get("meta") or {}
    prev_stamps = meta.get("sourceStamps") or {}
    cur_stamps = {
        "relinkIdentity": (inputs["relink_stamp"] or {}).get("identity"),
        "localisationIdentity":
            (inputs["localisation_stamp"] or {}).get("identity"),
    }
    if prev_stamps != cur_stamps:
        return {"reason": "source-stamp-changed"}
    if meta.get("buildId") != inputs["build_id"]:
        return {"reason": "build-id-changed"}
    if meta.get("scriptHashes") != script_hashes(pack_dir):
        return {"reason": "script-hash-changed"}
    return {"reason": "unchanged"}


# ---------------------------------------------------------------------------
# Ledger (§S5.4)

def build_ledger(inputs: dict, joins: dict, courses: dict,
                 alias_present: bool, dev_only_per_kind: dict,
                 mt_open_ids: list[str]) -> list[dict]:
    rows: list[dict] = []
    build_id = inputs["build_id"]

    def add(code: str, severity: str, detail: str) -> None:
        rows.append({"code": code, "severity": severity, "detail": detail,
                     "unblock": LEDGER_UNBLOCK.get(code, ""),
                     "buildId": build_id})

    if joins["state"] == "pending":
        add("item-title-joins-absent", "gap",
            f"pending item-title join edges: variationRefs="
            f"{joins['variationRefs']}/{SEEDS['joinCeilings']['variationRefs']}"
            f" twinEdges={joins['twinEdges']}/"
            f"{SEEDS['joinCeilings']['twinEdges']} — "
            f"pendingJoinCandidates={joins['pendingJoinCandidates']} of "
            f"{SEEDS['joinCeilings']['total']}")
    for cid in courses["defsOpen"]:
        add("course-name-open", "gap",
            f"course {cid} unresolved ({drift_note(cid)})")
    if not alias_present:
        add("alias-input-absent", "info",
            "data/sources/derived/course-name-aliases.jsonl absent — "
            "mechanical-only resolution floor applies (>=16/28)")
    if dev_only_per_kind:
        breakdown = "; ".join(f"{k}:{v}" for k, v in
                              sorted(dev_only_per_kind.items()))
        add("dev-only-names", "info",
            f"G4 population ships en-only dev-fallback names [{breakdown}]")
    for eid in sorted(mt_open_ids):
        add("mt-unresolved", "gap",
            f"unlockable {eid} DisplayName.mTerm does not resolve in en")
    internal = len(su.VISIBILITY_INTERNAL_ROSTER)
    add("campus-level-scope", "info",
        f"G8 scope decision applied: {internal} campus-level dev levels "
        "ship visibility:internal; flip by editing the pinned roster list")
    rows.sort(key=lambda r: (r["code"], r["detail"]))
    return rows


# ---------------------------------------------------------------------------
# Manifest + emission

def build_manifest(inputs: dict, locales: list[str], universe: dict,
                   payloads: dict, analyzers: dict, stats: dict,
                   alias_vol: dict, collisions: dict, course_block: dict,
                   joins: dict, trigger: dict, census: dict,
                   narrow_keys: list[str], narrow_edges: int,
                   narrow_unresolved_pivot: int,
                   expanded_walker_keys: set) -> dict:
    tables = inputs["tables"]
    build_id = inputs["build_id"]
    shards = {}
    f14 = {}
    f15 = {}
    for loc in locales:
        p = payloads[loc]
        docs = len(p["docs"])
        fb = len(p["full"].encode("utf-8"))
        tb = len(p["titles"].encode("utf-8"))
        table = tables[loc]
        f14[loc] = sum(len(table[k].encode("utf-8")) for k in narrow_keys
                       if k in table and table[k])
        f15[loc] = sum(
            len(json.dumps({"id": k, "text": table[k]}, ensure_ascii=False,
                           sort_keys=True, separators=(",", ":"))
                .encode("utf-8")) + 1
            for k in narrow_keys if k in table and table[k])
        shards[loc] = {
            "docs": docs,
            "bytes": fb,
            "sha256": log_util.sha256_bytes(p["full"].encode("utf-8")),
            "titlesDocs": docs,
            "titlesBytes": tb,
            "titlesSha256":
                log_util.sha256_bytes(p["titles"].encode("utf-8")),
        }
    ref_keys = {r["termKey"] for r in inputs["reverse"]}
    entity_relevant = 0
    for loc in locales:
        t = tables[loc]
        for k in ref_keys:
            if k in t and t[k]:
                entity_relevant += len(json.dumps(
                    {"id": k, "text": t[k]}, ensure_ascii=False,
                    sort_keys=True, separators=(",", ":")).encode("utf-8")) + 1
    plane_files = sum((inputs["extracted_root"] / f"locales/{loc}.jsonl")
                      .stat().st_size for loc in locales)
    base_overlay = inputs["extracted_root"] / "locales/base-overlay.jsonl"

    max_vocab = max((stats[l]["vocabDistinctTokens"] for l in locales),
                    default=0)
    manifest = {
        "meta": {
            "buildId": build_id,
            "stage": STAGE_ID,
            "scriptDeps": list(SCRIPT_DEPS),
            "scriptHashes": script_hashes(tc.resolve_pack_dir()),
            "sourceStamps": {
                "relinkIdentity": inputs["relink_stamp"].get("identity"),
                "localisationIdentity":
                    inputs["localisation_stamp"].get("identity"),
            },
        },
        "universe": {
            "narrow": universe["narrow"],
            "narrowPerKind": dict(sorted(universe["narrowPerKind"].items())),
            "expanded": universe["expanded"],
            "expandedPerKind": dict(sorted(
                universe["expandedPerKind"].items())),
            "components": universe["components"],
            "planningFloor": {"value": SEEDS["planningFloor"],
                              "share": SEEDS["planningFloorShare"]},
            "planningFloorDelta":
                universe["expanded"] - SEEDS["planningFloor"],
            "planningFloorAttribution":
                "boundary-dependent components: titleCarrierInstances "
                "(presence basis), nested Name strings excluded, room Name "
                "presence basis, unlockable mTerm rows basis, item-title "
                "join state pending, course-convention resolutions",
            "idOnly": universe["idOnly"],
            "idOnlyPerKind": dict(sorted(universe["idOnlyPerKind"].items())),
            "descriptionOnlyNoDoc": dict(sorted(
                universe["descriptionOnlyNoDoc"].items())),
            "joinProjectedCeiling": universe["expanded"]
            + joins["pendingJoinCandidates"],
        },
        "shards": shards,
        "analyzers": analyzers,
        "aliasVolumes": alias_vol,
        "titleKeySets": {
            "narrow": {
                "edges": narrow_edges,
                "keys": len(narrow_keys),
                "enResolvePct": pct(narrow_edges - narrow_unresolved_pivot,
                                    narrow_edges),
                "basis": "distinct term keys over the narrow name-class "
                         "edge set (verifier-reproduced triple)",
            },
            "expandedWalker": {
                "keys": len(expanded_walker_keys),
                "provenance": "UNVERIFIED doc-probe seed 2748 (verifyB saw "
                              "2655 over its superset definition); "
                              "reconciled fresh every run — never "
                              "load-bearing, never asserted (reviewer F10)",
            },
        },
        "sizes": {
            "localePlanesBytes": plane_files,
            "baseOverlayBytes": base_overlay.stat().st_size
            if base_overlay.is_file() else 0,
            "entityRelevantSerializedBytes": entity_relevant,
            "f14TitleTextBytes": f14,
            "f15KeyLineBytes": f15,
            "f16DocPlanes": {
                loc: {"docs": shards[loc]["docs"],
                      "fullBytes": shards[loc]["bytes"],
                      "fullBytesPerDoc": round(shards[loc]["bytes"]
                                               / shards[loc]["docs"], 1)
                      if shards[loc]["docs"] else 0,
                      "titlesBytes": shards[loc]["titlesBytes"],
                      "titlesBytesPerDoc":
                          round(shards[loc]["titlesBytes"]
                                / shards[loc]["titlesDocs"], 1)
                          if shards[loc]["titlesDocs"] else 0}
                for loc in locales},
            "metricLabels": "F14 raw UTF-8 title-text bytes / F15 {id,text} "
                            "JSONL key-line bytes / F16 shipped doc planes "
                            "— three distinct metrics, never mixed",
        },
        "kindWeights": dict(sorted(su.KIND_WEIGHTS.items())),
        "visibilityRoster": {
            "internal": list(su.VISIBILITY_INTERNAL_ROSTER),
            "public": ["All buildings", "Knight Level"],
            "note": "flip by editing one pinned list, never code "
                    "(arbiter-piece08 R3)",
        },
        "collisions": collisions,
        "courseResolution": course_block,
        "typoBudget": {
            "maxVocabObserved": max_vocab,
            "ceilingAssumed": 30000,
            "strategy": "client-side levenshtein-d2",
            "feasibility": "measured",
            "infra": "none-hosted",
            "bigramNote": "zh-Hans/zh-Hant edit distance operates on "
                          "character bigrams of cleaned text; ja mixes "
                          "whitespace runs with bigram fallback",
        },
        "joinState": {
            "state": joins["state"],
            "variationRefs": joins["variationRefs"],
            "twinEdges": joins["twinEdges"],
            "ceilings": dict(sorted(SEEDS["joinCeilings"].items())),
            "pendingJoinCandidates": joins["pendingJoinCandidates"],
            "pairFilesScanned": joins["pairFilesScanned"],
        },
        "excluded": {
            "spriteNameCarriers": census["spriteNameCarriers"],
            "uiChromeTerms": len({r["termKey"] for r in inputs["registry"]})
            - len({r["termKey"] for r in inputs["reverse"]}),
            "bonesIndexed": census["blacklistHits"],
            "flipPath": "icon bytes/CDN paths are the media piece's "
                        "contract; sprite names stay non-alias",
        },
        "rebuildTrigger": trigger,
        "upstreamVerdict": universe["upstreamVerdict"],
        "configBoneStringCensus": census["boneStrings"],
    }
    return manifest


def emit(extracted_root: Path, locales: list[str], payloads: dict,
         ledger_rows: list[dict], manifest: dict) -> tuple[list[str], int]:
    """Temp-file + atomic-rename writes for EVERY declared output. Returns
    (emitted relpaths, manifest bytes)."""
    relpaths: list[str] = []

    def put_text(rel: str, text: str) -> None:
        log_util.atomic_write_text(extracted_root / rel, text)
        relpaths.append(rel)

    for loc in locales:
        put_text(f"{SEARCH_DIR}/shards/{loc}.jsonl",
                 payloads[loc]["full"])
    for loc in locales:
        put_text(f"{SEARCH_DIR}/titles/{loc}.jsonl",
                 payloads[loc]["titles"])
    ledger_text = "".join(
        json.dumps(r, ensure_ascii=False, sort_keys=True,
                   separators=(",", ":")) + "\n"
        for r in ledger_rows)
    put_text(f"{SEARCH_DIR}/_ledger.jsonl", ledger_text)
    manifest_text = log_util.dump_json(manifest)
    put_text(f"{SEARCH_DIR}/manifest.json", manifest_text)

    files = {}
    for rel in sorted(relpaths):
        files[rel] = log_util.sha256_file(extracted_root / rel)
    hashes_rel = f"{SEARCH_DIR}/hashes.json"
    log_util.write_json(extracted_root / hashes_rel, {
        "algorithm": "sha256",
        "buildId": manifest["meta"]["buildId"],
        "excluded": [hashes_rel],
        "files": files,
    })
    return relpaths + [hashes_rel], len(manifest_text.encode("utf-8"))


# ---------------------------------------------------------------------------
# Entrypoint

def seed_assert(build_id, drift: Drift, label: str, measured, seed) -> None:
    """Hard EQUALITY assert at the seed buildId only (AC2/AC5 pins); across
    builds bounds REBASE — DRIFT line, fresh wins."""
    if build_id != SEED_BUILDID:
        drift.check(label, seed, measured)
        return
    if measured != seed:
        raise tc.StageError(
            f"seed assert failed at buildId {build_id}: {label} pinned "
            f"{seed!r} measured {measured!r} (spec §S1.1/§2 — deviation is "
            "an exit-1 validation failure)", exit_code=1)


def run(game_root: Path | None, extracted_root: Path) -> int:
    del game_root  # purely derived stage: opens NO bundles, needs NO game dir
    drift = Drift()
    precheck_inputs(extracted_root)
    inputs = load_inputs(extracted_root, drift)
    inputs["extracted_root"] = extracted_root
    validate_structure(inputs)
    pack_dir = tc.resolve_pack_dir()
    trigger = rebuild_trigger(extracted_root, pack_dir, inputs)

    verdict, problems = classify_upstream(inputs, drift)
    if verdict == "regression":
        # WRITE NOTHING — refusing to overwrite a healthy index with a
        # shrunken one is the anti-masking behavior (§S5.3 rationale).
        for line in problems + drift.lines:
            print(f"[{STAGE_ID}] {line}")
            print(f"[{STAGE_ID}] {line}", file=sys.stderr)
        log_util.append_run_section(
            extracted_root, STAGE_ID,
            ["- exitCode: 1 (failed)"]
            + [f"- PROBLEM: {p}" for p in problems]
            + ["- upstreamVerdict: regression"])
        print(f"[{STAGE_ID}] PROBLEM: upstream regression — artifacts "
              "unwritten", file=sys.stderr)
        return 1

    joins = scan_item_joins(extracted_root, drift)
    uni = collect_universes(inputs, drift)
    # Whitelist guard (§S1.5, F12): a LocalisedString reached under a
    # mesh/bone/material container is defect content, never indexable.
    if uni["census"]["blacklistHits"] != 0:
        raise tc.StageError(
            f"whitelist guard tripped: bonesIndexed="
            f"{uni['census']['blacklistHits']} name-class structs were "
            "reached under a blacklisted structural container "
            "(Bones/Meshes/GeometryList/Materials) — indexing them is a "
            "defect, not content", exit_code=1)
    edges = inputs["edges"]
    a_universe = {(e["srcKind"], str(e["srcId"])) for e in edges}
    seed_assert(inputs["build_id"], drift, "localeEdgePairs",
                len(a_universe), SEEDS["localeEdgePairs"])

    narrow_union = a_universe | uni["carriers"]
    narrow_per_kind = Counter(k for k, _i in narrow_union)
    carriers_per_kind = Counter(k for k, _i in uni["carriers"])
    seed_assert(inputs["build_id"], drift, "universeNarrow",
                len(narrow_union), SEEDS["universeNarrow"])
    seed_assert(inputs["build_id"], drift, "narrowPerKind",
                dict(sorted(narrow_per_kind.items())), SEEDS["narrowPerKind"])
    seed_assert(inputs["build_id"], drift, "carriers",
                len(uni["carriers"]), SEEDS["narrowCarriers"])
    lit_total = uni["components"]["plainStringNameLiterals"]["total"]
    seed_assert(inputs["build_id"], drift, "plainNameLiterals.total",
                lit_total, SEEDS["plainNameLiterals"]["total"])
    seed_assert(inputs["build_id"], drift, "plainNameLiterals.perKind",
                uni["components"]["plainStringNameLiterals"]["perKind"],
                SEEDS["plainNameLiterals"]["perKind"])
    seed_assert(inputs["build_id"], drift, "configLocalisedNameInstances",
                uni["components"]["configLocalisedNamePresenceInstances"],
                SEEDS["configLocalisedNameInstances"])
    seed_assert(inputs["build_id"], drift, "displayNameBrushScoped",
                uni["components"]["configDisplayName"]["landscapeBrushScoped"],
                SEEDS["displayNameBrushScoped"])
    seed_assert(inputs["build_id"], drift, "roomNamePresence",
                uni["components"]["roomNameLocstr"]["presence"],
                SEEDS["roomNamePresence"])
    seed_assert(inputs["build_id"], drift, "roomNameTextBearing",
                uni["components"]["roomNameLocstr"]["textBearing"],
                SEEDS["roomNameTextBearing"])
    seed_assert(inputs["build_id"], drift, "unlockableMTermResolvedEn",
                uni["components"]["unlockableMTerm"]["resolvingInEn"],
                SEEDS["unlockableMTermResolvedEn"])
    seed_assert(inputs["build_id"], drift, "unlockableDescriptiveName",
                uni["components"]["unlockableDescriptiveNameNonEmpty"],
                SEEDS["unlockableDescriptiveName"])

    curated_map = load_curated_alias_input(pack_dir)
    courses = resolve_courses(inputs, drift, curated_map)
    alias_vol = alias_volumes(inputs, drift, uni["facts"], uni["census"])
    seed_assert(inputs["build_id"], drift, "idTokens",
                alias_vol["idTokens"], SEEDS["idTokens"])

    pools, cleaned_empty_dropped, narrow_edge_count, narrow_key_set, \
        narrow_unresolved_pivot = build_name_pools(inputs)
    apply_join_inheritance(pools, joins)
    shard_data = build_shard_payloads(inputs, pools, uni["facts"],
                                      courses["resolutions"], joins, drift)
    drift.check("cleanedEmptyDropped", SEEDS["cleanedEmptyDropped"],
                cleaned_empty_dropped)
    g4 = {k: v for k, v in shard_data["devOnlyPerKind"].items()
          if k in SEEDS["g4DevOnlyNames"]}
    drift.check("g4DevOnlyNames", SEEDS["g4DevOnlyNames"],
                {k: g4.get(k, 0) for k in sorted(SEEDS["g4DevOnlyNames"])})
    payloads = shard_data["payloads"]

    analyzers, stats = analyzer_block(inputs, drift)
    collisions = collision_counters(inputs, drift)

    # expanded universe = conservative union + F7 components on their
    # pinned bases + joins AS EMITTED + course-convention resolutions
    expanded = set(narrow_union)
    expanded |= {(k, i) for k, ids in uni["literals"].items() for i in ids}
    cfg_locname = set()
    title_rows = set()
    dn_brush = set()
    for row in inputs["stubs"]["config"]:
        eid = str(row["id"])
        cls = (row.get("source") or {}).get("class") or ""
        rec = uni["facts"].get(("config", eid)) or {}
        roots = rec.get("roots") or {}
        if roots.get("LocalisedName"):
            cfg_locname.add(eid)
        if roots.get("Title"):
            title_rows.add(eid)
        if roots.get("DisplayName") and \
                cls == "TPC.LandscapeBrushDefinition":
            dn_brush.add(eid)
    expanded |= {("config", e) for e in cfg_locname}
    expanded |= {("config", e) for e in title_rows}
    expanded |= {("config", e) for e in dn_brush}
    for kind, field, tag in (("room", "Name", None),
                             ("unlockable", "DisplayName", "mterm"),
                             ("unlockable", "DescriptiveName", None)):
        got = set()
        for row in inputs["stubs"][kind]:
            fields = row.get("fields") or {}
            v = fields.get(field)
            if tag == "mterm":
                if isinstance(v, dict) and v.get("mTerm"):
                    got.add(str(row["id"]))
            elif field == "Name":
                if su.is_locstr(v):
                    got.add(str(row["id"]))
            else:
                if isinstance(v, str) and su.clean_text(v):
                    got.add(str(row["id"]))
        expanded |= {(kind, e) for e in got}
    if joins["state"] == "emitted":
        expanded |= {("item", s) for s in joins["inheritance"]}
    expanded |= {("course", c) for c in courses["resolutions"]}
    expanded_per_kind = Counter(k for k, _i in expanded)
    named_per_kind = Counter(k for k, _i in shard_data["namedEntities"])
    desc_only = {k: max(0, expanded_per_kind[k] - named_per_kind[k])
                 for k in set(expanded_per_kind) | set(named_per_kind)}
    id_only = set()
    for kind in su.KINDS:
        for row in inputs["stubs"][kind]:
            key = (kind, str(row["id"]))
            if key not in expanded:
                id_only.add(key)
    id_only_per_kind = Counter(k for k, _i in id_only)
    universe_view = {
        "narrow": len(narrow_union),
        "narrowPerKind": dict(narrow_per_kind),
        "expanded": len(expanded),
        "expandedPerKind": dict(expanded_per_kind),
        "idOnly": len(id_only),
        "idOnlyPerKind": dict(id_only_per_kind),
        "descriptionOnlyNoDoc": desc_only,
        "components": uni["components"],
        "facts": uni["facts"],
        "upstreamVerdict": verdict,
    }
    universe_view["components"]["localeEdgePairs"] = len(a_universe)
    pending_sources = sorted(
        s for s in joins.get("inheritance", {})
        if ("item", s) not in expanded)
    universe_view["components"]["itemTitleJoins"] = {
        "variationRefs": joins["variationRefs"],
        "twinEdges": joins["twinEdges"],
        "pendingSourcesNotYetInUniverse": len(pending_sources),
    }
    universe_view["components"]["courseConventionResolutions"] = {
        "coursesResolved": len(courses["resolutions"]),
        "courseDefinitionsResolved": courses["counts"]["seeded"]
        if curated_map is not None else courses["counts"]["withMap"],
    }

    narrow_key_set = set(narrow_key_set)
    seed_assert(inputs["build_id"], drift, "narrowTitleEdges",
                narrow_edge_count, SEEDS["narrowTitleEdges"])
    seed_assert(inputs["build_id"], drift, "narrowTitleKeys",
                len(narrow_key_set), SEEDS["narrowTitleKeys"])

    expanded_walker_keys = set(narrow_key_set)
    for key, pool in pools.items():
        expanded_walker_keys.update(dst for _fp, dst in pool["variants"])
        expanded_walker_keys.update(pool["inherited"])
    for rec in uni["facts"].values():
        if rec.get("mterm"):
            expanded_walker_keys.add(rec["mterm"])
    for res in courses["resolutions"].values():
        expanded_walker_keys.add(res["termKey"])
    drift.check("expandedWalkerKeys", SEEDS["expandedWalkerKeys"],
                len(expanded_walker_keys))

    manifest = build_manifest(
        inputs, inputs["locales"], universe_view, payloads, analyzers,
        stats, alias_vol, collisions, courses["block"], joins, trigger,
        uni["census"], sorted(narrow_key_set), narrow_edge_count,
        narrow_unresolved_pivot, expanded_walker_keys)

    ledger_rows = build_ledger(inputs, joins, courses, curated_map is not None,
                               shard_data["devOnlyPerKind"],
                               uni["components"]["unlockableMTerm"]["openIds"])

    relpaths, manifest_bytes = emit(extracted_root, inputs["locales"],
                                    payloads, ledger_rows, manifest)

    planning_floor_delta = len(expanded) - SEEDS["planningFloor"]
    if planning_floor_delta != 0:
        line = (f"DRIFT: expanded {len(expanded)} vs planning floor "
                f"{SEEDS['planningFloor']} "
                f"({pct(len(expanded), SEEDS['stubRows'])}); delta "
                "attributable to boundary components: titleCarrierInstances"
                f"={uni['components']['titleCarrierInstances']}, "
                "nested Name strings excluded, room Name presence basis, "
                "item-title join state "
                f"{joins['state']}, course-convention resolutions="
                f"{len(courses['resolutions'])}")
        print(f"[{STAGE_ID}] {line}", file=sys.stderr)
        drift.note(line)

    per_locale_docs = {loc: len(payloads[loc]["docs"])
                       for loc in inputs["locales"]}
    run_lines = [
        f"- exitCode: {2 if ledger_rows else 0}",
        "- S1: stubRows={} / universeNarrow={} / universeExpanded={} / "
        "universeComponents={} / planningFloorDelta={} / joinState={} / "
        "variationRefs={} / twinEdges={} / pendingJoinCandidates={} / "
        "idOnlyRemainder={}".format(
            SEEDS["stubRows"] if inputs["build_id"] == SEED_BUILDID
            else sum(len(v) for v in inputs["stubs"].values()),
            len(narrow_union), len(expanded),
            json.dumps(_compact_components(manifest), sort_keys=True,
                       ensure_ascii=False),
            planning_floor_delta, joins["state"], joins["variationRefs"],
            joins["twinEdges"], joins["pendingJoinCandidates"],
            len(id_only)),
        "- S2: docsEmitted={} / perLocaleDocs={} / cleanedEmptyDropped={} / "
        "devOnlyDocs={} / localePureViolations=0 / bonesIndexed={}".format(
            sum(per_locale_docs.values()),
            json.dumps(per_locale_docs, sort_keys=True),
            cleaned_empty_dropped,
            json.dumps(shard_data["devOnlyPerKind"], sort_keys=True),
            uni["census"]["blacklistHits"]),
        "- S3: idTokenVocab={} / devAliases={} / mTermResolved={} / "
        "courseMechanical={} / courseWithSeedTable={} / courseOpen={} / "
        "marketingResolved={} / marketingOpen={} / collisionPairs={}".format(
            alias_vol["idTokens"], alias_vol["devStrings"],
            alias_vol["mTermResolved"], courses["counts"]["mechanicalNoMap"],
            courses["counts"]["seeded"] if curated_map is not None
            else courses["counts"]["withMap"], len(courses["defsOpen"]),
            courses["counts"]["marketing"],
            len(courses["block"]["uniformResolver"]["marketingOpen"]),
            collisions["collidingPairs"]),
        "- S4: analyzerAssignments={} / vocabPerLocale={} / "
        "markupRowsStripped={}".format(
            json.dumps({loc: su.tokenizer_for(loc)
                        for loc in inputs["locales"]}, sort_keys=True),
            json.dumps({loc: stats[loc]["vocabDistinctTokens"]
                        for loc in inputs["locales"]}, sort_keys=True),
            stats[su.PIVOT]["markupTagRows"]
            + stats[su.PIVOT]["placeholderRows"]),
        "- S5: shardFiles={} / manifestBytes={} / hashesCount={} / "
        "ledgerRows={} / rebuildTrigger={} / upstreamVerdict={}".format(
            2 * len(inputs["locales"]), manifest_bytes,
            2 * len(inputs["locales"]) + 2, len(ledger_rows),
            trigger["reason"], verdict),
    ]
    log_util.append_run_section(extracted_root, STAGE_ID, run_lines)

    for line in drift.lines:
        print(f"[{STAGE_ID}] {line}", file=sys.stderr)
    print(f"[{STAGE_ID}] narrow={len(narrow_union)} expanded={len(expanded)} "
          f"idOnly={len(id_only)} joinState={joins['state']} "
          f"(pendingJoinCandidates={joins['pendingJoinCandidates']})")
    print(f"[{STAGE_ID}] docs/locale="
          + json.dumps(per_locale_docs, sort_keys=True))
    print(f"[{STAGE_ID}] courses mech={courses['counts']['mechanicalNoMap']}"
          f"/28 map={courses['counts']['withMap']}/28 seeded="
          f"{courses['counts']['seeded'] if curated_map is not None else 'n/a'}"
          f" uniform={courses['counts']['uniform']}/69 open={len(courses['defsOpen'])}")
    print(f"[{STAGE_ID}] ledger: "
          + ", ".join(f"{c}={sum(1 for r in ledger_rows if r['code'] == c)}"
                      for c in sorted({r["code"] for r in ledger_rows}))
          + f" (rows={len(ledger_rows)})")
    print(f"[{STAGE_ID}] rebuildTrigger={trigger['reason']} "
          f"upstreamVerdict={verdict} files={len(relpaths)}")
    return 2 if ledger_rows else 0


def _compact_components(manifest: dict) -> dict:
    comps = manifest["universe"]["components"]
    keep = {}
    for key in sorted(comps):
        val = comps[key]
        if isinstance(val, dict):
            keep[key] = {k: v for k, v in sorted(val.items())
                         if not isinstance(v, (list, dict))}
        else:
            keep[key] = val
    return keep


def main(argv=None) -> int:
    log_util.bootstrap_console()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("game_dir", nargs="?", default=None,
                        help="ignored: this stage opens no bundles")
    parser.add_argument("--extracted-root", default=None)
    args = parser.parse_args(argv)
    extracted_root = None
    try:
        extracted_root = tc.resolve_extracted_root(tc.resolve_pack_dir())
        if args.extracted_root:
            extracted_root = Path(args.extracted_root).resolve()
        return run(None, extracted_root)
    except tc.StageError as exc:
        try:
            log_util.append_failure_section(
                extracted_root if extracted_root
                else tc.resolve_extracted_root(tc.resolve_pack_dir()),
                STAGE_ID, exc.exit_code, [str(exc)])
        except Exception:  # noqa: BLE001 — logging must not mask the failure
            pass
        print(f"[{STAGE_ID}] ERROR: {exc}", file=sys.stderr)
        return exc.exit_code


if __name__ == "__main__":
    sys.exit(main())
