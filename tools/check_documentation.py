#!/usr/bin/env python3
"""Validate TwoPoint's current documentation and phase alignment."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

CURRENT_REQUIRED = (
    "README.md",
    "PROGRESS.mdx",
    "QUESTION-QUEUE.md",
    "spec.md",
    "data-acquisition.md",
    "competitor-research.md",
    "toolchain.md",
    "tools-plan.md",
    "missingdata.md",
    "contracts/README.mdx",
    "tests/README.md",
    "data/sources/MANIFEST.md",
    "extracted/EXTRACTION-LOG.md",
    "extracted/PROOF.md",
    "extracted/VALIDATION-REPORT.md",
    "extracted/RELATIONS.md",
    "extracted/MEDIA-CATALOGUE.md",
    "extracted/logic/LOGIC.md",
    "extracted/protocol/README.md",
    "docs/README.mdx",
    "docs/current-stage.mdx",
    "docs/architecture.mdx",
    "docs/site-plan.mdx",
    "docs/design-direction.mdx",
    "docs/review-history.mdx",
    "docs/reviewer-handoff.mdx",
)

SCOUT_REPORTS = (
    "docs/scout-report-001.mdx",
    "docs/scout-report-piece-02.mdx",
    "docs/scout-report-piece-03.mdx",
    "docs/scout-report-piece-04.mdx",
    "docs/scout-report-piece-05-contracts.mdx",
    "docs/scout-report-piece-06-media.mdx",
    "docs/scout-report-piece-07-locales.mdx",
    "docs/scout-report-piece-08-search.mdx",
)

PIECE_SPECS = tuple(
    f"docs/specs/piece-{index:02d}-{name}.mdx"
    for index, name in (
        (1, "extraction-pipeline"),
        (2, "relinking"),
        (3, "maps"),
        (4, "logic"),
        (5, "contracts"),
        (6, "media"),
        (7, "locale-proof"),
        (8, "search-corpus"),
    )
)

RULINGS = (
    "docs/rulings/arbiter-001-piece-01.mdx",
    "docs/rulings/arbiter-002-piece-01-build.mdx",
    "docs/rulings/arbiter-piece03-spec.mdx",
    "docs/rulings/arbiter-piece04-spec.mdx",
    "docs/rulings/arbiter-piece05-spec.mdx",
    "docs/rulings/arbiter-piece06-spec.mdx",
    "docs/rulings/arbiter-piece07-spec.mdx",
    "docs/rulings/arbiter-piece08-spec.mdx",
    "docs/rulings/orchestrator-piece03-scope.mdx",
    "docs/rulings/orchestrator-piece04-scope.mdx",
    "docs/rulings/reconciler-piece04-notes.mdx",
    "docs/rulings/reconciler-piece07-notes.mdx",
)

CONTRACT_NOTES = (
    "contracts/counter-units.mdx",
    "contracts/ledger-map.mdx",
    "contracts/families/exceptions.mdx",
    "contracts/families/stage0-identity.mdx",
    "contracts/families/stage1-decompile.mdx",
    "contracts/families/stage2-addressables.mdx",
    "contracts/families/stage3-harvest.mdx",
    "contracts/families/stage4-locales.mdx",
    "contracts/families/stage5-stubs.mdx",
    "contracts/families/stage6-relinks.mdx",
)

SOURCE_PROVENANCE = (
    "data/sources/competitor/fandom/PROVENANCE.md",
    "data/sources/competitor/steam-guides/PROVENANCE.md",
    "data/sources/competitor/wiki-gg/PROVENANCE.md",
)

SUPPORTING_EVIDENCE = ("docs/competitor-piece02-models.mdx",)

REQUIRED = (
    CURRENT_REQUIRED
    + SCOUT_REPORTS
    + PIECE_SPECS
    + RULINGS
    + CONTRACT_NOTES
    + SOURCE_PROVENANCE
    + SUPPORTING_EVIDENCE
)

DOCS_INVENTORY = frozenset(
    rel
    for rel in REQUIRED
    if rel.startswith("docs/")
)

CANONICAL = (
    "README.md",
    "PROGRESS.mdx",
    "QUESTION-QUEUE.md",
    "spec.md",
    "data-acquisition.md",
    "competitor-research.md",
    "toolchain.md",
    "tools-plan.md",
    "missingdata.md",
    "data/sources/MANIFEST.md",
    "extracted/PROOF.md",
    "extracted/VALIDATION-REPORT.md",
    "extracted/RELATIONS.md",
    "extracted/MEDIA-CATALOGUE.md",
    "docs/README.mdx",
    "docs/current-stage.mdx",
    "docs/reviewer-handoff.mdx",
)

RETIRED_PATTERNS = {
    r"Nothing is extracted yet": "bootstrap claim",
    r"PLACEHOLDER POINTER ONLY": "PROOF placeholder",
    r"PIECE-1 PLACEHOLDER": "validation placeholder",
    r"hub path TBD": "retired central-hosting vocabulary",
    r"dedicated vs hub path": "retired tier/hosting question",
    r"six stage": "retired stage-count prose",
    r"storefront langs == client 13": "incorrect storefront-locale claim",
    r"\bbefore merge\b": "merge-coupled project gate",
    r"empirical checks required before merge": "merge-coupled handoff wording",
    r"final PR review is submitted on this head": "self-invalidating review claim",
    r"complete the two review passes": "already-completed PR review task",
}

STAGES = (
    "verify-client",
    "decompile",
    "harvest-catalog",
    "harvest-bundles",
    "localisation",
    "emit-stub-datasets",
    "relink",
    "maps",
    "logic",
    "locale-proof",
    "check-contracts",
    "media",
    "search-corpus",
)

LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
REMOVED_TRANSCRIPT_DIRS = ("docs/reviews", "docs/verifications")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _markdown_paths(root: Path) -> list[Path]:
    return sorted(
        {
            *root.rglob("*.md"),
            *root.rglob("*.mdx"),
        }
    )


def _posix_under_root(path: Path, root: Path) -> str | None:
    """Return a lowercased posix path relative to root, or None if outside it."""
    try:
        return path.resolve().relative_to(root.resolve()).as_posix().lower()
    except ValueError:
        return None


def _rel_is_removed_transcript(rel_posix: str) -> bool:
    rel = rel_posix.replace("\\", "/").lower().rstrip("/")
    return any(
        rel == dirname or rel.startswith(f"{dirname}/")
        for dirname in REMOVED_TRANSCRIPT_DIRS
    )


def href_targets_removed_transcript(source: Path, href: str, root: Path) -> bool:
    """True when a Markdown href names or resolves to a deleted transcript path."""
    raw = href.strip()
    if not raw or raw.startswith(("http://", "https://", "mailto:", "#")):
        return False
    path_part = raw.split("#", 1)[0].split("?", 1)[0].replace("\\", "/")
    if not path_part:
        return False
    lowered = path_part.lower().rstrip("/")
    if _rel_is_removed_transcript(lowered):
        return True
    resolved_rel = _posix_under_root(source.parent / path_part, root)
    return bool(resolved_rel and _rel_is_removed_transcript(resolved_rel))


def github_actions_present(root: Path) -> bool:
    """True when any GitHub Actions workflow file exists under the pack root."""
    workflows = root / ".github" / "workflows"
    return workflows.exists() and any(path.is_file() for path in workflows.rglob("*"))


def unclassified_docs(root: Path) -> list[str]:
    """Return unexpected curated files under docs/."""
    docs_root = root / "docs"
    if not docs_root.exists():
        return []
    actual = {
        path.relative_to(root).as_posix()
        for path in _markdown_paths(docs_root)
        if path.is_file()
    }
    return sorted(actual - DOCS_INVENTORY)


def storefront_language_names(raw: str) -> list[str]:
    """Parse the storefront's comma-separated language field before its audio note."""
    listing = raw.split("<br", 1)[0]
    names = []
    for part in listing.split(","):
        text = re.sub(r"<[^>]+>", "", part).replace("*", "").strip()
        if text:
            names.append(text)
    return names


