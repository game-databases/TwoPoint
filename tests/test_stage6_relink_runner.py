"""piece-02 §8 runner obligations for stage `relink` (Revision 7).

Covers the Runner bullet of piece-02 §8 that piece-1's test_runner.py
deliberately does not (its fixture bullets stay written against the six
piece-1 stages — Revision 7 note-only clause routes the seventh stage's
runner duties HERE):

- `--list` enumerates SEVEN stages, `relink` AFTER `emit-stub-datasets`;
- `--only relink` isolation — declared outputs only, and the R4
  sole-owner pin (`relinks/locale_availability.jsonl`) byte-untouched;
- exit-code mapping for stage 6: 3 missing game root, 1 present-but-
  corrupt upstream, 2 completed-with-ledger WITH the run section naming
  every contributing ledger + size (exit 0 is NOT hostless-reachable on
  this corpus: the fixture plants dangling GUIDs/unresolved PPtrs/floor-
  unmet, and the competitor ladder executes outside the pipeline — an
  exit 0 here would be the lie §5.7 exists to prevent);
- stamp invalidation on a stage-6 script-hash change (spec pins deps
  `["stage6_relink.py", "relink_util.py", "tpc_common.py", "log_util.py"]`);
- interrupted-run convergence (temp-file + atomic-rename discipline);
- carve-out guard still green after a relink run (zero media bytes);
- `tests/build_fixture_tree.py --stage relink` materializes the §3
  upstream set through the CLI entry (AC1 hostless smoke mode).

Black-box legs skip LOUDLY (impl-lagging banner) until the CodeWriter
registers the seventh stage — never faking a pass.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _relinklib as rl  # noqa: E402
from _validators import (  # noqa: E402
    KIND_TO_FILE, diff_manifests, hash_tree, read_json, read_jsonl,
    scan_tree_for_media_extensions,
)

HERE = Path(__file__).parent
PACK_ROOT = HERE.parent

# Revision 7 amendment 2 / piece-02 AC1: exactly seven, in this order.
SEVEN_STAGES = (
    "verify-client",
    "decompile",
    "harvest-catalog",
    "harvest-bundles",
    "localisation",
    "emit-stub-datasets",
    "relink",
)

# Declared stage-6 write surface (piece-02 §4 ownership block) + the
# runner-managed trio excluded from byte-identity comparisons.
STAGE6_OUTPUT_PREFIXES = ("relinks/", "RELATIONS.md", "EXTRACTION-LOG.md",
                          ".stage-stamps", ".pipeline-meta.json")

TEMP_PATTERNS = ("*.tmp", "*.tmp.*", "*.partial", "*.part", "*.temp")


def _bb():
    rl.require_relink_registered()


def run_pack(args, **kw):
    """run_pack that resolves fixture-tree roots to their install root."""
    from conftest import run_pack as rp
    fixed = []
    for a in args:
        a = str(a)
        if (Path(a) / "steamapps" / "common" / "Two Point Campus").exists():
            from conftest import tree_game
            a = tree_game(a)
        fixed.append(a)
    return rp(fixed, **kw)


def _copy_harness(dst: Path):
    """Full-pack copy (tools/ included, extracted/ excluded) for the
    stamp-invalidation harness — mutations land on the COPY, never the
    real pack. `.pytest_tmp` MUST stay excluded: crashed sessions left
    recursive pack-copies nested under it (packcopy0/.pytest_tmp/packcopy0/
    …), and copying that tree explodes the walker."""
    ignore = shutil.ignore_patterns(
        ".git*", ".agents", ".claude", "__pycache__", "extracted",
        ".fixture-trees", "*.pyc", "site", "design", "data", ".pytest_tmp",
        ".venv", "node_modules")
    shutil.copytree(PACK_ROOT, dst, ignore=ignore, dirs_exist_ok=True)
    return dst


# --- §8 runner bullet 1: --list shows seven stages in order -------------------------

def test_list_enumerates_seven_stages_relink_last():
    _bb()
    r = run_pack(["--list"])
    assert r.returncode == 0, f"--list failed rc={r.returncode}\n{r.stdout}{r.stderr}"
    out = r.stdout
    pos = []
    for sid in SEVEN_STAGES:
        p = out.find(sid)
        assert p >= 0, f"--list output missing stage id {sid!r}:\n{out}"
        pos.append(p)
    assert pos == sorted(pos), (
        f"--list enumerates the seven stages out of order "
        f"(Revision 7: relink AFTER emit-stub-datasets):\n{out}")
    header = out.lower()
    for word in ("tool", "version", "status"):
        assert word in header, f"--list lacks the {word!r} column"


def test_make_list_shows_seven_stages():
    _bb()
    make = shutil.which("make")
    if make is None:
        pytest.skip("environment-missing: `make` not on PATH on this host")
    r = subprocess.run([make, "list"], cwd=str(PACK_ROOT), capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=120)
    assert r.returncode == 0, f"make list failed rc={r.returncode}\n{r.stdout}{r.stderr}"
    pos = []
    for sid in SEVEN_STAGES:
        p = r.stdout.find(sid)
        assert p >= 0, f"`make list` missing stage {sid!r}"
        pos.append(p)
    assert pos == sorted(pos), "`make list` enumerates stages out of order"


# --- §8 runner bullet 2: --only relink isolation -------------------------------------

def test_only_relink_isolation_and_stage5_sole_owner_untouched(
        fx_relink, tmp_path_factory):
    """`--only relink` writes ONLY its declared outputs — and never touches
    stage 5's `locale_availability.jsonl` (R4 single-writer pin) nor any
    upstream stub/harvest artifact."""
    _bb()
    from conftest import seeded_extracted_root
    ext = seeded_extracted_root(fx_relink, tmp_path_factory.mktemp("iso6"))
    avail = ext / "relinks" / "locale_availability.jsonl"
    avail_before = avail.read_bytes()
    before = hash_tree(ext)
    r = run_pack([fx_relink, "--only", "relink"], extracted_root=ext, timeout=600)
    assert r.returncode in (0, 2), \
        f"isolation run failed rc={r.returncode}\n{r.stdout}{r.stderr}"
    after = hash_tree(ext)
    only_b, only_a, changed = diff_manifests(before, after)
    outside = [p for p in sorted(set(only_a) | set(changed))
               if not (p.startswith(STAGE6_OUTPUT_PREFIXES) or p == "RELATIONS.md")]
    assert not outside, (
        f"--only relink wrote outside its declared outputs: {outside[:8]}")
    assert only_a or changed, "isolation run produced nothing at all"
    assert avail.exists() and avail.read_bytes() == avail_before, \
        "R4 ownership pin violated: stage 6 modified locale_availability.jsonl"
    untouched_upstream = [p for p in changed
                          if p.startswith(("stubs/", "harvest/", "addressables/",
                                           "locales/", "decompiled/"))
                          or p == "bundle-roster.jsonl"]
    assert not untouched_upstream, \
        f"stage 6 mutated its own upstream artifacts: {untouched_upstream[:8]}"
    # the matrix is the headline artifact of the pass
    assert (ext / "relinks" / "matrix.json").exists(), "matrix.json not emitted"


# --- §8 runner bullet 4a: exit-code mapping ------------------------------------------

def test_exit_code_3_missing_game_root(fx_relink, tmp_path):
    """Stage 6 consumes the game dir (the R1 bridge passes open bundles);
    a missing game root is an environment refusal — exit 3 — even with the
    full upstream artifact set present."""
    _bb()
    from conftest import seeded_extracted_root
    ext = seeded_extracted_root(fx_relink, tmp_path / "e3")
    r = run_pack([tmp_path / "absent-game", "--only", "relink"],
                 extracted_root=ext)
    assert r.returncode == 3, (
        f"missing game root must refuse with exit 3, got rc={r.returncode}\n"
        f"{r.stdout}{r.stderr}")


def test_exit_code_1_corrupt_upstream_is_stage_failure(fx_relink, tmp_path_factory,
                                                       tmp_path):
    """A present-but-corrupt upstream artifact is a schema/validation FAILURE
    (exit 1) — never an env refusal (the input exists) and never a silent
    ledger row. The Addressables catalog is the victim: the R3 bridge filters
    guid keys out of it eagerly."""
    _bb()
    from conftest import seeded_extracted_root
    ext = seeded_extracted_root(fx_relink, tmp_path / "e1")
    victim = ext / "addressables" / "catalog.json"
    assert victim.exists()
    victim.write_text("{ this is not json", encoding="utf-8")
    r = run_pack([fx_relink, "--only", "relink"], extracted_root=ext, timeout=600)
    assert r.returncode == 1, (
        f"a corrupt upstream input must fail the stage with exit 1, got "
        f"rc={r.returncode}\n{r.stdout}{r.stderr}")


def _line_with_size(text: str, name: str, count: int) -> bool:
    """True when `name` appears on a line carrying `count` (or on a line
    whose immediate successor carries it) — the 'names every contributing
    ledger + size' reading of AC7."""
    num = re.compile(rf"(?<!\d){re.escape(str(count))}(?!\d)")
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        if name in ln:
            if num.search(ln):
                return True
            if i + 1 < len(lines) and num.search(lines[i + 1]):
                return True
    return False


