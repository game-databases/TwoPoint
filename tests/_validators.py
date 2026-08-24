"""Contract constants + schema validators for the TwoPoint piece-1 test suite.

Every pin here is lifted from docs/specs/piece-01-extraction-pipeline.mdx
(Revision 2). These helpers are TEST-ONLY: they validate emitted artifacts
and fixture shapes; they never import the implementation.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

# --- pins (spec §2/§3/§5) ----------------------------------------------------

BUILD_ID = 20226581
TARGET_BUILD_ID = 20226581
APPID = 1649080
VERSION_STRING = "10.3.169253+2024-12-06.1241"
UNITY_VERSION = "2020.3.47f1"
METADATA_SANITY = 0xFAB11BAF
METADATA_VERSION = 27
ADDRESSABLES_VERSION = "1.21.10"
SETTINGS_HASH = "ff59c4d7914829f354d3efeefc3819f0"

EXPECTED_BUNDLES = {"aa": 158, "dlc-space": 10, "dlc-ghost": 8}
TOTAL_BUNDLES = 176
LOCALE_BUNDLE_COUNT = 14

# spec §3 stage 0 identity.json sceneCounts pins (measured install)
SCENE_COUNT_PINS = {
    "strictUnityBase": 21,
    "seasonalSceneCarryingBase": 22,
    "strictUnityInstall": 25,
    "sceneCarryingInstall": 26,
}

CONTENT_AXES = ("base", "dlc-space", "dlc-ghost")
SCENE_FLAGS = ("none", ".unity", "seasonal-scenes")

# spec §3 stage 4 BCP-47 table — 13 exact mappings (character-exact)
LOCALE_TABLE = {
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
BASE_OVERLAY_NAME = "base-overlay"
COMPOSITION_POLICIES = (
    "english-only",
    "english-over-base",
    "base-over-english",
    "mixed",
)

# spec §3 stage 5 kind value ↔ filename map (9 kinds, pinned exactly)
KIND_TO_FILE = {
    "item": "items.jsonl",
    "unlockable": "unlockables.jsonl",
    "room": "rooms.jsonl",
    "campus-level": "campus-levels.jsonl",
    "course": "courses.jsonl",
    "config": "configs.jsonl",
    "staff": "staff.jsonl",
    "metagame-node": "metagame-nodes.jsonl",
    "student-type": "student-types.jsonl",
}

# spec §5 criterion 6 carve-out guard extensions:
# 8 audio/video + 7 image = 15 total (regex verbatim from the spec).
MEDIA_EXTENSIONS_AUDIO_VIDEO = ("ogg", "wav", "mp3", "bnk", "fsb", "mp4", "usm", "bk2")
MEDIA_EXTENSIONS_IMAGE = ("png", "jpg", "jpeg", "tga", "dds", "bmp", "exr")
MEDIA_EXTENSION_RE = re.compile(
    r"\.(?:" + "|".join(MEDIA_EXTENSIONS_AUDIO_VIDEO + MEDIA_EXTENSIONS_IMAGE) + r")",
    re.IGNORECASE,
)
# files whose *content* legitimately mentions media extensions (the catalogue itself)
MEDIA_GUARD_ALLOW = {"media-catalogue.jsonl", "media-catalogue.jsonl.tmp", "MEDIA-CATALOGUE.md"}

# spec §4 determinism: byte-identity comparisons exclude these
BYTE_IDENTITY_EXEMPT = {"EXTRACTION-LOG.md", ".stage-stamps", ".pipeline-meta.json"}

STAGE_IDS = (
    "verify-client",
    "decompile",
    "harvest-catalog",
    "harvest-bundles",
    "localisation",
    "emit-stub-datasets",
)


# --- JSONL discipline ---------------------------------------------------------

def write_jsonl(path: Path, rows) -> Path:
    """Spec write discipline: utf-8, newline='\n', sorted keys."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return path


