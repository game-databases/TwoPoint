"""Stage 0 `verify-client` obligations (spec §8 stage-0 bullets + §3 acceptance)."""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

import pytest

from _impl import (ACF_PARSER_NAMES, LOCALE_FN_NAMES, LOCALE_TABLE_NAMES,
                   METADATA_READER_NAMES, SCENE_FLAG_NAMES, get_sym, load_any,
                   skip_if_none)
from _validators import (EXPECTED_BUNDLES, LOCALE_BUNDLE_COUNT, LOCALE_TABLE,
                         METADATA_SANITY, SCENE_COUNT_PINS, TOTAL_BUNDLES,
                         diff_manifests, hash_tree, read_json, read_jsonl,
                         validate_identity, validate_roster_row)

STAGE = "verify-client"


def run_stage0(tree: Path, extracted_root: Path, *extra):
    from conftest import run_pack, tree_game
    return run_pack([tree_game(tree), "--only", STAGE, *extra],
                    extracted_root=extracted_root)


# --- unit-level obligations (adapter; loud impl-missing skips) -------------------

def test_manifest_acf_parser_on_fixture_text(tmp_path):
    mod = skip_if_none(load_any("stage0_verify_client.py", "tpc_common.py"),
                      "tools/stage0_verify_client.py | tools/tpc_common.py")
    fn = skip_if_none(get_sym(mod, *ACF_PARSER_NAMES), "acf parser")
    from _fixturelib import ACF_TEXT
    try:
        obj = fn(ACF_TEXT)
    except TypeError:
        p = tmp_path / "appmanifest_1649080.acf"
        p.write_text(ACF_TEXT, encoding="utf-8", newline="\n")
        obj = fn(p)
    flat = json.dumps(obj, default=str)
    assert "20226581" in flat, f"buildid not surfaced by parser: {flat[:200]}"
    assert "english" in flat, f"language not surfaced by parser: {flat[:200]}"
    # nested blocks must survive parsing
    assert "1649081" in flat, "nested InstalledDepots block lost"


def test_metadata_header_reader_offsets_0_and_4(tmp_path):
    mod = skip_if_none(load_any("stage0_verify_client.py", "tpc_common.py"),
                       "tools/stage0_verify_client.py | tools/tpc_common.py")
    fn = skip_if_none(get_sym(mod, *METADATA_READER_NAMES), "metadata header reader")

    def read(buf, name="meta.dat"):
        p = tmp_path / name
        p.write_bytes(buf)
        out = None
        try:
            out = fn(buf)                # bytes form if supported
        except (TypeError, AttributeError):
            pass
        if out is None:
            out = fn(p)                  # path form
        if isinstance(out, tuple):
            return int(out[0]), int(out[1])
        if isinstance(out, dict):
            sanity = next(v for k, v in out.items() if "sanit" in k.lower())
            version = next(v for k, v in out.items() if "version" in k.lower())
            return int(sanity), int(version)
        raise AssertionError(f"unsupported reader return {type(out).__name__}: {out!r}")

    sanity, version = read(struct.pack("<II", METADATA_SANITY, 27) + b"\xde\xad\xbe\xef",
                           name="meta27.dat")
    assert sanity == METADATA_SANITY, \
        f"sanity word {sanity:#010x} != {METADATA_SANITY:#010x} (offset 0)"
    assert version == 27, f"metadata version {version} != 27 (int32 LE @ offset 4)"
    # offset-split proof: a different version word must be read from offset 4
    sanity2, version2 = read(struct.pack("<II", METADATA_SANITY, 38), name="meta38.dat")
    assert (sanity2, version2) == (METADATA_SANITY, 38)


@pytest.mark.parametrize("name,expected", [
    ("scenes-scene-campus1.unity.bundle", ".unity"),
    ("scenes_scenes_config_level_databases.unity.bundle", ".unity"),
    ("scenes-seasonalcontent_scenes_all.bundle", "seasonal-scenes"),
    ("items-general_assets_all.bundle", "none"),
    ("dlc-space-scenes_launchpadlevel.unity.bundle", ".unity"),
])
def test_scene_flag_classifier_strict_vs_seasonal(name, expected):
    mod = skip_if_none(load_any("stage0_verify_client.py", "tpc_common.py"),
                      "tools/stage0_verify_client.py | tools/tpc_common.py")
    fn = skip_if_none(get_sym(mod, *SCENE_FLAG_NAMES), "scene-flag classifier")
    got = fn(name)
    if isinstance(got, dict):
        got = got.get("sceneFlag")
    assert got == expected, (
        f"sceneFlag({name!r}) = {got!r}, expected {expected!r} "
        "(strict .unity suffix vs seasonal scene-carrying non-.unity)")