def test_exit_code_2_run_section_names_contributing_ledgers_with_sizes(
        fx_relink, tmp_path_factory):
    """Exit 2 is the EXPECTED steady state on the fixture corpus (planted
    dangling GUID + unresolved PPtrs + floor-unmet + registry misses) — and
    the run section must name every contributing ledger WITH its size, never
    bare silence (§5.7)."""
    _bb()
    from conftest import seeded_extracted_root
    ext = seeded_extracted_root(fx_relink, tmp_path_factory.mktemp("e2led"))
    r = run_pack([fx_relink, "--only", "relink"], extracted_root=ext, timeout=600)
    combined = r.stdout + r.stderr
    assert r.returncode == 2, (
        f"expected exit 2 (planted ledgers non-empty), got rc={r.returncode}\n"
        f"{combined}")
    log = (ext / "EXTRACTION-LOG.md")
    assert log.exists(), "no EXTRACTION-LOG.md under the extraction root"
    text = log.read_text(encoding="utf-8", errors="replace")

    ledgers = {}
    for rel in ("relinks/_unresolved_pptrs.jsonl", "relinks/_dangling_guids.jsonl",
                "relinks/competitor_applied.jsonl"):
        p = ext / rel
        if p.exists():
            n = len(read_jsonl(p))
            if n:
                ledgers[p.name] = n
    jr = ext / "relinks" / "locale_join_report.json"
    misses = None
    if jr.exists():
        obj = read_json(jr)
        misses = obj.get("registryMisses")
        if isinstance(misses, int) and misses:
            ledgers["locale_join_report.json(registryMisses)"] = misses

    assert ledgers, "exit 2 claimed but every contributing ledger is empty"
    # File-backed ledgers are named by basename; counter-backed contributions
    # (registryMisses) may surface under their pinned run-section key instead.
    token_variants = {
        "_unresolved_pptrs.jsonl": ("_unresolved_pptrs.jsonl", "unresolvedCrossFile"),
        "_dangling_guids.jsonl": ("_dangling_guids.jsonl",),
        "competitor_applied.jsonl": ("competitor_applied.jsonl", "flagsMissing",
                                     "wallsRecorded"),
        "locale_join_report.json": ("registryMisses", "locale_join_report"),
    }
    unnamed = []
    for name, count in sorted(ledgers.items()):
        base = name.split("(")[0]
        variants = token_variants.get(base, (base,))
        if not any(_line_with_size(text, tok, count) for tok in variants):
            unnamed.append(f"{name}(={count})")
    assert not unnamed, (
        f"run section does not name contributing ledger(s) with their sizes: "
        f"{unnamed}; expected 'names every contributing ledger + size' per AC7")


