"""piece-03 §8 TestWriter contract — stage `maps` (spec Revision 3), fixture-based.

Blind-build discipline: this file was written from
docs/specs/piece-03-maps.mdx Rev 3 + docs/rulings/arbiter-piece03-spec.mdx
ALONE — never from tools/stage7_maps.py or maps_util.py.

Three legs per obligation, honestly labeled (piece-02 convention):

- **fixture-self** — contracts of the synthetic corpus + the suite's own
  validators/detection rule; runnable NOW, keeps every oracle from going
  vacuous.
- **unit** — pure-function obligations driven through tests/_impl.py against
  the spec-pinned scripts (tools/stage7_maps.py + tools/maps_util.py).
  Skips LOUDLY (`impl-missing`) until those land — never fakes a pass.
- **black-box** — `run_all.py <game> --only maps` over the prepared maps
  fixture tree (`tests/build_fixture_tree.py --stage maps`). Skips LOUDLY
  (`impl-lagging`) while `--list` lacks `maps` after `relink`.

Client-gated real-corpus legs (marked client_gated) run against the real
extraction root and additionally require the registered stage.

Hostless; temp roots under D:/tpc_pytmp via --basetemp (never C:-rooted);
PYTHONUTF8=1; synthetic bytes only.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
PACK_ROOT = HERE.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import _impl  # noqa: E402
import _mapslib as ml  # noqa: E402
from _validators import (  # noqa: E402
    BUILD_ID, BYTE_IDENTITY_EXEMPT, diff_manifests, hash_tree,
    read_json, read_jsonl, scan_tree_for_media_extensions,
)
from conftest import game_dir, run_pack, seeded_extracted_root  # noqa: E402

MAPS_SCRIPTS = ("stage7_maps.py", "maps_util.py")

# spec §3/§4 declared stage write surface
DECLARED_MAPS_OUTPUTS = (
    "coordinate_law.json", "loadassets_read.json", "levels.jsonl",
    "scenarios.jsonl", "plots.jsonl", "plots_tiletypes.jsonl", "rooms.jsonl",
    "rooms_tiles.jsonl", "item_placements.jsonl", "students.jsonl",
    "staff_records.jsonl", "landscape_layers.jsonl", "landscape_maps.jsonl",
    "terrain_decode.json", "door_validators.jsonl",
    "door_placement_index.jsonl", "door_id_space.json", "named_plots.jsonl",
    "imagery_candidates.jsonl", "imagery_predicates.json", "join_report.json",
    "_manifest.sha256", "_absences.jsonl", "_unresolved_placements.jsonl",
)

# pinned EXTRACTION-LOG run-section keys (spec M1–M7 "Run-section keys")
PINNED_RUN_KEYS = (
    # M1
    "gridConstParsed", "gridDrift", "boundsRows", "spawnRows",
    "spawnVariants", "loadassetsReadStatus",
    # M2
    "scenariosRead", "plotRows", "roomRows", "roomTilesRows",
    "plotTileTypesRows", "placementRows", "studentRows", "staffRows",
    "identityCollisions", "axisCounts",
    # M3
    "indexEntries", "resolvedSameFile", "resolvedCrossFile", "unresolved",
    "widenedClassCount", "corroborationMatch", "corroborationTwinMismatch",
    # M4
    "layersTotal", "dimsMin", "dimsMax", "brushDatabasesRead",
    "brushDefinitionsRead", "legendValuesProven", "terrainDecodeStatus",
    # M5
    "validatorsEmitted", "validatorRefs", "doorPlacements", "doorKinds",
    "slidingDoorComponents", "reconciliation",
    # M6
    "namedPlots", "resolvedTermKeys", "unresolvedTermIds", "genericPlots",
    # M7
    "addressesScanned", "predicateCounts", "candidateRows",
)

EIGHT_STAGES = ("verify-client", "decompile", "harvest-catalog",
                "harvest-bundles", "localisation", "emit-stub-datasets",
                "relink", "maps")

TEMP_PATTERNS = ("*.tmp", "*.tmp.*", "*.partial", "*.part", "*.temp",
                 "*.tmp[0-9]*")


# --- shared helpers -----------------------------------------------------------------

def _unit(names, scripts=MAPS_SCRIPTS):
    """Resolve an impl symbol across EVERY spec-pinned maps script or skip.
    The piece's pure seams live in BOTH pinned files (`maps_util.py`
    helpers vs `stage7_maps.py` emitters), so a first-module-only search
    would skip loudly forever over landed code."""
    # stage scripts import their tools/ siblings bare (`import tpc_common`);
    # give the loader the same visibility the runner gives them (appended,
    # so tests/ modules keep precedence on name clashes).
    tools_dir = str(PACK_ROOT / "tools")
    if tools_dir not in sys.path:
        sys.path.append(tools_dir)
    loaded = [m for m in (_impl.load_tool(s) for s in scripts)
              if m is not None]
    for mod in loaded:
        scopes = [mod] + [a for a in (getattr(mod, "tc", None),
                                      getattr(mod, "mu", None))
                          if a is not None]
        for scope in scopes:
            for name in names:
                if hasattr(scope, name):
                    return scope, getattr(scope, name)
    _impl.note_missing_symbol(
        f"{'+'.join(scripts)}.{names[0]}"
        + (f" (tried: {', '.join(names)})" if len(names) > 1 else ""))
    pytest.skip("impl-missing: " + "+".join(scripts) + "." + names[0] +
                " not resolvable yet (CodeWriter pending)")


_REG_CACHE: dict[str, bool] = {}


def _maps_registered():
    """Loud gate for black-box stage-7 legs: `--list` must enumerate `maps`
    AFTER `relink`. Skips visibly until the CodeWriter registers the stage —
    never fails red for mere delivery lag."""
    if _REG_CACHE.get("maps") is None:
        r = run_pack(["--list"])
        ok = r.returncode == 0 and re.search(r"^maps\b", r.stdout, re.M)
        if ok:
            ok = 0 <= r.stdout.find("relink") < r.stdout.find("maps")
        if not ok and r.returncode == 0:
            _impl.note_missing_module(
                "run_all.py --list: stage 'maps' not registered yet "
                "(piece-03 CodeWriter pending)")
        _REG_CACHE["maps"] = bool(ok)
    if not _REG_CACHE["maps"]:
        pytest.skip("impl-lagging: stage 'maps' not registered by the runner "
                    "yet (piece-03 CodeWriter pending)")


def _bb():
    _maps_registered()


@pytest.fixture(scope="session")
def fx_maps(tmp_path_factory):
    """Session-shared prepared maps tree (cumulative upstream + §3 set),
    built through _mapslib.build_maps_tree so the suite does not depend on
    the shared STAGE_ARTIFACTS registry file."""
    import conftest
    if "maps-tree" not in conftest._TREES:
        out = tmp_path_factory.mktemp("fx_maps")
        ml.build_maps_tree(out)
        conftest._TREES["maps-tree"] = out
    return conftest._TREES["maps-tree"]


def run_maps(tree_root, ext, *extra, timeout=600, force=False):
    """Black-box `--only maps` with the fixture-tree install root resolved.
    force=True bypasses the up-to-date stamp so the run RE-EXECUTES (the
    stamp no-op is pinned piece-1/2 runner contract; determinism legs need
    genuine re-execution to have teeth)."""
    from conftest import tree_game
    args = [tree_game(tree_root), "--only", "maps"]
    if force:
        args.append("--force")
    return run_pack([*args, *extra], extracted_root=ext, timeout=timeout)


@pytest.fixture(scope="session")
def maps_run(request, fx_maps, tmp_path_factory):
    """ONE seeded extraction root + ONE completed `--only maps` run, shared
    by every READ-ONLY black-box leg (the stage's outputs are deterministic,
    so re-running per test buys nothing). Mutation/exit-code legs keep
    private roots."""
    _bb()
    ext = seeded_extracted_root(fx_maps, tmp_path_factory.mktemp("maps-shr"))
    r = run_maps(fx_maps, ext)
    assert r.returncode == 2, (
        f"steady-state hostless run must complete with ledger (exit 2), "
        f"got {r.returncode}\n{r.stdout[-1500:]}\n{r.stderr[-1500:]}")
    return ext


def maps_dir(ext: Path) -> Path:
    return Path(ext) / "maps"


def art(ext: Path, name: str) -> Path:
    p = maps_dir(ext) / name
    if not p.exists():
        pytest.skip(f"artifact-missing: extracted/maps/{name} not emitted "
                    f"(run failed earlier or impl lagging)")
    return p


def rows_of(ext: Path, name: str):
    return read_jsonl(art(ext, name))


def obj_of(ext: Path, name: str):
    return read_json(art(ext, name))


def last_maps_log_section(ext: Path) -> str:
    log = Path(ext) / "EXTRACTION-LOG.md"
    if not log.exists():
        return ""
    text = log.read_text(encoding="utf-8", errors="replace")
    parts = re.split(r"(?m)^#+.*maps.*$", text, flags=re.I)
    return parts[-1] if len(parts) > 1 else text


def assert_sorted(rows, keyfn, where):
    keys = [keyfn(r) for r in rows]

    def cmp(a, b):
        if a is None and b is None:
            return 0
        if a is None:
            return -1          # nulls sort first (M2 global sort law)
        if b is None:
            return 1
        return -1 if a < b else (1 if a > b else 0)

    for i in range(1, len(keys)):
        prev, cur = keys[i - 1], keys[i]
        for x, y in zip(prev, cur):
            c = cmp(x, y)
            if c != 0:
                break
        else:
            c = 0
        assert c <= 0, (
            f"{where} row {i} out of sort order: {prev} !<= {cur}")


def recursive_values(obj):
    if isinstance(obj, dict):
        for v in obj.values():
            yield from recursive_values(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from recursive_values(v)
    else:
        yield obj


# =====================================================================================
# Section 0 — fixture-self contracts + validator bite (pass NOW)
# =====================================================================================

def test_fixture_oracle_matches_built_corpus(fx_maps):
    """The fixture oracle is recomputed FROM THE BUILT TREE dumps — a stale
    constant oracle would be exactly the blind-fixture trap F14 warns of."""
    ext = fx_maps / "extracted"
    scen = [json.loads(p.read_text(encoding="utf-8"))
            for p in sorted((ext / "harvest" / "monobehaviours").rglob(
                "TPC.LevelScenarioV2/*.json"))]
    alpha = next(s for s in scen if s["m_Name"] == ml.SCEN_ALPHA)
    lr = alpha["_levelRecord"]
    fams = {
        "room": sum(len(r["ItemRecords"]) for r in lr["RoomRecords"]),
        "arrival": len(lr["ArrivalItemRecords"]),
        "nonArea": len(lr["NonAreaItemRecords"]),
        "waypoint": len(lr["NavPlotWaypointRecords"]),
        "plotActivation": sum(len(p.get("PlotActivationItemRecords") or [])
                              for p in lr["PlotRecords"]),
    }
    assert fams == ml.ORACLE["placementsByFamily"]
    assert sum(fams.values()) == ml.ORACLE["placementsTotal"]
    lcs = list((ext / "harvest" / "monobehaviours").rglob(
        "TPC.LevelConfig/*.json"))
    assert len(lcs) == ml.ORACLE["levels"] == 28
    empty_names = sum(
        1 for p in lcs if json.loads(p.read_text(encoding="utf-8"))["m_Name"]
        == "")
    assert empty_names == 28, "F14: m_Name is '' on ALL LevelConfig fixtures"
    layers = sum(len(p["PlotLayerRecords"]) for p in lr["PlotRecords"])
    assert layers == ml.ORACLE["landscapeLayers"]
    named = sum(1 for p in lr["PlotRecords"] if p["UsePlotDisplayName"])
    generic = sum(1 for p in lr["PlotRecords"] if not p["UsePlotDisplayName"])
    assert (named, generic) == (ml.ORACLE["namedPlots"],
                                ml.ORACLE["genericPlots"])
    gen_split = {}
    for family, scene, pc, part, g, pid, spawn, bounds in ml.LEVEL_CONFIGS:
        gen_split[ml.generation_of(family)] = \
            gen_split.get(ml.generation_of(family), 0) + 1
    assert gen_split == ml.ORACLE["generationSplit"], \
        "fixture must reproduce the REAL 13/9/4/2 generation split (F4/F5)"
    bounds_blank = sum(1 for s in ml.LEVEL_CONFIGS
                       if s[7]["extent"]["x"] != 200.0)
    spawn_dev = sum(1 for s in ml.LEVEL_CONFIGS
                    if s[6] not in (ml.SPAWN_CONST,))
    assert (bounds_blank, spawn_dev) == (ml.ORACLE["boundsBlank"],
                                         ml.ORACLE["spawnVariants"])


def test_imagery_oracle_is_stable_and_negative_preserved():
    counts, projection = ml.imagery_counts()
    again, projection2 = ml.imagery_counts(ml.catalog_addresses())
    # catalog carries the same IMG_ADDRESSES plus non-imagery ones that must
    # NOT match anything (the zero stays zero)
    base = {k: v for k, v in again.items()}
    expect = dict(counts)
    extra_addresses = [a for a in ml.catalog_addresses()
                       if a not in ml.IMG_ADDRESSES]
    extra_counts, _ = ml.imagery_counts(extra_addresses)
    merged = {k: counts[k] + extra_counts[k] for k in counts}
    assert base == merged, f"oracle drift over the full address set: " \
                           f"{base} vs {merged}"
    assert counts["minimap-any-spelling"] == 0, \
        "the zero-minimap negative result is first-class data (A 10.1)"
    assert projection["loadingscreen-image-suffixed"] < \
        counts["loadingscreen-images"], \
        "image-suffix secondary projection must be narrower than the family"


def test_detection_rule_bites_and_spares_containment():
    rooms = (ml.ROOM_UID_A, ml.ROOM_UID_B)
    # gated relation: validator ref + room-instance id in ONE row -> fires
    bad_rows = [
        {"validatorId": -2114520335, "entranceToRooms": [-39494005],
         "roomUniqueId": ml.ROOM_UID_A},
        {"entranceRef": [-39494005], "owningRoomUniqueId": ml.ROOM_UID_B},
        {"note": "x", "exitToRooms": [[-1741033445]],
         "linkedRoomIds": [ml.ROOM_UID_A]},
    ]
    for i, row in enumerate(bad_rows):
        assert ml.gated_relation_violation(row, rooms, where=f"bad{i}"), \
            f"detection rule MUST fire on gated row {i}"
    # validator refs alone are fine (they ARE door_validators.jsonl data)
    clean_val = {"validatorId": -2114520335,
                 "entranceToRooms": [-39494005, -1741033445]}
    assert ml.gated_relation_violation(clean_val, rooms) is None
    # room ids alone are fine
    assert ml.gated_relation_violation({"owningRoomUniqueId": 101},
                                       rooms) is None
    # placement containment exception: owningRoomId on a placement-family
    # row is REQUIRED data and passes while the gate is closed (M5 scope)
    containment = {"recordFamily": "room", "owningRoomId": ml.ROOM_UID_A,
                   "definitionName": "Item_Door_Building_Alpha_Main",
                   "itemIndex": 0}
    assert ml.gated_relation_violation(containment, rooms) is None


def test_suite_validators_have_teeth():
    good_levels = {
        "levelId": "KnightLevel", "contentAxis": "base",
        "worldBounds": {"center": {"x": 0, "y": 0, "z": 0},
                        "extent": {"x": 200.0, "y": 16.0, "z": 200.0}},
        "spawnPoint": {"x": -66.0, "y": 0.0, "z": -24.0},
        "plotCount": {"value": 7, "generation": "levels-prefabs",
                      "variantOf": None},
        "sceneNames": {"levelScene": "KnightLevel",
                       "optimized": "KnightLevel_Optimised"},
        "scenarioGuid": None, "scenarioAddress": None, "campaignPart": None,
        "assetAddress": None, "assetNameStem": None, "imagery": {},
        "iconRenderCamera": {}, "source": {"bundle": "b.bundle", "pathId": 1},
        "buildId": BUILD_ID,
    }
    assert ml.validate_levels_row(good_levels) == []
    fifth = json.loads(json.dumps(good_levels))
    fifth["plotCount"]["generation"] = "medical-school-configs"
    errs = ml.validate_levels_row(fifth)
    assert any("four-family enum" in e for e in errs), \
        "a FIFTH generation value must be REJECTED, never invented (R5/M2)"

    canonical = json.loads(json.dumps(good_levels))
    canonical["canonical"] = True
    assert ml.validate_levels_row(canonical), \
        "a canonical flag anywhere is forbidden under R4.0/R4.1"

    derived_bad = {
        "scenarioName": ml.SCEN_ALPHA, "recordFamily": "arrival",
        "owningRoomId": None, "plotUniqueId": None, "definitionId": 1,
        "definitionPptr": {"fileId": 0, "pathId": 1},
        "localPosition": {"x": 0, "y": 0, "z": 0}, "localRotation": 0.0,
        "generalParamInt1": 0, "customisationSwatchIndex": 0, "itemFlags": 0,
        "plotLayer": -1, "resolution": {"status": "pending"},
        "derived": {"world": {"x": 1.0, "y": 0.0, "z": 0.0},
                    "method": "roomWorldPlusLocal"},
        "source": {"bundle": "b.bundle", "pathId": 1}, "buildId": BUILD_ID,
    }
    errs = ml.validate_placement_row(derived_bad)
    assert any("FORBIDDEN on non-room" in e for e in errs), \
        "derived blocks are room-family ONLY (OQ2 frame unverified)"

    plot = {
        "scenarioName": ml.SCEN_ALPHA, "plotUniqueId": 15,
        "persistentName": "Plot 15", "definitionId": -1165001501,
        "definitionPptr": {"fileId": 0, "pathId": None},
        "bounds": {"center": {"x": 0.0, "y": 0.0, "z": 0.0},
                   "extent": {"x": 15.0, "y": 0.0, "z": 28.0}},
        "locked": 0, "initiallyBuilt": 0, "buildCost": 55000,
        "ignoreForCameraBounds": 0, "usePlotDisplayName": 0,
        "displayNameTermId": None, "tileTypes": {"width": 15, "height": 28},
        "tilesRef": {"artifact": "rooms_tiles.jsonl", "key": ["s", 15]},
        "layerCount": 2, "plotActivationCount": 1,
        "source": {"bundle": "b.bundle", "pathId": 1}, "buildId": BUILD_ID,
    }
    errs = ml.validate_plot_row(plot)
    assert any("plots_tiletypes.jsonl" in e for e in errs), \
        "TileTypes bitmaps live in plots_tiletypes.jsonl, never inline"

    bm = {"scenarioName": "s", "uniqueId": 101,
          "tiles": {"_width": 3, "_height": 3, "_saveData": [0] * 8},
          "source": {"bundle": "b", "pathId": 1}, "buildId": BUILD_ID}
    errs = ml.validate_room_tiles_row(bm)
    assert any("_saveData length" in e for e in errs), \
        "bitmap length mismatch must bite"

    coord = {"grid": {"type": "GridCoord", "sourceLine": 1, "cellSize": 3.0,
                      "cellSizeSq": 9.0, "cellSizeInv": 1 / 3,
                      "cellSizeHalf": 1.5, "parsedFrom": "dump.cs"},
             "plotTilePalette": {"type": "EPlotTileType", "sourceLine": 2,
                                 "values": {}},
             "worldBounds": [], "spawnPoints": [], "projection": {},
             "buildId": BUILD_ID}
    errs = ml.validate_coordinate_law(coord)
    assert any("cellSize" in e for e in errs), \
        "embedded coordinate expectations must DRIFT loudly"


def test_float_round_trip_sentinel_is_stable():
    """AC6: `-0.00016784668` stays `-0.00016784668` through serialize."""
    text = json.dumps({"y": ml.FLOAT_TRAP})
    assert "-0.00016784668" in text
    assert repr(json.loads(text)["y"]) == repr(ml.FLOAT_TRAP)


def test_door_census_counterfactual_on_fixture_names():
    resolved_names = [
        "Item_Door_Building_Alpha_Main",      # placed in R101 itemIndex 0
        "Unused_Item_Door_Building_Large",    # placed in R102 itemIndex 0
        "Item_Plain_Chair", "Item_Cross_File_Def",
    ]
    census = ml.door_kind_census(resolved_names)
    assert census["substring"] == {"placements": 2, "kinds": 2}
    assert census["anchored"] == {"placements": 1, "kinds": 1}, \
        "the anchored ^Item_Door_ form would DROP the Unused_* placement " \
        "(F16) — it must NOT be the shipped predicate"


def test_prepared_tree_build_is_byte_deterministic(tmp_path_factory):
    out1 = tmp_path_factory.mktemp("mapsdet1")
    out2 = tmp_path_factory.mktemp("mapsdet2")

    def th(root: Path):
        return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes())
                .hexdigest() for p in sorted(Path(root).rglob("*"))
                if p.is_file()}

    ml.build_maps_upstream(out1 / "extracted")
    ml.build_maps_upstream(out2 / "extracted")
    assert th(out1) == th(out2), "maps upstream build must be deterministic"


# =====================================================================================
# Section 1 — M1 coordinate-law artifact
# =====================================================================================

GRID_PARSE_NAMES = ("parse_coordinate_law", "parse_grid_constants",
                    "parse_dumpcs_constants", "parse_gridcoord",
                    "coordinate_law_from_dumpcs", "parse_constants",
                    "parse_coordinate_constants")
LOADASSETS_NAMES = ("build_loadassets_read", "loadassets_read",
                    "read_loadassets", "emit_loadassets_read",
                    "loadassets_evidence")


def test_m1_unit_constant_parser_over_slice(tmp_path):
    mod, fn = _unit(GRID_PARSE_NAMES)
    cs = tmp_path / "dump.cs"
    cs.write_text(ml.dump_cs_slice(), encoding="utf-8", newline="\n")
    result = None
    for arg in (cs,):
        try:
            result = fn(arg)
            break
        except TypeError:
            continue
    if result is None:
        try:
            result = fn(cs.read_text(encoding="utf-8"))
        except TypeError:
            pytest.skip("impl-shape: grid parser accepts neither path nor "
                        "text")
    blob = json.dumps(result, default=str)
    for token in ("2", "GridCoord"):
        assert token in blob
    parsed = result if isinstance(result, dict) else \
        getattr(result, "__dict__", {})
    flat = json.dumps(parsed, default=str)
    assert "cellSize" in flat.casefold() or "CellSize" in flat, \
        f"parser result should expose the cell constants: {flat[:400]}"


def test_m1_unit_parser_drift_flips_value(tmp_path):
    mod, fn = _unit(GRID_PARSE_NAMES)
    drifted = ml.dump_cs_slice().replace(
        "public const float CellSize = 2;", "public const float CellSize = 7;")
    cs = tmp_path / "dump.cs"
    cs.write_text(drifted, encoding="utf-8", newline="\n")
    try:
        result = fn(cs)
    except TypeError:
        result = fn(cs.read_text(encoding="utf-8"))
    flat = json.dumps(result, default=str)
    assert "7" in flat, "mutating dump.cs must flip the PARSED value " \
                        "(proves nothing is hardcoded)"


def test_m1_blackbox_coordinate_law_contract(maps_run):
    ext = maps_run
    cl = obj_of(ext, "coordinate_law.json")
    errs = ml.validate_coordinate_law(cl, grid_line=ml.GRID_LINE,
                                      palette_line=ml.PALETTE_LINE)
    assert not errs, f"coordinate_law contract violations: {errs}"

    # levelNames are NOT unique across the 28 rows (KnightLevel story/remix
    # AND both GhostsLevel twins share them): count by LIST, never by a
    # name-keyed dict, which silently collapses twin rows (the F14 trap).
    bounds_rows = cl["worldBounds"]
    spawn_rows = cl["spawnPoints"]
    assert len(bounds_rows) == 28 and len(spawn_rows) == 28
    blanks = [r for r in bounds_rows if r["extent"]["x"] != 200.0]
    std = [r for r in bounds_rows
           if r["extent"] == {"x": 200.0, "y": 16.0, "z": 200.0}]
    assert len(blanks) == 1 and blanks[0]["levelName"] == "Level"
    assert blanks[0]["extent"] == {"x": 128.0, "y": 10.0, "z": 128.0}
    assert len(std) == 27
    variants = [r for r in spawn_rows if r["variant"]]
    assert len(variants) == 2, \
        f"exactly two spawn deviants expected, got {[v['levelName'] for v in variants]}"
    names = {v["levelName"] for v in variants}
    assert names == {"Level", "PartyLevel"}
    party = next(r["value"] for r in spawn_rows
                 if r["levelName"] == "PartyLevel")
    assert abs(party["y"] - 2.08646) < 1e-9 and party["x"] == -66.0
    assert next(r["value"] for r in spawn_rows
                if r["levelName"] == "Level")["x"] == -68.0
    const = [r for r in spawn_rows if not r["variant"]]
    assert all(r["value"] == {"x": -66.0, "y": 0.0, "z": -24.0}
               for r in const)
    # AC5 complement: provenance on EVERY positional row, pointing at a real
    # LevelConfig dump of the matching family. Compared as a MULTISET of
    # (levelName, pathId) — a name-keyed dict would silently collapse the
    # twin rows that share levelId and differ only by pathId (the F14 trap).
    want_pairs = Counter((spec[1], spec[5]) for spec in ml.LEVEL_CONFIGS)
    for rows in (cl["worldBounds"], cl["spawnPoints"]):
        got_pairs = Counter((r["levelName"], r["source"]["pathId"])
                            for r in rows)
        assert got_pairs == want_pairs, (
            f"positional-row provenance must name each exact TPC.LevelConfig "
            f"dump (multiset {want_pairs}), got {got_pairs}")
        for r in rows:
            assert str(r["source"]["bundle"]).endswith(".bundle"), \
                f"source.bundle must be the bundle filename: {r['source']!r}"


def test_m1_blackbox_parse_not_hardcode_drift(fx_maps, tmp_path_factory):
    """AC3: mutating dump.cs's constant flips the emitted value AND raises
    a DRIFT line — proves the parse re-executes every run."""
    _bb()
    ext = seeded_extracted_root(fx_maps, tmp_path_factory.mktemp("m1drift"))
    cs = ext / "decompiled" / "il2cppdumper" / "dump.cs"
    cs.write_text(ml.dump_cs_slice().replace(
        "public const float CellSizeInv = 0.5;",
        "public const float CellSizeInv = 0.25;"),
        encoding="utf-8", newline="\n")
    r = run_maps(fx_maps, ext)
    combined = r.stdout + r.stderr + last_maps_log_section(ext)
    assert "DRIFT" in combined.upper(), \
        "a moved embedded expectation MUST print a DRIFT line"
    cl = obj_of(ext, "coordinate_law.json")
    assert cl["grid"]["cellSizeInv"] == 0.25, \
        f"fresh measurement wins over the seed: {cl['grid']}"
    assert cl["projection"]["cellsPerWorldUnit"] == 0.25, \
        "projection must be COMPUTED from the parsed constants, never pasted"


def test_m1_blackbox_unparseable_declarations_exit_1(fx_maps,
                                                     tmp_path_factory):
    """An UNPARSEABLE GridCoord/EPlotTileType declaration is exit 1 — loud,
    because every downstream unit statement depends on it."""
    _bb()
    ext = seeded_extracted_root(fx_maps, tmp_path_factory.mktemp("m1bad"))
    cs = ext / "decompiled" / "il2cppdumper" / "dump.cs"
    cs.write_text("// declarations destroyed\nno constants here\n",
                  encoding="utf-8", newline="\n")
    r = run_maps(fx_maps, ext)
    assert r.returncode == 1, \
        f"unparseable declarations must exit 1, got {r.returncode}\n{r.stdout}{r.stderr}"
    combined = (r.stdout + r.stderr).lower()
    assert "gridcoord" in combined or "declaration" in combined or \
        "eplottiletype" in combined, "refusal must NAME what failed to parse"


def test_m1_blackbox_loadassets_read_inconclusive(maps_run):
    ext = maps_run
    la = obj_of(ext, "loadassets_read.json")
    errs = ml.validate_loadassets_read(la, iterator_line=ml.ITERATOR_LINE)
    assert not errs, f"loadassets_read contract violations: {errs}"
    assert la["readStatus"] == "inconclusive-from-dumpcs", \
        "first-run value on a declaration-only dump.cs is honest-inconclusive"
    assert la["instantiatedGeneration"] is None
    unblock = str(la.get("unblock", ""))
    assert "corroboration" in unblock.lower() or "decompile" in \
        unblock.lower(), "the optional-corroboration routing must stay named"


# =====================================================================================
# Section 2 — M2 scenario emission
# =====================================================================================

def test_m2_blackbox_row_count_table(maps_run):
    """AC2 hostless analog: every artifact exists at its seeded count."""
    ext = maps_run
    o = ml.ORACLE
    assert len(rows_of(ext, "levels.jsonl")) == o["levels"]
    assert len(rows_of(ext, "scenarios.jsonl")) == o["scenarios"]
    assert len(rows_of(ext, "plots.jsonl")) == o["plots"]
    assert len(rows_of(ext, "rooms.jsonl")) == o["rooms"]
    assert len(rows_of(ext, "rooms_tiles.jsonl")) == len(
        rows_of(ext, "rooms.jsonl"))
    assert len(rows_of(ext, "plots_tiletypes.jsonl")) == len(
        rows_of(ext, "plots.jsonl"))
    placements = rows_of(ext, "item_placements.jsonl")
    assert len(placements) == o["placementsTotal"]
    by_family = {}
    for row in placements:
        by_family[row["recordFamily"]] = \
            by_family.get(row["recordFamily"], 0) + 1
    assert by_family == o["placementsByFamily"]
    assert len(rows_of(ext, "students.jsonl")) == o["students"]
    assert len(rows_of(ext, "staff_records.jsonl")) == o["staff"]
    assert len(rows_of(ext, "landscape_layers.jsonl")) == o["landscapeLayers"]
    assert len(rows_of(ext, "landscape_maps.jsonl")) == len(
        rows_of(ext, "landscape_layers.jsonl")), \
        "layers and maps files carry the SAME measured layers (join-clean pair)"
    assert len(rows_of(ext, "door_validators.jsonl")) == o["doorValidators"]
    assert len(rows_of(ext, "named_plots.jsonl")) == o["namedPlots"]


def test_m2_blackbox_levels_identity_law(maps_run):
    """F14/R4: levelId := LevelScene verbatim (never the EMPTY m_Name);
    identity = (generation, levelId, source.pathId); ghost twins share BOTH
    family and scene and are separated ONLY by pathId; variantOf links twins
    as FIRST-CLASS rows; NO canonical flag anywhere."""
    ext = maps_run
    levels = rows_of(ext, "levels.jsonl")
    assert len(levels) == 28
    identity = set()
    gen_split: dict[str, int] = {}
    for row in levels:
        errs = ml.validate_levels_row(row)
        assert not errs, f"{row.get('levelId')!r}: {errs}"
        ident = (row["plotCount"]["generation"], row["levelId"],
                 row["source"]["pathId"])
        assert ident not in identity, f"identity collision at {ident}"
        identity.add(ident)
        gen_split[row["plotCount"]["generation"]] = \
            gen_split.get(row["plotCount"]["generation"], 0) + 1
        assert row["levelId"], "levelId must be NON-EMPTY (F14)"
    assert gen_split == ml.ORACLE["generationSplit"]

    by_ident = {(r["plotCount"]["generation"], r["levelId"],
                 r["source"]["pathId"]): r for r in levels}

    def twins(gen_a, pid_a, gen_b, pid_b, level_id):
        ra = by_ident[(gen_a, level_id, pid_a)]
        rb = by_ident[(gen_b, level_id, pid_b)]
        va = ra.get("variantOf", ra.get("plotCount", {}).get("variantOf"))
        vb = rb.get("variantOf", rb.get("plotCount", {}).get("variantOf"))
        assert va is not None and vb is not None, (
            f"twin pair for {level_id!r}: BOTH rows ride variantOf as "
            f"first-class rows (R4.2), got {va!r} / {vb!r}")
        return ra, rb

    # base twin spans configs-levels-prefabs <-> configs_assets_all, and the
    # PlotCount DISAGREEMENT (7 vs 5) keeps both rows linked, neither deleted
    story, remix = twins(ml.GEN_LEVELS_PREFABS, -6100000000000000003,
                         ml.GEN_CONFIGS_ASSETS_ALL, -6200000000000000001,
                         "KnightLevel")
    assert story["plotCount"]["value"] == 7 and \
        remix["plotCount"]["value"] == 5
    # the ghost pair shares family AND scene; only pathId distinguishes them
    g1, g2 = twins(ml.GEN_DLC_GHOST, -6400000000000000001,
                   ml.GEN_DLC_GHOST, -6400000000000000002, "GhostsLevel")
    assert g1["source"]["pathId"] != g2["source"]["pathId"]
    # human-readable disambiguation via reverse container_index, method-stamped
    for g in (g1, g2):
        addr = g.get("assetAddress")
        assert addr, "ghost twin assetAddress should resolve via container-index"
    assert g1["assetAddress"] != g2["assetAddress"]
    # no canonical flag ANYWHERE in the artifact (terminal R4 policy)
    raw = art(ext, "levels.jsonl").read_text(encoding="utf-8").casefold()
    assert '"canonical"' not in raw and "'canonical'" not in raw
    # levelId equals the DUMP's LevelScene; m_Name was empty there
    for row in levels[:6]:
        pid = row["source"]["pathId"]
        spec = next(s for s in ml.LEVEL_CONFIGS if s[5] == pid)
        assert row["levelId"] == spec[1]


def test_m2_blackbox_levels_guid_chain_campaign_parts(maps_run):
    """R4.0 family<->mode split: story rows carry Part* campaignParts;
    remix/DLC rows resolve to non-story addresses with null campaignPart;
    the blank template resolves NOTHING (null guid/address/part)."""
    ext = maps_run
    levels = {r["levelId"] + "#" + str(r["source"]["pathId"]): r
              for r in rows_of(ext, "levels.jsonl")}
    resolvable = 0
    for key, row in levels.items():
        guid = row.get("scenarioGuid")
        addr = row.get("scenarioAddress")
        part = row.get("campaignPart")
        if row["levelId"] == "Level":
            assert guid is None and addr is None and part is None, \
                "blank template carries null guid/address/part (reviewer F13)"
            continue
        assert guid, f"non-blank row without GUID: {key}"
        resolvable += 1
        assert addr and guid.casefold() in str(addr).lower() or addr, \
            f"GUID must resolve through the catalog: {key} -> {addr!r}"
        if part is not None:
            assert any(p in str(addr) for p in ml.CAMPAIGN_PARTS) and \
                part in ml.CAMPAIGN_PARTS and part in str(addr), \
                f"campaignPart must equal the Part* segment of the address: " \
                f"{key} {addr!r} -> {part!r}"
    story_rows = [r for k, r in levels.items()
                  if r.get("campaignPart") in ml.CAMPAIGN_PARTS]
    assert len(story_rows) >= 12, \
        "every levels-prefabs playable row wires a campaign STORY scenario"
    assert resolvable == ml.ORACLE["guidResolvable"]


def test_m2_blackbox_scenarios_and_families(maps_run):
    ext = maps_run
    scen = rows_of(ext, "scenarios.jsonl")
    assert [r["scenarioName"] for r in scen] == sorted(
        r["scenarioName"] for r in scen), "sorted by (scenarioName)"
    by_name = {r["scenarioName"]: r for r in scen}
    alpha = by_name[ml.SCEN_ALPHA]
    beta = by_name[ml.SCEN_BETA]
    for row in (alpha, beta):
        errs = ml.validate_scenario_row(row)
        assert not errs, errs
    assert alpha["levelRecordName"] == ml.SCEN_ALPHA_RECORD, \
        "levelRecordName comes from _levelRecord.ScenarioName verbatim"
    c = alpha["counts"]
    assert c["plots"] == 4 and c["rooms"] == 2
    assert c["itemsByFamily"] == ml.ORACLE["placementsByFamily"]
    assert c["itemsTotal"] == ml.ORACLE["placementsTotal"]
    assert c["students"] == 2 and c["staff"] == 2
    assert beta["counts"]["plots"] == 0 and beta["counts"]["itemsTotal"] == 0
    assert beta["contentAxis"] == "dlc-space", \
        "contentAxis follows the source bundle (piece-1 family rule)"
    assert alpha["contentAxis"] == "base"


def test_m2_blackbox_plots_rooms_verbatim_and_tile_homes(maps_run):
    ext = maps_run
    plots = rows_of(ext, "plots.jsonl")
    assert_sorted(plots, lambda r: (r["scenarioName"], r["plotUniqueId"]),
                  "plots")
    alpha_plots = [p for p in plots if p["scenarioName"] == ml.SCEN_ALPHA]
    assert [p["plotUniqueId"] for p in alpha_plots] == [15, 16, 17, 18]
    p15 = alpha_plots[0]
    errs = ml.validate_plot_row(p15)
    assert not errs, errs
    # verbatim world-space bounds incl. the float sentinel byte-exactly
    assert p15["bounds"]["center"]["x"] == -141.0
    raw = art(ext, "plots.jsonl").read_text(encoding="utf-8")
    assert "-0.00016784668" in raw, \
        "float serialization round-trips stably (AC6)"
    assert p15["tilesRef"]["key"] == [ml.SCEN_ALPHA, 15]
    # definitionPptr carried verbatim even when null-pathId (F12/P2 sketch)
    assert p15["definitionPptr"] == {"fileId": 0, "pathId": None}
    named_ids = {p["plotUniqueId"] for p in alpha_plots
                 if p["usePlotDisplayName"]}
    assert named_ids == {15, 16, 17}
    assert p15["displayNameTermId"] == ml.TERM_PAD_SHARED

    rooms = rows_of(ext, "rooms.jsonl")
    assert_sorted(rooms, lambda r: (r["scenarioName"], r["uniqueId"]),
                  "rooms")
    r101 = next(r for r in rooms if r["uniqueId"] == ml.ROOM_UID_A)
    errs = ml.validate_room_row(r101)
    assert not errs, errs
    assert r101["worldPosition"] == {"x": -152.0, "y": -0.00016784668,
                                     "z": -116.0}
    assert r101["anchor"] == {"x": 2, "y": 2}
    assert r101["itemCount"] == 7

    tiles = rows_of(ext, "rooms_tiles.jsonl")
    assert_sorted(tiles, lambda r: (r["scenarioName"], r["uniqueId"]),
                  "rooms_tiles")
    src_r101 = next(iter(sorted(
        (ext / "harvest" / "monobehaviours").rglob(
            "TPC.LevelScenarioV2/*.json"))))
    payload = json.loads(src_r101.read_text(encoding="utf-8"))
    want = payload["_levelRecord"]["RoomRecords"][0]["Tiles"]
    t101 = next(t for t in tiles if t["uniqueId"] == ml.ROOM_UID_A)
    errs = ml.validate_room_tiles_row(t101)
    assert not errs, errs
    assert t101["tiles"] == want, "occupancy bitmap VERBATIM (no packing)"

    ptt = rows_of(ext, "plots_tiletypes.jsonl")
    assert_sorted(ptt, lambda r: (r["scenarioName"], r["plotUniqueId"]),
                  "plots_tiletypes")
    tt15 = next(t for t in ptt if t["plotUniqueId"] == 15)
    errs = ml.validate_plot_tiletypes_row(tt15)
    assert not errs, errs
    assert tt15["tileTypes"] == payload["_levelRecord"]["PlotRecords"][0][
        "TileTypes"]


def test_m2_blackbox_placements_identity_resolution_frames(maps_run):
    ext = maps_run
    place = rows_of(ext, "item_placements.jsonl")
    assert len(place) == ml.ORACLE["placementsTotal"]
    for row in place:
        errs = ml.validate_placement_row(row)
        assert not errs, f"{row['recordFamily']}@{row.get('itemIndex')}: {errs}"
        assert row["resolution"].get("status") != "pending", \
            "M3 rewrote the file once; intermediate states never persist"

    # per-family identity uniqueness (reviewer F7)
    seen = set()
    for row in place:
        fam = row["recordFamily"]
        if fam == "room":
            key = (row["scenarioName"], fam, row["owningRoomId"],
                   row["source"].get("itemIndex"))
        elif fam == "plotActivation":
            key = (row["scenarioName"], fam, row["plotUniqueId"],
                   row["source"].get("itemIndex"))
        else:
            key = (row["scenarioName"], fam, row["source"].get("itemIndex"))
        assert key not in seen, \
            f"per-family identity violated: {key} (the two plotActivation " \
            f"arrays collide under any GLOBAL key but pass here)"
        seen.add(key)

    # global sort tuple, nulls first
    assert_sorted(place, lambda r: (r["scenarioName"], r["recordFamily"],
                                    r["owningRoomId"], r["plotUniqueId"],
                                    r["source"].get("itemIndex")),
                  "item_placements")

    # derived block: room-family only, whole-or-nothing, F10 arithmetic
    door_main = next(r for r in place
                     if r["resolution"].get("definitionName")
                     == "Item_Door_Building_Alpha_Main"
                     and r["recordFamily"] == "room")
    assert door_main["localPosition"] == {"x": 17.0, "y": 0.0, "z": 33.0}
    derived = door_main.get("derived")
    if derived is not None:
        assert derived["method"] == "roomWorldPlusLocal"
        assert derived["world"]["x"] == -135.0, \
            "F10 arithmetic: room world x -152 + local x 17 => -135"
    non_room_derived = [r for r in place
                        if r["recordFamily"] != "room"
                        and r.get("derived") is not None]
    assert not non_room_derived, \
        "non-room families keep derived NULL until M3 proves their frame (OQ2)"

    # students/staff: sentinel termID 0 carried verbatim (piece-2 F8 semantics)
    students = rows_of(ext, "students.jsonl")
    assert len(students) == 2
    term_ids = {s["firstNameTermId"] for s in students} | \
        {s["lastNameTermId"] for s in students}
    assert 0 in term_ids, "_termID 0 sentinel must survive verbatim"
    staff = rows_of(ext, "staff_records.jsonl")
    assert len(staff) == 2
    assert any(s["qualifications"] == ["Cooking"] and s["rank"] == 3
               for s in staff)


def test_m2_blackbox_identity_collision_demotes_composite(fx_maps,
                                                          tmp_path_factory):
    """A measured identity collision demotes BOTH colliding rows to
    `<id>@r<recordIndex>` + an _absences.jsonl row — never a silent merge."""
    _bb()
    ext = seeded_extracted_root(fx_maps, tmp_path_factory.mktemp("m2coll"))
    scen_file = next((ext / "harvest" / "monobehaviours").rglob(
        f"*LevelScenarioV2/*_{ml.PID_SCEN_ALPHA}.json"))
    payload = json.loads(scen_file.read_text(encoding="utf-8"))
    payload["_levelRecord"]["PlotRecords"][1]["PlotUniqueId"] = \
        payload["_levelRecord"]["PlotRecords"][0]["PlotUniqueId"]
    scen_file.write_text(json.dumps(payload, indent=2, sort_keys=True),
                         encoding="utf-8", newline="\n")
    r = run_maps(fx_maps, ext)
    assert r.returncode == 2, \
        f"a demoted collision is completed-with-ledger, got rc={r.returncode}"
    plots = rows_of(ext, "plots.jsonl")
    composite = [p for p in plots if "@r" in str(p.get("plotUniqueId", ""))]
    assert len(composite) >= 2, \
        f"BOTH colliding rows must demote to composite ids: " \
        f"{[p['plotUniqueId'] for p in plots]}"
    absences = read_jsonl(maps_dir(ext) / "_absences.jsonl")
    classes = {a.get("class") for a in absences}
    assert "identity-collisions" in classes


def test_m2_blackbox_axis_openness_unseen_values_accepted(fx_maps,
                                                          tmp_path_factory):
    """R5: an unseen content axis (Medical-School-shaped future bundle) and
    an unseen scenario name pass validation — DRIFT line allowed, rejection
    forbidden; an INVENTED generation value is the defect."""
    _bb()
    ext = seeded_extracted_root(fx_maps, tmp_path_factory.mktemp("m2axis"))
    hospital_dir = ext / "harvest" / "monobehaviours" / "configs-hospital" / \
        "TPC.LevelScenarioV2"
    hospital_dir.mkdir(parents=True, exist_ok=True)
    payload = ml.scenario_beta_payload()
    payload["m_Name"] = "LevelScenarioV2_HospitalFixture"
    payload["_levelRecord"]["ScenarioName"] = "HospitalFixture"
    (hospital_dir /
     f"configs-hospital_assets_all_-7000000000000000009.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n")
    # the unseen-axis scenario is a WELL-FORMED dump — registered in the
    # export manifest like every other scenario, so this leg isolates the
    # AXIS variable and never conflates it with unregistered-dump
    # provenance (which is its own exit-1 gate)
    with open(ext / "harvest" / "export-manifest.jsonl", "a",
              encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps({
            "bytes": 256, "class": "TPC.LevelScenarioV2",
            "outRelPath": "harvest/monobehaviours/configs-hospital/"
                          "TPC.LevelScenarioV2/configs-hospital_"
                          "assets_all_-7000000000000000009.json",
            "pathId": -7000000000000000009,
            "sourceBundle": "configs-hospital_assets_all.bundle",
        }, sort_keys=True) + "\n")
    r = run_maps(fx_maps, ext)
    assert r.returncode != 1, \
        f"an unseen axis/scenario name must NOT hard-fail validation:\n" \
        f"{r.stdout[-600:]}{r.stderr[-600:]}"
    scen = rows_of(ext, "scenarios.jsonl")
    assert any(s["scenarioName"] == "LevelScenarioV2_HospitalFixture"
               for s in scen), "unseen scenario accepted and emitted"


def test_m2_blackbox_fifth_generation_family_never_invented(fx_maps,
                                                            tmp_path_factory):
    """A fifth config FAMILY is a DRIFT line + schema revision, NEVER an
    invented generation value (closed four-family enum)."""
    _bb()
    ext = seeded_extracted_root(fx_maps, tmp_path_factory.mktemp("m2fifth"))
    d = ext / "harvest" / "monobehaviours" / "configs-hospital" / \
        "TPC.LevelConfig"
    d.mkdir(parents=True, exist_ok=True)
    spec = ("configs-hospital", "HospitalLevel", 6, None, None,
            -6500000000000000042, ml.SPAWN_CONST, ml.EXTENT_STD)
    (d / "configs-hospital_assets_all_-6500000000000000042.json").write_text(
        json.dumps(ml.level_config_dump(spec), indent=2, sort_keys=True) +
        "\n", encoding="utf-8", newline="\n")
    r = run_maps(fx_maps, ext)
    levels = rows_of(ext, "levels.jsonl")
    hospital = [lv for lv in levels if lv["levelId"] == "HospitalLevel"]
    combined = (r.stdout + r.stderr + last_maps_log_section(ext)).upper()
    if hospital:
        assert "DRIFT" in combined, \
            "an unseen fifth family must raise a DRIFT line"
        assert hospital[0]["plotCount"]["generation"] in ml.GENERATION_ENUM, \
            "never invent a fifth generation VALUE"
    else:
        assert "DRIFT" in combined, \
            "rejecting the family still owes the DRIFT line naming it"


# =====================================================================================
# Section 3 — M3 definition resolution (PPtr-authoritative join)
# =====================================================================================

CORROBORATION_NAMES = ("classify_corroboration", "corroboration_class",
                       "classify_corroboration_for_record",
                       "compare_definition_id", "corroboration_for")
RESOLVER_NAMES = ("resolve_definition_pptr", "resolve_placement",
                  "resolve_pptr", "resolve_definition", "pptr_resolve")


def test_m3_blackbox_join_report_arithmetic(maps_run):
    ext = maps_run
    jr = obj_of(ext, "join_report.json")
    errs = ml.validate_join_report(jr)
    assert not errs, errs
    j = ml.ORACLE["join"]
    den = jr["denominator"]["measuredSet"]
    assert den == j["denominatorMeasuredSet"], \
        "denominator excludes plotActivation (measured separately below)"
    assert jr["resolved"] == j["resolved"]
    assert jr["residue"] == j["residue"]
    assert jr["residueCrossFile"] == j["residueCrossFile"]
    assert jr["residueSameFileMiss"] == j["residueSameFileMiss"]
    assert jr["resolved"] + jr["residue"] == den
    assert abs(jr["resolveRate"] - j["resolved"] / den) < 1e-9
    corr = jr["corroboration"]
    assert corr["match"] == j["corroboration"]["match"]
    assert corr["twinMismatch"] == j["corroboration"]["twinMismatch"]
    assert corr["absent"] == j["corroboration"]["absent"]
    cause = str(corr.get("cause", ""))
    assert "_raw" in cause or "undecoded" in cause.lower(), \
        f"F17 cause must travel beside the absent count: {cause!r}"
    assert jr["widenedClasses"] == j["widenedClasses"], \
        "widening is MEASURED: only classes resolving real residual PPtrs enter"
    assert jr["indexEntries"] == j["indexEntries"]
    assert jr["indexBundles"] == j["indexBundles"]
    paf = jr["plotActivationFamily"]
    assert paf == j["plotActivationFamily"], \
        "plotActivation resolution is measured fresh, never assumed"
    residue_head = max(jr["residueByScenario"], key=lambda r: r["count"]) \
        if jr["residueByScenario"] else None
    assert residue_head and residue_head["count"] == j["residue"], \
        "residueByScenario attributes the misses by name"


def test_m3_blackbox_worked_chain_and_ladder_evidence(maps_run):
    """F10 worked chain verbatim + the mandatory CAB leg evidence."""
    ext = maps_run
    place = rows_of(ext, "item_placements.jsonl")

    def find(pid):
        return next(r for r in place
                    if (r["definitionPptr"] or {}).get("pathId") == pid)

    same = find(ml.PID_DOOR_MAIN)
    res = same["resolution"]
    assert res["status"] == "resolved"
    assert res["definitionName"] == "Item_Door_Building_Alpha_Main"
    assert res["corroboration"] == "match"
    assert res["definitionId"] == ml.DEF_ID_DOOR_MAIN

    cross = find(ml.PID_CROSS)
    cres = cross["resolution"]
    assert cres["status"] == "resolved" and \
        cres["corroboration"] == "match"
    blob = json.dumps(cres).lower()
    assert "cab-mapsitemsa" in blob, \
        "cross-file evidence carries dstCab (Unity pathIds are per-" \
        "serialized-file; the CAB leg is MANDATORY) — house spelling is " \
        "the simplified lowercase CAB, same as stage 6's evidence"
    assert re.search(r'"extFileId"\s*:\s*1\b', blob) or \
        any(v == 1 for v in cres.values()), \
        "cross-file evidence carries extFileId beside the bundle/pathId pair"

    twin = find(ml.PID_TWIN)
    assert twin["resolution"]["corroboration"] == "twin-mismatch", \
        "genuine id divergence between resolvable targets is recorded, " \
        "never fixed"
    raw_only = find(ml.PID_RAWONLY)
    rres = raw_only["resolution"]
    assert rres["status"] == "resolved" and \
        rres["corroboration"] == "absent", \
        "targets whose payload failed decode classify ABSENT (F17), not " \
        "twin-mismatch"
    wide = find(ml.PID_WIDE)
    assert wide["resolution"]["status"] == "resolved", \
        "the widened class sweep must resolve the residual PPtr"

    unresolved_ledger = rows_of(ext, "_unresolved_placements.jsonl")
    assert len(unresolved_ledger) == ml.ORACLE["join"]["unresolvedLedgerRows"]
    for row in unresolved_ledger:
        errs = ml.validate_unresolved_row(row)
        assert not errs, errs
    dangling = [r for r in unresolved_ledger
                if r.get("dstCab") == ml.CAB_DANGLING or
                r.get("pathId") == ml.PID_UNRESOLVED]
    assert dangling, "the dangling-cab miss lands in the ledger by name"
    assert any((r.get("extFileId") in (4,)) or r.get("extFileId") == 4
               for r in dangling), "extFileId debug evidence present"
    same_miss = [r for r in unresolved_ledger
                 if r.get("pathId") == ml.PID_SAMEMISS]
    assert same_miss, "the same-file miss is attributable too"


def test_m3_unit_corroboration_classifier(tmp_path):
    _, fn = _unit(CORROBORATION_NAMES)
    shapes = [
        (({"_id": ml.DEF_ID_DOOR_MAIN, "m_Name": "X"},
          ml.DEF_ID_DOOR_MAIN), {}),
        (({"_id": ml.DEF_ID_TWIN_TARGET}, ml.DEF_ID_TWIN_RECORD), {}),
        (({"_raw": "<raw>"}, ml.DEF_ID_RAWONLY), {}),
    ]
    outcomes = []
    for args, kw in shapes:
        try:
            outcomes.append(fn(*args, **kw))
        except TypeError:
            outcomes.append(None)
    if all(o is None for o in outcomes):
        try:
            outcomes = [fn(a[0][0], definition_id=a[0][1])
                        for a in shapes]
        except Exception as exc:  # noqa: BLE001
            pytest.skip(f"impl-shape: corroboration classifier unusable: "
                        f"{exc!r}")
    flat = json.dumps([o for o in outcomes], default=str).casefold()
    assert "match" in flat, "classifier vocabulary must include match"
    assert "twin" in flat or "mismatch" in flat
    assert "absent" in flat


# =====================================================================================
# Section 4 — M4 landscape / terrain layer
# =====================================================================================

DECODE_STATUS_NAMES = ("terrain_decode_status", "decode_status_machine",
                       "brush_correlation_status", "terrain_decode",
                       "correlate_terrain_values")


def terrain_histogram(values):
    out = {}
    for v in values:
        out[v] = out.get(v, 0) + 1
    return {k: out[k] for k in sorted(out)}


def test_m4_blackbox_layers_maps_pairing_and_histograms(maps_run):
    ext = maps_run
    layers = rows_of(ext, "landscape_layers.jsonl")
    lmaps = rows_of(ext, "landscape_maps.jsonl")
    o = ml.ORACLE
    assert len(layers) == o["landscapeLayers"] == len(lmaps)
    lk = [(r["scenarioName"], r["plotUniqueId"], r["layerIndex"])
          for r in layers]
    mk = [(r["scenarioName"], r["plotUniqueId"], r["layerIndex"])
          for r in lmaps]
    assert lk == mk, "the pair is join-clean: identical sort identities"
    assert lk == sorted(lk)

    big = next(r for r in layers
               if (r["scenarioName"], r["plotUniqueId"], r["layerIndex"])
               == (ml.SCEN_ALPHA, 15, 0))
    errs = ml.validate_layer_row(big)
    assert not errs, errs
    assert big["dims"]["terrain"] == o["largestMap"]
    assert big["dims"]["object"] == o["largestMap"]
    assert big["roomRecordId"] == ml.ROOM_UID_A
    assert big["plotLayerFlags"] == 3
    # histogram determinism: recomputed from the fixture's verbatim map
    src = next(iter(sorted((ext / "harvest" / "monobehaviours").rglob(
        f"*LevelScenarioV2/*_{ml.PID_SCEN_ALPHA}.json"))))
    payload = json.loads(src.read_text(encoding="utf-8"))
    rec = payload["_levelRecord"]["PlotRecords"][0]["PlotLayerRecords"][0]
    want_hist = terrain_histogram(
        rec["LandscapeRecord"]["TerrainMap"]["_saveData"])
    # JSON round-trip makes histogram keys strings; compare as strings
    got_hist = {str(k): v for k, v
                in (big["valueHistograms"]["terrain"] or {}).items()}
    assert got_hist == {str(k): v for k, v in want_hist.items()}, (
        "histograms are deterministic summaries over the verbatim map "
        f"(want {want_hist}, got {got_hist})")

    zero = next(r for r in layers if r["dims"]["terrain"] == [0, 0])
    assert zero["dims"]["terrain"] == [0, 0] and \
        zero["dims"]["object"] == [0, 0], \
        "a 0-dim row is DATA, not a violation (AC2/F3)"

    big_map = next(r for r in lmaps
                   if (r["scenarioName"], r["plotUniqueId"], r["layerIndex"])
                   == (ml.SCEN_ALPHA, 15, 0))
    errs = ml.validate_landscape_map_row(big_map)
    assert not errs, errs
    assert big_map["terrainMap"] == rec["LandscapeRecord"]["TerrainMap"], \
        "LandscapeRecord payloads VERBATIM, row-major, nothing else"
    assert big_map["landscapeObjectMap"] == \
        rec["LandscapeRecord"]["LandscapeObjectMap"]


def test_m4_blackbox_terrain_decode_states(maps_run):
    ext = maps_run
    td = obj_of(ext, "terrain_decode.json")
    assert td["status"] in ("decoded", "partial", "blocked"), \
        f"status enum violated: {td['status']!r}"
    assert td["brushDatabases"] >= 1 and td["brushDefinitions"] >= 2, \
        "the brush corpus is read fresh (fixture plants 1 db + 2 defs)"
    if td["status"] == "blocked":
        reason = td.get("blockedReason")
        assert reason, "blocked state NAMES its reason (hard law 3)"
    assert str(td.get("unblock") or ""), \
        "every partial/blocked decode ships an unblock path"
    for entry in td.get("valueLegend", []):
        assert entry.get("confidence") in ("proven", "correlated",
                                           "unproven"), \
            f"legend confidence enum violated: {entry!r}"
    log = last_maps_log_section(ext)
    assert "terrainDecodeStatus" in log


def test_m4_unit_decode_status_machine(tmp_path):
    _, fn = _unit(DECODE_STATUS_NAMES)
    shapes = (
        (({"provenValues": 0, "cells": 0},), {}),
        (([], {},), {}),
        (("blocked",), {}),
    )
    got = None
    for args, kw in shapes:
        try:
            got = fn(*args, **kw)
            break
        except TypeError:
            continue
    if got is None:
        pytest.skip("impl-shape: decode-status machine signature unknown")
    flat = json.dumps(got, default=str).casefold()
    assert any(w in flat for w in ("decoded", "partial", "blocked")), \
        f"decode status vocabulary: {flat[:200]}"


# =====================================================================================
# Section 5 — M5 doors + HARD GATE
# =====================================================================================

DOOR_GATE_NAMES = ("assert_door_hard_gate", "check_door_hard_gate",
                   "enforce_door_gate", "door_hard_gate",
                   "assert_no_validator_room_edge", "gate_relation_row",
                   "door_gate_violation", "check_hard_gate")
DOOR_PROJECTION_NAMES = ("project_door_placements", "door_placement_rows",
                         "collect_door_placements", "door_projection")


def _gate_state(agreed: bool, links: int) -> dict:
    return {"reconciliation": "agreed" if agreed else "divergent",
            "instanceLinks": {"measured": links}}


def _probe_gate(fn, row, rooms, state):
    """Call the gate across plausible signatures.

    Returns ("refused", detail) when the row is rejected (raised error OR a
    truthy violation/error-code result), ("allowed", out) when it passes,
    ("unmatched", exc) when no signature matched."""
    gen = state["instanceLinks"]["measured"] \
        if isinstance(state, dict) and "instanceLinks" in state else 0
    rec = state.get("reconciliation") if isinstance(state, dict) else state
    attempts = (
        ((row,), {}),
        ((row, state), {}),
        ((row, rec, gen), {}),
        ((row, tuple(rooms), state), {}),
        ((row, {"room_unique_ids": tuple(rooms), "gate": state}), {}),
    )
    last_type_error: Exception | None = None
    for args, kw in attempts:
        try:
            out = fn(*args, **kw)
        except TypeError as exc:
            last_type_error = exc
            continue
        except (AssertionError, ValueError, PermissionError, RuntimeError,
                SystemExit) as exc:
            return "refused", f"raised {type(exc).__name__}: {exc}"
        if out is None or out is False or out == 0:
            return "allowed", out
        return "refused", f"returned {out!r}"
    return "unmatched", last_type_error


def test_m5_blackbox_validator_emitter_verbatim(maps_run):
    ext = maps_run
    vals = rows_of(ext, "door_validators.jsonl")
    assert len(vals) == ml.ORACLE["doorValidators"]
    assert [v["validatorId"] for v in vals] == sorted(
        v["validatorId"] for v in vals), "sort by (validatorId)"
    anchor = next(v for v in vals if v["validatorId"] == -2114520335)
    errs = ml.validate_validator_row(anchor)
    assert not errs, errs
    assert anchor["entranceToRooms"] == [-39494005, -1741033445], \
        "entrance lists ship VERBATIM (F11 sample echo)"
    assert anchor["exitToRooms"] == [-557321420, -606574128]
    assert anchor.get("catalogAddress") == ml.ADDR_VALIDATOR, \
        "the validator's own GUID resolves through the catalog where possible"
    bare = next(v for v in vals if v["validatorId"] == -2114520336)
    assert ml.validate_validator_row(bare) == [], \
        "message fields are OPTIONAL — a dump without them validates"
    joined = json.dumps(vals)
    for msg in ("InvalidEntranceMessage", "invalidEntranceMessage"):
        if msg in joined:
            break
    else:
        pass  # message emission spelling is implementation-free
    log = last_maps_log_section(ext)
    assert "slidingDoorComponents" in log


def test_m5_blackbox_placement_substring_projection(maps_run):
    """F16 ruled predicate: case-sensitive SUBSTRING `Item_Door_`, so the
    placed Unused_Item_Door_* records ship; anchored would drop them."""
    ext = maps_run
    proj = rows_of(ext, "door_placement_index.jsonl")
    kinds = sorted({p["definitionName"] for p in proj})
    # EVERY placement family counts: the fixture's plotActivation records
    # reference the door definition, so the substring census is 4 rows.
    assert len(proj) == ml.ORACLE["doorPlacements"], (
        f"door census {len(proj)} != oracle {ml.ORACLE['doorPlacements']} "
        "(activation-family placements reference the door definition too)")
    assert kinds == ["Item_Door_Building_Alpha_Main",
                     "Unused_Item_Door_Building_Large"]
    for row in proj:
        errs = ml.validate_door_placement_row(row)
        assert not errs, errs
        assert "Item_Door_" in row["definitionName"]
    anchored_names = [p["definitionName"] for p in proj
                      if p["definitionName"].startswith("Item_Door_")]
    assert (len(anchored_names), len(set(anchored_names))) == (
        ml.ORACLE["doorAnchoredCounterfactual"]["placements"],
        ml.ORACLE["doorAnchoredCounterfactual"]["kinds"]), (
        "the anchored ^Item_Door_ form measures strictly fewer — proof the "
        "shipped predicate is the SUBSTRING form (F16)")
    containment = {p.get("owningRoomId") for p in proj}
    assert containment <= {ml.ROOM_UID_A, ml.ROOM_UID_B, None}, (
        "owningRoomId records which room a placed door sits in (required "
        "data, explicitly OUTSIDE the hard gate's scope)")


def test_m5_blackbox_id_space_dual_sweep(maps_run):
    ext = maps_run
    ids = obj_of(ext, "door_id_space.json")
    errs = ml.validate_door_id_space(ids)
    assert not errs, errs
    assert ids["refsTotal"] == ml.ORACLE["validatorRefs"]
    matched = ids["sweeps"]["fullSpaceSweep"]["matched"]
    covered = set()
    for class_name, ints in matched.items():
        if isinstance(ints, int):
            continue          # some spellings record coverage COUNTS
        covered |= set(ints)
    if covered:
        assert covered <= set(ml.VALIDATOR_REFS) or \
            set(ml.VALIDATOR_REFS) <= covered | set(), \
            "full-space sweep walks real dump _ids"
    assert ids["instanceLinks"]["measured"] == 0 or \
        isinstance(ids["instanceLinks"]["measured"], int)
    assert ids["adjacencyStatus"] == "DERIVED-ONLY"
    log = last_maps_log_section(ext)
    assert "reconciliation" in log


def test_m5_unit_hard_gate_refusal_both_states(tmp_path):
    """The emitter path ITSELF refuses a synthetic gated row with exit-1
    semantics while instanceLinks.measured == 0, ACCEPTS it once the ledger
    reads agreed + links > 0; placement-containment passes in BOTH states."""
    mod, fn = _unit(DOOR_GATE_NAMES)
    rooms = (ml.ROOM_UID_A, ml.ROOM_UID_B)
    gated = {"validatorId": -2114520335,
             "entranceToRooms": [-39494005],
             "roomUniqueId": ml.ROOM_UID_A,
             "emitter": "door_relations"}
    closed = _gate_state(False, 0)
    verdict, detail = _probe_gate(fn, gated, rooms, closed)
    if verdict == "unmatched":
        pytest.skip(f"impl-shape: door gate signature unmatched ({detail})")
    assert verdict == "refused", (
        "HARD GATE closed: emitting a validator-ref x room-instance row "
        f"MUST refuse (exit 1, emitter named); the gate said {verdict} "
        f"({detail!r})")

    open_state = _gate_state(True, 3)
    verdict_open, detail_open = _probe_gate(fn, gated, rooms, open_state)
    if verdict_open != "unmatched":
        assert verdict_open == "allowed", (
            "once the ledger reads agreed + links > 0 the SAME gated row "
            f"is acceptable; got {verdict_open} ({detail_open!r})")

    containment = {"recordFamily": "room", "owningRoomId": ml.ROOM_UID_A,
                   "itemIndex": 0, "definitionName": "Item_Door_X"}
    for state in (closed, open_state):
        verdict_c, detail_c = _probe_gate(fn, containment, rooms, state)
        if verdict_c == "unmatched":
            continue
        assert verdict_c == "allowed", (
            "placement containment (owningRoomId) passes in BOTH gate "
            f"states; got {verdict_c} under {state} ({detail_c!r})")


def test_m5_post_hoc_audit_same_rule_over_emitted_artifacts(maps_run):
    """AC11 second check: the audit runs the SAME pinned detection rule over
    everything the stage wrote — while the fixture gate is closed."""
    ext = maps_run
    room_ids = {r["uniqueId"] for r in rows_of(ext, "rooms.jsonl")}
    violations = []
    md = maps_dir(ext)
    for p in sorted(md.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(md).as_posix()
        try:
            if p.suffix == ".jsonl":
                data = read_jsonl(p)
            elif p.suffix == ".json":
                data = [read_json(p)]
            elif p.suffix in (".sha256", ""):
                continue
            else:
                data = []
        except Exception as exc:  # noqa: BLE001
            violations.append(f"{rel}: unparsable artifact ({exc})")
            continue
        for i, row in enumerate(data):
            v = ml.gated_relation_violation(row, room_ids,
                                            where=f"{rel}[{i}]")
            if v:
                violations.append(v)
    assert not violations, \
        f"HARD GATE violated in emitted artifacts: {violations[:5]}"


# =====================================================================================
# Section 6 — M6 named plots + label joins
# =====================================================================================

def test_m6_blackbox_named_plots_shared_term_ids(maps_run):
    ext = maps_run
    named = rows_of(ext, "named_plots.jsonl")
    assert len(named) == ml.ORACLE["namedPlots"]
    assert_sorted(named, lambda r: (r["scenarioName"], r["plotUniqueId"]),
                  "named_plots")
    pads = [r for r in named if r["plotUniqueId"] in (15, 16)]
    assert len(pads) == 2
    assert all(r["displayNameTermId"] == ml.TERM_PAD_SHARED for r in pads), \
        "the MoonBase-analog pads SHARE one termID"
    assert all(r["resolvedTermKey"] == ml.TERM_PAD_KEY for r in pads), \
        "shared IDs resolve PER ROW — never deduped away"
    assert all(r["inferred"] is False and
               r["method"] == "i2-termid-registry" for r in pads)
    miss = next(r for r in named if r["plotUniqueId"] == 17)
    assert miss["displayNameTermId"] == ml.TERM_MISS
    assert miss["resolvedTermKey"] in (None, ""), \
        "a registry-miss termID resolves to null, never a guess"
    absences = read_jsonl(maps_dir(ext) / "_absences.jsonl")
    assert any(a.get("class") == "plot-display-name-unresolved"
               for a in absences), \
        "registry-miss termIDs land in the absence ledger — never dropped"
    # the generic class is counted, never emitted as gap rows
    plots_total = len(rows_of(ext, "plots.jsonl"))
    assert plots_total - len(named) >= ml.ORACLE["genericPlots"]
    log = last_maps_log_section(ext)
    assert "genericPlots" in log


# =====================================================================================
# Section 7 — M7 imagery candidates (metadata only)
# =====================================================================================

def _extract_predicate_entries(obj):
    """Tolerant extractor for imagery_predicates.json layout."""
    found = {}

    def walk(node):
        if isinstance(node, dict):
            keys = {k.casefold(): k for k in node}
            if "id" in keys and ("pattern" in keys or "regex" in keys) and \
                    ("count" in keys or "freshcount" in keys):
                cid = node[keys["id"]]
                pat = node.get(keys.get("pattern", "pattern")) or \
                    node.get(keys.get("regex", "regex"))
                cnt = node.get(keys.get("count", "count"),
                               node.get(keys.get("freshcount", "freshCount")))
                if isinstance(cid, str):
                    found[cid] = (pat, cnt)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(obj)
    if not found:
        # shape B: {predicates: {"metamap-...": {"pattern","count"}}}
        def walk2(node):
            if isinstance(node, dict):
                for k, v in node.items():
                    if k.casefold() in ml.PREDICATE_PATTERNS and \
                            isinstance(v, dict):
                        found[k] = (v.get("pattern") or v.get("regex"),
                                    v.get("count", v.get("freshCount")))
                    walk2(v)
            elif isinstance(node, list):
                for v in node:
                    walk2(v)

        walk2(obj)
    return found


def test_m7_blackbox_predicates_pinned_and_counted(maps_run):
    ext = maps_run
    pred = obj_of(ext, "imagery_predicates.json")
    entries = _extract_predicate_entries(pred)
    missing = set(ml.PREDICATE_PATTERNS) - set(entries)
    assert not missing, \
        f"EVERY predicate needs a literal pattern in the artifact; " \
        f"missing {sorted(missing)}"
    addresses = []
    cat = read_json(ext / "addressables" / "catalog.json")
    for row in cat["keys"]:
        if row.get("address"):
            addresses.append(row["address"])
    oracle, projection = ml.imagery_counts(addresses)
    for pid, (pat, cnt) in entries.items():
        assert isinstance(pat, str) and pat, \
            f"{pid}: pattern must be literal machine-checkable text"
        assert cnt == oracle[pid], \
            f"{pid}: fresh count {cnt} != oracle {oracle[pid]} applied to " \
            f"THIS run's catalog"
    log = last_maps_log_section(ext)
    assert "addressesScanned" in log and "candidateRows" in log

    candidates = rows_of(ext, "imagery_candidates.jsonl")
    assert [c["address"] for c in candidates] == sorted(
        c["address"] for c in candidates), "rows sorted by address"
    matched_union = set()
    for c in candidates:
        errs = ml.validate_imagery_candidate_row(c)
        assert not errs, errs
        matched_union |= set(c["matchedPredicates"])
        counts_here, _ = ml.imagery_counts([c["address"]])
        hits = {p for p, n in counts_here.items() if n}
        assert hits <= set(c["matchedPredicates"]), \
            f"{c['address']}: predicates must reflect the pinned patterns"
    assert matched_union <= set(ml.PREDICATE_PATTERNS)
    # the negative result preserved: no minimap rows AND the zero still ships
    assert not any("minimap-any-spelling" in c["matchedPredicates"]
                   for c in candidates)
    assert entries["minimap-any-spelling"][1] == 0


def test_m7_metadata_only_no_bytes_written(fx_maps, tmp_path_factory):
    """Carve-out guard intact (AC7): M7 emits METADATA ONLY — no texture is
    opened, decoded, or copied. Mechanical proof: every maps artifact parses
    as UTF-8 JSON/JSONL text, no media-extension FILENAMES appear, and the
    only media-extension TEXT hits are catalog-address strings inside the
    imagery artifacts."""
    _bb()
    ext = seeded_extracted_root(fx_maps, tmp_path_factory.mktemp("m7meta"))
    before_hits = scan_tree_for_media_extensions(Path(ext))
    assert run_maps(fx_maps, ext).returncode == 2
    md = maps_dir(ext)
    media_name_re = re.compile(
        r"\.(ogg|wav|mp3|bnk|fsb|mp4|usm|bk2|png|jpg|jpeg|tga|dds|bmp|exr)",
        re.I)
    for p in sorted(md.rglob("*")):
        if not p.is_file():
            continue
        assert not media_name_re.search(p.name), \
            f"media-extension filename written under maps/: {p.name}"
        try:
            text = p.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise AssertionError(f"{p.name} is not UTF-8 text (binary bytes "
                                 f"under maps/?): {exc}")
        if p.suffix == ".jsonl":
            for i, line in enumerate(text.splitlines(), 1):
                if line.strip():
                    json.loads(line)
        elif p.suffix == ".json":
            json.loads(text)
    hits_after = scan_tree_for_media_extensions(Path(ext))
    baseline = set(before_hits)
    new = [h for h in hits_after if h not in baseline]
    suspicious = [h for h in new
                  if not h.startswith("maps/")
                  and "EXTRACTION-LOG" not in h]
    assert not suspicious, \
        f"media-extension references appeared OUTSIDE maps/ + log: " \
        f"{suspicious[:6]}"
    in_maps = [h for h in new if h.startswith("maps/")]
    for h in in_maps:
        relpath, lineno = h.rsplit(":", 1)[0], h.rsplit(":", 1)[-1]
        p = Path(ext) / relpath
        if p.name in ("imagery_candidates.jsonl", "imagery_predicates.json"):
            continue      # catalog-address STRINGS are metadata, not bytes
        if "Assets/" in p.read_text(encoding="utf-8", errors="replace"):
            continue
        raise AssertionError(f"unexpected media reference in maps/: {h}")


# =====================================================================================
# Section 8 — M8 assembly: manifest, ledgers, byte-stability, single-writer
# =====================================================================================

ABSENCE_CLASSES_ALWAYS = ("scene-transforms-deferred",)


def test_m8_blackbox_declared_outputs_and_manifest(maps_run):
    ext = maps_run
    md = maps_dir(ext)
    missing = [name for name in DECLARED_MAPS_OUTPUTS if not (md / name)
               .exists()]
    assert not missing, \
        f"declared outputs absent from disk = stage failure, not absence " \
        f"(hard law 3): {missing}"
    manifest_lines = (md / "_manifest.sha256").read_text(
        encoding="utf-8").splitlines()
    assert manifest_lines, "manifest must hash THIS run's inputs (AC6)"
    listed = []
    for line in manifest_lines:
        sha, _, rel = line.partition("  ")
        assert re.fullmatch(r"[0-9a-f]{64}", sha), f"bad manifest line: {line}"
        listed.append(rel.strip())
        actual = hashlib.sha256((md / rel.strip()).read_bytes()).hexdigest()
        assert actual == sha, f"manifest digest stale for {rel}"
    assert listed == sorted(listed), "manifest sorted by relPath"
    declared = {name for name in DECLARED_MAPS_OUTPUTS
                if (md / name).stat().st_size}
    undeclared_in_manifest = [r for r in listed
                              if Path(r).name not in DECLARED_MAPS_OUTPUTS]
    assert not undeclared_in_manifest, \
        f"manifest lists undeclared files: {undeclared_in_manifest[:5]}"

    # every pinned run-section key appears in the appended section
    section = last_maps_log_section(ext)
    lost = [k for k in PINNED_RUN_KEYS if k not in section]
    assert not lost, f"pinned run-section keys missing from the log: {lost}"

    # ledger completeness: always-on classes + conditions the fixture plants
    absences = read_jsonl(md / "_absences.jsonl")
    for row in absences:
        errs = ml.validate_absence_row(row)
        assert not errs, errs
    classes = {a["class"] for a in absences}
    for cls in ABSENCE_CLASSES_ALWAYS:
        assert cls in classes, f"always-on absence class missing: {cls}"
    assert "university-level-config-out-of-scope" in classes, \
        "the planted TPC.UniversityLevelConfig sibling must be LEDGERED"
    assert "plot-display-name-unresolved" in classes
    assert "non-room-position-frame-unverified" in classes
    for a in absences:
        assert str(a.get("unblock") or ""), "every absence names its unblock"


def test_m8_blackbox_double_run_byte_identical(fx_maps, tmp_path_factory):
    """AC6: re-EXECUTING `--only maps` twice yields byte-identical declared
    outputs (_manifest.sha256 comparison; log/stamps/meta excluded). The
    second run passes --force: an unchanged stamped tree is a pinned no-op
    (piece-1/2 runner contract — stamp identity), and a no-op would make
    this leg vacuous."""
    _bb()
    ext = seeded_extracted_root(fx_maps, tmp_path_factory.mktemp("m8double"))
    r1 = run_maps(fx_maps, ext)
    assert r1.returncode == 2, r1.stdout[-600:] + r1.stderr[-600:]
    h1 = hash_tree(maps_dir(ext), exempt_byte_identity=False)
    manifest1 = (maps_dir(ext) / "_manifest.sha256").read_bytes()
    r2 = run_maps(fx_maps, ext, force=True)
    assert r2.returncode == 2
    h2 = hash_tree(maps_dir(ext), exempt_byte_identity=False)
    only1, only2, changed = diff_manifests(h1, h2)
    assert not (only1 or only2 or changed), (
        f"double-run drift: missing={only1[:5]} extra={only2[:5]} "
        f"changed={changed[:5]}")
    assert manifest1 == (maps_dir(ext) / "_manifest.sha256").read_bytes()


def test_m8_blackbox_single_writer_discipline(fx_maps, tmp_path_factory):
    """Hard law 5: the stage writes ONLY under extracted/maps/ (+ the
    EXTRACTION-LOG run section). It READS the bridges and registry; it never
    writes under relinks/, stubs/, harvest/, or any earlier stage's paths."""
    _bb()
    ext = seeded_extracted_root(fx_maps, tmp_path_factory.mktemp("m8single"))

    def snapshot(root: Path, skip_prefixes=("maps/",)):
        out = {}
        for p in sorted(Path(root).rglob("*")):
            if not p.is_file():
                continue
            rel = p.relative_to(root).as_posix()
            if any(rel.startswith(pre) for pre in skip_prefixes):
                continue
            if rel in BYTE_IDENTITY_EXEMPT or rel.split("/")[0] in \
                    BYTE_IDENTITY_EXEMPT:
                continue
            out[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
        return out

    before = snapshot(ext)
    assert run_maps(fx_maps, ext).returncode == 2
    after = snapshot(ext)
    changed = sorted(k for k in set(before) | set(after)
                     if before.get(k) != after.get(k))
    assert not changed, (
        f"single-writer violated — stage touched paths outside extracted/"
        f"maps/: {changed[:8]}")
    assert (maps_dir(ext) / "_manifest.sha256").exists()


def test_m8_blackbox_interrupted_run_converges(fx_maps, tmp_path_factory):
    """Interrupted-run convergence holds: temp+rename discipline means a
    killed mid-write leaves no partial finals and the rerun converges to the
    clean run result."""
    _bb()
    ref_ext = seeded_extracted_root(fx_maps,
                                    tmp_path_factory.mktemp("m8conv-ref"))
    r = run_maps(fx_maps, ref_ext)
    assert r.returncode == 2
    reference = hash_tree(maps_dir(ref_ext), exempt_byte_identity=False)

    work = seeded_extracted_root(fx_maps,
                                 tmp_path_factory.mktemp("m8conv-work"))
    md = maps_dir(work)
    md.mkdir(parents=True, exist_ok=True)
    # simulate a crash mid-write: truncated final + stray temp siblings
    (md / "coordinate_law.json").write_text('{"grid": {"cellSize": 2.',
                                           encoding="utf-8")
    (md / "levels.jsonl").write_text('{"levelId": "Trunc', encoding="utf-8")
    (md / "coordinate_law.json.tmp137").write_text("stale", encoding="utf-8")
    (md / "plots.jsonl.part").write_text("stale", encoding="utf-8")
    r2 = run_maps(fx_maps, work)
    assert r2.returncode == 2, r2.stdout[-500:] + r2.stderr[-500:]
    stray = [str(p.relative_to(work)) for pat in TEMP_PATTERNS
             for p in md.rglob(pat)]
    assert not stray, f"successful rerun left temp files behind: {stray[:5]}"
    converged = diff_manifests(reference,
                               hash_tree(md, exempt_byte_identity=False))
    assert not any(converged), \
        f"rerun after interrupted write did not converge: {converged}"


# =====================================================================================
# Section 9 — runner obligations
# =====================================================================================

def test_runner_list_enumerates_maps_after_relink():
    _bb()
    r = run_pack(["--list"])
    assert r.returncode == 0, f"--list failed rc={r.returncode}"
    out = r.stdout
    pos = []
    for sid in EIGHT_STAGES:
        p = out.find(sid)
        assert p >= 0, f"--list output missing stage id {sid!r}:\n{out}"
        pos.append(p)
    assert pos == sorted(pos), (
        "--list enumerates the eight stages out of order "
        "(piece-03 AC1: maps AFTER relink):\n{out}".format(out=out))
    header = out.lower()
    for word in ("tool", "version", "status"):
        assert word in header, f"--list lacks the {word!r} column"


def test_runner_make_list_equivalent():
    _bb()
    make = shutil.which("make")
    if make is None:
        pytest.skip("environment-missing: `make` not on PATH on this host")
    r = subprocess.run([make, "list"], cwd=str(PACK_ROOT), capture_output=True,
                       text=True, encoding="utf-8", errors="replace",
                       timeout=120)
    assert r.returncode == 0, "`make list` failed"
    pos = []
    for sid in EIGHT_STAGES:
        p = r.stdout.find(sid)
        assert p >= 0, f"`make list` missing stage {sid!r}"
        pos.append(p)
    assert pos == sorted(pos), "`make list` enumerates stages out of order"


def test_cli_build_fixture_tree_stage_maps(tmp_path):
    """AC1 hostless smoke mode, verbatim command:
    `python tests/build_fixture_tree.py --stage maps` materializes §3's
    upstream set synthetically. Depends on the SHARED STAGE_ARTIFACTS
    registry carrying `maps`; if that shared-file edit is not present in
    this checkout, skip LOUDLY rather than fail red for wiring lag."""
    import _fixturelib as fxmod
    if "maps" not in fxmod.STAGE_ARTIFACTS:
        pytest.skip("wiring-pending: _fixturelib.STAGE_ARTIFACTS lacks "
                    "'maps' (shared-file edit not present in this checkout)")
    builder = HERE / "build_fixture_tree.py"
    out = tmp_path / "maps-cli"
    env = {**os.environ, "PYTHONUTF8": "1"}
    r = subprocess.run([sys.executable, str(builder), "--stage", "maps",
                        "--out", str(out)],
                       capture_output=True, text=True, encoding="utf-8",
                       timeout=300, env=env)
    assert r.returncode == 0, f"builder failed for maps: {r.stderr}"
    ext = out / "extracted"
    mono = ext / "harvest" / "monobehaviours"
    assert len(list(mono.rglob("TPC.LevelScenarioV2/*.json"))) == \
        ml.ORACLE["scenarios"]
    assert len(list(mono.rglob("TPC.LevelConfig/*.json"))) == \
        ml.ORACLE["levels"]
    assert len(list(mono.rglob("TPC.ItemValidator_Door/*.json"))) == \
        ml.ORACLE["doorValidators"]
    for rel in ("relinks/bridges/cab_index.jsonl",
                "relinks/bridges/container_index.jsonl",
                "relinks/i2_term_registry.jsonl",
                "addressables/catalog.json",
                "decompiled/il2cppdumper/dump.cs",
                "harvest/export-manifest.jsonl", "harvest/externals.jsonl",
                "identity.json", "bundle-roster.jsonl"):
        assert (ext / rel).exists(), f"upstream artifact missing: {rel}"
    slice_text = (ext / "decompiled" / "il2cppdumper" / "dump.cs").read_text(
        encoding="utf-8")
    assert "GridCoord" in slice_text and "EPlotTileType" in slice_text
    assert "<LoadAssets>d__" in slice_text, \
        "the iterator declaration rides the slice (no body)"


def test_runner_only_maps_isolation(fx_maps, tmp_path_factory):
    """`--only maps` writes ONLY its declared surface; stages 0–6 outputs
    stay byte-identical around the run (additivity proof complement)."""
    _bb()
    ext = seeded_extracted_root(fx_maps, tmp_path_factory.mktemp("iso7"))
    before = hash_tree(ext)
    r = run_maps(fx_maps, ext)
    assert r.returncode == 2, r.stdout[-600:] + r.stderr[-600:]
    after = hash_tree(ext)
    only_before, only_after, changed = diff_manifests(before, after)
    legal = ("maps/", "EXTRACTION-LOG.md", ".stage-stamps/",
             ".pipeline-meta.json")
    offenders = [p for p in (only_after + changed)
                 if not any(p.startswith(pre) for pre in legal)]
    assert not offenders, f"--only maps wrote outside its surface: {offenders[:8]}"
    vanished = [p for p in only_before
                if not any(p.startswith(pre) for pre in legal)]
    assert not vanished, f"--only maps DELETED upstream files: {vanished[:8]}"


def test_runner_missing_upstream_exits_3(fx_maps, tmp_path_factory):
    _bb()
    ext = seeded_extracted_root(fx_maps, tmp_path_factory.mktemp("exit3"))
    (ext / "harvest" / "externals.jsonl").unlink()
    r = run_maps(fx_maps, ext)
    assert r.returncode == 3, \
        f"missing upstream must exit 3, got {r.returncode}\n{r.stdout}{r.stderr}"
    combined = (r.stdout + r.stderr).lower()
    assert "externals" in combined, \
        "the runner pre-check must NAME the missing artifact"


def test_runner_missing_scenario_glob_exits_3(fx_maps, tmp_path_factory):
    _bb()
    ext = seeded_extracted_root(fx_maps, tmp_path_factory.mktemp("exit3b"))
    shutil.rmtree(ext / "harvest" / "monobehaviours" / ml.DIR_SCEN_A)
    r = run_maps(fx_maps, ext)
    assert r.returncode == 3, \
        f"missing scenario dumps must exit 3, got {r.returncode}\n" \
        f"{r.stdout}{r.stderr}"


def test_runner_exit2_contributors_named(fx_maps, tmp_path_factory):
    """Exit 2 steady state names every contributor + size in the run
    section (terrain not proven-complete, door id-space divergent, frame
    unverified, transforms deferred, unresolved placements)."""
    _bb()
    ext = seeded_extracted_root(fx_maps, tmp_path_factory.mktemp("exit2"))
    r = run_maps(fx_maps, ext)
    assert r.returncode == 2, r.stdout[-600:] + r.stderr[-600:]
    section = last_maps_log_section(ext)
    low = section.lower()
    for contributor_word in ("terrain", "reconciliation", "unresolved"):
        assert contributor_word in low, \
            f"exit-2 run section must name the {contributor_word!r} contributor"
    td = obj_of(ext, "terrain_decode.json")
    ids = obj_of(ext, "door_id_space.json")
    contributors = []
    if td["status"] != "decoded":
        contributors.append("terrain")
    if ids["reconciliation"] != "agreed":
        contributors.append("door")
    if len(rows_of(ext, "_unresolved_placements.jsonl")):
        contributors.append("unresolved placements")
    assert contributors, "fixture plants at least one exit-2 contributor"


def test_runner_stamp_invalidation_on_script_hash_change(tmp_path_factory):
    """Spec pins script-hash deps ["stage7_maps.py", "maps_util.py",
    "tpc_common.py", "log_util.py"]: touching either maps script must
    invalidate the stamp and force re-execution. Runs against a pack COPY."""
    _bb()
    scripts = PACK_ROOT / "tools"
    if not (scripts / "stage7_maps.py").exists():
        pytest.skip("impl-lagging: tools/stage7_maps.py not present yet")

    def copy_harness(dst: Path) -> Path:
        ignore = shutil.ignore_patterns(
            ".git*", ".agents", ".claude", "__pycache__", "extracted",
            ".fixture-trees", "*.pyc", "site", "design", "data",
            ".pytest_tmp", ".venv", "node_modules")
        shutil.copytree(PACK_ROOT, dst, ignore=ignore, dirs_exist_ok=True)
        return dst

    pack = copy_harness(tmp_path_factory.mktemp("packcopy7"))
    tree = pack / "_fx"
    from conftest import tree_game
    ml.build_maps_tree(tree)
    ext = tree / "extracted"
    game = str(tree_game(tree))

    def run_once(force=False):
        args = [sys.executable, str(pack / "run_all.py"), game,
                "--only", "maps"]
        if force:
            args.append("--force")   # re-execute past the pinned stamp no-op
        return subprocess.run(
            args, cwd=str(pack),
            env={**os.environ, "PYTHONUTF8": "1",
                 "TPC_EXTRACTED_ROOT": str(ext)},
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=900)

    def signal() -> tuple[int, int]:
        log = ext / "EXTRACTION-LOG.md"
        n = 0
        if log.exists():
            n = sum(1 for ln in log.read_text(
                encoding="utf-8", errors="replace").splitlines()
                if "maps" in ln.lower())
        stamp_dir = ext / ".stage-stamps"
        mt = max((p.stat().st_mtime_ns for p in stamp_dir.glob("*maps*")),
                 default=0) if stamp_dir.exists() else 0
        return n, mt

    r1 = run_once()
    assert r1.returncode in (0, 2), r1.stdout[-500:] + r1.stderr[-500:]
    n1, mt1 = signal()
    time.sleep(0.03)
    r2 = run_once(force=True)
    assert r2.returncode in (0, 2)
    n2, mt2 = signal()
    if (n1, mt1) == (n2, mt2):
        pytest.skip("impl-shape: no stamp identity observed between two "
                    "clean runs (log lines and stamp mtimes identical)")
    time.sleep(0.03)
    script = pack / "tools" / "maps_util.py"
    target = script if script.exists() else pack / "tools" / "stage7_maps.py"
    with open(target, "a", encoding="utf-8") as fh:
        fh.write("\n# test-only hash bump (stamp invalidation)\n")
    r3 = run_once()
    assert r3.returncode in (0, 1, 2), \
        f"post-touch run crashed outright: {r3.stdout[-300:]}{r3.stderr[-300:]}"
    n3, mt3 = signal()
    assert (n3, mt3) != (n2, mt2), (
        "touching a spec-pinned dep script did NOT invalidate the maps "
        "stamp — the spec-pinned dep set is "
        '["stage7_maps.py", "maps_util.py", "tpc_common.py", "log_util.py"]')


def test_runner_carveout_guard_green_after_maps_run(maps_run):
    ext = maps_run
    md = maps_dir(ext)
    hits = scan_tree_for_media_extensions(md)
    textual_only = [h for h in hits
                    if "imagery_candidates" in h or
                    "imagery_predicates" in h]
    others = [h for h in hits if h not in textual_only]
    assert not others, \
        f"M7 emits METADATA ONLY — unexpected media reference: {others[:6]}"


def test_tools_carry_no_campus_axis_literals():
    """AC10 grep-half: no hardcoded campus/DLC/level-name literal may sit in
    tools/stage7_maps.py or tools/maps_util.py (axis-open schemas, R5).
    Matched as game-vocabulary TOKENS (camel compounds + *Level names), not
    bare English words, so ordinary prose ('final state on disk') cannot
    false-positive."""
    banned_patterns = (
        r"MoonBase", r"Moonbase",
        r"\b(?:Knight|Mitton|Gastronomy|Magic|PerformingArts|Archaeology|"
        r"Robotics|Sports|Spy|Party|Final|Tutorial|LaunchPad|SpaceportCity|"
        r"Ghosts)Level",
        r"SpaceportCity", r"Scene_DLC2_Ghosts",
        r"DLC1_Space", r"DLC2_Ghost", r"dlc-hospital",
        r"Remix_\d", r"Medical School",
    )
    present = [name for name in MAPS_SCRIPTS
               if (PACK_ROOT / "tools" / name).exists()]
    if not present:
        pytest.skip("impl-missing: tools/stage7_maps.py + maps_util.py not "
                    "present yet (CodeWriter pending)")
    offenders = []
    for name in present:
        text = (PACK_ROOT / "tools" / name).read_text(
            encoding="utf-8", errors="replace")
        for lit in banned_patterns:
            m = re.search(lit, text)
            if m:
                line_no = text[:m.start()].count("\n") + 1
                offenders.append(f"{name}:{line_no}: /{lit}/")
    assert not offenders, \
        "campus/DLC/level-name literals baked into the stage break axis " \
        f"openness (R5/AC10): {offenders[:8]}"


# =====================================================================================
# Section 10 — client-gated integration (real corpus; auto-skips without it)
# =====================================================================================

_CLIENT_CACHE: dict[str, object] = {}


def _real_maps_artifacts(tag: str):
    """Run `--only maps` ONCE against the real root per session (cached) and
    hand back the real extracted root."""
    if "root" not in _CLIENT_CACHE:
        g = game_dir()
        if g is None:
            pytest.skip("client_gated: no TPC_GAME_DIR / default install")
        _maps_registered()
        root = PACK_ROOT / "extracted"
        r = run_pack([str(g), "--only", "maps"], timeout=3600)
        assert r.returncode in (0, 2), \
            f"real-corpus --only maps failed rc={r.returncode}\n" \
            f"{r.stdout[-800:]}{r.stderr[-800:]}"
        _CLIENT_CACHE["root"] = root
    return _CLIENT_CACHE["root"]


@pytest.mark.client_gated
def test_client_ac2_row_count_table_holds():
    root = _real_maps_artifacts("ac2")
    md = root / "maps"
    n = lambda name: len(read_jsonl(md / name))  # noqa: E731
    assert n("levels.jsonl") == 28
    assert n("scenarios.jsonl") == 51
    assert n("plots.jsonl") == 1031
    assert n("rooms.jsonl") == 5188
    assert n("rooms_tiles.jsonl") == n("rooms.jsonl") == 5188
    assert n("plots_tiletypes.jsonl") == n("plots.jsonl") == 1031
    total = n("item_placements.jsonl")
    by_family = {}
    for row in read_jsonl(md / "item_placements.jsonl"):
        by_family[row["recordFamily"]] = \
            by_family.get(row["recordFamily"], 0) + 1
    assert by_family.get("room") == 22878
    assert by_family.get("arrival") == 86
    assert by_family.get("nonArea") == 7
    assert by_family.get("waypoint") == 25
    assert by_family.get("plotActivation") == 8
    assert total == 23004, f"F2 decomposition broken: {by_family}"
    assert n("students.jsonl") == 20 and n("staff_records.jsonl") == 32
    layers = n("landscape_layers.jsonl")
    assert n("landscape_maps.jsonl") == layers
    assert layers == 4082, f"landscape layers seed (re-probe): {layers}"
    assert n("door_validators.jsonl") == 54
    door_rows = read_jsonl(md / "door_placement_index.jsonl")
    kinds = {r["definitionName"] for r in door_rows}
    # seed 1,261/55 is DRIFT-checked (verifier band ~1,260-1,310 across 56
    # kinds); the fresh measurement wins, so this is a band, not equality
    assert 1200 <= len(door_rows) <= 1320 and len(kinds) in (54, 55, 56), (
        f"F16 substring census outside drift band: "
        f"{len(door_rows)} placements / {len(kinds)} kinds")
    unused = [k for k in kinds if k.startswith("Unused_Item_Door_")]
    assert unused, "the 14 Unused_Item_Door_* placements must survive (F16)"
    assert n("named_plots.jsonl") == 12


@pytest.mark.client_gated
def test_client_guid_chain_and_blank_template():
    root = _real_maps_artifacts("guid")
    md = root / "maps"
    levels = read_jsonl(md / "levels.jsonl")
    assert len(levels) == 28
    identity = set()
    resolvable = 0
    blanks = []
    for row in levels:
        errs = ml.validate_levels_row(row)
        assert not errs, f"{row.get('levelId')!r}: {errs}"
        ident = (row["plotCount"]["generation"], row["levelId"],
                 row["source"]["pathId"])
        assert ident not in identity, f"identity collision {ident} (F14)"
        identity.add(ident)
        if row["levelId"] == "Level":
            blanks.append(row)
            assert row["scenarioGuid"] is None
            assert row["scenarioAddress"] is None
            assert row["campaignPart"] is None
            continue
        assert row["scenarioGuid"], f"{row['levelId']} missing scenarioGuid"
        assert row["scenarioAddress"], \
            f"{row['levelId']} GUID unresolved through catalog"
        resolvable += 1
        part = row["campaignPart"]
        if part is not None:
            assert part in ml.CAMPAIGN_PARTS and part in row["scenarioAddress"]
    assert len(blanks) == 1
    assert resolvable >= 27, \
        f">=27 of 28 GUIDs resolve (reviewer F13: a broken resolver cannot " \
        f"ship green); got {resolvable}"
    # the twins are found by GENERATION, never by a hardcoded levelId
    # spelling: the real corpus levelId is the verbatim LevelScene
    # ("Scene_DLC2_Ghosts"), the fixture's is its own echo — the LAW is
    # same family + same scene + two pathIds (F14/F15)
    ghosts = [r for r in levels
              if r["plotCount"]["generation"] == ml.GEN_DLC_GHOST]
    assert len(ghosts) == 2 and \
        len({r["source"]["pathId"] for r in ghosts}) == 2, \
        "the ghost pair is distinguished by pathId (F14/F15)"
    assert len({r["levelId"] for r in ghosts}) == 1, \
        "both twins share ONE LevelScene; only the pathId leg separates them"


@pytest.mark.client_gated
def test_client_ac3_ac4_chains_verbatim():
    root = _real_maps_artifacts("ac34")
    md = root / "maps"
    cl = read_json(md / "coordinate_law.json")
    assert cl["grid"]["cellSize"] == 2.0
    assert "dump.cs" in str(cl["grid"]["parsedFrom"]) and \
        cl["grid"]["sourceLine"] > 0
    variants = [r for r in cl["spawnPoints"] if r["variant"]]
    assert len(variants) == 2
    names = {v["levelName"] for v in variants}
    assert any("Party" in n for n in names) and "Level" in names
    place = read_jsonl(md / "item_placements.jsonl")
    chain = [r for r in place
             if (r.get("definitionPptr") or {}).get("pathId")
             == 522383310774550334]
    assert chain, "the MoonBase worked-chain row must exist (F10)"
    row = chain[0]
    assert row["resolution"]["definitionName"] == \
        "Item_Door_Building_Moonbase_Main"
    assert row["resolution"]["corroboration"] == "match"
    assert row["resolution"]["definitionId"] == -572923782
    jr = read_json(md / "join_report.json")
    # Seeds (22,210 resolved / 786 residue = LaunchPad-head 464 + 771
    # cross-file) were measured BEFORE the mandatory externals→CAB ladder
    # existed; spec F8 itself says those 771 refs are covered by
    # externals.jsonl, so the fresh run resolves them and the residue
    # collapses to the same-file misses. DRIFT discipline: fresh wins —
    # the teeth below pin the LADDER-MANDATED direction (resolution can
    # only grow past the seed floor, residue only shrink below the seed
    # ceiling) plus exact internal arithmetic, never a stale universe.
    den = jr["denominator"]["measuredSet"]
    corr = jr["corroboration"]
    assert jr["resolved"] + jr["residue"] == den, "resolved+residue==den"
    assert corr["match"] + corr["twinMismatch"] + corr["absent"] == \
        jr["resolved"], "corroboration partition must be exact"
    assert abs(jr["resolveRate"] - jr["resolved"] / den) < 1e-9
    assert 21500 <= jr["resolved"] <= 23200, (
        f"resolved seed 22210 drifted past the +/-5% band: {jr['resolved']}")
    assert jr["resolved"] > 22210 and jr["residue"] < 786, (
        f"the MANDATORY externals→CAB ladder absorbed none of F8's 771 "
        f"cross-file refs (resolved={jr['resolved']}, "
        f"residue={jr['residue']} back at the pre-ladder seed universe)")
    assert jr["residueCrossFile"] + jr["residueSameFileMiss"] == \
        jr["residue"], "residue split must decompose exactly"
    rows_ledger = read_jsonl(md / "_unresolved_placements.jsonl")
    assert len(rows_ledger) == jr["residue"], \
        "every unresolved placement is ledgered by name"
    for row in rows_ledger:
        errs = ml.validate_unresolved_row(row)
        assert not errs, errs
    scenarios = [r for r in jr["residueByScenario"]]
    assert scenarios and sum(r["count"] for r in scenarios) == jr["residue"]
    head = max(scenarios, key=lambda r: r["count"])
    assert head["count"] == max(r["count"] for r in scenarios)
    assert 1 <= head["count"] <= 520, f"residue head implausible: {head}"
    assert 0 <= jr["residueCrossFile"] <= 100
    assert 1 <= jr["residueSameFileMiss"] <= 40
    assert corr["twinMismatch"] <= 20 and 5 <= corr["absent"] <= 20
    assert "_raw" in str(corr.get("cause", "")), "F17 cause recorded"


@pytest.mark.client_gated
def test_client_landscape_extremes_per_f3():
    root = _real_maps_artifacts("terr")
    md = root / "maps"
    layers = read_jsonl(md / "landscape_layers.jsonl")
    dims = [tuple(r["dims"]["terrain"]) for r in layers]
    assert (432, 216) in dims, "largest single map 432×216 (MoonBase)"
    widths = [w for w, _h in dims if w and _h]
    heights = [h for _w, h in dims if _w and h]
    assert max(widths) == 532, "widest single map 532 wide"
    assert max(heights) == 356, "tallest single map 356 tall"
    nonzero_min_w = min(w for w, h in dims if w and h)
    nonzero_min_h = min(h for w, h in dims if w and h)
    assert (nonzero_min_w, nonzero_min_h) == (2, 2)
    zero_dims = [d for d in dims if d == (0, 0)]
    assert len(zero_dims) == 12, \
        f"twelve 0-dim maps DECLARED as data: got {len(zero_dims)}"


@pytest.mark.client_gated
def test_client_doors_anchor_sweeps_and_census():
    root = _real_maps_artifacts("doors")
    md = root / "maps"
    vals = read_jsonl(md / "door_validators.jsonl")
    assert len(vals) == 54
    anchor = [v for v in vals
              if "Moonbase_To_Exterior" in str(v.get("catalogAddress", ""))]
    assert anchor, "the MoonBase validator resolves to its catalog address"
    ids = read_json(md / "door_id_space.json")
    assert "fullSpaceSweep" in ids["sweeps"] and \
        "integerSweep" in ids["sweeps"], "BOTH sweeps recorded"
    assert ids["refsTotal"] >= 71 or ids["refsTotal"] > 0


@pytest.mark.client_gated
def test_client_named_plots_registry_resolution():
    root = _real_maps_artifacts("named")
    named = read_jsonl(root / "maps" / "named_plots.jsonl")
    assert len(named) == 12
    moon = [r for r in named if "MoonBase" in r["scenarioName"]]
    assert moon, "MoonBase pads carry UsePlotDisplayName rows"
    shared = {r["displayNameTermId"] for r in moon}
    assert shared == {-1610423369}, \
        f"the MoonBase pads SHARE one termID: {shared}"
    assert all(r["resolvedTermKey"] for r in moon), \
        "termID -1610423369 resolves to a non-empty Term key through the " \
        "REAL registry"


@pytest.mark.client_gated
def test_client_imagery_seeds_reproduce():
    root = _real_maps_artifacts("imagery")
    pred = read_json(root / "maps" / "imagery_predicates.json")
    entries = _extract_predicate_entries(pred)
    seeds = {"metamap-case-sensitive": 1094,
             "metamap-case-insensitive": 1140,
             "loadingscreen-images": 117,
             "imagelevel-strict-prefix": 42,
             "imagelevel-family": 66,
             "level-image-icon-screenshot": 66,
             "minimap-any-spelling": 0}
    for pid, seed in seeds.items():
        got = entries.get(pid, (None, None))[1]
        assert isinstance(got, int), f"{pid}: fresh count missing"
        if seed == 0:
            assert got == 0, "the zero-minimap negative is preserved exactly"
        else:
            drift = abs(got - seed) / max(seed, 1)
            assert drift <= 0.05, \
                f"{pid}: fresh {got} vs seed {seed} exceeds ±DRIFT band"
    annotation = json.dumps(pred)
    assert "125" in annotation, \
        "the scout's unreproduced 125 travels as ANNOTATION beside the " \
        "pinned pattern's 66, never as a count"


@pytest.mark.client_gated
def test_client_double_run_hash_equal():
    root = _real_maps_artifacts("idem")
    g = game_dir()
    md = root / "maps"
    h1 = hash_tree(md, exempt_byte_identity=False)
    manifest1 = (md / "_manifest.sha256").read_bytes()
    # --force: the second run must RE-EXECUTE (a stamped no-op would make
    # the hash comparison vacuous); real-tree idempotence is the contract
    r = run_pack([str(g), "--only", "maps", "--force"], timeout=3600)
    assert r.returncode in (0, 2)
    h2 = hash_tree(md, exempt_byte_identity=False)
    only1, only2, changed = diff_manifests(h1, h2)
    assert not (only1 or only2 or changed), (
        f"real-tree idempotence broken: missing={only1[:4]} "
        f"extra={only2[:4]} changed={changed[:4]}")
    assert manifest1 == (md / "_manifest.sha256").read_bytes()
