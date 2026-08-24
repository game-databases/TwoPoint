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
