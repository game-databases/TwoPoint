"""Stage 2 `harvest-catalog` obligations (spec §8 stage-2 bullets, Revision 4).

Hostless scope: schema validation, match-key normalization, out-of-roster
hard-fail, coverage-universe math, and the PRIMARY TextAsset-catalog decode —
a synthetic TextAsset named "catalog" carrying `m_LocatorId` +
`m_KeyDataString`/`m_BucketDataString`/`m_EntryDataString` base64 blobs drives
the 1.21.x decode → normalization → coverage chain; absent/malformed
TextAssets route to the secondary MonoBehaviour probe with no silent garbage
decode. Decoding the real catalog bundle is client-gated.
"""
from __future__ import annotations

import base64
import io
import json
import struct
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from _impl import (COVERAGE_NAMES, MATCH_KEY_NAMES, SECONDARY_PROBE_NAMES,
                   TEXTASSET_DECODE_NAMES, get_sym, load_any,
                   note_missing_symbol, skip_if_none)
from _validators import (read_json, validate_catalog_json,
                         validate_coverage)

sys.path.insert(0, str(Path(__file__).parent))
import _fixturelib as fx  # noqa: E402
from _fixturelib import roster_rows  # noqa: E402


# --- catalog.json schema validator ------------------------------------------------

def test_schema_validator_accepts_fixture_catalog(fx_stage3):
    # catalog.json is stage 2's OUTPUT; it appears as upstream on the stage-3 tree
    obj = read_json(fx_stage3 / "extracted" / "addressables" / "catalog.json")
    errs = validate_catalog_json(obj)
    assert not errs, f"fixture catalog violates the pinned schema: {errs}"


def test_schema_validator_rejects_unsorted_and_missing_meta(tmp_path):
    bad = {"meta": {"buildId": 1}, "keys": [
        {"key": "b", "kind": "bundle"}, {"key": "a", "kind": "bundle"}]}
    assert validate_catalog_json(bad), "unsorted keys must be flagged"
    worse = {"keys": [{"key": "a", "kind": "bundle"}]}
    errs = validate_catalog_json(worse)
    assert any("meta" in e for e in errs), "missing meta block must be flagged"
    empty = {"meta": {}, "keys": []}
    assert validate_catalog_json(empty), "empty keys must be flagged"


# --- match-key normalization + coverage universes on a synthetic fixture -----------

def test_match_key_normalization_casefold_basename_prefix_strip():
    mod = skip_if_none(load_any("stage2_harvest_catalog.py", "tpc_common.py"),
                       "tools/stage2_harvest_catalog.py | tools/tpc_common.py")
    fn = skip_if_none(get_sym(mod, *MATCH_KEY_NAMES), "match-key normalizer")
    cases = [
        # (reference spelling, expected normalized MATCH KEY)
        ("StandaloneWindows64/items-general_assets_all.bundle",
         "items-general_assets_all"),                              # directory prefix + ext
        ("ITEMS-COURSES-MAGIC_ASSETS_ALL.BUNDLE",
         "items-courses-magic_assets_all"),                        # case-fold
        ("rooms_assets_all.bundle", "rooms_assets_all"),           # already bare
        ("041ed57fabcdef1234567890abcdef12_monoscripts.bundle",
         "041ed57fabcdef1234567890abcdef12_monoscripts"),          # hash-form basename
        ("DLCs/ghost/dlc-ghost-audio_assets_all.bundle",
         "dlc-ghost-audio_assets_all"),                            # DLC dir prefix
        ("Assets/Bundles/ui_assets_all.bundle", "ui_assets_all"),  # provider prefix
    ]
    for ref, expected in cases:
        got = fn(ref)
        got = got.get("key") if isinstance(got, dict) else got
        assert str(got).lower() == expected.lower(), (
            f"normalize({ref!r}) = {got!r}, expected {expected!r} "
            "(case-folded basename after prefix-strip)")
    # THE contract: catalog references and roster relpaths normalize to the
    # SAME key space — equivalent spellings must collide with their roster row
    for ref, _exp in cases:
        roster_equivalent = {
            "StandaloneWindows64/items-general_assets_all.bundle": "aa/StandaloneWindows64/items-general_assets_all.bundle",
            "rooms_assets_all.bundle": "x/rooms_assets_all.bundle",
            "DLCs/ghost/dlc-ghost-audio_assets_all.bundle": "DLCs/ghost/dlc-ghost-audio_assets_all.bundle",
        }
        same = roster_equivalent.get(ref)
        if same:
            assert str(fn(ref)).lower() == str(fn(same)).lower(),                 f"{ref!r} and its roster relpath {same!r} do not normalize to one key"


def test_out_of_roster_reference_lands_in_unresolved():
    """Drives the REAL mapping seam (`tools/stage2_harvest_catalog.py::
    map_catalog_keys` → `(rows, unresolved)`): a planted reference outside
    the roster must land in `unresolved`. The run()-level hard gate that
    turns a non-empty `unresolved` into exit 1 is covered by the runner
    exit-code tests; this binds the seam that feeds it."""
    mod = skip_if_none(load_any("stage2_harvest_catalog.py", "tpc_common.py"),
                       "tools/stage2_harvest_catalog.py | tools/tpc_common.py")
    fn = get_sym(mod, *COVERAGE_NAMES)
    if fn is None:
        pytest.skip("impl-missing: no coverage/reference-check function on "
                    f"tools/stage2_harvest_catalog.py (tried {COVERAGE_NAMES})")
    normalize = get_sym(mod, *MATCH_KEY_NAMES)
    if normalize is None:
        pytest.skip("impl-missing: no match-key normalizer to build the "
                    "roster key space")
    norm_to_relpath = {normalize(r["relpath"]): r["relpath"]
                       for r in roster_rows()}
    spec = fx.CATALOG_KEYS_SPEC
    refs_ok = [r for _k, r in spec]
    ref_bad = "totally-unknown_bundle.bundle"
    decoded = {"keys": [
        {"key": key,
         "entries": [{"provider": "BundledAssetProvider",
                      "dependencyKey": ref}]}
        for key, ref in zip([k for k, _r in spec] + ["Planted.Unknown"],
                            refs_ok + [ref_bad])]}
    rows, unresolved = fn(decoded, norm_to_relpath)
    bad_key = normalize(ref_bad)
    assert bad_key in unresolved, (
        f"out-of-roster reference {ref_bad!r} (key {bad_key!r}) did not land "
        f"in unresolved (got {sorted(unresolved)}) — the seam cannot feed "
        "the stage's hard gate")
    assert unresolved == {bad_key}, (
        f"unresolved must hold ONLY the planted bad reference, got {sorted(unresolved)}")
    assert len(rows) == len(refs_ok) + 1, (
        f"expected one output row per catalog slot, got {len(rows)}")
    resolved = {r["bundle"] for r in rows if r["bundle"]}
    assert all(normalize(ref) in {normalize(b) for b in resolved}
               for ref in refs_ok), (
        "in-roster references must resolve to their roster relpath rows")


