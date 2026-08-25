"""Stage 4 `localisation` obligations (spec §8 stage-4 bullets + R2 enum)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from _impl import (MATRIX_BUILDER_NAMES, POLICY_CLASSIFIER_NAMES, get_sym,
                   load_tool, skip_if_none)
from _validators import (BASE_OVERLAY_NAME, COMPOSITION_POLICIES, LOCALE_TABLE,
                         UNITY_VERSION, assert_jsonl_roundtrip,
                         locale_file_set_matches, locate_matrix_keys,
                         validate_base_overlay_report)

sys.path.insert(0, str(Path(__file__).parent))
import _fixturelib as fx  # noqa: E402


def test_jsonl_roundtrip_unicode_and_newline_discipline(tmp_path):
    rows = [
        {"id": "ui_common_cancel", "text": "Abbrechen"},
        {"id": "campus.motto", "text": "キャンパスのモットー"},
        {"id": "accent", "text": "déjà vu — über ção"},
    ]
    assert_jsonl_roundtrip(tmp_path, rows)


def _tables_from_fixture():
    """Fixture tables: 13 locales + the unnamed base overlay."""
    tables = {}
    for loc in LOCALE_TABLE.values():
        tables[loc] = [
            {"id": k, "text": f"{k} [{loc}]"}
            for k, (locs, in_base) in sorted(fx.MATRIX.items())
            if not in_base and loc in locs
        ]
    base = [{"id": k, "text": f"{k} [base]"}
            for k, (_l, in_base) in sorted(fx.MATRIX.items()) if in_base]
    return tables, base


def test_matrix_builder_includes_base_keys(tmp_path):
    mod = skip_if_none(load_tool("stage4_localisation.py"),
                       "tools/stage4_localisation.py")
    fn = skip_if_none(get_sym(mod, *MATRIX_BUILDER_NAMES), "locale-matrix builder")
    tables, base = _tables_from_fixture()
    try:
        out = fn(tables, base)
    except TypeError:
        tables_with_base = dict(tables)
        tables_with_base[BASE_OVERLAY_NAME] = base
        out = fn(tables_with_base)
    keys_map = locate_matrix_keys(out)
    assert keys_map is not None, f"matrix builder returned unusable shape: {str(out)[:200]}"
    all_keys = set(keys_map)
    expected_union = set(fx.MATRIX)
    missing = expected_union - all_keys
    extra = all_keys - expected_union
    assert not missing, f"matrix misses keys observed in inputs: {sorted(missing)}"
    assert not extra, f"matrix invented keys: {sorted(extra)}"
    # base keys present (the matrix INCLUDES base keys — spec §3 stage 4)
    assert {"ui_common_cancel", "ui_common_ok"} <= all_keys
    # presence across locales must be recoverable somewhere in the structure
    assert "en" in str(out), "locale presence info absent from matrix"


def test_composition_policy_classifier_all_four_branches(tmp_path):
    """All FOUR compositionPolicy values must be reachable on fixtures
    (spec §8 stage 4; R2 replaced prose merge-policy with this enum).
    Label semantics are deliberately NOT pinned here (spec §7: the policy is
    "selected by this stage's deterministic classifier … not pre-pinned");
    what is binding: enum membership, repeat-call determinism, sensitivity to
    genuinely different compositions, and reachability of the whole enum."""
    mod = skip_if_none(load_tool("stage4_localisation.py"),
                       "tools/stage4_localisation.py")
    fn = skip_if_none(get_sym(mod, *POLICY_CLASSIFIER_NAMES),
                      "compositionPolicy classifier")

    def policy(base_rows, en_rows):
        """Returns the emitted policy string for id->text row dicts."""
        try:
            out = fn(dict(base_rows), dict(en_rows))
        except TypeError:
            out = fn(base_rows=dict(base_rows), english_rows=dict(en_rows))
        pol = out.get("compositionPolicy") if isinstance(out, dict) else out
        assert pol in COMPOSITION_POLICIES, \
            f"classifier returned {pol!r}, not one of the pinned four values"
        return pol

    # deterministic classification: identical inputs -> identical label
    shapes = [
        ({"a": "A"}, {"a": "A", "c": "C"}),
        ({"a": "A*", "b": "B*"}, {"a": "A*"}),
        ({"a": "BASETEXT", "d": "D"}, {"a": "ENTEXT"}),
        ({}, {}),
    ]
    for base, en in shapes:
        assert policy(base, en) == policy(base, en), (
            f"classifier is not repeat-call deterministic for "
            f"base={base} en={en}")

    # exhaustive small-shape sweep: every combination must classify into the
    # enum without crashing (robustness leg), collecting what actually occurs.
    # Genuinely distinguishable compositions must NOT collapse onto one label.
    import itertools
    texts = [{}, {"a": "A1"}, {"a": "A2"}, {"a": "A1", "b": "B"}]
    seen = set()
    for base, en in itertools.product(texts, texts):
        seen.add(policy(base, en))
    assert len(seen) >= 2, (
        f"classifier returned the constant label {seen} across "
        f"{len(texts) ** 2} distinguishable input compositions — it does "
        "not classify anything, so consumers cannot observe composition")
    missing = set(COMPOSITION_POLICIES) - seen
    assert not missing, (
        f"compositionPolicy branches UNREACHABLE on any fixture shape: "
        f"{sorted(missing)} (observed {sorted(seen)}). Spec §8 requires all "
        f"four enum branches to be selectable by the deterministic classifier "
        f"— an unreachable value is dead code and consumers can never observe it.")


def test_bcp47_file_set_equality_helper(tmp_path):
    d = tmp_path / "locales"
    d.mkdir()
    for loc in LOCALE_TABLE.values():
        (d / f"{loc}.jsonl").write_text('{"id":"x","text":"y"}\n', encoding="utf-8")
    ok, missing, extra = locale_file_set_matches(d)
    assert ok, f"exact 13-set reported mismatch: missing={missing} extra={extra}"
    # removing one breaks it loudly with the precise name
    (d / "pt-BR.jsonl").unlink()
    ok, missing, extra = locale_file_set_matches(d)
    assert not ok and missing == ["pt-BR.jsonl"]
    # a 14th invented locale file is an EXTRA, never silently accepted
    (d / "xx-YY.jsonl").write_text("{}\n", encoding="utf-8")
    ok, missing, extra = locale_file_set_matches(d)
    assert not ok and extra == ["xx-YY.jsonl"] and missing == ["pt-BR.jsonl"]
    # base-overlay.jsonl never counts toward the 13
    (d / "xx-YY.jsonl").unlink()
    (d / "pt-BR.jsonl").write_text('{"id":"x","text":"y"}\n', encoding="utf-8")
    (d / f"{BASE_OVERLAY_NAME}.jsonl").write_text('{"id":"b","text":"B"}\n', encoding="utf-8")
    ok, missing, extra = locale_file_set_matches(d)
    assert ok, "base-overlay.jsonl must not disturb the 13-file equality"


def test_stage4_isolation_leaves_relinks_untouched(fx_stage4, tmp_path):
    """Sole-owner rule (R3): an `--only localisation` run NEVER writes under
    extracted/relinks/ — stage 5 owns that path. Holds even when the stage
    itself cannot complete hostless."""
    from conftest import run_pack, seeded_extracted_root, tree_game
    ext = seeded_extracted_root(fx_stage4, tmp_path, "s4iso")
    relinks = ext / "relinks"
    r = run_pack([tree_game(fx_stage4), "--only", "localisation"], extracted_root=ext)
    assert not relinks.exists(), (
        f"--only localisation created {relinks} — violates the stage-5 sole-owner rule "
        f"(rc was {r.returncode})")
    if r.returncode == 0:
        # completed hostless: hold the full acceptance too
        locales = ext / "locales"
        ok, missing, extra = locale_file_set_matches(locales)
        assert ok, f"emitted locale set != 13-entry BCP-47 table: missing={missing} extra={extra}"
        assert (locales / f"{BASE_OVERLAY_NAME}.jsonl").exists(), \
            "base-overlay.jsonl (persisted raw substrate) missing"
        report = __import__("json").loads(
            (locales / "base-overlay-report.json").read_text(encoding="utf-8"))
        errs = validate_base_overlay_report(report)
        assert not errs, f"base-overlay-report contract violations: {errs}"


# --- Revision 4: locale bundles share the stage-3 fallback-version seeding -----------

SEED_SCRIPTS_S4 = ("stage4_localisation.py", "unitypy_util.py", "tpc_common.py")


def _seed_helper_s4():
    from _impl import FALLBACK_SEED_NAMES, note_missing_symbol
    for script in SEED_SCRIPTS_S4:
        mod = load_tool(script)
        if mod is None:
            continue
        fn = get_sym(mod, *FALLBACK_SEED_NAMES)
        if fn is not None:
            return fn
    note_missing_symbol(
        f"fallback-version seeder via stage 4 (tried {FALLBACK_SEED_NAMES} "
        f"across {', '.join(SEED_SCRIPTS_S4)})")
    pytest.skip("impl-missing: shared fallback-version seeding helper not "
                "resolvable from stage 4 yet (CodeWriter pending)")


def _invoke_seed_s4(fn, bundle, extracted_root):
    from _impl import try_call_shapes
    return try_call_shapes(
        fn,
        ((bundle,), {}),
        ((bundle, extracted_root), {}),
        ((str(bundle)), {}),
        ((bundle.read_bytes(),), {}),
        ((), {"path": bundle, "extracted_root": extracted_root}),
        ((), {"bundle_path": bundle, "fallback_version": UNITY_VERSION}),
    )


def test_locale_bundles_share_fallback_version_seeding(tmp_path):
    """Revision 4 §8 stage 4: locale bundles are content bundles (their UnityFS
    headers read `0.0.0` too) and exercise the SAME identity-sourced seeding
    helper as stage 3; the usage count lands in this stage's run section."""
    fn = _seed_helper_s4()
    bundles = fx.write_seed_probe_bundles(tmp_path / "locale-bundles")
    out = _invoke_seed_s4(fn, bundles["zero"], tmp_path)
    cfg = getattr(__import__("UnityPy"), "config", None)
    assert getattr(cfg, "FALLBACK_UNITY_VERSION", None) == UNITY_VERSION, (
        f"a locale bundle with a `0.0.0` header must seed the fallback from "
        f"identity.json's unityVersion ({UNITY_VERSION!r})")

    def used(o):
        if isinstance(o, bool):
            return o
        if isinstance(o, tuple) and o:
            return bool(o[0])
        if isinstance(o, dict):
            return next((bool(o[k]) for k in
                         ("used", "fallbackUsed", "fallbackVersionUsed", "seeded")
                         if k in o), None)
        return None

    flag = used(out)
    assert flag is not False, (
        f"the seeded locale-bundle open must count as fallback usage; got {out!r}")


