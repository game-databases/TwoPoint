# LOGIC — gameplay logic reconstructed from client data

- buildId: 20226581
- stage: `logic` (canonical index 8) — sole writer of everything under `extracted/logic/`
- generated mechanically by `tools/stage8_logic.py`; reruns are byte-identical

## Input inventory

| artifact | bytes |
|---|---|
| `decompiled/structural/class-hierarchy.jsonl` | 3485766 |
| `decompiled/structural/id-registries/TPS.Game.BudgetType.jsonl` | 924 |
| `decompiled/structural/id-registries/TPS.Game.TPC.EAttribute.jsonl` | 313 |
| `decompiled/structural/id-registries/TPS.Game.TPC.EGrade.jsonl` | 216 |
| `decompiled/structural/id-registries/TPS.Game.TPC.EStaffStat.jsonl` | 1232 |
| `harvest/export-manifest.jsonl` | 51405908 |
| `harvest/externals.jsonl` | 310527 |
| `harvest/monobehaviours/configs/TPC.CourseDefinition/` | 185009 |
| `harvest/monobehaviours/configs/TPC.StudentDefinition/` | 8387 |
| `identity.json` | 592 |
| `relinks/bridges/cab_index.jsonl` | 98687829 |
| `relinks/bridges/container_index.jsonl` | 10806787 |
| `relinks/config_config.jsonl` | 4522019 |
| `relinks/entity_locale.jsonl` | 3635041 |
| `relinks/i2_term_registry.jsonl` | 2880645 |
| `relinks/matrix.json` | 57558 |
| `stubs/_absences.jsonl` | 3349 |
| `stubs/campus-levels.jsonl` | 12225 |
| `stubs/configs.jsonl` | 20884562 |
| `stubs/courses.jsonl` | 142615 |
| `stubs/items.jsonl` | 8221578 |
| `stubs/metagame-nodes.jsonl` | 420233 |
| `stubs/rooms.jsonl` | 298494 |
| `stubs/staff.jsonl` | 14568 |
| `stubs/student-types.jsonl` | 62476 |
| `stubs/unlockables.jsonl` | 546013 |

## Datasets

### Course progression (`course-progression/`)

| artifact | rows | join keys | seed vs measured |
|---|---|---|---|
| `courses.jsonl` | 69 | verbatim course ids | 69 → 69 |
| `modules.jsonl` | 319 | module id → RoomType/Qualification PPtr | 319 → 319 |
| `prerequisites.jsonl` | 471 | (carrierId, refKey) | 193 → 471 **DRIFT** |
| `prerequisite-nonmembers.jsonl` | 27 | (carrierId, refKey) | 27 → 27 |
| `course-unlock-edges.jsonl` | 50 | srcId → dstId via CAB/pathId | 50 → 50 |
| `attrition.jsonl` | 4 | Config_Campus field groups | 4 → 4 |
- census across ALL stub kinds measures 471 member blocks; the 193 seed scopes configs.jsonl (both probed, fresh wins)
- reconciliation leg (RF-2): relinksCoursePPTRRows 68 · unlockEdgeOverlapWithRelinks 50 · declaredScopeDifference 18 {'TPC.CharacterModifier_XP': 2, 'TPC.PrerequisiteHasCourseAtLevel': 3, 'TPC.PrerequisiteHasCourseRunning': 13}

### Economy (`economy/`)

| artifact | rows | join keys | seed vs measured |
|---|---|---|---|
| `money-taxonomy.json` | 28 | BudgetType registry byte-match | 28 → 28 |
| `finance-configs.jsonl` | 30 | Config_FinanceManager* ids | 30 → 30 |
| `kudosh-ledger.jsonl` | 2143 | carrier ids | sources+sinks → 2143 |
| `research-costs.jsonl` | 209 | metagame-node ids | 209 → 209 |
- kudosh prices serialize on GameItemLiteDefinition.Kudosh / RoomLiteDefinition.Kudosh / LandscapeBrushDefinition._kudosh; the IKudoshUnlockable interface sits on the full definitions (dump.cs 824971 / 836761 / 992046)
- 241 ResearchProjectLiteDefinition rows are the DECLARED-EMPTY cost class — counted, never zero-filled

### Grading (`grading/`)