def test_coverage_universes_math_synthetic_contentcatalogdata():
    """Synthetic ContentCatalogData fixture: both universes ⊆ the 176-style
    roster; catalog.bundle itself sits in NEITHER count."""
    mod = load_any("stage2_harvest_catalog.py", "tpc_common.py")
    fn = get_sym(mod, *COVERAGE_NAMES) if mod else None
    roster_rows_list = roster_rows()
    roster_names = {Path(r["relpath"]).name for r in roster_rows_list}
    referenced = set()
    for _k, ref in fx.CATALOG_KEYS_SPEC:
        norm = ref.replace("\\", "/").rsplit("/", 1)[-1].lower()
        assert norm in {n.lower() for n in roster_names}, (
            f"synthetic fixture reference {ref!r} does not resolve into the roster — "
            "the synthetic ContentCatalogData fixture itself is inconsistent")
        referenced.add(norm)
    unreferenced = sorted(roster_names - referenced)
    if fn is not None:
        try:
            out = fn([r for _k, r in fx.CATALOG_KEYS_SPEC],
                     sorted(roster_names))
            if isinstance(out, dict):
                db = out.get("distinctBundlesReferenced")
                bu = out.get("bundlesUnreferenced")
                if db is not None:
                    assert db == len(referenced), (
                        f"distinctBundlesReferenced {db} != {len(referenced)}")
                if bu is not None:
                    assert sorted(bu) == unreferenced or \
                        {Path(p).name.lower() for p in bu} == {u.lower() for u in unreferenced}, (
                        f"bundlesUnreferenced mismatch vs universe math: {sorted(bu)[:5]}…")
        except TypeError:
            note_missing_symbol("coverage function present but signature differs")
            # signature differs; the pure-math assertions below still bind
    else:
        note_missing_symbol(
            f"coverage function (tried {COVERAGE_NAMES}) — universe math asserted from fixture data only")

    # catalog.bundle exclusion: a self-reference spelling must land in NEITHER count
    assert "catalog.bundle" not in referenced
    assert "catalog.bundle" not in {u.lower() for u in unreferenced}


def test_fixture_coverage_artifact_matches_universe_math(fx_stage3):
    ext = fx_stage3 / "extracted"
    cov = read_json(ext / "addressables" / "catalog-coverage.json")
    cat = read_json(ext / "addressables" / "catalog.json")
    roster = {Path(r["relpath"]).name for r in roster_rows()}
    refs = {k.replace("\\", "/").rsplit("/", 1)[-1].lower()
            for k in (_r["bundle"] for _r in cat["keys"])}
    covered = {r for r in roster if r.lower() in refs}
    errs = validate_coverage(cov, roster, covered)
    assert not errs, f"fixture coverage artifact violates universe math: {errs}"
    assert cov["keysTotal"] == len(cat["keys"])


# --- Revision 4: the synthetic TextAsset-"catalog" fixture ---------------------------

def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def build_textasset_catalog_payload(spec=None) -> dict:
    """Tiny Addressables-1.21-shaped ContentCatalogData JSON (Revision 4
    primary payload): `m_LocatorId` plus base64 `m_KeyDataString` /
    `m_BucketDataString` / `m_EntryDataString`. One string key slot + one
    bucket + one entry per spec row; the entry's internalId carries that
    row's bundle-reference spelling (the varied spellings from
    CATALOG_KEYS_SPEC exercise match normalization downstream)."""
    spec = list(spec if spec is not None else fx.CATALOG_KEYS_SPEC)
    internal_ids = [ref for _k, ref in spec]
    kb, bb, eb = io.BytesIO(), io.BytesIO(), io.BytesIO()
    kb.write(struct.pack("<i", len(spec)))
    bb.write(struct.pack("<i", len(spec)))
    eb.write(struct.pack("<i", len(spec)))
    for i, (key, _ref) in enumerate(spec):
        raw = key.encode("utf-8")
        kb.write(b"\x00" + struct.pack("<i", len(raw)) + raw)
        bb.write(struct.pack("<2i", i, 1))            # bucketOffset, 1 entry idx
        bb.write(struct.pack("<i", i))                # -> entries[i]
        # internalIdIdx, providerIdx, dependencyKeyIdx, hashCode, dataOffset,
        # primaryKeyIdx, resourceTypeIdx (dependencyKey = own key slot)
        eb.write(struct.pack("<7i", i, 0, i, 0, 0, i, 0))
    return {
        "m_LocatorId": "AddressablesMainContentCatalog",
        "m_KeyDataString": _b64(kb.getvalue()),
        "m_BucketDataString": _b64(bb.getvalue()),
        "m_EntryDataString": _b64(eb.getvalue()),
        "m_InternalIds": internal_ids,
        "m_ProviderIds": ["UnityEngine.Addressables.AssetBundleProvider"],
        "m_resourceTypes": [{"m_ClassName": "AssetBundleRequestOptions"}],
    }


class _FakeAsset:
    def __init__(self, name, script):
        self.m_Name = name
        self.m_Script = script


class _FakeObj:
    def __init__(self, type_name, asset=None, path_id=1):
        self.type = SimpleNamespace(name=type_name)
        self._asset = asset
        self.path_id = path_id

    def read(self):
        if self._asset is None:
            raise ValueError("unreadable object")
        return self._asset


