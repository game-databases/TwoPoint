"""piece-03 prepared-tree builder + fixture oracle (stage `maps`, spec Rev 3).

Synthetic bytes ONLY — never real game data. Materializes the §3 upstream
set the maps stage reads:

  harvest/monobehaviours/**   TPC.LevelScenarioV2 ×2 · TPC.LevelConfig ×28
                              (the REAL 13/9/4/2 family split) ·
                              TPC.ItemValidator_Door ×2 ·
                              TPC.LandscapeBrushDatabase ×1 +
                              TPC.LandscapeBrushDefinition ×2 ·
                              GameItem{,Lite,Variation}Definition ×6 ·
                              widening-class + archetype/staff defs ·
                              TPC.UniversityLevelConfig ×1 (ledgered
                              out-of-scope)
  harvest/export-manifest.jsonl (+ externals.jsonl)
  relinks/bridges/{cab_index,container_index}.jsonl   (landed shapes,
                              synthesized because fixtures cannot run
                              stage 6; consumed READ-ONLY by stage 7)
  relinks/i2_term_registry.jsonl                       (landed shape)
  addressables/catalog.json   bundle-kind + guid-kind keys + the imagery
                              predicate address set
  decompiled/il2cppdumper/dump.cs   SLICE: GridCoord consts +
                              EPlotTileType + <LoadAssets>d__532 (no body)

Every value below is a measured-shape ECHO at fixture scale (spec §8):
the F10 arithmetic (-152 + 17 => -135), the F14 empty-m_Name law, the F16
substring-vs-anchored door split, the F17 absent-corroboration cause, the
R4 twin policy. Numbers are fixture-local; contracts are shapes.

Deterministic + timestamp-free so double-run hash legs mean something.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _fixturelib as fx  # noqa: E402
from _validators import BUILD_ID, write_jsonl  # noqa: E402

# --- bundles / serialized files -------------------------------------------------

B_SCEN_A = "configs_assets_all.bundle"                    # axis base
B_SCEN_B = "dlc-space-configs_assets_all.bundle"          # axis dlc-space
B_ITEMS = "items-general_assets_all.bundle"               # cross-file target
DIR_SCEN_A = "configs"
DIR_SCEN_B = "dlc-space-configs"
DIR_ITEMS = "items-general"
STEM_SCEN_A = "configs_assets_all"
STEM_SCEN_B = "dlc-space-configs_assets_all"
STEM_ITEMS = "items-general_assets_all"

CAB_SCEN_A = "CAB-mapsscena"
CAB_ITEMS_A = "CAB-mapsitemsa"
CAB_ITEMS_B = "CAB-mapsitemsb"
CAB_DANGLING = "CAB-mapsdangling"

# --- signed pathIds --------------------------------------------------------------

PID_DOOR_MAIN = 522383310774550334     # F10 echo (same-file resolution)
PID_UNUSED_DOOR = 4000000000000000207
PID_PLAIN = 4000000000000000208        # GameItemLiteDefinition
PID_CROSS = -4000000000000000201       # fileId 1 -> CAB_ITEMS_A
PID_TWIN = 4000000000000000202         # fileId 2 -> CAB_ITEMS_B (mismatch)
PID_RAWONLY = 4000000000000000203      # fileId 3 -> CAB_ITEMS_A (undecoded)
PID_UNRESOLVED = 4000000000000000204   # fileId 4 -> dangling cab
PID_SAMEMISS = 4000000000000000205     # fileId 0, nothing indexed there
PID_WIDE = 4000000000000000206         # resolves ONLY via widened class
PID_ARCH = 4000000000000000301
PID_STAFFDEF = 4000000000000000302
PID_BRUSH_DB = 4000000000000000401
PID_BRUSH_1 = 4000000000000000411
PID_BRUSH_2 = 4000000000000000412
# room-TYPE family dumps feeding the M5 dual id-space sweep (integer _id
# space; disjoint from room-instance uniqueIds by construction)
PID_ROOMTYPE_1 = 4000000000000000501
PID_ROOMTYPE_2 = 4000000000000000502
PID_ROOMTYPE_B_1 = 4000000000000000511
ROOMTYPE_IDS = (-39494005, -1741033445, -557321420)   # cover 3 of 4 refs
PID_UNIVERSITY = -6500000000000000001
PID_VALIDATOR_1 = -6600000000000000001
PID_VALIDATOR_2 = -6600000000000000002
PID_SCEN_ALPHA = -7000000000000000001
PID_SCEN_BETA = -7000000000000000002

WIDENED_CLASS = "TPC.PlotPropDefinition"

# --- ids / terms -----------------------------------------------------------------

DEF_ID_DOOR_MAIN = -572923782          # F10 echo
DEF_ID_CROSS = -572923783
DEF_ID_TWIN_RECORD = -572923784        # what the RECORD claims
DEF_ID_TWIN_TARGET = -999999001        # what the resolved Variation says
DEF_ID_RAWONLY = -572923785            # unreadable: target ships _raw only
DEF_ID_WIDE = -572923789
DEF_ID_UNUSED_DOOR = -572923787
DEF_ID_PLAIN = -572923788

TERM_PAD_SHARED = -1610423369          # F13 verbatim termID (shared pads)
TERM_PAD_KEY = "Levels/MoonBase/Rocket_Pad"
TERM_MISS = -1610423370                # registry miss -> absence row
TERM_STUDENT = 20011

GUID_VALIDATOR = "cc00000000000000000000000000d001"
ADDR_VALIDATOR = ("Assets/Data/DLCs/DLC1_Space/Game/Items/Validators/"
                  "ItemValidator_Door_Fixture_To_Exterior.asset")

ROOM_UID_A = 101
ROOM_UID_B = 102

SCEN_ALPHA = "LevelScenarioV2_FixtureAlpha"
SCEN_ALPHA_RECORD = "FixtureAlpha"
SCEN_BETA = "LevelScenarioV2_FixtureBeta"
SCEN_BETA_RECORD = "FixtureBeta"

FLOAT_TRAP = -0.00016784668             # AC6 float round-trip sentinel

# --- LevelConfigs: the real 13/9/4/2 generation split ----------------------------

GEN_LEVELS_PREFABS = "levels-prefabs"
GEN_CONFIGS_ASSETS_ALL = "configs-assets-all"
GEN_DLC_SPACE = "dlc-space-configs"
GEN_DLC_GHOST = "dlc-ghost-configs"
GENERATION_ENUM = (GEN_LEVELS_PREFABS, GEN_CONFIGS_ASSETS_ALL,
                   GEN_DLC_SPACE, GEN_DLC_GHOST)

FAMILY_LP = "configs-levels-prefabs"
FAMILY_CA = "configs"
FAMILY_DS = "dlc-space-configs"
FAMILY_DG = "dlc-ghost-configs"
STEM_BY_FAMILY = {
    FAMILY_LP: "configs-levels-prefabs_assets_all",
    FAMILY_CA: STEM_SCEN_A,
    FAMILY_DS: STEM_SCEN_B,
    FAMILY_DG: "dlc-ghost-configs_assets_all",
}

SPAWN_CONST = {"x": -66.0, "y": 0.0, "z": -24.0}
SPAWN_BLANK = {"x": -68.0, "y": 0.0, "z": -24.0}       # deviant 1 (x)
SPAWN_PARTY = {"x": -66.0, "y": 2.08646, "z": -24.0}   # deviant 2 (y)
EXTENT_STD = {"center": {"x": 0.0, "y": 0.0, "z": 0.0},
              "extent": {"x": 200.0, "y": 16.0, "z": 200.0}}
EXTENT_BLANK = {"center": {"x": 0.0, "y": 0.0, "z": 0.0},
                "extent": {"x": 128.0, "y": 10.0, "z": 128.0}}

ICON_CAMERA = {"cameraDistance": 0.0, "cameraFov": 10.0,
               "cameraRotation": {"x": -30.0, "y": 45.0, "z": 10.0},
               "textureSize": 128}


def _guid(n: int) -> str:
    return f"{(n & 0xFFFFFFFFFFFFFFFF):016x}{(0xC0FFEE ^ (n & 0xFFFF)):016x}"


def _addr_story(level: str, part: str) -> str:
    return f"Assets/Data/Game/Levels/Final/{part}/{level}.asset"


def _addr_remix(level: str, n: int) -> str:
    return f"Assets/Data/Game/Levels/Remix/Remix_{n}/{level}.asset"


# (familyDir, levelId, plotCount, part|None, guid|None, pathId, spawn, bounds)
LEVEL_CONFIGS = [
    # levels-prefabs: 12 playable + blank template = 13 rows
    (FAMILY_LP, "TutorialLevel", 5, "Part1_Early", None,
     -6100000000000000001, SPAWN_CONST, EXTENT_STD),
    (FAMILY_LP, "MittonLevel", 9, "Part1_Early", None,
     6100000000000000002, SPAWN_CONST, EXTENT_STD),
    (FAMILY_LP, "KnightLevel", 7, "Part2_Mid1", None,
     -6100000000000000003, SPAWN_CONST, EXTENT_STD),
    (FAMILY_LP, "MagicLevel", 7, "Part2_Mid1", None,
     6100000000000000004, SPAWN_CONST, EXTENT_STD),
    (FAMILY_LP, "ArchaeologyLevel", 7, "Part2_Mid1", None,
     -6100000000000000005, SPAWN_CONST, EXTENT_STD),
    (FAMILY_LP, "GastronomyLevel", 10, "Part2_Mid2", None,
     6100000000000000006, SPAWN_CONST, EXTENT_STD),
    (FAMILY_LP, "RoboticsLevel", 10, "Part2_Mid2", None,
     -6100000000000000007, SPAWN_CONST, EXTENT_STD),
    (FAMILY_LP, "SportsLevel", 6, "Part1_Early", None,
     6100000000000000008, SPAWN_CONST, EXTENT_STD),
    (FAMILY_LP, "SpyLevel", 10, "Part3_LateGame", None,
     -6100000000000000009, SPAWN_CONST, EXTENT_STD),
    (FAMILY_LP, "PerformingArtsLevel", 7, "Part3_LateGame", None,
     6100000000000000010, SPAWN_CONST, EXTENT_STD),
    (FAMILY_LP, "PartyLevel", 5, "Part3_LateGame", None,
     -6100000000000000011, SPAWN_PARTY, EXTENT_STD),
    (FAMILY_LP, "FinalLevel", 1, "Part3_LateGame", None,
     6100000000000000012, SPAWN_CONST, EXTENT_STD),
    # blank template: m_Name "", LevelScene "Level", PlotCount 0,
    # NO _ScenarioV2 GUID, (128,10,128) bounds, x=-68 spawn deviant (F4/F14)
    (FAMILY_LP, "Level", 0, None, None, -6100000000000000013,
     SPAWN_BLANK, EXTENT_BLANK),
    # configs_assets_all: 9 rows, EVERY one a Remix carrier incl. the
    # KnightLevel REMIX twin (PlotCount disagrees 7 vs 5 — BOTH ride, R4.2)
    (FAMILY_CA, "KnightLevel", 5, None, None, -6200000000000000001,
     SPAWN_CONST, EXTENT_STD),
    (FAMILY_CA, "RemixLevelOne", 6, None, None, -6200000000000000002,
     SPAWN_CONST, EXTENT_STD),
    (FAMILY_CA, "RemixLevelTwo", 6, None, None, -6200000000000000003,
     SPAWN_CONST, EXTENT_STD),
    (FAMILY_CA, "RemixLevelThree", 8, None, None, -6200000000000000004,
     SPAWN_CONST, EXTENT_STD),
    (FAMILY_CA, "RemixLevelFour", 6, None, None, -6200000000000000005,
     SPAWN_CONST, EXTENT_STD),
    (FAMILY_CA, "RemixLevelFive", 7, None, None, -6200000000000000006,
     SPAWN_CONST, EXTENT_STD),
    (FAMILY_CA, "RemixLevelSix", 6, None, None, -6200000000000000007,
     SPAWN_CONST, EXTENT_STD),
    (FAMILY_CA, "RemixLevelSeven", 9, None, None, -6200000000000000008,
     SPAWN_CONST, EXTENT_STD),
    (FAMILY_CA, "RemixLevelEight", 6, None, None, -6200000000000000009,
     SPAWN_CONST, EXTENT_STD),
    # dlc-space-configs: 4 rows (DLC1 carriers + Test/SpaceLevel analog)
    (FAMILY_DS, "SpaceportCityLevel", 18, None, None, -6300000000000000001,
     SPAWN_CONST, EXTENT_STD),
    (FAMILY_DS, "LaunchPadLevel", 11, None, None, -6300000000000000002,
     SPAWN_CONST, EXTENT_STD),
    (FAMILY_DS, "MoonBaseLevel", 15, None, None, -6300000000000000003,
     SPAWN_CONST, EXTENT_STD),
    (FAMILY_DS, "SpaceTestLevel", 3, None, None, -6300000000000000004,
     SPAWN_CONST, EXTENT_STD),
    # dlc-ghost-configs: the TWIN PAIR — same levelId, same family,
    # distinct pathIds (the F14 identity-triple case)
    (FAMILY_DG, "GhostsLevel", 15, None, None, -6400000000000000001,
     SPAWN_CONST, EXTENT_STD),
    (FAMILY_DG, "GhostsLevel", 15, None, None, -6400000000000000002,
     SPAWN_CONST, EXTENT_STD),
]

GUID_BY_PID = {
    -6100000000000000001: (_guid(0xA001), _addr_story("TutorialLevel", "Part1_Early")),
    6100000000000000002: (_guid(0xA002), _addr_story("MittonLevel", "Part1_Early")),
    -6100000000000000003: (_guid(0xA003), _addr_story("KnightLevel", "Part2_Mid1")),
    6100000000000000004: (_guid(0xA004), _addr_story("MagicLevel", "Part2_Mid1")),
    -6100000000000000005: (_guid(0xA005), _addr_story("ArchaeologyLevel", "Part2_Mid1")),
    6100000000000000006: (_guid(0xA006), _addr_story("GastronomyLevel", "Part2_Mid2")),
    -6100000000000000007: (_guid(0xA007), _addr_story("RoboticsLevel", "Part2_Mid2")),
    6100000000000000008: (_guid(0xA008), _addr_story("SportsLevel", "Part1_Early")),
    -6100000000000000009: (_guid(0xA009), _addr_story("SpyLevel", "Part3_LateGame")),
    6100000000000000010: (_guid(0xA00A), _addr_story("PerformingArtsLevel", "Part3_LateGame")),
    -6100000000000000011: (_guid(0xA00B), _addr_story("PartyLevel", "Part3_LateGame")),
    6100000000000000012: (_guid(0xA00C), _addr_story("FinalLevel", "Part3_LateGame")),
    -6200000000000000001: (_guid(0xB001), _addr_remix("KnightLevel", 3)),
    -6200000000000000002: (_guid(0xB002), _addr_remix("RemixLevelOne", 1)),
    -6200000000000000003: (_guid(0xB003), _addr_remix("RemixLevelTwo", 2)),
    -6200000000000000004: (_guid(0xB004), _addr_remix("RemixLevelThree", 4)),
    -6200000000000000005: (_guid(0xB005), _addr_remix("RemixLevelFour", 5)),
    -6200000000000000006: (_guid(0xB006), _addr_remix("RemixLevelFive", 6)),
    -6200000000000000007: (_guid(0xB007), _addr_remix("RemixLevelSix", 7)),
    -6200000000000000008: (_guid(0xB008), _addr_remix("RemixLevelSeven", 8)),
    -6200000000000000009: (_guid(0xB009), _addr_remix("RemixLevelEight", 9)),
    -6300000000000000001: (_guid(0xC001),
                           "Assets/Data/DLCs/DLC1_Space/Game/Levels/Final/"
                           "SpaceportCity/SpaceportCityLevel.asset"),
    -6300000000000000002: (_guid(0xC002),
                           "Assets/Data/DLCs/DLC1_Space/Game/Levels/Final/"
                           "LaunchPad/LaunchPadLevel.asset"),
    -6300000000000000003: (_guid(0xC003),
                           "Assets/Data/DLCs/DLC1_Space/Game/Levels/Final/"
                           "MoonBase/MoonBaseLevel.asset"),
    -6300000000000000004: (_guid(0xC004),
                           "Assets/Data/DLCs/DLC1_Space/Test/SpaceLevel/"
                           "SpaceTestLevel.asset"),
    -6400000000000000001: (_guid(0xD001),
                           "Assets/Data/DLCs/DLC2_Ghost/Game/Levels/"
                           "LevelScenarioV2_Ghosts.asset"),
    -6400000000000000002: (_guid(0xD002),
                           "Assets/Data/DLCs/DLC2_Ghost/Game/Levels/"
                           "Remix_Ghost/Ghosts_Remix_V2.asset"),
}

CAMPAIGN_PARTS = ("Part1_Early", "Part2_Mid1", "Part2_Mid2", "Part3_LateGame")


def generation_of(family_dir: str) -> str:
    return {
        FAMILY_LP: GEN_LEVELS_PREFABS,
        FAMILY_CA: GEN_CONFIGS_ASSETS_ALL,
        FAMILY_DS: GEN_DLC_SPACE,
        FAMILY_DG: GEN_DLC_GHOST,
    }[family_dir]


def level_config_dump(spec) -> dict:
    """Top-level payload (P1: NO _levelRecord on TPC.LevelConfig); m_Name
    EMPTY on ALL rows (F14 law); WorldBounds spelled m_Center/m_Extent like
    the real corpus."""
    family, level_scene, plot_count, _part, _g, pid, spawn, bounds = spec
    stem = STEM_BY_FAMILY.get(family, f"{family}_assets_all")
    obj = {
        "_decoded": {"method": "typetree+synthesis", "typetreeDecoded": True},
        "_scriptClass": "TPC.LevelConfig",
        "_sourceFile": f"{stem}_{pid}.json".lower(),
        "m_Name": "",
        "LevelScene": level_scene,
        "LevelScene_Optimized": f"{level_scene}_Optimised",
        "LevelHUDScene": None,
        "LevelDatabaseScene": None,
        "PlotCount": plot_count,
        "WorldBounds": {"m_Center": dict(bounds["center"]),
                        "m_Extent": dict(bounds["extent"])},
        "SpawnPoint": dict(spawn),
        "IconRenderCamera": json.loads(json.dumps(ICON_CAMERA)),
        "IsDebug": 1 if level_scene == "SpaceTestLevel" else 0,
    }
    g = GUID_BY_PID.get(pid)
    if g is not None:
        obj["_ScenarioV2"] = {"m_AssetGUID": g[0], "m_SubObjectName": "",
                              "m_SubObjectType": ""}
    return obj


# --- scenario payloads ------------------------------------------------------------


def _tiles(w, h):
    return {"_width": w, "_height": h,
            "_saveData": [1 if (i % 7) < 5 else 0 for i in range(w * h)]}


def _terrain_map(w, h):
    """Observed value patterns 0/16/20 (F14); deterministic mixture."""
    vals = [16 if (i % 37) < 3 else (20 if (i % 53) < 2 else 0)
            for i in range(w * h)]
    return {"_width": w, "_height": h, "_saveData": vals}


def _empty_map():
    return {"_width": 0, "_height": 0, "_saveData": []}


def _loc(dev, term_id):
    return {"_dev": dev, "_termID": term_id}


def _item(def_id, fid, pid, x, y, z, rot=90.0, layer=-1, flags=0):
    return {"CustomisationSwatchIndex": 0, "DefinitionID": def_id,
            "Definition": {"m_FileID": fid, "m_PathID": pid},
            "GeneralParamInt1": 0, "ItemFlags": flags,
            "LocalPosition": {"x": x, "y": y, "z": z},
            "LocalPosition2": {"x": 0.0, "y": 0.0, "z": 0.0},
            "LocalRotation": rot, "PlotLayer": layer}


def _layer(flags, room_id, terrain, objmap, attr):
    return {"PlotLayerFlags": flags, "RoomRecordID": room_id,
            "LandscapeRecord": {"TerrainMap": terrain,
                                "LandscapeObjectMap": objmap,
                                "AttributeMap": attr}}


def scenario_alpha_payload() -> dict:
    rooms = [
        # Anchor is a GridCoord: the REAL dumps spell its legs X/Y (F7)
        {"UniqueID": ROOM_UID_A, "Anchor": {"X": 2, "Y": 2},
         "WorldPosition": {"x": -152.0, "y": FLOAT_TRAP, "z": -116.0},
         "DefinitionID": -690496154,
         "Definition": {"m_FileID": 0, "m_PathID": None},
         "Tiles": _tiles(9, 20), "PlotLayer": 3, "ChildRoomRecordIDs": [],
         "VisualOverrideIDFloor": 0, "VisualOverrideIDWall": 0,
         "ItemRecords": [
             # 0: same-file resolved match; door substring hit;
             #    F10 arithmetic echo (-152 + 17 => world x -135)
             _item(DEF_ID_DOOR_MAIN, 0, PID_DOOR_MAIN, 17.0, 0.0, 33.0),
             # 1: cross-file via externals fileId 1 -> CAB_ITEMS_A (match)
             _item(DEF_ID_CROSS, 1, PID_CROSS, 3.0, 0.0, 4.0),
             # 2: resolves to a Variation twin whose _id DISAGREES
             _item(DEF_ID_TWIN_RECORD, 2, PID_TWIN, 5.0, 0.0, 6.0),
             # 3: resolves to an UNDECODED _raw-only dump -> absent
             _item(DEF_ID_RAWONLY, 3, PID_RAWONLY, 7.0, 0.0, 8.0),
             # 4: cross-file attempt into a cab no bridge row knows
             _item(-572923786, 4, PID_UNRESOLVED, 9.0, 0.0, 10.0),
             # 5: same-file miss (nothing indexed at that pathId)
             _item(-572923786, 0, PID_SAMEMISS, 11.0, 0.0, 12.0),
             # 6: resolves ONLY through the widened class sweep
             _item(DEF_ID_WIDE, 0, PID_WIDE, 13.0, 0.0, 14.0),
         ]},
        {"UniqueID": ROOM_UID_B, "Anchor": {"X": 12, "Y": 9},
         "WorldPosition": {"x": 10.0, "y": 0.0, "z": 20.0},
         "DefinitionID": -690496155,
         "Definition": {"m_FileID": 0, "m_PathID": None},
         "Tiles": _tiles(4, 5), "PlotLayer": 2, "ChildRoomRecordIDs": [],
         "VisualOverrideIDFloor": 0, "VisualOverrideIDWall": 0,
         "ItemRecords": [
             # the F16 case: an Unused_Item_Door_* placement the anchored
             # form would DROP (name carries the leading Unused_)
             _item(DEF_ID_UNUSED_DOOR, 0, PID_UNUSED_DOOR, 1.0, 0.0, 2.0,
                   rot=0.0),
             _item(DEF_ID_PLAIN, 0, PID_PLAIN, 2.0, 0.0, 3.0, rot=270.0),
         ]},
    ]
    plots = [
        {"PlotUniqueId": 15, "PersistentName": "Plot 15",
         "DefinitionID": -1165001501,
         "Definition": {"m_FileID": 0, "m_PathID": None},
         "Bounds": {"m_Center": {"x": -141.0, "y": FLOAT_TRAP, "z": -92.0},
                    "m_Extent": {"x": 15.0, "y": 0.0, "z": 28.0}},
         "Locked": 0, "InitiallyBuilt": 0, "BuildCost": 55000,
         "BuildCostBuiltup": 60000, "IgnoreForCameraBounds": 0,
         "UsePlotDisplayName": 1,
         "DisplayName": _loc("Rocket Pad A", TERM_PAD_SHARED),
         "TileTypes": _tiles(15, 28),
         "PlotLayerRecords": [
             # P6 echo: plot[0] layer[0] TerrainMap 30×56 (1680 ints)
             _layer(3, ROOM_UID_A, _terrain_map(30, 56),
                    _terrain_map(30, 56), [_terrain_map(1, 1)] * 2),
             # a 0-dim layer row is DATA, never a violation (AC2/F3)
             _layer(0, None, _empty_map(), _empty_map(), []),
         ],
         "PlotActivationItemRecords": [
             _item(DEF_ID_DOOR_MAIN, 0, PID_DOOR_MAIN, 0.0, 0.0, 0.0,
                   rot=0.0)],
         "NoNavigation": 0, "AllowWeeds": 1},
        {"PlotUniqueId": 16, "PersistentName": "Plot 16",
         "DefinitionID": -1165001502,
         "Definition": {"m_FileID": 0, "m_PathID": None},
         "Bounds": {"m_Center": {"x": -100.0, "y": FLOAT_TRAP, "z": -60.0},
                    "m_Extent": {"x": 8.0, "y": 0.0, "z": 9.0}},
         "Locked": 0, "InitiallyBuilt": 1, "BuildCost": 42000,
         "IgnoreForCameraBounds": 0,
         "UsePlotDisplayName": 1,
         "DisplayName": _loc("Rocket Pad B", TERM_PAD_SHARED),  # SHARED id
         "TileTypes": _tiles(4, 4),
         "PlotLayerRecords": [
             _layer(1, None, _terrain_map(2, 2), _terrain_map(2, 2), [])],
         # second activation array whose itemIndex collides with PLOT 15's
         # under ANY global key — passes only under the pinned per-family
         # key (scenarioName, plotActivation, plotUniqueId, itemIndex) (F7)
         "PlotActivationItemRecords": [
             _item(DEF_ID_DOOR_MAIN, 0, PID_DOOR_MAIN, 1.0, 0.0, 1.0,
                   rot=0.0)],
         "NoNavigation": 0, "AllowWeeds": 1},
        {"PlotUniqueId": 17, "PersistentName": "Plot 17",
         "DefinitionID": -1165001503,
         "Definition": {"m_FileID": 0, "m_PathID": None},
         "Bounds": {"m_Center": {"x": -50.0, "y": FLOAT_TRAP, "z": -30.0},
                    "m_Extent": {"x": 6.0, "y": 0.0, "z": 7.0}},
         "Locked": 0, "InitiallyBuilt": 0, "BuildCost": 31000,
         "IgnoreForCameraBounds": 0,
         "UsePlotDisplayName": 1,
         "DisplayName": _loc("", TERM_MISS),                 # registry MISS
         "TileTypes": _tiles(3, 3),
         "PlotLayerRecords": [],
         "PlotActivationItemRecords": [],
         "NoNavigation": 0, "AllowWeeds": 1},
        {"PlotUniqueId": 18, "PersistentName": "Plot 18",
         "DefinitionID": -1165001504,
         "Definition": {"m_FileID": 0, "m_PathID": None},
         "Bounds": {"m_Center": {"x": -20.0, "y": FLOAT_TRAP, "z": -10.0},
                    "m_Extent": {"x": 5.0, "y": 0.0, "z": 5.0}},
         "Locked": 0, "InitiallyBuilt": 0, "BuildCost": 12000,
         "IgnoreForCameraBounds": 0,
         "UsePlotDisplayName": 0,
         "DisplayName": None,                                 # generic plot
         "TileTypes": _tiles(2, 2),
         "PlotLayerRecords": [],
         "PlotActivationItemRecords": [],
         "NoNavigation": 0, "AllowWeeds": 1},
    ]
    record = {
        "ScenarioName": SCEN_ALPHA_RECORD,
        "Version": 3,
        "NextPlotUniqueId": 19,
        "MinimumHeightForCameraFocus": 8.0,
        "PlotRecords": plots,
        "RoomRecords": rooms,
        "ArrivalItemRecords": [
            _item(DEF_ID_PLAIN, 0, PID_PLAIN, 0.5, 0.0, 1.5, rot=0.0),
            _item(DEF_ID_CROSS, 1, PID_CROSS, 2.5, 0.0, 3.5, rot=180.0),
        ],
        "NonAreaItemRecords": [
            _item(DEF_ID_PLAIN, 0, PID_PLAIN, 4.5, 0.0, 5.5, rot=45.0),
        ],
        "NavPlotWaypointRecords": [
            _item(DEF_ID_PLAIN, 0, PID_PLAIN, 6.5, 0.0, 7.5, rot=0.0),
        ],
        "StudentRecords": [
            {"Archetype": {"m_FileID": 0, "m_PathID": PID_ARCH},
             "FirstName": _loc("Al", TERM_STUDENT),
             "LastName": _loc("Beta", 0),      # _termID 0 SENTINEL verbatim
             "LearningRate": 3, "Sex": 1},
            {"Archetype": {"m_FileID": 0, "m_PathID": None},
             "FirstName": _loc("Cy", 0),
             "LastName": _loc("Delta", TERM_STUDENT),
             "LearningRate": 2, "Sex": 0},
        ],
        "StaffGenerationRecord": {"StaffRecords": [
            {"Definition": {"m_FileID": 0, "m_PathID": PID_STAFFDEF},
             "Qualifications": ["Cooking"], "QualificationLevels": [2],
             "Rank": 3},
            {"Definition": {"m_FileID": 0, "m_PathID": None},
             "Qualifications": [], "QualificationLevels": [], "Rank": 1},
        ]},
    }
    return {
        "_decoded": {"method": "typetree+synthesis", "typetreeDecoded": True},
        "_scriptClass": "TPC.LevelScenarioV2",
        # landed shape: _sourceFile names the OWNING SERIALIZED FILE (the
        # CAB), not the dump filename — externals.jsonl is keyed by it and
        # the M3 cross-file ladder resolves through that key
        "_sourceFile": CAB_SCEN_A.lower(),
        "_id": -880000001,
        "m_Name": SCEN_ALPHA,
        "m_GameObject": {"m_FileID": 0, "m_PathID": 0},
        "m_Script": {"m_FileID": 1, "m_PathID": -7280612792328863924},
        "_levelRecord": record,
    }


def scenario_beta_payload() -> dict:
    """The near-empty scenario: header fields only, every record array
    empty — zero-row tolerance leg."""
    return {
        "_decoded": {"method": "typetree+synthesis", "typetreeDecoded": True},
        "_scriptClass": "TPC.LevelScenarioV2",
        "_sourceFile": "cab-mapsscenb",   # landed shape: serialized-file CAB
        "_id": -880000002,
        "m_Name": SCEN_BETA,
        "m_GameObject": {"m_FileID": 0, "m_PathID": 0},
        "m_Script": {"m_FileID": 1, "m_PathID": -7280612792328863924},
        "_levelRecord": {
            "ScenarioName": SCEN_BETA_RECORD,
            "Version": 1,
            "NextPlotUniqueId": 0,
            "PlotRecords": [], "RoomRecords": [], "ArrivalItemRecords": [],
            "NonAreaItemRecords": [], "NavPlotWaypointRecords": [],
            "StudentRecords": [],
            "StaffGenerationRecord": {"StaffRecords": []},
        },
    }


# --- definition / validator / brush dumps -----------------------------------------

def item_definition_dumps():
    """(bundle, familyDir, stem, cls, pathId, payload-fields) tuples."""
    scen = (B_SCEN_A, DIR_SCEN_A, STEM_SCEN_A)
    items = (B_ITEMS, DIR_ITEMS, STEM_ITEMS)
    return [
        (*scen, "TPC.GameItemDefinition", PID_DOOR_MAIN,
         {"_id": DEF_ID_DOOR_MAIN, "m_Name": "Item_Door_Building_Alpha_Main"}),
        (*scen, "TPC.GameItemDefinition", PID_UNUSED_DOOR,
         {"_id": DEF_ID_UNUSED_DOOR,
          "m_Name": "Unused_Item_Door_Building_Large"}),
        (*scen, "TPC.GameItemLiteDefinition", PID_PLAIN,
         {"_id": DEF_ID_PLAIN, "m_Name": "Item_Plain_Chair"}),
        (*scen, WIDENED_CLASS, PID_WIDE,
         {"_id": DEF_ID_WIDE, "m_Name": "Prop_Wide_Only"}),
        (*scen, "TPC.ArchetypeDefinition", PID_ARCH,
         {"_id": -555000001, "m_Name": "Archetype_Nerd"}),
        (*scen, "TPC.StaffDefinition", PID_STAFFDEF,
         {"_id": -555000002, "m_Name": "Staff_Assistant_Fixture"}),
        (*items, "TPC.GameItemDefinition", PID_CROSS,
         {"_id": DEF_ID_CROSS, "m_Name": "Item_Cross_File_Def"}),
        # the F17 cause: payload failed decode -> {_raw,_scriptClass,
        # _sourceFile} ONLY (no _id, no m_Name readable) -> classifier
        # emits corroboration ABSENT, never twin-mismatch
        (*items, "TPC.GameItemDefinition", PID_RAWONLY,
         {"_raw": "<synthetic undecoded payload>"}),
        (*items, "TPC.GameItemVariationDefinition", PID_TWIN,
         {"_id": DEF_ID_TWIN_TARGET, "m_Name": "Variation_Twin_Def"}),
    ]


def roomtype_dumps():
    """TPC.RoomType / TPC.RoomTypeBuilding family: integer-_id config dumps
    whose id space the M5 sweeps walk (F12: refs land in THIS space, never
    in room-definition or floor-area instance ids)."""
    return [
        ("TPC.RoomType", PID_ROOMTYPE_1,
         {"_id": ROOMTYPE_IDS[0], "m_Name": "RoomType_Fixture_A"}),
        ("TPC.RoomType", PID_ROOMTYPE_2,
         {"_id": ROOMTYPE_IDS[1], "m_Name": "RoomType_Fixture_B"}),
        ("TPC.RoomTypeBuilding", PID_ROOMTYPE_B_1,
         {"_id": ROOMTYPE_IDS[2], "m_Name": "RoomTypeBuilding_Fixture_A"}),
    ]


DOOR_VALIDATORS = [
    {   # anchor-shaped row: populated lists + message fields + GUID address
        "_id": -2114520335,
        "_entranceToRooms": [-39494005, -1741033445],   # F11 sample echo
        "_exitToRooms": [-557321420, -606574128],
        "_allowEntranceInAnyBuilding": 0, "_allowEntranceInAnyRoom": 0,
        "_allowExitToAnyBuilding": 0, "_allowExitToAnyRoom": 1,
        "InvalidEntranceMessage": _loc("Locked", -901001),
        "InvalidExitMessage": _loc("Blocked", -901002),
        "InvalidMessage": _loc("No way", -901003),
        "_assetGUID": GUID_VALIDATOR,
    },
    {   # OPTIONAL message fields ABSENT -> emitter validates without them
        "_id": -2114520336,
        "_entranceToRooms": [-1741033445],
        "_exitToRooms": [],
        "_allowEntranceInAnyBuilding": 1, "_allowEntranceInAnyRoom": 0,
        "_allowExitToAnyBuilding": 0, "_allowExitToAnyRoom": 0,
        "_assetGUID": None,
    },
]


def validator_refs():
    out = []
    for v in DOOR_VALIDATORS:
        out.extend(v["_entranceToRooms"])
        out.extend(v["_exitToRooms"])
    return sorted(set(out))


VALIDATOR_REFS = validator_refs()


def brush_dumps():
    db = ("TPC.LandscapeBrushDatabase", PID_BRUSH_DB,
          {"_id": -777000001,
           "_definitions": [{"m_FileID": 0, "m_PathID": PID_BRUSH_1},
                            {"m_FileID": 0, "m_PathID": PID_BRUSH_2}]})
    d1 = ("TPC.LandscapeBrushDefinition", PID_BRUSH_1,
          {"_id": -777000101, "ToolType": 2, "Cost": 25,
           "DisplayName": _loc("Brush One", -902001),
           "HasNoTerrain": 0, "Deprecated": 0})
    d2 = ("TPC.LandscapeBrushDefinition", PID_BRUSH_2,
          {"_id": -777000102, "ToolType": 3, "Cost": 40,
           "DisplayName": _loc("Brush Two", -902002),
           "HasNoTerrain": 1, "Deprecated": 1})
    return [db, d1, d2]


# --- dump.cs slice -----------------------------------------------------------------

DUMP_CS_LINES = [
    "// ---- fixture slice (synthetic; spellings + ordering mirror the REAL "
    "il2cppdumper output) ----",
    "",
    "// Namespace: TPS.Core.Grid",
    "[Serializable]",
    "public struct GridCoord // TypeDefIndex: 9130",
    "{",
    "	// Fields",
    "	public int X; // 0x0",
    "	public int Y; // 0x4",
    "	public const float CellSize = 2;",
    "	public const float CellSizeSq = 4;",
    "	public const float CellSizeInv = 0.5;",
    "	public const float CellSizeHalf = 1;",
    "	public static Vector3 CellSizeVec; // 0x0",
    "",
    "	// Properties",
    "	private string DebuggerDisplay { get; }",
    "",
    "	// Methods",
    "",
    "}",
    "",
    "// Namespace: TPC",
    "public enum EPlotTileType // TypeDefIndex: 18800",
    "{",
    "	// Fields",
    "	public int value__; // 0x0",
    "	public const EPlotTileType None = -1;",
    "	public const EPlotTileType Invalid = 0;",
    "	public const EPlotTileType Default = 1;",
    "	public const EPlotTileType Unbuildable = 2;",
    "	public const EPlotTileType NoNavigation = 3;",
    "	public const EPlotTileType NumTypes = 4;",
    "}",
    "",
    "// Namespace: ",
    "[CompilerGeneratedAttribute] // RVA: 0xAEF70 Offset: 0xAE570 VA: "
    "0x1800AEF70",
    "private sealed class LevelConfig.<LoadAssets>d__532 : "
    "IEnumerator<object>, IEnumerator, IDisposable // TypeDefIndex: 18952",
    "{",
    "	// Fields",
    "	private int <>1__state; // 0x10",
    "	private object <>2__current; // 0x18",
    "	public LevelConfig <>4__this; // 0x20",
    "",
    "	// Methods",
    "",
    "	[DebuggerHiddenAttribute] // RVA: 0xAEF70 Offset: 0xAE570 VA: "
    "0x1800AEF70",
    "	// RVA: 0x7E2A50 Offset: 0x7E1450 VA: 0x1807E2A50",
    "	public void .ctor(int <>1__state) { }",
    "",
    "	[DebuggerHiddenAttribute] // RVA: 0xAEF70 Offset: 0xAE570 VA: "
    "0x1800AEF70",
    "	// RVA: 0x669000 Offset: 0x667A00 VA: 0x180669000 Slot: 5",
    "	private void System.IDisposable.Dispose() { }",
    "",
    "	// RVA: 0x8D8D10 Offset: 0x8D7710 VA: 0x1808D8D10 Slot: 6",
    "	private bool MoveNext() { }",
    "}",
    "",
    "// Namespace: TPC",
    "public class LevelConfig : MonoBehaviour // TypeDefIndex: 18955",
    "{",
    "	// Fields",
    "	public string LevelScene; // 0x18",
    "	public int PlotCount; // 0x2C",
    "",
    "	// Methods",
    "",
    "	// RVA: 0xA58B10 Offset: 0xA57510 VA: 0x180A58B10",
    "	public IEnumerator LoadAssets() { }",
    "",
    "	// RVA: 0xA58BA0 Offset: 0xA575A0 VA: 0x180A58BA0",
    "	public void LoadAssetsSync() { }",
    "}",
]


def dump_cs_slice() -> str:
    return "\n".join(DUMP_CS_LINES) + "\n"


def dump_cs_line_of(fragment: str) -> int:
    """1-based line number of the first line containing `fragment`."""
    for i, ln in enumerate(DUMP_CS_LINES, 1):
        if fragment in ln:
            return i
    raise AssertionError(f"fragment not in slice: {fragment!r}")


GRID_LINE = dump_cs_line_of("public struct GridCoord")
PALETTE_LINE = dump_cs_line_of("public enum EPlotTileType")
LOADASSETS_METHOD_LINE = dump_cs_line_of("public IEnumerator LoadAssets()")
ITERATOR_LINE = dump_cs_line_of("<LoadAssets>d__532 : IEnumerator")


# --- bridges / externals / registry / catalog --------------------------------------

def _roster_relmap(extracted) -> dict:
    """Bundle FILENAME → roster relpath. Landed join shape: export-manifest
    `sourceBundle` and externals.jsonl `bundle` spell FULL ROSTER RELPATHS
    while the bridges carry bare filenames (the stage maps them back through
    the roster). Fixtures built over a cumulative tree mirror that; a bare
    fallback keeps standalone upstream builds deterministic."""
    out: dict[str, str] = {}
    p = Path(extracted) / "bundle-roster.jsonl"
    if p.is_file():
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                rel = row.get("relpath")
                if isinstance(rel, str) and rel:
                    out.setdefault(rel.replace("\\", "/").rsplit("/", 1)[-1],
                                   rel)
    return out


def externals_rows(rel=None):
    """LANDED shape: one row PER SERIALIZED FILE, sourceFile lowercase,
    bundle spelled as its roster relpath."""
    def b(name):
        return (rel or {}).get(name, name)

    def ext(fid, cab):
        return {"fileId": fid, "guid": "0" * 32,
                "path": f"archive:/{cab}", "type": 0}

    return [
        {"bundle": b(B_SCEN_A), "sourceFile": CAB_SCEN_A.lower(),
         "externals": [ext(1, CAB_ITEMS_A), ext(2, CAB_ITEMS_B),
                       ext(3, CAB_ITEMS_A), ext(4, CAB_DANGLING)]},
        {"bundle": b(B_ITEMS), "sourceFile": CAB_ITEMS_A.lower(),
         "externals": []},
        {"bundle": b(B_ITEMS), "sourceFile": CAB_ITEMS_B.lower(),
         "externals": []},
        {"bundle": b(B_SCEN_B), "sourceFile": "cab-mapsscenb",
         "externals": []},
    ]


def cab_index_rows():
    def objs(pairs):
        return [{"class": c, "pathId": p} for c, p in sorted(pairs)]

    scen_objs = [("TPC.GameItemDefinition", PID_DOOR_MAIN),
                 ("TPC.GameItemDefinition", PID_UNUSED_DOOR),
                 ("TPC.GameItemLiteDefinition", PID_PLAIN),
                 (WIDENED_CLASS, PID_WIDE),
                 ("TPC.ArchetypeDefinition", PID_ARCH),
                 ("TPC.StaffDefinition", PID_STAFFDEF),
                 ("TPC.LandscapeBrushDatabase", PID_BRUSH_DB),
                 ("TPC.LandscapeBrushDefinition", PID_BRUSH_1),
                 ("TPC.LandscapeBrushDefinition", PID_BRUSH_2),
                 ("TPC.RoomType", PID_ROOMTYPE_1),
                 ("TPC.RoomType", PID_ROOMTYPE_2),
                 ("TPC.RoomTypeBuilding", PID_ROOMTYPE_B_1),
                 ("MonoBehaviour", PID_SCEN_ALPHA)]
    items_a = [("TPC.GameItemDefinition", PID_CROSS),
               ("TPC.GameItemDefinition", PID_RAWONLY),
               ("MonoBehaviour", PID_SCEN_BETA)]
    items_b = [("TPC.GameItemVariationDefinition", PID_TWIN)]
    rows = [
        {"buildId": BUILD_ID, "bundle": B_SCEN_A, "cab": CAB_SCEN_A,
         "objects": objs(scen_objs)},
        {"buildId": BUILD_ID, "bundle": B_ITEMS, "cab": CAB_ITEMS_A,
         "objects": objs(items_a)},
        {"buildId": BUILD_ID, "bundle": B_ITEMS, "cab": CAB_ITEMS_B,
         "objects": objs(items_b)},
    ]
    return sorted(rows, key=lambda r: (r["bundle"], r["cab"]))


VALIDATOR_ADDR_2 = ("Assets/Data/Game/Items/Validators/"
                    "ItemValidator_Door_Fixture_Internal.asset")
CONTAINER_ROWS_EXTRA = [
    {"address": ADDR_VALIDATOR,
     "bundle": B_SCEN_A, "pathId": PID_VALIDATOR_1,
     "class": "MonoBehaviour"},
    {"address": VALIDATOR_ADDR_2,
     "bundle": B_SCEN_A, "pathId": PID_VALIDATOR_2,
     "class": "MonoBehaviour"},
    # reverse container-index rows that make the ghost twin pair human-
    # readable via assetAddress (distinct addresses, same levelId)
    {"address": "Assets/Data/DLCs/DLC2_Ghost/Configs/GhostsLevel_story.asset",
     "bundle": "dlc-ghost-configs_assets_all.bundle",
     "pathId": -6400000000000000001, "class": "MonoBehaviour"},
    {"address": "Assets/Data/DLCs/DLC2_Ghost/Configs/GhostsLevel_remix.asset",
     "bundle": "dlc-ghost-configs_assets_all.bundle",
     "pathId": -6400000000000000002, "class": "MonoBehaviour"},
]


def container_index_rows():
    rows = [{**r, "buildId": BUILD_ID} for r in CONTAINER_ROWS_EXTRA]
    return sorted(rows, key=lambda r: (r["bundle"], r["address"]))


def registry_rows():
    """i2_term_registry.jsonl landed shape. TERM_MISS deliberately ABSENT."""
    return [
        {"buildId": BUILD_ID, "canonical": True, "locales": ["en", "fr"],
         "sourceAsset": "I2LS_Levels", "termId": TERM_PAD_SHARED,
         "termKey": TERM_PAD_KEY, "termStatus": 1, "termType": 0},
        {"buildId": BUILD_ID, "canonical": True, "locales": ["en"],
         "sourceAsset": "I2LS_Students", "termId": TERM_STUDENT,
         "termKey": "Students/Nerd_Name", "termStatus": 1, "termType": 0},
    ]


# --- imagery predicate address set ---------------------------------------------------

IMG_ADDRESSES = [
    "Assets/Data/UI/Textures/Metamap/Meta_Fixture_A",
    "Assets/Data/UI/Textures/Metamap/Meta_Fixture_B",
    "Assets/data/ui/textures/metamap/meta_lower_c",
    "Assets/data/ui/textures/metamap/meta_pair_d",
    "Assets/Data/UI/LoadingScreens/Load_Fixture_E.png",
    "assets/data/ui/loadingscreen_pack/load_f",
    "Assets/Data/UI/Sandbox/UI_Sandbox_T_imageLevel_Knight",
    "UI_Sandbox_T_imageLevel_Mitton",
    "ui_sandbox_t_imagelevel_lowcase",
    "Assets/Data/Game/Levels/Final/Part1_Early/KnightLevel_Screenshot.png",
    "Assets/Data/Game/Levels/Remix/Remix_3/KnightLevel_Icon.png",
]

IMAGE_EXTS = ("png", "tga", "jpg", "jpeg")
MINIMAP_TOKENS = ("minimap", "mini-map", "mini_map", "compass", "worldmap")


def imagery_counts(addresses=IMG_ADDRESSES):
    """The SEVEN pinned patterns (spec M7 table, applied verbatim) plus the
    loadingscreen image-suffix secondary projection."""
    cs = ci = ls = ls_img = strict = fam = rx = mini = 0
    for a in addresses:
        low = a.casefold()
        name = a.rsplit("/", 1)[-1]
        suffix = name.rsplit(".", 1)[1].casefold() if "." in name else ""
        if "/MetaMap/" in a or "/Metamap/" in a:
            cs += 1
        if "metamap" in low:
            ci += 1
        if "loadingscreen" in low:
            ls += 1
            if suffix in IMAGE_EXTS:
                ls_img += 1
        if "UI_Sandbox_T_imageLevel_" in a:
            strict += 1
        if "imagelevel" in low:
            fam += 1
        if re.search(r"level.*(image|icon|screenshot)", low):
            rx += 1
        if any(t in low for t in MINIMAP_TOKENS):
            mini += 1
    counts = {"metamap-case-sensitive": cs,
              "metamap-case-insensitive": ci,
              "loadingscreen-images": ls,
              "imagelevel-strict-prefix": strict,
              "imagelevel-family": fam,
              "level-image-icon-screenshot": rx,
              "minimap-any-spelling": mini}
    projection = {"loadingscreen-image-suffixed": ls_img}
    return counts, projection


PREDICATE_PATTERNS = {
    "metamap-case-sensitive":
        "substring `/MetaMap/` OR `/Metamap/` (exact case)",
    "metamap-case-insensitive": "casefold substring `metamap`",
    "loadingscreen-images": "casefold substring `loadingscreen`",
    "imagelevel-strict-prefix":
        "exact-case substring `UI_Sandbox_T_imageLevel_`",
    "imagelevel-family": "casefold substring `imagelevel`",
    "level-image-icon-screenshot":
        "casefold regex `level.*(image\\|icon\\|screenshot)`",
    "minimap-any-spelling":
        "casefold substring any of `minimap, mini-map, mini_map, compass, "
        "worldmap`",
}


def catalog_obj():
    """Stage-2-style keys + guid-kind rows + the imagery address rows."""
    prov = ["ContentCatalogProvider", "BundledAssetProvider"]
    rows = []
    for k, ref in fx.CATALOG_KEYS_SPEC:
        rows.append({"key": k, "kind": "bundle", "bundle": ref,
                     "address": f"Assets/Content/{k.replace('.', '/')}",
                     "dependencies": [], "providerIds": prov})
    guid_rows = sorted((GUID_BY_PID[pid][0], GUID_BY_PID[pid][1])
                       for pid in GUID_BY_PID)
    guid_rows.append((GUID_VALIDATOR, ADDR_VALIDATOR))
    for guid, address in guid_rows:
        rows.append({"key": guid, "kind": "guid", "bundle": None,
                     "address": address, "dependencies": [],
                     "providerIds": prov})
    for i, address in enumerate(sorted(IMG_ADDRESSES)):
        rows.append({"key": f"Img.Fixture.{i:02d}", "kind": "bundle",
                     "bundle": B_ITEMS, "address": address,
                     "dependencies": [], "providerIds": prov})
    rows.sort(key=lambda r: r["key"])
    return {"meta": {"buildId": BUILD_ID,
                     "addressablesVersion": fx.ADDRESSABLES_VERSION,
                     "settingsHash": fx.SETTINGS_HASH,
                     "providerIds": prov},
            "keys": rows}


def catalog_addresses():
    return [row["address"] for row in catalog_obj()["keys"]
            if row.get("address")]


# --- export-manifest append ----------------------------------------------------------

def maps_export_manifest_append(rel=None):
    rows = []

    def b(name):
        return (rel or {}).get(name, name)

    def add(bundle, stem, family, cls, pid):
        out = f"harvest/monobehaviours/{family}/{cls}/{stem}_{pid}.json"
        rows.append({"sourceBundle": b(bundle), "pathId": pid, "class": cls,
                     "bytes": 256, "outRelPath": out})

    for bundle, family, stem, cls, pid, _f in item_definition_dumps():
        add(bundle, stem, family, cls, pid)
    for cls, pid, _f in brush_dumps():
        add(B_SCEN_A, STEM_SCEN_A, DIR_SCEN_A, cls, pid)
    for cls, pid, _f in roomtype_dumps():
        add(B_SCEN_A, STEM_SCEN_A, DIR_SCEN_A, cls, pid)
    add(B_SCEN_A, STEM_SCEN_A, DIR_SCEN_A, "TPC.LevelScenarioV2",
        PID_SCEN_ALPHA)
    add(B_SCEN_B, STEM_SCEN_B, DIR_SCEN_B, "TPC.LevelScenarioV2",
        PID_SCEN_BETA)
    for family, _scene, _pc, _part, _g, pid, _sp, _bo in LEVEL_CONFIGS:
        # landed shape: the manifest spells FULL roster relpaths whose tail
        # is `<stem>.bundle`; the stage's bundle_basename() + bridge lookups
        # key on exactly that shape
        add(f"{STEM_BY_FAMILY[family]}.bundle", STEM_BY_FAMILY[family],
            family, "TPC.LevelConfig", pid)
    add(B_SCEN_A, STEM_SCEN_A, DIR_SCEN_A, "TPC.UniversityLevelConfig",
        PID_UNIVERSITY)
    add(B_SCEN_A, STEM_SCEN_A, DIR_SCEN_A, "TPC.ItemValidator_Door",
        PID_VALIDATOR_1)
    add(B_SCEN_A, STEM_SCEN_A, DIR_SCEN_A, "TPC.ItemValidator_Door",
        PID_VALIDATOR_2)
    return rows

# --- tree assembly --------------------------------------------------------------------

def _write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8", newline="\n")


def _flat_payload(cls, stem, pid, fields):
    base = {"_decoded": {"method": "typetree+synthesis",
                         "typetreeDecoded": True},
            "_scriptClass": cls,
            "_sourceFile": f"{stem}_{pid}.json".lower()}
    base.update(fields)
    return base


def build_maps_upstream(extracted: Path) -> Path:
    """Materialize the piece-03 §3 upstream set over a cumulative fixture
    root. Idempotent + byte-deterministic; NEVER writes under extracted/maps
    (that directory stays the stage's sole write surface)."""
    extracted = Path(extracted)
    harv = extracted / "harvest"
    mono = harv / "monobehaviours"

    # scenario dumps (payload rides `_levelRecord`, P1)
    for payload, family, stem, pid in (
            (scenario_alpha_payload(), DIR_SCEN_A, STEM_SCEN_A,
             PID_SCEN_ALPHA),
            (scenario_beta_payload(), DIR_SCEN_B, STEM_SCEN_B,
             PID_SCEN_BETA)):
        p = mono / family / "TPC.LevelScenarioV2" / f"{stem}_{pid}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n",
                     encoding="utf-8", newline="\n")

    # 28 LevelConfig dumps (real 13/9/4/2 split; m_Name EMPTY everywhere)
    for spec in LEVEL_CONFIGS:
        family, _scene, _pc, _part, _g, pid, _sp, _bo = spec
        stem = STEM_BY_FAMILY[family]
        p = mono / family / "TPC.LevelConfig" / f"{stem}_{pid}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(level_config_dump(spec), indent=2,
                                sort_keys=True) + "\n",
                     encoding="utf-8", newline="\n")

    # out-of-scope sibling class (ledgered, never silently skipped)
    uni_dir = mono / FAMILY_CA / "TPC.UniversityLevelConfig"
    uni_dir.mkdir(parents=True, exist_ok=True)
    (uni_dir / f"{STEM_BY_FAMILY[FAMILY_CA]}_{PID_UNIVERSITY}.json").write_text(
        json.dumps(_flat_payload("TPC.UniversityLevelConfig",
                                 STEM_BY_FAMILY[FAMILY_CA], PID_UNIVERSITY,
                                 {"m_Name": "", "LevelScene": "UniLevel",
                                  "PlotCount": 4}),
                   indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n")

    # door validators
    val_dir = mono / FAMILY_CA / "TPC.ItemValidator_Door"
    val_dir.mkdir(parents=True, exist_ok=True)
    for cls_pid, v in ((PID_VALIDATOR_1, DOOR_VALIDATORS[0]),
                       (PID_VALIDATOR_2, DOOR_VALIDATORS[1])):
        payload = _flat_payload("TPC.ItemValidator_Door",
                                STEM_BY_FAMILY[FAMILY_CA], cls_pid, {})
        payload.update(v)
        (val_dir /
         f"{STEM_BY_FAMILY[FAMILY_CA]}_{cls_pid}.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True,
                       ensure_ascii=False) + "\n",
            encoding="utf-8", newline="\n")

    # definitions / brushes (flat payloads, _id + m_Name verbatim)
    for bundle, family, stem, cls, pid, fields in item_definition_dumps():
        assert bundle in (B_SCEN_A, B_ITEMS)
        p = mono / family / cls / f"{stem}_{pid}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        if set(fields) == {"_raw"} or "_raw" in fields and len(fields) == 1:
            obj = {"_raw": fields["_raw"], "_scriptClass": cls,
                   "_sourceFile": f"{stem}_{pid}.json".lower()}
        else:
            obj = _flat_payload(cls, stem, pid, fields)
        p.write_text(json.dumps(obj, indent=2, sort_keys=True,
                                ensure_ascii=False) + "\n",
                     encoding="utf-8", newline="\n")
    for cls, pid, fields in brush_dumps():
        p = mono / DIR_SCEN_A / cls / f"{STEM_SCEN_A}_{pid}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(_flat_payload(cls, STEM_SCEN_A, pid, fields),
                                indent=2, sort_keys=True,
                                ensure_ascii=False) + "\n",
                     encoding="utf-8", newline="\n")
    for cls, pid, fields in roomtype_dumps():
        p = mono / DIR_SCEN_A / cls / f"{STEM_SCEN_A}_{pid}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(_flat_payload(cls, STEM_SCEN_A, pid, fields),
                                indent=2, sort_keys=True,
                                ensure_ascii=False) + "\n",
                     encoding="utf-8", newline="\n")

    # export-manifest (cumulative merge, sorted) — bundle spellings follow
    # the LANDED join shape via the roster relmap when a roster exists
    roster_rel = _roster_relmap(extracted)
    man = harv / "export-manifest.jsonl"
    existing = []
    if man.exists():
        existing = [json.loads(x) for x in
                    man.read_text(encoding="utf-8").splitlines() if x.strip()]
    merged = {r["outRelPath"]: r for r in existing}
    for r in maps_export_manifest_append(roster_rel):
        merged.setdefault(r["outRelPath"], r)
    write_jsonl(man, sorted(merged.values(), key=lambda r: r["outRelPath"]))

    # externals (landed shape)
    write_jsonl(harv / "externals.jsonl", externals_rows(roster_rel))

    # relink bridges READ-ONLY inputs (landed shapes; fixtures cannot run
    # stage 6, so the bridge OUTPUTS are synthesized directly here)
    bridges = extracted / "relinks" / "bridges"
    bridges.mkdir(parents=True, exist_ok=True)
    write_jsonl(bridges / "cab_index.jsonl", cab_index_rows())
    write_jsonl(bridges / "container_index.jsonl", container_index_rows())
    write_jsonl(extracted / "relinks" / "i2_term_registry.jsonl",
                registry_rows())

    # catalog with guid-kind keys + imagery address rows
    _write_json(extracted / "addressables" / "catalog.json", catalog_obj())

    # dump.cs slice
    cs = extracted / "decompiled" / "il2cppdumper" / "dump.cs"
    cs.parent.mkdir(parents=True, exist_ok=True)
    cs.write_text(dump_cs_slice(), encoding="utf-8", newline="\n")
    return extracted


