"""Stage 3 `harvest-bundles` obligations (spec §8 stage-3 bullets + R1 lane)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from _impl import (FAMILY_NAMES, MEDIA_COMPLETE_NAMES, RECONCILE_NAMES,
                   get_sym, load_any, load_tool, skip_if_none)
from _validators import (MEDIA_EXTENSION_RE, MEDIA_EXTENSIONS_AUDIO_VIDEO,
                         MEDIA_EXTENSIONS_IMAGE, assert_unique_outrelpath,
                         scan_tree_for_media_extensions, validate_media_catalogue_row)

sys.path.insert(0, str(Path(__file__).parent))


# --- family splitter ---------------------------------------------------------------

FAMILY_CASES = [
    # (bundle filename, family, contentAxis, hashNamed)
    ("items-courses-magic_assets_all.bundle", "items-courses-magic", "base", False),
    ("rooms_assets_all.bundle", "rooms", "base", False),
    ("dlc-space-ui_assets_all.bundle", "ui", "dlc-space", False),
    ("dlc-ghost-audio_assets_all.bundle", "audio", "dlc-ghost", False),
    ("041ed57fabcdef1234567890abcdef12_monoscripts.bundle",
     "monoscripts", "base", True),                                   # hash-prefixed
    ("scenes_scenes_sandbox_optimised.unity",
     "scenes_scenes_sandbox", "base", False),                        # _optimised.unity shape
    ("dlc-space-scenes_launchpadlevel.unity.bundle",
     "scenes_launchpadlevel", "dlc-space", False),                   # .unity shape
]


def test_family_splitter():
    mod = skip_if_none(load_any("stage3_harvest_bundles.py", "tpc_common.py"),
                       "tools/stage3_harvest_bundles.py | tools/tpc_common.py")
    fn = skip_if_none(get_sym(mod, *FAMILY_NAMES), "family splitter")
    for name, family, axis, hash_named in FAMILY_CASES:
        dir_class = axis  # roster dirClass == contentAxis enum (R5)
        try:
            out = fn(name, dir_class)
        except TypeError:
            try:
                out = fn(name)
            except TypeError:
                out = fn(bundle_name=name, dir_class=dir_class)
        if isinstance(out, dict):
            got = (out.get("family"), out.get("contentAxis") or out.get("axis"),
                   bool(out.get("hashNamed")))
        elif isinstance(out, (tuple, list)):
            vals = list(out[:3]) + [False] * (3 - len(out[:3]))
            got = (vals[0], vals[1], bool(vals[2]))
        else:
            pytest.fail(f"family splitter returned unsupported shape {type(out).__name__}: {out!r}")
        assert got[0] == family, f"family({name!r}) = {got[0]!r}, expected {family!r}"
        assert got[1] == axis, (
            f"contentAxis({name!r}) = {got[1]!r}, expected {axis!r} "
            "(pinned enum base|dlc-space|dlc-ghost)")
        assert got[2] == hash_named, f"hashNamed({name!r}) = {got[2]!r}, expected {hash_named}"


# --- census reconciliation math on fabricated files ---------------------------------

def _fabricated_reconciliation():
    """Σ objectsByClass over censuses == manifest + catalogue + errors (9 = 5+4+0)."""
    census_rows = [
        {"bundle": "b1.bundle", "objectsByClass": {"TextAsset": 2, "MonoBehaviour": 3,
                                                   "Texture2D": 1}, "errors": []},
        {"bundle": "b2.bundle", "objectsByClass": {"AudioClip": 2, "Mesh": 1}, "errors": []},
    ]
    manifest_rows = [
        {"sourceBundle": "b1.bundle", "pathId": i, "class": cls,
         "outRelPath": f"harvest/x{i}", "bytes": 8}
        for i, cls in enumerate(["TextAsset"] * 2 + ["MonoBehaviour"] * 3)
    ]
    catalogue_rows = [
        {"class": "Texture2D", "bundle": "b1.bundle", "name": "t", "pathId": 90,
         "bytesEstimate": 4, "contentAxis": "base"},
        {"class": "AudioClip", "bundle": "b2.bundle", "name": "a", "pathId": 91,
         "bytesEstimate": 4, "contentAxis": "base"},
        {"class": "AudioClip", "bundle": "b2.bundle", "name": "b", "pathId": 92,
         "bytesEstimate": 4, "contentAxis": "base"},
        {"class": "Mesh", "bundle": "b2.bundle", "name": "m", "pathId": 93,
         "bytesEstimate": 4, "contentAxis": "base"},
    ]
    return census_rows, manifest_rows, catalogue_rows


def _call_reconcile(fn, census, manifest, catalogue):
    try:
        out = fn(census, manifest, catalogue)
    except TypeError:
        out = fn({"bundles": census}, manifest, catalogue)
    if isinstance(out, bool):
        return out, ""
    if isinstance(out, dict):
        return bool(out.get("ok", out.get("valid", True))), json.dumps(out, default=str)[:400]
    if isinstance(out, tuple) and out:
        return bool(out[0]), str(out[-1])
    return bool(out), str(out)


def test_census_reconciliation_consistent_set():
    mod = skip_if_none(load_tool("stage3_harvest_bundles.py"),
                       "tools/stage3_harvest_bundles.py")
    fn = skip_if_none(get_sym(mod, *RECONCILE_NAMES), "census reconciliation checker")
    ok, detail = _call_reconcile(fn, *_fabricated_reconciliation())
    assert ok, f"consistent fabricated set failed reconciliation: {detail}"


@pytest.mark.parametrize("drop_from", ["manifest", "catalogue"])
def test_census_reconciliation_detects_gap(drop_from):
    mod = load_tool("stage3_harvest_bundles.py")
    if mod is None:
        pytest.skip("impl-missing: tools/stage3_harvest_bundles.py")
    fn = get_sym(mod, *RECONCILE_NAMES)
    if fn is None:
        pytest.skip(f"impl-missing: reconciliation checker (tried {RECONCILE_NAMES})")
    census, manifest, catalogue = _fabricated_reconciliation()
    if drop_from == "manifest":
        manifest = manifest[:-1]
    else:
        catalogue = catalogue[:-1]
    raised = False
    try:
        ok, detail = _call_reconcile(fn, census, manifest, catalogue)
        raised = not ok
        detail = detail or "returned falsy"
    except (AssertionError, ValueError, RuntimeError) as exc:
        raised = True
        detail = f"{type(exc).__name__}: {exc}"
    assert raised, (
        f"dropping a {drop_from} row must break the reconciliation numbers; got pass ({detail})")


# --- media-catalogue completeness (carve-out incl. Texture2D/Sprite, R1 lane) -------

def test_media_catalogue_completeness_checker():
    mod = load_tool("stage3_harvest_bundles.py")
    if mod is None:
        pytest.skip("impl-missing: tools/stage3_harvest_bundles.py")
    fn = get_sym(mod, *MEDIA_COMPLETE_NAMES)
    if fn is None:
        pytest.skip("impl-missing: media-completeness checker "
                    f"(tried {MEDIA_COMPLETE_NAMES})")

    def invoke(census, catalogue):
        try:
            out = fn(census, catalogue)
        except TypeError:
            out = fn({"bundles": census}, catalogue)
        if isinstance(out, bool):
            return out
        if isinstance(out, tuple) and out:
            return bool(out[0])
        if isinstance(out, dict):
            return bool(out.get("ok", out.get("complete", True)))
        return bool(out)

    census, _manifest, catalogue = _fabricated_reconciliation()
    # carved classes in census: Texture2D 1 + AudioClip 2 + Mesh 1 = catalogue rows 4
    try:
        assert invoke(census, catalogue) is True, \
            "consistent carve-out set (Texture2D/AudioClip/Mesh counts == catalogue rows) reported incomplete"
    except (AssertionError, ValueError, RuntimeError) as exc:
        if "reported incomplete" not in str(exc):
            raise
        raise AssertionError(
            f"completeness checker crashed on a CONSISTENT input set: {exc}") from exc

    detected = False
    try:
        detected = not invoke(census, catalogue[:-1])
    except (AssertionError, ValueError, RuntimeError):
        detected = True
    assert detected, "removing a Texture2D/AudioClip/Mesh catalogue row must be detected"


def test_media_catalogue_row_schema_includes_texture_and_sprite_classes():
    """R1: Texture2D/Sprite are CATALOGUE-ONLY rows with the same row machinery."""
    rows = [
        {"class": "Texture2D", "bundle": "x.bundle", "name": "t", "pathId": 1,
         "bytesEstimate": 10, "contentAxis": "base"},
        {"class": "Sprite", "bundle": "x.bundle", "name": "s", "pathId": 2,
         "bytesEstimate": 20, "contentAxis": "dlc-space"},
        {"class": "AudioClip", "bundle": "y.bundle", "name": "a", "pathId": 3,
         "bytesEstimate": 30, "contentAxis": "dlc-ghost"},
    ]
    for i, r in enumerate(rows):
        errs = validate_media_catalogue_row(r, where=f"row[{i}]: ")
        assert not errs, f"catalogue-row machinery broken: {errs}"
    bad = dict(rows[0]); bad["contentAxis"] = "dlc1-space"   # site-plane spelling banned
    assert validate_media_catalogue_row(bad), \
        "site-plane axis spelling dlc1-space must be rejected (enum is base|dlc-space|dlc-ghost)"


# --- export-manifest uniqueness ------------------------------------------------------

def test_outrelpath_uniqueness_assertion():
    clean = [{"outRelPath": f"harvest/f{i}.json"} for i in range(5)]
    assert assert_unique_outrelpath(clean)
    dup = clean + [{"outRelPath": "harvest/f0.json"}]
    with pytest.raises(AssertionError, match="duplicate outRelPath"):
        assert_unique_outrelpath(dup)


def test_bundle_identity_filenames_prevent_collisions_by_construction():
    """The construction rule: <bundle-stem>_<pathId> embeds bundle identity, so
    equal pathIds from different bundles never collide."""
    from _fixturelib import ENTITIES, BIG_FAMILY_COUNT
    rels = set()
    for eid, cls, family, stem, pid, fields in ENTITIES:
        rels.add(f"harvest/monobehaviours/{family}/{cls}/{stem}_{pid}.json")
    for i in range(BIG_FAMILY_COUNT):
        rels.add(f"harvest/monobehaviours/items-general/ItemBigConfig/"
                 f"items-general_assets_all_{20000 + i}.json")
    assert len(rels) == len(ENTITIES) + BIG_FAMILY_COUNT


# --- carve-out extension guard --------------------------------------------------------

def test_media_extension_guard_extension_sets():
    assert len(MEDIA_EXTENSIONS_AUDIO_VIDEO) == 8 and len(MEDIA_EXTENSIONS_IMAGE) == 7
    all_ext = set(MEDIA_EXTENSIONS_AUDIO_VIDEO + MEDIA_EXTENSIONS_IMAGE)
    assert len(all_ext) == 15
    for ext in all_ext:
        assert MEDIA_EXTENSION_RE.search(f"x.{ext}"), f"regex misses .{ext}"
        assert MEDIA_EXTENSION_RE.search(f"x.{ext.upper()}"), f"regex not case-insensitive on .{ext}"
    assert not MEDIA_EXTENSION_RE.search("x.txt")
    assert not MEDIA_EXTENSION_RE.search("media-catalogue.jsonl")


def test_carveout_guard_scan_tree(tmp_path):
    ext = tmp_path
    (ext / "harvest").mkdir(parents=True)
    (ext / "media-catalogue.jsonl").write_text(
        '{"class":"AudioClip","name":"theme.ogg"}\n', encoding="utf-8")
    (ext / "MEDIA-CATALOGUE.md").write_text("# audio-music (.fsb)\n", encoding="utf-8")
    (ext / "harvest" / "leak.ogg").write_bytes(b"\x00")
    (ext / "harvest" / "notes.txt").write_text("see sprite.png inside\n", encoding="utf-8")
    (ext / "harvest" / "clean.txt").write_text("nothing here\n", encoding="utf-8")
    hits = scan_tree_for_media_extensions(ext)
    joined = "\n".join(hits)
    assert any("leak.ogg" in h for h in hits), f"planted .ogg file missed: {hits}"
    assert any("notes.txt" in h for h in hits), f"planted .png mention missed: {hits}"
    assert "clean.txt" not in joined, "false positive on clean tree"
    assert "media-catalogue" not in joined and "MEDIA-CATALOGUE" not in joined, \
        "catalogue files must stay exempt from the guard"


def test_clean_tree_zero_hits(tmp_path):
    ext = tmp_path
    (ext / "harvest" / "textassets").mkdir(parents=True)
    (ext / "harvest" / "textassets" / "a.txt").write_text("plain\n", encoding="utf-8")
    hits = scan_tree_for_media_extensions(ext)
    assert hits == [], f"clean tree produced guard hits: {hits}"


# --- exit-2 emission fixture (black-box) ----------------------------------------------

def test_unreadable_bundle_drives_ledger_and_exit2(fx_stage3, tmp_path):
    """Every fixture bundle is deliberately non-UnityFS -> unreadable ledger +
    completed-with-ledger exit code 2 (never silent)."""
    from conftest import run_pack, seeded_extracted_root, tree_game
    ext_root = seeded_extracted_root(fx_stage3, tmp_path, "s3exit2")
    r = run_pack([tree_game(fx_stage3), "--only", "harvest-bundles"],
                 extracted_root=ext_root)
    assert r.returncode == 2, (
        f"unreadable synthetic bundles must yield exit 2 (completed-with-ledger), "
        f"got rc={r.returncode}\nSTDOUT:{r.stdout}\nSTDERR:{r.stderr}")
    ledger = ext_root / "harvest" / "census" / "unreadable.jsonl"
    assert ledger.exists(), "exit 2 without an unreadable.jsonl ledger row"
    lines = [ln for ln in ledger.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert lines, "unreadable.jsonl exists but is empty while bundles were unreadable"
    import json
    for ln in lines:
        row = json.loads(ln)
        assert any(k in row for k in ("reason", "error", "message")), \
            f"unreadable row lacks a reason: {row}"


# --- Revision 4: identity-sourced FALLBACK_UNITY_VERSION seeding ----------------------
# Content bundles' UnityFS headers read literally `0.0.0` on this client; before
# opening any bundle stages 3+4 seed UnityPy's fallback from identity.json's
# unityVersion, flip that census's fallbackVersionUsed, and move the run-section
# usage total. The substrates here are shared with the stage-4 tests (spec §8:
# "shared helper with stage 4").

SEED_SCRIPTS = ("unitypy_util.py", "stage3_harvest_bundles.py", "tpc_common.py")

sys.path.insert(0, str(Path(__file__).parent))
import _fixturelib as fx  # noqa: E402


def _seed_helper():
    from _impl import FALLBACK_SEED_NAMES, note_missing_symbol
    for script in SEED_SCRIPTS:
        mod = load_tool(script)
        if mod is None:
            continue
        fn = get_sym(mod, *FALLBACK_SEED_NAMES)
        if fn is not None:
            return mod, fn
    note_missing_symbol(
        "fallback-version seeder (tried "
        f"{FALLBACK_SEED_NAMES} across {', '.join(SEED_SCRIPTS)})")
    pytest.skip("impl-missing: fallback-version seeding helper not resolvable "
                "yet (CodeWriter pending)")


def _UNITY_VERSION():
    from _validators import UNITY_VERSION
    return UNITY_VERSION


def _invoke_seed(fn, bundle: Path, extracted_root: Path):
    """Call-shape ladder — the helper may take (path), (path, extracted_root),
    (header bytes) or keyword spellings; first matching shape wins."""
    from _impl import try_call_shapes
    return try_call_shapes(
        fn,
        ((bundle,), {}),
        ((bundle, extracted_root), {}),
        ((str(bundle)), {}),
        ((bundle.read_bytes(),), {}),
        ((), {"path": bundle, "extracted_root": extracted_root}),
        ((), {"bundle_path": bundle, "fallback_version": _UNITY_VERSION()}),
    )


def _used_flag(out):
    """Interpret a seeder's 'did this open use the fallback' signal."""
    if out is None:
        return None
    if isinstance(out, bool):
        return out
    if isinstance(out, (int, float)):
        return bool(out)
    if isinstance(out, tuple) and out:
        return bool(out[0])
    if isinstance(out, dict):
        for k in ("used", "fallbackUsed", "fallbackVersionUsed", "seeded"):
            if k in out:
                return bool(out[k])
    return None


