"""Stage-11 media export fixtures + contract validators (piece-06 TestWriter).

Everything here is TEST-ONLY and synthetic-bytes-only: the fixture corpus is
built from declarative tables whose shapes mirror the LANDED corpus row
shapes verbatim (stubs/<kind>.jsonl, media-catalogue.jsonl,
relinks/bridges/container_index.jsonl, addressables/catalog.json,
relinks/entity_asset_guid.jsonl, relinks/course_config.jsonl) so the
CodeWriter's readers meet realistic input without any real game bytes.

Contract surfaces pinned from docs/specs/piece-06-media.mdx Revision 3
(+ arbiter-piece06-spec Part-3 binding pins):

- P1  hostless scoping: no game dir => wholesale auto-SKIP, never exit 3;
      exit 3 only for a missing upstream ARTIFACT while the dir resolves.
- P2  per-ledger escapes: `uncategorized-reason` (_missing_icons.jsonl),
      `uncategorized-slot` (_pptr_residue.jsonl slotClass/targetResolution);
      row emitted + DRIFT + exit 2, never exit 1.
- P3  cross-check CLI exports LOSSLESS (`--image-format png`; bmp/tga ok;
      webp/jpg forbidden) + `cliExportFormat` stamp.
- F4  zero-bundle-open hostless lane: the 7-name seed fixture drives
      `_missing_icons.jsonl` + `index.jsonl` end-to-end with resolved:false
      rows and NO bundle opens.

The suite runs stdlib+PIL only (pack `.venv` carries Pillow 12.3.0, no
numpy): pixel fixtures are deterministic bytes / PIL Images compared via
tobytes(), never binary Reads into agent context.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _fixturelib as fx  # noqa: E402
from _validators import BUILD_ID, CONTENT_AXES, write_jsonl  # noqa: E402

# --- stage identity -------------------------------------------------------------

STAGE11_SCRIPTS = ("stage11_media.py", "media_util.py")
UNITY_VERSION = fx.UNITY_VERSION          # 2020.3.47f1
CLI_VERSION_SEED = "0.19.0"               # AssetStudioModCLI v0.19.0 net8 portable

MEDIA_DIRNAME = "media"

# --- §4 enums / numeric pins ----------------------------------------------------

MISSING_REASONS = (
    "dlc-content-absent",
    "stale-name",
    "empty-sub-name",
    "editor-only-fallback",
    "visuals-prefab-target",
    "mesh-list-target",
    "level-config-target",
)
REASON_ESCAPE = "uncategorized-reason"
MISSING_REASON_ENUM = MISSING_REASONS + (REASON_ESCAPE,)

TARGET_RESOLUTIONS = (
    "resolved-address",
    "unresolved-open",
    "resolved-scene",
    "resolved-editor-only",
    "removed-content",
)
SLOT_CLASSES = ("external", "same-file")
SLOT_ESCAPE = "uncategorized-slot"
RESIDUE_BASIS = "122-basis"

# route vocabulary observed in the spec (E1 rule 2 classification + the E4(3)
# quota names + the E3 plane); NOT asserted as closed anywhere.
ROUTES_KNOWN = (
    "atlas-pair",
    "standalone",
    "standalone-pass-through",
    "direct-pointer-subrect",
    "ui-chrome",
)
PLANES = ("icons", "thumbs", "ui")
NAMED_BY_VALUES = ("subObjectName", "address-basename")

LOSSLESS_CLI_FORMATS = ("png", "bmp", "tga")
FORBIDDEN_CLI_FORMATS = ("webp", "jpg", "jpeg")

QUALITY_PIN = 80
PNG_TWIN_MAX_DIM = 64
ALPHA_TOLERANCE_LEVELS = 1                 # max per-pixel |alpha delta| <= 1/255
TEMP_FLOOR_GIB = 4.0
OUTPUT_FLOOR_GIB = 2.0
DEFAULT_CEILING_BYTES = 256 * 1024 * 1024  # AC7 default-run web/ ceiling
CHROME_CEILING_BYTES = 512 * 1024 * 1024   # AC7 --include-ui-chrome ceiling
CROSSCHECK_SAMPLE_MIN = 20

# AC5 byte-stability set: seven always-on text artifacts + MEDIA-EXPORT.md
# (+ course-icon-carrier-report.json when the E5 flag is on).
TEXT_ARTIFACTS_ALWAYS = (
    "export-manifest.jsonl",
    "index.jsonl",
    "hashes.sha256",
    "crosscheck-report.json",
    "_missing_icons.jsonl",
    "_pptr_residue.jsonl",
    "_skipped_classes.jsonl",
)
TEXT_ARTIFACTS_FLAGGED = ("course-icon-carrier-report.json",)
PORCELAIN_TRACKED = "MEDIA-EXPORT.md"

SKIPPED_CLASS_SEEDS_REAL = (138, 9, 29)    # Cubemap / Texture2DArray / zero-size font atlases (M19)

# --- worked geometry seeds (spec M10/M12 + §4 illustrative manifest row) ---------

WORKED_SPRITE_NAME = "UI_Generic_T_Spritesheet_Icons_InGame_ItemsList_Tabs_Main_DLC"
WORKED_RECT = {"x": 227.0, "y": 31.0, "w": 70.0, "h": 70.0}
WORKED_PAGE_H = 4096
WORKED_ROUNDED = {"left": 227, "top": 3995, "w": 70, "h": 70}   # top = H - y - h
WORKED_PAGE_NAME = "sactx-0-4096x4096-DXT5-UI_Icons-f59ce1d5"
WORKED_PAGE_PATHID = 2101954
ADVISOR_HUSKI_NAME = "AdvisorHuski"
ADVISOR_HUSKI_DIMS = (337.93, 509.97)      # fractional rect shape (M10)
ANCHOR_SML = ("DLC2_Qualifications_janitor_SML", 100, 116)
ANCHOR_LRG = ("DLC2_Qualifications_janitor_LRG", 211, 243)

HOME_BUNDLE_SEED = "ui-icons-atlased-assets_assets_all.bundle"
ATLAS_BUNDLE_SEED = "ui-spriteatlas_assets_all.bundle"

# --- M16 absence seed (verbatim; the F4 black-box driver) -----------------------

ABSENCE_SEED = (
    ("DLC3_UI_Icons_Objective_Pirates", "dlc-content-absent"),
    ("DLC3_UI_Icons_Objective_Volcano", "dlc-content-absent"),
    ("Gorge_UI_Icons_Objectives_DLC3_Emergency", "dlc-content-absent"),
    ("UI_HUD_Room_T_Icon_DLC3_plot", "dlc-content-absent"),
    ("UI_InGame_DLC3_Icon_studentArchetype_Doctors", "dlc-content-absent"),
    ("UI_InGame_DLC3_Icon_studentArchetype_Nurses", "dlc-content-absent"),
    ("UI_InGame_T_Icon_Item_Teamsports_Cheeseball", "stale-name"),
)

# --- fixture leaf shapes (verbatim landed-corpus spellings) ----------------------

SPRITE_SUBTYPE = (
    "UnityEngine.Sprite, UnityEngine.CoreModule, Version=0.0.0.0, "
    "Culture=neutral, PublicKeyToken=null"
)


def sprite_ref(guid: str = "", sub: str = "", subtype: str = SPRITE_SUBTYPE):
    """A GUID-carrying object-reference leaf exactly as harvested stubs hold it.

    guid="" + sub="" collapses to the real all-empty spelling (m_SubObjectType
    included as "")."""
    return {
        "m_AssetGUID": guid,
        "m_SubObjectName": sub,
        "m_SubObjectType": subtype if (guid or sub) else "",
    }


def tex_ref(guid: str = "", sub: str = ""):
    return sprite_ref(guid, sub,
                      "UnityEngine.Texture2D, UnityEngine.CoreModule, "
                      "Version=0.0.0.0, Culture=neutral, PublicKeyToken=null")


def pptr(fid: int, pid: int):
    return {"m_FileID": fid, "m_PathID": pid}


def stub_row(kind, sid, bundle, path_id, cls, fields):
    """Validator-clean piece-1 stub row (shape mirrors extracted/stubs/*.jsonl)."""
    return {
        "buildId": BUILD_ID,
        "fields": fields,
        "id": sid,
        "inferred": True,
        "kind": kind,
        "method": "seeded-family-heuristic",
        "provisional": True,
        "slug": None,
        "source": {"bundle": bundle, "class": cls, "pathId": path_id},
    }


def guid_for(name: str) -> str:
    """Deterministic 32-hex stand-in GUID (never a real one)."""
    return hashlib.md5(f"tw06-guid:{name}".encode()).hexdigest()


def det_pixels(tag: str, w: int, h: int) -> bytes:
    """Deterministic RGBA8 page bytes (stdlib only)."""
    out = bytearray()
    counter = 0
    while len(out) < w * h * 4:
        out.extend(hashlib.sha256(f"{tag}:{counter}".encode()).digest())
        counter += 1
    return bytes(out[: w * h * 4])


# =================================================================================
# Fixture corpus tables (the ONE source of truth the oracles read too)
# =================================================================================

# --- sprite-typed refs that never resolve: the 7 M16 absences --------------------
# (kind, srcId, fieldPath, spriteName, chain) — chain drives the expected
# chainBreak evidence: 'container' (guid hits catalog, no container row) or
# 'none' (full chain resolves; the NAME alone is unknown -> stale-name).
ABSENCE_REF_TABLE = [
    ("config", "Config_Objective_Pirates_A", "ObjectiveIconReference",
     "DLC3_UI_Icons_Objective_Pirates", "container"),
    ("config", "Config_Objective_Pirates_B", "ObjectiveIconReference",
     "DLC3_UI_Icons_Objective_Pirates", "container"),
    ("config", "Config_Objective_Pirates_C", "ObjectiveIconReference",
     "DLC3_UI_Icons_Objective_Pirates", "container"),
    ("config", "Config_Objective_Volcano", "ObjectiveIconReference",
     "DLC3_UI_Icons_Objective_Volcano", "container"),
    ("room", "Room_Gorge_Emergency", "HUDRoomIconReference",
     "Gorge_UI_Icons_Objectives_DLC3_Emergency", "container"),
    ("campus-level", "Campus_Level_DLC3_Plot", "LevelPlotIconReference",
     "UI_HUD_Room_T_Icon_DLC3_plot", "container"),
    ("student-type", "StudentType_Doctors", "ArchetypeIconReference",
     "UI_InGame_DLC3_Icon_studentArchetype_Doctors", "container"),
    ("student-type", "StudentType_Nurses", "ArchetypeIconReference",
     "UI_InGame_DLC3_Icon_studentArchetype_Nurses", "container"),
    ("item", "Item_Teamsports_Cheeseball", "ItemsMenuIconReference",
     "UI_InGame_T_Icon_Item_Teamsports_Cheeseball", "none"),
]
# NOTE: Pirates x3 exercises the many-to-one ledger aggregate (one
# _missing_icons row, sampleRefs[<=5] carrying three refs).

# --- sprite-typed ledgered-skip families (E1 rule 7) -----------------------------
# (kind, srcId, fieldPath, spriteName, reason) — GUIDs dangle (chainBreak
# 'guid') AND the family routes the pinned reason regardless.
SKIP_REF_TABLE = [
    ("item", "Item_EditorFallback_A", "EditorFallbackIconReference",
     "EditorFallback_Sprite_Alpha", "editor-only-fallback"),
    ("item", "Item_EditorFallback_B", "EditorFallbackIconReference",
     "EditorFallback_Sprite_Beta", "editor-only-fallback"),
    ("item", "Item_Visual_Prefab_Target", "VisualsPrefab",
     "VisualPrefab_Sprite_Gamma", "visuals-prefab-target"),
    ("unlockable", "Unlock_Mesh_Target", "Meshes[0]",
     "UnlockMesh_Sprite_Delta", "mesh-list-target"),
    ("campus-level", "Level_Config_Target", "LevelConfig",
     "LevelConfig_Sprite_Epsilon", "level-config-target"),
]

ALL_REF_TABLE = ABSENCE_REF_TABLE + SKIP_REF_TABLE


def walked_refs():
    """Every sprite-typed ref the E1 walk must find, as oracle dicts."""
    rows = []
    for kind, sid, fp, name, chain in ABSENCE_REF_TABLE:
        rows.append({"kind": kind, "srcId": sid, "fieldPath": fp,
                     "subObjectName": name, "assetGuid": guid_for(name),
                     "resolved": False, "chainBreak": chain, "file": None,
                     "reason": dict(ABSENCE_SEED).get(
                         name, "dlc-content-absent")})
    for kind, sid, fp, name, reason in SKIP_REF_TABLE:
        rows.append({"kind": kind, "srcId": sid, "fieldPath": fp,
                     "subObjectName": name, "assetGuid": guid_for(name),
                     "resolved": False, "chainBreak": "guid", "file": None,
                     "reason": reason})
    rows.sort(key=lambda r: (r["kind"], r["srcId"], r["fieldPath"]))
    return rows


# --- E6 residue scan slots (nine-kind mix) ---------------------------------------
# (kind, srcId, leafName, fileId, pathID, pairedRefGuid)
#   pairedRefGuid None  -> sibling *Reference field ABSENT
#   pairedRefGuid ""    -> sibling present but EMPTY (still admitted)
#   non-empty guid      -> sibling POPULATED (never admitted)
E6_SLOT_TABLE = [
    ("config", "CareerGoal_Award_BestClubs", "BadgeIcon", 4,
     -7344703678268865042, None),
    ("config", "CareerGoal_Award_BestResearchUniversity", "BadgeIcon", 4,
     191005181965227619, None),
    ("config", "Goal_External_NullPath", "RivalIcon", 12, 0, None),
    ("staff", "Staff_Inbox_Row", "InboxTrayIcon_Plain", 14, 42, ""),
    ("item", "Item_Overlay_Head", "OverlayIconHeader", 0, 77, None),
    ("room", "Room_Menu_Swatch", "SwatchMenuIcon", 1, 55,
     guid_for("SwatchMenuIcon-populated")),
    ("metagame-node", "Node_Leaf_Null_Slot", "BadgeIcon", 0, 0, None),
    ("student-type", "Archetype_IconRef_Leaf", "_iconReference", 5, 12345, None),
    ("campus-level", "Level_Title_Label_Decoy", "TitleLabel", 3, 999, None),
]


def oracle_residue_rows():
    """Expected `_pptr_residue.jsonl` rows for E6_SLOT_TABLE."""
    rows = []
    for kind, sid, leaf, fid, pid, sib in E6_SLOT_TABLE:
        if "icon" not in leaf.lower():
            continue                       # outside the pinned vocabulary
        null_slot = (fid == 0 and pid == 0)
        admitted = (not null_slot) and not sib
        if admitted:
            rows.append({
                "kind": kind, "srcId": sid, "fieldPath": leaf,
                "pptr": {"fileId": fid, "pathID": pid},
                "pairedReferenceEmpty": True,
                "slotClass": "external" if fid != 0 else "same-file",
                "targetResolution": "unresolved-open",
                "basis": RESIDUE_BASIS,
                "buildId": BUILD_ID,
            })
    rows.sort(key=lambda r: (r["kind"], r["srcId"], r["fieldPath"]))
    return rows


def oracle_e6_counters():
    scanned = len(E6_SLOT_TABLE)
    nulls = sum(1 for k in E6_SLOT_TABLE if k[3] == 0 and k[4] == 0)
    rows = oracle_residue_rows()
    ext = sum(1 for r in rows if r["slotClass"] == "external")
    return {
        "scanned": scanned, "nullSkipped": nulls, "rows": len(rows),
        "external": ext, "sameFile": len(rows) - ext,
    }


# --- catalogue composition (drives _skipped_classes policies) ---------------------

CATALOGUE_NOISE = [
    # present-but-unreferenced Sprite rows (resolution-predicate noise)
    ("Sprite", ATLAS_BUNDLE_SEED, WORKED_SPRITE_NAME, 3101954, "base", 1437),
    ("Sprite", HOME_BUNDLE_SEED, ADVISOR_HUSKI_NAME, 3201954, "base", 2210),
    ("Sprite", HOME_BUNDLE_SEED, "UI_HUD_Icon_Tab_Generic", 3301954, "base", 402),
    # the hosting atlas + one page texture
    ("SpriteAtlas", ATLAS_BUNDLE_SEED, "UI_Icons", 900000001, "base", 96000),
    ("Texture2D", ATLAS_BUNDLE_SEED, WORKED_PAGE_NAME, WORKED_PAGE_PATHID,
     "base", 209500708 % 1000000),
    # carve-out classes: policy rows must census-count these
    ("Cubemap", "environment_assets_all.bundle", "cube_sky_a", 4000001, "base", 48000),
    ("Cubemap", "environment_assets_all.bundle", "cube_sky_b", 4000002, "base", 48000),
    ("Texture2DArray", "environment_assets_all.bundle", "arr_terrain", 4100001, "base", 96000),
    # zero-size font-atlas Texture2D (pixels stream; fonts out of scope)
    ("Texture2D", "fonts_assets_all.bundle", "font_atlas_zero", 4200001, "base", 0),
]

SKIP_POLICY_ROWS_EXPECTED = [
    # (class-spelling family, censusCount) derived from CATALOGUE_NOISE
    ("Cubemap", 2),
    ("Texture2DArray", 1),
]


# --- container/catalog chains ------------------------------------------------------

CHEESEBALL_ADDRESS = "Assets/Data/UI/Atlases/UI_Icons.spriteatlasv2"


def catalog_guid_keys():
    """catalog.json `guid` keys: DLC3 guids hit addresses with NO container
    row; the Cheeseball guid resolves through to an installed atlas;
    skip-family guids dangle entirely (absent from catalog)."""
    keys = []
    for kind, sid, fp, name, chain in ABSENCE_REF_TABLE:
        addr = None if name.startswith("UI_InGame_T_Icon_Item_Teamsports") \
            else f"Assets/Data/DLC3/{name}"
        keys.append({"key": guid_for(name), "kind": "guid", "bundle": None,
                     "address": addr, "dependencies": [],
                     "providerIds": ["BundledAssetProvider"]})
    keys.append({"key": guid_for("UI_InGame_T_Icon_Item_Teamsports_Cheeseball"),
                 "kind": "guid", "bundle": None,
                 "address": CHEESEBALL_ADDRESS, "dependencies": [],
                 "providerIds": ["BundledAssetProvider"]})
    return keys


CONTAINER_ROWS_SPEC = [
    # (address, bundle, class, pathId)
    (CHEESEBALL_ADDRESS, ATLAS_BUNDLE_SEED, "SpriteAtlas", 900000001),
    ("Assets/Data/UI/Sprites/" + ADVISOR_HUSKI_NAME, HOME_BUNDLE_SEED,
     "Sprite", 3201954),
    ("Assets/Data/UI/Sprites/" + WORKED_SPRITE_NAME, ATLAS_BUNDLE_SEED,
     "Sprite", 3101954),
    ("Assets/Data/Environment/Tex/tex_noise_a", "environment_assets_all.bundle",
     "Texture2D", 4300001),
]


def container_index_rows():
    return [{"address": a, "buildId": BUILD_ID, "bundle": b, "class": c,
             "pathId": p} for a, b, c, p in CONTAINER_ROWS_SPEC]


def _cab_of(bundle: str) -> str:
    return "CAB-" + hashlib.md5(f"tw06-cab:{bundle}".encode()).hexdigest()


def cab_index_rows():
    """Transitive piece-02 bridge artifact (the stage reads it while walking
    chain evidence); tiny object tables over the fixture bundles."""
    seen, rows = set(), []
    for address, bundle, cls, pid in CONTAINER_ROWS_SPEC:
        if bundle in seen:
            continue
        seen.add(bundle)
        rows.append({"buildId": BUILD_ID, "bundle": bundle,
                     "cab": _cab_of(bundle),
                     "objects": [{"class": cls, "pathId": pid}]})
    return rows


def externals_rows():
    """Transitive harvest artifact: per-bundle external file tables. The
    atlas bundle carries fileId 14 -> monoscripts CAB (the M14 external
    PPtr shape); everything else ships empty or single-entry."""
    mono_cab = _cab_of("041ed57f62d7d6540bf750de21a4130d_monoscripts.bundle")
    rows = []
    bundles = sorted(set(KIND_BUNDLES.values()) |
                     {ATLAS_BUNDLE_SEED, HOME_BUNDLE_SEED,
                      "environment_assets_all.bundle",
                      "fonts_assets_all.bundle"})
    for b in bundles:
        ext = []
        if b == ATLAS_BUNDLE_SEED:
            ext.append({"fileId": 14, "guid": "0" * 32,
                        "path": f"archive:/{mono_cab}/{mono_cab}", "type": 0})
        rows.append({"bundle": b, "externals": ext,
                     "sourceFile": _cab_of(b).replace("CAB-", "cab-", 1)})
    return rows


def entity_asset_guid_rows():
    """Reconciliation surface: persisted rows for a SUBSET of the walk (walk
    14 refs vs persisted fewer -> the delta prints DRIFT and never fails)."""
    walked = walked_refs()
    keep = walked[: max(1, len(walked) // 2)]
    rows = []
    for r in keep:
        rows.append({
            "buildId": BUILD_ID,
            "dstId": f"Assets/Data/DLC3/{r['subObjectName']}",
            "dstKind": "asset",
            "evidence": {"assetGuid": r["assetGuid"],
                         "fieldPath": r["fieldPath"],
                         "resolvedVia": "catalog-guid+container-index"},
            "inferred": False, "mechanism": "hard",
            "method": "assetguid-catalog",
            "srcId": r["srcId"], "srcKind": r["kind"],
        })
    return rows


# --- courses/E5 minimal carrier chain ----------------------------------------------

COURSE_STUBS = [
    ("Course_Qual_Linked", {"Qualification": pptr(2, 555)}),
    ("Course_Qual_Plain", {"DurationWeeks": 2}),
]
COURSE_CONFIG_EDGES = [
    {"buildId": BUILD_ID, "dstId": "Qualification_Q1", "dstKind": "config",
     "evidence": {"dstBundle": "configs_assets_all.bundle",
                  "dstPathId": 7759708820184992202,
                  "fieldPath": "Qualification", "refCount": 1,
                  "srcBundle": "configs_assets_all.bundle",
                  "srcPathId": -2127165306295864506},
     "inferred": False, "mechanism": "hard", "method": "pptr-same-file",
     "srcId": "Course_Qual_Linked", "srcKind": "course"},
]


# --- stub assembly ------------------------------------------------------------------

KIND_BUNDLES = {
    "item": "items-general_assets_all.bundle",
    "unlockable": "unlockables_assets_all.bundle",
    "room": "rooms_assets_all.bundle",
    "campus-level": "configs_assets_all.bundle",
    "course": "items-courses-magic_assets_all.bundle",
    "config": "configs_assets_all.bundle",
    "staff": "character-shared_assets_all.bundle",
    "metagame-node": "configs-metagame_assets_all.bundle",
    "student-type": "character-shared_assets_all.bundle",
}


def media_stub_rows():
    """All nine kinds, validator-clean, containing exactly the leaves the
    oracle tables describe (plus deliberate cross-filter decoys)."""
    per_kind: dict[str, list] = {}

    def add(kind, sid, fields):
        # deterministic pathId (string hash() is process-randomized — never use)
        pid = int(hashlib.sha256(sid.encode()).hexdigest()[:12], 16)
        per_kind.setdefault(kind, []).append(
            stub_row(kind, sid, KIND_BUNDLES[kind], pid, "TPC.Fixture", fields))

    # E1 refs (absences + ledgered skips)
    for kind, sid, fp, name, _chain in ABSENCE_REF_TABLE:
        add(kind, sid, {fp: sprite_ref(guid_for(name), name)})
    for kind, sid, fp, name, _reason in SKIP_REF_TABLE:
        add(kind, sid, {fp: sprite_ref(guid_for(name), name)})

    # cross-filter decoys: never E1 (wrong subtype), never E6 (GUID-dict, not PPtr)
    add("item", "Item_TexDecoy", {
        "IconAtlasTexture": tex_ref(guid_for("tex-noise"), "tex_noise_a"),
        "DisplayNameLoc": "item_tex_decoy_name"})
    # E6 slots ride their own rows
    for kind, sid, leaf, fid, pid, sib in E6_SLOT_TABLE:
        fields = {leaf: pptr(fid, pid)}
        if sib is not None:
            fields[leaf + "Reference"] = sprite_ref(sib, "X" if sib else "")
        add(kind, sid, fields)
    # plain PPtr noise that is NOT icon-named (scanned but never admitted)
    add("config", "Config_Plain_Pptr_Noise", {
        "m_GameObject": pptr(0, 0), "m_Script": pptr(1, -42)})

    # courses (E5 chain; Qualification is a plain PPtr -> outside E1/E6 vocab)
    for cid, fields in COURSE_STUBS:
        add("course", cid, fields)

    rows = []
    for kind in sorted(per_kind):
        rows.extend(sorted(per_kind[kind], key=lambda r: r["id"]))
    return rows


def media_catalogue_rows():
    rows = list(CATALOGUE_NOISE)
    rows.sort(key=lambda r: (r[0], r[2]))
    return [{"class": c, "bundle": b, "name": n, "pathId": p,
             "bytesEstimate": est, "contentAxis": ax}
            for c, b, n, p, ax, est in rows]


def oracle_missing_rows():
    """Expected `_missing_icons.jsonl`: absence rows aggregated by name
    (sampleRefs <=5) + per-name ledgered-skip rows; sorted by subObjectName."""
    agg: dict[str, dict] = {}
    for r in walked_refs():
        row = agg.setdefault(r["subObjectName"], {
            "subObjectName": r["subObjectName"],
            "assetGuid": r["assetGuid"],
            "reason": r["reason"],
            "sampleRefs": [],
        })
        row["sampleRefs"].append({"kind": r["kind"], "srcId": r["srcId"],
                                  "fieldPath": r["fieldPath"]})
    rows = sorted(agg.values(), key=lambda r: r["subObjectName"])
    for r in rows:
        r["sampleRefs"] = sorted(
            r["sampleRefs"], key=lambda s: (s["kind"], s["srcId"], s["fieldPath"]))[:5]
        r["buildId"] = BUILD_ID
    return rows


def oracle_index_rows():
    return walked_refs()


# =================================================================================
# Tree builders
# =================================================================================

def build_client_shell(out: Path):
    """Synthetic install root (valid shape, unparseable det_bytes bundles) +
    identity/roster/catalog upstreams shared by every media tree variant."""
    out = Path(out)
    fx.build_client_inputs(out)
    extracted = out / "extracted"
    fx.build_identity_fixture(extracted)
    write_jsonl(extracted / "bundle-roster.jsonl", fx.roster_rows())
    return extracted


def write_media_upstreams(extracted: Path):
    """Stage-11 upstream set over the fixture tables."""
    extracted = Path(extracted)
    # catalog.json: meta + the real bundle keys from the shared fixture lib
    # PLUS this corpus's guid keys
    base_keys = [{"key": k, "kind": "bundle", "bundle": ref,
                  "address": f"Assets/Content/{k.replace('.', '/')}",
                  "dependencies": [], "providerIds": ["BundledAssetProvider"]}
                 for k, ref in fx.CATALOG_KEYS_SPEC]
    obj = {"meta": {"buildId": BUILD_ID,
                    "addressablesVersion": fx.ADDRESSABLES_VERSION,
                    "settingsHash": fx.SETTINGS_HASH,
                    "providerIds": ["ContentCatalogProvider",
                                    "BundledAssetProvider"]},
           "keys": base_keys + catalog_guid_keys()}
    (extracted / "addressables").mkdir(parents=True, exist_ok=True)
    (extracted / "addressables" / "catalog.json").write_text(
        json.dumps(obj, indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n")

    bridges = extracted / "relinks" / "bridges"
    write_jsonl(bridges / "container_index.jsonl", container_index_rows())
    write_jsonl(bridges / "cab_index.jsonl", cab_index_rows())
    write_jsonl(extracted / "relinks" / "entity_asset_guid.jsonl",
                entity_asset_guid_rows())
    write_jsonl(extracted / "relinks" / "course_config.jsonl",
                COURSE_CONFIG_EDGES)
    write_jsonl(extracted / "harvest" / "externals.jsonl", externals_rows())
    write_jsonl(extracted / "media-catalogue.jsonl", media_catalogue_rows())

    stubs = extracted / "stubs"
    by_kind: dict[str, list] = {}
    for r in media_stub_rows():
        by_kind.setdefault(r["kind"], []).append(r)
    from _validators import KIND_TO_FILE
    for kind, filename in KIND_TO_FILE.items():
        write_jsonl(stubs / filename, sorted(by_kind.get(kind, []),
                                             key=lambda r: r["id"]))
    return extracted


def build_media_tree(out: Path) -> Path:
    """The 7-name SEED tree: zero resolvable names -> zero bundle opens
    required (F4); ledgers carry the absences + ledgered skips.
    Returns the TREE ROOT (install root inside it at
    <root>/steamapps/common/Two Point Campus)."""
    out = Path(out)
    extracted = build_client_shell(out)
    write_media_upstreams(extracted)
    return out


# =================================================================================
# Validators (bite NOW against mutated rows; drive impl artifacts later)
# =================================================================================

HEX_RE = __import__("re").compile(r"^[0-9a-f]{64}$")


def validate_media_manifest_row(row, where=""):
    """Frozen §4 provenance key set on export-manifest.jsonl rows."""
    e = []
    if not isinstance(row, dict):
        return [f"{where}manifest row is not an object"]
    required = {"outRelPath", "plane", "format", "quality", "bytes",
                "sha256", "route", "namedBy", "source", "dims", "buildId"}
    keys = set(row)
    for k in sorted(required - keys):
        _err(e, f"{where}manifest row missing {k!r}")
    for k in sorted(keys - required):
        _err(e, f"{where}manifest row carries non-contract key {k!r}")
    if e:
        return e
    if row["plane"] not in PLANES:
        _err(e, f"{where}plane {row['plane']!r} not in {PLANES}")
    if row["format"] not in ("webp", "png"):
        _err(e, f"{where}format {row['format']!r} not webp/png")
    if row["quality"] != QUALITY_PIN and row["format"] == "webp":
        _err(e, f"{where}webp quality {row['quality']!r} != pinned q{QUALITY_PIN}")
    if not isinstance(row["bytes"], int) or isinstance(row["bytes"], bool) \
            or row["bytes"] < 0:
        _err(e, f"{where}bytes {row['bytes']!r} not a non-negative int")
    if not HEX_RE.match(str(row["sha256"])):
        _err(e, f"{where}sha256 not lowercase hex64")
    if not isinstance(row["route"], str) or not row["route"]:
        _err(e, f"{where}route empty/non-string")
    if row["namedBy"] not in NAMED_BY_VALUES:
        _err(e, f"{where}namedBy {row['namedBy']!r} not in {NAMED_BY_VALUES}")
    if not (isinstance(row.get("dims"), dict)
            and isinstance(row["dims"].get("w"), int)
            and isinstance(row["dims"].get("h"), int)
            and row["dims"]["w"] > 0 and row["dims"]["h"] > 0):
        _err(e, f"{where}dims must be positive-int {{w,h}}")
    if row.get("buildId") != BUILD_ID:
        _err(e, f"{where}buildId {row.get('buildId')!r} != {BUILD_ID}")
    src = row["source"]
    if not isinstance(src, dict):
        _err(e, f"{where}source must be an object")
        return e
    req_src = {"bundle", "pathId", "class", "subObjectName", "assetGuid",
               "rect", "rounded", "contentAxis"}
    opt_src = {"atlasName", "atlasGuid", "pageBundle", "pageName", "pagePathId"}
    for k in sorted(req_src - set(src)):
        _err(e, f"{where}source missing {k!r}")
    for k in sorted(set(src) - req_src - opt_src):
        _err(e, f"{where}source carries non-contract key {k!r}")
    if not isinstance(src.get("pathId"), int) or isinstance(src.get("pathId"), bool):
        _err(e, f"{where}source.pathId not a SIGNED int")
    if src.get("contentAxis") not in CONTENT_AXES:
        _err(e, f"{where}contentAxis {src.get('contentAxis')!r} invalid")
    rect = src.get("rect")
    if not (isinstance(rect, dict) and set(rect) == {"x", "y", "w", "h"}):
        _err(e, f"{where}rect must be raw floats {{x,y,w,h}}")
    rnd = src.get("rounded")
    if not (isinstance(rnd, dict) and set(rnd) == {"left", "top", "w", "h"}
            and all(isinstance(rnd[k], int) for k in rnd)):
        _err(e, f"{where}rounded must be POST-FLIP ints {{left,top,w,h}}")
    atlas_keys = opt_src & set(src)
    if atlas_keys and atlas_keys != opt_src:
        _err(e, f"{where}partial atlas stamp {sorted(atlas_keys)} — atlas-routed "
                "rows stamp the FULL {atlasName,atlasGuid,pageBundle,pageName,pagePathId}")
    return e


def validate_media_index_row(row, where=""):
    e = []
    if not isinstance(row, dict):
        return [f"{where}index row is not an object"]
    keys = set(row)
    required = {"kind", "srcId", "fieldPath", "assetGuid", "subObjectName",
                "resolved", "chainBreak", "file", "buildId"}
    for k in sorted(required - keys):
        _err(e, f"{where}index row missing {k!r}")
    for k in sorted(keys - required - {"reason"}):
        _err(e, f"{where}index row carries non-contract key {k!r}")
    if e:
        return e
    if row["chainBreak"] not in ("none", "guid", "address", "container"):
        _err(e, f"{where}chainBreak {row['chainBreak']!r} outside pinned enum")
    if not isinstance(row["resolved"], bool):
        _err(e, f"{where}resolved not bool")
    if row["resolved"] is False:
        if row.get("file") is not None:
            _err(e, f"{where}unresolved row carries file {row['file']!r}")
        if "reason" not in row:
            _err(e, f"{where}unresolved row without reason")
        elif row["reason"] not in MISSING_REASON_ENUM:
            _err(e, f"{where}reason {row['reason']!r} outside enum (escape is "
                    f"{REASON_ESCAPE!r}, never a novel value)")
    else:
        if not isinstance(row.get("file"), str) or not row.get("file"):
            _err(e, f"{where}resolved row needs a file path string")
    if row.get("buildId") != BUILD_ID:
        _err(e, f"{where}buildId mismatch")
    return e


def validate_missing_row(row, where=""):
    e = []
    if not isinstance(row, dict):
        return [f"{where}ledger row is not an object"]
    required = {"subObjectName", "assetGuid", "reason", "sampleRefs", "buildId"}
    for k in sorted(required - set(row)):
        _err(e, f"{where}ledger row missing {k!r}")
    for k in sorted(set(row) - required):
        _err(e, f"{where}ledger row carries non-contract key {k!r}")
    if e:
        return e
    if row["reason"] not in MISSING_REASON_ENUM:
        _err(e, f"{where}reason {row['reason']!r} outside the FROZEN enum "
                f"(escape {REASON_ESCAPE!r}; novel values never ship verbatim)")
    if not isinstance(row["sampleRefs"], list) or len(row["sampleRefs"]) > 5:
        _err(e, f"{where}sampleRefs must be a list of <=5")
    if row.get("buildId") != BUILD_ID:
        _err(e, f"{where}buildId mismatch")
    return e


def validate_residue_row(row, where=""):
    e = []
    if not isinstance(row, dict):
        return [f"{where}residue row is not an object"]
    required = {"kind", "srcId", "fieldPath", "pptr", "pairedReferenceEmpty",
                "slotClass", "targetResolution", "basis", "buildId"}
    for k in sorted(required - set(row)):
        _err(e, f"{where}residue row missing {k!r}")
    for k in sorted(set(row) - required):
        _err(e, f"{where}residue row carries non-contract key {k!r}")
    if e:
        return e
    if row["basis"] != RESIDUE_BASIS:
        _err(e, f"{where}basis must be the literal {RESIDUE_BASIS!r}")
    if row["slotClass"] not in SLOT_CLASSES + (SLOT_ESCAPE,):
        _err(e, f"{where}slotClass {row['slotClass']!r} outside enum "
                f"(escape {SLOT_ESCAPE!r})")
    if row["targetResolution"] not in TARGET_RESOLUTIONS:
        _err(e, f"{where}targetResolution {row['targetResolution']!r} outside enum")
    if row.get("pairedReferenceEmpty") is not True:
        _err(e, f"{where}admission requires pairedReferenceEmpty:true")
    p = row.get("pptr")
    if not (isinstance(p, dict) and set(p) == {"fileId", "pathID"}
            and all(isinstance(p[k], int) for k in p)):
        _err(e, f"{where}pptr must be {{fileId,pathID}} ints")
    if row.get("buildId") != BUILD_ID:
        _err(e, f"{where}buildId mismatch")
    return e


def validate_skipped_class_row(row, where=""):
    e = []
    required = {"class", "censusCount", "policy", "buildId"}
    if not isinstance(row, dict):
        return [f"{where}skipped-class row is not an object"]
    for k in sorted(required - set(row)):
        _err(e, f"{where}skipped-class row missing {k!r}")
    for k in sorted(set(row) - required):
        _err(e, f"{where}skipped-class row carries non-contract key {k!r}")
    if e:
        return e
    if not isinstance(row["censusCount"], int) or row["censusCount"] < 1:
        _err(e, f"{where}censusCount must be a positive int")
    if not isinstance(row["policy"], str) or not row["policy"]:
        _err(e, f"{where}policy must be a non-empty string")
    if row.get("buildId") != BUILD_ID:
        _err(e, f"{where}buildId mismatch")
    return e


def validate_crosscheck_report(obj, where=""):
    """crosscheck-report.json: verdict + the P3 LOSSLESS format stamp."""
    e = []
    if not isinstance(obj, dict):
        return [f"{where}crosscheck report is not an object"]
    for k in ("pixelMatchRate", "maxDelta"):
        if k not in obj:
            _err(e, f"{where}report missing {k!r}")
    for k in ("cliVersion", "cliUnityVersion", "cliExportFormat"):
        if k not in obj:
            _err(e, f"{where}P3 stamp missing {k!r}")
    if e:
        return e
    fmt = str(obj["cliExportFormat"]).lower()
    if fmt not in LOSSLESS_CLI_FORMATS:
        _err(e, f"{where}cliExportFormat {obj['cliExportFormat']!r} is not "
                f"LOSSLESS ({LOSSLESS_CLI_FORMATS}); lossy formats violate pin P3")
    if obj["cliUnityVersion"] != UNITY_VERSION:
        _err(e, f"{where}cliUnityVersion must pin {UNITY_VERSION}")
    rate = obj["pixelMatchRate"]
    if not (isinstance(rate, (int, float)) and 0.0 <= rate <= 1.0):
        _err(e, f"{where}pixelMatchRate {rate!r} not a rate")
    return e


def validate_hashes_text(text, tree_root: Path, where=""):
    """`<sha256>  <relpath>` LF lines, sorted by relpath, regenerating from
    the tree byte-for-byte."""
    e = []
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines = lines[:-1]
    rels = []
    for i, line in enumerate(lines, 1):
        parts = line.split("  ")
        if len(parts) != 2 or not HEX_RE.match(parts[0]):
            _err(e, f"{where}:{i}: malformed hashes line (want '<sha256>  <relpath>')")
            continue
        digest, rel = parts
        rels.append(rel)
        p = Path(tree_root) / rel
        if not p.exists():
            _err(e, f"{where}:{i}: {rel!r} absent from the tree")
            continue
        actual = hashlib.sha256(p.read_bytes()).hexdigest()
        if actual != digest:
            _err(e, f"{where}:{i}: sha256 mismatch for {rel!r}")
    if rels != sorted(rels):
        _err(e, f"{where}: lines not sorted by relpath")
    if "\r" in text:
        _err(e, f"{where}: CR byte — LF discipline broken")
    return e


def validate_media_export_md(text, where=""):
    """AC10 self-sufficiency floor: buildId header, every local artifact
    named with its schema presence, full ledger enums, escape values, the
    122-basis literal, hash-summary material, crosscheck verdict material."""
    e = []
    if str(BUILD_ID) not in text:
        _err(e, f"{where}: buildId {BUILD_ID} header absent")
    for token in TEXT_ARTIFACTS_ALWAYS + (PORCELAIN_TRACKED,):
        if token not in text:
            _err(e, f"{where}: local artifact {token!r} not documented")
    for token in ("dlc-content-absent", REASON_ESCAPE, SLOT_ESCAPE,
                  RESIDUE_BASIS, "sha256", "webp", "png",
                  "stale-name", "editor-only-fallback",
                  "mesh-list-target", "level-config-target",
                  "visuals-prefab-target", "empty-sub-name"):
        if token not in text:
            _err(e, f"{where}: self-sufficiency token {token!r} absent")
    if "cliExportFormat" not in text and "crosscheck" not in text.lower():
        _err(e, f"{where}: crosscheck verdict surface absent")
    return e


def amended_media_guard(root: Path):
    """M21 amendment: image-extension hits legal ONLY under
    extracted/media/**; audio/video extensions absolute-zero ANYWHERE.
    Returns sorted `relpath:lineno` hits OUTSIDE the legal zone."""
    import re
    from _validators import MEDIA_EXTENSIONS_AUDIO_VIDEO
    img_re = re.compile(
        r"\.(?:png|jpg|jpeg|tga|dds|bmp|exr)", re.IGNORECASE)
    av_re = re.compile(
        r"\.(?:" + "|".join(MEDIA_EXTENSIONS_AUDIO_VIDEO) + r")", re.IGNORECASE)
    hits = []
    root = Path(root)
    if not root.exists():
        return hits
    allow_names = {"media-catalogue.jsonl", "media-catalogue.jsonl.tmp",
                   "MEDIA-CATALOGUE.md"}
    for p in sorted(root.rglob("*")):
        if p.is_dir():
            continue
        rel = p.relative_to(root).as_posix()
        if Path(rel).name in allow_names:
            continue
        try:
            if p.stat().st_size > 32 * 1024 * 1024:
                continue
        except OSError:
            continue
        try:
            with open(p, "rb") as fh:
                for lineno, chunk in enumerate(_split_lines(fh), 1):
                    if av_re.search(chunk):
                        hits.append(f"{rel}:{lineno}:audio/video")
                    elif img_re.search(chunk) and \
                            not rel.startswith(f"{MEDIA_DIRNAME}/"):
                        hits.append(f"{rel}:{lineno}:image-outside-media")
        except (OSError, ValueError):
            hits.append(f"{rel}:?:unreadable")
    return hits


def _split_lines(fh):
    for raw in fh:
        yield raw.decode("utf-8", errors="ignore")


def _err(errors, msg):
    errors.append(msg)


def assert_manifest_bijection(media_root: Path):
    """AC3: one manifest row per file under web/, sha256 recomputes, and no
    file hides rowless. `outRelPath` lives in extracted/media/ space
    ("web/icons/X.webp"); the comparison is done in that space. Returns
    (rows, problems)."""
    problems = []
    web = Path(media_root) / "web"
    files = sorted(f"web/{p.relative_to(web).as_posix()}"
                   for p in web.rglob("*") if p.is_file()) if web.exists() else []
    man = Path(media_root) / "export-manifest.jsonl"
    rows = []
    if man.exists():
        from _validators import read_jsonl
        rows = read_jsonl(man)
    outs = [str(r.get("outRelPath")) for r in rows]
    if sorted(outs) != files:
        problems.append(
            f"bijection broken: {len(rows)} rows vs {len(files)} files under web/; "
            f"only-in-manifest={sorted(set(outs) - set(files))} "
            f"only-on-disk={sorted(set(files) - set(outs))}")
    for r in rows:
        f = Path(media_root) / str(r.get("outRelPath"))
        if f.exists() and isinstance(r.get("sha256"), str):
            actual = hashlib.sha256(f.read_bytes()).hexdigest()
            if actual != r["sha256"]:
                problems.append(f"sha256 mismatch on {r.get('outRelPath')}")
    return rows, problems


# =================================================================================
# Runner plumbing (registration gate, temp-root pick)
# =================================================================================

_REG_CACHE: dict[str, bool] = {}


def media_registered() -> bool:
    from conftest import run_pack
    cached = _REG_CACHE.get("media")
    if cached is None:
        r = run_pack(["--list"])
        cached = r.returncode == 0 and "media" in r.stdout
        _REG_CACHE["media"] = cached
    return cached


def require_media_registered():
    import pytest
    if not media_registered():
        from _impl import note_missing_module
        note_missing_module("run_all.py --list: stage 'media' not registered yet "
                            "(piece-06 CodeWriter pending)")
        pytest.skip("impl-lagging: stage 'media' not registered by the runner yet "
                    "(piece-06 CodeWriter pending)")


def floors_ok(drive_root: Path, need_gib: float) -> bool:
    try:
        return shutil.disk_usage(str(drive_root)).free >= need_gib * (1 << 30)
    except OSError:
        return False


TEMP_BASE = Path("D:/tpc_pytmp/tw06")


def pick_scratch_root(tag: str) -> Path | None:
    """A D:/A: scratch root meeting the 4 GiB floor; None when no legal root
    exists on this host (black-box legs then skip honestly)."""
    for base in (TEMP_BASE / tag, Path("A:/tpc_pytmp/tw06") / tag):
        try:
            base.mkdir(parents=True, exist_ok=True)
        except OSError:
            continue
        if floors_ok(base.anchor or str(base), TEMP_FLOOR_GIB):
            return base
    return None


def output_floor_ok(extracted_root: Path) -> bool:
    return floors_ok(Path(extracted_root).anchor or str(extracted_root),
                     OUTPUT_FLOOR_GIB)


# =================================================================================
# Impl symbol vocabularies (spec-vocabulary-derived candidate lists)
# =================================================================================

RECT_PARSE_NAMES = ("parse_texture_rect", "parse_rect", "texture_rect",
                    "rect_from_texture_rect", "parse_rd_rect", "rect_from_rd",
                    "normalize_rect")
ROUND_NAMES = ("round_half_away_from_zero", "round_half_away",
               "round_component", "round_rect_component", "round_half_up",
               "round_away_from_zero", "round_coord")
FLIP_NAMES = ("flip_to_image_space", "to_image_space", "image_space_top",
              "bottom_origin_top", "flip_rect", "rect_top_image_space",
              "image_space_rect")
BOUNDS_NAMES = ("check_rect_bounds", "rect_in_bounds", "validate_rect_bounds",
                "bounds_check_rect", "rect_within_page", "rect_fits_page")
PAIR_NAMES = ("match_render_data", "pair_render_data", "resolve_page_for_sprite",
              "find_render_data_entry", "pair_sprite_page", "match_page",
              "resolve_atlas_page", "match_rd_entry")
CROP_NAMES = ("crop_rgba", "crop_page", "crop_pixels", "compose_crop",
              "crop_array", "crop_image")
PASSTHROUGH_NAMES = ("is_pass_through", "rect_covers_texture",
                     "covers_texture", "pass_through", "is_full_texture")
FILENAME_NAMES = ("emit_filename", "asset_filename", "sprite_filename",
                  "output_name", "filename_for_sprite", "naming_for",
                  "out_rel_path", "outrelpath_for")
COLLISION_NAMES = ("collision_suffix", "collision_name", "disambiguated_name",
                   "suffix_signed_path_id", "collision_filename")
ADDRESS_BASENAME_NAMES = ("address_basename", "basename_from_address",
                          "standalone_name", "empty_sub_name",
                          "name_from_address")
JOIN_NAMES = ("join_ref", "resolve_ref", "classify_ref", "resolve_sprite_ref",
              "join_reference", "resolve_reference", "walk_join")
COMPARATOR_NAMES = ("compare_rgba", "compare_crops", "pixel_compare",
                    "compare_arrays", "compare_images", "compare_buffers")
SAMPLE_COMPOSER_NAMES = ("compose_crosscheck_sample",
                         "build_crosscheck_sample",
                         "select_crosscheck_sample", "crosscheck_sample",
                         "pick_crosscheck_sample")
RESIDUE_SCAN_NAMES = ("scan_pptr_residue", "pptr_residue_rows", "residue_scan",
                      "scan_icon_pptr", "collect_residue", "scan_residue")
TEMP_ROOT_NAMES = ("resolve_temp_root", "temp_root", "resolve_scratch_root",
                   "s0_resolve_temp_root", "resolve_media_tmp")
DRIVE_NAMES = ("drive_of", "drive_letter", "root_drive", "drive_of_path",
               "path_drive")
FLOOR_NAMES = ("check_free_space", "free_gib", "space_floor_ok",
               "free_space_gib", "free_space", "gib_free")
CEILING_NAMES = ("check_scope_ceiling", "scope_ceiling_breach",
                 "web_bytes_total", "tree_bytes", "scope_bytes",
                 "ceiling_breach")
EXPORT_MD_NAMES = ("write_media_export_md", "render_media_export_md",
                   "generate_media_export_md", "media_export_markdown",
                   "render_porcelain_md")
GAME_DIR_NAMES = ("resolve_game_dir", "find_game_dir", "resolve_client_dir",
                  "locate_install", "game_dir", "resolve_install")
RUN_NAMES = ("run", "main", "run_stage", "execute")
FORMAT_PIN_NAMES = ("cli_export_format", "CLI_IMAGE_FORMAT",
                    "ALLOWED_CLI_FORMATS", "CLI_FORMAT_ALLOWLIST",
                    "CLI_EXPORT_FORMAT", "LOSSLESS_CLI_FORMATS")
ALPHA_NAMES = ("alpha_roundtrip_ok", "alpha_sanity", "alpha_delta_ok",
               "check_alpha_roundtrip", "alpha_roundtrip_delta",
               "max_alpha_delta")
ENCODE_NAMES = ("encode_webp", "encode_asset", "write_asset",
                "encode_and_write", "emit_asset")
STAMP_NAMES = ("script_hash", "deps_hash", "stamp_payload", "stage_stamp",
               "compute_deps_hash")
