"""Runner obligations (spec §8 runner bullets + §5.1/§5.5 + R10)."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

from _validators import STAGE_IDS, diff_manifests, hash_tree, read_jsonl

HERE = Path(__file__).parent
PACK_ROOT = HERE.parent
RUN_ALL = PACK_ROOT / "run_all.py"

TEMP_PATTERNS = ("*.tmp", "*.tmp.*", "*.partial", "*.part", "*.temp")
_FX_TREES: list = []


def _require_impl():
    if not RUN_ALL.exists():
        pytest.skip(f"impl-missing: run_all.py not present yet (CodeWriter pending)")


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


# --- §5.1 --list -------------------------------------------------------------------

def test_list_enumerates_six_ids_in_order():
    _require_impl()
    r = run_pack(["--list"])
    assert r.returncode == 0, f"--list failed rc={r.returncode}\n{r.stdout}{r.stderr}"
    out = r.stdout
    pos = []
    for sid in STAGE_IDS:
        p = out.find(sid)
        assert p >= 0, f"--list output missing stage id {sid!r}:\n{out}"
        pos.append(p)
    assert pos == sorted(pos), (
        f"--list enumerates stages out of order: "
        f"{[sid for sid, _ in sorted(zip(STAGE_IDS, pos), key=lambda t: t[1])]}")
    header = out.lower()
    for word in ("tool", "version", "status"):
        assert word in header, f"--list lacks the {word!r} column (§5.1)"


def test_make_list_equivalent():
    _require_impl()
    make = shutil.which("make")
    if make is None:
        pytest.skip("environment-missing: `make` not on PATH on this host")
    r = subprocess.run([make, "list"], cwd=str(PACK_ROOT), capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=120)
    assert r.returncode == 0, f"make list failed rc={r.returncode}\n{r.stdout}{r.stderr}"
    for sid in STAGE_IDS:
        assert sid in r.stdout, f"`make list` missing stage {sid!r}"


# --- --only isolation ---------------------------------------------------------------

def test_only_isolation_leaves_other_stage_outputs_untouched(fx_stage5, tmp_path_factory):
    """`--only emit-stub-datasets` must not create/modify any other stage's
    declared outputs."""
    from conftest import seeded_extracted_root
    ext_root = seeded_extracted_root(fx_stage5, tmp_path_factory.mktemp("iso"))
    before = hash_tree(ext_root)
    r = run_pack([fx_stage5, "--only", "emit-stub-datasets"],
                 extracted_root=ext_root)
    after = hash_tree(ext_root)
    only_before, only_after, changed = diff_manifests(before, after)
    touched_other = [p for p in only_after + changed
                     if not p.startswith(("stubs/", "relinks/", ".stage-stamps",
                                          "EXTRACTION-LOG.md", ".pipeline-meta.json"))
                     and "EXTRACTION-LOG.md" not in p]
    assert r.returncode == 0, f"isolation run failed rc={r.returncode}\n{r.stdout}{r.stderr}"
    assert not touched_other, (
        f"--only emit-stub-datasets wrote outside its declared outputs: {touched_other}")
    assert only_after or changed, "isolation run produced nothing at all"


# --- stamp invalidation ---------------------------------------------------------------

def _copy_harness(dst: Path):
    ignore = shutil.ignore_patterns(
        ".git*", ".agents", ".claude", "__pycache__", "extracted",
        ".fixture-trees", "*.pyc", "site", "design", "data")
    shutil.copytree(PACK_ROOT, dst, ignore=ignore, dirs_exist_ok=True)
    return dst


def test_stamp_invalidation_on_script_hash_change(tmp_path_factory):
    _require_impl()
    pack = _copy_harness(tmp_path_factory.mktemp("packcopy"))
    ext = pack / "extracted"
    script = pack / "tools" / "stage0_verify_client.py"
    if not script.exists():
        pytest.skip("impl-missing: tools/stage0_verify_client.py")

    def log_count():
        log = ext / "EXTRACTION-LOG.md"
        if not log.exists():
            return 0
        return sum(1 for ln in log.read_text(encoding="utf-8", errors="replace").splitlines()
                   if "verify-client" in ln)

    roster = ext / "bundle-roster.jsonl"

    def mtime():
        return roster.stat().st_mtime_ns if roster.exists() else None

    tree = pack / "_fx"
    sys.path.insert(0, str(HERE))
    import _fixturelib as fx
    fx.build_tree(tree, "verify-client")
    game = str(fx.game_root(tree))
    ext = tree / "extracted"

    r1 = subprocess.run([sys.executable, str(pack / "run_all.py"), game,
                         "--only", "verify-client"],
                        cwd=str(pack),
                        env={**os.environ, "PYTHONUTF8": "1",
                             "TPC_EXTRACTED_ROOT": str(ext)},
                        capture_output=True, text=True, encoding="utf-8",
                        errors="replace", timeout=300)
    assert r1.returncode == 0, f"first run failed rc={r1.returncode}\n{r1.stdout}{r1.stderr}"
    c1, m1 = log_count(), mtime()

    # unchanged script -> stamped skip (no re-execution signal)
    time.sleep(0.02)
    r2 = subprocess.run([sys.executable, str(pack / "run_all.py"), game,
                         "--only", "verify-client"],
                        cwd=str(pack),
                        env={**os.environ, "PYTHONUTF8": "1",
                             "TPC_EXTRACTED_ROOT": str(ext)},
                        capture_output=True, text=True, encoding="utf-8",
                        errors="replace", timeout=300)
    assert r2.returncode == 0, r2.stdout + r2.stderr
    skipped = (log_count() == c1) or (mtime() == m1)
    assert skipped, (
        "rerunning an up-to-date stage produced new execution evidence "
        f"(log {c1}->{log_count()}, mtime moved) — no stamp/idempotence identity in play")

    # mutate the stage script -> hash changes -> stamp invalidated -> re-executes
    with open(script, "a", encoding="utf-8", newline="\n") as fh:
        fh.write("\n# test-only hash bump (stamp invalidation)\n")
    time.sleep(0.02)
    r3 = subprocess.run([sys.executable, str(pack / "run_all.py"), game,
                         "--only", "verify-client"],
                        cwd=str(pack),
                        env={**os.environ, "PYTHONUTF8": "1",
                             "TPC_EXTRACTED_ROOT": str(ext)},
                        capture_output=True, text=True, encoding="utf-8",
                        errors="replace", timeout=300)
    assert r3.returncode == 0, f"post-mutation rerun failed rc={r3.returncode}\n{r3.stdout}{r3.stderr}"
    m3 = mtime()
    c3 = log_count()
    reexecuted = (c3 > c1) or (m3 != m1)
    assert reexecuted, (
        "changing a stage script's hash did NOT invalidate its stamp "
        f"(log count {c1}->{c3}, output mtime unchanged) — no execution evidence")


# --- exit-code mapping 0/1/2/3 ---------------------------------------------------------

def test_exit_code_0_success(fx_stage0, tmp_path):
    r = run_pack([fx_stage0, "--only", "verify-client"], extracted_root=tmp_path / "e")
    assert r.returncode == 0, r.stdout + r.stderr


def test_exit_code_3_missing_game(tmp_path):
    r = run_pack([tmp_path / "absent-game", "--only", "verify-client"],
                 extracted_root=tmp_path / "e")
    assert r.returncode == 3


def test_exit_code_2_completed_with_ledger(fx_stage3, tmp_path):
    from conftest import seeded_extracted_root
    ext = seeded_extracted_root(fx_stage3, tmp_path, "e")
    r = run_pack([fx_stage3, "--only", "harvest-bundles"], extracted_root=ext)
    assert r.returncode == 2, r.stdout + r.stderr


def test_exit_code_1_stage_failure_on_corrupt_input(fx_stage5, tmp_path_factory, tmp_path):
    """A present-but-corrupt upstream artifact is a stage FAILURE (exit 1) —
    not an env refusal (the input exists) and never a silent pass. The locale
    matrix is the victim here: it is consumed eagerly, so a corrupt file must
    stop the stage loudly."""
    tree = tmp_path_factory.mktemp("fx5corrupt")
    sys.path.insert(0, str(HERE))
    import _fixturelib as fx
    fx.build_tree(tree, "emit-stub-datasets")
    from conftest import seeded_extracted_root
    ext = seeded_extracted_root(tree, tmp_path, "e")
    victim = ext / "locales" / "locale-matrix.json"
    victim.write_text("{ this is not json", encoding="utf-8")
    r = run_pack([fx.game_root(tree), "--only", "emit-stub-datasets"], extracted_root=ext)
    assert r.returncode == 1, (
        f"a corrupt upstream input must fail the stage with exit 1, got "
        f"rc={r.returncode}\n{r.stdout}{r.stderr}")


# --- interrupted-run convergence (R10 write discipline) ---------------------------------

def _wait_for_first_output(ext: Path, timeout_s: float = 30.0) -> Path | None:
    stubs = ext / "stubs"
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if stubs.exists():
            files = sorted(stubs.rglob("*"))
            real = [f for f in files if f.is_file()]
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


def test_interrupted_run_converges_to_clean_result(fx_stage5_full, tmp_path_factory):
    """Kill a stage mid-write; rerun to completion; final declared outputs must
    hash-equal a clean uninterrupted run (temp-file+atomic-rename discipline)."""
    _require_impl()

    def clean_manifest(into: Path) -> dict:
        r = run_pack([fx_stage5_full, "--only", "emit-stub-datasets"],
                     extracted_root=into)
        assert r.returncode == 0, r.stdout + r.stderr
        return hash_tree(into)

    from conftest import seeded_extracted_root
    reference = clean_manifest(
        seeded_extracted_root(fx_stage5_full, tmp_path_factory.mktemp("conv-ref")))

    caught_midwrite = False
    last_detail = ""
    for attempt in range(3):
        work_ext = seeded_extracted_root(
            fx_stage5_full, tmp_path_factory.mktemp(f"conv-kill-{attempt}"))
        env = {**os.environ, "PYTHONUTF8": "1",
               "TPC_EXTRACTED_ROOT": str(work_ext)}
        proc = subprocess.Popen(
            [sys.executable, str(RUN_ALL), *conftest_tree_game(fx_stage5_full),
             "--only", "emit-stub-datasets"],
            cwd=str(PACK_ROOT), env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        first = _wait_for_first_output(work_ext, timeout_s=60)
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

    # partial finals must never exist: whatever survived is parseable-complete
    stubs = work_ext / "stubs"
    if stubs.exists():
        for f in stubs.rglob("*.jsonl"):
            rows = read_jsonl(f)  # raises on truncated/partial finals
            assert rows or f.name.startswith("_"), f"empty partial final {f}"
    avail = work_ext / "relinks" / "locale_availability.jsonl"
    if avail.exists():
        read_jsonl(avail)

    # rerun to completion -> converge to the clean-run result byte-for-byte
    r = run_pack([str(fx_stage5_full), "--only", "emit-stub-datasets"],
                 extracted_root=work_ext)
    assert r.returncode == 0, f"rerun-after-kill failed rc={r.returncode}\n{r.stdout}{r.stderr}"
    final = hash_tree(work_ext)
    stray = [str(p.relative_to(work_ext)) for pat in TEMP_PATTERNS
             for p in work_ext.rglob(pat)]
    only_ref, only_final, changed = diff_manifests(reference, final)
    assert not (only_ref or only_final or changed), (
        f"interrupted run did not converge to the clean result: "
        f"missing={only_ref[:6]} extra={only_final[:6]} changed={changed[:6]}")
    # informational: leftover temp files would be cleaned by successful reruns
    assert not [s for s in stray], \
        f"successful rerun left temp files behind (rename discipline): {stray[:5]}"