# --- TestFixer-006: I2 Localization decode lane (testreviewer-003 G4) ---------------
# Neither LanguageSource nor the [i2t] category grammar was executed by any
# hostless test: wrong column index or a dropped alias yields swapped/empty
# zh tables with exit 0, and slugified terms break every downstream join with
# exit 0. These legs bind the pure decoders directly.

def _s4():
    mod = skip_if_none(load_tool("stage4_localisation.py"),
                       "tools/stage4_localisation.py")
    return mod


def _need(mod, name):
    fn = getattr(mod, name, None)
    if fn is None:
        pytest.skip(f"impl-missing: tools/stage4_localisation.py.{name}")
    return fn


def _ev(mod):
    return _need(mod, "_evidence")()


def test_i2_language_source_column_order_is_source_local():
    """Revision 5: text lookup is per-term `Languages[i]` indexed by THAT
    source's own mLanguages order — en sits at index 1 here, so an index-0
    (canonical-order) read picks the French cell: the off-by-one trap."""
    mod = _s4()
    dec = _need(mod, "decode_i2_language_source")
    langs = [dict(r) for r in fx.I2_REORDERED_LANGS]
    terms = [fx.i2_term("UI/Cancel_Button",
                        ["ANNULER", "CANCEL", "ABBRECHEN", "QUXIAO",
                         "CANCELAR-BR"], status=1)]
    ev = _ev(mod)
    rows: dict = {}
    ok = dec(fx.i2_language_source(langs, terms), ("en", "english"),
             rows, ev, None, None)
    assert ok is True, "an I2-shaped payload must be recognized"
    assert rows == {"UI/Cancel_Button": "CANCEL"}, (
        f"cell must come from Languages[mLanguages.index(en)] (index 1), "
        f"got {rows!r} — column order or index resolution regressed")
    # verbatim Term → id, never slugified/renamed (Principle one)
    assert "UI/Cancel_Button" in rows and "/" in next(iter(rows))
    assert ev["termsWalked"] == 1 and ev["rowsEmitted"] == 1
    assert ev["cellsSkippedEmpty"] == 0 and ev["cellsSkippedAbsent"] == 0


