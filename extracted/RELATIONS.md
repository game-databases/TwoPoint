# Relations

- buildId: 20226581
- generated mechanically from relinks/matrix.json + ledgers by the `relink` stage (piece-02); reruns are byte-identical

## Node universe

- nodes: config, item, room, course, staff, student-type, unlockable, metagame-node, campus-level, scene
- arithmetic: 10 nodes -> 100 ordered cells = 90 off-diagonal + 10 diagonal

## Ordered-pair matrix (100 cells)

| src | dst | joinKey | mechanism | status | edges | srcEntities | pairFile |
|---|---|---|---|---|---|---|---|
| config | config | PPtr(m_FileID,m_PathID) | hard | modeled | 9943 | 4428 | config_config.jsonl |
| config | item | PPtr(m_FileID,m_PathID) | hard | modeled | 3118 | 763 | config_item.jsonl |
| config | room | PPtr(m_FileID,m_PathID) | hard | modeled | 532 | 493 | config_room.jsonl |
| config | course | PPtr(m_FileID,m_PathID) | hard | modeled | 116 | 35 | config_course.jsonl |
| config | staff | PPtr(m_FileID,m_PathID) | hard | modeled | 61 | 60 | config_staff.jsonl |
| config | student-type | none-established | inferred | missing | 0 | 0 |  |
| config | unlockable | PPtr(m_FileID,m_PathID) | hard | modeled | 64 | 8 | config_unlockable.jsonl |
| config | metagame-node | PPtr(m_FileID,m_PathID) | hard | modeled | 35 | 5 | config_metagame-node.jsonl |
| config | campus-level | none-established | inferred | missing | 0 | 0 |  |
| config | scene | none-established | inferred | missing | 0 | 0 |  |
| item | config | PPtr(m_FileID,m_PathID) | hard | modeled | 8281 | 1788 | item_config.jsonl |
| item | item | PPtr(m_FileID,m_PathID) | hard | modeled | 155 | 129 | item_item.jsonl |
| item | room | none-established | inferred | missing | 0 | 0 |  |
| item | course | none-established | inferred | missing | 0 | 0 |  |
| item | staff | none-established | inferred | missing | 0 | 0 |  |
| item | student-type | none-established | inferred | missing | 0 | 0 |  |
| item | unlockable | none-established | inferred | missing | 0 | 0 |  |
| item | metagame-node | none-established | inferred | missing | 0 | 0 |  |
| item | campus-level | none-established | inferred | missing | 0 | 0 |  |
| item | scene | none-established | inferred | missing | 0 | 0 |  |
| room | config | PPtr(m_FileID,m_PathID) | hard | modeled | 570 | 112 | room_config.jsonl |
| room | item | PPtr(m_FileID,m_PathID) | hard | modeled | 132 | 59 | room_item.jsonl |
| room | room | none-established | inferred | missing | 0 | 0 |  |
| room | course | none-established | inferred | missing | 0 | 0 |  |
| room | staff | none-established | inferred | missing | 0 | 0 |  |
| room | student-type | none-established | inferred | missing | 0 | 0 |  |
| room | unlockable | PPtr(m_FileID,m_PathID) | hard | modeled | 6 | 4 | room_unlockable.jsonl |
| room | metagame-node | none-established | inferred | missing | 0 | 0 |  |
| room | campus-level | none-established | inferred | missing | 0 | 0 |  |
| room | scene | none-established | inferred | missing | 0 | 0 |  |
| course | config | PPtr(m_FileID,m_PathID) | hard | modeled | 652 | 53 | course_config.jsonl |
| course | item | PPtr(m_FileID,m_PathID) | hard | modeled | 16 | 16 | course_item.jsonl |
| course | room | none-established | inferred | missing | 0 | 0 |  |
| course | course | PPtr(m_FileID,m_PathID) | hard | modeled | 46 | 28 | course_course.jsonl |
| course | staff | none-established | inferred | missing | 0 | 0 |  |
| course | student-type | none-established | inferred | missing | 0 | 0 |  |
| course | unlockable | none-established | inferred | missing | 0 | 0 |  |
| course | metagame-node | none-established | inferred | missing | 0 | 0 |  |
| course | campus-level | none-established | inferred | missing | 0 | 0 |  |
| course | scene | none-established | inferred | missing | 0 | 0 |  |
| staff | config | PPtr(m_FileID,m_PathID) | hard | modeled | 72 | 3 | staff_config.jsonl |
| staff | item | none-established | inferred | missing | 0 | 0 |  |
| staff | room | none-established | inferred | missing | 0 | 0 |  |
| staff | course | none-established | inferred | missing | 0 | 0 |  |
| staff | staff | none-established | inferred | missing | 0 | 0 |  |
| staff | student-type | none-established | inferred | missing | 0 | 0 |  |
| staff | unlockable | PPtr(m_FileID,m_PathID) | hard | modeled | 3 | 3 | staff_unlockable.jsonl |
| staff | metagame-node | none-established | inferred | missing | 0 | 0 |  |
| staff | campus-level | none-established | inferred | missing | 0 | 0 |  |
| staff | scene | none-established | inferred | missing | 0 | 0 |  |
| student-type | config | PPtr(m_FileID,m_PathID) | hard | modeled | 277 | 27 | student-type_config.jsonl |
| student-type | item | none-established | inferred | missing | 0 | 0 |  |
| student-type | room | none-established | inferred | missing | 0 | 0 |  |
| student-type | course | none-established | inferred | missing | 0 | 0 |  |
| student-type | staff | none-established | inferred | missing | 0 | 0 |  |
| student-type | student-type | none-established | inferred | missing | 0 | 0 |  |
| student-type | unlockable | none-established | inferred | missing | 0 | 0 |  |
| student-type | metagame-node | none-established | inferred | missing | 0 | 0 |  |
| student-type | campus-level | none-established | inferred | missing | 0 | 0 |  |
| student-type | scene | none-established | inferred | missing | 0 | 0 |  |
| unlockable | config | PPtr(m_FileID,m_PathID) | hard | modeled | 34 | 24 | unlockable_config.jsonl |
| unlockable | item | PPtr(m_FileID,m_PathID) | hard | modeled | 110 | 38 | unlockable_item.jsonl |
| unlockable | room | none-established | inferred | missing | 0 | 0 |  |
| unlockable | course | none-established | inferred | missing | 0 | 0 |  |
| unlockable | staff | none-established | inferred | missing | 0 | 0 |  |
| unlockable | student-type | none-established | inferred | missing | 0 | 0 |  |
| unlockable | unlockable | PPtr(m_FileID,m_PathID) | hard | modeled | 139 | 77 | unlockable_unlockable.jsonl |
| unlockable | metagame-node | none-established | inferred | missing | 0 | 0 |  |
| unlockable | campus-level | none-established | inferred | partial | 0 | 0 |  |
| unlockable | scene | none-established | inferred | missing | 0 | 0 |  |
| metagame-node | config | PPtr(m_FileID,m_PathID) | hard | modeled | 205 | 205 | metagame-node_config.jsonl |
| metagame-node | item | PPtr(m_FileID,m_PathID) | hard | modeled | 3 | 3 | metagame-node_item.jsonl |
| metagame-node | room | none-established | inferred | missing | 0 | 0 |  |
| metagame-node | course | none-established | inferred | partial | 0 | 0 |  |
| metagame-node | staff | none-established | inferred | missing | 0 | 0 |  |
| metagame-node | student-type | none-established | inferred | missing | 0 | 0 |  |
| metagame-node | unlockable | none-established | inferred | missing | 0 | 0 |  |
| metagame-node | metagame-node | none-established | inferred | missing | 0 | 0 |  |
| metagame-node | campus-level | none-established | inferred | missing | 0 | 0 |  |
| metagame-node | scene | none-established | inferred | missing | 0 | 0 |  |
| campus-level | config | AssetGUID(m_AssetGUID)->catalog.guid->container-address->pathId | hard | modeled | 13 | 13 | campus-level_config.jsonl |
| campus-level | item | none-established | inferred | missing | 0 | 0 |  |
| campus-level | room | none-established | inferred | missing | 0 | 0 |  |
| campus-level | course | none-established | inferred | missing | 0 | 0 |  |
| campus-level | staff | none-established | inferred | missing | 0 | 0 |  |
| campus-level | student-type | none-established | inferred | missing | 0 | 0 |  |
| campus-level | unlockable | none-established | inferred | missing | 0 | 0 |  |
| campus-level | metagame-node | none-established | inferred | partial | 0 | 0 |  |
| campus-level | campus-level | none-established | inferred | missing | 0 | 0 |  |
| campus-level | scene | none-established | inferred | missing | 0 | 0 |  |
| scene | config | none-established | inferred | missing | 0 | 0 |  |
| scene | item | none-established | inferred | missing | 0 | 0 |  |
| scene | room | none-established | inferred | missing | 0 | 0 |  |
| scene | course | none-established | inferred | missing | 0 | 0 |  |
| scene | staff | none-established | inferred | missing | 0 | 0 |  |
| scene | student-type | none-established | inferred | missing | 0 | 0 |  |
| scene | unlockable | none-established | inferred | missing | 0 | 0 |  |
| scene | metagame-node | none-established | inferred | missing | 0 | 0 |  |
| scene | campus-level | none-established | inferred | missing | 0 | 0 |  |
| scene | scene | none-established | inferred | missing | 0 | 0 |  |

