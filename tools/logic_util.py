#!/usr/bin/env python3
"""Shared machinery for stage 8 — logic (piece-04 contract,
docs/specs/piece-04-logic.mdx Revision 3).

Everything here is a pure, deterministic function of its inputs: the
typed-block walker (the ONE new primitive this piece adds), the registry /
class-hierarchy / harvest-direct loaders, the cross-file PPtr ladder over
the committed bridges (REUSING the piece-02 resolution surface at function
level — no reimplementation), the numeric audit ledger that makes the R4
invention law executable, and the LOGIC.md renderer.

`relink_util` is consumed READ-ONLY: walk_pptr_refs / walk_pptr_leaves,
StubIndex + load_stubs, load_externals / simplify_external_path /
builtin_external, BridgeIndexes.resolve_cab_path/.container_exact/
.container_by_address, bundle_base. Nothing under relinks/ is ever written.

Determinism: sorted enumeration everywhere, no wall-clock inputs, atomic
temp+rename writes via log_util, UTF-8 + LF. Ids stay VERBATIM end to end
(Principle one) — twins keep their `@<contentHash8>` suffix.
"""
from __future__ import annotations

import ast
import json
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import log_util
import relink_util as ru
import tpc_common as tc


class LogicError(tc.StageError):
    pass


KIND_FILES = dict(ru.KIND_FILES)
STUB_KINDS = ru.STUB_KINDS

ABSTRACT_PREREQUISITE = "TPC.Prerequisite"
# Namespaced spelling for ANCESTRY matching; the sidecar's emitted
# interfaceFamily label is the spec's bare spelling (piece-04 §3 L1 sketch:
# interfaceFamily:"ILevelPrerequisiteData").
NONMEMBER_INTERFACE = "TPC.ILevelPrerequisiteData"
NONMEMBER_FAMILY_LABEL = "ILevelPrerequisiteData"

# Expected destination classes of a course-unlock edge (spec L1 step 3).
UNLOCK_DST_CLASSES = ("TPC.CourseLiteDefinition", "TPC.CourseDefinition",
                      "TPC.MarketingCourseDefinition")

# ---------------------------------------------------------------------------
# Scout-time reconciliation seeds (piece-04 §2 F-table). Drift prints a
# DRIFT: line and the fresh number wins — never a silent stale constant.

SEEDS = {
    "stubRowsItem": 3885,            # F1
    "stubRowsUnlockable": 415,
    "stubRowsMetagameNode": 454,
    "stubRowsRoom": 116,
    "stubRowsCourse": 69,
    "stubRowsStudentType": 54,
    "stubRowsCampusLevel": 17,
    "stubRowsStaff": 3,
    "stubRowsConfig": 8430,
    "courseSplitFull": 28,           # F2
    "courseSplitMarketing": 41,
    "moduleSplitPrefix": 312,        # F3
    "moduleSplitUnused": 7,
    "interactions": 630,             # F16
    "prerequisiteInstancesConfigs": 193,   # F4
    "prerequisiteClassHasCourseUnlocked": 50,
    "prerequisiteClassUniversityLevel": 43,
    "prerequisiteClassChallengeHasRoomUnlocked": 18,
    "prerequisiteClassDaysPassed": 17,
    "prerequisiteClassStarsInLevel": 13,
    "nonmemberBlocks": 27,           # F4 sidecar (26 + 1)
    "nonmemberFamilies": 2,
    "unlockEdgeInstances": 50,       # F4/F5/F6
    "termRefs": 75,                  # F12 matrix seed
    "gradeLadderRows": 9,
    "financeConfigs": 30,            # F9
    "researchCostRows": 209,         # F11
    "liteRowsWithoutCosts": 241,
    "kudoshConsumableRewardConfigs": 6,    # F10
    "staffDecayRawRaws": 2,          # F14
    "clubDecayRows": 7,
    "studentTypeStubs": 54,
    "kudoshSinkItem": 1728,          # GameItemLiteDefinition.Kudosh
    "kudoshSinkRoom": 70,            # RoomLiteDefinition.Kudosh
    "kudoshSinkLandscapeBrush": 170, # LandscapeBrushDefinition.Cost
    "kudoshSinkUpgrade": 77,         # GameItemUpgradeDefinition.Cost
    "kudoshSinkCourseLicence": 28,   # CourseDefinition.KudoshCost
    "relinksCoursePPTRRows": 68,     # F6
    "unlockEdgeOverlapWithRelinks": 50,
    "declaredScopeDifference": 18,
}

# The attrition group labels are the four MEASURED Config_Campus field names
# (Rev 2 F4; no stage-invented spellings — an invented label is a defect).
ATTRITION_GROUPS = (
    "StudentDropoutSettings",
    "StaffResignationSettings",
    "StudentFailPercent",
    "StudentUnhappyTuitionFeesThreshold",
)
ATTRITION_CODE_REF = "dump.cs TPC.CharacterEvents.Student"
# Code-derived event spellings (namespace members), cited by codeRef above.
ATTRITION_EVENTS = {
    "StudentDropoutSettings": [
        "TPC.CharacterEvents.Student.Expelled",
        "TPC.CharacterEvents.Student.ExpelledFail",
    ],
    "StaffResignationSettings": [],
    "StudentFailPercent": [],
    "StudentUnhappyTuitionFeesThreshold": [],
}

