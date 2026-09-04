# Two Point Campus — extraction proof and residue ledger

**Evidence buildId:** `20226581`  
**Evidence review date:** 2026-09-04  
**Verdict:** **NOT YET COMPLETE — Phase C remains open**

This document proves what the tracked evidence supports and states every known
reason it cannot yet prove full deconstruction. It replaces the former
placeholder; it is not a completion certificate.

**Latest-run precedence:** `EXTRACTION-LOG.md` is append-only. Historical
failed or earlier runs stay in that log and are not rewritten. Current
documents cite the latest ledgered run for each stage. For competitor
application that is the `2026-08-25T23:49:25Z` relink row:
`sourcesRead=2`, `sourcesApplied=0`, `floorMet=False`.

## 1. Source inventory

| Source | Measured universe | Current evidence |
|---|---:|---|
| installed Unity bundles | 176 | 158 base, 10 Space Academy, 8 School Spirits |
| Addressables key slots | 56,660 | decoded catalog |
| Addressables entries | 66,129 | every entry referenced by at least one bucket membership |
| bucket memberships | 81,146 | multi-key entries explain membership > entry count |
| localization bundles | 14 | 13 locales + one base overlay |
| storefront language field | 11 | Japanese and Russian absent there; client bundles remain authority for 13 |
| localization registry rows | 15,675 | canonical term registry |
| media catalogue rows | 47,939 | class inventory, not complete decoded export proof |
| entity kinds | 9 | config, item, room, course, staff, student-type, unlockable, metagame-node, campus-level |
| relation nodes | 10 | nine entity kinds + scene |
| ordered relation cells | 100 | 24 modeled, 3 partial, 73 missing |
| competitor models harvested | 2 readable + 1 wall | application floor not met |
| uninstalled DLC references | 19 | Medical School/preorder references, no payload |

Measurement methods and historical stage runs remain append-only in
`EXTRACTION-LOG.md`.

## 2. Pipeline coverage

| Stage | Output class | Evidence status |
|---|---|---|
| verify-client | identity and bundle roster | measured |
| decompile | dummy assemblies and structural indexes | measured |
| harvest-catalog | Addressables keys, entries, coverage | measured |
| harvest-bundles | raw manifests, objects, media catalogue | measured with residue |
| localisation | 13 locale tables and base overlay | measured |
| emit-stub-datasets | nine canonical families and absence ledgers | measured |
| relink | bridges, pair files, matrix, locale and UI-link indexes | measured, not exhausted |
| maps | levels, plots, rooms, placements, layers, validators | emitted but review-blocked |
| logic | progression, economy, grading, needs/decay | measured with two gaps |
| locale-proof | availability, holes, fallback and coverage | emitted |
| check-contracts | 44-family validator layer | emitted; expected-red state requires stage follow-up |
| media | entity web images and cross-checks | partial policy coverage |
| search-corpus | locale shards, aliases, manifest | emitted; stage follow-up after relation/locale changes |

## 3. Logic evidence

- course progression: 69 courses, 319 modules, 471 prerequisites, 27
  prerequisite non-members, 50 unlock edges, 4 attrition rows;
- economy: 28 money-taxonomy values, 30 finance configurations, 2,143
  Kudosh rows, 209 research costs;
- grading: 9 bands, 75 term pass-grade rows, 28 assessment rows;
- needs/decay: 30 staff rows, 13 student rows, 11 explicit null-carrier rows,
  630 interactions.

Open native carriers:

1. XP accumulation to assessment-score normalization;
2. student core-11 decay values.

No number is supplied for either gap.

## 4. Relation evidence

The ordered matrix and edge counts are summarized in `RELATIONS.md`.

Named residue:

- 2,391 unresolved PPtr rows;
- 1,137 unresolved-open GUID rows;
- 5 locale registry misses;
- 73 missing ordered-pair cells and 3 partial cells;
- zero applied competitor-model sources in the latest tracked run.

A missing cell is not silently discarded: `RELATIONS.md` and emitted ledgers
name the current probe class. The matrix nevertheless does not satisfy
“exhausted” until those unblocks are re-run against the latest source and the
competitor floor is met.

## 5. Map evidence and blocker

The map stage emits real campus scenarios, plots, rooms, item placements,
landscape layers, and door validators. The latest independent review measured:

- 1,775 post-demotion placement identity collision groups;
- 20,263 of 22,878 room-family placements whose `owningRoomId` joined no
  emitted room;
- 140 of 4,082 landscape-layer rows whose plot key joined no plot.

Those findings invalidate a clean map-completeness claim and block the campus
planner. The implementation must repair identity propagation, assert
post-demotion uniqueness, and prove reverse joins or emit exact ledgers.

## 6. Media evidence and blocker

Catalogue universe:

| Class | Rows |
|---|---:|
| AnimationClip | 7,985 |
| AudioClip | 5,624 |
| Font | 24 |
| Mesh | 19,249 |
| Shader | 213 |
| Sprite | 6,789 |
| SpriteAtlas | 47 |
| Texture2D | 7,977 |
| VideoClip | 31 |

The media stage has evidence for 2,222 WebP files plus 29 PNG twins and seven
named entity-media absences. The tracked human report for that **entity-web
subset** is [`media/MEDIA-EXPORT.md`](media/MEDIA-EXPORT.md). Local binaries
and hash manifests are not on this GitHub checkout. The subset does not
reconcile the complete image universe or eligible model universe under the
current policy.

Audio/video, location models, and models over 200 MB are excluded. Every text,
image, and non-location model under 50 MB is mandatory. Animations require a
complete inventory plus an owner retain/offload/drop decision. The 50–200 MB
non-location model band needs per-model confirmation; the parent census says it
is very likely empty but does not prove that withheld containers contain none.

## 7. Corpus publication blocker

Historical ignore rules kept generated non-Markdown artifacts out of Git. The
current policy requires every file below approximately 95 MB and every commit
below approximately 1 GB to be pushed; larger artifacts remain complete and
staged locally.

The blanket ignore is removed, but this GitHub-only checkout cannot enumerate
bytes that were never published. Physical corpus publication is required
**before Phase D / before a green project data gate**, not before merging this
documentation reconciliation. Before that data gate can close, the
corpus-owning agent must:

- inventory every generated file on `NE8K` and the Mac;
- commit all eligible files;
- shard reconstructible over-cap streams;
- move intentionally local-large artifacts into the explicit staging path;
- add exact local paths, byte totals, hashes, and production-sync readiness
  here.

## 8. DLC scope

Base, Space Academy, and School Spirits are held. Medical School is not held
and is visible only through 19 catalog references. The product can ship with
an explicit base-plus-two-DLC coverage label, or the owner can acquire Medical
School. It cannot claim all-DLC coverage today.

The soundtrack is audio-only and outside the extraction target.

## 9. Completion verdict

The pipeline is substantial and reproducible in shape, but full completeness
is **not proven** because map identities, media coverage, competitor
application, source-hash parity, and corpus publication remain open.

Phase D starts only after the data-host verification runbook in
[`../docs/reviewer-handoff.mdx`](../docs/reviewer-handoff.mdx) is executed,
the open rows above are replaced with empirical results, and the final project
validation verdict is green.

<!-- END OF extracted/PROOF.md -->
