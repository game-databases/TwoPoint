"""Stage 5 `emit-stub-datasets` obligations (spec §8 stage-5 bullets + R3/R8).

Stage 5 consumes only JSON artifacts (monobehaviour dumps, catalog.json,
structural/*, locale-matrix.json), so the FULL acceptance runs hostless on
the prepared tree: `run_all.py <tree> --only emit-stub-datasets`.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from _fixturelib import BIG_FAMILY_COUNT, ENTITIES, HARD_JOIN_IDS, UNMAPPED
from _impl import KIND_MAP_NAMES, STUB_VALIDATE_NAMES, get_sym, load_tool
from _validators import (BUILD_ID, KIND_TO_FILE, check_identifier_verbatim,
                         diff_manifests, hash_tree, identifier_sample_ids,
                         read_jsonl, validate_absence_row, validate_availability_row,
                         validate_stub_row, validate_unmapped_row)

STAGE = "emit-stub-datasets"


def run_stage5(tree: Path, extracted_root: Path, *extra):
    from conftest import run_pack, tree_game
    return run_pack([tree_game(tree), "--only", STAGE, *extra],
                    extracted_root=extracted_root)


def load_outputs(ext: Path):
    stubs = ext / "stubs"
    files = sorted(p.name for p in stubs.glob("*.jsonl")) if stubs.exists() else []
    rows_by_file = {}
    for name in files:
        rows_by_file[name] = read_jsonl(stubs / name)
    return stubs, files, rows_by_file


# --- the full hostless acceptance ---------------------------------------------------

@pytest.fixture(scope="module")
def stage5_run(fx_stage5, tmp_path_factory):
    from conftest import seeded_extracted_root
    ext = seeded_extracted_root(fx_stage5, tmp_path_factory.mktemp("s5run"))
    r = run_stage5(fx_stage5, ext)
    return r, ext


def test_stage5_runs_hostless(stage5_run):
    r, _ext = stage5_run
    assert r.returncode == 0, (
        f"stage 5 is pure-JSON and MUST complete hostless; rc={r.returncode}\n"
        f"STDOUT:{r.stdout}\nSTDERR:{r.stderr}")


def test_kind_filename_map_and_schema(stage5_run):
    r, ext = stage5_run
    if r.returncode != 0:
        pytest.skip("stage 5 did not complete — schema legs vacuous")
    stubs, files, rows_by_file = load_outputs(ext)
    assert files, "no stub files emitted"
    allowed = set(KIND_TO_FILE.values()) | {"_absences.jsonl", "_unmapped-families.jsonl"}
    unexpected = [f for f in files if f not in allowed]
    assert not unexpected, f"filenames outside the pinned kind↔file map: {unexpected}"
    for name, rows in rows_by_file.items():
        for i, row in enumerate(rows):
            if name.startswith("_"):
                continue
            errs = validate_stub_row(row, where=f"{name}:{i + 1}: ")
            assert not errs, f"stub row contract violations: {errs}"
            # kind VALUE ↔ FILENAME bijection
            assert KIND_TO_FILE.get(row["kind"]) == name, (
                f"row kind {row['kind']!r} landed in {name!r}; pinned map says "
                f"{KIND_TO_FILE.get(row['kind'])!r}")


def test_buildid_on_100_percent_of_rows(stage5_run):
    r, ext = stage5_run
    if r.returncode != 0:
        pytest.skip("stage 5 did not complete")
    _stubs, _files, rows_by_file = load_outputs(ext)
    checked = 0
    for name, rows in rows_by_file.items():
        for i, row in enumerate(rows):
            if name == "_unmapped-families.jsonl":
                continue
            assert row.get("buildId") == BUILD_ID, (
                f"{name}:{i + 1} buildId {row.get('buildId')!r} != identity buildId")
            checked += 1
    assert checked > 0


def test_nonempty_xor_absence_ledger(stage5_run):
    r, ext = stage5_run
    if r.returncode != 0:
        pytest.skip("stage 5 did not complete")
    _stubs, files, rows_by_file = load_outputs(ext)
    kinds_present = {}
    for name, rows in rows_by_file.items():
        for row in rows:
            k = row.get("kind")
            if k in KIND_TO_FILE:
                kinds_present.setdefault(k, 0)
                kinds_present[k] += 1

    # every fixture-backed kind must be non-empty
    fixture_kinds = {"item", "room", "course", "config", "metagame-node",
                     "student-type", "unlockable", "campus-level"}
    for kind in sorted(fixture_kinds):
        fname = KIND_TO_FILE[kind]
        assert fname in rows_by_file and rows_by_file[fname], (
            f"seeded family {kind!r} has neither non-empty {fname} nor an absence row")

    # staff has ZERO fixture dumps -> ledgered absence naming scan scope
    absences = rows_by_file.get("_absences.jsonl", [])
    staff_abs = [a for a in absences if a.get("kind") == "staff"]
    assert len(staff_abs) == 1, (
        f"staff family scanned with no matches must produce exactly one "
        f"_absences.jsonl row; got {len(staff_abs)}")
    errs = validate_absence_row(staff_abs[0], where="_absences[staff]: ")
    assert not errs, f"absence-row contract violations: {errs}"
    assert staff_abs[0]["evidence"], "absence row needs evidence text"
    # XOR discipline: no staff stub file with rows while an absence row exists
    staff_rows = rows_by_file.get("staff.jsonl", [])
    assert not staff_rows, "staff.jsonl non-empty AND absent-ledgered — XOR broken"
    # symmetric: WidgetConfig harvested but unmapped -> ledgered, never silent
    unmapped = rows_by_file.get("_unmapped-families.jsonl", [])
    widget_rows = [u for u in unmapped if u.get("class") == UNMAPPED[0][0]]
    assert len(widget_rows) >= 1, (
        f"class {UNMAPPED[0][0]} has no seeded kind and no _unmapped-families row")
    errs = validate_unmapped_row(widget_rows[0], where="_unmapped-families: ")
    assert not errs, f"unmapped-row contract violations: {errs}"


def test_impl_kind_map_matches_pinned_table():
    """When the impl exposes its kind↔filename map, it must equal the pinned
    9-entry table character-for-character."""
    mod = load_tool("stage5_emit_stubs.py")
    if mod is None:
        pytest.skip("impl-missing: tools/stage5_emit_stubs.py")
    scopes = [mod] + ([getattr(mod, "tc")] if hasattr(mod, "tc") else [])
    table = None
    for scope in scopes:
        for name in KIND_MAP_NAMES:
            attr = getattr(scope, name, None)
            if isinstance(attr, dict) and attr:
                table = attr
                break
        if table:
            break
    if table is None:
        pytest.skip(f"impl-missing: no kind↔file map constant (tried {KIND_MAP_NAMES})")
    assert {str(k): str(v) for k, v in table.items()} == KIND_TO_FILE


def test_impl_stub_row_validator_agrees_with_contract():
    """Validator conventions: no-exception (or truthy) == valid; raise/falsy
    == rejected."""
    mod = load_tool("stage5_emit_stubs.py")
    if mod is None:
        pytest.skip("impl-missing: tools/stage5_emit_stubs.py")
    fn = get_sym(mod, *STUB_VALIDATE_NAMES)
    if fn is None:
        pytest.skip(f"impl-missing: stub-row validator (tried {STUB_VALIDATE_NAMES})")

    def accepts(row):
        try:
            out = fn(dict(row))
        except Exception:
            return False
        return bool(out) if out is not None else True

    good = {"id": "item_alpha", "kind": "item", "slug": None,
            "fields": {"nameLoc": "item_alpha_name"},
            "source": {"bundle": "items-general_assets_all.bundle",
                       "pathId": 101, "class": "ItemConfig"},
            "provisional": True, "inferred": False,
            "method": "verbatim-copy", "buildId": BUILD_ID}
    assert accepts(good), "validator rejected a contract-perfect row"
    for mutate, why in (
        (("kind",), "missing kind"),
        (("source",), "missing source block"),
        (("provisional",), "missing provisional flag"),
    ):
        bad = {k: v for k, v in good.items() if k not in mutate}
        assert not accepts(bad), f"validator accepted a row with {why}"


def test_identifier_sample_policy_matches_pinned_shape():
    """≤1,000 ids -> all; else a deterministic sorted sample of 500."""
    from _impl import SAMPLE_NAMES
    from _validators import identifier_sample_ids
    mod = load_tool("stage5_emit_stubs.py")
    if mod is None:
        pytest.skip("impl-missing: tools/stage5_emit_stubs.py")
    fn = get_sym(mod, *SAMPLE_NAMES)
    if fn is None:
        pytest.skip(f"impl-missing: identifier sampler (tried {SAMPLE_NAMES})")
    small = [f"x{i:03d}" for i in range(400)]
    got_small = sorted(fn(list(small)))
    assert got_small == small, "≤1,000 rows must be checked in full"
    big = [f"y{i:04d}" for i in range(1200)]
    got_big = fn(list(big))
    assert len(got_big) == 500, f"sample policy must pick 500 of 1,200; got {len(got_big)}"
    assert set(got_big) <= set(big) and list(got_big) == sorted(got_big), \
        "sample must be sorted subset of the family ids"
    # determinism: identical inputs -> identical samples
    assert fn(list(big)) == got_big


def test_join_procedure_direct_hard_convention_prose(fx_stage5):
    """The PINNED join procedure driven directly on fixture data: exact
    matrix-key equality -> hard; <entityId>_<role> convention -> inferred +
    method; prose -> no join at all."""
    mod = load_tool("stage5_emit_stubs.py")
    if mod is None:
        pytest.skip("impl-missing: tools/stage5_emit_stubs.py")
    fn = get_sym(mod, *JOIN_NAMES)
    if fn is None:
        pytest.skip(f"impl-missing: availability/join builder (tried {JOIN_NAMES})")
    monos = fx_stage5 / "extracted" / "harvest" / "monobehaviours"
    import _validators as V
    matrix_obj = V.read_json(fx_stage5 / "extracted" / "locales" / "locale-matrix.json")
    matrix_keys = V.locate_matrix_keys(matrix_obj)
    rows_by_kind = {
        "item": [
            {"id": "item_alpha", "kind": "item",
             "source": {"bundle": "items-general_assets_all.bundle",
                        "pathId": 101, "class": "ItemConfig"}},
            {"id": "item_beta", "kind": "item",
             "source": {"bundle": "items-general_assets_all.bundle",
                        "pathId": 102, "class": "ItemConfig"}},
            {"id": "item_gamma", "kind": "item",
             "source": {"bundle": "items-general_assets_all.bundle",
                        "pathId": 103, "class": "ItemConfig"}},
        ],
        "room": [
            {"id": "room_main", "kind": "room",
             "source": {"bundle": "rooms_assets_all.bundle",
                        "pathId": 201, "class": "RoomConfig"}},
        ],
    }
    out_rows = fn(rows_by_kind, matrix_keys, monos, BUILD_ID)
    by_id = {r["id"]: r for r in out_rows}
    # exact-match joins are HARD
    for eid in ("item_alpha", "room_main"):
        assert eid in by_id, f"{eid} must join HARD via exact matrix-key equality"
        assert by_id[eid]["joinInferred"] is False
        errs = validate_availability_row(by_id[eid], where=f"{eid}: ")
        assert not errs, errs
        assert by_id[eid]["fieldPresence"], f"{eid}: fieldPresence must be populated"
    # convention-shaped joins carry inferred + method naming the convention
    conv = [r for r in out_rows if r.get("joinInferred") is True]
    assert conv, "no convention-shaped join produced — inferred branch dead"
    for r in conv:
        assert r["joinMethod"], "joinInferred=true requires joinMethod"
    # prose-only entity never joins (procedure step 4: no other path)
    assert "item_gamma" not in by_id


def test_availability_join_semantics(stage5_run):
    """Join procedure (pinned): exact matrix-key equality -> joinInferred:false;
    convention-shaped match -> true + method; no other path."""
    r, ext = stage5_run
    if r.returncode != 0:
        pytest.skip("stage 5 did not complete")
    avail_path = ext / "relinks" / "locale_availability.jsonl"
    assert avail_path.exists(), "stage 5 is sole owner and must emit locale_availability.jsonl"
    rows = read_jsonl(avail_path)
    by_id = {row["id"]: row for row in rows}

    for eid in HARD_JOIN_IDS:
        assert eid in by_id, (
            f"entity {eid!r} carries a field whose value EXACTLY equals a matrix key "
            "— it must join HARD (joinInferred:false)")
        row = by_id[eid]
        assert row["joinInferred"] is False, f"{eid}: exact match must be joinInferred=false"
        errs = validate_availability_row(row, where=f"availability[{eid}]: ")
        assert not errs, f"availability-row contract violations: {errs}"
        fp = row["fieldPresence"]
        assert isinstance(fp, dict) and fp, (
            f"{eid}: fieldPresence must be populated (locale -> joined fields)")
        for loc, fields in fp.items():
            assert loc in _LOCALES_SET(), f"{loc!r} is not one of the 13 locales"
            assert all(isinstance(f, str) for f in fields)

    # convention branch reachable: item_beta_title / node_research_labl are
    # <entityId>_<role> shapes whose entity id exists but exact key differs
    inferred_seen = [(eid, row) for eid, row in by_id.items()
                     if row.get("joinInferred") is True]
    assert inferred_seen, (
        "no convention-shaped join found — the inferred branch of the pinned join "
        "procedure never fired (item_beta/node_research fixtures target it)")
    for eid, row in inferred_seen:
        assert row["joinMethod"], f"{eid}: joinInferred=true requires joinMethod naming the convention"

    # prose-only entity must NOT appear (no other association path exists)
    assert "item_gamma" not in by_id, \
        "item_gamma's prose field must not join — step 4 of the procedure: no other path"

    # availableLocales ⊆ the 13 BCP-47 locales on every row
    valid = set(_LOCALES_SET())
    for row in rows:
        for field in ("availableLocales", "namedLocales"):
            v = row.get(field) or []
            unknown = [x for x in v if x not in valid]
            assert not unknown, f"{field} carries non-BCP-47 values {unknown}"


def _LOCALES_SET():
    from _validators import LOCALE_TABLE
    return set(LOCALE_TABLE.values())


def test_availability_regenerated_every_run(fx_stage5, tmp_path_factory):
    """Sole-owner regeneration: tamper/deletion is repaired to byte-identical."""
    from conftest import seeded_extracted_root
    ext1 = seeded_extracted_root(fx_stage5, tmp_path_factory.mktemp("reg1"))
    ext2 = seeded_extracted_root(fx_stage5, tmp_path_factory.mktemp("reg2"))
    r1 = run_stage5(fx_stage5, ext1)
    assert r1.returncode == 0, r1.stdout + r1.stderr
    good = (ext1 / "relinks" / "locale_availability.jsonl").read_bytes()

    # leg A: delete the file entirely, rerun -> regenerated
    avail2 = ext2 / "relinks" / "locale_availability.jsonl"
    r2 = run_stage5(fx_stage5, ext2)
    assert r2.returncode == 0, r2.stdout + r2.stderr
    assert avail2.read_bytes() == good, "clean rerun diverged from first run"

    avail2.unlink()
    r3 = run_stage5(fx_stage5, ext2)
    assert r3.returncode == 0, r3.stdout + r3.stderr
    assert avail2.exists(), "deleted locale_availability.jsonl was NOT regenerated on rerun"
    assert avail2.read_bytes() == good, "regenerated availability file is not byte-identical"

    # leg B: truncate it, rerun -> repaired
    avail2.write_bytes(b'{"broken": tru')
    r4 = run_stage5(fx_stage5, ext2)
    assert r4.returncode == 0, r4.stdout + r4.stderr
    assert avail2.read_bytes() == good, "truncated locale_availability.jsonl not repaired"


def test_identifier_preservation_sample_policy(stage5_run):
    r, ext = stage5_run
    if r.returncode != 0:
        pytest.skip("stage 5 did not complete")
    stubs, _files, rows_by_file = load_outputs(ext)
    source_ids = {f["id"] for _e, _c, _f, _s, _p, f in ENTITIES}
    source_ids |= {f"itembig_{i:04d}" for i in range(BIG_FAMILY_COUNT)}
    for cls, _family, _stem, pids in UNMAPPED:
        source_ids |= {f"widget_{pid}" for pid in pids}
    emitted = []
    big_rows = []
    for name, rows in rows_by_file.items():
        if name.startswith("_"):
            continue
        emitted.extend(rows)
        if any(r["kind"] == "item" and str(r["id"]).startswith("itembig_") for r in rows):
            big_rows.extend(r for r in rows if str(r["id"]).startswith("itembig_"))
    n_checked, n_total = check_identifier_verbatim(source_ids, emitted, where="stubs")
    if n_total > 1000:
        assert n_checked == 500, f"sample policy must check 500 of {n_total}, checked {n_checked}"
    else:
        assert n_checked == n_total
    # the >1000-row family exercised the sorted-500 sample policy directly
    assert len(identifier_sample_ids(list(range(1200)))) == 500
    assert len(big_rows) == BIG_FAMILY_COUNT, (
        f"big family truncated: {len(big_rows)} of {BIG_FAMILY_COUNT} rows")


def test_double_run_byte_identical_declared_outputs(fx_stage5, tmp_path_factory):
    from conftest import seeded_extracted_root
    ext1 = seeded_extracted_root(fx_stage5, tmp_path_factory.mktemp("dr1"))
    ext2 = seeded_extracted_root(fx_stage5, tmp_path_factory.mktemp("dr2"))
    r1 = run_stage5(fx_stage5, ext1)
    assert r1.returncode == 0, r1.stdout + r1.stderr
    r2 = run_stage5(fx_stage5, ext2, "--force")
    assert r2.returncode == 0, r2.stdout + r2.stderr
    m1 = hash_tree(ext1 / "stubs") | hash_tree(ext1 / "relinks")
    m2 = hash_tree(ext2 / "stubs") | hash_tree(ext2 / "relinks")
    only1, only2, changed = diff_manifests(m1, m2)
    assert not (only1 or only2 or changed), (
        f"rerun not byte-identical: only_run1={only1} only_run2={only2} changed={changed}")