# Staff ECPCharacterAttributes `_field` → EAttribute registry spelling
# (Rev 2 F8 pin). All identity-cased except _toilet→ToiletComfort.
STAFF_FIELD_TO_ATTRIBUTE = {
    "_drink": "Drink",
    "_energy": "Energy",
    "_food": "Food",
    "_fun": "Fun",
    "_happiness": "Happiness",
    "_health": "Health",
    "_hygiene": "Hygiene",
    "_sober": "Sober",
    "_social": "Social",
    "_toilet": "ToiletComfort",
}

# Student ECPStudent `_field` → emitted attribute spelling (identity-cased).
STUDENT_FIELD_TO_ATTRIBUTE = {
    "_clubNeed": "ClubNeed",
    "_relationship": "Relationship",
    "_selfStudy": "SelfStudy",
}

# Interaction fields copied verbatim as the cooldown/queue surface plus the
# pointer lists whose typed blocks ride `references`.
INTERACTION_VERBATIM_FIELDS = (
    "CooldownInSeconds", "MaxQueue", "QueueWarningThreshold",
    "CharacterModifiers", "CharacterStatusEffects", "Contexts", "Tags",
)


def full_type_spelling(type_dict: dict | None) -> str:
    """{asm,class,ns} → namespaced full spelling (`ns.class`); a bare class
    with no ns passes through. Namespaced matching is the LAW (bare
    'Prerequisite' matches nothing)."""
    t = type_dict or {}
    ns = str(t.get("ns") or "")
    cls = str(t.get("class") or "")
    return f"{ns}.{cls}" if ns else cls


# ---------------------------------------------------------------------------
# L0 loaders

def load_registries(extracted_root: Path, file_names: list[str]) -> dict:
    """id-registries/*.jsonl loader. Rows are stored NAME-SORTED upstream;
    that stored order IS the byte-match contract order (piece-04 AC3) and is
    preserved verbatim here."""
    out: dict[str, list[dict]] = {}
    base = extracted_root / "decompiled" / "structural" / "id-registries"
    for name in sorted(file_names):
        path = base / name
        rows = []
        with open(path, "r", encoding="utf-8", newline="\n") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
        out[name] = rows
    return out


def load_class_hierarchy(extracted_root: Path) -> list[dict]:
    path = extracted_root / "decompiled" / "structural" / "class-hierarchy.jsonl"
    rows = []
    with open(path, "r", encoding="utf-8", newline="\n") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def prerequisite_members(hier_rows: list[dict]) -> list[str]:
    """The taxonomy ENUM: every type whose baseType is the NAMESPACED abstract
    `TPC.Prerequisite`, alphabetically ordered over FULL SPELLINGS (pinned
    member order — index 0 ChallengePrerequisiteAcademicScore, index 10
    PrerequisiteHasCourseUnlocked, index 23 PrerequisiteUniversityLevel).

    Emitted spellings are BARE (`PrerequisiteHasCourseUnlocked`, F4 verbatim);
    selection stays NAMESPACED through :func:`prerequisite_membership`, whose
    namespaced set is guaranteed to biject these bare names."""
    return prerequisite_membership(hier_rows)[0]


def prerequisite_membership(hier_rows: list[dict]) -> tuple[list[str], set[str]]:
    """(bare alphabetical members, namespaced membership set for ancestry
    selection). A bare↔namespaced collision would make the pinned indices
    ambiguous and is a hard error."""
    bare: set[str] = set()
    namespaced: set[str] = set()
    for r in hier_rows:
        if str(r.get("baseType")) == ABSTRACT_PREREQUISITE:
            name = str(r.get("name"))
            ns = str(r.get("namespace") or "")
            bare.add(name)
            namespaced.add(f"{ns}.{name}" if ns else name)
    if len(bare) != len(namespaced):
        raise LogicError(
            "prerequisite taxonomy bare/name-spaced collision — pinned "
            f"alphabetical indices would be ambiguous "
            f"(bare={sorted(bare)[:5]}…)", 1)
    return sorted(bare), namespaced


def nonmember_classes(hier_rows: list[dict]) -> set[str]:
    """Classes declaring `: ILevelPrerequisiteData` — by baseType OR by
    interface membership (measured shape: LevelPrerequisiteStars declares the
    INTERFACE while its baseType stays System.Object)."""
    out = set()
    for r in hier_rows:
        namespaced_name = f"{r.get('namespace')}.{r.get('name')}" \
            if r.get("namespace") else str(r.get("name"))
        if str(r.get("baseType")) == NONMEMBER_INTERFACE \
                or NONMEMBER_INTERFACE in (r.get("interfaces") or []):
            out.add(namespaced_name)
    return out