class _FakeFile:
    def __init__(self, objs):
        self.objects = {o.path_id: o for o in objs}
        self._objs = objs


def _fake_env(*objects):
    return SimpleNamespace(files=[_FakeFile(list(objects))])


def _stage2_mod():
    return skip_if_none(load_any("stage2_harvest_catalog.py", "tpc_common.py"),
                        "tools/stage2_harvest_catalog.py | tools/tpc_common.py")


def _install_fake_env_iterators(monkeypatch, mod):
    """Simulate UnityPy's object walk over an open bundle without real bundle
    bytes — the decode route under test is the payload handling, not UnityFS
    block decompression."""
    uu = getattr(mod, "uu", None)
    if uu is None:
        pytest.skip("impl-missing: stage2 module has no unitypy_util alias to stub")
    monkeypatch.setattr(uu, "iter_environment_files",
                        lambda env: list(env.files), raising=False)
    monkeypatch.setattr(uu, "iter_objects_sorted",
                        lambda f: list(f._objs), raising=False)


def test_textasset_primary_decode_drives_mapping_and_coverage(monkeypatch):
    """§8 Revision 4: the synthetic TextAsset fixture drives the PRIMARY
    1.21.x decode AND the chain downstream of it — match normalization and
    the coverage universes (`catalog.bundle` itself in neither count)."""
    mod = _stage2_mod()
    fn = skip_if_none(get_sym(mod, *TEXTASSET_DECODE_NAMES),
                      "TextAsset primary decode route")
    _install_fake_env_iterators(monkeypatch, mod)
    env = _fake_env(_FakeObj(
        "TextAsset",
        _FakeAsset("catalog", json.dumps(build_textasset_catalog_payload()).encode()),
        path_id=700))
    decoded, note = fn(env)
    assert decoded is not None, f"primary decode failed: {note}"
    assert "primary" in note.lower() and "textasset" in note.lower(), \
        f"decode note must stamp the primary route: {note}"

    map_fn = get_sym(mod, *COVERAGE_NAMES)
    if map_fn is None:
        pytest.skip(f"impl-missing: mapping seam (tried {COVERAGE_NAMES})")
    normalize = get_sym(mod, *MATCH_KEY_NAMES)
    if normalize is None:
        pytest.skip(f"impl-missing: match-key normalizer (tried {MATCH_KEY_NAMES})")
    norm_to_relpath = {normalize(r["relpath"]): r["relpath"] for r in roster_rows()}
    rows, unresolved = map_fn(decoded, norm_to_relpath)
    assert unresolved == set(), (
        "every reference inside the synthetic TextAsset catalog must resolve "
        f"into the roster via the pinned match key; unresolved={sorted(unresolved)}")
    assert len(rows) == len(fx.CATALOG_KEYS_SPEC), (
        f"one output row per catalog key: {len(rows)} != {len(fx.CATALOG_KEYS_SPEC)}")
    referenced = {Path(r["bundle"]).name.lower() for r in rows if r["bundle"]}
    roster_names = {Path(r["relpath"]).name.lower() for r in roster_rows()}
    assert referenced and referenced <= roster_names, (
        f"resolved bundles must be roster relpaths: {sorted(referenced)}")
    # coverage-universe pin: catalog.bundle is not a roster row → neither count
    assert "catalog.bundle" not in referenced
    assert "catalog.bundle" not in norm_to_relpath
    assert decoded.get("providerIds"), "decoded model must carry providerIds"


def test_malformed_textasset_routes_to_secondary_without_garbage(monkeypatch):
    """A malformed catalog TextAsset yields NO model — the caller probes the
    secondary route; corrupt blobs never surface as silent garbage decode."""
    mod = _stage2_mod()
    fn = get_sym(mod, *TEXTASSET_DECODE_NAMES)
    if fn is None:
        pytest.skip(f"impl-missing: TextAsset primary decode route "
                    f"(tried {TEXTASSET_DECODE_NAMES})")
    _install_fake_env_iterators(monkeypatch, mod)

    # leg A: not JSON at all
    env = _fake_env(_FakeObj("TextAsset", _FakeAsset("catalog", b"{ not json"),
                             path_id=1))
    decoded, note = fn(env)
    assert decoded is None, "malformed JSON must not produce a decoded model"
    assert "json" in note.lower() or "malformed" in note.lower() or \
        "not valid" in note.lower(), f"note should say why: {note}"

    # leg B: valid JSON with m_LocatorId but undecodable blobs
    payload = build_textasset_catalog_payload([("Config.Global",
                                                "configs_assets_all.bundle")])
    payload["m_EntryDataString"] = _b64(b"\x01\x02\x03")  # truncated entry blob
    env2 = _fake_env(_FakeObj(
        "TextAsset", _FakeAsset("catalog", json.dumps(payload).encode()), path_id=2))
    decoded2, note2 = fn(env2)
    assert decoded2 is None, "corrupt blobs must not produce a decoded model"
    assert note2.strip(), "a malformed candidate must record its reason"

    # leg C: a NON-dict JSON top level is also malformed, never decoded
    env3 = _fake_env(_FakeObj("TextAsset", _FakeAsset("catalog", b"[1,2,3]"),
                              path_id=3))
    decoded3, note3 = fn(env3)
    assert decoded3 is None, "non-object JSON must not produce a decoded model"


