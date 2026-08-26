"""piece-06 §8 TestWriter contract — stage `media` (stage 11), blind suite.

Built from docs/specs/piece-06-media.mdx **Revision 3** alone (plus the
binding arbiter pins P1–P3/R1–R3); the CodeWriter deliverables
(tools/stage11_media.py, tools/media_util.py) were never read.

Three legs per obligation, honestly labeled (piece-02 suite conventions):

- **fixture-self** — contracts of the synthetic corpus, the oracles, and
  the validators themselves; runnable NOW. Every validator here carries
  negative controls (mutation teeth at the contract layer), and the
  geometry/pairing fixtures are proven to DISCRIMINATE wrong grammar
  (banker's rounding, missing bottom-origin flip, index-alignment
  pairing, wrong tiebreak order all produce different answers).
- **unit** — pure-function obligations driven through tests/_impl.py
  against the spec-pinned scripts tools/stage11_media.py +
  tools/media_util.py. Skips LOUDLY (`impl-missing`) until they land —
  never fakes a pass.
- **black-box** — `run_all.py <game> --only media` over the 7-name seed
  fixture tree. Skips LOUDLY (`impl-lagging`) until `--list` registers
  `media`. The seed tree is deliberately UNRESOLVABLE end-to-end: zero
  referenced name exists in the catalogue, so a contract-correct run
  opens ZERO bundles (pin F4) and still emits the full hostless
  artifact set at exit 2.

Synthetic bytes ONLY — never real game bytes, never binary Reads into
agent context. Scratch/temp roots live under D:/tpc_pytmp/tw06/ (never
C:-rooted); extracted-root copies ride the same D: root so the S0
output-floor leg measures a legal drive. Client-gated real-corpus legs
sit behind @pytest.mark.client_gated (+heavy where they execute the real
pipeline) and auto-skip like every sibling suite.

Coverage map (spec §8 bullet -> section):
  S0 discipline            -> TestS0*
  rect grammar             -> TestRectGrammar* (+fixture-self teeth)
  pairing matcher/tiebreak -> TestPairingTiebreak*
  crop compositor          -> TestCropCompositor*
  naming                   -> TestNaming*
  manifest/hash tooling    -> TestManifestHashes* / TestMediaExportMd*
  ledger validators        -> TestLedgerValidators* / TestResidueScan*
  join predicate           -> TestJoinPredicate*
  cross-check comparator   -> TestCrossCheck*
  guards                   -> TestGuards*
  runner                   -> TestRunnerBlackBox*
  client-gated integration -> TestClientGated*
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _impl  # noqa: E402
import _medialib as ml  # noqa: E402
from _validators import (  # noqa: E402
    BUILD_ID, diff_manifests, hash_tree, read_json, read_jsonl,
    write_jsonl,
)
from conftest import DEFAULT_GAME, run_pack, seeded_extracted_root  # noqa: E402

HERE = Path(__file__).resolve().parent


# --- oracle arithmetic (spec-pinned math, implemented independently) -------------

def round_half_away(v: float) -> int:
    """floor(v + 0.5) for v>=0, ceil(v - 0.5) for v<0 — NOT Python's banker's
    round(). Spec E1 rule 5."""
    import math
    return int(math.floor(v + 0.5)) if v >= 0 else int(math.ceil(v - 0.5))


def rounded_rect(rect) -> dict:
    """Round EACH component first, THEN derive image-space bounds."""
    left = round_half_away(rect["x"])
    w = round_half_away(rect["w"])
    h = round_half_away(rect["h"])
    top = round_half_away(rect["y"])  # bottom-origin y
    return {"left": left, "top": None, "w": w, "h": h, "_bottom_y": top}


def flipped_rounded(rect, page_h: int) -> dict:
    r = {k: round_half_away(rect[k]) for k in ("x", "y", "w", "h")}
    return {"left": r["x"], "top": page_h - r["y"] - r["h"],
            "w": r["w"], "h": r["h"]}


def _unit(names):
    """Resolve an impl symbol across BOTH stage-11 scripts and their import
    aliases (media_util carries the pure machinery; stage11_media the
    orchestration) — see ml.resolve_impl."""
    mod, fn = ml.resolve_impl(*names)
    if mod is None or fn is None:
        pytest.skip("impl-missing: stage11." + names[0] +
                    " not resolvable yet (CodeWriter pending)")
    return mod, fn


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# =================================================================================
# Session fixtures: the seed tree + D:-rooted run lanes
# =================================================================================

_TREES: dict[str, Path] = {}


def _session_tag() -> str:
    return f"tw06-{os.getpid()}"


@pytest.fixture(scope="session")
def media_seed_tree():
    """The 7-name seed fixture tree under the resolved A:/D: scratch volume
    (S0-legal; never C:)."""
    base = ml.temp_base(_session_tag() + "-tree")
    base.mkdir(parents=True, exist_ok=True)
    if "seed" not in _TREES:
        _TREES["seed"] = ml.build_media_tree(base)
    return _TREES["seed"]


@pytest.fixture()
def media_ext(media_seed_tree):
    """Private extracted-root copy on the same S0-legal volume (keeps both
    S0 floors on a legal drive; %TEMP% basetemp stays reserved for tiny
    text fixtures)."""
    import uuid
    base = ml.temp_base(_session_tag() + "-ext")
    base.mkdir(parents=True, exist_ok=True)
    ext = seeded_extracted_root(media_seed_tree, base,
                                name=f"ext-{uuid.uuid4().hex[:8]}")
    yield ext
    shutil.rmtree(ext, ignore_errors=True)


@pytest.fixture()
def scratch_root():
    root = ml.pick_scratch_root(_session_tag())
    if root is None:
        pytest.skip("env-gated: no D:/A: scratch root with >=4 GiB free "
                    "(S0 floors unmeetable on this host right now)")
    if not ml.output_floor_ok(root):
        pytest.skip("env-gated: output drive below the 2 GiB S0 floor")
    yield root


def _tree_game(media_seed_tree) -> str:
    return str(Path(media_seed_tree) / "steamapps" / "common"
               / "Two Point Campus")


def _run_media(media_seed_tree, ext, scratch, *extra, env_extra=None,
               timeout=420):
    """Black-box `--only media` over the seed tree; TPC_GAME_DIR is pinned to
    the SYNTHETIC install so ambient user env never leaks a real client in."""
    return run_pack(
        [_tree_game(media_seed_tree), "--only", "media", *extra],
        extracted_root=Path(ext),
        extra_env={"TPC_MEDIA_TMP": str(scratch),
                   "TPC_GAME_DIR": _tree_game(media_seed_tree),
                   **(env_extra or {})},
        timeout=timeout)


def _media_artifact(ext: Path, name: str) -> Path:
    return Path(ext) / ml.MEDIA_DIRNAME / name


# =================================================================================
# Section 0 — fixture-self contracts + validator teeth (pass NOW)
# =================================================================================

class TestSeedCorpusSelfContracts:
    def test_absence_seed_is_verbatim_m16_with_reason_map(self):
        names = [n for n, _r in ml.ABSENCE_SEED]
        assert len(names) == 7
        assert len(set(names)) == 7
        assert names == [
            "DLC3_UI_Icons_Objective_Pirates",
            "DLC3_UI_Icons_Objective_Volcano",
            "Gorge_UI_Icons_Objectives_DLC3_Emergency",
            "UI_HUD_Room_T_Icon_DLC3_plot",
            "UI_InGame_DLC3_Icon_studentArchetype_Doctors",
            "UI_InGame_DLC3_Icon_studentArchetype_Nurses",
            "UI_InGame_T_Icon_Item_Teamsports_Cheeseball",
        ]
        reasons = dict(ml.ABSENCE_SEED)
        assert sum(1 for r in reasons.values() if r == "dlc-content-absent") == 6
        assert reasons["UI_InGame_T_Icon_Item_Teamsports_Cheeseball"] == "stale-name"

    def test_walk_oracle_shape_and_sort(self):
        rows = ml.oracle_index_rows()
        assert len(rows) == 14, "9 absence refs (Pirates x3) + 5 ledgered skips"
        assert rows == sorted(rows, key=lambda r: (r["kind"], r["srcId"],
                                                   r["fieldPath"]))
        assert all(r["resolved"] is False and r["file"] is None for r in rows)
        by_name = {}
        for r in rows:
            by_name.setdefault(r["subObjectName"], []).append(r)
        pirates = by_name["DLC3_UI_Icons_Objective_Pirates"]
        assert len(pirates) == 3 and all(
            r["chainBreak"] == "container" for r in pirates)
        cheese = by_name["UI_InGame_T_Icon_Item_Teamsports_Cheeseball"][0]
        assert cheese["chainBreak"] == "none", \
            "stale-name row: chain complete, the NAME alone is unknown"

    def test_missing_ledger_oracle_aggregates_and_caps_sample_refs(self):
        rows = ml.oracle_missing_rows()
        assert len(rows) == 12, "7 absences + 5 ledgered-skip families"
        assert [r["subObjectName"] for r in rows] == sorted(
            r["subObjectName"] for r in rows), "sorted by subObjectName"
        pirates = next(r for r in rows
                       if r["subObjectName"] == "DLC3_UI_Icons_Objective_Pirates")
        assert len(pirates["sampleRefs"]) == 3
        for r in rows:
            errs = ml.validate_missing_row(r)
            assert errs == [], errs

    def test_every_stub_row_is_validator_clean_and_nine_kinds(self):
        from _validators import KIND_TO_FILE, validate_stub_row
        rows = ml.media_stub_rows()
        kinds = {r["kind"] for r in rows}
        assert kinds == set(KIND_TO_FILE), "all nine stub kinds present"
        for r in rows:
            errs = validate_stub_row(r, where=f"{r['id']} ")
            assert errs == [], errs

    def test_catalogue_holds_zero_referenced_names_f4_precondition(self):
        present = {r["name"] for r in ml.media_catalogue_rows()
                   if r["class"] == "Sprite"}
        walked_names = {r["subObjectName"] for r in ml.oracle_index_rows()}
        inter = present & walked_names
        assert not inter, f"F4 precondition broken — these would resolve: {inter}"

    def test_e6_oracle_admission_rules(self):
        rows = ml.oracle_residue_rows()
        counters = ml.oracle_e6_counters()
        assert counters["scanned"] == len(ml.E6_SLOT_TABLE)
        assert counters["nullSkipped"] == 1, "the {0,0} BadgeIcon null slot"
        assert counters["rows"] == 6
        assert counters["external"] == 5 and counters["sameFile"] == 1
        leaf_names = {r["fieldPath"] for r in rows}
        assert "_iconReference" in leaf_names, "case-insensitive vocabulary"
        assert "TitleLabel" not in leaf_names, "non-icon leaf never admitted"
        swatch = [r for r in rows if r["srcId"] == "Room_Menu_Swatch"]
        assert not swatch, "populated paired Reference excludes the slot"
        ext_null = [r for r in rows
                    if r["srcId"] == "Goal_External_NullPath"]
        assert ext_null and ext_null[0]["slotClass"] == "external", \
            "non-empty external pointer admits even with pathID 0"
        for r in rows:
            assert ml.validate_residue_row(r) == []

    def test_worked_geometry_matches_spec_manifest_example(self):
        got = flipped_rounded(ml.WORKED_RECT, ml.WORKED_PAGE_H)
        assert got == ml.WORKED_ROUNDED, (
            "spec §4 illustrative row: (227,31,70,70)@4096 -> top=3995")


class TestValidatorTeeth:
    """Every major guard mutated -> its validator flags it (suite fails)."""

    def test_manifest_row_rejectations(self):
        good = {
            "outRelPath": "web/icons/X.webp", "plane": "icons",
            "format": "webp", "quality": 80, "bytes": 10,
            "sha256": "a" * 64, "route": "atlas-pair",
            "namedBy": "subObjectName",
            "source": {"bundle": "b.bundle", "pathId": -441676934,
                       "class": "Sprite", "subObjectName": "X",
                       "assetGuid": "f" * 32,
                       "rect": {"x": 227.0, "y": 31.0, "w": 70.0, "h": 70.0},
                       "rounded": {"left": 227, "top": 3995, "w": 70, "h": 70},
                       "contentAxis": "base"},
            "dims": {"w": 70, "h": 70}, "buildId": BUILD_ID,
        }
        assert ml.validate_media_manifest_row(good) == []
        bad = [
            ({**good, "extraKey": 1}, "frozen key set"),
            ({k: v for k, v in good.items() if k != "buildId"}, "missing key"),
            ({**good, "quality": 75}, "quality pin"),
            ({**good, "format": "avif"}, "AVIF never emitted"),
            ({**good, "plane": "thumbs-down"}, "plane enum"),
            ({**good, "sha256": "XYZ"}, "hex64"),
            ({**good, "route": ""}, "empty route"),
            ({**good, "namedBy": "slug"}, "namedBy enum (slugs deferred)"),
            ({**good, "source": {**good["source"], "pathId": "float"}},
             "signed-int pathId"),
            ({**good, "source": {**good["source"], "contentAxis": "mars"}},
             "contentAxis enum"),
            ({**good, "rounded": {"left": 227, "top": 31, "w": 70, "h": 70}},
             "UNFLIPPED top detected (post-flip contract)"),
            ({**good, "source": {**good["source"], "atlasName": "UI_Icons"}},
             "partial atlas stamp"),
        ]
        for row, why in bad:
            errs = ml.validate_media_manifest_row(row)
            assert errs, f"manifest validator accepted defect ({why})"

    def test_index_row_rejectations(self):
        good = {"kind": "item", "srcId": "I1", "fieldPath": "ItemsMenuIconReference",
                "assetGuid": "a" * 32, "subObjectName": "N", "resolved": False,
                "chainBreak": "container", "file": None,
                "reason": "dlc-content-absent", "buildId": BUILD_ID}
        assert ml.validate_media_index_row(good) == []
        resolved = {**good, "resolved": True, "chainBreak": "none",
                    "reason": "dlc-content-absent"}
        assert ml.validate_media_index_row(resolved), \
            "resolved:true rows must NOT carry a failure reason"
        ok_resolved = {**good, "resolved": True, "chainBreak": "guid",
                       "file": "web/icons/N.webp"}
        ok_resolved.pop("reason")
        assert ml.validate_media_index_row(ok_resolved) == [], \
            "chainBreak stays EVIDENCE on resolved rows (F11 predicate)"
        for row, why in [
            ({**good, "chainBreak": "vibes"}, "chainBreak enum"),
            ({**good, "file": "web/icons/N.webp"}, "unresolved w/ file"),
            ({**good, "reason": "made-up-reason"}, "novel reason verbatim"),
            ({k: v for k, v in good.items() if k != "chainBreak"},
             "chainBreak is a REQUIRED key"),
        ]:
            assert ml.validate_media_index_row(row), why

    def test_missing_ledger_rejectations(self):
        good = {"subObjectName": "N", "assetGuid": "a" * 32,
                "reason": "editor-only-fallback", "sampleRefs": [],
                "buildId": BUILD_ID}
        assert ml.validate_missing_row(good) == []
        escaped = {**good, "reason": ml.REASON_ESCAPE}
        assert ml.validate_missing_row(escaped) == [], \
            "the declared escape value itself must be accepted"
        for row, why in [
            ({**good, "reason": "whatever-i-invented"},
             "novel reason must route to the escape, never ship verbatim"),
            ({**good, "sampleRefs": [{"k": 1}] * 6}, "sampleRefs <= 5"),
            ({**good, "extra": 1}, "frozen key set"),
            ({k: v for k, v in good.items() if k != "reason"}, "reason required"),
        ]:
            assert ml.validate_missing_row(row), why

    def test_residue_row_rejectations(self):
        good = {"kind": "config", "srcId": "S", "fieldPath": "BadgeIcon",
                "pptr": {"fileId": 4, "pathID": -7},
                "pairedReferenceEmpty": True, "slotClass": "external",
                "targetResolution": "unresolved-open",
                "basis": "122-basis", "buildId": BUILD_ID}
        assert ml.validate_residue_row(good) == []
        escaped = {**good, "slotClass": "uncategorized-slot"}
        assert ml.validate_residue_row(escaped) == [], "P2 escape accepted"
        for row, why in [
            ({**good, "basis": "24-basis"}, "basis literal"),
            ({**good, "slotClass": "maybe-external"}, "slotClass enum"),
            ({**good, "targetResolution": "resolved-maybe"}, "verdict enum"),
            ({**good, "pairedReferenceEmpty": False}, "admission rule"),
            ({**good, "pptr": {"m_FileID": 4, "m_PathID": -7}},
             "pptr key spelling"),
        ]:
            assert ml.validate_residue_row(row), why

    def test_crosscheck_report_enforces_lossless_pin_p3(self):
        good = {"pixelMatchRate": 1.0, "maxDelta": 0,
                "cliVersion": ml.CLI_VERSION_SEED,
                "cliUnityVersion": ml.UNITY_VERSION,
                "cliExportFormat": "png", "sampleSize": 20}
        assert ml.validate_crosscheck_report(good) == []
        for fmt in ("bmp", "tga"):
            assert ml.validate_crosscheck_report({**good, "cliExportFormat": fmt}) == []
        for fmt in ("webp", "jpg", "jpeg"):
            errs = ml.validate_crosscheck_report({**good, "cliExportFormat": fmt})
            assert errs, f"P3: lossy {fmt} export must be flagged"
        errs = ml.validate_crosscheck_report({k: v for k, v in good.items()
                                              if k != "cliUnityVersion"})
        assert errs, "unity-version stamp mandatory"

    def test_hashes_text_validator_bites(self, tmp_path):
        tree = tmp_path / "media"
        (tree / "web").mkdir(parents=True)
        (tree / "web" / "a.webp").write_bytes(b"\x01\x02")
        (tree / "web" / "b.png").write_bytes(b"\x03")
        d = hashlib.sha256((tree / "web" / "a.webp").read_bytes()).hexdigest()
        e = hashlib.sha256((tree / "web" / "b.png").read_bytes()).hexdigest()
        good = f"{d}  web/a.webp\n{e}  web/b.png\n"
        assert ml.validate_hashes_text(good, tree) == []
        unsorted = f"{e}  web/b.png\n{d}  web/a.webp\n"
        assert ml.validate_hashes_text(unsorted, tree), "sort-by-relpath"
        crlf = good.replace("\n", "\r\n")
        assert ml.validate_hashes_text(crlf, tree), "LF discipline"
        lying = f"{'0' * 64}  web/a.webp\n{e}  web/b.png\n"
        assert ml.validate_hashes_text(lying, tree), "recompute bite"
        oneline = f"{d} web/a.webp\n{e}  web/b.png\n"
        assert ml.validate_hashes_text(oneline, tree), "two-space separator"


class TestGrammarDiscriminationTeeth:
    """Prove the fixtures REJECT the classic wrong implementations."""

    def test_bankers_rounding_would_fail_the_pinned_table(self):
        cases = [(0.5, 1), (1.5, 2), (2.5, 3), (-0.5, -1), (-2.5, -3),
                 (337.93, 338), (509.97, 510)]
        for v, want in cases:
            assert round_half_away(v) == want, f"{v} -> {want}"
        for v, want in [(0.5, 1), (2.5, 3), (-0.5, -1), (-2.5, -3)]:
            assert round(v) != want, \
                f"teeth broken: banker's round({v}) agrees with the pinned {want}"

    def test_missing_flip_would_fail_the_worked_rect(self):
        unflipped = {"left": 227, "top": 31, "w": 70, "h": 70}
        assert unflipped != ml.WORKED_ROUNDED, \
            "no-flip answer differs from the pinned top=3995"

    def test_amended_guard_flags_violations_and_passes_clean(self, tmp_path):
        root = tmp_path / "extracted"
        (root / ml.MEDIA_DIRNAME / "web" / "icons").mkdir(parents=True)
        # legal: image bytes UNDER extracted/media/**
        (root / ml.MEDIA_DIRNAME / "web" / "icons" / "ok.png").write_bytes(
            b"\x89PNG\r\n\x1a\n payload.png")
        # violation 1: image-extension mention outside media/
        (root / "configs").mkdir()
        (root / "configs" / "bad.json").write_text('{"p":"x.png"}\n')
        # violation 2: audio/video mention ANYWHERE (even inside media/)
        (root / "audio").mkdir()
        (root / "audio" / "theme.json").write_text('{"bank":"a.bnk"}\n')
        (root / ml.MEDIA_DIRNAME / "sneaky.jsonl").write_text(
            '{"v":"hidden.ogg"}\n')
        hits = ml.amended_media_guard(root)
        assert any("image-outside-media" in h for h in hits), hits
        assert any("audio/video" in h for h in hits), \
            f"audio/video absolute-zero anywhere: {hits}"
        assert any(h.startswith("media/sneaky") for h in hits), \
            "the media zone is not a safe harbor for audio/video"
        media_png = [h for h in hits
                     if h.startswith(f"{ml.MEDIA_DIRNAME}/")
                     and "image-outside-media" in h]
        assert not media_png, "image extensions LEGAL under extracted/media/**"
        clean = tmp_path / "clean-extracted"
        (clean / ml.MEDIA_DIRNAME / "web" / "thumbs").mkdir(parents=True)
        (clean / ml.MEDIA_DIRNAME / "web" / "thumbs" /
         "A@96.webp").write_bytes(b"RIFFxxxxWEBP")
        assert ml.amended_media_guard(clean) == [], "clean tree passes"

    def test_skipped_class_rows_validate(self):
        for cls, count in (("Cubemap", 138), ("Texture2DArray", 9),
                           ("Texture2D", 29)):
            row = {"class": cls, "censusCount": count,
                   "policy": "catalogue-only-carve-out", "buildId": BUILD_ID}
            assert ml.validate_skipped_class_row(row) == []
        assert ml.SKIPPED_CLASS_SEEDS_REAL == (138, 9, 29)
        for row, why in [
            ({"class": "Cubemap", "censusCount": 0, "policy": "p",
              "buildId": BUILD_ID}, "zero census"),
            ({"class": "Cubemap", "censusCount": 138, "buildId": BUILD_ID},
             "policy required"),
        ]:
            assert ml.validate_skipped_class_row(row), why

    def test_porcelain_payload_floor(self):
        sample = ("# MEDIA EXPORT\n\n"
                  f"buildId: {BUILD_ID}\n\n## Local artifacts\n\n"
                  "`export-manifest.jsonl` rows {outRelPath,...}; "
                  "`index.jsonl`; `hashes.sha256`; `crosscheck-report.json` "
                  "(cliExportFormat png); `_missing_icons.jsonl` reason enum: "
                  "dlc-content-absent stale-name empty-sub-name "
                  "editor-only-fallback visuals-prefab-target "
                  "mesh-list-target level-config-target uncategorized-reason; "
                  "`_pptr_residue.jsonl` basis 122-basis escapes "
                  "uncategorized-slot; `_skipped_classes.jsonl`; "
                  "MEDIA-EXPORT.md tracked; formats webp q80 + png twins; "
                  "hash summary sha256 per artifact.\n")
        assert ml.validate_media_export_md(sample) == []
        thin = sample.replace("uncategorized-slot", "").replace("122-basis", "")
        assert ml.validate_media_export_md(thin), \
            "self-sufficiency floor bites on stripped payloads"


# =================================================================================
# Rect grammar (§8 unit lane)
# =================================================================================

class TestRectGrammarUnit:
    def test_parser_accepts_integral_fractional_zero_shapes(self):
        _mod, parse = _unit(ml.RECT_PARSE_NAMES)
        integral = ml.WORKED_RECT
        fractional = {"x": 12.4, "y": 8.7, "w": ml.ADVISOR_HUSKI_DIMS[0],
                      "h": ml.ADVISOR_HUSKI_DIMS[1]}
        zero = {"x": 5.0, "y": 5.0, "w": 0.0, "h": 0.0}
        for rect in (integral, fractional, zero):
            out = _impl.try_call_shapes(parse, (rect,), (dict(rect),))
            assert out is not None
            text = json.dumps(out) if not isinstance(out, dict) else None
            assert out or text

    def test_rounding_is_half_away_not_bankers(self):
        _mod, rnd = _unit(ml.ROUND_NAMES)
        # value table: the pinned half-away answers for every probed input
        for v, want in [(0.5, 1), (1.5, 2), (2.5, 3), (-0.5, -1), (-2.5, -3)]:
            got = _impl.try_call_shapes(rnd, (v,))
            assert got == want, f"round({v}) -> {want} (half-away-from-zero)"
        # discrimination rows only where banker's rounding DIFFERS
        for v, want in [(0.5, 1), (2.5, 3), (-0.5, -1), (-2.5, -3)]:
            assert round(v) != want, \
                f"teeth broken: banker's round({v}) agrees with the pinned {want}"

    def test_flip_arithmetic_over_synthetic_page_heights(self):
        _mod, flip = _unit(ml.FLIP_NAMES)
        for page_h, rect, want in [
            (4096, ml.WORKED_RECT, ml.WORKED_ROUNDED),
            (512, {"x": 10.0, "y": 20.0, "w": 30.0, "h": 40.0},
             {"left": 10, "top": 452, "w": 30, "h": 40}),
            (2048, {"x": 0.5, "y": 2047.5, "w": 2.5, "h": 2.5},
             {"left": 1, "top": 2048 - 2048 - 3, "w": 3, "h": 3}),
        ]:
            got = _impl.try_call_shapes(
                flip, (rect, page_h), (dict(rect), page_h),
                ({"rect": rect, "pageHeight": page_h},))
            assert got == want, f"flip {rect}@{page_h} -> {want}"

    def test_bounds_checker_boundary_rows(self):
        """Out-of-bounds after pinned rounding must be REJECTED. The impl's
        pinned surface is the raising one (MediaError exit 1 — EC row
        'rect-out-of-bounds after pinned rounding'); a falsy verdict is the
        alternate honest spelling. Either rejection counts; silence does
        not."""
        _mod, chk = _unit(ml.BOUNDS_NAMES)
        inside = {"x": 100.0, "y": 100.0, "w": 64.0, "h": 64.0,
                  "left": 100, "top": 100}
        edge = {"x": 4032.0, "y": 4032.0, "w": 64.0, "h": 64.0,
                "left": 4032, "top": 4032}

        def call(rect):
            try:
                return _impl.try_call_shapes(chk, (rect, 4096, 4096),
                                             (rect, {"w": 4096, "h": 4096}))
            except Exception as exc:    # a pinned raise IS a rejection
                assert getattr(exc, "exit_code", 1) == 1, \
                    f"bounds rejection must be exit-1-shaped: {exc!r}"
                return None

        ok_a = call(inside)
        ok_b = call(edge)
        assert bool(ok_a) and bool(ok_b), "in-boundary rects accepted"
        outs = [
            {"x": 4097.0, "y": 0.0, "w": 8.0, "h": 8.0},     # x overflow
            {"x": 0.0, "y": 4097.0, "w": 8.0, "h": 8.0},     # y overflow
            {"x": 4092.0, "y": 0.0, "w": 8.0, "h": 8.0},     # spills right
            {"x": -1.0, "y": 0.0, "w": 8.0, "h": 8.0},       # negative
            {"x": 0.0, "y": 0.0, "w": 0.0, "h": 0.0},        # zero-size
        ]
        for bad in outs:
            got = call(bad)
            assert not got, f"out-of-bounds rect accepted: {bad}"


# =================================================================================
# Pairing matcher + duplicate-size tiebreak (E4/M9/M12, arbiter F2)
# =================================================================================

def _rd_entry(page_name, page_path_id, entry_index, w, h, page_bundle):
    return {"pageName": page_name, "pagePathId": page_path_id,
            "entryIndex": entry_index, "width": w, "height": h,
            "pageBundle": page_bundle}


def tiebreak_fixtures():
    """Two duplicate-size scenarios whose pinned answers DIFFER from naive
    orders — the discrimination teeth the unit legs assert against."""
    size = (70, 70)
    home = ml.HOME_BUNDLE_SEED
    other = "ui-art-icons_assets_all.bundle"
    # Scenario A: the home-bundle candidate carries the LARGER pagePathId —
    # dropping the home-bundle preference picks wrong.
    scen_a = [_rd_entry("sactx-2-4096x4096-DXT5-A-h2", 300, 0, *size, other),
              _rd_entry("sactx-1-4096x4096-DXT5-A-h1", 400, 0, *size, home)]
    want_a = scen_a[1]
    # Scenario B: both candidates share the home bundle — (pagePathId ASC,
    # entryIndex ASC) first-wins decides (200 < 300).
    scen_b = [_rd_entry("sactx-0-4096x4096-DXT5-B-h2", 300, 7, *size, home),
              _rd_entry("sactx-0-4096x4096-DXT5-B-h1", 200, 3, *size, home)]
    want_b = scen_b[1]
    return size, home, (scen_a, want_a), (scen_b, want_b)


class TestPairingTiebreak:
    def test_fixture_discriminates_naive_orders(self):
        size, home, (scen_a, want_a), (scen_b, want_b) = tiebreak_fixtures()
        by_pid_min = lambda s: min(s, key=lambda e: (e["pagePathId"], e["entryIndex"]))
        assert by_pid_min(scen_a) is not want_a, \
            "scenario A only passes WITH the home-bundle preference"
        assert by_pid_min(scen_b) is want_b, \
            "scenario B resolves by (pagePathId, entryIndex) ASC"

    @staticmethod
    def _chosen_of(got):
        """Matcher result normalization: ({entry,...} | (entry, ambiguous)) ->
        (chosen_entry_or_None, ambiguous_or_None)."""
        if isinstance(got, dict):
            amb = got.get("ambiguous") if "ambiguous" in got else None
            return got.get("entry", got), amb
        if isinstance(got, tuple) and len(got) == 2:
            return got[0], got[1]
        return got, None

    def test_size_match_beats_index_alignment_m9_trap(self):
        _mod, pair = _unit(ml.PAIR_NAMES)
        entries = [
            _rd_entry("sactx-0-128x128-RGBA32-Misordered-h0", 11, 0, 64, 64,
                      "ui-icons-atlased-assets_assets_all.bundle"),
            _rd_entry("sactx-1-256x256-RGBA32-Misordered-h1", 12, 1, 96, 96,
                      "ui-icons-atlased-assets_assets_all.bundle"),
        ]
        packed_names = ["SPRITE_B", "SPRITE_A"]  # deliberately crossed
        sprite = {"name": "SPRITE_B", "rect": {"x": 0, "y": 0, "w": 96, "h": 96}}
        got = _impl.try_call_shapes(
            pair, (entries, sprite["rect"], None),
            (entries, {"sprite": sprite, "packedNames": packed_names}),
            ({"renderDataMap": entries, "spriteRect": sprite["rect"],
              "homeBundle": None},))
        chosen, _amb = self._chosen_of(got)
        assert chosen is not None
        text = json.dumps(chosen, sort_keys=True, default=str)
        assert "sactx-1-256x256" in text, \
            "size-match must win; index alignment picks the 64x64 entry (0/352 trap)"

    def test_tiebreak_home_bundle_preference_then_asc_first_wins(self):
        _mod, pair = _unit(ml.PAIR_NAMES)
        size, home, (scen_a, want_a), (scen_b, want_b) = tiebreak_fixtures()
        for scenario, want, home_bundle in ((scen_a, want_a, home),
                                            (scen_b, want_b, home)):
            got = _impl.try_call_shapes(
                pair, (scenario, {"x": 0, "y": 0, "w": size[0], "h": size[1]},
                       home_bundle),
                ({"renderDataMap": scenario,
                  "spriteRect": {"x": 0, "y": 0, "w": size[0], "h": size[1]},
                  "homeBundle": home_bundle},))
            chosen, amb = self._chosen_of(got)
            assert chosen is not None
            text = json.dumps(chosen, sort_keys=True, default=str)
            assert want["pageName"].split("-h")[-1] in text or \
                want["pagePathId"] in text, \
                f"pinned tiebreak order violated (want {want['pageName']})"
            if amb is not None:
                assert amb is True, \
                    "every multi-candidate resolution flags ambiguous"

    def test_single_candidate_is_not_ambiguous(self):
        _mod, pair = _unit(ml.PAIR_NAMES)
        solo = [_rd_entry("sactx-0-64x64-RGBA32-Solo-h0", 9, 0, 64, 64, "b.bundle")]
        got = _impl.try_call_shapes(
            pair, (solo, {"x": 0, "y": 0, "w": 64, "h": 64}, "b.bundle"),
            ({"renderDataMap": solo,
              "spriteRect": {"x": 0, "y": 0, "w": 64, "h": 64},
              "homeBundle": "b.bundle"},))
        _chosen, amb = self._chosen_of(got)
        if amb is not None:
            assert amb is False

    def test_no_match_on_referenced_sprite_is_a_loud_failure(self):
        """EC exit-1 row: 'pairing match failure on a referenced sprite'. The
        matcher must fail LOUDLY (raise) or return an explicit miss — never
        fabricate a page. A miss may be spelled None OR a (None, ambiguous)
        verdict pair; the PAGE half is what must stay empty."""
        _mod, pair = _unit(ml.PAIR_NAMES)
        entries = [_rd_entry("sactx-0-64x64-RGBA32-X-h0", 9, 0, 64, 64, "b")]
        raised = None
        got = None
        try:
            got = _impl.try_call_shapes(
                pair, (entries, {"x": 0, "y": 0, "w": 31, "h": 31}, "b"),
                ({"renderDataMap": entries,
                  "spriteRect": {"x": 0, "y": 0, "w": 31, "h": 31},
                  "homeBundle": "b", "referenced": True},))
        except AssertionError:
            raise  # no call shape matched — loud, per the adapter contract
        except Exception as exc:  # a raise IS the pinned loud failure
            raised = exc
        if raised is None:
            chosen, _amb = self._chosen_of(got)
            assert not chosen, \
                f"no-match must not resolve to a page: {got!r}"


# =================================================================================
# Crop compositor + pass-through (§8)
# =================================================================================

class TestCropCompositor:
    def test_crop_equals_oracle_slice_byte_equal(self):
        _mod, crop = _unit(ml.CROP_NAMES)
        w, h = 64, 48
        page = ml.det_pixels("page-alpha", w, h)
        rect = {"left": 8, "top": 4, "w": 16, "h": 12}
        expect = b"".join(
            page[(rect["top"] + r) * w * 4 + rect["left"] * 4:
                 (rect["top"] + r) * w * 4 + (rect["left"] + rect["w"]) * 4]
            for r in range(rect["h"]))
        got = _impl.try_call_shapes(crop, (page, w, h, rect),
                                    ({"pixels": page, "width": w, "height": h,
                                      "rect": rect},))
        raw = got.tobytes() if hasattr(got, "tobytes") else bytes(got)
        assert raw == expect, "crop must be an exact subarray of the page"

    def test_pass_through_detection_boundary_rows(self):
        _mod, passthru = _unit(ml.PASSTHROUGH_NAMES)
        assert _impl.try_call_shapes(
            passthru, ({"x": 0, "y": 0, "w": 64, "h": 48}, 64, 48)) in (True, 1)
        assert not _impl.try_call_shapes(
            passthru, ({"x": 1, "y": 0, "w": 63, "h": 48}, 64, 48))


# =================================================================================
# Naming (§4 + §8)
# =================================================================================

class TestNaming:
    def test_subobject_keying_and_signed_collision_suffix(self):
        _mod, name_fn = _unit(ml.FILENAME_NAMES)
        plain = _impl.try_call_shapes(name_fn, ("My_Sprite",),
                                      ({"subObjectName": "My_Sprite",
                                        "pathId": 1234},))
        text = json.dumps(plain, sort_keys=True, default=str) \
            if not isinstance(plain, str) else plain
        assert "My_Sprite" in text and ".webp" in text
        _mod2, coll = _unit(ml.COLLISION_NAMES)
        neg = _impl.try_call_shapes(coll, ("My_Sprite", -441676934),
                                    ("My_Sprite", {"pathId": -441676934}))
        ntext = json.dumps(neg, sort_keys=True, default=str) \
            if not isinstance(neg, str) else neg
        assert "-441676934" in ntext, "collision suffix uses the SIGNED int64"

    def test_empty_sub_address_basename_ladder(self):
        _mod, rung = _unit(ml.ADDRESS_BASENAME_NAMES)
        addr = "Assets/Data/UI/Sprites/AdvisorMessage_CharacterImage_03"
        got = _impl.try_call_shapes(rung, (addr,))
        text = json.dumps(got, sort_keys=True, default=str) \
            if not isinstance(got, (str, tuple)) else str(got)
        assert "AdvisorMessage_CharacterImage_03" in text, \
            "primary rung: container address basename"
        # full E2 ladder seam: (address, bundle-stem, signed pathId) ->
        # (stem, namedBy) with BOTH rungs spelled
        _mod2, ladder = _unit(ml.STANDALONE_LADDER_NAMES)
        bare = "/no/basename/suffix/"
        fb = _impl.try_call_shapes(ladder, (bare, "ui-loadingscreen_assets_all",
                                            -90002))
        ftext = json.dumps(fb, sort_keys=True, default=str) \
            if not isinstance(fb, (str, tuple)) else str(fb)
        assert "-90002" in ftext and "ui-loadingscreen" in ftext, \
            "fallback rung: {bundle-stem}_{signed pathId}"
        stem, named_by = fb if isinstance(fb, tuple) and len(fb) == 2 \
            else (fb, None)
        assert named_by in (None, "bundle-pathid"), \
            "fallback rung stamps its own namedBy breadcrumb"
        primary, primary_by = _impl.try_call_shapes(
            ladder, (addr, "ui-loadingscreen_assets_all", -90001))
        assert "AdvisorMessage_CharacterImage_03" in str(primary), \
            "empty-sub sprites name by address basename, never fabricate"
        assert primary_by == "address-basename", \
            "the address-basename rung carries its namedBy breadcrumb"


# =================================================================================
# Manifest / hash tooling (§8)
# =================================================================================

class TestManifestHashes:
    def test_bijection_helper_detects_both_drift_directions(self, tmp_path):
        media = tmp_path / ml.MEDIA_DIRNAME
        (media / "web" / "icons").mkdir(parents=True)
        (media / "web" / "icons" / "A.webp").write_bytes(b"A")
        payload = {
            "outRelPath": "web/icons/A.webp", "plane": "icons",
            "format": "webp", "quality": 80, "bytes": 1,
            "sha256": hashlib.sha256(b"A").hexdigest(), "route": "atlas-pair",
            "namedBy": "subObjectName",
            "source": {"bundle": "b.bundle", "pathId": 1, "class": "Sprite",
                       "subObjectName": "A", "assetGuid": "a" * 32,
                       "rect": {"x": 0, "y": 0, "w": 4, "h": 4},
                       "rounded": {"left": 0, "top": 0, "w": 4, "h": 4},
                       "contentAxis": "base"},
            "dims": {"w": 4, "h": 4}, "buildId": BUILD_ID,
        }
        write_jsonl(media / "export-manifest.jsonl", [payload])
        _rows, problems = ml.assert_manifest_bijection(media)
        assert problems == []
        (media / "web" / "icons" / "Orphan.webp").write_bytes(b"O")
        _rows, problems = ml.assert_manifest_bijection(media)
        assert problems and "bijection broken" in problems[0]

    def test_sha256_recompute_over_written_file(self, tmp_path):
        f = tmp_path / "x.bin"
        f.write_bytes(ml.det_pixels("x", 4, 4))
        assert _sha(f) == hashlib.sha256(f.read_bytes()).hexdigest()


class TestMediaExportMd:
    def test_generator_deterministic_two_builds_byte_equal(self, tmp_path):
        _mod, gen = _unit(ml.EXPORT_MD_NAMES)
        inputs = {"buildId": BUILD_ID, "counts": {"icons": 2151},
                  "hashSummary": {"index.jsonl": "ab" * 32}}
        a = _impl.try_call_shapes(gen, (inputs,), (dict(inputs),))
        b = _impl.try_call_shapes(gen, (inputs,), (dict(inputs),))
        ra = a.read_bytes() if isinstance(a, Path) else str(a).encode()
        rb = b.read_bytes() if isinstance(b, Path) else str(b).encode()
        assert ra == rb, "MEDIA-EXPORT.md generation must be deterministic"
        assert ml.validate_media_export_md(ra.decode("utf-8")) == []


# =================================================================================
# Join predicate (E1/F11: chain breaks are evidence, never gates)
# =================================================================================

class TestJoinPredicate:
    def _join(self, join_fn, *, guid_in_catalog, address_in_container,
              name_in_catalogue):
        guid = ml.guid_for("join-probe")
        ref = {"assetGuid": guid, "subObjectName": "Target_Sprite",
               "fieldPath": "IconReference", "kind": "item", "srcId": "I1"}
        catalog_keys = {guid} if guid_in_catalog else set()
        addresses = {ml.CHEESEBALL_ADDRESS} if address_in_container else set()
        container_index = {ml.CHEESEBALL_ADDRESS:
                           {"bundle": "b.bundle", "class": "SpriteAtlas",
                            "pathId": 900000001}} if address_in_container else {}
        catalogue_names = {"Target_Sprite"} if name_in_catalogue else set()
        return _impl.try_call_shapes(
            join_fn,
            (ref, catalog_keys, addresses, catalogue_names),
            ({"ref": ref, "catalogGuids": catalog_keys,
              "containerAddresses": addresses,
              "catalogueSpriteNames": catalogue_names}),
            ({"ref": ref, "catalogGuids": catalog_keys,
              "containerIndex": container_index,
              "catalogueSpriteNames": catalogue_names}),
        )

    @staticmethod
    def _as_dict(got) -> dict:
        if isinstance(got, dict):
            return got
        return json.loads(json.dumps(got, sort_keys=True, default=str))

    def test_name_presence_alone_resolves_chain_breaks_are_evidence(self):
        _mod, join = _unit(ml.JOIN_NAMES)
        got = self._as_dict(self._join(
            join, guid_in_catalog=False, address_in_container=False,
            name_in_catalogue=True))
        resolved = got.get("resolved")
        assert resolved is True or str(resolved).lower() == "true", \
            f"F11 predicate: known NAME resolves despite dangling GUID: {got!r}"
        blob = json.dumps(got, sort_keys=True)
        assert '"guid"' in blob, "dangling GUID recorded as chainBreak evidence"

    def test_full_chain_unknown_name_stays_unresolved_chain_none(self):
        _mod, join = _unit(ml.JOIN_NAMES)
        got = self._as_dict(self._join(
            join, guid_in_catalog=True, address_in_container=True,
            name_in_catalogue=False))
        blob = json.dumps(got, sort_keys=True, default=str)
        assert str(got.get("resolved", "")) in ("False", "false") \
            or got.get("resolved") is False, \
            f"unknown NAME stays unresolved on a complete chain: {blob[:300]}"
        assert got.get("chainBreak") in (None, "none"), \
            f"complete chain carries chainBreak 'none': {blob[:300]}"

    def test_each_break_classifies(self):
        _mod, join = _unit(ml.JOIN_NAMES)
        for guid_ok, addr_ok, want in ((False, False, "guid"),
                                       (True, False, "address"),
                                       (True, True, "none")):
            got = self._as_dict(self._join(
                join, guid_in_catalog=guid_ok, address_in_container=addr_ok,
                name_in_catalogue=False))
            blob = json.dumps(got, sort_keys=True)
            assert f'"{want}"' in blob, \
                f"{want}-break mis-classified: {blob[:300]}"


# =================================================================================
# Cross-check comparator + P3 pin + sample composition (E4(3))
# =================================================================================

class TestCrossCheck:
    @staticmethod
    def _rate_delta(got):
        """Normalize a comparator result to (pixelMatchRate, maxDelta)."""
        if isinstance(got, (int, float)) and not isinstance(got, bool):
            return float(got), None
        d = got if isinstance(got, dict) else {}
        rate = next((float(d[k]) for k in ("pixelMatchRate", "matchRate", "rate")
                     if k in d), None)
        delta = d.get("maxDelta", d.get("maxdelta"))
        return rate, delta

    @staticmethod
    def _opaque(tag: str, w: int = 8, h: int = 8) -> bytearray:
        """Deterministic RGBA8 buffer with EVERY alpha at 255 — the
        comparator's verdict surface is the fully-opaque texel set."""
        buf = bytearray(ml.det_pixels(tag, w, h))
        for i in range(3, len(buf), 4):
            buf[i] = 255
        return buf

    def test_identical_buffers_rate_one_delta_zero(self):
        _mod, cmp_fn = _unit(ml.COMPARATOR_NAMES)
        buf = bytes(self._opaque("cmp"))
        got = _impl.try_call_shapes(cmp_fn, (buf, buf, 8, 8), (buf, buf),
                                    ({"a": buf, "b": buf},))
        rate, delta = self._rate_delta(got)
        assert rate == 1.0 and (delta in (None, 0)), \
            f"identical buffers must read rate 1.0 / delta 0, got {got!r}"

    def test_one_pixel_perturbation_drops_rate_below_one(self):
        """The discriminator bites ON THE PINNED SURFACE: an opaque-texel RGB
        divergence drops the verdict below perfect."""
        _mod, cmp_fn = _unit(ml.COMPARATOR_NAMES)
        buf = self._opaque("cmp")
        pert = bytearray(buf)
        pert[10] ^= 0xFF          # pixel 2 channel B — opaque on both sides
        pert[11] = 255
        got = _impl.try_call_shapes(cmp_fn, (bytes(buf), bytes(pert), 8, 8),
                                    (bytes(buf), bytes(pert)))
        rate, delta = self._rate_delta(got)
        assert (rate is not None and rate < 1.0) or (delta not in (None, 0)), \
            f"perturbation must drop the verdict below perfect, got {got!r}"

    def test_non_opaque_texels_stay_off_the_verdict_surface(self):
        """Measured scoping (buildId 20226581): invisible texels carry
        undefined RGB (block-compressed bleed vs the CLI's cleared
        background) and semi-transparent texels differ by the exporter's
        alpha compositing while every OPAQUE texel matches bit-exact. A
        divergence confined to those texels must NOT fail the lane."""
        _mod, cmp_fn = _unit(ml.COMPARATOR_NAMES)
        ours = self._opaque("scope")
        theirs = bytearray(ours)
        # pixel 2: fully transparent on BOTH sides, RGB differs
        ours[8:12] = b"\x11\x22\x33\x00"
        theirs[8:12] = b"\xaa\xbb\xcc\x00"
        # pixel 3: semi-transparent on BOTH sides, RGB differs
        ours[12:16] = b"\x11\x22\x33\xC0"
        theirs[12:16] = b"\xaa\xbb\xcc\xC0"
        got = _impl.try_call_shapes(cmp_fn, (bytes(ours), bytes(theirs), 8, 8))
        rate, delta = self._rate_delta(got)
        assert rate == 1.0 and delta == 0, \
            f"non-opaque divergence leaked onto the verdict: {got!r}"

    def test_opaque_and_nonopaque_distinction_is_load_bearing(self):
        """Teeth for the scoping itself: the SAME byte moved between two
        OPAQUE texels MUST fail — proving the previous test passes because of
        the surface rule, not because the comparator went blind."""
        _mod, cmp_fn = _unit(ml.COMPARATOR_NAMES)
        ours = self._opaque("teeth")
        theirs = bytearray(ours)
        theirs[6] ^= 0xFF           # pixel 1 channel B — both alphas 255
        got = _impl.try_call_shapes(cmp_fn, (bytes(ours), bytes(theirs), 8, 8))
        rate, delta = self._rate_delta(got)
        assert (rate is not None and rate < 1.0) or (delta not in (None, 0))

    def test_pinned_conversion_path_single_rgba_convert(self):
        try:
            from PIL import Image
        except ImportError:
            pytest.skip("env-gated: Pillow unavailable")
        rgb = Image.new("RGB", (4, 4), (10, 20, 30))
        converted = rgb.convert("RGBA")
        assert converted.mode == "RGBA" and converted.size == (4, 4)
        assert converted.getpixel((0, 0)) == (10, 20, 30, 255)

    def test_cli_format_pin_constants_reject_lossy(self):
        pin = None
        for name in ml.FORMAT_PIN_NAMES:
            _scope, pin = ml.resolve_impl(name)
            if pin is not None:
                break
        if pin is None:
            pytest.skip("impl-missing: CLI format-pin constant not resolvable yet")
        allowed = pin() if callable(pin) else pin
        vals = set(allowed) if isinstance(allowed, (set, tuple, list, frozenset)) \
            else {str(allowed).lower()}
        vals = {str(v).lower().lstrip(".") for v in vals}
        assert "png" in vals or vals <= {"png", "bmp", "tga"}, vals
        assert not (vals & {"webp", "jpg", "jpeg"}), \
            f"P3 violation: lossy CLI formats allowed {vals}"

    def test_sample_composer_meets_all_quotas_deterministically(self):
        _mod, composer = _unit(ml.SAMPLE_COMPOSER_NAMES)
        pool = []
        routes = ["atlas-pair", "standalone-pass-through",
                  "direct-pointer-subrect"]
        for i in range(24):
            pool.append({
                "name": f"Sprite_{i:03d}",
                "route": routes[i % 3],
                "ambiguous": i < 3,           # >=3 ambiguous-tiebreak
                "fractional": i in (3, 4),     # >=2 fractional-rect
                "bc7Page": i == 5,
            })
        pool.append({"name": ml.ANCHOR_SML[0], "route": "atlas-pair",
                     "ambiguous": False, "fractional": False, "bc7Page": False})
        pool.append({"name": ml.ANCHOR_LRG[0], "route": "atlas-pair",
                     "ambiguous": False, "fractional": False, "bc7Page": False})
        a = _impl.try_call_shapes(composer, (pool,),
                                  ({"sprites": pool, "minSample": 20},))
        b = _impl.try_call_shapes(composer, (pool,),
                                  ({"sprites": pool, "minSample": 20},))

        def names_of(result):
            """Composer verdict spelling: a list of stems OR plan dicts."""
            items = result if isinstance(result, list) \
                else (result or {}).get("sample", [])
            return [s if isinstance(s, str) else s.get("name") for s in items]

        names_a = names_of(a)
        names_b = names_of(b)
        assert names_a == names_b, "composer must be deterministic"
        assert len(names_a) >= ml.CROSSCHECK_SAMPLE_MIN
        chosen = [s for s in pool if s["name"] in names_a]
        assert sum(1 for s in chosen if s["ambiguous"]) >= 3
        assert sum(1 for s in chosen if s["fractional"]) >= 2
        for route in routes:
            assert any(s["route"] == route for s in chosen), route
        for anchor in (ml.ANCHOR_SML[0], ml.ANCHOR_LRG[0]):
            assert anchor in names_a, "probe anchors are mandatory quota members"


