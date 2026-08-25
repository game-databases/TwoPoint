#!/usr/bin/env python3
"""Shared constants, path resolution and small parsers for the Two Point
Campus piece-1 extraction pipeline.

Every stage script imports this module; the entrypoint (run_all.py) does
too. Facts pinned here come from docs/specs/piece-01-extraction-pipeline.mdx
(the binding spec, incl. Revision 2), toolchain.md and data-acquisition.md.

No machine paths are hardcoded: staged-tool candidates are repo-relative
and resolve against the repo root (the parent of the pack dir); the one
absolute fallback below is the spec-pinned second copy of Il2CppDumper.
"""
from __future__ import annotations

import json
import os
import re
import struct
from pathlib import Path


class StageError(Exception):
    """Stage abort with a specific process exit code.

    Codes follow the spec §4 exit-code contract:
      0 success · 1 stage failure · 2 completed-with-ledger ·
      3 environment/gate refusal.
    """

    def __init__(self, message: str, exit_code: int = 1):
        super().__init__(message)
        self.exit_code = int(exit_code)


# ---------------------------------------------------------------------------
# Client identity pins (measured 2026-08-24 — data-acquisition.md §Client)

APPID = 1649080
BUILD_ID = 20226581  # = TargetBuildID at measurement; re-measured every run
EXPECTED_BUNDLES = {"aa": 158, "dlc-space": 10, "dlc-ghost": 8}
EXPECTED_LOCALE_ROWS = 14  # unnamed base overlay + 13 named languages
METADATA_SANITY = 0xFAB11BAF
METADATA_VERSION_WALL = 38  # >= this → Cpp2IL escalation gate, never attempted here
CPP2IL_ESCALATION_MESSAGE = (
    "metadata version >= 38 exceeds the staged dumper's supported range "
    "(KB does-not-work/il2cppdumper-new-metadata.md). Escalation is a "
    "declared manual step: `dotnet publish` on tools/Cpp2IL per "
    "toolchain.md section 'Primary dumper decision', version selected "
    "against the measured metadata version, result pinned in "
    "EXTRACTION-LOG.md. This pipeline never auto-builds Cpp2IL."
)

# Content-axis vocabulary — THE one emitted enum for every piece-1 artifact
# (Revision 2 / R5). spec.md's site-plane `dlc1-space`/`dlc2-ghost` map onto
# `dlc-space`/`dlc-ghost` at the site layer.
AXIS_BASE = "base"
AXIS_DLC_SPACE = "dlc-space"
AXIS_DLC_GHOST = "dlc-ghost"
CONTENT_AXES = (AXIS_BASE, AXIS_DLC_SPACE, AXIS_DLC_GHOST)
DIR_CLASSES = CONTENT_AXES  # roster dirClass uses the same enum (R5)

# Stage 4 BCP-47 table — fixed, from the verified scout inventory. The set
# of EMITTED locale files must equal EMITTED_LOCALES character-for-character.
EMITTED_LOCALES = [
    "en", "pt-BR", "zh-Hans", "zh-Hant", "fr", "de",
    "it", "ja", "ko", "pl", "ru", "es", "tr",
]
LOCALE_SUFFIX_TABLE = {
    "": "base",  # unnamed base overlay bundle (never a 14th locale)
    "english": "en",
    "brazilianportuguese": "pt-BR",
    "chinese(simplified)": "zh-Hans",
    "chinese(traditional)": "zh-Hant",
    "french": "fr",
    "german": "de",
    "italian": "it",
    "japanese": "ja",
    "korean": "ko",
    "polish": "pl",
    "russian": "ru",
    "spanish": "es",
    "turkish": "tr",
}
LOCALE_BUNDLE_STEM_PREFIX = "localisation_assets_localisation"
BASE_OVERLAY_NAME = "base"  # roster localeFlag value for the unnamed bundle

# Stage 3 media carve-out [DR-2026-08-18-media-scope] + arbiter-001 R1:
# these classes get catalogue rows ONLY (zero decoded bytes under
# extracted/ in piece 1). Texture2D/Sprite are catalogue-only too.
CARVE_OUT_CLASSES = frozenset({
    "Texture2D", "Texture3D", "Sprite", "SpriteAtlas",
    "AudioClip", "VideoClip", "Mesh", "AnimationClip",
    "Shader", "Font",
})

MEDIA_EXTENSIONS_RE = re.compile(
    r"\.(ogg|wav|mp3|bnk|fsb|mp4|usm|bk2|png|jpg|jpeg|tga|dds|bmp|exr)\b",
    re.IGNORECASE,
)