# --- §8 runner bullet 4b: stamp invalidation on stage-6 script-hash change ------------

def test_stamp_invalidation_on_stage6_script_hash_change(tmp_path_factory):
    """Spec pins stage-6 script-hash deps INCLUDING the shared
    `relink_util.py`: touching EITHER must invalidate the relink stamp and
    force re-execution. Runs against a full pack COPY."""
    _bb()
    pack = _copy_harness(tmp_path_factory.mktemp("packcopy6"))
    script = pack / "tools" / "relink_util.py"
    if not script.exists():
        pytest.skip("impl-lagging: tools/relink_util.py not present yet")

    ext = pack / "_fx" / "extracted"

    def signals():
        """(relink log-line count, matrix.json mtime) — the two execution
        evidence channels piece-1's harness uses."""
        log = ext / "EXTRACTION-LOG.md"
        n = 0
        if log.exists():
            n = sum(1 for ln in log.read_text(encoding="utf-8",
                                              errors="replace").splitlines()
                    if "relink" in ln.lower())
        matrix = ext / "relinks" / "matrix.json"
        mt = matrix.stat().st_mtime_ns if matrix.exists() else None
        return n, mt

    tree = pack / "_fx"
    rl.build_relink_tree(tree)
    from conftest import tree_game
    game = str(tree_game(tree))

    def run_once():
        return subprocess.run(
            [sys.executable, str(pack / "run_all.py"), game, "--only", "relink"],
            cwd=str(pack),
            env={**os.environ, "PYTHONUTF8": "1",
                 "TPC_EXTRACTED_ROOT": str(ext)},
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=900)

    r1 = run_once()
    assert r1.returncode in (0, 2), \
        f"first relink run failed rc={r1.returncode}\n{r1.stdout}{r1.stderr}"
    c1, m1 = signals()

    time.sleep(0.02)
    r2 = run_once()
    assert r2.returncode in (0, 2), r2.stdout + r2.stderr
    c2, m2 = signals()
    assert c2 == c1 or m2 == m1, (
        "rerunning an up-to-date stage produced new execution evidence on BOTH "
        f"channels (log {c1}->{c2}, matrix mtime moved) — no stamp identity in play")

    with open(script, "a", encoding="utf-8", newline="\n") as fh:
        fh.write("\n# test-only hash bump (stamp invalidation)\n")
    time.sleep(0.02)
    r3 = run_once()
    assert r3.returncode in (0, 2), \
        f"post-mutation rerun failed rc={r3.returncode}\n{r3.stdout}{r3.stderr}"
    c3, m3 = signals()
    assert c3 > c1 or m3 != m1, (
        "changing tools/relink_util.py's hash did NOT invalidate the relink "
        "stamp — the spec-pinned dep set is "
        "['stage6_relink.py','relink_util.py','tpc_common.py','log_util.py']")