## Locale-join ownership routing

- `relinks/locale_availability.jsonl` stays STAGE-5 SOLE PROPERTY (piece-02 §R4 pin; v1 procedure frozen at hardJoins: 0).
- The authoritative entity-granular locale relation is `relinks/entity_locale.jsonl` (10964 rows; mechanism `LocalisedString(_termID)->I2-termID->Term-key`, hard).
- Registry: `relinks/i2_term_registry.jsonl` (15675 rows, canonical-on-key); reverse index `relinks/locale_term_entity.jsonl`.

## Ledgers (gapped resolution is data, never silence)

- `_unresolved_pptrs.jsonl`: 2391 rows (cross-file misses, built-in externals, same-file non-entity targets; per-cell residue feeds matrix `evidence.unresolvedRefs`)
- `_dangling_guids.jsonl`: 1137 rows, verdicts: {"unresolved-open": 1137}
- `locale_join_report.json`: registryMisses=5 (termId -2044546668, termId -1942168175, termId -1451566921, termId -1172386361, termId -1168948158)

## Proven-absent / unreachable relations (this corpus)

- `config->student-type` [missing] no carrier found in client data today; probe candidates: cross-file PPtr growth (_unresolved_pptrs.jsonl), GUID-carried references (guid bridge), decompiled code analysis (decompiled/structural/class-hierarchy.jsonl)
- `config->campus-level` [missing] no carrier found in client data today; probe candidates: cross-file PPtr growth (_unresolved_pptrs.jsonl), GUID-carried references (guid bridge), decompiled code analysis (decompiled/structural/class-hierarchy.jsonl)
- `config->scene` [missing] no carrier found in client data today; probe candidates: cross-file PPtr growth (_unresolved_pptrs.jsonl), GUID-carried references (guid bridge), decompiled code analysis (decompiled/structural/class-hierarchy.jsonl)
- `item->room` [missing] no carrier found in client data today; probe candidates: cross-file PPtr growth (_unresolved_pptrs.jsonl), GUID-carried references (guid bridge), decompiled code analysis (decompiled/structural/class-hierarchy.jsonl)
- `item->course` [missing] no carrier found in client data today; probe candidates: cross-file PPtr growth (_unresolved_pptrs.jsonl), GUID-carried references (guid bridge), decompiled code analysis (decompiled/structural/class-hierarchy.jsonl)
- `item->staff` [missing] no carrier found in client data today; probe candidates: cross-file PPtr growth (_unresolved_pptrs.jsonl), GUID-carried references (guid bridge), decompiled code analysis (decompiled/structural/class-hierarchy.jsonl)
- `item->student-type` [missing] no carrier found in client data today; probe candidates: cross-file PPtr growth (_unresolved_pptrs.jsonl), GUID-carried references (guid bridge), decompiled code analysis (decompiled/structural/class-hierarchy.jsonl)
- `item->unlockable` [missing] no carrier found in client data today; probe candidates: cross-file PPtr growth (_unresolved_pptrs.jsonl), GUID-carried references (guid bridge), decompiled code analysis (decompiled/structural/class-hierarchy.jsonl)
- `item->metagame-node` [missing] no carrier found in client data today; probe candidates: cross-file PPtr growth (_unresolved_pptrs.jsonl), GUID-carried references (guid bridge), decompiled code analysis (decompiled/structural/class-hierarchy.jsonl)
- `item->campus-level` [missing] no carrier found in client data today; probe candidates: cross-file PPtr growth (_unresolved_pptrs.jsonl), GUID-carried references (guid bridge), decompiled code analysis (decompiled/structural/class-hierarchy.jsonl)
- `item->scene` [missing] no carrier found in client data today; probe candidates: cross-file PPtr growth (_unresolved_pptrs.jsonl), GUID-carried references (guid bridge), decompiled code analysis (decompiled/structural/class-hierarchy.jsonl)
- `room->room` [missing] no carrier found in client data today; probe candidates: cross-file PPtr growth (_unresolved_pptrs.jsonl), GUID-carried references (guid bridge), decompiled code analysis (decompiled/structural/class-hierarchy.jsonl)
- `room->course` [missing] no carrier found in client data today; probe candidates: cross-file PPtr growth (_unresolved_pptrs.jsonl), GUID-carried references (guid bridge), decompiled code analysis (decompiled/structural/class-hierarchy.jsonl)
- `room->staff` [missing] no carrier found in client data today; probe candidates: cross-file PPtr growth (_unresolved_pptrs.jsonl), GUID-carried references (guid bridge), decompiled code analysis (decompiled/structural/class-hierarchy.jsonl)
- `room->student-type` [missing] no carrier found in client data today; probe candidates: cross-file PPtr growth (_unresolved_pptrs.jsonl), GUID-carried references (guid bridge), decompiled code analysis (decompiled/structural/class-hierarchy.jsonl)
- `room->metagame-node` [missing] no carrier found in client data today; probe candidates: cross-file PPtr growth (_unresolved_pptrs.jsonl), GUID-carried references (guid bridge), decompiled code analysis (decompiled/structural/class-hierarchy.jsonl)
- `room->campus-level` [missing] no carrier found in client data today; probe candidates: cross-file PPtr growth (_unresolved_pptrs.jsonl), GUID-carried references (guid bridge), decompiled code analysis (decompiled/structural/class-hierarchy.jsonl)
- `room->scene` [missing] no carrier found in client data today; probe candidates: cross-file PPtr growth (_unresolved_pptrs.jsonl), GUID-carried references (guid bridge), decompiled code analysis (decompiled/structural/class-hierarchy.jsonl)
- `course->room` [missing] no carrier found in client data today; probe candidates: cross-file PPtr growth (_unresolved_pptrs.jsonl), GUID-carried references (guid bridge), decompiled code analysis (decompiled/structural/class-hierarchy.jsonl)
- `course->staff` [missing] no carrier found in client data today; probe candidates: cross-file PPtr growth (_unresolved_pptrs.jsonl), GUID-carried references (guid bridge), decompiled code analysis (decompiled/structural/class-hierarchy.jsonl)
- `course->student-type` [missing] no carrier found in client data today; probe candidates: cross-file PPtr growth (_unresolved_pptrs.jsonl), GUID-carried references (guid bridge), decompiled code analysis (decompiled/structural/class-hierarchy.jsonl)
- `course->unlockable` [missing] no carrier found in client data today; probe candidates: cross-file PPtr growth (_unresolved_pptrs.jsonl), GUID-carried references (guid bridge), decompiled code analysis (decompiled/structural/class-hierarchy.jsonl)
- `course->metagame-node` [missing] no carrier found in client data today; probe candidates: cross-file PPtr growth (_unresolved_pptrs.jsonl), GUID-carried references (guid bridge), decompiled code analysis (decompiled/structural/class-hierarchy.jsonl)
- `course->campus-level` [missing] no carrier found in client data today; probe candidates: cross-file PPtr growth (_unresolved_pptrs.jsonl), GUID-carried references (guid bridge), decompiled code analysis (decompiled/structural/class-hierarchy.jsonl)
- `course->scene` [missing] no carrier found in client data today; probe candidates: cross-file PPtr growth (_unresolved_pptrs.jsonl), GUID-carried references (guid bridge), decompiled code analysis (decompiled/structural/class-hierarchy.jsonl)
- `staff->item` [missing] no carrier found in client data today; probe candidates: cross-file PPtr growth (_unresolved_pptrs.jsonl), GUID-carried references (guid bridge), decompiled code analysis (decompiled/structural/class-hierarchy.jsonl)
- `staff->room` [missing] no carrier found in client data today; probe candidates: cross-file PPtr growth (_unresolved_pptrs.jsonl), GUID-carried references (guid bridge), decompiled code analysis (decompiled/structural/class-hierarchy.jsonl)
- `staff->course` [missing] no carrier found in client data today; probe candidates: cross-file PPtr growth (_unresolved_pptrs.jsonl), GUID-carried references (guid bridge), decompiled code analysis (decompiled/structural/class-hierarchy.jsonl)
- `staff->staff` [missing] no carrier found in client data today; probe candidates: cross-file PPtr growth (_unresolved_pptrs.jsonl), GUID-carried references (guid bridge), decompiled code analysis (decompiled/structural/class-hierarchy.jsonl)
- `staff->student-type` [missing] no carrier found in client data today; probe candidates: cross-file PPtr growth (_unresolved_pptrs.jsonl), GUID-carried references (guid bridge), decompiled code analysis (decompiled/structural/class-hierarchy.jsonl)
- `staff->metagame-node` [missing] no carrier found in client data today; probe candidates: cross-file PPtr growth (_unresolved_pptrs.jsonl), GUID-carried references (guid bridge), decompiled code analysis (decompiled/structural/class-hierarchy.jsonl)
- `staff->campus-level` [missing] no carrier found in client data today; probe candidates: cross-file PPtr growth (_unresolved_pptrs.jsonl), GUID-carried references (guid bridge), decompiled code analysis (decompiled/structural/class-hierarchy.jsonl)
- `staff->scene` [missing] no carrier found in client data today; probe candidates: cross-file PPtr growth (_unresolved_pptrs.jsonl), GUID-carried references (guid bridge), decompiled code analysis (decompiled/structural/class-hierarchy.jsonl)
- `student-type->item` [missing] no carrier found in client data today; probe candidates: cross-file PPtr growth (_unresolved_pptrs.jsonl), GUID-carried references (guid bridge), decompiled code analysis (decompiled/structural/class-hierarchy.jsonl)
- `student-type->room` [missing] no carrier found in client data today; probe candidates: cross-file PPtr growth (_unresolved_pptrs.jsonl), GUID-carried references (guid bridge), decompiled code analysis (decompiled/structural/class-hierarchy.jsonl)
- `student-type->course` [missing] no carrier found in client data today; probe candidates: cross-file PPtr growth (_unresolved_pptrs.jsonl), GUID-carried references (guid bridge), decompiled code analysis (decompiled/structural/class-hierarchy.jsonl)
- `student-type->staff` [missing] no carrier found in client data today; probe candidates: cross-file PPtr growth (_unresolved_pptrs.jsonl), GUID-carried references (guid bridge), decompiled code analysis (decompiled/structural/class-hierarchy.jsonl)
- `student-type->student-type` [missing] no carrier found in client data today; probe candidates: cross-file PPtr growth (_unresolved_pptrs.jsonl), GUID-carried references (guid bridge), decompiled code analysis (decompiled/structural/class-hierarchy.jsonl)
- `student-type->unlockable` [missing] no carrier found in client data today; probe candidates: cross-file PPtr growth (_unresolved_pptrs.jsonl), GUID-carried references (guid bridge), decompiled code analysis (decompiled/structural/class-hierarchy.jsonl)
- `student-type->metagame-node` [missing] no carrier found in client data today; probe candidates: cross-file PPtr growth (_unresolved_pptrs.jsonl), GUID-carried references (guid bridge), decompiled code analysis (decompiled/structural/class-hierarchy.jsonl)
- `student-type->campus-level` [missing] no carrier found in client data today; probe candidates: cross-file PPtr growth (_unresolved_pptrs.jsonl), GUID-carried references (guid bridge), decompiled code analysis (decompiled/structural/class-hierarchy.jsonl)
- `student-type->scene` [missing] no carrier found in client data today; probe candidates: cross-file PPtr growth (_unresolved_pptrs.jsonl), GUID-carried references (guid bridge), decompiled code analysis (decompiled/structural/class-hierarchy.jsonl)
- `unlockable->room` [missing] no carrier found in client data today; probe candidates: cross-file PPtr growth (_unresolved_pptrs.jsonl), GUID-carried references (guid bridge), decompiled code analysis (decompiled/structural/class-hierarchy.jsonl)
- `unlockable->course` [missing] no carrier found in client data today; probe candidates: cross-file PPtr growth (_unresolved_pptrs.jsonl), GUID-carried references (guid bridge), decompiled code analysis (decompiled/structural/class-hierarchy.jsonl)
- `unlockable->staff` [missing] no carrier found in client data today; probe candidates: cross-file PPtr growth (_unresolved_pptrs.jsonl), GUID-carried references (guid bridge), decompiled code analysis (decompiled/structural/class-hierarchy.jsonl)
- `unlockable->student-type` [missing] no carrier found in client data today; probe candidates: cross-file PPtr growth (_unresolved_pptrs.jsonl), GUID-carried references (guid bridge), decompiled code analysis (decompiled/structural/class-hierarchy.jsonl)
- `unlockable->metagame-node` [missing] no carrier found in client data today; probe candidates: cross-file PPtr growth (_unresolved_pptrs.jsonl), GUID-carried references (guid bridge), decompiled code analysis (decompiled/structural/class-hierarchy.jsonl)
- `unlockable->campus-level` [partial] probe cell: scanned unlockable payloads for Levels[] / LevelFilters / level-name segments matching campus-level ids — no measured carrier on this corpus; re-check after cross-file PPtr resolution growth
- `unlockable->scene` [missing] no carrier found in client data today; probe candidates: cross-file PPtr growth (_unresolved_pptrs.jsonl), GUID-carried references (guid bridge), decompiled code analysis (decompiled/structural/class-hierarchy.jsonl)
- `metagame-node->room` [missing] no carrier found in client data today; probe candidates: cross-file PPtr growth (_unresolved_pptrs.jsonl), GUID-carried references (guid bridge), decompiled code analysis (decompiled/structural/class-hierarchy.jsonl)
- `metagame-node->course` [partial] needs-probe cell: .references.NNNN.data.Course PPtrs resolve through the R1 bridges; 0 still dangle against non-stub (scene/prefab-resident) objects — owner: scene-dump walk (maps piece)
- `metagame-node->staff` [missing] no carrier found in client data today; probe candidates: cross-file PPtr growth (_unresolved_pptrs.jsonl), GUID-carried references (guid bridge), decompiled code analysis (decompiled/structural/class-hierarchy.jsonl)
- `metagame-node->student-type` [missing] no carrier found in client data today; probe candidates: cross-file PPtr growth (_unresolved_pptrs.jsonl), GUID-carried references (guid bridge), decompiled code analysis (decompiled/structural/class-hierarchy.jsonl)
- `metagame-node->unlockable` [missing] no carrier found in client data today; probe candidates: cross-file PPtr growth (_unresolved_pptrs.jsonl), GUID-carried references (guid bridge), decompiled code analysis (decompiled/structural/class-hierarchy.jsonl)
- `metagame-node->metagame-node` [missing] no carrier found in client data today; probe candidates: cross-file PPtr growth (_unresolved_pptrs.jsonl), GUID-carried references (guid bridge), decompiled code analysis (decompiled/structural/class-hierarchy.jsonl)
- `metagame-node->campus-level` [missing] no carrier found in client data today; probe candidates: cross-file PPtr growth (_unresolved_pptrs.jsonl), GUID-carried references (guid bridge), decompiled code analysis (decompiled/structural/class-hierarchy.jsonl)
- `metagame-node->scene` [missing] no carrier found in client data today; probe candidates: cross-file PPtr growth (_unresolved_pptrs.jsonl), GUID-carried references (guid bridge), decompiled code analysis (decompiled/structural/class-hierarchy.jsonl)
- `campus-level->item` [missing] no carrier found in client data today; probe candidates: cross-file PPtr growth (_unresolved_pptrs.jsonl), GUID-carried references (guid bridge), decompiled code analysis (decompiled/structural/class-hierarchy.jsonl)
- `campus-level->room` [missing] no carrier found in client data today; probe candidates: cross-file PPtr growth (_unresolved_pptrs.jsonl), GUID-carried references (guid bridge), decompiled code analysis (decompiled/structural/class-hierarchy.jsonl)
- `campus-level->course` [missing] no carrier found in client data today; probe candidates: cross-file PPtr growth (_unresolved_pptrs.jsonl), GUID-carried references (guid bridge), decompiled code analysis (decompiled/structural/class-hierarchy.jsonl)
- `campus-level->staff` [missing] no carrier found in client data today; probe candidates: cross-file PPtr growth (_unresolved_pptrs.jsonl), GUID-carried references (guid bridge), decompiled code analysis (decompiled/structural/class-hierarchy.jsonl)
- `campus-level->student-type` [missing] no carrier found in client data today; probe candidates: cross-file PPtr growth (_unresolved_pptrs.jsonl), GUID-carried references (guid bridge), decompiled code analysis (decompiled/structural/class-hierarchy.jsonl)
- `campus-level->unlockable` [missing] no carrier found in client data today; probe candidates: cross-file PPtr growth (_unresolved_pptrs.jsonl), GUID-carried references (guid bridge), decompiled code analysis (decompiled/structural/class-hierarchy.jsonl)
- `campus-level->metagame-node` [partial] carrier found and resolving: campus-level payloads' .MetagameConfig.m_AssetGUID → catalog → Config_Metagame resolves, but stage-5 emits that asset as kind `config`, so the rows land in campus-level_config.jsonl — metagame-node identity is blocked on the KINDING, not on a missing carrier (owner-routable via the decision register; no dual-kind rows are emitted)
- `campus-level->campus-level` [missing] no carrier found in client data today; probe candidates: cross-file PPtr growth (_unresolved_pptrs.jsonl), GUID-carried references (guid bridge), decompiled code analysis (decompiled/structural/class-hierarchy.jsonl)
- `campus-level->scene` [missing] no carrier found in client data today; probe candidates: cross-file PPtr growth (_unresolved_pptrs.jsonl), GUID-carried references (guid bridge), decompiled code analysis (decompiled/structural/class-hierarchy.jsonl)
- `scene->config` [missing] no stub-payload emitter exists for the scene source node by design — scene objects have no stubs; owner: the maps piece's scene-dump walk (inherits this piece's scene node seam)
- `scene->item` [missing] no stub-payload emitter exists for the scene source node by design — scene objects have no stubs; owner: the maps piece's scene-dump walk (inherits this piece's scene node seam)
- `scene->room` [missing] no stub-payload emitter exists for the scene source node by design — scene objects have no stubs; owner: the maps piece's scene-dump walk (inherits this piece's scene node seam)
- `scene->course` [missing] no stub-payload emitter exists for the scene source node by design — scene objects have no stubs; owner: the maps piece's scene-dump walk (inherits this piece's scene node seam)
- `scene->staff` [missing] no stub-payload emitter exists for the scene source node by design — scene objects have no stubs; owner: the maps piece's scene-dump walk (inherits this piece's scene node seam)
- `scene->student-type` [missing] no stub-payload emitter exists for the scene source node by design — scene objects have no stubs; owner: the maps piece's scene-dump walk (inherits this piece's scene node seam)
- `scene->unlockable` [missing] no stub-payload emitter exists for the scene source node by design — scene objects have no stubs; owner: the maps piece's scene-dump walk (inherits this piece's scene node seam)
- `scene->metagame-node` [missing] no stub-payload emitter exists for the scene source node by design — scene objects have no stubs; owner: the maps piece's scene-dump walk (inherits this piece's scene node seam)
- `scene->campus-level` [missing] no stub-payload emitter exists for the scene source node by design — scene objects have no stubs; owner: the maps piece's scene-dump walk (inherits this piece's scene node seam)
- `scene->scene` [missing] no stub-payload emitter exists for the scene source node by design — scene objects have no stubs; owner: the maps piece's scene-dump walk (inherits this piece's scene node seam)

## UI-link coverage (bar 2)

- surfaces: 344 (mapped-schema 9 / documented-gap 335); tooltip target census 0 classes fully partitioned; I2.Loc.Localize bindings 11312 route text lookups to `entity_locale.jsonl`

## Competitor application (bar 3)

- sourcesRead=2 confirms-hard=0 adds-derived=0 flags-missing=417 walls=0; floor UNMET (≥3 applied sources required)
- fandom: confirms-hard=0 adds-derived=0 flags-missing=383
- steam-guides: confirms-hard=0 adds-derived=0 flags-missing=34
- TERMINAL: measured dead end for raw more-of-the-same corpus: the committed community-word claims resolve zero under the pinned exact + casefold/_<->space convention (measured across the committed corpus: 0/417; prefix-strip variant 1/417) and scraped stubs carry no slugs (null on every row), so plain acquisition cannot flip this floor — the levers are claims named in internal ids or an authored community-name->internal-id alias input riding this research-pass lane (owner-routed per competitor-research.md); the stage consumes committed bytes only
