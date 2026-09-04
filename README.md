# Two Point Campus database pack

This repository contains the extraction, normalization, relation, map-geometry,
logic, localization, media, contract, and search pipeline for **Two Point
Campus** (Steam appid `1649080`).

Current measured client scope:

- buildId `20226581`
- game version `10.3.169253+2024-12-06.1241`
- Unity `2020.3.47f1`, IL2CPP metadata version `27`
- 176 readable bundles: 158 base, 10 Space Academy, 8 School Spirits
- 13 client text locales plus one non-locale base overlay

## Current stage

The pack is in **Phase C: data hardening and proof closure**. The thirteen-stage
pipeline exists and has produced real-corpus outputs, but the global
data-before-frontend gate is still closed.

The live C2 blocker families are the table in
[`PROGRESS.mdx`](PROGRESS.mdx): C2-MAP, C2-MEDIA, C2-REL, C2-PROOF, C2-GIT,
and C2-STAGE-REV. That table is the canonical list; this README does not keep a
shorter competing count.

There is deliberately **no public site implementation in this branch**. A
generic analytics-only shell from an earlier branch state was removed because
it preceded data completion and claimed product surfaces that did not exist.
The complete site contract remains documented in
[`docs/site-plan.mdx`](docs/site-plan.mdx).

## Canonical documents

| Document | Authority |
|---|---|
| [`spec.md`](spec.md) | current product, data, locale, map, and tool contract |
| [`PROGRESS.mdx`](PROGRESS.mdx) | concise live phase board |
| [`QUESTION-QUEUE.md`](QUESTION-QUEUE.md) | owner-only decisions |
| [`data-acquisition.md`](data-acquisition.md) | source, corpus, media, and publication policy |
| [`data/sources/MANIFEST.md`](data/sources/MANIFEST.md) | factual acquisition register |
| [`extracted/EXTRACTION-LOG.md`](extracted/EXTRACTION-LOG.md) | append-only tool and run evidence |
| [`extracted/PROOF.md`](extracted/PROOF.md) | measured coverage and residue evidence |
| [`extracted/VALIDATION-REPORT.md`](extracted/VALIDATION-REPORT.md) | current verification verdict |
| [`extracted/logic/LOGIC.md`](extracted/logic/LOGIC.md) | generated logic-layer evidence |
| [`missingdata.md`](missingdata.md) | one ledger of unresolved data and proof gaps |
| [`docs/current-stage.mdx`](docs/current-stage.mdx) | implementation-to-plan reconciliation |
| [`docs/architecture.mdx`](docs/architecture.mdx) | ownership and dependency boundaries |
| [`docs/design-direction.mdx`](docs/design-direction.mdx) | source-only visual review and future design bar |
| [`docs/reviewer-handoff.mdx`](docs/reviewer-handoff.mdx) | completed PR-review record and data-host verification runbook |
| [`docs/README.mdx`](docs/README.mdx) | exhaustive documentation classification |

Dated scout reports, piece specifications, and arbiter rulings remain evidence
or executable contracts. Superseded agent review transcripts and duplicate
verification reports were consolidated into
[`docs/review-history.mdx`](docs/review-history.mdx) and removed.

## Pipeline

```bash
python run_all.py --list
python run_all.py "A:\\SteamLibrary\\steamapps\\common\\Two Point Campus"
python -m pytest tests -q
python tools/check_documentation.py
```

`run_all.py` owns this order:

1. `verify-client`
2. `decompile`
3. `harvest-catalog`
4. `harvest-bundles`
5. `localisation`
6. `emit-stub-datasets`
7. `relink`
8. `maps`
9. `logic`
10. `locale-proof`
11. `check-contracts`
12. `media`
13. `search-corpus`

The source checkout used on `NE8K` must be hash-identical to the reviewed
branch before any result is called reproducible. The host cannot authenticate
Git operations initiated through SSH; relay the committed scripts and verify
their hashes as described in the parent repository's extraction-host standard.

## Product boundary

The eventual site is one independently deployable Two Point Campus database
with origin `TBD`. It is not hosted by, imported into, or coupled to the
separate Steam intelligence product. Production origin and trademark clearance
remain owner operations.

All names, descriptions, stats, localized strings, entity imagery, and map
imagery come from the game or its first-party services. External community
material is repo-only research for relation modeling and authored guides; its
identity never appears on player-facing surfaces.

<!-- END OF README.md -->