def short_name_map(members: list[str]) -> dict:
    """shortName → full-spelling map from spec §2 F4, FORWARD DIRECTION ONLY
    (24 pairs — the taxonomy artifact's `shortNameMap` is the F4 map
    verbatim; a bidirectional fold would double the keyset and lose the
    pinned direction). Members absent from this corpus's hierarchy are
    dropped so the emitted map never names a non-member."""
    pairs = {
        "DaysPassed": "PrerequisiteDaysPassed",
        "DaysPassedSinceCourseStart": "PrerequisiteDaysPassedSinceCourseStart",
        "ItemUnlocked": "PrerequisiteItemUnlocked",
        "ItemAvailable": "PrerequisiteItemAvailable",
        "HasResearchProjectUnlocked": "PrerequisiteHasResearchProjectUnlocked",
        "HasCourseUnlocked": "PrerequisiteHasCourseUnlocked",
        "HasLevelDiscovered": "PrerequisiteHasLevelDiscovered",
        "HasStarsInLevel": "PrerequisiteHasStarsInLevel",
        "UniversityLevel": "PrerequisiteUniversityLevel",
        "TimeSinceArrival": "PrerequisiteTimeSinceArrival",
        "HasCourseRunning": "PrerequisiteHasCourseRunning",
        "HaveStudentsOnCampus": "PrerequisiteHaveStudentsOnCampus",
        "HasDefeatedChallengeEvent": "PrerequisiteHasDefeatedChallengeEvent",
        "HasClubLevel": "PrerequisiteHasClubLevel",
        "StaffWithQualification": "PrerequisiteStaffWithQualification",
        "QualificationUnlocked": "PrerequisiteQualificationUnlocked",
        "EventUnlocked": "PrerequisiteEventUnlocked",
        "HasItemInLevel": "PrerequisiteHasItemInLevel",
        "HasCourseAtLevel": "PrerequisiteHasCourseAtLevel",
        "DaysSinceEventRun": "PrerequisiteDaysSinceEventRun",
        "HasUnlockable": "PrerequisiteHasUnlockable",
        "ChallengeHasRoom": "ChallengePrerequisiteHasRoom",
        "ChallengeHasRoomUnlocked": "ChallengePrerequisiteHasRoomUnlocked",
        "ChallengeAcademicScore": "ChallengePrerequisiteAcademicScore",
    }
    return {k: v for k, v in pairs.items() if v in set(members)}


def iter_stub_rows(stubs_dir: Path):
    """(kind, row) for every stub row across the 9 kinds, kind-major then id
    order — the deterministic census walk."""
    for kind in STUB_KINDS:
        path = stubs_dir / KIND_FILES[kind]
        if not path.is_file():
            continue
        with open(path, "r", encoding="utf-8", newline="\n") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                yield kind, json.loads(line)


def load_harvest_family(monobehaviours_root: Path, class_name: str):
    """Harvest-direct loader (ruling R2): every raw dump of one TPC.* family
    across all bundle subdirs, parsed, ordered by path. Returns
    [(relpath, bundle_stem, path_id, payload)]."""
    out = []
    base = monobehaviours_root
    if not base.is_dir():
        return out
    for d in sorted(base.iterdir()):
        fam = d / class_name
        if not fam.is_dir():
            continue
        for p in sorted(fam.glob("*.json")):
            try:
                payload = json.loads(p.read_text(encoding="utf-8"))
            except ValueError:
                continue
            stem, pid = tc.parse_harvest_stem(p.stem) or (None, None)
            rel = p.relative_to(base.parent.parent).as_posix()
            out.append((rel, stem, pid, payload))
    out.sort(key=lambda t: t[0])
    return out


# ---------------------------------------------------------------------------
# THE new primitive — the typed-block walker

def walk_typed_blocks(fields: dict) -> list[dict]:
    """Typed SerializeReference view over one stub row's fields — descends
    into `fields.references[*]`, returning ONE RECORD PER BLOCK:

        {"refKey":    "00000000",
         "fieldPath": "references[00000000].data._course" (block location:
                      the refKey anchor plus every PPtr leaf path it carries),
         "type":      {"asm","class","ns"} verbatim,
         "fullClass": namespaced spelling,
         "data":      block payload verbatim,
         "pptrs":     [{"fieldPath", "m_FileID", "m_PathID"}] under data}

    Plain PPtr walking already REACHES these leaves anonymously (piece-04
    F6); what it cannot produce is the TYPED view — the census, the
    non-member routing and edge semantics all need `data` + `type`. The
    `version` bookkeeping key of the references map is skipped. Blocks sort
    by refKey so walker output round-trips deterministically.
    """
    refs = (fields or {}).get("references")
    if not isinstance(refs, dict):
        return []
    blocks = []
    for ref_key in sorted(k for k in refs if k != "version"):
        block = refs[ref_key]
        if not isinstance(block, dict):
            continue
        data = block.get("data")
        dtype = block.get("type")
        pptrs = []
        # walk_pptr_leaves yields paths relative to its root; the root here
        # IS the block payload, so the typed view prefixes `data.` — matching
        # the F5/F7 trace spelling ("data._course").
        for _leaf_key, raw_path, fid, pid in ru.walk_pptr_leaves(data or {}):
            pptrs.append({"fieldPath": f"data.{ru.normalize_field_path(raw_path)}",
                          "m_FileID": int(fid), "m_PathID": int(pid)})
        pptrs.sort(key=lambda p: (p["fieldPath"], p["m_PathID"]))
        field_path = f"references[{ref_key}]" + "".join(
            "." + p["fieldPath"] for p in pptrs)
        blocks.append({
            "refKey": str(ref_key),
            "fieldPath": field_path,
            "type": dtype if isinstance(dtype, dict) else {},
            "fullClass": full_type_spelling(dtype),
            "data": data if isinstance(data, dict) else {},
            "pptrs": pptrs,
        })
    blocks.sort(key=lambda b: b["refKey"])
    return blocks


_LIST_POINTER_RE = re.compile(r"\[[0-9]+\]")


