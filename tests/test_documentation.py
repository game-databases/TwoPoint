from pathlib import Path
import sys

PACK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACK_ROOT / "tools"))

from check_documentation import run_checks  # noqa: E402


def test_documentation_alignment() -> None:
    assert run_checks(PACK_ROOT) == []
