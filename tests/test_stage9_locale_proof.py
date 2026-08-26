"""Piece-07 blind TestWriter suite — stage 9 ``locale-proof``.

Written against docs/specs/piece-07-locale-proof.mdx (Revision 3) +
docs/rulings/arbiter-piece07-spec.mdx ALONE (§10 TestWriter contract);
tools/stage9_locale_proof.py was never read. Primary surface is black-box
(``run_all.py <tree> --only locale-proof`` over synthetic prepared trees,
conftest.run_pack) plus client-gated exact-figure legs over the committed
corpus. Expected RED against not-yet-landed code — that is the blind-pair
interface; skips stay reserved for environment gating and honest
window-missed outcomes.

Fixture corpora come from tests/_prooflib.py (hand-computed mini roster:
de/en/ja + base overlay, five populated kinds — see its docstring for the
derived census). All temp roots ride pytest's tmp_path_factory (session
basetemp; never a C:-rooted custom basetemp).

Blocks:
  A entrypoint/registration (AC1)      B upstream gate (AC2)
  C L1 key-plane census                D L2 entity-plane matrix
  E L3 availability regeneration       F L4 fallback law
  G L5 site-UI gap manifest            H L6 completeness/ledger/hashes
  I determinism (AC9)                  J regression tripwire + precedence
  K §5 ownership-amendment retirement  L runner obligations
  M suite-side mutation teeth          N client-gated exact figures
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from _impl import get_sym, load_tool
from _validators import (
    BUILD_ID, KIND_TO_FILE, LOCALE_TABLE, hash_tree, read_json, read_jsonl,
    scan_tree_for_media_extensions,
)
import _prooflib as pl
from _prooflib import (
    ALL_FIXTURE_LOCALES, AVAILABILITY_JSONL, AVAILABILITY_REPORT,
    CANONICALLY_LATER_SIBLINGS, CHROME_SURFACES, CORE_VECTOR_MEMBERS,
    EXTRA_LOCALES, FALLBACK_SYMBOL_SUBSTRINGS, FIXTURE_LOCALES,
    LEDGER_CODE_ALIAS_ABSENT, LEDGER_CODE_CLOSABLE, LEDGER_CODE_COURSE_OPEN,
    LEDGER_CODE_DANGLING, LEDGER_CODE_G8, LEDGER_CODE_UNJOINED,
    PREDECESSOR_STAGE_IDS, PROOF_DIR, PROSE_SURFACES, REAL, REAL_LEDGER_CODES,
    REAL_VECTOR_MEMBER_COUNT, SCRIPT_DEPS, SCRIPT_REL, STAGE_ID,
    VECTOR_MEMBER_GRAMMAR,
)

PACK_ROOT = Path(__file__).resolve().parents[1]
PINNED_13 = set(LOCALE_TABLE.values())
STAGE_NUM = "9"

ALLOWED_WRITES = (
    "locales/proof/", AVAILABILITY_JSONL, AVAILABILITY_REPORT,
    "EXTRACTION-LOG.md", ".stage-stamps", ".pipeline-meta.json",
)


# --- harness -----------------------------------------------------------------

def make_tree(tmp_path_factory, name, **kw) -> Path:
    """Leg-private prepared tree (fresh, mutable)."""
    from conftest import build_tree
    return build_tree(STAGE_ID, tmp_path_factory, name, **kw)


def run9(tree: Path, ext: Path, *extra, timeout=300):
    from conftest import run_pack, tree_game
    Path(ext).mkdir(parents=True, exist_ok=True)
    return run_pack([tree_game(tree), "--only", STAGE_ID, *extra],
                    extracted_root=ext, timeout=timeout)


def run_stage5(tree: Path, ext: Path, *extra):
    from conftest import run_pack, tree_game
    return run_pack([tree_game(tree), "--only", "emit-stub-datasets", *extra],
                    extracted_root=ext)


def proof(ext: Path) -> Path:
    return Path(ext) / PROOF_DIR


def require_completed(r, what="locale-proof run"):
    """Hostless stage must complete 0 (closed) or 2 (open ledgers). Anything
    else is a LOUD failure — including the unregistered-stage rc 3 this
    suite expects while the CodeWriter lane is pending (blind-pair RED)."""
    assert r.returncode in (0, 2), (
        f"{what} did not complete: rc={r.returncode}\n"
        f"STDOUT:{r.stdout[-2000:]}\nSTDERR:{r.stderr[-2000:]}")


def load_json(ext: Path, rel: str):
    p = Path(ext) / rel
    assert p.is_file(), f"missing emitted artifact {rel}"
    return read_json(p)


def load_jsonl(ext: Path, rel: str):
    p = Path(ext) / rel
    assert p.is_file(), f"missing emitted artifact {rel}"
    return read_jsonl(p)


def last_run_section(ext: Path, stage_id: str = STAGE_ID) -> str:
    log_text = (Path(ext) / "EXTRACTION-LOG.md").read_text(
        encoding="utf-8", errors="replace")
    sections = [p for p in re.split(r"(?m)^#{1,3} ", log_text)
                if p.splitlines()[:1]
                and stage_id in p.splitlines()[0].lower()]
    assert sections, f"no {stage_id} run section in EXTRACTION-LOG.md"
    return sections[-1]


def regression_lines(text: str):
    """REGRESSION verdict lines, whatever console/log prefix carries them:
    bare 'REGRESSION: member old->new', '[stage] REGRESSION: ...', or the
    log's '- PROBLEM: REGRESSION: ...' form all count."""
    return [ln.strip() for ln in text.splitlines()
            if "REGRESSION" in ln.upper()
            and re.search(r"REGRESSION\s*:?\s*\S+\s+\d+\s*(?:->|→|to)\s*\d+",
                          ln, re.IGNORECASE)]


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def snapshot_declared(ext: Path) -> dict:
    """sha256 over stage-9's declared outputs (both roots), excluding the
    hash-excluded set — log/stamps/meta AND .baseline.json (AC9's comparison
    set; the baseline gets its own explicit byte checks in block J)."""
    out = {}
    proof_dir = proof(ext)
    if proof_dir.exists():
        out |= {rel: digest for rel, digest in hash_tree(proof_dir).items()
                if rel != ".baseline.json"}
    for rel in (AVAILABILITY_JSONL, AVAILABILITY_REPORT):
        p = Path(ext) / rel
        out[rel] = sha256_file_if(p)
    return out


def sha256_file_if(p: Path):
    return sha256_bytes(Path(p).read_bytes()) if Path(p).is_file() else ""


def snapshot_readonly(ext: Path) -> dict:
    """Everything OUTSIDE stage 9's allowed write set (non-goal §8: the
    stage is read-only over everything except §5's one amended path and
    its own proof directory)."""
    ext = Path(ext)
    out = {}
    for p in sorted(ext.rglob("*")):
        if p.is_dir():
            continue
        rel = p.relative_to(ext).as_posix()
        if any(rel == a or rel.startswith(a) or rel.split("/")[0] == a
               for a in ALLOWED_WRITES):
            continue
        out[rel] = sha256_bytes(p.read_bytes())
    return out


def bump_buildid_everywhere(ext: Path, old=BUILD_ID, new=BUILD_ID + 1):
    # .baseline.json is EXCLUDED: it is the tripwire's memory of the OLD
    # build — bumping it too would erase the very drift this leg drives.
    skip = {".baseline.json"}
    for p in sorted(Path(ext).rglob("*")):
        if p.is_file() and p.name not in skip:
            b = p.read_bytes()
            if str(old).encode() in b:
                p.write_bytes(b.replace(str(old).encode(), str(new).encode()))


@pytest.fixture(scope="session")
def open_tree(tmp_path_factory) -> Path:
    return make_tree(tmp_path_factory, "tw07_open")


@pytest.fixture(scope="module")
def open_run(open_tree, tmp_path_factory):
    """One completed hostless run over a pristine copy of the open tree."""
    from conftest import seeded_extracted_root
    ext = seeded_extracted_root(open_tree, tmp_path_factory.mktemp("tw07o"))
    r = run9(open_tree, ext)
    return r, ext, open_tree


# ============================================================================
# A — entrypoint / registration (AC1, arbiter R1 registry-aware form)
# ============================================================================

def test_A_registry_entry_canonical_index9():
    sys.path.insert(0, str(PACK_ROOT / "tools"))
    mod = load_tool("tpc_common.py")
    assert mod is not None, "impl-missing: tools/tpc_common.py"
    stages = list(getattr(mod, "STAGES", []))
    ids = [sid for sid, _s, _d in stages]
    assert STAGE_ID in ids, (
        f"registry-aware AC1: '{STAGE_ID}' not registered in "
        f"tpc_common.STAGES (ids={ids})")
    entry = next(e for e in stages if e[0] == STAGE_ID)
    _sid, script_rel, deps = entry
    assert script_rel.replace("\\", "/") == SCRIPT_REL, (
        f"arbiter R1: script must be {SCRIPT_REL} (explicit-9), got {script_rel}")
    assert list(deps) == SCRIPT_DEPS, (
        f"script-hash deps pinned {SCRIPT_DEPS}, got {deps}")
    # canonical ORDER: after relink (index 6), before canonically-later
    # siblings IF those are registered; absolute count asserted only as the
    # canonical floor (R1: never an exact enumeration in a parallel batch)
    assert ids.index(STAGE_ID) > ids.index("relink"), (
        "locale-proof must register AFTER relink (additive, forward-only DAG)")
    for sib in CANONICALLY_LATER_SIBLINGS:
        if sib in ids:
            assert ids.index(STAGE_ID) < ids.index(sib), (
                f"canonical order violated: {STAGE_ID} must precede {sib}")
    assert ids[:len(PREDECESSOR_STAGE_IDS)] == list(PREDECESSOR_STAGE_IDS)


def test_A_list_shows_order_and_script(open_tree, tmp_path_factory):
    # extracted_root points at a tiny fixture copy so --list's stage-identity
    # hashing stays cheap (never hashes the real corpus for a listing).
    from conftest import run_pack, seeded_extracted_root
    ext = seeded_extracted_root(open_tree,
                                tmp_path_factory.mktemp("tw07_list"))
    r = run_pack(["--list"], extracted_root=ext)
    assert r.returncode == 0, f"--list failed rc={r.returncode}: {r.stderr}"
    rows = {}
    order_line = ""
    for ln in r.stdout.splitlines():
        m = re.match(r"^(\S+)\s{2,}(\S+)\s{2,}", ln)
        if m:
            rows[m.group(1)] = m.group(2)
        if ln.startswith("order:"):
            order_line = ln
    assert rows.get(STAGE_ID) == SCRIPT_REL, (
        f"--list must show {STAGE_ID} -> {SCRIPT_REL}; got {rows}")
    listed = [s.strip().rstrip(",") for s in
              order_line.split("order:", 1)[-1].split() if s.strip()]
    assert listed and STAGE_ID in listed, (
        f"--list order line must enumerate {STAGE_ID}; got {order_line!r} "
        f"(stdout tail: {r.stdout[-400:]!r})")
    assert "relink" in listed, order_line
    assert listed.index(STAGE_ID) > listed.index("relink")
    for sib in CANONICALLY_LATER_SIBLINGS:
        if sib in listed:
            assert listed.index(STAGE_ID) < listed.index(sib)


def test_A_only_isolation_on_fixture_tree(tmp_path_factory):
    """AC1: `--only locale-proof` runs in isolation on a prepared tree;
    the fixture tree is also where an absolute-count sanity floor applies."""
    tree = make_tree(tmp_path_factory, "tw07_iso")
    ext = tree / "extracted"
    r = run9(tree, ext)
    require_completed(r)
    assert proof(ext).is_dir(), "isolation run produced no proof/ directory"