def attach_list_fields(rows: list[dict], fields: dict) -> None:
    """Fill each census record's `listFields`: the carrier-side LIST fields
    whose `{id: N}` entries point at the block (the F5 indirection:
    Prerequisites=[{id:0}] → references["00000000"]). Deterministic and
    bounded to top-level list-valued fields of the row."""
    pointers_by_id: dict[int, list[str]] = {}
    stack = [("", fields or {})]
    while stack:
        path, node = stack.pop()
        if isinstance(node, dict):
            prefix = f"{path}." if path else ""
            for k, v in node.items():
                stack.append((prefix + k, v))
        elif isinstance(node, list):
            norm = ru.normalize_field_path(path)
            for item in node:
                if isinstance(item, dict) and set(item) == {"id"} \
                        and isinstance(item["id"], int):
                    pointers_by_id.setdefault(item["id"], []).append(norm)
    for rec in rows:
        ids = {int(rec["refKey"], 16)}
        hits = sorted({p for i in ids for p in pointers_by_id.get(i, ())})
        rec["listFields"] = hits


# ---------------------------------------------------------------------------
# Bridge rebuild + the pinned resolution ladder

def roster_bundle_map(roster: list[dict]) -> tuple[dict, dict, list[str]]:
    """(basename→relpath, stem→relpath, collisions). Stub `source.bundle`
    spells BASENAMES while roster/externals/bridges key RELPATHS (F7)."""
    basename_to_rel: dict[str, str] = {}
    collisions: list[str] = []
    for r in roster:
        name = ru.bundle_base(r["relpath"])
        prev = basename_to_rel.setdefault(name, r["relpath"])
        if prev != r["relpath"]:
            collisions.append(name)
    return basename_to_rel, collisions


def rebuild_bridges(extracted_root: Path, basename_to_rel: dict[str, str],
                    build_id) -> ru.BridgeIndexes:
    """Rebuild a real BridgeIndexes from the COMMITTED bridge artifacts
    (relinks/bridges/{cab_index,container_index}.jsonl) — read-only inputs;
    the returned instance exposes the named lookup surface
    (resolve_cab_path / container_exact / container_by_address)."""
    bridges = ru.BridgeIndexes(build_id)
    cab_rows_by_bundle: dict[str, list[dict]] = {}
    with open(extracted_root / "relinks" / "bridges" / "cab_index.jsonl",
              encoding="utf-8", newline="\n") as fh:
        for line in fh:
            if line.strip():
                row = json.loads(line)
                cab_rows_by_bundle.setdefault(str(row["bundle"]), []).append(row)
    cont_rows_by_bundle: dict[str, list[dict]] = {}
    with open(extracted_root / "relinks" / "bridges" / "container_index.jsonl",
              encoding="utf-8", newline="\n") as fh:
        for line in fh:
            if line.strip():
                row = json.loads(line)
                cont_rows_by_bundle.setdefault(str(row["bundle"]), []).append(row)
    for base in sorted(set(cab_rows_by_bundle) | set(cont_rows_by_bundle)):
        rel = basename_to_rel.get(base, base)
        cab_objects = []
        for row in sorted(cab_rows_by_bundle.get(base, []),
                          key=lambda r: str(r["cab"]).lower()):
            objs = [(int(o["pathId"]), str(o["class"]))
                    for o in sorted(row.get("objects") or [],
                                    key=lambda o: int(o["pathId"]))]
            cab_objects.append((str(row["cab"]), objs))
        bridges.add_bundle(rel, cab_objects, [], False)
        # container rows carry no cab column: derive each address's owning
        # serialized file from the just-registered cab tables
        for row in sorted(cont_rows_by_bundle.get(base, []),
                          key=lambda r: str(r["address"])):
            pid = row.get("pathId")
            pid = None if pid is None or int(pid) < 0 else int(pid)
            cab = bridges.cab_of(rel, pid) if pid is not None else ""
            ci = None
            tbl = bridges.cabs.get((rel, cab))
            if tbl is not None and pid is not None:
                ci = tbl.class_of(pid)
            bridges.container[(rel, str(row["address"]))] = (cab, pid, ci)
            bridges.address_multi.setdefault(str(row["address"]), []).append(
                (rel, cab, pid, ci))
    return bridges


