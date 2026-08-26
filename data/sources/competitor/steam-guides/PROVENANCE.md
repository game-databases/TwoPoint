# PROVENANCE — competitor source `steam-guides` (Steam Community, appid 1649080)

Repo-only provenance per AGENTS rule 3 / [DR-2026-08-15 D2]. R6 input
(`docs/specs/piece-02-relinking.mdx` §R6).

## Source identity

| Field | Value |
|---|---|
| sourceId | `steam-guides` |
| Source | Steam Community guides hub for Two Point Campus |
| Base URL | `steamcommunity.com/app/1649080/guides/`; guides at `steamcommunity.com/sharedfiles/filedetails/?id=<gid>` |
| Access rung reached | **F2 — AI-crawler UA** (mission ladder) |
| Fetch window | 2026-08-25 (ISO stamps in `../_fetch-log.txt`) |
| Method | `curl -A "Claude-User"`, ≥2 s pacing, one ladder attempt per rung |
| Requests this session | 1 list + 4 guide bodies (+2s gaps) — all HTTP 200 |

## Ladder record

| Rung | Outcome |
|---|---|
| F1 plain curl | PARTIAL — scout-002 2026-08-24: bare `/guides/` returns HTTP 200 shell with **0 guide links** server-rendered (`competitor-research.md` §1 C3). Treated as no-extraction; not the success rung. |
| F2 AI-crawler UA | **SUCCESS** — `Claude-User` UA against the *paginated browse shape* `?browsefilter=trend&numperpage=30` yields real listing markup: 9 guide rows with ids/titles/descriptions. The prior pass's empty result was the URL shape, not a wall. |
| F3 api.php | n/a — not a MediaWiki host. |
| F4 web-browse | not needed (stop at first success). |
| F5 give-up | not reached. |

## Files (this dir)

| File | What |
|---|---|
| `_f2-list-claudeuser.html` | raw F2 listing pull (81 KB; trend filter, 30/page) |
| `_f2-guide-index.tsv` | extracted index: publishedfileid → title → short description (9 rows) |
| `guide-<gid>.html` ×4 | raw guide bodies |
| `guide-<gid>.txt` ×4 | readable text extraction of the same bodies (section titles preserved) |
| `model.jsonl` | R6 relationship rows mined from those texts (34 rows) |

Guides pulled (trend top-9 ranked by model value):

| gid | title | why pulled |
|---|---|---|
| 2852555025 | Tips and tricks... | mechanics chains: room capacity, teacher ratios, effect stacking/scope, trait lists, skill % effects |
| 2875066931 | Kudos, Loans and R&D "TwoPointHospital-Style" | economy edges: kudosh/loans/research interplay |
| 2853410023 | All Levels (All DLCs) | campus ladder base 1–12 + DLC rosters incl. Medical School DLC campuses; per-campus objective→entity goals |
| 2849835291 | How to be wealthy? Quick money asap | money-economy edges |

Remaining 5 listed guides are achievement/localization/walkthrough
focused (ids in `_f2-guide-index.tsv`) — low relationship-model density,
left unpulled under polite-volume discipline.

## Caveats for mapping

- Guide claims are player-derived numbers (capacity 8, bed:5 students,
  +10%/rank course skill). Treat as `cardinalityClaim` hints to verify
  against client data — never as measured truth.
- "Medical School DLC" campuses appear here although the DLC is NOT in
  our install (catalog-KNOWN only, `data-acquisition.md` §S2) — useful
  advance notice of `dlc-hospital-*` bundle content.

buildId context stamp: 20226581.
