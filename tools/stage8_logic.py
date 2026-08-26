#!/usr/bin/env python3
"""Stage 8 — logic (piece-04, Revision 3).

Derives gameplay logic reconstructed from client data into
`extracted/logic/`, from committed artifacts only — the stage opens ZERO
asset bundles and needs NO game dir:

  L0 load & index   stub index, registries, harvest-direct loaders,
                    typed-block walker; F-table drift probes fire here
  L1 course         courses / modules / prerequisites census +
                    prerequisite-nonmembers sidecar / course-unlock edges
                    (externals→CAB→pathId resolver) + MANDATORY relinks
                    reconciliation leg / attrition triggers
  L2 economy        money taxonomy (28 BudgetTypes byte-matched), finance
                    configs, kudosh sources/sinks, research costs (209)
  L3 grading        EGrade ∞ Config_UISprite.Grades[9] ladder, per-term
                    PassGrade, assessment scoring, XP→score UNPROVEN-NATIVE
                    marker
  L4 needs & decay  staff ECPCharacterAttributes, student ECPStudent
                    (harvest-direct), core-11 absent-carrier ledger,
                    InteractionDefinition family
  L5 guard + gaps   invention guard (R4 executable: every numeric leaf
                    cited or labeled; derived arithmetic RECOMPUTED from its
                    cited inputs) + unified gap ledger
  L6 rollup         LOGIC.md (byte-stable) + sha256 digest map

Exit codes (piece-1 contract): 0 all families populated AND gap ledger
empty · 2 completed-with-ledger — the EXPECTED steady state until the
deferred native piece closes the two standing gaps · 1 schema/validation/
invention-guard failure · 3 missing upstream artifacts.

Audit-registration discipline: rows are built together with their CITATIONS
(logical sub-paths), and numeric citations are registered only AFTER the
rows reach their final emitted order — emitted-pointer form is
`<rowIndex>/<subpath>` and must match the guard's disk scan exactly.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import log_util
import logic_util as lu
import relink_util as ru
import tpc_common as tc

STAGE_ID = "logic"
LOGIC_DIR = "logic"

REGISTRY_FILES = (
    "TPS.Game.BudgetType.jsonl",
    "TPS.Game.TPC.EAttribute.jsonl",
    "TPS.Game.TPC.EGrade.jsonl",
    "TPS.Game.TPC.EStaffStat.jsonl",
)

HARVEST_COURSE_DIR = "harvest/monobehaviours/configs/TPC.CourseDefinition"
HARVEST_STUDENT_DIR = "harvest/monobehaviours/configs/TPC.StudentDefinition"

ECON_KEYS = [
    ("LicenseCost", "licenseCost"),
    ("KudoshCost", "kudoshCost"),
    ("YearlyTuitionFee", "yearlyTuitionFee"),
    ("StartPointsCost", "startPointsCost"),
    ("DefaultStudentCount", "defaultStudentCount"),
    ("ApplicantsBoost", "applicantsBoost"),
    ("ApplicantsFromCourseRating", "applicantsFromCourseRating"),
    ("ApplicantsFromUniversityRating", "applicantsFromUniversityRating"),
]
LEVEL_KEYS = [
    ("PointsCost", "pointsCost"),
    ("ApplicantsBoost", "applicantsBoost"),
    ("LearningRatePercentBoost", "learningRatePercentBoost"),
    ("HiringTeacherSkillLevelMax", "hiringTeacherSkillLevelMax"),
    ("TrainingTeacherSkillLevelMax", "trainingTeacherSkillLevelMax"),
]
SCORING_KEYS = [
    ("BonusPointsPerLevel", "bonusPointsPerLevel"),
    ("ExpectedAverageXPPerSecond", "expectedAverageXPPerSecond"),
    ("PowerFactor", "powerFactor"),
    ("UseTimeFactors", "useTimeFactors"),
    ("TimeInMedicalConsultationFactor", "timeInMedicalConsultationFactor"),
    ("TimeOnCourseFactor", "timeOnCourseFactor"),
]

NEED_RE = re.compile(r"(?i)(need|satisfy)")


def cite_leaves(dst_obj, src_obj):
    """Relative (subpath, SOURCE value) pairs for every numeric leaf of a
    verbatim-copied subtree (identical key names both sides)."""
    out = []
    stack = [("", dst_obj, src_obj)]
    while stack:
        dpath, dnode, snode = stack.pop()
        if isinstance(dnode, dict):
            prefix = f"{dpath}/" if dpath else ""
            for k, v in dnode.items():
                stack.append((prefix + str(k), v,
                              snode.get(k) if isinstance(snode, dict)
                              else None))
        elif isinstance(dnode, list):
            for i, v in enumerate(dnode):
                child = f"{dpath}/{i}" if dpath else str(i)
                stack.append((child, v,
                              snode[i] if isinstance(snode, list)
                              and i < len(snode) else None))
        elif isinstance(dnode, bool) or dnode is None:
            continue
        elif isinstance(dnode, (int, float)):
            out.append((dpath, snode))
    return out


def _src_path(base: str, sub: str) -> str:
    """Emitted pointers join EVERYTHING with '/'; the SOURCE document walk
    (pointer_get) wants `[i]` brackets for list segments. Both sides carry
    identical key NAMES, so the relative path converts mechanically."""
    base = base.rstrip("./")
    if not sub:
        return base
    out = []
    for seg in sub.split("/"):
        out.append(f"[{seg}]" if seg.isdigit() else f".{seg}")
    return base + "".join(out)


class Cites:
    """Per-row citation buffer: (logical subpath, value, sourceArtifact,
    sourcePath). Flushed into the NumericAudit after final row order."""

    def __init__(self):
        self.per_row: list[list[tuple]] = []

    def row(self) -> list[tuple]:
        holder: list[tuple] = []
        self.per_row.append(holder)
        return holder

    def tree(self, holder, dst_obj, src_obj, source_artifact, src_base,
             prefix: str = ""):
        """Register every numeric leaf of a verbatim-copied subtree.
        `prefix` is the ROW-RELATIVE path of the subtree root (the row-key
        chain between the row root and dst_obj); `src_base` is the SOURCE
        document path of that same root."""
        for sub, sval in cite_leaves(dst_obj, src_obj):
            full = f"{prefix}{sub}"
            holder.append((full, sval, source_artifact,
                           _src_path(src_base, sub)))

    def flush(self, audit, artifact: str, rows: list[dict]) -> None:
        if len(self.per_row) != len(rows):
            raise tc.StageError(
                f"citation buffer misaligned for {artifact}: "
                f"{len(self.per_row)} buffers vs {len(rows)} rows",
                exit_code=1)
        for i, holder in enumerate(self.per_row):
            for sub, value, sa, sp in holder:
                audit.copy(artifact, f"{i}/{sub}", value, sa, sp)

    def drop_tail(self, n: int) -> None:
        del self.per_row[len(self.per_row) - n:]


class Pass:
    def __init__(self):
        self.L0: dict = {}
        self.L1: dict = {}
        self.L2: dict = {}
        self.L3: dict = {}
        self.L4: dict = {}
        self.L5: dict = {}
        self.L6: dict = {}
        self.drift_probes: dict[str, dict] = {}


def check_probe(p: Pass, drift: list[str], name: str, expected, measured) \
        -> None:
    p.drift_probes[name] = {"expected": expected, "measured": measured}
    if measured != expected:
        drift.append(f"DRIFT: {name} measures {measured} against seed "
                     f"{expected} — fresh number wins")


# ---------------------------------------------------------------------------
# L0 — load & index

def run_l0(extracted_root: Path, p: Pass, drift: list[str]) -> dict:
    identity = json.loads(
        (extracted_root / "identity.json").read_text(encoding="utf-8"))
    build_id = identity["buildId"]

    roster = tc.load_roster(extracted_root)
    basename_to_rel, collisions = lu.roster_bundle_map(roster)
    if collisions:
        raise tc.StageError(
            "roster bundle basenames collide — bundle-keyed joins ambiguous: "
            f"{sorted(set(collisions))[:5]}", exit_code=1)

    stubs = ru.load_stubs(extracted_root / "stubs",
                          bundle_map=basename_to_rel)
    registries = lu.load_registries(extracted_root, list(REGISTRY_FILES))
    hier = lu.load_class_hierarchy(extracted_root)
    members = lu.prerequisite_members(hier)
    if members != sorted(members) or len(set(members)) != len(members):
        raise tc.StageError(
            "prerequisite taxonomy is not a distinct alphabetically-ordered "
            f"set: {members}", exit_code=1)
    nonmembers = lu.nonmember_classes(hier)
    externals = ru.load_externals(extracted_root / "harvest" / "externals.jsonl")
    bridges = lu.rebuild_bridges(extracted_root, basename_to_rel, build_id)

    class_by_stub: dict[tuple[str, str], str] = {}
    for kind in lu.STUB_KINDS:
        for row in stubs.rows_by_kind[kind]:
            cls = str((row.get("source") or {}).get("class") or "")
            if cls:
                class_by_stub[(kind, str(row["id"]))] = cls

    ctx = {
        "identity": identity, "build_id": build_id,
        "basename_to_rel": basename_to_rel, "stubs": stubs,
        "registries": registries, "hier": hier, "members": members,
        "nonmembers": nonmembers, "externals": externals,
        "bridges": bridges, "class_by_stub": class_by_stub,
        "_extracted_root": extracted_root,
    }

    seed_for_kind = {
        "item": "stubRowsItem", "unlockable": "stubRowsUnlockable",
        "room": "stubRowsRoom", "campus-level": "stubRowsCampusLevel",
        "course": "stubRowsCourse", "config": "stubRowsConfig",
        "staff": "stubRowsStaff", "metagame-node": "stubRowsMetagameNode",
        "student-type": "stubRowsStudentType"}
    for kind in lu.STUB_KINDS:
        check_probe(p, drift, f"stubRows[{kind}]",
                    lu.SEEDS[seed_for_kind[kind]],
                    len(stubs.rows_by_kind[kind]))

    p.L0 = {
        "stubsLoaded": sum(len(stubs.rows_by_kind[k]) for k in lu.STUB_KINDS),
        "stubIndexEntries": len(stubs.by_location),
        "registriesLoaded": len(registries),
        "driftProbes": p.drift_probes,
    }
    return ctx


# ---------------------------------------------------------------------------
# shared resolution seam

def resolve_field_ptr(ctx: dict, src: dict, ptr) -> tuple[dict, dict | None]:
    """Resolve one `{m_FileID, m_PathID}` payload slot. Returns
    ({kind,id,resolved}, outcome). Zero-targets are null slots, never gaps;
    genuine resolution failures come back as outcome for gap routing."""
    if not (isinstance(ptr, dict) and "m_PathID" in ptr):
        return {"kind": None, "id": None, "resolved": False}, None
    fid, pid = int(ptr.get("m_FileID", 0)), int(ptr.get("m_PathID", 0))
    if fid == 0 and pid == 0:
        return {"kind": None, "id": None, "resolved": False}, None
    out = lu.resolve_typed_pptr(ru.bundle_base(str(src.get("bundle"))),
                                int(src.get("pathId")), fid, pid, ctx)
    if out["status"] == "resolved":
        return {"kind": out["kind"], "id": out["id"], "resolved": True}, out
    return {"kind": None, "id": None, "resolved": False}, out


# ---------------------------------------------------------------------------
# L1 — courses

def run_l1_courses(ctx: dict, p: Pass, drift: list[str],
                   audit: lu.NumericAudit, out_dir: Path,
                   problems: list[str]):
    build_id = ctx["build_id"]
    stubs = ctx["stubs"]
    artifact = "logic/course-progression/courses.jsonl"
    monobehaviours = ctx["_extracted_root"] / "harvest" / "monobehaviours"
    raws = lu.load_harvest_family(monobehaviours, "TPC.CourseDefinition")
    raw_by_pid = {}
    scoring_hits = 0
    for rel, stem, pid, payload in raws:
        del stem
        raw_by_pid[pid] = (rel, payload)
        if isinstance(payload.get("_assessmentScoring"), dict):
            scoring_hits += 1

    course_rows = sorted(stubs.rows_by_kind["course"], key=lambda r: r["id"])
    rows: list[dict] = []
    cites = Cites()
    full = marketing = other_class_rows = 0
    for row in course_rows:
        holder = cites.row()
        rid = str(row["id"])
        cls = str((row.get("source") or {}).get("class"))
        src = row.get("source") or {}
        stem = ru.bundle_base(str(src.get("bundle")))
        stem = stem[:-len(".bundle")] if stem.endswith(".bundle") else stem
        pid = int(src.get("pathId"))
        raw_hit = raw_by_pid.get(pid)
        raw = raw_hit[1] if raw_hit else None
        raw_dump_rel = f"{HARVEST_COURSE_DIR}/{stem}_{pid}.json"
        f = row.get("fields") or {}

        if cls == "TPC.CourseDefinition":
            full += 1
            doc: dict = {"id": rid, "class": cls}
            for raw_key, out_key in ECON_KEYS:
                val = f.get(raw_key)
                doc[out_key] = val
                if val is not None:
                    holder.append((out_key, val, f"stubs/courses.jsonl#{rid}",
                                   f"fields.{raw_key}"))
                if raw is not None and raw.get(raw_key) != val:
                    problems.append(
                        f"courses.jsonl:{rid} economics mismatch stub-vs-raw "
                        f"for {raw_key}: {val!r} != {raw.get(raw_key)!r}")
            levels_raw = f.get("Levels") or []
            if raw is not None and (raw.get("Levels") or []) != levels_raw:
                problems.append(
                    f"courses.jsonl:{rid} Levels[] mismatch stub-vs-raw")
            levels_out = []
            for li, lv in enumerate(levels_raw):
                entry = {}
                for raw_key, out_key in LEVEL_KEYS:
                    val = lv.get(raw_key)
                    entry[out_key] = val
                    if val is not None:
                        holder.append((f"levels/{li}/{out_key}", val,
                                       f"stubs/courses.jsonl#{rid}",
                                       f"fields.Levels[{li}].{raw_key}"))
                levels_out.append(entry)
            doc["levels"] = levels_out
            doc["terms"] = _emit_course_terms(ctx, row, holder)
            scoring = None
            archetypes = None
            if raw is not None:
                raw_scoring = raw.get("_assessmentScoring")
                if isinstance(raw_scoring, dict):
                    scoring = {}
                    for raw_key, out_key in SCORING_KEYS:
                        val = raw_scoring.get(raw_key)
                        scoring[out_key] = val
                        if val is not None:
                            holder.append((
                                f"assessmentScoring/{out_key}", val,
                                raw_dump_rel,
                                f"_assessmentScoring.{raw_key}"))
                arch_in = raw.get("_studentArchetypes") or []
                archetypes = []
                for ai, sa_rec in enumerate(arch_in):
                    aptr = sa_rec.get("Archetype") or {}
                    resolved, _out = resolve_field_ptr(ctx, src, aptr)
                    w = sa_rec.get("Weight")
                    if w is not None:
                        holder.append((
                            f"studentArchetypes/{ai}/weight", w,
                            raw_dump_rel,
                            f"_studentArchetypes[{ai}].Weight"))
                    archetypes.append({"weight": w,
                                       "archetype": resolved["id"]})
            doc["assessmentScoring"] = scoring
            doc["studentArchetypes"] = archetypes
            doc["marketingFor"] = None
        elif cls == "TPC.MarketingCourseDefinition":
            marketing += 1
            doc = {"id": rid, "class": cls}
            for _raw_key, out_key in ECON_KEYS:
                doc[out_key] = None          # emptiness is DATA, not fill-in
            doc.update({"levels": None, "terms": None,
                        "assessmentScoring": None,
                        "studentArchetypes": None,
                        "marketingFor": _marketing_link_target(ctx, row)})
        else:
            other_class_rows += 1
            drift.append(
                f"DRIFT: courses.jsonl row {rid} carries new source class "
                f"{cls} — emitted with null economics (fresh wins)")
            doc = {"id": rid, "class": cls}
            for _raw_key, out_key in ECON_KEYS:
                doc[out_key] = None
            doc.update({"levels": None, "terms": None,
                        "assessmentScoring": None,
                        "studentArchetypes": None,
                        "marketingFor": _marketing_link_target(ctx, row)})
        doc["evidence"] = {"stubRow": f"stubs/courses.jsonl#{rid}",
                           "rawDump": raw_dump_rel if raw else None}
        doc["buildId"] = build_id
        holder.append(("buildId", build_id, "identity.json", "buildId"))
        rows.append(doc)

    cites.flush(audit, artifact, rows)
    _register_term_derivations(ctx, audit, artifact, rows)
    check_probe(p, drift, "courseSplitFull", lu.SEEDS["courseSplitFull"],
                full)
    check_probe(p, drift, "courseSplitMarketing",
                lu.SEEDS["courseSplitMarketing"], marketing)
    if len(rows) != full + marketing + other_class_rows:
        raise tc.StageError(
            f"courses.jsonl arithmetic broken: {len(rows)} rows != "
            f"{full} full + {marketing} marketing + "
            f"{other_class_rows} new-class", exit_code=1)
    p.L1.update({"courseRowsFull": full, "courseRowsMarketing": marketing,
                 "courseRowsNewClass": other_class_rows,
                 "assessmentScoringRawHits": scoring_hits})
    log_util.write_jsonl(out_dir / "courses.jsonl", rows)
    return rows


def _emit_course_terms(ctx: dict, course_row: dict, holder: list[tuple]) \
        -> list[dict]:
    """Terms[] PPtr resolution. TermDefinition.PassGrade is `public int` in
    code and measures 40 on every row — OUTSIDE the EGrade domain — so
    `passGrade` carries a member name ONLY for in-domain values and
    `passGradeValue` preserves the verbatim int (a name mapping would be an
    invented rule, R4)."""
    stubs = ctx["stubs"]
    grade_by_value = {int(r["value"]): str(r["name"]) for r in
                      ctx["registries"]["TPS.Game.TPC.EGrade.jsonl"]}
    src = course_row.get("source") or {}
    rid = str(course_row["id"])
    terms_raw = (course_row.get("fields") or {}).get("Terms") or []
    out_terms = []
    for i, tptr in enumerate(terms_raw):
        resolved, _outcome = resolve_field_ptr(ctx, src, tptr)
        term_id = None
        pass_value = None
        weight = None
        module_count = None
        if resolved["resolved"]:
            term_row = next((r for r in stubs.rows_by_kind[resolved["kind"]]
                             if r["id"] == resolved["id"]), None)
            if term_row is not None:
                term_id = str(term_row["id"])
                tf = term_row.get("fields") or {}
                pass_value = tf.get("PassGrade")
                weight = tf.get("Weight")
                mods = tf.get("Modules")
                if isinstance(mods, list):
                    module_count = len(mods)
        idx = len(out_terms)
        if pass_value is not None:
            holder.append((f"terms/{idx}/passGradeValue", pass_value,
                           f"stubs/{lu.KIND_FILES['config']}#{term_id}",
                           "fields.PassGrade"))
        if weight is not None:
            holder.append((f"terms/{idx}/weight", weight,
                           f"stubs/{lu.KIND_FILES['config']}#{term_id}",
                           "fields.Weight"))
        out_terms.append({
            "index": i,
            "termId": term_id,
            "passGrade": grade_by_value.get(pass_value)
            if isinstance(pass_value, int) else None,
            "passGradeValue": pass_value,
            "weight": weight,
            "moduleCount": module_count,
        })
    return out_terms


def _register_term_derivations(ctx: dict, audit, artifact: str,
                               rows: list[dict]) -> None:
    """Per-term derived-arithmetic registrations (post-order, aligned):
    `index` is the array position inside the course's Terms[]; moduleCount
    is len(TermDefinition.Modules[]) — the guard RECOMPUTES both from the
    cited inputs rather than trusting the emitted value."""
    del ctx
    for i, row in enumerate(rows):
        terms = row.get("terms") or []
        for ti, term in enumerate(terms):
            audit.derive(
                artifact, f"{i}/terms/{ti}/index", "index-in-array(Terms[])",
                [{"sourceArtifact": f"stubs/courses.jsonl#{row['id']}",
                  "sourcePath": "fields.Terms"}],
                lambda vals, _ti=ti: (_ti if isinstance(vals[0], list)
                                      and _ti < len(vals[0]) else -1))
            if term.get("moduleCount") is None:
                continue
            audit.derive(
                artifact, f"{i}/terms/{ti}/moduleCount",
                "len(TermDefinition.Modules[])",
                [{"sourceArtifact":
                  f"stubs/{lu.KIND_FILES['config']}#{term['termId']}",
                  "sourcePath": "fields.Modules"}],
                lambda vals: len(vals[0]))


def _marketing_link_target(ctx: dict, row: dict):
    """The marketing variant's link target where the payload carries one —
    PPtr-resolved, else null."""
    fields = row.get("fields") or {}
    src = row.get("source") or {}
    for key in ("Course", "CourseDefinition", "_course"):
        ptr = fields.get(key)
        if isinstance(ptr, dict) and "m_PathID" in ptr:
            resolved, _out = resolve_field_ptr(ctx, src, ptr)
            if resolved["resolved"]:
                return resolved["id"]
    return None


# ---------------------------------------------------------------------------
# L1 — modules

def run_l1_modules(ctx: dict, p: Pass, drift: list[str],
                   audit: lu.NumericAudit, out_dir: Path, gaps: list[dict]):
    build_id = ctx["build_id"]
    artifact = "logic/course-progression/modules.jsonl"
    mods = sorted((r for r in ctx["stubs"].rows_by_kind["config"]
                   if str((r.get("source") or {}).get("class"))
                   == "TPC.CourseModuleDefinition"),
                  key=lambda r: r["id"])
    reward_order = ["AA", "A", "BB", "B", "CC", "C", "D", "F"]
    rows: list[dict] = []
    cites = Cites()
    split = Counter()
    room_resolved = room_unresolved = qual_resolved = qual_unresolved = 0
    graphs_resolved = 0
    for row in mods:
        holder = cites.row()
        rid = str(row["id"])
        split["Unused_Module_*" if rid.startswith("Unused_Module_")
              else "Module_*"] += 1
        src = row.get("source") or {}
        f = row.get("fields") or {}
        blocks = lu.walk_typed_blocks(f)
        lu.attach_list_fields(blocks, f)

        def res(field_name):
            return resolve_field_ptr(ctx, src, f.get(field_name))

        room, room_out = res("RoomType")
        qual, _q = res("Qualification")
        if room["resolved"]:
            room_resolved += 1
        elif room_out is not None:
            room_unresolved += 1
            gaps.append(lu.make_gap_row(
                "course-progression", "unresolved-pptr", rid,
                f"RoomType target unresolved: {room_out.get('reason')}",
                "grow bridges/externals coverage and re-run", build_id))
        if qual["resolved"]:
            qual_resolved += 1
        elif qual_out_check(qual, f):
            qual_unresolved += 1

        gmr_src = f.get("GradeMoneyRewards") or {}
        gmr = {}
        for k in reward_order:
            gmr[k] = gmr_src.get(k)
        cites.tree(holder, gmr, gmr_src, f"stubs/configs.jsonl#{rid}",
                   "fields.GradeMoneyRewards.", prefix="gradeMoneyRewards/")

        doc = {"id": rid, "roomType": room,
               "qualification": {"kind": qual["kind"], "id": qual["id"],
                                 "resolved": qual["resolved"]},
               "gradeMoneyRewards": gmr}
        for raw_key, out_key in (("ClassSize", "classSize"),
                                 ("Duration", "duration"),
                                 ("XPMultiplier", "xpMultiplier")):
            val = f.get(raw_key)
            doc[out_key] = val
            if val is not None:
                holder.append((out_key, val, f"stubs/configs.jsonl#{rid}",
                               f"fields.{raw_key}"))
        gs, _ = res("GraphStudent")
        gt, _ = res("GraphTeacher")
        gsp, _ = res("GraphSpectator")
        bk, _ = res("BackupCourseModule")
        graphs_resolved += sum(1 for g in (gs, gt, gsp) if g["resolved"])
        doc.update({"graphStudent": gs["id"], "graphTeacher": gt["id"],
                    "graphSpectator": gsp["id"],
                    "backupCourseModule": bk["id"]})
        modifier_blocks = [b for b in blocks
                           if any(lf.endswith("Modifiers")
                                  for lf in (b.get("listFields") or []))]
        modifiers = [{"refKey": b["refKey"], "type": dict(b["type"]),
                      "data": json.loads(json.dumps(b["data"]))}
                     for b in modifier_blocks]
        for mi, (mb, b) in enumerate(zip(modifiers, modifier_blocks)):
            cites.tree(holder, mb["data"], b["data"],
                       f"stubs/configs.jsonl#{rid}",
                       f"fields.references[{b['refKey']}].data.",
                       prefix=f"modifiers/{mi}/data/")
        doc["modifiers"] = modifiers
        holder.append(("evidence/srcPathId", int(src.get("pathId")),
                       f"stubs/configs.jsonl#{rid}", "source.pathId"))
        doc["evidence"] = {
            "fieldPaths": ["RoomType", "Qualification", "GradeMoneyRewards",
                           "ClassSize", "Duration", "XPMultiplier"],
            "srcBundle": ru.bundle_base(str(src.get("bundle"))),
            "srcPathId": int(src.get("pathId")),
        }
        doc["buildId"] = build_id
        holder.append(("buildId", build_id, "identity.json", "buildId"))
        rows.append(doc)

    cites.flush(audit, artifact, rows)
    check_probe(p, drift, "moduleSplitPrefix", lu.SEEDS["moduleSplitPrefix"],
                split["Module_*"])
    check_probe(p, drift, "moduleSplitUnused", lu.SEEDS["moduleSplitUnused"],
                split["Unused_Module_*"])
    if len(rows) != sum(split.values()):
        raise tc.StageError(
            f"modules.jsonl arithmetic broken: {len(rows)} rows != prefix "
            f"split {dict(split)}", exit_code=1)
    p.L1.update({
        "moduleRows": len(rows),
        "modulePrefixSplit": {"Module_*": split["Module_*"],
                              "Unused_Module_*": split["Unused_Module_*"]},
        "moduleRoomResolved": room_resolved,
        "moduleRoomUnresolved": room_unresolved,
        "moduleQualificationResolved": qual_resolved,
        "moduleQualificationUnresolved": qual_unresolved,
        "aiGraphsResolvedModules": graphs_resolved,
    })
    log_util.write_jsonl(out_dir / "modules.jsonl", rows)
    return rows


def qual_out_check(resolved: dict, fields: dict) -> bool:
    """True when the Qualification slot is a NON-null target that failed to
    resolve (null slots are data, not gaps)."""
    ptr = fields.get("Qualification")
    if not (isinstance(ptr, dict) and "m_PathID" in ptr):
        return False
    return not (int(ptr.get("m_FileID", 0)) == 0
                and int(ptr.get("m_PathID", 0)) == 0) \
        and not resolved["resolved"]


# ---------------------------------------------------------------------------
# L1 — typed-block census + prerequisites/nonmembers/taxonomy

def census_typed_blocks(stubs_dir: Path) -> list[dict]:
    records = []
    for kind, row in lu.iter_stub_rows(stubs_dir):
        fields = row.get("fields") or {}
        blocks = lu.walk_typed_blocks(fields)
        if not blocks:
            continue
        lu.attach_list_fields(blocks, fields)
        src = row.get("source") or {}
        for b in blocks:
            rec = dict(b)
            rec["carrierKind"] = kind
            rec["carrierId"] = str(row["id"])
            rec["carrierClass"] = str(src.get("class"))
            rec["carrierBundle"] = str(src.get("bundle"))
            rec["carrierPathId"] = int(src.get("pathId"))
            records.append(rec)
    return records


def run_l1_prerequisites(ctx: dict, p: Pass, drift: list[str],
                         audit: lu.NumericAudit, out_dir: Path,
                         records: list[dict], gaps: list[dict]):
    build_id = ctx["build_id"]
    members = ctx["members"]

    member_records = [r for r in records
                      if r["fullClass"] in set(members)]
    configs_members = [r for r in member_records if r["carrierKind"] == "config"]
    nm_classes = ctx["nonmembers"]      # NAMESPACED spellings
    nonmember_records = [r for r in records if r["fullClass"] in nm_classes]

    # --- taxonomy artifact ---------------------------------------------------
    tax_artifact = "logic/course-progression/prerequisite-taxonomy.json"
    shortmap = lu.short_name_map(members)
    taxonomy = {
        "abstract": lu.ABSTRACT_PREREQUISITE,
        "members": list(members),
        "selection": "ancestry: class-hierarchy.baseType == "
                     "'TPC.Prerequisite'",
        "shortNameMap": {k: shortmap[k] for k in sorted(shortmap)},
        "source": "class-hierarchy.jsonl + dump.cs census",
        "provenance": "hard-read",
        "buildId": build_id,
    }
    audit.copy(tax_artifact, "buildId", build_id, "identity.json", "buildId")
    log_util.write_json(out_dir / "prerequisite-taxonomy.json", taxonomy)

    # --- prerequisites.jsonl -------------------------------------------------
    art = "logic/course-progression/prerequisites.jsonl"
    rows: list[dict] = []
    cites = Cites()
    for rec in sorted(member_records, key=lambda r: (r["carrierId"],
                                                     r["refKey"])):
        holder = cites.row()
        stub_artifact = (f"stubs/{lu.KIND_FILES[rec['carrierKind']]}"
                         f"#{rec['carrierId']}")
        payload = json.loads(json.dumps(rec["data"]))
        cites.tree(holder, payload, rec["data"], stub_artifact,
                   f"fields.references[{rec['refKey']}].data.",
                   prefix="payload/")
        targets = []
        for tp in rec["pptrs"]:
            edge = (rec["fullClass"] == "TPC.PrerequisiteHasCourseUnlocked"
                    and tp["fieldPath"] == "data._course")
            targets.append({
                "fieldPath": tp["fieldPath"], "fileId": tp["m_FileID"],
                "pathId": tp["m_PathID"],
                "resolution": "course-unlock-edge" if edge else None})
            base = f"references[{rec['refKey']}].{tp['fieldPath']}"
            holder.append((f"targets/{len(targets) - 1}/fileId",
                           tp["m_FileID"], stub_artifact,
                           f"fields.{base}.m_FileID"))
            holder.append((f"targets/{len(targets) - 1}/pathId",
                           tp["m_PathID"], stub_artifact,
                           f"fields.{base}.m_PathID"))
        list_fields = sorted(rec.get("listFields") or [])
        doc = {
            "carrierId": rec["carrierId"],
            "carrierKind": rec["carrierKind"],
            "listField": list_fields[0] if list_fields else None,
            "refKey": rec["refKey"],
            "prerequisiteClass": str((rec["type"] or {}).get("class")),
            "asm": str((rec["type"] or {}).get("asm") or ""),
            "ns": str((rec["type"] or {}).get("ns") or ""),
            "payload": payload,
            "targets": targets,
            "taxonomyIndex": members.index(rec["fullClass"]),
            "evidence": {"sourceArtifact": stub_artifact},
            "buildId": build_id,
        }
        holder.append(("buildId", build_id, "identity.json", "buildId"))
        rows.append(doc)
    cites.flush(audit, art, rows)
    for i, rec in enumerate(sorted(member_records,
                                   key=lambda r: (r["carrierId"],
                                                  r["refKey"]))):
        audit.derive(art, f"{i}/taxonomyIndex",
                     "taxonomy-member-index(prerequisite-taxonomy.json)",
                     [{"sourceArtifact":
                       "logic/course-progression/prerequisite-taxonomy.json",
                       "sourcePath": "members"}],
                     lambda vals, _c=rec["fullClass"]: list(vals[0]).index(_c))

    # --- non-member sidecar --------------------------------------------------
    nm_artifact = "logic/course-progression/prerequisite-nonmembers.jsonl"
    nm_rows: list[dict] = []
    nm_cites = Cites()
    for rec in sorted(nonmember_records,
                      key=lambda r: (r["carrierId"], r["refKey"])):
        holder = nm_cites.row()
        stub_artifact = (f"stubs/{lu.KIND_FILES[rec['carrierKind']]}"
                         f"#{rec['carrierId']}")
        payload = json.loads(json.dumps(rec["data"]))
        nm_cites.tree(holder, payload, rec["data"], stub_artifact,
                      f"fields.references[{rec['refKey']}].data.",
                      prefix="payload/")
        doc = {"carrierId": rec["carrierId"],
               "carrierKind": rec["carrierKind"], "refKey": rec["refKey"],
               "blockClass": str((rec["type"] or {}).get("class")),
               "interfaceFamily": lu.NONMEMBER_INTERFACE,
               "payload": payload,
               "evidence": {"sourceArtifact": stub_artifact},
               "buildId": build_id}
        holder.append(("buildId", build_id, "identity.json", "buildId"))
        nm_rows.append(doc)
    nm_cites.flush(audit, nm_artifact, nm_rows)

    # --- probes --------------------------------------------------------------
    cfg_counts = Counter(str((r["type"] or {}).get("class"))
                         for r in configs_members)
    check_probe(p, drift, "prerequisiteInstancesConfigs",
                lu.SEEDS["prerequisiteInstancesConfigs"],
                len(configs_members))
    for name, seed_key in (
            ("PrerequisiteHasCourseUnlocked",
             "prerequisiteClassHasCourseUnlocked"),
            ("PrerequisiteUniversityLevel", "prerequisiteClassUniversityLevel"),
            ("ChallengePrerequisiteHasRoomUnlocked",
             "prerequisiteClassChallengeHasRoomUnlocked"),
            ("PrerequisiteDaysPassed", "prerequisiteClassDaysPassed"),
            ("PrerequisiteHasStarsInLevel", "prerequisiteClassStarsInLevel")):
        check_probe(p, drift, f"prerequisiteClass[{name}]",
                    lu.SEEDS[seed_key], cfg_counts.get(f"TPC.{name}", 0))
    check_probe(p, drift, "nonmemberBlocks", lu.SEEDS["nonmemberBlocks"],
                len(nonmember_records))
    check_probe(p, drift, "nonmemberFamilies", lu.SEEDS["nonmemberFamilies"],
                len({str((r["type"] or {}).get("class"))
                     for r in nonmember_records}))
    distinct_full = sorted({r["fullClass"] for r in member_records})
    outside = [c for c in distinct_full if c not in set(members)]
    if outside:
        drift.append(
            f"DRIFT: {len(outside)} new ancestor-resolving prerequisite "
            f"class(es) outside the 24-type taxonomy: {outside[:5]} — new "
            "content")
        for c in outside:
            gaps.append(lu.make_gap_row(
                "course-progression", "missing-carrier", f"taxonomy:{c}",
                f"class '{c}' resolves to TPC.Prerequisite ancestry but is "
                "absent from the emitted 24-type taxonomy",
                "refresh prerequisite-taxonomy.json members (new game "
                "content)", build_id))

    p.L1.update({
        "prerequisiteInstances": len(rows),
        "prerequisiteInstancesAllKinds": len(member_records),
        "taxonomyDistinctClasses": len(distinct_full),
        "nonmemberBlocks": len(nm_rows),
        "nonmemberFamilies": len({d["blockClass"] for d in nm_rows}),
    })
    log_util.write_jsonl(out_dir / "prerequisites.jsonl", rows)
    log_util.write_jsonl(out_dir / "prerequisite-nonmembers.jsonl", nm_rows)
    return rows, nm_rows


# ---------------------------------------------------------------------------
# L1 — unlock edges + relinks reconciliation leg

def run_l1_unlock_edges(ctx: dict, p: Pass, drift: list[str],
                        audit: lu.NumericAudit, out_dir: Path,
                        records: list[dict], gaps: list[dict],
                        problems: list[str]):
    build_id = ctx["build_id"]
    artifact = "logic/course-progression/course-unlock-edges.jsonl"
    unlock_recs = [r for r in records
                   if r["fullClass"] == "TPC.PrerequisiteHasCourseUnlocked"]
    built: list[tuple[dict, list[tuple]]] = []
    resolved = unresolved = builtin_skipped = 0
    for rec in sorted(unlock_recs, key=lambda r: (r["carrierId"],
                                                  r["refKey"])):
        stub_artifact = (f"stubs/{lu.KIND_FILES[rec['carrierKind']]}"
                         f"#{rec['carrierId']}")
        holder: list[tuple] = []
        course_pptrs = [t for t in rec["pptrs"]
                        if t["fieldPath"] == "data._course"]
        field_path = f"references[{rec['refKey']}].data._course"
        if not course_pptrs:
            unresolved += 1
            built.append((_edge_row(rec, None, build_id,
                                    "no _course PPtr in the block payload"),
                          holder))
            continue
        tp = course_pptrs[0]
        holder.append(("evidence/srcPathId", rec["carrierPathId"],
                       stub_artifact, "source.pathId"))
        holder.append(("evidence/extFileId", tp["m_FileID"], stub_artifact,
                       f"fields.{field_path}.m_FileID"))
        holder.append(("evidence/dstPathId", tp["m_PathID"], stub_artifact,
                       f"fields.{field_path}.m_PathID"))
        out = lu.resolve_typed_pptr(rec["carrierBundle"], rec["carrierPathId"],
                                    tp["m_FileID"], tp["m_PathID"], ctx,
                                    want_classes=lu.UNLOCK_DST_CLASSES)
        if out["status"] == "resolved":
            resolved += 1
            dst_id = out["id"]
            doc = {
                "srcKind": rec["carrierKind"], "srcId": rec["carrierId"],
                "verb": "requires-course-unlocked", "dstKind": out["kind"],
                "dstId": dst_id, "resolved": True, "mechanism": "hard",
                "method": "pptr-same-file-typed-block"
                if out.get("sameFile") else "pptr-cross-file-typed-block",
                "inferred": False,
                "evidence": {
                    "fieldPath": field_path,
                    "srcBundle": ru.bundle_base(rec["carrierBundle"]),
                    "srcPathId": rec["carrierPathId"],
                    "extFileId": tp["m_FileID"],
                    "dstBundle": ru.bundle_base(out["dstBundle"]),
                    "dstCab": out.get("dstCab") or "",
                    "dstPathId": tp["m_PathID"],
                },
                "buildId": build_id,
            }
            if "@" in dst_id:
                doc["dstTwinOf"] = dst_id.split("@", 1)[0]
        else:
            unresolved += 1
            doc = _edge_row(rec, field_path, build_id, out["reason"],
                            ext_file_id=tp["m_FileID"],
                            path_id=tp["m_PathID"])
            if out["status"] == "builtin":
                builtin_skipped += 1
                gaps.append(lu.make_gap_row(
                    "course-progression", "builtin-target",
                    rec["carrierId"], out["reason"],
                    "built-in resources are never entity targets; no action",
                    build_id))
            elif out["status"] == "ambiguous":
                gaps.append(lu.make_gap_row(
                    "course-progression", "ambiguous-target",
                    rec["carrierId"],
                    f"multiple surviving candidates: {out.get('candidates')}",
                    "disambiguate by destination class then container "
                    "address; still ambiguous ⇒ manual review", build_id))
            else:
                gaps.append(lu.make_gap_row(
                    "course-progression", "unresolved-pptr",
                    rec["carrierId"], out["reason"],
                    "grow the bridges/externals coverage and re-run",
                    build_id))
        built.append((doc, holder))

    # dedup identity (srcId, dstId, method, fieldPath); final sort
    dedup: dict[tuple, dict] = {}
    holder_by_key: dict[tuple, list[tuple]] = {}
    for (doc, holder) in built:
        key = (doc["srcId"], doc.get("dstId") or "", doc["method"],
               doc["evidence"]["fieldPath"])
        if key not in dedup:
            dedup[key] = doc
            holder_by_key[key] = holder
    ordered_keys = sorted(dedup)
    rows = [dedup[k] for k in ordered_keys]
    holders = [holder_by_key[k] for k in ordered_keys]

    # ---- MANDATORY reconciliation leg (arbiter-piece04-spec R1/RF-2) -------
    relink_rows = []
    cc_path = ctx["_extracted_root"] / "relinks" / "config_config.jsonl"
    with open(cc_path, encoding="utf-8", newline="\n") as fh:
        for line in fh:
            if line.strip():
                r = json.loads(line)
                if str((r.get("evidence") or {}).get("fieldPath", "")).endswith(
                        ".data._course"):
                    relink_rows.append(r)
    relinks_keys = {
        (str(r["evidence"]["srcBundle"]), int(r["evidence"]["srcPathId"]),
         int(r["evidence"]["dstPathId"])) for r in relink_rows}
    my_keys = set()
    for doc in rows:
        if doc.get("resolved"):
            ev = doc["evidence"]
            my_keys.add((ev["srcBundle"], int(ev["srcPathId"]),
                         int(ev["dstPathId"])))
    overlap = len(my_keys & relinks_keys)
    scope_only = sorted(relinks_keys - my_keys)
    mine_only = sorted(my_keys - relinks_keys)

    accounting: dict[tuple, str] = {}
    for rec in records:
        for tp in rec["pptrs"]:
            if tp["fieldPath"] != "data._course":
                continue
            key = (ru.bundle_base(rec["carrierBundle"]),
                   rec["carrierPathId"], tp["m_PathID"])
            accounting.setdefault(key, rec["fullClass"])
    class_accounting: Counter = Counter()
    for key in scope_only:
        cls = accounting.get(key)
        if cls is None:
            gaps.append(lu.make_gap_row(
                "course-progression", "relinks-divergence",
                f"{key[0]}#{key[1]}->{key[2]}",
                "relinks-side `_course` counterpart no logic-side typed "
                "block accounts for (outside the declared scope difference)",
                "extend the census to the block family that carries it",
                build_id))
        else:
            class_accounting[cls] += 1
    for key in mine_only:
        problems.append(
            f"unlock edge {key} has NO relinks counterpart in "
            "relinks/config_config.jsonl — the ledgers diverge")
        gaps.append(lu.make_gap_row(
            "course-progression", "relinks-divergence",
            f"{key[0]}#{key[1]}->{key[2]}",
            "resolved unlock edge without a relinks-side counterpart",
            "re-run the relink stage or reconcile its pair-file filter",
            build_id))
    if overlap != resolved:
        drift.append(
            f"DRIFT: unlockEdgeOverlapWithRelinks {overlap} != resolved "
            f"count {resolved} — gap rows hold exit 2")

    check_probe(p, drift, "relinksCoursePPTRRows",
                lu.SEEDS["relinksCoursePPTRRows"], len(relink_rows))
    check_probe(p, drift, "unlockEdgeInstances",
                lu.SEEDS["unlockEdgeInstances"], len(unlock_recs))

    # citations registered in FINAL order
    for i, holder in enumerate(holders):
        audit_cites = [(sub, val, sa, sp) for sub, val, sa, sp in holder
                       if sub != "buildId"]
        for sub, val, sa, sp in audit_cites:
            audit.copy(artifact, f"{i}/{sub}", val, sa, sp)
        audit.copy(artifact, f"{i}/buildId", build_id, "identity.json",
                   "buildId")

    p.L1.update({
        "unlockEdgesResolved": resolved,
        "unlockEdgesUnresolved": unresolved,
        "builtinExternalsSkipped": builtin_skipped,
        "relinksCoursePPTRRows": len(relink_rows),
        "unlockEdgeOverlapWithRelinks": overlap,
        "declaredScopeDifference": len(scope_only),
        "declaredScopeDifferenceByClass": {k: class_accounting[k]
                                           for k in sorted(class_accounting)},
    })
    log_util.write_jsonl(out_dir / "course-unlock-edges.jsonl", rows)
    return rows


def _edge_row(rec: dict, field_path, build_id, reason, ext_file_id=None,
              path_id=None) -> dict:
    doc = {
        "srcKind": rec["carrierKind"], "srcId": rec["carrierId"],
        "verb": "requires-course-unlocked", "dstKind": None, "dstId": None,
        "resolved": False, "reason": reason, "mechanism": "hard",
        "method": "pptr-cross-file-typed-block", "inferred": False,
        "evidence": {
            "fieldPath": field_path or f"references[{rec['refKey']}]",
            "srcBundle": ru.bundle_base(rec["carrierBundle"]),
            "srcPathId": rec["carrierPathId"],
        },
        "buildId": build_id,
    }
    if ext_file_id is not None:
        doc["evidence"]["extFileId"] = ext_file_id
    if path_id is not None:
        doc["evidence"]["dstPathId"] = path_id
    return doc


# ---------------------------------------------------------------------------
# L1 — attrition

def run_l1_attrition(ctx: dict, p: Pass, drift: list[str],
                     audit: lu.NumericAudit, out_dir: Path):
    build_id = ctx["build_id"]
    artifact = "logic/course-progression/attrition.jsonl"
    campus = next((r for r in ctx["stubs"].rows_by_kind["config"]
                   if r["id"] == "Config_Campus"), None)
    if campus is None:
        raise tc.StageError("Config_Campus stub row not found", exit_code=1)
    f = campus.get("fields") or {}
    rows: list[dict] = []
    cites = Cites()
    for group in lu.ATTRITION_GROUPS:
        holder = cites.row()
        val = f.get(group)
        fields_out = json.loads(json.dumps(val)) if isinstance(val, dict) \
            else val
        if isinstance(fields_out, dict) and isinstance(val, dict):
            cites.tree(holder, fields_out, val,
                       "stubs/configs.jsonl#Config_Campus",
                       "fields." + group + "/", prefix="fields/")
        elif val is not None:
            holder.append(("fields", val,
                           "stubs/configs.jsonl#Config_Campus",
                           f"fields.{group}"))
        rows.append({
            "group": group, "fields": fields_out,
            "events": list(lu.ATTRITION_EVENTS[group]),
            "evidence": {"artifact": "stubs/configs.jsonl#Config_Campus",
                         "fieldPath": group,
                         "codeRef": lu.ATTRITION_CODE_REF},
            "buildId": build_id,
        })
    for i, holder in enumerate(cites.per_row):
        holder.append(("buildId", build_id, "identity.json", "buildId"))
    cites.flush(audit, artifact, rows)

    dropout = f.get("StudentDropoutSettings") or {}
    resign = f.get("StaffResignationSettings") or {}
    if not (
            (dropout.get("ThresholdWarning"),
             dropout.get("ThresholdChangeOfMind"),
             dropout.get("ThresholdUrgent"), dropout.get("CountdownTimer"))
            == (20.0, 15.0, 10.0, 120.0)
            and (resign.get("ThresholdWarning"),
                 resign.get("ThresholdChangeOfMind"),
                 resign.get("ThresholdUrgent"),
                 resign.get("CountdownTimer")) == (20.0, 15.0, 10.0, 240.0)):
        drift.append(
            "DRIFT: attrition anchor twins moved — dropout="
            f"{dropout} resignation={resign}; fresh values win (emitted "
            "verbatim)")
    campus_twins = [r["id"] for r in ctx["stubs"].rows_by_kind["config"]
                    if str((r.get("source") or {}).get("class"))
                    == "TPC.CampusConfig"]
    check_probe(p, drift, "campusConfigRows", 2, len(campus_twins))
    p.L1["attritionGroups"] = len(rows)
    log_util.write_jsonl(out_dir / "attrition.jsonl", rows)
    return rows


# ---------------------------------------------------------------------------
# L2 — economy

def run_l2(ctx: dict, p: Pass, drift: list[str], audit: lu.NumericAudit,
           out_dir: Path, records: list[dict], problems: list[str]):
    build_id = ctx["build_id"]
    budget_rows = ctx["registries"]["TPS.Game.BudgetType.jsonl"]

    # --- money-taxonomy.json -------------------------------------------------
    art = "logic/economy/money-taxonomy.json"
    doc = {
        "budgetTypes": [{"name": str(r["name"]), "value": int(r["value"])}
                        for r in budget_rows],
        "budgetTypeSource": ("decompiled/structural/id-registries/"
                             "TPS.Game.BudgetType.jsonl"),
        "profitType": ["TuitionFees", "Rent", "Bonus"],
        "expenseType": ["Wages", "Loans"],
        "summaryColumns": ["TuitionFees", "Rent", "Wages", "Bonus",
                           "LoanRepayments", "LoanInterest", "BungleBonus",
                           "SocialBonus", "ResearchBonus", "MiningProfit",
                           "PatientTreatment", "CheesyBonus",
                           "MonthlyAllowance", "OtherIn", "OtherOut"],
        "resources": [
            {"resource": "money",
             "carriers": ["FinanceManager balance"],
             "budgetMembership": True},
            {"resource": "kudosh",
             "carriers": ["MetagameLevelState.TotalKudosh (int, dump.cs "
                          "~881087)"],
             "budgetMembership": False,
             "note": "NO BudgetType member is Kudosh — decisive negative, "
                     "F10"},
            {"resource": "course-points",
             "carriers": ["CoursesConfig.InitialCoursePoints",
                          "CoursesConfig.PointsPerUniversityLevel",
                          "CourseDefinition.StartPointsCost",
                          "Levels[].PointsCost"],
             "budgetMembership": False,
             "note": "never named a currency in code; acts as one — "
                     "spendable resource DISTINCT from money and Kudosh "
                     "(report §3)"},
        ],
        "provenanceBlocks": {
            "summaryColumns": "FinanceManager.Summary struct layout — a "
                              "code-derived projection, not a payload "
                              "(R4 hatch a)"},
        "provenance": "reconstructed-from-code",
        "buildId": build_id,
    }
    for i, bt in enumerate(doc["budgetTypes"]):
        reg_ref = ("decompiled/structural/id-registries/"
                   "TPS.Game.BudgetType.jsonl#" + bt["name"])
        audit.copy(art, f"budgetTypes/{i}/value", bt["value"], reg_ref,
                   "value")
    audit.label_code_block(art, "summaryColumns/",
                           "FinanceManager.Summary struct projection")
    audit.copy(art, "buildId", build_id, "identity.json", "buildId")
    reg_seq = [(str(r["name"]), int(r["value"])) for r in budget_rows]
    emit_seq = [(b["name"], b["value"]) for b in doc["budgetTypes"]]
    if reg_seq != emit_seq:
        problems.append(
            "money-taxonomy.budgetTypes does not byte-match "
            "TPS.Game.BudgetType.jsonl name-for-name/value-for-value in the "
            "registry file's own order")
    check_probe(p, drift, "budgetTypeCount", 28, len(budget_rows))
    p.L2 = {"budgetTypeCount": len(budget_rows)}
    log_util.write_json(out_dir / "money-taxonomy.json", doc)

    # --- finance-configs.jsonl -----------------------------------------------
    art = "logic/economy/finance-configs.jsonl"
    fin_keys = [
        ("InitialBalance", "initialBalance"),
        ("FailStateBalanceWarning", "failStateBalanceWarning"),
        ("FailStateBalanceGameOver", "failStateBalanceGameOver"),
        ("RentMultiplier", "rentMultiplier"),
        ("TuitionFeesMultiplier", "tuitionFeesMultiplier"),
        ("AllowTuitionFeeModification", "allowTuitionFeeModification"),
        ("UseBungleBonus", "useBungleBonus"),
    ]
    fin_rows = sorted((r for r in ctx["stubs"].rows_by_kind["config"]
                       if str((r.get("source") or {}).get("class"))
                       == "TPC.FinanceManagerConfig"), key=lambda r: r["id"])
    base = next((r for r in fin_rows if r["id"] == "Config_FinanceManager"),
                None)
    rows: list[dict] = []
    cites = Cites()
    diff_only = 0
    multi_field_overrides = []
    for r in fin_rows:
        holder = cites.row()
        f = r.get("fields") or {}
        doc_r: dict = {"id": r["id"]}
        for raw_key, out_key in fin_keys:
            val = f.get(raw_key)
            doc_r[out_key] = val
            if val is not None:
                holder.append((out_key, val, f"stubs/configs.jsonl#{r['id']}",
                               f"fields.{raw_key}"))
        doc_r["evidence"] = {"stubRow": f"stubs/configs.jsonl#{r['id']}"}
        doc_r["buildId"] = build_id
        if base is not None and r["id"] != base["id"]:
            bf = base.get("fields") or {}
            diffs = {rk for rk, ok in fin_keys if f.get(rk) != bf.get(rk)}
            if diffs == {"InitialBalance"}:
                diff_only += 1
            elif diffs:
                multi_field_overrides.append((r["id"], sorted(diffs)))
        rows.append(doc_r)
    for i, holder in enumerate(cites.per_row):
        holder.append(("buildId", build_id, "identity.json", "buildId"))
    cites.flush(audit, art, rows)
    archaeology = next((r for r in rows
                        if r["id"] == "Config_FinanceManager_Level_Archaeology"),
                       None)
    if base is not None and archaeology is not None:
        bf = base.get("fields") or {}
        diffs = {rk for rk, ok in fin_keys
                 if archaeology[ok] != bf.get(rk)}
        if diffs != {"InitialBalance"} \
                or archaeology["initialBalance"] != 80000:
            drift.append(
                "DRIFT: Config_FinanceManager_Level_Archaeology is no longer "
                "a diff-only InitialBalance override (diff keys "
                f"{sorted(diffs)}) — fresh values win")
    if multi_field_overrides:
        drift.append(
            f"DRIFT: {len(multi_field_overrides)} finance overrides differ "
            "beyond InitialBalance (legitimate wider overrides) e.g. "
            f"{multi_field_overrides[:3]}")
    check_probe(p, drift, "financeConfigs", lu.SEEDS["financeConfigs"],
                len(fin_rows))
    p.L2.update({"financeConfigRows": len(fin_rows),
                 "financeDiffOnlyOverrides": diff_only})
    log_util.write_jsonl(out_dir / "finance-configs.jsonl", rows)

    # --- kudosh-ledger.jsonl -------------------------------------------------
    art = "logic/economy/kudosh-ledger.jsonl"
    built: list[tuple[dict, list[tuple]]] = []
    sinks_by_impl: Counter = Counter()

    def add_sink(carrier_class, rid, amount, amount_field, implementer,
                 stub_kind):
        holder: list[tuple] = []
        if amount is not None:
            holder.append(("amount", amount,
                           f"stubs/{lu.KIND_FILES[stub_kind]}#{rid}",
                           f"fields.{amount_field}"))
        doc = {"direction": "sink", "implementer": implementer,
               "carrierClass": carrier_class, "carrierId": rid,
               "amount": amount, "amountField": amount_field,
               "evidence": {"stubRow":
                            f"stubs/{lu.KIND_FILES[stub_kind]}#{rid}",
                            "fieldPath": amount_field},
               "buildId": build_id}
        built.append((doc, holder))

    for kind in lu.STUB_KINDS:
        for r in sorted(ctx["stubs"].rows_by_kind[kind], key=lambda x: x["id"]):
            cls = str((r.get("source") or {}).get("class"))
            flds = r.get("fields") or {}
            if cls == "TPC.GameItemLiteDefinition" and "Kudosh" in flds:
                sinks_by_impl["item"] += 1
                add_sink(cls, r["id"], flds["Kudosh"], "Kudosh",
                         "GameItemDefinition", kind)
            elif cls == "TPC.RoomLiteDefinition" and "Kudosh" in flds:
                sinks_by_impl["room"] += 1
                add_sink(cls, r["id"], flds["Kudosh"], "Kudosh",
                         "RoomDefinition", kind)
            elif cls == "TPC.LandscapeBrushDefinition"                     and ("Cost" in flds or "_kudosh" in flds):
                price_field = "Cost" if "Cost" in flds else "_kudosh"
                sinks_by_impl["landscapeBrush"] += 1
                add_sink(cls, r["id"], flds[price_field], price_field,
                         "LandscapeBrushDefinition", kind)
            elif cls == "TPC.GameItemUpgradeDefinition" and "Cost" in flds:
                sinks_by_impl["upgrade"] += 1
                add_sink(cls, r["id"], flds["Cost"], "Cost",
                         "GameItemUpgradeDefinition", kind)
            elif cls == "TPC.CourseDefinition" and "KudoshCost" in flds:
                sinks_by_impl["courseLicence"] += 1
                add_sink(cls, r["id"], flds["KudoshCost"], "KudoshCost",
                         "CourseDefinition", kind)
    for rec in sorted(records, key=lambda r: (r["carrierId"], r["refKey"])):
        if rec["fullClass"] != "TPC.RewardKudoshDefinition":
            continue
        holder: list[tuple] = []
        amount = rec["data"].get("_amount")
        stub_artifact = (f"stubs/{lu.KIND_FILES[rec['carrierKind']]}"
                         f"#{rec['carrierId']}")
        if amount is not None:
            holder.append(("amount", amount, stub_artifact,
                           _src_path(
                               f"fields.references[{rec['refKey']}].data",
                               "_amount")))
        hud = rec["data"].get("_displayInHUD")
        if hud is not None:
            holder.append(("displayInHUD", hud, stub_artifact,
                           _src_path(
                               f"fields.references[{rec['refKey']}].data",
                               "_displayInHUD")))
        built.append(({
            "direction": "source", "carrierClass": rec["carrierClass"],
            "carrierId": rec["carrierId"], "amount": amount,
            "amountField": "_amount",
            "displayInHUD": rec["data"].get("_displayInHUD"),
            "evidence": {"stubRow": stub_artifact,
                         "fieldPath":
                         f"references[{rec['refKey']}].data._amount"},
            "buildId": build_id}, holder))
    consumables = [r for r in sorted(ctx["stubs"].rows_by_kind["config"],
                                     key=lambda x: x["id"])
                   if str((r.get("source") or {}).get("class"))
                   == "TPC.KudoshConsumableRewardConfig"]
    for r in consumables:
        built.append(({
            "direction": "source",
            "carrierClass": "TPC.KudoshConsumableRewardConfig",
            "carrierId": r["id"], "amount": None, "amountField": None,
            "evidence": {"stubRow": f"stubs/configs.jsonl#{r['id']}",
                         "note": "stub payload serializes no amount fields "
                                 "(declared-empty, never zero-filled)"},
            "buildId": build_id}, []))

    built.sort(key=lambda t: (t[0]["direction"], t[0]["carrierId"],
                              t[0].get("amountField") or "",
                              t[0].get("evidence", {}).get("fieldPath") or ""))
    rows = [doc for doc, _h in built]
    for i, (_doc, holder) in enumerate(built):
        holder.append(("buildId", build_id, "identity.json", "buildId"))
        for sub, val, sa, sp in holder:
            audit.copy(art, f"{i}/{sub}", val, sa, sp)
    check_probe(p, drift, "kudoshConsumableRewardConfigs",
                lu.SEEDS["kudoshConsumableRewardConfigs"], len(consumables))
    p.L2.update({
        "kudoshSources": sum(1 for d in rows if d["direction"] == "source"),
        "kudoshSinksByImplementer": {
            k: sinks_by_impl[k] for k in ("item", "room", "landscapeBrush",
                                          "upgrade", "courseLicence")},
    })
    for impl, iface, seed_key in (
            ("item", "GameItemDefinition", "kudoshSinkItem"),
            ("room", "RoomDefinition", "kudoshSinkRoom"),
            ("landscapeBrush", "LandscapeBrushDefinition",
             "kudoshSinkLandscapeBrush"),
            ("upgrade", "GameItemUpgradeDefinition", "kudoshSinkUpgrade"),
            ("courseLicence", "CourseDefinition",
             "kudoshSinkCourseLicence")):
        check_probe(p, drift, f"kudoshSink[{iface}]",
                    lu.SEEDS[seed_key], sinks_by_impl[impl])
        if sinks_by_impl[impl] == 0:
            drift.append(
                f"DRIFT: kudosh-ledger IKudoshUnlockable implementer "
                f"partition '{impl}' ({iface}) is EMPTY on this corpus")
    log_util.write_jsonl(out_dir / "kudosh-ledger.jsonl", rows)

    # --- research-costs.jsonl ------------------------------------------------
    art = "logic/economy/research-costs.jsonl"
    domain_seed = {100, 200, 250, 300, 500, 600, 1200, 2500, 3000}
    dist_seed = {100: 4, 200: 1, 250: 12, 300: 52, 500: 82, 600: 27,
                 1200: 29, 2500: 1, 3000: 1}
    meta_rows = sorted(ctx["stubs"].rows_by_kind["metagame-node"],
                       key=lambda r: r["id"])
    full_defs = [r for r in meta_rows
                 if str((r.get("source") or {}).get("class"))
                 == "TPC.ResearchProjectDefinition"]
    rows: list[dict] = []
    cites = Cites()
    lite_without_costs = 0
    for r in meta_rows:
        cls = str((r.get("source") or {}).get("class"))
        flds = r.get("fields") or {}
        if cls == "TPC.ResearchProjectLiteDefinition" \
                and "ResearchPoints" not in flds:
            lite_without_costs += 1
            continue
        if cls != "TPC.ResearchProjectDefinition":
            continue
        holder = cites.row()
        rp = flds.get("ResearchPoints")
        if rp is not None:
            holder.append(("researchPoints", rp,
                           f"stubs/metagame-nodes.jsonl#{r['id']}",
                           "fields.ResearchPoints"))
        rows.append({
            "id": r["id"], "researchPoints": rp,
            "evidence": {"stubRow": f"stubs/metagame-nodes.jsonl#{r['id']}"},
            "buildId": build_id})
    for i, holder in enumerate(cites.per_row):
        holder.append(("buildId", build_id, "identity.json", "buildId"))
    cites.flush(audit, art, rows)
    cost_rows = [r for r in rows if r["researchPoints"] is not None]
    if len(cost_rows) != len(full_defs):
        problems.append(
            f"research-costs: {len(cost_rows)} cost-bearing rows != "
            f"{len(full_defs)} TPC.ResearchProjectDefinition stub rows")
    dist = Counter(r["researchPoints"] for r in cost_rows)
    if sum(dist.values()) != len(cost_rows):
        problems.append("research-costs distribution does not sum to the "
                        "row count")
    grown = sorted(set(dist) - domain_seed)
    if grown:
        drift.append(f"DRIFT: research domain grew beyond the 9-value seed: "
                     f"{grown} — fresh wins")
    for value in sorted(set(dist) & set(dist_seed)):
        if dist[value] != dist_seed[value]:
            drift.append(f"DRIFT: research distribution at {value}: "
                         f"{dist[value]} vs seed {dist_seed[value]} — fresh "
                         "wins")
    check_probe(p, drift, "researchCostRows", lu.SEEDS["researchCostRows"],
                len(cost_rows))
    check_probe(p, drift, "liteRowsWithoutCosts",
                lu.SEEDS["liteRowsWithoutCosts"], lite_without_costs)
    p.L2.update({"researchCostRows": len(cost_rows),
                 "liteRowsWithoutCosts": lite_without_costs,
                 "researchDomainDistinct": len(dist)})
    log_util.write_jsonl(out_dir / "research-costs.jsonl", rows)


# ---------------------------------------------------------------------------
# L3 — grading

def run_l3(ctx: dict, p: Pass, drift: list[str], audit: lu.NumericAudit,
           out_dir: Path, problems: list[str]) -> dict:
    build_id = ctx["build_id"]
    stubs = ctx["stubs"]

    # --- grade-ladder.json ---------------------------------------------------
    art = "logic/grading/grade-ladder.json"
    ui = next((r for r in stubs.rows_by_kind["config"]
               if r["id"] == "Config_UISprite"), None)
    if ui is None:
        raise tc.StageError("Config_UISprite stub row not found", exit_code=1)
    grades = (ui.get("fields") or {}).get("Grades")
    if not isinstance(grades, list):
        raise tc.StageError("Config_UISprite.fields.Grades missing",
                            exit_code=1)
    enum_rows = ctx["registries"]["TPS.Game.TPC.EGrade.jsonl"]
    grade_rows: list[dict] = []
    for i, g in enumerate(grades):
        sub = ((g.get("AlternativeIconReference") or {}).get("m_SubObjectName")
               or "")
        token = sub.rsplit("Grade_", 1)[-1] if "Grade_" in sub else None
        term_id = (g.get("DisplayName") or {}).get("_termID")
        display = None
        if term_id is not None:
            reg = ctx["term_registry"].get(int(term_id))
            display = reg["termKey"] if reg else None
        grade_rows.append({"grade": token, "enumValue": g.get("Enum"),
                           "threshold": g.get("Threshold"),
                           "displayNameTermId": term_id,
                           "displayName": display})
    # AC3 gate: the re-derived table IS the emitted table (same construction)
    # + monotonicity beyond the NA sentinel row
    thresholds = [r["threshold"] for r in grade_rows[1:]
                  if isinstance(r["threshold"], (int, float))]
    monotonic_ok = all(a <= b for a, b in zip(thresholds, thresholds[1:]))
    if not monotonic_ok:
        problems.append(
            "grade-ladder thresholds are not monotonically non-decreasing "
            "beyond the NA sentinel row")
    doc = {
        "enum": {
            "source": "decompiled/structural/id-registries/"
                      "TPS.Game.TPC.EGrade.jsonl",
            "members": [{"name": str(r["name"]), "value": int(r["value"])}
                        for r in enum_rows],
        },
        "thresholdTable": {
            "sourceArtifact":
                "stubs/configs.jsonl#Config_UISprite.fields.Grades",
            "rows": grade_rows,
            "consumer": "UISpriteConfig.GetGrade(float score) / "
                        "GetGradeDisplayName (dump.cs ~1000712)",
        },
        "displayNameLocaleJoin": "i2_term_registry/entity_locale (relinks)",
        "provenance": "hard-read",
        "buildId": build_id,
    }
    for i, row in enumerate(grade_rows):
        audit.copy(art, f"thresholdTable/rows/{i}/threshold",
                   row["threshold"], "stubs/configs.jsonl#Config_UISprite",
                   f"fields.Grades[{i}].Threshold")
        audit.copy(art, f"thresholdTable/rows/{i}/enumValue",
                   row["enumValue"], "stubs/configs.jsonl#Config_UISprite",
                   f"fields.Grades[{i}].Enum")
        if row["displayNameTermId"] is not None:
            audit.copy(art, f"thresholdTable/rows/{i}/displayNameTermId",
                       row["displayNameTermId"],
                       "stubs/configs.jsonl#Config_UISprite",
                       f"fields.Grades[{i}].DisplayName._termID")
    for i, m in enumerate(doc["enum"]["members"]):
        audit.copy(art, f"enum/members/{i}/value", m["value"],
                   "decompiled/structural/id-registries/"
                   f"TPS.Game.TPC.EGrade.jsonl#{m['name']}", "value")
    audit.copy(art, "buildId", build_id, "identity.json", "buildId")
    if len(grade_rows) != len(enum_rows):
        problems.append(
            f"grade-ladder join broken: {len(grade_rows)} Grades rows vs "
            f"{len(enum_rows)} EGrade registry members")
    check_probe(p, drift, "gradeLadderRows", lu.SEEDS["gradeLadderRows"],
                len(grade_rows))
    p.L3 = {"gradeLadderRows": len(grade_rows),
            "thresholdMonotonicCheck": monotonic_ok}
    log_util.write_json(out_dir / "grade-ladder.json", doc)

    # --- term-pass-grades.jsonl ----------------------------------------------
    art = "logic/grading/term-pass-grades.jsonl"
    grade_by_value = {int(r["value"]): str(r["name"]) for r in enum_rows}
    rows: list[dict] = []
    cites = Cites()
    term_unresolved = 0
    terms_refs = 0
    for course in sorted(stubs.rows_by_kind["course"], key=lambda r: r["id"]):
        if str((course.get("source") or {}).get("class")) \
                != "TPC.CourseDefinition":
            continue
        src = course.get("source") or {}
        for ti, tptr in enumerate((course.get("fields") or {}).get("Terms")
                                  or []):
            terms_refs += 1
            holder = cites.row()
            resolved, _out = resolve_field_ptr(ctx, src, tptr)
            term_id = pass_value = weight = module_count = None
            if resolved["resolved"]:
                term_row = next((r for r in stubs.rows_by_kind[resolved["kind"]]
                                 if r["id"] == resolved["id"]), None)
                if term_row is not None:
                    term_id = str(term_row["id"])
                    tf = term_row.get("fields") or {}
                    pass_value = tf.get("PassGrade")
                    weight = tf.get("Weight")
                    mods = tf.get("Modules")
                    if isinstance(mods, list):
                        module_count = len(mods)
            else:
                term_unresolved += 1
            if pass_value is not None:
                holder.append(("passGradeValue", pass_value,
                               f"stubs/configs.jsonl#{term_id}",
                               "fields.PassGrade"))
            if weight is not None:
                holder.append(("weight", weight,
                               f"stubs/configs.jsonl#{term_id}",
                               "fields.Weight"))
            rows.append({
                "courseId": course["id"], "termIndex": ti, "termId": term_id,
                "passGrade": grade_by_value.get(pass_value)
                if isinstance(pass_value, int) else None,
                "passGradeValue": pass_value, "weight": weight,
                "moduleCount": module_count,
                "evidence": {"fieldPath": f"Terms[{ti}]",
                             "resolution": "pptr-same-file"
                             if resolved["resolved"]
                             and _was_same_file(ctx, src, tptr)
                             else "pptr-cross-file"},
                "buildId": build_id})
    for i, holder in enumerate(cites.per_row):
        holder.append(("buildId", build_id, "identity.json", "buildId"))
    cites.flush(audit, art, rows)
    for i, row in enumerate(rows):
        audit.derive(
            art, f"{i}/termIndex", "index-in-array(Terms[])",
            [{"sourceArtifact":
              f"stubs/courses.jsonl#{row['courseId']}",
              "sourcePath": "fields.Terms"}],
            lambda vals, _ti=row["termIndex"]: (_ti if isinstance(vals[0], list)
                                                and _ti < len(vals[0])
                                                else -1))
        if row.get("moduleCount") is None:
            continue
        audit.derive(art, f"{i}/moduleCount", "len(TermDefinition.Modules[])",
                     [{"sourceArtifact":
                       f"stubs/{lu.KIND_FILES['config']}#{row['termId']}",
                       "sourcePath": "fields.Modules"}],
                     lambda vals: len(vals[0]))
    check_probe(p, drift, "termRefs", lu.SEEDS["termRefs"], terms_refs)
    p.L3.update({"termPassGradeRows": len(rows),
                 "termPassGradeUnresolved": term_unresolved})
    log_util.write_jsonl(out_dir / "term-pass-grades.jsonl", rows)

    # --- assessment-scoring.jsonl --------------------------------------------
    art = "logic/grading/assessment-scoring.jsonl"
    raws = lu.load_harvest_family(
        ctx["_extracted_root"] / "harvest" / "monobehaviours",
        "TPC.CourseDefinition")
    raw_by_pid = {pid: (rel, payload) for rel, _stem, pid, payload in raws}
    rows = []
    for course in sorted(stubs.rows_by_kind["course"], key=lambda r: r["id"]):
        src = course.get("source") or {}
        if str(src.get("class")) != "TPC.CourseDefinition":
            continue
        hit = raw_by_pid.get(int(src.get("pathId")))
        if hit is None:
            continue      # marketing variants absent BY DATA (no struct)
        rel, payload = hit
        scoring = payload.get("_assessmentScoring")
        if not isinstance(scoring, dict):
            continue
        holder: list[tuple] = []
        doc = {"courseId": course["id"]}
        for raw_key, out_key in SCORING_KEYS:
            val = scoring.get(raw_key)
            doc[out_key] = val
            if val is not None:
                holder.append((out_key, val, rel,
                               f"_assessmentScoring.{raw_key}"))
        doc["evidence"] = {"rawDump": rel}
        doc["buildId"] = build_id
        rows.append((doc, holder))
    for i, (_doc, holder) in enumerate(rows):
        holder.append(("buildId", build_id, "identity.json", "buildId"))
        for sub, val, sa, sp in holder:
            audit.copy(art, f"{i}/{sub}", val, sa, sp)
    final_rows = [d for d, _h in rows]
    p.L3["assessmentScoringRows"] = len(final_rows)
    log_util.write_jsonl(out_dir / "assessment-scoring.jsonl", final_rows)

    # --- xp-score-normalization.json (UNPROVEN-NATIVE marker) -----------------
    xp_doc = {
        "surface": "XP accumulation -> assessment score normalization "
                   "feeding GetGrade(score)",
        "status": "UNPROVEN-NATIVE",
        "basis": "score->grade cut-offs ARE data (thresholdTable above); "
                 "the normalization feeding them lives native/Burst "
                 "(report §4 item 6, G4 residual)",
        "emittedNumbers": [],
        "unblock": "scoped native-analysis piece over GameAssembly.dll "
                   "guided by script.json (orchestrator ruling R3 UPDATE: "
                   "THE single known trigger case)",
        "siteLaw": "site presents the bands as client data and the step "
                   "below them as unknown — never an authored curve",
        "buildId": build_id,
    }
    audit.copy("logic/grading/xp-score-normalization.json", "buildId",
               build_id, "identity.json", "buildId")
    log_util.write_json(out_dir / "xp-score-normalization.json", xp_doc)
    return xp_doc


def _was_same_file(ctx: dict, src: dict, ptr: dict) -> bool:
    del ctx
    return int(ptr.get("m_FileID", 0)) == 0


# ---------------------------------------------------------------------------
# L4 — needs & decay

def run_l4(ctx: dict, p: Pass, drift: list[str], audit: lu.NumericAudit,
           out_dir: Path):
    build_id = ctx["build_id"]
    stubs = ctx["stubs"]

    # --- staff-decay.jsonl ----------------------------------------------------
    art = "logic/needs-decay/staff-decay.jsonl"
    rows: list[dict] = []
    for staff in sorted(stubs.rows_by_kind["staff"], key=lambda r: r["id"]):
        blocks = lu.walk_typed_blocks(staff.get("fields") or {})
        ecp = [b for b in blocks
               if str((b["type"] or {}).get("class"))
               == "ECPCharacterAttributes"]
        if not ecp:
            continue
        b = ecp[0]
        for field_name in sorted(lu.STAFF_FIELD_TO_ATTRIBUTE):
            attr_block = b["data"].get(field_name)
            if not isinstance(attr_block, dict):
                continue
            holder: list[tuple] = []
            ref_prefix = f"references[{b['refKey']}].data.{field_name}"
            doc = {
                "staffId": staff["id"],
                "attribute": lu.STAFF_FIELD_TO_ATTRIBUTE[field_name],
                "changeOverTime": attr_block.get("ChangeOverTime"),
                "minInitialValue": attr_block.get("MinInitialValue"),
                "maxInitialValue": attr_block.get("MaxInitialValue"),
                "disabled": attr_block.get("Disabled"),
                "component": "ECPCharacterAttributes",
                "evidence": {
                    "stubRow": f"stubs/staff.jsonl#{staff['id']}",
                    "refKey": b["refKey"], "fieldPath": ref_prefix},
                "buildId": build_id,
            }
            for out_key, src_key in (("changeOverTime", "ChangeOverTime"),
                                     ("minInitialValue", "MinInitialValue"),
                                     ("maxInitialValue", "MaxInitialValue"),
                                     ("disabled", "Disabled")):
                if doc[out_key] is not None:
                    holder.append((out_key, doc[out_key],
                                   f"stubs/staff.jsonl#{staff['id']}",
                                   f"fields.{ref_prefix}.{src_key}"))
            holder.append(("buildId", build_id, "identity.json", "buildId"))
            rows.append(doc)
            for sub, val, sa, sp in holder:
                audit.copy(art, f"{len(rows) - 1}/{sub}", val, sa, sp)
    if len(rows) != 30:
        drift.append(f"DRIFT: staff decay rows measure {len(rows)} against "
                     "the 3×10 seed — fresh wins")
    p.L4 = {"staffDecayRows": len(rows)}
    log_util.write_jsonl(out_dir / "staff-decay.jsonl", rows)

    # --- student-decay.jsonl (ECPStudent harvest-direct + club corroboration)
    art = "logic/needs-decay/student-decay.jsonl"
    rows = []
    raws = lu.load_harvest_family(
        ctx["_extracted_root"] / "harvest" / "monobehaviours",
        "TPC.StudentDefinition")
    for rel, _stem, _pid, payload in raws:
        refs = payload.get("references") or {}
        for ref_key in sorted(k for k in refs if k != "version"):
            block = refs[ref_key]
            dtype = block.get("type") or {}
            if str(dtype.get("class")) != "ECPStudent":
                continue
            data = block.get("data") or {}
            for field_name in sorted(lu.STUDENT_FIELD_TO_ATTRIBUTE):
                attr_block = data.get(field_name)
                if not isinstance(attr_block, dict):
                    continue
                holder: list[tuple] = []
                doc = {
                    "studentTypeId": str(payload.get("m_Name") or ""),
                    "component": "ECPStudent",
                    "attribute": lu.STUDENT_FIELD_TO_ATTRIBUTE[field_name],
                    "changeOverTime": attr_block.get("ChangeOverTime"),
                    "minInitialValue": attr_block.get("MinInitialValue"),
                    "maxInitialValue": attr_block.get("MaxInitialValue"),
                    "evidence": {
                        "rawDump": rel,
                        "fieldPath": f"references[{ref_key}].data."
                                     f"{field_name}"},
                    "buildId": build_id,
                }
                for out_key, src_key in (
                        ("changeOverTime", "ChangeOverTime"),
                        ("minInitialValue", "MinInitialValue"),
                        ("maxInitialValue", "MaxInitialValue")):
                    if doc[out_key] is not None:
                        holder.append((out_key, doc[out_key], rel,
                                       f"references[{ref_key}].data."
                                       f"{field_name}.{src_key}"))
                holder.append(("buildId", build_id, "identity.json",
                               "buildId"))
                for sub, val, sa, sp in holder:
                    audit.copy(art, f"{len(rows)}/{sub}", val, sa, sp)
                rows.append(doc)
    n_student_rows = len(rows)
    club_rows = 0
    for club in sorted(stubs.rows_by_kind["config"], key=lambda r: r["id"]):
        if str((club.get("source") or {}).get("class")) != "TPC.ClubDefinition":
            continue
        rate = (club.get("fields") or {}).get("ClubNeedChangeOverTime")
        if rate is None:
            continue
        audit.copy(art, f"{len(rows)}/changeOverTime", rate,
                   f"stubs/configs.jsonl#{club['id']}",
                   "fields.ClubNeedChangeOverTime")
        audit.copy(art, f"{len(rows)}/buildId", build_id, "identity.json",
                   "buildId")
        rows.append({
            "studentTypeId": club["id"], "component": "ClubDefinition",
            "attribute": "ClubNeed", "changeOverTime": rate,
            "minInitialValue": None, "maxInitialValue": None,
            "evidence": {"stubRow": f"stubs/configs.jsonl#{club['id']}",
                         "fieldPath": "ClubNeedChangeOverTime"},
            "buildId": build_id})
        club_rows += 1
    check_probe(p, drift, "studentDecayRawRaws",
                lu.SEEDS["staffDecayRawRaws"], len(raws))
    check_probe(p, drift, "clubDecayRows", lu.SEEDS["clubDecayRows"],
                club_rows)
    p.L4.update({
        "studentDecayRows": n_student_rows, "clubDecayRows": club_rows,
        "studentDecayRawCoverage": {
            "raws": len(raws),
            "studentTypeStubs": len(stubs.rows_by_kind["student-type"])},
    })
    log_util.write_jsonl(out_dir / "student-decay.jsonl", rows)

    # --- student-core11-decay.jsonl (absent-carrier ledger, nulls by law) ----
    art = "logic/needs-decay/student-core11-decay.jsonl"
    rows = []
    for i, m in enumerate(ctx["registries"]["TPS.Game.TPC.EAttribute.jsonl"]):
        audit.copy(art, f"{i}/buildId", build_id, "identity.json", "buildId")
        rows.append({
            "attribute": str(m["name"]), "changeOverTime": None,
            "initRange": None, "carrier": "absent",
            "searchScope": "all 9 stub kinds + every harvested "
                           "monobehaviour family",
            "status": "UNPROVEN-NATIVE",
            "unblock": "native probe (G1/G8) or save-state diffing across "
                       "time intervals (report G3)",
            "buildId": build_id})
    p.L4["core11LedgerRows"] = len(rows)
    log_util.write_jsonl(out_dir / "student-core11-decay.jsonl", rows)

    # --- interactions.jsonl ---------------------------------------------------
    art = "logic/needs-decay/interactions.jsonl"
    interactions = sorted(
        (r for r in stubs.rows_by_kind["config"]
         if str((r.get("source") or {}).get("class"))
         == "TPC.InteractionDefinition"), key=lambda r: r["id"])
    rows = []
    ai_graphs = 0
    for inter in interactions:
        rid = inter["id"]
        src = inter.get("source") or {}
        f = inter.get("fields") or {}
        stub_artifact = f"stubs/configs.jsonl#{rid}"
        holder: list[tuple] = []
        holder.append(("evidence/srcPathId", int(src.get("pathId")),
                       stub_artifact, "fields.source.pathId"
                       if False else "source.pathId"))
        verbatim = {}
        for key in lu.INTERACTION_VERBATIM_FIELDS:
            if key in f:
                verbatim[key] = json.loads(json.dumps(f[key]))
                for sub, sval in cite_leaves(verbatim[key], f[key]):
                    full = (f"cooldownAndQueue/{key}/{sub}" if sub
                            else f"cooldownAndQueue/{key}")
                    holder.append((full, sval, stub_artifact,
                                   _src_path(f"fields.{key}", sub)))
        fm_ptr = f.get("FinanceModifier")
        finance_modifier = None
        if isinstance(fm_ptr, dict) and (fm_ptr.get("m_FileID"),
                                         fm_ptr.get("m_PathID")) != (0, 0):
            resolved, _o = resolve_field_ptr(ctx, src, fm_ptr)
            if resolved["resolved"]:
                finance_modifier = {"kind": resolved["kind"],
                                    "id": resolved["id"]}
        blocks = lu.walk_typed_blocks(f)
        typed_blocks = [{"refKey": b["refKey"], "class": b["fullClass"],
                         "type": dict(b["type"]),
                         "data": json.loads(json.dumps(b["data"]))}
                        for b in blocks]
        for bi, (tb, b) in enumerate(zip(typed_blocks, blocks)):
            for sub, sval in cite_leaves(tb["data"], b["data"]):
                holder.append((f"typedBlocks/{bi}/data/{sub}",
                               sval, stub_artifact,
                               _src_path(
                                   f"fields.references[{b['refKey']}].data",
                                   sub)))
        graph_refs = _graph_targets(ctx, inter)
        ai_graphs += len(graph_refs)
        doc = {
            "id": rid, "cooldownAndQueue": verbatim,
            "financeModifier": finance_modifier,
            "typedBlocks": typed_blocks,
            "satisfactionTargets": sorted(
                {b["fullClass"] for b in blocks if NEED_RE.search(b["fullClass"])}),
            "aiGraphRefs": graph_refs,
            "aiGraphRef": graph_refs[0]["id"] if graph_refs else None,
            "evidence": {"stubRow": stub_artifact,
                         "srcBundle": ru.bundle_base(str(src.get("bundle"))),
                         "srcPathId": int(src.get("pathId"))},
            "buildId": build_id,
        }
        holder.append(("buildId", build_id, "identity.json", "buildId"))
        for sub, val, sa, sp in holder:
            audit.copy(art, f"{len(rows)}/{sub}", val, sa, sp)
        rows.append(doc)
    check_probe(p, drift, "interactionRows", lu.SEEDS["interactions"],
                len(interactions))
    p.L4.update({"interactionRows": len(interactions),
                 "aiGraphsResolved": ai_graphs})
    log_util.write_jsonl(out_dir / "interactions.jsonl", rows)


def _graph_targets(ctx: dict, row: dict) -> list[dict]:
    """PPtr leaves of one interaction row resolving onto GOOSE
    GraphDefinition stub rows — topology pointers only (semantics stay
    native)."""
    out = []
    src = row.get("source") or {}
    bundle = ru.bundle_base(str(src.get("bundle")))
    pid = int(src.get("pathId"))
    for ref in ru.walk_pptr_refs(row):
        resolved = lu.resolve_typed_pptr(bundle, pid,
                                         int(ref["m_FileID"]),
                                         int(ref["m_PathID"]), ctx)
        if resolved["status"] != "resolved":
            continue
        if ctx["class_by_stub"].get((resolved["kind"], resolved["id"])) \
                == "TPS.Core.GOOSE.GraphDefinition":
            out.append({"fieldPath": ref["fieldPath"], "id": resolved["id"]})
    out.sort(key=lambda d: (d["fieldPath"], d["id"]))
    return out


# ---------------------------------------------------------------------------
# entrypoint

def run(game_root: Path | None, extracted_root: Path) -> int:
    del game_root   # this stage opens ZERO asset bundles and needs NO game dir
    global EXTRACTED_ROOT
    EXTRACTED_ROOT = extracted_root
    problems: list[str] = []
    drift: list[str] = []
    gaps: list[dict] = []
    p = Pass()

    required = [
        extracted_root / "identity.json",
        extracted_root / "stubs" / "_absences.jsonl",
        *[extracted_root / "stubs" / lu.KIND_FILES[k]
          for k in lu.STUB_KINDS],
        extracted_root / HARVEST_COURSE_DIR,
        extracted_root / HARVEST_STUDENT_DIR,
        extracted_root / "decompiled" / "structural" /
        "class-hierarchy.jsonl",
        *[extracted_root / "decompiled" / "structural" / "id-registries" / n
          for n in REGISTRY_FILES],
        extracted_root / "relinks" / "matrix.json",
        extracted_root / "relinks" / "config_config.jsonl",
        extracted_root / "relinks" / "i2_term_registry.jsonl",
        extracted_root / "relinks" / "entity_locale.jsonl",
        extracted_root / "relinks" / "bridges" / "cab_index.jsonl",
        extracted_root / "relinks" / "bridges" / "container_index.jsonl",
        extracted_root / "harvest" / "externals.jsonl",
        extracted_root / "harvest" / "export-manifest.jsonl",
    ]
    missing = [q for q in required if not q.exists()]
    if missing:
        raise tc.StageError(
            f"stage '{STAGE_ID}' is missing upstream artifacts "
            f"({', '.join(q.relative_to(extracted_root).as_posix() for q in missing)}) "
            "— prepare the tree first (client mode: run the pipeline "
            "without this stage; hostless smoke: tests/build_fixture_tree.py "
            f"--stage {STAGE_ID})", exit_code=3)

    logic_dir = extracted_root / LOGIC_DIR
    cp_dir = logic_dir / "course-progression"
    ec_dir = logic_dir / "economy"
    gr_dir = logic_dir / "grading"
    nd_dir = logic_dir / "needs-decay"
    for d in (cp_dir, ec_dir, gr_dir, nd_dir):
        d.mkdir(parents=True, exist_ok=True)

    ctx = run_l0(extracted_root, p, drift)
    build_id = ctx["build_id"]

    term_registry = {}
    with open(extracted_root / "relinks" / "i2_term_registry.jsonl",
              encoding="utf-8", newline="\n") as fh:
        for line in fh:
            if line.strip():
                row = json.loads(line)
                term_registry[int(row["termId"])] = row
    ctx["term_registry"] = term_registry

    audit = lu.NumericAudit(build_id)

    # -- L1..L4 ---------------------------------------------------------------
    run_l1_courses(ctx, p, drift, audit, cp_dir, problems)
    run_l1_modules(ctx, p, drift, audit, cp_dir, gaps)
    records = census_typed_blocks(extracted_root / "stubs")
    run_l1_prerequisites(ctx, p, drift, audit, cp_dir, records, gaps)
    run_l1_unlock_edges(ctx, p, drift, audit, cp_dir, records, gaps, problems)
    run_l1_attrition(ctx, p, drift, audit, cp_dir)
    run_l2(ctx, p, drift, audit, ec_dir, records, problems)
    xp_doc = run_l3(ctx, p, drift, audit, gr_dir, problems)
    run_l4(ctx, p, drift, audit, nd_dir)

    # -- L5 -------------------------------------------------------------------
    gaps.append(lu.make_gap_row(
        "grading", "missing-carrier", "xp-score-normalization",
        "XP→score normalization lives native/Burst; score->grade cut-offs "
        "are data (grading/xp-score-normalization.json)",
        "scoped native-analysis piece over GameAssembly.dll guided by "
        "script.json (orchestrator ruling R3 UPDATE)", build_id))
    gaps.append(lu.make_gap_row(
        "needs-decay", "missing-carrier", "student-core11-decay",
        "the student core-11 attribute decay carrier is genuinely absent "
        "(needs-decay/student-core11-decay.jsonl)",
        "native probe (G1/G8) or save-state diffing across time intervals "
        "(report G3)", build_id))
    gap_rows = lu.finalize_gaps(gaps)

    totals: Counter = Counter()
    guard_failures: list[str] = []

    def audit_one(rel: str, loader) -> None:
        try:
            doc = loader()
        except Exception as exc:  # noqa: BLE001
            guard_failures.append(f"{rel}: unreadable during audit "
                                  f"({type(exc).__name__}: {exc})")
            return
        res = audit.audit_artifact(
            rel, doc, lambda src: lu.load_source_document(extracted_root, src))
        for bucket in ("copied", "derivedArithmetic", "reconstructedFromCode",
                       "explicitNull"):
            totals[bucket] += res[bucket]
        guard_failures.extend(res["failures"])

    for rel, loader in _declared_documents():
        audit_one(rel, loader)
    numerics_audited = sum(totals[b] for b in
                           ("copied", "derivedArithmetic",
                            "reconstructedFromCode", "explicitNull"))

    if xp_doc.get("emittedNumbers") != []:
        problems.append(
            "xp-score-normalization.json emittedNumbers MUST be empty by "
            "law (R4)")
    core11 = [json.loads(l) for l in
              open(nd_dir / "student-core11-decay.jsonl", encoding="utf-8",
                   newline="\n") if l.strip()]
    if len(core11) != 11 or any(
            r.get("carrier") != "absent" or r.get("changeOverTime") is not None
            or r.get("initRange") is not None for r in core11):
        problems.append(
            "student-core11-decay.jsonl must carry 11 rows all "
            "carrier:'absent' with null rates — null is the LAW (R4)")
    if guard_failures:
        problems.extend(guard_failures)

    p.L5 = {
        "numericsAudited": numerics_audited,
        "numericsByEscapeHatch": {
            "copied": totals["copied"],
            "reconstructedFromCode": totals["reconstructedFromCode"],
            "derivedArithmetic": totals["derivedArithmetic"],
            "explicitNull": totals["explicitNull"],
        },
        "inventionGuardFailures": len(guard_failures),
        "gapRowsStanding": len(gap_rows),
        "gapRowsByFamily": {fam: sum(1 for g in gap_rows
                                     if g["family"] == fam)
                            for fam in sorted({g["family"]
                                               for g in gap_rows})},
    }
    log_util.write_jsonl(logic_dir / "_gaps.jsonl", gap_rows)

    # -- L6 -------------------------------------------------------------------
    input_inventory = _input_inventory(extracted_root, required)
    families = [
        {"title": "Course progression (`course-progression/`)",
         "tables": [
             {"artifact": "courses.jsonl",
              "measured": p.L1["courseRowsFull"]
              + p.L1["courseRowsMarketing"], "seed": 69,
              "joinKeys": "verbatim course ids"},
             {"artifact": "modules.jsonl", "measured": p.L1["moduleRows"],
              "seed": 319,
              "joinKeys": "module id → RoomType/Qualification PPtr"},
             {"artifact": "prerequisites.jsonl",
              "measured": p.L1["prerequisiteInstances"], "seed": 193,
              "joinKeys": "(carrierId, refKey)"},
             {"artifact": "prerequisite-nonmembers.jsonl",
              "measured": p.L1["nonmemberBlocks"], "seed": 27,
              "joinKeys": "(carrierId, refKey)"},
             {"artifact": "course-unlock-edges.jsonl",
              "measured": p.L1["unlockEdgesResolved"]
              + p.L1["unlockEdgesUnresolved"], "seed": 50,
              "joinKeys": "srcId → dstId via CAB/pathId"},
             {"artifact": "attrition.jsonl",
              "measured": p.L1.get("attritionGroups", 0), "seed": 4,
              "joinKeys": "Config_Campus field groups"},
         ],
         "notes": [
             "census across ALL stub kinds measures "
             f"{p.L1.get('prerequisiteInstancesAllKinds')} member blocks; "
             "the 193 seed scopes configs.jsonl (both probed, fresh wins)",
             "reconciliation leg (RF-2): relinksCoursePPTRRows "
             f"{p.L1['relinksCoursePPTRRows']} · unlockEdgeOverlapWithRelinks "
             f"{p.L1['unlockEdgeOverlapWithRelinks']} · "
             f"declaredScopeDifference {p.L1['declaredScopeDifference']} "
             f"{p.L1.get('declaredScopeDifferenceByClass', {})}",
         ]},
        {"title": "Economy (`economy/`)",
         "tables": [
             {"artifact": "money-taxonomy.json",
              "measured": p.L2["budgetTypeCount"], "seed": 28,
              "joinKeys": "BudgetType registry byte-match"},
             {"artifact": "finance-configs.jsonl",
              "measured": p.L2["financeConfigRows"], "seed": 30,
              "joinKeys": "Config_FinanceManager* ids"},
             {"artifact": "kudosh-ledger.jsonl",
              "measured": p.L2["kudoshSources"]
              + sum(p.L2["kudoshSinksByImplementer"].values()),
              "seed": "sources+sinks", "joinKeys": "carrier ids"},
             {"artifact": "research-costs.jsonl",
              "measured": p.L2["researchCostRows"], "seed": 209,
              "joinKeys": "metagame-node ids"},
         ],
         "notes": [
             "kudosh prices serialize on GameItemLiteDefinition.Kudosh / "
             "RoomLiteDefinition.Kudosh / LandscapeBrushDefinition._kudosh; "
             "the IKudoshUnlockable interface sits on the full definitions "
             "(dump.cs 824971 / 836761 / 992046)",
             f"{p.L2['liteRowsWithoutCosts']} ResearchProjectLiteDefinition "
             "rows are the DECLARED-EMPTY cost class — counted, never "
             "zero-filled",
         ]},
        {"title": "Grading (`grading/`)",
         "tables": [
             {"artifact": "grade-ladder.json",
              "measured": p.L3["gradeLadderRows"], "seed": 9,
              "joinKeys": "Grades[].Enum → EGrade.value"},
             {"artifact": "term-pass-grades.jsonl",
              "measured": p.L3["termPassGradeRows"], "seed": 75,
              "joinKeys": "(courseId, termIndex)"},
             {"artifact": "assessment-scoring.jsonl",
              "measured": p.L3["assessmentScoringRows"], "seed": 28,
              "joinKeys": "courseId (harvest-direct)"},
             {"artifact": "xp-score-normalization.json", "measured": 1,
              "seed": 1, "joinKeys": "—"},
         ],
         "notes": [
             "MEASURED SHAPE NOTE: TermDefinition.PassGrade is `public int` "
             "in code (dump.cs ~840152) and measures 40 on every row — "
             "outside the EGrade domain; passGrade therefore emits null and "
             "passGradeValue carries the verbatim int (mapping 40 to a "
             "grade NAME would be an invented rule, R4)",
         ]},
        {"title": "Needs & decay (`needs-decay/`)",
         "tables": [
             {"artifact": "staff-decay.jsonl",
              "measured": p.L4["staffDecayRows"], "seed": 30,
              "joinKeys": "(staffId, attribute)"},
             {"artifact": "student-decay.jsonl",
              "measured": p.L4["studentDecayRows"] + p.L4["clubDecayRows"],
              "seed": "6+7", "joinKeys": "studentTypeId/component"},
             {"artifact": "student-core11-decay.jsonl",
              "measured": p.L4["core11LedgerRows"], "seed": 11,
              "joinKeys": "EAttribute members"},
             {"artifact": "interactions.jsonl",
              "measured": p.L4["interactionRows"], "seed": 630,
              "joinKeys": "verbatim interaction ids"},
         ],
         "notes": [
             f"studentDecayRawCoverage {p.L4['studentDecayRawCoverage']} — "
             "a MEASURED COUNTER printed beside the dataset table, NEVER a "
             "gap row (arbiter-piece04-spec Part 2/R4)",
         ]},
    ]
    unproven_register = [
        {"id": "grading/xp-score-normalization.json",
         "text": "XP accumulation → assessment score normalization feeding "
                 "GetGrade(score) — status UNPROVEN-NATIVE, emittedNumbers "
                 "[] by law; site presents bands as client data and the "
                 "step below them as unknown."},
        {"id": "needs-decay/student-core11-decay.jsonl",
         "text": "student core-11 attribute decay carrier absent everywhere "
                 "in the corpus; 11 null-carrier rows keep the narrowness "
                 "in the record (the staff side IS data-recoverable above)."},
    ]
    logic_md = lu.render_logic_md(build_id, input_inventory, families,
                                  unproven_register, gap_rows, drift, {
                                      "studentDecayRawCoverage":
                                          p.L4["studentDecayRawCoverage"]})
    log_util.atomic_write_text(logic_dir / "LOGIC.md", logic_md)

    digests = {}
    for rel in log_util.stage_outputs(STAGE_ID):
        fpath = extracted_root / rel
        if fpath.is_file():
            digests[rel] = log_util.sha256_file(fpath)[:8]
    p.L6 = {"logicMdBytes": len(logic_md.encode("utf-8")), "digests": digests}

    lines = [
        ("- exitCode: 0" if not problems and not gap_rows
         else ("- exitCode: 2 (completed-with-ledger)" if not problems
               else f"- exitCode: 1 ({len(problems)} problem(s))")),
        "- L0: " + log_util.dump_jsonl_row(p.L0).rstrip(),
        "- L1: " + log_util.dump_jsonl_row(p.L1).rstrip(),
        "- driftProbes: "
        + log_util.dump_jsonl_row(p.drift_probes).rstrip(),
        "- L2: " + log_util.dump_jsonl_row(p.L2).rstrip(),
        "- L3: " + log_util.dump_jsonl_row(p.L3).rstrip(),
        "- L4: " + log_util.dump_jsonl_row(p.L4).rstrip(),
        "- L5: " + log_util.dump_jsonl_row(p.L5).rstrip(),
        "- L6: " + log_util.dump_jsonl_row(
            {"digestCount": len(digests),
             "logicMdBytes": p.L6["logicMdBytes"]}).rstrip(),
        ("- LEDGER-CONTRIBUTORS (exit 2): "
         + "; ".join(g["gapId"] for g in gap_rows)) if gap_rows
        else "- LEDGER-CONTRIBUTORS: none",
        * [f"- {d}" for d in drift],
        * [f"- PROBLEM: {pr}" for pr in problems],
    ]
    log_util.append_run_section(extracted_root, STAGE_ID, lines)

    print(f"[{STAGE_ID}] courses={p.L1['courseRowsFull']}+"
          f"{p.L1['courseRowsMarketing']} modules={p.L1['moduleRows']} "
          f"prereqs={p.L1['prerequisiteInstances']} "
          f"nonmembers={p.L1['nonmemberBlocks']} edges="
          f"{p.L1['unlockEdgesResolved']}+{p.L1['unlockEdgesUnresolved']}")
    print(f"[{STAGE_ID}] reconciliation relinks="
          f"{p.L1['relinksCoursePPTRRows']} overlap="
          f"{p.L1['unlockEdgeOverlapWithRelinks']} scopeDiff="
          f"{p.L1['declaredScopeDifference']}")
    print(f"[{STAGE_ID}] research={p.L2['researchCostRows']} "
          f"kudoshSources={p.L2['kudoshSources']} sinks="
          f"{sum(p.L2['kudoshSinksByImplementer'].values())} "
          f"interactions={p.L4['interactionRows']}")
    print(f"[{STAGE_ID}] guard audited={p.L5['numericsAudited']} "
          f"hatches={log_util.dump_jsonl_row(p.L5['numericsByEscapeHatch']).rstrip()} "
          f"failures={p.L5['inventionGuardFailures']} gaps={len(gap_rows)}")
    for d in drift:
        print(f"[{STAGE_ID}] {d}", file=sys.stderr)
    for pr in problems[:20]:
        print(f"[{STAGE_ID}] PROBLEM: {pr}", file=sys.stderr)
    if problems:
        return 1
    if gap_rows:
        return 2
    return 0


def _declared_documents():
    """(relpath, lazy loader) for every emitted JSON/JSONL the invention
    guard re-opens from disk."""
    docs = []
    base = LOGIC_DIR

    def json_doc(rel):
        root = EXTRACTED_ROOT
        return (rel, lambda: json.loads(
            (root / rel).read_text(encoding="utf-8")))

    def jsonl_doc(rel):
        root = EXTRACTED_ROOT
        def load():
            with open(root / rel, encoding="utf-8", newline="\n") as fh:
                return [json.loads(l) for l in fh if l.strip()]
        return (rel, load)

    docs.append(json_doc(f"{base}/course-progression/"
                         "prerequisite-taxonomy.json"))
    for name in ("courses", "modules", "prerequisites",
                 "prerequisite-nonmembers", "course-unlock-edges",
                 "attrition"):
        docs.append(jsonl_doc(f"{base}/course-progression/{name}.jsonl"))
    docs.append(json_doc(f"{base}/economy/money-taxonomy.json"))
    for name in ("finance-configs", "kudosh-ledger", "research-costs"):
        docs.append(jsonl_doc(f"{base}/economy/{name}.jsonl"))
    docs.append(json_doc(f"{base}/grading/grade-ladder.json"))
    docs.append(json_doc(f"{base}/grading/xp-score-normalization.json"))
    for name in ("term-pass-grades", "assessment-scoring"):
        docs.append(jsonl_doc(f"{base}/grading/{name}.jsonl"))
    for name in ("staff-decay", "student-decay", "student-core11-decay",
                 "interactions"):
        docs.append(jsonl_doc(f"{base}/needs-decay/{name}.jsonl"))
    return docs


EXTRACTED_ROOT = None   # bound in run() before any audit loads


def _input_inventory(extracted_root: Path, required) -> list[tuple[str, int]]:
    inv = []
    seen = set()
    for q in required:
        rel = q.relative_to(extracted_root).as_posix()
        if rel in seen:
            continue
        seen.add(rel)
        if q.is_file():
            inv.append((rel, q.stat().st_size))
        elif q.is_dir():
            size = sum(x.stat().st_size for x in sorted(q.rglob("*"))
                       if x.is_file())
            inv.append((rel + "/", size))
    inv.sort()
    return inv


def main(argv=None) -> int:
    log_util.bootstrap_console()
    global EXTRACTED_ROOT
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
        EXTRACTED_ROOT = root
        game_root = None
        if args.game_dir:
            game_root = tc.resolve_game_root(args.game_dir)
        return run(game_root, root)
    except tc.StageError as exc:
        if root is not None:
            log_util.append_failure_section(root, STAGE_ID, exc.exit_code,
                                            [str(exc)])
        print(f"[{STAGE_ID}] ERROR: {exc}", file=sys.stderr)
        return exc.exit_code


if __name__ == "__main__":
    sys.exit(main())