# UnityPy pin — embedded fallback for the EXTRACTION-LOG stage-defaults block.
UNITYPY_PIN = "1.25.3"

# Staged Il2CppDumper candidates, first existing wins. Repo-relative entries
# resolve against the REPO ROOT (no ../ prefixes — they must name paths
# inside this repo). Order: measured-on-disk staged copy first, then the two
# other in-repo copies, then the spec-pinned D:\ absolute fallback.
IL2CPP_DUMPER_CANDIDATES = [
    "zero-parades/work/_tooling/il2cppdumper/Il2CppDumper.exe",
    "disco-elysium/zero-parades/work/_tooling/il2cppdumper/Il2CppDumper.exe",
    "disco-elysium/tools/Il2CppDumper/Il2CppDumper.exe",
    "D:\\unpacked_game_data\\albion-online\\_tooling\\il2cppdumper\\Il2CppDumper.exe",
]
VENDORED_UNITYPY_CANDIDATES = ["../tools/UnityPy"]

STAGES = [
    ("verify-client", "tools/stage0_verify_client.py",
     ["stage0_verify_client.py", "tpc_common.py", "log_util.py"]),
    ("decompile", "tools/stage1_decompile.py",
     ["stage1_decompile.py", "build_structural.py", "ilmetadata.py",
      "tpc_common.py", "log_util.py"]),
    ("harvest-catalog", "tools/stage2_harvest_catalog.py",
     ["stage2_harvest_catalog.py", "aa_catalog.py", "unitypy_util.py",
      "tpc_common.py", "log_util.py"]),
    ("harvest-bundles", "tools/stage3_harvest_bundles.py",
     ["stage3_harvest_bundles.py", "aa_catalog.py", "unitypy_util.py",
      "tpc_common.py", "log_util.py"]),
    ("localisation", "tools/stage4_localisation.py",
     ["stage4_localisation.py", "unitypy_util.py",
      "tpc_common.py", "log_util.py"]),
    ("emit-stub-datasets", "tools/stage5_emit_stubs.py",
     ["stage5_emit_stubs.py", "unitypy_util.py",
      "tpc_common.py", "log_util.py"]),
    # piece-02 relinking stage (piece-01 Revision 7 §5.1: seventh stage,
    # registered ADDITIVELY — stages 0–5 byte-behave identically)
    ("relink", "tools/stage6_relink.py",
     ["stage6_relink.py", "relink_util.py", "tpc_common.py", "log_util.py"]),
]
STAGE_IDS = [sid for sid, _script, _deps in STAGES]


# ---------------------------------------------------------------------------
# Path resolution

def resolve_pack_dir() -> Path:
    env = os.environ.get("TPC_PACK_DIR")
    if env:
        return Path(env).resolve()
    return Path(__file__).resolve().parent.parent


def resolve_repo_root(pack_dir: Path) -> Path:
    return pack_dir.parent


def resolve_extracted_root(pack_dir: Path) -> Path:
    """Extraction root: <pack>/extracted unless TPC_EXTRACTED_ROOT redirects
    it (tens-of-GB writes prefer D:/A: per toolchain.md host realities).
    Every 'extracted/…' path in the spec is relative to this root."""
    env = os.environ.get("TPC_EXTRACTED_ROOT")
    if env:
        return Path(env).resolve()
    return (pack_dir / "extracted").resolve()


def _looks_like_install_root(p: Path) -> bool:
    return (
        (p / "GameAssembly.dll").is_file()
        and (p / "TPC_Data" / "il2cpp_data" / "Metadata" / "global-metadata.dat").is_file()
        and (p / "TPC_Data" / "StreamingAssets" / "aa").is_dir()
    )


def _looks_like_tpc_data(p: Path) -> bool:
    return (
        p.name == "TPC_Data"
        and (p / "il2cpp_data" / "Metadata" / "global-metadata.dat").is_file()
        and (p / "StreamingAssets" / "aa").is_dir()
    )


def resolve_game_root(cli_arg: str | None) -> Path:
    """Install root from CLI arg or TPC_GAME_DIR; accepts the install root
    itself or its TPC_Data child (auto-detected)."""
    raw = cli_arg or os.environ.get("TPC_GAME_DIR")
    if not raw:
        raise StageError(
            "no game directory given: pass the install root as the "
            "positional argument or set TPC_GAME_DIR", exit_code=3)
    p = Path(raw).resolve()
    if _looks_like_install_root(p):
        return p
    if _looks_like_tpc_data(p):
        return p.parent
    raise StageError(
        f"'{raw}' does not look like a Two Point Campus install: need "
        "GameAssembly.dll + TPC_Data/il2cpp_data/Metadata/global-metadata.dat "
        "+ TPC_Data/StreamingAssets/aa (install root or TPC_Data accepted)",
        exit_code=3)