def test_i2_language_source_msource_wrapper_shape():
    """The asset wrapper shape (payload.mSource carrying the registry) reads
    identically to a bare source payload."""
    mod = _s4()
    dec = _need(mod, "decode_i2_language_source")
    langs = [fx.i2_lang("English", "en")]
    terms = [fx.i2_term("k_one", ["ONE"], status=1)]
    wrapped_rows: dict = {}
    ev = _ev(mod)
    assert dec(fx.i2_language_source(langs, terms, wrap_msource=True),
               ("en",), wrapped_rows, ev, None, None) is True
    assert wrapped_rows == {"k_one": "ONE"}
    # non-I2 payloads are refused (caller counts them elsewhere)
    ev2 = _ev(mod)
    assert dec({"someOther": "shape"}, ("en",), {}, ev2, None, None) is False
    assert dec({"mTerms": "not-a-list", "mLanguages": []}, ("en",), {},
               _ev(mod), None, None) is False


def test_i2_alias_matching_zh_pt_and_name_fallback():
    """Code-then-Name matching with the measured zh-CN/zh-TW/pt-BR aliases,
    case-insensitively — a dropped alias silently empties whole zh tables."""
    mod = _s4()
    dec = _need(mod, "decode_i2_language_source")
    wanted = _need(mod, "_wanted_codes_for")
    match_idx = _need(mod, "_match_language_index")

    assert "zh-cn" in {w.casefold() for w in wanted("zh-Hans")}
    assert "zh-tw" in {w.casefold() for w in wanted("zh-Hant")}
    assert "brazilian portuguese" in {w.casefold() for w in wanted("pt-BR")}

    langs = [
        fx.i2_lang("French", "fr"),
        fx.i2_lang("Chinese Traditional", "zh-TW"),
        fx.i2_lang("Chinese Simplified", "zh-CN"),
        fx.i2_lang("Brazilian Portuguese", ""),   # Code empty → Name leg only
    ]
    cells = ["MAGIE_FR", "FANTOME_TW", "MOFA_HANS", "MAGIA_BR"]
    term = fx.i2_term("Course/Magic_Name", cells, status=1)

    rows_zh: dict = {}
    dec(fx.i2_language_source(langs, [term]), wanted("zh-Hans"),
        rows_zh, _ev(mod), None, None)
    assert rows_zh == {"Course/Magic_Name": "MOFA_HANS"}, (
        f"zh-CN Code alias must hit its own column: got {rows_zh!r}")

    rows_br: dict = {}
    dec(fx.i2_language_source(langs, [term]), wanted("pt-BR"),
        rows_br, _ev(mod), None, None)
    assert rows_br == {"Course/Magic_Name": "MAGIA_BR"}, (
        f"pt-BR must resolve via the Name fallback when Code is empty: "
        f"got {rows_br!r}")

    # pivot matched by NAME when the code spelling differs ("EN-US")
    langs_pivot = [fx.i2_lang("English", "EN-US")]
    idx = match_idx(langs_pivot, ("en", "english"))
    assert idx == 0, f"pivot Name fallback dead: idx={idx!r}"
    # nothing matches → None (callers count cellsSkippedAbsent)
    assert match_idx([fx.i2_lang("Klingon", "tlh")], ("en",)) is None


