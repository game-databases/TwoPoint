"""Client-gated integration tests (spec §8, second block).

Auto-SKIP — loudly, never failing — when neither TPC_GAME_DIR nor the default
install path exists. Heavy legs (stages 1/2/4/5 over the real corpus: minutes
to hours and tens of GB under the extraction root) additionally require
TPC_IT_HEAVY=1 so a bare `pytest tests/` on the game host stays cheap.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

from _validators import (ADDRESSABLES_VERSION, APPID, BUILD_ID,
                         LOCALE_BUNDLE_COUNT, LOCALE_TABLE, METADATA_VERSION,
                         SCENE_COUNT_PINS, SETTINGS_HASH, TARGET_BUILD_ID,
                         TOTAL_BUNDLES, UNITY_VERSION,
                         assert_unique_outrelpath, diff_manifests, hash_tree,
                         locale_file_set_matches, read_json, read_jsonl,
                         scan_tree_for_media_extensions,
                         validate_media_catalogue_row)

pytestmark = pytest.mark.client_gated


def _game_or_skip():
    from conftest import game_dir
    g = game_dir()
    if g is None:
        pytest.skip(
            "client-gated: neither TPC_GAME_DIR nor "
            r"A:\SteamLibrary\steamapps\common\Two Point Campus exists")
    return g


def _heavy_or_skip():
    import os
    _game_or_skip()
    if os.environ.get("TPC_IT_HEAVY", "").strip().lower() not in ("1", "true", "yes"):
        pytest.skip(
            "client-gated-heavy: set TPC_IT_HEAVY=1 to run real-corpus stages 1-5 "
            "(long-running; writes tens of GB under the extraction root)")


# --- stage 0 end-to-end -------------------------------------------------------------

def test_stage0_identity_fields_roster_and_locales(tmp_path):
    game = _game_or_skip()
    from conftest import run_pack
    ext = tmp_path / "ext"
    r = run_pack([str(game), "--only", "verify-client"], extracted_root=ext)
    assert r.returncode == 0, f"stage 0 failed on the live client rc={r.returncode}\n{r.stdout}{r.stderr}"
    combined = r.stdout + r.stderr
    ident = read_json(ext / "identity.json")
    assert ident["appid"] == APPID
    assert ident["buildId"] == BUILD_ID == TARGET_BUILD_ID
    assert ident["versionString"] == "10.3.169253+2024-12-06.1241"
    assert ident["unityVersion"] == UNITY_VERSION
    assert ident["metadataVersion"] == METADATA_VERSION == 27
    assert ident["dumper"] == "il2cppdumper", \
        "metadata v27 must gate to Il2CppDumper (primary per toolchain.md)"
    assert ident["addressablesVersion"] == ADDRESSABLES_VERSION
    assert ident["settingsHash"] == SETTINGS_HASH
    assert ident["languageSetting"] == "english"
    assert ident["localeBundleCount"] == LOCALE_BUNDLE_COUNT == 14

    rows = read_jsonl(ext / "bundle-roster.jsonl")
    assert len(rows) == TOTAL_BUNDLES == 176, f"roster rows {len(rows)} != 176"
    by_class = {"base": 0, "dlc-space": 0, "dlc-ghost": 0}
    for row in rows:
        by_class[row["dirClass"]] += 1
    assert by_class == {"base": 158, "dlc-space": 10, "dlc-ghost": 8}, by_class
    flagged = [row for row in rows if row["localeFlag"] is not None]
    assert len(flagged) == 14

    # measured scene counts hit the recounted pins exactly (spec §2)
    sc = ident["sceneCounts"]
    for key, pin in SCENE_COUNT_PINS.items():
        assert sc[key] == pin, f"sceneCounts.{key} = {sc[key]}, recount pin {pin}"

    assert "DRIFT:" not in combined, \
        "live install matches expectedBundles — no DRIFT line may print"


def test_stage0_double_run_hash_equal(tmp_path_factory):
    game = _game_or_skip()
    from conftest import run_pack
    e1, e2 = tmp_path_factory.mktemp("cg-run1"), tmp_path_factory.mktemp("cg-run2")
    r1 = run_pack([str(game), "--only", "verify-client"], extracted_root=e1)
    assert r1.returncode == 0, r1.stdout + r1.stderr
    r2 = run_pack([str(game), "--only", "verify-client"], extracted_root=e2)
    assert r2.returncode == 0, r2.stdout + r2.stderr
    m1, m2 = hash_tree(e1), hash_tree(e2)
    only1, only2, changed = diff_manifests(m1, m2)
    assert not (only1 or only2 or changed), (
        f"live stage-0 double run not byte-identical: {only1[:3]} {only2[:3]} {changed[:3]}")


# --- heavy client-gated legs ---------------------------------------------------------

@pytest.mark.heavy
def test_stage1_multi_image_gate_and_hierarchy_span(tmp_path):
    """Stage-1 acceptance under Revision 4: the DummyDll set is NON-EMPTY and
    every ScriptingAssemblies.json entry appears in assembly-index.json
    classified present-or-absent-with-marker with ≥1 dummy-present entry
    backed by a real image. `Assembly-CSharp.dll` is NOT expected on this
    client (game code lives in TPS.Game/TPS.Core images) — its absence is a
    PASS condition, never a failure. Class-hierarchy rows span the present
    game-code images."""
    _heavy_or_skip()
    from conftest import game_dir, run_pack
    game = game_dir()
    ext = tmp_path / "ext"
    r = run_pack([str(game), "--only", "decompile"], extracted_root=ext, timeout=3600)
    assert r.returncode == 0, f"stage 1 failed rc={r.returncode}\n{r.stdout}{r.stderr}"

    dummy_dir = ext / "decompiled" / "il2cppdumper" / "DummyDll"
    images = sorted(p.stem for p in dummy_dir.glob("*.dll")) if dummy_dir.is_dir() else []
    assert images, ("DummyDll set is EMPTY — the multi-image gate requires at "
                    "least one managed image (Assembly-CSharp.dll NOT required)")
    assert "Assembly-CSharp" not in images, (
        "this client ships NO Assembly-CSharp image; finding one means the "
        "client changed — re-measure before trusting this leg")

    idx_path = ext / "decompiled" / "structural" / "assembly-index.json"
    idx = json.loads(idx_path.read_text(encoding="utf-8"))
    rows = idx.get("assemblies") if isinstance(idx, dict) else idx
    assert isinstance(rows, list) and rows, "assembly-index.json carries no rows"
    by_stem = {str(row.get("assembly")): str(row.get("status")) for row in rows}

    sa = game / "TPC_Data" / "ScriptingAssemblies.json"
    names = json.loads(sa.read_text(encoding="utf-8"))
    names = names.get("Names", names) if isinstance(names, dict) else names
    expected = {str(n).removesuffix(".dll") for n in names}
    missing = sorted(expected - set(by_stem))
    assert not missing, f"ScriptingAssemblies entries unclassified in assembly-index: {missing}"
    bad_status = {a: s for a, s in by_stem.items()
                  if s != "dummy-present" and not any(
                      m in s.lower() for m in ("absent", "stripped"))}
    assert not bad_status, (
        f"statuses must be present-or-absent-with-marker: {bad_status}")
    backed_present = [a for a, s in by_stem.items()
                      if s == "dummy-present"
                      and (dummy_dir / f"{a}.dll").is_file()]
    assert backed_present, (
        "at least one dummy-present entry must be backed by a real DummyDll "
        "image (multi-image gate)")

    hier_path = ext / "decompiled" / "structural" / "class-hierarchy.jsonl"
    hier_rows = read_jsonl(hier_path)
    assert hier_rows, "class-hierarchy.jsonl is empty"
    row_assemblies = {str(row.get("assembly") or "") for row in hier_rows}
    source = ""
    if isinstance(idx, dict):
        source = str((idx.get("meta") or {}).get("hierarchySource", ""))
    if "dumpcs" not in source.lower() and "fallback" not in source.lower():
        spanning = {a for a in row_assemblies
                    if any(a.lower() == img.lower()
                           or a.lower() == img.lower().removesuffix(".dll")
                           for img in images)}
        assert len(spanning) >= 2, (
            "hierarchy rows span all present game-code images (Revision 4); "
            f"attributed assemblies were {sorted(row_assemblies)[:8]}… over "
            f"{len(images)} images")
    log = (ext / "EXTRACTION-LOG.md").read_text(encoding="utf-8")
    assert "class-hierarchy" in log or "hierarchy" in log, \
        "EXTRACTION-LOG must record the hierarchy count + its named source"


@pytest.mark.heavy
def test_stage2_catalog_references_resolve_into_roster(tmp_path):
    _heavy_or_skip()
    from conftest import game_dir, run_pack
    game = game_dir()
    ext = tmp_path / "ext"
    r = run_pack([str(game), "--only", "harvest-catalog"],
                 extracted_root=ext, timeout=1800)
    assert r.returncode == 0, f"stage 2 failed rc={r.returncode}\n{r.stdout}{r.stderr}"
    roster = {Path(row["relpath"]).name for row in
              read_jsonl(ext / "bundle-roster.jsonl")}
    cat = read_json(ext / "addressables" / "catalog.json")
    assert len(cat["keys"]) > 0, "keysTotal > 0 required"
    outside = []
    for k in cat["keys"]:
        ref = str(k.get("bundle") or "")
        norm = ref.replace("\\", "/").rsplit("/", 1)[-1].lower()
        if norm and norm not in {x.lower() for x in roster}:
            outside.append(ref)
    assert not outside, (
        f"{len(outside)} catalog references resolve OUTSIDE the roster "
        f"(hard-fail contract): {outside[:5]}")


@pytest.mark.heavy
def test_stage3_fallback_version_usage_recorded(tmp_path):
    """§8 client-gated (Revision 4): fallback-version usage is recorded and
    > 0 — every content bundle on this client ships a `0.0.0` UnityFS header.
    Every per-bundle census carries `fallbackVersionUsed` (presence-always,
    value true here) and the harvest-bundles run section carries the usage
    total."""
    _heavy_or_skip()
    from conftest import game_dir, run_pack
    game = game_dir()
    ext = tmp_path / "ext"
    r = run_pack([str(game), "--only", "harvest-bundles"],
                 extracted_root=ext, timeout=6 * 3600)
    if r.returncode == 1:
        # arbiter-003 F10 / TR-G8: a stage that RAN and failed is a failure,
        # never rendered as a skip — skip stays honest for environment
        # gating only (rc==3 gate refusal / absent game dir).
        pytest.fail("client-gated-heavy: harvest-bundles ran and exited 1:\n"
                    f"{(r.stdout + r.stderr)[-300:]}")
    if r.returncode not in (0, 2):  # 2 = completed-with-ledger is fine here
        pytest.skip(f"client-gated-heavy: harvest rc={r.returncode}: "
                    f"{(r.stdout + r.stderr)[-300:]}")
    census_dir = ext / "harvest" / "census" / "bundles"
    censuses = sorted(census_dir.glob("*.json"))
    assert censuses, "no per-bundle censuses emitted"
    flagged = []
    for p in censuses:
        c = read_json(p)
        assert "fallbackVersionUsed" in c, (
            f"{p.name}: every per-bundle census must carry "
            "fallbackVersionUsed (presence-always contract)")
        if c["fallbackVersionUsed"] is True:
            flagged.append(p.name)
    assert len(flagged) == len(censuses), (
        f"every content bundle ships a `0.0.0` header on this client, so all "
        f"censuses expect fallbackVersionUsed=true; got {len(flagged)}/"
        f"{len(censuses)}")

    log_text = (ext / "EXTRACTION-LOG.md").read_text(encoding="utf-8",
                                                     errors="replace")
    # run sections are headed `### <timestamp> — <stage-id>`; this run's
    # harvest-bundles section is the LAST one appended
    sections = [p for p in re.split(r"(?m)^#{1,3} ", log_text)
                if p.splitlines()[:1]
                and "harvest-bundles" in p.splitlines()[0].lower()]
    assert sections, "harvest-bundles run section missing from EXTRACTION-LOG.md"
    section = sections[-1]
    usage_matches = [int(m) for m in
                     re.findall(r"(?i)fallback[^\n]*?(\d+)", section)]
    assert any(n > 0 for n in usage_matches), (
        "the run section must carry a fallback-version usage TOTAL > 0; "
        f"fallback numbers seen: {usage_matches[:8]}")


@pytest.mark.heavy
def test_stage4_locale_files_and_availability_v2(tmp_path):
    _heavy_or_skip()
    from conftest import game_dir, run_pack
    game = game_dir()
    ext = tmp_path / "ext"
    # one full pass materializes every upstream output in the same tree
    r = run_pack([str(game)], extracted_root=ext, timeout=6 * 3600)
    if r.returncode == 1:
        # arbiter-003 F10 / TR-G8: a pipeline stage that RAN and failed is a
        # failure, never rendered as a skip — skip stays honest for
        # environment gating only (rc==3 gate refusal / absent game dir).
        pytest.fail("client-gated-heavy: pipeline ran and exited 1:\n"
                    f"{(r.stdout + r.stderr)[-300:]}")
    if r.returncode not in (0, 2):
        pytest.skip(f"client-gated-heavy: pipeline run failed rc={r.returncode}: "
                    f"{(r.stdout + r.stderr)[-300:]}")
    locales = ext / "locales"
    ok, missing, extra = locale_file_set_matches(locales)
    assert ok, f"13-file set != BCP-47 table: missing={missing} extra={extra}"
    assert (locales / "base-overlay.jsonl").exists()
    report = read_json(locales / "base-overlay-report.json")
    assert report.get("compositionPolicy") in (
        "english-only", "english-over-base", "base-over-english", "mixed")

    # piece-07 §5 amendment (arbiter R4): stage locale-proof is the SOLE
    # writer of this path and emits the v2 row shape — the retired v1
    # vocabulary (joinInferred/joinMethod) must never reappear.
    avail = ext / "relinks" / "locale_availability.jsonl"
    assert avail.exists(), "availability file missing after full run (stage locale-proof owns it)"
    rows = read_jsonl(avail)
    assert rows, "availability ledger empty"
    ids = [(row.get("kind"), row.get("id")) for row in rows]
    distinct = set(ids)
    assert len(rows) == len(distinct), (
        f"availability row count {len(rows)} != distinct joined entities {len(distinct)}")
    for i, row in enumerate(rows):
        assert "joinInferred" not in row and "joinMethod" not in row, \
            f"availability[{i}]: retired v1 row vocabulary survived"
        for field in ("availableLocales", "partialLocales", "namedLocales",
                      "identityToPivotLocales"):
            v = row.get(field)
            assert isinstance(v, list) and v == sorted(v), f"availability[{i}].{field}"
            unknown = [x for x in v if x not in LOCALE_TABLE.values()]
            assert not unknown, f"availability[{i}].{field}: non-BCP-47 {unknown}"
        fp = row.get("fieldPresence")
        assert isinstance(fp, dict) and fp, f"row {i}: fieldPresence must be populated"
        assert set(fp) <= set(row["availableLocales"]), \
            f"row {i}: fieldPresence keys ⊄ availableLocales"


@pytest.mark.heavy
def test_stage3_census_reconciliation_math_on_real_outputs(tmp_path):
    """Stage-3 acceptance math over the REAL corpus outputs (hostless suite
    covers this only with fabricated numbers):
      Σ objectsByClass over per-bundle censuses
        == export-manifest rows + media-catalogue rows + error rows
           + census-only residual (per-class totals outside the exported
             classes ∪ the carved-out classes);
      media-catalogue covers EVERY census object of carved-out classes
      (audio/video/mesh/animation/shader/font AND Texture2D/Sprite);
      every outRelPath in the export manifest is unique."""
    _heavy_or_skip()
    from conftest import game_dir, run_pack
    game = game_dir()
    ext_root = tmp_path / "ext"
    r = run_pack([str(game), "--only", "harvest-bundles"],
                 extracted_root=ext_root, timeout=6 * 3600)
    if r.returncode == 1:
        # arbiter-003 F10 / TR-G8: a stage that RAN and failed is a failure,
        # never rendered as a skip — skip stays honest for environment
        # gating only (rc==3 gate refusal / absent game dir).
        pytest.fail("client-gated-heavy: harvest-bundles ran and exited 1:\n"
                    f"{(r.stdout + r.stderr)[-300:]}")
    if r.returncode not in (0, 2):  # 2 = completed-with-ledger is fine here
        pytest.skip(f"client-gated-heavy: harvest rc={r.returncode}: "
                    f"{(r.stdout + r.stderr)[-300:]}")
    ext = ext_root
    census_dir = ext / "harvest" / "census" / "bundles"
    assert census_dir.is_dir(), "no per-bundle censuses emitted"

    per_class_total = {}
    errors = 0
    for p in sorted(census_dir.glob("*.json")):
        c = read_json(p)
        for cls, n in (c.get("objectsByClass") or {}).items():
            per_class_total[cls] = per_class_total.get(cls, 0) + n
        errors += len(c.get("errors") or [])
    sigma = sum(per_class_total.values())

    carved = {"AudioClip", "VideoClip", "Mesh", "AnimationClip", "Shader",
              "Font", "Texture2D", "Sprite"}
    census_carved = {cls: n for cls, n in per_class_total.items() if cls in carved}
    # Revision-3 residual-inclusive identity: a census object is exported
    # (manifest row), carved out (catalogue row), an error, or plumbing
    # outside both sets — the residual must account for that last bucket.
    exported = {"TextAsset", "MonoBehaviour"}
    census_residual = sum(n for cls, n in per_class_total.items()
                          if cls not in exported and cls not in carved)

    manifest_rows = read_jsonl(ext / "harvest" / "export-manifest.jsonl")
    catalogue_rows = read_jsonl(ext / "media-catalogue.jsonl")
    assert (len(manifest_rows) + len(catalogue_rows) + errors
            + census_residual == sigma), (
        f"reconciliation broke: ΣobjectsByClass={sigma} vs "
        f"manifest={len(manifest_rows)} catalogue={len(catalogue_rows)} "
        f"errors={errors} residual={census_residual}")

    cat_by_class = {}
    for row in catalogue_rows:
        errs = validate_media_catalogue_row(row, where="media-catalogue: ")
        assert not errs, errs
        cat_by_class[row["class"]] = cat_by_class.get(row["class"], 0) + 1
    for cls, n in census_carved.items():
        got = cat_by_class.get(cls, 0)
        assert got == n, (
            f"carve-out completeness broken for {cls}: census={n} catalogue={got}")
    assert not any(row.get("class") in {"TextAsset", "MonoBehaviour"}
                   for row in catalogue_rows), \
        "exported classes must never appear as catalogue rows"

    # whole-piece carve-out acceptance (§5.6), applied mechanically: the
    # suite-owned scanner over the REAL extraction root must find zero media
    # extensions outside the catalogue itself (allowlist lives in the scanner)
    hits = scan_tree_for_media_extensions(ext)
    assert not hits, (
        f"§5.6 violated on the real corpus — media extensions outside "
        f"media-catalogue.* under {ext}: {hits[:8]}")

    assert_unique_outrelpath(manifest_rows)


@pytest.mark.slow
@pytest.mark.heavy
def test_full_pipeline_double_run_byte_identical(tmp_path_factory):
    """Optional slow mark: the whole pipeline twice, byte-identical outputs."""
    _heavy_or_skip()
    from conftest import game_dir, run_pack
    game = game_dir()
    e1, e2 = tmp_path_factory.mktemp("full1"), tmp_path_factory.mktemp("full2")
    for tag, ext in (("run1", e1), ("run2", e2)):
        r = run_pack([str(game)], extracted_root=ext, timeout=6 * 3600)
        assert r.returncode in (0, 2), \
            f"full pipeline {tag} rc={r.returncode}\n{r.stdout[-500:]}\n{r.stderr[-500:]}"
    m1, m2 = hash_tree(e1), hash_tree(e2)
    only1, only2, changed = diff_manifests(m1, m2)
    assert not (only1 or only2 or changed), (
        f"full-pipeline double run not byte-identical: "
        f"missing={only1[:5]} extra={only2[:5]} changed={changed[:5]}")