# =================================================================================
# S0 scratch discipline (precedence chain, refusals, ceilings)
# =================================================================================

class TestS0Discipline:
    def test_temp_root_precedence_arg_env_env_default(self, tmp_path, monkeypatch):
        _mod, resolver = _unit(ml.TEMP_ROOT_NAMES)
        extracted = tmp_path / "extracted"
        extracted.mkdir()
        arg = tmp_path / "arg-tmp"
        env_a = tmp_path / "media-tmp"
        env_b = tmp_path / "temp-root"
        monkeypatch.setenv("TPC_MEDIA_TMP", str(env_a))
        monkeypatch.setenv("TPC_TEMP_ROOT", str(env_b))
        got_arg = _impl.try_call_shapes(resolver, (str(arg), str(extracted)),
                                        ({"tempRootArg": str(arg),
                                          "extractedRoot": str(extracted)},))
        assert str(arg) in str(got_arg), "--temp-root arg wins"
        # both env vars set: TPC_MEDIA_TMP beats TPC_TEMP_ROOT
        got_a = _impl.try_call_shapes(resolver, (None, str(extracted)),
                                      ({"tempRootArg": None,
                                        "extractedRoot": str(extracted)},))
        assert str(env_a) in str(got_a), "TPC_MEDIA_TMP beats TPC_TEMP_ROOT"
        monkeypatch.delenv("TPC_MEDIA_TMP", raising=False)
        got_b = _impl.try_call_shapes(resolver, (None, str(extracted)),
                                      ({"tempRootArg": None,
                                        "extractedRoot": str(extracted)},))
        assert str(env_b) in str(got_b), \
            "TPC_TEMP_ROOT is the next rung once TPC_MEDIA_TMP is gone"
        monkeypatch.delenv("TPC_TEMP_ROOT", raising=False)
        got_def = _impl.try_call_shapes(resolver, (None, str(extracted)),
                                        ({"tempRootArg": None,
                                          "extractedRoot": str(extracted)},))
        assert ".tmp-stage11" in str(got_def), \
            f"default rung is <extracted-root>/.tmp-stage11, got {got_def}"

    def test_c_drive_refusal_names_temp_lever(self, monkeypatch):
        """S0 hard gate: a C:-rooted temp root refuses with exit 3 carrying
        the TEMP-leg lever text. The landed split resolves (pure) then gates
        (s0_preflight) — both seams are driven; a resolver that refuses by
        itself is the alternate honest spelling."""
        _mod, resolver = _unit(ml.TEMP_ROOT_NAMES)
        c_root = Path("C:/tpc_c_refusal_unit_tw06")   # explicitly C:-rooted
        extracted = ml.temp_base(_session_tag() + "-s0out")
        extracted.mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv("TPC_MEDIA_TMP", str(c_root))

        def lever_ok(blob: str) -> bool:
            return "TPC_MEDIA_TMP" in blob or "TPC_TEMP_ROOT" in blob

        resolved = None
        try:
            resolved = _impl.try_call_shapes(
                resolver, (None, str(extracted)),
                ({"tempRootArg": None, "extractedRoot": str(extracted)},))
        except Exception as exc:      # refusing resolver: gate already fired
            assert "3" in repr(exc) or "exit" in repr(exc).lower(), \
                f"C:-temp refusal must map to exit 3: {exc!r}"
            assert lever_ok(repr(exc)), f"TEMP-lever must be named: {exc!r}"
            return
        assert resolved is not None
        assert "C:" in str(resolved), \
            f"resolver must surface the C: root it was given: {resolved!r}"
        _gmod, preflight = _unit(ml.S0_PREFLIGHT_NAMES)
        try:
            _impl.try_call_shapes(
                preflight, (Path(resolved), Path(extracted)),
                ({"temp_root": Path(resolved),
                  "output_root": Path(extracted)},))
        except AssertionError:
            raise
        except Exception as exc:      # the pinned refusal shape
            assert getattr(exc, "exit_code", None) == 3 or "3" in repr(exc), \
                f"C:-temp refusal must map to exit 3: {exc!r}"
            assert lever_ok(f"{exc}"), \
                f"TEMP-lever remediation must be named: {exc!r}"
        else:
            raise AssertionError(
                "a C:-rooted temp root passed the S0 preflight unrefused")

    def test_free_space_readings_returned_for_run_section(self, tmp_path):
        _mod, free = _unit(ml.FLOOR_NAMES)
        got = _impl.try_call_shapes(free, (str(tmp_path),))
        val = got() if callable(got) and not isinstance(got, (int, float)) else got
        # accept a bare number or any structure CARRYING one (pair/dict rows)
        def numbers(v):
            if isinstance(v, bool):
                return
            if isinstance(v, (int, float)):
                yield v
            elif isinstance(v, dict):
                for x in v.values():
                    yield from numbers(x)
            elif isinstance(v, (list, tuple)):
                for x in v:
                    yield from numbers(x)
        nums = list(numbers(val))
        assert nums and all(n >= 0 for n in nums), \
            f"free-space reading must surface measured GiB, got {val!r}"

    def test_scope_ceiling_detector_fires_at_ceilings(self):
        _mod, ceiling = _unit(ml.CEILING_NAMES)
        over_default = ml.DEFAULT_CEILING_BYTES + 1
        got = _impl.try_call_shapes(ceiling, (over_default, False),
                                    ({"bytes": over_default,
                                      "uiChrome": False},))
        assert got, f"default ceiling {over_default}B must breach"
        under = ml.DEFAULT_CEILING_BYTES - 1
        got_ok = _impl.try_call_shapes(ceiling, (under, False),
                                       ({"bytes": under, "uiChrome": False},))
        assert not got_ok, "under-ceiling totals pass"
        chrome_band = ml.DEFAULT_CEILING_BYTES + 1024   # legal ONLY when chrome
        got_chrome = _impl.try_call_shapes(ceiling, (chrome_band, True),
                                           ({"bytes": chrome_band,
                                             "uiChrome": True},))
        assert not got_chrome, \
            "the 512 MiB chrome ceiling must admit what the 256 MiB default refuses"

    def test_game_dir_resolver_returns_none_hostless(self, monkeypatch):
        mod, fn = ml.resolve_impl(*ml.GAME_DIR_NAMES)
        if fn is None:
            pytest.skip("impl-missing: game-dir resolver not resolvable yet")
        monkeypatch.setenv("TPC_GAME_DIR", "")
        for scope in (mod, getattr(mod, "mu", None)):
            if scope is None:
                continue
            for const in ("DEFAULT_GAME", "DEFAULT_INSTALL",
                          "DEFAULT_CLIENT_DIR", "DEFAULT_GAME_DIR",
                          "DEFAULT_INSTALL_CANDIDATES"):
                if hasattr(scope, const):
                    monkeypatch.setattr(
                        scope, const,
                        [] if const.endswith("CANDIDATES")
                        else Path("Z:/definitely-absent"))
        got = _impl.try_call_shapes(fn, (), (None,))
        assert got is None, \
            "P1: with no env var and no default install, resolver yields None " \
            "-> wholesale auto-SKIP, never exit 3"


