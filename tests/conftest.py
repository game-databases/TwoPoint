"""Suite wiring: black-box runner invocation, shared fixture trees, markers,
and the LOUD impl-missing accounting (skipped-for-missing-impl must be visible
in the summary, never silent)."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
PACK_ROOT = HERE.parent
RUN_ALL = PACK_ROOT / "run_all.py"
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

DEFAULT_GAME = Path(r"A:\SteamLibrary\steamapps\common\Two Point Campus")

# heavy client-gated legs rewrite large parts of extracted/ (stages 1-5 over the
# real corpus: minutes-to-hours + tens of GB). They need BOTH the game present
# AND this explicit opt-in knob; stage-0 legs are cheap and game-presence only.
HEAVY_ENV = "TPC_IT_HEAVY"


def game_dir() -> Path | None:
    env = os.environ.get("TPC_GAME_DIR")
    if env and Path(env).exists():
        return Path(env)
    if DEFAULT_GAME.exists():
        return DEFAULT_GAME
    return None


def require_impl():
    """Loud guard for black-box tests: the runner entrypoint must exist."""
    if not RUN_ALL.exists():
        pytest.skip(f"impl-missing: {RUN_ALL.name} not present yet (CodeWriter pending)")


def run_pack(args, *, game=None, extracted_root=None, extra_env=None, timeout=300):
    """Invoke `python run_all.py ...` as a black box with test-scoped env."""
    require_impl()
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    env.setdefault("PYTHONIOENCODING", "utf-8")
    if game is not None:
        env["TPC_GAME_DIR"] = str(game)
    if extracted_root is not None:
        env["TPC_EXTRACTED_ROOT"] = str(extracted_root)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, str(RUN_ALL), *args],
        cwd=str(PACK_ROOT), env=env, timeout=timeout,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )


def tree_game(tree) -> str:
    """Install-root path inside a prepared fixture tree."""
    return str(Path(tree) / "steamapps" / "common" / "Two Point Campus")


def seeded_extracted_root(tree, base, name="ext"):
    """Private copy of a prepared tree's synthetic extraction root.

    Hostless `--only <id>` runs read their upstream artifacts from AND write
    their outputs into the extraction root (TPC_EXTRACTED_ROOT); the copy
    keeps the session-shared fixture trees pristine between tests.
    Recursion guard: hazardous directories never ride along — nested-deeper
    ones are excluded silently, one DIRECTLY inside the source root raises
    loudly (build_fixture_tree.check_source_root / hazard_ignore).
    """
    import shutil

    from build_fixture_tree import check_source_root, hazard_ignore

    src = Path(tree) / "extracted"
    dst = Path(base) / name
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True)
    if src.exists():
        check_source_root(src)
        shutil.copytree(src, dst, dirs_exist_ok=True, ignore=hazard_ignore)
    return dst


def build_tree(stage: Path | str, tmp_path_factory, name: str, **kw) -> Path:
    out = tmp_path_factory.mktemp(name)
    sys.path.insert(0, str(HERE))
    import _fixturelib as fx

    from build_fixture_tree import check_source_root
    check_source_root(out)  # recursion guard (fresh mktemp dirs pass trivially)
    fx.build_tree(out, str(stage), **kw)
    return out


# --- cached per-stage prepared trees (session scope) -----------------------------

_TREES: dict[str, Path] = {}


@pytest.fixture(scope="session")
def fx_stage0(tmp_path_factory) -> Path:
    if "verify-client" not in _TREES:
        _TREES["verify-client"] = build_tree("verify-client", tmp_path_factory, "fx_stage0")
    return _TREES["verify-client"]


@pytest.fixture(scope="session")
def fx_stage2(tmp_path_factory) -> Path:
    if "harvest-catalog" not in _TREES:
        _TREES["harvest-catalog"] = build_tree("harvest-catalog", tmp_path_factory, "fx_stage2")
    return _TREES["harvest-catalog"]


@pytest.fixture(scope="session")
def fx_stage3(tmp_path_factory) -> Path:
    if "harvest-bundles" not in _TREES:
        _TREES["harvest-bundles"] = build_tree("harvest-bundles", tmp_path_factory, "fx_stage3")
    return _TREES["harvest-bundles"]


@pytest.fixture(scope="session")
def fx_stage4(tmp_path_factory) -> Path:
    if "localisation" not in _TREES:
        _TREES["localisation"] = build_tree("localisation", tmp_path_factory, "fx_stage4")
    return _TREES["localisation"]


@pytest.fixture(scope="session")
def fx_stage5(tmp_path_factory) -> Path:
    if "emit-stub-datasets" not in _TREES:
        _TREES["emit-stub-datasets"] = build_tree(
            "emit-stub-datasets", tmp_path_factory, "fx_stage5")
    return _TREES["emit-stub-datasets"]


@pytest.fixture(scope="session")
def fx_stage5_full(tmp_path_factory) -> Path:
    """Full-scale tree (176 roster rows): live counts match expectedBundles."""
    key = "emit-stub-datasets-full"
    if key not in _TREES:
        _TREES[key] = build_tree("emit-stub-datasets", tmp_path_factory,
                                 "fx_stage5_full", full_scale=True)
    return _TREES[key]


@pytest.fixture(scope="session")
def fx_relink(tmp_path_factory) -> Path:
    """piece-02 §3 stage-6 prepared tree (Revision 7 hostless mode)."""
    if "relink" not in _TREES:
        _TREES["relink"] = build_tree("relink", tmp_path_factory, "fx_relink")
    return _TREES["relink"]


def pytest_configure(config):
    config.addinivalue_line("markers", "client_gated: needs TPC_GAME_DIR/default install; auto-skips when absent")
    config.addinivalue_line("markers", "heavy: rewrites real extracted/ at scale; also needs TPC_IT_HEAVY=1")


def pytest_sessionfinish(session, exitstatus):
    from _impl import missing_modules, missing_symbols
    n_mod = len(missing_modules)
    n_sym = len(missing_symbols)
    if n_mod or n_sym:
        print(f"\n=== IMPL-MISSING SUMMARY: {n_mod} module(s), {n_sym} symbol(s) unresolved "
              f"-- skips above marked 'impl-missing' await the CodeWriter deliverable ===")
        for m in missing_modules[:12]:
            print(f"    module : {m}")
        for s in missing_symbols[:24]:
            print(f"    symbol : {s}")
