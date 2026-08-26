# PROVENANCE — competitor source `wiki-gg` (twopointcampus.wiki.gg)

Repo-only provenance per AGENTS rule 3 / [DR-2026-08-15 D2]. R6 input
(`docs/specs/piece-02-relinking.mdx` §R6). **No `model.jsonl` exists for
this source: the access ladder exhausted every rung without one readable
byte.** Absent inputs route as FLOOR-UNMET for this sourceId per §R6 —
the floor itself is still met by `fandom` + `steam-guides` + reserves.

## Source identity

| Field | Value |
|---|---|
| sourceId | `wiki-gg` |
| Source | twopointcampus.wiki.gg (independent wiki.gg farm instance) |
| Access rung reached | **WALL — all rungs** |

## Ladder record (one attempt per rung, never retried into)

| Rung | Attempt | Outcome |
|---|---|---|
| F1 plain curl | scout-002, 2026-08-24 | HTTP **401** on default UA (`competitor-research.md` §1 C2) |
| F2 AI-crawler UA | scout-002, 2026-08-24 | HTTP **401** with `OAI-SearchBot` UA (same ledger row) |
| F3 MediaWiki api.php | this session 2026-08-25 | `GET /api.php?action=query&meta=siteinfo` → HTTP **401** (5,777 B body, not JSON) |
| F4 web-browse headless | this session 2026-08-25 | stealth Chrome `page.goto https://twopointcampus.wiki.gg/` → `net::ERR_INVALID_AUTH_CREDENTIALS` — the edge answers even a real-browser fingerprint at the auth layer |
| F5 give-up+ledger | this session | THIS FILE is that ledger row |

The wall is an HTTP-auth-layer gate (401 family across curl and Chrome),
not a JS-render gap — a different client does not change the answer.

**One question it would have answered:** whether the independent
wiki.gg instance models the course→room→item requirement chains the same
way Fandom does — i.e. which of Fandom's edges are farm-conventions and
which are community-consensus (delta analysis per
`competitor-research.md` §1 C2's stated role).

## Unblock path (owner-directed corpus acquisition)

An owner browser session exporting the wiki.gg entity/category trees into
this directory would feed the identical APPLY step; no pipeline change
needed. Until then this source stays a wall row in
`extracted/relinks/competitor_applied.jsonl` (R6 ledger schema:
`{sourceId:"wiki-gg", rung:"wall", wall:{httpStatus:401,
oneQuestionItWouldHaveAnswered:"…above…"}, buildId:20226581}`).

No other files exist in this directory.
