#!/usr/bin/env python3
"""Validate TwoPoint's current documentation and phase alignment."""
from __future__ import annotations

import re
import sys
from pathlib import Path

REQUIRED = (
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
    "extracted/PROOF.md",
    "extracted/VALIDATION-REPORT.md",
    "extracted/RELATIONS.md",
    "extracted/MEDIA-CATALOGUE.md",
    "extracted/protocol/README.md",
    "docs/README.mdx",
    "docs/current-stage.mdx",
    "docs/architecture.mdx",
    "docs/site-plan.mdx",
    "docs/design-direction.mdx",
    "docs/review-history.mdx",
    "docs/reviewer-handoff.mdx",
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
    "extracted/PROOF.md",
    "extracted/VALIDATION-REPORT.md",
    "extracted/RELATIONS.md",
    "extracted/MEDIA-CATALOGUE.md",
    "docs/current-stage.mdx",
)

RETIRED_PATTERNS = {
    r"Nothing is extracted yet": "bootstrap claim",
    r"PLACEHOLDER POINTER ONLY": "PROOF placeholder",
    r"PIECE-1 PLACEHOLDER": "validation placeholder",
    r"hub path TBD": "retired central-hosting vocabulary",
    r"dedicated vs hub path": "retired tier/hosting question",
    r"six stage": "retired stage-count prose",
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


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def run_checks(root: Path) -> list[str]:
    failures: list[str] = []

    for rel in REQUIRED:
        path = root / rel
        if not path.is_file():
            failures.append(f"missing required document: {rel}")
        elif not _read(path).strip():
            failures.append(f"empty required document: {rel}")

    for dirname in ("docs/reviews", "docs/verifications"):
        if (root / dirname).exists():
            failures.append(f"superseded transcript directory still exists: {dirname}")

    workflows = root / ".github" / "workflows"
    if workflows.exists() and any(path.is_file() for path in workflows.rglob("*")):
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

    docs_index = root / "docs/README.mdx"
    if docs_index.is_file():
        text = _read(docs_index)
        for family in ("Scout reports", "Piece specifications", "Rulings", "Removed documentation"):
            if family not in text:
                failures.append(f"docs/README.mdx lacks classification: {family}")

    for path in sorted((*root.rglob("*.md"), *root.rglob("*.mdx"))):
        rel = path.relative_to(root).as_posix()
        for target in LINK_RE.findall(_read(path)):
            normalized = target.replace("\\", "/").lower()
            if "docs/reviews/" in normalized or "docs/verifications/" in normalized:
                failures.append(f"{rel}: link targets a removed transcript: {target}")

    for rel in REQUIRED:
        path = root / rel
        if not path.is_file():
            continue
        text = _read(path)
        for target in LINK_RE.findall(text):
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            target = target.split("#", 1)[0]
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
    print(f"documentation check: PASS ({len(REQUIRED)} required documents)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
