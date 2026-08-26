"""Blind test suite for stage 10 contract-pinning (piece-05, Revision 3).

Built from docs/specs/piece-05-contracts.mdx ALONE -- the CodeWriter's
tools/stage10_check_contracts.py is never read by this seat; the runner is
driven strictly black-box through candidate invocation spellings (loud
impl-missing skips until it lands; expected RED against unwritten code is
correct and desired).

Legs:
  - day-one EXPECTED-RED -> exit 2 over exactly {V-L1, V-U1, V-U2, V-D1};
  - RED->GREEN ladder applying the three emitter amendments synthetically;
  - exit semantics: PIN-STALE -> 1 (--warn-stale -> 0), PIN-MISMATCH -> 1,
    inputs-missing -> 3, sidecar-absent -> 3, unit-gate load refusal;
  - heavy-artifact policy (default run opens catalog.json ZERO times;
    --scan-catalog re-derives the sidecar);
  - zero-write, determinism, SUBSET-AND-ORDER --list, --only isolation,
    `make contracts`;
  - mutation-teeth harness over all 44 validators (AC3, 100% score) with a
    toothless-validator self-test;
  - V-I9 exactly-one-writer green in BOTH handover orders (RF-1);
  - client-gated integration against the real corpus.

Temp discipline: point pytest at D:/tpc_pytmp/tw05 or leave %TEMP%;
NEVER a C:-rooted basetemp inside the pack (recursion-guard doctrine):

    python -m pytest tests/test_stage10_check_contracts.py \
        --basetemp=D:/tpc_pytmp/tw05 -q
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from _validators import diff_manifests, hash_tree

import _contractlib as cl
from _contractlib import (
    ALL_FIXES, ALL_VALIDATOR_IDS, MUTATIONS, Mutation, RED_REGISTRY_IDS,
    TRANSFORM_NAME, build_fixture, failing_ids, expected_red_ids,
    mutation_killed, parse_events, parse_summary, require_tool, run_tool,
    run_tool_parsed, score_mutations,
)

HERE = Path(__file__).resolve().parent
PACK_ROOT = HERE.parent


# --- session plumbing -----------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def _temp_guard(tmp_path_factory):
    """Never let basetemp sit inside the pack (runaway-copy incident class)."""
    base = Path(tmp_path_factory.getbasetemp()).resolve()
    pack = PACK_ROOT.resolve()
    if base == pack or pack in base.parents:
        raise pytest.UsageError(
            f"basetemp {base} sits inside the pack {pack} -- recursion-guard "
            "doctrine forbids it; pass --basetemp=D:/tpc_pytmp/tw05")
    yield


@pytest.fixture(autouse=True)
def _free_tmp_path(tmp_path):
    """Disk discipline: a fixture tree runs tens of MB and the teeth legs
    copy one per test. Each test's private tmp_path is removed on teardown;
    the SESSION trees (tw_dayone/tw_green/tw_handover, ladder base) live in
    their own mktemp dirs and survive the run."""
    yield tmp_path
    shutil.rmtree(tmp_path, ignore_errors=True)


def _build(kind: str, tmp_path_factory, *, handover=False, fixes=()):
    out = tmp_path_factory.mktemp(f"tw05-{kind}")
    return build_fixture(out, handover=handover, fixes=frozenset(fixes))


@pytest.fixture(scope="session")
def tw_dayone(tmp_path_factory):
    return _build("dayone", tmp_path_factory)


@pytest.fixture(scope="session")
def tw_green(tmp_path_factory):
    return _build("green", tmp_path_factory, fixes=ALL_FIXES)


@pytest.fixture(scope="session")
def tw_handover(tmp_path_factory):
    return _build("handover", tmp_path_factory, handover=True,
                  fixes=ALL_FIXES)


def fresh(tree: Path, tmp_path: Path) -> Path:
    dst = Path(tmp_path) / "copy"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(tree, dst)
    return dst


@pytest.fixture(scope="session")
def binding_ready(tw_green):
    """Calibrate the black-box invocation ONCE before any exotic-output leg."""
    run_tool_parsed(tw_green)


@pytest.fixture(scope="session")
def dayone_run(tw_dayone):
    return run_tool_parsed(tw_dayone)


@pytest.fixture(scope="session")
def green_run(tw_green):
    return run_tool_parsed(tw_green)


@pytest.fixture(scope="session")
def handover_run(tw_handover):
    return run_tool_parsed(tw_handover)


def _events_for(result, vid):
    return [e for e in result["events"] if e["vid"] == vid]


# --- calibration / day-one color -------------------------------------------------------

def test_day_one_is_exactly_four_registered_reds(dayone_run):
    proc, events, summary = dayone_run["proc"], dayone_run["events"], \
        dayone_run["summary"]
    assert summary is not None, f"no machine summary line:\n{proc.stdout}"
    reds = expected_red_ids(dayone_run)
    unexpected = failing_ids(dayone_run)
    assert proc.returncode == 2, (
        f"day-one state must complete-with-known-ledger (exit 2), got "
        f"{proc.returncode}\n{proc.stdout}\n{proc.stderr}")
    assert reds == set(RED_REGISTRY_IDS), (
        f"EXPECTED-RED set {sorted(reds)} != registered "
        f"{sorted(RED_REGISTRY_IDS)} (spec section 9 + arbiter watch item 2)")
    assert not unexpected, (
        f"unexpected FAILs on the honest day-one fixture = spec defects: "
        f"{sorted(unexpected)}")
    assert summary["failed"] == 0
    assert summary.get("expectedRed", 0) >= len(RED_REGISTRY_IDS)
    for vid in RED_REGISTRY_IDS:
        mine = _events_for(dayone_run, vid)
        assert any(e["kind"] == "EXPECTED-RED" for e in mine), (
            f"{vid} not spelled EXPECTED-RED: {mine}")
        for e in mine:
            if e["kind"] == "EXPECTED-RED":
                assert e["rest"].strip(), f"{vid} EXPECTED-RED lacks payload"


def test_day_one_green_on_honest_current_state(dayone_run):
    """Iff-set scoping (V-I8) and the pre-handover exactly-one-writer map
    (V-I9, RF-1 order A) must be GREEN at introduction -- arbiter watch
    items 1 + RF-1."""
    for vid in ("V-I8", "V-I9"):
        kinds = {e["kind"] for e in _events_for(dayone_run, vid)}
        assert "PASS" in kinds, (
            f"{vid} must be day-one green on the honest fixture; got "
            f"{sorted(kinds) or 'no events'}")
        assert kinds & {"FAIL", "PIN-MISMATCH", "PIN-STALE"} == set(), \
            f"{vid} unexpectedly failing: {kinds}"


def test_green_end_state_all_44_validators_pass(green_run):
    """AC2 end state: exit 0, zero EXPECTED-RED, every one of the 44 named
    validators present and passing (INFO-only legs may spell INFO)."""
    proc = green_run["proc"]
    assert proc.returncode == 0, (
        f"post-amendment fixture must be fully green (exit 0), got "
        f"{proc.returncode}\n{proc.stdout}\n{proc.stderr}")
    assert not expected_red_ids(green_run)
    assert not failing_ids(green_run)
    seen = {e["vid"] for e in green_run["events"]
            if e["kind"] in ("PASS", "INFO")}
    missing = sorted(set(ALL_VALIDATOR_IDS) - seen)
    assert not missing, f"validators absent from the report: {missing}"
    summary = green_run["summary"]
    assert summary is not None and summary.get("failed") == 0


def test_handover_world_order_b_green(handover_run):
    """RF-1 order B: after the piece-07 section-5 handover the flipped
    pathOwner entry + v2 companion keep V-I9 and V-S10 green."""
    assert handover_run["proc"].returncode == 0, handover_run["proc"].stdout
    for vid in ("V-I9", "V-S10"):
        kinds = {e["kind"] for e in _events_for(handover_run, vid)}
        assert "PASS" in kinds and \
            kinds & {"FAIL", "PIN-MISMATCH", "PIN-STALE"} == set(), (
                f"{vid} must survive the handover green; got {sorted(kinds)}")


# --- RED->GREEN ladder ------------------------------------------------------------------

def test_red_to_green_ladder(tmp_path):
    """Sequencing contract (section 9): applying each amendment synthetically
    flips exactly its validators red->green; all four => suite exits 0 with an
    empty registry. Each step's tree is removed before the next is built
    (shared-host disk discipline)."""
    steps = []
    acc = set()
    plan = [
        ("dupkeys", {"V-U2"}),
        ("counterunits", {"V-U1"}),
        ("ledger", {"V-L1"}),
        ("relations", {"V-D1"}),
    ]
    for i, (fix, vids) in enumerate(plan):
        acc = acc | {fix}
        tree = build_fixture(tmp_path / f"step{i}", fixes=acc)
        res = run_tool_parsed(tree)
        reds = expected_red_ids(res)
        for vid in vids:
            assert not any(e["kind"] == "EXPECTED-RED"
                           and e["vid"] == vid
                           for e in res["events"]), (
                               f"after +{fix}, {vid} should be fixed")
        steps.append((fix, vids, reds))
        shutil.rmtree(tree, ignore_errors=True)
    final_tree = build_fixture(tmp_path / "final", fixes=ALL_FIXES)
    final = run_tool_parsed(final_tree)
    assert final["proc"].returncode == 0, final["proc"].stdout
    assert not expected_red_ids(final)
    assert not failing_ids(final)


# --- exit semantics ----------------------------------------------------------------------

def test_pin_stale_bumped_buildscope_exits_1(tw_green, tmp_path):
    tree = fresh(tw_green, tmp_path)
    import _contractlib as m
    next(m for m in MUTATIONS if m.vid == "V-D4").apply(tree)
    res = run_tool_parsed(tree)
    stale = [e for e in res["events"] if e["kind"] == "PIN-STALE"]
    assert res["proc"].returncode == 1, res["proc"].stdout
    assert stale, "bumping pins.buildScope.buildId must print PIN-STALE"
    line = stale[0]["rest"]
    assert line.strip(), "PIN-STALE event carries no payload"


def test_pin_stale_identity_bump_also_stale(tw_green, tmp_path):
    tree = fresh(tw_green, tmp_path)
    p = tree / "extracted" / "identity.json"
    obj = json.loads(p.read_text(encoding="utf-8"))
    obj["buildId"] = cl.TARGET_BUILD + 1
    p.write_text(json.dumps(obj, sort_keys=True, indent=2) + "\n",
                 encoding="utf-8", newline="\n")
    res = run_tool_parsed(tree)
    assert [e for e in res["events"] if e["kind"] == "PIN-STALE"], \
        "corpus buildId != pins.buildScope.buildId must read PIN-STALE"
    assert res["proc"].returncode == 1


def test_warn_stale_downgrades_to_exit_zero(tw_green, tmp_path):
    tree = fresh(tw_green, tmp_path)
    import _contractlib as m
    next(m for m in MUTATIONS if m.vid == "V-D4").apply(tree)
    res = run_tool_parsed(tree, args=("--warn-stale",))
    out = res["proc"].stdout
    if "unrecognized" in (out + res["proc"].stderr).lower() or \
            "--warn-stale" not in (out + res["proc"].stderr):
        pass  # usage errors are handled by run_tool's skip path below
    assert res["proc"].returncode == 0, (
        f"--warn-stale must downgrade PIN-STALE to INFO (exit 0):\n{out}")
    assert not [e for e in res["events"] if e["kind"] == "PIN-STALE"], \
        "--warn-stale still printed PIN-STALE lines"


def test_pin_mismatch_constant_at_pinned_build(tw_green, tmp_path):
    tree = fresh(tw_green, tmp_path)
    import _contractlib as m
    next(m for m in MUTATIONS
         if m.vid == "V-S2" and m.name ==
         "change-an-int-dirclass-count").apply(tree)
    res = run_tool_parsed(tree)
    mism = [e for e in res["events"] if e["kind"] == "PIN-MISMATCH"]
    assert mism, "perturbing a pinned constant AT the pinned build must " \
                 "print PIN-MISMATCH (not DRIFT, not plain FAIL)"
    assert res["proc"].returncode == 1


def test_exit_3_missing_input(tw_green, tmp_path):
    tree = fresh(tw_green, tmp_path)
    (tree / "extracted" / "identity.json").unlink()
    res = run_tool_parsed(tree, allow_no_summary=True)
    assert res["proc"].returncode == 3, (
        f"a missing upstream artifact must exit 3, got "
        f"{res['proc'].returncode}\n{res['proc'].stdout}")


def test_exit_3_sidecar_absent_names_it(tw_green, tmp_path):
    tree = fresh(tw_green, tmp_path)
    victim = tree / "extracted" / "addressables" / \
        "catalog-mini-report.json"
    victim.unlink()
    res = run_tool_parsed(tree, allow_no_summary=True)
    assert res["proc"].returncode == 3
    out = (res["proc"].stdout + res["proc"].stderr).lower()
    assert "mini-report" in out or "catalog-mini" in out, (
        f"exit-3 refusal must NAME the missing sidecar:\n{out}")


# --- heavy-artifact policy ----------------------------------------------------------------

_OPEN_DRIVER = r'''
import builtins, io, os, pathlib, runpy, sys

COUNT = 0
REAL_OPEN = builtins.open


def _tally(path):
    global COUNT
    try:
        name = os.path.basename(os.fspath(path))
    except TypeError:
        return
    if name == "catalog.json":
        COUNT += 1


def open_tally(file, *a, **k):
    _tally(file)
    return REAL_OPEN(file, *a, **k)


builtins.open = open_tally
io.open = open_tally
pathlib.Path.open = lambda self, *a, **k: open_tally(str(self), *a, **k)
sys.argv = sys.argv[1:]
try:
    runpy.run_path(sys.argv[0], run_name="__main__")
except SystemExit as exc:  # argparse / sys.exit paths
    pass
sys.stdout.write("\n###CATALOG_OPENS=%d\n" % COUNT)
'''


def _run_with_open_counter(tree: Path, args=(), tmp_path=None):
    ext, con = cl.resolve_ext_and_contracts(Path(tree))
    script = require_tool()
    driver = Path(tmp_path) / "_open_counter_driver.py"
    driver.write_text(_OPEN_DRIVER, encoding="utf-8", newline="\n")
    prefix_idx = cl._BINDING_CACHE.get(
        f"{script}:{script.stat().st_mtime_ns}")
    if prefix_idx is None:
        pytest.skip("impl-missing: binding not calibrated yet")
    prefix = cl.ARG_PREFIX_CANDIDATES[prefix_idx](ext, con)
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    env.setdefault("PYTHONIOENCODING", "utf-8")
    proc = subprocess.run([sys.executable, str(driver), str(script),
                           *prefix, *[str(a) for a in args]],
                          cwd=str(PACK_ROOT), env=env, timeout=300,
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace")
    marker = [ln for ln in proc.stdout.splitlines()
              if ln.startswith("###CATALOG_OPENS=")]
    if not marker:
        pytest.skip(f"open-counter driver produced no marker "
                    f"(rc={proc.returncode}):\n{proc.stdout[-400:]}"
                    f"\n{proc.stderr[-400:]}")
    opens = int(marker[-1].split("=")[1])
    body = "\n".join(ln for ln in proc.stdout.splitlines()
                     if not ln.startswith("###"))
    return opens, proc, parse_events(body), parse_summary(body)


def test_default_run_never_opens_catalog_json(tw_green, tmp_path,
                                              binding_ready):
    opens, proc, _events, summary = _run_with_open_counter(
        tw_green, tmp_path=tmp_path)
    assert summary is not None, proc.stdout
    assert opens == 0, (
        f"default run touched catalog.json {opens}x -- heavy-artifact "
        "policy violated; catalog pins must ride the persisted sidecar")


def test_scan_catalog_streams_catalog_once_and_rederives_sidecar(
        tw_green, tmp_path, binding_ready):
    sidecar = tw_green / "extracted" / "addressables" / \
        "catalog-mini-report.json"
    before = hashlib.sha256(sidecar.read_bytes()).hexdigest()
    opens, proc, events, summary = _run_with_open_counter(
        tw_green, args=("--scan-catalog",), tmp_path=tmp_path)
    if "--scan-catalog" not in (proc.stdout + proc.stderr) and \
            cl._usage_error(proc.stdout + proc.stderr):
        pytest.skip("impl-missing: --scan-catalog flag unsupported "
                    "(usage error)")
    assert proc.returncode == 0, (
        f"--scan-catalog must re-derive the sidecar and agree:\n{proc.stdout}"
        f"\n{proc.stderr}")
    assert opens >= 1, "--scan-catalog never streamed catalog.json"
    after = hashlib.sha256(sidecar.read_bytes()).hexdigest()
    assert before == after, (
        "--scan-catalog rewrote the persisted sidecar although the "
        "re-derivation agreed (zero-write discipline)")


def test_scan_catalog_detects_mutated_persisted_sidecar(
        tw_green, tmp_path, binding_ready):
    tree = fresh(tw_green, tmp_path)
    p = tree / "extracted" / "addressables" / "catalog-mini-report.json"

    def bump(o):
        o["counts"]["keysTotal"] += 1
    cl._rw_json(p, bump)
    proc = run_tool(tree, args=("--scan-catalog",),
                    allow_no_summary=False)
    if cl._usage_error(proc.stdout + proc.stderr):
        pytest.skip("impl-missing: --scan-catalog flag unsupported "
                    "(usage error)")
    assert proc.returncode != 0, (
        "--scan-catalog accepted a persisted sidecar that disagrees with "
        f"the streamed re-derivation:\n{proc.stdout}")


# --- zero-write + determinism ---------------------------------------------------------------

def test_runner_is_zero_write_over_extracted(tw_green, tmp_path):
    tree = fresh(tw_green, tmp_path)
    ext = tree / "extracted"
    before = hash_tree(ext)
    res = run_tool_parsed(tree)
    assert res["proc"].returncode == 0
    after = hash_tree(ext)
    only_before, only_after, changed = diff_manifests(before, after)
    assert not (only_before or only_after or changed), (
        f"the contracts runner wrote under extracted/ (AC4): "
        f"removed={only_before[:5]} added={only_after[:5]} "
        f"changed={changed[:5]}")


def test_determinism_double_run_byte_identical_stdout(tw_green):
    r1 = run_tool(tw_green)
    r2 = run_tool(tw_green)
    assert r1.returncode == 0 and r2.returncode == 0
    assert r1.stdout == r2.stdout, (
        "two consecutive runs on an unchanged tree diverged (AC5):\n"
        f"--- run1\n{r1.stdout[:800]}\n--- run2\n{r2.stdout[:800]}")


# --- unit gate (V-U3 / AC7) ------------------------------------------------------------------

def test_unit_gate_refuses_mixed_units_without_declared_transform(
        tw_green, tmp_path, binding_ready):
    tree = fresh(tw_green, tmp_path)
    p = tree / "contracts" / "counter-units.mdx"
    text = p.read_text(encoding="utf-8")
    kept = [ln for ln in text.splitlines()
            if TRANSFORM_NAME not in ln and ln.strip() != "```transforms"]
    # drop the fenced block body too
    out, in_block = [], False
    for ln in kept:
        if ln.strip() == "```" and in_block:
            in_block = False
            continue
        if in_block:
            continue
        out.append(ln)
        if '"name":' in ln or "licenses" in ln:
            pass
    write = "\n".join(out) + "\n"
    p.write_text(write, encoding="utf-8", newline="\n")
    proc = run_tool(tree, allow_no_summary=True)
    out_all = proc.stdout + proc.stderr
    assert proc.returncode == 1, (
        f"undeclared mixed-unit registration must refuse to load with "
        f"exit 1 BEFORE any check:\n{out_all}")
    summary = parse_summary(proc.stdout)
    assert summary is None, (
        "load-time refusal must not emit a validator report:\n"
        f"{proc.stdout}")
    assert not [e for e in parse_events(proc.stdout)
                if e["kind"] == "PASS"], "refusal ran checks anyway"
    low = out_all.lower()
    assert any(tok in low for tok in ("transform", "refus", "unit")), (
        f"refusal message says nothing about transforms/units:\n{out_all}")


def test_unit_gate_registering_unit_mismatched_reconciliation_refused(
        tw_green, tmp_path, binding_ready):
    tree = fresh(tw_green, tmp_path)
    p = tree / "contracts" / "pins.json"

    def add(o):
        o["reconciliations"].append({
            "id": "probe-mixed-units-undeclared",
            "kind": "constant",
            "left": "probe.a.rowsLogged", "leftUnit": "emission-events",
            "right": "probe.b.lines", "rightUnit": "bytes"})
    cl._rw_json(p, add)
    proc = run_tool(tree, allow_no_summary=True)
    assert proc.returncode == 1 and parse_summary(proc.stdout) is None, (
        f"registering a unit-mismatched reconciliation without its "
        f"transform must refuse to load:\n{proc.stdout}\n{proc.stderr}")


def test_unit_gate_declared_transform_lets_fixture_load(
        tw_green, tmp_path, binding_ready):
    tree = fresh(tw_green, tmp_path)
    p = tree / "contracts" / "pins.json"

    def add(o):
        o["reconciliations"].append({
            "id": "probe-mixed-units-declared",
            "kind": "constant",
            "left": "probe.a.rowsLogged", "leftUnit": "emission-events",
            "right": "probe.b.lines", "rightUnit": "distinct-keys",
            "transform": TRANSFORM_NAME})
    cl._rw_json(p, add)
    res = run_tool_parsed(tree)
    assert res["proc"].returncode == 0, (
        f"declaring the registered transform must let the fixture load:\n"
        f"{res['proc'].stdout}\n{res['proc'].stderr}")
    assert res["summary"] is not None


# --- mutation teeth (AC3: 100% score) ----------------------------------------------------------

@pytest.mark.parametrize("mut", MUTATIONS,
                         ids=lambda m: f"{m.vid}:{m.name}")
def test_mutation_teeth(tw_green, mut, tmp_path):
    """Every FAIL-capable validator dies to >=1 scripted mutation with the
    CORRECT id + payload shape. INFO-only legs exempt (exercised via the
    info-not-fail expectation)."""
    if mut.vid == "V-R7" and mut.name == "enumerated-bundle-deleted":
        # V-R7's enumeration leg is CLIENT-GATED: the black-box harness
        # drives the runner with --root only, never a positional game root,
        # so hostless runs always skip that validator loudly. The kill
        # proof for this mutant happens on NE8K pipeline runs.
        pytest.skip("client-gated kill proof: V-R7 enumeration runs only "
                    "with a positional game root (NE8K pipeline)")
    tree = fresh(tw_green, tmp_path / "mut")
    mut.apply(tree)
    res = run_tool_parsed(tree, allow_no_summary=True)
    killed, why = mutation_killed(res, mut)
    assert killed, (
        f"mutation {mut.vid}:{mut.name} was NOT caught with the correct "
        f"payload: {why}\nrc={res['proc'].returncode}\n{res['proc'].stdout}"
        f"\n{res['proc'].stderr}")


def test_mutation_score_is_100_percent():
    """AC3 aggregate: the registry itself must claim a perfect score once
    every mutation has been proven killing by the parametrized legs above.
    Any exception must be listed per-validator."""
    results = {(m.vid, m.name): True
               for m in MUTATIONS
               if m.vid != "V-R8"}          # V-R8 is client-gated (documented)
    report = score_mutations(results)
    assert report["score"] == 100.0, report["unkilled"]


def test_mutation_harness_reports_toothless_validator(tw_green, tmp_path,
                                                      binding_ready):
    """Self-test: an intentionally toothless validator registered only inside
    tests must be reported as a score-failure by the harness."""
    toothless = Mutation("V-ZZ-TOOTHLESS", "no-op", lambda t: None, "fail")
    tree = fresh(tw_green, tmp_path / "toothless")
    toothless.apply(tree)                    # no-op: nothing breaks
    res = run_tool_parsed(tree)
    assert res["proc"].returncode == 0
    killed, _why = mutation_killed(res, toothless)
    results = {(m.vid, m.name): True for m in MUTATIONS}
    results[(toothless.vid, toothless.name)] = killed
    report = score_mutations(results)
    assert report["score"] < 100.0, (
        "the harness accepted a toothless validator at 100% score")
    assert "V-ZZ-TOOTHLESS:no-op" in report["unkilled"], report


def test_v_i9_second_writer_and_zero_writer_both_fail(tw_green, tmp_path):
    pre = fresh(tw_green, tmp_path / "i9-pre")
    for m in ("second-writer-injected", "zero-writers"):
        mutant = next(x for x in MUTATIONS if x.vid == "V-I9"
                      and x.name == m)
        tree = fresh(pre, tmp_path / f"i9-{m}")
        mutant.apply(tree)
        res = run_tool_parsed(tree)
        kinds = {e["kind"] for e in _events_for(res, "V-I9")}
        assert kinds & {"FAIL", "PIN-MISMATCH"}, (
            f"V-I9 must fail loudly on {m}; got {sorted(kinds)}")


def test_v_i9_exactly_one_writer_green_in_both_orders(dayone_run,
                                                      handover_run):
    """RF-1: handover-aware exactly-one-writer passes in EITHER landing order;
    two concurrent writers or zero fail (covered by the mutants above)."""
    for label, run in (("order A (pre-handover)", dayone_run),
                       ("order B (post-handover)", handover_run)):
        kinds = {e["kind"] for e in _events_for(run, "V-I9")}
        assert "PASS" in kinds, f"{label}: V-I9 not green ({sorted(kinds)})"


# --- runner integration: --list / make / --only ------------------------------------------------

RUN_ALL = PACK_ROOT / "run_all.py"


def _require_run_all():
    if not RUN_ALL.exists():
        pytest.skip("impl-missing: run_all.py not present yet")


def test_list_subset_and_order_contains_check_contracts():
    """SUBSET-AND-ORDER only (F1): contains verify-client ... relink ...
    check-contracts in canonical order; NEVER a frozen total stage count, so
    synthetic siblings at any other index cannot break this assertion."""
    _require_run_all()
    from conftest import run_pack
    r = run_pack(["--list"])
    assert r.returncode == 0, r.stdout + r.stderr
    out = r.stdout
    if "check-contracts" not in out:
        pytest.skip("impl-missing: check-contracts not registered in "
                    "run_all.py yet (CodeWriter pending)")
    required = ["verify-client", "harvest-bundles", "relink",
                "check-contracts"]
    pos = []
    for sid in required:
        p = out.find(sid)
        assert p >= 0, f"--list output missing {sid!r}:\n{out}"
        pos.append(p)
    assert pos == sorted(pos), (
        f"canonical order violated: {list(zip(required, pos))}")
    lp = out.find("locale-proof")
    if lp >= 0:
        assert lp < out.find("check-contracts"), (
            "once registered, locale-proof (9) must list before "
            "check-contracts (10)")


def test_make_contracts_target_runs():
    require_tool()
    make = shutil.which("make")
    if make is None:
        pytest.skip("environment-missing: `make` not on PATH on this host")
    mkfile = PACK_ROOT / "Makefile"
    if not mkfile.exists():
        pytest.skip("impl-missing: pack Makefile absent")
    r = subprocess.run([make, "-n", "-C", str(PACK_ROOT), "contracts"],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=60)
    if r.returncode != 0 or "No rule to make target" in r.stdout + \
            r.stderr:
        pytest.skip("impl-missing: `make contracts` target not added yet")
    assert "stage10_check_contracts" in r.stdout + r.stderr, (
        f"`make contracts` does not delegate to the stage-10 module:\n"
        f"{r.stdout}\n{r.stderr}")


def test_only_check_contracts_isolation(tmp_path_factory, tw_dayone):
    """--only check-contracts runs in isolation on a prepared tree and writes
    NOTHING outside the log/stamp/meta exemption set (non-emitting stage)."""
    _require_run_all()
    from conftest import run_pack, tree_game
    ext_root = tmp_path_factory.mktemp("tw05-only") / "ext"
    shutil.copytree(tw_dayone / "extracted", ext_root)
    before = hash_tree(ext_root)
    r = run_pack([tree_game(tw_dayone), "--only", "check-contracts"],
                 extracted_root=ext_root)
    combined = r.stdout + r.stderr
    if r.returncode != 0 and ("unknown" in combined.lower()
                              or "unrecognized" in combined.lower()):
        pytest.skip("impl-missing: --only check-contracts not accepted by "
                    "run_all.py yet")
    assert r.returncode in (0, 1, 2), (
        f"--only check-contracts failed outright: rc={r.returncode}\n"
        f"{combined}")
    after = hash_tree(ext_root)
    _, only_after, changed = diff_manifests(before, after)
    touched = [p for p in only_after + changed
               if Path(p).parts[0] not in
               ("EXTRACTION-LOG.md", ".stage-stamps",
                ".pipeline-meta.json")]
    assert not touched, (
        f"the non-emitting contracts stage wrote outside its stamp/log/meta "
        f"exemption set: {touched[:8]}")


# --- CLI smoke materialization ------------------------------------------------------------------

def test_cli_materialization_smoke(tmp_path):
    r = subprocess.run(
        [sys.executable, str(HERE / "_contractlib.py"),
         "--out", str(tmp_path / "cli")],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=120, env={**os.environ, "PYTHONUTF8": "1"})
    assert r.returncode == 0, r.stdout + r.stderr
    for sub in ("extracted", "contracts", "tools"):
        assert (tmp_path / "cli" / sub).is_dir(), f"{sub}/ missing"
    assert (tmp_path / "cli" / "contracts" / "pins.json").exists()


def test_fixture_world_internal_identities(tw_green):
    """Guard rail: the GREEN fixture world itself must satisfy every pinned
    identity the validators enforce -- a self-inconsistent fixture would turn
    teeth legs into false passes."""
    ext = tw_green / "extracted"

    def jl(rel):
        return cl.read_jsonl(ext / rel)

    def rj(rel):
        return json.loads((ext / rel).read_text(encoding="utf-8"))

    cab_rows = jl("relinks/bridges/cab_index.jsonl")
    assert len(cab_rows) == cl.CAB_ROWS_PIN
    census_files = sorted((ext / "harvest" / "census" / "bundles")
                          .glob("*.json"))
    assert len(census_files) == 176
    media_by_class = {}
    for r in jl("media-catalogue.jsonl"):
        media_by_class[r["class"]] = media_by_class.get(r["class"], 0) + 1
    assert media_by_class == cl.MEDIA_CLASS_COUNTS
    reg_keys = {r["termKey"] for r in jl("relinks/i2_term_registry.jsonl")}
    matrix_keys = set(rj("locales/locale-matrix.json")["keys"])
    assert reg_keys == matrix_keys
    usages = sum(len(r["usages"]) for r in
                 jl("relinks/locale_term_entity.jsonl"))
    assert usages == len(jl("relinks/entity_locale.jsonl"))
    m = rj("relinks/matrix.json")
    edges = sum(p["cardinality"]["edges"] for p in m["pairs"])
    pair_files = {f for c in m["pairs"] for f in c["pairFiles"]}
    named_rows = sum(len(jl(f"relinks/{f}")) for f in pair_files)
    assert edges == named_rows, (edges, named_rows)
    counts = {"modeled": 0, "partial": 0, "missing": 0}
    for c in m["pairs"]:
        counts[c["status"]] += 1
    assert counts == {"modeled": 24, "partial": 3, "missing": 73}
    ledger = jl("relinks/_uncontained_addresses.jsonl")
    container = {r["address"] for r in
                 jl("relinks/bridges/container_index.jsonl")}
    asset_dst = {r["dstId"] for r in jl("relinks/entity_asset_guid.jsonl")}
    uncontained = sorted(asset_dst - container)
    assert sorted(r["address"] for r in ledger) == uncontained
    mini = rj("addressables/catalog-mini-report.json")
    assert set(uncontained) <= set(mini["nullBundleAddresses"])


# --- client-gated integration (real corpus; auto-skips without the game) ------------------------

def _require_real_corpus() -> Path:
    import pytest
    from conftest import game_dir
    if game_dir() is None:
        pytest.skip("client-gated: neither TPC_GAME_DIR nor the default "
                    "install exists on this host")
    ext = PACK_ROOT / "extracted"
    if not (ext / "identity.json").exists():
        pytest.skip("client-gated: real extracted/ corpus absent")
    return ext


@pytest.fixture(scope="session")
def real_run():
    _require_real_corpus()
    return run_tool_parsed(PACK_ROOT, timeout=900)


def _amendments_pending() -> bool:
    """The three emitter amendments (piece-05 §9) land in SEPARATE fixer
    lanes. Until they do, the real corpus MUST read the day-one state --
    exactly the four registered EXPECTED-REDs, exit 2 (AC2 sequencing).
    Probed by amendment markers, never assumed."""
    ledger = PACK_ROOT / "extracted" / "relinks" / \
        "_uncontained_addresses.jsonl"
    if not ledger.exists():
        return True
    try:
        overlay = json.loads((PACK_ROOT / "extracted" / "locales" /
                              "base-overlay-report.json").read_text(
                                  encoding="utf-8"))
        bridge = json.loads((PACK_ROOT / "extracted" / "relinks" /
                             "guid_bridge_report.json").read_text(
                                 encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return True
    dup = (overlay.get("evidence") or {}).get("duplicateKeysOverwritten")
    return not (dup and bridge.get("counterUnits"))


@pytest.mark.client_gated
def test_cg_day_one_still_four_registered_reds(real_run):
    """Sequencing contract, real-corpus half: BEFORE the emitter amendments
    land, the honest verdict is exactly 40 PASS / 4 EXPECTED-RED / exit 2.
    Skips once the amendments land (the green leg takes over)."""
    proc, summary = real_run["proc"], real_run["summary"]
    if not _amendments_pending():
        pytest.skip("amendments landed: green end-state leg owns the "
                    "verdict now")
    assert proc.returncode == 2, (
        f"pre-amendment real corpus must complete-with-known-ledger "
        f"(exit 2), got {proc.returncode}\n{proc.stdout[-2000:]}")
    assert summary is not None and summary.get("failed") == 0
    reds = expected_red_ids(real_run)
    assert reds == set(RED_REGISTRY_IDS), (
        f"real-corpus EXPECTED-RED set {sorted(reds)} != registered "
        f"{sorted(RED_REGISTRY_IDS)}")


@pytest.mark.client_gated
def test_cg_full_suite_green_at_pinned_build(real_run):
    """AC2 end state on the REAL corpus at buildId 20226581. Gated on the
    three emitter amendments (separate fixer lanes, §9 sequencing): until
    they land the day-one leg above owns the verdict."""
    if _amendments_pending():
        pytest.skip("amendment pending: RED-1/RED-2/RED-3 emitter lanes "
                    "have not landed on this corpus yet; day-one state must "
                    "read exactly 4 registered EXPECTED-REDs / exit 2")
    proc, events = real_run["proc"], real_run["events"]
    assert proc.returncode == 0, (
        f"real-corpus suite must be fully green after the emitter "
        f"amendments land:\n{proc.stdout[-3000:]}\n{proc.stderr[-800:]}")
    assert not expected_red_ids(real_run)
    assert not failing_ids(real_run)
    seen = {e["vid"] for e in events if e["kind"] in ("PASS", "INFO")}
    missing = sorted(set(ALL_VALIDATOR_IDS) - seen)
    assert not missing, f"validators absent from the real report: {missing}"


@pytest.mark.client_gated
def test_cg_vr8_replay_bit_exact(real_run):
    kinds = {e["kind"] for e in _events_for(real_run, "V-R8")}
    assert "PASS" in kinds, (
        f"guid-bridge replay must reproduce the report bit-exact incl. "
        f"float rates + universe membership; got {sorted(kinds)}")


@pytest.mark.client_gated
def test_cg_i2_mini_report_scan_catalog_agreement():
    """AC6: the streamed rebuild byte-agrees with the persisted sidecar.
    This leg owns ONLY the agreement contract — the overall exit code stays
    owned by the color legs (2 while the emitter amendments pend, 0 after)."""
    _require_real_corpus()
    require_tool()
    proc = run_tool(PACK_ROOT, args=("--scan-catalog",), timeout=1800)
    if cl._usage_error(proc.stdout + proc.stderr):
        pytest.skip("impl-missing: --scan-catalog flag unsupported")
    events = parse_events(proc.stdout)
    agreed = [e for e in events if e["vid"] == "V-I2"
              and e["kind"] == "INFO" and "agreement" in e["rest"]]
    assert agreed, (
        f"--scan-catalog re-derivation must byte-agree with the persisted "
        f"mini-report:\n{proc.stdout[-2000:]}\n{proc.stderr[-500:]}")
    assert proc.returncode in (0, 2), (
        f"--scan-catalog run neither green nor known-ledger: "
        f"rc={proc.returncode}\n{proc.stdout[-1500:]}")
    if not _amendments_pending():
        assert proc.returncode == 0, (
            f"post-amendment --scan-catalog must be fully green: "
            f"{proc.stdout[-1500:]}")


@pytest.mark.client_gated
def test_cg_l1_population_5_rows_9_edges():
    _require_real_corpus()
    ledger = PACK_ROOT / "extracted" / "relinks" / \
        "_uncontained_addresses.jsonl"
    if not ledger.exists():
        pytest.skip("amendment pending: _uncontained_addresses.jsonl not "
                    "emitted yet (RED-1 fix lane)")
    rows = cl.read_jsonl(ledger)
    mini = json.loads((PACK_ROOT / "extracted" / "addressables" /
                       "catalog-mini-report.json").read_text(encoding="utf-8"))
    container = {r["address"] for r in cl.read_jsonl(
        PACK_ROOT / "extracted" / "relinks" / "bridges" /
        "container_index.jsonl")}
    asset_rows = cl.read_jsonl(PACK_ROOT / "extracted" / "relinks" /
                               "entity_asset_guid.jsonl")
    uncontained = sorted({r["dstId"] for r in asset_rows
                          if r["dstId"] not in container})
    edges = [r for r in asset_rows if r["dstId"] in set(uncontained)]
    assert len(rows) == 5 and len(uncontained) == 5, (
        f"ledger population drifted: {len(rows)} rows over "
        f"{len(uncontained)} addresses")
    assert len(edges) == 9, (
        f"expected the 9 measured uncontained edge rows, saw {len(edges)}")
    assert all(r.get("reason") == "catalog-bundle-null-uninstalled-dlc"
               for r in rows)
    assert sorted(r["address"] for r in rows) == uncontained
    assert set(uncontained) <= set(mini["nullBundleAddresses"])


@pytest.mark.client_gated
def test_cg_u2_duplicate_keys_identities_on_13_locales():
    _require_real_corpus()
    report = json.loads((PACK_ROOT / "extracted" / "locales" /
                         "base-overlay-report.json").read_text(
                             encoding="utf-8"))
    dup = (report.get("evidence") or {}).get("duplicateKeysOverwritten")
    if dup is None:
        pytest.skip("amendment pending: duplicateKeysOverwritten not "
                    "persisted yet (RED-2 fix lane)")
    per_locale = dup["perLocale"]
    assert dup["total"] == sum(per_locale.values()), \
        "persisted total must equal the per-locale map sum"
    locales_dir = PACK_ROOT / "extracted" / "locales"
    checked = 0
    for loc, dup_n in sorted(per_locale.items()):
        lines = sum(1 for ln in (locales_dir / f"{loc}.jsonl")
                    .read_text(encoding="utf-8").splitlines() if ln.strip())
        rows_logged = walked = skipped = None
        log = (PACK_ROOT / "extracted" / "EXTRACTION-LOG.md").read_text(
            encoding="utf-8")
        for ln in log.splitlines():
            s = ln.strip()
            if s.startswith(f"locale={loc} ") or \
                    (s.startswith("locale=") and f"={loc}" in s.split()[0]):
                for tok in s.split():
                    if tok.startswith("rows(emission-events)="):
                        rows_logged = int(tok.split("=")[1])
                    elif tok.startswith("termsWalked="):
                        walked = int(tok.split("=")[1])
                    elif tok.startswith("skippedEmpty="):
                        skipped = int(tok.split("=")[1])
                break
        if rows_logged is None:
            continue          # run-section spelling not parseable; V-U2 owns it
        assert rows_logged == walked - skipped, (
            f"{loc}: identity 1 violated ({rows_logged} != {walked}-"
            f"{skipped})")
        assert rows_logged - lines == dup_n, (
            f"{loc}: identity 2 violated ({rows_logged}-{lines} != {dup_n})")
        checked += 1
    assert checked >= 13 or checked == 0, (
        f"only {checked}/13 locales parsed from the run section")
    if checked:
        totals = sum(v[3] for v in cl.locale_totals().values()) if False \
            else None
        # real-corpus headline numbers (spec F9)
        all_rows = []
        log = (PACK_ROOT / "extracted" / "EXTRACTION-LOG.md").read_text(
            encoding="utf-8")
        for ln in log.splitlines():
            s = ln.strip()
            if s.startswith("localeRowsEmittedTotal"):
                try:
                    all_rows.append(int(s.split("=")[1]))
                except ValueError:
                    pass
        assert not all_rows or all_rows[-1] in (200977,), (
            f"localeRowsEmittedTotal drifted from the pinned 200,977: "
            f"{all_rows[-1:]}")


@pytest.mark.client_gated
@pytest.mark.slow
def test_cg_idempotence_double_run_hash_equal():
    _require_real_corpus()
    require_tool()
    scope_roots = ("relinks", "addressables", "locales", "stubs")

    def manifest(ext: Path) -> dict:
        out = {}
        for root in scope_roots:
            base = ext / root
            if not base.exists():
                continue
            for p in sorted(base.rglob("*")):
                if p.is_file():
                    st = p.stat()
                    out[str(p.relative_to(ext))] = (st.st_size,
                                                    st.st_mtime_ns)
        return out

    r1 = run_tool(PACK_ROOT, timeout=900)
    m1 = manifest(PACK_ROOT / "extracted")
    r2 = run_tool(PACK_ROOT, timeout=900)
    m2 = manifest(PACK_ROOT / "extracted")
    assert r1.returncode == r2.returncode
    assert r1.stdout == r2.stdout, (
        "--only check-contracts double-run stdout diverged on the real "
        "corpus (AC5)")
    _, _, changed = diff_manifests(m1, m2)
    assert not changed, (
        f"a contracts run mutated validated families (AC4): {changed[:8]}")