def resolve_typed_pptr(src_bundle: str, src_path_id: int, ext_file_id: int,
                       path_id: int, ctx: dict, want_classes=()) -> dict:
    """The pinned unlock-edge ladder (piece-04 L1 steps 1–4):

      0. source side — basename→roster relpath normalization (bundle_base);
      1. fileId == 0 → same-file leg through the stub index;
      2. externals table of the source's own serialized file
         (load_externals keys) — built-ins detected with builtin_external,
         on-disk DOUBLED paths simplified with simplify_external_path
         (MANDATORY — unsimplified strings match no cab_index cab);
      3. candidates from BridgeIndexes.resolve_cab_path, surviving iff the
         stub index holds the (bundle, pathId) — twins WITH suffix;
      4. multiple survivors disambiguate by destination-class membership,
         then stay ambiguous (gap) — never a silent pick.

    Returns a structured outcome; every failure mode names its cause.
    """
    rel = ctx["basename_to_rel"].get(ru.bundle_base(src_bundle))
    if rel is None:
        return {"status": "unresolved",
                "reason": f"source bundle '{src_bundle}' is not in the roster"}
    stubs = ctx["stubs"]
    if int(ext_file_id) == 0:
        hit = stubs.at(rel, int(path_id))
        if hit is not None:
            return {"status": "resolved", "sameFile": True, "kind": hit[0],
                    "id": hit[1], "dstBundle": rel, "dstCab": "",
                    "extFileId": 0}
        return {"status": "unresolved",
                "reason": "same-file pathId is not an emitted stub entity"}
    bridges = ctx["bridges"]
    src_cab = bridges.cab_of(rel, int(src_path_id))
    exts = ctx["externals"].get((rel, src_cab)) if src_cab is not None else None
    if exts is None:
        return {"status": "unresolved",
                "reason": "owning serialized file unknown for the source "
                          f"object ({src_cab})"}
    ext_path = exts.get(int(ext_file_id))
    if ext_path is None:
        return {"status": "unresolved",
                "reason": f"external fileId {ext_file_id} is not in the "
                          "serialized file's externals table"}
    if ru.builtin_external(ext_path):
        return {"status": "builtin", "extPath": str(ext_path),
                "reason": f"built-in external is not an entity target: "
                          f"{ext_path}"}
    cab = ru.simplify_external_path(ext_path)
    homes = bridges.resolve_cab_path(cab, int(path_id))
    survivors = []
    for b, _home_cab in homes:
        hit = stubs.at(b, int(path_id))
        if hit is not None:
            survivors.append((b, hit[0], hit[1]))
    if len(survivors) > 1:
        classes = ctx["class_by_stub"]
        byclass = [s for s in survivors
                   if classes.get((s[1], s[2])) in set(want_classes)]
        if len(byclass) == 1:
            survivors = byclass
    if len(survivors) > 1:
        return {"status": "ambiguous",
                "candidates": sorted((b, k, i) for b, k, i in survivors),
                "dstCab": cab}
    if not survivors:
        return {"status": "unresolved", "reason": "pathId-not-a-stub-entity",
                "dstCab": cab, "homes": sorted({b for b, _ in homes})}
    b, k, i = survivors[0]
    return {"status": "resolved", "sameFile": False, "kind": k, "id": i,
            "dstBundle": b, "dstCab": cab, "extFileId": int(ext_file_id)}


# ---------------------------------------------------------------------------
# Numeric audit ledger (L5 pass 1 — R4 made executable)

_POINTER_PART_RE = re.compile(r"([^.\[\]]+)|\[([^\]]*)\]")


def pointer_get(obj, pointer: str):
    """'fields.Levels[3].PointsCost' / 'references[00000000].data._amount'
    → value, or raise KeyError. Bracket segments index LISTS numerically
    and DICTS by their literal key (`references["00000000"]` shape carries
    hex-string keys). Pure syntax walk — no semantics."""
    cur = obj
    for part in re.findall(_POINTER_PART_RE, pointer):
        key, idx = part
        if key:
            if not isinstance(cur, dict) or key not in cur:
                raise KeyError(pointer)
            cur = cur[key]
        else:
            if isinstance(cur, list):
                i = int(idx)
                if i >= len(cur):
                    raise KeyError(pointer)
                cur = cur[i]
            elif isinstance(cur, dict):
                if idx not in cur:
                    raise KeyError(pointer)
                cur = cur[idx]
            else:
                raise KeyError(pointer)
    return cur


def _numbers_equal(a, b) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    if isinstance(a, int) and isinstance(b, int):
        return a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        fa, fb = float(a), float(b)
        if math.isnan(fa) and math.isnan(fb):
            return True
        return fa == fb and math.copysign(1.0, fa) == math.copysign(1.0, fb)
    return a == b


