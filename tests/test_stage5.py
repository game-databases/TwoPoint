"""Stage 5 `emit-stub-datasets` obligations (spec §8 stage-5 bullets + R3/R8).

Stage 5 consumes only JSON artifacts (monobehaviour dumps, catalog.json,
structural/*, locale-matrix.json), so the FULL acceptance runs hostless on
the prepared tree: `run_all.py <tree> --only emit-stub-datasets`.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from _fixturelib import BIG_FAMILY_COUNT, ENTITIES, UNMAPPED
from _impl import (JOIN_NAMES, KIND_MAP_NAMES, STUB_VALIDATE_NAMES, get_sym,
                   load_tool)
from _validators import (BUILD_ID, KIND_TO_FILE, check_identifier_verbatim,
                         diff_manifests, hash_tree, identifier_sample_ids,
                         read_jsonl, validate_absence_row,
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


def test_retired_availability_builder_gone_from_stage5():
    """piece-07 §5 item 1 / arbiter R4 (supersedes piece-2 §R4): stage 5's
    availability emission was REFUTED and REMOVED — no availability/join
    builder symbol may survive on the stage-5 module (reintroduction would
    resurrect a dead writer for the canonical path stage locale-proof owns)."""
    mod = load_tool("stage5_emit_stubs.py")
    if mod is None:
        pytest.skip("impl-missing: tools/stage5_emit_stubs.py")
    scopes = [mod] + ([getattr(mod, "tc")] if hasattr(mod, "tc") else [])
    survivors = []
    for scope in scopes:
        for name in JOIN_NAMES:
            if hasattr(scope, name):
                survivors.append(f"{getattr(scope, '__name__', 'tc')}.{name}")
    assert not survivors, (
        "retired availability builder still resolvable on stage 5: "
        f"{survivors} — piece-07 §5 removal hasn't landed")


def test_availability_emission_retired_byte_untouched(fx_stage5,
                                                      tmp_path_factory):
    """piece-07 §5 / arbiter R4 handover (supersedes piece-1 Rev 2/R3 and
    piece-2 §R4 ownership pins): stage `locale-proof` is the SOLE writer of
    relinks/locale_availability.jsonl. An isolated `--only
    emit-stub-datasets` run must leave that path BYTE-UNTOUCHED — whatever
    it holds (v1 rows, v2 rows, anything) — while its other outputs keep
    behaving identically. The old 'regenerated on every run' demand is
    retired together with the emission itself."""
    from conftest import seeded_extracted_root

    ext = seeded_extracted_root(fx_stage5, tmp_path_factory.mktemp("retire"))
    r = run_stage5(fx_stage5, ext)
    assert r.returncode == 0, r.stdout + r.stderr
    avail_path = ext / "relinks" / "locale_availability.jsonl"
    before = avail_path.read_bytes() if avail_path.exists() else None
    r2 = run_stage5(fx_stage5, ext, "--force")
    assert r2.returncode == 0, r2.stdout + r2.stderr
    after = avail_path.read_bytes() if avail_path.exists() else None
    assert after == before, (
        "stage 5 still WRITES relinks/locale_availability.jsonl — the piece-07 "
        "§5 emission removal hasn't landed "
        f"(before={_short(before)} after={_short(after)})")


def _short(b):
    if b is None:
        return "(absent)"
    import hashlib
    return f"{len(b)}B#{hashlib.sha256(b).hexdigest()[:12]}"


def test_availability_refusal_guard_on_populated_target(fx_stage5,
                                                        tmp_path_factory):
    """Refusal guard, CALLER-SCOPED TO STAGE 5: a stage-5-originated write
    against a target holding populated non-v1/non-empty content exits 1
    NAMING the conflict and leaves the file byte-intact. Stage locale-proof's
    own v2 rewrites are NOT refused (caller scoping — see test_stage9's
    double-run legs)."""
    from conftest import seeded_extracted_root

    def _v2_rows():
        rows = []
        for kind, fname in sorted(KIND_TO_FILE.items()):
            rows.append({"kind": kind, "id": f"v2_probe_{kind}",
                         "availableLocales": ["en"], "partialLocales": [],
                         "namedLocales": [], "identityToPivotLocales": [],
                         "fieldPresence": {}, "buildId": BUILD_ID})
        return rows

    ext = seeded_extracted_root(fx_stage5, tmp_path_factory.mktemp("guard"))
    from _validators import write_jsonl
    seeded = write_jsonl(ext / "relinks" / "locale_availability.jsonl",
                         _v2_rows())
    payload = seeded.read_bytes()
    r = run_stage5(fx_stage5, ext, "--force")
    assert r.returncode == 1, (
        f"a stage-5-originated write against a populated v2 availability "
        f"file must refuse exit 1 naming the conflict, got rc={r.returncode}\n"
        f"{r.stdout[-700:]}{r.stderr[-700:]}")
    combined = (r.stdout + r.stderr).lower()
    assert "conflict" in combined or "refus" in combined or \
        "availability" in combined, combined[-500:]
    assert (ext / "relinks" / "locale_availability.jsonl").read_bytes() == \
        payload, "refused run truncated or rewrote the populated file"


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


# --- TestFixer-006: Revision 5+6 lane (testreviewer-003 G1/G2/G6/G7) ---------------
# The shared trees above hold only positive singleton path_ids, wrapped dumps,
# and unique ids — the entire Rev 6 identity policy was deletable with this
# suite green. The corpora below materialize every policy shape synthetically.

import re as _re  # noqa: E402

from _fixturelib import (  # noqa: E402
    IDENTITY_AXES, IDENTITY_DUPE_ID, LARGE_NEG_PID, THEME_ID,
    build_flat_shape_corpus, build_identity_policy_corpus,
    build_starved_corpus,
)


def _copy_corpus(src: Path, base: Path, name: str) -> Path:
    import shutil
    dst = Path(base) / name
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    return dst


@pytest.fixture(scope="module")
def identity_corpus(tmp_path_factory):
    out = tmp_path_factory.mktemp("idpcorpus")
    return build_identity_policy_corpus(out)


@pytest.fixture(scope="module")
def identity_run(identity_corpus, fx_stage5, tmp_path_factory):
    """One hostless stage-5 run over a fresh copy of the identity corpus."""
    ext = _copy_corpus(identity_corpus, tmp_path_factory.mktemp("idprun"), "ext")
    return run_stage5(fx_stage5, ext), ext


def test_identity_policy_run_completes_hostless(identity_run):
    r, _ext = identity_run
    assert r.returncode == 0, (
        f"stage 5 must complete hostless on the Rev-6 identity corpus; "
        f"rc={r.returncode}\nSTDOUT:{r.stdout}\nSTDERR:{r.stderr}")


def _last_section(ext: Path, stage_id: str = STAGE) -> str:
    log_text = (ext / "EXTRACTION-LOG.md").read_text(encoding="utf-8",
                                                     errors="replace")
    sections = [p for p in _re.split(r"(?m)^#{1,3} ", log_text)
                if p.splitlines()[:1] and stage_id in p.splitlines()[0].lower()]
    assert sections, f"no {stage_id} run section in EXTRACTION-LOG.md"
    return sections[-1]


def _count(section: str, token: str) -> int:
    m = _re.search(_re.escape(token) + r"\s*=?\s*(\d+)", section)
    assert m, f"counter {token!r} missing from run section:\n{section[-600:]}"
    return int(m.group(1))


def test_identity_policy_counters_counted_in_run_section(identity_run):
    """Rev 6: 'applied before any row is emitted; every rule's decisions are
    counted in the run section' — the four counters plus the byte-match and
    signed-stem contract lines must reflect THIS corpus exactly."""
    r, ext = identity_run
    if r.returncode != 0:
        pytest.skip("identity-policy run failed — counter legs vacuous")
    section = _last_section(ext)
    assert _count(section, "componentExcluded") == 3, section
    assert _count(section, "identifierLess") == 3, section
    assert _count(section, "mergedDuplicates") == 2, section
    assert _count(section, "disambiguatedDuplicates") == 1, section
    # signed-stem contract over the export-manifest universe (incl. negatives)
    assert _count(section, "unparsed=") == 0, section
    assert _count(section, "mismatched=") == 0, section
    # byte-match gate ran against real dump shapes and validated something
    checked = _count(section, "checked=")
    assert checked >= 6, f"byte-match checked={checked}, corpus holds ≥6 rows"
    assert _count(section, "mismatches=") == 0, section


def test_component_exclusion_never_emits_entities(identity_run):
    """Rev 6 rule 1: engine/primitive/component/generic dumps are census rows,
    never entity rows — and land in the unmapped ledger with evidence."""
    r, ext = identity_run
    if r.returncode != 0:
        pytest.skip("identity-policy run failed")
    _stubs, _files, rows_by_file = load_outputs(ext)
    banned = {"UnityEngine.Transform", "TPC.Components.RoomSensor",
              "MonoBehaviour"}
    for name, rows in rows_by_file.items():
        for row in rows:
            src_cls = (row.get("source") or {}).get("class")
            assert src_cls not in banned, (
                f"{name}: dump class {src_cls!r} became an entity row "
                f"(id={row.get('id')!r}) — component exclusion deleted?")
            assert not str(row.get("id", "")).startswith("UnityEngine."), \
                f"{name}: engine-spelled id emitted: {row['id']!r}"
    unmapped = rows_by_file.get("_unmapped-families.jsonl", [])
    by_class = {u.get("class"): u for u in unmapped}
    for cls in sorted(banned):
        assert cls in by_class, (
            f"excluded class {cls!r} missing from _unmapped-families.jsonl "
            "(exclusion must be ledgered, never silent)")
        assert by_class[cls].get("objectCount", 0) >= 1
        assert by_class[cls].get("evidence"), f"{cls}: exclusion evidence text required"


def test_empty_identifier_rows_ledgered_not_emitted(identity_run):
    """Rev 6 rule 2: id='' shapes (absent / whitespace / bool-typed) land in
    _absences.jsonl counted + sampled — never as stub rows."""
    r, ext = identity_run
    if r.returncode != 0:
        pytest.skip("identity-policy run failed")
    _stubs, _files, rows_by_file = load_outputs(ext)
    absences = [a for a in rows_by_file.get("_absences.jsonl", [])
                if a.get("absenceType") == "no-identifier"]
    by_kind = {a["kind"]: a for a in absences}
    assert by_kind.get("room", {}).get("count") == 1, (
        f"room id-less sweep count wrong: {by_kind.get('room')}")
    assert by_kind.get("item", {}).get("count") == 2, (
        f"item id-less sweep counts (whitespace + bool) wrong: {by_kind.get('item')}")
    for kind, agg in by_kind.items():
        errs = validate_absence_row(agg, where=f"_absences[{kind}]: ")
        assert not errs, errs
        assert agg["scannedBundles"] and agg["scannedClasses"]
        samples = agg.get("samples") or []
        assert len(samples) == agg["count"], (
            f"{kind}: samples must cover every id-less candidate at this scale")
        for s in samples:
            for k in ("bundle", "pathId", "class"):
                assert k in s, f"{kind} sample missing {k!r}: {s}"
    assert any(s["pathId"] == 220 for s in by_kind["room"]["samples"])
    # nothing identifier-less leaked into any emitted stub file
    for name, rows in rows_by_file.items():
        for row in rows:
            if name.startswith("_") or "id" not in row:
                continue
            assert isinstance(row["id"], str) and row["id"].strip(), (
                f"{name}: whitespace/empty identifier emitted: {row['id']!r}")


def test_equal_payload_duplicates_merge_one_row_with_axes(identity_run):
    """Rev 6 rule 3a: identical-id rows with EQUAL payload hashes across
    base+dlc-* bundles merge into ONE row whose axes[] names every
    contributing content axis (the Bloom ×N measured shape)."""
    from _validators import CONTENT_AXES, read_jsonl
    r, ext = identity_run
    if r.returncode != 0:
        pytest.skip("identity-policy run failed")
    rows = read_jsonl(ext / "stubs" / "configs.jsonl")
    blooms = [row for row in rows if row["fields"].get("id") == IDENTITY_DUPE_ID]
    assert len(blooms) == 1, (
        f"expected ONE merged {IDENTITY_DUPE_ID!r} row, got {len(blooms)} — "
        "the duplicate-policy block is dead again")
    row = blooms[0]
    assert sorted(row.get("axes") or []) == IDENTITY_AXES, (
        f"axes provenance list must span every contributing axis "
        f"({IDENTITY_AXES}), got {row.get('axes')!r}")
    assert set(row["axes"]) <= set(CONTENT_AXES), (
        f"axes vocabulary outside {CONTENT_AXES}: {row['axes']!r}")
    assert row["fields"]["tagline"] == "petal", "merge kept the wrong payload"
    assert row["source"]["bundle"] == "configs_assets_all.bundle"
    assert row["source"]["pathId"] == 801


def test_differing_payloads_disambiguate_preserving_verbatim_id(identity_run):
    """Rev 6 rule 3b: identical-id rows with DIFFERING payloads stay DISTINCT
    via `<id>@<contentHash8>`; the verbatim id survives inside fields.id."""
    r, ext = identity_run
    if r.returncode != 0:
        pytest.skip("identity-policy run failed")
    _stubs, _files, rows_by_file = load_outputs(ext)
    themes = [row for row in rows_by_file.get("rooms.jsonl", [])
              if str(row.get("fields", {}).get("id")) == THEME_ID
              or str(row.get("id")).split("@")[0] == THEME_ID]
    assert len(themes) == 2, (
        f"differing-payload pair collapsed to {len(themes)} rows — "
        "disambiguation deleted or over-merging")
    bare = [t for t in themes if "@" not in str(t["id"])]
    suffixed = [t for t in themes if "@" in str(t["id"])]
    assert len(bare) == 1 and len(suffixed) == 1, (
        f"exactly one bare + one @<hash8> row expected: {[t['id'] for t in themes]}")
    sfx = suffixed[0]
    import re as re2
    assert re2.fullmatch(rf"{THEME_ID}@[0-9a-f]{{8}}", sfx["id"]), (
        f"suffixed id {sfx['id']!r} is not <verbatim-id>@<8 lowercase hex>")
    assert sfx["fields"].get("id") == THEME_ID, (
        "disambiguated row lost the verbatim id inside fields (Principle one)")
    assert bare[0]["fields"].get("slots") != sfx["fields"].get("slots")
    assert {bare[0]["source"]["pathId"], sfx["source"]["pathId"]} == {230, 231}


def test_post_policy_uniqueness_and_axes_presence_rule(identity_run):
    """Rev 6 rule 4 + reviewer G7: uniqueness asserted post-policy per family;
    axes vocabulary ⊆ CONTENT_AXES and present iff multi-contributor."""
    from _validators import CONTENT_AXES
    r, ext = identity_run
    if r.returncode != 0:
        pytest.skip("identity-policy run failed")
    _stubs, files, rows_by_file = load_outputs(ext)
    axes_carriers = []
    for name in files:
        if name.startswith("_"):
            continue
        rows = rows_by_file[name]
        ids = [str(row["id"]) for row in rows]
        assert len(set(ids)) == len(ids), (
            f"post-policy uniqueness violated in {name}: duplicates "
            f"{sorted({i for i in ids if ids.count(i) > 1})}")
        for row in rows:
            if "axes" in row:
                axes_carriers.append((name, row))
                assert set(row["axes"]) <= set(CONTENT_AXES), (
                    f"{name}: axes vocabulary drift {row['axes']!r}")
                assert row["axes"] == sorted(row["axes"])
    # this corpus holds exactly one multi-contributor group (Bloom ×3 axes);
    # every other row is a singleton or a single-member subgroup -> no axes
    carriers = {(name, str(row["id"])) for name, row in axes_carriers}
    bloom_carriers = {(n, str(r_["id"])) for n, r_ in axes_carriers
                      if r_["fields"].get("id") == IDENTITY_DUPE_ID}
    assert carriers == bloom_carriers and bloom_carriers, (
        f"axes presence must track multi-contributor groups exactly; got "
        f"{sorted(carriers)}")


def test_parse_harvest_stem_accepts_signed_path_ids():
    """Reviewer G2: reverting the stem regex to `_(\\d+)$` turned 60,582 real
    rows into pathId=None — every signed spelling must parse."""
    mod = load_tool("stage5_emit_stubs.py")
    if mod is None:
        pytest.skip("impl-missing: tools/stage5_emit_stubs.py")
    parse = getattr(getattr(mod, "tc", mod), "parse_harvest_stem", None)
    if parse is None:
        pytest.skip("impl-missing: tc.parse_harvest_stem")
    int64_floor = -9223372036854775808
    cases = [
        ("dlc-ghost-art_assets_all_-1030583540197932202",
         ("dlc-ghost-art_assets_all", LARGE_NEG_PID)),
        ("dlc-ghost-art_assets_all_-1030583540197932202.json",
         ("dlc-ghost-art_assets_all", LARGE_NEG_PID)),
        ("rooms_assets_all_-700.json", ("rooms_assets_all", -700)),
        ("items-general_assets_all_-5000000000.txt",
         ("items-general_assets_all", -5000000000)),
        ("items-general_assets_all_101.json", ("items-general_assets_all", 101)),
        ("scenes_scenes_config_level_databases_123.json",
         ("scenes_scenes_config_level_databases", 123)),
        ("monoscripts_bundle_name_7", ("monoscripts_bundle_name", 7)),
        ("floor_case_-9223372036854775808", ("floor_case", int64_floor)),
        ("trailing_sign_-5", ("trailing_sign", -5)),
    ]
    for stem, expected in cases:
        assert parse(stem) == expected, (
            f"parse_harvest_stem({stem!r}) = {parse(stem)!r}, expected {expected!r} "
            "(signed-int64 stem contract, Rev 6 amendment 2)")
    for stem in ("ui_art", "item_alpha_name", "no_pid_here.x", "lead_-12x",
                 "minus_only_-"):
        got = parse(stem)
        assert got is None, f"parse_harvest_stem({stem!r}) must be None, got {got!r}"
    # the measured negative spelling must survive the ROUND TRIP through the
    # loader's restore step too (bundle stem + sign preserved, not truncated)
    base, pid = parse(f"dlc-ghost-art_assets_all_{LARGE_NEG_PID}.json")
    assert f"{base}_{pid}" == f"dlc-ghost-art_assets_all_{LARGE_NEG_PID}"


def test_negative_pathids_survive_manifest_and_emit(identity_run):
    """Round trip: export-manifest `{base, signed pid}` ↔ dump filename ↔
    emitted `source.pathId < 0` — the pre-R10 defect was silent None-ing."""
    r, ext = identity_run
    if r.returncode != 0:
        pytest.skip("identity-policy run failed")
    mod = load_tool("stage5_emit_stubs.py")
    if mod is None:
        pytest.skip("impl-missing: tools/stage5_emit_stubs.py")
    parse = getattr(getattr(mod, "tc", mod), "parse_harvest_stem", None)
    assert parse is not None, "impl-missing: tc.parse_harvest_stem"
    manifest = read_jsonl(ext / "harvest" / "export-manifest.jsonl")
    signed_rows = [m for m in manifest if isinstance(m["pathId"], int)
                   and m["pathId"] < 0]
    assert len(signed_rows) >= 3, (
        "fixture manifest must carry negative pathId rows (.json and .txt)")
    for mrow in manifest:
        parsed = parse(Path(mrow["outRelPath"]).name)
        want_base = Path(mrow["sourceBundle"]).stem
        assert parsed == (want_base, mrow["pathId"]), (
            f"manifest stem contract broken: {mrow['outRelPath']!r} parsed "
            f"{parsed!r}, want ({want_base!r}, {mrow['pathId']!r})")
    _stubs, _files, rows_by_file = load_outputs(ext)
    room_neg = [row for row in rows_by_file.get("rooms.jsonl", [])
                if row["fields"].get("id") == "room_signed_neg"]
    assert room_neg and room_neg[0]["source"]["pathId"] == LARGE_NEG_PID, (
        "negative source.pathId did not survive load→emit (unsigned-parser "
        "regression turns these into None)")
    item_neg = [row for row in rows_by_file.get("items.jsonl", [])
                if row["fields"].get("id") == "item_signed_neg"]
    assert item_neg and item_neg[0]["source"]["pathId"] == -5000000000


def test_flat_shape_dumps_emit_and_byte_match(fx_stage5, tmp_path_factory):
    """Reviewer G6: the REAL harvest shape is FLAT (no `fields` wrapper). A
    reader regression to wrapper-only would yield mass identifierLess and the
    checked=0 gate — this leg must fail loudly if that ever ships."""
    corpus = build_flat_shape_corpus(tmp_path_factory.mktemp("flatcorpus"))
    ext = _copy_corpus(corpus, tmp_path_factory.mktemp("flatrun"), "ext")
    r = run_stage5(fx_stage5, ext)
    assert r.returncode == 0, (
        f"flat-shape corpus must emit cleanly; rc={r.returncode}\n"
        f"STDOUT:{r.stdout}\nSTDERR:{r.stderr}")
    _stubs, _files, rows_by_file = load_outputs(ext)
    flat_items = [row for row in rows_by_file.get("items.jsonl", [])
                  if row["id"] == "item_flat_one"]
    flat_rooms = [row for row in rows_by_file.get("rooms.jsonl", [])
                  if row["id"] == "room_flat_two"]
    assert flat_items and flat_items[0]["source"]["pathId"] == 301, (
        "flat dump's m_Name identifier never became the emitted id")
    assert flat_rooms and flat_rooms[0]["source"]["pathId"] == 302
    section = _last_section(ext)
    assert _count(section, "checked=") >= 2, section
    assert _count(section, "mismatches=") == 0, (
        "flat-shape byte-match mismatched — dual-shape read broken")


def test_starved_corpus_fails_checked_zero_gate_loud(fx_stage5, tmp_path_factory):
    """Revision 6 amendment 3: a run that validates NOTHING (checked=0) fails
    its own gate instead of recording the zero — exit 1, named on stderr."""
    corpus = build_starved_corpus(tmp_path_factory.mktemp("starvedcorpus"))
    ext = _copy_corpus(corpus, tmp_path_factory.mktemp("starvedrun"), "ext")
    r = run_stage5(fx_stage5, ext)
    assert r.returncode == 1, (
        f"a checked=0 run MUST exit 1, got rc={r.returncode}\n"
        f"STDOUT:{r.stdout}\nSTDERR:{r.stderr}")
    combined = r.stdout + r.stderr
    assert "checked=0" in combined, (
        f"exit-1 output must name the identifierByteMatch checked=0 gate: "
        f"{combined[-400:]}")


def test_identity_rerun_byte_identical(identity_corpus, fx_stage5,
                                       tmp_path_factory):
    """Merge/disambiguation decisions are deterministic: same corpus twice →
    byte-identical stubs + relinks (suffix choice never depends on scan
    filesystem order)."""
    ext1 = _copy_corpus(identity_corpus, tmp_path_factory.mktemp("idir1"), "ext")
    ext2 = _copy_corpus(identity_corpus, tmp_path_factory.mktemp("idir2"), "ext")
    r1 = run_stage5(fx_stage5, ext1)
    assert r1.returncode == 0, r1.stdout + r1.stderr
    r2 = run_stage5(fx_stage5, ext2, "--force")
    assert r2.returncode == 0, r2.stdout + r2.stderr
    m1 = hash_tree(ext1 / "stubs") | hash_tree(ext1 / "relinks")
    m2 = hash_tree(ext2 / "stubs") | hash_tree(ext2 / "relinks")
    only1, only2, changed = diff_manifests(m1, m2)
    assert not (only1 or only2 or changed), (
        f"identity-policy rerun not byte-identical: only1={only1} "
        f"only2={only2} changed={changed}")
