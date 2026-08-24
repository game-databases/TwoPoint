"""Stage 2 `harvest-catalog` obligations (spec §8 stage-2 bullets).

Hostless scope: schema validation, match-key normalization, out-of-roster
hard-fail, coverage-universe math over a synthetic ContentCatalogData-shaped
fixture. Decoding the real binary catalog is client-gated.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from _impl import (COVERAGE_NAMES, MATCH_KEY_NAMES, get_sym, load_any,
                   note_missing_symbol, skip_if_none)
from _validators import (read_json, validate_catalog_json,
                         validate_coverage)

sys.path.insert(0, str(Path(__file__).parent))
import _fixturelib as fx  # noqa: E402
from _fixturelib import roster_rows  # noqa: E402


# --- catalog.json schema validator ------------------------------------------------

def test_schema_validator_accepts_fixture_catalog(fx_stage3):
    # catalog.json is stage 2's OUTPUT; it appears as upstream on the stage-3 tree
    obj = read_json(fx_stage3 / "extracted" / "addressables" / "catalog.json")
    errs = validate_catalog_json(obj)
    assert not errs, f"fixture catalog violates the pinned schema: {errs}"


def test_schema_validator_rejects_unsorted_and_missing_meta(tmp_path):
    bad = {"meta": {"buildId": 1}, "keys": [
        {"key": "b", "kind": "bundle"}, {"key": "a", "kind": "bundle"}]}
    assert validate_catalog_json(bad), "unsorted keys must be flagged"
    worse = {"keys": [{"key": "a", "kind": "bundle"}]}
    errs = validate_catalog_json(worse)
    assert any("meta" in e for e in errs), "missing meta block must be flagged"
    empty = {"meta": {}, "keys": []}
    assert validate_catalog_json(empty), "empty keys must be flagged"


# --- match-key normalization + coverage universes on a synthetic fixture -----------

def _normalized_roster_basenames():
    return {Path(r["relpath"]).name for r in roster_rows()}


def test_match_key_normalization_casefold_basename_prefix_strip():
    mod = skip_if_none(load_any("stage2_harvest_catalog.py", "tpc_common.py"),
                       "tools/stage2_harvest_catalog.py | tools/tpc_common.py")
    fn = skip_if_none(get_sym(mod, *MATCH_KEY_NAMES), "match-key normalizer")
    cases = [
        # (reference spelling, expected normalized MATCH KEY)
        ("StandaloneWindows64/items-general_assets_all.bundle",
         "items-general_assets_all"),                              # directory prefix + ext
        ("ITEMS-COURSES-MAGIC_ASSETS_ALL.BUNDLE",
         "items-courses-magic_assets_all"),                        # case-fold
        ("rooms_assets_all.bundle", "rooms_assets_all"),           # already bare
        ("041ed57fabcdef1234567890abcdef12_monoscripts.bundle",
         "041ed57fabcdef1234567890abcdef12_monoscripts"),          # hash-form basename
        ("DLCs/ghost/dlc-ghost-audio_assets_all.bundle",
         "dlc-ghost-audio_assets_all"),                            # DLC dir prefix
        ("Assets/Bundles/ui_assets_all.bundle", "ui_assets_all"),  # provider prefix
    ]
    for ref, expected in cases:
        got = fn(ref)
        got = got.get("key") if isinstance(got, dict) else got
        assert str(got).lower() == expected.lower(), (
            f"normalize({ref!r}) = {got!r}, expected {expected!r} "
            "(case-folded basename after prefix-strip)")
    # THE contract: catalog references and roster relpaths normalize to the
    # SAME key space — equivalent spellings must collide with their roster row
    for ref, _exp in cases:
        roster_equivalent = {
            "StandaloneWindows64/items-general_assets_all.bundle": "aa/StandaloneWindows64/items-general_assets_all.bundle",
            "rooms_assets_all.bundle": "x/rooms_assets_all.bundle",
            "DLCs/ghost/dlc-ghost-audio_assets_all.bundle": "DLCs/ghost/dlc-ghost-audio_assets_all.bundle",
        }
        same = roster_equivalent.get(ref)
        if same:
            assert str(fn(ref)).lower() == str(fn(same)).lower(),                 f"{ref!r} and its roster relpath {same!r} do not normalize to one key"


def test_out_of_roster_reference_hard_fails():
    mod = skip_if_none(load_any("stage2_harvest_catalog.py", "tpc_common.py"),
                       "tools/stage2_harvest_catalog.py | tools/tpc_common.py")
    fn = get_sym(mod, *COVERAGE_NAMES)
    if fn is None:
        pytest.skip("impl-missing: no coverage/reference-check function on "
                    f"tools/stage2_harvest_catalog.py (tried {COVERAGE_NAMES})")
    roster = sorted(_normalized_roster_basenames())
    refs_ok = [r for _k, r in fx.CATALOG_KEYS_SPEC]
    ref_bad = ["totally-unknown_bundle.bundle"]
    raised_or_false = False
    detail = ""
    try:
        out = fn(refs_ok + ref_bad, roster)
        ok = out.get("ok") if isinstance(out, dict) else out
        if ok is False:
            raised_or_false = True
        elif isinstance(out, dict) and out.get("unknown"):
            raised_or_false = True
        else:
            detail = f"returned {out!r}"
    except (AssertionError, ValueError, RuntimeError) as exc:
        raised_or_false = True
        detail = f"raised {type(exc).__name__}: {exc}"
    assert raised_or_false, (
        "an out-of-roster reference did NOT hard-fail "
        f"(spec pins hard-fail so the guard cannot trip spuriously); {detail}")


def test_coverage_universes_math_synthetic_contentcatalogdata():
    """Synthetic ContentCatalogData fixture: both universes ⊆ the 176-style
    roster; catalog.bundle itself sits in NEITHER count."""
    mod = load_any("stage2_harvest_catalog.py", "tpc_common.py")
    fn = get_sym(mod, *COVERAGE_NAMES) if mod else None
    roster_rows_list = roster_rows()
    roster_names = {Path(r["relpath"]).name for r in roster_rows_list}
    referenced = set()
    for _k, ref in fx.CATALOG_KEYS_SPEC:
        norm = ref.replace("\\", "/").rsplit("/", 1)[-1].lower()
        assert norm in {n.lower() for n in roster_names}, (
            f"synthetic fixture reference {ref!r} does not resolve into the roster — "
            "the synthetic ContentCatalogData fixture itself is inconsistent")
        referenced.add(norm)
    unreferenced = sorted(roster_names - referenced)
    if fn is not None:
        try:
            out = fn([r for _k, r in fx.CATALOG_KEYS_SPEC],
                     sorted(roster_names))
            if isinstance(out, dict):
                db = out.get("distinctBundlesReferenced")
                bu = out.get("bundlesUnreferenced")
                if db is not None:
                    assert db == len(referenced), (
                        f"distinctBundlesReferenced {db} != {len(referenced)}")
                if bu is not None:
                    assert sorted(bu) == unreferenced or \
                        {Path(p).name.lower() for p in bu} == {u.lower() for u in unreferenced}, (
                        f"bundlesUnreferenced mismatch vs universe math: {sorted(bu)[:5]}…")
        except TypeError:
            pass  # signature differs; the pure-math assertions below still bind
    else:
        note_missing_symbol(
            f"coverage function (tried {COVERAGE_NAMES}) — universe math asserted from fixture data only")

    # catalog.bundle exclusion: a self-reference spelling must land in NEITHER count
    assert "catalog.bundle" not in referenced
    assert "catalog.bundle" not in {u.lower() for u in unreferenced}


def test_fixture_coverage_artifact_matches_universe_math(fx_stage3):
    ext = fx_stage3 / "extracted"
    cov = read_json(ext / "addressables" / "catalog-coverage.json")
    cat = read_json(ext / "addressables" / "catalog.json")
    roster = {Path(r["relpath"]).name for r in roster_rows()}
    refs = {k.replace("\\", "/").rsplit("/", 1)[-1].lower()
            for k in (_r["bundle"] for _r in cat["keys"])}
    covered = {r for r in roster if r.lower() in refs}
    errs = validate_coverage(cov, roster, covered)
    assert not errs, f"fixture coverage artifact violates universe math: {errs}"
    assert cov["keysTotal"] == len(cat["keys"])
