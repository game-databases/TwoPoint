#!/usr/bin/env python3
"""Shared helpers for stage 11 — media export (piece-06).

The split is pinned by docs/specs/piece-06-media.mdx §3 Scripts: THIS
module carries the pure machinery — rect grammar + rounding rule, render-
data pairing matcher + duplicate-size tiebreak (contract), naming,
manifest/hash writers + row-schema validators, the cross-check driver
seams, the E6 residue scanner, S0 scratch-discipline math, and the
MEDIA-EXPORT.md renderer. tools/stage11_media.py owns sub-pass
orchestration and holds the only writes under extracted/media/.

Ground truth: piece-06-media.mdx Revision 3 (+ arbiter pins P1–P3),
facts M1–M21 of scout-report-piece-06-media.mdx r2, conventions of
piece-01-extraction-pipeline.mdx (write discipline, exit codes, enums).

No UnityPy import at module scope: every function here is fixture-
testable hostless (synthetic bytes / duck-typed objects only).
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import os
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import log_util  # noqa: E402
import tpc_common as tc  # noqa: E402


class MediaError(tc.StageError):
    """Stage abort with the piece-01 exit-code contract (0/1/2/3)."""


# ---------------------------------------------------------------------------
# Pinned constants (spec §3/§4 — every value traceable to the spec text)

STAGE_ID = "media"
WEB_SUBDIR = "web"

WEBP_QUALITY = 80                       # lossy q80 primary — pre-ruling pin
PNG_TWIN_MAX_DIM = 64                   # flat-glyph twin threshold (M7: 29 refs)
ALPHA_TOLERANCE = 1                     # ≤ 1/255 max per-pixel |Δalpha| (F9 pin)
THUMB_LADDER_DEFAULT = (96, 128)

TEMP_FLOOR_GIB = 4.0                    # S0 floors (M18 grounds the gates)
OUTPUT_FLOOR_GIB = 2.0
SCOPE_CEILING_MIB_DEFAULT = 256         # AC7 scope-breach detectors (exit 1)
SCOPE_CEILING_MIB_UI_CHROME = 512

# Route vocabulary — manifest `route` values AND the cross-check quota names.
ROUTE_ATLAS_PAIR = "atlas-pair"
ROUTE_DIRECT_POINTER = "direct-pointer-subrect"
ROUTE_PASS_THROUGH = "standalone-pass-through"
ROUTES = (ROUTE_ATLAS_PAIR, ROUTE_DIRECT_POINTER, ROUTE_PASS_THROUGH)

# _missing_icons.jsonl reason enum — COMPLETE and FROZEN (§4 Ledgers).
REASON_DLC_ABSENT = "dlc-content-absent"
REASON_STALE_NAME = "stale-name"
REASON_EMPTY_SUB = "empty-sub-name"
REASON_EDITOR_FALLBACK = "editor-only-fallback"
REASON_VISUALS_PREFAB = "visuals-prefab-target"
REASON_MESH_LIST = "mesh-list-target"
REASON_LEVEL_CONFIG = "level-config-target"
ESCAPE_REASON = "uncategorized-reason"          # binding pin P2 (this ledger)
MISSING_REASONS = (
    REASON_DLC_ABSENT, REASON_STALE_NAME, REASON_EMPTY_SUB,
    REASON_EDITOR_FALLBACK, REASON_VISUALS_PREFAB, REASON_MESH_LIST,
    REASON_LEVEL_CONFIG, ESCAPE_REASON,
)

# _pptr_residue.jsonl enums — E6(4) frozen; escape per binding pin P2.
SLOT_CLASS_EXTERNAL = "external"
SLOT_CLASS_SAME_FILE = "same-file"
SLOT_CLASSES = (SLOT_CLASS_EXTERNAL, SLOT_CLASS_SAME_FILE)
TARGET_RESOLUTIONS = (
    "resolved-address", "unresolved-open", "resolved-scene",
    "resolved-editor-only", "removed-content",
)
ESCAPE_SLOT = "uncategorized-slot"
RESIDUE_BASIS = "122-basis"                     # literal on EVERY row
ICON_VOCABULARY_SUBSTRING = "icon"

# Ledgered-skip families (E1 rule 7) — field-path detectors, in priority
# order (EditorFallback wins when several could match).
FAMILY_REASONS = (
    (REASON_EDITOR_FALLBACK, re.compile(r"EditorFallbackIcon", re.IGNORECASE)),
    (REASON_VISUALS_PREFAB, re.compile(r"VisualsPrefab")),
    (REASON_MESH_LIST, re.compile(r"Meshes\[\d+\]")),
    (REASON_LEVEL_CONFIG, re.compile(r"(?:^|\.)(?:m_)?LevelConfig(?:\.|$)")),
)

# Cross-check lane (E4(3)) — binding pin P3: LOSSLESS CLI exports only.
LOSSLESS_CLI_FORMATS = ("png", "bmp", "tga")
FORBIDDEN_CLI_FORMATS = ("webp", "jpg", "jpeg")
CROSSCHECK_MIN_SAMPLE = 20
CLI_UNITY_VERSION_PIN = "2020.3.47f1"
# probe anchors (M9 — pixel-exact validation pair from the verification round)
CROSSCHECK_ANCHORS = (
    "DLC2_Qualifications_janitor_SML",
    "DLC2_Qualifications_janitor_LRG",
)

# AssetStudioModCLI staged location (M17; zero-parades precedent layout).
# Repo-relative entries resolve against the REPO ROOT (no ../ prefixes —
# they must name paths inside this repo), same convention as
# tpc_common.IL2CPP_DUMPER_CANDIDATES.
ASSETSTUDIO_CLI_CANDIDATES = [
    "zero-parades/work/_tooling/AssetStudioModCLI/"
    "AssetStudioModCLI_net8_portable/AssetStudioModCLI.exe",
]

# Client-gate default installs (§3 hostless end-state / pin P1: neither
# TPC_GAME_DIR nor the default install resolving ⇒ wholesale auto-SKIP).
DEFAULT_INSTALL_CANDIDATES = [
    "A:\\SteamLibrary\\steamapps\\common\\Two Point Campus",
]

_GUID_RE = re.compile(r"^[0-9a-f]{32}$")   # same shape as relink_util's

# Seeds (spec §2 M-table) — drift prints `DRIFT:` and the fresh number wins;
# never a silent constant, never a failure on movement alone.
SEED_BUILD_ID = 20226581
SEED_DISTINCT_NAMES = 2158              # M4 PRIMARY basis
SEED_RESOLVED_NAMES = 2151
SEED_MISSING_NAMES = (
    "DLC3_UI_Icons_Objective_Pirates",
    "DLC3_UI_Icons_Objective_Volcano",
    "Gorge_UI_Icons_Objectives_DLC3_Emergency",
    "UI_HUD_Room_T_Icon_DLC3_plot",
    "UI_InGame_DLC3_Icon_studentArchetype_Doctors",
    "UI_InGame_DLC3_Icon_studentArchetype_Nurses",
    "UI_InGame_T_Icon_Item_Teamsports_Cheeseball",
)
SEED_PER_KIND_CELLS = {                 # M5 (rows, rowsWithRefs, guidRefs,
    "item": (3885, 3875, 8140, 1919, 363),
    "config": (8430, 3406, 11422, 1565, 3664),
    "metagame-node": (454, 344, 202, 202, 0),
    "room": (116, 106, 115, 115, 0),
    "student-type": (54, 27, 27, 27, 0),
    "staff": (3, 3, 15, 9, 0),
    "unlockable": (415, 63, 201, 33, 26),
    "course": (69, 0, 0, 0, 0),
    "campus-level": (17, 13, 20, 0, 7),
}
SEED_ATLAS_ROUTE_REFS = 3717            # M6 (atlas-pair / sprite-typed total)
SEED_SPRITE_TYPED_REFS = 3870
SEED_E6_TOTAL = 122                     # M14 canonical basis
SEED_E6_EXTERNAL = 24
SEED_SKIP_CLASSES = (                   # M19 census seeds
    ("Cubemap", 138),
    ("Texture2DArray", 9),
    ("Texture2D", 29),                  # zero-size font-atlas rows (seed-carried)
)
SEED_ENTITY_ASSET_GUID_ROWS = 15630     # M3
SEED_CONVENTION_YIELD = 9               # M15 strict Course_X → icon yield
SEED_COURSE_ROWS = 69
SEED_PPTR_POPULATED = 28


# ---------------------------------------------------------------------------
# Rect grammar (E1 rule 4/5 — rounding PINNED half-away-from-zero, flip
# bottom-origin → image space BEFORE cutting; bounds-checked after rounding)

def round_half_away(v) -> int:
    """Round-half-away-from-zero — deliberately NOT Python's banker's
    round(): round(0.5)==0 and round(2.5)==2 here would corrupt rects.
    floor(v + 0.5) for positives, symmetric for negatives."""
    x = float(v)
    if x >= 0:
        return int(math.floor(x + 0.5))
    return -int(math.floor(-x + 0.5))


def parse_rect(d) -> tuple[float, float, float, float]:
    """textureRect dict → (x, y, w, h) floats. Accepts the Unity spellings
    width/height and the short w/h forms. Raises MediaError(exit 1) on
    malformed input — a rect that cannot be parsed on a REFERENCED sprite
    is a mechanism failure, never silence."""
    if not isinstance(d, dict):
        raise MediaError(f"rect is not a dict: {d!r}", exit_code=1)
    try:
        x = float(d["x"])
        y = float(d["y"])
        w = float(d.get("width", d.get("w")))
        h = float(d.get("height", d.get("h")))
    except (KeyError, TypeError, ValueError) as exc:
        raise MediaError(f"malformed textureRect {d!r}: {exc}", exit_code=1) \
            from None
    for name, val in (("x", x), ("y", y), ("w", w), ("h", h)):
        if math.isnan(val) or math.isinf(val):
            raise MediaError(f"non-finite rect component {name}={val}",
                             exit_code=1)
    return x, y, w, h


def rounded_crop_bounds(rect, page_h=None, page_w=None) -> dict:
    """Round EACH component half-away-from-zero FIRST, THEN derive top/bounds
    from the ROUNDED components (E1 rule 5 — determinism-critical). When the
    page height is known the bottom-origin flip applies
    (top = pageHeight − y − h). Bounds-checked AFTER rounding; breach ⇒
    MediaError exit 1 (EC row: rect-out-of-bounds after pinned rounding)."""
    x, y, w, h = parse_rect(rect)
    rx, ry, rw, rh = (round_half_away(x), round_half_away(y),
                      round_half_away(w), round_half_away(h))
    if rw <= 0 or rh <= 0:
        raise MediaError(
            f"zero/non-positive crop extent after rounding "
            f"(rect={rect!r} -> w={rw}, h={rh})", exit_code=1)
    top = ry if page_h is None else page_h - ry - rh
    left = rx
    if page_w is not None and page_h is not None:
        if left < 0 or top < 0 or left + rw > page_w or top + rh > page_h:
            raise MediaError(
                f"rounded crop out of page bounds: left={left} top={top} "
                f"w={rw} h={rh} page={page_w}x{page_h}", exit_code=1)
    return {"left": left, "top": top, "w": rw, "h": rh}


_PASS_THROUGH_EPS = 1e-3


def rect_covers_texture(rect, tex_w: int, tex_h: int,
                        eps: float = _PASS_THROUGH_EPS) -> bool:
    """E2 pass-through predicate: the sprite's rect covers its ENTIRE texture
    (measured population: 492 corpus-wide). Float-exactness boundary rows are
    the TestWriter's; the epsilon keeps fractional full-cover rects honest."""
    x, y, w, h = parse_rect(rect)
    return (x <= eps and y <= eps
            and w >= tex_w - eps and h >= tex_h - eps)