def test_absent_textasset_returns_none_and_secondary_refuses_loudly(monkeypatch):
    """No TextAsset in the bundle → primary returns None (absent) and the
    secondary probe refuses with the stage-failure exit code — never silence."""
    mod = _stage2_mod()
    fn = get_sym(mod, *TEXTASSET_DECODE_NAMES)
    if fn is None:
        pytest.skip(f"impl-missing: TextAsset primary decode route "
                    f"(tried {TEXTASSET_DECODE_NAMES})")
    _install_fake_env_iterators(monkeypatch, mod)
    env = _fake_env(
        _FakeObj("Texture2D", path_id=1),
        _FakeObj("TextAsset",
                 _FakeAsset("tutorial_tips", json.dumps({"lines": ["hi"]})),
                 path_id=2),
    )
    decoded, note = fn(env)
    assert decoded is None, "an unrelated TextAsset must never decode as the catalog"
    assert note.strip(), "the absent case must carry a reason for the run section"
    probe = get_sym(mod, *SECONDARY_PROBE_NAMES)
    if probe is None:
        pytest.skip(f"impl-missing: secondary probe (tried {SECONDARY_PROBE_NAMES})")
    raised = None
    try:
        raised = probe(env, None)
    except Exception as exc:  # noqa: BLE001 — StageError expected here
        raised = exc
    assert isinstance(raised, Exception), (
        "with no decodable payload on EITHER route the secondary probe must "
        f"raise the stage failure, got {raised!r}")
    assert getattr(raised, "exit_code", 1) == 1, (
        f"secondary-route refusal must exit 1, got {raised!r}")


# --- Round 8 regression: the REAL AA 1.21.10 blob shapes ---------------------------
# Measured heads from the real client catalog (.agents/catalog-blob-probe.json):
# key+bucket blobs share count 0x0000dd54 = 56660; entries declare 66129 with
# byte length exactly 4 + 28·66129. Buckets carry 81,146 memberships over those
# 66,129 entries — multi-key entries (labels / two-slot hash pairs) put
# memberships ABOVE entries, which the pre-round-8 decoder rejected as fatal.

REAL_PROBE_HEAD_HEX = {
    "m_KeyDataString":
        "54dd00000040000000646c632d67686f73742d6172745f6173736574735f616c6c5f"
        "3666646664663537343662613364",
    "m_BucketDataString":
        "54dd0000040000000100000000000000490000000100000001000000900000000100"
        "000002000000d900000001000000",
    # Byte-exact from .agents/catalog-blob-probe.json (the parked patch quoted a
    # 32-byte variant here that had lost one zero int32 and shifted
    # entry[0].resourceType to 1 — corrected to the measured 48 bytes).
    "m_EntryDataString":
        "510201000000000000000000ffffffff00000000000000000000000000000000"
        "0100000000000000ffffffff00000000",
}
KEY_SLOTS = 56660
ENTRY_COUNT = 66129
EXTRA_MEMBERSHIP_SLOTS = 24486   # slots 4..24489 carry a second (label-style) ref


def _probe_ascii_key(length: int, seed: int) -> str:
    alphabet = "abcdefghijklmnopqrstuvwxyz0123456789_"
    base = f"k{seed:06d}-"
    fill = "".join(alphabet[(seed + i) % len(alphabet)]
                   for i in range(max(0, length - len(base))))
    return (base + fill)[:length]


def build_probe_shaped_blobs():
    """Synthetic blobs reproducing the measured wire shapes AT THE MEASURED
    SCALE: same counts (56660 slots/buckets, 66129 entries), same first key
    spelling and 64-byte length ('dlc-ghost-art_assets_all_…'), same leading
    bucket dataOffsets (4/73/144/217 = the int32-length key-record boundaries),
    same entry[0] row (0,0,-1,0,0,0,0) — and the same 81146-vs-66129 membership
    arithmetic that killed the old decoder."""
    lens = {0: 64, 1: 66, 2: 68, 3: 69}
    keys: dict[int, str] = {}
    offs: dict[int, int] = {}
    off = 4
    for i in range(KEY_SLOTS):
        ln = lens.get(i, 12 + (i * 7) % 31)
        keys[i] = ("dlc-ghost-art_assets_all_6fdfdf5746ba3d" + "f" * 25
                   if i == 0 else _probe_ascii_key(ln, i))
        offs[i] = off
        off += 5 + ln                       # type tag + int32 length + payload
    kb = io.BytesIO()
    kb.write(struct.pack("<i", KEY_SLOTS))
    for i in range(KEY_SLOTS):
        raw = keys[i].encode("ascii")
        kb.write(b"\x00" + struct.pack("<i", len(raw)) + raw)

    bb = io.BytesIO()
    bb.write(struct.pack("<i", KEY_SLOTS))
    memberships = 0
    referenced: set[int] = set()
    for i in range(KEY_SLOTS):
        items = [i]
        if 4 <= i < 4 + EXTRA_MEMBERSHIP_SLOTS:
            items.append(ENTRY_COUNT - 1 - (i - 4))   # shared entry, in range
        bb.write(struct.pack("<2i", offs[i], len(items)))
        bb.write(struct.pack(f"<{len(items)}i", *items))
        memberships += len(items)
        referenced.update(items)
    assert memberships == 81146, memberships     # the measured real number

    eb = io.BytesIO()
    eb.write(struct.pack("<i", ENTRY_COUNT))
    for j in range(ENTRY_COUNT):
        if j == 0:
            row = (0, 0, -1, 0, 0, 0, 0)          # verbatim probe entry[0]
        elif j == 1:
            row = (1, 0, -1, 0, 0, 1 % KEY_SLOTS, 0)   # probe entry[1] head
        else:
            row = (0, 0, -1, 0, 0, j % KEY_SLOTS, 0)
        eb.write(struct.pack("<7i", *row))
    return kb.getvalue(), bb.getvalue(), eb.getvalue(), {
        "memberships": memberships, "distinct": len(referenced)}


def build_probe_shaped_payload():
    kb, bb, eb, facts = build_probe_shaped_blobs()
    payload = {
        "m_LocatorId": "AddressablesMainContentCatalog",
        "m_KeyDataString": _b64(kb),
        "m_BucketDataString": _b64(bb),
        "m_EntryDataString": _b64(eb),
        "m_InternalIds": ["AA/StandaloneWindows64/regression-placeholder.bundle"],
        "m_ProviderIds": ["UnityEngine.AddressableAssets.AssetBundleProvider"],
        "m_resourceTypes": [
            {"m_ClassName": "AssetBundleRequestOptions"},
            {"m_ClassName": "TextureProvider"}],
    }
    return payload, facts