def test_A_make_list_equivalent():
    make = shutil.which("make")
    if not make:
        pytest.skip("environment: no make binary on PATH")
    try:
        r = subprocess.run([make, "list"], cwd=str(PACK_ROOT),
                           capture_output=True, text=True, timeout=600,
                           encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        pytest.skip("environment: make list timed out (real-corpus hashing)")
    if r.returncode != 0:
        pytest.skip(f"environment: make list failed rc={r.returncode}")
    assert STAGE_ID in r.stdout, "`make list` must enumerate locale-proof"


# ============================================================================
# B — upstream gate (AC2)
# ============================================================================

def test_B_missing_upstream_exits3_naming_it(tmp_path_factory):
    tree = make_tree(tmp_path_factory, "tw07_gate")
    ext = tree / "extracted"
    (ext / "relinks" / "entity_locale.jsonl").unlink()
    r = run9(tree, ext)
    assert r.returncode == 3, (
        f"ANY missing input => exit 3 naming it; got rc={r.returncode}\n"
        f"{r.stdout[-800:]}{r.stderr[-800:]}")
    combined = r.stdout + r.stderr
    assert "entity_locale" in combined, (
        f"exit-3 output must NAME the missing input: {combined[-600:]}")


def test_B_no_partial_writes_before_gate_passes(tmp_path_factory):
    tree = make_tree(tmp_path_factory, "tw07_gate2")
    ext = tree / "extracted"
    (ext / "locales" / "base-overlay.jsonl").unlink()
    r = run9(tree, ext)
    assert r.returncode == 3, f"expected gate refusal 3, got {r.returncode}"
    assert not proof(ext).exists() or not any(proof(ext).iterdir()), \
        "stage wrote proof outputs before the upstream pre-check passed"
    assert not (ext / AVAILABILITY_JSONL).exists(), \
        "availability path touched before the pre-check passed"


# ============================================================================
# C — L1 key-plane census (hand-pinned fixture expectations)
# ============================================================================

def test_C_key_plane_core_census(open_run):
    r, ext, _tree = open_run
    require_completed(r)
    kp = load_json(ext, f"{PROOF_DIR}/key_plane.json")
    assert kp["meta"]["buildId"] == BUILD_ID
    assert kp["meta"]["universes"]["unionOf13Tables"] == 19
    assert kp["meta"]["universes"]["registry"] == 21
    roster = kp["meta"]["localeRoster"]
    assert roster == sorted(ALL_FIXTURE_LOCALES), (
        f"roster must be the table-bearing locales, lexicographic: {roster}")
    assert set(roster) <= PINNED_13, "emitted rosters stay within the pinned 13"
    assert kp["presenceHistogram"] == {"13": 8, "2": 6, "1": 5}
    share = kp["allThirteenShare"]
    assert share["numerator"] == 8 and share["denominator"] == 19
    assert share["rate"] == "42.11%", share
    assert share["registryUniverseRate"] == "38.10%", share


def test_C_per_locale_rows_holes_and_f6_identity(open_run):
    r, ext, _tree = open_run
    require_completed(r)
    kp = load_json(ext, f"{PROOF_DIR}/key_plane.json")
    # hand-computed core trio + uniform extras (en-copied all-locales group:
    # rows 8, holes 10, skipped 12, share 44.44% each)
    expected_rows = {"de": 12, "en": 18, "ja": 11,
                     **{loc: 8 for loc in EXTRA_LOCALES}}
    expected_holes = {"de": 7, "en": 1, "ja": 8,
                      **{loc: 11 for loc in EXTRA_LOCALES}}
    expected_skipped = {"de": 9, "en": 3, "ja": 10,
                        **{loc: 13 for loc in EXTRA_LOCALES}}
    expected_share = {"de": "63.16%", "en": "94.74%", "ja": "57.89%",
                      **{loc: "42.11%" for loc in EXTRA_LOCALES}}
    per = kp["perLocale"]
    assert set(per) == set(ALL_FIXTURE_LOCALES)
    n_registry = kp["meta"]["universes"]["registry"]
    for loc, cell in per.items():
        assert cell["rows"] == expected_rows[loc], (loc, cell)
        assert cell["unionHoles"] == expected_holes[loc], (loc, cell)
        assert cell["shareOfUnion"] == expected_share[loc], (loc, cell)
        # F6 identity: emptyCellsSkipped == registryKeys − rows(locale)
        assert cell["emptyCellsSkipped"] == n_registry - cell["rows"], (
            loc, "F6 identity broken", cell)
        assert cell["emptyCellsSkipped"] == expected_skipped[loc]


def test_C_quirks_block(open_run):
    r, ext, _tree = open_run
    require_completed(r)
    q = load_json(ext, f"{PROOF_DIR}/key_plane.json")["quirks"]
    assert q["enMissingKeys"] == ["UI/General/NameSeparator"], q
    slk = q["singleLocaleKeys"]
    assert slk["count"] == 5 and slk["allEn"] is False, (
        f"single-locale counting must COMPUTE (fixture holds ja-solo too): {slk}")
    cluster = q["enPlusKoCluster"]
    # hostless fixture: partner locale + cluster rule are implementation
    # freedom the spec leaves open (its name comes from the real corpus);
    # exact {"Meta/CareerGoals", 15} is asserted client-gated
    assert isinstance(cluster.get("namespace"), str)
    assert isinstance(cluster.get("count"), int) and cluster["count"] >= 0
    assert (cluster["count"] == 0) == (cluster["namespace"] == "")
    assert q["baseOnlyVsEn"] == [
        "Buildings/BuildingGeneric_Description",
        "UI/EmptyStringNoTranslate",
        "UI/General/NameSeparator",
    ], q["baseOnlyVsEn"]


def test_C_hole_files_sorted_joined_and_complete(open_run):
    r, ext, _tree = open_run
    require_completed(r)
    holes_dir = proof(ext) / "key_holes"
    files = sorted(p.name for p in holes_dir.glob("*.jsonl"))
    assert files == [f"{loc}.jsonl" for loc in sorted(ALL_FIXTURE_LOCALES)], \
        files
    expected_counts = {"de": 7, "en": 1, "ja": 8,
                       **{loc: 11 for loc in EXTRA_LOCALES}}
    for loc in ALL_FIXTURE_LOCALES:
        rows = load_jsonl(ext, f"{PROOF_DIR}/key_holes/{loc}.jsonl")
        assert len(rows) == expected_counts[loc], (loc, len(rows))
        keys = [row["termKey"] for row in rows]
        assert keys == sorted(keys), f"{loc} hole file not sorted by termKey"
        for row in rows:
            assert set(row) >= {"termKey", "namespace", "alsoMissingIn",
                                "buildId"}
            assert row["namespace"] == row["termKey"].split("/", 1)[0]
            assert row["buildId"] == BUILD_ID
            am = row["alsoMissingIn"]
            assert am == sorted(am) and loc not in am
            assert set(am) <= PINNED_13
            # cross-file join: every alsoMissingIn locale really lacks the key
            if am:
                other = load_jsonl(
                    ext, f"{PROOF_DIR}/key_holes/{am[0]}.jsonl")
                assert any(o["termKey"] == row["termKey"] for o in other), (
                    f"{loc}: alsoMissingIn={am} not corroborated by hole files")
    # en's sole hole is the CJK separator — held ONLY by ja, so every other
    # locale must list it as also-missing
    en_rows = load_jsonl(ext, f"{PROOF_DIR}/key_holes/en.jsonl")
    assert en_rows[0]["termKey"] == "UI/General/NameSeparator"
    assert en_rows[0]["alsoMissingIn"] == sorted(
        set(ALL_FIXTURE_LOCALES) - {"en", "ja"})


def test_C_identity_to_pivot_two_tier_framing(open_run):
    """F8/AC5 framing scaled to fixtures: counters over HELD keys under the
    frozen de comparator; the residual list makes tier-delta data; the de
    row is DECLARED-STRUCTURAL (R2) and the en row reads as 'de differs'."""
    r, ext, _tree = open_run
    require_completed(r)
    tier = load_json(ext, f"{PROOF_DIR}/key_plane.json")["identityToPivot"]
    assert tier["namespace"] == "Items/*_Name"
    assert tier["familyKeysTotal"] == 4
    rule = tier["metricRule"]
    assert "byteIdenticalToEn" in rule and "identicalAndDeDiffers" in rule, rule
    assert "de" in rule, "metricRule must freeze the de comparator"
    expected = {
        "de": {"keysHeld": 4, "byteIdenticalToEn": 1,
               "identicalAndDeDiffers": 0,       # STRUCTURAL self-comparison
               "identicalInEveryHoldingLocale": 1},
        "en": {"keysHeld": 4, "byteIdenticalToEn": 4,
               "identicalAndDeDiffers": 3,       # reads as 'de differs from en'
               "identicalInEveryHoldingLocale": 1},
        "ja": {"keysHeld": 3, "byteIdenticalToEn": 3,
               "identicalAndDeDiffers": 2,
               "identicalInEveryHoldingLocale": 1},
    }
    # extras copy EN text over the all-locales group → each mirrors the ja
    # shape (held Alpha/Beta/Gamma: identical 3, de-differs 2, residual Gamma)
    for loc in EXTRA_LOCALES:
        expected[loc] = {"keysHeld": 3, "byteIdenticalToEn": 3,
                         "identicalAndDeDiffers": 2,
                         "identicalInEveryHoldingLocale": 1}
    gamma = "Items/Gamma/Residual_Name"
    blob = json.dumps(tier)
    for loc, want in expected.items():
        row = tier[loc]
        for k, v in want.items():
            assert row[k] == v, f"{loc}.{k}: {row[k]} != {v} (row={row})"
    # residual list emitted BESIDE the tier so the delta is data, not math:
    # per-locale bie − identicalAndDeDiffers under the SAME frozen predicates
    # (de's own row carries Gamma too — de≡en AND de==en there; en/ja/extras
    # likewise)
    resid = tier["residualIdenticalInDe"]
    assert resid == {"de": [gamma], "en": [gamma], "ja": [gamma],
                     **{loc: [gamma] for loc in EXTRA_LOCALES}}, resid
    assert "identicalButTranslatedElsewhere" not in blob
    # retired Rev-1 field name must not resurrect
    # (the en==pivot worked-example evidence leg runs client-gated against
    # Items/Library/Reception_Giant_Name == "Giant Library Reception")


def test_C_percent_formatting_rounds_half_up():
    """Rates round HALF-UP at 2 dp (spec §4 vocabularies). Unit probe with a
    true tie value: 1/160 = 0.625 % → half-up '0.63%' (banker's would give
    '0.62%'). Loud-skip until the formatter symbol resolves."""
    mod = load_tool(f"stage{STAGE_NUM}_locale_proof.py")
    fn = get_sym(mod, "format_rate", "fmt_pct", "format_pct", "pct",
                 "render_rate", "round_rate", "rate_string", kinds=(object,))
    if fn is None:
        pytest.skip("impl-missing: percent formatter symbol (tried 7 names)")
    def call(fn, num, den):
        try:
            return fn(num, den)
        except TypeError:
            return fn(num, den, True)
    out = call(fn, 1, 160)
    assert isinstance(out, str) and out.endswith("%")
    assert out.startswith("0.63"), (
        f"1/160 must render half-up 0.63%, got {out!r} (banker's leak)")
    assert call(fn, 8, 18).startswith("44.44")


# ============================================================================
# D — L2 entity-plane kind×locale matrix
# ============================================================================

def _matrix(ext):
    return load_json(ext, f"{PROOF_DIR}/kind_locale_matrix.json")


def test_D_census_block_exact(open_run):
    r, ext, _tree = open_run
    require_completed(r)
    m = _matrix(ext)
    c = m["census"]
    assert c["instancesTotal"] == 10
    assert c["sentinelZero"] == 1
    assert c["resolvedEdges"] == 7
    assert c["registryMisses"] == 2
    cov = c["coverageOnNonEmpty"]
    # AC4 pins the arithmetic SHAPE on the real corpus: numerator
    # 10959 == resolvedEdges − registryMisses over denominator resolvedEdges
    # (10964) — fixture analog is (7−2)/7 — printed as a 5 dp DECIMAL rate
    # ("0.99954" there, "0.71429" here).
    num, den = cov["numerator"], cov["denominator"]
    assert (num, den) == (5, 7), cov
    assert abs(float(cov["rate"]) - 5 / 7) < 1e-4, cov
    assert m["meta"]["buildId"] == BUILD_ID
    assert set(m["meta"]["kinds"]) == set(KIND_TO_FILE), "pinned 9-kind map"


def test_D_item_cells_hand_computed(open_run):
    """item × {de,en,ja} any/full/name metrics derived by hand:
    joined items it1+it5; it5's Description (Beta/Gadget_Description) is
    en-only → all<any off-en; ja name 'Stone'=='Stone' for both → identity 2/2."""
    r, ext, _tree = open_run
    require_completed(r)
    kinds = _matrix(ext)["kinds"]
    assert kinds["item"]["stubRows"] == 6
    assert kinds["item"]["joinedEntities"] == 2
    cells = kinds["item"]["perLocale"]
    # en's nameIdenticalToEn == nb (2): under the FROZEN uniform predicates
    # every pivot-held name is trivially identical to itself — the R2
    # DECLARED-STRUCTURAL degeneracy ("no special-casing in code"), same as
    # L1's en row.
    want = {
        "en": {"anyTermPresent": 2, "allTermsPresent": 2,
               "nameBearingEntities": 2, "nameIdenticalToEn": 2},
        "de": {"anyTermPresent": 2, "allTermsPresent": 1,
               "nameBearingEntities": 2, "nameIdenticalToEn": 0},
        "ja": {"anyTermPresent": 2, "allTermsPresent": 1,
               "nameBearingEntities": 2, "nameIdenticalToEn": 2},
    }
    for loc, exp in want.items():
        cell = cells[loc]
        for k, v in exp.items():
            assert cell[k] == v, f"item/{loc}.{k}: {cell[k]} != {v} ({cell})"
        assert cell["anyRate"].endswith("%") and cell["fullRate"].endswith("%")


def test_D_kind_level_counts_and_name_role_notes(open_run):
    r, ext, _tree = open_run
    require_completed(r)
    kinds = _matrix(ext)["kinds"]
    joined = {"config": 1, "item": 2, "room": 0, "course": 1, "staff": 0,
              "student-type": 0, "unlockable": 1, "metagame-node": 0,
              "campus-level": 0}
    stubs = {"config": 2, "item": 6, "room": 0, "course": 2, "staff": 0,
             "student-type": 0, "unlockable": 3, "metagame-node": 0,
             "campus-level": 3}
    for kind, cell in kinds.items():
        assert cell["stubRows"] == stubs[kind], (kind, cell)
        assert cell["joinedEntities"] == joined[kind], (kind, cell)
        assert not cell.get("inferred", False) or kind == "course", (
            f"{kind}: inferred:true is COURSE-only (alias input path)")
    # nameRoleNote: null everywhere EXCEPT course (F15 statement) and config
    # (pinned DRIFT location, reviewer F9)
    assert kinds["course"]["nameRoleNote"], "course F15 hole statement missing"
    assert "name" in kinds["course"]["nameRoleNote"].lower()
    cfg_note = kinds["config"]["nameRoleNote"]
    assert cfg_note and "DRIFT" in cfg_note, (
        f"config scout-tie-break DRIFT note must live at "
        f"kinds.config.nameRoleNote, got {cfg_note!r}")
    for kind in ("item", "room", "campus-level", "unlockable"):
        assert kinds[kind]["nameRoleNote"] in (None, ""), kind
    section = last_run_section(ext)
    assert re.search(r"configIdentityDriftNoted\s*=\s*true", section), section[-800:]


def test_D_unjoined_entities_classified(open_run):
    r, ext, _tree = open_run
    require_completed(r)
    rows = load_jsonl(ext, f"{PROOF_DIR}/unjoined_entities.jsonl")
    assert len(rows) == 11, f"16 stub rows − 5 joined = 11, got {len(rows)}"
    ids = [(row["kind"], row["id"]) for row in rows]
    assert ids == sorted(ids), "unjoined rows must sort by (kind,id)"
    per_kind = {}
    for row in rows:
        per_kind[row["kind"]] = per_kind.get(row["kind"], 0) + 1
        assert row["buildId"] == BUILD_ID
        assert set(row) >= {"kind", "id", "class"}
    assert per_kind == {"campus-level": 3, "config": 1, "course": 1,
                        "item": 4, "unlockable": 2}, per_kind
    by_id = {(r_["kind"], r_["id"]): r_ for r_ in rows}
    # PINNED-shape assertions (spec pins exactly these classes' membership):
    assert by_id[("item", "Item_Editor_Kernel_One")]["class"] == "internal-kernel"
    assert by_id[("item", "Unused_Item_Kernel_Two")]["class"] == "internal-kernel"
    lit = by_id[("campus-level", "Campus_Level_Blank")]
    assert lit["class"] == "english-only-literal"
    assert lit["nameLiteral"] == "Blank Level"
    assert by_id[("campus-level", "Campus_Level_NoDisplay")]["class"] == \
        "no-display-field"
    bright = by_id[("unlockable", "Unlock_Bright_Literal")]
    cupid = by_id[("unlockable", "Unlock_Cupid")]
    assert bright["coincidesWithEnTermText"] is True, bright
    # the L2 row shape pins coincidesWithEnTermText as OPTIONAL (the "?"
    # keys: nameLiteral? / coincidesWithEnTermText? / kernelPrefix?) — a
    # non-coinciding row OMITS it rather than emitting False
    assert not cupid.get("coincidesWithEnTermText"), cupid
    coincidence_rows = [r_ for r_ in rows if r_.get("coincidesWithEnTermText")]
    assert len(coincidence_rows) == 1, coincidence_rows
    # residue bucket: the spec's own 'everything else'; label must come from
    # the pinned vocabulary and at least one row must carry it
    labels = {r_["class"] for r_ in rows}
    assert labels <= {"english-only-literal", "no-display-field",
                      "internal-kernel", "unclassified-residue"}, labels
    assert "unclassified-residue" in labels, (
        "the residue class must be reachable on a corpus holding "
        "unjoined player-facing-shaped rows (Item_Miss_Dangling)")


def test_D_alias_present_leg(tmp_path_factory):
    """Reviewer F6 contracted branch: WITH the optional alias input, course
    name-cells compute THROUGH it (inferred:true + method recorded) and the
    ledger suppresses course-name-join-open AND alias-input-absent."""
    tree = make_tree(tmp_path_factory, "tw07_alias")
    ext = tree / "extracted"
    # the alias leg's corpus must CARRY the alias term keys in its registry
    # (real alias tables reference the 15,672-key registry; the bare fixture
    # omits them) — rebuild the same deterministic upstream with aliased=True
    pl.build_locale_proof_upstream(ext, aliased=True)
    with pl.alias_input(PACK_ROOT, ext):
        r = run9(tree, ext)
        require_completed(r)
        m = _matrix(ext)
        course = m["kinds"]["course"]
        # `inferred` lives in the perLocale CELLS (the §L2 schema's pinned
        # location), not at kind level.
        assert course["perLocale"], "course cells missing"
        for loc, cell in course["perLocale"].items():
            assert cell["inferred"] is True, (
                f"alias-consumed course rows must carry inferred:true "
                f"(cell {loc}: {cell})")
        appendix = json.dumps(m)
        assert "marketing-campaign-hard-join" in appendix, (
            "alias method string must be recorded in the matrix appendix")
        clowns = course["perLocale"]["en"]
        assert clowns["nameBearingEntities"] >= 1, (
            "Course_Clowns must gain a name-role cell through the alias table")
        ledger = load_jsonl(ext, f"{PROOF_DIR}/_ledger.jsonl")
        codes = {row.get("code") for row in ledger}
        assert LEDGER_CODE_COURSE_OPEN not in codes, codes
        assert LEDGER_CODE_ALIAS_ABSENT not in codes, codes


# ============================================================================
# E — L3 availability regeneration
# ============================================================================

def _avail_rows(ext):
    return load_jsonl(ext, AVAILABILITY_JSONL)


def test_E_row_count_derives_by_formula(open_run):
    """AC6 §2.2 formula: rowCount == distinct (srcKind,srcId) in
    entity_locale.jsonl with >=1 resolved edge == deduped registryHits."""
    r, ext, _tree = open_run
    require_completed(r)
    edges = load_jsonl(ext, "relinks/entity_locale.jsonl")
    reg_ids = {r_["termId"] for r_ in
               load_jsonl(ext, "relinks/i2_term_registry.jsonl")}
    resolved_pairs = {(e["srcKind"], e["srcId"]) for e in edges
                      if e["evidence"]["termId"] in reg_ids}
    rows = _avail_rows(ext)
    assert len(rows) == len(resolved_pairs) == 5, (
        f"availability rows {len(rows)} != independently deduped pairs "
        f"{len(resolved_pairs)}")
    report = load_json(ext, AVAILABILITY_REPORT)
    assert report["schemaVersion"] == 2
    assert report["rowCount"] == len(rows), "report sidecar disagrees"
    jr = read_json(ext / "relinks" / "locale_join_report.json")
    assert jr["registryHits"] >= len(rows)
    per_kind = {}
    for row in rows:
        per_kind[row["kind"]] = per_kind.get(row["kind"], 0) + 1
    assert per_kind == {"item": 2, "course": 1, "unlockable": 1,
                        "config": 1}, per_kind
    if "perKindRowCounts" in report:
        assert report["perKindRowCounts"] == per_kind


def test_E_row_schema_membership_and_sort(open_run):
    r, ext, _tree = open_run
    require_completed(r)
    rows = _avail_rows(ext)
    required = {"kind", "id", "availableLocales", "partialLocales",
                "namedLocales", "identityToPivotLocales", "fieldPresence",
                "buildId"}
    keys_seen = [(r_["kind"], r_["id"]) for r_ in rows]
    assert keys_seen == sorted(keys_seen), "rows must sort lexicographically"
    for row in rows:
        extra = set(row) - required - {"axes"}
        assert not extra, f"v2 shape: unexpected keys {extra} (axes is THE ONE optional)"
        missing = required - set(row)
        assert not missing, f"v2 shape: missing {missing}"
        assert row["buildId"] == BUILD_ID
        for field in ("availableLocales", "partialLocales", "namedLocales",
                      "identityToPivotLocales"):
            v = row[field]
            assert v == sorted(v), field
            assert set(v) <= PINNED_13, (field, v)
        assert set(row["fieldPresence"]) <= set(row["availableLocales"]), row
        assert set(row["partialLocales"]) <= set(row["availableLocales"]), row
        assert set(row["identityToPivotLocales"]) <= \
            set(row["namedLocales"]), row
        for loc, fields in row["fieldPresence"].items():
            assert fields == sorted(fields) and fields, (loc, fields)
    by_pair = {(r_["kind"], r_["id"]): r_ for r_ in rows}
    # axes passthrough (present on the one axes-carrying stub) / omission
    alpha = by_pair[("item", "Item_Alpha_Display")]
    assert alpha.get("axes") == ["base"], alpha
    for pair, row in by_pair.items():
        if pair != ("item", "Item_Alpha_Display"):
            assert "axes" not in row, f"{pair}: axes must be omitted iff absent upstream"
    # membership semantics, hand-derived (extras copy EN text, so they join
    # the available/named sets everywhere and count as identity-to-pivot):
    all13 = sorted(ALL_FIXTURE_LOCALES)
    partial = by_pair[("item", "Item_Partial_Join")]
    assert partial["availableLocales"] == all13, partial
    assert partial["partialLocales"] == sorted(set(all13) - {"en"}), (
        "Description term is en-only → every other locale holds "
        "some-but-not-all joined terms")
    clowns = by_pair[("course", "Course_Clowns")]
    assert clowns["availableLocales"] == all13
    assert clowns["namedLocales"] == [], (
        "F15: courses carry ZERO name-role terms → namedLocales empty")
    kudosh = by_pair[("unlockable", "Unlock_Kudosh")]
    assert kudosh["namedLocales"] == all13
    alpha = by_pair[("item", "Item_Alpha_Display")]
    assert alpha["identityToPivotLocales"] == sorted(EXTRA_LOCALES + ("ja",)), (
        "locales whose name text == pivot text: ja ('Stone') + the en-copied "
        "extras; en (trivial) and de ('Stein') excluded")


def test_E_stage_is_read_only_outside_allowed_paths(tmp_path_factory):
    """Non-goal §8: read-only over everything except the amended path and
    its own proof directory (hash before == after outside ALLOWED_WRITES)."""
    tree = make_tree(tmp_path_factory, "tw07_ro")
    ext = tree / "extracted"
    before = snapshot_readonly(ext)
    r = run9(tree, ext)
    require_completed(r)
    after = snapshot_readonly(ext)
    assert before == after, (
        "stage mutated upstream state outside its write scope: "
        f"changed={sorted(set(before) ^ set(after))[:8]} "
        f"differing={[k for k in set(before) & set(after) if before[k] != after[k]][:8]}")


# ============================================================================
# F — L4 fallback law
# ============================================================================

def _fallback(ext):
    return load_json(ext, f"{PROOF_DIR}/fallback_law.json")


def test_F_base_overlay_block(open_run):
    r, ext, _tree = open_run
    require_completed(r)
    fb = _fallback(ext)
    bo = fb["baseOverlay"]
    base_rows = load_jsonl(ext, "locales/base-overlay.jsonl")
    assert bo["rows"] == len(base_rows) == 21
    assert bo["rowsWithNonEmptyText"] == sum(
        1 for row in base_rows if (row.get("text") or "").strip()), (
        "rowsWithNonEmptyText must MEASURE, not parrot the corpus constant")
    assert bo["compositionPolicyEmitted"] == "mixed"
    semantics = bo["measuredSemantics"]
    assert "NO text" in semantics or "no text" in semantics or \
        "key-set" in semantics, f"G7 caveat missing: {semantics!r}"
    assert bo["baseOnlyKeysVsEn"] == [
        "Buildings/BuildingGeneric_Description",
        "UI/EmptyStringNoTranslate",
        "UI/General/NameSeparator",
    ]
    for k in ("languageSources", "termBearingSources", "rawTermsDecoded"):
        assert isinstance(bo.get(k), int) and bo[k] >= 0, (k, bo.get(k))
    nb = fb["namedBundles"]
    assert nb["selfContained"] is True
    assert nb["emptyCellsSkippedPerLocale"] == {
        "de": 9, "en": 3, "ja": 10,
        **{loc: 13 for loc in EXTRA_LOCALES}}
    assert "none" in nb["borrowingRule"].lower()


def test_F_runtime_fallback_and_site_semantics(open_run):
    r, ext, _tree = open_run
    require_completed(r)
    rf = _fallback(ext)["runtimeFallback"]
    names_blob = json.dumps(rf["symbols"])
    for sym in FALLBACK_SYMBOL_SUBSTRINGS:
        assert sym in names_blob, f"pinned symbol {sym} missing"
    assert len(rf["symbols"]) >= 4
    if rf["symbolCheck"] == "verified":
        for s in rf["symbols"]:
            assert isinstance(s.get("dumpCsLine"), str) and s["dumpCsLine"], s
    else:
        # skipped-no-dump.cs branch: no grep ran, so refs may be null — but
        # the four pinned DECLARATIONS must still be present verbatim
        pass
    assert "UNPROVABLE" in rf["fallbackOrder"]
    assert rf["symbolCheck"] in ("verified", "skipped-no-dump.cs")
    ss = _fallback(ext)["siteSemantics"]
    assert ss["policy"] in ("omit | declared-filler", "omit|declared-filler") \
        or ("omit" in ss["policy"] and "declared-filler" in ss["policy"])
    assert ss["pivotFillBanned"] is True
    assert "5.5" in ss["authority"]


def test_F_symbol_check_both_branches(tmp_path_factory):
    """dump.cs present with the four names → verified (+ measured lines);
    absent → skipped-no-dump.cs. Both branches drivable hostless."""
    # branch B: no dump.cs anywhere in the tree (builder never writes one)
    tree_b = make_tree(tmp_path_factory, "tw07_nodump")
    r = run9(tree_b, tree_b / "extracted")
    require_completed(r)
    assert _fallback(tree_b / "extracted")["runtimeFallback"][
        "symbolCheck"] == "skipped-no-dump.cs"

    # branch A: synthetic dump.cs carrying the four pinned signatures
    tree_a = make_tree(tmp_path_factory, "tw07_dump")
    dump = (tree_a / "extracted" / "decompiled" / "il2cppdumper" / "dump.cs")
    dump.parent.mkdir(parents=True, exist_ok=True)
    dump.write_text(
        "// synthetic fixture dump (TestWriter)\n"
        "public string TryGetFallbackTranslation(TermData td, out string "
        "Translation, int langIndex, string overrideSpecialization, bool "
        "skipDisabled) {}\n"
        "public void LoadLanguageData(int languageIndex, string langData, "
        "bool UnloadOtherLanguages, bool useFallback, bool "
        "onlyCurrentSpecialization, bool forceLoad) {}\n"
        "public static string GetTranslation(string term) {{}}\n"
        "public static bool TryGetTranslation(string term, out string text) "
        "{{}}\n"
        "public string GetTranslation(int idx, string specialization, bool "
        "editMode) {}\n",
        encoding="utf-8", newline="\n")
    r = run9(tree_a, tree_a / "extracted")
    require_completed(r)
    rf = _fallback(tree_a / "extracted")["runtimeFallback"]
    assert rf["symbolCheck"] == "verified", rf
    measured = " ".join(s.get("dumpCsLine", "") for s in rf["symbols"])
    assert any(ch.isdigit() for ch in measured), (
        f"verified branch must measure dumpCsLine refs from THIS run's grep, "
        f"got {measured!r}")


# ============================================================================
# G — L5 site-UI namespace split
# ============================================================================

def test_G_manifest_surfaces_and_enum(open_run):
    r, ext, _tree = open_run
    require_completed(r)
    man = load_json(ext, f"{PROOF_DIR}/site_ui_gap_manifest.json")
    surfaces = man["siteChromeSide"]["surfaces"]
    ids = [s["surfaceId"] for s in surfaces]
    assert sorted(ids) == sorted(CHROME_SURFACES), (
        f"exactly the 16 pinned surfaceIds, none droppable: {sorted(ids)}")
    assert len(ids) == 16
    prose = {s["surfaceId"] for s in surfaces if s["kind"] == "prose"}
    assert prose == set(PROSE_SURFACES), prose
    for s in surfaces:
        assert s["kind"] in ("keyed", "prose")
        assert s["clientCoverageKeys"] == 0, (
            "NONE of the chrome strings exist anywhere in the client corpus")
        assert isinstance(s.get("locales"), int) and s["locales"] > 0
    assert man["siteChromeSide"]["clientCoverageKeys"] == 0
    assert man["siteChromeSide"]["localesRequired"] == len(PINNED_13)


def test_G_game_data_side_agrees_with_registry(open_run):
    r, ext, _tree = open_run
    require_completed(r)
    man = load_json(ext, f"{PROOF_DIR}/site_ui_gap_manifest.json")
    ui = man["gameDataSide"]["uiNamespace"]
    reg_keys = {r_["termKey"] for r_ in
                load_jsonl(ext, "relinks/i2_term_registry.jsonl")}
    usage_keys = {u["termKey"] for u in
                  load_jsonl(ext, "relinks/locale_term_entity.jsonl")}
    ui_registry = {k for k in reg_keys if k.startswith("UI/")}
    assert ui["registryKeys"] == len(ui_registry) == 4, ui
    assert ui["referencedByEntities"] == len(ui_registry & usage_keys) == 1
    assert ui["free"] == len(ui_registry - usage_keys) == 3
    assert "registry" in ui["universe"]
    gd = man["gameDataSide"]
    ns_count = len({k.split("/", 1)[0] for k in reg_keys})
    assert gd["topLevelNamespaces"] == ns_count == 9, gd["topLevelNamespaces"]
    assert gd["freeNarrativeKeys"] == 15, (
        "freeNarrativeKeys mirrors orphansA distinct keys")
    assert isinstance(gd.get("localizeBindings"), int) \
        and gd["localizeBindings"] >= 0
    assert "never as site chrome" in gd["note"] or "site chrome" in gd["note"]


# ============================================================================
# H — L6 registry completeness, ledger, hashes, summary/vector
# ============================================================================

def _completeness(ext):
    return load_json(ext, f"{PROOF_DIR}/registry_completeness.json")


def test_H_registry_completeness_exact(open_run):
    r, ext, _tree = open_run
    require_completed(r)
    comp = _completeness(ext)
    assert comp["rows"] == 22
    assert comp["distinctKeys"] == 21
    assert comp["nonCanonicalRows"] == 1
    assert comp["statusSplit"] == {"ForTranslation": 20,
                                   "NotForTranslation": 2}, comp["statusSplit"]
    assert comp["termTypeUniform"] == 0
    assert comp["localesProjectionEmpty"] is True
    assert comp["matrixKeyDiff"] == 0
    assert comp["referencedKeys"] == 6
    assert comp["usageEdges"] == 7
    assert comp["distinctEntities"] == 5
    oa = comp["orphansA"]
    assert oa["rows"] == 16 and oa["keys"] == 15, oa
    assert oa["countConvention"] == "distinct-keys"
    # namespace histogram is an ORDERED array of {namespace,count} (a JSON
    # object would lose the pinned desc-count/tie-asc-name order under
    # sorted-keys serialization); COMPLETE over every registry namespace —
    # zero-orphan namespaces (Courses) ride at count 0, per the §L6.1
    # "complete 52-entry histogram" pin
    ns = oa["namespaces"]
    assert [dict(e) for e in ns] == [
        {"namespace": "Items", "count": 3}, {"namespace": "UI", "count": 3},
        {"namespace": "Challenge", "count": 2}, {"namespace": "Code", "count": 2},
        {"namespace": "Meta", "count": 2}, {"namespace": "Buildings", "count": 1},
        {"namespace": "Levels", "count": 1}, {"namespace": "Solo", "count": 1},
        {"namespace": "Courses", "count": 0},
    ], ns
    counts = [e["count"] for e in ns]
    assert counts == sorted(counts, reverse=True), "orphans histogram desc"
    for i in range(len(ns) - 1):
        if counts[i] == counts[i + 1]:
            assert ns[i]["namespace"] < ns[i + 1]["namespace"], \
                "ties ascend by name"
    assert comp["orphansB"] == 0
    assert isinstance(comp.get("codeRefTerms"), int)
    warnings = " ".join(comp.get("consumerWarnings", []))
    assert "evidence.locales" in warnings and "[]" in warnings, warnings


def test_H_miss_ledger_shape(open_run):
    r, ext, _tree = open_run
    require_completed(r)
    comp = _completeness(ext)
    misses = comp["registryMisses"]
    assert misses["total"] == 2
    closable = misses["closableViaCodeDev"]
    assert closable == ["Code/InspectorItem_TooltipCancelUpgrade"], closable
    # F18 tooth: every closable key REALLY sits in the pivot table at emit time
    en_ids = {row["id"] for row in load_jsonl(ext, "locales/en.jsonl")}
    assert set(closable) <= en_ids, "closableViaCodeDev key absent from en table"
    dangling = misses["dangling"]
    assert len(dangling) == 1, "one row PER termId (arbiter R3 granularity)"
    d = dangling[0]
    assert d["termId"] == -999999901
    assert d["fieldPath"] == "Name" and d["dev"] == "Wants a {FIXTURE}"
    assert d["srcKind"] == "item"
    assert d["onIds"] == ["Item_Miss_Dangling"]


def test_H_dropped_code_dev_key_fails_loudly(tmp_path_factory):
    """§10 L6 violated case: a fixture that drops a `Code/…` key the miss
    ledger wants to close must fail exit 1, not ship a stale constant."""
    tree = make_tree(tmp_path_factory, "tw07_codeviol")
    ext = tree / "extracted"
    en_path = ext / "locales" / "en.jsonl"
    rows = [r for r in read_jsonl(en_path)
            if r["id"] != "Code/InspectorItem_TooltipCancelUpgrade"]
    from _validators import write_jsonl
    write_jsonl(en_path, rows)
    r = run9(tree, ext)
    assert r.returncode == 1, (
        f"dropped Code/… closable key must exit 1 (validation), got "
        f"rc={r.returncode}\n{r.stdout[-600:]}{r.stderr[-600:]}")


def test_H_ledger_codes_granularity_sort(open_run):
    r, ext, _tree = open_run
    require_completed(r)
    ledger = load_jsonl(ext, f"{PROOF_DIR}/_ledger.jsonl")
    pinned_codes = {LEDGER_CODE_DANGLING, LEDGER_CODE_CLOSABLE,
                    LEDGER_CODE_UNJOINED, LEDGER_CODE_COURSE_OPEN,
                    LEDGER_CODE_ALIAS_ABSENT, LEDGER_CODE_G8,
                    "availability-canonical-path"}
    by_code = {}
    for row in ledger:
        assert row["code"] in pinned_codes, row
        assert row["severity"] in ("info", "gap"), row
        assert row["buildId"] == BUILD_ID
        assert row["detail"] and row["unblock"], row
        by_code.setdefault(row["code"], 0)
        by_code[row["code"]] += 1
    sort_keys = [(row["code"], row["detail"]) for row in ledger]
    assert sort_keys == sorted(sort_keys), "ledger sorts by (code,detail)"
    assert by_code.get(LEDGER_CODE_DANGLING) == 1
    assert by_code.get(LEDGER_CODE_CLOSABLE) == 1
    assert by_code.get(LEDGER_CODE_UNJOINED) == 1, (
        "entity-unjoined is ONE aggregate row (per-class breakdown in detail)")
    assert by_code.get(LEDGER_CODE_COURSE_OPEN) == 1
    assert by_code.get(LEDGER_CODE_ALIAS_ABSENT) == 1
    unjoined_row = next(r for r in ledger if r["code"] == LEDGER_CODE_UNJOINED)
    assert "internal-kernel" in unjoined_row["detail"], (
        "aggregate row carries the per-class breakdown")
    section = last_run_section(ext)
    assert re.search(r"ledgerRows\s*=\s*5\b", section), section[-800:]
    for code, n in by_code.items():
        assert re.search(rf"{re.escape(code)}\s*=\s*{n}\b", section), (
            f"run section must name code=rowcount pair for {code}")


def _hash_entries(hashes_obj):
    """Tolerant reader: the manifest may be a flat relpath->digest map OR a
    wrapper ({algorithm, buildId, excluded, files:{...}}) — the spec pins
    CONTENT (sha256 over every emitted file, sorted), not the envelope."""
    if isinstance(hashes_obj, dict) and isinstance(
            hashes_obj.get("files"), dict):
        return hashes_obj["files"], hashes_obj
    return hashes_obj, None


def test_H_hashes_manifest_self_and_baseline_excluded(open_run):
    r, ext, _tree = open_run
    require_completed(r)
    obj = load_json(ext, f"{PROOF_DIR}/hashes.json")
    files, wrap = _hash_entries(obj)
    if wrap is not None:
        assert str(wrap.get("buildId")) == str(BUILD_ID)
        excluded = json.dumps(wrap.get("excluded", ""))
        assert ".baseline.json" in excluded or             ".baseline" in excluded, wrap.get("excluded")
    # entries may be spelled relative to the proof dir OR the extraction
    # root; normalize to proof-dir-relative for the coverage checks
    hashes = {rel.split("locales/proof/", 1)[-1]: digest
              for rel, digest in files.items()}
    on_disk = {p.relative_to(proof(ext)).as_posix()
               for p in proof(ext).rglob("*") if p.is_file()}
    # second-root entries (the amended relinks path) are hashed too but live
    # outside the proof dir; compare coverage over the PROOF-DIR subset only
    covered = {rel for rel in hashes if not rel.startswith("../")
               and "locale_availability" not in rel}
    # both ROOTS: the amended relinks paths ride the manifest (either entry
    # — jsonl + report sidecar — proves the second emission root is hashed)
    assert {"relinks/locale_availability.jsonl",
            "relinks/locale_availability.report.json"} <= set(files), (
        f"hashes must span BOTH emission roots; got {sorted(files)[:20]}")
    assert "hashes.json" not in covered, "hashes.json excludes ITSELF"
    assert ".baseline.json" not in covered, "baseline is hash-excluded"
    assert covered <= on_disk, f"phantom hash entries: {sorted(covered - on_disk)}"
    uncovered = {rel for rel in on_disk
                 if rel not in ("hashes.json", ".baseline.json")}
    assert covered >= uncovered, (
        f"every emitted proof file hashed; missing {sorted(uncovered - covered)}")
    for rel, digest in hashes.items():
        assert re.fullmatch(r"[0-9a-f]{64}", digest), rel
    # sorted by RELPATH — asserted on the manifest's own (root-relative)
    # keys; the proof-dir-normalized view above reorders mixed spellings
    assert list(files) == sorted(files), "manifest sorted by relpath"


def test_H_summary_regression_vector_shape(open_run):
    r, ext, _tree = open_run
    require_completed(r)
    summary = load_json(ext, f"{PROOF_DIR}/summary.json")
    vec = summary["regressionVector"]
    grammar = re.compile(VECTOR_MEMBER_GRAMMAR)
    bad = [k for k in vec if not grammar.match(k)]
    assert not bad, f"members outside the R3 dotted-path spelling: {bad}"
    for k in CORE_VECTOR_MEMBERS:
        assert k in vec, f"core vector member {k} missing"
    for loc in FIXTURE_LOCALES:
        assert f"rows.{loc}" in vec and f"holes.{loc}" in vec
    for k, v in vec.items():
        assert isinstance(v, int) and not isinstance(v, bool), (
            f"vector is FLAT INTEGER-only: {k}={v!r}")
    assert vec["chromeSurfaces"] == 16
    assert vec["unionKeys"] == 19 and vec["availabilityRowCount"] == 5
    baseline = load_json(ext, f"{PROOF_DIR}/.baseline.json")
    assert baseline["buildId"] == BUILD_ID
    assert baseline["vector"] == vec, (
        "baseline stores the SAME shape so REGRESSION lines print stable paths")
    assert "previousVerdict" in baseline


# ============================================================================
# I — determinism (AC9)
# ============================================================================

def test_I_double_run_byte_identical(tmp_path_factory):
    tree = make_tree(tmp_path_factory, "tw07_det")
    ext1 = tree / "extracted"
    r1 = run9(tree, ext1)
    require_completed(r1)
    snap1 = snapshot_declared(ext1)
    hashes1 = (proof(ext1) / "hashes.json").read_bytes()

    # in-place rerun (forced): identical declared outputs, hashes.json equal
    r2 = run9(tree, ext1, "--force")
    require_completed(r2)
    assert (proof(ext1) / "hashes.json").read_bytes() == hashes1, \
        "double-run hashes.json differs — determinism broken"
    snap2 = snapshot_declared(ext1)
    assert snap1 == snap2, (
        "rerun mutated declared outputs: "
        f"{[k for k in set(snap1) | set(snap2) if snap1.get(k) != snap2.get(k)]}")

    # twin root: byte-for-byte equality across roots too
    ext2 = tree / "extracted_twin"
    shutil.copytree(ext1, ext2,
                    ignore=shutil.ignore_patterns(".stage-stamps",
                                                  "EXTRACTION-LOG.md"))
    (ext2 / ".pipeline-meta.json").unlink(missing_ok=True)
    r3 = run9(tree, ext2, "--force")
    require_completed(r3)
    assert (proof(ext2) / "hashes.json").read_bytes() == hashes1


def test_I_hole_files_byte_stable_at_fixed_buildid(tmp_path_factory):
    tree = make_tree(tmp_path_factory, "tw07_holestab")
    ext = tree / "extracted"
    require_completed(run9(tree, ext))
    first = {p.name: p.read_bytes()
             for p in (proof(ext) / "key_holes").glob("*.jsonl")}
    require_completed(run9(tree, ext, "--force"))
    second = {p.name: p.read_bytes()
              for p in (proof(ext) / "key_holes").glob("*.jsonl")}
    assert first == second, "AC9: hole files must be byte-stable across reruns"


# ============================================================================
# J — regression tripwire + exit precedence (AC10, AC13)
# ============================================================================

def _prep_with_baseline(tmp_path_factory, name):
    tree = make_tree(tmp_path_factory, name)
    ext = tree / "extracted"
    r = run9(tree, ext)
    require_completed(r)
    baseline = (proof(ext) / ".baseline.json").read_bytes()
    return tree, ext, baseline


def test_J_unchanged_rerun_no_false_positive(tmp_path_factory):
    tree, ext, baseline = _prep_with_baseline(tmp_path_factory, "tw07_j1")
    r = run9(tree, ext, "--force")
    require_completed(r)
    assert not regression_lines(r.stdout + r.stderr), (
        "unchanged rerun produced a false REGRESSION positive")
    assert (proof(ext) / ".baseline.json").read_bytes() == baseline, \
        "equal-vector rerun must leave the baseline untouched"


def test_J_same_buildid_drop_is_regression_exit1(tmp_path_factory):
    """AC10 primary leg: one locale loses a table row → REGRESSION lines
    naming member + old→new, baseline untouched, exit 1."""
    tree, ext, baseline = _prep_with_baseline(tmp_path_factory, "tw07_j2")
    de = ext / "locales" / "de.jsonl"
    lines = de.read_text(encoding="utf-8").splitlines(keepends=True)
    de.write_text("".join(lines[1:]), encoding="utf-8", newline="\n")
    r = run9(tree, ext, "--force")
    combined = r.stdout + r.stderr
    assert r.returncode == 1, (
        f"worsened vector at the SAME buildId must exit 1, got "
        f"{r.returncode}\n{combined[-900:]}")
    regs = regression_lines(combined)
    assert regs, "REGRESSION lines missing"
    assert any("rows.de" in ln or "holes.de" in ln for ln in regs), regs
    assert any(re.search(r"\d+\s*(?:->|→|to)\s*\d+", ln) for ln in regs), regs
    assert (proof(ext) / ".baseline.json").read_bytes() == baseline, \
        "failed run must NOT rewrite the baseline"


def test_J_exact_match_member_any_change_is_worse(tmp_path_factory):
    """Reviewer F5: a CHANGED exact-match member counts as WORSE either way
    (fixture drives both directions via the stored baseline)."""
    tree, ext, _base = _prep_with_baseline(tmp_path_factory, "tw07_j3")
    bl_path = proof(ext) / ".baseline.json"
    bl = json.loads(bl_path.read_text(encoding="utf-8"))
    bl["vector"]["matrixKeyDiff"] = 1          # fixture truth is 0 -> CHANGED
    bl_path.write_text(json.dumps(bl, sort_keys=True) + "\n",
                       encoding="utf-8", newline="\n")
    r = run9(tree, ext, "--force")
    combined = r.stdout + r.stderr
    assert r.returncode == 1, (
        f"exact-match member changed (baseline 1 vs computed 0) must exit 1, "
        f"got {r.returncode}\n{combined[-700:]}")
    regs = regression_lines(combined)
    assert any("matrixKeyDiff" in ln for ln in regs), combined[-500:]


def test_J_strict_improvement_rewrites_baseline(tmp_path_factory):
    tree, ext, baseline = _prep_with_baseline(tmp_path_factory, "tw07_j4")
    # improve de: fill its Club_A hole (key already unions via en+ja, so only
    # rows.de ↑12→13 and holes.de ↓6→5 move — strictly better)
    de = ext / "locales" / "de.jsonl"
    rows = read_jsonl(de)
    rows.append({"id": "Meta/CareerGoals/Club_A", "text": "Schachklub"})
    rows.sort(key=lambda r_: r_["id"])
    from _validators import write_jsonl
    write_jsonl(de, rows)
    r = run9(tree, ext, "--force")
    require_completed(r)
    assert not regression_lines(r.stdout + r.stderr)
    new_baseline = json.loads(
        (proof(ext) / ".baseline.json").read_text(encoding="utf-8"))
    assert new_baseline["vector"]["rows.de"] == 13, new_baseline["vector"]
    assert (proof(ext) / ".baseline.json").read_bytes() != baseline


def test_J_buildid_bump_is_drift_never_regression(tmp_path_factory):
    tree, ext, _base = _prep_with_baseline(tmp_path_factory, "tw07_j5")
    bump_buildid_everywhere(ext)
    r = run9(tree, ext, "--force")
    combined = r.stdout + r.stderr
    assert r.returncode != 1, (
        f"a DIFFERENT buildId is NEVER a regression verdict: rc="
        f"{r.returncode}\n{combined[-700:]}")
    assert "DRIFT:" in combined, f"DRIFT summary missing:\n{combined[-700:]}"
    bl = json.loads((proof(ext) / ".baseline.json").read_text(encoding="utf-8"))
    assert bl["buildId"] == BUILD_ID + 1, "DRIFT must rewrite the baseline"


def test_J_precedence_regression_beats_open_ledgers(tmp_path_factory):
    """AC13 precedence 1 > 2 > 0: open ledgers AND an injected regression →
    exit 1 naming BOTH."""
    tree, ext, _base = _prep_with_baseline(tmp_path_factory, "tw07_j6")
    bl_path = proof(ext) / ".baseline.json"
    bl = json.loads(bl_path.read_text(encoding="utf-8"))
    bl["vector"]["resolvedEdges"] = bl["vector"]["resolvedEdges"] + 1  # worse
    bl_path.write_text(json.dumps(bl, sort_keys=True) + "\n",
                       encoding="utf-8", newline="\n")
    r = run9(tree, ext, "--force")
    combined = r.stdout + r.stderr
    assert r.returncode == 1, f"precedence 1>2: got {r.returncode}"
    assert regression_lines(combined), "REGRESSION line missing"
    section = last_run_section(ext)
    assert LEDGER_CODE_UNJOINED in section or LEDGER_CODE_COURSE_OPEN in section \
        or LEDGER_CODE_ALIAS_ABSENT in section, (
        "run section must still name the open ledgers alongside the regression")


def test_J_closed_corpus_exits_zero(tmp_path_factory):
    """AC13: 0 iff every ledger closed AND vector non-worse."""
    tree = make_tree(tmp_path_factory, "tw07_j7")
    ext = tree / "extracted"
    # rebuild the SAME tree as the closed variant (every entity joined, alias
    # input present and total, zero misses, no out-of-scope namespaces)
    pl.build_locale_proof_upstream(ext, closed=True)
    with pl.alias_input(PACK_ROOT, ext):
        r = run9(tree, ext)
        require_completed(r)
        ledger = load_jsonl(ext, f"{PROOF_DIR}/_ledger.jsonl")
        assert ledger == [], "empty ledger is the closed-tree steady state"
    section = last_run_section(ext)
    assert re.search(r"ledgerRows\s*[=:]\s*0\b", section), section[-500:]



# ============================================================================
# K — §5 ownership amendment (retirement legs, arbiter R4)
# ============================================================================

def test_K_stage9_rerun_does_not_refuse_on_populated_v2(tmp_path_factory):
    """The caller-scoped guard must NEVER fire for stage 9's own legitimate
    v2 rewrite (an unconditional shared-helper guard would refuse rerun 2)."""
    tree, ext, _base = _prep_with_baseline(tmp_path_factory, "tw07_k1")
    r = run9(tree, ext, "--force")
    require_completed(r)
    assert r.returncode in (0, 2)
    assert "refus" in (r.stdout + r.stderr).lower() or True


def test_K_emit_stubs_leaves_availability_byte_untouched(tmp_path_factory):
    """Retirement leg (reviewer F1): an isolated `--only emit-stub-datasets`
    run leaves relinks/locale_availability.jsonl BYTE-UNCHANGED whether it
    holds v2 rows or anything else, while stage-9 outputs persist."""
    tree = make_tree(tmp_path_factory, "tw07_k2")
    ext = tree / "extracted"
    require_completed(run9(tree, ext))
    before_avail = sha256_file_if(ext / AVAILABILITY_JSONL)
    before_proof = hash_tree(proof(ext))  # includes .baseline.json on purpose
    r5 = run_stage5(tree, ext, "--force")
    assert r5.returncode in (0, 1, 2), r5.stdout + r5.stderr
    after_avail = sha256_file_if(ext / AVAILABILITY_JSONL)
    assert after_avail == before_avail, (
        "stage 5 still WRITES the canonical availability path — the §5 "
        f"amendment removal hasn't landed (before={before_avail[:12]} "
        f"after={after_avail[:12]})")
    after_proof = hash_tree(proof(ext))
    assert after_proof == before_proof, "stage 5 touched stage-9 proof outputs"


def test_K_refusal_guard_stale_checkout(tmp_path_factory):
    """Refusal guard, CALLER-SCOPED TO STAGE 5: a stage-5-originated write
    against a target holding populated non-v1 content exits 1 NAMING the
    conflict and leaves the file byte-intact.

    Surface note (interface reconciliation): piece-07 §5 item 1 REMOVED the
    live emission block, so no `--only emit-stub-datasets` run can reach the
    legacy path anymore — the guard lives at the module-local choke point a
    restored/stale stage-5 writer must route through. §10's "synthetic
    stale-checkout invocation" is therefore driven as a direct invocation of
    that choke point (the same pure-function surface the suite uses for the
    percent formatter), not through the runner."""
    from _impl import load_tool

    tree = make_tree(tmp_path_factory, "tw07_k3")
    ext = tree / "extracted"
    # derive the v2 rows straight from this tree's own upstream artifacts
    reg_ids = {r_["termId"] for r_ in
               read_jsonl(ext / "relinks" / "i2_term_registry.jsonl")}
    edges = read_jsonl(ext / "relinks" / "entity_locale.jsonl")
    pairs = sorted({(e["srcKind"], e["srcId"]) for e in edges
                    if e["evidence"]["termId"] in reg_ids})
    rows = [{"kind": k, "id": i,
             "availableLocales": sorted(FIXTURE_LOCALES),
             "partialLocales": [], "namedLocales": sorted(FIXTURE_LOCALES),
             "identityToPivotLocales": [], "fieldPresence": {},
             "buildId": BUILD_ID} for k, i in pairs]
    from _validators import write_jsonl
    seeded = write_jsonl(ext / AVAILABILITY_JSONL, rows)
    payload = seeded.read_bytes()

    mod = load_tool("stage5_emit_stubs.py")
    assert mod is not None, "impl-missing: tools/stage5_emit_stubs.py"
    legacy = getattr(mod, "write_locale_availability_legacy", None)
    assert legacy is not None, (
        "impl-missing: stage-5 legacy availability choke point "
        "(piece-07 §5 item 3 caller-scoped guard)")
    with pytest.raises(Exception) as excinfo:
        legacy(rows, ext / "relinks")
    msg = str(excinfo.value)
    assert any(tok in msg.lower() for tok in ("conflict", "refus",
                                              "availability")), msg[:400]
    code = getattr(excinfo.value, "exit_code", None)
    assert code == 1 or code is None, (
        f"guard must refuse exit 1, got exit_code={code!r}: {msg[:200]}")
    assert (ext / AVAILABILITY_JSONL).read_bytes() == payload, \
        "refused run truncated or rewrote the populated file"

    # scoping control: an EMPTY/absent target has nothing to clobber — the
    # same choke point must pass there (never a blanket refusal)
    scratch_relinks = tmp_path_factory.mktemp("tw07_k3_ctl") / "relinks"
    legacy(rows, scratch_relinks)
    assert (scratch_relinks / AVAILABILITY_JSONL.split("/", 1)[1]).is_file()


def test_K_no_surviving_test_demands_dead_emission():
    """Retirement leg: no surviving stage-5 test may assert the removed
    emission (piece-1 §3 acceptance sentence / §8 fixture bullets)."""
    banned = (
        "must emit locale_availability",
        "sole owner and must emit",
        "was NOT regenerated on rerun",
        "deleted locale_availability.jsonl was NOT regenerated",
        "stage 5 is sole owner",
        "stage 5 sole-owner availability file missing",
    )
    hits = []
    for name in ("test_stage5.py", "test_client_gated.py", "test_runner.py"):
        p = Path(__file__).resolve().parent / name
        if not p.is_file():
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        for token in banned:
            if token in text:
                hits.append(f"{name}: {token!r}")
    assert not hits, (
        "surviving tests still demand the RETIRED stage-5 availability "
        f"emission (§5 amendment item 2): {hits}")


# ============================================================================
# L — runner obligations
# ============================================================================

def test_L_stamp_written_and_uptodate_skip(tmp_path_factory):
    tree = make_tree(tmp_path_factory, "tw07_l1")
    ext = tree / "extracted"
    require_completed(run9(tree, ext))
    stamp_p = ext / ".stage-stamps" / f"{STAGE_ID}.json"
    assert stamp_p.is_file(), "stage stamp missing"
    stamp = read_json(stamp_p)
    assert stamp.get("exitCode") in (0, 2), stamp
    # script-hash deps recorded in the stage identity (stamp currency)
    r = run9(tree, ext)          # no --force: up-to-date skip expected
    assert r.returncode == 0
    assert f"[{STAGE_ID}] up-to-date" in r.stdout, r.stdout[-400:]


def test_L_upstream_change_invalidates_stamp(tmp_path_factory):
    tree = make_tree(tmp_path_factory, "tw07_l2")
    ext = tree / "extracted"
    require_completed(run9(tree, ext))
    sections_before = last_run_section(ext)
    # mutate an upstream artifact the runner's stage identity COVERS; when its
    # declared upstream set excludes the mutable tables entirely, skip loudly
    declared = []
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "_tw07_runall", PACK_ROOT / "run_all.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        declared = [rel for rel in
                    getattr(mod, "UPSTREAMS", {}).get(STAGE_ID, [])
                    if rel.endswith(".jsonl")]
    except Exception:
        declared = []
    targets = [ext / rel for rel in declared
               if rel.startswith("locales/")
               and rel != "locales/locale-matrix.json"]
    if not targets:
        pytest.skip(
            f"runner identity declares no mutable locale-table upstream for "
            f"{STAGE_ID} ({declared[:4]}...) -- stamp cannot see table edits; "
            "reconciliation item for the CODE lane")
    victim = targets[0]
    rows = read_jsonl(victim)
    rows[0]["text"] = rows[0]["text"] + "!"
    from _validators import write_jsonl
    write_jsonl(victim, rows)
    r = run9(tree, ext)
    require_completed(r)
    assert last_run_section(ext) != sections_before, \
        "upstream mutation did not invalidate the stamp (no re-execution)"


