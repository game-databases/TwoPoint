# PROVENANCE — competitor source `fandom` (Two Point Campus Wiki)

Repo-only provenance per AGENTS rule 3 / [DR-2026-08-15 D2]. This file is
an R6 input (`docs/specs/piece-02-relinking.mdx` §R6); nothing here may
reach a user-facing surface.

## Source identity

| Field | Value |
|---|---|
| sourceId | `fandom` |
| Source | Two Point Campus Wiki — Fandom farm instance |
| Canonical host measured | `two-point-campus.fandom.com` (`twopointcampus.fandom.com` 301→ this) |
| Platform | MediaWiki 1.43.9 / PHP 8.3.33 (measured from `siteinfo.json`) |
| Access rung reached | **F3 — MediaWiki api.php** (mission ladder) |
| Fetch window | 2026-08-25 (UTC+local; see `../_fetch-log.txt` for ISO stamps) |
| Method | `curl` GET against `api.php`, plain curl UA, ≥2 s pacing between every request, one attempt per rung |
| Requests fired this session | 24 to api.php (+2 ladder probes: 301 redirect follow on F3 probe; prior-pass walls cited below) |
| HTTP outcomes | all logged pulls **200**; zero bot-wall hits |

## Ladder record

| Rung | Outcome |
|---|---|
| F1 plain curl | WALL — ledgered by scout-002 2026-08-24: HTML 403 challenge (5.4 KiB), `competitor-research.md` §1 C1. Not re-fired this session (no retries into walls). |
| F2 AI-crawler UA | WALL — same pass: `Claude-User` UA → HTTP 402. Not re-fired. |
| F3 MediaWiki api.php | **SUCCESS** — api.php answers 200 JSON without challenge (301 domain normalization only). All data below pulled through it. |
| F4 web-browse | not needed (stop at first success). |
| F5 give-up | not reached. |

## Files (this dir)

| File | What | Rows/size |
|---|---|---|
| `siteinfo.json` | site identity + namespaces probe | 6,322 B |
| `allcategories-p1.json` | full category list with page counts | 282 categories, single page (no continuation) |
| `catmembers-<Cat>.json` ×16 | members of structural categories (Courses, Rooms, Items p1+p2, room classes, Campuses, Staff kinds, DLC cats, Increases_Happiness exemplar effect-cat, Kudosh_Bundle) | Items: 500+337 = 837 pages (complete vs category size 837) |
| `catmembers-InfoboxTemplates.json` | infobox template inventory | Template:Infobox Room / Item / DLC visible among farm boilerplate |
| `wikitext-A…F.json` | raw wikitext of 91 pages: 3 infobox templates, 20 rooms, 15 courses, 24 items, campuses/clubs/bundles/meta (16), hub pages (Assignments→redirect, Events 22.9 kB, Research 81.2 kB, Traits, both Course/Item infobox templates) | batched ≤50 titles/request |
| `model.jsonl` | R6 relationship rows (community naming) | 383 rows |

## model.jsonl generation

Mechanical extraction script `_gen_extra.py` + `_gen_fandom_model.py`
(kept beside the data): infobox field → row parsing over the captured
wikitext batches, plus hand-authored cross-cutting rows whose
`sourcePage` names the exact captured file. Every row traces to bytes in
this directory. Community names are verbatim page/field names — NOT our
internal ids (mapping is stage R6's job).

## Known community-data defects observed (carry into mapping as flags)

- Typo categories exist: "Dornmitory", "Decreases Healthinesse",
  "Decreases Thirstt" — near-duplicate keys.
- Redirect stubs for hub concepts (Assignments → `Courses#Assignments`,
  Nature Club → `Clubs#Nature Club`, Cheeseball Bundle →
  `Amazon Prime Items#Cheeseball Bundle`).
- 797 pages tagged Stubs — coverage is uneven; absence of an edge here is
  weak evidence of absence in the game.

buildId context stamp: client buildid 20226581 (pack-wide provenance
stamp per `data-acquisition.md`).