class NumericAudit:
    """Every emitted numeric leaf must sit in exactly one audited route:

      copied               — cited (sourceArtifact, sourcePath); the guard
                             RE-READS the source and demands a match
                             (float-exact / integer-exact);
      derived-arithmetic   — labeled `method:"derived-arithmetic:<expr>"`
                             with cited inputs; the guard RECOMPUTES from
                             the cited inputs (non-recomputable ⇒ failure);
      reconstructed-from-code — a labeled block (label + buildId checked);
      explicit-null        — absent-with-ledger representations.

    A numeric leaf found in an emitted artifact but absent from this ledger
    is UNCITED → invention-guard failure naming artifact + path.
    """

    def __init__(self, build_id):
        self.build_id = build_id
        self.copied: dict[tuple[str, str], dict] = {}
        self.derived: dict[tuple[str, str], dict] = {}
        self.code_blocks: dict[str, dict] = {}   # artifact → block descriptor

    # -- registration --------------------------------------------------------

    def copy(self, artifact: str, pointer: str, value, source_artifact: str,
             source_path: str) -> None:
        self.copied[(artifact, pointer)] = {
            "sourceArtifact": source_artifact, "sourcePath": source_path}
        del value

    def copy_tree(self, artifact: str, base_pointer: str, dst_obj,
                  src_obj, source_artifact: str, src_base: str) -> None:
        """Register EVERY numeric leaf of a verbatim-copied subtree. Key
        names are identical on both sides (verbatim copy), so relative
        paths transfer one-to-one; lists keep their indexes. Pointer syntax
        matches the scan side exactly: `a/b` between levels, `[i]` never —
        list indexes join with `/` too."""
        stack = [(base_pointer, dst_obj, src_base, src_obj)]
        while stack:
            dpath, dnode, spath, snode = stack.pop()
            if isinstance(dnode, dict):
                prefix_d = f"{dpath}/" if dpath else ""
                prefix_s = f"{spath}/" if spath else ""
                for k, v in dnode.items():
                    stack.append((prefix_d + str(k), v, prefix_s + str(k),
                                  snode.get(k) if isinstance(snode, dict)
                                  else None))
            elif isinstance(dnode, list):
                for i, v in enumerate(dnode):
                    stack.append((f"{dpath}/{i}", v, f"{spath}/{i}",
                                  snode[i] if isinstance(snode, list)
                                  and i < len(snode) else None))
            elif isinstance(dnode, bool) or dnode is None:
                continue
            elif isinstance(dnode, (int, float)):
                self.copy(artifact, dpath, dnode, source_artifact, spath)

    def derive(self, artifact: str, pointer: str, expr: str,
               inputs: list[dict], recompute) -> None:
        """inputs: [{"sourceArtifact","sourcePath"}…]; recompute(values)
        → expected value. The guard reloads every input fresh and demands
        equality — mis-derived numbers cannot launder through."""
        self.derived[(artifact, pointer)] = {
            "method": f"derived-arithmetic:{expr}",
            "expr": expr, "inputs": inputs, "recompute": recompute}

    def label_code_block(self, artifact: str, block_pointer_prefix: str,
                         description: str) -> None:
        self.code_blocks[artifact] = {
            "pointerPrefix": block_pointer_prefix, "description": description}

    # -- execution ------------------------------------------------------------

    @staticmethod
    def _iter_leaves(obj, root: str):
        stack = [(root, obj)]
        while stack:
            path, node = stack.pop()
            if isinstance(node, dict):
                prefix = f"{path}/" if path else ""
                for k in sorted(node, key=str):
                    stack.append((f"{prefix}{k}", node[k]))
            elif isinstance(node, list):
                for i, v in enumerate(node):
                    stack.append((f"{path}/{i}" if path else str(i), v))
            else:
                yield path, node

    def audit_artifact(self, artifact: str, doc, source_loader) -> dict:
        """Audit ONE emitted artifact (a parsed single-object document or a
        LIST of JSONL rows). Emitted-pointer form mirrors registration:
        `<rowIndex>/field/…` for JSONL, `field/…` for single objects.
        source_loader(sourceArtifact) → parsed source document (cached by
        the caller). Returns bucket counters + failure rows."""
        copied = derived = code = nulls = 0
        failures = []
        block = self.code_blocks.get(artifact)
        rows = doc if isinstance(doc, list) else [doc]
        leaves = []
        for ri, row in enumerate(rows):
            root = str(ri) if isinstance(doc, list) else ""
            for path, value in self._iter_leaves(row, root):
                leaves.append((path, value))

        seen = set()
        for pointer, value in leaves:
            key = (artifact, pointer)
            if key in seen:
                continue
            seen.add(key)
            if value is None:
                nulls += 1
                continue
            if isinstance(value, bool):
                continue
            if not isinstance(value, (int, float)):
                continue
            if key in self.derived:
                d = self.derived[key]
                try:
                    values = []
                    for inp in d["inputs"]:
                        src = source_loader(inp["sourceArtifact"])
                        values.append(pointer_get(src, inp["sourcePath"]))
                    expected = d["recompute"](values)
                    if not _numbers_equal(expected, value):
                        failures.append(
                            f"{artifact}:/{pointer} derived-arithmetic:"
                            f"{d['expr']} recomputes to {expected!r}, "
                            f"emitted {value!r}")
                    else:
                        derived += 1
                except Exception as exc:  # noqa: BLE001 — non-recomputable
                    failures.append(
                        f"{artifact}:/{pointer} derived-arithmetic:"
                        f"{d['expr']} not recomputable from cited inputs "
                        f"({type(exc).__name__}: {exc})")
                continue
            if key in self.copied:
                c = self.copied[key]
                try:
                    src = source_loader(c["sourceArtifact"])
                    src_value = pointer_get(src, c["sourcePath"])
                except Exception as exc:  # noqa: BLE001
                    failures.append(
                        f"{artifact}:/{pointer} citation unreadable "
                        f"({c['sourceArtifact']}#{c['sourcePath']}: {exc})")
                    continue
                if not _numbers_equal(src_value, value):
                    failures.append(
                        f"{artifact}:/{pointer} copied value {value!r} != "
                        f"cited {c['sourceArtifact']}#{c['sourcePath']} "
                        f"value {src_value!r}")
                    continue
                copied += 1
                continue
            if block is not None and pointer.startswith(block["pointerPrefix"]):
                code += 1
                continue
            failures.append(f"{artifact}:/{pointer} numeric leaf is UNCITED "
                            f"(no copied citation, no labeled hatch)")
        return {"copied": copied, "derivedArithmetic": derived,
                "reconstructedFromCode": code, "explicitNull": nulls,
                "failures": failures}


_DERIVED_EXPR_ALLOWED_BINOPS = (ast.Add, ast.Sub, ast.Mult, ast.Div,
                                ast.FloorDiv, ast.Mod, ast.Pow)