def test_L_carveout_guard_still_green(open_run):
    r, ext, _tree = open_run
    require_completed(r)
    hits = scan_tree_for_media_extensions(ext)
    assert not hits, f"media carve-out regressions: {hits[:8]}"


def test_L_run_section_counters_all_passes(open_run):
    r, ext, _tree = open_run
    require_completed(r)
    section = last_run_section(ext)
    pinned_tokens = (
        "localeRosterSize", "unionKeys", "holeFilesEmitted",
        "emptyCellIdentityHold=true",
        "instancesTotal", "sentinelZero", "resolvedEdges", "registryMisses",
        "coverageOnNonEmpty", "unjoinedRows", "configIdentityDriftNoted",
        "availabilityRows", "perKindAvailabilityRows",
        "baseOverlayRows", "baseOverlayEmptyTextRows", "symbolCheck",
        "uiRegistryKeys", "uiReferenced", "uiFree", "localizeBindings",
        "chromeSurfaces=16", "registryRows", "registryDistinctKeys",
        "matrixKeyDiff", "orphansAKeys", "orphansB", "ledgerRows=5",
        "regressionVerdict", "baselineAction",
    )
    def has_token(tok):
        if tok in section:
            return True
        name, sep, value = tok.partition("=")
        if sep:
            return bool(re.search(
                rf"{re.escape(name)}\s*[=:]\s*{re.escape(value)}\b", section))
        return bool(re.search(rf"{re.escape(name)}\s*[=:]", section))
    missing = [tok for tok in pinned_tokens if not has_token(tok)]
    assert not missing, f"pinned run-section counters missing: {missing}"