def build_maps_tree(out, *, full_scale=False, metadata_version=27) -> Path:
    """Cumulative prepared tree WITHOUT depending on the shared
    STAGE_ARTIFACTS registry (that file is a concurrent-edit hotspot): the
    piece-1 stages 0–5 fixture outputs + the piece-03 upstream overlay."""
    out = Path(out)
    fx.build_tree(out, "emit-stub-datasets", full_scale=full_scale,
                  metadata_version=metadata_version)
    build_maps_upstream(out / "extracted")
    return out


# ============================ ORACLE =================================================

PLACEMENT_FAMILIES = ("room", "arrival", "nonArea", "waypoint",
                      "plotActivation")

ORACLE = {
    "levels": 28,
    "generationSplit": {GEN_LEVELS_PREFABS: 13, GEN_CONFIGS_ASSETS_ALL: 9,
                        GEN_DLC_SPACE: 4, GEN_DLC_GHOST: 2},
    "scenarios": 2,
    "plots": 4, "rooms": 2, "roomTiles": 2, "plotTileTypes": 4,
    "placementsTotal": 15,
    "placementsByFamily": {"room": 9, "arrival": 2, "nonArea": 1,
                           "waypoint": 1, "plotActivation": 2},
    "students": 2, "staff": 2,
    "landscapeLayers": 3, "landscapeMaps": 3, "zeroDimLayers": 1,
    "largestMap": [30, 56],
    "doorValidators": 2, "validatorRefs": 4, "slidingDoorComponents": 0,
    "doorPlacements": 4, "doorKinds": 2,
    "doorAnchoredCounterfactual": {"placements": 3, "kinds": 1},
    "namedPlots": 3, "genericPlots": 1, "sharedTermRows": 2,
    "boundsStd": 27, "boundsBlank": 1, "spawnVariants": 2,
    "join": {
        "denominatorMeasuredSet": 13,
        "resolved": 11, "residue": 2,
        "residueCrossFile": 1, "residueSameFileMiss": 1,
        "corroboration": {"match": 9, "twinMismatch": 1, "absent": 1},
        "widenedClasses": [WIDENED_CLASS],
        "indexEntries": 6, "indexBundles": 2,
        "plotActivationFamily": {"total": 2, "resolved": 2, "unresolved": 0},
        "unresolvedLedgerRows": 2,
    },
    "guidResolvable": 27, "guidBlank": 1,
}


