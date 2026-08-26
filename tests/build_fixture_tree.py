#!/usr/bin/env python3
"""Shared prepared-tree builder for the piece-1 suite (spec §5.2 hostless mode).

    python tests/build_fixture_tree.py --stage <id> [--out DIR] [--full]
                                      [--metadata-version N]

--stage <id>   one of: verify-client decompile harvest-catalog
               harvest-bundles localisation emit-stub-datasets relink
               (`relink` = piece-02 §3 upstream set, Revision 7)
--out DIR      target directory (default: a fresh sibling of this file,
               `.fixture-trees/<id>`; created, never cleared)
--full         scale the aa listing to the real 158/10/8 corpus counts
               (default small: fast trees that trigger the DRIFT warning path)
--metadata-version N
               global-metadata.dat version word (default 27; pass >=38 to
               exercise the stage-0 dumper gate)

The tree contains synthetic fixture files ONLY — no real game bytes.

Recursion guard: hazardous directories (.pytest_tmp, .fixture-trees,
__pycache__, .git, .venv, node_modules) sitting DIRECTLY inside the target
root abort the build loudly; nested-deeper occurrences are excluded from
every walk/copy (see HAZARDOUS_DIR_NAMES below).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _fixturelib as fx  # noqa: E402


# --- recursion guard --------------------------------------------------------------
# Incident 2026-08: one orchestrator ran pytest with --basetemp=./.pytest_tmp
# INSIDE this pack; the fixture machinery then copied that directory into its
# own tree copies, nesting recursively until 1.6 GB+ filled C:. Every directory
# walk/copy in the fixture machinery must exclude these names, and one sitting
# DIRECTLY inside a declared source/out root aborts LOUDLY instead of being
# skipped silently (deeper-nested ones are excluded silently).

HAZARDOUS_DIR_NAMES = frozenset((
    ".pytest_tmp",     # pytest --basetemp payloads (the incident amplifier)
    ".fixture-trees",  # this builder's own default output root
    "__pycache__",
    ".git",
    ".venv",
    "node_modules",
))


class HazardousTreeError(RuntimeError):
    """A hazardous directory sits directly inside a declared source root."""


def is_hazardous(name_or_path) -> bool:
    """True when a directory entry carries a known runaway-copy name.

    Exact-name match only, so near-misses like `.github` stay legal.
    """
    return Path(name_or_path).name in HAZARDOUS_DIR_NAMES


def hazard_ignore(_directory, names):
    """`shutil.copytree(ignore=...)` adapter: skip hazardous entries silently."""
    return sorted(name for name in names if is_hazardous(name))


def check_source_root(root) -> Path:
    """Loud recursion guard for a build/copy SOURCE or OUT root.

    A hazardous directory DIRECTLY inside `root` raises HazardousTreeError
    naming the path. Deeper-nested occurrences are deliberately NOT seen
    here — the walk/copy legs exclude those via `hazard_ignore`.
    """
    root = Path(root)
    if not root.is_dir():
        return root
    hits = sorted(p.name for p in root.iterdir()
                  if p.is_dir() and is_hazardous(p.name))
    if hits:
        listed = ", ".join(str(root / name) for name in hits)
        raise HazardousTreeError(
            f"hazardous directories sit directly inside declared source root "
            f"{root}: {listed} — refusing to recurse/copy. Remove them first "
            f"(recursion guard; guarded names: "
            f"{', '.join(sorted(HAZARDOUS_DIR_NAMES))})")
    return root


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--stage", required=True, choices=fx.STAGE_ARTIFACTS)
    ap.add_argument("--out", default=None)
    ap.add_argument("--full", action="store_true",
                    help="scale aa to 158 bundles so live counts match expectedBundles")
    ap.add_argument("--metadata-version", type=int, default=27)
    args = ap.parse_args(argv)

    out = Path(args.out) if args.out else (
        Path(__file__).resolve().parent / ".fixture-trees" / args.stage)
    check_source_root(out)  # recursion guard: refuse contaminated roots loudly
    out.mkdir(parents=True, exist_ok=True)
    fx.build_tree(out, args.stage, full_scale=args.full,
                  metadata_version=args.metadata_version)
    print(f"prepared[{args.stage}] -> {out}")
    print(f"  game root : {fx.game_root(out)}")
    print(f"  extracted : {out / 'extracted'} (point TPC_EXTRACTED_ROOT here)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
