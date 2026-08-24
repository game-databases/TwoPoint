#!/usr/bin/env python3
"""Shared prepared-tree builder for the piece-1 suite (spec §5.2 hostless mode).

    python tests/build_fixture_tree.py --stage <id> [--out DIR] [--full]
                                      [--metadata-version N]

--stage <id>   one of: verify-client decompile harvest-catalog
               harvest-bundles localisation emit-stub-datasets
--out DIR      target directory (default: a fresh sibling of this file,
               `.fixture-trees/<id>`; created, never cleared)
--full         scale the aa listing to the real 158/10/8 corpus counts
               (default small: fast trees that trigger the DRIFT warning path)
--metadata-version N
               global-metadata.dat version word (default 27; pass >=38 to
               exercise the stage-0 dumper gate)

The tree contains synthetic fixture files ONLY — no real game bytes.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _fixturelib as fx  # noqa: E402


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
    out.mkdir(parents=True, exist_ok=True)
    fx.build_tree(out, args.stage, full_scale=args.full,
                  metadata_version=args.metadata_version)
    print(f"prepared[{args.stage}] -> {out}")
    print(f"  game root : {fx.game_root(out)}")
    print(f"  extracted : {out / 'extracted'} (point TPC_EXTRACTED_ROOT here)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
