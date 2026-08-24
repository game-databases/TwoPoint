"""Self-tests for the suite's own shared fixture builder (spec §5.2).

`tests/build_fixture_tree.py --stage <id>` must materialize each stage's
upstream set, deterministically, for all six ids.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from _fixturelib import (BASE_SEASONAL, BASE_STRICT_SCENES, DLC_GHOST, DLC_SPACE,
                         build_tree, game_root)
from _validators import LOCALE_TABLE, STAGE_IDS, diff_manifests, hash_tree, read_jsonl

HERE = Path(__file__).parent
BUILDER = HERE / "build_fixture_tree.py"

GR = "steamapps/common/Two Point Campus"

UPSTREAM_KEYS = {
    "verify-client": [
        "steamapps/appmanifest_1649080.acf",
        f"{GR}/GameAssembly.dll",
        f"{GR}/TPC_Data/il2cpp_data/Metadata/global-metadata.dat",
        f"{GR}/TPC_Data/StreamingAssets/aa/settings.json",
    ],
    "decompile": [
        f"{GR}/GameAssembly.dll",
        f"{GR}/TPC_Data/il2cpp_data/Metadata/global-metadata.dat",
        f"{GR}/TPC_Data/ScriptingAssemblies.json",
    ],
    "harvest-catalog": [
        "extracted/bundle-roster.jsonl",
        f"{GR}/TPC_Data/StreamingAssets/aa/catalog.bundle",
        f"{GR}/TPC_Data/StreamingAssets/aa/settings.json",
    ],
    "harvest-bundles": [
        "extracted/bundle-roster.jsonl",
        "extracted/addressables/catalog.json",
    ],
    "localisation": [
        "extracted/bundle-roster.jsonl",
        "extracted/harvest/monobehaviours",
        "extracted/decompiled/structural/assembly-index.json",
    ],
    "emit-stub-datasets": [
        "extracted/harvest/monobehaviours",
        "extracted/addressables/catalog.json",
        "extracted/decompiled/structural/class-hierarchy.jsonl",
        "extracted/locales/locale-matrix.json",
    ],
}


@pytest.mark.parametrize("stage", list(STAGE_IDS))
def test_cli_builds_every_stage_upstream_set(stage, tmp_path):
    out = tmp_path / stage
    r = subprocess.run([sys.executable, str(BUILDER), "--stage", stage,
                        "--out", str(out)],
                       capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert r.returncode == 0, f"builder failed for {stage}: {r.stderr}"
    for rel in UPSTREAM_KEYS[stage]:
        assert (out / rel).exists(), f"{stage} upstream missing {rel}"
    # the game-input skeleton is always present
    assert (out / GR / "TPC_Data").exists()
    # locale-flagged roster rows available from harvest-catalog onward
    if stage in ("harvest-catalog", "harvest-bundles", "localisation", "emit-stub-datasets"):
        rows = read_jsonl(out / "extracted" / "bundle-roster.jsonl")
        flagged = [r_ for r_ in rows if r_.get("localeFlag")]
        assert len(flagged) == 14, f"fixture roster lacks the 14 locale bundles: {len(flagged)}"


def test_builder_deterministic_across_dirs(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    build_tree(a, "emit-stub-datasets")
    build_tree(b, "emit-stub-datasets")
    ma, mb = hash_tree(a, exempt_byte_identity=False), hash_tree(b, exempt_byte_identity=False)
    only_a, only_b, changed = diff_manifests(ma, mb)
    assert not (only_a or only_b or changed), (
        f"fixture builder not deterministic: {only_a[:3]} {only_b[:3]} {changed[:3]}")


def test_fixture_roster_scene_and_locale_flags(tmp_path):
    tree = tmp_path / "t"
    build_tree(tree, "harvest-catalog")
    rows = read_jsonl(tree / "extracted" / "bundle-roster.jsonl")
    by_name = {Path(r["relpath"]).name: r for r in rows}
    for n in BASE_STRICT_SCENES:
        assert by_name[n]["sceneFlag"] == ".unity"
    for n in BASE_SEASONAL:
        assert by_name[n]["sceneFlag"] == "seasonal-scenes"
    base = by_name["localisation_assets_localisation.bundle"]
    assert base["localeFlag"] == "base"
    for suffix, loc in LOCALE_TABLE.items():
        row = by_name[f"localisation_assets_localisation_{suffix}.bundle"]
        # localeFlag resolves to the BCP-47 code (the pipeline's convention)
        assert row["localeFlag"] == loc, \
            f"localeFlag for {suffix!r} should be {loc!r}, got {row['localeFlag']!r}"
    for n in DLC_SPACE:
        assert by_name[n]["dirClass"] == "dlc-space"
    for n in DLC_GHOST:
        assert by_name[n]["dirClass"] == "dlc-ghost"


def test_full_scale_matches_expected_corpus_counts(tmp_path):
    tree = tmp_path / "full"
    build_tree(tree, "harvest-catalog", full_scale=True)
    rows = read_jsonl(tree / "extracted" / "bundle-roster.jsonl")
    counts = {"base": 0, "dlc-space": 0, "dlc-ghost": 0}
    for r in rows:
        counts[r["dirClass"]] += 1
    assert counts == {"base": 158, "dlc-space": 10, "dlc-ghost": 8}, counts
    assert len(rows) == 176


def test_metadata_version_knob(tmp_path):
    tree = tmp_path / "gate"
    build_tree(tree, "verify-client", metadata_version=38)
    blob = (game_root(tree) / "TPC_Data" / "il2cpp_data" / "Metadata"
            / "global-metadata.dat").read_bytes()
    import struct
    sanity, version = struct.unpack("<II", blob[:8])
    assert sanity == 0xFAB11BAF and version == 38


def test_invalid_stage_id_rejected():
    r = subprocess.run([sys.executable, str(BUILDER), "--stage", "nope"],
                       capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode != 0 and ("invalid choice" in (r.stderr + r.stdout))


def test_no_real_game_bytes_in_fixtures(tmp_path):
    """Every fixture file is tiny synthetic content — never real game bytes."""
    tree = tmp_path / "t"
    build_tree(tree, "emit-stub-datasets")
    big = []
    for p in tree.rglob("*"):
        if p.is_file() and p.stat().st_size > 1024 * 1024:
            big.append(p)
    assert not big, f"fixture files must stay tiny (<1 MiB); oversized: {[str(x) for x in big[:5]]}"


def test_game_root_layout_matches_install_shape(tmp_path):
    tree = tmp_path / "layout"
    build_tree(tree, "verify-client")
    root = game_root(tree)
    assert (root / "GameAssembly.dll").exists()
    assert (root / "TPC.exe").exists(), "GameAssembly.dll sits beside TPC.exe per §2"
    manifest = tree / "steamapps" / "appmanifest_1649080.acf"
    assert manifest.exists()
    # steamapps reachable within <=4 parent hops from the game root
    hops = 0
    cur = root
    while hops <= 4:
        if (cur / "appmanifest_1649080.acf").exists():
            break
        cur = cur.parent
        hops += 1
    assert hops <= 4