def door_kind_census(resolved_names, prefix="Item_Door_"):
    """Substring census (F16 ruled predicate) + anchored counterfactual."""
    sub = [n for n in resolved_names if prefix in n]
    anchored = [n for n in resolved_names if n.startswith(prefix)]
    return {"substring": {"placements": len(sub), "kinds": len(set(sub))},
            "anchored": {"placements": len(anchored),
                         "kinds": len(set(anchored))}}


# ---------------- M5 HARD-GATE detection rule (pinned mechanically) ---------------

VALIDATOR_REF_NAME_TOKENS = ("validatorid", "entrancetorooms", "exittorooms",
                             "entranceref", "exitref")
ROOM_INSTANCE_NAME_TOKENS = ("owningroomuniqueid", "roomuniqueid")


def _walk_leaves(v):
    if isinstance(v, dict):
        for x in v.values():
            yield from _walk_leaves(x)
    elif isinstance(v, (list, tuple)):
        for x in v:
            yield from _walk_leaves(x)
    else:
        yield v


def gated_relation_violation(row, room_unique_ids=(), where="row"):
    """M5 HARD GATE detection rule, verbatim (Rev 3 M5): a row carrying BOTH
    (a) a field whose value-or-name references a validator ref
    (`validatorId`, `entranceToRooms`, `exitToRooms`, `entranceRef`,
    `exitRef`) AND (b) a room-instance reference (`owningRoomUniqueId`,
    `roomUniqueId`, or a value resolving against the same scenario's
    rooms.jsonl uniqueId set) — EXCEPT placement containment via
    `owningRoomId` on a placement-family row. Returns a reason string when
    the rule fires, None when clean. The SAME rule backs the AC11 post-hoc
    audit and the in-stage refusal expectation."""
    if not isinstance(row, dict):
        return None
    keys_l = {str(k).casefold() for k in row}
    ref_named = any(any(t in k for t in VALIDATOR_REF_NAME_TOKENS)
                    for k in keys_l)
    ref_vals = set()
    for k in keys_l:
        if any(t in k for t in VALIDATOR_REF_NAME_TOKENS):
            ref_vals.update(v for v in _walk_leaves(row.get(
                next(kk for kk in row if str(kk).casefold() == k))))
    has_ref = bool(ref_named or ref_vals)
    if not has_ref:
        return None
    room_ids = set(room_unique_ids or ())
    named_room = any(any(t in k for t in ROOM_INSTANCE_NAME_TOKENS)
                     for k in keys_l)
    value_room = any(isinstance(v, int) and v in room_ids
                     for v in _walk_leaves(row))
    if not (named_room or value_room):
        return None
    containment_excepted = (
        "owningroomid" in keys_l
        and row.get("recordFamily") in PLACEMENT_FAMILIES
        and not named_room)
    if containment_excepted:
        return None
    return (f"{where}: validator-ref x room-instance relation emitted while "
            f"the door id-space gate is closed (M5 HARD GATE)")