def _eval_derived_expr(expr: str, env: dict):
    """Recompute a `derived-arithmetic:<expr>` label from its cited inputs.

    Supports arithmetic over dotted/subscripted names rooted in `env`
    (`inputs.a + inputs.b`). Anything else — calls, attributes outside the
    environment, comparison chains — raises ValueError, which the guard
    reports as non-recomputable: a label that cannot be recomputed cannot
    launder an invented number.
    """

    def ev(node):
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.BinOp) and \
                isinstance(node.op, _DERIVED_EXPR_ALLOWED_BINOPS):
            left, right = ev(node.left), ev(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                return left / right
            if isinstance(node.op, ast.FloorDiv):
                return left // right
            if isinstance(node.op, ast.Mod):
                return left % right
            return left ** right
        if isinstance(node, ast.UnaryOp) and \
                isinstance(node.op, (ast.UAdd, ast.USub)):
            v = ev(node.operand)
            return v if isinstance(node.op, ast.UAdd) else -v
        if isinstance(node, ast.Constant) and \
                isinstance(node.value, (int, float)) and \
                not isinstance(node.value, bool):
            return node.value
        if isinstance(node, ast.Name):
            if node.id in env:
                return env[node.id]
            raise ValueError(f"name {node.id!r} is not a cited input")
        if isinstance(node, ast.Attribute):
            base = ev(node.value)
            key = node.attr
            if isinstance(base, dict) and key in base:
                return base[key]
            raise ValueError(f"'{key}' is not a cited input")
        if isinstance(node, ast.Subscript):
            base, idx = ev(node.value), ev(node.slice)
            if isinstance(base, (dict, list)):
                try:
                    return base[idx]
                except (KeyError, IndexError, TypeError) as exc:
                    raise ValueError(str(exc))
        raise ValueError(f"unsupported expression node "
                         f"{type(node).__name__}")

    tree = ast.parse(expr, mode="eval")
    return ev(tree)


def run_invention_guard(doc, extracted_root=None) -> dict:
    """Routing-level AC7 audit of ONE parsed emitted document (unit surface;
    the disk byte-match lives in :meth:`NumericAudit.audit_artifact`).

    Every numeric leaf must sit in exactly one audited route:

      copied               — the row cites a source identity
                             (`evidence.source`/`sourceArtifact`);
      derived-arithmetic   — the row carries
                             `method:"derived-arithmetic:<expr>"` with cited
                             inputs; the expression is RECOMPUTED from those
                             inputs and must match the emitted value;
      reconstructed-from-code — the row is labeled
                             `provenance:"reconstructed-from-code"`;
      explicit-null        — null absent-with-ledger representations.

    A numeric satisfying NONE of these routes is UNCITED → failure naming
    artifact path; a derived label that does not recompute → failure (the
    label-laundering route closes here too).
    """
    del extracted_root   # routing audit: no disk re-read at this level
    failures: list[str] = []
    buckets = {"copied": 0, "derivedArithmetic": 0,
               "reconstructedFromCode": 0, "explicitNull": 0}
    rows = doc if isinstance(doc, list) else [doc]
    for ri, row in enumerate(rows):
        prefix = f"{ri}/" if isinstance(doc, list) else ""
        if not isinstance(row, dict):
            continue
        method = str(row.get("method") or "")
        ev = row.get("evidence") if isinstance(row.get("evidence"), dict) \
            else {}
        cited = bool(ev.get("source") or ev.get("sourceArtifact")
                     or ev.get("stubRow") or ev.get("rawDump"))
        labeled_code = row.get("provenance") == "reconstructed-from-code"
        if method.startswith("derived-arithmetic:"):
            expr = method.split(":", 1)[1].strip()
            inputs = ev.get("inputs")
            emitted = row.get("value", row.get("amount"))
            try:
                expected = _eval_derived_expr(expr,
                                              {"inputs": inputs})
            except Exception as exc:  # noqa: BLE001 — non-recomputable
                failures.append(
                    f"{prefix or './'}value derived-arithmetic:{expr} not "
                    f"recomputable from cited inputs "
                    f"({type(exc).__name__}: {exc})")
                continue
            if not _numbers_equal(expected, emitted):
                failures.append(
                    f"{prefix or './'}value derived-arithmetic:{expr} "
                    f"recomputes to {expected!r}, emitted {emitted!r}")
                continue
            buckets["derivedArithmetic"] += 1
            continue
        for sub, value in _numeric_leaves(row, ("evidence", "inputs")):
            if value is None:
                buckets["explicitNull"] += 1
                continue
            if labeled_code:
                buckets["reconstructedFromCode"] += 1
                continue
            if cited:
                buckets["copied"] += 1
                continue
            failures.append(f"{prefix}{sub} numeric leaf is UNCITED "
                            f"(no copied citation, no labeled hatch)")
    out = dict(buckets)
    out["failures"] = failures
    return out


def _numeric_leaves(obj, skip_subtrees: tuple[str, ...] = ()):
    """(relative path, value) for every numeric leaf, NOT descending into
    the named bookkeeping subtrees (citations/inputs are anchors, not
    emissions)."""
    stack = [("", obj)]
    while stack:
        path, node = stack.pop()
        if isinstance(node, dict):
            prefix = f"{path}/" if path else ""
            for k, v in node.items():
                if not path and k in skip_subtrees:
                    continue
                stack.append((prefix + str(k), v))
        elif isinstance(node, list):
            for i, v in enumerate(node):
                stack.append((f"{path}/{i}" if path else str(i), v))
        elif node is None:
            yield path, node
        elif isinstance(node, bool):
            continue
        elif isinstance(node, (int, float)):
            yield path, node


def load_source_document(extracted_root: Path, source_artifact: str):
    """source-loader for the audit: 'stubs/<kind>.jsonl#<id>' |
    'decompiled/structural/id-registries/<file>.jsonl#<name>' |
    '<repo-relative .json path>' | 'identity.json'."""
    cache = getattr(load_source_document, "_cache", None)
    if cache is None:
        cache = load_source_document._cache = {}
    if source_artifact in cache:
        return cache[source_artifact]
    if "#" in source_artifact:
        path_part, key = source_artifact.rsplit("#", 1)
        path = extracted_root / path_part
        if path.suffix == ".jsonl":
            for line in open(path, "r", encoding="utf-8", newline="\n"):
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                if str(row.get("id", row.get("name"))) == key:
                    cache[source_artifact] = row
                    return row
            raise KeyError(f"{source_artifact}: keyed row not found")
        doc = json.loads(path.read_text(encoding="utf-8"))
        cache[source_artifact] = doc
        return doc
    path = extracted_root / source_artifact
    doc = json.loads(path.read_text(encoding="utf-8"))
    cache[source_artifact] = doc
    return doc


# ---------------------------------------------------------------------------
# Gap ledger (L5 pass 2)

GAP_KINDS = ("unresolved-pptr", "missing-carrier", "ambiguous-target",
             "builtin-target", "relinks-divergence")


def make_gap_row(family: str, kind: str, subject_id: str, reason: str,
                 unblock: str, build_id) -> dict:
    if kind not in GAP_KINDS:
        raise LogicError(f"gap kind '{kind}' outside the frozen enum", 1)
    return {"gapId": f"{family}:{kind}:{subject_id}", "family": family,
            "kind": kind, "subjectId": subject_id, "reason": reason,
            "unblock": unblock, "buildId": build_id}


def finalize_gaps(rows: list[dict]) -> list[dict]:
    rows.sort(key=lambda r: (r["family"], r["gapId"]))
    seen = set()
    out = []
    for r in rows:
        if r["gapId"] in seen:
            continue
        seen.add(r["gapId"])
        out.append(r)
    return out


# ---------------------------------------------------------------------------
# LOGIC.md renderer (L6)

def render_logic_md(build_id, input_inventory, families, unproven_register,
                    gap_rows, drift_lines, counters) -> str:
    """Fixed section order, deterministic markdown: two builds byte-equal."""
    lines = [
        "# LOGIC — gameplay logic reconstructed from client data",
        "",
        f"- buildId: {build_id}",
        "- stage: `logic` (canonical index 8) — sole writer of everything "
        "under `extracted/logic/`",
        "- generated mechanically by `tools/stage8_logic.py`; reruns are "
        "byte-identical",
        "",
        "## Input inventory",
        "",
        "| artifact | bytes |",
        "|---|---|",
    ]
    for rel, size in input_inventory:
        lines.append(f"| `{rel}` | {size} |")
    lines += ["", "## Datasets", ""]
    for family in families:
        lines.append(f"### {family['title']}")
        lines.append("")
        lines.append("| artifact | rows | join keys | seed vs measured |")
        lines.append("|---|---|---|---|")
        for t in family["tables"]:
            seed = t["seed"]
            measured = t["measured"]
            comparable = isinstance(seed, int) and isinstance(measured, int)
            mark = "" if (not comparable or seed == measured) else " **DRIFT**"
            lines.append(f"| `{t['artifact']}` | {measured} | "
                         f"{t['joinKeys']} | {seed} → {measured}{mark} |")
        for note in family.get("notes", []):
            lines.append(f"- {note}")
        lines.append("")
    lines += ["## UNPROVEN-NATIVE register", ""]
    for u in unproven_register:
        lines.append(f"- **{u['id']}** — {u['text']}")
    lines += [
        "",
        "Native-analysis deferral (orchestrator ruling R3): deferred, not "
        "cancelled — the single known trigger case is the XP→score "
        "normalization above; a site piece genuinely needing a "
        "code-computed constant reopens it.",
        "",
        "## Gap ledger",
        "",
    ]
    by_family: dict[str, int] = {}
    for g in gap_rows:
        by_family[g["family"]] = by_family.get(g["family"], 0) + 1
    lines.append(f"- rows: {len(gap_rows)} "
                 f"({', '.join(f'{k}: {v}' for k, v in sorted(by_family.items()))}"
                 " — see `_gaps.jsonl`)" if gap_rows else "- rows: 0")
    for g in gap_rows:
        lines.append(f"- `{g['gapId']}` — {g['reason']} Unblock: "
                     f"{g['unblock']}")
    lines += [
        "",
        "## Reconstruction-labeling law",
        "",
        "- Every emitted number is copied-and-matching under citation OR "
        "sits in one of three labeled hatches: "
        "`provenance:\"reconstructed-from-code\"` blocks, "
        "`method:\"derived-arithmetic:<expr>\"` aggregates recomputed by "
        "the stage's invention guard from their cited inputs, or explicit "
        "null absent-with-ledger rows.",
        "- Invented numbers are a launch-gate failure; the guard exits 1 "
        "naming artifact + path.",
        "- Coverage counter (NOT a gap row): student decay raw coverage "
        f"{counters.get('studentDecayRawCoverage')} — prefab-side student "
        "definitions were never harvested (arbiter-piece04-spec Part 2/R4); "
        "the core-11 null ledger covers the same absence once.",
    ]
    if drift_lines:
        lines += ["", "## Drift notes (fresh measurement wins)", ""]
        for d in drift_lines:
            lines.append(f"- {d}")
    return "\n".join(lines) + "\n"
