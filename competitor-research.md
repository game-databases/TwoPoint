# Two Point Campus — Competitor Research

Purpose under the relinking bare minimum ([DR-2026-08-17-relink] bar #3):
≥3 independent wiki/database sources analyzed for their entity-relationship
model, and the model **APPLIED** to our relink layer — added joins, derived
edges, missing-relation flags landing in `extracted/relinks/` +
`RELATIONS.md`. A source list alone does not meet the bar.

**Status: NOT-YET-APPLIED.** This file fixes targets, records access
walls, and schedules the analysis + fallback ladder. Nothing below has
been applied to any dataset; the applied delta is a later-piece deliverable
consumed by the pipeline's relink stages.

## 0. Reference-site bar (site-side, separate from relinking)

The site design bar and its measured defects live in `spec.md` context +
[`_foundation/design-standard.md`](../_foundation/design-standard.md);
scout §7's reference-site findings (Enka hover-joins, NWG URL state,
crawlable link graph, honest empty states, owned map module) carry into
the site build, not this file.

## 1. Target list + access state (probed by scout-002, 2026-08-24)

Every candidate was curl-probed once (+1 crawler-UA retry where walled);
per AGENTS rule 10 no wall was retried into. **All walled or empty — that
is the finding, not a blocker.**

| # | Source | Access state (measured) | Relationship model it carries | Role |
|---|---|---|---|---|
| C1 | Two Point Campus Wiki — `twopointcampus.fandom.com` | HTTP **403** bot wall (5.4 KiB challenge); retry with `Claude-User` UA → **402** | Primary community taxonomy: course↔room↔item↔staff/student cross-links, DLC coverage | Floor source 1 |
| C2 | `twopointcampus.wiki.gg` | HTTP **401** on default + `OAI-SearchBot` UAs | Independent second instance of the same model; deltas vs C1 expose load-bearing edges | Floor source 2 |
| C3 | Steam Community guides — `steamcommunity.com/app/1649080/guides/` | **HTTP 200 alive** (60 KiB shell) but guide list not server-rendered in that URL shape (0 guide links in HTML) | Player-authored chains: course→room→item needs, staff traits→course speed — derived-edge candidates our layer must reproduce from client data | Floor source 3 |
| C4 | `twopointcampus.wiki.fextralife.com` | DNS **NXDOMAIN** — no dedicated Fextralife TPC wiki exists | (absence finding) | — |
| C5 | IGN wikis — `ign.com/wikis/two-point-campus/` | **403**, body truncated at timeout | Publisher-grade entity lists (courses, rooms, items) | Reserve |
| C6 | `game8.co/games/Two-Point-Campus` | HTTP **202**, 0 B body (challenge page) | Guide-style relationship chains | Reserve |
| C7 | Neoseeker — `neoseeker.com/two-point-campus/` | **403** wall | Entity tables + community Q&A | Reserve |

## 2. Scheduled analysis plan (ABP browser passes)

Per AGENTS rule 10 every browser run goes through the ABP `browser` MCP
server; a bot check or login wall is a finding, never retried into. The
scout's walls were **curl** results — an ABP pass is the planned unlock,
not a retry of a forbidden loop; each source still gets ONE attempt,
then its wall is re-recorded as a finding.

For each of C1, C2, C3 (+ reserves only if needed):

1. **Enumerate** the entity-kind inventory and category tree.
2. **Extract the relationship model** per kind: which cross-links exist
   (infoboxes, "used in", requirement tables), their cardinality, and
   their join keys as the community names them.
3. **Diff against our client-derived schema**: edges the community
   surfaces that our extraction has not yet derived become work items;
   edges we have that they lack become differentiators.
4. **Apply** accepted findings to `extracted/relinks/*.jsonl` +
   `RELATIONS.md` with mechanism tags (`inferred`, method =
   `competitor-model:<source-id>`) — repo-only provenance; source
   identity never reaches user surfaces (AGENTS rule 3).

## 3. Fallback ladder (pre-named before ABP is proven — verifyB 5.2)

Bar #3 is unconditional; walls are access facts, not waivers. If the ABP
passes cannot read C1–C3, each rung below fires in order. Every probe
stays one-attempt-per-rung-per-source (rule 10); every result is
recorded here as data.

| Rung | Action | Trigger | Notes / risk |
|---|---|---|---|
| F1 | **ABP-browser passes on C1–C3** (§2 plan) | scheduled at competitor-research phase start | Primary plan. Single attempt each; walls → findings rows. |
| F2 | **Web Archive snapshots** of C1/C2 entity + category pages via the CDX API (`web.archive.org/cdx/search/cdx?url=twopointcampus.fandom.com/wiki/*&output=json&filter=statuscode:200`), then snapshot fetches | any source unreadable after its F1 attempt | Archive.org endpoints are typically not challenge-walled to curl. Content-complete title (last patch 2025-12-19) means snapshot lag ≈ zero content cost; staleness stamped per row regardless. |
| F3 | **Steam Community guides corpus via alternate fetch shapes** — paginated browse URLs (`/guides/?browsefilter=mostrecent&numperpage=…`) and individual guide pages fetched by curl with a browser UA; individual-guide URLs are UNPROBED (only the list shape was found JS-driven) | F2 yields <3 usable sources or thin relationship coverage | Each new URL shape = one attempt. INFERRED until probed; recorded either way. |
| F4 | **Community mining outside wikis** — r/TwoPointCampus via old.reddit JSON endpoints; official Two Point Studios site/news posts (course/room showcases) | F3 insufficient | Read-only public surfaces; one attempt per endpoint class. |
| F5 | **Reserves C5–C7 through the same ladder** (ABP → archive → direct fetch) | floor still short of 3 applied sources | Last community instances before the ledger state. |

### Terminal state if the floor stays unmet

If fewer than three independent sources end up APPLIED after F1–F5:
the gap is **ledgered, never waived** — a residue-ledger entry in
`extracted/PROOF.md` naming exactly which bars are unmet, plus the
concrete unblock path (owner-directed corpus acquisition: e.g. an owner
browser session exporting the fandom/wiki.gg entity trees into
`data/sources/`, which then feed the same APPLY step). Bar #3 then reads
as partially met with the ledger pointing at its own exit — the doctrine
state for "missing pairs are ledgered with the concrete unblock".

## 4. What the analysis must produce (acceptance of this file's plan)

- ≥3 sources with an extracted relationship model, each stored under
  `data/sources/` with provenance (repo-only).
- An applied-delta record: joins added / edges derived / flags raised,
  each traceable to `competitor-model:<source-id>` method strings in
  RELATIONS.md.
- Walls and dead ends recorded as data rows here, never silently dropped.

END OF competitor-research.md
