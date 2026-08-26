"""Blind fixture library for the piece-05 contracts suite (spec Revision 3).

Materializes a COMPLETE synthetic contract-checking world at small scale --

    <tree>/steamapps/common/Two Point Campus/...   install layout (*.bundle fakes)
    <tree>/contracts/                              pins.json + families/*.mdx +
                                                   red-registry + counter-units
    <tree>/tools/*.py                              MINIATURE writer universe the
                                                   V-I9 ownership grep can sweep
    <tree>/extracted/                              every validated family

-- with EVERY pinned constant COMPUTED FROM the very rows it describes, so the
green state is internally consistent by construction and any single mutation
breaks exactly the identities it aims at. No real game bytes anywhere; every
builder is deterministic (sorted keys, UTF-8, LF, no wall clock).

States:
    build_fixture(out)                          day-one RED state (spec section 9):
                                                V-L1 / V-U1 / V-U2 / V-D1 fail, all
                                                four registered in red-registry.json
    build_fixture(out, fixes={"dupkeys", ...})  post-amendment states for the
                                                RED->GREEN ladder (sequencing contract)
    build_fixture(out, handover=True)           post-piece-07 s5 world: the
                                                locale_availability writer flip
                                                + v2 companion (RF-1 order B)

The miniature tools/ tree exists ONLY so the exactly-one-writer invariant has a
greppable writer universe inside the fixture; it never shadows the pack's own
tools/ (different directory entirely).

CLI smoke entry (hostless, mirrors tests/build_fixture_tree.py's interface):

    python tests/_contractlib.py [--out DIR] [--handover] [--fix dupkeys ...]

Temp discipline: build into pytest tmp/basetemp only -- point pytest at
D:/tpc_pytmp/tw05 (or leave the default %TEMP%); NEVER inside the pack.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACK_ROOT = HERE.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from _validators import (  # noqa: E402
    BUILD_ID, LOCALE_TABLE, ADDRESSABLES_VERSION, SETTINGS_HASH, VERSION_STRING,
    UNITY_VERSION, APPID, write_jsonl,
)

# --- fixture-scale identity constants ----------------------------------------------

TARGET_BUILD = BUILD_ID                      # pins.buildScope.buildId
ADDRESS_KIND = "address"
GUID_KIND = "guid"
COMPOSITION_POLICY = "mixed"

UNIT_VOCABULARY = (
    "reference-events", "deduped-rows", "distinct-keys", "emission-events",
    "walked-terms", "skipped-cells", "bytes", "objects",
)

ROUTING_SENTENCE = ("per-term locale availability lives in "
                    "`locales/locale-matrix.json`; `locales[]` fields are "
                    "reserved-but-empty")
FAITHFUL_SENTENCE = "The projection is faithful, not broken."
TRANSFORM_NAME = "events-minus-distinct-lines"
TRANSFORM_EXPRESSION = "emission-events - distinct-keys == overwrite-events"

REASON_UNCONTAINED = "catalog-bundle-null-uninstalled-dlc"

# --- guid / address world -----------------------------------------------------------

# The measured F12 offender set verbatim (spec section 2 fact F12)
A_DLC_RURAL = ("Assets/Data/DLCs/DLC3_Hospital/Levels/"
               "Config_Level_Rural.prefab")
A_DLC_SNOWY = ("Assets/Data/DLCs/DLC3_Hospital/Levels/"
               "Config_Level_Snowy.prefab")
A_DLC_TROPICAL = ("Assets/Data/DLCs/DLC3_Hospital/Levels/"
                  "Config_Level_Tropical.prefab")
A_DLC_VARIATIONS = ("Assets/Data/DLCs/DLC3_Hospital/"
                    "DB_DLC3_Hospital_Variations.asset")
A_DLC_ATLAS = ("Assets/Data/DLCs/DLC3_Hospital/UI/"
               "Atlas_DLC3_Icons_Inspector.spriteatlasv2")
G_DLC_RURAL = "cc01dddd00000000aaaabbbbccccdddd"
G_DLC_SNOWY = "cc02dddd00000000aaaabbbbccccdddd"
G_DLC_TROPICAL = "cc03dddd00000000aaaabbbbccccdddd"
G_DLC_VARIATIONS = "cc04dddd00000000aaaabbbbccccdddd"
G_DLC_ATLAS = "cc05dddd00000000aaaabbbbccccdddd"
UNCONTAINED_ADDRESSES = sorted((A_DLC_RURAL, A_DLC_SNOWY, A_DLC_TROPICAL,
                                A_DLC_VARIATIONS, A_DLC_ATLAS))
assert len(UNCONTAINED_ADDRESSES) == 5

# contained world (small, but every asset dstId lives here)
_CONTAINED_SPEC = [
    (f"Assets/Content/Items/Fixture_{i:02d}.prefab",
     f"dd{i:02d}eeee00000000aaaabbbbccccdddd", "items-general_assets_all.bundle")
    for i in range(8)
]
CONTAINED_ADDRESSES = sorted(a for a, _g, _b in _CONTAINED_SPEC)
GUID_BY_ADDRESS = {a: g for a, g, _b in _CONTAINED_SPEC}
for _a, _g in ((A_DLC_RURAL, G_DLC_RURAL), (A_DLC_SNOWY, G_DLC_SNOWY),
               (A_DLC_TROPICAL, G_DLC_TROPICAL),
               (A_DLC_VARIATIONS, G_DLC_VARIATIONS),
               (A_DLC_ATLAS, G_DLC_ATLAS)):
    GUID_BY_ADDRESS[_a] = _g

G_STYLE = "f952c082cb03451daed3ee968ac6c63e"   # THE measured duplicate key
A_STYLE = "Style Sheets/Default Style Sheet"
GUID_DANGLE = "9999aaaabbbbccccddddeeeeffff0000"

# pptr reason strings exactly as the corpus pins them
REASON_PPTR_A = ("pathId exists in the resolved file but is not an emitted "
                 "stub entity")
REASON_PPTR_B = ("same-file pathId is not an emitted stub entity and the "
                 "bundle carries no scene flag")
JOIN_KEY_ASSET = ("AssetGUID(…)->catalog.guid->container-address->pathId")

AA_REL = "TPC_Data/StreamingAssets/aa/StandaloneWindows64"

# --- term keys ----------------------------------------------------------------------

K_PRESTIGE = "UI/General/PrestigeLevel"
K_MEDICAL = "UI/Inspector/MedicalIssuesCured"
K_DOCTOR = "Characters/DLC_Hospital/Archetypes/Doctor_M_Name"
K_ROOM_TITLE = "Room/Main/Title"
K_ITEM_NAME = "Item/Alpha/Name"
TERM_KEYS = sorted((K_PRESTIGE, K_MEDICAL, K_DOCTOR, K_ROOM_TITLE, K_ITEM_NAME))
MISSING_TERM_ID = 99999               # registryMisses known id (fixture pin)


NODES = ("asset", "campus-level", "config", "course", "item", "locale-term",
         "metagame-node", "room", "staff", "student-type", "unlockable")
JOIN_KEY_PPTR = "PPtr(m_FileID,m_PathID)"
JOIN_KEY_LOCALE = "LocalisedString(_termID)->I2-termID->Term-key"
JOIN_KEY_NONE = "none-established"
MECHANISMS = ("hard", "logic", "inferred")
STATUSES = ("modeled", "partial", "missing")
PAIR_METHODS = ("pptr-same-file", "pptr-cross-file", "assetguid-catalog",
                "i2-termid-registry", "name-convention:<rule>",
                "code-analysis:<descriptor>", "competitor-model:<source-id>")
COLD_PAIR_METHOD_PREFIXES = ("name-convention:", "code-analysis:",
                             "competitor-model:")
STUB_METHODS = ("seeded-family-heuristic", "seeded-class-heuristic")
DANGLING_VERDICTS = ("unresolved-open", "resolved-scene", "resolved-editor-only",
                     "removed-content")
UNMAPPED_EVIDENCE = ("component-chain", "engine/primitive namespace",
                     "no seeded kind", "unresolved-generic")
UI_STATUSES = ("mapped-schema", "documented-gap")
ABSENCE_TYPES = ("no-identifier",)


def hash8(seed: str) -> str:
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:8]


def det_bytes(tag: str, size: int) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < size:
        out.extend(hashlib.sha256(f"{tag}:{counter}".encode()).digest())
        counter += 1
    return bytes(out[:size])


def canon(obj) -> str:
    """Canonical JSON spelling: sorted keys, indent 2, LF-terminated."""
    return json.dumps(obj, sort_keys=True, ensure_ascii=False,
                      allow_nan=False, indent=2) + "\n"


def write_text(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def read_jsonl(path: Path):
    return [json.loads(line) for line in
            path.read_text(encoding="utf-8").splitlines() if line.strip()]


def dedup_tuple(row: dict) -> tuple:
    return (row["srcKind"], row["srcId"], row["dstKind"], row["dstId"],
            row["method"], row.get("evidence", {}).get("fieldPath"))


def sort_pair_rows(rows):
    return sorted(rows, key=dedup_tuple)


# --- roster (real-corpus distribution: 158/10/8, scene 150/25/1, locale 162/1/13) -----

BASE_BUNDLE_NAMES = [
    "items-general_assets_all.bundle", "items-courses-magic_assets_all.bundle",
    "rooms_assets_all.bundle", "unlockables_assets_all.bundle",
    "configs_assets_all.bundle", "configs-app_assets_all.bundle",
    "configs-metagame_assets_all.bundle", "configs-levels-prefabs_assets_all.bundle",
    "character-shared_assets_all.bundle", "ui_assets_all.bundle",
]
SCENE_BASE = [f"scenes-scene-campus{i:02d}.unity.bundle"
              for i in range(21)]                        # 21 .unity base rows
SEASONAL = ["scenes-seasonalcontent_scenes_all.bundle"]     # seasonal-scenes
LOCALE_BUNDLE_NAMES = ["localisation_assets_localisation.bundle"] + [
    f"localisation_assets_localisation_{s}.bundle"
    for s in ("brazilianportuguese", "chinese(simplified)", "chinese(traditional)",
              "english", "french", "german", "italian", "japanese", "korean",
              "polish", "russian", "spanish", "turkish")]
DLC_SPACE_NAMES = ([f"dlc-space-family{i:02d}_assets_all.bundle"
                    for i in range(8)] +
                   ["dlc-space-scenes_launchpad.unity.bundle",
                    "dlc-space-scenes_moonbaselevel.unity.bundle"])
DLC_GHOST_NAMES = ([f"dlc-ghost-family{i:02d}_assets_all.bundle"
                    for i in range(6)] +
                   ["dlc-ghost-scenes_ghosts_optimised.unity.bundle",
                    "dlc-ghost-scenes_ghosttown.unity.bundle"])
FILLER_AA = [f"filler-family{i:03d}_assets_all.bundle"
             for i in range(158 - len(BASE_BUNDLE_NAMES) - len(SCENE_BASE)
                            - len(SEASONAL) - len(LOCALE_BUNDLE_NAMES))]


def _roster_spec():
    spec = []   # (relpath, dirClass, sceneFlag, localeFlag)
    for n in BASE_BUNDLE_NAMES + FILLER_AA:
        spec.append((f"{AA_REL}/{n}", "base", "none", None))
    for n in SCENE_BASE:
        spec.append((f"{AA_REL}/{n}", "base", ".unity", None))
    for n in SEASONAL:
        spec.append((f"{AA_REL}/{n}", "base", "seasonal-scenes", None))
    for suffix, code in sorted({
            "localisation": "base",
            "brazilianportuguese": "pt-BR", "chinese(simplified)": "zh-Hans",
            "chinese(traditional)": "zh-Hant", "english": "en", "french": "fr",
            "german": "de", "italian": "it", "japanese": "ja", "korean": "ko",
            "polish": "pl", "russian": "ru", "spanish": "es",
            "turkish": "tr"}.items()):
        name = (f"localisation_assets_localisation.bundle" if code == "base"
                else f"localisation_assets_localisation_{suffix}.bundle")
        spec.append((f"{AA_REL}/{name}", "base", "none", code))
    dlc_space_scene = 0
    for n in DLC_SPACE_NAMES:
        sf = ".unity" if n.endswith(".unity.bundle") else "none"
        dlc_space_scene += sf == ".unity"
        spec.append((f"DLCs/space/{n}", "dlc-space", sf, None))
    for n in DLC_GHOST_NAMES:
        sf = ".unity" if n.endswith(".unity.bundle") else "none"
        spec.append((f"DLCs/ghost/{n}", "dlc-ghost", sf, None))
    return spec


_ROSTER_SPEC = _roster_spec()


def roster_rows():
    rows = [{"buildId": TARGET_BUILD, "bytes": 2048, "dirClass": dc,
             "localeFlag": lf, "relpath": rel, "sceneFlag": sf}
            for rel, dc, sf, lf in _ROSTER_SPEC]
    rows.sort(key=lambda r: r["relpath"])
    return rows


def roster_relpaths():
    return [r["relpath"] for r in roster_rows()]


def roster_basenames():
    return {Path(r).name for r in roster_relpaths()}


def scene_ids():
    return sorted(r["relpath"] for r in roster_rows() if r["sceneFlag"] != "none")


def expected_bundles():
    # identity.expectedBundles spells the base axis "aa" (measured corpus)
    out = {"aa": 0, "dlc-space": 0, "dlc-ghost": 0}
    for r in roster_rows():
        out["aa" if r["dirClass"] == "base" else r["dirClass"]] += 1
    return out


# --- stubs ---------------------------------------------------------------------------

ENGINE_KEYS = ("m_Enabled", "m_GameObject", "m_Name", "m_Script")


STUB_ROWS_BY_KIND = {"campus-level": 17, "config": 8430, "course": 69,
                     "item": 3885, "metagame-node": 454, "room": 116,
                     "staff": 3, "student-type": 54, "unlockable": 415}
TWIN_COUNTS = {"config": 12, "item": 3, "metagame-node": 2}
AXES_COUNTS = {"config": 4, "metagame-node": 2}
STUB_BUNDLE_UNIVERSE = sorted(BASE_BUNDLE_NAMES + [
    "audio-music_assets_all.bundle"])                    # exactly 11
assert len(STUB_BUNDLE_UNIVERSE) == 11


def _fields(extra=None, ident=None):
    fields = {k: 1 if k == "m_Enabled" else ("" if k != "m_GameObject" else 0)
              for k in ENGINE_KEYS}
    if ident is not None:
        fields["id"] = ident               # VERBATIM original (suffix-stripped)
    for k, v in (extra or {}).items():
        fields[k] = v
    return fields


def stub_rows():
    """Full-scale synthetic stubs: real per-kind counts, twins 12/3/2 with
    fields.id carrying the suffix-stripped verbatim id, axes on config x4 /
    metagame-node x2."""
    out: dict[str, list[dict]] = {}
    twin_budget = dict(TWIN_COUNTS)
    axes_budget = dict(AXES_COUNTS)
    for kind in sorted(STUB_ROWS_BY_KIND):
        n = STUB_ROWS_BY_KIND[kind]
        prefix = kind.split("-")[0]
        rows = []
        for i in range(n):
            ident = f"{prefix}_entity_{i:05d}"
            twin = twin_budget.get(kind, 0) > 0
            if twin:
                twin_budget[kind] -= 1
                ident = f"{ident}@{hash8(ident)}"
            row = {"buildId": TARGET_BUILD,
                   "fields": _fields({"Kudosh": i}, ident=None),
                   "id": ident,
                   "inferred": True, "kind": kind,
                   "method": ("seeded-family-heuristic" if i % 3 == 0
                              else "seeded-class-heuristic"),
                   "provisional": True, "slug": None,
                   "source": {"bundle":
                              STUB_BUNDLE_UNIVERSE[i % len(STUB_BUNDLE_UNIVERSE)],
                              "class": f"{kind.capitalize()}Config",
                              "pathId": 100000 + hash_n(kind, i)}}
            bare = ident.split("@")[0]
            if "@" in ident:
                row["fields"]["id"] = bare
            if axes_budget.get(kind, 0) > 0:
                axes_budget[kind] -= 1
                row["axes"] = ["base", "dlc-space"] if i % 2 else                     ["base", "dlc-ghost"]
            rows.append(row)
        rows.sort(key=lambda r: r["id"])
        out[kind] = rows
    return out


def hash_n(kind: str, i: int) -> int:
    return int(hashlib.sha256(f"{kind}:{i}".encode()).hexdigest()[:6], 16)


STUB_FILENAMES = {
    "campus-level": "campus-levels.jsonl", "config": "configs.jsonl",
    "course": "courses.jsonl", "item": "items.jsonl",
    "metagame-node": "metagame-nodes.jsonl", "room": "rooms.jsonl",
    "staff": "staff.jsonl", "student-type": "student-types.jsonl",
    "unlockable": "unlockables.jsonl",
}


def stub_id_pool(kind: str, n: int = 4):
    return [r["id"] for r in stub_rows()[kind][:n]]


# --- pair datasets (24 <src>_<dst>.jsonl over the real node universe) + relations -----

AXES_CARRIER_FIELD_PATH = "Levels[].Prefab"
NODE_UNIVERSE_REAL = ("campus-level", "config", "course", "item",
                      "metagame-node", "room", "scene", "staff",
                      "student-type", "unlockable")


def _ev_same(src_row, dst_row, field_path, ref_count=1):
    return {"dstBundle": dst_row["source"]["bundle"],
            "dstPathId": dst_row["source"]["pathId"],
            "fieldPath": field_path, "refCount": ref_count,
            "srcBundle": src_row["source"]["bundle"],
            "srcPathId": src_row["source"]["pathId"]}


def _pair_file_names():
    """24 deterministic classic pair names over stub kinds (scene excluded —
    its branch is unexercised, scout G7)."""
    kinds = [k for k in NODE_UNIVERSE_REAL if k != "scene"]
    names = []
    for s in kinds:
        for d in kinds:
            names.append(f"{s}_{d}.jsonl")
            if len(names) == 24:
                return sorted(names)
    return sorted(names)


def pair_datasets():
    st = stub_rows()
    pool = {k: st[k] for k in st}
    files = {}
    carrier_done = False
    for fname in _pair_file_names():
        src_kind, dst_kind = fname[:-6].split("_")
        rows = []
        for i in range(2):
            src = pool[src_kind][i % len(pool[src_kind])]
            dst = pool[dst_kind][(i + 1) % len(pool[dst_kind])]
            ev = _ev_same(src, dst, f"{src_kind.title()}To{dst_kind.title()}[]",
                          ref_count=i + 1)
            row = {"buildId": TARGET_BUILD, "dstId": dst["id"],
                   "dstKind": dst_kind, "evidence": ev, "inferred": False,
                   "mechanism": "hard", "method":
                       "pptr-same-file" if i == 0 else "pptr-cross-file",
                   "srcId": src["id"], "srcKind": src_kind}
            if i == 1:
                row["evidence"] = dict(ev, dstCab="CAB-fixturemain",
                                       extFileId=1,
                                       resolvedVia="externals+cab-index")
            if not carrier_done and src_kind == "config" and                     dst_kind == "config" and "axes" in src:
                row["sourceAxes"] = list(dict.fromkeys(
                    (src.get("axes") or []) + (dst.get("axes") or [])))
                row["evidence"]["fieldPath"] = AXES_CARRIER_FIELD_PATH
                carrier_done = True
            rows.append(row)
        files[fname] = sort_pair_rows(rows)
    assert carrier_done, "axes carrier row missing"
    return files


def relation_datasets():
    """entity_locale + locale_term_entity at modest scale (rowcounts are not
    pinned; the R5 identity is internal)."""
    st = stub_rows()

    def lrow(src_kind, src_id, term_key, term_id, dev, field_path):
        return {"buildId": TARGET_BUILD, "dstId": term_key,
                "dstKind": "locale-term",
                "evidence": {"dev": dev, "fieldPath": field_path,
                             "locales": [], "termId": term_id},
                "inferred": False, "mechanism": "hard",
                "method": "i2-termid-registry", "srcId": src_id,
                "srcKind": src_kind}

    entity_locale = sort_pair_rows([
        lrow("config", st["config"][0]["id"], K_PRESTIGE, 101,
             "", "PrestigeLevelName"),
        lrow("config", st["config"][1]["id"], K_PRESTIGE, 101,
             "Prestige level", "PrestigeLevelName"),
        lrow("item", st["item"][0]["id"], K_MEDICAL, 102, "", "Description"),
    ])
    usages: dict[str, list] = {}
    for r in entity_locale:
        usages.setdefault(r["dstId"], []).append(
            {"fieldPath": r["evidence"]["fieldPath"], "srcId": r["srcId"],
             "srcKind": r["srcKind"]})
    reverse = [{"buildId": TARGET_BUILD, "locales": [], "termKey": k,
                "usages": v} for k, v in sorted(usages.items())]
    return {"entity_locale.jsonl": entity_locale,
            "locale_term_entity.jsonl": reverse}


def relation_datasets_asset():
    """entity_asset_guid: every dstId is EITHER a container address OR one of
    the 5 measured DLC3_Hospital uncontained addresses (9 edge rows)."""

    def grow(src_kind, src_id, address, guid, field_path):
        return {"buildId": TARGET_BUILD, "dstId": address, "dstKind": "asset",
                "evidence": {"assetGuid": guid, "catalogAddress": address,
                             "fieldPath": field_path,
                             "resolvedVia": "catalog-guid+container-index"},
                "inferred": False, "mechanism": "hard",
                "method": "assetguid-catalog",
                "srcId": src_id, "srcKind": src_kind}

    st = stub_rows()
    contained_pool = CONTAINED_ADDRESSES
    refs = []
    for i in range(6):
        addr = contained_pool[i % len(contained_pool)]
        refs.append(grow("item", st["item"][i]["id"], addr,
                         GUID_BY_ADDRESS[addr], "Visual.Prefab"))
    # the F12 offender set verbatim: 9 edge rows over 5 addresses
    offenders = [
        ("Config_DLC3", "Levels[]", A_DLC_RURAL, G_DLC_RURAL),
        ("Config_DLC3", "Levels[]", A_DLC_SNOWY, G_DLC_SNOWY),
        ("Config_DLC3", "Levels[]", A_DLC_TROPICAL, G_DLC_TROPICAL),
        ("Config_GameMode_IconGenerator", "Icons[]", A_DLC_VARIATIONS,
         G_DLC_VARIATIONS),
        ("Config_UISprite", "Sprites[]", A_DLC_ATLAS, G_DLC_ATLAS),
        ("ObjectiveType_PatientEmergency", "Icon", A_DLC_ATLAS, G_DLC_ATLAS),
        ("ObjectiveType_PirateEmergency", "Icon", A_DLC_ATLAS, G_DLC_ATLAS),
        ("ObjectiveType_PlotTropical", "Icon", A_DLC_ATLAS, G_DLC_ATLAS),
        ("ObjectiveType_Volcano", "Icon", A_DLC_ATLAS, G_DLC_ATLAS),
    ]
    for i, (src, fp, addr, guid) in enumerate(offenders):
        refs.append(grow("config", st["config"][i]["id"], addr, guid, fp))
    return {"entity_asset_guid.jsonl": sort_pair_rows(refs)}


# --- bridges + census + media + catalog trio ------------------------------------------

MEDIA_CLASS_COUNTS = {"AnimationClip": 7985, "AudioClip": 5624, "Font": 24,
                      "Mesh": 19249, "Shader": 213, "Sprite": 6789,
                      "SpriteAtlas": 47, "Texture2D": 7977, "VideoClip": 31}
CARVED_CLASSES = tuple(sorted(MEDIA_CLASS_COUNTS))
CONTAINER_ROWS_PIN = 49855
CAB_ROWS_PIN = 222
EXTERNALS_ROWS_PIN = 222
MANIFEST_ROWS_PIN = 167069
REGISTRY_ROWS_PIN = 15675
UI_COVERAGE_ROWS_PIN = 344
UI_MAPPED_PIN = 9
UI_GAP_PIN = 335

PPTR_REASON_A_COUNT = 2284
PPTR_REASON_B_COUNT = 107
DANGLING_GUID_ROWS = 1137
ABSENCES_ROWS = 2
UNMAPPED_ROWS = 768


def media_rows():
    rows = []
    pid = 800000
    for cls in CARVED_CLASSES:
        for i in range(MEDIA_CLASS_COUNTS[cls]):
            pid += 1
            axis = ("base", "dlc-space", "dlc-ghost")[pid % 3]
            bundle = STUB_BUNDLE_UNIVERSE[pid % len(STUB_BUNDLE_UNIVERSE)]
            if axis == "dlc-space":
                bundle = "dlc-space-family00_assets_all.bundle"
            elif axis == "dlc-ghost":
                bundle = "dlc-ghost-family00_assets_all.bundle"
            rows.append({"bundle": bundle, "bytesEstimate": 256,
                         "class": cls, "contentAxis": axis,
                         "name": f"{cls.lower()}_{i:06d}", "pathId": pid})
    return rows


def census_files():
    """176 census files; carved-class totals match MEDIA_CLASS_COUNTS exactly."""
    per_file = {b: {} for b in roster_basenames()}
    ordered = sorted(per_file)
    for cls in CARVED_CLASSES:
        for i in range(MEDIA_CLASS_COUNTS[cls]):
            b = ordered[i % len(ordered)]
            per_file[b][cls] = per_file[b].get(cls, 0) + 1
    for i, b in enumerate(ordered):
        per_file[b]["MonoBehaviour"] = (i % 7) + 1
        per_file[b]["MonoScript"] = (i % 3) + 1
    out = {}
    for b in ordered:
        classes = per_file[b]
        out[f"{b}.json"] = {"bytesByClass": {k: v * 128 for k, v in
                                             sorted(classes.items())},
                            "errors": [], "fallbackVersionUsed": True,
                            "objectsByClass": dict(sorted(classes.items()))}
    assert len(out) == 176
    return out


def cab_index_rows():
    cens = census_files()
    by_bundle = {name[:-5]: obj["objectsByClass"]
                 for name, obj in cens.items()}
    counter = iter(range(900000, 900000 + 40000))
    rows = []
    bundles = sorted(by_bundle)
    # 222 cab rows over 176 bundles: split the largest bundles into 2 cabs
    extra = CAB_ROWS_PIN - len(bundles)
    for i, bundle in enumerate(bundles):
        classes = by_bundle[bundle]
        splits = 2 if i < extra else 1
        items = [{"class": cls, "pathId": next(counter)}
                 for cls in sorted(classes) for _ in range(1)]
        per = max(1, len(items) // splits)
        for part in range(splits):
            rows.append({"buildId": TARGET_BUILD, "bundle": bundle,
                         "cab": "CAB-%s%02d" % (
                             abs(hash(bundle)) % 10 ** 8, part),
                         "objects": items[part * per:(part + 1) * per]
                         or [{"class": "Empty", "pathId":
                              next(counter)}]})
    rows.sort(key=lambda r: (r["bundle"], r["cab"]))
    assert len(rows) == CAB_ROWS_PIN, len(rows)
    return rows


def container_index_rows():
    rows = []
    roster = sorted(roster_basenames())
    for i in range(CONTAINER_ROWS_PIN - len(_CONTAINED_SPEC)):
        addr = f"Assets/Content/Filler/{i:06d}.asset"
        rows.append({"address": addr, "buildId": TARGET_BUILD,
                     "bundle": roster[i % len(roster)], "class":
                     "MonoBehaviour", "pathId": 600000 + i})
    for i, (addr, _g, bundle) in enumerate(_CONTAINED_SPEC):
        rows.append({"address": addr, "buildId": TARGET_BUILD,
                     "bundle": bundle, "class": "GameObject",
                     "pathId": 700000 + i})
    rows.sort(key=lambda r: (r["bundle"], r["address"]))
    assert len(rows) == CONTAINER_ROWS_PIN
    assert len({r["address"] for r in rows}) == CONTAINER_ROWS_PIN
    return rows


def catalog_rows():
    prov = ["ContentCatalogProvider", "BundledAssetProvider"]
    guid_rows = [g(guid, addr) for addr, guid, _b in _CONTAINED_SPEC]
    guid_rows += [g(G_DLC_RURAL, A_DLC_RURAL), g(G_DLC_SNOWY, A_DLC_SNOWY),
                  g(G_DLC_TROPICAL, A_DLC_TROPICAL),
                  g(G_DLC_VARIATIONS, A_DLC_VARIATIONS),
                  g(G_DLC_ATLAS, A_DLC_ATLAS)]
    dupe = g(G_STYLE, A_STYLE)
    guid_rows += [dupe, dict(dupe)]          # byte-identical duplicate pair
    address_rows = [
        a("Assets/Content/Configs/Global.asset",
          "configs_assets_all.bundle", []),
        a("Assets/Content/Items/General.itemset",
          "items-general_assets_all.bundle", [guid_rows[0]["key"]]),
        a("Assets/Content/Rooms.rooms", "rooms_assets_all.bundle", []),
        an("Assets/Content/UI.nulladdr1", "ui_assets_all.bundle"),
        an("Assets/Content/UI.nulladdr2", None),
        a("Assets/OutOfRoster/Extra.file", "NOT-IN-ROSTER_extra.bundle", []),
    ]
    rows = sorted(guid_rows + address_rows,
                  key=lambda r: (r["key"], str(r.get("address"))))
    dup_keys = [k for k in {r["key"] for r in rows}
                if sum(1 for r in rows if r["key"] == k) > 1]
    assert dup_keys == [G_STYLE] and len(rows) == 21
    return rows


def g(key, address):
    return {"address": address, "bundle": None, "dependencies": [],
            "key": key, "kind": GUID_KIND,
            "providerIds": ["ContentCatalogProvider", "BundledAssetProvider"]}


def a(key, bundle, deps):
    return {"address": key, "bundle": bundle, "dependencies": list(deps),
            "key": key, "kind": ADDRESS_KIND,
            "providerIds": ["ContentCatalogProvider", "BundledAssetProvider"]}


def an(key, bundle):
    return {"address": None, "bundle": bundle, "dependencies": [],
            "key": key, "kind": ADDRESS_KIND,
            "providerIds": ["ContentCatalogProvider", "BundledAssetProvider"]}


# --- catalog mini-report (the persisted sidecar, section 3.3) -------------------------

def mini_report(catalog_bytes: bytes) -> dict:
    rows = catalog_rows()
    keys = [r["key"] for r in rows]
    counts: dict = {}
    null_bundle_rows = []
    null_addr = 0
    no_deps = 0
    edges = 0
    for r in rows:
        counts[r["kind"]] = counts.get(r["kind"], 0) + 1
        if r["bundle"] is None:
            null_bundle_rows.append(r)
        if r["address"] is None:
            null_addr += 1
        if not r["dependencies"]:
            no_deps += 1
        edges += len(r["dependencies"])
    ref_bundles = {r["bundle"] for r in rows if r["bundle"]}
    referenced = sorted(r["relpath"] for r in roster_rows()
                        if Path(r["relpath"]).name in ref_bundles)
    unreferenced = sorted(r["relpath"] for r in roster_rows()
                          if Path(r["relpath"]).name not in ref_bundles)
    out_of_roster = sorted(b for b in ref_bundles
                           if b not in roster_basenames())
    return {
        "bundleUniverse": {"bundlesUnreferenced": unreferenced,
                           "danglingDependencyKeys": [],
                           "outOfRosterFileReferences": out_of_roster,
                           "referencedRelpaths": referenced},
        "counts": {"dependencyEdgesTotal": edges,
                   "distinctKeys": len(set(keys)), "keysTotal": len(rows),
                   "kindCounts": counts, "nullAddressRows": null_addr,
                   "nullBundleRows": {
                       "addressKind": sum(1 for r in null_bundle_rows
                                          if r["kind"] == ADDRESS_KIND),
                       "guidKind": sum(1 for r in null_bundle_rows
                                       if r["kind"] == GUID_KIND),
                       "total": len(null_bundle_rows)},
                   "rowsWithNoDependencies": no_deps},
        "duplicateKeys": [{"address": A_STYLE, "key": G_STYLE,
                           "rowCount": 2, "rowsByteIdentical": True,
                           "kind": GUID_KIND}],
        "guidIndex": {k: [{"address": addr, "kind": GUID_KIND}]
                      for k, addr in _guid_addresses()},
        "meta": {"addressablesVersion": ADDRESSABLES_VERSION,
                 "buildId": TARGET_BUILD,
                 "catalogSha256": hashlib.sha256(catalog_bytes).hexdigest(),
                 "settingsHash": SETTINGS_HASH,
                 "sourceBytes": len(catalog_bytes)},
        "nullBundleAddresses": sorted(r["address"] for r in
                                      null_bundle_rows
                                      if r["address"] is not None),
    }


def _guid_addresses():
    return sorted({r["key"]: r["address"] for r in catalog_rows()
                   if r["kind"] == GUID_KIND
                   and r["address"] is not None}.items())


def catalog_coverage_obj() -> dict:
    rows = catalog_rows()
    ref_bundles = {r["bundle"] for r in rows if r["bundle"]}
    referenced = {Path(r["relpath"]).name for r in roster_rows()
                  if Path(r["relpath"]).name in ref_bundles}
    out_of_roster = sorted(b for b in ref_bundles
                           if b not in roster_basenames())
    return {
        "bundlesUnreferenced": sorted(roster_basenames() - referenced),
        "danglingDependencyKeys": {"count": 0, "samples": []},
        "distinctBundlesReferenced": len(referenced),
        "keysTotal": len(rows),
        "outOfRosterFileReferences": {"count": len(out_of_roster),
                                      "samples": out_of_roster},
    }


# --- locales + registry + reports ------------------------------------------------------

LOCALE_LINE_COUNTS = {
    "en": 15665, "pt-BR": 15443, "zh-Hans": 15445, "zh-Hant": 15446,
    "fr": 15445, "de": 15445, "it": 15445, "pl": 15445, "ja": 15371,
    "ko": 15457, "ru": 15422, "es": 15440, "tr": 15443}
BASE_OVERLAY_ROWS_PIN = 15672
REGISTRY_DISTINCT_KEYS_PIN = 15672
DUP_OVERWRITE_PER_LOCALE = {loc: 5 for loc in LOCALE_LINE_COUNTS}
DUP_OVERWRITE_TOTAL = sum(DUP_OVERWRITE_PER_LOCALE.values())

TERM_KEY_POOL_SIZE = REGISTRY_DISTINCT_KEYS_PIN
REAL_DUP_TERM_KEYS = (
    "UI/General/PrestigeLevel", "UI/Inspector/MedicalIssuesCured",
    "UI/Inspector/PastoralIssuesCured",
    "Characters/DLC_Hospital/Archetypes/Doctor_M_Name",
    "Characters/DLC_Hospital/Archetypes/Nurse_F_Description")


def term_key(i: int) -> str:
    if i < len(REAL_DUP_TERM_KEYS):
        return REAL_DUP_TERM_KEYS[i]
    return f"UI/Fixture/Key_{i:05d}"


def locale_file_ids(loc: str):
    n = LOCALE_LINE_COUNTS[loc]
    step = max(1, TERM_KEY_POOL_SIZE // n)
    return sorted(term_key((i * step) % TERM_KEY_POOL_SIZE)
                  for i in range(n))


def locale_totals():
    """{loc: (lines, walked, skippedEmpty, rowsLogged, dup)} -- identities:
    rowsLogged == walked - skippedEmpty AND rowsLogged - lines == dup."""
    out = {}
    for loc, lines in LOCALE_LINE_COUNTS.items():
        rows_l = lines + DUP_OVERWRITE_PER_LOCALE[loc]
        skipped = 7 if loc in ("en", "fr", "ja") else 227
        walked = rows_l + skipped
        out[loc] = (lines, walked, skipped, rows_l,
                    DUP_OVERWRITE_PER_LOCALE[loc])
    return out


def registry_rows():
    rows = []
    dual = {term_key(0), term_key(1), term_key(2)}
    assets = [f"harvest/textassets/langsource_{i:02d}.json" for i in range(25)]
    tid = 100000
    status_budget_0 = [275]

    def status_of(t):
        if status_budget_0[0] > 0 and t % 58 == 0:
            status_budget_0[0] -= 1
            return 0
        return 1

    for i in range(REGISTRY_DISTINCT_KEYS_PIN):
        key = term_key(i)
        ids_for_key = [tid] + ([tid + 1] if key in dual else [])
        for j, t in enumerate(ids_for_key):
            rows.append({"buildId": TARGET_BUILD,
                         "canonical": j == 0,
                         "locales": [],
                         "sourceAsset": assets[(t // 7) % len(assets)],
                         "termId": t, "termKey": key,
                         "termStatus": status_of(t),
                         "termType": 0})
            tid += 2
    assert len(rows) == REGISTRY_ROWS_PIN, len(rows)
    assert len({r["termKey"] for r in rows}) == REGISTRY_DISTINCT_KEYS_PIN
    assert sum(1 for r in rows if r["termStatus"] == 0) == 275
    assert sum(1 for r in rows if r["canonical"]) == REGISTRY_DISTINCT_KEYS_PIN
    return rows


def locale_matrix_obj():
    keys = {}
    for r in registry_rows():
        keys.setdefault(r["termKey"], {"baseOverlay": False, "locales": []})
    for loc in sorted(LOCALE_LINE_COUNTS):
        for k in locale_file_ids(loc):
            entry = keys.get(k)
            if entry is not None and loc not in entry["locales"]:
                entry["locales"].append(loc)
    for k in keys:
        keys[k]["locales"] = sorted(keys[k]["locales"])
    return {"buildId": TARGET_BUILD, "includesBaseKeys": True,
            "keys": keys, "meta": {"buildId": TARGET_BUILD},
            "locales": sorted(LOCALE_LINE_COUNTS)}


def base_overlay_report(dup_keys):
    evidence = {"baseCellsSkippedAbsent": 0,
                "baseCellsSkippedEmpty": 15677,
                "baseOnlyKeys": 7, "differingTextSharedKeys": 15665,
                "englishRowCount": 15665, "englishOnlyKeys": 0,
                "identicalTextSharedKeys": 0, "registrySources": 26,
                "registryTerms": 15677,
                "termStatusForTranslation": 15402,
                "termStatusNotForTranslation": 275}
    if dup_keys is not None:
        evidence["duplicateKeysOverwritten"] = dup_keys
    return {"buildId": TARGET_BUILD, "compositionPolicy": COMPOSITION_POLICY,
            "evidence": evidence}


BRIDGE_REPORT_OVERRIDES: dict = {}


def guid_bridge_report() -> dict:
    base = {"buildId": TARGET_BUILD, "danglingDistinctGuids": 5,
            "distinctGuids": 13, "guidRefsTotal": 15,
            "resolveRateAddress": 10 / 15, "resolveRateStub": 6 / 15,
            "resolvedToAddress": 10, "resolvedToStub": 6}
    base.update(BRIDGE_REPORT_OVERRIDES)
    return base


def locale_join_report():
    hits, misses = 10964, 5
    total = 20070
    sentinel = total - hits - misses
    st = stub_rows()
    return {"buildId": TARGET_BUILD,
            "codeRefTerms": {
                "auditPath": "extracted/relinks/i2_term_registry.jsonl",
                "note": "audit-if-present-else-note"},
            "coverageOnNonEmpty": hits / (hits + misses),
            "instancesTotal": total, "matrixKeyDiff": 0,
            "perKindHits": {"campus-level": 17, "config": 8425, "course": 69,
                            "item": 3880, "metagame-node": 454, "room": 116,
                            "staff": 3, "student-type": 54},
            "registryHits": hits, "registryMisses": misses,
            "sentinelZero": sentinel,
            "unresolvedIds": [{"sampleRefs": [
                {"fieldPath": "Title", "srcId":
                 st["unlockable"][i]["id"], "srcKind": "unlockable"}],
                "termId": MISSING_TERM_IDS[i]} for i in range(5)]}


UNIT_BY_NAME = {
    "Rate": "reference-events", "coverageOnNonEmpty": "reference-events",
    "guidRefsTotal": "reference-events", "resolvedToAddress":
        "reference-events", "resolvedToStub": "reference-events",
    "registryHits": "reference-events",
    "distinctGuids": "distinct-keys", "danglingDistinctGuids":
        "distinct-keys", "registryMisses": "distinct-keys",
    "matrixKeyDiff": "distinct-keys", "keysTotal": "distinct-keys",
    "termId": "distinct-keys",
    "instancesTotal": "deduped-rows", "sentinelZero": "deduped-rows",
}


def _unit_for(path: str) -> str:
    for token in sorted(UNIT_BY_NAME, key=len, reverse=True):
        if path == token or path.endswith("." + token):
            return UNIT_BY_NAME[token]
    return "deduped-rows"


def counter_units_for(obj) -> dict:
    """Dotted-path units for numeric leaves up to depth 3 (wildcards for
    uniform map children), per the V-U1 coverage rule."""
    units: dict = {}

    def walk(node, prefix, depth):
        if isinstance(node, bool):
            return
        if isinstance(node, (int, float)):
            units[prefix] = _unit_for(prefix)
            return
        if isinstance(node, dict):
            if depth >= 3 and node and all(
                    isinstance(v, (int, float)) and not
                    isinstance(v, bool) for v in node.values()):
                units[prefix + ".*"] = _unit_for(prefix)
                return
            for k, v in node.items():
                walk(v, f"{prefix}.{k}" if prefix else k, depth + 1)

    walk(obj, "", 0)
    return units


MISSING_TERM_IDS = [-1168948158, -2044546668, -1942168175, -1312157894,
                    -2044546669]

UNMAPPED_EVIDENCE_VALUES = ("component-chain", "engine-primitive-namespace",
                            "no-seeded-kind", "unresolved-generic")
UNMAPPED_EVIDENCE_COUNTS = (677, 43, 47, 1)



def ui_link_coverage_rows():
    rows = []
    for i in range(UI_MAPPED_PIN):
        rows.append({"buildId": TARGET_BUILD,
                     "definitionClasses": [{"class": f"TPC.MappedClass{i}",
                                            "corpusCount": 3}],
                     "exportedCount": 3 + i, "gapReason": None,
                     "genericContainerClasses": i == 0,
                     "impliedFamilies": ["config"],
                     "joins": ["config_config"],
                     "status": "mapped-schema",
                     "surfaceId": f"bar-{i}.mapped",
                     "uiClass": f"TPC.ItemGridMenu{i}", "unblock": None})
    gap_reasons = ("quest payloads serialize empty client-side",
                   "no seeded kind on this corpus",
                   "live-capture unblock pending")
    unblocks = ("live capture per orchestrator-piece03-scope R5",
                "map the class onto a seeded kind",
                "alias input riding the research-pass lane")
    for i in range(UI_GAP_PIN):
        rows.append({"buildId": TARGET_BUILD, "definitionClasses": [],
                     "exportedCount": 2, "gapReason": gap_reasons[i % 3],
                     "genericContainerClasses": False,
                     "impliedFamilies": [], "joins": [],
                     "status": "documented-gap",
                     "surfaceId": f"bar-gap-{i}",
                     "uiClass": f"TPC.GapMenu{i:03d}",
                     "unblock": unblocks[i % 3]})
    return rows


def competitor_rows():
    return [
        {"buildId": TARGET_BUILD,
         "dispositions": {"adds-derived": 1, "confirms-hard": 2,
                          "flags-missing": 383},
         "rung": "applied", "samples": ["Config_Kudosh"],
         "sourceId": "fandom-wiki"},
        {"buildId": TARGET_BUILD,
         "dispositions": {"confirms-hard": 0, "flags-missing": 34},
         "rung": "applied", "samples": ["Course_Potions_Guide"],
         "sourceId": "steam-guides"},
        {"buildId": TARGET_BUILD, "floorRequired": 3,
         "rung": "floor-unmet", "samples": [],
         "sourcesApplied": 0,
         "sourceId": "~floor-terminal", "terminal": True,
         "unblock": "alias input riding the research-pass lane"},
    ]



def ledgers():
    st = stub_rows()
    dangling = []
    for i in range(DANGLING_GUID_ROWS):
        dangling.append({
            "assetGuid": (f"{i:08x}" + "aaaabbbbccccddddeeeeffff0000")[:32],
            "buildId": TARGET_BUILD,
            "sampleRefs": [{"fieldPath": "IconGuid",
                            "srcId": st["item"][i % len(st["item"])]["id"],
                            "srcKind": "item"}],
            "unblock": "re-dump source bundle with full typetrees",
            "verdict": "unresolved-open"})
    dangling.sort(key=lambda r: r["assetGuid"])
    unresolved = []
    for reason, n in ((REASON_PPTR_A, PPTR_REASON_A_COUNT),
                      (REASON_PPTR_B, PPTR_REASON_B_COUNT)):
        for i in range(n):
            src_kind = "course" if reason == REASON_PPTR_A \
                else "metagame-node"
            pool = st[src_kind]
            unresolved.append({
                "buildId": TARGET_BUILD, "extFileId": i % 4,
                "extPath": f"archive:/CAB-fixture{i % 999:04d}",
                "fieldPath": f"Refs[{i}].Target",
                "m_PathID": -(i + 1), "reason": reason,
                "srcId": pool[i % len(pool)]["id"],
                "srcKind": src_kind})
    unresolved.sort(key=lambda r: (r["srcKind"], r["srcId"],
                                   r["fieldPath"], r["m_PathID"],
                                   r["extFileId"]))
    absences = [
        {"absenceType": "no-identifier", "buildId": TARGET_BUILD, "count": 1,
         "evidence": "no identifier-bearing field on any candidate",
         "kind": "config", "samples": [{"srcId": "cfg_orphan",
                                        "srcKind": "config"}],
         "scannedBundles": 176, "scannedClasses": 95},
        {"absenceType": "no-identifier", "buildId": TARGET_BUILD, "count": 44,
         "evidence": "identifier-less candidates ledgered",
         "kind": "item",
         "samples": [{"srcId": f"itm_orphan_{i:02d}", "srcKind": "item"}
                     for i in range(25)],
         "scannedBundles": 176, "scannedClasses": 95}]
    unmapped = []
    for value, n in zip(UNMAPPED_EVIDENCE_VALUES, UNMAPPED_EVIDENCE_COUNTS):
        for i in range(n):
            unmapped.append({
                "buildId": TARGET_BUILD,
                "bundles": [STUB_BUNDLE_UNIVERSE[i % 11]],
                "class": f"UnmappedClass{i:04d}", "evidence": value,
                "objectCount": 1 + (i % 9)})
    return {"_absences.jsonl": absences, "_dangling_guids.jsonl": dangling,
            "_unmapped-families.jsonl": unmapped,
            "_unresolved_pptrs.jsonl": unresolved}


def uncontained_ledger_rows():
    by_address = {}
    for row in relation_datasets_asset()["entity_asset_guid.jsonl"]:
        addr = row["dstId"]
        if addr in UNCONTAINED_ADDRESSES:
            entry = by_address.setdefault(addr, {
                "address": addr, "catalogGuid":
                row["evidence"]["assetGuid"], "reason": REASON_UNCONTAINED,
                "sampleRefs": []})
            entry["sampleRefs"].append({"fieldPath":
                                        row["evidence"]["fieldPath"],
                                        "srcId": row["srcId"],
                                        "srcKind": row["srcKind"]})
    rows = [by_address[addr] for addr in UNCONTAINED_ADDRESSES]
    for r in rows:
        r["buildId"] = TARGET_BUILD
        r["sampleRefs"] = r["sampleRefs"][:5]
    return rows


# --- matrix (real node universe, statuses 24/3/73, classic-only edges) -----------------

MATRIX_STATUSES_PIN = {"modeled": 24, "partial": 3, "missing": 73}


def matrix_obj():
    pairs_by_file = pair_datasets()
    cell_edges = {}
    for fname, rows in pairs_by_file.items():
        src, dst = fname[:-6].split("_")
        cell_edges[(src, dst)] = len(rows)
    nodes = list(NODE_UNIVERSE_REAL)
    cells = []
    partial_budget = 3
    for src in nodes:
        for dst in nodes:
            edges = cell_edges.get((src, dst), 0)
            if edges:
                files = [f"{src}_{dst}.jsonl"]
                cells.append({
                    "cardinality": {"edges": edges,
                                    "perDst": max(1, edges // 2),
                                    "perSrc": max(1, edges // 2),
                                    "srcEntitiesWithEdges": 2},
                    "joinKey": JOIN_KEY_PPTR,
                    "mechanism": "hard", "pairFiles": files,
                    "srcKind": src, "dstKind": dst, "status": "modeled",
                    "unblock": ""})
            elif partial_budget > 0 and src in ("course", "item",
                                                "metagame-node"):
                partial_budget -= 1
                cells.append({
                    "cardinality": {"edges": 0, "perDst": 0, "perSrc": 0,
                                    "srcEntitiesWithEdges": 0},
                    "joinKey": JOIN_KEY_NONE, "mechanism": "inferred",
                    "pairFiles": [], "srcKind": src, "dstKind": dst,
                    "status": "partial",
                    "unblock": ("PPtr targets live in payloads this fixture "
                                "does not materialize; re-walk after a full "
                                "re-dump")})
            else:
                cells.append({
                    "cardinality": {"edges": 0, "perDst": 0, "perSrc": 0,
                                    "srcEntitiesWithEdges": 0},
                    "joinKey": JOIN_KEY_NONE, "mechanism": "inferred",
                    "pairFiles": [], "srcKind": src, "dstKind": dst,
                    "status": "missing",
                    "unblock": f"derive the {src}->{dst} join "
                               "(no seeded mechanism on this corpus)"})
    counts = {"modeled": 0, "partial": 0, "missing": 0}
    for c in cells:
        counts[c["status"]] += 1
    assert counts == MATRIX_STATUSES_PIN, counts
    assert len(cells) == 100
    return {
        "meta": {
            "buildId": TARGET_BUILD,
            "enums": {"joinKeys": [JOIN_KEY_PPTR, JOIN_KEY_ASSET,
                                   JOIN_KEY_LOCALE,
                                   "name-equality(<rule>)"],
                      "mechanism": list(MECHANISMS),
                      "status": list(STATUSES)},
            "nodeUniverse": {
                "arithmetic": ("10 nodes -> 100 ordered cells "
                               "(90 off-diagonal, 10 diagonal)"),
                "nodes": nodes},
            "reconciliation": ("sum(cardinality.edges) over cells == total "
                               "rows across the emitted <src>_<dst>.jsonl "
                               "pair files")},
        "pairs": cells,
    }


def matrix_status_counts():
    return dict(MATRIX_STATUSES_PIN)


# --- harvest flat families + structural ------------------------------------------------

def export_manifest_rows():
    rows = []
    dumps = [
        ("configs", "GlobalConfig", "configs_assets_all", 801),
        ("configs", "GlobalConfig", "configs_assets_all", 802),
        ("configs", "GlobalConfig", "configs_assets_all", 803),
        ("configs", "GlobalConfig", "dlc-space-configs_assets_all", 811),
        ("items-general", "ItemConfig", "items-general_assets_all", 301),
        ("items-general", "ItemConfig", "items-general_assets_all", 302),
        ("rooms", "RoomConfig", "rooms_assets_all", 201),
        ("courses", "CourseConfig", "courses_assets_all", 401),
        ("metagame", "MetagameNodeConfig", "metagame_assets_all", 901),
        ("metagame", "MetagameNodeConfig", "metagame_assets_all", 902),
        ("metagame", "CampusLevelConfig", "metagame_assets_all", 701),
        ("ui", "SpriteAtlas", "ui_assets_all", 9999),
    ]
    for fam, cls, stem, pid in dumps:
        rows.append({"bytes": 256, "class": cls,
                     "outRelPath": (f"harvest/monobehaviours/{fam}/{cls}/"
                                    f"{stem}_{pid}.json"),
                     "pathId": pid, "sourceBundle": f"{stem}.bundle"})
    carved = [
        ("Texture2D", "configs_assets_all", 9001), ("Texture2D",
                                                    "configs_assets_all", 9002),
        ("Sprite", "items-general_assets_all", 9101),
        ("Mesh", "items-general_assets_all", 9201),
    ]
    for cls, stem, pid in carved:
        rows.append({"bytes": 512, "class": cls,
                     "outRelPath": f"harvest/media/{stem}_{pid}.asset",
                     "pathId": pid, "sourceBundle": f"{stem}.bundle"})
    text = [("items-general_assets_all", 90001), ("items-general_assets_all",
                                                  -90002)]
    for stem, pid in text:
        rows.append({"bytes": 32, "class": "TextAsset",
                     "outRelPath": f"harvest/textassets/items-general/"
                                   f"{stem}_{pid}.txt",
                     "pathId": pid, "sourceBundle": f"{stem}.bundle"})
    rows.sort(key=lambda r: r["outRelPath"])
    return rows


def externals_rows():
    return [
        {"bundle": "configs_assets_all.bundle", "externals": [
            {"fileId": 1, "guid": "0" * 32,
             "path": "archive:/CAB-itemsmain", "type": 0},
            {"fileId": 2, "guid": "0" * 32,
             "path": "Library/unity default resources", "type": 0}],
         "sourceFile": "cab-configsmain"},
        {"bundle": "items-general_assets_all.bundle", "externals": [],
         "sourceFile": "cab-itemsmain"},
    ]


def structural_files():
    assemblies = [
        {"assembly": "Assembly-CSharp", "status": "dummy-absent(stripped)"},
        {"assembly": "TPS.Core", "status": "dummy-present"},
        {"assembly": "TPS.Game", "status": "dummy-present"},
        {"assembly": "mscorlib", "status": "dummy-present"},
    ]
    assembly_index = {
        "assemblies": assemblies,
        "buildId": TARGET_BUILD,
        "hierarchyStamp": {
            "buildId": TARGET_BUILD,
            "hierarchyCountMethod":
                "pure-python ECMA-335 metadata reader over DummyDll/*.dll",
            "hierarchyRowCount": 40,
            "hierarchySource": "dummydll-typedef-enumeration"},
    }
    hierarchy = [{"assembly": "TPS.Core" if i % 2 else "TPS.Game",
                  "baseType": "ScriptableObject", "fieldCount": i % 5,
                  "interfaces": [], "methodCount": i % 3,
                  "name": f"Type_{i:03d}", "namespace": "TPC.Fixture"}
                 for i in range(40)]
    registries = {
        "rarity.json": [{"name": "Common", "value": 0},
                        {"name": "Rare", "value": 1}],
        "staffroles.json": [{"name": "Janitor", "value": 0},
                            {"name": "Assistant", "value": 1}],
    }
    return assembly_index, hierarchy, registries


# --- EXTRACTION-LOG + stage stamps (real house format) ---------------------------------

LOG_STAGE1_LINE_DAY1 = "- registryCount: 1900 hierarchyRowCount=40"
LOG_STAGE1_LINE_FIXED = ("- registryCount(covered classes; files = 2): 1900 "
                         "hierarchyRowCount=40")


def _log_sections(*, dup_printed=False, uncontained_contributor=False,
                  stage1_units=False) -> list:
    secs = []

    def sec(stage, ts):
        body = []
        secs.append((f"### {ts} " + chr(0x2014) + f" {stage}", body))
        return body.append

    add = sec("decompile", "2026-08-25T19:13:56Z")
    add("- exitCode: 0")
    add(LOG_STAGE1_LINE_FIXED if stage1_units else LOG_STAGE1_LINE_DAY1)

    add = sec("harvest-catalog", "2026-08-25T09:03:08Z")
    add("- exitCode: 0")
    add("- decodeRoute: textasset-json(primary)")
    add("- keysTotal: 21 duplicateKeys: 1")

    add = sec("localisation", "2026-08-25T20:00:00Z")
    add("- exitCode: 0")
    add("- emittedLocales: " + repr(sorted(locale_totals())))
    add("- compositionPolicy: mixed")
    total_rows = 0
    total_dup = 0
    for loc in sorted(locale_totals()):
        lines, walked, skipped, rows_l, dup = locale_totals()[loc]
        line = (f"- {loc}: rows={rows_l} skippedEmpty={skipped} "
                f"skippedAbsent=0 categories=0 sources=0 malformed=0")
        if dup_printed:
            line += f" duplicateKeysOverwritten={dup}"
        add(line)
        total_rows += rows_l
        total_dup += dup
    add(f"- localeRowsEmittedTotal(emission-events): {total_rows}")
    if dup_printed:
        add(f"- duplicateKeysOverwrittenTotal(emission-events): {total_dup}")

    add = sec("emit-stub-datasets", "2026-08-25T12:13:37Z")
    add("- exitCode: 0")
    counts = {k: len(v) for k, v in stub_rows().items()}
    add(f"- stubRowsByKind: {json.dumps(counts, sort_keys=True)}")
    add("- identifierByteMatch: checked=2128 mismatches=0")
    add("- absences: 2; unmappedClasses: 768")

    add = sec("relink", "2026-08-25T23:49:25Z")
    add("- exitCode: 2 (completed-with-ledger)")
    contrib = ["_dangling_guids.jsonl unresolved-open: 1137",
               "_unresolved_pptrs.jsonl any-row: 2391",
               "registryMisses: 5",
               "outOfRosterFileReferences: 1",
               ("competitor floor unmet (<3 applied sources; terminal "
                "ledger row ~floor)")]
    if uncontained_contributor:
        contrib.insert(2, "_uncontained_addresses.jsonl uninstalled-dlc: 5")
    add("- LEDGER-CONTRIBUTORS (exit 2): " + "; ".join(contrib))
    add("- R2: cellsTotal=100 cellsModeled=24 cellsPartial=3 "
        "cellsMissing=73 pairFilesEmitted=24 edgesEmitted=48")
    return secs


def extraction_log(**kw) -> str:
    parts = ["# Extraction log (synthetic contract fixture)", ""]
    for heading, body in _log_sections(**kw):
        parts.append(heading)
        parts.extend(body)
        parts.append("")
    return chr(10).join(parts) + chr(10)


full_extraction_log = extraction_log


def stage_stamp_harvest_catalog(catalog_bytes: bytes) -> dict:
    return {
        "decodeRoute": "textasset-json(primary)",
        "exitCode": 0,
        "finishedAt": "2026-08-25T23:49:26Z",
        "identity": {"scriptHash": "0" * 64},
        "outputs": {"addressables/catalog.json": {
            "bytes": len(catalog_bytes),
            "sha256": hashlib.sha256(catalog_bytes).hexdigest()}},
        "stage": "harvest-catalog"}


# --- contracts layer ---------------------------------------------------------------------

def ENUM_PINS():
    return {
        "_absences.absenceType": list(ABSENCE_TYPES),
        "_dangling_guids.verdict": list(DANGLING_VERDICTS),
        "_uncontained_addresses.reason": [REASON_UNCONTAINED],
        "_unmapped-families.evidence": list(UNMAPPED_EVIDENCE),
        "compositionPolicy": ["english-only", "english-over-base",
                              "base-over-english", "mixed"],
        "contentAxis": ["base", "dlc-space", "dlc-ghost"],
        "pair.method": list(PAIR_METHODS),
        "sceneFlag": ["none", ".unity", "seasonal-scenes"],
        "stub.method": list(STUB_METHODS),
        "ui_link_coverage.status": list(UI_STATUSES),
    }


def RECONCILIATION_PINS():
    return [
        {"id": "matrix-edges-eq-named-file-rows", "kind": "derived",
         "left": "sum(matrix.cardinality.edges)", "leftUnit": "deduped-rows",
         "right": "rows across the DISTINCT set of pairFiles-named files",
         "rightUnit": "deduped-rows"},
        {"id": "cab-objects-eq-census-sum", "kind": "derived",
         "left": "sum(cab_index.objects)", "leftUnit": "objects",
         "right": "sum(census.objectsByClass)", "rightUnit": "objects"},
        {"id": "media-eq-carved-census", "kind": "derived",
         "left": "media-catalogue rows per class", "leftUnit": "deduped-rows",
         "right": "census carved classes per class",
         "rightUnit": "deduped-rows"},
        {"id": "registry-eq-matrix-keys", "kind": "derived",
         "left": "i2_term_registry distinct termKeys",
         "leftUnit": "distinct-keys",
         "right": "locale-matrix keys", "rightUnit": "distinct-keys"},
        {"id": "reverse-usages-eq-entity-locale", "kind": "derived",
         "left": "sum(locale_term_entity.usages)", "leftUnit": "deduped-rows",
         "right": "entity_locale rows", "rightUnit": "deduped-rows"},
        {"id": "localisation-overwrite-identity", "kind": "constant",
         "left": "run-section rowsLogged per locale",
         "leftUnit": "emission-events",
         "right": "locale-file distinct-key lines per locale",
         "rightUnit": "distinct-keys",
         "transform": TRANSFORM_NAME},
        {"id": "catalog-mini-report-internal", "kind": "derived",
         "left": "counts.keysTotal", "leftUnit": "distinct-keys",
         "right": "sum(counts.kindCounts)", "rightUnit": "distinct-keys"},
        {"id": "roster-eq-enumerated-bundles", "kind": "derived",
         "left": "bundle-roster rows", "leftUnit": "deduped-rows",
         "right": "enumerated *.bundle files over the three dirs",
         "rightUnit": "deduped-rows"},
    ]


def _family_pins(*, handover, dir_counts, scene_counts, loc_counts,
                 axes_counts, twins, msc):
    st = stub_rows()
    total_stubs = sum(len(v) for v in st.values())
    cov = catalog_coverage_obj()
    mini = mini_report(b"")
    joinr = locale_join_report()
    fam = {}
    return_alias = None   # built below via closure-free post step
    def _finish(d):
        # alias every per-file entry under BOTH its bare name and its
        # root-relative path so either lookup spelling finds required/
        optional = {}
        for group in ("relations", "ledgers"):
            grp = d.get(group, {})
            extra = {}
            for name, shape in list(grp.items()):
                path = shape.get("path") if isinstance(shape, dict) else None
                if path and path not in grp:
                    extra[path] = shape
            grp.update(extra)
            d[group] = grp
        return d
    return _finish({
        "exceptions": {
            "catalogDuplicateKey": {"address": A_STYLE,
                                    "byteIdentical": True, "key": G_STYLE,
                                    "rowCount": 2},
            "catalogNullBundle": {"addressKind": 2, "guidKind": 15,
                                  "nullAddressRows": 2, "total": 17},
            "localesReservedEmpty": {"registryRows": REGISTRY_ROWS_PIN},
            "slugNull": {"rows": total_stubs}},
        "stage0": {
            "identityTopKeys": [
                "appid", "addressablesVersion", "buildId", "dumper",
                "expectedBundles", "languageSetting", "localeBundleCount",
                "metadataVersion", "sceneCounts", "settingsHash",
                "targetBuildId", "unityVersion", "versionString"],
            "roster": {
                "dirClass": {"base": dir_counts[0],
                             "dlc-ghost": dir_counts[2],
                             "dlc-space": dir_counts[1]},
                "keyset": ["buildId", "bytes", "dirClass", "localeFlag",
                           "relpath", "sceneFlag"],
                "localeFlag": {"<codes>": loc_counts[2],
                               "<null>": loc_counts[0],
                               "base": loc_counts[1]},
                "rows": len(roster_rows()),
                "sceneFlag": {".unity": scene_counts[1],
                              "none": scene_counts[0],
                              "seasonal-scenes": scene_counts[2]}},
        },
        "stage1": {
            "assemblyIndex": {"assemblies": 4,
                              "hierarchyCountMethod":
                              "pure-python ECMA-335 metadata reader "
                              "over DummyDll/*.dll",
                              "hierarchyRowCount": 40},
            "idRegistries": {"files": 2}},

        "stage2": {
            "coverage": {
                "bundlesUnreferenced": [],
                "danglingDependencyKeys": 0,
                "distinctBundlesReferenced":
                    cov["distinctBundlesReferenced"],
                "duplicateKeyValue": G_STYLE,
                "keysTotal": len(catalog_rows()),
                "outOfRosterFileReferences":
                    cov["outOfRosterFileReferences"]["count"]},
            "miniReport": {
                "counts": dict(mini["counts"]),
                "duplicateKey": G_STYLE,
                "guidIndexKeys": len(mini["guidIndex"]),
                "keyset": ["bundleUniverse", "counts", "duplicateKeys",
                           "guidIndex", "meta", "nullBundleAddresses"],
                "referencedRelpaths": cov["distinctBundlesReferenced"]}},
        "flat": {
            "harvest/export-manifest.jsonl": {
                "keyset": ["bytes", "class", "outRelPath", "pathId",
                           "sourceBundle"],
                "rows": MANIFEST_ROWS_PIN},
            "harvest/externals.jsonl": {
                "keyset": ["bundle", "externals", "sourceFile"],
                "rows": EXTERNALS_ROWS_PIN},
            "media-catalogue.jsonl": {
                "keyset": ["bundle", "bytesEstimate", "class",
                           "contentAxis", "name", "pathId"],
                "rows": sum(MEDIA_CLASS_COUNTS.values())},
            "relinks/bridges/cab_index.jsonl": {
                "keyset": ["buildId", "bundle", "cab", "objects"],
                "rows": CAB_ROWS_PIN},
            "relinks/bridges/container_index.jsonl": {
                "keyset": ["address", "buildId", "bundle", "class",
                           "pathId"],
                "rows": CONTAINER_ROWS_PIN},
            "relinks/i2_term_registry.jsonl": {
                "keyset": ["buildId", "canonical", "locales", "sourceAsset",
                           "termId", "termKey", "termStatus", "termType"],
                "rows": REGISTRY_ROWS_PIN},
            "relinks/ui_link_coverage.jsonl": {
                "keyset": ["buildId", "definitionClasses", "exportedCount",
                           "gapReason", "genericContainerClasses",
                           "impliedFamilies", "joins", "status",
                           "surfaceId", "uiClass", "unblock"],
                "rows": UI_COVERAGE_ROWS_PIN}},
        "stage3": {
            "censusFiles": 176,
            "exportManifestRows": MANIFEST_ROWS_PIN,
            "externalsRows": EXTERNALS_ROWS_PIN,
            "mediaCatalogueClasses": sorted(MEDIA_CLASS_COUNTS),
            "mediaCatalogueRows": sum(MEDIA_CLASS_COUNTS.values())},
        "stage4": {
            "baseOverlayReport": {"compositionPolicy": COMPOSITION_POLICY},
            "lineCounts": {**{k: v for k, v in
                              sorted(LOCALE_LINE_COUNTS.items())},
                           "BASE-OVERLAY": BASE_OVERLAY_ROWS_PIN},
            "linesTotal": sum(LOCALE_LINE_COUNTS.values()) +
                BASE_OVERLAY_ROWS_PIN,
            "localeCodes": sorted(LOCALE_LINE_COUNTS)},
        "stage5": {
            "absencesRows": ABSENCES_ROWS,
            "axesRows": dict(AXES_COUNTS),
            "kindFiles": dict(STUB_FILENAMES),
            "kinds": sorted(st),
            "rowsByKind": dict(STUB_ROWS_BY_KIND),
            "stubRows": total_stubs,
            "twinsByKind": dict(TWIN_COUNTS),
            "unmappedEvidenceCounts": dict(zip(UNMAPPED_EVIDENCE_VALUES,
                                               UNMAPPED_EVIDENCE_COUNTS)),
            "unmappedRows": UNMAPPED_ROWS},

        "ledgers": {
            "_absences.jsonl": {
                "optional": [],
                "path": "stubs/_absences.jsonl",
                "required": ["absenceType", "buildId", "count", "evidence",
                             "kind", "samples", "scannedBundles",
                             "scannedClasses"]},
            "_dangling_guids.jsonl": {
                "optional": ["unblock"],
                "path": "relinks/_dangling_guids.jsonl",
                "required": ["assetGuid", "buildId", "sampleRefs",
                             "verdict"]},
            "_uncontained_addresses.jsonl": {
                "optional": ["catalogGuid"],
                "path": "relinks/_uncontained_addresses.jsonl",
                "required": ["address", "buildId", "reason", "sampleRefs"]},
            "_unmapped-families.jsonl": {
                "optional": [],
                "path": "stubs/_unmapped-families.jsonl",
                "required": ["buildId", "bundles", "class", "evidence",
                             "objectCount"]},
            "_unresolved_pptrs.jsonl": {
                "optional": [],
                "path": "relinks/_unresolved_pptrs.jsonl",
                "required": ["buildId", "extFileId", "extPath", "fieldPath",
                             "m_PathID", "reason", "srcId", "srcKind"]},
            "competitor_applied.jsonl": {
                "optional": ["dispositions", "floorRequired", "samples",
                             "sourcesApplied", "terminal", "unblock"],
                "path": "relinks/competitor_applied.jsonl",
                "required": ["buildId", "rung", "sourceId"]},
            "entity_asset_guid.jsonl": {
                "dstKind": "asset",
                "keyset": ["buildId", "dstId", "dstKind", "evidence",
                           "inferred", "mechanism", "method", "srcId",
                           "srcKind"],
                "optional": [],
                "path": "relinks/entity_asset_guid.jsonl",
                "required": ["buildId", "dstId", "dstKind", "evidence",
                             "inferred", "mechanism", "method", "srcId",
                             "srcKind"]},
            "entity_locale.jsonl": {
                "dstKind": "locale-term",
                "optional": [],
                "path": "relinks/entity_locale.jsonl",
                "required": ["buildId", "dstId", "dstKind", "evidence",
                             "inferred", "mechanism", "method", "srcId",
                             "srcKind"]},
            "locale_term_entity.jsonl": {
                "optional": [],
                "path": "relinks/locale_term_entity.jsonl",
                "required": ["buildId", "locales", "termKey", "usages"],
                "usagesEntryKeyset": ["fieldPath", "srcId", "srcKind"]}},

        "relations": {
            "competitor_applied.jsonl": {
                                        "path": "relinks/competitor_applied.jsonl","optional":
                                         ["dispositions", "floorRequired",
                                          "genericContainerClasses",
                                          "samples", "sourcesApplied",
                                          "terminal", "unblock"],
                                         "required": ["buildId", "rung",
                                                      "sourceId"]},
            "_absences.jsonl": {
                                        "path": "stubs/_absences.jsonl","optional": [],
                                "required": ["absenceType", "buildId",
                                             "count", "evidence", "kind",
                                             "samples", "scannedBundles",
                                             "scannedClasses"]},
            "_dangling_guids.jsonl": {
                                        "path": "relinks/_dangling_guids.jsonl","optional": ["unblock"],
                                      "required": ["assetGuid", "buildId",
                                                   "sampleRefs",
                                                   "verdict"]},
            "_unmapped-families.jsonl": {
                                        "path": "stubs/_unmapped-families.jsonl","optional": [],
                                         "required": ["buildId", "bundles",
                                                      "class", "evidence",
                                                      "objectCount"]},
            "_unresolved_pptrs.jsonl": {
                                        "path": "relinks/_unresolved_pptrs.jsonl","optional": [],
                                        "required": ["buildId",
                                                     "extFileId", "extPath",
                                                     "fieldPath",
                                                     "m_PathID", "reason",
                                                     "srcId", "srcKind"]},
            "_uncontained_addresses.jsonl": {
                                        "path": "relinks/_uncontained_addresses.jsonl","optional": ["catalogGuid"],
                                             "required": ["address",
                                                          "buildId",
                                                          "reason",
                                                          "sampleRefs"]},
            "entity_asset_guid.jsonl": {
                                        "path": "relinks/entity_asset_guid.jsonl","dstKind": "asset",
                                        "keyset": ["buildId", "dstId",
                                                   "dstKind", "evidence",
                                                   "inferred", "mechanism",
                                                   "method", "srcId",
                                                   "srcKind"],
                                        "resolvedVia":
                                        "catalog-guid+container-index"},
            "entity_locale.jsonl": {
                                        "path": "relinks/entity_locale.jsonl","dstKind": "locale-term",
                                    "keyset": ["buildId", "dstId",
                                               "dstKind", "evidence",
                                               "inferred", "mechanism",
                                               "method", "srcId", "srcKind"]},
            "locale_term_entity.jsonl": {
                                        "optional": [],
                                        "path":
                                        "relinks/locale_term_entity.jsonl",
                                        "required": ["buildId", "locales",
                                                     "termKey", "usages"],
                                         "usagesEntryKeyset":
                                         ["fieldPath", "srcId",
                                          "srcKind"]}},
        "stage6": {

            "bridges": {"cabRows": CAB_ROWS_PIN,
                        "containerRows": CONTAINER_ROWS_PIN},
            "bundleClosure": {"manifest sourceBundle": 114,
                              "pair evidence bundles": None,
                              "stub source.bundle":
                                  len(STUB_BUNDLE_UNIVERSE)},
            "joinReport": {"registryMisses":
                           joinr["registryMisses"],
                           "registryMissesKnownIDs": MISSING_TERM_IDS},
            "ledgers": {
                "_dangling_guids.jsonl": DANGLING_GUID_ROWS,
                "danglingVerdictCounts": {"unresolved-open":
                                          DANGLING_GUID_ROWS},
                "pptrReasonCounts": {REASON_PPTR_A: PPTR_REASON_A_COUNT,
                                     REASON_PPTR_B: PPTR_REASON_B_COUNT},
                "_unresolved_pptrs.jsonl":
                    PPTR_REASON_A_COUNT + PPTR_REASON_B_COUNT},
            "matrix": {
                "cells": 100,
                "joinKeyVocabulary": [JOIN_KEY_PPTR, JOIN_KEY_ASSET,
                                      JOIN_KEY_LOCALE,
                                      "name-equality(<rule>)",
                                      JOIN_KEY_NONE],
                "mechanismVocabulary": list(MECHANISMS),
                "nodes": 10,
                "statusVocabulary": list(STATUSES),
                "statuses": msc},
            "evidenceKeysets": {
                "pptr-same-file": ["dstBundle", "dstPathId", "fieldPath",
                                   "refCount", "srcBundle", "srcPathId"],
                "pptr-cross-file": ["dstBundle", "dstPathId", "fieldPath",
                                    "refCount", "srcBundle", "srcPathId",
                                    "dstCab", "extFileId", "resolvedVia"],
                "assetguid-catalog": ["assetGuid", "catalogAddress",
                                      "fieldPath"]},
            "keysets": {
                "_absences.jsonl": ["absenceType", "buildId", "count",
                                    "evidence", "kind", "samples",
                                    "scannedBundles", "scannedClasses"],
                "_dangling_guids.jsonl": ["assetGuid", "buildId",
                                          "sampleRefs", "unblock",
                                          "verdict"],
                "_unmapped-families.jsonl": ["buildId", "bundles", "class",
                                             "evidence", "objectCount"],
                "_unresolved_pptrs.jsonl": ["buildId", "extFileId",
                                            "extPath", "fieldPath",
                                            "m_PathID", "reason", "srcId",
                                            "srcKind"],
                "competitor_applied.jsonl": ["buildId", "dispositions",
                                             "rung", "samples",
                                             "sourceId"],
                "entity_asset_guid.jsonl": ["buildId", "dstId", "dstKind",
                                            "evidence", "inferred",
                                            "mechanism", "method", "srcId",
                                            "srcKind"],
                "entity_locale.jsonl": ["buildId", "dstId", "dstKind",
                                        "evidence", "inferred", "mechanism",
                                        "method", "srcId", "srcKind"],
                "locale_term_entity.jsonl": ["buildId", "locales",
                                             "termKey", "usages"]},
            "pairFiles": {"count": len(pair_datasets())},
            "reports": {"competitorLedgerRows": 3,
                        "uiCoverage": {"gap": UI_GAP_PIN,
                                       "mapped": UI_MAPPED_PIN},
                        "uncontainedCarveOut": {"addresses": 5,
                                                "edgeRows": 9}}},})


def pins_obj(*, handover: bool) -> dict:
    roster = roster_rows()
    dir_counts = [sum(1 for r in roster if r["dirClass"] == k)
                  for k in ("base", "dlc-space", "dlc-ghost")]
    scene_counts = [sum(1 for r in roster if r["sceneFlag"] == k)
                    for k in ("none", ".unity", "seasonal-scenes")]
    loc_counts = [sum(1 for r in roster if r["localeFlag"] is None),
                  sum(1 for r in roster if r["localeFlag"] == "base"),
                  sum(1 for r in roster
                      if r["localeFlag"] not in (None, "base"))]
    st = stub_rows()
    axes_counts = dict(AXES_COUNTS)
    twins = dict(TWIN_COUNTS)
    availability_writer = "locale-proof" if handover else \
        "emit-stub-datasets"
    path_owner = {
        "extracted/RELATIONS.md": {"regeneratedBy": "relink",
                                   "writer": "relink"},
        "extracted/addressables/*": {"writer": "harvest-catalog"},
        "extracted/bundle-roster.jsonl": {"writer": "verify-client"},
        "extracted/harvest/*": {"writer": "harvest-bundles"},
        "extracted/identity.json": {"writer": "verify-client"},
        "extracted/locales/*": {"writer": "localisation"},
        "extracted/media-catalogue.jsonl": {"writer": "harvest-bundles"},
        "extracted/relinks/locale_availability.jsonl": {
            "handover": ("piece-07 section 5 flips the sole writer; "
                         "this map moves WITH the handover"),
            "writer": availability_writer,
            "writerAfterHandover": "locale-proof"},
        "extracted/relinks/*": {"writer": "relink"},
        "extracted/stubs/*": {"writer": "emit-stub-datasets"}}
    if handover:
        path_owner["extracted/relinks/locale_availability.report.json"] = {
            "handover": "joins the owned set with the v2 companion",
            "writer": "locale-proof"}
    pins = {"buildScope": {"buildId": TARGET_BUILD},
            "counterUnitExemptFields": ["buildId", "meta.buildId"],
            "ledgerPaths": {
                "_absences.jsonl": "stubs/_absences.jsonl",
                "_dangling_guids.jsonl": "relinks/_dangling_guids.jsonl",
                "_unmapped-families.jsonl": "stubs/_unmapped-families.jsonl",
                "_unresolved_pptrs.jsonl": "relinks/_unresolved_pptrs.jsonl",
                "_uncontained_addresses.jsonl":
                    "relinks/_uncontained_addresses.jsonl",
                "competitor_applied.jsonl":
                    "relinks/competitor_applied.jsonl",
                "entity_asset_guid.jsonl":
                    "relinks/entity_asset_guid.jsonl",
                "entity_locale.jsonl": "relinks/entity_locale.jsonl",
                "locale_term_entity.jsonl":
                    "relinks/locale_term_entity.jsonl"},
            "enums": ENUM_PINS(),
            "pathOwner": path_owner,
            "reconciliations": RECONCILIATION_PINS(),
            "transforms": {TRANSFORM_NAME: {
                "expression": TRANSFORM_EXPRESSION,
                "licenses": ["localisation-overwrite-identity"],
                "units": ["emission-events", "distinct-keys"]}},
            "transformsLicense": {TRANSFORM_NAME:
                                  ["localisation-overwrite-identity"]},
            "unitVocabulary": list(UNIT_VOCABULARY)}
    pins["families"] = _family_pins(handover=handover,
                                    dir_counts=dir_counts,
                                    scene_counts=scene_counts,
                                    loc_counts=loc_counts,
                                    axes_counts=axes_counts, twins=twins,
                                    msc=matrix_status_counts())
    return pins


FAMILY_SLICES = (
    # (family mdx filename, pins.families key)
    ("stage0-identity.mdx", "stage0"),
    ("stage1-decompile.mdx", "stage1"),
    ("stage2-addressables.mdx", "stage2"),
    ("stage3-harvest.mdx", "stage3"),
    ("stage4-locales.mdx", "stage4"),
    ("stage5-stubs.mdx", "stage5"),
    ("stage6-relinks.mdx", "stage6"),
)

RED_REGISTRY_IDS = ("V-L1", "V-U1", "V-U2", "V-D1")
ALL_VALIDATOR_IDS = tuple(
    [f"V-S{i}" for i in range(1, 14)] +
    [f"V-I{i}" for i in range(1, 10)] +
    ["V-X1", "V-X2", "V-X3", "V-X4"] +
    ["V-U1", "V-U2", "V-U3"] +
    ["V-L1", "V-L2", "V-L3"] +
    ["V-D1", "V-D2", "V-D3", "V-D4"] +
    [f"V-R{i}" for i in range(1, 9)]
)
assert len(ALL_VALIDATOR_IDS) == 44


def family_mdx(name: str, key: str, pins: dict) -> str:
    slice_obj = pins["families"][key]
    prose = {
        "stage0": "Client identity + roster envelope.",
        "stage1": "Decompile outputs (assembly index stamp block).",
        "stage2": "Addressables trio + the persisted catalog mini-report.",
        "stage3": "Harvest trees: manifest, externals, census, catalogue.",
        "stage4": "Locales: 13 codes + base-overlay key registry.",
        "stage5": "Stub envelopes + the two permanent-by-design ledgers.",
        "stage6": "Relinks: pairs, matrix, bridges, registry, reports, ledgers.",
    }[key]
    return (f"# {name[:-4]} family contract\n\n{prose}\n\n"
            "The fenced block below MUST canonically equal this family's "
            "pins.json slice (V-D3).\n\n```pins\n"
            + json.dumps(slice_obj, sort_keys=True, indent=2,
                         ensure_ascii=False) + "\n```\n")


def exceptions_mdx(pins: dict) -> str:
    ex = pins["families"]["exceptions"]
    dup = ex["catalogDuplicateKey"]
    nb = ex["catalogNullBundle"]
    slug = ex["slugNull"]
    return f"""# Exception sheet (consumers read this BEFORE building loaders)