def test_regression_real_head_shapes_decode_with_memberships_over_entries():
    """THE round-8 killer: bucket item total 81146 > entry count 66129 (real
    TPC numbers) must decode clean, byte-reproduce the measured heads, and
    report the arithmetic in meta instead of raising CatalogDecodeError."""
    aa = skip_if_none(load_any("aa_catalog.py"), "tools/aa_catalog.py")
    payload, facts = build_probe_shaped_payload()
    for field, head in REAL_PROBE_HEAD_HEX.items():
        raw = base64.b64decode(payload[field])
        assert raw[: len(head) // 2].hex() == head, (
            f"synthetic {field} does not reproduce the measured head bytes")
    decoded = aa.decode_catalog_payload(payload)
    meta = decoded["meta"]
    assert meta["bucketMembershipTotal"] == facts["memberships"] == 81146
    assert meta["keySlotCount"] == KEY_SLOTS == meta["bucketCount"]
    assert meta["entryCount"] == ENTRY_COUNT
    assert meta["distinctEntriesReferenced"] == facts["distinct"]
    assert meta["unreferencedEntryCount"] == ENTRY_COUNT - facts["distinct"]
    first = decoded["keys"][0]
    assert first["kind"] == "str" and first["bucketOffset"] == 4
    assert first["key"].startswith("dlc-ghost-art_assets_all_")
    row = first["entries"][0]
    assert row["primaryKey"] == first["key"] and row["dependencyKey"] is None
    assert row["resourceType"] == "AssetBundleRequestOptions"


def test_regression_corrupt_blob_shapes_fail_loud_and_typed():
    """A payload that genuinely does NOT parse dies loudly as
    CatalogDecodeError naming the blob and offset — never silent, never a raw
    struct.error escaping to the caller."""
    aa = skip_if_none(load_any("aa_catalog.py"), "tools/aa_catalog.py")

    def blobs(spec=(("alpha_one", "items-a_assets_all.bundle"),
                    ("beta_two", "items-b_assets_all.bundle"))):
        kb, bb, eb = io.BytesIO(), io.BytesIO(), io.BytesIO()
        kb.write(struct.pack("<i", len(spec)))
        bb.write(struct.pack("<i", len(spec)))
        eb.write(struct.pack("<i", len(spec)))
        ids = []
        for i, (key, ref) in enumerate(spec):
            raw = key.encode("utf-8")
            kb.write(b"\x00" + struct.pack("<i", len(raw)) + raw)
            bb.write(struct.pack("<2i", i, 1))
            bb.write(struct.pack("<i", i))
            eb.write(struct.pack("<7i", i, 0, -1, 0, 0, i, 0))
            ids.append(ref)
        return kb.getvalue(), bb.getvalue(), eb.getvalue(), ids

    def payload_with(m_KeyDataString=None, m_BucketDataString=None,
                     m_EntryDataString=None):
        # kwargs carry the payload's own field names so rejects() can plant
        # one corrupted blob per call site verbatim
        k0, b0, e0, ids = blobs()
        return {
            "m_LocatorId": "AddressablesMainContentCatalog",
            "m_KeyDataString": _b64(k0 if m_KeyDataString is None else m_KeyDataString),
            "m_BucketDataString": _b64(b0 if m_BucketDataString is None else m_BucketDataString),
            "m_EntryDataString": _b64(e0 if m_EntryDataString is None else m_EntryDataString),
            "m_InternalIds": ids,
            "m_ProviderIds": ["UnityEngine.AddressableAssets.AssetBundleProvider"],
            "m_resourceTypes": [{"m_ClassName": "AssetBundleRequestOptions"}],
        }

    k0, b0, e0, _ = blobs()

    def rejects(field, blob, frag):
        with pytest.raises(aa.CatalogDecodeError, match=frag):
            aa.decode_catalog_payload(payload_with(**{field: blob}))

    rejects("m_KeyDataString", k0[:-3], "truncated")                    # cut mid-string
    rejects("m_KeyDataString",                                          # unknown tag
            struct.pack("<i", 1) + b"\x09" + struct.pack("<i", 2) + b"\x02\x03",
            "unknown key type 9")
    rejects("m_BucketDataString", b0 + b"\x00\x00\x00\x00", "residue")  # trailing junk
    rejects("m_EntryDataString", e0[:-4], "entry blob length mismatch") # count vs len
    rejects("m_BucketDataString",                                       # item OOB
            struct.pack("<i", 2)
            + struct.pack("<2i", 0, 1) + struct.pack("<i", 9999)
            + struct.pack("<2i", 1, 1) + struct.pack("<i", 1),
            "out of range")


def test_regression_key_type_codes_int_and_hash128_resolve():
    """AA key type codes beyond strings — 2 = prime int, 3 = Hash128 — were
    fatal 'unknown key type' before round 8; values must round-trip into the
    key slots and classify downstream as integer/guid/address."""
    aa = skip_if_none(load_any("aa_catalog.py"), "tools/aa_catalog.py")
    h128 = bytes(range(16))
    kb = (struct.pack("<i", 3)
          + b"\x02" + struct.pack("<i", 1234567)
          + b"\x03" + h128
          + b"\x00" + struct.pack("<i", 5) + b"hello")
    slots = aa.parse_keys(kb)
    assert [(s["kind"], s["key"]) for s in slots] == [
        ("int", 1234567), ("hash128", h128.hex()), ("str", "hello")]
    s2 = load_any("stage2_harvest_catalog.py")
    if s2 is not None and hasattr(s2, "classify_key"):
        assert s2.classify_key(1234567) == "integer"
        assert s2.classify_key(h128.hex()) == "guid"
        assert s2.classify_key("hello") == "address"


# --- TestFixer-006: Revision-5 key-space + file-form lane (G3/G5) -------------------
# No fixture previously carried a decimal dependencyKey, a `_<32hex>` hash-
# suffix spelling, or braces — deleting pass 2 or the hash-suffix ladder kept
# all pre-existing tests green while catalog.json.dependencies[] degraded to [].

HASH32 = "3053e16d24e0f8c9a1b2c3d4e5f60718"
DECIMAL_SLOT_KEY = "-1064046067"   # the measured negative-named catalog key

KEYSPACE_ROSTER = [
    "TPC_Data/StreamingAssets/aa/StandaloneWindows64/rooms_assets_all.bundle",
    "TPC_Data/StreamingAssets/aa/StandaloneWindows64/ui-art-mainmenu_assets_all.bundle",
    "TPC_Data/StreamingAssets/aa/StandaloneWindows64/localisation_assets_localisation_french.bundle",
]


