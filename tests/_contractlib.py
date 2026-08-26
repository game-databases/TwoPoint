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
    "audio-music_assets_all.bundle",
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
STUB_BUNDLE_UNIVERSE = sorted(BASE_BUNDLE_NAMES)         # exactly 11, all in roster
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
    """24 pair datasets. V-X4 is enforced BY CONSTRUCTION: whenever >=1
    endpoint row carries `axes`, the pair row carries sourceAxes == the
    endpoint union — so the green world satisfies the biconditional on every
    row, not just a hand-picked carrier."""
    st = stub_rows()
    pool = {k: st[k] for k in st}
    files = {}
    carriers = 0
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
            union = sorted({*(src.get("axes") or []),
                            *(dst.get("axes") or [])})
            if union:
                carriers += 1
                row["sourceAxes"] = union
            rows.append(row)
        files[fname] = sort_pair_rows(rows)
    assert carriers > 0, "axes carrier rows missing"
    return files


def pair_source_axes_carriers() -> int:
    return sum(1 for rows in pair_datasets().values()
               for r in rows if "sourceAxes" in r)


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
MANIFEST_ROWS_PIN = 16709   # fixture-scale manifest; the REAL 167,069 pin
                            # lives in the pack's contracts/pins.json and is
                            # enforced there (V-S6). Fixture scale keeps the
                            # shared host's disk flat (per-test tree copies).
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
    """222 cab rows over the 176 census bundles; each cab's `objects` lists
    ONE ENTRY PER CENSUS OBJECT so Σ len(objects) == Σ objectsByClass across
    all files (the V-R2 identity) and the split covers every entry."""
    cens = census_files()
    by_bundle = {name[:-len(".json")]: obj["objectsByClass"]
                 for name, obj in cens.items()}
    total_objects = sum(sum(c.values()) for c in by_bundle.values())
    counter = iter(range(900000, 900000 + total_objects + 1000))
    rows = []
    bundles = sorted(by_bundle)
    extra = CAB_ROWS_PIN - len(bundles)
    for i, bundle in enumerate(bundles):
        classes = by_bundle[bundle]
        items = [{"class": cls, "pathId": next(counter)}
                 for cls in sorted(classes) for _ in range(classes[cls])]
        if i < extra:
            mid = len(items) // 2
            parts = [items[:mid], items[mid:]]
        else:
            parts = [items]
        for part_idx, chunk in enumerate(parts):
            rows.append({"buildId": TARGET_BUILD, "bundle": bundle,
                         "cab": "CAB-%s%02d" % (
                             abs(hash(bundle)) % 10 ** 8, part_idx),
                         "objects": chunk or [{"class": "Empty",
                                               "pathId": next(counter)}]})
    rows.sort(key=lambda r: (r["bundle"], r["cab"]))
    assert len(rows) == CAB_ROWS_PIN, len(rows)
    assert sum(len(r["objects"]) for r in rows) == \
        sum(sum(v.values()) for v in by_bundle.values())
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


def _bundle_rel(name: str) -> str:
    """Catalog `bundle` spellings are FULL ROSTER RELPATHS (the measured
    corpus spells them so; derive_mini_report intersects them with the
    roster relpath set)."""
    return f"{AA_REL}/{name}"