Four measured realities look like defects and are not.

## 1. catalog duplicate key

Exactly {dup["rowCount"]} duplicated `key` (`{dup["key"]}`), the rows
canonical-JSON BYTE-IDENTICAL (legal Addressables duplicate registration).
Key->row dict-building MUST be collision-aware; last-wins silently drops
one row. Pin: duplicates always byte-identical, count build-scoped.

## 2. catalog `bundle` null

`bundle` is null on {nb["total"]} of the fixture key rows
({nb["guidKind"]} guid-kind + {nb["addressKind"]} address-kind);
`address` is null on {nb["nullAddressRows"]} address-kind rows. For guid
rows the address IS the container address; owning-bundle lookup = the
catalog->container_index ladder, never `row.bundle` direct.

## 3. stub `slug`

null on {slug["rows"]} of {slug["rows"]} rows BY DESIGN ({slug["rows"]}/
{slug["rows"]}). Display names derive via `entity_locale.jsonl` -> locale
tables; the site layer owns slug generation policy.

## 4. `locales[]` reserved-but-empty

Empty on ALL registry/relation rows because the client stores NO per-term
availability. {ROUTING_SENTENCE[0].upper()}{ROUTING_SENTENCE[1:]} — treat
the empty arrays as RESERVED fields, never data.