def test_fallback_seed_triggers_on_zero_header_bundle(tmp_path):
    mod, fn = _seed_helper()
    bundles = fx.write_seed_probe_bundles(tmp_path / "bundles")
    cfg = getattr(__import__("UnityPy"), "config", None)
    before = getattr(cfg, "FALLBACK_UNITY_VERSION", None)
    out = _invoke_seed(fn, bundles["zero"], tmp_path)
    after = getattr(cfg, "FALLBACK_UNITY_VERSION", None) if cfg else None
    assert after == _UNITY_VERSION(), (
        f"after a `0.0.0` header the FALLBACK_UNITY_VERSION knob must be seeded "
        f"from identity.json's unityVersion ({_UNITY_VERSION()!r}); got {after!r} "
        f"(was {before!r})")
    assert _used_flag(out) is not False, (
        f"a `0.0.0`-header bundle must be flagged as using the fallback "
        f"(census mark contract); seeder returned {out!r}")
    _ = mod  # module kept for future symbol-level assertions


def test_fallback_seed_triggers_on_unparseable_header(tmp_path):
    _mod, fn = _seed_helper()
    bundles = fx.write_seed_probe_bundles(tmp_path / "bundles")
    out = _invoke_seed(fn, bundles["garbage"], tmp_path)
    cfg = getattr(__import__("UnityPy"), "config", None)
    assert getattr(cfg, "FALLBACK_UNITY_VERSION", None) == _UNITY_VERSION(), \
        "an unparseable header must trigger the identity-sourced seed too"
    assert _used_flag(out) is not False, (
        f"an unparseable-header bundle counts as fallback-seeded; got {out!r}")


def test_fallback_seed_skips_true_version_header(tmp_path):
    """catalog.bundle alone reports the true engine version — a well-formed
    header needs no fallback (usage total must not count it)."""
    _mod, fn = _seed_helper()
    bundles = fx.write_seed_probe_bundles(tmp_path / "bundles")
    out = _invoke_seed(fn, bundles["true-version"], tmp_path)
    used = _used_flag(out)
    if used is not None:
        assert used is False, (
            f"a bundle whose header already reads {_UNITY_VERSION()} must NOT "
            f"count toward the fallback usage total; got {out!r}")