def test_i2_skip_and_count_empty_absent_cells_and_registry_keep():
    """Empty/whitespace/absent cells are SKIPPED in locale tables and COUNTED;
    the master-registry caller (keep_empty_rows) persists "" rows instead —
    the registry-vs-table divergence, never invented text."""
    mod = _s4()
    dec = _need(mod, "decode_i2_language_source")
    langs = [fx.i2_lang("English", "en")]
    terms = [
        fx.i2_term("k_present", ["VISIBLE"], status=1),
        fx.i2_term("k_empty", [""], status=1),
        fx.i2_term("k_whitespace", ["   "], status=1),
        fx.i2_term("k_absent", [], status=1),      # no cell at matched index
        fx.i2_term(42, ["x"], status=1),           # malformed: non-str Term
        fx.i2_term("", ["y"], status=1),           # malformed: empty Term
    ]
    # locale-table mode: drop empty, keep counting
    ev = _ev(mod)
    rows: dict = {}
    dec(fx.i2_language_source(langs, terms), ("en",), rows, ev, None, None)
    assert rows == {"k_present": "VISIBLE"}, (
        f"untranslated cells must never invent rows: {rows!r}")
    assert ev["cellsSkippedEmpty"] == 2   # "" + whitespace-only
    assert ev["cellsSkippedAbsent"] == 1  # [] at matched index
    assert ev["malformedEntries"] == 2
    assert ev["termsWalked"] == 4         # malformed terms never walked
    assert ev["rowsEmitted"] == 1

    # master-registry mode: matched-but-empty cells persist verbatim as ""
    ev_reg = _ev(mod)
    rows_reg: dict = {}
    dec(fx.i2_language_source(langs, terms), ("en",), rows_reg, ev_reg,
        None, None, drop_empty_cells=False)
    assert rows_reg.get("k_empty") == "" and rows_reg.get("k_whitespace") == ""
    assert rows_reg.get("k_present") == "VISIBLE"
    assert "k_absent" not in rows_reg or rows_reg.get("k_absent") == ""
    assert ev_reg["cellsSkippedEmpty"] == 2, (
        "kept-empty rows stay COUNTED either way")
    assert set(rows) <= set(rows_reg), "registry table must ⊇ the locale table"

    # duplicate keys overwrite with a counted decision
    ev_dup = _ev(mod)
    rows_dup: dict = {}
    dup_terms = [fx.i2_term("k_dupe", ["FIRST"], status=1),
                 fx.i2_term("k_dupe", ["SECOND"], status=1)]
    dec(fx.i2_language_source(langs, dup_terms), ("en",), rows_dup, ev_dup,
        None, None)
    assert rows_dup == {"k_dupe": "SECOND"}
    assert ev_dup["duplicateKeysOverwritten"] == 1