def read_jsonl(path: Path):
    rows = []
    with open(path, "r", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{lineno}: invalid JSONL: {exc}") from exc
    return rows


def read_json(path: Path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def assert_jsonl_roundtrip(tmp_path: Path, rows, name="roundtrip.jsonl") -> None:
    """Stage-4 obligation: JSONL round-trip under the pinned write discipline."""
    p = write_jsonl(Path(tmp_path) / name, rows)
    raw = p.read_bytes()
    assert b"\r" not in raw, "CR byte in JSONL — newline='\\n' discipline broken"
    assert raw.endswith(b"\n") or not raw, "JSONL must end with a newline"
    back = read_jsonl(p)
    assert back == rows, "JSONL round-trip lost data"


# --- hashing / byte-identity --------------------------------------------------

def hash_tree(root: Path, exempt_byte_identity: bool = True):
    """sha256 manifest of every file under root.

    exempt_byte_identity=True drops EXTRACTION-LOG.md, .stage-stamps/ and
    .pipeline-meta.json per spec §4/§5.5.
    """
    root = Path(root)
    out = {}
    if not root.exists():
        return out
    for p in sorted(root.rglob("*")):
        if p.is_dir():
            continue
        rel = p.relative_to(root).as_posix()
        top = rel.split("/", 1)[0]
        if exempt_byte_identity and (rel in BYTE_IDENTITY_EXAMPT_SET or top in BYTE_IDENTITY_EXAMPT_SET):
            continue
        h = hashlib.sha256()
        with open(p, "rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
        out[rel] = h.hexdigest()
    return out


BYTE_IDENTITY_EXAMPT_SET = set(BYTE_IDENTITY_EXEMPT)


def diff_manifests(a, b):
    only_a = sorted(set(a) - set(b))
    only_b = sorted(set(b) - set(a))
    changed = sorted(k for k in set(a) & set(b) if a[k] != b[k])
    return only_a, only_b, changed


# --- carve-out guard ----------------------------------------------------------

def scan_tree_for_media_extensions(root: Path):
    """Spec §5.6 guard: grep extracted/ for audio/video/image extensions.

    Returns sorted list of hits `relpath:lineno` outside media-catalogue.* .
    """
    root = Path(root)
    hits = []
    if not root.exists():
        return hits
    for p in sorted(root.rglob("*")):
        if p.is_dir() or p.name in MEDIA_GUARD_ALLOW:
            continue
        rel = p.relative_to(root).as_posix()
        # filenames count too (a stray foo.png file is a hit even with no text match)
        for m in MEDIA_EXTENSION_RE.finditer(p.name):
            hits.append(f"{rel}:name:{m.group(0).lower()}")
        try:
            with open(p, "r", encoding="utf-8", errors="ignore") as fh:
                for lineno, line in enumerate(fh, 1):
                    if MEDIA_EXTENSION_RE.search(line):
                        hits.append(f"{rel}:{lineno}")
        except (OSError, ValueError):
            hits.append(f"{rel}:unreadable-as-text")
    return hits


# --- artifact schema validators (return error list; [] == valid) --------------

def _err(errors, msg):
    errors.append(msg)


def validate_roster_row(row, where=""):
    e = []
    if not isinstance(row, dict):
        return [f"{where}row is not an object"]
    for k in ("relpath", "dirClass", "bytes", "sceneFlag", "localeFlag", "buildId"):
        if k not in row:
            _err(e, f"{where}missing key {k!r}")
    if row.get("dirClass") not in CONTENT_AXES:
        _err(e, f"{where}dirClass {row.get('dirClass')!r} not in {CONTENT_AXES}")
    if row.get("sceneFlag") not in SCENE_FLAGS:
        _err(e, f"{where}sceneFlag {row.get('sceneFlag')!r} not in {SCENE_FLAGS}")
    lf = row.get("localeFlag")
    if lf is not None and lf != BASE_OVERLAY_NAME and not isinstance(lf, str):
        _err(e, f"{where}localeFlag must be null|'base'|<bundle-lang>")
    if not isinstance(row.get("bytes"), int) or row.get("bytes", -1) < 0:
        _err(e, f"{where}bytes not a non-negative int")
    if not isinstance(row.get("buildId"), int):
        _err(e, f"{where}buildId not an int")
    return e


def validate_identity(obj):
    e = []
    required = [
        "appid", "buildId", "targetBuildId", "versionString", "unityVersion",
        "metadataVersion", "dumper", "addressablesVersion", "settingsHash",
        "languageSetting", "expectedBundles", "localeBundleCount", "sceneCounts",
    ]
    for k in required:
        if k not in obj:
            _err(e, f"identity.json missing key {k!r}")
    if obj.get("appid") != APPID:
        _err(e, f"identity.appid {obj.get('appid')!r} != {APPID}")
    if obj.get("expectedBundles") != EXPECTED_BUNDLES:
        _err(e, f"identity.expectedBundles {obj.get('expectedBundles')!r} != {EXPECTED_BUNDLES}")
    sc = obj.get("sceneCounts") or {}
    for k in SCENE_COUNT_PINS:
        if k not in sc:
            _err(e, f"identity.sceneCounts missing {k!r}")
    return e


def validate_catalog_json(obj):
    e = []
    meta = obj.get("meta") or {}
    for k in ("buildId", "addressablesVersion", "settingsHash", "providerIds"):
        if k not in meta:
            _err(e, f"catalog.meta missing {k!r}")
    keys = obj.get("keys")
    if not isinstance(keys, list) or not keys:
        return e + ["catalog.keys must be a non-empty list"]
    prev = None
    for i, row in enumerate(keys):
        for k in ("key", "kind"):
            if k not in row:
                _err(e, f"catalog.keys[{i}] missing {k!r}")
        for k in ("dependencies", "providerIds"):
            if k in row and not isinstance(row[k], list):
                _err(e, f"catalog.keys[{i}].{k} not a list")
        cur = str(row.get("key", ""))
        if prev is not None and cur < prev:
            _err(e, f"catalog.keys not sorted by key at index {i} ({prev!r} > {cur!r})")
        prev = cur
    return e


def validate_coverage(obj, roster_relpaths, referenced_normalized):
    """Universes math per spec §3 stage 2: both universes ⊆ the roster."""
    e = []
    if obj.get("keysTotal", 0) <= 0:
        _err(e, "coverage.keysTotal must be > 0")
    referenced = set(referenced_normalized)
    expected_unref = sorted(set(roster_relpaths) - referenced)
    got_unref = sorted(obj.get("bundlesUnreferenced") or [])
    if got_unref != expected_unref:
        _err(e, f"bundlesUnreferenced mismatch: expected {expected_unref}, got {got_unref}")
    if obj.get("distinctBundlesReferenced") != len(referenced):
        _err(e,
             f"distinctBundlesReferenced {obj.get('distinctBundlesReferenced')} "
             f"!= distinct normalized references {len(referenced)}")
    return e


def validate_media_catalogue_row(row, where=""):
    e = []
    for k in ("class", "bundle", "name", "pathId", "bytesEstimate", "contentAxis"):
        if k not in row:
            _err(e, f"{where}media-catalogue row missing {k!r}")
    if row.get("contentAxis") not in CONTENT_AXES:
        _err(e, f"{where}contentAxis {row.get('contentAxis')!r} not in {CONTENT_AXES}")
    return e


def validate_export_manifest_row(row, where=""):
    e = []
    for k in ("sourceBundle", "pathId", "class", "outRelPath", "bytes"):
        if k not in row:
            _err(e, f"{where}export-manifest row missing {k!r}")
    return e


def assert_unique_outrelpath(rows):
    """Stage-3 acceptance: every outRelPath unique (assertion-style helper)."""
    seen = {}
    dups = []
    for i, row in enumerate(rows):
        p = row.get("outRelPath")
        if p in seen:
            dups.append(f"{p!r} at rows {seen[p]} and {i}")
        else:
            seen[p] = i
    if dups:
        raise AssertionError("duplicate outRelPath values: " + "; ".join(dups))
    return True


def validate_stub_row(row, where=""):
    """Pinned stage-5 row contract (spec §3 stage 5 Row shape)."""
    e = []
    if not isinstance(row, dict):
        return [f"{where}stub row is not an object"]
    for k, typ in (
        ("id", str), ("slug", (str, type(None))), ("fields", dict),
        ("provisional", bool), ("inferred", bool), ("method", str),
        ("buildId", int),
    ):
        if k not in row:
            _err(e, f"{where}missing {k!r}")
        elif not isinstance(row[k], typ):
            _err(e, f"{where}{k!r} wrong type: {type(row[k]).__name__}")
    if row.get("kind") not in KIND_TO_FILE:
        _err(e, f"{where}kind {row.get('kind')!r} not in pinned kind map")
    src = row.get("source")
    if not isinstance(src, dict):
        _err(e, f"{where}source must be an object")
    else:
        for k in ("bundle", "pathId", "class"):
            if k not in src:
                _err(e, f"{where}source missing {k!r}")
        if "pathId" in src and not isinstance(src["pathId"], int):
            _err(e, f"{where}source.pathId not an int")
    if row.get("inferred") is False and not row.get("method"):
        _err(e, f"{where}method string required even when inferred=false (provenance)")
    return e


def validate_absence_row(row, where=""):
    e = []
    for k in ("kind", "scannedBundles", "scannedClasses", "evidence"):
        if k not in row:
            _err(e, f"{where}_absences row missing {k!r}")
    if row.get("kind") not in KIND_TO_FILE:
        _err(e, f"{where}_absences kind {row.get('kind')!r} not a seeded kind")
    return e


def validate_unmapped_row(row, where=""):
    e = []
    for k in ("class", "bundles", "objectCount", "evidence"):
        if k not in row:
            _err(e, f"{where}_unmapped-families row missing {k!r}")
    return e


def validate_availability_row(row, where=""):
    e = []
    for k in ("kind", "id", "availableLocales", "namedLocales", "fieldPresence",
              "joinInferred", "joinMethod", "buildId"):
        if k not in row:
            _err(e, f"{where}availability row missing {k!r}")
    for k in ("availableLocales", "namedLocales"):
        v = row.get(k)
        if v is not None and not isinstance(v, list):
            _err(e, f"{where}{k} must be a list")
    fp = row.get("fieldPresence")
    if not isinstance(fp, dict):
        _err(e, f"{where}fieldPresence must be an object of locale -> [fields]")
    else:
        for loc, fields in fp.items():
            if not isinstance(fields, list):
                _err(e, f"{where}fieldPresence[{loc!r}] must be a list of field names")
    if row.get("joinInferred") is True and not row.get("joinMethod"):
        _err(e, f"{where}joinInferred=true requires joinMethod naming the convention")
    return e


def validate_locale_file(path: Path, *, expect_name: str | None = None):
    """{id,text} contract held by the 13 locale files AND base-overlay.jsonl."""
    e = []
    rows = read_jsonl(path)  # raises with line info on invalid JSON
    if not rows:
        _err(e, f"{path.name}: empty locale file")
    for i, row in enumerate(rows):
        if "id" not in row or "text" not in row:
            _err(e, f"{path.name}:{i + 1}: row missing id/text")
    if expect_name and path.name != expect_name:
        _err(e, f"file named {path.name!r}, expected {expect_name!r}")
    return e


def validate_base_overlay_report(obj):
    e = []
    pol = obj.get("compositionPolicy")
    if pol not in COMPOSITION_POLICIES:
        _err(e, f"compositionPolicy {pol!r} not in four-value enum {COMPOSITION_POLICIES}")
    ev = obj.get("evidence")
    if not isinstance(ev, dict) or not ev:
        _err(e, "evidence object with counts required")
    else:
        total = 0
        for k, v in ev.items():
            if not isinstance(v, int) or v < 0:
                _err(e, f"evidence.{k} must be a non-negative count (got {v!r})")
            total += v or 0
        if total <= 0:
            _err(e, "evidence counts are all zero — no observation recorded")
    return e


def locate_matrix_keys(obj):
    """Tolerantly locate the key->presence mapping inside locale-matrix.json.

    The matrix shape is implementation-defined beyond 'per key: presence across
    the 13 locales PLUS base'; find the first dict whose keys look like loc keys.
    """
    if isinstance(obj, dict):
        for candidate in ("keys", "matrix", "byKey"):
            v = obj.get(candidate)
            if isinstance(v, dict) and v:
                return v
        # maybe the root IS the mapping
        vals = [v for v in obj.values() if isinstance(v, (dict, list))]
        if len(vals) >= len(obj) / 2 and all(isinstance(v, (dict, list)) for v in obj.values()):
            return obj
    return None


def locale_file_set_matches(locales_dir: Path):
    """BCP-47 file-set equality helper (spec §5 criterion 8).

    Returns (ok, missing, extra, bad): exactly the 13 `<locale>.jsonl` names,
    character-for-character, plus base-overlay.jsonl handled by callers.
    """
    expected = {f"{loc}.jsonl" for loc in LOCALE_TABLE.values()}
    got = set()
    if locales_dir.exists():
        got = {p.name for p in locales_dir.glob("*.jsonl")} - {f"{BASE_OVERLAY_NAME}.jsonl"}
    missing = sorted(expected - got)
    extra = sorted(got - expected)
    return (not missing and not extra), missing, extra


# --- identifier preservation sample policy (spec §3 stage 5) -------------------

def identifier_sample_ids(ids):
    """≤1,000 ids → all (sorted); else deterministic sorted sample of 500."""
    ordered = sorted(ids)
    if len(ordered) <= 1000:
        return ordered
    return ordered[:500]


def check_identifier_verbatim(source_ids, emitted_rows, where="stubs"):
    """Byte-match emitted ids against source dump ids under the sample policy.

    source_ids: iterable of verbatim ids present in the synthetic dumps.
    emitted_rows: parsed stub rows (dicts with 'id').
    """
    src = set(source_ids)
    emitted_ids = [r["id"] for r in emitted_rows]
    sample = identifier_sample_ids(emitted_ids)
    checked = [(sid, sid in src) for sid in sample]
    bad = [sid for sid, ok in checked if not ok]
    assert not bad, (
        f"{where}: identifiers not byte-matching their source dump values "
        f"({len(bad)}/{len(sample)} sampled): {bad[:5]}"
    )
    return len(sample), len(emitted_ids)