# ============================ VALIDATORS =============================================

def _err(e, m):
    e.append(m)


def _keys(e, row, required, where, optional=()):
    got = set(row)
    miss = set(required) - got
    extra = got - set(required) - set(optional)
    if miss:
        _err(e, f"{where}missing keys {sorted(miss)}")
    if extra:
        _err(e, f"{where}unexpected keys {sorted(extra)}")


def _vec3(e, obj, where):
    if not isinstance(obj, dict) or set(obj) != {"x", "y", "z"}:
        _err(e, f"{where}not an {{x,y,z}} triple: {obj!r}")


AXIS_ENUM = ("base", "dlc-space", "dlc-ghost")


def validate_levels_row(row, where="levels"):
    e = []
    req = {"levelId", "contentAxis", "worldBounds", "spawnPoint", "plotCount",
           "sceneNames", "scenarioGuid", "scenarioAddress", "campaignPart",
           "assetAddress", "assetNameStem", "imagery", "iconRenderCamera",
           "source", "buildId"}
    # leniency note: variantOf rides plotCount.variantOf in the sketch; a
    # top-level variantOf is accepted too — the SUBSTANCE legs (twin links,
    # no canonical flag anywhere) are enforced regardless of nesting.
    opt = {"variantOf"}
    if not isinstance(row, dict):
        return [f"{where}row is not an object"]
    _keys(e, row, req, where, opt)
    if not isinstance(row.get("levelId"), str) or not row.get("levelId"):
        _err(e, f"{where}levelId must be a NON-EMPTY string equal to "
                f"LevelScene (F14 law: never m_Name, which is '' on every "
                f"real dump)")
    if row.get("contentAxis") not in AXIS_ENUM:
        _err(e, f"{where}contentAxis {row.get('contentAxis')!r} outside "
                f"the piece-1 enum {AXIS_ENUM}")
    pc = row.get("plotCount") or {}
    gen = pc.get("generation")
    if gen is not None and gen not in GENERATION_ENUM:
        _err(e, f"{where}plotCount.generation {gen!r} outside the closed "
                f"four-family enum {GENERATION_ENUM}")
    for k in set(pc) - {"value", "generation", "variantOf"}:
        _err(e, f"{where}plotCount unexpected key {k!r}")
    blob = json.dumps(row, sort_keys=True).casefold()
    if '"canonical"' in blob or "canonical:true" in blob.replace(" ", ""):
        _err(e, f"{where}a canonical flag is FORBIDDEN while loadassets "
                f"readStatus is inconclusive-from-dumpcs (R4.0/R4.1)")
    wb = row.get("worldBounds") or {}
    for side in ("center", "extent"):
        _vec3(e, wb.get(side), f"{where}worldBounds.{side} ")
    _vec3(e, row.get("spawnPoint"), f"{where}spawnPoint ")
    sn = row.get("sceneNames") or {}
    _keys(e, sn, {"levelScene", "optimized"}, f"{where}sceneNames ",
          optional={"hud", "databaseScene"})
    im = row.get("imagery") or {}
    _keys(e, im, set(), f"{where}imagery ",
          optional={"loadingScreenBackground", "sandboxScreenshot",
                    "sandboxContainerScreenshot", "levelIcon"})
    cam = row.get("iconRenderCamera") or {}
    _keys(e, cam, set(), f"{where}iconRenderCamera ",
          optional={"cameraDistance", "cameraFov", "cameraRotation",
                    "textureSize"})
    src = row.get("source") or {}
    if "bundle" not in src or "pathId" not in src:
        _err(e, f"{where}source must carry {{bundle, pathId}} provenance")
    return e