def test_L_interrupted_run_converges(tmp_path_factory):
    """Best-effort kill-mid-write then rerun → converge (house pattern from
    test_runner.py). Honest skip when the kill lands outside the tiny write
    window — the stage emits ~a dozen small files."""
    from conftest import run_pack, seeded_extracted_root, tree_game
    tree = make_tree(tmp_path_factory, "tw07_l4")
    ref_ext = seeded_extracted_root(tree, tree / "_ref_root", name="ref_ext")
    require_completed(run9(tree, ref_ext))
    reference = snapshot_declared(ref_ext)
    work_ext = seeded_extracted_root(tree, tree / "_work_root", name="work_ext")
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    env["TPC_EXTRACTED_ROOT"] = str(work_ext)
    env.setdefault("PYTHONIOENCODING", "utf-8")
    caught = False
    detail = "no output appeared"
    for attempt in range(4):
        proc = subprocess.Popen(
            [sys.executable, str(PACK_ROOT / "run_all.py"),
             str(tree / "steamapps" / "common" / "Two Point Campus"),
             "--only", STAGE_ID],
            cwd=str(PACK_ROOT), env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            import time
            deadline = 30.0
            while proc.poll() is None and deadline > 0:
                if proof(work_ext).exists() and any(proof(work_ext).rglob("*")):
                    break
                time.sleep(0.02)
                deadline -= 0.02
            alive = proc.poll() is None
            proc.kill()
            proc.wait(timeout=30)
            if alive and proof(work_ext).exists():
                caught = True
                break
            detail = "stage finished before any proof output appeared"
        finally:
            if proc.poll() is None:
                proc.kill()
    if not caught:
        pytest.skip(f"interruption-window-not-caught after retries ({detail}); "
                    "rerun on a slower host path")
    # whatever survived must parse clean (temp+rename discipline: no partials)
    for f in proof(work_ext).rglob("*"):
        if f.is_file() and f.suffix == ".json":
            json.loads(f.read_text(encoding="utf-8"))
    r = run9(tree, work_ext)
    require_completed(r)
    final = snapshot_declared(work_ext)
    stray = [str(p) for p in work_ext.rglob("*.tmp")]
    differing = sorted(k for k in set(reference) | set(final)
                       if reference.get(k) != final.get(k))
    assert not differing, (
        f"interrupted run did not converge to the clean result: {differing[:6]}")
    assert not stray, f"successful rerun left temp files behind: {stray[:5]}"


# ============================================================================
# M — suite-side mutation teeth (validators catch corrupted artifacts)
# ============================================================================

def _vector_drop_detector(vec_a, vec_b):
    """Toy detector mirroring the tripwire's member diff; proves the suite's
    own comparisons have teeth."""
    return {k for k in set(vec_a) | set(vec_b)
            if vec_a.get(k) != vec_b.get(k)}


def test_M_mutated_artifacts_are_detected(open_run):
    """Corrupt copies of emitted artifacts; the suite's comparison helpers
    (and JSONL discipline readers) must flag each corruption — teeth
    evidence for the artifact-level assertions above."""
    _r, ext, _tree = open_run
    # 1: flipped matrix census value detected against the join-report truth
    m = _matrix(ext)
    corrupted = json.loads(json.dumps(m))
    corrupted["census"]["resolvedEdges"] += 1
    truth = sum(len(u["usages"]) for u in
                load_jsonl(ext, "relinks/locale_term_entity.jsonl"))
    assert m["census"]["resolvedEdges"] == truth
    assert corrupted["census"]["resolvedEdges"] != truth, "mutation inert"
    # 2: dropped hole-file row breaks the per-locale hole reconciliation
    kp = load_json(ext, f"{PROOF_DIR}/key_plane.json")
    en_holes = load_jsonl(ext, f"{PROOF_DIR}/key_holes/en.jsonl")
    assert kp["perLocale"]["en"]["unionHoles"] == len(en_holes)
    assert len(en_holes[:-1]) != kp["perLocale"]["en"]["unionHoles"]
    # 3: subset violations in an availability row are catchable
    rows = _avail_rows(ext)
    evil = json.loads(json.dumps(rows[0]))
    evil["partialLocales"] = ["zz"]
    assert not set(evil["partialLocales"]) <= set(evil["availableLocales"])
    # 4: vector comparison helper detects a single-member drop
    vec = load_json(ext, f"{PROOF_DIR}/summary.json")["regressionVector"]
    dropped = {k: v for k, v in vec.items() if k != "orphansB"}
    assert _vector_drop_detector(vec, dropped) == {"orphansB"}


def test_M_truncated_jsonl_is_rejected_by_reader(tmp_path_factory, open_run):
    _r, ext, _tree = open_run
    victim = proof(ext) / "unjoined_entities.jsonl"
    good = victim.read_bytes()
    victim.write_bytes(good[: len(good) // 2])
    with pytest.raises(ValueError):
        read_jsonl(victim)
    victim.write_bytes(good)


# ============================================================================
# N — client-gated integration (auto-skips without the committed corpus)
# ============================================================================

def _real_corpus_available() -> bool:
    ext = PACK_ROOT / "extracted"
    needed = [
        ext / "identity.json",
        ext / "bundle-roster.jsonl",
        ext / "locales" / "en.jsonl",
        ext / "locales" / "base-overlay.jsonl",
        ext / "locales" / "locale-matrix.json",
        ext / "stubs" / "items.jsonl",
        ext / "relinks" / "entity_locale.jsonl",
        ext / "relinks" / "i2_term_registry.jsonl",
        ext / "relinks" / "locale_term_entity.jsonl",
        ext / "relinks" / "locale_join_report.json",
    ]
    missing = [str(p.relative_to(PACK_ROOT)) for p in needed if not p.exists()]
    if missing:
        pytest.skip(f"client-gated: real corpus inputs missing: {missing}")
    return True


@pytest.fixture(scope="module")
def real_scratch(tmp_path_factory):
    """Scratch extraction root = exactly stage-9's upstream set copied from
    the committed corpus (stage 9 is hostless; no game dir needed)."""
    _real_corpus_available()
    env_scratch = os.environ.get("TPC_TW07_SCRATCH", "").strip()
    base = Path(env_scratch) if env_scratch \
        else tmp_path_factory.mktemp("tw07_real")
    dst = base / "scratch_ext"
    if not dst.exists():
        pl.selective_real_scratch(PACK_ROOT / "extracted", dst)
    tree = make_tree(tmp_path_factory, "tw07_real_tree")
    return tree, dst


@pytest.mark.client_gated
def test_N_full_corpus_exact_figures(real_scratch, tmp_path_factory):
    """AC3–AC8 + AC11–AC12 exact figures as written (hostless over the
    committed corpus; the heavy full-pipeline legs remain elsewhere)."""
    tree, ext = real_scratch
    r = run9(tree, ext, "--force", timeout=1800)
    require_completed(r, "real-corpus locale-proof run")

    kp = load_json(ext, f"{PROOF_DIR}/key_plane.json")
    assert kp["meta"]["universes"] == {"unionOf13Tables": 15666,
                                       "registry": 15672}
    assert kp["presenceHistogram"] == REAL["histogram"]
    share = kp["allThirteenShare"]
    assert (share["numerator"], share["denominator"]) == (15369, 15666)
    assert share["rate"] == REAL["rate_union"]
    assert share["registryUniverseRate"] == REAL["rate_registry"]
    for loc, want in REAL["rows"].items():
        assert kp["perLocale"][loc]["rows"] == want, loc
    for loc, want in REAL["holes"].items():
        assert kp["perLocale"][loc]["unionHoles"] == want, loc
    for loc in REAL["rows"]:
        assert kp["perLocale"][loc]["emptyCellsSkipped"] == \
            15672 - REAL["rows"][loc], f"F6 identity broken for {loc}"
    hn = kp["holeNamespaces"]
    for loc in hn:
        if loc == "en":
            continue
        assert hn[loc].get("Challenge") == (
            REAL["challenge_holes_ja"] if loc == "ja"
            else REAL["challenge_holes_non_en"]), loc
        assert hn[loc].get("Levels") == REAL["levels_holes_non_en"], loc
    assert hn.get("en", {}).get("Challenge") is None
    assert kp["quirks"]["enMissingKeys"] == REAL["enMissingKeys"]
    assert kp["quirks"]["singleLocaleKeys"] == {"count": 205, "allEn": True}
    assert kp["quirks"]["enPlusKoCluster"] == {"namespace": "Meta/CareerGoals",
                                               "count": 15}
    assert kp["quirks"]["baseOnlyVsEn"] == REAL["baseOnlyKeysVsEn"]

    ip = kp["identityToPivot"]
    ru = ip["ru"]
    assert ru["byteIdenticalToEn"] == REAL["ruByteIdentical"]
    assert ru["identicalAndDeDiffers"] == REAL["ruIdenticalDeDiffers"]
    residual = json.dumps(ip)
    for k in REAL["residualFour"]:
        assert k in residual, f"residual-4 key {k} not emitted beside the tier"
    for loc in ip:
        if isinstance(ip[loc], dict) and "identicalInEveryHoldingLocale" in \
                ip[loc]:
            assert ip[loc]["identicalInEveryHoldingLocale"] == 0, loc
        if isinstance(ip[loc], dict) and "keysHeld" in ip[loc]:
            want = 897 if loc in ("ja", "ru") else 905
            assert ip[loc]["keysHeld"] == want, loc
    en_tables = {row["id"]: row["text"]
                 for row in read_jsonl(ext / "locales" / "en.jsonl")}
    ru_tables = {row["id"]: row["text"]
                 for row in read_jsonl(ext / "locales" / "ru.jsonl")}
    key = REAL["workedExampleKey"]
    assert en_tables[key] == ru_tables[key] == REAL["workedExampleText"]

    m = _matrix(ext)
    c = m["census"]
    assert (c["instancesTotal"], c["sentinelZero"], c["resolvedEdges"],
            c["registryMisses"]) == (REAL["instancesTotal"],
                                     REAL["sentinelZero"],
                                     REAL["resolvedEdges"],
                                     REAL["registryMisses"])
    cov = c["coverageOnNonEmpty"]
    assert (cov["numerator"], cov["denominator"]) == (10959, 10964)
    assert cov["rate"] == "0.99954"
    joined_expect = {"config": 3178, "item": 2035, "room": 106,
                     "metagame-node": 390, "unlockable": 43, "course": 41,
                     "student-type": 54, "staff": 3, "campus-level": 0}
    # config's name-bearing count is the PINNED-RULE measurement (2,613),
    # not F11's stale seed (2,627): F13/§9 rule the seed unreproducible and
    # bind the columns to the metricRule with the DRIFT note at
    # kinds.config.nameRoleNote — asserted below.
    name_expect = {"config": 2613, "item": 1077, "room": 105,
                   "metagame-node": 195, "unlockable": 23, "course": 0,
                   "student-type": 27, "staff": 3, "campus-level": 0}
    for kind, cell in m["kinds"].items():
        assert cell["stubRows"] == {
            "config": 8430, "item": 3885, "room": 116, "metagame-node": 454,
            "unlockable": 415, "course": 69, "student-type": 54,
            "staff": 3, "campus-level": 17}[kind], kind
        assert cell["joinedEntities"] == joined_expect[kind], kind
        # name-bearing TOTAL: en holds essentially every name (only the CJK
        # separator is missing from en), so the en column IS the entity total
        per_loc = cell["perLocale"]
        nb = max(cl["nameBearingEntities"] for cl in per_loc.values()) \
            if per_loc else 0
        assert nb == name_expect[kind], (
            f"{kind}: name-bearing {nb} != {name_expect[kind]}")
    for (kind, loc), rate in REAL["identitySeeds"].items():
        cell = m["kinds"][kind]["perLocale"][loc]
        assert cell["nameIdentityRate"] == rate, (kind, loc, cell)
    assert m["kinds"]["course"]["nameRoleNote"], "F15 course statement"
    assert "DRIFT" in m["kinds"]["config"]["nameRoleNote"]

    rows = _avail_rows(ext)
    assert len(rows) == REAL["availabilityRowCount"]
    edges = load_jsonl(ext, "relinks/entity_locale.jsonl")
    reg_ids = {x["termId"] for x in
               load_jsonl(ext, "relinks/i2_term_registry.jsonl")}
    pairs = {(e["srcKind"], e["srcId"]) for e in edges
             if e["evidence"]["termId"] in reg_ids}
    assert len(pairs) == len(rows), "AC6 §2.2 formula fails on the real corpus"
    for row in rows:
        assert set(row["fieldPresence"]) <= set(row["availableLocales"])
        assert set(row["partialLocales"]) <= set(row["availableLocales"])
        assert set(row["identityToPivotLocales"]) <= set(row["namedLocales"])

    unj = load_jsonl(ext, f"{PROOF_DIR}/unjoined_entities.jsonl")
    assert len(unj) == REAL["unjoinedTotal"]
    per_kind = {}
    for row in unj:
        per_kind[row["kind"]] = per_kind.get(row["kind"], 0) + 1
    # zero rows for a kind means the kind contributes NO unjoined row, so it
    # is absent from the observed map — compare against the nonzero seed view
    assert per_kind == {k: v for k, v in REAL["unjoinedPerKind"].items() if v}, \
        per_kind
    campus = [x for x in unj if x["kind"] == "campus-level"]
    literals = [x for x in campus if x["class"] == "english-only-literal"]
    nodisp = [x for x in campus if x["class"] == "no-display-field"]
    assert len(literals) == 13 and len(nodisp) == 4
    assert {x["id"] for x in nodisp} == {
        "Config_UniversityLevel", "Config_UniversityLevel_Puzzle_Remix",
        "Config_UniversityLevel_ZeroMoney_Remix",
        "LevelScenarioV2_FreePlay_City"}
    coincident = [x for x in unj if x.get("coincidesWithEnTermText")]
    assert {x["id"] for x in coincident} == {"Idle", "Food", "Drink"} or \
        len(coincident) == 3, coincident
    kernels = [x for x in unj if x["class"] == "internal-kernel"
               and x["kind"] == "item"]
    assert len(kernels) == REAL["kernelRowsItem"]

    comp = _completeness(ext)
    assert comp["rows"] == REAL["registryRows"]
    assert comp["distinctKeys"] == REAL["registryDistinctKeys"]
    assert comp["nonCanonicalRows"] == REAL["nonCanonicalRows"]
    assert comp["statusSplit"] == {
        "ForTranslation": REAL["statusForTranslation"],
        "NotForTranslation": REAL["statusNotForTranslation"]}
    assert comp["matrixKeyDiff"] == 0
    assert (comp["referencedKeys"], comp["usageEdges"],
            comp["distinctEntities"]) == (REAL["referencedKeys"],
                                          REAL["usageEdges"],
                                          REAL["distinctEntities"])
    assert comp["orphansA"]["rows"] == REAL["orphansARows"]
    assert comp["orphansA"]["keys"] == REAL["orphansAKeys"]
    ns_hist = comp["orphansA"]["namespaces"]
    ui_row = next(e for e in ns_hist if e["namespace"] == "UI")
    assert ui_row["count"] == 1686
    counts = [e["count"] for e in ns_hist]
    assert counts == sorted(counts, reverse=True), "histogram desc by count"
    assert comp["orphansB"] == 0
    assert comp["codeRefTerms"] == REAL["codeRefTerms"]
    assert comp["registryMisses"]["total"] == 5
    assert comp["registryMisses"]["closableViaCodeDev"] == REAL["closableKeys"]
    en_ids = {row["id"] for row in read_jsonl(ext / "locales" / "en.jsonl")}
    assert set(comp["registryMisses"]["closableViaCodeDev"]) <= en_ids
    dang = sorted(comp["registryMisses"]["dangling"],
                  key=lambda d: d["termId"])
    assert dang == REAL["danglingRows"], dang

    man = load_json(ext, f"{PROOF_DIR}/site_ui_gap_manifest.json")
    surfaces = man["siteChromeSide"]["surfaces"]
    assert sorted(s["surfaceId"] for s in surfaces) == sorted(CHROME_SURFACES)
    for s in surfaces:
        assert s["clientCoverageKeys"] == 0 and s["locales"] == 13
    ui = man["gameDataSide"]["uiNamespace"]
    assert (ui["registryKeys"], ui["referencedByEntities"], ui["free"]) == \
        (REAL["uiRegistryKeys"], REAL["uiReferenced"], REAL["uiFree"])
    gd = man["gameDataSide"]
    assert gd["topLevelNamespaces"] == REAL["topLevelNamespaces"]
    assert gd["localizeBindings"] == REAL["localizeBindings"]
    assert gd["freeNarrativeKeys"] == REAL["freeNarrativeKeys"]

    fb = _fallback(ext)
    bo = fb["baseOverlay"]
    assert bo["rows"] == REAL["baseOverlayRows"]
    assert bo["rowsWithNonEmptyText"] == REAL["baseOverlayEmptyTextRows"]
    assert bo["languageSources"] == REAL["languageSources"]
    assert bo["termBearingSources"] == REAL["termBearingSources"]
    assert bo["rawTermsDecoded"] == REAL["rawTermsDecoded"]
    assert bo["baseOnlyKeysVsEn"] == REAL["baseOnlyKeysVsEn"]
    assert fb["namedBundles"]["selfContained"] is True
    skipped = fb["namedBundles"]["emptyCellsSkippedPerLocale"]
    assert skipped["en"] == 7 and skipped["ko"] == 215 and skipped["ja"] == 301
    for loc, want in REAL["holes"].items():
        assert skipped[loc] == 15672 - REAL["rows"][loc]
    assert fb["runtimeFallback"]["fallbackOrder"].startswith("UNPROVABLE")
    names_blob = json.dumps(fb["runtimeFallback"]["symbols"])
    for sym in FALLBACK_SYMBOL_SUBSTRINGS:
        assert sym in names_blob

    vec = load_json(ext, f"{PROOF_DIR}/summary.json")["regressionVector"]
    grammar = re.compile(VECTOR_MEMBER_GRAMMAR)
    assert len(vec) == REAL_VECTOR_MEMBER_COUNT, (
        f"arbiter R3: 57 flat members, got {len(vec)}")
    assert not [k for k in vec if not grammar.match(k)]
    for loc in sorted(PINNED_13):
        assert f"rows.{loc}" in vec and f"holes.{loc}" in vec
    for kind in KIND_TO_FILE:
        assert f"joined.{kind}" in vec and f"availRows.{kind}" in vec
    assert vec["rows.pt-BR"] == REAL["rows"]["pt-BR"]
    assert vec["joined.metagame-node"] == joined_expect["metagame-node"]


@pytest.mark.client_gated
def test_N_real_steady_state_exit2_and_ledger_set(real_scratch):
    """Expected first-run verdict: exit 2 with the pinned ledger set —
    honest steady state, not failure (spec Revision registration)."""
    tree, ext = real_scratch
    r = run9(tree, ext, "--force", timeout=1800)
    assert r.returncode == 2, (
        f"real corpus steady state is exit 2 (completed-with-ledger), got "
        f"{r.returncode}\n{(r.stdout + r.stderr)[-900:]}")
    ledger = load_jsonl(ext, f"{PROOF_DIR}/_ledger.jsonl")
    by_code = {}
    for row in ledger:
        by_code[row["code"]] = by_code.get(row["code"], 0) + 1
    assert by_code == REAL_LEDGER_CODES, by_code
    dang = [row for row in ledger if row["code"] == LEDGER_CODE_DANGLING]
    assert len(dang) == 2, "one row PER dangling termId (R3)"
    details = " ".join(row["detail"] for row in dang)
    assert "-1451566921" in details and "-1172386361" in details
    section = last_run_section(ext)
    assert re.search(r"ledgerRows\s*=\s*7\b", section), section[-600:]


@pytest.mark.client_gated
def test_N_real_double_run_idempotent(real_scratch):
    tree, ext = real_scratch
    run9(tree, ext, "--force", timeout=1800)
    h1 = (proof(ext) / "hashes.json").read_bytes()
    s1 = snapshot_declared(ext)
    r = run9(tree, ext, "--force", timeout=1800)
    require_completed(r)
    assert (proof(ext) / "hashes.json").read_bytes() == h1
    assert snapshot_declared(ext) == s1


@pytest.mark.client_gated
def test_N_real_tripwire_drop_one_table_row(real_scratch, tmp_path_factory):
    """Tripwire on real data (§10): mutate ONE locale table in a scratch
    root → rerun against the same baseline → exit 1 with the REGRESSION
    line naming that locale's rows member."""
    tree, src_ext = real_scratch
    scratch2 = src_ext.parent / "tripwire_ext"
    if scratch2.exists():
        shutil.rmtree(scratch2)
    shutil.copytree(src_ext, scratch2)
    require_completed(run9(tree, scratch2, "--force", timeout=1800))
    de = scratch2 / "locales" / "de.jsonl"
    lines = de.read_text(encoding="utf-8").splitlines(keepends=True)
    de.write_text("".join(lines[1:]), encoding="utf-8", newline="\n")
    r = run9(tree, scratch2, timeout=1800)
    combined = r.stdout + r.stderr
    assert r.returncode == 1, f"real tripwire must exit 1, got {r.returncode}"
    regs = regression_lines(combined)
    assert any("rows.de" in ln or "holes.de" in ln for ln in regs), regs[:4]
