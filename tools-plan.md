# Two Point Campus — Tools Plan (skeleton, spec-freeze draft)

Per [`_foundation/site-sections.md`](../_foundation/site-sections.md)
§Tools [CORE] + the mandatory tool-discovery process. This is the
**spec-freeze draft**: it satisfies the D5 floor (`tools-plan.md` with
≥5 scored ideas at spec freeze) with candidates seeded from TPC's bundle
families and mechanics vocabulary. Every idea is **PROVISIONAL —
data-readiness unconfirmed until pipeline stages 2–5 land**; the whole
plan is re-run through the discovery process after Tier 1 (the
post-extraction mechanics pass).

## 1. Tool-discovery process checklist (re-run on every major patch)

| Step | State today |
|---|---|
| 1. Competitor inventory (gaming.tools / niche leaders / SERP hits for "[game] calculator\|planner\|map"; tools named in subreddit/Discord) | **PENDING** — scout §6 probed wiki-class sources only; no dedicated TPC tool site surfaced in those probes. One gaming.tools + SERP sweep scheduled with the post-Tier-1 re-run; Steam Community guides corpus (C3, alive) doubles as a pain-point source |
| 2. Mechanics enumeration from the extracted logic layer | **BLOCKED BY DATA** — runs after stages 1–5 produce `logic/` inputs; this file's candidate list is its seed |
| 3. Moat tools first (what full deconstruction enables that wikis cannot build) | applied to scoring below (defensibility axis) |
| 4. Pain-point mining (Reddit/Discord/Steam forums, autocomplete) | PENDING — folds into the same re-run; r/TwoPointCampus JSON endpoints are ladder F4 in `competitor-research.md` |
| 5. Scoring: traffic potential × build cost × data-readiness × defensibility | done provisionally below; re-scored when data-readiness resolves |
| 6. Ship → embed → iterate (MVP fast, URL states, interlinking rule) | standing rule for every shipped tool |

## 2. Candidate tools (≥5 floor met — 6 listed)

Scores are provisional H/M/L per axis; `data-readiness` names the exact
pipeline artifact that must exist before the tool can be built.

### T1 — Course requirement calculator (course → room → item)

What it answers: "to run course X at grade Y I need rooms R with items
I" — the game's core join rendered as an interactive chain.
Powers from: stage-5 canonical datasets joining `course`↔`room`↔`item`
(configs_* + items-* bundles).
Traffic **H** (the query every player has) · Build cost **M** ·
Data-readiness **H** (join edges are expected hard references) ·
Defensibility **M** (wikis list requirements as prose tables).

### T2 — Campus layout planner / builder (flagship candidate)

The new-world.guide build-creator analog: place plots/rooms on a campus
plot map, see capacity/course-slot effects live, shareable URL state.
Powers from: stage-3 scene/config dumps (plot geometry from
`config_level_databases` + `configs-levels-prefabs`) + later-piece derived
geometry; owned-map module doubles as its canvas ([DR-2026-08-20-design-bar]
map differentiator).
Traffic **H** · Build cost **H** · Data-readiness **M** (needs scene
transforms — the maps block's `unknown-P0` flip) · Defensibility **H**
(nobody builds planners over extracted plot coordinates).

### T3 — Student happiness simulator

"What breaks my students?" — needs/environment/grade model simulated
from config rows instead of anecdote.
Powers from: stage-5 config dumps + logic-layer derivation of the
happiness/need formulas (later piece reads decompiled services).
Traffic **M** · Build cost **H** · Data-readiness **L→M** (formula
extraction is real work past stage 5) · Defensibility **H** (pure
logic-layer moat).

### T4 — Kudosh economy planner

Income vs spend planner over the Kudosh currency: what unlocks what,
what earns how much, purchase ordering.
Powers from: stage-5 unlockable/economy datasets (`unlockables`,
`configs_*`; prices PROVISIONAL until confirmed in data).
Traffic **M** · Build cost **M** · Data-readiness **M** ·
Defensibility **M**.

### T5 — Research-tree explorer

Full course/research unlock tree with dependency highlighting and
patch-stamped diffs if updates ever resume.
Powers from: `metagame-node` datasets (`configs-metagame` family) +
relink edges.
Traffic **M** · Build cost **L** (once nodes exist) · Data-readiness
**M** · Defensibility **L–M** (wikis draw static trees).

### T6 — Staff-trait matcher

Which staff traits accelerate which courses; roster optimizer.
Powers from: staff/student-type datasets + trait-effect edges
(expected `logic` mechanism, not hard refs — flagged accordingly).
Traffic **M** · Build cost **M** · Data-readiness **L** (edges likely
derived from decompiled code) · Defensibility **M**.

## 3. Section mapping (mandatory sections covered by these tools)

Tools [CORE] — T1/T3/T4/T6 calculators+simulators, T2 flagship planner;
Database [CORE] — every tool links its input entities both ways
(aggressive-interlinking rule); News [CORE] — patch-diff route rides the
buildid-stamped rerun even though cadence is dormant; Guides [CORE] —
each tool gets a grounded explainer once its dataset lands.

## 4. Post-Tier-1 obligations

1. Re-run steps 1–5 above with real mechanic enumerations from
   `extracted/logic/`.
2. Confirm or kill each candidate on measured data-readiness; add the
   competitor-inventory table with traffic estimates.
3. Re-check the ≥5 evidence-linked quota against the surviving set.

END OF tools-plan.md