def validate_scenario_row(row, where="scenarios"):
    e = []
    if not isinstance(row, dict):
        return [f"{where}row is not an object"]
    _keys(e, row, {"scenarioName", "levelRecordName", "contentAxis",
                   "version", "nextPlotUniqueId", "counts", "source",
                   "buildId"}, where)
    if row.get("contentAxis") not in AXIS_ENUM:
        _err(e, f"{where}contentAxis outside enum")
    counts = row.get("counts") or {}
    _keys(e, counts, {"plots", "rooms", "itemsByFamily", "itemsTotal",
                      "students", "staff"}, f"{where}counts ")
    byf = counts.get("itemsByFamily") or {}
    _keys(e, byf, set(PLACEMENT_FAMILIES), f"{where}counts.itemsByFamily ")
    if sum(byf.values()) != counts.get("itemsTotal"):
        _err(e, f"{where}itemsByFamily cells must sum to itemsTotal (F2)")
    return e


def validate_plot_row(row, where="plots"):
    e = []
    if not isinstance(row, dict):
        return [f"{where}row is not an object"]
    _keys(e, row, {"scenarioName", "plotUniqueId", "persistentName",
                   "definitionId", "definitionPptr", "bounds", "locked",
                   "initiallyBuilt", "buildCost", "ignoreForCameraBounds",
                   "usePlotDisplayName", "displayNameTermId", "tileTypes",
                   "tilesRef", "layerCount", "plotActivationCount", "source",
                   "buildId"}, where)
    pp = row.get("definitionPptr")
    if not isinstance(pp, dict) or "fileId" not in pp or "pathId" not in pp:
        _err(e, f"{where}definitionPptr must carry {{fileId, pathId}} "
                f"verbatim, never dropped in favor of the numeric id (F12)")
    tt = row.get("tileTypes") or {}
    if "width" not in tt or "height" not in tt:
        _err(e, f"{where}tileTypes carries DIMS only; the bitmap lives in "
                f"plots_tiletypes.jsonl")
    ref = row.get("tilesRef") or {}
    if ref.get("artifact") != "plots_tiletypes.jsonl":
        _err(e, f"{where}tilesRef.artifact must point at "
                f"plots_tiletypes.jsonl")
    b = row.get("bounds") or {}
    for side in ("center", "extent"):
        _vec3(e, b.get(side), f"{where}bounds.{side} ")
    return e