def _stage2_any():
    return skip_if_none(load_any("stage2_harvest_catalog.py", "tpc_common.py"),
                        "tools/stage2_harvest_catalog.py | tools/tpc_common.py")


def test_hash_suffix_and_braced_reference_ladders():
    """Reviewer G5: the strip ladder (`<name>_<32hex>` → `<name>`) and the two
    braced spellings decide the measured dlc-hospital/dlc-preorder evidence
    classes — dropping either converts real references into warnings or a
    spurious exit 1."""
    mod = _stage2_any()
    normalize = skip_if_none(get_sym(mod, *MATCH_KEY_NAMES),
                             "match-key normalizer")
    # braced spellings: `{RSC}name…` strips the provider prefix;
    # `{hash}.bundle` wraps the NAME itself and keeps its content
    assert normalize("{RSC}dlc-hospital-ui.bundle") == "dlc-hospital-ui"
    assert normalize(f"{{{HASH32}}}.bundle") == HASH32
    assert normalize("Assets/{RSC}FRENCH.Bundle") == "french"
    assert normalize("ROOMS_Assets_All.BUNDLE") == "rooms_assets_all"

    strip = get_sym(mod, "strip_hash_suffix")
    resolve = get_sym(mod, "resolve_file_form_reference")
    norm_to_relpath = {normalize(r): r for r in KEYSPACE_ROSTER}
    if strip is not None:
        assert strip(f"ui-art-mainmenu_assets_all_{HASH32}") == \
            "ui-art-mainmenu_assets_all"
        assert strip("rooms_assets_all") is None
        assert strip("name_" + "a" * 31) is None, \
            "31 hex chars must NOT count as a hash suffix"
        assert strip("name_" + "a" * 32) == "name"
    else:
        note_missing_symbol("strip_hash_suffix")
    if resolve is not None:
        kind, rel, _norm = resolve("rooms_assets_all.bundle", norm_to_relpath)
        assert kind == "direct"
        assert rel == norm_to_relpath["rooms_assets_all"]
        kind2, rel2, _norm2 = resolve(
            f"StandaloneWindows64/ui-art-mainmenu_assets_all_{HASH32}.bundle",
            norm_to_relpath)
        assert kind2 == "hash-suffix", (
            f"hash-suffix ladder dead (got {kind2!r}): the measured "
            f"`_<32hex>` reference class degrades to warnings or a spurious "
            "exit 1")
        assert rel2 == norm_to_relpath["ui-art-mainmenu_assets_all"]
        kind3, rel3, norm3 = resolve("totally-absent_bundle.bundle",
                                     norm_to_relpath)
        assert kind3 is None and rel3 is None and norm3 == "totally-absent_bundle"
    else:
        note_missing_symbol("resolve_file_form_reference")


def _kslot(key, entries):
    return {"key": key, "kind": "str", "bucketOffset": 4, "a": None,
            "entries": entries}


def _kentry(internal_id=None, dependency_key=None):
    return {"internalId": internal_id,
            "provider": "UnityEngine.Addressables.AssetBundleProvider",
            "resourceType": "AssetBundleRequestOptions",
            "dependencyKey": dependency_key, "primaryKey": None}


def test_decimal_dependency_keys_resolve_transitively_with_details():
    """Reviewer G3: dependency keys live in KEY SPACE. A decimal string naming
    ANOTHER slot's key resolves transitively; `dependencies[]` carries the
    RESOLVED roster relpaths; pass-2 counters land only via `details=` —
    which no call site exercised before this test."""
    mod = _stage2_any()
    map_fn = skip_if_none(get_sym(mod, *COVERAGE_NAMES), "mapping seam")
    normalize = skip_if_none(get_sym(mod, *MATCH_KEY_NAMES),
                             "match-key normalizer")
    norm_to_relpath = {normalize(r): r for r in KEYSPACE_ROSTER}
    ui_rel = norm_to_relpath["ui-art-mainmenu_assets_all"]
    rooms_rel = norm_to_relpath["rooms_assets_all"]
    french_rel = norm_to_relpath["localisation_assets_localisation_french"]

    decoded = {"keys": [
        _kslot("Rooms.Main", [_kentry(internal_id="rooms_assets_all.bundle")]),
        _kslot(DECIMAL_SLOT_KEY,
               [_kentry(internal_id=f"StandaloneWindows64/"
                                     f"ui-art-mainmenu_assets_all_{HASH32}"
                                     f".bundle")]),
        _kslot("Menu.Dep", [_kentry(dependency_key=DECIMAL_SLOT_KEY)]),
        _kslot("Deep.Chain", [_kentry(dependency_key=DECIMAL_SLOT_KEY)]),
        _kslot("Self.Key",
               [_kentry(internal_id="localisation_assets_localisation_french.bundle",
                        dependency_key="Self.Key")]),
    ]}
    details: dict = {}
    rows, unresolved = map_fn(decoded, norm_to_relpath, details)
    assert unresolved == set(), f"dangling file-form refs: {sorted(unresolved)}"
    by_key = {r["key"]: r for r in rows}
    # transitive: dep-key → other slot → that slot's bundles, as RELPATHS
    assert by_key["Menu.Dep"]["dependencies"] == [ui_rel]
    assert by_key["Deep.Chain"]["dependencies"] == [ui_rel], (
        "one-level key-index resolution must reach the referenced slot's bundle")
    assert by_key["Rooms.Main"]["bundle"] == rooms_rel
    assert by_key[DECIMAL_SLOT_KEY]["bundle"] == ui_rel, (
        "the hash-suffixed internalId on the negative-named slot must match "
        "via the strip ladder")
    assert by_key["Self.Key"]["bundle"] == french_rel
    # the raw decimal NEVER leaks into emitted dependencies/bundles
    for row in rows:
        blob = json.dumps(row, default=str)
        assert DECIMAL_SLOT_KEY not in (row["bundle"] or ""), blob
        assert all(DECIMAL_SLOT_KEY not in d for d in row["dependencies"])
    # details ledger: resolutions counted, suffix mapping counted, no danglers
    assert details.get("keySpaceResolutions", 0) >= 3, (
        f"pass-2 hit counter dead: {details!r} (delete-pass-2 regression)")
    assert details.get("hashSuffixMatches", 0) == 1
    assert details.get("danglingDependencyKeys") == []
    assert details.get("outOfRosterFileReferences") == []