def crop_rgba_bytes(page_rgba: bytes, page_w: int, page_h: int,
                    bounds: dict) -> bytes:
    """Crop a raw RGBA8 page buffer by pre-rounded bounds (row slicing —
    byte-exact, no resampling, no color conversion)."""
    left, top, w, h = bounds["left"], bounds["top"], bounds["w"], bounds["h"]
    stride = page_w * 4
    out = bytearray()
    for row in range(top, top + h):
        start = row * stride + left * 4
        out += page_rgba[start:start + w * 4]
    return bytes(out)


# ---------------------------------------------------------------------------
# Render-data pairing matcher (E4(1)) — CONTRACT tiebreak

def _guid_words_of(node) -> tuple | None:
    """Extract the (d0,d1,d2,d3[,pathId]) identity from a renderdata-map key
    half: UnityPy decodes it as ({'data[0]': int, …}, pathID) or a dict with
    data[i] members."""
    words = []
    pid = None
    if isinstance(node, dict) and "first" in node:
        node = node["first"]      # m_RenderDataKey spelling
    if isinstance(node, (tuple, list)) and node:
        head = node[0]
        if len(node) > 1:
            try:
                pid = int(node[1])
            except (TypeError, ValueError):
                pid = None
        node = head
    if not isinstance(node, dict):
        return None
    for k, v in sorted(node.items()):
        name = str(k)
        if "data" in name:
            try:
                words.append(int(v))
            except (TypeError, ValueError):
                return None
        elif name in ("m_PathID", "pathID"):
            try:
                pid = int(v)
            except (TypeError, ValueError):
                pass
    if len(words) != 4:
        return None
    return tuple(words) + ((pid,) if pid is not None else ())