def test_i2_term_status_histogram_and_per_locale_distribution():
    """TermStatus lands in the histogram AND per key; `_status_distribution`
    joins a locale's rows against the registry, `unregistered` for keys the
    registry never saw."""
    mod = _s4()
    dec = _need(mod, "decode_i2_language_source")
    dist_fn = _need(mod, "_status_distribution")
    langs = [fx.i2_lang("English", "en")]
    terms = [
        fx.i2_term("k_trans", ["T1"], status=1),    # FOR translation
        fx.i2_term("k_trans2", ["T2"], status=1),
        fx.i2_term("k_noftr", ["N1"], status=0),    # NOT for translation
        fx.i2_term("k_orphan", ["O1"], status=None),  # no status recorded
    ]
    hist: dict = {}
    by_key: dict = {}
    ev = _ev(mod)
    rows: dict = {}
    dec(fx.i2_language_source(langs, terms), ("en",), rows, ev,
        by_key, hist)
    assert hist == {1: 2, 0: 1}, f"histogram drifted: {hist!r}"
    assert by_key.get("k_trans") == 1 and by_key.get("k_noftr") == 0

    dist = dist_fn(rows, by_key)
    assert dist == {"forTranslation": 2, "notForTranslation": 1,
                    "unregistered": 1}, (
        f"per-locale distribution must join against the registry: {dist!r}")


def test_i2_category_textasset_grammar():
    """`I2LS_*` TextAssets: `[i2t]` splits entries, FIRST `=` splits term from
    text, malformed chunks count, empty values skip-and-count, ids stay
    verbatim — the pure grammar, previously untested."""
    mod = _s4()
    cat = _need(mod, "decode_i2_category_textasset")
    ev = _ev(mod)
    rows: dict = {}
    raw = (b"term_alpha=Alpha[i2t]"
           b"Course/Magic_Name=Mage = master[i2t]"
           b"[i2t]"
           b"empty_key=[i2t]"
           b"no_equals_chunk")
    assert cat("I2LS_Course", raw, rows, ev) is True
    assert rows == {"term_alpha": "Alpha", "Course/Magic_Name": "Mage = master"}, (
        f"first-= split + verbatim ids broken: {rows!r}")
    assert ev["categoriesDecoded"] == 1
    assert ev["rowsEmitted"] == 2
    assert ev["cellsSkippedEmpty"] == 1      # empty_key=
    assert ev["malformedEntries"] == 1       # chunk without any '='

    # case-insensitive prefix + UTF-8 BOM tolerance
    ev2 = _ev(mod)
    rows2: dict = {}
    assert cat("i2ls_ui", "﻿btn_ok=OK[i2t]btn_no=".encode("utf-8"),
               rows2, ev2) is True
    assert rows2 == {"btn_ok": "OK"}
    assert ev2["cellsSkippedEmpty"] == 1

    # a NON-I2 TextAsset is refused (caller counts ignoredTextAssets)
    ev3 = _ev(mod)
    assert cat("Tutorial_Tips", b"x=1", {}, ev3) is False
    assert ev3["categoriesDecoded"] == 0
    # an empty I2 payload is treated as I2 but decodes nothing
    ev4 = _ev(mod)
    assert cat("I2LS_Empty", b"", {}, ev4) is True
    assert ev4["categoriesDecoded"] == 0