def validate_room_row(row, where="rooms"):
    e = []
    if not isinstance(row, dict):
        return [f"{where}row is not an object"]
    _keys(e, row, {"scenarioName", "uniqueId", "anchor", "worldPosition",
                   "definitionId", "definitionPptr", "tiles", "tilesRef",
                   "plotLayer", "childRoomRecordIds", "itemCount", "source",
                   "buildId"}, where)
    pp = row.get("definitionPptr")
    if not isinstance(pp, dict) or "fileId" not in pp or "pathId" not in pp:
        _err(e, f"{where}definitionPptr must carry {{fileId, pathId}} (F12)")
    ref = row.get("tilesRef") or {}
    if ref.get("artifact") != "rooms_tiles.jsonl":
        _err(e, f"{where}tilesRef.artifact must point at rooms_tiles.jsonl")
    a = row.get("anchor") or {}
    if not isinstance(a, dict) or set(a) != {"x", "y"}:
        _err(e, f"{where}anchor is GRID CELLS {{x,y}}, not world units")
    _vec3(e, row.get("worldPosition"), f"{where}worldPosition ")
    return e


def _validate_bitmap_row(row, bitmap_key, id_key, where):
    e = []
    if not isinstance(row, dict):
        return [f"{where}row is not an object"]
    # the identity key rides every row (spec M2 sketches pin
    # {scenarioName, uniqueId | plotUniqueId, <bitmap>, source, buildId})
    _keys(e, row, {"scenarioName", id_key, bitmap_key, "source", "buildId"},
          where)
    bm = row.get(bitmap_key) or {}
    if set(bm) != {"_width", "_height", "_saveData"}:
        _err(e, f"{where}bitmap must be verbatim {{_width,_height,"
                f"_saveData[]}} — no re-encoding, no packing")
        return e
    w, h, data = bm["_width"], bm["_height"], bm["_saveData"]
    if isinstance(w, int) and isinstance(h, int) and isinstance(data, list) \
            and len(data) != w * h:
        _err(e, f"{where}_saveData length {len(data)} != {w}*{h}")
    return e