def test_dangling_decimal_keys_ledgered_not_unresolved():
    """A decimal key naming NO known key-space slot is warning-ledger evidence
    (`danglingDependencyKeys`), never an unresolved file-form reference and
    never a silent drop."""
    mod = _stage2_any()
    map_fn = skip_if_none(get_sym(mod, *COVERAGE_NAMES), "mapping seam")
    normalize = skip_if_none(get_sym(mod, *MATCH_KEY_NAMES),
                             "match-key normalizer")
    norm_to_relpath = {normalize(r): r for r in KEYSPACE_ROSTER}
    decoded = {"keys": [
        _kslot("Lonely.Slot", [_kentry(dependency_key="777777")]),
        _kslot("777777", [_kentry()]),   # address-only slot: no file-form hits
    ]}
    details: dict = {}
    rows, unresolved = map_fn(decoded, norm_to_relpath, details)
    assert unresolved == set(), (
        "key-space danglings are warning-class, not unresolved file forms")
    danglers = details.get("danglingDependencyKeys")
    assert danglers == ["777777"], f"ledger dead or wrong: {details!r}"
    lonely = next(r for r in rows if r["key"] == "Lonely.Slot")
    assert lonely["dependencies"] == [] and lonely["bundle"] is None


def _topology_payload(spec):
    """ContentCatalogData JSON with ARBITRARY key-space topology.
    spec rows: (key, internalId_ref | None, dependencyKey_slot_index | None);
    None internalIds become non-file-form asset addresses."""
    n = len(spec)
    kb, bb, eb = io.BytesIO(), io.BytesIO(), io.BytesIO()
    kb.write(struct.pack("<i", n))
    bb.write(struct.pack("<i", n))
    eb.write(struct.pack("<i", n))
    internal_ids, offs, off = [], [], 4
    for i, (key, ref, dep_idx) in enumerate(spec):
        raw = key.encode("utf-8")
        kb.write(b"\x00" + struct.pack("<i", len(raw)) + raw)
        offs.append(off)
        off += 5 + len(raw)
        bb.write(struct.pack("<2i", offs[i], 1))
        bb.write(struct.pack("<i", i))
        internal_ids.append(ref if ref is not None
                            else f"Assets/Content/slot{i}")
        eb.write(struct.pack("<7i", i, 0, -1 if dep_idx is None else dep_idx,
                             0, 0, i, 0))
    return {
        "m_LocatorId": "AddressablesMainContentCatalog",
        "m_KeyDataString": _b64(kb.getvalue()),
        "m_BucketDataString": _b64(bb.getvalue()),
        "m_EntryDataString": _b64(eb.getvalue()),
        "m_InternalIds": internal_ids,
        "m_ProviderIds": ["UnityEngine.Addressables.AssetBundleProvider"],
        "m_resourceTypes": [{"m_ClassName": "AssetBundleRequestOptions"}],
    }


def _write_stage2_upstreams(ext: Path):
    from _validators import write_jsonl
    ext = Path(ext)
    ext.mkdir(parents=True, exist_ok=True)
    write_jsonl(ext / "bundle-roster.jsonl", roster_rows())
    fx.build_identity_fixture(ext)
    return ext


HEALTHY_SPEC = [
    ("Rooms.Main", "rooms_assets_all.bundle", None),
    ("-1064046067",
     f"StandaloneWindows64/ui_assets_all_{HASH32}.bundle", None),
    ("Menu.Dep", None, 1),          # decimal key-space indirection
    ("Deep.Chain", None, 1),        # transitively through the same slot
    ("Self.Key", "unlockables_assets_all.bundle", 4),
]

WARN_SPEC = [
    ("DLC.Hospital", "{RSC}dlc-hospital-ui.bundle", None),   # braced prefix
    ("Absent.SelfIdx", "absent-selfindexed.bundle", None),   # self-indexed below
    ("absent-selfindexed.bundle", "rooms_assets_all.bundle", None),
    ("Dangler", None, 4),                                    # dangling decimal
    ("888888", None, None),                                  # address-only slot
]


def _drive_stage2_run(monkeypatch, spec, ext, game_tree):
    """tools/stage2_harvest_catalog.run() hostless: the catalog TextAsset is
    the synthetic payload and UnityPy is stubbed at the stage module's uu
    seam — the run-level gate/coverage contract becomes fixture-testable."""
    mod = _stage2_mod()
    payload = json.dumps(_topology_payload(spec)).encode()
    env = _fake_env(_FakeObj("TextAsset",
                             _FakeAsset("catalog", payload), path_id=700))
    fake_uu = SimpleNamespace(
        ensure_unitypy=lambda: (SimpleNamespace(load=lambda p: env),
                                "fixture-stub"),
        iter_environment_files=lambda e: list(e.files),
        iter_objects_sorted=lambda f: list(f._objs))
    monkeypatch.setattr(mod, "uu", fake_uu, raising=False)
    from conftest import tree_game
    rc = mod.run(Path(tree_game(game_tree)), Path(ext))
    return rc, mod


def _run_section_text(ext: Path, stage_id: str = "harvest-catalog") -> str:
    import re as _re2
    log_text = (Path(ext) / "EXTRACTION-LOG.md").read_text(
        encoding="utf-8", errors="replace")
    sections = [p for p in _re2.split(r"(?m)^#{1,3} ", log_text)
                if p.splitlines()[:1] and stage_id in p.splitlines()[0].lower()]
    assert sections, f"no {stage_id} run section written"
    return sections[-1]