def game_paths(game_root: Path) -> dict[str, Path]:
    data = game_root / "TPC_Data"
    aa = data / "StreamingAssets" / "aa"
    return {
        "root": game_root,
        "data": data,
        "game_assembly": game_root / "GameAssembly.dll",
        "metadata": data / "il2cpp_data" / "Metadata" / "global-metadata.dat",
        "scripting_assemblies": data / "ScriptingAssemblies.json",
        "globalgamemanagers": data / "globalgamemanagers",
        "version_txt": game_root / "version.txt",
        "appinfo": data / "app.info",
        "aa": aa,
        "settings_json": aa / "settings.json",
        "catalog_bundle": aa / "catalog.bundle",
        "aa_bundles": aa / "StandaloneWindows64",
        "dlc_space": game_root / "DLCs" / "space",
        "dlc_ghost": game_root / "DLCs" / "ghost",
    }


def find_appmanifest(game_root: Path) -> Path | None:
    """Walk up <=4 levels looking for appmanifest_1649080.acf (steamapps)."""
    probe = game_root
    for _ in range(4):
        cand = probe / "appmanifest_1649080.acf"
        if cand.is_file():
            return cand
        if probe.parent == probe:
            break
        probe = probe.parent
    return None


# ---------------------------------------------------------------------------
# Small client-file parsers (pure functions over text/bytes — fixture-testable)

_ACF_TOKEN_RE = re.compile(r'"((?:[^"\\]|\\.)*)"|\{|\}')


def parse_acf(text: str) -> dict:
    """Minimal Steam appmanifest (ACF) parser → nested dicts of quoted keys.
    Tolerates the two `language` occurrences; callers take the first."""
    pos = 0
    n = len(text)

    def skip_ws(i: int) -> int:
        while i < n and text[i] in " \t\r\n":
            i += 1
        return i

    def parse_value(i: int):
        i = skip_ws(i)
        if i >= n:
            return None, i
        if text[i] == "{":
            obj: dict = {}
            i += 1
            while True:
                i = skip_ws(i)
                if i >= n or text[i] == "}":
                    return obj, i + 1
                key, i = parse_value(i)
                val, i = parse_value(i)
                obj[str(key)] = val
        m = _ACF_TOKEN_RE.match(text, i)
        if m and m.group(1) is not None:
            return m.group(1), m.end()
        return None, i + 1

    top: dict = {}
    while True:
        pos = skip_ws(pos)
        if pos >= n or text[pos] == "}":
            break
        key, pos = parse_value(pos)
        val, pos = parse_value(pos)
        if key is not None:
            top[str(key)] = val
    return top


def read_unity_version(globalgamemanagers_path: Path) -> str:
    """Unity ASCII version string near offset 0x30 of globalgamemanagers."""
    data = globalgamemanagers_path.read_bytes()[:256]
    m = re.search(rb"\b(\d{4}\.\d+\.\d+[fpab]\d+)\b", data)
    if not m:
        raise StageError(
            f"no Unity version string found in {globalgamemanagers_path}",
            exit_code=3)
    return m.group(1).decode("ascii")


def read_metadata_header(metadata_path: Path) -> tuple[int, int]:
    """(sanity word, metadata version) — int32 LE @ offsets 0 and 4."""
    head = metadata_path.read_bytes()[:8]
    if len(head) < 8:
        raise StageError(f"{metadata_path} too small for an IL2CPP metadata header",
                         exit_code=3)
    sanity, version = struct.unpack("<Ii", head)
    return sanity, version


# ---------------------------------------------------------------------------
# Harvest filename contract (spec §3 stage 3, Revision 6)

# Every harvest filename embeds `<bundle-stem>_<signed-int64 pathId>`:
# path_ids are int64 and NEGATIVE on this client (60,582 of 167,069 manifest
# rows measured), so the embedded spelling carries an optional leading `-`.
# EVERY stem parser — stage-5 loaders AND checkers alike — accepts the sign
# through this one helper.
_HARVEST_STEM_RE = re.compile(r"^(?P<base>.+)_(?P<pid>-?\d+)$")
_HARVEST_EXT_RE = re.compile(r"\.[A-Za-z0-9]{1,5}$")


