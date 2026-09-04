# Two Point Campus — current tools plan

The logic, map, relation, locale, and search stages now provide measured
evidence for tool selection. This replaces the pre-extraction skeleton.

Scores use 1–5 where higher demand, readiness, or defensibility is better and
higher cost is more expensive.

## Prioritized tools

| Priority | Tool | Player job | Demand | Readiness | Defensibility | Cost | Gate |
|---:|---|---|---:|---:|---:|---:|---|
| 1 | campus layout planner | place plots, rooms, and items; validate a campus; share a layout | 5 | 2 | 5 | 5 | map identity and reverse joins |
| 2 | course prerequisite explorer | see course unlocks, modules, prerequisites, rooms, and related items | 5 | 4 | 4 | 3 | relation exhaustion |
| 3 | Kudosh economy planner | compare 2,143 measured source/sink rows and sequence unlock spending | 4 | 4 | 4 | 3 | public entity contracts |
| 4 | research and unlock tree | traverse research costs, metagame nodes, courses, rooms, and unlockables | 4 | 3 | 4 | 3 | partial metagame↔course relation |
| 5 | grading calculator | inspect assessment scoring and grade cutoffs by course | 4 | 3 | 5 | 3 | XP→score native normalization |
| 6 | needs and decay simulator | explain staff/student decay and interaction effects | 4 | 3 | 5 | 4 | student core-11 carrier |
| 7 | localized database search | find entities and game strings across all 13 client locales | 4 | 4 | 3 | 2 | route and slug manifests |
| 8 | patch difference explorer | compare entities, logic, relations, and media between builds | 4 | 1 | 5 | 4 | a second extracted build |

## Measured backing

- 69 courses, 319 modules, 471 prerequisite rows, and 50 course-unlock
  edges;
- 28 money-taxonomy values, 2,143 Kudosh ledger rows, and 209 research
  costs;
- nine grade bands, 75 term pass-grade rows, and 28 assessment-scoring rows;
- 30 staff-decay rows, 13 student-decay rows, and 630 interactions;
- 13 locale search shards and a client-derived term registry;
- campus scenarios, plots, rooms, placements, layers, and validators exist,
  but the latest review proves their identity joins are not yet safe.

These counts are input evidence, not public marketing copy. Public tools use
the regenerated current corpus and link every input/output entity both ways.

## Product rules

- The layout planner is the flagship creator, but it cannot ship on broken
  placement identity.
- Inputs respond as typed; tools do not require a submit button.
- Every meaningful state is shareable through a stable URL, except transient
  map camera/filter/search state.
- Tools are server-rendered around their initial answer and keep crawlable
  entity links.
- Mobile supports calculators, search, and textual database pages. The
  interactive map and map-backed layout canvas are desktop/TV surfaces.
- Saved layouts, favorites, comments, corrections, ratings, and screenshots
  use the local auth/UGC adapter until a public origin enables real providers.
- No tool invents a missing game value. Unknown native formulas remain
  visibly unavailable and ledgered.

## Research follow-up

Before Phase D freezes tool scope:

1. finish the three-source competitor model application;
2. mine recurring player questions from the acquired guide corpus;
3. rerun the score table against current search demand and the repaired data;
4. identify which tools become launch scope and which follow immediately;
5. add entity↔tool, guide↔tool, and news↔tool reverse indexes to the data
   contract.

<!-- END OF tools-plan.md -->
