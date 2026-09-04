# Two Point Campus — relation matrix status

**buildId:** `20226581`  
**Nodes:** config, item, room, course, staff, student-type, unlockable,
metagame-node, campus-level, scene  
**Matrix:** 100 ordered cells — 24 modeled, 3 partial, 73 missing

Legend: `M` modeled · `P` partial · `—` missing.

## Complete ordered-pair status grid

| from \ to | config | item | room | course | staff | student | unlock | meta | campus | scene |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| config | M | M | M | M | M | — | M | M | — | — |
| item | M | M | — | — | — | — | — | — | — | — |
| room | M | M | — | — | — | — | M | — | — | — |
| course | M | M | — | M | — | — | — | — | — | — |
| staff | M | — | — | — | — | — | M | — | — | — |
| student-type | M | — | — | — | — | — | — | — | — | — |
| unlockable | M | M | — | — | — | — | M | — | P | — |
| metagame-node | M | M | — | P | — | — | — | — | — | — |
| campus-level | M | — | — | — | — | — | — | P | — | — |
| scene | — | — | — | — | — | — | — | — | — | — |

Every `—` cell is represented in the machine matrix with
`mechanism: inferred`, `status: missing`, and its probe/unblock class. It is
not silently omitted.

## Modeled edge families

| From | To | Mechanism | Edges | Source entities |
|---|---|---|---:|---:|
| config | config | hard PPtr | 9,943 | 4,428 |
| config | item | hard PPtr | 3,118 | 763 |
| config | room | hard PPtr | 532 | 493 |
| config | course | hard PPtr | 116 | 35 |
| config | staff | hard PPtr | 61 | 60 |
| config | unlockable | hard PPtr | 64 | 8 |
| config | metagame-node | hard PPtr | 35 | 5 |
| item | config | hard PPtr | 8,281 | 1,788 |
| item | item | hard PPtr | 155 | 129 |
| room | config | hard PPtr | 570 | 112 |
| room | item | hard PPtr | 132 | 59 |
| room | unlockable | hard PPtr | 6 | 4 |
| course | config | hard PPtr | 652 | 53 |
| course | item | hard PPtr | 16 | 16 |
| course | course | hard PPtr | 46 | 28 |
| staff | config | hard PPtr | 72 | 3 |
| staff | unlockable | hard PPtr | 3 | 3 |
| student-type | config | hard PPtr | 277 | 27 |
| unlockable | config | hard PPtr | 34 | 24 |
| unlockable | item | hard PPtr | 110 | 38 |
| unlockable | unlockable | hard PPtr | 139 | 77 |
| metagame-node | config | hard PPtr | 205 | 205 |
| metagame-node | item | hard PPtr | 3 | 3 |
| campus-level | config | hard AssetGUID→catalog→container→pathId | 13 | 13 |

## Partial cells

| From | To | Current evidence | Unblock |
|---|---|---|---|
| unlockable | campus-level | level-shaped fields found without a stable resolved carrier | repeat cross-file/GUID probe after map identity repair |
| metagame-node | course | course PPtr carriers exist but some targets remain outside the emitted identity universe | resolve scene/prefab targets and reclassify |
| campus-level | metagame-node | campus GUID resolves to `Config_Metagame`, currently emitted as `config` | settle one authoritative kind mapping; never dual-emit guessed identities |

## Locale relation ownership

Stage 9 `locale-proof` is the sole writer of
`relinks/locale_availability.jsonl`. Stage 6 writes:

- `i2_term_registry.jsonl`: 15,675 rows;
- `entity_locale.jsonl`: 10,964 entity-locale joins;
- `locale_term_entity.jsonl`: reverse index;
- `locale_join_report.json`.

The former statement that stage 5 owned locale availability is retired.

## Current ledgers

| Ledger | Rows / state | Meaning |
|---|---:|---|
| unresolved PPtrs | 2,391 | same/cross-file targets outside the current emitted identity universe |
| dangling GUIDs | 1,137 | unresolved-open Addressables GUIDs |
| locale registry misses | 5 | term IDs absent from the canonical registry |
| competitor application | 0 applied sources | two models harvested; third-source and application floor open |
| map placement joins | review failure | identity propagation breaks room/plot reverse joins |

## UI-link and competitor duties

The emitted UI-link coverage artifact maps observed game UI relationships to
schema/join families. Any uncovered UI link is a named gap.

Competitor relationship models do not count merely because their files exist.
Three independent models must each produce a measured application record:
delta, strengthened probe, or zero-delta comparison. Current count is zero.

## Completion verdict

The matrix is complete as an inventory but not exhausted as a relation model.
Map identity repair, competitor application, unresolved-target re-probes, and a
fresh real-corpus run are required before the data gate can close.

The detailed pair JSONL files and machine `matrix.json` remain the authoritative
row-level artifacts. This document is the human status view and is regenerated
after relation changes.

<!-- END OF extracted/RELATIONS.md -->