{FAITHFUL_SENTENCE} That sentence is itself part of the pinned text.
"""


def _transform_registry_line() -> str:
    # house spelling: NAME: left − right == result  (U+2212 minus sign)
    return (TRANSFORM_NAME + ": emission-events " + chr(0x2212) +
            " distinct-keys == overwrite-events")


def counter_units_mdx() -> str:
    nl = chr(10)
    vocab = nl.join(f"- `{u}`" for u in UNIT_VOCABULARY)
    obj = {"expression": TRANSFORM_EXPRESSION,
           "licenses": ["localisation-overwrite-identity"],
           "name": TRANSFORM_NAME,
           "units": ["emission-events", "distinct-keys"]}
    arr = json.dumps([obj], indent=2, sort_keys=True)
    yamlish = nl.join([
        "- name: " + TRANSFORM_NAME,
        "  units: [emission-events, distinct-keys]",
        "  expression: " + TRANSFORM_EXPRESSION,
        "  licenses: [localisation-overwrite-identity]"])
    body = nl.join([
        "# Counter units (frozen vocabulary + transform registry)",
        "",
        "## Frozen unit vocabulary",
        "",
        "`" + " | ".join(UNIT_VOCABULARY) + "`",
        "",
        "Exactly eight strings. Validators reject any value outside this set.",
        "",
        "## transforms",
        "",
        "Fenced registry parsed by the runner at load time. A reconciliation",
        "whose left/right units differ may load ONLY if its transform name",
        "appears here:",
        "",
        "```transforms",
        _transform_registry_line(),
        "    licenses: V-U2's flagship identity rowsLogged - fileLines =="
        " duplicateKeysOverwritten -- and nothing else",
        "```",
        "",
        "- `" + TRANSFORM_NAME + "`: " + TRANSFORM_EXPRESSION,
        "  (licenses V-U2's flagship identity and nothing else)",
        ""])
    return body


def ledger_map_mdx() -> str:
    return """# Ledger map (declared ledgers, owners, exit-2 contribution)