def test_locale_suffix_table_13_exact_mappings():
    mod = skip_if_none(load_any("stage0_verify_client.py", "tpc_common.py"),
                      "tools/stage0_verify_client.py | tools/tpc_common.py")
    scopes = [mod] + ([mod.tc] if hasattr(mod, "tc") else [])
    table = None
    for scope in scopes:
        for cname in LOCALE_TABLE_NAMES:
            attr = getattr(scope, cname, None)
            if isinstance(attr, dict) and attr:
                table = {str(k).lower(): str(v) for k, v in attr.items()}
                break
        if table:
            break
    if table is None:
        fn = get_sym(mod, *LOCALE_FN_NAMES)
        if fn is not None:
            table = {}
            for suffix in LOCALE_TABLE:
                try:
                    table[suffix.lower()] = str(fn(suffix))
                except Exception:
                    table = None
                    break
    if table is None:
        pytest.skip(
            "impl-missing: no locale suffix->BCP-47 table/function on "
            "tools/stage0_verify_client.py "
            f"(tried constants {LOCALE_TABLE_NAMES} / functions {LOCALE_FN_NAMES})")
    # the impl's table may also carry the unnamed-overlay row ("": "base") —
    # the 13 named mappings must match exactly on top of it
    named = {k: v for k, v in table.items() if k not in ("", "base")}
    base_row = {k: v for k, v in table.items() if k in ("", "base")}
    expected = {k.lower(): v for k, v in LOCALE_TABLE.items()}
    assert named == expected, (
        f"locale table drift:\n  missing={sorted(set(expected)-set(named))}\n"
        f"  extra={sorted(set(named)-set(expected))}\n"
        f"  wrong={[k for k in set(expected)&set(named) if expected[k]!=named[k]]}")
    assert len(named) == 13, "the BCP-47 table must hold exactly the 13 named locales"
    if base_row:
        assert list(base_row.values()) == ["base"], \
            "unnamed overlay row must resolve to 'base', never a 14th locale"


def test_locale_for_bundle_end_to_end_real_bundle_names():
    """F1 regression wall: drive `locale_for_bundle` over the REAL bundle
    basenames (scout-report §4 spellings, verified-from-client), not just
    the table dict — the prefix-strip→table lookup beside that table once
    retained a `_` separator and every named bundle degraded to
    `unknown:_<lang>` with zero coverage here."""
    mod = skip_if_none(load_any("stage0_verify_client.py", "tpc_common.py"),
                      "tools/stage0_verify_client.py | tools/tpc_common.py")
    fn = skip_if_none(get_sym(mod, *LOCALE_FN_NAMES), "locale_for_bundle")
    for suffix, bcp47 in sorted(LOCALE_TABLE.items()):
        bundle = f"localisation_assets_localisation_{suffix}.bundle"
        got = fn(bundle)
        assert got == bcp47, (
            f"locale_for_bundle({bundle!r}) = {got!r}, expected {bcp47!r} "
            "(real bundle basename must resolve to its BCP-47 code)")
    # unnamed stem → base overlay, with and without the .bundle extension
    stem = "localisation_assets_localisation"
    assert fn(stem + ".bundle") == "base", "unnamed base overlay bundle misflagged"
    assert fn(stem) == "base", "bare unnamed stem must also flag as base"
    # non-localisation bundles never carry a localeFlag
    assert fn("items-general_assets_all.bundle") is None
    assert fn("scenes-scene-campus1.unity.bundle") is None


# --- black-box behavior on the prepared tree --------------------------------------

def test_stage0_run_success_and_artifact_contract(fx_stage0, tmp_path):
    r = run_stage0(fx_stage0, tmp_path)
    assert r.returncode == 0, f"stage 0 failed rc={r.returncode}\nSTDOUT:{r.stdout}\nSTDERR:{r.stderr}"
    ext = tmp_path
    ident = read_json(ext / "identity.json")
    errs = validate_identity(ident)
    assert not errs, f"identity.json contract violations: {errs}"
    assert ident["metadataVersion"] == 27 and ident["dumper"] == "il2cppdumper"

    rows = read_jsonl(ext / "bundle-roster.jsonl")
    assert len(rows) > 0
    for i, row in enumerate(rows):
        bad = validate_roster_row(row, where=f"roster[{i}]: ")
        assert not bad, f"roster row contract violations: {bad}"
    relpaths = [row["relpath"] for row in rows]
    assert relpaths == sorted(relpaths), "roster not sorted by relpath (determinism)"
    # fixture carries the full 14-bundle localisation set even at small scale
    locale_rows = [row for row in rows if row["localeFlag"] is not None]
    assert len(locale_rows) == LOCALE_BUNDLE_COUNT, (
        f"expected {LOCALE_BUNDLE_COUNT} localeFlag rows, got {len(locale_rows)}")
    assert any(row["localeFlag"] == "base" for row in locale_rows), "unnamed base overlay row missing"
    # roster rows == enumerated *.bundle count over the three corpus dirs
    gr = fx_stage0 / "steamapps" / "common" / "Two Point Campus"
    dirs = [gr / "TPC_Data" / "StreamingAssets" / "aa" / "StandaloneWindows64",
            gr / "DLCs" / "space", gr / "DLCs" / "ghost"]
    bundles_on_disk = [p for d in dirs for p in d.glob("*.bundle")]
    assert len(rows) == len(bundles_on_disk), (
        f"roster rows {len(rows)} != enumerated *.bundle count {len(bundles_on_disk)} "
        "(catalog.bundle sits outside the three dirs and is not a roster row)")