def source_manifest_failures(root: Path) -> list[str]:
    """Cross-check the human manifest against the checked-in raw appdetails snapshot."""
    failures: list[str] = []
    manifest_path = root / "data" / "sources" / "MANIFEST.md"
    snapshot_path = root / "data" / "sources" / "steam-appdetails-1649080.json"
    if not manifest_path.is_file() or not snapshot_path.is_file():
        return failures
    try:
        snapshot = json.loads(_read(snapshot_path))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"invalid storefront snapshot: {exc}"]
    names = storefront_language_names(
        str(snapshot.get("supported_languages_raw") or "")
    )
    if len(names) != 11:
        failures.append(
            f"storefront snapshot language count changed: expected 11, measured {len(names)}"
        )
    unexpected = sorted({"Japanese", "Russian"} & set(names))
    if unexpected:
        failures.append(
            "storefront snapshot unexpectedly contains client-only locales: "
            + ", ".join(unexpected)
        )
    manifest = _read(manifest_path)
    for phrase in (
        "11 storefront languages",
        "Japanese and Russian are absent",
        "client's 13 locale bundles",
    ):
        if phrase not in manifest:
            failures.append(
                f"data/sources/MANIFEST.md lacks storefront reconciliation phrase: {phrase}"
            )
    return failures


