"""Stage 4 `localisation` obligations (spec §8 stage-4 bullets + R2 enum)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from _impl import (MATRIX_BUILDER_NAMES, POLICY_CLASSIFIER_NAMES, get_sym,
                   load_tool, skip_if_none)
from _validators import (BASE_OVERLAY_NAME, COMPOSITION_POLICIES, LOCALE_TABLE,
                         assert_jsonl_roundtrip, locale_file_set_matches,
                         locate_matrix_keys, validate_base_overlay_report)

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