def normalize_render_entries(render_data_map) -> list[dict]:
    """UnityPy decodes SpriteAtlas m_RenderDataMap as [(key, data-dict), …].
    Normalize to positional candidate records — INDEX ALIGNMENT WITH
    m_PackedSpriteNamesToIndex IS PROVABLY WRONG (M9: 0/352 agreement) and
    is never used; entryIndex exists only as the final tiebreak discriminator
    within ONE atlas (total order — unique by construction). The map KEY
    (the packed sprite asset's GUID+pathId identity) is captured so a
    sprite's own m_RenderDataKey can resolve its entry EXACTLY — the pinned
    size+tiebreak ladder stays as the fallback when that evidence is
    absent."""
    entries: list[dict] = []
    for i, item in enumerate(render_data_map or []):
        key_identity = None
        if isinstance(item, dict):
            data = item
        else:
            try:
                key_part, data = item
                key_identity = _guid_words_of(key_part)
            except (TypeError, ValueError):
                data = item
        if not isinstance(data, dict):
            continue
        tr = data.get("textureRect") or {}
        tex = data.get("texture") or {}
        try:
            entries.append({
                "entryIndex": i,
                "keyIdentity": key_identity,
                "pageFileId": int(tex.get("m_FileID", 0) or 0),
                "pagePathId": int(tex.get("m_PathID", 0) or 0),
                "x": float(tr.get("x", 0.0)),
                "y": float(tr.get("y", 0.0)),
                "w": float(tr.get("width", tr.get("w", 0.0))),
                "h": float(tr.get("height", tr.get("h", 0.0))),
            })
        except (TypeError, ValueError):
            continue
    return entries


def select_entry_by_render_key(entries: list[dict], render_data_key) -> dict | None:
    """Exact pairing through the SPRITE's own m_RenderDataKey — the game's
    own pointer into the atlas render-data map. Resolves same-page same-size
    collisions the size+tiebreak ladder cannot (measured: Gorge swatch
    families pack dozens of identical-size slots onto one page)."""
    ident = _guid_words_of(render_data_key)
    if ident is None:
        return None
    for e in entries:
        if e.get("keyIdentity") == ident:
            return e
    # tolerate a GUID-only spelling (no pathId on either side)
    if len(ident) == 4:
        for e in entries:
            k = e.get("keyIdentity")
            if k and tuple(k[:4]) == tuple(ident[:4]):
                return e
    return None


def select_page_entry(entries: list[dict], sprite_rect_wh,
                      home_bundle_keys=None) -> tuple[dict | None, bool]:
    """PINNED duplicate-size tiebreak (spec §3 E4(1), arbiter F2):

      candidates = entries whose ROUNDED (w, h) equal the sprite's OWN
      rounded m_RD.textureRect SIZE (never index alignment);
      (a) >1 candidate and page-bundle evidence present → prefer candidates
          whose ``pageBundleKey`` sits in the sprite's HOME-bundle set
          (container_index-derived); if NONE live there, keep the full set;
      (b) still >1 → order by ``(pagePathId ASC, entryIndex ASC)`` and take
          the FIRST.

    Returns (entry_or_None, ambiguous). ``None`` ⇒ pairing MATCH FAILURE on
    a referenced sprite (EC exit 1 — the grammar model is broken). Callers
    increment ``ambiguousPairings`` whenever ambiguous is True and stamp the
    chosen pageName/pagePathId on the manifest row."""
    sw = round_half_away(sprite_rect_wh[0])
    sh = round_half_away(sprite_rect_wh[1])
    cands = [e for e in entries
             if round_half_away(e["w"]) == sw and round_half_away(e["h"]) == sh]
    if not cands:
        return None, False
    ambiguous = len(cands) > 1
    if ambiguous and home_bundle_keys:
        pref = [e for e in cands
                if e.get("pageBundleKey") in home_bundle_keys]
        if pref:
            cands = pref
    cands.sort(key=lambda e: (e["pagePathId"], e["entryIndex"]))
    return cands[0], ambiguous


# ---------------------------------------------------------------------------
# Naming (§4) — subObjectName-keyed; signed-pathId collision suffix;
# empty-sub address-basename ladder with namedBy breadcrumbs

_UNSAFE_FILENAME_RE = re.compile(r"[<>:\"/\\|?*\x00-\x1f]")


def sanitize_component(name: str) -> str:
    """Deterministic filename-component sanitizer (Windows-reserved chars →
    `_`, trailing dots/spaces stripped). Sprite names in this corpus are
    already safe; sanitization is a guard, counted nowhere because it is a
    pure function of the name."""
    cleaned = _UNSAFE_FILENAME_RE.sub("_", str(name)).rstrip(" .")
    return cleaned or "_unnamed"


def emitted_stem(sub_object_name: str, path_id: int | None = None) -> str:
    """`<subObjectName>` or, under collision, `<subObjectName>_<signed
    int64 pathId>` (piece-1 Revision 6 signed-stem contract — negative
    pathIds exist on this client)."""
    base = sanitize_component(sub_object_name)
    if path_id is None:
        return base
    return f"{base}_{int(path_id)}"


def address_basename(address: str) -> str | None:
    """Last path segment of a container address, extension stripped.
    None when nothing usable remains (the ladder falls through)."""
    s = str(address).replace("\\", "/").rsplit("/", 1)[-1]
    if "." in s:
        s = s.rsplit(".", 1)[0]
    return s or None


def standalone_naming(address: str | None, bundle_stem: str,
                      path_id: int) -> tuple[str, str]:
    """Empty-sub naming ladder (E2): container address basename → fallback
    `{bundle-stem}_{signed pathId}`. Returns (stem, namedBy)."""
    base = address_basename(address) if address else None
    if base:
        return sanitize_component(base), "address-basename"
    return f"{sanitize_component(bundle_stem)}_{int(path_id)}", \
        "bundle-pathid"


def bundle_stem(bundle_rel: str) -> str:
    name = str(bundle_rel).replace("\\", "/").rsplit("/", 1)[-1]
    return name[:-len(".bundle")] if name.endswith(".bundle") else name


# ---------------------------------------------------------------------------
# Row schemas — frozen key sets (§4); violations are EC exit-1 material

MANIFEST_KEYS = frozenset({
    "outRelPath", "plane", "format", "quality", "bytes", "sha256", "route",
    "namedBy", "source", "dims", "buildId"})
MANIFEST_SOURCE_KEYS = frozenset({
    "bundle", "pathId", "class", "subObjectName", "assetGuid", "rect",
    "rounded", "contentAxis"})
MANIFEST_SOURCE_ATLAS_KEYS = frozenset({
    "atlasName", "atlasGuid", "pageBundle", "pageName", "pagePathId"})
INDEX_KEYS = frozenset({
    "kind", "srcId", "fieldPath", "assetGuid", "subObjectName", "resolved",
    "chainBreak", "file", "reason", "buildId"})
CHAIN_BREAKS = ("none", "guid", "address", "container")
MISSING_KEYS = frozenset({
    "subObjectName", "assetGuid", "reason", "sampleRefs", "buildId"})
RESIDUE_KEYS = frozenset({
    "kind", "srcId", "fieldPath", "pptr", "pairedReferenceEmpty",
    "slotClass", "targetResolution", "basis", "buildId"})
SKIPPED_KEYS = frozenset({"class", "censusCount", "policy", "buildId"})


def _exact_keys(row: dict, keys: frozenset, what: str) -> None:
    got = set(row.keys())
    if got != set(keys):
        raise MediaError(
            f"{what} schema violation: key set {sorted(got)} != expected "
            f"{sorted(keys)}", exit_code=1)


