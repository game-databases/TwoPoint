# Two Point Campus — competitor relationship research

## Purpose and current verdict

The relation doctrine requires at least three independent wiki/database models
to be analyzed **and applied** to the client-derived relation layer.

Current state:

- readable and harvested models: **2**
- independently applied models: **0** in the latest tracked relation run
- recorded access-wall sources: **1**
- floor: **not met**

This file owns that gap. It does not describe external content as the game's
fact plane, and no source identity, URL, license tag, or provenance chain may
reach a public page, JSON API, `llms.txt`, search result, or metadata surface.

## Acquired models

| ID | Corpus | Harvest | Model rows | Useful relationship families | Application |
|---|---|---:|---:|---|---|
| C1 | community wiki export | category tree, 91 page bodies, item/category slices | 383 | course↔room↔item, campus/course taxonomy, staff and student categories | pending |
| C2 | Steam guide corpus | nine-guide index and four guide bodies | 34 | course/room needs, money, Kudosh, research, campus progression | pending |
| C3 | second independent wiki instance | access wall recorded after permitted attempts | 0 | expected independent taxonomy check | unavailable |

Raw files and acquisition facts live under `data/sources/competitor/`; the
append-only source manifest is the inventory. Their identity remains repo-only.

## Why the current stage is still incomplete

Harvesting a model is not application. The relink stage must produce a durable
`competitor_applied` record and an actual schema/relation delta for each source.
A model that adds no edge may still count only when the run records the
independent comparison, the zero delta, and why the client model already covers
it.

The latest tracked relink run (`EXTRACTION-LOG.md`, `2026-08-25T23:49:25Z`)
reports `sourcesApplied=0`. Earlier log rows that printed `sourcesApplied=2`
are historical and are not rewritten. Current documents use the latest row.
Until `sourcesApplied` is 3, the matrix may be client-derived and useful but
does not satisfy the competitor floor.

## Application contract

For each usable source:

1. enumerate entity kinds and relationship families;
2. normalize community labels to existing internal kinds without replacing
   game identifiers;
3. compare the model to hard, logic, and inferred client edges;
4. emit one of:
   - a new or strengthened relation;
   - a new missing-pair probe;
   - a measured zero-delta result;
5. record the method in repo-only evidence;
6. regenerate `RELATIONS.md`, the application ledger, and PROOF counts.

A community relationship may direct where to look; any game fact rendered to a
player still comes from the client or first-party services.

## Third-source acquisition

The next C2 relation pass must make one bounded attempt through the remaining
ladder:

1. archive snapshots for the second wiki;
2. another independent guide/database corpus;
3. an owner-exported category/entity tree if public access remains blocked.

A bot/login wall is a finding, not an invitation to retry around it. If the
third source remains unreachable, PROOF must say exactly which source classes
were attempted, which relation question remained unanswered, and what concrete
owner-provided corpus would close it. That leaves the pack honestly
incomplete; it does not waive the floor.

## Completion criteria

- three independent model inventories;
- three application records;
- every accepted relationship delta present in emitted relation artifacts;
- zero external-source names on user-facing surfaces;
- relation and proof documents regenerated from the same run.

<!-- END OF competitor-research.md -->