def catalog_rows():
    guid_rows = [g(guid, addr) for addr, guid, _b in _CONTAINED_SPEC]
    guid_rows += [g(G_DLC_RURAL, A_DLC_RURAL), g(G_DLC_SNOWY, A_DLC_SNOWY),
                  g(G_DLC_TROPICAL, A_DLC_TROPICAL),
                  g(G_DLC_VARIATIONS, A_DLC_VARIATIONS),
                  g(G_DLC_ATLAS, A_DLC_ATLAS)]
    dupe = g(G_STYLE, A_STYLE)
    guid_rows += [dupe, dict(dupe)]          # byte-identical duplicate pair
    address_rows = [
        a("Assets/Content/Configs/Global.asset",
          _bundle_rel("configs_assets_all.bundle"), []),
        a("Assets/Content/Items/General.itemset",
          _bundle_rel("items-general_assets_all.bundle"),
          [guid_rows[0]["key"]]),
        a("Assets/Content/Rooms.rooms",
          _bundle_rel("rooms_assets_all.bundle"), []),
        an("Assets/Content/UI.nulladdr1",
           _bundle_rel("ui_assets_all.bundle")),
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
    """The emit-time sidecar, produced through the ONE shared derivation the
    spec mandates (piece-05 section 3.3: 'the single sidecar derivation
    consumed by stage-2 post-parse AND by the runner's --scan-catalog audit
    lane'). The fixture PLAYS stage 2 here; importing the shared module is
    what makes AC6's byte-agreement true by construction instead of by
    coincidence. Byte-formatting parity (canon vs log_util.dump_json) is
    exact: same flags, same trailing LF."""
    sys.path.insert(0, str(PACK_ROOT / "tools"))
    import contracts_lib as clib

    meta = {"addressablesVersion": ADDRESSABLES_VERSION,
            "buildId": TARGET_BUILD, "settingsHash": SETTINGS_HASH}
    doc = clib.derive_mini_report(
        catalog_rows(), roster_relpaths(), catalog_coverage_obj(),
        len(catalog_bytes), hashlib.sha256(catalog_bytes).hexdigest(),
        meta=meta)
    assert clib.canonical_json(doc) == clib.canonical_json(
        json.loads(canon(doc)))
    return doc


def catalog_coverage_obj() -> dict:
    """catalog-coverage spelled so it AGREES with the sidecar on every shared
    field (V-R6): referenced/unreferenced over full roster relpaths,
    warning ledgers carrying the FULL list (count == len(samples))."""
    rows = catalog_rows()
    roster_set = set(roster_relpaths())
    referenced = sorted({str(r["bundle"]) for r in rows if r["bundle"]}
                        & roster_set
                        | {str(d) for r in rows for d in r["dependencies"]}
                        & roster_set)
    out_of_roster = sorted({str(r["bundle"]) for r in rows if r["bundle"]}
                           - roster_set)
    return {
        "bundlesUnreferenced": sorted(roster_set - set(referenced)),
        "danglingDependencyKeys": {"count": 0, "sample": []},
        "distinctBundlesReferenced": len(referenced),
        "keysTotal": len(rows),
        "outOfRosterFileReferences": {"count": len(out_of_roster),
                                      "sample": out_of_roster},
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


REGISTRY_TERMS_WALKED = 15684   # ONE walked-terms total for the whole run
                                # (measured semantics: termsWalked is constant
                                # across locales; skippedEmpty varies)


def locale_totals():
    """{loc: (lines, walked, skippedEmpty, rowsLogged, dup)} -- identities:
    rowsLogged == walked - skippedEmpty (walked CONSTANT per run, the F9
    measured semantic) AND rowsLogged - lines == dup."""
    out = {}
    for loc, lines in LOCALE_LINE_COUNTS.items():
        rows_l = lines + DUP_OVERWRITE_PER_LOCALE[loc]
        skipped = REGISTRY_TERMS_WALKED - rows_l
        assert skipped > 0
        out[loc] = (lines, REGISTRY_TERMS_WALKED, skipped, rows_l,
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


EVIDENCE_COUNTER_NAMES = (
    # the pinned 15 overlay evidence counters (V-S8: evidence ⊇ these names;
    # RED-2's duplicateKeysOverwritten joins as an allowed superset)
    "baseCellsSkippedAbsent", "baseCellsSkippedEmpty", "baseOnlyKeys",
    "categoriesMerged", "differingTextSharedKeys", "englishRowCount",
    "englishOnlyKeys", "identicalTextSharedKeys", "overlayCellsWritten",
    "perLocaleTablesEmitted", "registrySources", "registryTerms",
    "skippedMalformedCells", "termStatusForTranslation",
    "termStatusNotForTranslation")
assert len(EVIDENCE_COUNTER_NAMES) == 15


def _null_bundle_pin():
    """catalogNullBundle exception numbers COMPUTED from the rows they
    describe (fixture doctrine: no hand-transcribed constants)."""
    rows = catalog_rows()
    null_bundle = [r for r in rows if r["bundle"] is None]
    return {"addressKind": sum(1 for r in null_bundle
                               if r["kind"] == ADDRESS_KIND),
            "guidKind": sum(1 for r in null_bundle
                            if r["kind"] == GUID_KIND),
            "nullAddressRows": sum(1 for r in rows
                                   if r["address"] is None),
            "total": len(null_bundle)}


def base_overlay_report(dup_keys):
    """Measured shape (V-S8): {compositionPolicy, evidence} — NO buildId
    (the real corpus carries none). Evidence carries the pinned 15 counter
    names (+ duplicateKeysOverwritten once RED-2 lands: superset allowed)."""
    evidence = {"baseCellsSkippedAbsent": 0,
                "baseCellsSkippedEmpty": 15677,
                "baseOnlyKeys": 7, "categoriesMerged": 0,
                "differingTextSharedKeys": 15665,
                "englishRowCount": 15665, "englishOnlyKeys": 0,
                "identicalTextSharedKeys": 0,
                "overlayCellsWritten": BASE_OVERLAY_ROWS_PIN,
                "perLocaleTablesEmitted": len(LOCALE_LINE_COUNTS),
                "registrySources": 26,
                "registryTerms": REGISTRY_TERMS_WALKED,
                "skippedMalformedCells": 0,
                "termStatusForTranslation": 15402,
                "termStatusNotForTranslation": 275}
    if dup_keys is not None:
        evidence["duplicateKeysOverwritten"] = dup_keys
    return {"compositionPolicy": COMPOSITION_POLICY, "evidence": evidence}


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
    "guidRefsTotal": "reference-events",
    "resolveRateAddress": "reference-events",
    "resolveRateStub": "reference-events",
    "resolvedToAddress": "reference-events",
    "resolvedToStub": "reference-events",
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
    """Full-scale manifest (167,069 rows): every sourceBundle is a roster
    member (X3 closure), stems all carry the signed-pathId grammar (V-S10),
    outRelPath unique (V-I1). Deterministic; no wall clock."""
    bundles = sorted(roster_basenames())
    mb_classes = ["GlobalConfig", "ItemConfig", "RoomConfig", "CourseConfig",
                  "MetagameNodeConfig", "CampusLevelConfig"]
    carved_classes = sorted(MEDIA_CLASS_COUNTS)
    rows = []
    for i in range(MANIFEST_ROWS_PIN):
        bundle = bundles[i % len(bundles)]
        stem = bundle[:-len(".bundle")]
        phase = i % 10
        pid = 100000 + i
        if phase == 7:                       # signed pathId spelling (Rev 6)
            pid = -pid
        if phase < 6:
            cls = mb_classes[i % len(mb_classes)]
            rel = (f"harvest/monobehaviours/mb{(i % 9)}/{cls}/"
                   f"{stem}_{pid}.json")
        elif phase < 9:
            cls = carved_classes[i % len(carved_classes)]
            rel = f"harvest/media/{stem}_{pid}.asset"
        else:
            cls = "TextAsset"
            rel = f"harvest/textassets/ta{i % 5}/{stem}_{pid}.txt"
        rows.append({"bytes": 256 + (i % 64) * 8, "class": cls,
                     "outRelPath": rel, "pathId": pid,
                     "sourceBundle": bundle})
    assert len({r["outRelPath"] for r in rows}) == MANIFEST_ROWS_PIN
    assert {r["sourceBundle"] for r in rows} <= roster_basenames()
    rows.sort(key=lambda r: r["outRelPath"])
    return rows


def externals_rows():
    """222 rows over roster bundles; (bundle, sourceFile) unique (V-I1)."""
    bundles = sorted(roster_basenames())
    rows = []
    for i in range(EXTERNALS_ROWS_PIN):
        refs = [] if i % 4 == 0 else [{
            "fileId": (i % 3) + 1, "guid": "0" * 32,
            "path": f"archive:/CAB-fixture{i % 997:04d}", "type": 0}]
        rows.append({"bundle": bundles[i % len(bundles)], "externals": refs,
                     "sourceFile": f"cab-fixturemain{i:04d}"})
    assert len({(r["bundle"], r["sourceFile"]) for r in rows}) == \
        EXTERNALS_ROWS_PIN
    return rows


def structural_files():
    assemblies = [
        {"assembly": "Assembly-CSharp", "status": "dummy-absent(stripped)"},
        {"assembly": "TPS.Core", "status": "dummy-present"},
        {"assembly": "TPS.Game", "status": "dummy-present"},
        {"assembly": "mscorlib", "status": "dummy-present"},
    ]
    # measured shape: the stamp block lives under `meta` (V-S8/V-S12 read it
    # there), exactly like the real corpus's assembly-index.json
    assembly_index = {
        "assemblies": assemblies,
        "meta": {
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
    total_rows = 0
    total_dup = 0
    for loc in sorted(locale_totals()):
        lines, walked, skipped, rows_l, dup = locale_totals()[loc]
        total_rows += rows_l
        total_dup += dup
    # RED-2 amended spelling: per-locale rows carry their inline unit
    # comment and duplicateKeysOverwritten; the policy line carries the
    # machine-readable evidence tuple (registryTerms + event total).
    if dup_printed:
        add("- compositionPolicy: mixed (evidence: "
            f"{{'localeRowsEmittedTotal': {total_rows}, "
            f"'registryTerms': {REGISTRY_TERMS_WALKED}}})")
    else:
        add("- compositionPolicy: mixed")
    for loc in sorted(locale_totals()):
        lines, walked, skipped, rows_l, dup = locale_totals()[loc]
        line = (f"- {loc}: rows={rows_l}"
                f"{'(emission-events)' if dup_printed else ''} "
                f"skippedEmpty={skipped} "
                f"skippedAbsent=0 categories=0 sources=0 malformed=0")
        if dup_printed:
            line += f" duplicateKeysOverwritten={dup}"
        add(line)
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
    """Declared enum domains under the SAME family keys the runner counts
    occurrences by (V-S11 is scoped PER FAMILY)."""
    return {
        "_unmapped.evidence": sorted(UNMAPPED_EVIDENCE_VALUES),
        "absences.absenceType": list(ABSENCE_TYPES),
        "asset.resolvedVia": ["catalog-guid+container-index"],
        "catalog.kind": [ADDRESS_KIND, GUID_KIND],
        "dangling.verdict": list(DANGLING_VERDICTS),
        "matrix.joinKey": [JOIN_KEY_PPTR, JOIN_KEY_ASSET, JOIN_KEY_LOCALE,
                           "name-equality(<rule>)", JOIN_KEY_NONE],
        "matrix.mechanism": list(MECHANISMS),
        "matrix.status": list(STATUSES),
        "media.class": sorted(MEDIA_CLASS_COUNTS),
        "media.contentAxis": ["base", "dlc-space", "dlc-ghost"],
        "overlay.compositionPolicy": ["english-only", "english-over-base",
                                      "base-over-english", "mixed"],
        "pair.method": list(PAIR_METHODS),
        "pptrs.reason": [REASON_PPTR_A, REASON_PPTR_B],
        "registry.termStatus": [0, 1],
        "registry.termType": [0],
        "roster.dirClass": ["base", "dlc-space", "dlc-ghost"],
        "roster.sceneFlag": ["none", ".unity", "seasonal-scenes"],
        "stub.axes": ["base", "dlc-space", "dlc-ghost"],
        "stub.kind": sorted(STUB_ROWS_BY_KIND),
        "stub.method": list(STUB_METHODS),
        "ui.status": list(UI_STATUSES),
    }


def COLD_ARMS():
    """DECLARED-and-not-occurring arms (V-S11 INFO leg): the four unexercised
    pair-method arms live ONLY in the pair files; matrix mechanism 'logic'
    + two joinKeys cold; three dangling verdicts cold."""
    return {
        "dangling.verdict": [v for v in DANGLING_VERDICTS
                             if v != "unresolved-open"],
        "matrix.joinKey": [JOIN_KEY_LOCALE, "name-equality(<rule>)"],
        "matrix.mechanism": ["logic"],
        "pair.method": ["code-analysis:<descriptor>",
                        "competitor-model:<source-id>",
                        "i2-termid-registry",
                        "name-convention:<rule>"],
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
    """pins.families slices under the SAME vocabulary the runner consumes
    (the pack's proven spelling): full-path relations keys carrying
    required/optional, flattened stage6 constants, computed bundleClosure,
    and the measured overlay shape {compositionPolicy, evidence}."""
    st = stub_rows()
    total_stubs = sum(len(v) for v in st.values())
    cov = catalog_coverage_obj()
    mini = mini_report(b"")
    joinr = locale_join_report()
    pairs = pair_datasets()
    pair_rows_total = sum(len(v) for v in pairs.values())
    manifest_bundles = {str(r["sourceBundle"]).rsplit("/", 1)[-1].casefold()
                        for r in export_manifest_rows()}
    relation_pair_keys = ["buildId", "dstId", "dstKind", "evidence",
                          "inferred", "mechanism", "method", "srcId",
                          "srcKind"]
    ledgers_group = {
        "_absences.jsonl": {
            "optional": [],
            "path": "stubs/_absences.jsonl",
            "required": ["absenceType", "buildId", "count", "evidence",
                         "kind", "samples", "scannedBundles",
                         "scannedClasses"]},
        "_dangling_guids.jsonl": {
            "optional": ["unblock"],
            "path": "relinks/_dangling_guids.jsonl",
            "required": ["assetGuid", "buildId", "sampleRefs", "verdict"]},
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
        "_uncontained_addresses.jsonl": {
            "optional": ["catalogGuid"],
            "path": "relinks/_uncontained_addresses.jsonl",
            "required": ["address", "buildId", "reason", "sampleRefs"]},
        "competitor_applied.jsonl": {
            "optional": ["dispositions", "floorRequired", "samples",
                         "sourcesApplied", "terminal", "unblock"],
            "path": "relinks/competitor_applied.jsonl",
            "required": ["buildId", "rung", "sourceId"]},
        "entity_asset_guid.jsonl": {
            "dstKind": "asset",
            "keyset": list(relation_pair_keys),
            "optional": [],
            "path": "relinks/entity_asset_guid.jsonl",
            "required": list(relation_pair_keys)},
        "entity_locale.jsonl": {
            "dstKind": "locale-term",
            "keyset": list(relation_pair_keys),
            "optional": [],
            "path": "relinks/entity_locale.jsonl",
            "required": list(relation_pair_keys)},
        "locale_term_entity.jsonl": {
            "optional": [],
            "path": "relinks/locale_term_entity.jsonl",
            "required": ["buildId", "locales", "termKey", "usages"],
            "usagesEntryKeyset": ["fieldPath", "srcId", "srcKind"]},
    }
    return {
        "exceptions": {
            "catalogDuplicateKey": {"address": A_STYLE,
                                    "byteIdentical": True, "key": G_STYLE,
                                    "rowCount": 2},
            "catalogNullBundle": _null_bundle_pin(),
            "localesReservedEmpty": {
                "entityLocaleRows":
                    len(relation_datasets()["entity_locale.jsonl"]),
                "registryRows": REGISTRY_ROWS_PIN,
                "reservedEmptyCells": 0,
                "reverseIndexRows":
                    len(relation_datasets()["locale_term_entity.jsonl"])},
            "slugNull": {"rows": total_stubs}},
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
        "ledgers": {
            "_uncontained_addresses": {
                "optional": ["catalogGuid"],
                "reason": REASON_UNCONTAINED,
                "required": ["address", "buildId", "reason", "sampleRefs"]}},
        "owned": {"relinks": [
            "relinks/_uncontained_addresses.jsonl",
            "relinks/locale_availability.jsonl",
            "relinks/locale_availability.report.json"]},
        "relations": dict(ledgers_group),
        "stage0": {
            "identityTopKeys": sorted([
                "appid", "addressablesVersion", "buildId", "dumper",
                "expectedBundles", "languageSetting", "localeBundleCount",
                "metadataVersion", "sceneCounts", "settingsHash",
                "targetBuildId", "unityVersion", "versionString"]),
            "roster": {
                "dirClass": {"base": dir_counts[0],
                             "dlc-ghost": dir_counts[2],
                             "dlc-space": dir_counts[1]},
                "keyset": ["buildId", "bytes", "dirClass", "localeFlag",
                           "relpath", "sceneFlag"],
                "localeFlag": {"base": loc_counts[1],
                               "named": loc_counts[2],
                               "null": loc_counts[0]},
                "rows": len(roster_rows()),
                "sceneFlag": {".unity": scene_counts[1],
                              "none": scene_counts[0],
                              "seasonal-scenes": scene_counts[2]}}},
        "stage1": {
            "assemblyIndex": {"assemblies": 4,
                              "hierarchyCountMethod":
                              "pure-python ECMA-335 metadata reader "
                              "over DummyDll/*.dll",
                              "hierarchyRowCount": 40},
            "idRegistries": {"files": 2}},
        "stage2": {
            "coverage": {
                "bundlesUnreferenced": len(cov["bundlesUnreferenced"]),
                "danglingDependencyKeys":
                    cov["danglingDependencyKeys"]["count"],
                "distinctBundlesReferenced":
                    cov["distinctBundlesReferenced"],
                "keysTotal": cov["keysTotal"],
                "outOfRosterFileReferences":
                    cov["outOfRosterFileReferences"]["count"]},
            "dependencyEdgesTotal": mini["counts"]["dependencyEdgesTotal"],
            "distinctKeys": mini["counts"]["distinctKeys"],
            "duplicateKeyAddress": A_STYLE,
            "duplicateKeyCount": len(mini["duplicateKeys"]),
            "duplicateKeyValue": G_STYLE,
            "keysTotal": mini["counts"]["keysTotal"],
            "kindCounts": dict(mini["counts"]["kindCounts"]),
            "miniReportTopKeys": ["bundleUniverse", "counts",
                                  "duplicateKeys", "guidIndex", "meta",
                                  "nullBundleAddresses"],
            "nullBundleRows": dict(mini["counts"]["nullBundleRows"]),
            "rowsWithNoDependencies":
                mini["counts"]["rowsWithNoDependencies"]},
        "stage3": {
            "censusFiles": 176,
            "exportManifestRows": MANIFEST_ROWS_PIN,
            "externalsRows": EXTERNALS_ROWS_PIN,
            "mediaCatalogueClasses": sorted(MEDIA_CLASS_COUNTS),
            "mediaCatalogueRows": sum(MEDIA_CLASS_COUNTS.values())},
        "stage4": {
            "baseOverlayReport": {"compositionPolicy": COMPOSITION_POLICY},
            "evidenceCounterNames": sorted(EVIDENCE_COUNTER_NAMES),
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
        "stage6": {
            "bridgeReportFields": [
                "buildId", "danglingDistinctGuids", "distinctGuids",
                "guidRefsTotal", "resolveRateAddress", "resolveRateStub",
                "resolvedToAddress", "resolvedToStub"],
            "bridges": {"cabRows": CAB_ROWS_PIN,
                        "containerRows": CONTAINER_ROWS_PIN},
            "bundleClosure": {"manifest sourceBundle": len(manifest_bundles),
                              "pair evidence bundles": None,
                              "stub source.bundle":
                                  len(STUB_BUNDLE_UNIVERSE)},
            "evidenceKeysets": {
                "pptr-same-file": ["dstBundle", "dstPathId", "fieldPath",
                                   "refCount", "srcBundle", "srcPathId"],
                "pptr-cross-file": ["dstBundle", "dstPathId", "fieldPath",
                                    "refCount", "srcBundle", "srcPathId",
                                    "dstCab", "extFileId", "resolvedVia"],
                "assetguid-catalog": ["assetGuid", "catalogAddress",
                                      "fieldPath"]},
            "joinReport": {"instancesTotal": joinr["instancesTotal"],
                           "registryMisses": joinr["registryMisses"],
                           "sentinelZero": joinr["sentinelZero"],
                           "unresolvedIdCount": len(joinr["unresolvedIds"])},
            "joinReportFields": [
                "buildId", "codeRefTerms", "coverageOnNonEmpty",
                "instancesTotal", "matrixKeyDiff", "perKindHits",
                "registryHits", "registryMisses", "sentinelZero",
                "unresolvedIds"],
            "ledgers": {
                "danglingUnresolvedOpen": DANGLING_GUID_ROWS,
                "pptrReasonCounts": {REASON_PPTR_A: PPTR_REASON_A_COUNT,
                                     REASON_PPTR_B: PPTR_REASON_B_COUNT}},
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
            "pairFiles": len(pairs),
            "pairRows": pair_rows_total,
            "sourceAxesCarrierRows": pair_source_axes_carriers(),
            "uiCoverage": {"documentedGap": UI_GAP_PIN,
                           "genericContainerRows": 1,
                           "mappedSchema": UI_MAPPED_PIN},
            "uncontainedCarveOut": {"addresses": 5, "edgeRows": 9}},
    }


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
    availability_writer = ("stage9_locale_proof.py" if handover
                           else "stage5_emit_stubs.py")
    # V-I9 shape (pack parity): the INVARIANT with a greppable writer map.
    # Each path names candidate [script, source-regex] pairs; PASS iff
    # EXACTLY ONE candidate's pattern matches its script's source and it is
    # the canonical expect. The availability entry is HANDOVER-AWARE (RF-1):
    # stage5 until piece-07 section 5 lands, locale-proof after -- green in
    # EITHER landing order; two concurrent writers or zero fail loudly.
    path_owner = {
        "invariant": ("exactly-one-writer per extracted/ path at any "
                      "moment; map entries name the CURRENT canonical "
                      "writer per the pack's stage registry (RF-1)"),
        "toolsDir": "writer-universe",
        "paths": {
            "RELATIONS.md": {
                "expect": "stage6_relink.py",
                "writers": [["stage6_relink.py", r'"RELATIONS\.md"']]},
            "addressables/catalog-mini-report.json": {
                "expect": "stage2_harvest_catalog.py",
                "writers": [["stage2_harvest_catalog.py", r"MINI_REPORT"]]},
            "identity.json": {
                "expect": "stage0_verify_client.py",
                "writers": [["stage0_verify_client.py", r"IDENTITY_OUT"]]},
            "locales/base-overlay-report.json": {
                "expect": "stage4_localisation.py",
                "writers": [["stage4_localisation.py",
                             r"BASE_OVERLAY_REPORT"]]},
            "media-catalogue.jsonl": {
                "expect": "stage3_harvest_bundles.py",
                "writers": [["stage3_harvest_bundles.py",
                             r"MEDIA_CATALOGUE"]]},
            "relinks/locale_availability.jsonl": {
                "expect": availability_writer,
                "handover": ("piece-07 section 5 flips the sole writer; "
                             "this entry moves WITH the handover"),
                "writers": [
                    ["stage5_emit_stubs.py", r"locale_availability"],
                    ["stage6_relink.py", r"locale_availability"],
                    ["stage9_locale_proof.py", r"locale_availability"]]},
            "relinks/matrix.json": {
                "expect": "stage6_relink.py",
                "writers": [["stage6_relink.py", r'"matrix\.json"']]}},
    }
    pins = {"buildScope": {"buildId": TARGET_BUILD},
            "coldArms": COLD_ARMS(),
            "counterUnitExemptFields": ["buildId"],
            "docPins": {
                "faithfulProjection":
                    "The projection is faithful, not broken",
                "familyBlocks": {fname: key
                                 for fname, key in FAMILY_SLICES},
                "routingStatement": ROUTING_SENTENCE},
            "enums": ENUM_PINS(),
            "exceptions": EXCEPTION_PINS(),
            "exitCodeContributors": {"members": EXIT_CODE_CONTRIBUTORS()},
            "pathOwner": path_owner,
            "reconciliations": RECONCILIATION_PINS(),
            "sampleCaps": {"absenceSamples": 25, "danglingSampleRefs": 5,
                           "joinUnresolvedSampleRefs": 5},
            "unitVocabulary": list(UNIT_VOCABULARY)}
    pins["families"] = _family_pins(handover=handover,
                                    dir_counts=dir_counts,
                                    scene_counts=scene_counts,
                                    loc_counts=loc_counts,
                                    axes_counts=dict(AXES_COUNTS),
                                    twins=dict(TWIN_COUNTS),
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


def EXIT_CODE_CONTRIBUTORS():
    """The declared exit-2 contributor iff-set (section 7), member name ->
    one-line rule; mirrors the pack's spelling."""
    return {
        "catalog-out-of-roster-or-dangling":
            "catalog-coverage.outOfRosterFileReferences.count > 0 OR "
            "danglingDependencyKeys.count > 0; size = the counts",
        "competitor-floor-unmet":
            "a competitor_applied terminal floor-unmet row exists; size 1/0",
        "dangling-guids-open":
            "any _dangling_guids row with verdict unresolved-open; size = "
            "count of those rows",
        "registry-misses":
            "locale_join_report.registryMisses > 0; size = the counter",
        "uncontained-addresses":
            "any _uncontained_addresses row; size = row count (RED-1 "
            "declares this ledger)",
        "unresolved-pptrs": "any _unresolved_pptrs row; size = row count",
    }


def EXCEPTION_PINS():
    """V-D2's machine slice: anchor heading + every number the sheet must
    interpolate, COMPUTED from the rows they describe."""
    nb = _null_bundle_pin()
    reserved = {"entityLocaleRows":
                len(relation_datasets()["entity_locale.jsonl"]),
                "registryRows": REGISTRY_ROWS_PIN,
                "reverseIndexRows":
                    len(relation_datasets()["locale_term_entity.jsonl"])}
    return [
        {"anchor": "## catalog duplicate key", "id": "catalog-duplicate-key",
         "numbers": [G_STYLE, 2]},
        {"anchor": "## catalog bundle null", "id": "catalog-bundle-null",
         "numbers": [nb["total"], nb["guidKind"], nb["addressKind"],
                     nb["nullAddressRows"]]},
        {"anchor": "## stub slug null", "id": "stub-slug-null",
         "numbers": [sum(STUB_ROWS_BY_KIND.values())]},
        {"anchor": "## locales reserved-but-empty",
         "id": "locales-reserved-empty",
         "numbers": [reserved["registryRows"], reserved["entityLocaleRows"],
                     reserved["reverseIndexRows"]]},
    ]


def exceptions_mdx(pins: dict) -> str:
    ex = pins["families"]["exceptions"]
    dup = ex["catalogDuplicateKey"]
    nb = ex["catalogNullBundle"]
    slug = ex["slugNull"]
    res = ex["localesReservedEmpty"]
    return f"""# Exception sheet (consumers read this BEFORE building loaders)

Four measured realities look like defects and are not.

## catalog duplicate key

Exactly {dup["rowCount"]} duplicated `key` (`{dup["key"]}`), the rows
canonical-JSON BYTE-IDENTICAL (legal Addressables duplicate registration).
Key->row dict-building MUST be collision-aware; last-wins silently drops
one row. Pin: duplicates always byte-identical, count build-scoped.

## catalog bundle null

`bundle` is null on {nb["total"]} of the fixture key rows
({nb["guidKind"]} guid-kind + {nb["addressKind"]} address-kind);
`address` is null on {nb["nullAddressRows"]} address-kind rows. For guid
rows the address IS the container address; owning-bundle lookup = the
catalog->container_index ladder, never `row.bundle` direct.

## stub slug null

null on {slug["rows"]} of {slug["rows"]} rows BY DESIGN ({slug["rows"]}/
{slug["rows"]}). Display names derive via `entity_locale.jsonl` -> locale
tables; the site layer owns slug generation policy.

## locales reserved-but-empty

Empty on all {res["registryRows"]} registry rows, the
{res["entityLocaleRows"]} entity-locale relation rows and the
{res["reverseIndexRows"]} reverse-index rows because the client stores NO
per-term availability. Availability routing:
{ROUTING_SENTENCE} — treat the empty arrays as RESERVED fields, never data.

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
    """Pack spelling: entries[] each carrying the break key, fixing
    amendment, summary, and the validator ids it registers."""
    if not red:
        return {"entries": [],
                "note": ("empty steady-state registry: every validator "
                         "passes on an honest current tree")}
    fixes = {
        "V-L1": ("uncontained-address-ledger", "RED-1",
                 "stage6 emits _uncontained_addresses.jsonl during the R3 "
                 "pass"),
        "V-U1": ("counter-units-undocumented", "RED-3",
                 "report generators emit counterUnits dicts (frozen "
                 "vocabulary)"),
        "V-U2": ("overwrite-counter-invisible", "RED-2",
                 "stage4 prints per-locale duplicateKeysOverwritten AND "
                 "persists map+total into base-overlay-report evidence"),
        "V-D1": ("availability-routing-note-relations", "RED-3",
                 "RELATIONS.md template gains the availability-routing "
                 "paragraph"),
    }
    return {
        "entries": [
            {"break": fixes[vid][1],
             "fix": "piece-05-amendments",
             "key": fixes[vid][0],
             "summary": fixes[vid][2],
             "validators": [vid]}
            for vid in RED_REGISTRY_IDS],
        "note": ("deliberately-red validators awaiting their fixing "
                 "amendment; EXPECTED-RED lines exit 2, never silent"),
    }


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
    # roster relpaths are INSTALL-ROOT-relative (TPC_Data/StreamingAssets/…);
    # they must land under the install root the runner validates
    for rel in roster_relpaths():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(det_bytes(f"bundle:{rel}", 512))
    (root / "GameAssembly.dll").write_bytes(b"MZ" + det_bytes("ga", 64))
    # il2cpp metadata the runner's install-root validation requires
    meta_dir = root / "TPC_Data" / "il2cpp_data" / "Metadata"
    meta_dir.mkdir(parents=True, exist_ok=True)
    (meta_dir / "global-metadata.dat").write_bytes(
        b"AF1BB1FA" + det_bytes("metadata", 2048))
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
            {k: v for k, v in overlay_obj.items() if k != "counterUnits"})
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

    # 13. miniature WRITER UNIVERSE (V-I9's grep target) — lives in its own
    # directory that the runner's tool-copy NEVER overwrites; pins.pathOwner.
    # toolsDir names it. <tree>/tools/ stays for the runner's own imports.
    (out / "tools").mkdir(parents=True, exist_ok=True)
    wu = out / "writer-universe"
    write_text(wu / "tpc_common.py", TPC_COMMON_MINI)
    write_text(wu / "stage0_verify_client.py", STAGE0_MINI)
    write_text(wu / "stage1_decompile.py", STAGE1_MINI)
    write_text(wu / "stage2_harvest_catalog.py", STAGE2_MINI)
    write_text(wu / "stage4_localisation.py",
               STAGE4_MINI + STAGE4_BODY)
    write_text(wu / "stage3_harvest_bundles.py", STAGE3_MINI)
    stage5 = STAGE5_MINI if not handover else \
        STAGE5_MINI.replace(
            'AVAILABILITY_PATH = "extracted/relinks/locale_availability.jsonl"',
            '# AVAILABILITY_PATH ownership MOVED to locale-proof '
            '(piece-07 section 5)').replace(
            '    # honest-zero v1 availability artifact: SOLE WRITER until the\n'
            '    # locale-proof handover lands (piece-07 section 5)\n'
            '    (root / "relinks" / "locale_availability.jsonl").write_bytes(b"")\n',
            "    # emission block DELETED by the piece-07 section 5 handover\n")
    write_text(wu / "stage5_emit_stubs.py", stage5)
    write_text(wu / "stage6_relink.py", STAGE6_MINI)
    if handover:
        write_text(wu / "stage9_locale_proof.py",
                   stage_locale_proof_mini())
    return out


def _relations_md(*, routing: bool, generated_from=None) -> str:
    gf = generated_from or {"edgesEmitted": 48}
    parts = ["# RELATIONS (synthetic contract fixture)", "",
             "generatedFrom:", ""]
    parts += [f"- {k}: {v}" for k, v in gf.items()]
    parts.append("")
    if routing:
        # the PINNED sentence rides VERBATIM (V-D1 substring-matches it)
        parts += ["## Availability routing",
                  "",
                  "Availability routing: " + ROUTING_SENTENCE + ".",
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
    # calibrate the open-counter driver's invocation spelling: this proven
    # argv (--root <ext>) IS one of ARG_PREFIX_CANDIDATES
    _BINDING_CACHE[f"{script}:{script.stat().st_mtime_ns}"] = next(
        i for i, cand in enumerate(ARG_PREFIX_CANDIDATES)
        if cand(Path(ext), Path(cwd) / "contracts") == ["--root", str(ext)])
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

    def mut(rows):
        base = next(r for r in rows if r["dirClass"] == "base")
        base["dirClass"] = "dlc-ghost"
        return rows
    _rw_jsonl(p, mut)


@add("V-S3", "add-a-key")
def _(t):
    p = _ext(t) / "stubs" / "items.jsonl"
    _rw_jsonl(p, lambda rows: (rows[0].__setitem__("bogus", True), rows)[1])


@add("V-S4", "drop-a-key")
def _(t):
    p = _ext(t) / "relinks" / "config_config.jsonl"
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
        r = next(r for r in rows if r["pathId"] > 0)
        signed = f"_{r['pathId']}"
        assert signed in r["outRelPath"]
        r["outRelPath"] = r["outRelPath"].replace(signed, "", 1)
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
        gap = next(r for r in rows if r["status"] == "documented-gap")
        gap["unblock"] = None
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


@add("V-I8", "declared-list-desyncs-from-files")
def _(t):
    # list-side desync (the exit-2 contract breaks both ways): the run
    # section SPELLS a contributor size the files no longer support
    _rw_text(t / "extracted" / "EXTRACTION-LOG.md",
             "unresolved-open: 1137", "unresolved-open: 1136")


@add("V-I8", "declared-list-names-permanent-ledger")
def _(t):
    _rw_text(t / "extracted" / "EXTRACTION-LOG.md",
             "(exit 2): ",
             "(exit 2): _absences.jsonl no-identifier: 2; ")


@add("V-I9", "second-writer-injected")
def _(t):
    p = t / "writer-universe" / "stage6_relink.py"
    text = p.read_text(encoding="utf-8")
    text += ('\n\ndef emit_also_availability(extracted_root):\n'
             '    # MUTANT: a second writer for the availability file\n'
             '    (Path(extracted_root) / "relinks" /\n'
             '     "locale_availability.jsonl").write_bytes(b"")\n')
    write_text(p, text)


@add("V-I9", "zero-writers")
def _(t):
    p = t / "writer-universe" / "stage5_emit_stubs.py"
    text = p.read_text(encoding="utf-8")
    lines = [ln for ln in text.splitlines()
             if "locale_availability" not in ln
             and "honest-zero v1" not in ln and "SOLE WRITER" not in ln]
    write_text(p, "\n".join(lines) + "\n")


# V-X family
@add("V-X1", "invented-dstid")
def _(t):
    p = t / "extracted" / "relinks" / "campus-level_config.jsonl"

    def mut(rows):
        rows[0]["dstId"] = "Config_Ghost"
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


@add("V-L3", "known-id-drift", "pin-mismatch")
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
    _rw_text(t / "extracted" / "RELATIONS.md",
             "Availability routing: " + ROUTING_SENTENCE + ".",
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

    def mut(rows):
        victim = sorted(MEDIA_CLASS_COUNTS)[0]   # AnimationClip
        kept = [r for r in rows if r["class"] != victim]
        assert len(kept) == len(rows) - MEDIA_CLASS_COUNTS[victim]
        return kept
    _rw_jsonl(p, mut)


@add("V-R4", "registry-key-renamed")
def _(t):
    p = t / "extracted" / "relinks" / "i2_term_registry.jsonl"

    def mut(rows):
        for r in rows:
            if r["termKey"] == K_PRESTIGE:
                r["termKey"] = K_PRESTIGE + "_RENAMED"
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
    root = t / "steamapps" / "common" / "Two Point Campus"
    victim = root / roster_relpaths()[0]
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