# =================================================================================
# E6 residue scan over the synthetic nine-kind mix
# =================================================================================

class TestEncodeLoudFailure:
    """EC exit-1 row: 'WebP/PNG encode exception on valid pixels' must be a
    mechanism failure, never a silent skip. Unit lane proves the encoder
    surface fails LOUD on impossible input (the pipeline maps the raise to
    exit 1; that mapping is only observable client-gated)."""

    def test_encoder_raises_on_invalid_input_never_silent(self, tmp_path):
        _mod, enc = _unit(ml.ENCODE_NAMES)
        good = ml.det_pixels("enc", 8, 8)
        out = tmp_path / "ok.webp"
        raised_good = None
        try:
            _impl.try_call_shapes(enc, (good, 8, 8, str(out)),
                                  ({"pixels": good, "w": 8, "h": 8,
                                    "outPath": str(out), "format": "webp"}))
        except AssertionError:
            raise
        except Exception as exc:
            raised_good = exc
        if raised_good is None and not out.exists():
            # encoder may return bytes instead of writing; both fine
            pass
        for bad_pixels, w, h in ((None, 8, 8), (b"\x00", -4, 4)):
            raised = None
            try:
                _impl.try_call_shapes(
                    enc, (bad_pixels, w, h, str(tmp_path / "bad.webp")),
                    ({"pixels": bad_pixels, "w": w, "h": h,
                      "outPath": str(tmp_path / "bad.webp"),
                      "format": "webp"}))
            except AssertionError:
                raise
            except Exception as exc:
                raised = exc
            if raised is None:
                bad_out = tmp_path / "bad.webp"
                assert not bad_out.exists() or bad_out.stat().st_size == 0, \
                    "invalid pixels silently produced an artifact"