| artifact | rows | join keys | seed vs measured |
|---|---|---|---|
| `grade-ladder.json` | 9 | Grades[].Enum → EGrade.value | 9 → 9 |
| `term-pass-grades.jsonl` | 75 | (courseId, termIndex) | 75 → 75 |
| `assessment-scoring.jsonl` | 28 | courseId (harvest-direct) | 28 → 28 |
| `xp-score-normalization.json` | 1 | — | 1 → 1 |
- MEASURED SHAPE NOTE: TermDefinition.PassGrade is `public int` in code (dump.cs ~840152) and measures 40 on every row — outside the EGrade domain; passGrade therefore emits null and passGradeValue carries the verbatim int (mapping 40 to a grade NAME would be an invented rule, R4)

### Needs & decay (`needs-decay/`)

| artifact | rows | join keys | seed vs measured |
|---|---|---|---|
| `staff-decay.jsonl` | 30 | (staffId, attribute) | 30 → 30 |
| `student-decay.jsonl` | 13 | studentTypeId/component | 6+7 → 13 |
| `student-core11-decay.jsonl` | 11 | EAttribute members | 11 → 11 |
| `interactions.jsonl` | 630 | verbatim interaction ids | 630 → 630 |
- studentDecayRawCoverage {'raws': 2, 'studentTypeStubs': 54} — a MEASURED COUNTER printed beside the dataset table, NEVER a gap row (arbiter-piece04-spec Part 2/R4)

## UNPROVEN-NATIVE register

- **grading/xp-score-normalization.json** — XP accumulation → assessment score normalization feeding GetGrade(score) — status UNPROVEN-NATIVE, emittedNumbers [] by law; site presents bands as client data and the step below them as unknown.
- **needs-decay/student-core11-decay.jsonl** — student core-11 attribute decay carrier absent everywhere in the corpus; 11 null-carrier rows keep the narrowness in the record (the staff side IS data-recoverable above).

Native-analysis deferral (orchestrator ruling R3): deferred, not cancelled — the single known trigger case is the XP→score normalization above; a site piece genuinely needing a code-computed constant reopens it.

## Gap ledger

- rows: 2 (grading: 1, needs-decay: 1 — see `_gaps.jsonl`)
- `grading:missing-carrier:xp-score-normalization` — XP→score normalization lives native/Burst; score->grade cut-offs are data (grading/xp-score-normalization.json) Unblock: scoped native-analysis piece over GameAssembly.dll guided by script.json (orchestrator ruling R3 UPDATE)
- `needs-decay:missing-carrier:student-core11-decay` — the student core-11 attribute decay carrier is genuinely absent (needs-decay/student-core11-decay.jsonl) Unblock: native probe (G1/G8) or save-state diffing across time intervals (report G3)

## Reconstruction-labeling law

- Every emitted number is copied-and-matching under citation OR sits in one of three labeled hatches: `provenance:"reconstructed-from-code"` blocks, `method:"derived-arithmetic:<expr>"` aggregates recomputed by the stage's invention guard from their cited inputs, or explicit null absent-with-ledger rows.
- Invented numbers are a launch-gate failure; the guard exits 1 naming artifact + path.
- Coverage counter (NOT a gap row): student decay raw coverage {'raws': 2, 'studentTypeStubs': 54} — prefab-side student definitions were never harvested (arbiter-piece04-spec Part 2/R4); the core-11 null ledger covers the same absence once.

## Drift notes (fresh measurement wins)

- DRIFT: prerequisiteClass[PrerequisiteHasCourseUnlocked] measures 0 against seed 50 — fresh number wins
- DRIFT: prerequisiteClass[PrerequisiteUniversityLevel] measures 0 against seed 43 — fresh number wins
- DRIFT: prerequisiteClass[ChallengePrerequisiteHasRoomUnlocked] measures 0 against seed 18 — fresh number wins
- DRIFT: prerequisiteClass[PrerequisiteDaysPassed] measures 0 against seed 17 — fresh number wins
- DRIFT: prerequisiteClass[PrerequisiteHasStarsInLevel] measures 0 against seed 13 — fresh number wins
- DRIFT: 11 finance overrides differ beyond InitialBalance (legitimate wider overrides) e.g. [('Config_FinanceManager_Level_Ghosts_Remix', ['AllowTuitionFeeModification', 'FailStateBalanceGameOver', 'FailStateBalanceWarning', 'InitialBalance', 'RentMultiplier', 'TuitionFeesMultiplier']), ('Config_FinanceManager_Level_LaunchPad', ['InitialBalance', 'RentMultiplier', 'TuitionFeesMultiplier']), ('Config_FinanceManager_Level_Party', ['AllowTuitionFeeModification', 'RentMultiplier', 'TuitionFeesMultiplier'])]