def run_checks(root: Path) -> list[str]:
    failures: list[str] = []

    for rel in REQUIRED:
        path = root / rel
        if not path.is_file():
            failures.append(f"missing required document: {rel}")
        elif not _read(path).strip():
            failures.append(f"empty required document: {rel}")

    for rel in unclassified_docs(root):
        failures.append(f"unclassified documentation under docs/: {rel}")

    for dirname in REMOVED_TRANSCRIPT_DIRS:
        if (root / dirname).exists():
            failures.append(f"superseded transcript directory still exists: {dirname}")

    if github_actions_present(root):
        failures.append("GitHub Actions workflows are forbidden for this pack")

    if (root / "site").exists():
        failures.append("site/ exists while canonical phase is data-gate closed")

    for rel in CANONICAL:
        path = root / rel
        if not path.is_file():
            continue
        text = _read(path)
        for pattern, label in RETIRED_PATTERNS.items():
            if re.search(pattern, text, flags=re.IGNORECASE):
                failures.append(f"{rel}: contains retired {label}: /{pattern}/")

    toolchain = root / "toolchain.md"
    readme = root / "README.md"
    if toolchain.is_file() and readme.is_file():
        combined = _read(toolchain) + "\n" + _read(readme)
        for stage in STAGES:
            if f"`{stage}`" not in combined:
                failures.append(f"stage undocumented in README/toolchain: {stage}")

    docs_index = root / "docs" / "README.mdx"
    if docs_index.is_file():
        text = _read(docs_index)
        for family in (
            "Current authorities",
            "Scout reports",
            "Piece specifications",
            "Rulings",
            "Contract notes",
            "Source provenance",
            "Removed documentation",
        ):
            if family not in text:
                failures.append(f"docs/README.mdx lacks classification: {family}")

    for failure in source_manifest_failures(root):
        failures.append(failure)

    for path in _markdown_paths(root):
        rel = path.relative_to(root).as_posix()
        for target in LINK_RE.findall(_read(path)):
            if href_targets_removed_transcript(path, target, root):
                failures.append(f"{rel}: link targets a removed transcript: {target}")

    for rel in CURRENT_REQUIRED:
        path = root / rel
        if not path.is_file():
            continue
        text = _read(path)
        for target in LINK_RE.findall(text):
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            target = target.split("#", 1)[0].split("?", 1)[0]
            if not target:
                continue
            resolved = (path.parent / target).resolve()
            try:
                resolved.relative_to(root.resolve())
            except ValueError:
                # Cross-repository foundation links are intentionally outside
                # a standalone pack checkout.
                continue
            if not resolved.exists():
                failures.append(f"{rel}: broken local link: {target}")

    return sorted(set(failures))


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    failures = run_checks(root)
    if failures:
        print("documentation check: FAIL", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print(f"documentation check: PASS ({len(REQUIRED)} curated documents)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