def validate_manifest_row(row: dict) -> None:
    _exact_keys(row, MANIFEST_KEYS, "export-manifest row")
    src = row.get("source")
    if not isinstance(src, dict):
        raise MediaError("export-manifest row.source must be an object",
                         exit_code=1)
    expected = set(MANIFEST_SOURCE_KEYS)
    atlas_routed = any(k in src for k in MANIFEST_SOURCE_ATLAS_KEYS)
    if atlas_routed:
        expected |= set(MANIFEST_SOURCE_ATLAS_KEYS)
    if set(src.keys()) != expected:
        raise MediaError(
            f"export-manifest source key set {sorted(src.keys())} != "
            f"expected {sorted(expected)} (atlas-routed={atlas_routed})",
            exit_code=1)
    if row.get("route") not in ROUTES:
        raise MediaError(f"unknown route {row.get('route')!r}", exit_code=1)
    if row.get("quality") != WEBP_QUALITY and row.get("format") == "webp":
        raise MediaError(
            f"webp row carries quality {row.get('quality')} != pin "
            f"{WEBP_QUALITY}", exit_code=1)


def validate_index_row(row: dict) -> None:
    _exact_keys(row, INDEX_KEYS, "index row")
    if row.get("chainBreak") not in CHAIN_BREAKS:
        raise MediaError(
            f"index row chainBreak {row.get('chainBreak')!r} outside enum",
            exit_code=1)
    if row.get("resolved") is False:
        if row.get("reason") not in MISSING_REASONS:
            raise MediaError(
                f"unresolved index row carries reason "
                f"{row.get('reason')!r} outside the frozen enum", exit_code=1)
    elif row.get("resolved") is True and row.get("reason") is not None:
        raise MediaError("resolved index row must carry reason:null",
                         exit_code=1)


def validate_missing_row(row: dict) -> None:
    _exact_keys(row, MISSING_KEYS, "_missing_icons row")
    if row.get("reason") not in MISSING_REASONS:
        raise MediaError(
            f"_missing_icons reason {row.get('reason')!r} outside the "
            "frozen enum", exit_code=1)
    refs = row.get("sampleRefs")
    if not isinstance(refs, list) or len(refs) > 5:
        raise MediaError("sampleRefs must be a list capped at 5", exit_code=1)


def validate_residue_row(row: dict) -> None:
    _exact_keys(row, RESIDUE_KEYS, "_pptr_residue row")
    if row.get("basis") != RESIDUE_BASIS:
        raise MediaError(
            f"residue row basis {row.get('basis')!r} != literal "
            f"{RESIDUE_BASIS!r}", exit_code=1)
    if row.get("slotClass") not in SLOT_CLASSES + (ESCAPE_SLOT,):
        raise MediaError(
            f"slotClass {row.get('slotClass')!r} outside enum+escape "
            "(binding pin P2)", exit_code=1)
    if row.get("targetResolution") not in TARGET_RESOLUTIONS + (ESCAPE_SLOT,):
        raise MediaError(
            f"targetResolution {row.get('targetResolution')!r} outside "
            "enum+escape (binding pin P2)", exit_code=1)


def validate_skipped_row(row: dict) -> None:
    _exact_keys(row, SKIPPED_KEYS, "_skipped_classes row")


ROW_VALIDATORS = {
    "export-manifest.jsonl": validate_manifest_row,
    "index.jsonl": validate_index_row,
    "_missing_icons.jsonl": validate_missing_row,
    "_pptr_residue.jsonl": validate_residue_row,
    "_skipped_classes.jsonl": validate_skipped_row,
}


# ---------------------------------------------------------------------------
# Hash manifest (AC3) — "<sha256>  <relpath>" LF, sorted by relpath

HASHES_SEP = "  "


def hashes_line(sha: str, relpath: str) -> str:
    return f"{sha}{HASHES_SEP}{relpath}"


def parse_hashes_line(line: str) -> tuple[str, str] | None:
    parts = line.rstrip("\n").split(HASHES_SEP, 1)
    if len(parts) != 2:
        return None
    return parts[0], parts[1]


def tree_hash_entries(root: Path) -> list[tuple[str, str]]:
    """(relpath, sha256) for every file under root, sorted by relpath."""
    out: list[tuple[str, str]] = []
    if root.is_dir():
        for p in sorted(root.rglob("*")):
            if p.is_file():
                out.append((p.relative_to(root).as_posix(),
                            log_util.sha256_file(p)))
    out.sort(key=lambda t: t[0])
    return out


def write_hashes_sha256(path: Path, entries: list[tuple[str, str]]) -> bytes:
    payload = "".join(hashes_line(s, r) + "\n" for r, s in
                      sorted(entries, key=lambda t: t[0]))
    log_util.atomic_write_text(path, payload)
    return payload.encode("utf-8")


# ---------------------------------------------------------------------------
# Encoders + alpha sanity (format rule §4) — PIL-only, numpy-free

def load_pil():
    from PIL import Image  # noqa: PLC0415 — deferred so fixture tests can
    return Image           # import this module without Pillow present


def pil_versions() -> dict:
    import PIL  # noqa: PLC0415
    import PIL.features  # noqa: PLC0415
    webp_ver = None
    try:
        webp_ver = PIL.features.version("webp")
    except Exception:  # noqa: BLE001 — feature table gap stays non-fatal
        webp_ver = None
    return {"pillowVersion": PIL.__version__,
            "webpFeatureVersion": webp_ver,
            "webpFeatureCheck": bool(PIL.features.check("webp"))}


def image_from_rgba(buf: bytes, w: int, h: int):
    Image = load_pil()
    return Image.frombytes("RGBA", (int(w), int(h)), buf)


def encode_webp(img, quality: int = WEBP_QUALITY) -> bytes:
    bio = io.BytesIO()
    img.save(bio, format="WEBP", quality=int(quality), lossless=False)
    return bio.getvalue()


def encode_png(img) -> bytes:
    bio = io.BytesIO()
    img.save(bio, format="PNG")
    return bio.getvalue()


def encode_thumb(img, dim: int) -> bytes:
    """Derived tier: downscale ONLY (never upscale), LANCZOS, WebP q80."""
    w, h = img.size
    scale = min(1.0, float(dim) / float(max(w, h)))
    tw = max(1, int(w * scale))
    th = max(1, int(h * scale))
    resized = img.resize((tw, th), load_pil().Resampling.LANCZOS)
    return encode_webp(resized)


def alpha_roundtrip_max_delta(webp_bytes: bytes, src_img) -> int:
    """Encode→decode the WebP and compare the decoded ALPHA channel against
    the source crop pixelwise; returns the max per-pixel absolute delta.
    Pinned tolerance: ≤ ALPHA_TOLERANCE (one level on the 0–255 scale);
    beyond ⇒ PNG twin + alphaSanityFallbacks counter, never a failure."""
    Image = load_pil()
    dec = Image.open(io.BytesIO(webp_bytes)).convert("RGBA")
    if dec.size != src_img.size:
        return 255
    a_src = list(src_img.getchannel("A").getdata())
    a_dec = list(dec.getchannel("A").getdata())
    worst = 0
    for x, y in zip(a_src, a_dec):
        d = x - y
        if d < 0:
            d = -d
        if d > worst:
            worst = d
            if worst > 255:
                break
    return worst


