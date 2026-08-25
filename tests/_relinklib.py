"""Relink-stage (piece-02 §8) synthetic fixture library + contract validators.

Everything here is SYNTHETIC — never real game bytes. The corpus mirrors the
LANDED artifact shapes (grounded 2026-08-25 on extracted/ at buildId
20226581: stub row shape, externals sidecar `{bundle, externals:[{fileId,
guid, path, type}]}`, catalog guid/address key kinds, I2 LanguageSource dump
wrapper `{mSource:{mLanguages, mTerms[]}}`) so stage 6 consumes fixture trees
exactly like the real corpus.

Layout of the little world (all ids verbatim-stable, hand-computed oracle in
EXPECTED_* below):

  rooms_assets_all.bundle            Room_Archaeology_Display + the anchor
                                     ITEM at pathId 3001 (same-file anchor
                                     edges, repeat-collapse, scene
                                     attribution, dangling pathId)
  items-general_assets_all.bundle    TWO serialized files (CAB-items-a/-b);
                                     the @hash8 twin endpoint only
  configs_assets_all.bundle          Caterer participants-graph anchor (same-
                                     file config->config), ghost/builtin/
                                     twin cross-file refs, dangling-GUID holder
  items-courses-magic_assets_all     Course_Archaeology -> its own-bundle
                                     module config edge (same-file)
  character-shared_assets_all        Staff_Assistant term-ID anchor, nerd,
                                     sentinel-0, registry-miss students
  unlockables_assets_all             Unlock_Kudosh_Chair (probe cell substrate)
  configs-metagame_assets_all        metagame-node needs-probe (cross-file
                                     Course PPtr dangling into the scene bundle)
  configs_assets_all (cont.)         CampusLevel_Metagame carrying the §2
                                     anchor GUID -> Config_Metagame.asset
  scenes-scene-campus1.unity.bundle  sceneFlag '.unity'; non-stub objects the
                                     walkers must attribute to the scene node
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _validators import (  # noqa: E402
    ADDRESSABLES_VERSION, BUILD_ID, CONTENT_AXES, LOCALE_TABLE, SETTINGS_HASH,
    UNITY_VERSION, read_json, read_jsonl, write_jsonl,
)
import _fixturelib as fx  # noqa: E402

# --- pinned vocabulary (piece-02 §3) ----------------------------------------------

NODE_UNIVERSE = ("config", "item", "room", "course", "staff", "student-type",
                 "unlockable", "metagame-node", "campus-level", "scene")
STUB_KINDS = tuple(k for k in NODE_UNIVERSE if k != "scene")
CELL_TOTAL = len(NODE_UNIVERSE) ** 2          # 100
OFF_DIAGONAL = len(NODE_UNIVERSE) ** 2 - len(NODE_UNIVERSE)   # 90
DIAGONAL = len(NODE_UNIVERSE)                 # 10
ARITHMETIC_PIN = (f"{len(NODE_UNIVERSE)} nodes -> {CELL_TOTAL} ordered cells "
                  f"= {OFF_DIAGONAL} off-diagonal + {DIAGONAL} diagonal")

JOIN_KEY_LITERAL = (
    "PPtr(m_FileID,m_PathID)",
    "AssetGUID(m_AssetGUID)->catalog.guid->container-address->pathId",
    "LocalisedString(_termID)->I2-termID->Term-key",
)
JOIN_KEY_PREFIXED = "name-equality("
JOIN_KEY_NONE = "none-established"
MECHANISMS = ("hard", "logic", "inferred")
STATUSES = ("modeled", "partial", "missing")

HARD_METHODS = ("pptr-same-file", "pptr-cross-file", "assetguid-catalog",
                "i2-termid-registry")
METHOD_FREE_PREFIXES = ("name-convention:", "code-analysis:", "competitor-model:")
CONTENT_AXIS_ENUM = CONTENT_AXES

# Run-section counters, pinned per pass (piece-02 §3 Run-section keys)
RUN_SECTION_KEYS = {
    "R1": ["bundlesBridged", "cabRows", "containerRows", "fallbackVersionUsedBundles"],
    "R2": ["cellsTotal", "cellsModeled", "cellsPartial", "cellsMissing",
           "pairFilesEmitted", "edgesEmitted", "sameFileResolved",
           "crossFileResolved", "sceneAttributedEdges", "unresolvedCrossFile",
           "builtinExternalsSkipped", "unresolvedSameFile", "twinEndpointEdges"],
    "R3": ["guidRefsTotal", "distinctGuids", "resolvedToAddress", "resolvedToStub",
           "danglingDistinctGuids", "danglingVerdicts"],
    "R4": ["languageSourcesRead", "registryRows", "registryDistinctKeys",
           "matrixKeyDiff", "instancesTotal", "sentinelZero", "registryHits",
           "registryMisses", "coverageOnNonEmpty"],
    "R5": ["surfacesTotal", "mappedSchema", "documentedGaps", "tooltipTargetClasses",
           "tooltipGenericContainers", "localizeBindings"],
    "R6": ["sourcesRead", "sourcesApplied", "floorMet", "confirmsHard",
           "addsDerived", "flagsMissing", "wallsRecorded"],
    "R7": ["relationsMdBytes", "generatedFrom"],
}


def run_section_key_violations(text, *, where="run section"):
    """Arbiter F10 (TR8): every pinned RUN_SECTION_KEYS key must appear in
    the pass's run text with a parseable value after it (int, or true/false
    for the boolean keys like floorMet). Returns violation strings — EMPTY
    means the pass named all its counters; absence now FAILS instead of
    being skipped over."""
    e: list[str] = []
    for section, keys in sorted(RUN_SECTION_KEYS.items()):
        for key in keys:
            m = re.search(rf"{re.escape(key)}\b[^0-9\n]*(-?\d+|true|false)",
                          text, re.IGNORECASE)
            if m is None:
                e.append(f"{where}: {section} key {key!r} absent from the "
                         "run section or carries no parseable value")
    return e

# --- §2 sample-edge anchors, embedded verbatim in the synthetic corpus -------------

ANCHOR_GRAPH_SRC = "Activity_Dynamic_Social_Item_Caterer"
ANCHOR_GRAPH_DST = "BG_Character_Interaction_Caterer"
ANCHOR_ROOM = "Room_Archaeology_Display"
ANCHOR_ITEM = "Item_Door_Building_Archaeology_Display"
# ADAPTED 2026-08-25 (blind-pair repair): the course edge's destination was
# pinned to ANCHOR_GRAPH_DST while referencing pathId +1002 from another
# bundle — unresolvable as a same-file PPtr under Unity semantics (a fid==0
# reference names an object in the SAME serialized file; the spec's §2
# sample edges pin the room/course anchors as measured same-file pairs,
# which on the real corpus ride Unity's dependent-definition duplication
# INSIDE the referring bundle). The fixture now models that reality: the
# anchor item lives in the rooms bundle, and the course references a module
# config resident in its own bundle.
COURSE_MODULE_ID = "Course_Module_Archaeology"
ANCHOR_STAFF = "Staff_Assistant"
STAFF_TERM_ID = -1312157894                    # corrected value per spec §2
STAFF_TERM_KEY = "UI/General/Sims/Assistant"
ANCHOR_LEVEL_GUID = "1676b22c239b1554fad03b6027331112"   # -> …Config_Metagame.asset
META_ADDRESS = "Assets/Content/Metagame/Config_Metagame.asset"
ART_ADDRESS = "Assets/Content/UI/icon_atlas_sheet.asset"
SCENE_ADDRESS = "Assets/Content/Scenes/Campus1_Banner.asset"
GUID_ART = "aaaaaaaa111122223333444455556666"
GUID_DANGLING = "99999999888877776666555544443333"
GUID_SCENE = "bbbbbbbb7777888899990000aaaabbbb"
TWIN_BARE_ID = "Item_Twin_Definition"
TWIN_HASH8 = "1a2b3c4d"
TWIN_ID = f"{TWIN_BARE_ID}@{TWIN_HASH8}"
ANCHOR_DST_PID = -1002          # signed pathId (Revision-6 spelling end to end)
# F8's five measured non-registry IDs (client-gated reconciliation; two of
# them seed the fixture's miss ledger)
KNOWN_UNRESOLVED_TERM_IDS = (-1168948158, -2044546668, -1942168175,
                             -1451566921, -1172386361)
MISS_TERM_IDS = (KNOWN_UNRESOLVED_TERM_IDS[0], KNOWN_UNRESOLVED_TERM_IDS[4])

B_ROOMS = "TPC_Data/StreamingAssets/aa/StandaloneWindows64/rooms_assets_all.bundle"
B_ITEMS = "TPC_Data/StreamingAssets/aa/StandaloneWindows64/items-general_assets_all.bundle"
B_CONFIGS = "TPC_Data/StreamingAssets/aa/StandaloneWindows64/configs_assets_all.bundle"
B_COURSE = "TPC_Data/StreamingAssets/aa/StandaloneWindows64/items-courses-magic_assets_all.bundle"
B_SHARED = "TPC_Data/StreamingAssets/aa/StandaloneWindows64/character-shared_assets_all.bundle"
B_UNLOCK = "TPC_Data/StreamingAssets/aa/StandaloneWindows64/unlockables_assets_all.bundle"
B_META = "TPC_Data/StreamingAssets/aa/StandaloneWindows64/configs-metagame_assets_all.bundle"
B_UI = "TPC_Data/StreamingAssets/aa/StandaloneWindows64/ui_assets_all.bundle"
B_SCENE = ("TPC_Data/StreamingAssets/aa/StandaloneWindows64/"
           "scenes-scene-campus1.unity.bundle")
CAB_ITEMS_A = "CAB-2f6a1itemsa"
CAB_ITEMS_B = "CAB-2f6b1itemsb"
CAB_SCENES = "CAB-9scenescampus1"

# --- hand-computed edge oracle (what the walkers MUST emit) ------------------------

PPTR_STRUCT = lambda fid, pid: {"m_FileID": fid, "m_PathID": pid}  # noqa: E731


def loc_field(dev, term_id):
    """The LocalisedString instance shape measured on the corpus."""
    return {"_dev": dev, "_termID": term_id}


def icon_ref(guid, sub=None):
    ref = {"m_AssetGUID": guid}
    if sub is not None:
        ref["m_SubObjectName"] = sub
    return ref


EXPECTED_PAIR_EDGES = [
    # (srcKind, srcId, dstKind, dstId, method, fieldPath, refCount)
    ("config", ANCHOR_GRAPH_SRC, "config", ANCHOR_GRAPH_DST,
     "pptr-same-file", "ParticipantsGraph", 1),
    ("course", "Course_Archaeology", "config", COURSE_MODULE_ID,
     "pptr-same-file", "Modules[].Definition", 1),
    ("room", ANCHOR_ROOM, "item", ANCHOR_ITEM,
     "pptr-same-file", "RequiredItems[].DefaultItem", 2),
    ("room", ANCHOR_ROOM, "item", ANCHOR_ITEM,
     "pptr-same-file", "RequiredWorkingItems[]", 1),
]
EXPECTED_CROSS_FILE_EDGES = [
    ("config", ANCHOR_GRAPH_SRC, "item", TWIN_ID, "pptr-cross-file", "Graph", 1),
]
EXPECTED_SCENE_EDGES = [
    # pptr-resolved target inside a sceneFlag != none bundle, not a stub
    ("room", ANCHOR_ROOM, "scene", Path(B_SCENE).name.replace(".bundle", ""),
     "pptr-cross-file", "SceneProp", 1),
]
EXPECTED_UNRESOLVED = [
    # (srcKind, srcId, fieldPath, reason-class)
    ("config", ANCHOR_GRAPH_SRC, "GhostRef", "unknown-file-id"),
    ("config", ANCHOR_GRAPH_SRC, "BuiltinRef", "builtin-external"),
    ("metagame-node", "Node_Research_Tree", "references.0001.data.Course",
     "dangling-path-id"),
    ("room", ANCHOR_ROOM, "DeadRef", "dangling-path-id"),
]
EXPECTED_GUID_ASSET_EDGES = [
    # (srcKind, srcId, fieldPath, catalogAddress)
    ("campus-level", "CampusLevel_Metagame", "LevelConfig.m_AssetGUID", ART_ADDRESS),
    ("campus-level", "CampusLevel_Metagame", "MetagameConfig.m_AssetGUID", META_ADDRESS),
    ("campus-level", "CampusLevel_Metagame", "SceneBanner.m_AssetGUID", SCENE_ADDRESS),
    ("config", ANCHOR_GRAPH_SRC, "IconReference", ART_ADDRESS),
    ("config", "Config_Dangling_Guid_Holder", "IconReference", None),  # placeholder: never emits
    ("staff", ANCHOR_STAFF, "IconReference", ART_ADDRESS),
]
EXPECTED_GUID_ASSET_EDGES = [e for e in EXPECTED_GUID_ASSET_EDGES if e[3] is not None]
EXPECTED_GUID_PAIR_EDGES = [
    ("campus-level", "CampusLevel_Metagame", "metagame-node", "Node_Research_Tree",
     "MetagameConfig.m_AssetGUID"),
]
EXPECTED_GUID_SCENE_EDGES = [
    ("campus-level", "CampusLevel_Metagame", "scene",
     Path(B_SCENE).name.replace(".bundle", ""), "SceneBanner.m_AssetGUID"),
]
EXPECTED_DANGLING_GUIDS = [GUID_DANGLING]

# --- synthetic corpus rows ----------------------------------------------------------

def _ptr_edge_fields():
    return {
        "m_GameObject": PPTR_STRUCT(0, 0),                      # excluded zero-target
        "m_Script": PPTR_STRUCT(1, -9000000000000000001),       # excluded script leaf
    }


def relink_entities():
    """(kind, class, bundle-relpath, stem, pathId, fields) — the stub corpus."""
    aa = "TPC_Data/StreamingAssets/aa/StandaloneWindows64"
    return [
        ("config", "TPC.ActivityConfig", B_CONFIGS, "configs_assets_all", 1001, {
            **_ptr_edge_fields(),
            "Title": loc_field("Caterer activity", 10001),
            "ParticipantsGraph": PPTR_STRUCT(0, ANCHOR_DST_PID),  # signed same-file
            "Graph": PPTR_STRUCT(1, 3500),                      # cross-file -> twin
            "GhostRef": PPTR_STRUCT(9, 1),                      # unknown fileId
            "BuiltinRef": PPTR_STRUCT(2, 5),                    # built-in external
            "IconReference": icon_ref(GUID_ART, "sheet_caterer"),
        }),
        ("config", "TPC.BGCharacterConfig", B_CONFIGS, "configs_assets_all",
         ANCHOR_DST_PID, {
            **_ptr_edge_fields(),
            "DisplayName": loc_field("BG caterer", 20001),
        }),
        ("config", "TPC.ItemConfig", B_CONFIGS, "configs_assets_all", 1003, {
            **_ptr_edge_fields(),
            "IconReference": icon_ref(GUID_DANGLING),
        }),
        # the course's own-bundle module definition (see COURSE_MODULE_ID note)
        ("config", "TPC.CourseModuleDefinition", B_COURSE,
         "items-courses-magic_assets_all", 1002, {
            **_ptr_edge_fields(),
            "DisplayName": loc_field("Archaeology module", 20001),
        }),
        ("campus-level", "TPC.CampusLevelConfig", B_CONFIGS, "configs_assets_all",
         1005, {
            **_ptr_edge_fields(),
            "Name": loc_field("Campus one", 10001),
            "LevelConfig": {"m_AssetGUID": GUID_ART},
            "MetagameConfig": {"m_AssetGUID": ANCHOR_LEVEL_GUID},
            "SceneBanner": {"m_AssetGUID": GUID_SCENE},
        }),
        # ADAPTED 2026-08-25: the anchor item is resident in the ROOMS bundle
        # (dependent-definition duplication — same-file PPtr target), not in
        # items-general; items-general now carries only the twin endpoint.
        ("item", "TPC.ItemConfig", B_ROOMS, "rooms_assets_all", 3001, {
            **_ptr_edge_fields(),
            "Name": loc_field("Archaeology door", 10003),
            "Price": 12,
        }),
        ("item", "TPC.ItemConfig", B_ITEMS, "items-general_assets_all", 3500, {
            **_ptr_edge_fields(),
            "id": TWIN_BARE_ID,          # verbatim original preserved (F10)
            "Variant": "b",
        }),
        ("room", "TPC.RoomConfig", B_ROOMS, "rooms_assets_all", 2001, {
            **_ptr_edge_fields(),
            "RequiredItems": [
                {"DefaultItem": PPTR_STRUCT(0, 3001)},
                {"DefaultItem": PPTR_STRUCT(0, 3001)},          # repeat -> refCount 2
            ],
            "RequiredWorkingItems": [PPTR_STRUCT(0, 3001)],
            "SceneProp": PPTR_STRUCT(1, 7001),                  # -> scene node
            "DeadRef": PPTR_STRUCT(1, 7999),                    # dangling pathId
        }),
        ("course", "TPC.CourseConfig", B_COURSE, "items-courses-magic_assets_all",
         4001, {
            **_ptr_edge_fields(),
            "Modules": [{"Definition": PPTR_STRUCT(0, 1002)}],
        }),
        ("staff", "TPC.StaffConfig", B_SHARED, "character-shared_assets_all", 5001, {
            **_ptr_edge_fields(),
            "LocalisedName": loc_field("Assistant", STAFF_TERM_ID),   # §2 anchor
            "IconReference": icon_ref(GUID_ART),
        }),
        ("student-type", "TPC.StudentTypeConfig", B_SHARED,
         "character-shared_assets_all", 5002, {
            **_ptr_edge_fields(),
            "Name": loc_field("Nerd", 10004),
         }),
        ("student-type", "TPC.StudentTypeConfig", B_SHARED,
         "character-shared_assets_all", 5003, {
            **_ptr_edge_fields(),
            "Name": loc_field("dev only", 0),                   # sentinel -> counted
         }),
        ("student-type", "TPC.StudentTypeConfig", B_SHARED,
         "character-shared_assets_all", 5004, {
            **_ptr_edge_fields(),
            "Name": loc_field("mystery", MISS_TERM_IDS[0]),     # registry miss
         }),
        ("unlockable", "TPC.UnlockableConfig", B_UNLOCK, "unlockables_assets_all",
         6001, {
            **_ptr_edge_fields(),
            "Description": loc_field("kudosh chair", MISS_TERM_IDS[1]),
            "Levels": ["Level_Metagame_01"],                    # probe-cell substrate
            "CostKudosh": 120,
         }),
        ("metagame-node", "TPC.MetagameNodeConfig", B_META,
         "configs-metagame_assets_all", 1004, {
            **_ptr_edge_fields(),
            "references": {"0001": {"data": {"Course": PPTR_STRUCT(1, 8001)}}},
         }),
    ]


def relink_stub_rows():
    """kind -> list of piece-1-pinned stub rows (sorted by id)."""
    named = {
        1001: ANCHOR_GRAPH_SRC, ANCHOR_DST_PID: ANCHOR_GRAPH_DST,
        1002: COURSE_MODULE_ID,
        1003: "Config_Dangling_Guid_Holder", 1004: "Node_Research_Tree",
        1005: "CampusLevel_Metagame", 3001: ANCHOR_ITEM, 3500: TWIN_ID,
        2001: ANCHOR_ROOM, 4001: "Course_Archaeology", 5001: ANCHOR_STAFF,
        5002: "StudentType_Nerd", 5003: "StudentType_Dev",
        5004: "StudentType_Mystery", 6001: "Unlock_Kudosh_Chair",
    }
    out: dict[str, list[dict]] = {k: [] for k in STUB_KINDS}
    for kind, cls, bundle, stem, pid, fields in relink_entities():
        out[kind].append({
            "id": named[pid], "kind": kind, "slug": None, "fields": fields,
            "source": {"bundle": Path(bundle).name, "class": cls, "pathId": pid},
            "provisional": True, "inferred": True,
            "method": "seeded-class-heuristic", "buildId": BUILD_ID,
        })
    for rows in out.values():
        rows.sort(key=lambda r: r["id"])
    return out


def stub_index():
    """(bundle filename, pathId) -> (kind, emitted id) — the identity table the
    cross-file/GUID resolvers match against."""
    idx = {}
    for kind, rows in relink_stub_rows().items():
        for r in rows:
            idx[(r["source"]["bundle"], r["source"]["pathId"])] = (kind, r["id"])
    return idx


def roster_scene_ids():
    """Roster relpaths (basename-with-extension stripped per the attribution
    rule examples) of scene-carrying rows in the relink tree."""
    return {r["relpath"] for r in fx.roster_rows() if r["sceneFlag"] != "none"}


# --- bridges substrate (resolver INPUTS + R1 expectations over the fake envs) -------

class FakeObj:
    """Minimal UnityPy-object stand-in: path_id + class name."""

    def __init__(self, path_id, class_name):
        self.path_id = path_id
        self.type = type("T", (), {"name": class_name})()


class FakeSerializedFile:
    def __init__(self, name, objects: dict[int, FakeObj]):
        self.name = name
        self.objects = objects


class FakeEnv:
    """Minimal UnityPy-env stand-in: `.files` + `.container`."""

    def __init__(self, files, container=None):
        self.files = files
        self.container = container or {}


def bridge_envs():
    """bundle basename -> FakeEnv describing the synthetic serialized-file
    layout (the de-facto fixture contract stage 6's R1 may also accept)."""
    objs = {}
    for kind, rows in relink_stub_rows().items():
        for r in rows:
            b, pid = r["source"]["bundle"], r["source"]["pathId"]
            objs.setdefault(b, {})[pid] = FakeObj(pid, r["source"]["class"])
    # scene-bundle non-stub objects (7001 attributed to scene; 8001 ABSENT on
    # purpose -> dangling-path-id; 8002 unreferenced filler)
    scene_objs = {7001: FakeObj(7001, "GameObject"),
                  8002: FakeObj(8002, "GameObject")}
    atlas = {9999: FakeObj(9999, "SpriteAtlas")}
    envs = {}
    for b, o in objs.items():
        if b == "items-general_assets_all.bundle":
            a = {p: obj for p, obj in o.items() if p != 3500}
            bb = {3500: o[3500]}
            envs[b] = FakeEnv([FakeSerializedFile(CAB_ITEMS_A, a),
                               FakeSerializedFile(CAB_ITEMS_B, bb)])
        elif b == "configs_assets_all.bundle":
            envs[b] = FakeEnv([FakeSerializedFile("CAB-1configsmain", o)])
        else:
            envs[b] = FakeEnv([FakeSerializedFile(f"CAB-x{b.split('_')[0]}", o)])
    envs["scenes-scene-campus1.unity.bundle"] = FakeEnv(
        [FakeSerializedFile(CAB_SCENES, scene_objs)])
    envs["ui_assets_all.bundle"] = FakeEnv(
        [FakeSerializedFile("CAB-uiatlas", atlas)])
    # container maps (address -> object)
    envs["configs-metagame_assets_all.bundle"].container = {
        META_ADDRESS: FakeObj(1004, "MonoBehaviour")}
    envs["ui_assets_all.bundle"].container = {
        ART_ADDRESS: FakeObj(9999, "SpriteAtlas")}
    envs["scenes-scene-campus1.unity.bundle"].container = {
        SCENE_ADDRESS: FakeObj(7001, "GameObject")}
    return envs


def externals_rows():
    """harvest/externals.jsonl content — LANDED SHAPE (byte-verified against
    extracted/harvest/externals.jsonl 2026-08-25: 222 rows): ONE ROW PER
    SERIALIZED FILE `{bundle, sourceFile, externals:[{fileId, guid, path,
    type}]}`, sourceFile spelled LOWERCASE (real sample 'cab-f961…')."""
    ext = lambda fid, path: {"fileId": fid, "guid": "0" * 32, "path": path,  # noqa: E731
                             "type": 0}

    by_row = {
        (Path(B_ROOMS).name, "cab-xrooms"): [
            ext(1, f"archive:/{CAB_SCENES}"),
            ext(2, "Library/unity default resources")],
        (Path(B_CONFIGS).name, "cab-1configsmain"): [
            ext(1, f"archive:/{CAB_ITEMS_B}"),
            ext(2, "Library/unity default resources")],
        (Path(B_META).name, "cab-xconfigs-metagame"): [
            ext(1, f"archive:/{CAB_SCENES}")],
        (Path(B_ITEMS).name, CAB_ITEMS_A.lower()): [],
        (Path(B_ITEMS).name, CAB_ITEMS_B.lower()): [],
        (Path(B_SCENE).name, CAB_SCENES.lower()): [],
        (Path(B_UI).name, "cab-uiatlas"): [],
    }
    # every remaining roster bundle in the fixture world gets its (empty)
    # per-serialized-file row so the sidecar stays complete over bridge_envs()
    special = {Path(b).name for b in (B_ITEMS, B_SCENE, B_UI, B_ROOMS,
                                      B_CONFIGS, B_META)}
    for kind_rows in relink_stub_rows().values():
        for r in kind_rows:
            b = Path(r["source"]["bundle"]).name
            if b not in special:
                by_row.setdefault((b, f"cab-x{b.split('_')[0]}"), [])
    return [{"bundle": b, "sourceFile": sf, "externals": exs}
            for (b, sf), exs in sorted(by_row.items())]


def externals_by_bundle():
    """bundle basename -> merged externals list (rows are per serialized
    file; unit probes usually want one flat list per bundle)."""
    out: dict[str, list] = {}
    for r in externals_rows():
        out.setdefault(r["bundle"], []).extend(r["externals"])
    return out


def cab_index_seed_rows():
    """The cab_index.jsonl rows R1 must derive from `bridge_envs()` (sorted by
    (bundle, cab)); doubles as resolver input for hostless cross-file tests."""
    rows = []
    for b, env in bridge_envs().items():
        for sf in env.files:
            rows.append({
                "bundle": b, "cab": sf.name,
                "objects": [{"pathId": pid, "class": obj.type.name}
                            for pid, obj in sorted(sf.objects.items())],
                "buildId": BUILD_ID})
    rows.sort(key=lambda r: (r["bundle"], r["cab"]))
    return rows


def container_index_seed_rows():
    rows = [
        {"bundle": Path(B_META).name, "address": META_ADDRESS,
         "pathId": 1004, "class": "MonoBehaviour", "buildId": BUILD_ID},
        {"bundle": Path(B_SCENE).name, "address": SCENE_ADDRESS,
         "pathId": 7001, "class": "GameObject", "buildId": BUILD_ID},
        {"bundle": Path(B_UI).name, "address": ART_ADDRESS,
         "pathId": 9999, "class": "SpriteAtlas", "buildId": BUILD_ID},
    ]
    rows.sort(key=lambda r: (r["bundle"], r["address"]))
    return rows


# --- catalog / locale matrix / I2 dumps ----------------------------------------------

def relink_catalog_keys():
    """Stage-2-style catalog rows PLUS the guid-kind keys R3 filters (landed
    shape: guid rows carry `address`, `bundle: null`)."""
    deps = []
    prov = ["ContentCatalogProvider", "BundledAssetProvider"]
    rows = []
    for k, ref in fx.CATALOG_KEYS_SPEC:      # keep the stage-2 fixture keys
        rows.append({"key": k, "kind": "bundle", "bundle": ref, "address": None,
                     "dependencies": deps, "providerIds": prov})
    for guid, address in ((ANCHOR_LEVEL_GUID, META_ADDRESS),
                          (GUID_ART, ART_ADDRESS),
                          (GUID_SCENE, SCENE_ADDRESS)):
        rows.append({"key": guid, "kind": "guid", "bundle": None,
                     "address": address, "dependencies": deps,
                     "providerIds": prov})
    rows.sort(key=lambda r: r["key"])
    return rows


TERM_TABLE = [
    # (termId, termKey, sourceDump, locales-non-empty-in-order)
    (STAFF_TERM_ID, STAFF_TERM_KEY, "langsource_main.json", ["en"]),
    (10001, "UI/Configs/Activity_Caterer_Title", "langsource_main.json", ["en", "fr"]),
    (20001, "UI/General/Common/Ok", "langsource_main.json", ["en", "de"]),
    (20002, "UI/General/Common/Ok", "langsource_main.json", ["en"]),  # dupe ID/key G10
    (10003, "UI/Items/Archaeology_Door_Name", "langsource_alt.json", ["en", "ja"]),
    (10004, "UI/Students/Nerd_Name", "langsource_alt.json", ["en"]),
]
REGISTRY_ROWS = len(TERM_TABLE)              # 6
REGISTRY_DISTINCT_KEYS = len({t[1] for t in TERM_TABLE})      # 5


def relink_locale_matrix_obj():
    keys = {}
    for tid, key, _src, locs in TERM_TABLE:
        cur = keys.setdefault(key, {"inBase": False, "locales": []})
        cur["locales"] = sorted(set(cur["locales"]) | set(locs))
    return {"buildId": BUILD_ID, "keys": keys,
            "locales": sorted(LOCALE_TABLE.values())}


def i2_dump_sources():
    """LanguageSource dump payloads keyed by filename (mLanguages order is
    deliberately NOT canonical BCP-47 order — per-term locales[] must be
    indexed by THIS order)."""
    main_langs = [{"Name": "French", "Code": "fr"},
                  {"Name": "English", "Code": "en"},
                  {"Name": "German", "Code": "de"}]
    alt_langs = [{"Name": "English", "Code": "en"},
                 {"Name": "Japanese", "Code": "ja"}]

    def cells(order, filled):
        # per-language text cells indexed by the SOURCE's mLanguages order
        # (ADAPTED 2026-08-25: the previous `zip(order, filled)` paired the
        # language objects with a dict's KEYS — a type misuse that shifted
        # every text one slot; the intent was always code-keyed lookup)
        return [filled.get(l["Code"], "") for l in order]

    def wrap(name, langs, terms):
        return {"_decoded": {"method": "typetree+synthesis", "typetreeDecoded": True},
                "_scriptClass": "I2.Loc.LanguageSourceAsset",
                "_sourceFile": name, "m_Enabled": 1,
                "m_GameObject": {"m_FileID": 0, "m_PathID": 0},
                "m_Name": "LanguageSource",
                "m_Script": {"m_FileID": 1, "m_PathID": -7280612792328863924},
                "mSource": {"mLanguages": langs, "mTerms": terms,
                            "Assets": [], "CaseInsensitiveTerms": 0}}

    fr, en, de = "fr", "en", "de"
    main_terms = [
        {"ID": STAFF_TERM_ID, "Term": STAFF_TERM_KEY, "TermType": 0,
         "TermStatus": 1, "Flags": [0, 0, 0],
         "Languages": cells(main_langs, {en: "Assistant"}),
         "Languages_Touch": ["2024-01-01"]},   # ignored safely
        {"ID": 10001, "Term": "UI/Configs/Activity_Caterer_Title", "TermType": 0,
         "TermStatus": 1, "Flags": [0, 0, 0],
         "Languages": cells(main_langs, {en: "Caterer title", fr: "Titre traiteur"}),
         "Languages_Touch": []},
        {"ID": 20001, "Term": "UI/General/Common/Ok", "TermType": 0,
         "TermStatus": 1, "Flags": [0, 0, 0],
         "Languages": cells(main_langs, {en: "OK", de: "OK"}),
         "Languages_Touch": []},
        {"ID": 20002, "Term": "UI/General/Common/Ok", "TermType": 0,
         "TermStatus": 1, "Flags": [0, 0, 0],
         "Languages": cells(main_langs, {en: "OK"}), "Languages_Touch": []},
    ]
    alt_terms = [
        {"ID": 10003, "Term": "UI/Items/Archaeology_Door_Name", "TermType": 0,
         "TermStatus": 1, "Flags": [0, 0],
         "Languages": cells(alt_langs, {en: "Door", "ja": "ドア"}),
         "Languages_Touch": []},
        {"ID": 10004, "Term": "UI/Students/Nerd_Name", "TermType": 0,
         "TermStatus": 1, "Flags": [0, 0],
         "Languages": cells(alt_langs, {en: "Nerd"}), "Languages_Touch": []},
    ]
    return {
        "langsource_main.json": wrap("langsource_main", main_langs, main_terms),
        "langsource_alt.json": wrap("langsource_alt", alt_langs, alt_terms),
    }


# --- UI-link coverage substrate -------------------------------------------------------

SEEDED_SURFACE_UI_CLASSES = (
    "CourseManagementMenu_Requirements",
    "InspectorRoomCourseItem",
    "TrainingMenu_Qualification",
    "ResearchProjectInspector",
    "ResearchBaseUI",
    "StaffJobAssignmentUI",
    "CampusEventMenu",
    "InboxMenuMessageUI_PersonalGoalRequest",
    "ObjectiveView",
)
LOCALIZE_CLASS = "I2.Loc.Localize"
TOOLTIP_CLASS = "TPC.TooltipSpawner"
# tooltip TARGET classes the spawner dumps enumerate; the last one is covered
# by NO mapped definitionClass -> the anchor-rule partition must flag it
TOOLTIP_TARGETS = ("TPC.CourseModuleDefinition", "TPC.RoomConfig",
                   "TPC.MysteryUncoveredTarget")
DISCOVERY_FLOOR_PROBE_CLASS = "WidgetMenuUnknown"   # *Menu* -> mapped XOR gap REQUIRED


def tooltip_dump_rows():
    """Three TooltipSpawner dumps whose own fields enumerate the target census."""
    return [
        ("ui", TOOLTIP_CLASS, "ui_assets_all", 8801,
         {"TargetType": TOOLTIP_TARGETS[0], "TipKey": 10001}),
        ("ui", TOOLTIP_CLASS, "ui_assets_all", 8802,
         {"TargetType": TOOLTIP_TARGETS[1], "TipKey": 10003}),
        ("ui", TOOLTIP_CLASS, "ui_assets_all", 8803,
         {"TargetType": TOOLTIP_TARGETS[2], "TipKey": 0}),
    ]


# --- competitor model CONTENT (unit-level only; NEVER written to data/) ---------------

def competitor_model_rows(source="fandom"):
    """model.jsonl rows (community naming, NOT our ids) exercising every
    disposition: confirms-hard (verbatim ids), convention-match (casefold +
    underscore/space), flags-missing (unresolvable)."""
    return [
        {"subjectKind": "course", "subjectName": "Course_Archaeology",
         "relationVerb": "teaches-modules-of", "objectKind": "config",
         "objectName": ANCHOR_GRAPH_DST, "cardinalityClaim": "1..N",
         "notes": "module table", "sourcePage": "https://fixture.invalid/courses"},
        {"subjectKind": "room", "subjectName": ANCHOR_ROOM,
         "relationVerb": "requires", "objectKind": "item",
         "objectName": ANCHOR_ITEM, "sourcePage": "https://fixture.invalid/rooms"},
        {"subjectKind": "room", "subjectName": "room archaeology display",
         "relationVerb": "requires", "objectKind": "item",
         "objectName": "item_door_building_archaeology_display",
         "sourcePage": "https://fixture.invalid/convention"},
        {"subjectKind": "config", "subjectName": "Nonexistent Widget Thing",
         "relationVerb": "grants", "objectKind": "unlockable",
         "objectName": "Unlock_Kudosh_Chair",
         "sourcePage": "https://fixture.invalid/missing"},
    ]


# --- resolve-rate arithmetic fixtures (R3.5 exactness) --------------------------------

def resolve_rate_one_to_one_case():
    """Six GUIDs, each referenced EXACTLY ONCE -> refs == distinct, so
    resolveRate formulas coincide and the fixture pins exact arithmetic:
    resolvedToAddress=4, resolvedToStub=2, dangling=2, rates 4/6 and 2/6."""
    stub_hit = ("config", "Cfg_A", 1001, True)
    cases = [
        dict(guid="g1-stub", address="Assets/a1", container=(B_META, 1004),
             stub=("metagame-node", "Node_Research_Tree")),
        dict(guid="g2-stub", address="Assets/a2", container=(B_META, 1004),
             stub=("metagame-node", "Node_Research_Tree")),
        dict(guid="g3-asset", address="Assets/a3", container=(B_UI, 9999),
             stub=None),
        dict(guid="g4-asset", address="Assets/a4", container=(B_UI, 9999),
             stub=None),
        dict(guid="g5-dangle", address=None, container=None, stub=None),
        dict(guid="g6-dangle", address=None, container=None, stub=None),
    ]
    expect = {"guidRefsTotal": 6, "distinctGuids": 6, "resolvedToAddress": 4,
              "resolvedToStub": 2, "danglingDistinctGuids": 2,
              "resolveRateAddress": 4 / 6, "resolveRateStub": 2 / 6}
    return cases, expect


# --- prepared-tree assembly (Revision 7 amendment 3) ----------------------------------

def _absences_row():
    return {"absenceType": "no-identifier", "buildId": BUILD_ID,
            "kind": "staff", "count": 0,
            "evidence": "fixture placeholder — stage-5 ledger shape mirrored"}


def _unmapped_row():
    return {"class": DISCOVERY_FLOOR_PROBE_CLASS,
            "bundles": [Path(B_UI).name], "objectCount": 1,
            "evidence": "no seeded kind covers this class"}


def availability_v1_row():
    """A stage-5-owned locale_availability.jsonl row (v1 schema, foreign to
    stage 6) so the sole-owner/isolation legs can prove stage 6 never touches
    the file."""
    return {"kind": "staff", "id": ANCHOR_STAFF,
            "availableLocales": ["en"], "namedLocales": ["en"],
            "fieldPresence": {"en": ["LocalisedName"]},
            "joinInferred": False, "joinMethod": "", "buildId": BUILD_ID}


def relink_export_manifest_append():
    """Manifest rows for every synthetic stub + tooltip dump + the atlas
    object, appended onto the cumulative stage-2..5 fixture manifest."""
    rows = []
    for kind, cls, bundle, stem, pid, _f in relink_entities():
        rel = f"harvest/monobehaviours/{kind}/{cls}/{stem}_{pid}.json"
        rows.append({"sourceBundle": Path(bundle).name, "pathId": pid,
                     "class": cls, "bytes": 256, "outRelPath": rel})
    for family, cls, stem, pid, _f in tooltip_dump_rows():
        rel = f"harvest/monobehaviours/{family}/{cls}/{stem}_{pid}.json"
        rows.append({"sourceBundle": f"{stem}.bundle", "pathId": pid,
                     "class": cls, "bytes": 256, "outRelPath": rel})
    rel = "harvest/monobehaviours/ui/SpriteAtlas/ui_assets_all_9999.json"
    rows.append({"sourceBundle": Path(B_UI).name, "pathId": 9999,
                 "class": "SpriteAtlas", "bytes": 256, "outRelPath": rel})
    return rows


def build_relink_upstream(extracted: Path) -> Path:
    """Materialize the §3/Rev-7 stage-6 upstream set synthetically (extracted
    side). Idempotent + byte-deterministic; NEVER writes under relinks/."""
    extracted = Path(extracted)

    # stubs/** ×9 + ledgers + the stage-5-owned availability file (untouched)
    for kind, rows in relink_stub_rows().items():
        fname = fx_roster_style_kind_file(kind)
        write_jsonl(extracted / "stubs" / fname, rows)
    write_jsonl(extracted / "stubs" / "_absences.jsonl", [_absences_row()])
    write_jsonl(extracted / "stubs" / "_unmapped-families.jsonl", [_unmapped_row()])
    write_jsonl(extracted / "relinks" / "locale_availability.jsonl",
                [availability_v1_row()])

    harv = extracted / "harvest"
    # export-manifest: cumulative rows (existing fixture rows + ours), sorted
    man_path = harv / "export-manifest.jsonl"
    existing = read_jsonl(man_path) if man_path.exists() else []
    merged = {r["outRelPath"]: r for r in existing}
    for r in relink_export_manifest_append():
        merged.setdefault(r["outRelPath"], r)
    write_jsonl(man_path, sorted(merged.values(), key=lambda r: r["outRelPath"]))
    write_jsonl(harv / "externals.jsonl",
                sorted(externals_rows(), key=lambda r: r["bundle"]))

    # physical dumps backing the manifest rows (empty payloads suffice: stage 6
    # reads stubs/, not these; presence keeps the tree self-consistent)
    for kind, cls, bundle, stem, pid, _f in relink_entities():
        p = harv / "monobehaviours" / kind / cls / f"{stem}_{pid}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("{}\n", encoding="utf-8", newline="\n")
    for family, cls, stem, pid, fields in tooltip_dump_rows():
        p = harv / "monobehaviours" / family / cls / f"{stem}_{pid}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"_scriptClass": cls, "fields": fields},
                                sort_keys=True) + "\n",
                     encoding="utf-8", newline="\n")

    # I2 LanguageSourceAsset dumps (F7 glob path)
    i2dir = (harv / "monobehaviours" / "localisation_assets_localisation"
             / "I2.Loc.LanguageSourceAsset")
    i2dir.mkdir(parents=True, exist_ok=True)
    for name, payload in sorted(i2_dump_sources().items()):
        (i2dir / name).write_text(
            json.dumps(payload, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8", newline="\n")

    # catalog: stage-2 fixture keys + guid-kind keys (sorted by key)
    cat = {"meta": {"buildId": BUILD_ID,
                    "addressablesVersion": fx.ADDRESSABLES_VERSION
                    if hasattr(fx, "ADDRESSABLES_VERSION") else "1.21.10",
                    "settingsHash": fx.SETTINGS_HASH,
                    "providerIds": ["ContentCatalogProvider"]},
           "keys": relink_catalog_keys()}
    (extracted / "addressables" / "catalog.json").write_text(
        json.dumps(cat, indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n")

    # locale-matrix: keys == registry term keys (bidirectional diff 0)
    (extracted / "locales" / "locale-matrix.json").write_text(
        json.dumps(relink_locale_matrix_obj(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n")
    return extracted


def fx_roster_style_kind_file(kind: str) -> str:
    """kind value ↔ filename map (piece-1 §3 stage 5, pinned)."""
    return {
        "item": "items.jsonl", "unlockable": "unlockables.jsonl",
        "room": "rooms.jsonl", "campus-level": "campus-levels.jsonl",
        "course": "courses.jsonl", "config": "configs.jsonl",
        "staff": "staff.jsonl", "metagame-node": "metagame-nodes.jsonl",
        "student-type": "student-types.jsonl",
    }[kind]


PROBE_HEADER_BUNDLES = {
    # bundle basename -> header flavor for the Revision-4 seeding probes
    "rooms_assets_all.bundle": "zero",
    "configs_assets_all.bundle": "garbage",
    "items-general_assets_all.bundle": "true-version",
}


def stamp_probe_headers(tree: Path):
    """Overwrite three roster bundles' bytes with the shared stage-3/4 seeding
    substrates (0.0.0 header / garbage / true engine version) so the R1
    fallback-version flip is exercisable hostless."""
    tree = Path(tree)
    probes = fx.write_seed_probe_bundles(tree / "_seed_probes")
    stamped = []
    for row in fx.roster_rows():
        basename = Path(row["relpath"]).name
        flavor = PROBE_HEADER_BUNDLES.get(basename)
        if flavor:
            dst = fx.game_root(tree) / row["relpath"]
            dst.write_bytes(probes[flavor].read_bytes())
            stamped.append((basename, flavor))
    return dict(stamped)


def build_relink_tree(out: Path, *, full_scale: bool = False) -> Path:
    """Cumulative relink prepared tree: client-input fakes + stage-0..5
    fixture outputs + the §3 stage-6 upstream set + probe-header bundles."""
    out = Path(out)
    fx.build_tree(out, "emit-stub-datasets", full_scale=full_scale)
    build_relink_upstream(out / "extracted")
    stamp_probe_headers(out)
    return out


def copy_upstream_set(src_extracted: Path, dst_extracted: Path) -> Path:
    """Copy JUST the stage-6 upstream set from a real extraction root into a
    private temp root, so client-gated `--only relink` runs stay cheap and
    never touch the shared tree. Returns the destination root."""
    import shutil
    src = Path(src_extracted)
    dst = Path(dst_extracted)
    dst.mkdir(parents=True, exist_ok=True)

    def cp_file(rel):
        s = src / rel
        if s.exists():
            d = dst / rel
            d.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(s, d)
            return True
        return False

    def cp_dir(rel):
        s = src / rel
        if s.is_dir():
            shutil.copytree(s, dst / rel, dirs_exist_ok=True)
            return True
        return False

    copied = []
    stubs = src / "stubs"
    if stubs.is_dir():
        for p in sorted(stubs.glob("*.jsonl")):
            cp_file(Path("stubs") / p.name)
            copied.append(p.name)
    for rel in ("harvest/export-manifest.jsonl", "harvest/externals.jsonl",
                "addressables/catalog.json", "locales/locale-matrix.json",
                "bundle-roster.jsonl", "identity.json",
                "relinks/locale_availability.jsonl"):
        assert cp_file(rel), f"real upstream artifact missing: {rel}"
        copied.append(rel)
    assert cp_dir("decompiled/structural"), "decompiled/structural missing"
    i2rel = Path("harvest/monobehaviours/localisation_assets_localisation/"
                 "I2.Loc.LanguageSourceAsset")
    assert cp_dir(i2rel), "I2 LanguageSourceAsset dumps missing"
    return dst


# --- loud gating helpers ---------------------------------------------------------------

_REGISTERED_CACHE: dict[str, bool] = {}


def require_relink_registered():
    """Loud gate for black-box stage-6 legs: `--list` must enumerate `relink`.

    Skips (visibly, counted in the session IMPL-MISSING banner) until the
    CodeWriter registers the seventh stage — never fakes a pass, never fails
    red for mere delivery lag."""
    import pytest
    from conftest import run_pack
    cached = _REGISTERED_CACHE.get("relink")
    if cached is None:
        r = run_pack(["--list"])
        cached = r.returncode == 0 and "relink" in r.stdout
        if not cached and r.returncode == 0:
            from _impl import note_missing_module
            note_missing_module("run_all.py --list: stage 'relink' not registered "
                                "yet (piece-02 CodeWriter pending)")
        _REGISTERED_CACHE["relink"] = cached
    if not cached:
        pytest.skip("impl-lagging: stage 'relink' not registered by the runner yet "
                    "(piece-02 CodeWriter pending)")


# --- validators (return error lists; [] == valid) --------------------------------------

_PAIR_ROW_KEYS = {"srcKind", "srcId", "dstKind", "dstId", "mechanism", "method",
                  "inferred", "evidence", "buildId"}
_EVIDENCE_BASE = {"fieldPath"}
_EVIDENCE_BY_METHOD = {
    "pptr-same-file": {"fieldPath", "srcBundle", "srcPathId", "dstBundle",
                       "dstPathId", "refCount"},
    "pptr-cross-file": {"fieldPath", "srcBundle", "srcPathId", "dstBundle",
                        "dstPathId", "refCount", "extFileId", "dstCab",
                        "resolvedVia"},
    "assetguid-catalog": {"fieldPath", "assetGuid", "catalogAddress"},
}
_LOCALE_TERM_KIND = "locale-term"


def _err(e, m):
    e.append(m)


def validate_join_key(v, where=""):
    e = []
    if v in JOIN_KEY_LITERAL or v == JOIN_KEY_NONE:
        return e
    if isinstance(v, str) and v.startswith(JOIN_KEY_PREFIXED) and v.endswith(")"):
        return e
    _err(e, f"{where}joinKey {v!r} outside the frozen vocabulary")
    return e


def validate_pair_row(row, where="", overlay=False):
    """Frozen pair-dataset row shape (exact key sets, enums, evidence per
    method, provenance flags). `overlay=True` relaxes dstKind to the
    community plane but keeps the same core shape."""
    e = []
    if not isinstance(row, dict):
        return [f"{where}row is not an object"]
    extra = set(row) - _PAIR_ROW_KEYS - {"sourceAxes"}
    missing = _PAIR_ROW_KEYS - set(row)
    if extra:
        _err(e, f"{where}unexpected keys {sorted(extra)} (frozen shape)")
    if missing:
        _err(e, f"{where}missing keys {sorted(missing)}")
    if row.get("srcKind") not in STUB_KINDS:
        _err(e, f"{where}srcKind {row.get('srcKind')!r} not a stub kind")
    dst = row.get("dstKind")
    if dst not in NODE_UNIVERSE and dst != _LOCALE_TERM_KIND and dst != "asset":
        _err(e, f"{where}dstKind {dst!r} outside the node universe")
    if row.get("mechanism") not in MECHANISMS:
        _err(e, f"{where}mechanism {row.get('mechanism')!r} not in {MECHANISMS}")
    if not isinstance(row.get("buildId"), int):
        _err(e, f"{where}buildId not an int")
    method = row.get("method", "")
    if method in HARD_METHODS:
        pass
    elif isinstance(method, str) and any(method.startswith(p) for p in METHOD_FREE_PREFIXES):
        pass
    else:
        _err(e, f"{where}method {method!r} outside the frozen vocabulary")
    # provenance rule: inferred:false ONLY for the hard-read methods
    inf = row.get("inferred")
    if inf is False and method not in HARD_METHODS:
        _err(e, f"{where}inferred=false on derived method {method!r}")
    if inf is True and method in HARD_METHODS:
        _err(e, f"{where}inferred=true on hard-read method {method!r}")

    ev = row.get("evidence")
    if not isinstance(ev, dict):
        _err(e, f"{where}evidence must be an object")
        return e
    if method in _EVIDENCE_BY_METHOD:
        want = set(_EVIDENCE_BY_METHOD[method])
        optional = {"subObjectName"} if method == "assetguid-catalog" else set()
        got = set(ev)
        if got - want - optional:
            _err(e, f"{where}evidence extra keys {sorted(got - want - optional)}")
        if want - got:
            _err(e, f"{where}evidence missing keys {sorted(want - got)}")
        if method == "pptr-cross-file":
            if ev.get("resolvedVia") != "externals+cab-index":
                _err(e, f"{where}cross-file evidence.resolvedVia must be "
                        f"'externals+cab-index', got {ev.get('resolvedVia')!r}")
        if "refCount" in ev and (not isinstance(ev["refCount"], int)
                                 or ev["refCount"] < 1):
            _err(e, f"{where}refCount must be an int >= 1")
    elif method.startswith("competitor-model:"):
        for k in ("fieldPath", "sourcePage", "claim"):
            if k not in ev:
                _err(e, f"{where}competitor evidence missing {k!r}")
    elif method.startswith(("name-convention:", "code-analysis:")):
        if "fieldPath" not in ev:
            _err(e, f"{where}{method.split(':')[0]} evidence missing fieldPath")
    axes = row.get("sourceAxes")
    if axes is not None:
        if not isinstance(axes, list) or not axes or \
                any(a not in CONTENT_AXIS_ENUM for a in axes):
            _err(e, f"{where}sourceAxes must be a non-empty list ⊆ {CONTENT_AXIS_ENUM}")
    return e


def validate_pair_dataset(rows, src_kind, dst_kind, where=""):
    """Filename/schema/sort/dedup contract for ONE <src>_<dst>.jsonl."""
    e = []
    for i, row in enumerate(rows):
        e.extend(validate_pair_row(row, where=f"{where}[{i}] "))
        if row.get("srcKind") != src_kind or row.get("dstKind") != dst_kind:
            _err(e, f"{where}[{i}] kind pair {row.get('srcKind')}->{row.get('dstKind')} "
                    f"does not match filename {src_kind}_{dst_kind}")
    keys = [(r.get("srcKind"), r.get("srcId"), r.get("dstKind"), r.get("dstId"),
             r.get("method"), (r.get("evidence") or {}).get("fieldPath"))
            for r in rows]
    if keys != sorted(keys):
        _err(e, f"{where}rows not sorted by the dedup identity tuple")
    if len(set(keys)) != len(keys):
        _err(e, f"{where}duplicate dedup-identity tuples present")
    for i, r in enumerate(rows):
        sid = r.get("srcId")
        if not isinstance(sid, str) or sid != sid.strip() or sid == "":
            _err(e, f"{where}[{i}] srcId not verbatim-clean")
    return e


PAIR_FILE_RE = re.compile(
    r"^(?P<src>[a-z\-]+)_(?P<dst>[a-z\-]+)(?:\.jsonl)?$")


def classify_pair_filename(name: str):
    """'room_item.jsonl' -> ('room','item'); overlays ('room_item.competitor.jsonl')
    -> (..., overlay=True). Returns None for non-pair artifacts (ledgers,
    reports, bridges)."""
    overlay = name.endswith(".competitor.jsonl")
    bare = name[: -len(".competitor.jsonl")] if overlay else name
    m = PAIR_FILE_RE.fullmatch(bare)
    if not m:
        return None
    src, dst = m.group("src"), m.group("dst")
    if src not in NODE_UNIVERSE or dst not in NODE_UNIVERSE:
        if not (dst == _LOCALE_TERM_KIND or dst == "asset"):
            return ("INVALID", name)
    return (src, dst, overlay)


def validate_cab_row(row, where=""):
    e = []
    for k in ("bundle", "cab", "objects", "buildId"):
        if k not in row:
            _err(e, f"{where}cab_index row missing {k!r}")
    if not str(row.get("cab", "")).startswith("CAB-"):
        _err(e, f"{where}cab {row.get('cab')!r} not a CAB- name")
    for o in row.get("objects") or []:
        if "pathId" not in o or "class" not in o:
            _err(e, f"{where}objects[] entry missing pathId/class")
    return e


def validate_container_row(row, where=""):
    e = []
    for k in ("bundle", "address", "pathId", "class", "buildId"):
        if k not in row:
            _err(e, f"{where}container_index row missing {k!r}")
    return e


def validate_unresolved_row(row, where=""):
    e = []
    for k in ("srcKind", "srcId", "fieldPath", "extFileId", "extPath",
              "m_PathID", "reason", "buildId"):
        if k not in row:
            _err(e, f"{where}_unresolved_pptrs row missing {k!r}")
    return e


DANGLING_VERDICTS = ("unresolved-open", "resolved-scene", "resolved-editor-only",
                     "removed-content")


def validate_dangling_row(row, where=""):
    e = []
    for k in ("assetGuid", "sampleRefs", "verdict", "buildId"):
        if k not in row:
            _err(e, f"{where}_dangling_guids row missing {k!r}")
    if row.get("verdict") not in DANGLING_VERDICTS:
        _err(e, f"{where}verdict {row.get('verdict')!r} outside the enum")
    refs = row.get("sampleRefs")
    if not isinstance(refs, list) or not refs or len(refs) > 5:
        _err(e, f"{where}sampleRefs must hold 1..5 entries")
    return e


def validate_registry_row(row, where=""):
    e = []
    for k in ("termId", "termKey", "sourceAsset", "termType", "termStatus",
              "locales", "canonical", "buildId"):
        if k not in row:
            _err(e, f"{where}registry row missing {k!r}")
    if not isinstance(row.get("termId"), int):
        _err(e, f"{where}termId not an int")
    for loc in row.get("locales") or []:
        if loc not in LOCALE_TABLE.values():
            _err(e, f"{where}locale {loc!r} outside the 13-code BCP-47 set")
    return e


def validate_entity_locale_row(row, where=""):
    e = []
    for k in ("srcKind", "srcId", "dstKind", "dstId", "mechanism", "method",
              "inferred", "evidence", "buildId"):
        if k not in row:
            _err(e, f"{where}entity_locale row missing {k!r}")
    if row.get("dstKind") != _LOCALE_TERM_KIND:
        _err(e, f"{where}dstKind must be {_LOCALE_TERM_KIND!r}")
    if row.get("mechanism") != "hard" or row.get("method") != "i2-termid-registry":
        _err(e, f"{where}locale join is hard/i2-termid-registry, got "
                f"{row.get('mechanism')!r}/{row.get('method')!r}")
    if row.get("inferred") is not False:
        _err(e, f"{where}registry-hit rows are hard-read (inferred false)")
    ev = row.get("evidence") or {}
    for k in ("fieldPath", "termId", "dev", "locales"):
        if k not in ev:
            _err(e, f"{where}evidence missing {k!r}")
    if ev.get("termId") == 0:
        _err(e, f"{where}sentinel _termID==0 leaked into entity_locale rows")
    return e


def validate_reverse_row(row, where=""):
    e = []
    for k in ("termKey", "usages", "locales", "buildId"):
        if k not in row:
            _err(e, f"{where}locale_term_entity row missing {k!r}")
    for u in row.get("usages") or []:
        for k in ("srcKind", "srcId", "fieldPath"):
            if k not in u:
                _err(e, f"{where}usages[] entry missing {k!r}")
    return e


def validate_guid_report(obj, *, exact=None, where="guid_bridge_report"):
    """Shape + internal-arithmetic identities; `exact` pins hand-computed
    numbers when refs==distinct makes every rate formula coincide."""
    e = []
    for k in ("guidRefsTotal", "distinctGuids", "resolvedToAddress",
              "resolvedToStub", "danglingDistinctGuids", "resolveRateAddress",
              "resolveRateStub", "buildId"):
        if k not in obj:
            _err(e, f"{where} missing {k!r}")
    if e:
        return e
    refs, dist = obj["guidRefsTotal"], obj["distinctGuids"]
    addr, stub = obj["resolvedToAddress"], obj["resolvedToStub"]
    dang = obj["danglingDistinctGuids"]
    for k, v in (("guidRefsTotal", refs), ("distinctGuids", dist),
                 ("resolvedToAddress", addr), ("resolvedToStub", stub),
                 ("danglingDistinctGuids", dang)):
        if not isinstance(v, int) or v < 0:
            _err(e, f"{where}.{k} must be a non-negative int")
    if stub > addr:
        _err(e, f"{where}: resolvedToStub {stub} > resolvedToAddress {addr} "
                "(stub hits ride the address resolution)")
    # F9's arithmetic counts address-resolutions over REFS and danglings over
    # DISTINCT guids, so `dangling == distinct - resolvedToAddress` holds only
    # in the one-ref-per-guid case — bounded checks here, exact pins via
    # `exact=` where the fixture makes both readings coincide.
    if dang > dist:
        _err(e, f"{where}: danglingDistinctGuids {dang} > distinct {dist}")
    if refs and addr > refs:
        _err(e, f"{where}: resolvedToAddress {addr} > guidRefsTotal {refs}")
    for k in ("resolveRateAddress", "resolveRateStub"):
        r = obj[k]
        if not isinstance(r, (int, float)) or not (0.0 <= r <= 1.0):
            _err(e, f"{where}.{k} {r!r} not a rate in [0,1]")
    if refs and dist:
        denom_addr = refs if abs(obj["resolveRateAddress"] - addr / refs) < 1e-9 \
            else dist
        denom_stub = refs if abs(obj["resolveRateStub"] - stub / refs) < 1e-9 \
            else dist
        if abs(obj["resolveRateAddress"] - addr / denom_addr) > 1e-9:
            _err(e, f"{where}.resolveRateAddress inconsistent with "
                    f"{addr}/(refs|distinct)")
        if abs(obj["resolveRateStub"] - stub / denom_stub) > 1e-9:
            _err(e, f"{where}.resolveRateStub inconsistent with "
                    f"{stub}/(refs|distinct)")
    if exact is not None:
        for k, v in exact.items():
            got = obj[k]
            if isinstance(v, float):
                if abs(got - v) > 1e-9:
                    _err(e, f"{where}.{k} = {got!r}, expected exactly {v!r}")
            elif got != v:
                _err(e, f"{where}.{k} = {got!r}, expected exactly {v!r}")
    return e


def validate_join_report(obj, where="locale_join_report"):
    e = []
    for k in ("instancesTotal", "sentinelZero", "registryHits", "registryMisses",
              "unresolvedIds", "coverageOnNonEmpty", "perKindHits",
              "codeRefTerms", "buildId"):
        if k not in obj:
            _err(e, f"{where} missing {k!r}")
    if e:
        return e
    tot, sent, hits, misses = (obj["instancesTotal"], obj["sentinelZero"],
                               obj["registryHits"], obj["registryMisses"])
    if tot != sent + hits + misses:
        _err(e, f"{where}: instancesTotal {tot} != sentinelZero {sent} + "
                f"hits {hits} + misses {misses}")
    cov = obj["coverageOnNonEmpty"]
    denom = hits + misses
    if denom and abs(cov - hits / denom) > 1e-9:
        _err(e, f"{where}.coverageOnNonEmpty {cov} != {hits}/{denom}")
    for entry in obj["unresolvedIds"]:
        if "termId" not in entry or "sampleRefs" not in entry:
            _err(e, f"{where}.unresolvedIds entry missing termId/sampleRefs")
        elif not (0 < len(entry["sampleRefs"]) <= 5):
            _err(e, f"{where}.unresolvedIds sampleRefs must hold 1..5")
    crt = obj["codeRefTerms"]
    if not isinstance(crt, dict) or "note" not in crt:
        _err(e, f"{where}.codeRefTerms must carry the note (audit-if-present-else-note)")
    return e


def validate_coverage_row(row, where=""):
    e = []
    for k in ("surfaceId", "uiClass", "exportedCount", "definitionClasses",
              "impliedFamilies", "status", "joins", "gapReason", "unblock",
              "buildId"):
        if k not in row:
            _err(e, f"{where}ui_link_coverage row missing {k!r}")
    st = row.get("status")
    if st not in ("mapped-schema", "documented-gap"):
        _err(e, f"{where}status {st!r} outside the two-value enum")
    joins, gap, unb = row.get("joins"), row.get("gapReason"), row.get("unblock")
    if st == "mapped-schema":
        if gap is not None or unb is not None:
            _err(e, f"{where}mapped row carries gap fields (XOR violated)")
        if not joins:
            _err(e, f"{where}mapped row names no joins")
    elif st == "documented-gap":
        if not gap or not unb:
            _err(e, f"{where}gap row requires gapReason + unblock")
        if joins:
            _err(e, f"{where}gap row carries joins {joins!r} (XOR violated)")
    for dc in row.get("definitionClasses") or []:
        if "class" not in dc or "corpusCount" not in dc:
            _err(e, f"{where}definitionClasses entry missing class/corpusCount")
    return e


def coverage_partition_violations(rows, tooltip_targets, discovered_classes):
    """Bar-2 gates: mapped-XOR-gap (per row) + tooltip-anchor partition +
    *Menu*/*UI*/*Inspector* discovery floor. A target class is covered by a
    mapped row's definitionClasses[] OR by an explicit documented-gap row
    naming it as its uiClass (the anchor rule's two legal homes)."""
    e = []
    covered_targets = set()
    seen_surfaces = set()
    for i, row in enumerate(rows):
        e.extend(validate_coverage_row(row, where=f"coverage[{i}] "))
        seen_surfaces.add(row.get("surfaceId"))
        if row.get("status") == "mapped-schema":
            for dc in row.get("definitionClasses") or []:
                covered_targets.add(dc["class"])
        elif row.get("status") == "documented-gap" and row.get("uiClass"):
            covered_targets.add(row["uiClass"])
    uncovered = sorted(set(tooltip_targets) - covered_targets)
    if uncovered:
        e.append(f"tooltip-target partition hole: {uncovered} appear in no "
                 "mapped definitionClasses nor a dedicated gap row")
    for cls in sorted(set(discovered_classes)):
        if not any(cls == r.get("uiClass") or
                   any(dc.get("class") == cls for dc in r.get("definitionClasses") or [])
                   for r in rows):
            e.append(f"discovery-floor violation: harvested class {cls!r} "
                     "matches *Menu*|*UI*|*Inspector* but appears nowhere")
    return e


def validate_competitor_ledger_row(row, where=""):
    e = []
    # Terminal floor-state rows are a distinct class (§R6 freezes only the
    # per-(source, disposition) shape): they name the owner-directed unblock.
    if row.get("terminal"):
        for k in ("sourceId", "rung", "unblock", "buildId"):
            if k not in row:
                _err(e, f"{where}terminal ledger row missing {k!r}")
        return e
    for k in ("sourceId", "rung", "dispositions", "buildId"):
        if k not in row:
            _err(e, f"{where}competitor_applied row missing {k!r}")
    disp = row.get("dispositions") or {}
    for k in ("confirms-hard", "adds-derived", "flags-missing"):
        if k in disp and (not isinstance(disp[k], int) or disp[k] < 0):
            _err(e, f"{where}dispositions.{k} must be a non-negative int")
    if row.get("rung") == "wall":
        w = row.get("wall")
        if not isinstance(w, dict) or "httpStatus" not in w or \
                "oneQuestionItWouldHaveAnswered" not in w:
            _err(e, f"{where}wall row requires wall.httpStatus + "
                    "oneQuestionItWouldHaveAnswered")
    elif row.get("wall") is not None:
        _err(e, f"{where}non-wall rung {row.get('rung')!r} carries a wall block")
    return e


def ac4_pair_dataset_sweep(ext):
    """Arbiter F6 (TR2; spec §8-R7/AC4): identifier preservation over every
    emitted `<src>_<dst>.jsonl` pair dataset, under the pinned sample policy
    (`identifier_sample_ids`: <=1000 -> all, else deterministic 500).

    - srcId must be a verbatim stub id of ANY kind (twins carry their
      @hash8 suffix — the emitted id space, never the bare form);
    - dstId must land in the AC4 exception set: stub ids, roster scene ids
      (either the roster relpath or its bundle-basename spelling),
      container/catalog addresses, or registry term keys.

    Returns a list of violation strings; empty means the sweep passed."""
    from _validators import identifier_sample_ids

    ext = Path(ext)
    e: list[str] = []
    stub_ids: set[str] = set()
    stubs_dir = ext / "stubs"
    if stubs_dir.is_dir():
        for f in sorted(stubs_dir.glob("*.jsonl")):
            if f.name.startswith("_"):
                continue
            for r in read_jsonl(f):
                if isinstance(r.get("id"), str):
                    stub_ids.add(r["id"])
    scene_ids: set[str] = set()
    roster = ext / "bundle-roster.jsonl"
    if roster.is_file():
        for r in read_jsonl(roster):
            if r.get("sceneFlag", "none") != "none":
                rel = str(r["relpath"])
                scene_ids.add(rel)
                scene_ids.add(Path(rel).name.removesuffix(".bundle"))
                scene_ids.add(Path(rel).name)
    addresses: set[str] = set()
    cat = ext / "addressables" / "catalog.json"
    if cat.is_file():
        doc = json.loads(cat.read_text(encoding="utf-8"))
        for k in doc.get("keys") or []:
            if isinstance(k.get("address"), str):
                addresses.add(k["address"])
    cont_idx = ext / "relinks" / "bridges" / "container_index.jsonl"
    if cont_idx.is_file():
        for r in read_jsonl(cont_idx):
            if isinstance(r.get("address"), str):
                addresses.add(r["address"])
    term_keys: set[str] = set()
    reg = ext / "relinks" / "i2_term_registry.jsonl"
    if reg.is_file():
        for r in read_jsonl(reg):
            if isinstance(r.get("termKey"), str):
                term_keys.add(r["termKey"])
    dst_allowed = stub_ids | scene_ids | addresses | term_keys

    relinks = ext / "relinks"
    if not relinks.is_dir():
        return [f"ac4: {relinks} missing — nothing to sweep"]
    for f in sorted(relinks.glob("*.jsonl")):
        kind = classify_pair_filename(f.name)
        if not kind or kind[0] == "INVALID" or kind[2]:
            continue   # ledgers/reports/overlays are not client pair sets
        rows = read_jsonl(f)
        src_sample = identifier_sample_ids(
            [str(r.get("srcId")) for r in rows])
        bad_src = [s for s in src_sample if s not in stub_ids]
        if bad_src:
            e.append(f"{f.name}: srcId outside the stub id space (twins "
                     f"keep their suffix): {bad_src[:5]}")
        dst_sample = identifier_sample_ids(
            [str(r.get("dstId")) for r in rows])
        bad_dst = [d for d in dst_sample if d not in dst_allowed]
        if bad_dst:
            e.append(f"{f.name}: dstId outside the AC4 exception set "
                     f"(stubs/scene/container/registry): {bad_dst[:5]}")
    return e


def floor_gate(dispositions_by_source):
    """Bar-3 floor (DR-2026-08-17-relink, arbiter F4b): MET iff >=3 distinct
    sourceIds each carry >=1 confirms-hard / adds-derived disposition —
    flags-missing-only sources are reported but never floor-count."""
    met = sum(1 for d in dispositions_by_source.values()
              if int(d.get("confirms-hard", 0)) > 0
              or int(d.get("adds-derived", 0)) > 0)
    return met >= 3, met


def matrix_cell_order():
    """Row-major (src, dst) sequence over the pinned nodeUniverse."""
    return [(s, d) for s in NODE_UNIVERSE for d in NODE_UNIVERSE]


def seed_registry_rows():
    """TERM_TABLE projected into emitted-registry row shape (canonical flag
    resolved deterministically: smallest termId per key is primary)."""
    by_key: dict[str, list[tuple]] = {}
    for tid, key, src, locs in TERM_TABLE:
        by_key.setdefault(key, []).append((tid, src, locs))
    rows = []
    for key in sorted(by_key):
        primary = min(t[0] for t in by_key[key])
        for tid, src, locs in sorted(by_key[key]):
            rows.append({"termId": tid, "termKey": key,
                         "sourceAsset": f"harvest/monobehaviours/"
                                        f"localisation_assets_localisation/"
                                        f"I2.Loc.LanguageSourceAsset/{src}",
                         "termType": 0, "termStatus": 1,
                         "locales": sorted(locs),
                         "canonical": tid == primary, "buildId": BUILD_ID})
    return rows


def registry_agreement(emitted_rows, seed_rows=None):
    """Bidirectional diff of an emitted i2_term_registry against a seed
    (default: this library's synthetic TERM_TABLE projection). Returns
    {missingKeys, extraKeys, missingRows, extraRows, canonicalViolations}.
    Mirrors F7's 'bidirectional diff vs locale-matrix keys == 0' at fixture
    scale and G10's canonical-on-key invariant."""
    seed = seed_rows if seed_rows is not None else seed_registry_rows()
    emit_keys = {r["termKey"] for r in emitted_rows}
    seed_keys = {r["termKey"] for r in seed}
    emit_pairs = {(r.get("termId"), r.get("termKey")) for r in emitted_rows}
    seed_pairs = {(r["termId"], r["termKey"]) for r in seed}
    canon_bad = []
    for key in emit_keys:
        flags = [r.get("canonical") for r in emitted_rows if r["termKey"] == key]
        if sum(1 for f in flags if f) != 1:
            canon_bad.append(key)
    return {
        "missingKeys": sorted(seed_keys - emit_keys),
        "extraKeys": sorted(emit_keys - seed_keys),
        "missingRows": sorted(seed_pairs - emit_pairs),
        "extraRows": sorted(emit_pairs - seed_pairs),
        "canonicalViolations": sorted(canon_bad),
    }


def validate_matrix(obj, *, where="matrix"):
    """AC2 + R2/R7 frozen shape over ALL 100 cells."""
    e = []
    meta = obj.get("meta") or {}
    if meta.get("buildId") != BUILD_ID:
        _err(e, f"{where}.meta.buildId {meta.get('buildId')!r} != {BUILD_ID}")
    nu = meta.get("nodeUniverse") or {}
    if list(nu.get("nodes") or []) != list(NODE_UNIVERSE):
        _err(e, f"{where}.nodeUniverse.nodes {nu.get('nodes')!r} != pinned universe")
    arith = nu.get("arithmetic", "")
    for token in (str(CELL_TOTAL), f"{OFF_DIAGONAL} off-diagonal",
                  f"{DIAGONAL} diagonal"):
        if token not in arith:
            _err(e, f"{where}.nodeUniverse.arithmetic lacks {token!r} (got {arith!r})")
    enums = meta.get("enums") or {}
    if sorted(enums.get("mechanism") or []) != sorted(MECHANISMS):
        _err(e, f"{where}.enums.mechanism != {MECHANISMS}")
    if sorted(enums.get("status") or []) != sorted(STATUSES):
        _err(e, f"{where}.enums.status != {STATUSES}")
    pairs = obj.get("pairs")
    if not isinstance(pairs, list) or len(pairs) != CELL_TOTAL:
        _err(e, f"{where}.pairs length {len(pairs) if isinstance(pairs, list) else '?'} "
                f"!= {CELL_TOTAL}")
        return e
    want_order = matrix_cell_order()
    got_order = [(p.get("srcKind"), p.get("dstKind")) for p in pairs]
    if got_order != want_order:
        bad = next(((w, g) for w, g in zip(want_order, got_order) if w != g), None)
        _err(e, f"{where}.pairs not row-major over nodeUniverse (first divergence "
                f"want={bad[0]} got={bad[1]})")
    n_modeled = n_partial = n_missing = 0
    for i, p in enumerate(pairs):
        w = f"{where}.pairs[{i}]({p.get('srcKind')}->{p.get('dstKind')}) "
        if p.get("mechanism") not in MECHANISMS:
            _err(e, f"{w}mechanism outside enum")
        st = p.get("status")
        if st not in STATUSES:
            _err(e, f"{w}status outside enum")
            continue
        if st == "modeled":
            n_modeled += 1
            if not p.get("pairFiles"):
                _err(e, f"{w}modeled cell names no pairFiles")
        elif st == "partial":
            n_partial += 1
            if not p.get("unblock"):
                _err(e, f"{w}partial cell requires a non-empty unblock")
        else:
            n_missing += 1
            if not p.get("unblock"):
                _err(e, f"{w}missing cell requires a non-empty unblock")
        e.extend(validate_join_key(p.get("joinKey"), where=w))
        card = p.get("cardinality")
        if not isinstance(card, dict):
            _err(e, f"{w}cardinality missing")
        else:
            for k in ("perSrc", "perDst", "srcEntitiesWithEdges", "edges"):
                if k not in card:
                    _err(e, f"{w}cardinality missing {k!r}")
            if isinstance(card.get("edges"), int) and card["edges"] < 0:
                _err(e, f"{w}cardinality.edges negative")
        if not isinstance(p.get("pairFiles"), list):
            _err(e, f"{w}pairFiles must be a list (possibly empty)")
    return e


def reconcile_matrix_to_pair_files(matrix, relinks_dir, *, where="matrix"):
    """Arbiter F2 (TR1; spec §8-R7): the matrix's per-cell numbers must
    reconcile to the emitted pair datasets on disk — for every cell naming
    pairFiles, each entry exists under `relinks_dir`, is spelled
    `<src>_<dst>.jsonl`, carries exactly cardinality.edges rows and exactly
    srcEntitiesWithEdges distinct srcIds. Phantom numbers hard-fail in BOTH
    directions (edges without a file, files without a claiming cell), and
    the swept row total must equal the summed edges — the real cross-check
    that replaced validate_matrix's self-voiding status-tally comparison.
    Overlays (`*.competitor.jsonl`) and non-pair artifacts are excluded from
    the sweep exactly as classify_pair_filename draws the line; INVALID
    naming is F11's tripwire's job, not this leg's."""
    d = Path(relinks_dir)
    e: list[str] = []
    claimed: dict[str, int] = {}
    claimed_rows = 0
    sum_edges = 0
    for p in matrix.get("pairs") or []:
        w = f"{where}({p.get('srcKind')}->{p.get('dstKind')}) "
        card = p.get("cardinality") or {}
        edges = card.get("edges")
        want_src = card.get("srcEntitiesWithEdges")
        names = p.get("pairFiles") or []
        if not isinstance(edges, int):
            _err(e, f"{w}cardinality.edges not an int: {edges!r}")
            continue
        expected = f"{p.get('srcKind')}_{p.get('dstKind')}.jsonl"
        if edges == 0:
            if names:
                _err(e, f"{w}zero-edge cell names pairFiles {sorted(names)!r}")
            continue
        sum_edges += edges
        if not names:
            _err(e, f"{w}edges={edges} but no pairFiles named")
            continue
        for name in names:
            if name != expected:
                _err(e, f"{w}pairFiles entry {name!r} != pinned spelling "
                        f"{expected!r}")
                continue
            f = d / name
            if not f.is_file():
                _err(e, f"{w}names {name!r}: absent under {d.name}/")
                continue
            rows = read_jsonl(f)
            claimed[name] = len(rows)
            claimed_rows += len(rows)
            if len(rows) != edges:
                _err(e, f"{w}{name}: {len(rows)} rows on disk != "
                        f"cardinality.edges={edges}")
            distinct_src = len({str(r.get("srcId")) for r in rows})
            if distinct_src != want_src:
                _err(e, f"{w}{name}: {distinct_src} distinct srcId != "
                        f"srcEntitiesWithEdges={want_src}")
    swept: dict[str, int] = {}
    if d.is_dir():
        for f in sorted(d.glob("*.jsonl")):
            kind = classify_pair_filename(f.name)
            if kind is None or kind[0] == "INVALID" or kind[2]:
                continue   # ledgers/reports/overlays are not client cells
            swept[f.name] = len(read_jsonl(f))
    unclaimed = sorted(set(swept) - set(claimed))
    if unclaimed:
        _err(e, f"{where}: pair dataset(s) on disk no cell claims: "
                f"{unclaimed[:5]}")
    phantom = sorted(set(claimed) - set(swept))
    if phantom:
        _err(e, f"{where}: cells claim pair dataset(s) absent from the "
                f"sweep: {phantom[:5]}")
    if claimed_rows != sum_edges:
        _err(e, f"{where}: swept claimed pair datasets carry {claimed_rows} "
                f"rows != sum(cardinality.edges)={sum_edges}")
    return e


def validate_relations_md(text: str, *, where="RELATIONS.md"):
    """Regenerated-catalog obligations: placeholder gone, ownership-routing
    note present, every family + mechanism + ledgers covered."""
    e = []
    if "PLACEHOLDER" in text.upper():
        _err(e, f"{where} still carries the piece-1 placeholder pointer")
    for token in ("entity_locale", "locale_availability"):
        if token not in text:
            _err(e, f"{where} lacks the {token} ownership-routing mention")
    for token in ("_unresolved_pptrs", "_dangling_guids", "competitor"):
        if token not in text:
            _err(e, f"{where} lacks ledger coverage for {token}")
    if str(BUILD_ID) not in text:
        _err(e, f"{where} lacks the buildId-stamped header")
    return e