# --- §8 runner bullet 5: interrupted-run convergence ----------------------------------

def _wait_for_first_output(ext: Path, timeout_s: float = 60.0) -> Path | None:
    watch = ext / "relinks"
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if watch.exists():
            real = [f for f in sorted(watch.rglob("*")) if f.is_file()]
            if real:
                return real[0]
        time.sleep(0.005)
    return None


def _kill(proc):
    try:
        proc.kill()
    except OSError:
        pass
    proc.wait(timeout=15)


def test_interrupted_relink_run_converges_to_clean_result(fx_relink,
                                                          tmp_path_factory):
    """Kill `--only relink` mid-write; whatever survived must be
    parseable-complete finals (temp-file + atomic-rename); a rerun to
    completion converges byte-for-byte to a clean uninterrupted run."""
    _bb()
    from conftest import seeded_extracted_root, tree_game

    def clean_manifest(into: Path) -> dict:
        r = run_pack([fx_relink, "--only", "relink"], extracted_root=into,
                     timeout=900)
        assert r.returncode in (0, 2), r.stdout + r.stderr
        return hash_tree(into)

    reference = clean_manifest(
        seeded_extracted_root(fx_relink, tmp_path_factory.mktemp("conv6-ref")))

    caught_midwrite = False
    work_ext = None
    last_detail = ""
    for attempt in range(3):
        work_ext = seeded_extracted_root(
            fx_relink, tmp_path_factory.mktemp(f"conv6-kill-{attempt}"))
        env = {**os.environ, "PYTHONUTF8": "1",
               "TPC_EXTRACTED_ROOT": str(work_ext)}
        proc = subprocess.Popen(
            [sys.executable, str(PACK_ROOT / "run_all.py"),
             str(tree_game(fx_relink)), "--only", "relink"],
            cwd=str(PACK_ROOT), env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        first = _wait_for_first_output(work_ext)
        if first is not None:
            time.sleep(0.01 * (attempt + 1))
            alive = proc.poll() is None
            _kill(proc)
            caught_midwrite = alive
            if alive:
                break
        else:
            _kill(proc)
            last_detail = "stage finished before any output appeared to interrupt"
        if proc.poll() is None:
            _kill(proc)

    if not caught_midwrite:
        pytest.skip(
            f"interruption-window-not-caught after retries ({last_detail}); "
            "the kill landed outside the write window — rerun on a slower host path")

    # partial finals must never exist: whatever survived parses complete
    for f in work_ext.rglob("*.jsonl"):
        rows = read_jsonl(f)  # raises on truncated/partial finals
        assert rows or Path(f).name.startswith("_"), f"empty partial final {f}"
    if (work_ext / "relinks" / "matrix.json").exists():
        read_json(work_ext / "relinks" / "matrix.json")

    r = run_pack([fx_relink, "--only", "relink"], extracted_root=work_ext,
                 timeout=900)
    assert r.returncode in (0, 2), \
        f"rerun-after-kill failed rc={r.returncode}\n{r.stdout}{r.stderr}"
    stray = [str(p.relative_to(work_ext)) for pat in TEMP_PATTERNS
             for p in work_ext.rglob(pat)]
    only_ref, only_final, changed = diff_manifests(reference, hash_tree(work_ext))
    assert not (only_ref or only_final or changed), (
        f"interrupted relink run did not converge to the clean result: "
        f"missing={only_ref[:6]} extra={only_final[:6]} changed={changed[:6]}")
    assert not stray, \
        f"successful rerun left temp files behind (rename discipline): {stray[:5]}"


# --- §8 runner bullet 6: carve-out guard stays green ----------------------------------

def test_carveout_guard_green_after_relink_run(fx_relink, tmp_path_factory):
    """AC11: the piece emits ZERO media bytes — bridges open bundles
    read-only and emit metadata only. The media-extension grep over the
    extraction root must stay clean after a relink run."""
    _bb()
    from conftest import seeded_extracted_root
    ext = seeded_extracted_root(fx_relink, tmp_path_factory.mktemp("carve6"))
    r = run_pack([fx_relink, "--only", "relink"], extracted_root=ext, timeout=600)
    assert r.returncode in (0, 2), r.stdout + r.stderr
    hits = scan_tree_for_media_extensions(ext)
    assert not hits, f"media carve-out broken by stage 6: {hits[:8]}"


# --- §8 runner bullet 3: CLI prepared-tree builder covers the §3 upstream set ----------

def test_cli_build_fixture_tree_stage_relink(tmp_path):
    """AC1 hostless smoke mode, verbatim command:
    `python tests/build_fixture_tree.py --stage relink` materializes the §3
    upstream set synthetically, including the two-serialized-file bundle."""
    builder = HERE / "build_fixture_tree.py"
    out = tmp_path / "relink-cli"
    r = subprocess.run([sys.executable, str(builder), "--stage", "relink",
                        "--out", str(out)],
                       capture_output=True, text=True, encoding="utf-8",
                       timeout=300)
    assert r.returncode == 0, f"builder failed for relink: {r.stderr}"
    ext = out / "extracted"
    for fname in KIND_TO_FILE.values():
        assert (ext / "stubs" / fname).exists(), f"stubs/{fname} missing"
    for rel in ("stubs/_absences.jsonl", "stubs/_unmapped-families.jsonl",
                "harvest/export-manifest.jsonl", "harvest/externals.jsonl",
                "addressables/catalog.json", "locales/locale-matrix.json",
                "decompiled/structural/class-hierarchy.jsonl",
                "bundle-roster.jsonl", "relinks/locale_availability.jsonl"):
        assert (ext / rel).exists(), f"upstream artifact missing: {rel}"
    i2glob = sorted((ext / "harvest/monobehaviours/localisation_assets_localisation"
                     "/I2.Loc.LanguageSourceAsset").glob("*.json"))
    assert i2glob, "I2 LanguageSourceAsset dumps missing"
    two_cab = [row for row in rl.cab_index_seed_rows()
               if row["bundle"] == "items-general_assets_all.bundle"]
    assert len(two_cab) == 2, \
        "the synthetic items bundle must carry TWO serialized files (Rev-7 pin)"
    from conftest import tree_game
    game = tree_game(out)
    assert (Path(game) / "TPC_Data").exists(), "game skeleton missing"