def parse_harvest_stem(name: str) -> tuple[str, int] | None:
    """`<bundle-stem>_<signed-int64 pathId>[.<ext>]` → (bundle-stem,
    path_id); None when no trailing signed decimal is present.

    The optional `-` belongs to the path_id (Rev 6). A trailing file
    extension (`.json`, `.txt`, …) is stripped first when present; a bundle
    stem that itself ends in `_<digits>` parses correctly because the
    greedy base group always takes the LAST `_`-separated decimal."""
    s = str(name)
    m = _HARVEST_EXT_RE.search(s)
    if m and m.end() == len(s):
        sm = _HARVEST_STEM_RE.match(s[: m.start()])
        if sm is not None:
            return sm.group("base"), int(sm.group("pid"))
    sm = _HARVEST_STEM_RE.match(s)
    if sm is not None:
        return sm.group("base"), int(sm.group("pid"))
    return None


def axis_for_bundle_name(bundle_name: str) -> str:
    """Content axis from a bundle FILENAME alone (stage-5 side has no roster):
    DLC bundles carry the axis as their filename tag (`dlc-space-…`,
    `dlc-ghost-…`); everything else is `base` — the ONE emitted enum."""
    stem = bundle_name[:-len(".bundle")] \
        if bundle_name.endswith(".bundle") else bundle_name
    for axis in (AXIS_DLC_SPACE, AXIS_DLC_GHOST):
        if stem.startswith(axis + "-"):
            return axis
    return AXIS_BASE


# ---------------------------------------------------------------------------
# Roster classification helpers

def locale_for_bundle(bundle_name: str) -> str | None:
    """localeFlag value for a bundle basename: None when not a localisation
    bundle; 'base' for the unnamed overlay; else the BCP-47 code."""
    stem = bundle_name[:-len(".bundle")] if bundle_name.endswith(".bundle") else bundle_name
    if stem == LOCALE_BUNDLE_STEM_PREFIX:
        return BASE_OVERLAY_NAME
    if stem.startswith(LOCALE_BUNDLE_STEM_PREFIX):
        # the separator `_` is not part of the table's keys ("english", not
        # "_english") — strip it before lookup
        suffix = stem[len(LOCALE_BUNDLE_STEM_PREFIX):].lower().lstrip("_")
        locale = LOCALE_SUFFIX_TABLE.get(suffix)
        if locale is None:
            # unknown language suffix — surface it verbatim as its own flag so
            # drift is visible rather than silently unflagged
            return f"unknown:{suffix}"
        return locale
    return None


_SEASONAL_SCENE_RE = re.compile(r"^scenes-seasonalcontent_scenes")


def scene_flag_for(bundle_name: str) -> str:
    """'none' | '.unity' | 'seasonal-scenes'. Seasonal nuance: the seasonal
    scene bundle carries scenes WITHOUT a .unity suffix, while
    items-seasonalcontent_* carries no scenes."""
    stem = bundle_name[:-len(".bundle")] if bundle_name.endswith(".bundle") else bundle_name
    if stem.endswith(".unity"):
        return ".unity"
    if _SEASONAL_SCENE_RE.match(stem):
        return "seasonal-scenes"
    return "none"


_HASH_PREFIX_RE = re.compile(r"^([0-9a-f]{16,})_(.+)$")
_FAMILY_SUFFIXES = ("_optimised.unity", ".unity", "_assets_all", "_all")


def split_family(bundle_name: str, dir_class: str) -> tuple[str, str, bool]:
    """Bundle filename → (family, contentAxis, hashNamed).

    Family rule (spec §3 stage 3): strip trailing _assets_all /
    _optimised.unity / .unity shapes and the leading dlc-{space,ghost}- tag;
    hash-prefixed bundles keep the suffix after the hex prefix and flag
    hashNamed:true. dir_class is the ONE axis source (roster dirClass)."""
    stem = bundle_name[:-len(".bundle")] if bundle_name.endswith(".bundle") else bundle_name
    axis = dir_class if dir_class in CONTENT_AXES else AXIS_BASE
    if axis != AXIS_BASE and stem.startswith(f"{axis}-"):
        stem = stem[len(axis) + 1:]
    hash_named = False
    m = _HASH_PREFIX_RE.match(stem)
    if m:
        stem, hash_named = m.group(2), True
    for suf in _FAMILY_SUFFIXES:
        if stem.endswith(suf) and len(stem) > len(suf):
            stem = stem[: -len(suf)]
            break
    return stem, axis, hash_named


