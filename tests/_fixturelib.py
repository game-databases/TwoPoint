"""Synthetic prepared-tree builder library (spec §5.2 hostless smoke mode).

Materializes tiny deterministic fixture trees — NEVER real game bytes —
containing exactly the per-stage upstream sets from spec §5.2:

  stage 0 <- client input fakes only (install-root layout, manifests, headers,
             aa/DLC directory listings with synthetic *.bundle files)
  stage 1 <- + GameAssembly.dll/global-metadata.dat/ScriptingAssemblies.json
             (cumulative: also identity.json as the stage-0 output)
  stage 2 <- + extracted/bundle-roster.jsonl
  stage 3 <- + extracted/addressables/{catalog.json,settings.snapshot.json,
             catalog-coverage.json}
  stage 4 <- + harvest/** (monobehaviour dumps, census, export-manifest,
             media-catalogue), decompiled/structural/*
  stage 5 <- + locales/locale-matrix.json

Everything is sorted, timestamp-free and byte-deterministic so double-run
hash-equality tests are meaningful.
"""
from __future__ import annotations

import hashlib
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _validators import (  # noqa: E402
    BUILD_ID, LOCALE_TABLE, ADDRESSABLES_VERSION, SETTINGS_HASH, VERSION_STRING,
    UNITY_VERSION, METADATA_SANITY, write_jsonl,
)

GAME_DIRNAME = "Two Point Campus"

# --- deterministic filler ------------------------------------------------------

def det_bytes(tag: str, size: int) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < size:
        out.extend(hashlib.sha256(f"{tag}:{counter}".encode()).digest())
        counter += 1
    return bytes(out[:size])


