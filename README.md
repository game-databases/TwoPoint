# Two Point Campus — pack README

Pack for **Two Point Campus** (Two Point Studios; Steam appid **1649080**;
client buildid **20226581**, `version.txt` `10.3.169253+2024-12-06.1241`;
Unity **2020.3.47f1**, IL2CPP, Windows x64). The client installs locally on
this host (NE8K) at `A:\SteamLibrary\steamapps\common\Two Point Campus`
(~4.37 GiB on disk; base depot 1649081 + two DLC packs — appid 1884560
"Space Academy" via depot 1884561, installed as `DLCs/space/`, and appid
1907450 "School Spirits" via depot 1907451, installed as `DLCs/ghost/`;
Steam's internal dir codenames don't track marketing names here).
Extraction runs here, in place — this machine holds the
data ([`_foundation/extraction-host.md](../_foundation/extraction-host.md)).

The product is the Two Point Campus database site — entity database,
owned interactive campus maps, course/campus planner tools, guides, news,
calculators, full client locale coverage — forward-designed as the first
entry of a Two Point game picker (per-game themes over a shared house
style). Binding standards: repo-root [`AGENTS.md`](../AGENTS.md),
[`_foundation/extraction-doctrine.md`](../_foundation/extraction-doctrine.md),
[`FRAMEWORK.md`](../FRAMEWORK.md), and the `_foundation/*` standards.

## Status

Bootstrap/prepare pass. Scout report verified (21/21 facts CONFIRMED;
coverage READY-FOR-DOCUMENTATOR): `docs/scout-report-001.mdx`,
verdicts in `docs/verifications/`. Convention docs + the piece-1
extraction-pipeline spec were authored by documentator-001 on 2026-08-24.
Nothing is extracted yet; `extracted/` does not exist until pipeline
piece 1 runs. Domain + tier are the one standing owner item
([QUESTION-QUEUE.md](QUESTION-QUEUE.md)); local-first build proceeds.

## Layout

| Path | What | State |
|---|---|---|
| `PROGRESS.mdx` | live progress page (orchestrator-maintained) | exists |
| `QUESTION-QUEUE.md` | owner questions (domain+tier) | exists |
| `README.md`, `spec.md`, `data-acquisition.md`, `competitor-research.md`, `toolchain.md`, `tools-plan.md` | pack conventions (AGENTS rule 4 set) | written 2026-08-24 |
| `docs/scout-report-001.mdx` | verified intelligence base | exists |
| `docs/verifications/verifyA-scout-001.mdx`, `verifyB-scout-001.mdx` | fact + coverage verdicts | exist |
| `docs/specs/piece-01-extraction-pipeline.mdx` | piece-1 spec (CodeWriter/TestWriter input) | written 2026-08-24 |
| `.agents/` | agent prompts + logs | exists |
| `Makefile` + `run_all.py` | single reproducible extraction entrypoint ([DR-2026-08-18-pipeline]) | piece 1 deliverable |
| `tools/` | pack-local pipeline scripts | piece 1 deliverable |
| `contracts/` | emitted dataset contracts | later pieces |
| `extracted/` (+ `EXTRACTION-LOG.md`, `VALIDATION-REPORT.md`, `RELATIONS.md`, `PROOF.md`) | extraction outputs | created by piece 1 |
| `design/`, `site/`, `data/sources/MANIFEST.md` | design tokens, site, source manifest | gated behind data completeness (AGENTS rule 8) |

## Entrypoint contract

One discoverable command reproduces the full extraction A→Z from a fresh
clone + the game folder: `./run_all <path-to-game>` / `make extract
GAME=...` (stages idempotent, individually runnable, `--list`
enumerates them). Tool + version + client buildid pins live in
`extracted/EXTRACTION-LOG.md`, which the entrypoint reads its defaults
from. The contract is [DR-2026-08-18-pipeline] +
[extraction-doctrine.md §Principle two](../_foundation/extraction-doctrine.md);
the concrete stages are specified in
[docs/specs/piece-01-extraction-pipeline.mdx](docs/specs/piece-01-extraction-pipeline.mdx).
Extraction runs on NE8K where the corpus is; only derived artifacts travel.

## Reading order for a new agent on this pack

1. Repo-root `AGENTS.md` (in full) + `_foundation/extraction-doctrine.md`.
2. This pack's `spec.md`, `data-acquisition.md`, `toolchain.md` (in full).
3. `docs/scout-report-001.mdx` + both `docs/verifications/` verdicts —
   the factual base; where this README, the spec, and the scout report
   disagree, the measured numbers win and the docs get corrected.
4. For pipeline work: `docs/specs/piece-01-extraction-pipeline.mdx`.

END OF README.md