def validate_room_tiles_row(row, where="rooms_tiles"):
    return _validate_bitmap_row(row, "tiles", "uniqueId", where)


def validate_plot_tiletypes_row(row, where="plots_tiletypes"):
    return _validate_bitmap_row(row, "tileTypes", "plotUniqueId", where)


def validate_placement_row(row, where="item_placements"):
    e = []
    if not isinstance(row, dict):
        return [f"{where}row is not an object"]
    _keys(e, row, {"scenarioName", "recordFamily", "owningRoomId",
                   "plotUniqueId", "definitionId", "definitionPptr",
                   "localPosition", "localRotation", "generalParamInt1",
                   "customisationSwatchIndex", "itemFlags", "plotLayer",
                   "resolution", "derived", "source", "buildId"}, where)
    if row.get("recordFamily") not in PLACEMENT_FAMILIES:
        _err(e, f"{where}recordFamily {row.get('recordFamily')!r} outside "
                f"the frozen five-family enum")
    derived = row.get("derived")
    if derived is not None:
        if row.get("recordFamily") != "room":
            _err(e, f"{where}derived block FORBIDDEN on non-room families "
                    f"(their reference frame is unverified, OQ2)")
        elif set(derived) != {"world", "method"} or \
                derived.get("method") != "roomWorldPlusLocal":
            _err(e, f"{where}derived block must be whole-or-nothing "
                    f"{{world{{x,y,z}}, method:'roomWorldPlusLocal'}}")
        else:
            _vec3(e, derived.get("world"), f"{where}derived.world ")
    res = row.get("resolution")
    if not isinstance(res, dict) or "status" not in res:
        _err(e, f"{where}resolution must carry status (pending on first "
                f"write, rewritten once by M3)")
    elif res.get("status") not in ("pending", "resolved", "unresolved"):
        _err(e, f"{where}resolution.status {res.get('status')!r} outside "
                f"pending|resolved|unresolved")
    return e


def validate_student_row(row, where="students"):
    e = []
    if not isinstance(row, dict):
        return [f"{where}row is not an object"]
    _keys(e, row, {"scenarioName", "studentIndex", "archetypePptr",
                   "archetypeDefinitionId", "firstNameDev", "firstNameTermId",
                   "lastNameDev", "lastNameTermId", "learningRate", "sex",
                   "source", "buildId"}, where)
    return e


def validate_staff_row(row, where="staff_records"):
    e = []
    if not isinstance(row, dict):
        return [f"{where}row is not an object"]
    _keys(e, row, {"scenarioName", "staffIndex", "definitionPptr",
                   "definitionId", "qualifications", "qualificationLevels",
                   "rank", "source", "buildId"}, where)
    return e


def validate_layer_row(row, where="landscape_layers"):
    e = []
    if not isinstance(row, dict):
        return [f"{where}row is not an object"]
    _keys(e, row, {"scenarioName", "plotUniqueId", "layerIndex",
                   "plotLayerFlags", "roomRecordId", "dims",
                   "valueHistograms", "source", "buildId"}, where)
    dims = row.get("dims") or {}
    _keys(e, dims, {"terrain", "object", "attribute"}, f"{where}dims ")
    for plane, pair in dims.items():
        ok = isinstance(pair, (list, tuple)) and len(pair) == 2
        if plane == "attribute" and not ok:
            # AttributeMap is a verbatim STRUCT ARRAY (P6 families); the
            # sketch's attribute:[w,h] is ill-defined for it, so an honest
            # null, an int cell count, or a {width,height}-style object is
            # tolerated on THAT PLANE ONLY (terrain/object stay strict)
            ok = pair is None or isinstance(pair, int) or                 isinstance(pair, dict)
        if not ok:
            _err(e, f"{where}dims.{plane} must be [w, h]")
        # a [0, 0] row is DATA, never a violation (AC2/F3)
    vh = row.get("valueHistograms") or {}
    for plane in ("terrain", "object"):
        hist = vh.get(plane)
        if hist is not None and not isinstance(hist, dict):
            _err(e, f"{where}valueHistograms.{plane} must be a value->count "
                    f"map with sorted keys")
    return e


def validate_landscape_map_row(row, where="landscape_maps"):
    e = []
    if not isinstance(row, dict):
        return [f"{where}row is not an object"]
    # sketch keys are contract; `source` tolerated as the AC5 complement
    _keys(e, row, {"scenarioName", "plotUniqueId", "layerIndex", "terrainMap",
                   "landscapeObjectMap", "attributeMap", "buildId"},
          where, optional={"source"})
    for plane in ("terrainMap", "landscapeObjectMap"):
        bm = row.get(plane) or {}
        if set(bm) != {"_width", "_height", "_saveData"}:
            _err(e, f"{where}.{plane} must be verbatim {{_width,_height,"
                    f"_saveData[]}}")
    return e