def _write(path: Path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _write_text(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


# --- corpus inventory (names mirror the real corpus shapes, contents synthetic) --

BASE_STRICT_SCENES = [
    "scenes-scene-campus1.unity.bundle",
    "scenes-scene-campus2.unity.bundle",
    "scenes_scenes_config_level_databases.unity.bundle",
]
BASE_SEASONAL = ["scenes-seasonalcontent_scenes_all.bundle"]
# scene-carrying *_optimised.unity shaped FILES (not *.bundle -> not roster rows;
# kept because the family rule strips `_optimised.unity` shapes)
BASE_UNITY_SHAPED_FILES = [
    "scenes_scenes_sandbox_optimised.unity",
    "scenes_scenes_remix.unity",
]
BASE_FAMILIES = [
    "items-general_assets_all.bundle",
    "items-courses-magic_assets_all.bundle",
    "items-courses-potions_assets_all.bundle",
    "rooms_assets_all.bundle",
    "unlockables_assets_all.bundle",
    "configs_assets_all.bundle",
    "configs-app_assets_all.bundle",
    "configs-metagame_assets_all.bundle",
    "configs-levels-prefabs_assets_all.bundle",
    "character-shared_assets_all.bundle",
    "character-shared-textures_assets_all.bundle",
    "animations-character-courses_assets_all.bundle",
    "animations-character-common_assets_all.bundle",
    "environment_assets_all.bundle",
    "environment-landscape_assets_all.bundle",
    "ui_assets_all.bundle",
    "ui-spriteatlas_assets_all.bundle",
    "loadingscreen_assets_all.bundle",
    "art_assets_all.bundle",
    "audio-music_assets_all.bundle",
    "audio-sfx_assets_all.bundle",
    "audio-radio_assets_english.bundle",
    "audio-radio_assets_german.bundle",
    "audio-radio_assets_mandarin.bundle",
    "audio-tannoy_assets_english.bundle",
    "video-intro-hi_assets_all.bundle",
]
HASH_NAMED = [
    "041ed57fabcdef1234567890abcdef12_monoscripts.bundle",
    "0ffa11ce00112233445566778899aabb_unitybuiltinshaders.bundle",
]

def locale_bundles():
    return ["localisation_assets_localisation.bundle"] + [
        f"localisation_assets_localisation_{s}.bundle" for s in sorted(LOCALE_TABLE)
    ]

DLC_SPACE = [
    "dlc-space-art_assets_all.bundle",
    "dlc-space-audio_assets_all.bundle",
    "dlc-space-configs_assets_all.bundle",
    "dlc-space-environment-debug_assets_all.bundle",
    "dlc-space-loadingscreen_assets_all.bundle",
    "dlc-space-ui_assets_all.bundle",
    "dlc-space-ui-spriteatlas_assets_all.bundle",
    "dlc-space-scenes_launchpadlevel.unity.bundle",
    "dlc-space-scenes_moonbaselevel.unity.bundle",
    "dlc-space-scenes_spaceportcitylevel.unity.bundle",
]
DLC_GHOST = [
    "dlc-ghost-art_assets_all.bundle",
    "dlc-ghost-audio_assets_all.bundle",
    "dlc-ghost-configs_assets_all.bundle",
    "dlc-ghost-environment-debug_assets_all.bundle",
    "dlc-ghost-loadingscreen_assets_all.bundle",
    "dlc-ghost-ui_assets_all.bundle",
    "dlc-ghost-ui-spriteatlas_assets_all.bundle",
    "dlc-ghost-scenes_ghosts_optimised.unity.bundle",
]


def base_aa_listing(full_scale: bool):
    """(filename, sceneFlag, localeFlag) rows for aa/StandaloneWindows64."""
    rows = []
    for n in BASE_FAMILIES + HASH_NAMED:
        rows.append((n, "none", None))
    for n in BASE_STRICT_SCENES:
        rows.append((n, ".unity", None))
    for n in BASE_SEASONAL:
        rows.append(("scenes-seasonalcontent_scenes_all.bundle", "seasonal-scenes", None))
    rows.append(("localisation_assets_localisation.bundle", "none", "base"))
    for suffix, _loc in sorted(LOCALE_TABLE.items()):
        rows.append((f"localisation_assets_localisation_{suffix}.bundle", "none", suffix))
    if full_scale:
        have = len(rows)
        for i in range(158 - have):
            rows.append((f"filler-family{i:03d}_assets_all.bundle", "none", None))
    return rows


# --- client-input fakes ---------------------------------------------------------

ACF_TEXT = (
    '"AppState"\n'
    '{\n'
    '\t"appid"\t\t"1649080"\n'
    '\t"Universe"\t\t"1"\n'
    '\t"name"\t\t"Two Point Campus"\n'
    '\t"StateFlags"\t\t"4"\n'
    '\t"installdir"\t\t"Two Point Campus"\n'
    '\t"LastUpdated"\t\t"1766136803"\n'
    '\t"SizeOnDisk"\t\t"4694205668"\n'
    '\t"buildid"\t\t"20226581"\n'
    '\t"TargetBuildID"\t\t"20226581"\n'
    '\t"language"\t\t"english"\n'
    '\t"InstalledDepots"\n'
    '\t{\n'
    '\t\t"1649081"\n'
    '\t\t{\n'
    '\t\t\t"gid"\t\t"289369811377342695"\n'
    '\t\t\t"size"\t\t"4112128282"\n'
    '\t\t}\n'
    '\t}\n'
    '\t"MountedDepots"\n'
    '\t{\n'
    '\t\t"1649081"\t\t"289369811377342695"\n'
    '\t}\n'
    '\t"UserConfig"\n'
    '\t{\n'
    '\t\t"language"\t\t"english"\n'
    '\t}\n'
    '}\n'
)

SETTINGS_JSON = {
    "m_AddressablesVersion": ADDRESSABLES_VERSION,
    "m_IsLocalCatalogInBundle": True,
    "m_ProviderIds": ["ContentCatalogProvider"],
    "m_SettingsHash": SETTINGS_HASH,
    "m_BuildTarget": "StandaloneWindows64",
}


def metadata_bytes(version: int = 27) -> bytes:
    """sanity word @ offset 0, int32-LE version @ offset 4 (spec §2)."""
    return struct.pack("<II", METADATA_SANITY, version) + det_bytes("meta", 32)


def game_root(tree: Path) -> Path:
    return tree / "steamapps" / "common" / GAME_DIRNAME


def aa_dir(tree: Path) -> Path:
    return game_root(tree) / "TPC_Data" / "StreamingAssets" / "aa"


def build_client_inputs(tree: Path, *, full_scale=False, metadata_version=27):
    """Stage-0 upstream: client input fakes ONLY (plus the aa/DLC listings)."""
    root = game_root(tree)
    _write(root / "GameAssembly.dll", b"MZ" + det_bytes("ga", 2046))
    _write(root / "TPC.exe", b"MZ" + det_bytes("tpcexe", 512))
    _write_text(root / "version.txt", VERSION_STRING)

    tpc_data = root / "TPC_Data"
    # globalgamemanagers lives inside TPC_Data (Unity layout); ASCII engine
    # version near offset 0x30
    ggm = bytearray(b"\x00" * 0x30)
    ggm += UNITY_VERSION.encode("ascii") + b"\x00" * (256 - len(ggm) - len(UNITY_VERSION))
    _write(tpc_data / "globalgamemanagers", bytes(ggm))
    _write_text(tpc_data / "version.txt", VERSION_STRING)
    _write(tpc_data / "il2cpp_data" / "Metadata" / "global-metadata.dat",
           metadata_bytes(metadata_version))
    _write_text(tpc_data / "ScriptingAssemblies.json", json.dumps({
        # Revision 4 client reality: NO Assembly-CSharp image ships (the entry
        # still appears in the requested-assembly list and must classify as
        # absent-with-marker); game code lives in TPS.Game/TPS.Core images.
        "Names": [
            "Assembly-CSharp.dll",
            "Assembly-CSharp-firstpass.dll",
            "mscorlib.dll",
            "UnityEngine.CoreModule.dll",
            "TPS.Game.dll",
            "TPS.Core.dll",
            "TPC.Stripped.dll",
        ]
    }, indent=2) + "\n")

    aa = aa_dir(tree)
    _write_text(aa / "settings.json", json.dumps(SETTINGS_JSON, indent=2, sort_keys=True) + "\n")
    _write(aa / "catalog.bundle", det_bytes("catalog-bundle", 4096))
    _write_text(aa / "AddressablesLink" / "provider_pack.json",
                '{"providers":["ContentCatalogProvider"]}\n')
    for name, _sf, _lf in base_aa_listing(full_scale):
        _write(aa / "StandaloneWindows64" / name, det_bytes(f"bundle:{name}", 2048))
    for name in BASE_UNITY_SHAPED_FILES:
        _write(aa / "StandaloneWindows64" / name, det_bytes(f"unity:{name}", 1024))
    for name in DLC_SPACE:
        _write(tree_game_dlc(tree, "space") / name, det_bytes(f"bundle:{name}", 2048))
    for name in DLC_GHOST:
        _write(tree_game_dlc(tree, "ghost") / name, det_bytes(f"bundle:{name}", 2048))

    # appmanifest discovered by walking up <=4 levels to the steamapps dir
    _write_text(tree / "steamapps" / "appmanifest_1649080.acf", ACF_TEXT)


def tree_game_dlc(tree: Path, axis: str) -> Path:
    return game_root(tree) / "DLCs" / axis


# --- synthetic extracted-side upstream artifacts ---------------------------------

def roster_rows(full_scale=False):
    rows = []
    aa_rel = "TPC_Data/StreamingAssets/aa/StandaloneWindows64"
    for name, sf, lf in base_aa_listing(full_scale):
        # localeFlag carries the resolved value: 'base' for the unnamed
        # overlay, else the BCP-47 code (matches the pipeline's convention)
        resolved = "base" if lf == "base" else (
            LOCALE_TABLE.get(lf) if lf else None)
        rows.append({
            "relpath": f"{aa_rel}/{name}", "dirClass": "base",
            "bytes": len(det_bytes(f"bundle:{name}", 2048)) if not name.endswith(".unity") else 1024,
            "sceneFlag": sf, "localeFlag": resolved, "buildId": BUILD_ID,
        })
    for name in DLC_SPACE:
        rows.append({"relpath": f"DLCs/space/{name}", "dirClass": "dlc-space",
                     "bytes": 2048, "sceneFlag":
                     ".unity" if name.endswith(".unity.bundle") else "none",
                     "localeFlag": None, "buildId": BUILD_ID})
    for name in DLC_GHOST:
        rows.append({"relpath": f"DLCs/ghost/{name}", "dirClass": "dlc-ghost",
                     "bytes": 2048, "sceneFlag":
                     ".unity" if name.endswith(".unity.bundle") else "none",
                     "localeFlag": None, "buildId": BUILD_ID})
    rows.sort(key=lambda r: r["relpath"])
    return rows


CATALOG_KEYS_SPEC = [
    # (key, bundle reference spelling — deliberately varied to exercise normalization)
    ("Config.Global", "configs_assets_all.bundle"),
    ("Course.Magic", "ITEMS-COURSES-MAGIC_ASSETS_ALL.BUNDLE"),          # case-fold
    ("DLC.Ghost.Audio", "DLCs/ghost/dlc-ghost-audio_assets_all.bundle"),  # dir prefix
    ("DLC.Space.UI", "dlc-space-ui_assets_all.bundle"),
    ("Hash.MonoScripts", "041ed57fabcdef1234567890abcdef12_monoscripts.bundle"),
    ("Items.General", "StandaloneWindows64/items-general_assets_all.bundle"),
    ("Locale.French", "localisation_assets_localisation_french.bundle"),
    ("Rooms.All", "rooms_assets_all.bundle"),
    ("Scene.Campus1", "scenes-scene-campus1.unity.bundle"),
    ("Unlockables.All", "unlockables_assets_all.bundle"),
]


def build_catalog_json(extracted: Path):
    keys = []
    for k, ref in CATALOG_KEYS_SPEC:
        keys.append({"key": k, "kind": "bundle", "bundle": ref,
                     "address": f"Assets/Content/{k.replace('.', '/')}",
                     "dependencies": [], "providerIds": ["BundledAssetProvider"]})
    obj = {"meta": {"buildId": BUILD_ID, "addressablesVersion": ADDRESSABLES_VERSION,
                    "settingsHash": SETTINGS_HASH,
                    "providerIds": ["ContentCatalogProvider", "BundledAssetProvider"]},
           "keys": keys}
    _write_text(extracted / "addressables" / "catalog.json",
                json.dumps(obj, indent=2, sort_keys=True) + "\n")
    snap = dict(SETTINGS_JSON)
    snap["source"] = "aa/settings.json verbatim copy"
    _write_text(extracted / "addressables" / "settings.snapshot.json",
                json.dumps(snap, indent=2, sort_keys=True) + "\n")
    # coverage universes computed over THIS fixture's roster + references
    roster = {Path(r["relpath"]).name for r in roster_rows()}
    refs = {ref.replace("\\", "/").rsplit("/", 1)[-1].lower() for _k, ref in CATALOG_KEYS_SPEC}
    covered = {r for r in roster if r.lower() in refs}
    cov = {"keysTotal": len(keys),
           "distinctBundlesReferenced": len(covered),
           "bundlesUnreferenced": sorted(roster - covered)}
    _write_text(extracted / "addressables" / "catalog-coverage.json",
                json.dumps(cov, indent=2, sort_keys=True) + "\n")


def build_identity_fixture(extracted: Path, full_scale=False):
    strict_base = len(BASE_STRICT_SCENES)
    seasonal_base = strict_base + len(BASE_SEASONAL)
    strict_install = strict_base + sum(
        1 for n in DLC_SPACE + DLC_GHOST if n.endswith(".unity.bundle"))
    obj = {
        "appid": 1649080, "buildId": BUILD_ID, "targetBuildId": BUILD_ID,
        "versionString": VERSION_STRING, "unityVersion": UNITY_VERSION,
        "metadataVersion": 27, "dumper": "il2cppdumper",
        "addressablesVersion": ADDRESSABLES_VERSION, "settingsHash": SETTINGS_HASH,
        "languageSetting": "english",
        "expectedBundles": {"aa": 158, "dlc-space": 10, "dlc-ghost": 8},
        "localeBundleCount": 14,
        "sceneCounts": {"strictUnityBase": strict_base,
                        "seasonalSceneCarryingBase": seasonal_base,
                        "strictUnityInstall": strict_install,
                        "sceneCarryingInstall": strict_install + len(BASE_SEASONAL)},
        "liveCounts": {"aa": len(base_aa_listing(full_scale)), "dlc-space": len(DLC_SPACE),
                       "dlc-ghost": len(DLC_GHOST)},
    }
    _write_text(extracted / "identity.json", json.dumps(obj, indent=2, sort_keys=True) + "\n")


# --- stage 4/5 substrate: monobehaviour dumps + locale matrix ---------------------

MATRIX = {
    # key -> (locales containing it, inBase)
    "config_global_tagline": (["en", "ru", "tr"], False),
    "course_magic_desc": (["en", "ja"], False),
    "decoy_unused_key": (["en"], False),
    "item_alpha_name": (["en", "fr", "de"], False),
    "item_beta_desc": (["en"], False),
    "level_campus1_name": (["en", "zh-Hans", "zh-Hant"], False),
    "node_research_label": (["en", "fr"], False),
    "room_main_title": (sorted(LOCALE_TABLE.values()), False),
    "student_nerd_name": (["en", "ko", "pl"], False),
    "unlock_kudosh_title": (["en", "es"], False),
    "ui_common_cancel": ([], True),
    "ui_common_ok": ([], True),
}

# entity -> (class, family, bundle stem, pathId, fields)
ENTITIES = [
    ("item_alpha", "ItemConfig", "items-general", "items-general_assets_all", 101,
     {"displayName": "A fine sword", "id": "item_alpha", "nameLoc": "item_alpha_name"}),
    ("item_beta", "ItemConfig", "items-general", "items-general_assets_all", 102,
     {"flavour": "standard issue", "id": "item_beta", "nameLoc": "item_beta_title"}),
    ("item_gamma", "ItemConfig", "items-general", "items-general_assets_all", 103,
     {"flavor": "A shiny blade of legend", "id": "item_gamma"}),
    ("room_main", "RoomConfig", "rooms", "rooms_assets_all", 201,
     {"id": "room_main", "slots": 12, "titleLoc": "room_main_title"}),
    ("course_magic", "CourseConfig", "items-courses-magic", "items-courses-magic_assets_all", 301,
     {"descLoc": "course_magic_desc", "id": "course_magic", "length": 3}),
    ("node_research", "MetagameNodeConfig", "configs-metagame", "configs-metagame_assets_all", 401,
     {"id": "node_research", "label": "node_research_labl"}),
    ("student_nerd", "StudentTypeConfig", "character-shared", "character-shared_assets_all", 501,
     {"id": "student_nerd", "nameLoc": "student_nerd_name"}),
    ("unlock_kudosh", "UnlockableConfig", "unlockables", "unlockables_assets_all", 601,
     {"cost": 150, "id": "unlock_kudosh", "titleLoc": "unlock_kudosh_title"}),
    ("level_campus1", "CampusLevelConfig", "configs", "configs_assets_all", 701,
     {"id": "level_campus1", "nameLoc": "level_campus1_name"}),
    ("config_global", "GlobalConfig", "configs-app", "configs-app_assets_all", 801,
     {"id": "config_global", "taglineLoc": "config_global_tagline"}),
]
BIG_FAMILY_COUNT = 1200  # >1000 -> identifier sample policy kicks in
UNMAPPED = [
    ("WidgetConfig", "widget-things", "widget-things_assets_all", [901, 902]),
]
HARD_JOIN_IDS = ["item_alpha", "room_main", "course_magic", "student_nerd",
                 "unlock_kudosh", "level_campus1", "config_global"]


def mb_dump_obj(cls, fields, typetree=True):
    # `_scriptClass` is the pipeline's class signal; "class" kept for humans
    return {"_scriptClass": cls, "class": cls,
            "typetreeDecoded": typetree, "fields": fields}


def build_monobehaviours(extracted: Path):
    """harvest/monobehaviours/** + textassets + derived census/manifest/catalogue."""
    harv = extracted / "harvest"
    dumps = []       # (family, cls, relpath-under-monobehaviours)
    manifest = []    # export-manifest rows
    catalogue = []   # media-catalogue rows (carved-out classes)

    def dump(family, cls, stem, path_id, fields):
        rel = f"{family}/{cls}/{stem}_{path_id}.json"
        _write_text(harv / "monobehaviours" / rel,
                    json.dumps(mb_dump_obj(cls, fields), sort_keys=True, indent=2) + "\n")
        dumps.append((family, cls, rel, stem, path_id))
        manifest.append({"sourceBundle": f"{stem}.bundle", "pathId": path_id,
                         "class": cls, "bytes": 256,
                         "outRelPath": f"harvest/monobehaviours/{rel}"})

    for eid, cls, family, stem, pid, fields in ENTITIES:
        dump(family, cls, stem, pid, fields)
    for i in range(BIG_FAMILY_COUNT):
        dump("items-general", "ItemBigConfig", "items-general_assets_all", 20000 + i,
             {"id": f"itembig_{i:04d}", "tier": i % 5})

    for cls, family, stem, pids in UNMAPPED:
        for pid in pids:
            dump(family, cls, stem, pid, {"id": f"widget_{pid}", "weight": 1})

    for i, (stem, pid) in enumerate([("items-general_assets_all", 90001),
                                     ("items-general_assets_all", 90002)]):
        rel = f"items-general/{stem}_{pid}.txt"
        _write_text(harv / "textassets" / rel, f"textasset-{i}\ndeterministic\n")
        manifest.append({"sourceBundle": f"{stem}.bundle", "pathId": pid,
                         "class": "TextAsset", "bytes": 32,
                         "outRelPath": f"harvest/textassets/{rel}"})

    # carved-out classes: census + catalogue rows only, ZERO decoded bytes
    catalogue_spec = [
        ("Texture2D", "items-general_assets_all.bundle", "tex_sword", 100001, "base", 512),
        ("Texture2D", "items-general_assets_all.bundle", "tex_shield", 100002, "base", 640),
        ("Sprite", "items-general_assets_all.bundle", "spr_coin", 100003, "base", 128),
        ("AudioClip", "audio-music_assets_all.bundle", "mus_theme", 110001, "base", 262144),
        ("Mesh", "environment_assets_all.bundle", "mesh_tree", 120001, "base", 4096),
    ]
    for cls, bundle, name, pid, axis, est in catalogue_spec:
        catalogue.append({"class": cls, "bundle": bundle, "name": name,
                          "pathId": pid, "bytesEstimate": est, "contentAxis": axis})

    # per-bundle census derived from what was actually written (+ carved classes)
    per_bundle = {}
    for family, cls, rel, stem, pid in dumps:
        c = per_bundle.setdefault(f"{stem}.bundle", {})
        c[cls] = c.get(cls, 0) + 1
    for cls, bundle, name, pid, axis, est in catalogue_spec:
        c = per_bundle.setdefault(bundle, {})
        c[cls] = c.get(cls, 0) + 1
    for bundle in sorted(per_bundle):
        classes = per_bundle[bundle]
        obj = {"objectsByClass": {k: classes[k] for k in sorted(classes)},
               "bytesByClass": {k: classes[k] * 256 for k in sorted(classes)},
               "errors": []}
        _write_text(harv / "census" / "bundles" / f"{bundle}.json",
                    json.dumps(obj, indent=2, sort_keys=True) + "\n")
    write_jsonl(harv / "export-manifest.jsonl", sorted(manifest, key=lambda r: r["outRelPath"]))
    write_jsonl(extracted / "media-catalogue.jsonl",
                sorted(catalogue, key=lambda r: (r["class"], r["bundle"], r["pathId"])))


def build_structural_fixture(extracted: Path):
    """Stage-1 structural OUTPUTS over the Revision-4 multi-image reality:
    game code lives in TPS.Game/TPS.Core images; Assembly-CSharp is classified
    absent-with-marker, never present."""
    st = extracted / "decompiled" / "structural"
    idx = [
        {"assembly": "Assembly-CSharp", "status": "dummy-absent(stripped)"},
        {"assembly": "mscorlib", "status": "dummy-present"},
        {"assembly": "UnityEngine.CoreModule", "status": "dummy-present"},
        {"assembly": "TPS.Core", "status": "dummy-present"},
        {"assembly": "TPS.Game", "status": "dummy-present"},
        {"assembly": "TPC.Stripped", "status": "dummy-absent(stripped)"},
    ]
    _write_text(st / "assembly-index.json", json.dumps(
        {"meta": {"hierarchySource": "dummydll-typedef-enumeration"},
         "assemblies": idx}, indent=2) + "\n")
    hier = [
        {"assembly": "TPS.Game", "namespace": "TPC.Items", "name": "ItemConfig",
         "baseType": "ScriptableObject", "interfaces": ["ILocNamed"],
         "methodCount": 2, "fieldCount": 3},
        {"assembly": "TPS.Game", "namespace": "TPC.Rooms", "name": "RoomConfig",
         "baseType": "RoomBase", "interfaces": [], "methodCount": 0, "fieldCount": 1},
        {"assembly": "TPS.Core", "namespace": "TPC.Core", "name": "ServiceLocator",
         "baseType": None, "interfaces": [], "methodCount": 4, "fieldCount": 1},
    ]
    write_jsonl(st / "class-hierarchy.jsonl", hier)
    write_jsonl(st / "id-registries" / "rarity.jsonl",
                [{"name": "Common", "value": 0}, {"name": "Rare", "value": 1}])


MATRIX_OBJ = None


def build_locale_matrix_fixture(extracted: Path):
    global MATRIX_OBJ
    keys = {}
    for k, (locs, in_base) in sorted(MATRIX.items()):
        keys[k] = {"inBase": in_base, "locales": sorted(locs)}
    obj = {"buildId": BUILD_ID, "keys": keys,
           "locales": sorted(LOCALE_TABLE.values())}
    MATRIX_OBJ = obj
    _write_text(extracted / "locales" / "locale-matrix.json",
                json.dumps(obj, indent=2, sort_keys=True) + "\n")


# --- Revision-4 fallback-version seeding substrates (stages 3+4) -------------------
# Content bundles' UnityFS headers read literally "0.0.0" on this client
# (catalog.bundle alone reports the true engine version); UnityPy raises
# UnityVersionFallbackError on those unless FALLBACK_UNITY_VERSION is seeded
# from identity.json's unityVersion.

ZERO_VERSION_HEADER = "0.0.0"


def unityfs_header_bytes(version_string: str = ZERO_VERSION_HEADER,
                         engine_version: str = UNITY_VERSION,
                         tail: int = 256) -> bytes:
    """Leading bytes of a synthetic UnityFS bundle: magic + format word + the
    bundle's Unity version cstring + the engine revision cstring + filler."""
    out = bytearray()
    out += b"UnityFS\x00"
    out += (7).to_bytes(4, "big")
    out += version_string.encode("ascii") + b"\x00"
    out += engine_version.encode("ascii") + b"\x00"
    out += det_bytes(f"unityfs:{version_string}:{engine_version}", tail)
    return bytes(out)


def write_seed_probe_bundles(directory: Path) -> dict[str, Path]:
    """The three seeding substrates shared by the stage-3 and stage-4 tests:
    a `0.0.0` header, an unparseable/garbage header, and a well-formed one."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    paths = {
        "zero": directory / "content-zero.bundle",
        "garbage": directory / "content-garbage.bundle",
        "true-version": directory / "catalog-like.bundle",
    }
    _write(paths["zero"], unityfs_header_bytes(ZERO_VERSION_HEADER))
    _write(paths["garbage"], det_bytes("unparseable-bundle", 512))
    _write(paths["true-version"],
           unityfs_header_bytes(UNITY_VERSION, UNITY_VERSION))
    return paths


# --- orchestrator -----------------------------------------------------------------

STAGE_ARTIFACTS = ("verify-client", "decompile", "harvest-catalog",
                   "harvest-bundles", "localisation", "emit-stub-datasets")


def build_tree(out: Path, stage: str, *, full_scale=False, metadata_version=27) -> Path:
    if stage not in STAGE_ARTIFACTS:
        raise ValueError(f"unknown stage {stage!r}; expected one of {STAGE_ARTIFACTS}")
    out = Path(out)
    extracted = out / "extracted"
    build_client_inputs(out, full_scale=full_scale, metadata_version=metadata_version)
    order = STAGE_ARTIFACTS.index(stage)
    if order >= 1:  # decompile sees stage-0 outputs (identity) among upstream tree state
        build_identity_fixture(extracted, full_scale)
    if order >= 2:
        write_jsonl(extracted / "bundle-roster.jsonl", roster_rows(full_scale))
    if order >= 3:
        build_catalog_json(extracted)
    if order >= 4:
        build_monobehaviours(extracted)
        build_structural_fixture(extracted)
    if order >= 5:
        build_locale_matrix_fixture(extracted)
    return out
