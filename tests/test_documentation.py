from pathlib import Path
import sys

PACK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACK_ROOT / "tools"))

from check_documentation import (  # noqa: E402
    github_actions_present,
    href_targets_removed_transcript,
    run_checks,
)


def test_documentation_alignment() -> None:
    assert run_checks(PACK_ROOT) == []


def test_relative_transcript_hrefs_are_detected(tmp_path: Path) -> None:
    source = tmp_path / "docs" / "specs" / "piece.mdx"
    source.parent.mkdir(parents=True)
    source.write_text("placeholder\n", encoding="utf-8")
    assert href_targets_removed_transcript(
        source, "../reviews/reviewer-002-piece-01.mdx", tmp_path
    )
    assert href_targets_removed_transcript(source, "../verifications/", tmp_path)
    assert href_targets_removed_transcript(
        source, "../verifications/verifyA-scout-piece08.mdx", tmp_path
    )
    assert href_targets_removed_transcript(
        source, "docs/reviews/reviewer-002-piece-01.mdx", tmp_path
    )
    assert not href_targets_removed_transcript(
        source, "../review-history.mdx", tmp_path
    )
    assert not href_targets_removed_transcript(
        source, "../rulings/arbiter-001-piece-01.mdx", tmp_path
    )
    assert not href_targets_removed_transcript(
        source, "https://example.com/docs/reviews/x.mdx", tmp_path
    )


def test_github_actions_workflows_are_detected(tmp_path: Path) -> None:
    workflow = tmp_path / ".github" / "workflows" / "ci.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text("name: ci\n", encoding="utf-8")
    assert github_actions_present(tmp_path) is True
    assert github_actions_present(PACK_ROOT) is False