def test_scene_counts_cumulative_arithmetic(fx_stage0, tmp_path):
    """strictUnityInstall >= strictUnityBase etc. — internal consistency of the
    measured counts on fixture data (absolute pins are client-gated)."""
    r = run_stage0(fx_stage0, tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    sc = read_json(tmp_path / "identity.json")["sceneCounts"]
    for k in SCENE_COUNT_PINS:
        assert k in sc
    assert sc["seasonalSceneCarryingBase"] >= sc["strictUnityBase"]
    assert sc["strictUnityInstall"] >= sc["strictUnityBase"]
    assert sc["sceneCarryingInstall"] >= max(sc["strictUnityInstall"],
                                             sc["seasonalSceneCarryingBase"])


def test_drift_warning_path_small_tree(fx_stage0, tmp_path):
    """Live counts differing from expectedBundles -> DRIFT: line, never failure."""
    import re as _re
    r = run_stage0(fx_stage0, tmp_path)
    assert r.returncode == 0, f"DRIFT must warn, not fail: rc={r.returncode}"
    combined = r.stdout + r.stderr
    assert "DRIFT:" in combined, "small fixture (counts != expectedBundles) printed no DRIFT: warning"
    assert _re.search(r"DRIFT:\s*aa\b", combined), (
        "bundle-count drift must name the axis: " + combined)


def test_no_drift_when_counts_match_full_scale(tmp_path_factory, tmp_path):
    tree = Path(str(tmp_path_factory.mktemp("fx0full")))
    sys.path.insert(0, str(Path(__file__).parent))
    import _fixturelib as fx
    fx.build_tree(tree, STAGE, full_scale=True)
    import re as _re
    r = run_stage0(tree, tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    combined = r.stdout + r.stderr
    bundle_drift = [ln2 for ln2 in combined.splitlines()
                   if _re.search(r"DRIFT:\s*(aa\b|dlc-space|dlc-ghost|localisation)", ln2)]
    assert not bundle_drift, (
        "full-scale fixture matches expectedBundles yet produced "
        f"bundle-count DRIFT lines: {bundle_drift}")


def test_metadata_version_gate_v38_exit3(tmp_path_factory, tmp_path):
    """version >= 38 -> exit 3 with the Cpp2IL escalation message (KB wall)."""
    tree = tmp_path_factory.mktemp("fx0gate")
    sys.path.insert(0, str(Path(__file__).parent))
    import _fixturelib as fx
    fx.build_tree(tree, STAGE, metadata_version=38)
    r = run_stage0(tree, tmp_path)
    assert r.returncode == 3, f"metadata v38 must refuse with exit 3, got rc={r.returncode}\n{r.stdout}{r.stderr}"
    assert "cpp2il" in (r.stdout + r.stderr).lower(), \
        "gate refusal must print the pinned Cpp2IL escalation message"


def test_missing_game_dir_exit3(tmp_path):
    from conftest import run_pack, tree_game
    r = run_pack([str(tmp_path / "no-such-game"), "--only", STAGE],
                 extracted_root=tmp_path / "ext")
    assert r.returncode == 3, f"missing dirs are env refusal exit 3, got rc={r.returncode}"


def test_auto_detect_accepts_tpc_data_dir_arg(fx_stage0, tmp_path):
    tpc_data = fx_stage0 / "steamapps" / "common" / "Two Point Campus" / "TPC_Data"
    from conftest import run_pack, tree_game
    r = run_pack([str(tpc_data), "--only", STAGE], extracted_root=tmp_path)
    assert r.returncode == 0, (
        f"TPC_Data auto-detect failed rc={r.returncode}\n{r.stdout}{r.stderr}")


def test_double_run_byte_identical(fx_stage0, tmp_path_factory):
    ext1, ext2 = tmp_path_factory.mktemp("run1"), tmp_path_factory.mktemp("run2")
    r1 = run_stage0(fx_stage0, ext1)
    assert r1.returncode == 0, r1.stdout + r1.stderr
    r2 = run_stage0(fx_stage0, ext2, "--force")
    assert r2.returncode == 0, r2.stdout + r2.stderr
    m1, m2 = hash_tree(ext1), hash_tree(ext2)
    only1, only2, changed = diff_manifests(m1, m2)
    assert not (only1 or only2 or changed), (
        f"second run not byte-identical: only_run1={only1} only_run2={only2} changed={changed}")