def test_stage2_run_healthy_keyspace_end_to_end(fx_stage2, tmp_path,
                                                monkeypatch):
    """Full hostless stage-2 run over a key-space corpus: rc 0, resolved
    relpaths in catalog.json.dependencies[], coverage reconciles, ledgers at
    zero, counters stamped in the run section."""
    ext = _write_stage2_upstreams(tmp_path / "ext")
    rc, _mod = _drive_stage2_run(monkeypatch, HEALTHY_SPEC, ext, fx_stage2)
    assert rc == 0, f"healthy key-space run failed rc={rc}"
    cat = read_json(ext / "addressables" / "catalog.json")
    errs = validate_catalog_json(cat)
    assert not errs, errs
    by_key = {row["key"]: row for row in cat["keys"]}
    ui_rel = next(r["relpath"] for r in roster_rows()
                  if Path(r["relpath"]).name == "ui_assets_all.bundle")
    unlock_rel = next(r["relpath"] for r in roster_rows()
                      if Path(r["relpath"]).name == "unlockables_assets_all.bundle")
    assert by_key["Menu.Dep"]["dependencies"] == [ui_rel], (
        f"the backbone join degraded: {by_key['Menu.Dep']!r} — pass 2 deleted?")
    assert by_key["Deep.Chain"]["dependencies"] == [ui_rel]
    assert by_key[DECIMAL_SLOT_KEY]["bundle"] == ui_rel
    assert by_key["Rooms.Main"]["bundle"] == next(
        r["relpath"] for r in roster_rows()
        if Path(r["relpath"]).name == "rooms_assets_all.bundle")
    assert by_key["Self.Key"]["bundle"] == unlock_rel
    assert by_key["Self.Key"]["dependencies"] == [unlock_rel]

    cov = read_json(ext / "addressables" / "catalog-coverage.json")
    referenced = {b for k in cat["keys"]
                  for b in ([k["bundle"]] if k["bundle"] else [])
                  + k["dependencies"]}
    errs = validate_coverage(cov, {r["relpath"] for r in roster_rows()},
                             referenced)
    assert not errs, errs
    assert cov["keysTotal"] == len(HEALTHY_SPEC)
    assert cov["distinctBundlesReferenced"] == 3
    assert cov["danglingDependencyKeys"] == {"count": 0, "sample": []}

    section = _run_section_text(ext)
    import re as _re3
    m = _re3.search(r"keySpaceResolutions:\s*(\d+)", section)
    assert m and int(m.group(1)) >= 3, (
        f"pass-2 resolution counter missing from the run section:\n{section}")
    m = _re3.search(r"hashSuffixMatches:\s*(\d+)", section)
    assert m and int(m.group(1)) == 1, section


def test_stage2_gate_refuses_bare_file_form_miss_hostless(fx_stage2, tmp_path,
                                                          monkeypatch):
    """The NARROWED hard gate (Revision 5): a FILE-FORM reference matching
    neither the direct nor the hash-suffix ladder, with no braced/self-index
    evidence, exits 1 BEFORE any output write."""
    ext = _write_stage2_upstreams(tmp_path / "ext")
    with pytest.raises(Exception) as excinfo:
        _drive_stage2_run(monkeypatch, [("Bad.Ref",
                                         "totally-missing_bundle.bundle",
                                         None)], ext, fx_stage2)
    raised = excinfo.value
    code = getattr(raised, "exit_code", None)
    assert code == 1, (
        f"bare file-form miss must raise exit_code=1, got {raised!r}")
    text = str(raised)
    assert "FILE-FORM" in text.upper() or "hash-suffix" in text.lower()
    assert not (ext / "addressables" / "catalog.json").exists(), (
        "gate fired AFTER output writes — partial finals escaped")


def test_stage2_warn_ledgers_braced_selfindexed_and_dangling(
        fx_stage2, tmp_path, monkeypatch):
    """Evidence classes are honest absences, never fatal: braced provider
    prefixes, self-indexed absent bundles, and dangling decimal keys all warn
    into catalog-coverage.json while the run exits 0 — with the ledger blocks'
    pinned {count, sample} schema."""
    ext = _write_stage2_upstreams(tmp_path / "ext")
    rc, _mod = _drive_stage2_run(monkeypatch, WARN_SPEC, ext, fx_stage2)
    assert rc == 0, f"warn-only evidence classes must not fail the run: rc={rc}"
    cov = read_json(ext / "addressables" / "catalog-coverage.json")

    for block in ("danglingDependencyKeys", "outOfRosterFileReferences"):
        entry = cov.get(block)
        assert isinstance(entry, dict) and set(entry) >= {"count", "sample"}, (
            f"coverage.{block} missing the pinned {{count, sample}} schema: "
            f"{entry!r}")
        assert isinstance(entry["count"], int) and entry["count"] >= 0
        assert isinstance(entry["sample"], list)

    danglers = cov["danglingDependencyKeys"]
    assert danglers["count"] == 1 and danglers["sample"] == ["888888"], danglers

    oor = cov["outOfRosterFileReferences"]
    assert oor["count"] == 2, f"{oor!r} — braced/self-indexed misses must ledger"
    refs = {row["reference"] for row in oor["sample"]}
    assert "{RSC}dlc-hospital-ui.bundle" in refs, (
        "braced provider-prefix reference missing from the warning ledger")
    assert all({"normalized", "reference"} <= set(row) for row in oor["sample"])
    normalized = {row["normalized"] for row in oor["sample"]}
    assert "dlc-hospital-ui" in normalized
    assert "absent-selfindexed" in normalized, (
        "self-indexed absent bundle (catalog indexes it as its own key) must "
        "land in the ledger, not the gate")

    # every miss stayed OUT of the fatal path AND out of the resolved universe
    cat = read_json(ext / "addressables" / "catalog.json")
    flat_resolved = set()
    for k in cat["keys"]:
        for b in ([k["bundle"]] if k["bundle"] else []) + k["dependencies"]:
            flat_resolved.add(Path(b).name.lower())
    assert "dlc-hospital-ui.bundle" not in flat_resolved
    rooms_rel = next(r["relpath"] for r in roster_rows()
                     if Path(r["relpath"]).name == "rooms_assets_all.bundle")
    by_key = {row["key"]: row for row in cat["keys"]}
    assert by_key["absent-selfindexed.bundle"]["bundle"] == rooms_rel