def validate_validator_row(row, where="door_validators"):
    e = []
    if not isinstance(row, dict):
        return [f"{where}row is not an object"]
    _keys(e, row, {"validatorId", "entranceToRooms", "exitToRooms",
                   "allowEntranceInAnyBuilding", "allowEntranceInAnyRoom",
                   "allowExitToAnyBuilding", "allowExitToAnyRoom", "source",
                   "buildId"}, where,
          optional={"catalogAddress", "invalidEntranceMessage",
                    "InvalidEntranceMessage", "invalidExitMessage",
                    "InvalidExitMessage", "invalidMessage",
                    "InvalidMessage"})
    for lst in ("entranceToRooms", "exitToRooms"):
        if not isinstance(row.get(lst), list):
            _err(e, f"{where}.{lst} must be a verbatim list of ints")
    return e


def validate_door_placement_row(row, where="door_placement_index"):
    e = []
    if not isinstance(row, dict):
        return [f"{where}row is not an object"]
    _keys(e, row, set(), where,
          optional={"scenarioName", "recordFamily", "owningRoomId",
                    "itemIndex", "definitionName", "source", "buildId",
                    "plotUniqueId"})
    name = str(row.get("definitionName", ""))
    if "Item_Door_" not in name:
        _err(e, f"{where}projection predicate violated: {name!r} lacks the "
                f"pinned SUBSTRING Item_Door_ (F16)")
    for coord in ("localPosition", "localRotation", "worldPosition",
                  "bounds", "anchor"):
        if coord in row:
            _err(e, f"{where}must NOT duplicate coordinates ({coord}); it is "
                    f"a projection over item_placements.jsonl")
    return e


def validate_named_plot_row(row, where="named_plots"):
    e = []
    if not isinstance(row, dict):
        return [f"{where}row is not an object"]
    _keys(e, row, {"scenarioName", "plotUniqueId", "persistentName",
                   "displayNameTermId", "resolvedTermKey", "locales",
                   "method", "inferred", "source", "buildId"}, where)
    if row.get("method") != "i2-termid-registry":
        _err(e, f"{where}method must be 'i2-termid-registry'")
    if row.get("inferred") is not False:
        _err(e, f"{where}inferred must be false (hard termID join)")
    return e


def validate_imagery_candidate_row(row, where="imagery_candidates"):
    e = []
    if not isinstance(row, dict):
        return [f"{where}row is not an object"]
    _keys(e, row, {"address", "bundle", "matchedPredicates",
                   "mediaCatalogueClasses", "buildId"}, where)
    mp = row.get("matchedPredicates")
    if not isinstance(mp, list) or not mp or \
            any(p not in PREDICATE_PATTERNS for p in mp):
        _err(e, f"{where}matchedPredicates must name pinned predicate ids, "
                f"got {mp!r}")
    return e


def validate_coordinate_law(obj, grid_line=None, palette_line=None):
    e = []
    if not isinstance(obj, dict):
        return ["coordinate_law.json is not an object"]
    _keys(e, obj, {"grid", "plotTilePalette", "worldBounds", "spawnPoints",
                   "projection", "buildId"}, "coordinate_law ")
    grid = obj.get("grid") or {}
    _keys(e, grid, {"type", "sourceLine", "cellSize", "cellSizeSq",
                    "cellSizeInv", "cellSizeHalf", "parsedFrom"},
          "coordinate_law.grid ")
    if grid.get("type") != "GridCoord":
        _err(e, "grid.type must be GridCoord")
    if grid.get("cellSize") != 2.0:
        _err(e, f"grid.cellSize must parse to 2.0, got "
                f"{grid.get('cellSize')!r} (embedded expectation; movement "
                f"raises DRIFT)")
    for k, want in (("cellSizeSq", 4.0), ("cellSizeInv", 0.5),
                    ("cellSizeHalf", 1.0)):
        if grid.get(k) != want:
            _err(e, f"grid.{k} must parse to {want}, got {grid.get(k)!r}")
    if "dump.cs" not in str(grid.get("parsedFrom", "")):
        _err(e, f"grid.parsedFrom must name dump.cs, got "
                f"{grid.get('parsedFrom')!r}")
    if grid_line is not None and grid.get("sourceLine") != grid_line:
        _err(e, f"grid.sourceLine {grid.get('sourceLine')!r} != fixture "
                f"slice line {grid_line}")
    pal = obj.get("plotTilePalette") or {}
    _keys(e, pal, {"type", "sourceLine", "values"}, "plotTilePalette ")
    want = {"None": -1, "Invalid": 0, "Default": 1,
            "Unbuildable": 2, "NoNavigation": 3}
    got = pal.get("values")
    if not isinstance(got, dict):
        _err(e, f"palette values missing: {got!r}")
    else:
        extra = {k: v for k, v in got.items() if k not in want}
        if {k: got.get(k) for k in want} != want:
            _err(e, f"palette values drifted: {got!r}")
        # the real enum also carries NumTypes=4 (dump.cs); tolerated
        if extra and set(extra) != {"NumTypes"}:
            _err(e, f"palette carries unexpected members beyond the pinned "
                    f"five + NumTypes: {extra!r}")
    if palette_line is not None and pal.get("sourceLine") != palette_line:
        _err(e, f"palette sourceLine {pal.get('sourceLine')!r} != fixture "
                f"slice line {palette_line}")
    proj = obj.get("projection") or {}
    inv = grid.get("cellSizeInv")
    if proj.get("cellsPerWorldUnit") != inv:
        _err(e, f"projection.cellsPerWorldUnit must be COMPUTED from the "
                f"parsed CellSizeInv ({inv!r}), never pasted")
    for i, row in enumerate(obj.get("worldBounds") or []):
        _keys(e, row, {"levelName", "center", "extent", "source"},
              f"worldBounds[{i}] ")
        src = row.get("source") or {}
        if "bundle" not in src or "pathId" not in src:
            _err(e, "every positional row carries source{bundle, pathId} "
                    "(AC5 complement)")
    for i, row in enumerate(obj.get("spawnPoints") or []):
        _keys(e, row, {"levelName", "value", "variant", "source"},
              f"spawnPoints[{i}] ")
        src = row.get("source") or {}
        if "bundle" not in src or "pathId" not in src:
            _err(e, "every positional row carries source{bundle, pathId}")
    return e


def validate_loadassets_read(obj, iterator_line=None):
    e = []
    if not isinstance(obj, dict):
        return ["loadassets_read.json is not an object"]
    _keys(e, obj, {"subject", "declaration", "readStatus",
                   "instantiatedGeneration", "evidence", "unblock",
                   "buildId"}, "loadassets_read ")
    decl = obj.get("declaration") or {}
    _keys(e, decl, {"methodDeclaration", "methodDumpCsLine",
                    "enclosingClass", "iteratorShape", "iteratorDumpCsLine",
                    "members", "methodBodyAvailable", "note"},
          "loadassets_read.declaration ",
          optional={"enclosingTypeDefIndex", "iteratorTypeDefIndex"})
    if obj.get("readStatus") not in ("resolved", "inconclusive-from-dumpcs"):
        _err(e, f"readStatus {obj.get('readStatus')!r} outside the two-state "
                f"enum")
    if decl.get("methodBodyAvailable") is not False:
        _err(e, "il2cppdumper emits declarations, not bodies — "
                "methodBodyAvailable must be false")
    shape = str(decl.get("iteratorShape", ""))
    if "d__532" not in shape:
        _err(e, f"iteratorShape must carry the generic d__NN state machine "
                f"name parsed fresh (fixture plants d__532), got {shape!r}")
    if iterator_line is not None and \
            decl.get("iteratorDumpCsLine") != iterator_line:
        _err(e, f"iteratorDumpCsLine {decl.get('iteratorDumpCsLine')!r} != "
                f"slice line {iterator_line}")
    if obj.get("instantiatedGeneration") is not None:
        _err(e, "instantiatedGeneration must stay null while the body is "
                "unreadable (honest inconclusive state, R4.1 terminal)")
    return e


def validate_join_report(obj):
    e = []
    if not isinstance(obj, dict):
        return ["join_report.json is not an object"]
    _keys(e, obj, {"denominator", "resolved", "resolveRate", "residue",
                   "residueByScenario", "residueCrossFile",
                   "residueSameFileMiss", "widenedClasses",
                   "plotActivationFamily", "corroboration", "indexEntries",
                   "indexBundles", "buildId"}, "join_report ",
          optional={"cause", "note"})
    den = obj.get("denominator") or {}
    if "measuredSet" not in den:
        _err(e, "denominator.measuredSet missing")
    corr = obj.get("corroboration") or {}
    _keys(e, corr, {"match", "twinMismatch", "absent"}, "corroboration ",
          optional={"cause"})
    if corr.get("absent") and not str(corr.get("cause", "")):
        _err(e, "a nonzero `absent` class MUST carry its cause (F17: targets "
                "are _raw-only undecoded dumps)")
    paf = obj.get("plotActivationFamily") or {}
    _keys(e, paf, {"total", "resolved", "unresolved"},
          "plotActivationFamily ")
    return e


def validate_door_id_space(obj):
    e = []
    if not isinstance(obj, dict):
        return ["door_id_space.json is not an object"]
    _keys(e, obj, {"refsTotal", "sweeps", "reconciliation",
                   "slidingDoorComponents", "instanceLinks",
                   "adjacencyStatus", "verdict", "unblock", "buildId"},
          "door_id_space ", optional={"extraKindSpellings"})
    if obj.get("adjacencyStatus") != "DERIVED-ONLY":
        _err(e, "adjacencyStatus must stay DERIVED-ONLY until the id space "
                "is reconciled (G8)")
    sweeps = obj.get("sweeps") or {}
    _keys(e, sweeps, {"fullSpaceSweep", "integerSweep"}, "sweeps ")
    full = sweeps.get("fullSpaceSweep") or {}
    for k in ("method", "matched"):
        if k not in full:
            _err(e, f"sweeps.fullSpaceSweep.{k} missing (both sweeps re-run "
                    f"MECHANICALLY)")
    integ = sweeps.get("integerSweep") or {}
    if "bestMatch" not in integ:
        _err(e, "sweeps.integerSweep.bestMatch missing")
    if obj.get("reconciliation") not in ("agreed", "divergent"):
        _err(e, f"reconciliation {obj.get('reconciliation')!r} outside "
                f"agreed|divergent")
    links = obj.get("instanceLinks") or {}
    if "measured" not in links:
        _err(e, "instanceLinks.measured must be present (drift-checked seed, "
                "never a constant)")
    return e


def validate_absence_row(row, where="_absences"):
    e = []
    if not isinstance(row, dict):
        return [f"{where}row is not an object"]
    _keys(e, row, {"class", "scope", "evidence", "unblock", "buildId"},
          where)
    return e


def validate_unresolved_row(row, where="_unresolved_placements"):
    e = []
    if not isinstance(row, dict):
        return [f"{where}row is not an object"]
    for k in ("scenarioName", "recordFamily", "extFileId", "dstCab",
              "pathId", "reason", "buildId"):
        if k not in row:
            _err(e, f"{where}missing debug-evidence key {k!r} (a miss is "
                    f"attributable to its exact serialized file)")
    return e