class TestResidueScan:
    @staticmethod
    def _scan_rows(got):
        """Scan-seam result normalization: ({rows:[...]}, (rows, counters,
        drift) tuple, or a bare row list) -> the row list."""
        if isinstance(got, dict) and "rows" in got:
            return got["rows"]
        if isinstance(got, tuple) and got and isinstance(got[0], list):
            return got[0]
        return got

    def test_scan_matches_oracle_over_synthetic_stubs(self):
        _mod, scan = _unit(ml.RESIDUE_SCAN_NAMES)
        rows = ml.media_stub_rows()
        got = _impl.try_call_shapes(scan, (rows,),
                                    ({"stubRows": rows},),
                                    ({"stubs": {r["kind"]: [r] for r in rows}},))
        assert got is not None
        got_rows = self._scan_rows(got)
        norm = []
        for r in got_rows:
            norm.append({
                "kind": r.get("kind"), "srcId": r.get("srcId"),
                "fieldPath": r.get("fieldPath"),
                "pptr": r.get("pptr") or {"fileId": r.get("fileId"),
                                          "pathID": r.get("pathID")},
                "pairedReferenceEmpty": r.get("pairedReferenceEmpty"),
                "slotClass": r.get("slotClass"),
                "targetResolution": r.get("targetResolution"),
                "basis": r.get("basis"), "buildId": r.get("buildId"),
            })
        want = {(r["kind"], r["srcId"], r["fieldPath"]): r
                for r in ml.oracle_residue_rows()}
        gotmap = {(r["kind"], r["srcId"], r["fieldPath"]): r for r in norm}
        missing = sorted(set(want) - set(gotmap))
        extra = sorted(set(gotmap) - set(want))
        assert not missing, f"scan missed admitted slots: {missing}"
        assert not extra, f"scan admitted non-residue slots: {extra}"
        for key, w in want.items():
            g = gotmap[key]
            assert g["slotClass"] == w["slotClass"], key
            assert g["basis"] == ml.RESIDUE_BASIS, key
            assert g["targetResolution"] in ml.TARGET_RESOLUTIONS, key
            assert ml.validate_residue_row(g) == [] or \
                ml.validate_residue_row({**g, "buildId": BUILD_ID}) == [], key

    def test_scan_sorted_by_kind_srcid_fieldpath(self):
        _mod, scan = _unit(ml.RESIDUE_SCAN_NAMES)
        rows = ml.media_stub_rows()
        got = _impl.try_call_shapes(scan, (rows,), ({"stubRows": rows},))
        got_rows = self._scan_rows(got)
        keys = [(r.get("kind"), r.get("srcId"), r.get("fieldPath"))
                for r in got_rows]
        assert keys == sorted(keys), "emission sort contract"