# ---------------------------------------------------------------------------
# Page cache (E4(2)) — pages decoded ONCE per run, cached in the temp root
# as raw RGBA arrays, cropped N times. Format-agnostic: whatever UnityPy's
# Texture2D.image returns (BC1/BC3/BC7/RGBA32/…) enters as RGBA8.

class PageCache:
    def __init__(self, pages_dir: Path):
        self.dir = Path(pages_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self._mem: dict[str, tuple[bytes, int, int]] = {}
        self.decoded = 0          # fresh decodes this run (E3 pagesDecoded)

    @staticmethod
    def key_for(bundle_rel: str, path_id: int) -> str:
        return f"{log_util.identity_hash([str(bundle_rel), int(path_id)])[:24]}" \
               f"_{int(path_id)}"

    def _paths(self, key: str) -> tuple[Path, Path]:
        return self.dir / f"{key}.raw", self.dir / f"{key}.json"

    def get(self, key: str) -> tuple[bytes, int, int, int | None] | None:
        """(rgba_bytes, w, h, texture_format|None) or None."""
        hit = self._mem.get(key)
        if hit is not None:
            return hit
        raw_path, meta_path = self._paths(key)
        if raw_path.is_file() and meta_path.is_file():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            buf = raw_path.read_bytes()
            if len(buf) == meta["w"] * meta["h"] * 4:
                hit = (buf, int(meta["w"]), int(meta["h"]),
                       meta.get("fmt"))
                self._mem[key] = hit
                return hit
        return None

    def put(self, key: str, rgba: bytes, w: int, h: int,
            fmt: int | None = None) -> None:
        rec = (rgba, int(w), int(h), (int(fmt) if fmt is not None else None))
        if key not in self._mem:
            self.decoded += 1
        self._mem[key] = rec
        raw_path, meta_path = self._paths(key)
        if not raw_path.exists():       # reruns stay byte-stable; first wins
            tmp_raw = raw_path.with_name(raw_path.name + ".tmp")
            tmp_meta = meta_path.with_name(meta_path.name + ".tmp")
            tmp_raw.write_bytes(rgba)
            tmp_meta.write_text(
                json.dumps({"w": int(w), "h": int(h), "fmt": fmt},
                           sort_keys=True),
                encoding="utf-8", newline="\n")
            os.replace(tmp_raw, raw_path)
            os.replace(tmp_meta, meta_path)


# ---------------------------------------------------------------------------
# Cross-check lane (E4(3))

def assert_lossless_cli_format(image_format: str) -> str:
    """Binding pin P3: CLI exports must be LOSSLESS (`png`; bmp/tga ok).
    webp/jpg are FORBIDDEN — a lossy CLI export manufactures phantom pixel
    mismatches against our decoded crops. Violation = EC exit 1."""
    fmt = str(image_format).lower()
    if fmt in FORBIDDEN_CLI_FORMATS:
        raise MediaError(
            f"cross-check CLI export format '{fmt}' is LOSSY and forbidden "
            f"by pin P3 (allowed: {LOSSLESS_CLI_FORMATS})", exit_code=1)
    if fmt not in LOSSLESS_CLI_FORMATS:
        raise MediaError(
            f"cross-check CLI export format '{fmt}' is not a declared "
            f"lossless option {LOSSLESS_CLI_FORMATS}", exit_code=1)
    return fmt


def cli_export_argv(cli_exe, input_path, out_dir, *,
                    unity_version: str = CLI_UNITY_VERSION_PIN,
                    image_format: str = "png",
                    name_filter: str | None = None) -> list[str]:
    fmt = assert_lossless_cli_format(image_format)
    argv = [str(cli_exe), str(input_path),
            "-m", "export", "-t", "sprite",
            "--image-format", fmt,
            "--unity-version", str(unity_version),
            "-o", str(out_dir)]
    if name_filter:
        argv += ["--filter-by-name", name_filter]
    return argv


def compare_rgba8(ours_img, cli_img) -> dict:
    """PINNED comparator path: CLI export loaded via PIL and converted
    with a single convert("RGBA"); compared ELEMENTWISE against our
    crop's RGBA8 array. Required verdict: identical dimensions AND 0
    differing pixels on the EXACT surface - texels fully opaque on BOTH
    sides.

    Measured scoping necessity (buildId 20226581): (a) texels invisible
    on both sides carry undefined RGB (atlas block-compressed bleed vs
    the CLI's cleared background); (b) semi-transparent texels differ by
    the exporter's alpha compositing while every opaque texel matches
    bit-exact. Opaque-surface identity proves decode + crop placement +
    color fidelity; alpha edges stay reported (softTexels /
    softDivergent) rather than failing the lane. PIL stats only - never
    a binary Read into context."""
    ours = ours_img.convert("RGBA")
    theirs = cli_img.convert("RGBA")
    dims_match = ours.size == theirs.size
    if not dims_match:
        return {"dimensionsMatch": False, "pixelMatchRate": 0.0,
                "maxDelta": None, "diffPixels": None}
    from PIL import ImageChops  # noqa: PLC0415
    d = ImageChops.difference(ours, theirs)
    exact_surface = 0
    diff_pixels = 0
    max_delta = 0
    soft_texels = 0
    soft_divergent = 0
    for px_ours, px_theirs, px_diff in zip(ours.getdata(), theirs.getdata(),
                                           d.getdata()):
        a0 = px_ours[3]
        a1 = px_theirs[3]
        if a0 == 255 and a1 == 255:
            exact_surface += 1
            if px_diff != (0, 0, 0, 0):
                diff_pixels += 1
                local = max(px_diff)
                if local > max_delta:
                    max_delta = local
        elif a0 > 0 or a1 > 0:
            soft_texels += 1
            if px_diff != (0, 0, 0, 0):
                soft_divergent += 1
    rate = (1.0 if diff_pixels == 0
            else 1.0 - (diff_pixels / float(max(1, exact_surface))))
    return {"dimensionsMatch": True, "pixelMatchRate": rate,
            "maxDelta": max_delta, "diffPixels": diff_pixels,
            "exactSurfacePixels": exact_surface,
            "softTexels": soft_texels, "softDivergent": soft_divergent}

def compose_crosscheck_sample(planned, *, min_total: int = CROSSCHECK_MIN_SAMPLE,
                              ) -> list[str]:
    """Deterministic ≥20-sample composition (ALL quotas mandatory):
    ≥1 per route · ≥3 ambiguous-tiebreak · ≥2 fractional-rect · the BC7-page
    sprite if referenced · BOTH probe anchors · remainder filled by
    deterministic stride over the sorted name list. ``planned`` is the dict
    name → plan built by the stage; plans carry the quota attributes."""
    if not planned:
        return []
    names = sorted(planned)
    chosen: list[str] = []

    def add(name):
        if name is not None and name in planned and name not in chosen:
            chosen.append(name)

    for anchor in CROSSCHECK_ANCHORS:
        add(anchor)
    for route in ROUTES:
        for n in names:
            if planned[n].get("route") == route:
                add(n)
                break
    amb = 0
    for n in names:
        if amb >= 3:
            break
        if planned[n].get("ambiguousPairing"):
            add(n)
            amb += 1
    frac = 0
    for n in names:
        if frac >= 2:
            break
        if planned[n].get("fractionalRect"):
            add(n)
            frac += 1
    for n in names:
        if planned[n].get("bc7Page"):
            add(n)
            break
    if len(chosen) < min_total:
        stride = max(1, len(names) // max(1, min_total - len(chosen)))
        for i in range(0, len(names), stride):
            add(names[i])
            if len(chosen) >= min_total:
                break
    i = 0
    while len(chosen) < min_total and i < len(names):
        add(names[i])
        i += 1
    return chosen


def resolve_cli_exe(extracted_root: Path) -> Path | None:
    """Staged AssetStudioModCLI (M17) — repo-relative candidates first, then
    the EXTRACTION-LOG stage-defaults override. None ⇒ the lane reports
    cliAbsent rather than guessing a path."""
    defaults = log_util.read_stage_defaults(extracted_root) or {}
    pinned = (defaults.get("assetStudioModCli") or {}).get("path")
    cands = ([pinned] if pinned else []) + ASSETSTUDIO_CLI_CANDIDATES
    repo_root = tc.resolve_repo_root(tc.resolve_pack_dir())
    for cand in cands:
        if not cand:
            continue
        p = Path(cand)
        if not p.is_absolute():
            p = (repo_root / cand).resolve()
        if p.is_file():
            return p
    return None


# ---------------------------------------------------------------------------
# Stub walkers (shared substrate of E1 and E6)

def walk_asset_guid_refs(fields):
    """Every AssetGUID-SHAPED reference: a dict leaf carrying a VALID 32-hex
    m_AssetGUID (the `{m_AssetGUID, m_SubObjectName, m_SubObjectType}`
    reference shapes). Bare guid-valued strings under guid-named keys
    (relink_util walks those for its bridge) are deliberately NOT part of
    this population: the M5 census columns reproduce from reference-DICT
    refs only (unlockables 201 refs / 63 rows measured both ways)."""
    out: list[dict] = []
    stack = [((), fields)]
    while stack:
        path, node = stack.pop()
        if isinstance(node, dict):
            g = node.get("m_AssetGUID")
            if isinstance(g, str) and _GUID_RE.match(g):
                sub = node.get("m_SubObjectName")
                subt = node.get("m_SubObjectType")
                out.append({
                    "fieldPath": ".".join(path) if path else "(root)",
                    "assetGuid": g,
                    "subObjectName": sub if isinstance(sub, str) else "",
                    "subObjectType": subt if isinstance(subt, str) else "",
                })
                continue
            for k, v in node.items():
                if isinstance(v, (dict, list)):
                    stack.append((path + (str(k),), v))
        elif isinstance(node, list):
            for i, v in enumerate(node):
                stack.append((path + (f"[{i}]",), v))
    out.sort(key=lambda r: tuple(str(r["fieldPath"]).split(".")))
    return out


def is_sprite_typed(sub_object_type: str) -> bool:
    return bool(sub_object_type) \
        and sub_object_type.startswith("UnityEngine.Sprite")


def family_reason_for(field_path: str) -> str | None:
    """Ledgered-skip family detection (E1 rule 7) — priority-ordered."""
    for reason, rx in FAMILY_REASONS:
        if rx.search(field_path or ""):
            return reason
    return None


def reference_field_present(fields) -> bool:
    """True when ANY member carries the reference SHAPE — a dict containing
    `m_AssetGUID`, even when its value is "". The M5 `rows w/ …refs` column
    reproduces on THIS basis for items/configs/metagame-nodes/rooms (verifyA
    recount note: the column counts guid-shaped fields including empty)."""
    stack = [fields]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            if "m_AssetGUID" in node:
                return True
            stack.extend(v for v in node.values()
                         if isinstance(v, (dict, list)))
        elif isinstance(node, list):
            stack.extend(v for v in node if isinstance(v, (dict, list)))
    return False


def walk_pptr_slots(fields):
    """Every PPtr leaf ({m_FileID, m_PathID}) over ALL fields — the E6 scan
    population (nine kinds × all fields, the E1 walk WITHOUT the sprite-type
    filter). Each record carries the OWNING dict (for paired-Reference
    admission) and sorts by field path — deterministic DFS order."""
    out: list[dict] = []

    def visit(node, path, leaf, owner):
        if isinstance(node, dict):
            keys = set(node.keys())
            if keys == {"m_FileID", "m_PathID"} and owner is not node:
                try:
                    fid = int(node.get("m_FileID") or 0)
                    pid = int(node.get("m_PathID") or 0)
                except (TypeError, ValueError):
                    return
                out.append({"fieldPath": ".".join(path) if path else "(root)",
                            "leafName": leaf, "fileId": fid, "pathID": pid,
                            "parent": owner})
                return
            for k, v in node.items():
                visit(v, path + (str(k),), str(k), node)
        elif isinstance(node, list):
            for i, v in enumerate(node):
                visit(v, path + (f"[{i}]",), leaf, owner)

    visit(fields, (), "", None)
    out.sort(key=lambda r: tuple(str(r["fieldPath"]).split(".")))
    return out


def paired_reference_empty(parent, leaf_name: str) -> bool:
    """Admission half-rule: the paired `*Reference` GUID field is EMPTY or
    ABSENT (a populated Reference means the slot's data rides the Reference
    plane and the bare PPtr is dead weight, not residue)."""
    if not isinstance(parent, dict):
        return True
    ref = parent.get(f"{leaf_name}Reference")
    if not isinstance(ref, dict):
        return True
    guid = ref.get("m_AssetGUID")
    return not (isinstance(guid, str) and guid.strip())


def residue_slot_class(file_id: int) -> str:
    return SLOT_CLASS_EXTERNAL if file_id != 0 else SLOT_CLASS_SAME_FILE


def make_residue_row(kind: str, src_id: str, field_path: str, file_id: int,
                     path_id: int, verdict: str, build_id: int) -> tuple[dict, list[str]]:
    """Row assembly with the PER-LEDGER escape routing of binding pin P2:
    out-of-enum slotClass/targetResolution ship as `uncategorized-slot`,
    row STILL EMITTED, DRIFT lines returned to the caller, exit 2 never
    exit 1."""
    drift: list[str] = []
    slot_class = residue_slot_class(file_id)
    if slot_class not in SLOT_CLASSES:
        drift.append(
            f"DRIFT: _pptr_residue slotClass '{slot_class}' outside enum — "
            "shipping escape value uncategorized-slot (pin P2)")
        slot_class = ESCAPE_SLOT
    if verdict not in TARGET_RESOLUTIONS:
        drift.append(
            f"DRIFT: _pptr_residue targetResolution '{verdict}' outside "
            "enum — shipping escape value uncategorized-slot (pin P2)")
        verdict = ESCAPE_SLOT
    row = {
        "kind": kind, "srcId": src_id, "fieldPath": field_path,
        "pptr": {"fileId": int(file_id), "pathID": int(path_id)},
        "pairedReferenceEmpty": True,
        "slotClass": slot_class,
        "targetResolution": verdict,
        "basis": RESIDUE_BASIS,
        "buildId": int(build_id),
    }
    return row, drift


def is_icon_named(leaf_name: str) -> bool:
    """PINNED vocabulary: case-insensitive substring `icon` on the field-path
    LEAF NAME (catches BadgeIcon ×67, RivalIcon, InboxTrayIcon_*,
    ItemsMenuIcon, SwatchMenuIcon, IconReference, _iconReference,
    OverlayIcon*). The RULE is canonical; the NUMBER follows the rule."""
    return ICON_VOCABULARY_SUBSTRING in str(leaf_name or "").lower()


# ---------------------------------------------------------------------------
# S0 scratch discipline (hard preflight)

DRIVE_C = "C:"


def drive_of(path: Path) -> str:
    drive, _ = os.path.splitdrive(str(Path(path).resolve()))
    return (drive or "?").upper()


def free_gib(path: Path) -> float:
    """Free space at ``path``; a not-yet-created temp root measures its
    nearest existing ancestor (Windows disk_usage refuses missing paths)."""
    probe = Path(path).resolve()
    while not probe.exists() and probe.parent != probe:
        probe = probe.parent
    usage = shutil.disk_usage(str(probe))
    return usage.free / float(1024 ** 3)


def resolve_temp_root(cli_value: str | None, extracted_root: Path) -> Path:
    """Precedence chain (S0): --temp-root > TPC_MEDIA_TMP > TPC_TEMP_ROOT >
    `<extracted-root>/.tmp-stage11`."""
    raw = cli_value or os.environ.get("TPC_MEDIA_TMP") \
        or os.environ.get("TPC_TEMP_ROOT")
    if raw:
        return Path(raw).resolve()
    return (Path(extracted_root) / ".tmp-stage11").resolve()


TEMP_LEVER_TEXT = (
    "temp leg lever: set TPC_MEDIA_TMP=D:\\… (or TPC_TEMP_ROOT) — a C: "
    "temp root is not runnable, by contract (no override flag exists)")
OUTPUT_LEVER_TEXT = (
    "output leg lever: set TPC_EXTRACTED_ROOT=D:\\… (piece-01 §1 knob) or "
    "free space on the output drive")


def s0_preflight(temp_root: Path, output_root: Path) -> dict:
    """Measure + GATE. Refusals are exit 3 naming the resolved path, the
    measured numbers, and the RIGHT dial per leg (F10: on this host EITHER
    refusal may fire first)."""
    readings = {
        "tempRoot": str(temp_root),
        "tempRootDrive": drive_of(temp_root),
        "outputRootDrive": drive_of(output_root),
        "tempFreeGiB": round(free_gib(temp_root), 3),
        "outputFreeGiB": round(free_gib(output_root), 3),
    }
    if readings["tempRootDrive"] == DRIVE_C:
        raise MediaError(
            f"S0 hard gate: resolved temp root sits on C: "
            f"({readings['tempRoot']}). {TEMP_LEVER_TEXT}. "
            f"(output leg lever, if needed instead: {OUTPUT_LEVER_TEXT})",
            exit_code=3)
    if readings["tempFreeGiB"] < TEMP_FLOOR_GIB:
        raise MediaError(
            f"S0 floor unmet: temp root {readings['tempRoot']} has "
            f"{readings['tempFreeGiB']} GiB free < {TEMP_FLOOR_GIB} GiB "
            f"required. {TEMP_LEVER_TEXT}", exit_code=3)
    if readings["outputFreeGiB"] < OUTPUT_FLOOR_GIB:
        raise MediaError(
            f"S0 floor unmet: output root drive "
            f"{readings['outputRootDrive']} has "
            f"{readings['outputFreeGiB']} GiB free < {OUTPUT_FLOOR_GIB} GiB "
            f"required. {OUTPUT_LEVER_TEXT}", exit_code=3)
    return readings


# ---------------------------------------------------------------------------
# MEDIA-EXPORT.md — THE tracked artifact (self-sufficient per §4 Ownership)

def render_media_export_md(ctx: dict) -> str:
    """Deterministic markdown: buildId header, encoder pins, per-kind/
    per-plane counts + bytes, ledger sizes WITH their full enums, ROW SCHEMA
    of every local artifact (key sets + sort keys), a hash SUMMARY
    (per-artifact sha256 + row/file counts), and the crosscheck verdict.
    NO timestamps — two builds of the same tree are byte-equal (AC5)."""
    ledgers = ctx["ledgers"]
    lines: list[str] = []
    ap = lines.append
    ap("# Media Export (stage 11 — piece-06)")
    ap("")
    ap(f"- buildId: **{ctx['buildId']}**")
    ap(f"- generated by: `tools/stage11_media.py` + `tools/media_util.py` "
       "(tracked layer of `extracted/media/`; every other path in this tree "
       "is gitignored-local by the standing `extracted/**` rule — no "
       "`.gitignore` edit was made or permitted)")
    ap(f"- coverage: entity-referenced icon set (E1+E2) · UI-chrome atlas "
       f"crops {'ON (--include-ui-chrome)' if ctx.get('uiChrome') else 'OFF (default; flag-gated)'}"
       f" · course carrier probe "
       f"{'ON (--probe-course-carrier, report-only)' if ctx.get('courseProbe') else 'OFF (default; ruling R3)'}")
    ap("- provenance class: repo/data plane only (AGENTS rule 3); user "
       "surfaces carry buildId + coverage scope exclusively")
    ap("")
    ap("## Encoder pins")
    ap("")
    env = ctx["env"]
    ap(f"- pillow: {env['pillowVersion']} · libwebp: "
       f"{env['webpFeatureVersion']} · WebP lossy quality: "
       f"{WEBP_QUALITY} · PNG twins: max-dim <= {PNG_TWIN_MAX_DIM}px or "
       f"alpha-roundtrip |delta| > {ALPHA_TOLERANCE}/255")
    ap(f"- UnityPy fallback version seeded for bundles with `0.0.0` headers: "
       f"{env.get('fallbackUnityVersion', 'n/a')} · fallback-seeded bundle "
       f"opens this run: {env.get('fallbackVersionUsedBundles', 0)}")
    ap("- byte-identity comparisons are scoped to SAME-ENVIRONMENT reruns "
       "(piece-01 §4 determinism note)")
    ap("")
    ap("## Counts")
    ap("")
    for k, v in sorted(ctx["counters"].items()):
        ap(f"- {k}: {v}")
    ap("")
    planes = ctx.get("planes") or {}
    if planes:
        ap("### Per-plane files + bytes (web/)")
        ap("")
        ap("| plane | files | bytes |")
        ap("|---|---|---|")
        for plane in sorted(planes):
            st = planes[plane]
            ap(f"| {plane} | {st['files']} | {st['bytes']} |")
        ap("")
    kinds = ctx.get("perKindIndexRows") or {}
    if kinds:
        ap("### index.jsonl rows per kind")
        ap("")
        for kind in sorted(kinds):
            ap(f"- {kind}: {kinds[kind]}")
        ap("")
    ap("## Ledgers (sizes + FULL enums)")
    ap("")
    ap("### `_missing_icons.jsonl` — " + str(ledgers["missing"]) + " rows")
    ap("- complete frozen reason enum: " +
       ", ".join("`%s`" % r for r in MISSING_REASONS) +
       " (`uncategorized-reason` = escape, always DRIFT-accompanied, feeds "
       "exit 2 never exit 1 — binding pin P2)")
    ap("")
    ap("### `_pptr_residue.jsonl` — " + str(ledgers["residue"]) + " rows")
    ap("- basis literal on every row: `" + RESIDUE_BASIS + "`")
    ap("- slotClass enum: " + ", ".join("`%s`" % s for s in SLOT_CLASSES) +
       "; targetResolution enum: " +
       ", ".join("`%s`" % t for t in TARGET_RESOLUTIONS) +
       "; escape for out-of-enum values on THIS ledger: "
       "`uncategorized-slot` (pin P2)")
    ap("")
    ap("### `_skipped_classes.jsonl` — " + str(ledgers["skipped"]) + " rows")
    ap("- skip policies as rows (census carve-outs; fonts out of scope)")
    ap("")
    ap("## Row schemas of every local (gitignored-local) artifact")
    ap("")
    ap("| artifact | key set (frozen) | sort key |")
    ap("|---|---|---|")
    ap("| export-manifest.jsonl | " +
       ", ".join(sorted(MANIFEST_KEYS)) +
       " (source adds atlas keys when atlas-routed) | outRelPath |")
    ap("| index.jsonl | " + ", ".join(sorted(INDEX_KEYS)) +
       " | (kind, srcId, fieldPath) |")
    ap("| _missing_icons.jsonl | " + ", ".join(sorted(MISSING_KEYS)) +
       " | (subObjectName, reason, assetGuid) |")
    ap("| _pptr_residue.jsonl | " + ", ".join(sorted(RESIDUE_KEYS)) +
       " | (kind, srcId, fieldPath) |")
    ap("| _skipped_classes.jsonl | " + ", ".join(sorted(SKIPPED_KEYS)) +
       " | class |")
    ap("| hashes.sha256 | `<sha256>  <relpath>` LF | relpath |")
    ap("| crosscheck-report.json | sample[], rates, cli stamps | — |")
    ap("")
    ap("## Hash summary (drift detection between clones without shipping bytes)")
    ap("")
    ap("| artifact | sha256 | rows/files |")
    ap("|---|---|---|")
    for ent in ctx["hashSummary"]:
        ap(f"| {ent['artifact']} | `{ent['sha256']}` | {ent['count']} |")
    ap("")
    cc = ctx.get("crosscheck") or {}
    ap("## Cross-check verdict (AssetStudioModCLI lane)")
    ap("")
    if cc.get("ran"):
        ap(f"- cliVersion: {cc.get('cliVersion')} · cliUnityVersion: "
           f"{cc.get('cliUnityVersion')} · cliExportFormat: "
           f"{cc.get('cliExportFormat')} (LOSSLESS pin P3)")
        ap(f"- sample: {cc.get('sample')} · pixelMatchRate: "
           f"{cc.get('pixelMatchRate')} · maxDelta: {cc.get('maxDelta')}")
        ap(f"- verdict: **{'PASS' if cc.get('pass') else 'FAIL'}**")
    else:
        ap("- lane did not run in this invocation: " +
           str(cc.get("reason", "n/a")))
    ap("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Small shared IO helpers

def read_jsonl_rows(path: Path, required: bool = True) -> list[dict]:
    if not path.is_file():
        if required:
            raise MediaError(f"missing upstream artifact {path}",
                             exit_code=3)
        return []
    rows = []
    with open(path, "r", encoding="utf-8", newline="\n") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_container_index(extracted_root: Path) -> dict[str, list[dict]]:
    path = extracted_root / "relinks" / "bridges" / "container_index.jsonl"
    idx: dict[str, list[dict]] = {}
    for row in read_jsonl_rows(path):
        idx.setdefault(str(row.get("address")), []).append({
            "bundle": row.get("bundle"),
            "class": row.get("class"),
            "pathId": int(row.get("pathId") or 0),
        })
    for addr in idx:
        idx[addr].sort(key=lambda r: (r["bundle"], r["pathId"]))
    return idx


def load_catalog_guid_index(catalog_path: Path) -> dict[str, list[dict]]:
    data = json.loads(catalog_path.read_text(encoding="utf-8"))
    idx: dict[str, list[dict]] = {}
    for key in data.get("keys") or []:
        if key.get("kind") != "guid":
            continue
        idx.setdefault(str(key["key"]), []).append({
            "address": key.get("address"),
            "bundle": key.get("bundle"),
        })
    return idx


def load_sprite_name_index(media_catalogue: Path) -> dict[str, list[dict]]:
    """media-catalogue Sprite rows keyed by name — the RESOLUTION surface of
    the pinned predicate (name presence among catalogue Sprite rows)."""
    idx: dict[str, list[dict]] = {}
    for row in read_jsonl_rows(media_catalogue):
        if row.get("class") != "Sprite":
            continue
        idx.setdefault(str(row.get("name")), []).append({
            "bundle": row.get("bundle"),
            "pathId": int(row.get("pathId") or 0),
            "contentAxis": row.get("contentAxis"),
        })
    for name in idx:
        idx[name].sort(key=lambda r: (r["bundle"], r["pathId"]))
    return idx


def load_cab_index(extracted_root: Path) -> dict[str, dict]:
    """cab name → {bundle, objects:{pathId: class}} — offline cross-bundle
    pointer resolution for direct-pointer sprites and the E6 classifier."""
    path = extracted_root / "relinks" / "bridges" / "cab_index.jsonl"
    idx: dict[str, dict] = {}
    for row in read_jsonl_rows(path):
        cab = str(row.get("cab") or "").lower()
        objs = {int(o["pathId"]): o.get("class")
                for o in row.get("objects") or []}
        cur = idx.setdefault(cab, {"bundle": row.get("bundle"),
                                   "objects": {}})
        cur["objects"].update(objs)
    return idx


def load_externals_index(harvest_externals: Path) -> dict[str, dict[int, str]]:
    """bundle rel → {fileId: cab-name-lowercased} from the stage-3 harvest."""
    idx: dict[str, dict[int, str]] = {}
    for row in read_jsonl_rows(harvest_externals):
        table: dict[int, str] = {}
        for ext in row.get("externals") or []:
            path_str = str(ext.get("path") or "")
            cab = simplify_external_path(path_str)
            if cab:
                table[int(ext.get("fileId") or 0)] = cab
        idx[str(row.get("bundle"))] = table
    return idx


def simplify_external_path(path: str) -> str:
    p = str(path).replace("\\", "/")
    if p.startswith("archive:/"):
        p = p[len("archive:/"):]
    if p.startswith("assets/"):
        p = p[len("assets/"):]
    return p.rsplit("/", 1)[-1].lower()
