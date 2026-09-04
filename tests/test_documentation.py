import json
from pathlib import Path
import sys

PACK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACK_ROOT / "tools"))

from check_documentation import (  # noqa: E402
    CURRENT_REQUIRED,
    REQUIRED,
    github_actions_present,
    href_targets_removed_transcript,
    run_checks,
    source_manifest_failures,
    storefront_language_names,
    unclassified_docs,
)


def test_documentation_alignment() -> None:
    assert run_checks(PACK_ROOT) == []


def test_complete_curated_inventory_is_guarded() -> None:
    assert len(REQUIRED) == 68
    for rel in (
        "data/sources/MANIFEST.md",
        "extracted/EXTRACTION-LOG.md",
        "extracted/logic/LOGIC.md",
        "docs/scout-report-piece-08-search.mdx",
        "docs/specs/piece-08-search-corpus.mdx",
        "docs/rulings/reconciler-piece07-notes.mdx",
    ):
        assert rel in REQUIRED
    assert len(CURRENT_REQUIRED) == 26


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


def test_unclassified_curated_doc_is_detected(tmp_path: Path) -> None:
    path = tmp_path / "docs" / "unowned-plan.mdx"
    path.parent.mkdir(parents=True)
    path.write_text("# unowned\n", encoding="utf-8")
    assert unclassified_docs(tmp_path) == ["docs/unowned-plan.mdx"]


def test_storefront_language_reconciliation(tmp_path: Path) -> None:
    raw = (
        "English<strong>*</strong>, French, Italian, German<strong>*</strong>, "
        "Spanish - Spain, Korean, Polish, Portuguese - Brazil, Simplified Chinese"
        "<strong>*</strong>, Traditional Chinese, Turkish<br>"
        "<strong>*</strong>languages with full audio support"
    )
    assert storefront_language_names(raw) == [
        "English",
        "French",
        "Italian",
        "German",
        "Spanish - Spain",
        "Korean",
        "Polish",
        "Portuguese - Brazil",
        "Simplified Chinese",
        "Traditional Chinese",
        "Turkish",
    ]
    sources = tmp_path / "data" / "sources"
    sources.mkdir(parents=True)
    (sources / "steam-appdetails-1649080.json").write_text(
        json.dumps({"supported_languages_raw": raw}), encoding="utf-8"
    )
    (sources / "MANIFEST.md").write_text(
        "11 storefront languages; Japanese and Russian are absent; "
        "client's 13 locale bundles are authoritative.\n",
        encoding="utf-8",
    )
    assert source_manifest_failures(tmp_path) == []
    (sources / "MANIFEST.md").write_text(
        "storefront langs == client 13\n", encoding="utf-8"
    )
    assert source_manifest_failures(tmp_path)


def test_github_actions_workflows_are_detected(tmp_path: Path) -> None:
    workflow = tmp_path / ".github" / "workflows" / "ci.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text("name: ci\n", encoding="utf-8")
    assert github_actions_present(tmp_path) is True
    assert github_actions_present(PACK_ROOT) is False
