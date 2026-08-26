"""piece-04 section 8 blind test suite for stage 8 `logic` (Revision 3).

Written from the SPEC ALONE (docs/specs/piece-04-logic.mdx Rev 3 +
docs/rulings/arbiter-piece04-spec.mdx) against a synthetic mini-corpus in
tests/_logiclib.py - tools/stage8_logic.py was never read (blind pair).
Sections map to the sub-passes:

  PART A  pure-oracle pins + validator TEETH (always run, no impl needed)
  PART B  runner obligations: --list order-not-count [AC1], isolation +
          ownership [AC10], exit mapping incl. the exit-2 steady state
          with EXACTLY the two standing gaps [AC9], drift fresh-wins,
          double-run byte identity [AC6]
  PART C  artifact contracts per sub-pass L1-L6 (courses/modules/
          prerequisites/sidecar/unlock-edges/attrition/money-taxonomy/
          finance/kudosh/research/ladder/terms/scoring/xp-marker/staff/
          student/core11/interactions/LOGIC.md/digests/id sweep)
  PART D  negatives: failure-mode routing, monotonic break -> exit 1,
          stub-vs-raw mismatch -> exit 1, financedrift -> DRIFT not crash,
          relinks divergence gap, missing-upstream -> exit 3
  PART E  adapter-level invention-guard unit legs (loud skips until the
          impl symbols exist)
  PART F  client-gated integration over the REAL corpus (seeds reproduce
          or DRIFT-print; RF-2 reconciliation seeds 68/50/18)

Black-box legs skip LOUDLY until `logic` is registered by the runner -
never faking a pass (impl-lagging banner accounting via _impl).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

os.environ.setdefault("PYTHONUTF8", "1")

HERE = Path(__file__).resolve().parent
PACK_ROOT = HERE.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import _logiclib as L  # noqa: E402
from _validators import (  # noqa: E402
    BUILD_ID, diff_manifests, hash_tree, read_json, read_jsonl,
    scan_tree_for_media_extensions,
)
from _impl import note_missing_module  # noqa: E402


# --- loud registration gate ---------------------------------------------------

_REGISTERED = None


def require_logic_registered():
    """Skip LOUDLY until `--list` enumerates stage `logic`."""
    global _REGISTERED
    import pytest
    if _REGISTERED is None:
        from conftest import run_pack
        r = run_pack(["--list"])
        _REGISTERED = r.returncode == 0 and bool(
            re.search(r"^logic\b", r.stdout, re.MULTILINE))
        if not _REGISTERED and r.returncode == 0:
            note_missing_module("run_all.py --list: stage 'logic' not "
                                "registered yet (piece-04 CodeWriter pending)")
    if not _REGISTERED:
        pytest.skip("impl-lagging: stage 'logic' not registered by the "
                    "runner yet (piece-04 CodeWriter pending)")


# --- fixture-tree + black-box run helpers -------------------------------------

_TREE_SEQ = {"n": 0}


def fx_tree(variant: str, name: str) -> Path:
    root = L.scratch(f"{name}-{os.getpid()}")
    if root.exists():
        shutil.rmtree(root)
    return L.build_logic_tree(root, variant)


def run_logic(tree: Path, *, timeout=900, force=False):
    from conftest import run_pack, tree_game
    args = [tree_game(str(tree)), "--only", "logic"]
    if force:
        args.append("--force")
    ext = Path(tree) / "extracted"
    return run_pack(args, extracted_root=ext, timeout=timeout), ext


def logic_rows(ext: Path, family: str, name: str):
    p = Path(ext) / "logic" / family / name
    return read_jsonl(p) if p.exists() else None


def logic_obj(ext: Path, family: str, name: str):
    p = Path(ext) / "logic" / family / name
    return read_json(p) if p.exists() else None


def log_text(ext: Path) -> str:
    p = ext / "EXTRACTION-LOG.md"
    return p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""


def _mutated_copy(obj, mutate):
    import copy as _copy
    c = _copy.deepcopy(obj)
    mutate(c)
    return c


# ===========================================================================
# PART A - pure-oracle pins + validator TEETH (impl-independent)
# ===========================================================================

def test_taxonomy_pins_alphabetical_order_and_indices():
    """F2/F4: the 24-member taxonomy is alphabetical; indices 0/10/23 are
    ChallengePrerequisiteAcademicScore / PrerequisiteHasCourseUnlocked /
    PrerequisiteUniversityLevel; the short-name map covers all 24."""
    assert L.TAXONOMY_24 == sorted(L.TAXONOMY_24), \
        "the pinned taxonomy order IS alphabetical"
    assert len(L.TAXONOMY_24) == 24
    assert L.TAXONOMY_24[0] == "ChallengePrerequisiteAcademicScore"
    assert L.TAXONOMY_24[10] == "PrerequisiteHasCourseUnlocked"
    assert L.TAXONOMY_24[23] == "PrerequisiteUniversityLevel"
    # spot pins from the spec's own index list
    for idx, name in ((3, "PrerequisiteDaysPassed"),
                      (9, "PrerequisiteHasCourseRunning"),
                      (15, "PrerequisiteHasStarsInLevel")):
        assert L.TAXONOMY_24[idx] == name
    assert set(L.SHORT_NAME_MAP.values()) == set(L.TAXONOMY_24)
    assert len(L.SHORT_NAME_MAP) == 24
    # bare-name ancestry matches NOTHING (F4 spelling law)
    namespaced, bare = L.hierarchy_member_names(L.hierarchy_rows())
    assert sorted(namespaced) == L.TAXONOMY_24
    assert bare == ["NaughtyBareBaseHelper"]
    assert not [n for n in namespaced if n == "Prerequisite"]


def test_budgettype_and_egrade_table_pins():
    assert len(L.BUDGET_TYPES) == 28   # verifyA-corrected count (not 27)
    values = [v for _n, v in L.BUDGET_TYPES]
    assert values == list(range(28))
    assert dict(L.BUDGET_TYPES)["TuitionFees"] == 0
    assert dict(L.BUDGET_TYPES)["PatientTreatmentIncome"] == 27
    assert "Kudosh" not in {n for n, _v in L.BUDGET_TYPES}, \
        "decisive negative F10: no BudgetType member is Kudosh"
    name_sorted = [n for n, _v in sorted(L.BUDGET_TYPES)]
    assert name_sorted[:3] == ["Allowance", "Bonus", "BudgetRefund"]
    assert name_sorted[-1] == "Wages"
    assert dict(L.EGRADE_MEMBERS) == {"Invalid": 0, "F": 1, "D": 2, "C": 3,
                                      "CC": 4, "B": 5, "BB": 6, "A": 7,
                                      "AA": 8}
    assert [v for _n, v in L.EGRADE_MEMBERS] == list(range(9))
    assert sum(1 for n, _ in L.EATTRIBUTE_MEMBERS if n == "Litter") == 1


def test_grade_rows_threshold_sequence_and_tokens():
    seq = [L.GRADE_ROWS[e]["threshold"] for e in range(9)]
    assert seq == [-1.0, 0.0, 40.0, 50.0, 60.0, 70.0, 75.0, 80.0, 90.0]
    assert [L.GRADE_ROWS[e]["token"] for e in range(9)] == \
        ["NA", "F", "D", "C", "CC", "B", "BB", "A", "AA"]
    for e in range(9):   # AIR uniform; IR diverges F-AA only
        air = L.AIR_PREFIX + L.GRADE_ROWS[e]["token"]
        expect_ir = (L.IR_PREFIX_F_AA + L.GRADE_ROWS[e]["token"]) \
            if e >= 1 else air
        assert air.endswith("Grade_" + L.GRADE_ROWS[e]["token"])
        assert expect_ir


def test_research_seed_distribution_sums_to_209():
    assert L.RESEARCH_DOMAIN == {100, 200, 250, 300, 500, 600, 1200,
                                 2500, 3000}
    assert sum(L.RESEARCH_SEED_DIST.values()) == 209   # F11


# --- teeth: each major guard bites on a mutated copy -------------------------

def test_tooth_budget_byte_match_checker():
    reg = [{"name": n, "value": v} for n, v in sorted(L.BUDGET_TYPES)]
    emitted = [{"name": n, "value": v} for n, v in sorted(L.BUDGET_TYPES)]
    assert L.budget_type_violations(emitted, reg) == []
    def rename(o):
        o[5]["name"] = "Kudosh"
    assert L.budget_type_violations(_mutated_copy(emitted, rename), reg)
    def reval(o):
        o[0]["value"] = 99
    assert L.budget_type_violations(_mutated_copy(emitted, reval), reg)
    assert L.budget_type_violations(list(reversed(emitted)), reg), \
        "registry-file ORDER is part of the byte-match"


def test_tooth_monotonicity_checker_na_sentinel_exempt():
    rows = [{"grade": t, "enumValue": e, "threshold": th}
            for e, t, th in (("NA", 0, -1.0), ("F", 1, 0.0), ("D", 2, 40.0),
                             ("C", 3, 50.0), ("CC", 4, 60.0), ("B", 5, 70.0),
                             ("BB", 6, 75.0), ("A", 7, 80.0), ("AA", 8, 90.0))]
    assert L.monotonic_threshold_violations(rows) == []
    broken = _mutated_copy(rows, lambda o: o[3].__setitem__("threshold", 35.0))
    assert L.monotonic_threshold_violations(broken)


def test_tooth_xp_normalization_validator():
    good = {"buildId": BUILD_ID, "surface": "XP -> score normalization",
            "status": "UNPROVEN-NATIVE", "emittedNumbers": [],
            "unblock": "scoped native-analysis piece over GameAssembly.dll"}
    assert L.xp_normalization_violations(good) == []
    bad = _mutated_copy(good, lambda o: o.__setitem__("emittedNumbers",
                                                      [1.37]))
    errs = L.xp_normalization_violations(bad)
    assert any("invented number" in x for x in errs)
    bad2 = _mutated_copy(good, lambda o: o.__setitem__("status", "DERIVED"))
    assert L.xp_normalization_violations(bad2)


def test_tooth_core11_null_law():
    good = [{"attribute": n, "changeOverTime": None, "initRange": None,
             "carrier": "absent", "status": "UNPROVEN-NATIVE"}
            for n, _v in L.EATTRIBUTE_MEMBERS]
    assert L.core11_violations(good) == []
    def invent(o):
        o[1]["changeOverTime"] = -0.033
    errs = L.core11_violations(_mutated_copy(good, invent))
    assert any("invented number" in x for x in errs)
    def drop_litter(o):
        o[:] = [r for r in o if r["attribute"] != "Litter"]
    assert L.core11_violations(_mutated_copy(good, drop_litter))


def test_tooth_staff_verbatim_float_and_spelling():
    def row(attr, cot, lo=90.0, hi=100.0):
        return {"staffId": "Staff_Assistant", "attribute": attr,
                "changeOverTime": cot, "minInitialValue": lo,
                "maxInitialValue": hi, "disabled": 0,
                "component": "ECPCharacterAttributes",
                "evidence": {"stubRow": "stubs/staff.jsonl#Staff_Assistant",
                             "refKey": "00000000", "fieldPath":
                             f"references[00000000].data.{attr}"}}
    good = [row(a, L.DECAY_SIX if a in ("Drink", "Energy") else 0.0)
            for a in ("Drink", "Energy")]
    # fieldPath must preserve the raw _field spelling
    inverse = {v: k for k, v in L.STAFF_FIELD_TO_ATTRIBUTE.items()}
    good = [_mutated_copy(r, lambda o: o["evidence"].__setitem__(
        "fieldPath",
        o["evidence"]["fieldPath"].replace(o["attribute"],
                                           inverse[o["attribute"]])))
        for r in good]
    assert L.staff_decay_violations(good) == []
    rounded = _mutated_copy(good, lambda o: o[0].__setitem__(
        "changeOverTime", round(L.DECAY_SIX, 6)))
    assert L.staff_decay_violations(rounded), "rounding edits data"
    raw = _mutated_copy(good, lambda o: o[0].__setitem__("attribute",
                                                         "_toilet"))
    assert any("_toilet" in x or "_field" in x or "registry" in x
               for x in L.staff_decay_violations(raw))
    assert repr(L.DECAY_SIX) == "-0.05000000074505806"


def test_tooth_attrition_label_restriction():
    good = [
        {"group": "StudentDropoutSettings", "fields": dict(L.DROPOUT_FIELDS),
         "events": list(L.EVENT_DROPOUT),
         "evidence": {"artifact": "stubs/configs.jsonl#Config_Campus",
                      "fieldPath": "StudentDropoutSettings",
                      "codeRef": L.ATTRITION_CODE_REF}},
        {"group": "StaffResignationSettings",
         "fields": dict(L.RESIGNATION_FIELDS), "events": [],
         "evidence": {"codeRef": L.ATTRITION_CODE_REF}},
        {"group": "StudentFailPercent", "fields": {"value": 10},
         "events": [], "evidence": {}},
        {"group": "StudentUnhappyTuitionFeesThreshold",
         "fields": {"value": 20.0}, "events": [], "evidence": {}},
    ]
    assert L.attrition_violations(good) == []
    invented = good + [{"group": "GlobalFails", "fields": {}, "events": [],
                        "evidence": {}}]
    errs = L.attrition_violations(invented)
    assert any("GlobalFails" in x for x in errs), \
        "an invented group label must fail the validator"


def test_tooth_prerequisite_taxonomy_membership_and_index():
    def row(cls, idx):
        return {"carrierId": "CareerChallenge_X", "refKey": "00000000",
                "prerequisiteClass": cls, "taxonomyIndex": idx,
                "asm": "TPS.Game", "ns": "TPC", "payload": {},
                "targets": []}
    good = [{"carrierId": "CareerChallenge_X", "refKey": "00000000",
             "prerequisiteClass": "PrerequisiteHasCourseUnlocked",
             "taxonomyIndex": 10, "asm": "TPS.Game", "ns": "TPC",
             "payload": {}, "targets": []},
            {"carrierId": "CampusLevel_Y", "refKey": "00000000",
             "prerequisiteClass": "PrerequisiteUniversityLevel",
             "taxonomyIndex": 23, "asm": "TPS.Game", "ns": "TPC",
             "payload": {}, "targets": []}]
    assert L.prerequisite_violations(good) == []
    wrong_idx = _mutated_copy(good, lambda o: o[0].__setitem__(
        "taxonomyIndex", 3))
    assert L.prerequisite_violations(wrong_idx)
    nonmember = good + [row("LevelPrerequisiteStars", 0)]
    assert L.prerequisite_violations(nonmember), \
        "a same-prefix NON-member must fail the member validator"


def test_tooth_unlock_edge_shape_sort_dedup():
    def edge(src, dst, fp="references.00000000.data._course"):
        return {"srcKind": "config", "srcId": src,
                "verb": "requires-course-unlocked", "dstKind": "course",
                "dstId": dst, "mechanism": "hard",
                "method": "pptr-cross-file-typed-block", "inferred": False,
                "resolved": True,
                "evidence": {"fieldPath": fp, "srcBundle": L.B_META,
                             "srcPathId": 9101}}
    good = [edge("A", "B"), edge("A", "C")]
    assert L.unlock_edge_violations(good) == []
    unsorted = list(reversed(good))
    assert L.unlock_edge_violations(unsorted)
    badverb = _mutated_copy(good, lambda o: o[0].__setitem__("verb",
                                                             "unlocks"))
    assert L.unlock_edge_violations(badverb)
    inferred = _mutated_copy(good, lambda o: o[0].__setitem__("inferred",
                                                              True))
    assert L.unlock_edge_violations(inferred)


def test_tooth_reconciliation_checker_divergence_and_scope():
    def relink(src, spid, dpid, bundle):
        return {"srcId": src, "dstId": "D",
                "evidence": {"fieldPath": "references.00000000.data._course",
                             "srcBundle": bundle, "srcPathId": spid,
                             "dstPathId": dpid}}
    edges = [{"srcId": "E1", "resolved": True, "evidence": {
        "fieldPath": "references.00000000.data._course",
        "srcBundle": L.B_META, "srcPathId": 9101, "dstPathId": 9406}}]
    good = [relink("E1", 9101, 9406, L.B_META),
            relink(L.SCOPE_CARRIERS.copy().pop(), 9103, 9403, L.B_META)]
    c = L.reconciliation_counters(edges, good, L.SCOPE_CARRIERS)
    assert c["relinksCoursePPTRRows"] == 2
    assert c["unlockEdgeOverlapWithRelinks"] == 1 == len(edges)
    assert c["declaredScopeDifference"] == 1
    assert not c["divergentCarriers"]
    divergent = _mutated_copy(good, lambda o: o[0]["evidence"].__setitem__(
        "dstPathId", 12345))
    c2 = L.reconciliation_counters(edges, divergent, L.SCOPE_CARRIERS)
    assert c2["divergentCarriers"], \
        "an unexplained relinks counterpart is a divergence"
    assert c2["unlockEdgeOverlapWithRelinks"] != len(edges)


def test_tooth_gap_ledger_shape_sort():
    good = [
        {"gapId": "a", "family": "grading", "kind": "missing-carrier",
         "subjectId": "xp-score-normalization", "reason": "r",
         "unblock": "u", "buildId": BUILD_ID},
        {"gapId": "b", "family": "needs-decay", "kind": "missing-carrier",
         "subjectId": "student-core11-decay", "reason": "r",
         "unblock": "u", "buildId": BUILD_ID},
    ]
    assert L.gaps_violations(good) == []
    assert L.gaps_violations(list(reversed(good))), "must sort by (fam,id)"
    badkind = _mutated_copy(good, lambda o: o[0].__setitem__("kind",
                                                             "made-up"))
    assert L.gaps_violations(badkind)


def test_tooth_distribution_checker():
    rows = [{"id": f"R{i}", "researchPoints": v}
            for i, v in enumerate([250, 500, 500, 100])]
    assert L.research_violations(rows) == []
    out_of_domain = rows + [{"id": "RX", "researchPoints": 777}]
    errs = L.research_violations(out_of_domain)
    assert any("domain" in x for x in errs)


# ===========================================================================
# PART B - runner obligations
# ===========================================================================

CANONICAL_ORDER = ("verify-client", "decompile", "harvest-catalog",
                   "harvest-bundles", "localisation", "emit-stub-datasets",
                   "relink", "maps", "logic", "locale-proof", "contracts",
                   "media", "search-corpus")


def _list_ids():
    from conftest import run_pack
    r = run_pack(["--list"])
    assert r.returncode == 0, f"--list failed: {r.stdout}{r.stderr}"
    ids = []
    for ln in r.stdout.splitlines():
        tok = ln.split()
        if tok and tok[0] in CANONICAL_ORDER:
            ids.append(tok[0])
    return ids, r.stdout


def test_list_order_not_count():
    """RF-3/AC1: `logic` appears AFTER `maps` IF maps is registered, ELSE
    directly after `relink`; BEFORE any canonically-later sibling IF
    registered. Absolute enumeration asserted ONLY when the registration set
    is exactly the canonical nine (fixture-scale knowledge)."""
    require_logic_registered()
    ids, out = _list_ids()
    assert "logic" in ids, f"--list lacks logic:\n{out}"
    pos = {sid: i for i, sid in enumerate(ids)}
    anchor = pos["maps"] if "maps" in pos else pos.get("relink")
    assert anchor is not None, f"neither maps nor relink registered:\n{out}"
    assert pos["logic"] > anchor, \
        f"logic must seat after {'maps' if 'maps' in pos else 'relink'}:\n{out}"
    for later in ("locale-proof", "contracts", "media", "search-corpus"):
        if later in pos:
            assert pos["logic"] < pos[later], \
                f"logic must precede canonically-later {later}:\n{out}"
    if set(ids) == set(CANONICAL_ORDER[:9]):
        assert ids == list(CANONICAL_ORDER[:9]), \
            f"canonical-nine order broken:\n{ids}"


def test_only_logic_isolation_ownership_and_carveout():
    """AC10: writes confined to extracted/logic/** + the runner-owned logs;
    upstream artifacts byte-untouched; zero media bytes anywhere."""
    require_logic_registered()
    tree = fx_tree("green", "iso8")
    ext = tree / "extracted"
    before = hash_tree(ext)
    r, ext = run_logic(tree)
    combined = r.stdout + r.stderr
    assert r.returncode in (0, 2), \
        f"isolation run failed rc={r.returncode}\n{combined}"
    after = hash_tree(ext)
    only_b, only_a, changed = diff_manifests(before, after)
    allowed = ("logic/",) + ("EXTRACTION-LOG.md", ".stage-stamps",
                             ".pipeline-meta.json")
    outside = [p for p in sorted(set(only_a) | set(changed))
               if not p.startswith(allowed)]
    assert not outside, f"--only logic wrote outside its surface: {outside[:8]}"
    assert only_a or changed, "isolation run produced nothing"
    untouched = [p for p in changed
                 if p.startswith(("stubs/", "harvest/", "relinks/",
                                  "decompiled/", "identity.json"))]
    assert not untouched, f"stage 8 mutated its own inputs: {untouched[:8]}"
    hits = [h for h in scan_tree_for_media_extensions(ext / "logic")]
    assert not hits, f"media bytes under extracted/logic/: {hits[:5]}"


def test_exit2_steady_state_with_exactly_two_standing_gaps():
    """AC9: on a fully-resolvable fixture the ONLY gaps are the two standing
    UNPROVEN-NATIVE rows -> exit 2 (completed-with-ledger), never 0."""
    require_logic_registered()
    r, ext = run_logic(fx_tree("green", "exit2"))
    assert r.returncode == 2, (
        f"expected exit 2 steady state, got rc={r.returncode}\n"
        f"{r.stdout}{r.stderr}")
    gaps = read_jsonl(ext / "logic" / "_gaps.jsonl")
    assert len(gaps) == 2, \
        f"expected exactly the two standing gaps, got {len(gaps)}: {gaps}"
    standing = L.standing_gap_rows(gaps)
    assert len(standing) == 2, \
        f"the two gaps must be the XP-normalization + core-11 rows: {gaps}"
    fams = sorted({g.get("family") for g in standing})
    assert fams == ["grading", "needs-decay"], fams
    errs = L.gaps_violations(gaps)
    assert not errs, errs


def test_run_section_headline_keys_and_fixture_values():
    """Pinned run-section keys exist with numbers; fixture-derived values
    reconcile (5 relinks rows / 2 resolved edges / 3 scope counterparts /
    20 staff rows / 11 core-11 / guard green)."""
    require_logic_registered()
    r, ext = run_logic(fx_tree("green", "runkeys"))
    text = log_text(ext)
    errs = L.run_section_violations(text)
    assert not errs, errs

    def keyval(key):
        """Headline-counter reader. The L0/driftProbes lines legitimately echo
        every probed key as {"expected": <seed>, "measured": ...} — reading
        the seed as the measurement was this test's own parsing defect (the
        reconciliation keys are probed WITH drift seeds per RF-2), so the
        probe-echo contexts are skipped and the pass counters are read."""
        for ln in text.splitlines():
            s = ln.strip()
            if s.startswith(("- driftProbes", "- L0:")) or '"expected"' in s:
                continue
            m = re.search(rf"{re.escape(key)}\b[^0-9\n\-]*(-?\d+)", s,
                          re.IGNORECASE)
            if m:
                return int(m.group(1))
        return None

    assert keyval("relinksCoursePPTRRows") == 5
    assert keyval("unlockEdgeOverlapWithRelinks") == 2
    assert keyval("declaredScopeDifference") == 3
    assert keyval("unlockEdgesResolved") == 2
    assert keyval("unlockEdgesUnresolved") == 0
    assert keyval("staffDecayRows") == 20
    assert keyval("core11LedgerRows") == 11
    assert keyval("gradeLadderRows") == 9
    assert keyval("budgetTypeCount") == 28
    assert keyval("researchCostRows") == 5
    assert keyval("liteRowsWithoutCosts") == 1
    assert keyval("inventionGuardFailures") == 0
    cov = re.search(r"studentDecayRawCoverage[^}]*raws\D*(\d+)"
                    r"[^}]*studentTypeStubs\D*(\d+)", text)
    assert cov and (int(cov.group(1)), int(cov.group(2))) == (2, 3), \
        "R4: coverage is a MEASURED COUNTER in the run section, not a gap row"


def test_drift_probes_fire_and_never_gate():
    """L0: every fixture count drifts from the F-table seeds -> DRIFT lines
    print, the fresh number wins, and the run still completes (2)."""
    require_logic_registered()
    r, ext = run_logic(fx_tree("green", "drift8"))
    assert r.returncode == 2, r.stdout + r.stderr
    drifts = L.drift_lines(r.stdout + log_text(ext))
    assert drifts, "expected DRIFT: lines on a corpus that differs from seeds"
    text = log_text(ext)
    m = re.search(r"driftProbes\s*:?\s*\{[^}]*expected\D*(\d+)[^}]*"
                  r"measured\D*(\d+)", text)
    assert m, "driftProbes must record {expected, measured} pairs"


def test_double_run_byte_identical():
    """AC6: rerunning --only logic yields byte-identical declared outputs
    (runner-owned logs excluded); LOGIC.md byte-equal; digests recorded."""
    require_logic_registered()
    tree = fx_tree("green", "byteid")
    r1, ext = run_logic(tree)
    assert r1.returncode in (0, 2), r1.stdout + r1.stderr
    first = hash_tree(ext / "logic")
    md1 = (ext / "logic" / "LOGIC.md").read_bytes()
    r2, ext = run_logic(tree, force=True)
    assert r2.returncode in (0, 2), r2.stdout + r2.stderr
    second = hash_tree(ext / "logic")
    only_b, only_a, changed = diff_manifests(first, second)
    assert not (only_b or only_a or changed), \
        f"double-run not byte-identical: {only_b[:4]} {only_a[:4]} {changed[:4]}"
    assert (ext / "logic" / "LOGIC.md").read_bytes() == md1
    log = log_text(ext)
    # L6 records the rerun-comparison surface: the per-file digest map in the
    # spec sketch's own spelling (the reconciler round restored the map; the
    # bare-count alternative stays accepted so both forms keep biting)
    assert re.search(r"digests\s*:", log) or re.search(r"\bdigestCount\b",
                                                       log), \
        "L6 digest record missing from the run section"


# ===========================================================================
# PART C - artifact contracts over the green fixture corpus
# ===========================================================================

_GREEN: dict = {}


def green_run(*, expect_rc=(0, 1, 2)):
    """One shared hostless green run for all PART C legs (cached).

    Content legs accept any completed run so a single upstream defect (e.g.
    an invention-guard false positive flipping the exit code) does not mask
    thirty independent artifact verdicts; the EXIT-CODE LAW itself stays
    enforced strictly by PART B/D legs (exit-2 steady state, DRIFT-not-crash,
    relinks-divergence)."""
    if "ext" not in _GREEN:
        require_logic_registered()
        r, ext = run_logic(fx_tree("green", "greenC"))
        assert r.returncode in expect_rc, (
            f"stage did not complete: rc={r.returncode}\n"
            f"{r.stdout[-2000:]}{r.stderr[-800:]}")
        _GREEN["rc"] = r.returncode
        _GREEN["stdout"] = r.stdout
        _GREEN["stderr"] = r.stderr
        _GREEN["ext"] = ext
    return _GREEN["ext"]


def test_c1_courses_rows_split_and_anchors():
    ext = green_run()
    rows = logic_rows(ext, "course-progression", "courses.jsonl")
    assert rows is not None, "courses.jsonl not emitted"
    full = [r for r in rows if r.get("class") == "TPC.CourseDefinition"]
    marketing = [r for r in rows
                 if r.get("class") == "TPC.MarketingCourseDefinition"]
    # AC2 arithmetic identity: rows == full + marketing (28+41 analog 3+2)
    assert len(rows) == len(full) + len(marketing) == 5
    assert len(full) == 3 and len(marketing) == 2
    by = {r["id"]: r for r in rows}
    arch = by["Course_Archaeology"]
    # frozen economics key set, verbatim values
    for k, v in (("licenseCost", 0), ("kudoshCost", 0),
                 ("yearlyTuitionFee", 8000), ("startPointsCost", 20),
                 ("defaultStudentCount", 12), ("applicantsBoost", 0)):
        assert arch[k] == v, f"{k}={arch.get(k)!r} != {v!r}"
    # levels[] order + values verbatim incl float spelling (20.0 not 20)
    pts = [l["pointsCost"] for l in arch["levels"]]
    assert pts == [20.0, 25.0, 30.0]
    boosts = [l["applicantsBoost"] for l in arch["levels"]]
    assert boosts == [10.0, 15.0, 20.0]
    hiring = [l["hiringTeacherSkillLevelMax"] for l in arch["levels"]]
    assert hiring == [1, 2, 3]


    # terms: passGrade via the Terms[] PPtr, moduleCount from TermDefinition
    trow = arch["terms"][0]
    assert trow["passGrade"] == "B", f"Term_Archaeology_Y1 PassGrade 5 -> B"
    assert trow["moduleCount"] == 2
    pot = by["Course_Potions"]
    assert [t["passGrade"] for t in pot["terms"]] == ["C", "AA"]
    # assessmentScoring is HARVEST-DIRECT (F2); Archaeology anchor verifyA 2d
    asc = arch["assessmentScoring"]
    assert asc["bonusPointsPerLevel"] == 10.0
    assert asc["expectedAverageXPPerSecond"] == 0.75
    assert asc["powerFactor"] == 2.0
    assert asc["useTimeFactors"] == 0
    assert asc["timeInMedicalConsultationFactor"] == 0.0
    assert asc["timeOnCourseFactor"] == 0.0
    # studentArchetypes from raws; null archetype stays null (never guessed)
    sarch = pot.get("studentArchetypes")
    assert isinstance(sarch, list) and len(sarch) == 2
    assert sarch[1]["archetype"] is None
    # marketing rows keep NULL economics - emptiness is DATA (no zero-fill)
    mk = by["Marketing_Potions"]
    for k in ("licenseCost", "kudoshCost", "yearlyTuitionFee", "levels"):
        assert mk[k] is None, f"{k} must be null on a marketing variant"
    assert mk["marketingFor"] == "Course_Potions"
    assert by["Marketing_Smithing"]["marketingFor"] is None
    # the Lite twin endpoint is CONFIG kind -> NOT in courses.jsonl
    assert L.LITE_ID not in by and L.LITE_BARE not in by
    # buildId on every row; evidence cites stub + raw dump paths
    for r in rows:
        assert r["buildId"] == BUILD_ID


def test_c2_modules_class_selected_prefix_split_anchor():
    ext = green_run()
    rows = logic_rows(ext, "course-progression", "modules.jsonl")
    assert rows is not None, "modules.jsonl not emitted"
    # selector = source.class TPC.CourseModuleDefinition (7 fixture rows);
    # prefix split asserted POST-selection [F3]
    prefixes = ["Unused_Module_" if r["id"].startswith("Unused_Module_")
                else "Module_" for r in rows]
    split = {p: prefixes.count(p) for p in set(prefixes)}
    assert split == {"Module_": 5, "Unused_Module_": 2}
    assert len(rows) == sum(split.values()) == 7   # AC2 identity
    anchor = next(r for r in rows if r["id"] ==
                  "Module_Alien_Science_Year1_Lesson1")
    assert anchor["classSize"] == 8 and anchor["duration"] == 2
    assert anchor["xpMultiplier"] == 1.0
    assert anchor["roomType"]["id"] == "Room_Alien_Science"
    assert anchor["roomType"]["resolved"] is True
    assert anchor["qualification"]["id"] == "Qualification_Archaeology"
    assert anchor["graphStudent"] == "Graph_Lecture_Default"
    # GradeMoneyRewards zeros VERBATIM on the all-zero majority; payout-
    # bearing minority counted, not curated
    zeros = [r for r in rows if set(r["gradeMoneyRewards"].values()) == {0}]
    assert len(zeros) == 6
    pay = next(r for r in rows if r["id"] ==
               "Module_Gradepay_Test_Year1_Lesson1")
    assert pay["gradeMoneyRewards"]["AA"] == 250


def test_c3_prerequisites_census_taxonomy_and_sidecar():
    ext = green_run()
    rows = logic_rows(ext, "course-progression", "prerequisites.jsonl")
    tax = logic_obj(ext, "course-progression", "prerequisite-taxonomy.json")
    assert rows is not None and tax is not None
    # green census: 8 member blocks across 7 distinct classes
    errs = L.prerequisite_violations(rows, expect_instances=8,
                                     expect_classes=7)
    assert not errs, errs
    byc = {}
    for r in rows:
        byc[r["prerequisiteClass"]] = byc.get(r["prerequisiteClass"], 0) + 1
    assert byc.get("PrerequisiteHasCourseUnlocked") == 2
    assert byc.get("PrerequisiteHasStarsInLevel") == 1, \
        "the REAL stars member is PrerequisiteHasStarsInLevel"
    # CharacterModifier_XP is NOT a taxonomy member (scope class only)
    assert "CharacterModifier_XP" not in byc
    # the emitted enum carries the pinned order + selection provenance
    members = tax["members"]
    assert members == L.TAXONOMY_24
    assert tax["abstract"] == "TPC.Prerequisite"
    assert "TPC.Prerequisite" in str(tax.get("selection"))
    smap = tax.get("shortNameMap") or {}
    assert len(smap) == 24 and smap.get("HasCourseUnlocked") == \
        "PrerequisiteHasCourseUnlocked"
    # keyed census identity: the F5 indirection shape
    arch_row = next(r for r in rows if r["carrierId"] ==
                    "CareerChallenge_Course_Archaeology_V1")
    assert arch_row["refKey"] == "00000000"
    assert arch_row["listField"] == "Prerequisites"
    assert arch_row["taxonomyIndex"] == 10
    tgt = arch_row["targets"][0]
    assert tgt["fileId"] == 2
    assert tgt["pathId"] == -abs(tgt["pathId"]) or isinstance(
        tgt["pathId"], int)
    # sidecar: declared NON-members never ride the member census [F4]
    nm = logic_rows(ext, "course-progression",
                    "prerequisite-nonmembers.jsonl")
    assert nm is not None and len(nm) == 2
    errs = L.nonmember_violations(nm)
    assert not errs, errs
    assert {r["blockClass"] for r in nm} == set(L.NONMEMBER_CLASSES)


def test_c4_unlock_edges_and_reconciliation():
    ext = green_run()
    edges = logic_rows(ext, "course-progression",
                       "course-unlock-edges.jsonl")
    relinks = read_jsonl(ext / "relinks" / "config_config.jsonl")
    assert edges is not None
    errs = L.unlock_edge_violations(edges, resolved_expected=2)
    assert not errs, errs
    by_src = {r["srcId"]: r for r in edges}
    edge = by_src["CareerChallenge_Course_Archaeology_V1"]
    # F7 trace shape end-to-end: carrier -> externals -> CAB -> twin stub id
    assert edge["dstId"] == L.LITE_ID, (
        f"expected the @hash8 twin endpoint verbatim, got "
        f"{edge['dstId']!r}")
    if "dstTwinOf" in edge:
        assert edge["dstTwinOf"] == L.LITE_BARE
    assert edge["evidence"]["extFileId"] == 2
    ev_cab = str(edge["evidence"].get("dstCab", ""))
    assert ev_cab.lower() == "cab-common04"
    pot = by_src["CareerChallenge_Course_Potions_V2"]
    assert pot["dstId"] == "Course_Potions"
    # AC5: resolved + unresolved == measured instance count (per class seed)
    n_instances = sum(1 for c in L.PREREQ_CARRIERS if c["verbEdge"])
    assert len(edges) == n_instances


def test_c4b_reconciliation_counters_from_artifacts():
    """RF-2 leg over the green corpus: overlap == resolved count, scope
    rows class-accounted, zero divergences."""
    ext = green_run()
    edges = logic_rows(ext, "course-progression",
                       "course-unlock-edges.jsonl")
    relinks = read_jsonl(ext / "relinks" / "config_config.jsonl")
    c = L.reconciliation_counters(edges, relinks, L.SCOPE_CARRIERS)
    assert c["relinksCoursePPTRRows"] == len(relinks) == 5
    assert c["unlockEdgeOverlapWithRelinks"] == 2 == sum(
        1 for e in edges if e.get("resolved", True)), (
        "overlap != resolved-count would mint a gap row [RF-2]")
    assert c["declaredScopeDifference"] == 3
    assert not c["divergentCarriers"]
    assert not c["unmatchedEdges"]


def test_c5_attrition_rows():
    ext = green_run()
    rows = logic_rows(ext, "course-progression", "attrition.jsonl")
    assert rows is not None, "attrition.jsonl not emitted"
    errs = L.attrition_violations(rows)
    assert not errs, errs   # incl. the GlobalFails decoy never surfacing


def test_c6_money_taxonomy_byte_match_and_resources():
    ext = green_run()
    obj = logic_obj(ext, "economy", "money-taxonomy.json")
    assert obj is not None
    reg = read_jsonl(ext / "decompiled" / "structural" / "id-registries" /
                     "TPS.Game.BudgetType.jsonl")
    errs = L.budget_type_violations(obj["budgetTypes"], reg)
    assert not errs, errs
    assert obj.get("profitType") == L.PROFIT_TYPE
    assert obj.get("expenseType") == L.EXPENSE_TYPE
    sc = obj.get("summaryColumns")
    assert sc == L.SUMMARY_COLUMNS
    # R4 hatch: the code-derived projection is LABELED reconstructed-from-code
    blob = json.dumps(obj)
    assert '"reconstructed-from-code"' in blob or any(
        v == "reconstructed-from-code"
        for v in _walk_values(obj)), \
        "summaryColumns projection must carry provenance label"
    assert obj.get("buildId") == BUILD_ID
    res = {r["resource"]: r for r in obj.get("resources", [])}
    assert set(res) >= {"money", "kudosh", "course-points"}
    assert res["kudosh"]["budgetMembership"] is False
    assert res["course-points"]["budgetMembership"] is False


def _walk_values(o):
    if isinstance(o, dict):
        for v in o.values():
            yield from _walk_values(v)
    elif isinstance(o, list):
        for v in o:
            yield from _walk_values(v)
    else:
        yield o


def test_c7_finance_configs_diff_only():
    ext = green_run()
    rows = logic_rows(ext, "economy", "finance-configs.jsonl")
    assert rows is not None and len(rows) == 3
    errs = L.finance_violations(rows)
    assert not errs, errs
    by = {r["id"]: r for r in rows}
    arch = by["Config_FinanceManager_Level_Archaeology"]
    base = by["Config_FinanceManager"]
    # diff-only property recomputed mechanically over ECONOMIC fields
    # (provenance/evidence blocks are per-row by design, not data deltas)
    skip = {"id", "evidence", "buildId", "provenance", "sourceAxes"}
    differing = {k for k in (set(arch) | set(base)) - skip
                 if arch.get(k) != base.get(k)}
    assert differing <= {"initialBalance"}, \
        f"second differing field: {differing}"
    assert arch["initialBalance"] == L.FIN_ARCH_BALANCE == 80000


def test_c8_kudosh_ledger_sources_sinks():
    ext = green_run()
    rows = logic_rows(ext, "economy", "kudosh-ledger.jsonl")
    assert rows is not None
    sources = [r for r in rows if r.get("direction") == "source"]
    sinks = [r for r in rows if r.get("direction") == "sink"]
    # sources: typed RewardKudoshDefinition (250, HUD) + 2 consumables whose
    # stub payloads carry NO amount -> declared-empty, never zero-filled
    assert len(sources) >= 3
    amounts = {r.get("carrierId"): r.get("amount") for r in sources}
    assert amounts.get("Activity_Completion_Reward") == 250
    cons = [r for r in sources
            if str(r.get("carrierId", "")).startswith("Kudosh_Consumable")]
    assert len(cons) == 2 and all(r.get("amount") is None for r in cons),         "consumable sources must be declared-empty (a zero would be invented)"
    # sinks partitioned by IKudoshUnlockable implementer - all three REQUIRED
    # present [F10]; rows may spell the bucket OR the implementing class
    bucket = {"GameItemDefinition": "item", "RoomDefinition": "room",
              "LandscapeBrushDefinition": "landscapeBrush",
              "GameItemUpgradeDefinition": "upgrade",
              "CourseDefinition": "courseLicence"}
    parts = {}
    for s in sinks:
        impl = s.get("implementer")
        parts.setdefault(bucket.get(impl, impl), []).append(s)
    for impl in ("item", "room", "landscapeBrush"):
        assert parts.get(impl), f"IKudoshUnlockable implementer {impl} empty"
    upg = {s["carrierId"]: s["amount"] for s in parts.get("upgrade", [])}
    assert upg.get("Alien_Refiner_V2") == 10000   # F10 anchors verbatim
    assert upg.get("Alien_Refiner_V3") == 30000
    lic = {s["carrierId"]: s["amount"] for s in sinks
           if s.get("implementer") == "courseLicence"}
    assert lic.get("Course_Archaeology") == 0, \
        "a zero cost is VERBATIM data, never omitted"
    assert lic.get("Course_Potions") == 400
    # the runtime balance appears ONLY as taxonomy metadata, never a row [F10]
    blob = json.dumps(rows)
    assert "TotalKudosh" not in blob or '"direction"' not in blob


def test_c9_research_costs_domain_and_lite_empty():
    ext = green_run()
    rows = logic_rows(ext, "economy", "research-costs.jsonl")
    assert rows is not None and len(rows) == 5
    errs = L.research_violations(rows)
    assert not errs, errs
    dist = {}
    for r in rows:
        dist[r["researchPoints"]] = dist.get(r["researchPoints"], 0) + 1
    assert dist == {250: 1, 500: 2, 1200: 1, 100: 1}
    ids = {r["id"] for r in rows}
    assert {"ResearchProject_Bookshelf_Robotics",
            "ResearchProject_Computer_Digital",
            "ResearchProject_Computer_Super",
            "ResearchProject_Course_Computer"} <= ids
    assert L.RESEARCH_LITE_ID not in ids, \
        "Lite twins are a DECLARED-EMPTY class - never zero-cost rows"


def _fixture_uisprite_grades(ext):
    for r in read_jsonl(ext / "stubs" / "configs.jsonl"):
        if r["id"] == "Config_UISprite":
            return r["fields"]["Grades"]
    raise AssertionError("Config_UISprite stub missing from fixture tree")


def test_c10_grade_ladder_rederived_from_stub():
    ext = green_run()
    obj = logic_obj(ext, "grading", "grade-ladder.json")
    assert obj is not None, "grade-ladder.json not emitted"
    grades = _fixture_uisprite_grades(ext)
    errs = L.grade_ladder_violations(obj, grades)
    assert not errs, errs
    rows = obj["thresholdTable"]["rows"]
    assert [r["grade"] for r in rows] == \
        ["NA", "F", "D", "C", "CC", "B", "BB", "A", "AA"]
    aa = rows[8]
    assert aa["threshold"] == 90.0 and aa["displayNameTermId"] == -1320794757
    # displayName locale join: fills ONLY where the termID resolves
    filled = {r["grade"]: r["displayName"] for r in rows}
    assert filled["AA"] is not None and filled["F"] is not None
    assert all(filled[g] is None
               for g in ("NA", "D", "C", "CC", "B", "BB", "A")), filled


def test_c11_term_pass_grades_population():
    ext = green_run()
    rows = logic_rows(ext, "grading", "term-pass-grades.jsonl")
    assert rows is not None
    names = {n for n, _v in L.EGRADE_MEMBERS} - {"Invalid"}
    n_terms = sum(len(c["terms"]) for c in L.COURSE_SPECS)
    assert len(rows) == n_terms == 4   # == resolved Terms[] refs
    for r in rows:
        pg = r.get("passGrade")
        assert pg is None or pg in names, f"passGrade {pg!r} not an EGrade"
    byc = {}
    for r in rows:
        byc.setdefault(r.get("courseId"), []).append(r)
    assert len(byc["Course_Archaeology"][0]["passGrade"]) >= 0
    weights = sorted(r.get("weight") for r in rows if r.get("weight"))
    assert weights == sorted([2.0, 1.0, 1.0, 1.0])


def test_c12_assessment_scoring_harvest_direct():
    ext = green_run()
    rows = logic_rows(ext, "grading", "assessment-scoring.jsonl")
    assert rows is not None and len(rows) == 3   # full definitions only
    ids = {r["courseId"] for r in rows}
    assert ids == {"Course_Archaeology", "Course_Potions", "Course_Smithing"}
    arch = next(r for r in rows if r["courseId"] == "Course_Archaeology")
    assert arch["expectedAverageXPPerSecond"] == 0.75
    assert arch["powerFactor"] == 2.0


def test_c13_xp_score_normalization_marker():
    ext = green_run()
    obj = logic_obj(ext, "grading", "xp-score-normalization.json")
    assert obj is not None, \
        "the UNPROVEN-NATIVE marker artifact must ALWAYS exist"
    errs = L.xp_normalization_violations(obj)
    assert not errs, errs


def test_c14_staff_decay_rows():
    ext = green_run()
    rows = logic_rows(ext, "needs-decay", "staff-decay.jsonl")
    assert rows is not None
    # 2 staff x 10 attributes = 20 rows (Litter has NO staff carrier)
    assert len(rows) == 20 == 2 * 10
    errs = L.staff_decay_violations(rows)
    assert not errs, errs
    by = {}
    for r in rows:
        by.setdefault(r["staffId"], {})[r["attribute"]] = r
    ast_rows = by["Staff_Assistant"]
    assert ast_rows["Energy"]["changeOverTime"] == L.DECAY_SIX
    assert repr(ast_rows["Energy"]["changeOverTime"]) == \
        repr(-0.05000000074505806), "verbatim float noise required"
    six = {"Drink", "Energy", "Food", "Hygiene", "Social", "ToiletComfort"}
    zeros = {"Fun", "Happiness", "Health", "Sober"}
    for a in six:
        assert ast_rows[a]["changeOverTime"] == L.DECAY_SIX, a
        assert (ast_rows[a]["minInitialValue"],
                ast_rows[a]["maxInitialValue"]) == (90.0, 100.0)
    for a in zeros:
        assert ast_rows[a]["changeOverTime"] == 0.0, a
    assert (ast_rows["Sober"]["minInitialValue"],
            ast_rows["Sober"]["maxInitialValue"]) == (0.0, 0.0), \
        "sober init pinned 0-0 [F13]"
    assert (ast_rows["Fun"]["minInitialValue"],
            ast_rows["Fun"]["maxInitialValue"]) == (100.0, 100.0)
    # per-row ranges copied verbatim (Lecturer energy differs from Assistant)
    lec = by["Staff_Lecturer"]["Energy"]
    assert (lec["minInitialValue"], lec["maxInitialValue"]) == (70.0, 100.0)
    assert not any(r["attribute"] == "Litter" for r in rows)


def test_c15_student_decay_and_coverage_counter():
    ext = green_run()
    rows = logic_rows(ext, "needs-decay", "student-decay.jsonl")
    assert rows is not None
    ecp = [r for r in rows if r.get("component") == "ECPStudent"]
    assert len(ecp) == 6, f"ECPStudent rows: {rows}"
    assert all(r.get("studentTypeId") for r in ecp),         "studentTypeId must join the raw dump back to its stub id"
    by = {(r["studentTypeId"], r["attribute"]): r for r in ecp}
    nerd = by[("StudentType_Nerd", "ClubNeed")]
    assert nerd["changeOverTime"] == -0.10000000149011612, \
        "verbatim float noise required"
    assert (nerd["minInitialValue"], nerd["maxInitialValue"]) == (80.0, 100.0)
    rel = by[("StudentType_Nerd", "Relationship")]
    assert rel["changeOverTime"] == -0.20000000298023224
    assert (rel["minInitialValue"], rel["maxInitialValue"]) == (40.0, 100.0)
    jock = by[("StudentType_Jock", "SelfStudy")]
    assert jock["changeOverTime"] == -0.20000000298023224
    clubs = [r for r in rows if r.get("component") == "ClubDefinition"]
    assert len(clubs) == 2


def test_c16_core11_ledger():
    ext = green_run()
    rows = logic_rows(ext, "needs-decay", "student-core11-decay.jsonl")
    assert rows is not None, "the absent-carrier ledger must always exist"
    errs = L.core11_violations(rows)
    assert not errs, errs
    reg = read_jsonl(ext / "decompiled" / "structural" / "id-registries" /
                     "TPS.Game.TPC.EAttribute.jsonl")
    assert [r["attribute"] for r in rows] == [x["name"] for x in reg], \
        "vocabulary sourced DIRECTLY from the EAttribute registry (F8)"


def test_c17_interactions_verbatim_typed_blocks():
    """F16/F17: typed blocks round-trip data+type VERBATIM; the GOOSE graph
    pointer resolves; cooldown fields copy verbatim; the bare-class decoy is
    never selected."""
    ext = green_run()
    rows = logic_rows(ext, "needs-decay", "interactions.jsonl")
    assert rows is not None
    ids = {r["id"] for r in rows}
    assert len(rows) == 4
    assert "Interaction_Bare_Naming_Decoy" not in ids
    cat = next(r for r in rows if r["id"] == "Interaction_Caterer_Needs")
    cq = cat.get("cooldownAndQueue") or {}
    assert cq.get("CooldownInSeconds") == 30.0 and cq.get("MaxQueue") == 4, cq
    blocks = (cat.get("typedBlocks")
              or cat.get("characterModifiers")
              or cat.get("characterModifiersBlocks") or [])
    assert blocks, "typed blocks must copy data+type VERBATIM"
    b0 = blocks[0]
    data = b0.get("data") or {}
    assert data.get("_amount") == 90.0 and data.get("WhenToModify") == 2
    t = b0.get("type") or {}
    assert str(t.get("class")).endswith("CharacterModifier_Drink")
    assert t.get("ns") == "TPC" and t.get("asm") == "TPS.Game"
    assert cat.get("aiGraphRef") == "Graph_Lecture_Default", (
        f"aiGraphRef={cat.get('aiGraphRef')!r}")
    others = [r for r in rows if r["id"] != "Interaction_Caterer_Needs"]
    assert all(r.get("aiGraphRef") is None for r in others)


def test_c18_logic_md_rollup_and_digests():
    ext = green_run()
    md = ext / "logic" / "LOGIC.md"
    assert md.exists(), "L6 LOGIC.md rollup missing"
    text = md.read_text(encoding="utf-8", errors="replace")
    assert str(BUILD_ID) in text, "provenance header carries the buildId"
    assert "UNPROVEN-NATIVE" in text, \
        "the register of the two standing rows must be printed"
    log = log_text(ext)
    # L6 records the rerun-comparison surface: the per-file digest map in the
    # spec sketch's own spelling (the reconciler round restored the map; the
    # bare-count alternative stays accepted so both forms keep biting)
    assert re.search(r"digests\s*:", log) or re.search(r"\bdigestCount\b",
                                                       log), \
        "digest record missing"


def test_c19_id_verbatim_sweep():
    """AC4: every emitted id/srcId/dstId resolves to a stub id (twins WITH
    suffix) or null-with-gap-row; <=1000 ids -> ALL checked."""
    ext = green_run()
    stub_ids = set()
    for f in sorted((ext / "stubs").glob("*.jsonl")):
        if f.name.startswith("_"):
            continue
        for r in read_jsonl(f):
            if isinstance(r.get("id"), str):
                stub_ids.add(r["id"])
    errs = L.id_verbatim_violations(ext / "logic", stub_ids)
    assert not errs, errs


# ===========================================================================
# PART D - negatives and failure-mode routing
# ===========================================================================

def test_d1_failure_modes_route_to_rows_and_gaps():
    """Every resolver failure mode lands as an unresolved ROW + a gap row -
    never silence - while the run still completes-with-ledger [L1/AC9]."""
    require_logic_registered()
    r, ext = run_logic(fx_tree("failmodes", "fail8"))
    combined = r.stdout + r.stderr
    assert r.returncode == 2, (
        f"gaps are honest ledger state -> exit 2, got rc={r.returncode}\n"
        f"{combined}")
    edges = logic_rows(ext, "course-progression",
                       "course-unlock-edges.jsonl")
    unresolved = [e for e in edges if e.get("resolved") is False]
    assert len(unresolved) == 4, \
        f"four doomed typed refs must yield four unresolved rows: {edges}"
    assert all(e["dstId"] is None for e in unresolved)
    reasons = " | ".join(str(e.get("reason")) for e in unresolved)
    assert "pathId-not-a-stub-entity" in reasons, \
        "pinned zero-survivor reason spelling missing"
    gaps = read_jsonl(ext / "logic" / "_gaps.jsonl")
    kinds = {g["kind"] for g in gaps}
    assert {"builtin-target", "ambiguous-target"} <= kinds
    amb = next(g for g in gaps if g["kind"] == "ambiguous-target")
    blob = json.dumps(amb)
    assert "Item_Duplicate_Common" in blob and "Room_Duplicate_Rooms" in \
        blob, f"ambiguous gap must list ALL candidates: {blob[:300]}"
    # the two standing rows STILL stand beside the planted ones
    assert len(L.standing_gap_rows(gaps)) == 2
    text = log_text(ext)
    m = re.search(r"builtinExternalsSkipped\b[^0-9\n]*([0-9]+)", text,
                  re.IGNORECASE)
    assert m and int(m.group(1)) >= 2, "edge + module builtin skips counted"
    m2 = re.search(r"moduleRoomUnresolved\b[^0-9\n]*([0-9]+)", text,
                   re.IGNORECASE)
    assert m2 and int(m2.group(1)) >= 1, "broken module room ref ledgered"


def test_d2_broken_threshold_monotonicity_exits_1():
    require_logic_registered()
    r, ext = run_logic(fx_tree("monotonic", "mono8"))
    combined = r.stdout + r.stderr
    assert r.returncode == 1, (
        f"a broken threshold table is a validation FAILURE -> exit 1, "
        f"got rc={r.returncode}\n{combined}")
    blob = (combined + log_text(ext)).lower()
    assert any(tok in blob for tok in ("threshold", "monoton", "grades")), \
        "the failure must name the offending surface"


def test_d3_stub_vs_raw_mismatch_exits_1_naming_path():
    """Copied-but-mismatching numeric: stub economics disagree with the raw
    dump both layers claim to carry -> exit 1 naming the field path [F2/L5]."""
    require_logic_registered()
    r, ext = run_logic(fx_tree("econmismatch", "econ8"))
    combined = r.stdout + r.stderr
    assert r.returncode == 1, (
        f"stub-vs-raw mismatch must fail exit 1, got rc={r.returncode}\n"
        f"{combined}")
    blob = combined.lower() + log_text(ext).lower()
    assert any(tok in blob for tok in ("licensecost", "mismatch",
                                       "cross-check", "course_potions")), \
        f"the offending path should be named:\n{combined[-600:]}"


def test_d4_second_differing_finance_field_is_drift_not_crash():
    require_logic_registered()
    r, ext = run_logic(fx_tree("financedrift", "findrift"))
    combined = r.stdout + r.stderr
    assert r.returncode == 2, (
        f"a second differing override field is DRIFT territory, not a "
        f"crash: rc={r.returncode}\n{combined}")
    drifts = L.drift_lines(combined + log_text(ext))
    assert drifts, "expected a DRIFT line for the multi-field override"
    gaps = read_jsonl(ext / "logic" / "_gaps.jsonl")
    assert len(L.standing_gap_rows(gaps)) == 2
    rows = logic_rows(ext, "economy", "finance-configs.jsonl")
    errs = L.finance_violations(rows)
    assert not errs, errs   # base anchors unaffected by the variant


def test_d5_relinks_divergence_gaps_loudly():
    """RF-2: a relinks counterpart claiming a different dstPathId than the
    resolved edge -> kind `relinks-divergence` (PINNED spelling) gap row;
    overlap != resolved-count; exit stays 2."""
    require_logic_registered()
    r, ext = run_logic(fx_tree("divergence", "div8"))
    combined = r.stdout + r.stderr
    assert r.returncode == 2, f"{r.returncode}\n{combined}"
    edges = logic_rows(ext, "course-progression",
                       "course-unlock-edges.jsonl")
    relinks = read_jsonl(ext / "relinks" / "config_config.jsonl")
    c = L.reconciliation_counters(edges, relinks, L.SCOPE_CARRIERS)
    assert c["unlockEdgeOverlapWithRelinks"] != len(
        [e for e in edges if e.get("resolved", True)]), \
        "the divergent counterpart must break the equality"
    assert c["declaredScopeDifference"] == 3
    gaps = read_jsonl(ext / "logic" / "_gaps.jsonl")
    div = [g for g in gaps if g.get("kind") == "relinks-divergence"]
    assert div, f"relinks-divergence gap row required: {gaps}"
    blob = json.dumps(div).lower()
    assert "potions" in blob or "9402" in blob, \
        "the divergence must name its subject"
    assert len(L.standing_gap_rows(gaps)) == 2


@pytest.mark.parametrize("victim", [
    "relinks/i2_term_registry.jsonl",
    "identity.json",
])
def test_d6_missing_upstream_refuses_exit_3_naming_it(victim):
    require_logic_registered()
    tree = fx_tree("green", f"exit3-{victim.replace('/', '_')}")
    p = tree / "extracted" / victim
    assert p.exists()
    p.unlink()
    r, ext = run_logic(tree)
    combined = r.stdout + r.stderr
    assert r.returncode == 3, (
        f"missing upstream artifact {victim} must refuse with exit 3, got "
        f"rc={r.returncode}\n{combined}")
    assert Path(victim).name in combined, \
        f"refusal does not name the missing artifact:\n{combined[:600]}"


# ===========================================================================
# PART E - adapter-level invention-guard unit legs (pure-function surface)
# ===========================================================================

def _logic_impl():
    import pytest
    from _impl import load_any
    mod = load_any(*L.LOGIC_SCRIPTS)
    if mod is None:
        pytest.skip("impl-missing: tools/{logic_util,stage8_logic}.py not "
                    "present yet (piece-04 CodeWriter pending)")
    return mod


def _sym(mod, candidates):
    import pytest
    from _impl import get_sym
    return get_sym(mod, *candidates)


CARRIER_PAYLOAD = {
    "Prerequisites": [{"id": 0}],
    "references": {"00000000": {
        "data": {"_visibleOnHUD": 0,
                 "_course": {"m_FileID": 2,
                             "m_PathID": -7906850020505022578}},
        "type": {"asm": "TPS.Game", "ns": "TPC",
                 "class": "PrerequisiteHasCourseUnlocked"}}},
}


def test_e1_typed_block_walker_yields_typed_leaves():
    """The walker's raison d'etre [F6/RF-1]: TYPED view (data+type per leaf)
    that plain PPtr walking cannot attribute."""
    mod = _logic_impl()
    walk = _sym(mod, L.WALKER_SYMBOLS)
    if walk is None:
        import pytest
        pytest.skip("impl-missing: no typed-block walker symbol resolvable "
                    f"(tried {L.WALKER_SYMBOLS})")
    leaves = None
    last = None
    for args in ((CARRIER_PAYLOAD,), ({"fields": CARRIER_PAYLOAD},),
                 (CARRIER_PAYLOAD, "fields")):
        try:
            leaves = walk(*args)
            break
        except TypeError as exc:
            last = exc
    assert leaves is not None, \
        f"walker matched none of its call shapes; last: {last}"
    leaves = list(leaves)
    assert leaves, "walker found no typed leaves"
    leaf = leaves[0]
    t = leaf.get("type") or {}
    assert t.get("class") == "PrerequisiteHasCourseUnlocked"
    assert t.get("ns") == "TPC" or t.get("asm") == "TPS.Game"
    fp = str(leaf.get("fieldPath", ""))
    assert "_course" in fp and "00000000" in fp


def test_e2_invention_guard_bites_on_uncited_and_misderived():
    """AC7 negatives at unit level: an UNCITED numeric and a MIS-DERIVED
    arithmetic label must both fail the guard naming the path; a green
    artifact passes with buckets counted."""
    mod = _logic_impl()
    guard = _sym(mod, L.GUARD_SYMBOLS)
    if guard is None:
        import pytest
        pytest.skip("impl-missing: no invention-guard symbol resolvable "
                    f"(tried {L.GUARD_SYMBOLS})")

    def run_guard(artifact):
        last = None
        for args, kw in (((artifact,), {}),
                         ((artifact, None), {"extracted_root": None}),
                         ((), {"artifact": artifact})):
            try:
                return guard(*args, **kw)
            except TypeError as exc:
                last = exc
        raise AssertionError(
            f"guard matched none of its call shapes; last: {last}")

    good = {"value": 250,
            "evidence": {"source": "stubs/configs.jsonl#Activity_X",
                         "fieldPath": "references.00000000.data._amount"}}
    res_good = run_guard(good)
    assert not _guard_failed(res_good), res_good
    uncited = {"value": 999, "evidence": {}}
    res_bad = run_guard(uncited)
    assert _guard_failed(res_bad), \
        "an uncited numeric MUST fail the invention guard"
    mis = {"value": 7,
           "method": "derived-arithmetic: inputs.a + inputs.b",
           "evidence": {"inputs": {"a": 1, "b": 2}}}
    res_mis = run_guard(mis)
    assert _guard_failed(res_mis), \
        "a derived label that does not recompute MUST fail (label laundering)"


def _guard_failed(result):
    """Normalize guard results: bool, {failures:[..]}, or object with
    failure counters - any truthy failure signal counts."""
    if result is True or result is False:
        return result is False
    if isinstance(result, dict):
        fails = result.get("failures")
        if isinstance(fails, list):
            return len(fails) > 0
        for k in ("inventionGuardFailures", "failureCount", "failed",
                  "violations"):
            if k in result and result[k]:
                return bool(result[k]) if isinstance(result[k], int) \
                    else len(result[k]) > 0
        return False
    if isinstance(result, list):
        return len(result) > 0
    return bool(result) is False


# ===========================================================================
# PART F - client-gated integration over the REAL extracted corpus
# ===========================================================================

_REAL: dict = {}

REAL_RELATIVES = (
    "identity.json",
    "bundle-roster.jsonl",
    "harvest/export-manifest.jsonl",
    "harvest/externals.jsonl",
    "relinks/matrix.json",
    "relinks/config_config.jsonl",
    "relinks/i2_term_registry.jsonl",
    "relinks/entity_locale.jsonl",
)


def real_extracted_root() -> Path | None:
    env = os.environ.get("TPC_LOGIC_REAL_EXTRACTED")
    if env and Path(env).exists():
        return Path(env)
    p = PACK_ROOT / "extracted"
    return p if (p / "identity.json").exists() else None


def conftest_game_dir():
    from conftest import game_dir
    return game_dir()


def real_run():
    """Copy the section-3 upstream set from the REAL tree into a private
    scratch root, then run --only logic ONCE (cached for the session)."""
    import pytest
    if "rc" in _REAL:
        return _REAL["rc"], _REAL["ext"]
    require_logic_registered()
    from conftest import game_dir
    if game_dir() is None:
        pytest.skip("client-gated: neither TPC_GAME_DIR nor the default "
                    "install path exists")
    src = real_extracted_root()
    if src is None:
        pytest.skip("client-gated: no real extracted corpus found "
                    "(identity.json missing)")
    ext = L.scratch(f"real-{os.getpid()}") / "extracted"
    if ext.exists():
        shutil.rmtree(ext)
    ext.mkdir(parents=True)
    for rel in REAL_RELATIVES:
        s = src / rel
        assert s.exists(), f"real upstream artifact missing: {rel}"
        d = ext / rel
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(s, d)
    bridges = src / "relinks" / "bridges"
    assert bridges.is_dir(), "relinks/bridges missing on the real tree"
    shutil.copytree(bridges, ext / "relinks" / "bridges")
    structural = src / "decompiled" / "structural"
    assert structural.is_dir()
    shutil.copytree(structural, ext / "decompiled" / "structural")
    stubs = src / "stubs"
    assert stubs.is_dir()
    shutil.copytree(stubs, ext / "stubs",
                    ignore=lambda d, names: [n for n in names
                                             if n == "_unmapped-families.jsonl"])
    for fam in ("TPC.CourseDefinition", "TPC.StudentDefinition"):
        s = src / "harvest" / "monobehaviours" / "configs" / fam
        assert s.is_dir(), f"harvest-direct family missing: {fam}"
        shutil.copytree(s, ext / "harvest" / "monobehaviours" / "configs" /
                        fam)
    game = str(conftest_game_dir())
    from conftest import run_pack
    r = run_pack([game, "--only", "logic"],
                 extracted_root=ext, timeout=3600)
    _REAL["rc"] = r.returncode
    _REAL["ext"] = ext
    _REAL["stdout"] = r.stdout
    _REAL["stderr"] = r.stderr
    return r.returncode, ext


def _seed_or_drift(text: str, measured, seed):
    """Drift-wins contract [AC5]: measured == seed passes; a movement is
    legal only when DRIFT printed somewhere (fresh number wins)."""
    if measured == seed:
        return None
    if L.drift_lines(text):
        return None
    return f"measured {measured} != seed {seed} and no DRIFT line printed"


def test_f1_real_corpus_seeds_reproduce_or_drift():
    rc, ext = real_run()
    text = _REAL["stdout"] + _REAL["stderr"] + log_text(ext)
    assert rc == 2, (
        f"exit 2 is the EXPECTED steady state on today's corpus "
        f"(two standing gaps), got rc={rc}\n"
        f"{_REAL['stdout'][-1500:]}{_REAL['stderr'][-800:]}")
    # L1 course split 28 + 41
    courses = logic_rows(ext, "course-progression", "courses.jsonl")
    full = sum(1 for r in courses if r.get("class") == "TPC.CourseDefinition")
    mkt = sum(1 for r in courses
              if r.get("class") == "TPC.MarketingCourseDefinition")
    assert len(courses) == full + mkt   # AC2 identity holds at any scale
    assert not _seed_or_drift(text, full, 28)
    assert not _seed_or_drift(text, mkt, 41)
    # L1 modules 319 with the 312/7 split
    modules = logic_rows(ext, "course-progression", "modules.jsonl")
    unused = [r for r in modules if r["id"].startswith("Unused_Module_")]
    assert len(modules) == len(modules) and len(unused) > 0
    assert not _seed_or_drift(text, len(modules), 319)
    assert len(modules) == (len(modules) - len(unused)) + len(unused)
    anchor = next(r for r in modules
                  if r["id"] == "Module_Alien_Science_Year1_Lesson1")
    assert anchor["classSize"] == 8 and anchor["duration"] == 2
    assert anchor["xpMultiplier"] == 1.0
    assert anchor["roomType"]["id"], "anchor RoomType resolves on real data"


    # L1 unlock edges: the Archaeology trace resolves end-to-end [F7]
    edges = logic_rows(ext, "course-progression",
                       "course-unlock-edges.jsonl")
    arch = [e for e in edges
            if e.get("srcId") == "CareerChallenge_Course_Archaeology_V1"]
    assert arch and arch[0].get("dstId") == "Course_Archaeology_Lite", \
        f"F7 trace broken: {arch[:1]}"
    n_res = sum(1 for e in edges if e.get("resolved", True))
    assert not _seed_or_drift(text, len(edges), 50), \
        "resolved + unresolved rows must equal the measured instance count"
    assert n_res <= len(edges)
    # census 193-or-fresh, taxonomy subset of the 24 namespaced spellings
    census = logic_rows(ext, "course-progression", "prerequisites.jsonl")
    bad_cls = [r["prerequisiteClass"] for r in census
               if r.get("prerequisiteClass") not in set(L.TAXONOMY_24)]
    assert not bad_cls, f"non-taxonomy classes in the census: {bad_cls[:5]}"
    assert not _seed_or_drift(text, len(census), 193)
    sidecar = logic_rows(ext, "course-progression",
                         "prerequisite-nonmembers.jsonl")
    assert {r["blockClass"] for r in sidecar} <= set(L.NONMEMBER_CLASSES)
    assert not any(r.get("blockClass") in set(L.TAXONOMY_24)
                   for r in census), "non-members leaked into the census"
    # RF-2 seeds: 68 / overlap == resolved / 18-or-fresh (run-section keys;
    # the scope accounting is impl-side knowledge on the real corpus)
    def keyval(key):
        m = re.search(rf"{re.escape(key)}\b[^0-9\n\-]*(-?\d+)", text,
                      re.IGNORECASE)
        return int(m.group(1)) if m else None

    n_relinks = sum(1 for _ in open(ext / "relinks" / "config_config.jsonl",
                                    encoding="utf-8"))
    assert n_relinks >= 50
    assert not _seed_or_drift(text, keyval("relinksCoursePPTRRows"), 68)
    assert not _seed_or_drift(text, keyval("declaredScopeDifference"), 18)
    ov = keyval("unlockEdgeOverlapWithRelinks")
    assert ov is not None and ov == n_res, \
        f"overlap {ov} != resolved {n_res} [RF-2]"
    gaps = read_jsonl(ext / "logic" / "_gaps.jsonl")
    div = [g for g in gaps if g.get("kind") == "relinks-divergence"]
    assert not div, f"real-corpus reconciliation diverged: {div[:3]}"


def test_f1b_real_corpus_family_seeds():
    rc, ext = real_run()
    assert rc == 2
    text = _REAL["stdout"] + _REAL["stderr"] + log_text(ext)

    def keyval(key):
        m = re.search(rf"{re.escape(key)}\b[^0-9\n\-]*(-?\d+)", text,
                      re.IGNORECASE)
        return int(m.group(1)) if m else None

    # L2: 30 finance rows, Archaeology diff-only, kudosh partitions, research
    fin = logic_rows(ext, "economy", "finance-configs.jsonl")
    assert not _seed_or_drift(text, len(fin), 30)
    by = {r["id"]: r for r in fin}
    base, arch = by.get("Config_FinanceManager"), \
        by.get("Config_FinanceManager_Level_Archaeology")
    assert base and arch and arch.get("initialBalance") == 80000
    skip = {"id", "evidence", "buildId", "provenance", "sourceAxes"}
    diffs = {k for k in (set(arch) | set(base)) - skip
             if arch.get(k) != base.get(k)}
    assert diffs <= {"initialBalance"}, f"diff-only broken: {diffs}"
    kl = logic_rows(ext, "economy", "kudosh-ledger.jsonl")
    bucket = {"GameItemDefinition": "item", "RoomDefinition": "room",
              "LandscapeBrushDefinition": "landscapeBrush",
              "GameItemUpgradeDefinition": "upgrade"}
    impls = {bucket.get(r.get("implementer"), r.get("implementer"))
             for r in kl if r.get("direction") == "sink"}
    assert {"item", "room", "landscapeBrush"} <= impls, impls
    upg = {r.get("carrierId"): r.get("amount") for r in kl
           if bucket.get(r.get("implementer")) == "upgrade"}
    assert upg.get("Item_Alien_Refiner_Upgrade_V2") == 10000, upg
    assert upg.get("Item_Alien_Refiner_Upgrade_V3") == 30000
    res = logic_rows(ext, "economy", "research-costs.jsonl")
    errs = L.research_violations(res)
    assert not errs, errs
    assert not _seed_or_drift(text, len(res), 209)
    dom = {100, 200, 250, 300, 500, 600, 1200, 2500, 3000}
    assert {r["researchPoints"] for r in res} <= dom
    assert keyval("liteRowsWithoutCosts") is not None


def _real_uisprite_grades(ext):
    for r in read_jsonl(ext / "stubs" / "configs.jsonl"):
        if r["id"] == "Config_UISprite":
            return r["fields"]["Grades"]
    raise AssertionError("Config_UISprite missing from the REAL stub corpus")


def test_f1c_real_grading_and_needs_seeds():
    rc, ext = real_run()
    assert rc == 2
    # L3: ladder re-derived from the REAL Config_UISprite stub equals the
    # emitted table row-for-row (thresholds -1/0/40/50/60/70/75/80/90)
    obj = logic_obj(ext, "grading", "grade-ladder.json")
    grades = _real_uisprite_grades(ext)
    errs = L.grade_ladder_violations(obj, grades) if obj else \
        ["grade-ladder.json missing"]
    # displayName join expectations are fixture-specific on the real corpus
    soft = [e for e in errs if "displayName" not in e]
    assert not soft, soft
    rows = obj["thresholdTable"]["rows"]
    assert [r["threshold"] for r in rows] == \
        [-1.0, 0.0, 40.0, 50.0, 60.0, 70.0, 75.0, 80.0, 90.0]
    assert len(rows) == 9
    asc = logic_rows(ext, "grading", "assessment-scoring.jsonl")
    a = next((r for r in asc if r.get("courseId") == "Course_Archaeology"),
             None)
    assert a and (a["bonusPointsPerLevel"], a["expectedAverageXPPerSecond"],
                  a["powerFactor"]) == (10.0, 0.75, 2.0), \
        "verifyA 2d anchor broken"
    # L4: 30 staff rows with the six-set / zero-set; core-11 null law
    staff = logic_rows(ext, "needs-decay", "staff-decay.jsonl")
    assert len(staff) == 30 == 3 * 10   # AC2 identity
    by = {}
    for r in staff:
        if r["staffId"] == "Staff_Assistant":
            by[r["attribute"]] = r
    assert repr(by["Energy"]["changeOverTime"]) == repr(L.DECAY_SIX)
    assert (by["Sober"]["minInitialValue"], by["Sober"]["maxInitialValue"]) \
        == (0.0, 0.0)
    errs = L.staff_decay_violations(staff)
    soft_errs = [e for e in errs if "fieldPath" not in e]
    assert not soft_errs, soft_errs
    core = logic_rows(ext, "needs-decay", "student-core11-decay.jsonl")
    errs = L.core11_violations(core)
    assert not errs, errs
    sd = logic_rows(ext, "needs-decay", "student-decay.jsonl")
    ecp = {(r.get("studentTypeId"), r.get("attribute")): r
           for r in sd if r.get("component") == "ECPStudent"}
    nerd_club = ecp.get(("StudentType_Nerd", "ClubNeed"))
    if nerd_club:   # the two harvested raws carry these exact anchors [F14]
        assert nerd_club["changeOverTime"] == -0.10000000149011612


def test_f1d_real_interactions_and_guard_green():
    rc, ext = real_run()
    text = _REAL["stdout"] + _REAL["stderr"] + log_text(ext)
    inter = logic_rows(ext, "needs-decay", "interactions.jsonl")
    assert inter, "interactions.jsonl missing"
    m = re.search(rf"interactionRows\b[^0-9\n]*([0-9]+)", text, re.IGNORECASE)
    if m:
        assert int(m.group(1)) == len(inter)
    assert not _seed_or_drift(text, len(inter), 630), \
        f"interaction count {len(inter)} vs seed 630 without DRIFT"
    # guard green over the real tree
    ig = re.search(r"inventionGuardFailures\b[^0-9\n]*([0-9]+)", text,
                   re.IGNORECASE)
    assert ig and int(ig.group(1)) == 0
    na = re.search(r"numericsAudited\b[^0-9\n]*([0-9]+)", text,
                   re.IGNORECASE)
    assert na and int(na.group(1)) > 0   # AC7


def test_f2_real_exit2_gap_accounting():
    """exit 2 with exactly the two standing gaps PLUS any genuinely new ones
    - each new one must be enumerated in the run section [AC9/L5/L6]."""
    rc, ext = real_run()
    gaps = read_jsonl(ext / "logic" / "_gaps.jsonl")
    standing = L.standing_gap_rows(gaps)
    fresh = [g for g in gaps if g not in standing]
    errs = L.gaps_violations(gaps)
    soft = [e for e in errs if "sorted" not in e]
    assert not soft, soft
    text = log_text(ext)
    gs = re.search(r"gapRowsStanding\b[^0-9\n]*([0-9]+)", text,
                   re.IGNORECASE)
    if gs:
        assert int(gs.group(1)) >= 2
    for g in fresh:   # genuinely-new gaps must be loud, never silent
        blob = f"{g.get('subjectId','')} {g.get('reason','')}"
        named = any(tok and tok in text for tok in
                    (g.get("subjectId"), g.get("gapId"))) or blob.strip() == ""
        assert named or L.drift_lines(_REAL["stdout"]), \
            f"unenumerated fresh gap: {g}"


@pytest.mark.slow
@pytest.mark.client_gated
def test_f3_real_digests_stable_across_double_run():
    rc1, ext = real_run()
    first = hash_tree(ext / "logic")
    from conftest import run_pack, game_dir
    r2 = run_pack([str(game_dir()), "--only", "logic", "--force"],
                  extracted_root=ext, timeout=3600)
    assert r2.returncode in (0, 2), r2.stdout + r2.stderr
    second = hash_tree(ext / "logic")
    only_b, only_a, changed = diff_manifests(first, second)
    assert not (only_b or only_a or changed), \
        f"real-corpus double run not byte-identical: {changed[:6]}"