def normalize_ref(ref: str) -> str:
    """MATCH KEY normalization (spec §3 stage 2 acceptance): catalog bundle
    references AND roster relpaths both normalize to case-folded basenames
    after stripping directory/provider-prefix segments.

    Braced spellings resolve deterministically by what follows the closing
    brace: `…}.bundle` / `…}.json` / `…}?…` means the braces wrap the NAME
    (the Addressables hash-form `{hash}.bundle`) — content kept; anything
    else after `}` means the braces wrap a provider/scheme PREFIX
    (`{RSC}name…`) — the braced segment is stripped."""
    s = str(ref).replace("\\", "/")
    s = s.rsplit("/", 1)[-1]          # directory segments
    while s.startswith("{"):
        close = s.find("}")
        if close < 0:                 # malformed — drop braces wholesale
            s = s.replace("{", "").replace("}", "")
            break
        head, tail = s[1:close], s[close + 1:]
        if not tail or tail[0] in ".?":
            s = head                  # braces wrapped the name itself
            break
        s = tail                      # braces wrapped a scheme prefix
    s = s.replace("{", "").replace("}", "")
    if "?" in s:
        s = s.split("?", 1)[0]
    s = s.casefold()
    if s.endswith(".bundle"):
        s = s[: -len(".bundle")]
    return s


# Revision 5 hash-suffix match mapping: catalog references may spell a roster
# bundle with a trailing `_<32-hex>` content hash the on-disk filename does
# not carry (measured real forms:
#   ui-art-mainmenu_assets_all_3053e16d….bundle,
#   localisation_assets_localisationturkish_5e018e92….bundle).
# Applied to the NORMALIZED key (post-`normalize_ref`, so case-folded and
# extension-stripped); stripping reuses the normal match key.
_HASH_SUFFIX_RE = re.compile(r"^(.+)_[0-9a-f]{32}$", re.IGNORECASE)


def strip_hash_suffix(norm_key: str) -> str | None:
    """`<name>_<32-hex>` → `<name>`, else None. Input must already be a
    normalized match key (`normalize_ref` output)."""
    m = _HASH_SUFFIX_RE.match(norm_key or "")
    return m.group(1) if m else None


def resolve_file_form_reference(ref: str, norm_to_relpath: dict[str, str],
                                ) -> tuple[str | None, str | None, str]:
    """FILE-FORM reference resolution ladder (Revision 5): normalize the raw
    spelling, then match a roster relpath directly, then via hash-suffix
    stripping. Returns (match_kind, relpath, normalized_key) where
    match_kind is 'direct' | 'hash-suffix' | None."""
    norm = normalize_ref(ref)
    rel = norm_to_relpath.get(norm)
    if rel is not None:
        return "direct", rel, norm
    stripped = strip_hash_suffix(norm)
    if stripped is not None:
        rel = norm_to_relpath.get(stripped)
        if rel is not None:
            return "hash-suffix", rel, norm
    return None, None, norm


# ---------------------------------------------------------------------------
# Roster IO

def load_roster(extracted_root: Path) -> list[dict]:
    path = extracted_root / "bundle-roster.jsonl"
    if not path.is_file():
        raise StageError(
            f"missing upstream artifact {path} — run the verify-client stage "
            "first (--only verify-client)", exit_code=3)
    rows = []
    with open(path, "r", encoding="utf-8", newline="\n") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    if not rows:
        raise StageError(f"{path} holds no roster rows", exit_code=3)
    return rows


def roster_locale_rows(rows: list[dict]) -> list[dict]:
    return [r for r in rows if r.get("localeFlag")]


def enumerate_bundle_files(paths: dict) -> list[tuple[str, str, Path]]:
    """(relpath, dirClass, absolute path) for every *.bundle under the three
    corpus dirs — sorted by relpath for determinism."""
    out: list[tuple[str, str, Path]] = []
    pairs = [
        (paths["root"], "base", [paths["aa_bundles"]]),
        (paths["root"], AXIS_DLC_SPACE, [paths["dlc_space"]]),
        (paths["root"], AXIS_DLC_GHOST, [paths["dlc_ghost"]]),
    ]
    for root, cls, dirs in pairs:
        for d in dirs:
            if not d.is_dir():
                continue
            for child in sorted(d.iterdir()):
                if child.is_file() and child.name.endswith(".bundle"):
                    rel = child.relative_to(root).as_posix()
                    out.append((rel, cls, child))
    out.sort(key=lambda t: t[0])
    return out