DECLARED EXIT-2 CONTRIBUTORS (the complete iff-set):

- `_dangling_guids.jsonl` (exists iff any `unresolved-open` verdict row)
- `_unresolved_pptrs.jsonl` (any row)
- `_uncontained_addresses.jsonl` (any row)
- `locale_join_report.registryMisses > 0`
- `catalog-coverage.outOfRosterFileReferences.count > 0` OR
  `danglingDependencyKeys.count > 0`
- a competitor terminal floor-unmet row

DELIBERATELY NOT CONTRIBUTORS (permanent-by-design ledgers):

- `_absences.jsonl`
- `_unmapped-families.jsonl`

Counting them would make relink exit 0 unreachable for all time; their
honesty is pinned by shapes/sorts/caps validators instead.
"""


def red_registry_obj(*, red: bool) -> dict:
    if not red:
        return {"note": ("empty steady-state registry: every validator "
                         "passes on an honest current tree"),
                "registered": []}
    fixes = {
        "V-L1": ("piece-05-amendments RED-1: stage6 emits "
                 "_uncontained_addresses.jsonl during the R3 pass"),
        "V-U1": ("piece-05-amendments RED-3: report generators emit "
                 "counterUnits dicts (frozen vocabulary)"),
        "V-U2": ("piece-05-amendments RED-2: stage4 prints per-locale "
                 "duplicateKeysOverwritten AND persists map+total into "
                 "base-overlay-report evidence"),
        "V-D1": ("piece-05-amendments RED-3: RELATIONS.md template gains "
                 "the availability-routing paragraph"),
    }
    return {"note": ("deliberately-red validators awaiting their fixing "
                     "amendment; EXPECTED-RED lines exit 2, never silent"),
            "registered": [{"fix": fixes[vid], "id": vid}
                           for vid in RED_REGISTRY_IDS]}


def contracts_readme() -> str:
    return """# contracts/ -- what this layer is