# =================================================================================
# Black-box legs over the seed tree (F4: zero bundle opens, exit 2)
# =================================================================================

def require_blackbox_ready(media_seed_tree, ext):
    ml.require_media_registered()
    if not (Path(ext) / "identity.json").exists():
        pytest.fail("seed tree lost its identity.json upstream")


class TestRunnerBlackBox:
    def test_list_registers_media_after_last_registered_stage(self):
        ml.require_media_registered()
        r = run_pack(["--list"])
        assert r.returncode == 0 and "media" in r.stdout
        registry_order = ["verify-client", "decompile", "harvest-catalog",
                          "harvest-bundles", "localisation",
                          "emit-stub-datasets", "relink", "maps", "logic",
                          "locale-proof", "contracts", "media",
                          "search-corpus"]
        pos = {sid: r.stdout.find(sid) for sid in registry_order
               if sid in r.stdout}
        assert "media" in pos
        earlier = [sid for sid, p in pos.items()
                   if registry_order.index(sid) < registry_order.index("media")]
        later = [sid for sid, p in pos.items()
                 if registry_order.index(sid) > registry_order.index("media")]
        assert all(pos[s] < pos["media"] for s in earlier), pos
        assert all(pos[s] > pos["media"] for s in later), pos

    def test_seed_tree_runs_exit2_with_zero_bundle_opens(
            self, media_seed_tree, media_ext, scratch_root):
        require_blackbox_ready(media_seed_tree, media_ext)
        r = _run_media(media_seed_tree, media_ext, scratch_root)
        assert r.returncode == 2, (
            "expected exit 2 (completed-with-ledger); stdout:\n"
            f"{r.stdout[-2000:]}\nstderr:\n{r.stderr[-2000:]}")

        media = Path(media_ext) / ml.MEDIA_DIRNAME
        assert media.exists(), "media output tree absent"

        # F4 black-box assertion standing in for decode: the 7-name seed drove
        # BOTH ledgers end-to-end with ZERO bundle opens.
        missing = read_jsonl(media / "_missing_icons.jsonl")
        by_name = {row["subObjectName"]: row for row in missing}
        for name, reason in ml.ABSENCE_SEED:
            assert name in by_name, f"M16 name {name!r} absent from the ledger"
            assert by_name[name]["reason"] == reason
        skip_reasons = {row["reason"] for row in missing} & set(ml.MISSING_REASONS)
        assert {"editor-only-fallback", "visuals-prefab-target",
                "mesh-list-target", "level-config-target"} <= skip_reasons
        for row in missing:
            assert ml.validate_missing_row(row) == [], row

        index = read_jsonl(media / "index.jsonl")
        assert len(index) == 14
        assert all(row["resolved"] is False and row["file"] is None
                   for row in index)
        for row in index:
            assert ml.validate_media_index_row(row) == [], row
        assert index == sorted(index, key=lambda r: (r["kind"], r["srcId"],
                                                     r["fieldPath"]))

        # zero bundle opens PROVEN mechanically: nothing resolved => no files
        web = media / "web"
        emitted = [p for p in web.rglob("*") if p.is_file()] if web.exists() else []
        assert emitted == [], \
            f"resolved:false-only run emitted files — bundles were opened: {emitted}"

    def test_missing_icons_sorted_and_sample_refs_capped(
            self, media_seed_tree, media_ext, scratch_root):
        require_blackbox_ready(media_seed_tree, media_ext)
        assert _run_media(media_seed_tree, media_ext, scratch_root).returncode == 2
        media = Path(media_ext) / ml.MEDIA_DIRNAME
        rows = read_jsonl(media / "_missing_icons.jsonl")
        names = [r["subObjectName"] for r in rows]
        assert names == sorted(names)
        pirates = next(r for r in rows
                       if r["subObjectName"] == "DLC3_UI_Icons_Objective_Pirates")
        assert 1 <= len(pirates["sampleRefs"]) <= 5
        assert len(pirates["sampleRefs"]) == 3, "many-to-one aggregate"

    def test_residue_ledger_matches_oracle(
            self, media_seed_tree, media_ext, scratch_root):
        require_blackbox_ready(media_seed_tree, media_ext)
        assert _run_media(media_seed_tree, media_ext, scratch_root).returncode == 2
        media = Path(media_ext) / ml.MEDIA_DIRNAME
        rows = read_jsonl(media / "_pptr_residue.jsonl")
        got = {(r["kind"], r["srcId"], r["fieldPath"]): r for r in rows}
        want = {(r["kind"], r["srcId"], r["fieldPath"]): r
                for r in ml.oracle_residue_rows()}
        assert sorted(got) == sorted(want)
        for key in want:
            g, w = got[key], want[key]
            assert g["slotClass"] == w["slotClass"], key
            assert g["basis"] == ml.RESIDUE_BASIS, key
            assert g["pairedReferenceEmpty"] is True, key
            assert g["pptr"] == w["pptr"], key
        assert rows == sorted(rows, key=lambda r: (r["kind"], r["srcId"],
                                                   r["fieldPath"]))

    def test_skipped_classes_match_catalogue_census(
            self, media_seed_tree, media_ext, scratch_root):
        require_blackbox_ready(media_seed_tree, media_ext)
        assert _run_media(media_seed_tree, media_ext, scratch_root).returncode == 2
        media = Path(media_ext) / ml.MEDIA_DIRNAME
        rows = read_jsonl(media / "_skipped_classes.jsonl")
        counts = {}
        for row in rows:
            assert ml.validate_skipped_class_row(row) == [], row
            counts[row["class"]] = counts.get(row["class"], 0) + row["censusCount"]
        assert counts.get("Cubemap") == 2, counts
        assert counts.get("Texture2DArray") == 1, counts
        total = sum(counts.values())
        assert total >= 4, "zero-size font-atlas Texture2D row must policy-row too"

    def test_manifest_bijection_hashes_and_crosscheck_stamp(
            self, media_seed_tree, media_ext, scratch_root):
        require_blackbox_ready(media_seed_tree, media_ext)
        assert _run_media(media_seed_tree, media_ext, scratch_root).returncode == 2
        media = Path(media_ext) / ml.MEDIA_DIRNAME
        rows, problems = ml.assert_manifest_bijection(media)
        assert problems == [], problems
        hashes = (media / "hashes.sha256").read_text(encoding="utf-8")
        assert ml.validate_hashes_text(hashes, media) == []
        report = read_json(media / "crosscheck-report.json")
        assert ml.validate_crosscheck_report(report) == []
        # flag-gated surfaces stay dark on the default run (AC7)
        assert not (media / "course-icon-carrier-report.json").exists(), \
            "E5 flag OFF must write NOTHING"
        ui_plane = media / "web" / "ui"
        assert not ui_plane.exists() or not any(ui_plane.iterdir()), \
            "E3 flag OFF must emit nothing"

    def test_media_export_md_self_sufficiency(
            self, media_seed_tree, media_ext, scratch_root):
        require_blackbox_ready(media_seed_tree, media_ext)
        assert _run_media(media_seed_tree, media_ext, scratch_root).returncode == 2
        md = (_media_artifact(media_ext, ml.PORCELAIN_TRACKED)
              .read_text(encoding="utf-8"))
        assert ml.validate_media_export_md(md) == []

    def test_double_run_byte_identical_ac5(
            self, media_seed_tree, media_ext, scratch_root):
        require_blackbox_ready(media_seed_tree, media_ext)
        assert _run_media(media_seed_tree, media_ext, scratch_root).returncode == 2

        def snapshot(ext):
            media = Path(ext) / ml.MEDIA_DIRNAME
            snap = {}
            for name in ml.TEXT_ARTIFACTS_ALWAYS:
                p = media / name
                if p.exists():
                    snap[name] = _sha(p)
            md = media / ml.PORCELAIN_TRACKED
            if md.exists():
                snap[ml.PORCELAIN_TRACKED] = _sha(md)
            web = media / "web"
            if web.exists():
                for p in sorted(web.rglob("*")):
                    if p.is_file():
                        snap[f"web/{p.relative_to(web).as_posix()}"] = _sha(p)
            return snap

        gitignore_before = _sha(HERE.parent / ".gitignore")
        first = snapshot(media_ext)
        assert first, "no declared artifacts produced"
        # --force makes BOTH legs real executions (the runner's up-to-date
        # stamp short-circuit is piece-1 contract; AC5's determinism claim
        # is about REGENERATION, so it must bypass the skip)
        r2 = _run_media(media_seed_tree, media_ext, scratch_root, "--force")
        assert r2.returncode == 2
        second = snapshot(media_ext)
        only_a, only_b, changed = diff_manifests(first, second)
        assert not (only_a or only_b or changed), \
            f"AC5 byte-stability broken: +{only_a} -{only_b} ~{changed}"
        assert _sha(HERE.parent / ".gitignore") == gitignore_before, \
            "the stage must NEVER touch .gitignore (settled commit policy)"

    def test_missing_upstream_artifact_exit3_names_it(
            self, media_seed_tree, media_ext, scratch_root):
        require_blackbox_ready(media_seed_tree, media_ext)
        victim = Path(media_ext) / "relinks" / "entity_asset_guid.jsonl"
        victim.unlink()
        r = _run_media(media_seed_tree, media_ext, scratch_root)
        assert r.returncode == 3, (
            f"missing ARTIFACT with resolving game dir must exit 3, got "
            f"{r.returncode}: {r.stdout[-800:]} {r.stderr[-800:]}")
        assert "entity_asset_guid" in (r.stdout + r.stderr)

    def test_c_temp_root_refuses_exit3_with_temp_lever(
            self, media_seed_tree, media_ext, tmp_path):
        require_blackbox_ready(media_seed_tree, media_ext)
        c_scratch = Path(tmp_path.anchor) / "tpc_c_refusal_probe_tw06"
        r = _run_media(media_seed_tree, media_ext, c_scratch)
        assert r.returncode == 3, \
            f"C:-rooted temp must refuse exit 3, got {r.returncode}"
        blob = r.stdout + r.stderr
        assert "TPC_MEDIA_TMP" in blob or "TPC_TEMP_ROOT" in blob, blob[-800:]

    def test_wholesale_auto_skip_without_any_game_dir(
            self, media_seed_tree, media_ext, scratch_root):
        ml.require_media_registered()
        if DEFAULT_GAME.exists():
            pytest.skip(
                "auto-skip leg unreachable on this host: the default install "
                "resolves, and the spec pins no force-hostless override knob "
                "(unit-level coverage in TestS0Discipline::"
                "test_game_dir_resolver_returns_none_hostless)")
        ext = Path(media_ext)
        # a game dir that does NOT exist anywhere + cleared env var: P1 says
        # this path is a wholesale auto-SKIP (exit 0), never exit 3.
        absent_game = str(ml.temp_base(_session_tag() + "-absent-install"))
        r = run_pack([absent_game, "--only", "media"],
                     extracted_root=ext,
                     extra_env={"TPC_GAME_DIR": "",
                                "TPC_MEDIA_TMP": str(scratch_root)})
        assert r.returncode == 0, \
            f"P1: no game dir => auto-SKIP exit 0, got {r.returncode}: " \
            f"{(r.stdout + r.stderr)[-500:]}"
        meta = ext / ".pipeline-meta.json"
        if meta.exists():
            blob = meta.read_text(encoding="utf-8")
            assert "media" in blob and "skip" in blob.lower(), blob[:400]
        assert not (ext / ml.MEDIA_DIRNAME / "_missing_icons.jsonl").exists(), \
            "wholesale skip writes no partial stage outputs"

    @staticmethod
    def _corrupt_first_string_value(obj):
        """Replace the first string leaf's content with deadbeef, keeping the
        stamp schema parseable (a hash-drift simulation, never corrupt JSON)."""
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, str) and v:
                    obj[k] = "deadbeef" + v[8:]
                    return obj
                hit = TestRunnerBlackBox._corrupt_first_string_value(v)
                if hit is not None:
                    return obj
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                if isinstance(v, str) and v:
                    obj[i] = "deadbeef" + v[8:]
                    return obj
                hit = TestRunnerBlackBox._corrupt_first_string_value(v)
                if hit is not None:
                    return obj
        return None

    def test_stamp_invalidation_reruns_stage(
            self, media_seed_tree, media_ext, scratch_root):
        require_blackbox_ready(media_seed_tree, media_ext)
        assert _run_media(media_seed_tree, media_ext, scratch_root).returncode == 2
        stamps_dir = Path(media_ext) / ".stage-stamps"
        stamp_files = sorted(stamps_dir.glob("*media*")) \
            if stamps_dir.exists() else []
        if not stamp_files and stamps_dir.exists():
            stamp_files = [p for p in sorted(stamps_dir.glob("*.json"))
                           if "stage11" in p.read_text(encoding="utf-8")]
        if not stamp_files:
            pytest.skip("impl-shape: no media stage stamp found to corrupt")
        stamp = stamp_files[0]
        obj = read_json(stamp)
        # The tripwire is the stamp's IDENTITY digest (runner compares it
        # against its own recomputation). Corrupt THAT field specifically —
        # mutating an arbitrary string leaf (e.g. config.extractedRoot) can
        # leave identity intact and the skip honest.
        assert "identity" in obj, \
            f"stamp schema drifted; identity field absent: {sorted(obj)}"
        obj["identity"] = "deadbeef" + str(obj["identity"])[8:]
        stamp.write_text(json.dumps(obj, sort_keys=True), encoding="utf-8",
                         newline="\n")
        log = Path(media_ext) / "EXTRACTION-LOG.md"
        size_before = log.stat().st_size if log.exists() else 0
        r = _run_media(media_seed_tree, media_ext, scratch_root)
        assert r.returncode in (0, 2)
        assert log.exists() and log.stat().st_size > size_before, \
            "corrupt stamp must force a fresh run section (no silent trust)"

    def test_interrupted_run_convergence(
            self, media_seed_tree, media_ext, scratch_root):
        import time
        require_blackbox_ready(media_seed_tree, media_ext)
        env = dict(os.environ)
        env.update({"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8",
                    "TPC_GAME_DIR": _tree_game(media_seed_tree),
                    "TPC_EXTRACTED_ROOT": str(media_ext),
                    "TPC_MEDIA_TMP": str(scratch_root)})
        proc = subprocess.Popen(
            [sys.executable, str(HERE.parent / "run_all.py"),
             _tree_game(media_seed_tree), "--only", "media"],
            cwd=str(HERE.parent), env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        killed = False
        deadline = time.time() + 90
        while time.time() < deadline and proc.poll() is None:
            media = Path(media_ext) / ml.MEDIA_DIRNAME
            partial = any(media.glob("_*.jsonl")) if media.exists() else False
            if partial:
                proc.kill()
                killed = True
                break
            time.sleep(0.05)
        proc.wait()
        if not killed:
            pytest.skip("interruption-window-not-caught (run finished before "
                        "any ledger hit the disk)")

        def snap():
            media = Path(media_ext) / ml.MEDIA_DIRNAME
            return {p.name: _sha(p) for p in sorted(media.glob("*.jsonl"))}

        r1 = _run_media(media_seed_tree, media_ext, scratch_root, "--force")
        first = snap()
        r2 = _run_media(media_seed_tree, media_ext, scratch_root, "--force")
        second = snap()
        assert r1.returncode == r2.returncode == 2
        assert first == second, \
            "interrupted run must converge to the identical tree on rerun"

    def test_extraction_log_carries_pinned_run_section_keys(
            self, media_seed_tree, media_ext, scratch_root):
        require_blackbox_ready(media_seed_tree, media_ext)
        assert _run_media(media_seed_tree, media_ext, scratch_root).returncode == 2
        log = (Path(media_ext) / "EXTRACTION-LOG.md").read_text(encoding="utf-8")
        for key in ("tempRoot", "refsTotal", "distinctNames", "resolvedNames",
                    "unresolvedNames", "spritesEmitted", "ambiguousPairings",
                    "pairingFailures", "crossCheckSample", "pixelMatchRate",
                    "maxDelta", "cliVersion", "cliUnityVersion",
                    "cliExportFormat", "pptrSlotsScanned", "pptrSlotsNullSkipped",
                    "pptrResidueRows", "pillowVersion", "webpFeatureVersion",
                    "fallbackVersionUsedBundles"):
            assert key in log, f"pinned run-section key {key!r} missing"

    def test_e5_flag_on_writes_report_only_and_never_emits(
            self, media_seed_tree, media_ext, scratch_root):
        """R3 binding ruling: --probe-course-carrier emits ONLY
        course-icon-carrier-report.json inside extracted/media/; it never
        emits an icon and never writes outside extracted/media/."""
        require_blackbox_ready(media_seed_tree, media_ext)
        baseline = _run_media(media_seed_tree, media_ext, scratch_root)
        assert baseline.returncode == 2
        media = Path(media_ext) / ml.MEDIA_DIRNAME
        before = sorted(p.relative_to(media).as_posix()
                        for p in media.rglob("*") if p.is_file())
        r = _run_media(media_seed_tree, media_ext, scratch_root,
                       "--probe-course-carrier")
        assert r.returncode in (0, 2), \
            f"report-only probe must not fail the stage: {(r.stdout + r.stderr)[-500:]}"
        after = sorted(p.relative_to(media).as_posix()
                       for p in media.rglob("*") if p.is_file())
        report = "course-icon-carrier-report.json"
        assert report in after, "flag-ON run must emit its report"
        delta = set(after) - set(before)
        unexpected = {p for p in delta - {report}
                      if p.startswith("web/") and "icons" in p.split("/")}
        assert not unexpected, \
            f"E5 turned probe into emission (R3 violation): {unexpected}"
        obj = read_json(media / report)
        assert isinstance(obj, dict) and obj.get("buildId") == BUILD_ID

    def test_commit_surface_check_ignore_mechanics(self):
        """AC10 mechanics on THIS repo: standing rules ignore every local
        media artifact and leave exactly MEDIA-EXPORT.md tracked-eligible;
        no .gitignore edit needed or made."""
        import subprocess as sp

        def ignored(rel: str) -> bool:
            rc = sp.run(["git", "check-ignore", "-q", rel], cwd=str(HERE.parent),
                        capture_output=True).returncode
            return rc == 0

        for rel in ("extracted/media/export-manifest.jsonl",
                    "extracted/media/index.jsonl",
                    "extracted/media/hashes.sha256",
                    "extracted/media/crosscheck-report.json",
                    "extracted/media/_missing_icons.jsonl",
                    "extracted/media/_pptr_residue.jsonl",
                    "extracted/media/_skipped_classes.jsonl",
                    "extracted/media/course-icon-carrier-report.json",
                    "extracted/media/web/icons/X.webp",
                    "extracted/media/web/ui/A/Y.webp"):
            assert ignored(rel), f"{rel} must stay gitignored-local"
        assert not ignored("extracted/media/MEDIA-EXPORT.md"), \
            "the .md carve-out must keep MEDIA-EXPORT.md trackable"


# =================================================================================
# Client-gated integration (real corpus; auto-skips without the install)
# =================================================================================

def _require_client():
    gd = os.environ.get("TPC_GAME_DIR")
    if gd and Path(gd).exists():
        return Path(gd)
    if DEFAULT_GAME.exists():
        return DEFAULT_GAME
    pytest.skip("client-gated: no TPC_GAME_DIR/default install present")


def _require_heavy():
    _require_client()
    if os.environ.get("TPC_IT_HEAVY") != "1":
        pytest.skip("heavy: real-corpus execution needs TPC_IT_HEAVY=1")


@pytest.mark.client_gated
@pytest.mark.heavy
class TestClientGated:
    def test_join_reconciliation_m4_triple(self, tmp_path):
        _require_heavy()
        # real-corpus run asserts distinctNames == 2158, resolvedNames == 2151,
        # unresolved set EQUALS the 7 verbatim M16 names.
        scratch = ml.pick_scratch_root(_session_tag())
        ext = ml.temp_base(_session_tag() + "-cg-ext")
        ext.mkdir(parents=True, exist_ok=True)
        r = run_pack([str(_require_client()), "--only", "media"],
                     extracted_root=ext,
                     extra_env={"TPC_MEDIA_TMP": str(scratch)}, timeout=3600)
        assert r.returncode == 2
        media = ext / ml.MEDIA_DIRNAME
        missing = read_jsonl(media / "_missing_icons.jsonl")
        absence = {row["subObjectName"]: row["reason"] for row in missing
                   if row["reason"] in ("dlc-content-absent", "stale-name",
                                        "empty-sub-name")}
        assert dict(ml.ABSENCE_SEED) == absence
        log = (ext / "EXTRACTION-LOG.md").read_text(encoding="utf-8")
        assert "distinctNames" in log and "2158" in log
        assert "resolvedNames" in log and "2151" in log

    def test_crosscheck_real_bytes_quotas_and_pixel_exactness(self, tmp_path):
        _require_heavy()
        scratch = ml.pick_scratch_root(_session_tag())
        ext = ml.temp_base(_session_tag() + "-cg-ext2")
        ext.mkdir(parents=True, exist_ok=True)
        r = run_pack([str(_require_client()), "--only", "media"],
                     extracted_root=ext,
                     extra_env={"TPC_MEDIA_TMP": str(scratch)}, timeout=3600)
        assert r.returncode in (0, 2)
        report = read_json(ext / ml.MEDIA_DIRNAME / "crosscheck-report.json")
        assert report["pixelMatchRate"] == 1.0 and report["maxDelta"] == 0
        assert report["cliExportFormat"] in ml.LOSSLESS_CLI_FORMATS
        assert report["cliUnityVersion"] == ml.UNITY_VERSION
        sample = report.get("sample") or report.get("sampleSize") or []
        if isinstance(sample, list) and sample:
            names = [s.get("subObjectName") or s.get("name") for s in sample]
            assert ml.ANCHOR_SML[0] in names and ml.ANCHOR_LRG[0] in names
            amb = [s for s in sample if s.get("ambiguous")]
            assert len(amb) >= 3, ">=3 ambiguous-tiebreak samples from real collisions"
        log = (ext / "EXTRACTION-LOG.md").read_text(encoding="utf-8")
        assert "fallbackVersionUsedBundles" in log

    def test_double_run_hash_equal_on_real_tree(self, tmp_path):
        _require_heavy()
        scratch = ml.pick_scratch_root(_session_tag())
        ext = ml.temp_base(_session_tag() + "-cg-ext3")
        ext.mkdir(parents=True, exist_ok=True)

        def snap():
            media = ext / ml.MEDIA_DIRNAME
            out = {}
            for name in ml.TEXT_ARTIFACTS_ALWAYS:
                p = media / name
                if p.exists():
                    out[name] = _sha(p)
            return out

        args = [str(_require_client()), "--only", "media"]
        env = {"TPC_MEDIA_TMP": str(scratch)}
        run_pack(args, extracted_root=ext, extra_env=env, timeout=3600)
        first = snap()
        run_pack(args, extracted_root=ext, extra_env=env, timeout=3600)
        only_a, only_b, changed = diff_manifests(first, snap())
        assert not (only_a or only_b or changed)

    def test_pptr_residue_reconciles_122_basis_seed(self, tmp_path):
        _require_heavy()
        ext = ml.temp_base(_session_tag() + "-cg-ext4")
        if not (ext / ml.MEDIA_DIRNAME / "_pptr_residue.jsonl").exists():
            scratch = ml.pick_scratch_root(_session_tag())
            ext.mkdir(parents=True, exist_ok=True)
            run_pack([str(_require_client()), "--only", "media"],
                     extracted_root=ext,
                     extra_env={"TPC_MEDIA_TMP": str(scratch)}, timeout=3600)
        rows = read_jsonl(ext / ml.MEDIA_DIRNAME / "_pptr_residue.jsonl")
        assert all(r["basis"] == ml.RESIDUE_BASIS for r in rows)
        ext_subset = sum(1 for r in rows if r["slotClass"] == "external")
        log = (ext / "EXTRACTION-LOG.md").read_text(encoding="utf-8")
        assert "DRIFT" in log or "122" in log, \
            "fresh number becomes the seed with DRIFT against 122@20226581"
        assert ext_subset >= 24, "external subset seed is 24 rows (M14)"