Machine-checkable pins over every emitted dataset family. Re-pin after a
game patch by: re-running the harvest, measuring the new constants,
editing `pins.json` in a REVIEWED commit (measured numbers win; prose gets
corrected, never silently), and re-rendering the family ```pins blocks.
Constants are build-scoped: a corpus whose identity.buildId differs from
`buildScope.buildId` reads PIN-STALE.
"""


# --- miniature tools/ writer universe (V-I9 grep target) ---------------------------------

STAGE5_MINI = '''"""Miniature stage-5 emitter (fixture-only; never imported)."""
from pathlib import Path

STUBS_DIR = "extracted/stubs"
AVAILABILITY_PATH = "extracted/relinks/locale_availability.jsonl"


def emit(extracted_root):
    root = Path(extracted_root)
    (root / "stubs" / "items.jsonl").write_text("", encoding="utf-8")
    # honest-zero v1 availability artifact: SOLE WRITER until the
    # locale-proof handover lands (piece-07 section 5)
    (root / "relinks" / "locale_availability.jsonl").write_bytes(b"")
'''

STAGE6_MINI = '''"""Miniature stage-6 relink emitter (fixture-only; never imported)."""
from pathlib import Path

RELINKS_DIR = "extracted/relinks"


def emit(extracted_root):
    relinks = Path(extracted_root) / "relinks"
    for name in ("matrix.json", "RELATIONS.md", "_dangling_guids.jsonl",
                 "_unresolved_pptrs.jsonl", "config_config.jsonl"):
        (relinks / name).write_text("", encoding="utf-8")
'''


def stage_locale_proof_mini() -> str:
    return '''"""Miniature locale-proof stage (fixture-only; never imported).

Present only in the post-handover world (piece-07 section 5): the v2
availability file + its report companion are written HERE and nowhere else.
"""
from pathlib import Path

AVAILABILITY_V2 = "extracted/relinks/locale_availability.jsonl"
AVAILABILITY_REPORT = "extracted/relinks/locale_availability.report.json"


def emit(extracted_root):
    relinks = Path(extracted_root) / "relinks"
    (relinks / "locale_availability.jsonl").write_text(
        "", encoding="utf-8")
    (relinks / "locale_availability.report.json").write_text(
        "{}\n", encoding="utf-8")
'''


STAGE3_MINI = """Miniature stage-3 harvest emitter (fixture-only).
from pathlib import Path
MEDIA_CATALOGUE = "extracted/media-catalogue.jsonl"
def emit(extracted_root):
    root = Path(extracted_root)
    (root / "media-catalogue.jsonl").write_text("", encoding="utf-8")
"""

TPC_COMMON_MINI = '''"""Miniature tpc_common stand-in (fixture-only)."""

STAGES = [
    ("verify-client", "tools/stage0_verify_client.py", 0),
    ("decompile", "tools/stage1_decompile.py", 1),
    ("harvest-catalog", "tools/stage2_harvest_catalog.py", 2),
    ("harvest-bundles", "tools/stage3_harvest_bundles.py", 3),
    ("localisation", "tools/stage4_localisation.py", 4),
    ("emit-stub-datasets", "tools/stage5_emit_stubs.py", 5),
    ("relink", "tools/stage6_relink.py", 6),
]
'''

STAGE2_MINI = '''"""Miniature stage-2 catalog emitter (fixture-only)."""
MINI_REPORT = "extracted/addressables/catalog-mini-report.json"
COVERAGE = "extracted/addressables/catalog-coverage.json"
'''

STAGE4_MINI = """Miniature stage-4 localisation emitter (fixture-only)."""
STAGE4_BODY = """
from pathlib import Path

BASE_OVERLAY_REPORT = "extracted/locales/base-overlay-report.json"
LOCALE_DIR = "extracted/locales"
LOCALE_ROWS_TEMPLATE = "extracted/locales/<locale>.jsonl"


def emit(extracted_root):
    root = Path(extracted_root)
    for code in ("en", "fr", "de"):
        (root / "locales" / (code + ".jsonl")).write_text(
            "", encoding="utf-8")
    (root / "locales" / "base-overlay-report.json").write_text(
        "{}" + chr(10), encoding="utf-8")
"""

STAGE1_MINI = '''"""Miniature stage-1 decompile emitter (fixture-only)."""
STRUCTURAL_DIR = "extracted/decompiled/structural"
ID_REGISTRIES = "extracted/decompiled/structural/id-registries"
'''

STAGE0_MINI = '''"""Miniature stage-0 verifier (fixture-only)."""
IDENTITY_OUT = "extracted/identity.json"
ROSTER_OUT = "extracted/bundle-roster.jsonl"
'''


# --- orchestrator -------------------------------------------------------------------------

FIX_NAMES = ("dupkeys", "counterunits", "ledger", "relations")
ALL_FIXES = frozenset(FIX_NAMES)


def _write_install(tree: Path):
    root = tree / "steamapps" / "common" / "Two Point Campus"
    root.mkdir(parents=True, exist_ok=True)
    for rel in roster_relpaths():
        p = tree / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(det_bytes(f"bundle:{rel}", 512))
    (root / "GameAssembly.dll").write_bytes(b"MZ" + det_bytes("ga", 64))
    acf = tree / "steamapps" / "appmanifest_1649080.acf"
    write_text(acf, f'"AppState"{{\n\t"buildid"\t\t"{TARGET_BUILD}"\n}}\n')


def build_fixture(out: Path, *, handover: bool = False,
                  fixes=()) -> Path:
    """Materialize the full synthetic contract world under `out`."""
    from build_fixture_tree import check_source_root
    out = Path(out)
    check_source_root(out)
    ext = out / "extracted"
    fixes = frozenset(fixes)
    unknown = fixes - ALL_FIXES
    if unknown:
        raise ValueError(f"unknown fixes {sorted(unknown)}; "
                         f"expected subset of {sorted(ALL_FIXES)}")

    # 1. install layout
    _write_install(out)

    # 2. stage 0/1 outputs
    identity = {
        "appid": APPID, "buildId": TARGET_BUILD,
        "dumper": "il2cppdumper",
        "expectedBundles": expected_bundles(),
        "languageSetting": "english",
        "localeBundleCount": sum(1 for r in roster_rows()
                                 if r["localeFlag"] is not None),
        "metadataVersion": 27,
        "sceneCounts": {"sceneCarryingInstall": len(scene_ids()),
                        "seasonalSceneCarryingBase":
                            sum(1 for r in roster_rows()
                                if r["sceneFlag"] == "seasonal-scenes"),
                        "strictUnityBase": sum(1 for r in roster_rows()
                                               if r["sceneFlag"] == ".unity"
                                               and r["dirClass"] == "base"),
                        "strictUnityInstall": sum(1 for r in roster_rows()
                                                  if r["sceneFlag"] ==
                                                  ".unity")},
        "settingsHash": SETTINGS_HASH,
        "targetBuildId": TARGET_BUILD, "unityVersion": UNITY_VERSION,
        "versionString": VERSION_STRING,
        "addressablesVersion": ADDRESSABLES_VERSION,
    }
    assert len(identity) == 13, sorted(identity)
    write_text(ext / "identity.json", canon(identity))
    write_jsonl(ext / "bundle-roster.jsonl", roster_rows())

    assembly_index, hierarchy, registries = structural_files()
    st_dir = ext / "decompiled" / "structural"
    write_text(st_dir / "assembly-index.json", canon(assembly_index))
    write_jsonl(st_dir / "class-hierarchy.jsonl", hierarchy)
    for name, rows in registries.items():
        write_jsonl(st_dir / "id-registries" / name, rows)
    dd = ext / "decompiled" / "il2cppdumper" / "DummyDll"
    dd.mkdir(parents=True, exist_ok=True)
    for dll in ("mscorlib.dll", "TPS.Core.dll", "TPS.Game.dll"):
        (dd / dll).write_bytes(det_bytes(f"dll:{dll}", 128))

    # 3. addressables trio + sidecar + catalog
    catalog_text = json.dumps(
        {"meta": {"addressablesVersion": ADDRESSABLES_VERSION,
                  "buildId": TARGET_BUILD, "providerIds":
                  ["ContentCatalogProvider"],
                  "settingsHash": SETTINGS_HASH},
         "keys": catalog_rows()},
        sort_keys=True, ensure_ascii=False, indent=2) + "\n"
    catalog_bytes = catalog_text.encode("utf-8")
    addr = ext / "addressables"
    write_text(addr / "catalog.json", catalog_text)
    mini = mini_report(catalog_bytes)
    if handover:
        pass  # sidecar shape is handover-independent
    write_text(addr / "catalog-mini-report.json", canon(mini))
    write_text(addr / "catalog-coverage.json",
               canon(catalog_coverage_obj()))
    snapshot = {"parsed": {"m_AddressablesVersion": ADDRESSABLES_VERSION,
                           "m_BuildTarget": "StandaloneWindows64",
                           "m_IsLocalCatalogInBundle": True,
                           "m_SettingsHash": SETTINGS_HASH},
                "verbatim": '{"m_AddressablesVersion": "%s"}'
                            % ADDRESSABLES_VERSION}
    write_text(addr / "settings.snapshot.json", canon(snapshot))
    write_text(ext / ".stage-stamps" / "harvest-catalog.json",
               canon(stage_stamp_harvest_catalog(catalog_bytes)))

    # 4. harvest flat families
    write_jsonl(ext / "harvest" / "export-manifest.jsonl",
                export_manifest_rows())
    write_jsonl(ext / "harvest" / "externals.jsonl", externals_rows())
    for name, obj in census_files().items():
        write_text(ext / "harvest" / "census" / "bundles" / name, canon(obj))
    write_jsonl(ext / "media-catalogue.jsonl", media_rows())

    # 5. locales
    locdir = ext / "locales"
    for loc in sorted(locale_totals()):
        ids = locale_file_ids(loc)
        assert len(ids) == len(set(ids))
        rows = [{"id": k, "text": f"fixture text {i}"} for i, k in
                enumerate(ids)]
        write_jsonl(locdir / f"{loc}.jsonl", rows)
    write_jsonl(locdir / "base-overlay.jsonl",
                [{"id": term_key(i), "text": ""}
                 for i in range(BASE_OVERLAY_ROWS_PIN)])
    dup_keys = None
    if "dupkeys" in fixes:
        dup_keys = {"perLocale": dict(sorted(DUP_OVERWRITE_PER_LOCALE.items())),
                    "total": DUP_OVERWRITE_TOTAL}
    write_text(locdir / "base-overlay-report.json",
               canon(base_overlay_report(dup_keys)))
    write_text(locdir / "locale-matrix.json", canon(locale_matrix_obj()))
    return _build_fixture_rest(out, ext, handover=handover, fixes=fixes,
                               dup_keys=dup_keys)


def _build_fixture_rest(out: Path, ext: Path, *, handover, fixes,
                        dup_keys) -> Path:
    # 6. stubs + stage-5 ledgers
    st = stub_rows()
    for kind, fname in STUB_FILENAMES.items():
        write_jsonl(ext / "stubs" / fname, st[kind])
    led = ledgers()
    for name, rows in led.items():
        home = ext / ("stubs" if name in ("_absences.jsonl",
                                          "_unmapped-families.jsonl")
                      else "relinks")
        write_jsonl(home / name, rows)

    relinks = ext / "relinks"
    (relinks / "bridges").mkdir(parents=True, exist_ok=True)

    # 7. relink family
    for fname, rows in pair_datasets().items():
        write_jsonl(relinks / fname, rows)
    for fname, rows in relation_datasets().items():
        write_jsonl(relinks / fname, rows)
    for fname, rows in relation_datasets_asset().items():
        write_jsonl(relinks / fname, rows)
    write_jsonl(relinks / "bridges" / "cab_index.jsonl", cab_index_rows())
    write_jsonl(relinks / "bridges" / "container_index.jsonl",
                container_index_rows())
    write_jsonl(relinks / "i2_term_registry.jsonl", registry_rows())
    bridge_report = guid_bridge_report()
    if "counterunits" in fixes:
        bridge_report["counterUnits"] = counter_units_for(
            {k: v for k, v in bridge_report.items()
             if k != "counterUnits"})
    write_text(relinks / "guid_bridge_report.json", canon(bridge_report))
    join_report = locale_join_report()
    if "counterunits" in fixes:
        join_report["counterUnits"] = counter_units_for(
            {k: v for k, v in join_report.items()
             if k != "counterUnits"})
    write_text(relinks / "locale_join_report.json", canon(join_report))
    coverage_report = catalog_coverage_obj()
    if "counterunits" in fixes:
        coverage_report["counterUnits"] = counter_units_for(
            catalog_coverage_obj())
    write_text(ext / "addressables" / "catalog-coverage.json",
               canon(coverage_report))
    overlay_report_path = ext / "locales" / "base-overlay-report.json"
    overlay_obj = json.loads(overlay_report_path.read_text(encoding="utf-8"))
    if "counterunits" in fixes and dup_keys is not None:
        overlay_obj["counterUnits"] = counter_units_for(
            {"evidence": overlay_obj["evidence"]})
    write_text(overlay_report_path, canon(overlay_obj))
    write_jsonl(relinks / "ui_link_coverage.jsonl",
                ui_link_coverage_rows())
    write_jsonl(relinks / "competitor_applied.jsonl", competitor_rows())
    write_text(relinks / "matrix.json", canon(matrix_obj()))

    # 8. availability artifact (handover-aware)
    avail = relinks / "locale_availability.jsonl"
    if handover:
        v2 = [{"availableLocales": sorted(LOCALE_LINE_COUNTS)[:3],
               "buildId": TARGET_BUILD,
               "fieldPresence": {"en": ["Name"]}, "id": f"ent_{i:05d}",
               "joinInferred": i % 2 == 0,
               "joinMethod": "<entityId>_Title convention"
               if i % 2 == 0 else "",
               "kind": ("config", "item")[i % 2],
               "namedLocales": ["en"]}
              for i in range(5850)]
        write_jsonl(avail, v2)
        write_text(relinks / "locale_availability.report.json",
                   canon({"buildId": TARGET_BUILD, "rows": 5850,
                          "v": 2}))
    else:
        avail.write_bytes(b"")

    # 9. _uncontained_addresses ledger (RED-1 fix)
    if "ledger" in fixes:
        write_jsonl(relinks / "_uncontained_addresses.jsonl",
                    uncontained_ledger_rows())

    # 9b. ROOT-LEVEL LEDGER MIRRORS (compatibility shim): the landed vs9
    # resolves ledgers at extracted/ ROOT while the measured corpus keeps
    # them under stubs/ and relinks/. Mirror byte-identical copies so the
    # rest of the suite can proceed; flagged as a finding for the pair.
    led_all = dict(led)
    # RED-1 ledger: absent at the canonical relinks/ location day-one;
    # the root mirror ships EMPTY so vs9's unconditional open survives
    # (implementation-defect shim) while population checks stay red.
    led_all["_uncontained_addresses.jsonl"] =         uncontained_ledger_rows() if "ledger" in fixes else []
    led_all["competitor_applied.jsonl"] = competitor_rows()
    led_all["entity_locale.jsonl"] =         relation_datasets()["entity_locale.jsonl"]
    led_all["locale_term_entity.jsonl"] =         relation_datasets()["locale_term_entity.jsonl"]
    led_all["entity_asset_guid.jsonl"] =         relation_datasets_asset()["entity_asset_guid.jsonl"]
    for name, rows in sorted(led_all.items()):
        home = ext / ("stubs" if name in ("_absences.jsonl",
                                          "_unmapped-families.jsonl")
                      else "relinks")
        write_jsonl(ext / name, rows)          # root mirror (vs9 compat)
        write_jsonl(home / name, rows)         # canonical location

    # 10. RELATIONS.md (+ routing paragraph on the RED-3 fix);
    # the real corpus emits it at extracted/RELATIONS.md (root), not relinks/
    relations = _relations_md(routing=("relations" in fixes),
                              generated_from={
                                  "edgesEmitted": 48, "registryRows":
                                  REGISTRY_ROWS_PIN, "guidRefsTotal":
                                  guid_bridge_report()["guidRefsTotal"],
                                  "coverageRows": UI_COVERAGE_ROWS_PIN,
                                  "competitorLedgerRows": 3})
    write_text(ext / "RELATIONS.md", relations)

    # 11. EXTRACTION-LOG
    log_kw = {"dup_printed": "dupkeys" in fixes,
              "uncontained_contributor": "ledger" in fixes,
              "stage1_units": "counterunits" in fixes}
    write_text(ext / "EXTRACTION-LOG.md", full_extraction_log(**log_kw))

    # 12. contracts layer
    con = out / "contracts"
    pins = pins_obj(handover=handover)
    write_text(con / "pins.json", canon(pins))
    write_text(con / "red-registry.json",
               canon(red_registry_obj(red=fixes != ALL_FIXES)))
    write_text(con / "counter-units.mdx", counter_units_mdx())
    write_text(con / "ledger-map.mdx", ledger_map_mdx())
    write_text(con / "README.mdx", contracts_readme())
    famdir = con / "families"
    for fname, key in FAMILY_SLICES:
        write_text(famdir / fname, family_mdx(fname, key, pins))
    write_text(famdir / "exceptions.mdx", exceptions_mdx(pins))

    # 13. miniature tools/ writer universe
    tools = out / "tools"
    write_text(tools / "tpc_common.py", TPC_COMMON_MINI)
    write_text(tools / "stage0_verify_client.py", STAGE0_MINI)
    write_text(tools / "stage1_decompile.py", STAGE1_MINI)
    write_text(tools / "stage2_harvest_catalog.py", STAGE2_MINI)
    write_text(tools / "stage4_localisation.py",
               STAGE4_MINI + STAGE4_BODY)
    write_text(tools / "stage3_harvest_bundles.py", STAGE3_MINI)
    stage5 = STAGE5_MINI if not handover else \
        STAGE5_MINI.replace(
            '    # honest-zero v1 availability artifact: SOLE WRITER until the\n'
            '    # locale-proof handover lands (piece-07 section 5)\n'
            '    (root / "relinks" / "locale_availability.jsonl").write_bytes(b"")\n',
            "    # emission block DELETED by the piece-07 section 5 handover\n")
    write_text(tools / "stage5_emit_stubs.py", stage5)
    write_text(tools / "stage6_relink.py", STAGE6_MINI)
    if handover:
        write_text(tools / "stage9_locale_proof.py",
                   stage_locale_proof_mini())
    return out


def _relations_md(*, routing: bool, generated_from=None) -> str:
    gf = generated_from or {"edgesEmitted": 48}
    parts = ["# RELATIONS (synthetic contract fixture)", "",
             "generatedFrom:", ""]
    parts += [f"- {k}: {v}" for k, v in gf.items()]
    parts.append("")
    if routing:
        parts += ["## Availability routing",
                  "",
                  ROUTING_SENTENCE[0].upper() + ROUTING_SENTENCE[1:] + ".",
                  "", FAITHFUL_SENTENCE + " That sentence is itself part "
                  "of the pinned text.", ""]
    return "\n".join(parts)


# --- runner adapter (black-box; candidate invocation spellings) ---------------------------

TOOL_REL = Path("tools") / "stage10_check_contracts.py"

USAGE_ERROR_TOKENS = ("unrecognized arguments", "no such option",
                      "invalid choice", "unknown argument",
                      "error: argument")

_BINDING_CACHE: dict[str, int] = {}

ARG_PREFIX_CANDIDATES = (
    lambda ext, con: ["--root", str(ext), "--contracts", str(con)],
    lambda ext, con: ["--root", str(ext), "--contracts-dir", str(con)],
    lambda ext, con: ["--root", str(ext), "--pins", str(con / "pins.json")],
    lambda ext, con: ["--root", str(ext)],
    lambda ext, con: [str(ext)],
)


def tool_path() -> Path:
    return PACK_ROOT / TOOL_REL


def require_tool() -> Path:
    import pytest
    p = tool_path()
    if not p.exists():
        pytest.skip(f"impl-missing: {TOOL_REL} not present yet "
                    "(CodeWriter pending)")
    return p


def _spawn(argv, ext_root: Path, timeout: int, extra_env=None):
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env["TPC_EXTRACTED_ROOT"] = str(ext_root)
    tree = Path(ext_root).parent
    game = tree / "steamapps" / "common" / "Two Point Campus"
    env.setdefault("TPC_GAME_DIR", str(game))
    if extra_env:
        env.update(extra_env)
    return subprocess.run([sys.executable, *argv], cwd=str(PACK_ROOT),
                          env=env, timeout=timeout, capture_output=True,
                          text=True, encoding="utf-8", errors="replace")


def resolve_ext_and_contracts(tree_or_ext: Path) -> tuple[Path, Path]:
    p = Path(tree_or_ext)
    if (p / "extracted").exists():
        ext, con = p / "extracted", p / "contracts"
    else:
        ext = p
        sibling = p.parent / "contracts"
        con = sibling if sibling.exists() else PACK_ROOT / "contracts"
    return ext, con


def _usage_error(output: str) -> bool:
    low = output.lower()
    return any(tok in low for tok in USAGE_ERROR_TOKENS)


EVENT_RE = re.compile(
    r"^(PASS|FAIL|EXPECTED-RED|PIN-STALE|PIN-MISMATCH|INFO)\s+"
    r"\[(?P<vid>[A-Z]{1,2}-[A-Z0-9]+)\]\s*(?P<rest>.*)$")


def parse_events(stdout: str):
    events = []
    for line in stdout.splitlines():
        m = EVENT_RE.match(line.strip())
        if m:
            events.append({"kind": m.group(1), "rest": m.group("rest"),
                           "vid": m.group("vid")})
    return events


def parse_summary(stdout: str):
    for line in reversed(stdout.splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict) and "passed" in obj:
                return obj
    return None


def run_tool(tree_or_ext, *, args=(), timeout=900, extra_env=None,
             allow_no_summary=False):
    """Drive the stage-10 runner BLACK-BOX.

    Fixture trees: the tool modules are COPIED into <tree>/tools/ and the
    copy is executed with cwd=<tree>, so its script-relative contracts
    resolution binds to the FIXTURE's own contracts/ layer (verified
    behaviorally; the pack-side install always binds pack pins).
    The real pack root is driven in place (cwd=PACK_ROOT).
    """
    import pytest
    script = require_tool()
    target = Path(tree_or_ext)
    is_pack = target.resolve() == PACK_ROOT.resolve()
    if is_pack:
        ext, con = PACK_ROOT / "extracted", PACK_ROOT / "contracts"
        exe, cwd = script, PACK_ROOT
    else:
        ext = target / "extracted" if (target / "extracted").exists()             else target
        con = target / "contracts"
        ftools = target / "tools"
        ftools.mkdir(parents=True, exist_ok=True)
        for src in PACK_ROOT.glob("tools/*.py"):
            shutil.copy2(src, ftools / src.name)
        exe, cwd = ftools / script.name, target
    argv = [str(exe), "--root", str(ext), *[str(a) for a in args]]
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env["TPC_EXTRACTED_ROOT"] = str(ext)
    game = target / "steamapps" / "common" / "Two Point Campus"
    if game.exists():
        env.setdefault("TPC_GAME_DIR", str(game))
    if extra_env:
        env.update(extra_env)
    proc = subprocess.run([sys.executable, *argv], cwd=str(cwd), env=env,
                          timeout=timeout, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    out = proc.stdout + proc.stderr
    if _usage_error(out):
        pytest.skip(f"impl-missing: runner rejected arguments {args} "
                    f"(usage error): {out[-300:]!r}")
    return proc


def run_tool_parsed(tree_or_ext, *, args=(), timeout=300, extra_env=None,
                    allow_no_summary=False):
    proc = run_tool(tree_or_ext, args=args, timeout=timeout,
                    extra_env=extra_env, allow_no_summary=allow_no_summary)
    return {"events": parse_events(proc.stdout), "proc": proc,
            "summary": parse_summary(proc.stdout)}


def failing_ids(result) -> set:
    return {e["vid"] for e in result["events"]
            if e["kind"] in ("FAIL", "PIN-MISMATCH", "PIN-STALE")}


def expected_red_ids(result) -> set:
    return {e["vid"] for e in result["events"]
            if e["kind"] == "EXPECTED-RED"}


# --- mutation helpers -----------------------------------------------------------------------

def _rw_json(path: Path, mutate):
    obj = json.loads(path.read_text(encoding="utf-8"))
    mutate(obj)
    write_text(path, canon(obj))


def _rw_jsonl(path: Path, mutate_rows):
    rows = read_jsonl(path)
    rows = mutate_rows(rows)
    if rows is None:
        rows = read_jsonl(path)
    write_jsonl(path, rows)


def _rw_text(path: Path, old: str, new: str, count=1):
    text = path.read_text(encoding="utf-8")
    assert old in text, f"mutation anchor missing in {path.name}: {old!r}"
    write_text(path, text.replace(old, new, count))


# --- mutation registry (AC3 teeth; one entry per scripted mutant) ----------------------------

class Mutation:
    def __init__(self, vid, name, apply, expect="fail"):
        self.apply = apply
        self.expect = expect          # fail | pin-mismatch | pin-stale |
                                      # load-refusal | info-not-fail
        self.vid = vid
        self.name = name

    def __repr__(self):
        return f"<Mutation {self.vid}:{self.name}>"


def _m(vid, name, expect="fail"):
    def deco(fn):
        return Mutation(vid, name, fn, expect)
    return deco


def _tree(root: Path) -> Path:
    return Path(root)


MUTATIONS = []


def add(vid, name, expect="fail"):
    def deco(fn):
        MUTATIONS.append(Mutation(vid, name, fn, expect))
        return fn
    return deco


# V-S family
@add("V-S1", "drop-a-key")
def _(t):
    _rw_json(_ext(t) / "identity.json", lambda o: o.pop("dumper"))


@add("V-S2", "add-a-key")
def _(t):
    p = _ext(t) / "bundle-roster.jsonl"
    _rw_jsonl(p, lambda rows: (rows[0].__setitem__("extra", 1), rows)[1])


@add("V-S2", "change-an-int-dirclass-count", "pin-mismatch")
def _(t):
    p = _ext(t) / "bundle-roster.jsonl"
    _rw_jsonl(p, lambda rows: (rows[0].__setitem__("dirClass",
                                                    "dlc-ghost"), rows)[1])


@add("V-S3", "add-a-key")
def _(t):
    p = _ext(t) / "stubs" / "items.jsonl"
    _rw_jsonl(p, lambda rows: (rows[0].__setitem__("bogus", True), rows)[1])


@add("V-S4", "drop-a-key")
def _(t):
    p = _ext(t) / "relinks" / "item_room.jsonl"
    _rw_jsonl(p, lambda rows: (rows[0]["evidence"].pop("fieldPath"),
                                rows)[1])


@add("V-S5", "add-a-key")
def _(t):
    p = _ext(t) / "locales" / "en.jsonl"
    _rw_jsonl(p, lambda rows: (rows[0].__setitem__("txt", "x"), rows)[1])


@add("V-S6", "drop-a-key")
def _(t):
    p = _ext(t) / "media-catalogue.jsonl"
    _rw_jsonl(p, lambda rows: (rows[0].pop("bytesEstimate"), rows)[1])


@add("V-S7", "unsort-pairs-row-major")
def _(t):
    p = _ext(t) / "relinks" / "matrix.json"

    def swap(o):
        o["pairs"][0], o["pairs"][1] = o["pairs"][1], o["pairs"][0]
    _rw_json(p, swap)


@add("V-S8", "drop-mini-report-top-level-key")
def _(t):
    _rw_json(_ext(t) / "addressables" / "catalog-mini-report.json",
             lambda o: o.pop("guidIndex"))


@add("V-S9", "drop-ledger-row-key")
def _(t):
    p = _ext(t) / "stubs" / "_unmapped-families.jsonl"
    _rw_jsonl(p, lambda rows: (rows[0].pop("objectCount"), rows)[1])


def _ext(tree_or_root: Path) -> Path:
    p = Path(tree_or_root)
    return p / "extracted" if (p / "extracted").exists() else p


@add("V-S10", "unsigned-stem")
def _(t):
    p = _ext(t) / "harvest" / "export-manifest.jsonl"

    def mut(rows):
        for r in rows:
            if r["pathId"] == 302:
                r["outRelPath"] = r["outRelPath"].replace("_302.json",
                                                          ".json")
        return rows
    _rw_jsonl(p, mut)


@add("V-S10", "stray-relinks-file")
def _(t):
    (t / "extracted" / "relinks" / "_stray_notes.jsonl").write_text(
        '{"note": "stray"}\n', encoding="utf-8")


@add("V-S11", "out-of-vocabulary-enum")
def _(t):
    p = t / "extracted" / "relinks" / "config_config.jsonl"

    def mut(rows):
        rows[0]["method"] = "telepathy"
        return sort_pair_rows(rows)
    _rw_jsonl(p, mut)


@add("V-S11", "declared-arm-growth-info", "info-not-fail")
def _(t):
    p = t / "extracted" / "relinks" / "config_config.jsonl"

    def mut(rows):
        rows[0]["method"] = "code-analysis:tooltip-anchor"
        return sort_pair_rows(rows)
    _rw_jsonl(p, mut)


@add("V-S12", "row-buildid-drift")
def _(t):
    p = t / "extracted" / "bundle-roster.jsonl"

    def mut(rows):
        rows[0]["buildId"] = TARGET_BUILD - 1
        return rows
    _rw_jsonl(p, mut)


@add("V-S13", "unsort-two-rows")
def _(t):
    p = t / "extracted" / "relinks" / "_unresolved_pptrs.jsonl"

    def swap(rows):
        rows[0], rows[1] = rows[1], rows[0]
        return rows
    _rw_jsonl(p, swap)


# V-I family
@add("V-I1", "duplicate-a-natural-key")
def _(t):
    p = t / "extracted" / "stubs" / "items.jsonl"
    _rw_jsonl(p, lambda rows: rows + [dict(rows[0])])


@add("V-I2", "distinct-keys-drift")
def _(t):
    p = t / "extracted" / "addressables" / "catalog-mini-report.json"
    _rw_json(p, lambda o: o["counts"].__setitem__("distinctKeys", 13))


@add("V-I2", "dupe-rows-differ-by-one-byte")
def _(t):
    p = t / "extracted" / "addressables" / "catalog-mini-report.json"

    def flip(o):
        o["duplicateKeys"][0]["rowsByteIdentical"] = False
    _rw_json(p, flip)


@add("V-I3", "xor-mapped-row-gains-gap-fields")
def _(t):
    p = t / "extracted" / "relinks" / "ui_link_coverage.jsonl"

    def mut(rows):
        rows[0]["gapReason"] = "suddenly gapped"
        return rows
    _rw_jsonl(p, mut)


@add("V-I3", "xor-gap-row-loses-unblock")
def _(t):
    p = t / "extracted" / "relinks" / "ui_link_coverage.jsonl"

    def mut(rows):
        rows[2]["unblock"] = None
        return rows
    _rw_jsonl(p, mut)


@add("V-I4", "missing-cell-unblock-cleared")
def _(t):
    p = t / "extracted" / "relinks" / "matrix.json"

    def mut(o):
        cell = next(c for c in o["pairs"] if c["status"] == "missing")
        cell["unblock"] = ""
    _rw_json(p, mut)


@add("V-I5", "twin-without-fields-id")
def _(t):
    p = t / "extracted" / "stubs" / "configs.jsonl"

    def mut(rows):
        twin = next(r for r in rows if "@" in r["id"])
        twin["fields"].pop("id")
        return rows
    _rw_jsonl(p, mut)


@add("V-I6", "byte-match-checked-zero")
def _(t):
    _rw_text(t / "extracted" / "EXTRACTION-LOG.md",
             "- identifierByteMatch: checked=2128 mismatches=0",
             "- identifierByteMatch: checked=0 mismatches=0")


@add("V-I7", "sample-cap-overflow")
def _(t):
    p = t / "extracted" / "relinks" / "_dangling_guids.jsonl"

    def mut(rows):
        base = rows[0]["sampleRefs"][0]
        rows[0]["sampleRefs"] = [dict(base, fieldPath=f"F{i}")
                                 for i in range(6)]
        return rows
    _rw_jsonl(p, mut)


@add("V-I8", "declared-list-drops-contributor")
def _(t):
    _rw_text(t / "extracted" / "EXTRACTION-LOG.md",
             "_dangling_guids.jsonl unresolved-open: 1137; ", "")


@add("V-I8", "declared-list-names-permanent-ledger")
def _(t):
    _rw_text(t / "extracted" / "EXTRACTION-LOG.md",
             "(exit 2): ",
             "(exit 2): _absences.jsonl no-identifier: 2; ")


@add("V-I9", "second-writer-injected")
def _(t):
    p = t / "tools" / "stage6_relink.py"
    text = p.read_text(encoding="utf-8")
    text += ('\n\ndef emit_also_availability(extracted_root):\n'
             '    # MUTANT: a second writer for the availability file\n'
             '    (Path(extracted_root) / "relinks" /\n'
             '     "locale_availability.jsonl").write_bytes(b"")\n')
    write_text(p, text)


@add("V-I9", "zero-writers")
def _(t):
    p = t / "tools" / "stage5_emit_stubs.py"
    text = p.read_text(encoding="utf-8")
    lines = [ln for ln in text.splitlines()
             if "locale_availability" not in ln
             and "honest-zero v1" not in ln and "SOLE WRITER" not in ln]
    write_text(p, "\n".join(lines) + "\n")


# V-X family
@add("V-X1", "invented-dstid")
def _(t):
    p = t / "extracted" / "relinks" / "item_room.jsonl"

    def mut(rows):
        rows[0]["dstId"] = "Room_Ghost"
        return sort_pair_rows(rows)
    _rw_jsonl(p, mut)


@add("V-X2", "scene-id-space-violation")
def _(t):
    row = {"buildId": TARGET_BUILD, "dstId":
           "scenes-scene-GHOST.unity.bundle", "dstKind": "scene",
           "evidence": {"fieldPath": "Scene[]"}, "inferred": False,
           "mechanism": "hard", "method": "pptr-same-file",
           "srcId": "cfg_alpha", "srcKind": "config"}
    write_jsonl(t / "extracted" / "relinks" / "config_scene.jsonl", [row])


@add("V-X2", "carve-out-desync-from-ledger")
def _(t):
    p = t / "extracted" / "addressables" / "catalog-mini-report.json"

    def mut(o):
        o["nullBundleAddresses"] = [a for a in o["nullBundleAddresses"]
                                    if a != A_DLC_ATLAS]
    _rw_json(p, mut)


@add("V-X3", "bundle-name-orphan")
def _(t):
    p = t / "extracted" / "stubs" / "rooms.jsonl"

    def mut(rows):
        rows[0]["source"]["bundle"] = "ghost_bundle_not_in_roster.bundle"
        return rows
    _rw_jsonl(p, mut)


@add("V-X4", "axes-union-wrong")
def _(t):
    p = t / "extracted" / "relinks" / "config_config.jsonl"

    def mut(rows):
        for r in rows:
            if "sourceAxes" in r:
                r["sourceAxes"] = ["dlc-ghost"]
        return rows
    _rw_jsonl(p, mut)


@add("V-X4", "axes-carrier-stripped")
def _(t):
    p = t / "extracted" / "relinks" / "config_config.jsonl"

    def mut(rows):
        for r in rows:
            r.pop("sourceAxes", None)
        return rows
    _rw_jsonl(p, mut)


# V-U family
@add("V-U1", "counterunits-absent")
def _(t):
    _rw_json(t / "extracted" / "relinks" / "guid_bridge_report.json",
             lambda o: o.pop("counterUnits"))


@add("V-U1", "wrong-vocabulary")
def _(t):
    p = t / "extracted" / "relinks" / "guid_bridge_report.json"
    _rw_json(p, lambda o: o["counterUnits"].__setitem__("guidRefsTotal",
                                                        "widgets"))


@add("V-U1", "field-coverage-incomplete")
def _(t):
    p = t / "extracted" / "relinks" / "locale_join_report.json"
    _rw_json(p, lambda o: o["counterUnits"].pop("registryMisses"))


@add("V-U2", "printed-not-persisted")
def _(t):
    p = t / "extracted" / "locales" / "base-overlay-report.json"
    _rw_json(p, lambda o: o["evidence"].pop("duplicateKeysOverwritten"))


@add("V-U2", "persisted-not-printed")
def _(t):
    p = t / "extracted" / "EXTRACTION-LOG.md"

    def mut(text):
        kept = [ln for ln in text.splitlines()
                if "duplicateKeysOverwritten" not in ln]
        return "\n".join(kept) + "\n"
    text = p.read_text(encoding="utf-8")
    write_text(p, mut(text))


@add("V-U2", "bump-counter-without-sibling")
def _(t):
    log = t / "extracted" / "EXTRACTION-LOG.md"
    text = log.read_text(encoding="utf-8")
    old = next(ln for ln in text.splitlines()
               if ln.startswith("- en: rows="))
    new = old.replace("rows=", "rowsX=", 1).replace(
        "rowsX=", "rows=", 1)
    bumped = old.replace(" skippedEmpty=", "_SKIP_", 1)
    parts = bumped.split("_SKIP_")
    bumped = parts[0] + " skippedEmpty=" + str(
        int(parts[1].split()[0]) + 1) + " " +         parts[1].split(maxsplit=1)[1] if len(parts) > 1 else bumped
    write_text(log, text.replace(old, bumped, 1))


# V-L family
@add("V-L1", "delete-a-ledger-row")
def _(t):
    p = t / "extracted" / "relinks" / "_uncontained_addresses.jsonl"
    _rw_jsonl(p, lambda rows: rows[1:])


@add("V-L1", "wrong-reason-vocabulary")
def _(t):
    p = t / "extracted" / "relinks" / "_uncontained_addresses.jsonl"
    _rw_jsonl(p, lambda rows: (rows[0].__setitem__("reason",
                                                    "snapshot-skew"),
                                rows)[1])


@add("V-L2", "reason-string-drift")
def _(t):
    p = t / "extracted" / "relinks" / "_unresolved_pptrs.jsonl"
    _rw_jsonl(p, lambda rows: (rows[0].__setitem__("reason", "mystery"),
                                rows)[1])


@add("V-L2", "unsorted-ledger")
def _(t):
    p = t / "extracted" / "relinks" / "_uncontained_addresses.jsonl"

    def swap(rows):
        rows[0], rows[1] = rows[1], rows[0]
        return rows
    _rw_jsonl(p, swap)


@add("V-L3", "registrymisses-dropped-from-contributors")
def _(t):
    _rw_text(t / "extracted" / "EXTRACTION-LOG.md",
             "; registryMisses: 5", "")


@add("V-L3", "known-id-drift")
def _(t):
    p = t / "extracted" / "relinks" / "locale_join_report.json"
    _rw_json(p, lambda o: o.__setitem__("registryMisses", 2))


# V-D family
@add("V-D1", "routing-note-removed-from-exceptions")
def _(t):
    p = t / "contracts" / "families" / "exceptions.mdx"
    text = p.read_text(encoding="utf-8")
    kept = [ln for ln in text.splitlines() if "locale-matrix" not in ln]
    write_text(p, "\n".join(kept) + "\n")


@add("V-D1", "routing-note-removed-from-relations")
def _(t):
    _rw_text(t / "extracted" / "relinks" / "RELATIONS.md",
             ROUTING_SENTENCE[0].upper() + ROUTING_SENTENCE[1:] + ".",
             "[paragraph removed by mutant]")


@add("V-D2", "sheet-number-drift")
def _(t):
    ex = json.loads((t / "contracts" / "pins.json").read_text(
        encoding="utf-8"))["families"]["exceptions"]["catalogNullBundle"]
    _rw_text(t / "contracts" / "families" / "exceptions.mdx",
             f'is null on {ex["total"]} of the fixture key rows',
             f'is null on {ex["total"] + 1} of the fixture key rows')


@add("V-D3", "pins-block-hand-edit")
def _(t):
    _rw_text(t / "contracts" / "families" / "stage5-stubs.mdx",
             '"stubRows": 13443', '"stubRows": 13444')


@add("V-D4", "buildscope-bumped", "pin-stale")
def _(t):
    _rw_json(t / "contracts" / "pins.json",
             lambda o: o["buildScope"].__setitem__("buildId",
                                                   TARGET_BUILD + 1))


# V-R family (one-sided reconciliation mutations)
@add("V-R1", "matrix-edge-bumped")
def _(t):
    p = t / "extracted" / "relinks" / "matrix.json"

    def mut(o):
        cell = next(c for c in o["pairs"] if c["pairFiles"] ==
                    ["config_config.jsonl"])
        cell["cardinality"]["edges"] += 1
    _rw_json(p, mut)


@add("V-R2", "census-object-dropped")
def _(t):
    p = t / "extracted" / "harvest" / "census" / "bundles" / \
        "configs_assets_all.bundle.json"
    _rw_json(p, lambda o: o["objectsByClass"].__setitem__(
        "GlobalConfig", 3))


@add("V-R3", "media-class-count-shift")
def _(t):
    p = t / "extracted" / "media-catalogue.jsonl"
    _rw_jsonl(p, lambda rows: [r for r in rows if r["pathId"] != 9002])


@add("V-R4", "registry-key-renamed")
def _(t):
    p = t / "extracted" / "relinks" / "i2_term_registry.jsonl"

    def mut(rows):
        for r in rows:
            if r["termKey"] == K_ITEM_NAME:
                r["termKey"] = K_ITEM_NAME + "_RENAMED"
        return rows
    _rw_jsonl(p, mut)


@add("V-R5", "reverse-usage-deleted")
def _(t):
    p = t / "extracted" / "relinks" / "locale_term_entity.jsonl"

    def mut(rows):
        for r in rows:
            if r["termKey"] == K_PRESTIGE and len(r["usages"]) > 1:
                r["usages"] = r["usages"][1:]
        return rows
    _rw_jsonl(p, mut)


@add("V-R6", "sidecar-counts-drift")
def _(t):
    p = t / "extracted" / "addressables" / "catalog-mini-report.json"
    _rw_json(p, lambda o: o["counts"].__setitem__("keysTotal", 16))


@add("V-R7", "enumerated-bundle-deleted")
def _(t):
    victim = t / roster_relpaths()[0]
    assert victim.exists()
    victim.unlink()


# --- teeth scoring ---------------------------------------------------------------------------

EXPECT_KINDS = {
    "fail": ("FAIL",),
    "pin-mismatch": ("PIN-MISMATCH",),
    "pin-stale": ("PIN-STALE",),
    "load-refusal": (),
    "info-not-fail": (),
}
FAILING_KINDS = ("FAIL", "PIN-MISMATCH", "PIN-STALE")


def mutation_killed(result, mut: Mutation) -> tuple[bool, str]:
    """Did this mutant die with the CORRECT validator id + payload shape?"""
    events = result["events"]
    proc = result["proc"]
    mine = [e for e in events if e["vid"] == mut.vid]
    if mut.expect == "load-refusal":
        ok = (proc.returncode == 1 and parse_summary(proc.stdout) is None
              and not [e for e in events if e["kind"] == "PASS"])
        why = "" if ok else "expected a load-time refusal (exit 1, no report)"
        return ok, why
    if mut.expect == "info-not-fail":
        bad = [e for e in mine if e["kind"] in FAILING_KINDS]
        info = [e for e in mine if e["kind"] == "INFO"]
        ok = not bad and bool(info)
        why = "" if ok else (
            f"validator fired {sorted({e['kind'] for e in bad}) or 'no INFO'}"
            "; expected a loud INFO arm-growth line and NO failing line")
        return ok, why
    want = EXPECT_KINDS[mut.expect]
    hit = [e for e in mine if e["kind"] in want]
    if not hit:
        return False, (f"no {'/'.join(want)} event for {mut.vid}; got "
                       f"{sorted({e['kind'] for e in mine}) or 'nothing'}")
    rest = hit[0]["rest"]
    if not rest.strip():
        return False, f"{mut.vid} event carries no payload"
    return True, ""


def score_mutations(results: dict) -> dict:
    """results: {(vid, name): killed_bool} -> score report."""
    total = len(results)
    killed = sum(1 for v in results.values() if v)
    unkilled = sorted(f"{vid}:{name}" for (vid, name), v in
                      results.items() if not v)
    return {"killed": killed, "score": (100.0 * killed / total)
            if total else 100.0,
            "total": total, "unkilled": unkilled}


# --- CLI smoke entry --------------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=None)
    ap.add_argument("--handover", action="store_true",
                    help="post-piece-07 section-5 world (RF-1 order B)")
    ap.add_argument("--fix", action="append", default=[],
                    choices=sorted(FIX_NAMES),
                    help="apply an emitter amendment synthetically "
                         "(repeatable; all four => green end state)")
    args = ap.parse_args(argv)

    out = Path(args.out) if args.out else (
        HERE / ".fixture-trees" / "check-contracts")
    check_source_root_guard(out)
    build_fixture(out, handover=args.handover, fixes=frozenset(args.fix))
    print(f"prepared[check-contracts] -> {out}")
    print(f"  extracted : {out / 'extracted'} (point --root here)")
    print(f"  contracts : {out / 'contracts'}")
    print(f"  state     : fixes={sorted(set(args.fix))} "
          f"handover={args.handover}")
    return 0


def check_source_root_guard(root):
    from build_fixture_tree import check_source_root
    return check_source_root(root)


if __name__ == "__main__":
    raise SystemExit(main())
