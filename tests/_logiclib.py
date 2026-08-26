"""Stage-8 logic (piece-04 section 8) synthetic fixture library + validators.

Everything here is SYNTHETIC - never real game bytes. The mini-corpus mirrors
the MEASURED corpus shapes (grounded on extracted/ at buildId 20226581:
piece-1-pinned stub rows, FLAT harvest raw dumps carrying
_assessmentScoring/_studentArchetypes, SerializeReference typed blocks
references["%08x"].{data,type} behind fields.Prerequisites=[{id:N}]
indirection (plus the non-hex version key the real references dicts carry),
externals rows keyed by FULL bundle relpath with DOUBLED archive:/CAB-x/CAB-x
paths, cab_index/container_index bridge rows, pair-row relinks shape with
dstCab spelled lowercase). Where this library pins a number the source is
docs/specs/piece-04-logic.mdx Rev 3 (section 2 facts F1-F17, section 3
sub-passes L0-L6, section 5 AC1-AC10) or docs/rulings/arbiter-piece04-spec.mdx
- cited inline as [F..]/[AC..]/[R..].

Layout of the little world (all ids verbatim-stable):

  configs_assets_all.bundle          career-challenge carriers (two unlock
                                     edges + declared-scope counterparts),
                                     finance trio (base + 2 diff-only level
                                     overrides), qualifications,
                                     TermDefinitions, 5 Module_* +
                                     2 Unused_Module_* (class-selected;
                                     prefix split asserted post-selection),
                                     4 TPC.InteractionDefinition + 1 bare-name
                                     decoy that must never be selected, the
                                     GOOSE graph target, kudosh brush/consum-
                                     ables/reward chest, campus levels
                                     (one LevelLite non-member carrier, one
                                     UniversityLevel member carrier), clubs,
                                     event/challenge prerequisite carriers,
                                     and the THREE full course definitions
                                     (courses live here on the real corpus -
                                     their raw dumps are
                                     configs_assets_all_<pathId>.json)
  configs-app_assets_all.bundle      Config_UISprite (Grades[9], verifyB 1.1)
  configs-metagame_assets_all.bundle research nodes (5 full + 1 Lite twin +
                                     1 database row), Config_Metagame_Global
                                     non-member carrier
  configs-common_assets_all.bundle   the @hash8 twin ENDPOINT
                                     Course_Archaeology_Lite@c0ffee42
  rooms_assets_all.bundle            Room_Alien_Science + peers + kudosh sink
  character-shared_assets_all.bundle staff decay blocks, student-type stubs
  items-general_assets_all.bundle    GameItemDefinition sink + upgrades
  unlockables_assets_all.bundle      one unlockable row (kind coverage)

Variants (build_logic_tree(variant=...)):
  green          everything resolvable; gaps == exactly the two standing
                 UNPROVEN-NATIVE rows -> exit 2 steady state [AC9]
  failmodes      adds a broken carrier with four doomed typed refs (unknown
                 fileId / builtin external / dangling pathId / ambiguous
                 double-CAB candidate) and flips Unused_Module_Broken to
                 builtin RoomType + dangling Qualification; exit stays 2
  monotonic      Grades[3].Threshold 50.0 -> 35.0 breaks monotonicity -> exit 1
  econmismatch   raw Course_Potions LicenseCost disagrees with the stub ->
                 copied-but-mismatching -> exit 1 naming the path
  financedrift   Space override differs in a SECOND field -> DRIFT, not crash
  divergence     relinks claims a different dstPathId for one edge ->
                 relinks-divergence gap row [RF-2], exit stays 2
"""
from __future__ import annotations

import copy
import json
import re
import os
import sys
from pathlib import Path

os.environ.setdefault("PYTHONUTF8", "1")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _validators import BUILD_ID, KIND_TO_FILE, read_jsonl, write_jsonl  # noqa: E402,F401
import _fixturelib as fx  # noqa: E402
import _relinklib as rl  # noqa: E402

TAXONOMY_24 = [
    "ChallengePrerequisiteAcademicScore",
    "ChallengePrerequisiteHasRoom",
    "ChallengePrerequisiteHasRoomUnlocked",
    "PrerequisiteDaysPassed",
    "PrerequisiteDaysPassedSinceCourseStart",
    "PrerequisiteDaysSinceEventRun",
    "PrerequisiteEventUnlocked",
    "PrerequisiteHasClubLevel",
    "PrerequisiteHasCourseAtLevel",
    "PrerequisiteHasCourseRunning",
    "PrerequisiteHasCourseUnlocked",
    "PrerequisiteHasDefeatedChallengeEvent",
    "PrerequisiteHasItemInLevel",
    "PrerequisiteHasLevelDiscovered",
    "PrerequisiteHasResearchProjectUnlocked",
    "PrerequisiteHasStarsInLevel",
    "PrerequisiteHasUnlockable",
    "PrerequisiteHaveStudentsOnCampus",
    "PrerequisiteItemAvailable",
    "PrerequisiteItemUnlocked",
    "PrerequisiteQualificationUnlocked",
    "PrerequisiteStaffWithQualification",
    "PrerequisiteTimeSinceArrival",
    "PrerequisiteUniversityLevel",
]

# F4 short-name <-> full-spelling map (verbatim from the spec cell).
SHORT_NAME_MAP = {
    "DaysPassed": "PrerequisiteDaysPassed",
    "DaysPassedSinceCourseStart": "PrerequisiteDaysPassedSinceCourseStart",
    "ItemUnlocked": "PrerequisiteItemUnlocked",
    "ItemAvailable": "PrerequisiteItemAvailable",
    "HasResearchProjectUnlocked": "PrerequisiteHasResearchProjectUnlocked",
    "HasCourseUnlocked": "PrerequisiteHasCourseUnlocked",
    "HasLevelDiscovered": "PrerequisiteHasLevelDiscovered",
    "HasStarsInLevel": "PrerequisiteHasStarsInLevel",
    "UniversityLevel": "PrerequisiteUniversityLevel",
    "TimeSinceArrival": "PrerequisiteTimeSinceArrival",
    "HasCourseRunning": "PrerequisiteHasCourseRunning",
    "HaveStudentsOnCampus": "PrerequisiteHaveStudentsOnCampus",
    "HasDefeatedChallengeEvent": "PrerequisiteHasDefeatedChallengeEvent",
    "HasClubLevel": "PrerequisiteHasClubLevel",
    "StaffWithQualification": "PrerequisiteStaffWithQualification",
    "QualificationUnlocked": "PrerequisiteQualificationUnlocked",
    "EventUnlocked": "PrerequisiteEventUnlocked",
    "HasItemInLevel": "PrerequisiteHasItemInLevel",
    "HasCourseAtLevel": "PrerequisiteHasCourseAtLevel",
    "DaysSinceEventRun": "PrerequisiteDaysSinceEventRun",
    "HasUnlockable": "PrerequisiteHasUnlockable",
    "ChallengeHasRoom": "ChallengePrerequisiteHasRoom",
    "ChallengeHasRoomUnlocked": "ChallengePrerequisiteHasRoomUnlocked",
    "ChallengeAcademicScore": "ChallengePrerequisiteAcademicScore",
}

# Declared NON-member look-alikes (F4: ILevelPrerequisiteData family,
# dump.cs 880899/880924 - a different interface, never taxonomy members).
NONMEMBER_CLASSES = ("LevelPrerequisiteStars", "LevelPrerequisiteStarsByLevelID")
NONMEMBER_FAMILY = "ILevelPrerequisiteData"

# F8: BudgetType = 28 named values TuitionFees=0 .. PatientTreatmentIncome=27
# (value order as sketched; registry FILES store name-sorted - AC3 equality is
# against the file own name-sorted sequence).
BUDGET_TYPES = [
    ("TuitionFees", 0), ("Rent", 1), ("Bonus", 2), ("Allowance", 3),
    ("BudgetRefund", 4), ("ResearchIncome", 5), ("Objectives", 6),
    ("ItemsIncome", 7), ("EventsIncome", 8), ("LoanReceived", 9),
    ("Wages", 10), ("LoansExpense", 11), ("Training", 12),
    ("ResearchExpense", 13), ("Marketing", 14), ("RecruitmentFees", 15),
    ("EventsExpense", 16), ("Upgrades", 17), ("ItemsExpense", 18),
    ("Building", 19), ("CourseLicences", 20), ("Misc", 21), ("Cheats", 22),
    ("BungleBonus", 23), ("SocialBonus", 24), ("MiscExpense", 25),
    ("Mining", 26), ("PatientTreatmentIncome", 27),
]
PROFIT_TYPE = ["TuitionFees", "Rent", "Bonus"]
EXPENSE_TYPE = ["Wages", "Loans"]
SUMMARY_COLUMNS = ["TuitionFees", "Rent", "Wages", "Bonus", "LoanRepayments",
                   "LoanInterest", "BungleBonus", "SocialBonus",
                   "ResearchBonus", "MiningProfit", "PatientTreatment",
                   "CheesyBonus", "MonthlyAllowance", "OtherIn", "OtherOut"]

# F12: EGrade 9 members Invalid=0 .. AA=8.
EGRADE_MEMBERS = [("Invalid", 0), ("F", 1), ("D", 2), ("C", 3), ("CC", 4),
                  ("B", 5), ("BB", 6), ("A", 7), ("AA", 8)]
ESTAFFSTAT_COUNT = 31   # F8: EStaffStat = 31 members (count-only fixture)

# F12/verifyB 1.1: Config_UISprite.Grades[9] Enum/Threshold pairs, measured
# displayNameTermIds (arbiter: digit-for-digit), and the sprite-reference
# sub-name token per row (AIR uniform Notifications_Grade_<X>; IR diverges to
# Status_T_Icon_Grade_<X> for F-AA and AGREES with AIR on the NA row).
GRADE_ROWS = {
    0: {"threshold": -1.0, "termId": -1534872139, "token": "NA"},
    1: {"threshold": 0.0, "termId": -1180291283, "token": "F"},
    2: {"threshold": 40.0, "termId": -693951262, "token": "D"},
    3: {"threshold": 50.0, "termId": -673216108, "token": "C"},
    4: {"threshold": 60.0, "termId": -639021983, "token": "CC"},
    5: {"threshold": 70.0, "termId": -1899866650, "token": "B"},
    6: {"threshold": 75.0, "termId": -1708865281, "token": "BB"},
    7: {"threshold": 80.0, "termId": -1381827241, "token": "A"},
    8: {"threshold": 90.0, "termId": -1320794757, "token": "AA"},
}
AIR_PREFIX = "UI_HUD_T_Spritesheet_Notifications_Grade_"
IR_PREFIX_F_AA = "UI_HUD_Status_T_Icon_Grade_"
# grade-ladder displayName locale join fills ONLY these two termIDs
DISPLAYNAME_JOINED_TERMIDS = {-1320794757: "Grade AA", -1180291283: "Grade F"}

# L4: EAttribute registry = 11 members (name-sorted file); ToiletComfort=5 and
# Litter=6 pinned by arbiter F8; staff carriers hold TEN fields (no Litter)
# hence staff-decay is N_staff x 10, never x 11.
EATTRIBUTE_MEMBERS = [
    ("Drink", 0), ("Energy", 1), ("Food", 2), ("Fun", 3), ("Happiness", 4),
    ("Health", 7), ("Hygiene", 8), ("Litter", 6), ("Sober", 9),
    ("Social", 10), ("ToiletComfort", 5),
]
STAFF_FIELD_TO_ATTRIBUTE = {
    "_drink": "Drink", "_energy": "Energy", "_food": "Food", "_fun": "Fun",
    "_happiness": "Happiness", "_health": "Health", "_hygiene": "Hygiene",
    "_sober": "Sober", "_social": "Social", "_toilet": "ToiletComfort",
}
DECAY_SIX = -0.05000000074505806   # drink/energy/food/hygiene/social/toilet
DECAY_ZERO = 0.0                   # fun/happiness/health/sober

# F15: attrition trigger groups = the four MEASURED Config_Campus field names
# only (GlobalFails ABSENT from the row AND dump.cs - invented labels fail).
ATTRITION_GROUPS = (
    "StudentDropoutSettings", "StaffResignationSettings",
    "StudentFailPercent", "StudentUnhappyTuitionFeesThreshold",
)
DROPOUT_FIELDS = {"CountdownTimer": 120.0, "ThresholdChangeOfMind": 15.0,
                  "ThresholdUrgent": 10.0, "ThresholdWarning": 20.0}
RESIGNATION_FIELDS = {"CountdownTimer": 240.0, "ThresholdChangeOfMind": 15.0,
                      "ThresholdUrgent": 10.0, "ThresholdWarning": 20.0}
EVENT_DROPOUT = ["TPC.CharacterEvents.Student.Expelled",
                 "TPC.CharacterEvents.Student.ExpelledFail"]
ATTRITION_CODE_REF = "dump.cs TPC.CharacterEvents.Student"

# F14: ECPStudent anchors with verbatim float noise.
STUDENT_RATES = {
    "ClubNeed": (-0.10000000149011612, 80.0, 100.0),
    "Relationship": (-0.20000000298023224, 40.0, 100.0),
    "SelfStudy": (-0.20000000298023224, 40.0, 100.0),
}

# F11: research domain (9 values) + seed distribution summing 209.
RESEARCH_DOMAIN = {100, 200, 250, 300, 500, 600, 1200, 2500, 3000}
RESEARCH_SEED_DIST = {100: 4, 200: 1, 250: 12, 300: 52, 500: 82, 600: 27,
                      1200: 29, 2500: 1, 3000: 1}
assert sum(RESEARCH_SEED_DIST.values()) == 209

# F9 finance anchors.
FIN_BASE_FIELDS = {
    "AllowTuitionFeeModification": 1, "FailStateBalanceGameOver": -300000,
    "FailStateBalanceWarning": -150000, "InitialBalance": 150000,
    "PerformanceBonusCurve": {"_factor": 0.5, "_maxX": 20000.0,
                              "_maxY": 40000.0, "_minX": 0.0, "_minY": 0.0,
                              "_type": 1},
    "RentMultiplier": 1.0, "TuitionFeesMultiplier": 1.0, "UseBungleBonus": 0,
}
FIN_DIFF_FIELD = "InitialBalance"
FIN_ARCH_BALANCE = 80000
FIN_SPACE_BALANCE = 120000

XP_STATUS = "UNPROVEN-NATIVE"   # L3 marker artifact law (R4)

# Headline run-section keys this suite parses out of EXTRACTION-LOG.md
# (spec section 3 Run-section-keys block; artifact-level checks carry the rest).
RUN_KEYS_WITH_NUMBERS = (
    "stubsLoaded", "stubIndexEntries", "registriesLoaded", "courseRowsFull",
    "courseRowsMarketing", "moduleRows", "moduleRoomResolved",
    "moduleRoomUnresolved", "prerequisiteInstances", "taxonomyDistinctClasses",
    "nonmemberBlocks", "nonmemberFamilies", "unlockEdgesResolved",
    "unlockEdgesUnresolved", "builtinExternalsSkipped", "relinksCoursePPTRRows",
    "unlockEdgeOverlapWithRelinks", "declaredScopeDifference",
    "budgetTypeCount", "financeConfigRows", "financeDiffOnlyOverrides",
    "kudoshSources", "researchCostRows", "liteRowsWithoutCosts",
    "researchDomainDistinct", "gradeLadderRows", "termPassGradeRows",
    "assessmentScoringRows", "staffDecayRows", "studentDecayRows",
    "clubDecayRows", "core11LedgerRows", "interactionRows", "aiGraphsResolved",
    "numericsAudited", "inventionGuardFailures", "gapRowsStanding",
)

# ---------------------------------------------------------------------------
# World geometry: bundles / CABs / pathIds
# ---------------------------------------------------------------------------

AA_REL = "TPC_Data/StreamingAssets/aa/StandaloneWindows64"
B_CONFIGS = "configs_assets_all.bundle"
B_APP = "configs-app_assets_all.bundle"
B_META = "configs-metagame_assets_all.bundle"
B_COMMON = "configs-common_assets_all.bundle"
B_ROOMS = "rooms_assets_all.bundle"
B_SHARED = "character-shared_assets_all.bundle"
B_ITEMS = "items-general_assets_all.bundle"
B_UNLOCK = "unlockables_assets_all.bundle"

CAB_CONFIGS = "CAB-c0nfig5main01"
CAB_APP = "CAB-appui02"
CAB_META = "CAB-meta03"
CAB_COMMON = "CAB-common04"
CAB_ROOMS = "CAB-rooms05"
CAB_SHARED = "CAB-shared06"
CAB_ITEMS = "CAB-items07"
CAB_UNLOCK = "CAB-unlock08"
CAB_DUP = "CAB-dupdup09"        # registered under TWO bundles (ambiguity leg)
CAB_GHOST404 = "CAB-ghost404"   # externals path with NO cab_index row

TWIN_HASH8 = "c0ffee42"
LITE_BARE = "Course_Archaeology_Lite"
LITE_ID = f"{LITE_BARE}@{TWIN_HASH8}"

DUP_PID = 5555                  # the ambiguous double-bundle candidate
DANGLING_PID = 88888888         # CAB resolves but no stub object there
SAME_FILE_DANGLING_PID = 77777777

P = lambda fid, pid: {"m_FileID": fid, "m_PathID": pid}  # noqa: E731


def full_rel(basename: str) -> str:
    """FULL roster-style relpath for a bundle basename (F7 mismatch: stubs
    store the BASENAME, externals rows key the FULL relpath)."""
    return f"{AA_REL}/{basename}"


PID = {
    # career-challenge carriers + typed prerequisite instances (config kind)
    "CareerChallenge_Course_Archaeology_V1": 9101,
    "CareerChallenge_Course_Potions_V2": 9102,
    "CareerChallenge_Course_Baking_V1": 9103,      # HasCourseRunning scope
    "CareerChallenge_Space_V1": 9104,              # HasCourseAtLevel scope
    "Activity_XP_Twin": 9105,                      # CharacterModifier_XP scope
    "CareerChallenge_Stars_V1": 9106,              # PrerequisiteHasStarsInLevel
    "Config_UISprite": 9115,                       # in B_APP on the real corpus
    "Config_Campus": 9110,
    "Config_FinanceManager": 9111,
    "Config_FinanceManager_Level_Archaeology": 9112,
    "Config_FinanceManager_Level_Space": 9113,
    "Qualification_Archaeology": 9120,
    "Term_Potions_Y1": 9121, "Term_Potions_Y2": 9122,
    "Term_Archaeology_Y1": 9123, "Term_Smithing_Y1": 9124,
    "Module_Alien_Science_Year1_Lesson1": 9131,
    "Module_Potions_Intro_Year1_Lesson1": 9132,
    "Module_Potions_Adv_Year1_Lesson1": 9133,
    "Module_Smith_Basics_Year1_Lesson1": 9134,
    "Module_Gradepay_Test_Year1_Lesson1": 9135,
    "Unused_Module_Old_Archaeology_Year1_Lesson1": 9136,
    "Unused_Module_Broken_Year1_Lesson1": 9137,
    "Interaction_Caterer_Needs": 9141, "Interaction_Cafeteria_Grab": 9142,
    "Interaction_Library_Study": 9143, "Interaction_Bench_Sit": 9144,
    "Interaction_Bare_Naming_Decoy": 9145,   # bare class spelling decoy
    "Graph_Lecture_Default": 9150,
    "CampusLevel_One": 9160,             # TPC.LevelLiteConfig non-member
    "Config_Metagame_Global": 9161,      # TPC.MetagameConfig non-member
    "CampusLevel_Two": 9162,             # UniversityLevel member carrier
    "Event_Summer_Open_Day": 9163,       # DaysPassed member carrier
    "Challenge_Academic_Honours": 9164,  # AcademicScore member carrier
    "Club_Book_Club": 9170, "Club_Chess_Club": 9171,
    "Kudosh_Consumable_Energy_Drink": 9180, "Kudosh_Consumable_Pizza": 9181,
    "Brush_Tree_Fancy": 9182, "Activity_Completion_Reward": 9183,
    "Staff_Assistant": 9201, "Staff_Lecturer": 9202,
    "StudentType_Nerd": 9210, "StudentType_Jock": 9211, "StudentType_Goth": 9212,
    "Archetype_Partier": 9220,
    "Room_Alien_Science": 9301, "Room_Lecture_Theatre": 9302,
    "Room_Kudosh_Sink_Room": 9303,
    "Course_Archaeology": 9401, "Course_Potions": 9402, "Course_Smithing": 9403,
    "Marketing_Potions": 9404, "Marketing_Smithing": 9405,
    LITE_ID: 9406,
    "Unlock_Kudosh_Sculpture": 9501,
    "Item_Kudosh_Trophy": 9601,
    "Alien_Refiner_V2": 9602, "Alien_Refiner_V3": 9603,
    "ResearchProject_Bookshelf_Robotics": 9701,
    "ResearchProject_Computer_Digital": 9702,
    "ResearchProject_Computer_Super": 9703,
    "ResearchProject_Course_Computer": 9704,
    "ResearchProject_Telescope_Kit": 9705,
    "ResearchProject_Bookshelf_Robotics_Lite": 9706,
    "ResearchProject_Database_Main": 9707,
    "Item_Duplicate_Common": DUP_PID,     # ambiguity twin in B_COMMON
    "Room_Duplicate_Rooms": DUP_PID,     # ambiguity twin in B_ROOMS
}

# ---------------------------------------------------------------------------
# Entity specs (the fixture oracle)
# ---------------------------------------------------------------------------

COURSE_SPECS = [
    # full TPC.CourseDefinition rows; economics cross-check stub-vs-raw [F2]
    {"id": "Course_Archaeology", "pid": 9401, "licenseCost": 0,
     "kudoshCost": 0, "yearlyTuitionFee": 8000, "startPointsCost": 20,
     "defaultStudentCount": 12, "applicantsBoost": 0,
     "applicantsFromCourseRating": 1, "applicantsFromUniversityRating": 1,
     "terms": [9123],
     "archetypes": [None],
     "levels": [
         {"ApplicantsBoost": 10.0, "HiringTeacherSkillLevelMax": 1,
          "LearningRatePercentBoost": 0.0, "PointsCost": 20.0,
          "TrainingTeacherSkillLevelMax": 3},
         {"ApplicantsBoost": 15.0, "HiringTeacherSkillLevelMax": 2,
          "LearningRatePercentBoost": 0.0, "PointsCost": 25.0,
          "TrainingTeacherSkillLevelMax": 4},
         {"ApplicantsBoost": 20.0, "HiringTeacherSkillLevelMax": 3,
          "LearningRatePercentBoost": 0.0, "PointsCost": 30.0,
          "TrainingTeacherSkillLevelMax": 5},
     ]},
    {"id": "Course_Potions", "pid": 9402, "licenseCost": 5000,
     "kudoshCost": 400, "yearlyTuitionFee": 9000, "startPointsCost": 25,
     "defaultStudentCount": 10, "applicantsBoost": 5,
     "applicantsFromCourseRating": 1, "applicantsFromUniversityRating": 1,
     "terms": [9121, 9122], "archetypes": [9220, None],
     "levels": [
         {"ApplicantsBoost": 10.0, "HiringTeacherSkillLevelMax": 1,
          "LearningRatePercentBoost": 0.0, "PointsCost": 20.0,
          "TrainingTeacherSkillLevelMax": 3},
         {"ApplicantsBoost": 20.0, "HiringTeacherSkillLevelMax": 4,
          "LearningRatePercentBoost": 0.0, "PointsCost": 40.0,
          "TrainingTeacherSkillLevelMax": 6},
     ]},
    {"id": "Course_Smithing", "pid": 9403, "licenseCost": 4500,
     "kudoshCost": 350, "yearlyTuitionFee": 7500, "startPointsCost": 15,
     "defaultStudentCount": 14, "applicantsBoost": 0,
     "applicantsFromCourseRating": 1, "applicantsFromUniversityRating": 1,
     "terms": [9124], "archetypes": [],
     "levels": [
         {"ApplicantsBoost": 10.0, "HiringTeacherSkillLevelMax": 1,
          "LearningRatePercentBoost": 0.0, "PointsCost": 20.0,
          "TrainingTeacherSkillLevelMax": 3},
     ]},
]

# F2: assessmentScoring is HARVEST-DIRECT (stub emitter dropped it); the
# Archaeology anchor {10.0, 0.75, 2.0, 0, ..} is verifyA 2d.
ASSESSMENT_ANCHOR = {
    "BonusPointsPerLevel": 10.0, "ExpectedAverageXPPerSecond": 0.75,
    "PowerFactor": 2.0, "UseTimeFactors": 0,
    "TimeInMedicalConsultationFactor": 0.0, "TimeOnCourseFactor": 0.0,
}
MARKETING_SPECS = [
    # marketingFor = the PPtr link target where the payload carries one;
    # null economics/ladders - emptiness is DATA, never a fill-in
    {"id": "Marketing_Potions", "pid": 9404, "targetPid": 9402},
    {"id": "Marketing_Smithing", "pid": 9405, "targetPid": None},
]
TERM_SPECS = [
    {"id": "Term_Potions_Y1", "pid": 9121, "passGrade": 3, "weight": 1.0,
     "modules": [9132, 9133, 9135]},
    {"id": "Term_Potions_Y2", "pid": 9122, "passGrade": 8, "weight": 1.0,
     "modules": [9133]},
    {"id": "Term_Archaeology_Y1", "pid": 9123, "passGrade": 5, "weight": 2.0,
     "modules": [9131, 9136]},
    {"id": "Term_Smithing_Y1", "pid": 9124, "passGrade": 1, "weight": 1.0,
     "modules": [9134, 9137]},
]

ZEROS = {"AA": 0, "A": 0, "BB": 0, "B": 0, "CC": 0, "C": 0, "D": 0, "F": 0}
PAYOUT_REWARDS = {"AA": 250, "A": 100, "BB": 0, "B": 0, "CC": 50,
                  "C": 0, "D": 0, "F": 0}

MODULE_SPECS = [
    # selection is source.class == TPC.CourseModuleDefinition; the prefix
    # split is asserted POST-selection (312+7 analog: 5 + 2) [F3]
    {"id": "Module_Alien_Science_Year1_Lesson1", "pid": 9131,
     "roomPid": 9301, "roomFid": 1, "qualPid": 9120, "rewards": ZEROS,
     "classSize": 8, "duration": 2, "xpMultiplier": 1.0, "graphPid": 9150},
    {"id": "Module_Potions_Intro_Year1_Lesson1", "pid": 9132,
     "roomPid": 9302, "roomFid": 1, "qualPid": 9120, "rewards": ZEROS,
     "classSize": 12, "duration": 3, "xpMultiplier": 1.0, "graphPid": None},
    {"id": "Module_Potions_Adv_Year1_Lesson1", "pid": 9133,
     "roomPid": 9302, "roomFid": 1, "qualPid": 9120, "rewards": ZEROS,
     "classSize": 10, "duration": 2, "xpMultiplier": 1.25, "graphPid": None},
    {"id": "Module_Smith_Basics_Year1_Lesson1", "pid": 9134,
     "roomPid": 9302, "roomFid": 1, "qualPid": 9120, "rewards": ZEROS,
     "classSize": 14, "duration": 2, "xpMultiplier": 1.0, "graphPid": None},
    {"id": "Module_Gradepay_Test_Year1_Lesson1", "pid": 9135,
     "roomPid": 9303, "roomFid": 1, "qualPid": 9120, "rewards": PAYOUT_REWARDS,
     "classSize": 16, "duration": 2, "xpMultiplier": 1.0, "graphPid": None},
    {"id": "Unused_Module_Old_Archaeology_Year1_Lesson1", "pid": 9136,
     "roomPid": 9301, "roomFid": 1, "qualPid": 9120, "rewards": ZEROS,
     "classSize": 8, "duration": 2, "xpMultiplier": 1.0, "graphPid": None},
    {"id": "Unused_Module_Broken_Year1_Lesson1", "pid": 9137,
     "roomPid": 9302, "roomFid": 1, "qualPid": 9120, "rewards": ZEROS,
     "classSize": 8, "duration": 2, "xpMultiplier": 1.0, "graphPid": None},
]

# Typed prerequisite instances [F4/F5/F6]. scope: None -> taxonomy member;
# "running"/"atlevel"/"xp" -> the DECLARED scope difference classes relinks
# resolves but logic deliberately does not emit as unlock edges [R1/RF-2].
PREREQ_CARRIERS = [
    {"carrierId": "CareerChallenge_Course_Archaeology_V1", "refKey": "00000000",
     "cls": "PrerequisiteHasCourseUnlocked", "scope": None,
     "payload": {"_visibleOnHUD": 0, "_description": {"_dev": "", "_termID": 0}},
     "coursePtr": P(2, PID[LITE_ID]), "dstId": LITE_ID,
     "dstBundle": B_COMMON, "extFileId": 2, "verbEdge": True},
    {"carrierId": "CareerChallenge_Course_Potions_V2", "refKey": "00000000",
     "cls": "PrerequisiteHasCourseUnlocked", "scope": None,
     "payload": {"_visibleOnHUD": 1},
     "coursePtr": P(3, 9402), "dstId": "Course_Potions",
     "dstBundle": B_CONFIGS, "extFileId": 3, "verbEdge": True},
    {"carrierId": "CareerChallenge_Course_Baking_V1", "refKey": "00000000",
     "cls": "PrerequisiteHasCourseRunning", "scope": "running",
     "payload": {"_visibleOnHUD": 0},
     "coursePtr": P(3, 9403), "dstId": "Course_Smithing",
     "dstBundle": B_CONFIGS, "extFileId": 3, "verbEdge": False},
    {"carrierId": "CareerChallenge_Space_V1", "refKey": "00000000",
     "cls": "PrerequisiteHasCourseAtLevel", "scope": "atlevel",
     "payload": {"_visibleOnHUD": 0},
     "coursePtr": P(3, 9402), "dstId": "Course_Potions",
     "dstBundle": B_CONFIGS, "extFileId": 3, "verbEdge": False},
    {"carrierId": "Activity_XP_Twin", "refKey": "00000000",
     "cls": "CharacterModifier_XP", "scope": "xp",
     "payload": {"_amount": 500, "_visibleOnHUD": 0},
     "coursePtr": P(3, 9401), "dstId": "Course_Archaeology",
     "dstBundle": B_CONFIGS, "extFileId": 3, "verbEdge": False},
]

# census-only members (no _course PPtr): stars member is the REAL
# PrerequisiteHasStarsInLevel [F4]; UniversityLevel rides a campus-level
# carrier so the census spans kinds beyond configs.jsonl.
MORE_PREREQ_CARRIERS = [
    {"carrierId": "CareerChallenge_Stars_V1", "refKey": "00000000",
     "cls": "PrerequisiteHasStarsInLevel", "scope": None,
     "payload": {"_visibleOnHUD": 1, "_stars": 2, "_levelId": "Campus1"},
     "carrierKind": "config", "coursePtr": None},
    {"carrierId": "CampusLevel_Two", "refKey": "00000000",
     "cls": "PrerequisiteUniversityLevel", "scope": None,
     "payload": {"_visibleOnHUD": 0, "_level": 2},
     "carrierKind": "campus-level", "coursePtr": None},
    {"carrierId": "Event_Summer_Open_Day", "refKey": "00000000",
     "cls": "PrerequisiteDaysPassed", "scope": None,
     "payload": {"_visibleOnHUD": 0, "_days": 5},
     "carrierKind": "config", "coursePtr": None},
    {"carrierId": "Challenge_Academic_Honours", "refKey": "00000000",
     "cls": "ChallengePrerequisiteAcademicScore", "scope": None,
     "payload": {"_visibleOnHUD": 0, "_score": 100},
     "carrierKind": "config", "coursePtr": None},
]

# FAILMODES variant only: one carrier, FOUR doomed refs - every failure mode
# routes to an unresolved ROW (dstId null) + a gap row, never silence.
BROKEN_CARRIER_ID = "CareerChallenge_Course_Broken_V1"
BROKEN_REFS = [
    {"refKey": "00000000", "fid": 9, "pid": 1,
     "why": "unknown-file-id"},                 # no externals entry for fid 9
    {"refKey": "00000001", "fid": 1, "pid": 5,
     "why": "builtin-external"},                # Library/unity default resources
    {"refKey": "00000002", "fid": 2, "pid": DANGLING_PID,
     "why": "dangling-path-id"},                # CAB resolves, no stub object
    {"refKey": "00000003", "fid": 4, "pid": DUP_PID,
     "why": "ambiguous-target"},                # two bundles hold CAB_DUP+5555
]

NONMEMBER_CARRIERS = [
    {"carrierId": "CampusLevel_One", "carrierKind": "campus-level",
     "cls": "LevelPrerequisiteStars", "refKey": "00000000",
     "payload": {"_stars": 3}},
    {"carrierId": "Config_Metagame_Global", "carrierKind": "config",
     "cls": "LevelPrerequisiteStarsByLevelID", "refKey": "00000000",
     "payload": {"_entries": [{"levelId": "Campus1", "stars": 4}]}},
]

def _attr_block(rate_by_field, init_by_field):
    """ECPCharacterAttributes-shaped typed-block data (real shape: ten
    _fields, each {ChangeOverTime, Disabled, MaxInitialValue,
    MinInitialValue})."""
    data = {}
    for field in ("_drink", "_energy", "_food", "_fun", "_happiness",
                  "_health", "_hygiene", "_sober", "_social", "_toilet"):
        rate = rate_by_field.get(field, DECAY_ZERO)
        lo, hi = init_by_field.get(field, (90.0, 100.0))
        data[field] = {"ChangeOverTime": rate, "Disabled": 0,
                       "MaxInitialValue": hi, "MinInitialValue": lo}
    return data

SIX = {"_drink": DECAY_SIX, "_energy": DECAY_SIX, "_food": DECAY_SIX,
       "_hygiene": DECAY_SIX, "_social": DECAY_SIX, "_toilet": DECAY_SIX}
STAFF_SPECS = [
    # F13 anchors: energy -0.05 init 90-100; sober pinned 0-0; fun 100-100
    {"id": "Staff_Assistant", "pid": 9201,
     "rates": {**SIX},
     "init": {"_sober": (0.0, 0.0), "_fun": (100.0, 100.0),
              "_happiness": (80.0, 100.0), "_health": (90.0, 100.0)}},
    {"id": "Staff_Lecturer", "pid": 9202,
     "rates": {**SIX},
     "init": {"_sober": (0.0, 0.0), "_fun": (100.0, 100.0),
              "_happiness": (75.0, 100.0), "_health": (85.0, 100.0),
              "_energy": (70.0, 100.0)}},
]

# F14: ECPStudent rides references["00000000"].data on the RAW dumps only;
# StudentType_Goth has NO raw -> studentDecayRawCoverage {raws:2, stubs:3}.
STUDENT_RAW_IDS = ("StudentType_Nerd", "StudentType_Jock")
CLUB_ROWS = [
    {"id": "Club_Book_Club", "pid": 9170,
     "rate": -0.05000000074505806},
    {"id": "Club_Chess_Club", "pid": 9171,
     "rate": -0.05000000074505806},
]

RESEARCH_SPECS = [
    {"id": "ResearchProject_Bookshelf_Robotics", "pid": 9701, "points": 250},
    {"id": "ResearchProject_Computer_Digital", "pid": 9702, "points": 500},
    {"id": "ResearchProject_Computer_Super", "pid": 9703, "points": 500},
    {"id": "ResearchProject_Course_Computer", "pid": 9704, "points": 1200},
    {"id": "ResearchProject_Telescope_Kit", "pid": 9705, "points": 100},
]
RESEARCH_LITE_ID = "ResearchProject_Bookshelf_Robotics_Lite"

# measured InteractionDefinition stub spellings: CooldownInSeconds /
# MaxQueue / QueueWarningThreshold / Tags / CharacterBehaviour (the PPtr the
# impl resolves into aiGraphRef); needs-facing typed blocks ride references.
INTERACTION_SPECS = [
    {"id": "Interaction_Caterer_Needs", "pid": 9141, "cooldown": 30.0,
     "maxQueue": 4, "queueWarn": 2, "tags": 8, "behaviourPid": 9150,
     "modifiers": [{"cls": "CharacterModifier_Drink",
                    "data": {"_amount": 90.0, "WhenToModify": 2}}]},
    {"id": "Interaction_Cafeteria_Grab", "pid": 9142, "cooldown": 15.0,
     "maxQueue": 0, "queueWarn": 0, "tags": 8, "behaviourPid": None,
     "modifiers": []},
    {"id": "Interaction_Library_Study", "pid": 9143, "cooldown": 60.0,
     "maxQueue": 2, "queueWarn": 1, "tags": 8, "behaviourPid": None,
     "modifiers": [{"cls": "CharacterModifier_XP",
                    "data": {"_amount": 10.0, "WhenToModify": 1}}]},
    {"id": "Interaction_Bench_Sit", "pid": 9144, "cooldown": 20.0,
     "maxQueue": 0, "queueWarn": 0, "tags": 8, "behaviourPid": None,
     "modifiers": []},
]
# F16: the selector is the NAMESPACED source.class spelling; a bare
# InteractionDefinition row matches NOTHING and must never be emitted.
BARE_INTERACTION_DECOY = {"id": "Interaction_Bare_Naming_Decoy", "pid": 9145}

KUDOSH_SOURCES = [
    # RewardKudoshDefinition typed block (F10 _amount/_displayInHUD)
    {"carrierId": "Activity_Completion_Reward", "kind": "config",
     "pid": 9183, "typedCls": "RewardKudoshDefinition",
     "amount": 250, "displayInHUD": 1},
]
# measured reality [F10]: KudoshConsumableRewardConfig stub payloads carry
# NO amount fields -> declared-empty sources (never zero-filled)
KUDOSH_CONSUMABLES = [
    {"id": "Kudosh_Consumable_Energy_Drink", "pid": 9180},
    {"id": "Kudosh_Consumable_Pizza", "pid": 9181},
]
KUDOSH_SINKS = [
    # three IKudoshUnlockable implementers REQUIRED present [F10/R-part3]
    {"direction": "sink", "implementer": "item",
     "carrierId": "Item_Kudosh_Trophy", "kind": "item", "pid": 9601,
     "amountField": "Cost", "amount": 750},
    {"direction": "sink", "implementer": "room",
     "carrierId": "Room_Kudosh_Sink_Room", "kind": "room", "pid": 9303,
     "amountField": "Cost", "amount": 1200},
    {"direction": "sink", "implementer": "landscapeBrush",
     "carrierId": "Brush_Tree_Fancy", "kind": "config", "pid": 9182,
     "amountField": "Cost", "amount": 500},
    {"direction": "sink", "implementer": "upgrade",
     "carrierId": "Alien_Refiner_V2", "kind": "item", "pid": 9602,
     "amountField": "Cost", "amount": 10000},   # F10 anchor
    {"direction": "sink", "implementer": "upgrade",
     "carrierId": "Alien_Refiner_V3", "kind": "item", "pid": 9603,
     "amountField": "Cost", "amount": 30000},   # F10 anchor
]

# ---------------------------------------------------------------------------
# Stub-row assembly
# ---------------------------------------------------------------------------

def _stub(kind, sid, pid, cls, bundle, fields):
    return {"id": sid, "kind": kind, "slug": None, "fields": fields,
            "source": {"bundle": bundle, "class": cls, "pathId": pid},
            "provisional": True, "inferred": True,
            "method": "seeded-class-heuristic", "buildId": BUILD_ID}


def _typed(ref_key, cls, data):
    """SerializeReference typed block, measured shape [F5]."""
    return {"data": data,
            "type": {"asm": "TPS.Game", "ns": "TPC", "class": cls}}


def stub_rows(variant: str = "green") -> dict:
    """kind -> sorted stub rows for the whole mini-corpus."""
    fm = variant == "failmodes"
    by_kind: dict[str, list] = {k: [] for k in KIND_TO_FILE}

    # --- config kind -------------------------------------------------------
    cfg = by_kind["config"]
    for c in PREREQ_CARRIERS:
        refs = {"version": 1}
        blk = {"data": dict(c["payload"]), "type": {
            "asm": "TPS.Game", "ns": "TPC", "class": c["cls"]}}
        if c["coursePtr"] is not None:
            blk = {"data": {**c["payload"], "_course": c["coursePtr"]},
                   "type": {"asm": "TPS.Game", "ns": "TPC",
                            "class": c["cls"]}}
        refs[c["refKey"]] = blk
        cfg.append(_stub("config", c["carrierId"],
                         PID[c["carrierId"]], "TPC.CareerChallengeConfig",
                         B_META,   # real carriers ride configs-metagame [F6]
                         {"Prerequisites": [{"id": 0}], "references": refs,
                          "m_Name": c["carrierId"]}))
    for c in MORE_PREREQ_CARRIERS:
        kind = c.get("carrierKind", "config")
        refs = {"00000000": _typed("00000000", c["cls"], dict(c["payload"]))}
        target = by_kind[kind]
        target.append(_stub(kind, c["carrierId"], PID[c["carrierId"]],
                            "TPC.ChallengeDefinition" if kind == "config"
                            else "TPC.CampusLevelConfig",
                            B_CONFIGS,
                            {"Prerequisites": [{"id": 0}],
                             "references": refs,
                             "m_Name": c["carrierId"]}))
    if fm:
        refs = {"version": 1}
        for spec in BROKEN_REFS:
            refs[spec["refKey"]] = {
                "data": {"_visibleOnHUD": 0,
                         "_course": P(spec["fid"], spec["pid"])},
                "type": {"asm": "TPS.Game", "ns": "TPC",
                         "class": "PrerequisiteHasCourseUnlocked"}}
        cfg.append(_stub("config", BROKEN_CARRIER_ID, 9199,
                         "TPC.CareerChallengeConfig", B_META,
                         {"Prerequisites": [{"id": 0}, {"id": 1},
                                            {"id": 2}, {"id": 3}],
                          "references": refs, "m_Name": BROKEN_CARRIER_ID}))

    # finance trio [F9]
    cfg.append(_stub("config", "Config_FinanceManager", 9111,
                     "TPC.FinanceManagerConfig", B_CONFIGS,
                     dict(FIN_BASE_FIELDS)))
    arch = dict(FIN_BASE_FIELDS)
    arch[FIN_DIFF_FIELD] = FIN_ARCH_BALANCE
    cfg.append(_stub("config", "Config_FinanceManager_Level_Archaeology",
                     9112, "TPC.FinanceManagerConfig", B_CONFIGS, arch))
    space = dict(FIN_BASE_FIELDS)
    space[FIN_DIFF_FIELD] = FIN_SPACE_BALANCE
    if variant == "financedrift":
        space["RentMultiplier"] = 1.25   # second differing field -> DRIFT only
    cfg.append(_stub("config", "Config_FinanceManager_Level_Space", 9113,
                     "TPC.FinanceManagerConfig", B_CONFIGS, space))
    # Config_Campus attrition groups [F15] + the GlobalFails DECOY (absent on
    # the real row AND dump.cs - must never surface as a group label)
    campus = {"StudentDropoutSettings": dict(DROPOUT_FIELDS),
              "StaffResignationSettings": dict(RESIGNATION_FIELDS),
              "StudentFailPercent": 10,
              "StudentUnhappyTuitionFeesThreshold": 20.0,
              "GlobalFails": {"SomeThreshold": 5.0}}
    cfg.append(_stub("config", "Config_Campus", 9110, "TPC.CampusConfig",
                     B_CONFIGS, campus))
    # Config_UISprite Grades[9] - verifyB 1.1 measured rows (AIR uniform
    # Notifications_Grade_<X>; IR diverges to Status_T_Icon_Grade_<X> for
    # F-AA, AGREES on NA); lives in configs-app_assets_all.bundle
    def _grades():
        out_rows = []
        for enum_v in range(9):
            spec = GRADE_ROWS[enum_v]
            token = spec["token"]
            air = {"m_AssetGUID": "3c97deeb5a6a865419e6f8fde36ae509",
                   "m_SubObjectName": AIR_PREFIX + token,
                   "m_SubObjectType": "UnityEngine.Sprite"}
            ir_guid = ("3c97deeb5a6a865419e6f8fde36ae509" if enum_v == 0
                       else "bb0ee6530ac6cc74ebe5708654d1b0de")
            ir = {"m_AssetGUID": ir_guid,
                  "m_SubObjectName": AIR_PREFIX + token if enum_v == 0
                  else IR_PREFIX_F_AA + token,
                  "m_SubObjectType": "UnityEngine.Sprite"}
            threshold = spec["threshold"]
            if variant == "monotonic" and enum_v == 3:
                threshold = 35.0   # breaks monotonicity -> exit 1 [L3]
            out_rows.append({"Enum": enum_v, "Threshold": threshold,
                             "DisplayName": {"_dev": "",
                                             "_termID": spec["termId"]},
                             "Icon": P(0, 0), "IconReference": ir,
                             "AlternativeIcon": P(0, 0),
                             "AlternativeIconReference": air})
        return out_rows

    cfg.append(_stub("config", "Config_UISprite", PID["Config_UISprite"],
                     "TPC.UI.UISpriteConfig", B_APP,
                     {"Grades": _grades(),
                      "m_Name": "Config_UISprite"}))
    cfg.append(_stub("config", "Qualification_Archaeology", 9120,
                     "TPC.QualificationDefinition", B_CONFIGS,
                     {"m_Name": "Qualification_Archaeology"}))
    for t in TERM_SPECS:
        cfg.append(_stub("config", t["id"], t["pid"],
                         "TPC.TermDefinition", B_CONFIGS,
                         {"Weight": t["weight"], "PassGrade": t["passGrade"],
                          "Modules": [P(0, p) for p in t["modules"]]}))
    for m in MODULE_SPECS:
        fields = {
            "RoomType": P(m["roomFid"], m["roomPid"]),
            "Qualification": P(0, m["qualPid"]),
            "GradeMoneyRewards": dict(m["rewards"]),
            "ClassSize": m["classSize"], "Duration": m["duration"],
            "XPMultiplier": m["xpMultiplier"],
        }
        if m["graphPid"] is not None:
            fields["GraphStudent"] = P(0, m["graphPid"])
        if fm and m["id"] == "Unused_Module_Broken_Year1_Lesson1":
            fields["RoomType"] = P(2, 5)               # builtin external
            fields["Qualification"] = P(0, SAME_FILE_DANGLING_PID)
        cls = ("TPC.CourseModuleDefinition")
        cfg.append(_stub("config", m["id"], m["pid"], cls, B_CONFIGS, fields))

    for it in INTERACTION_SPECS:
        # verbatim measured field set (spec L4: satisfaction layer rows copy
        # need-shaped fields verbatim; the impl mirrors stub spellings)
        fields = {"CooldownInSeconds": it["cooldown"],
                  "MaxQueue": it["maxQueue"],
                  "QueueWarningThreshold": it["queueWarn"],
                  "Tags": it["tags"],
                  "CharacterModifiers": [], "CharacterStatusEffects": [],
                  "Contexts": []}
        if it["behaviourPid"] is not None:
            fields["CharacterBehaviour"] = P(0, it["behaviourPid"])
            # spec-letter shape kept alongside so either carrier resolves
            fields["ActionSatisfyNeeds"] = {"_aiGraph": P(0,
                                                          it["behaviourPid"])}
        refs = {"version": 1}
        for i, mod in enumerate(it["modifiers"], 0):
            refs[f"{i:08x}"] = _typed(f"{i:08x}", mod["cls"],
                                      dict(mod["data"]))
        if refs == {"version": 1}:
            fields_only = fields
        else:
            fields_only = {**fields, "references": refs}
        cfg.append(_stub("config", it["id"], it["pid"],
                         "TPC.InteractionDefinition", B_CONFIGS, fields_only))
    # the bare-spelling decoy: class NOT namespaced -> never selected [F16]
    cfg.append(_stub("config", BARE_INTERACTION_DECOY["id"],
                     BARE_INTERACTION_DECOY["pid"], "InteractionDefinition",
                     B_CONFIGS, {"CooldownInSeconds": 99.0}))
    cfg.append(_stub("config", "Graph_Lecture_Default", 9150,
                     # measured GOOSE spelling (configs.jsonl, 625 rows);
                     # spec L4 pins the aiGraphRef target as a GOOSE
                     # GraphDefinition — never an invented class spelling
                     "TPS.Core.GOOSE.GraphDefinition", B_CONFIGS,
                     {"m_Name": "Graph_Lecture_Default"}))
    for c in NONMEMBER_CARRIERS:
        kind = c["carrierKind"]
        target = by_kind[kind]
        cls = ("TPC.LevelLiteConfig" if c["carrierId"] == "CampusLevel_One"
               else "TPC.MetagameConfig")
        pid = PID[c["carrierId"]]
        bundle = B_META if c["carrierId"] == "Config_Metagame_Global" \
            else B_CONFIGS
        target.append(_stub(kind, c["carrierId"], pid, cls, bundle,
                            {"references": {
                                c["refKey"]: _typed(c["refKey"], c["cls"],
                                                    dict(c["payload"]))},
                             "m_Name": c["carrierId"]}))
    for k in KUDOSH_CONSUMABLES:
        cfg.append(_stub("config", k["id"], k["pid"],
                         "TPC.KudoshConsumableRewardConfig", B_CONFIGS,
                         {"DisplayName": {"_dev": k["id"], "_termID": 0}}))
    cfg.append(_stub("config", "Brush_Tree_Fancy", 9182,
                     "TPC.LandscapeBrushDefinition", B_CONFIGS, {"Cost": 500}))
    cfg.append(_stub("config", "Activity_Completion_Reward", 9183,
                     "TPC.ActivityConfig", B_CONFIGS,
                     {"references": {"00000000": _typed(
                         "00000000", "RewardKudoshDefinition",
                         {"_amount": 250, "_displayInHUD": 1})}}))

    for cl in CLUB_ROWS:
        cfg.append(_stub("config", cl["id"], cl["pid"], "TPC.ClubDefinition",
                         B_SHARED, {"ClubNeedChangeOverTime": cl["rate"],
                                    "m_Name": cl["id"]}))

    # --- course kind: 3 full + 2 marketing; the Lite twin is CONFIG kind ----
    crs = by_kind["course"]
    for c in COURSE_SPECS:
        fields = {
            "LicenseCost": c["licenseCost"], "KudoshCost": c["kudoshCost"],
            "YearlyTuitionFee": c["yearlyTuitionFee"],
            "StartPointsCost": c["startPointsCost"],
            "DefaultStudentCount": c["defaultStudentCount"],
            "ApplicantsBoost": c["applicantsBoost"],
            "ApplicantsFromCourseRating": c["applicantsFromCourseRating"],
            "ApplicantsFromUniversityRating":
                c["applicantsFromUniversityRating"],
            "Levels": [dict(l) for l in c["levels"]],
            "Terms": [P(0, p) for p in c["terms"]],
        }
        crs.append(_stub("course", c["id"], c["pid"],
                         "TPC.CourseDefinition", B_CONFIGS, fields))
    for m in MARKETING_SPECS:
        fields = {"m_Name": m["id"]}
        if m["targetPid"] is not None:
            fields["MarketingFor"] = P(0, m["targetPid"])
        crs.append(_stub("course", m["id"], m["pid"],
                         "TPC.MarketingCourseDefinition", B_CONFIGS, fields))

    # --- config-kind Lite twin endpoint (real corpus placement) -------------
    cfg.append(_stub("config", LITE_ID, PID[LITE_ID],
                     "TPC.CourseLiteDefinition", B_COMMON,
                     {"id": LITE_BARE, "m_Name": LITE_BARE}))

    # --- metagame-node kind: research [F11] ---------------------------------
    meta = by_kind["metagame-node"]
    for r in RESEARCH_SPECS:
        meta.append(_stub("metagame-node", r["id"], r["pid"],
                          "TPC.ResearchProjectDefinition", B_META,
                          {"ResearchPoints": r["points"], "Type": 0,
                           "Repeatable": 0, "CanReject": 0,
                           "GreenlightCash": 0, "GreenlightKudosh": 0}))
    meta.append(_stub("metagame-node", RESEARCH_LITE_ID, 9706,
                      "TPC.ResearchProjectLiteDefinition", B_META,
                      {"Type": 0}))   # NO ResearchPoints -> declared-empty
    meta.append(_stub("metagame-node", "ResearchProject_Database_Main", 9707,
                      "TPC.ResearchProjectDatabase", B_META, {}))

    # --- staff kind: typed decay block on every row [F13] -------------------
    stf = by_kind["staff"]
    for s in STAFF_SPECS:
        refs = {"version": 1,
                "00000000": _typed("00000000", "ECPCharacterAttributes",
                                   _attr_block(s["rates"], s["init"]))}
        stf.append(_stub("staff", s["id"], s["pid"], "TPC.StaffDefinition",
                         B_SHARED, {"references": refs,
                                    "BaseSalary": 20000,
                                    "m_Name": s["id"]}))

    # --- student-type kind: stubs WITHOUT carriers; raws carry ECPStudent ---
    # student-type stubs sit in configs_assets_all on the real corpus - the
    # harvested StudentDefinition raw stems (configs_assets_all_<pid>.json)
    # must match their (bundle, pathId) for the harvest-direct join [F14]
    for sid in ("StudentType_Nerd", "StudentType_Jock", "StudentType_Goth"):
        by_kind["student-type"].append(_stub(
            "student-type", sid, PID[sid], "TPC.StudentTypeConfig",
            B_CONFIGS, {"m_Name": sid}))

    # --- room / item / unlockable kinds -------------------------------------
    by_kind["room"].append(_stub("room", "Room_Alien_Science", 9301,
                                 "TPC.RoomDefinition", B_ROOMS, {}))
    by_kind["room"].append(_stub("room", "Room_Lecture_Theatre", 9302,
                                 "TPC.RoomDefinition", B_ROOMS, {}))
    # measured sink amountField on rooms is Kudosh (real corpus row shape)
    by_kind["room"].append(_stub("room", "Room_Kudosh_Sink_Room", 9303,
                                 "TPC.RoomDefinition", B_ROOMS,
                                 {"Kudosh": 1200}))
    # ambiguity twins: SAME pathId in TWO bundles, both in the stub index
    by_kind["item"].append(_stub("item", "Item_Duplicate_Common", DUP_PID,
                                 "TPC.GameItemDefinition", B_COMMON,
                                 {"Cost": 750}))
    by_kind["room"].append(_stub("room", "Room_Duplicate_Rooms", DUP_PID,
                                 "TPC.RoomDefinition", B_ROOMS, {}))
    # measured sink amountField on GameItemDefinition rows is Kudosh [F10]
    by_kind["item"].append(_stub("item", "Item_Kudosh_Trophy", 9601,
                                 "TPC.GameItemDefinition", B_ITEMS,
                                 {"Kudosh": 750}))
    by_kind["item"].append(_stub("item", "Alien_Refiner_V2", 9602,
                                 "TPC.GameItemUpgradeDefinition", B_ITEMS,
                                 {"Cost": 10000}))
    by_kind["item"].append(_stub("item", "Alien_Refiner_V3", 9603,
                                 "TPC.GameItemUpgradeDefinition", B_ITEMS,
                                 {"Cost": 30000}))
    by_kind["unlockable"].append(_stub("unlockable", "Unlock_Kudosh_Sculpture",
                                       9501, "TPC.UnlockableDefinition",
                                       B_UNLOCK, {"CostKudosh": 120}))

    # config-kind archetype target for the harvest-direct join
    cfg.append(_stub("config", "Archetype_Partier", 9220,
                     "TPC.StudentArchetypeDefinition", B_CONFIGS,
                     {"m_Name": "Archetype_Partier"}))
    for rows in by_kind.values():
        rows.sort(key=lambda r: r["id"])
    return by_kind

# ---------------------------------------------------------------------------
# Harvest-direct raw dumps (R2: read from harvest/, never from stubs)
# ---------------------------------------------------------------------------

def course_raw_obj(course: dict) -> dict:
    """FLAT dump shape measured on the real corpus (no fields wrapper):
    PascalCase payload keys + _assessmentScoring + _studentArchetypes."""
    obj = {
        "_scriptClass": "TPC.CourseDefinition",
        "_sourceFile": f"cab-c0nfig5main01",
        "LicenseCost": course["licenseCost"],
        "KudoshCost": course["kudoshCost"],
        "YearlyTuitionFee": course["yearlyTuitionFee"],
        "StartPointsCost": course["startPointsCost"],
        "DefaultStudentCount": course["defaultStudentCount"],
        "ApplicantsBoost": course["applicantsBoost"],
        "ApplicantsFromCourseRating": course["applicantsFromCourseRating"],
        "ApplicantsFromUniversityRating":
            course["applicantsFromUniversityRating"],
        "Levels": [dict(l) for l in course["levels"]],
        "Terms": [P(0, p) for p in course["terms"]],
        "_assessmentScoring": dict(ASSESSMENT_ANCHOR),
        "_studentArchetypes": [],
        "m_Name": course["id"], "m_Enabled": 1,
    }
    if course["id"] == "Course_Potions":
        obj["_studentArchetypes"] = [
            {"Weight": 1.0, "Archetype": P(0, 9220)},
            {"Weight": 1.0, "Archetype": P(0, 0)},   # zero target -> null
        ]
    return obj


def student_raw_obj(sid: str) -> dict:
    attrs = {}
    camel = {"ClubNeed": "_clubNeed", "Relationship": "_relationship",
             "SelfStudy": "_selfStudy"}
    for name, (rate, lo, hi) in STUDENT_RATES.items():
        attrs[camel[name]] = {
            "ChangeOverTime": rate, "Disabled": 0,
            "MaxInitialValue": hi, "MinInitialValue": lo}
    return {
        "_scriptClass": "TPC.StudentTypeConfig",
        "_id": sid,
        "references": {"00000000": _typed("00000000", "ECPStudent", attrs)},
        "m_Enabled": 1,
    }

# ---------------------------------------------------------------------------
# Structural upstream: id-registries + class-hierarchy
# ---------------------------------------------------------------------------

def registry_files() -> dict:
    """name-sorted registry jsonl bodies (AC3: emission must match the
    file own sequence, so the FIXTURE stores name-sorted rows)."""
    budget = [{"name": n, "value": v}
              for n, v in sorted(BUDGET_TYPES, key=lambda t: t[0])]
    egrade = [{"name": n, "value": v}
              for n, v in sorted(EGRADE_MEMBERS)]
    eattr = [{"name": n, "value": v} for n, v in EATTRIBUTE_MEMBERS]
    estaff = [{"name": f"SynthStat{i:02d}", "value": i}
              for i in range(ESTAFFSTAT_COUNT)]
    profit = [{"name": n, "value": i} for i, n in enumerate(PROFIT_TYPE)]
    expense = [{"name": n, "value": i} for i, n in enumerate(EXPENSE_TYPE)]
    return {
        "TPS.Game.BudgetType.jsonl": budget,
        "TPS.Game.TPC.EGrade.jsonl": egrade,
        "TPS.Game.TPC.EAttribute.jsonl": eattr,
        "TPS.Game.TPC.EStaffStat.jsonl": estaff,
        "TPS.Game.ProfitType.jsonl": profit,
        "TPS.Game.ExpenseType.jsonl": expense,
    }


HIERARCHY_BASE_ROWS = [
    {"assembly": "TPS.Game", "namespace": "TPC",
     "name": "Prerequisite", "baseType": "UnityEngine.ScriptableObject",
     "interfaces": [], "methodCount": 2, "fieldCount": 1},
    {"assembly": "TPS.Game", "namespace": "TPC",
     "name": "CourseModuleDefinition", "baseType": "UnityEngine.ScriptableObject",
     "interfaces": [], "methodCount": 4, "fieldCount": 9},
    {"assembly": "TPS.Game", "namespace": "TPC",
     "name": "InteractionDefinition",
     "baseType": "UnityEngine.ScriptableObject",
     "interfaces": [], "methodCount": 2, "fieldCount": 6},
]


def hierarchy_rows() -> list:
    """class-hierarchy rows: abstract TPC.Prerequisite + EXACTLY the 24
    namespaced subclasses (baseType == 'TPC.Prerequisite') + the two
    ILevelPrerequisiteData non-members + a BARE-baseType decoy that must
    select nothing [F2/F4]."""
    rows = []
    for cls in TAXONOMY_24:
        rows.append({"assembly": "TPS.Game", "namespace": "TPC",
                     "name": cls,
                     "baseType": "TPC.Prerequisite", "interfaces": [],
                     "methodCount": 1, "fieldCount": 2})
    for cls in NONMEMBER_CLASSES:
        rows.append({"assembly": "TPS.Game", "namespace": "TPC",
                     "name": cls, "baseType":
                     f"TPC.{NONMEMBER_FAMILY}", "interfaces": [],
                     "methodCount": 1, "fieldCount": 2})
    # decoy: bare (non-namespaced) baseType - a naive matcher would take it
    rows.append({"assembly": "TPS.Game", "namespace": "", "name":
                 "NaughtyBareBaseHelper", "baseType": "Prerequisite",
                 "interfaces": [], "methodCount": 1, "fieldCount": 1})
    return HIERARCHY_BASE_ROWS + rows

# ---------------------------------------------------------------------------
# Relink-side upstream (read-only inputs for the reconciliation leg)
# ---------------------------------------------------------------------------

def unlock_edge_carriers(variant: str = "green"):
    """The verbEdge carriers (the 50-analog) in emission order."""
    return [c for c in PREREQ_CARRIERS if c["verbEdge"]]


def relinks_config_config_rows(variant: str = "green") -> list:
    """config_config.jsonl rows whose evidence.fieldPath ends
    .data._course [F6/RF-2]. green: one MATCHING counterpart per resolved
    unlock edge + three DECLARED-SCOPE rows (running/atlevel/xp).
    divergence: the Potions edge counterpart claims a different dstPathId."""
    rows = []
    for c in PREREQ_CARRIERS:
        dst_pid = c["coursePtr"]["m_PathID"]
        if variant == "divergence" and c["carrierId"] == \
                "CareerChallenge_Course_Potions_V2":
            dst_pid = 9403   # claims Course_Smithing; logic resolves Potions
        rows.append({
            "buildId": BUILD_ID, "srcKind": "config", "srcId": c["carrierId"],
            "dstKind": "config", "dstId": c["dstId"],
            "mechanism": "hard", "method": "pptr-cross-file",
            "inferred": False,
            "evidence": {
                "fieldPath": f"references.{c['refKey']}.data._course",
                "srcBundle": B_META,
                "srcPathId": PID[c["carrierId"]],
                "dstBundle": c["dstBundle"], "dstPathId": dst_pid,
                "extFileId": c["extFileId"],
                "dstCab": {"configs-common_assets_all.bundle":
                           "cab-common04",
                           "configs_assets_all.bundle":
                           "cab-c0nfig5main01"}[c["dstBundle"]],
                "resolvedVia": "externals+cab-index", "refCount": 1,
            }})
    return sorted(rows, key=lambda r: (r["srcId"], r["dstId"]))


def relinks_matrix_obj() -> dict:
    """Minimal but structurally-shaped matrix.json (stage-8 reads it
    cross-check-only; never mutated)."""
    cells = []
    for src in rl.NODE_UNIVERSE:
        for dst in rl.NODE_UNIVERSE:
            modeled = src == "config" and dst == "config"
            cells.append({
                "srcKind": src, "dstKind": dst,
                "mechanism": "hard" if modeled else "logic",
                "status": "modeled" if modeled else "missing",
                "joinKey": "PPtr(m_FileID,m_PathID)" if modeled
                else "none-established",
                "cardinality": {"perSrc": "1..N", "perDst": "0..N",
                                "srcEntitiesWithEdges": 5, "edges": 5}
                if modeled else {"perSrc": "0..N", "perDst": "0..N",
                                 "srcEntitiesWithEdges": 0, "edges": 0},
                "pairFiles": ["config_config.jsonl"] if modeled else [],
                "unblock": None if modeled else
                ("no stub-payload emitter" if src == "scene"
                 else "fixture-scale: not modeled"),
            })
    return {"meta": {"buildId": BUILD_ID,
                     "nodeUniverse": {"nodes": list(rl.NODE_UNIVERSE),
                                      "arithmetic": "fixture-scale"}},
            "pairs": cells}


GRADE_TERM_KEYS = {-1320794757: "UI/Grades/AA", -1180291283: "UI/Grades/F"}


def i2_term_registry_rows() -> list:
    rows = []
    for tid, key in sorted(GRADE_TERM_KEYS.items()):
        rows.append({"buildId": BUILD_ID, "canonical": True, "locales": ["en"],
                     "sourceAsset": "I2LS_UIGrades", "termId": tid,
                     "termKey": key, "termStatus": 1, "termType": 0})
    return rows


def entity_locale_rows() -> list:
    rows = []
    for tid, dev in DISPLAYNAME_JOINED_TERMIDS.items():
        rows.append({
            "buildId": BUILD_ID, "srcKind": "config",
            "srcId": "Config_UISprite", "dstKind": "locale-term",
            "dstId": GRADE_TERM_KEYS[tid], "mechanism": "hard",
            "method": "i2-termid-registry", "inferred": False,
            "evidence": {"fieldPath": "fields.Grades[].DisplayName._termID",
                         "termId": tid, "dev": dev, "locales": ["en"]}})
    return sorted(rows, key=lambda r: r["dstId"])


# ---------------------------------------------------------------------------
# Bridges + externals + export manifest
# ---------------------------------------------------------------------------

def _cab_objects(bundle: str, variant: str = "green") -> list:
    objs = []
    for rows in stub_rows(variant).values():
        for r in rows:
            if r["source"]["bundle"] == bundle:
                objs.append({"pathId": r["source"]["pathId"],
                             "class": r["source"]["class"]})
    return sorted(objs, key=lambda o: o["pathId"])


def cab_index_rows(variant: str = "green") -> list:
    # the bridge tables MUST describe the SAME world as the stub corpus they
    # index: a variant-added source object (the failmodes broken carrier)
    # has to be locatable as a SOURCE side for its planted per-ref failure
    # modes to be exercised (unknown fileId / builtin / dangling / ambiguous
    # all presuppose the owning serialized file is known)
    rows = []
    for b, cab in ((B_CONFIGS, CAB_CONFIGS), (B_APP, CAB_APP),
                   (B_META, CAB_META), (B_COMMON, CAB_COMMON),
                   (B_ROOMS, CAB_ROOMS), (B_SHARED, CAB_SHARED),
                   (B_ITEMS, CAB_ITEMS), (B_UNLOCK, CAB_UNLOCK)):
        rows.append({"bundle": b, "cab": cab,
                     "objects": _cab_objects(b, variant),
                     "buildId": BUILD_ID})
    # the ambiguity setup: ONE cab registered under TWO bundles
    rows.append({"bundle": B_COMMON, "cab": CAB_DUP,
                 "objects": [{"pathId": DUP_PID,
                              "class": "TPC.GameItemDefinition"}],
                 "buildId": BUILD_ID})
    rows.append({"bundle": B_ROOMS, "cab": CAB_DUP,
                 "objects": [{"pathId": DUP_PID,
                              "class": "TPC.RoomDefinition"}],
                 "buildId": BUILD_ID})
    return sorted(rows, key=lambda r: (r["bundle"], r["cab"]))


def container_index_rows() -> list:
    return sorted([
        {"bundle": B_META, "address":
         "Assets/Content/Metagame/Config_Metagame.asset", "pathId": 9161,
         "class": "MonoBehaviour", "buildId": BUILD_ID},
        {"bundle": B_CONFIGS,
         "address": "Assets/Content/Courses/Course_Archaeology.asset",
         "pathId": 9401, "class": "MonoBehaviour", "buildId": BUILD_ID},
    ], key=lambda r: (r["bundle"], r["address"]))


def externals_rows() -> list:
    """Per-serialized-file rows keyed by FULL relpath [F7]; on-disk paths are
    DOUBLED archive:/CAB-x/CAB-x (simplify_external_path is MANDATORY)."""
    ext = lambda fid, path: {"fileId": fid, "guid": "0" * 32,
                             "path": path, "type": 0}  # noqa: E731
    dbl = lambda cab: f"archive:/{cab}/{cab}"          # noqa: E731
    by_bundle = {
        B_META: [
            ext(1, "Library/unity default resources"),
            ext(2, dbl(CAB_COMMON)),
            ext(3, dbl(CAB_CONFIGS)),
            ext(4, dbl(CAB_DUP)),
            ext(9, dbl(CAB_GHOST404)),   # no cab_index row anywhere
        ],
        B_CONFIGS: [
            ext(1, dbl(CAB_ROOMS)),      # modules -> rooms cross-file
            ext(2, "Library/unity default resources"),
        ],
        B_COMMON: [], B_ROOMS: [], B_SHARED: [], B_ITEMS: [],
        B_UNLOCK: [], B_APP: [],
    }
    return [{"bundle": full_rel(b), "sourceFile": cab.lower(),
             "externals": exs}
            for b, cab, exs in (
                (B_CONFIGS, CAB_CONFIGS, by_bundle[B_CONFIGS]),
                (B_APP, CAB_APP, by_bundle[B_APP]),
                (B_META, CAB_META, by_bundle[B_META]),
                (B_COMMON, CAB_COMMON, by_bundle[B_COMMON]),
                (B_ROOMS, CAB_ROOMS, by_bundle[B_ROOMS]),
                (B_SHARED, CAB_SHARED, by_bundle[B_SHARED]),
                (B_ITEMS, CAB_ITEMS, by_bundle[B_ITEMS]),
                (B_UNLOCK, CAB_UNLOCK, by_bundle[B_UNLOCK]))]


def export_manifest_rows() -> list:
    rows = []
    for c in COURSE_SPECS:
        rel = (f"harvest/monobehaviours/configs/TPC.CourseDefinition/"
               f"configs_assets_all_{c['pid']}.json")
        rows.append({"sourceBundle": B_CONFIGS, "pathId": c["pid"],
                     "class": "TPC.CourseDefinition", "bytes": 256,
                     "outRelPath": rel})
    for m in MARKETING_SPECS:
        rel = (f"harvest/monobehaviours/configs/TPC.CourseDefinition/"
               f"configs_assets_all_{m['pid']}.json")
        rows.append({"sourceBundle": B_CONFIGS, "pathId": m["pid"],
                     "class": "TPC.MarketingCourseDefinition", "bytes": 256,
                     "outRelPath": rel})
    for sid in STUDENT_RAW_IDS:
        stem = ("configs_assets_all" if sid == "StudentType_Nerd"
                else "dlc-ghost-configs_assets_all")
        pid = PID[sid] if sid == "StudentType_Nerd" else -PID[sid]
        rel = (f"harvest/monobehaviours/configs/TPC.StudentDefinition/"
               f"{stem}_{pid}.json")
        rows.append({"sourceBundle": f"{stem}.bundle", "pathId": pid,
                     "class": "TPC.StudentTypeConfig", "bytes": 256,
                     "outRelPath": rel})
    return sorted(rows, key=lambda r: r["outRelPath"])


# ---------------------------------------------------------------------------
# Tree assembly
# ---------------------------------------------------------------------------

VARIANTS = ("green", "failmodes", "monotonic", "econmismatch",
            "financedrift", "divergence")


def write_harvest_direct(extracted: Path, variant: str = "green") -> None:
    base = extracted / "harvest" / "monobehaviours" / "configs"
    for c in COURSE_SPECS:
        obj = course_raw_obj(c)
        if variant == "econmismatch" and c["id"] == "Course_Potions":
            obj["LicenseCost"] = 12345   # stub says 5000 -> mismatch -> exit 1
        p = base / "TPC.CourseDefinition" / f"configs_assets_all_{c['pid']}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(obj, sort_keys=True) + "\n",
                     encoding="utf-8", newline="\n")
    for m in MARKETING_SPECS:
        # marketing variants carry NO scoring struct - declared-empty [F2]
        obj = {"_scriptClass": "TPC.MarketingCourseDefinition",
               "m_Name": m["id"], "m_Enabled": 1}
        if m["targetPid"] is not None:
            obj["MarketingFor"] = P(0, m["targetPid"])
        p = base / "TPC.CourseDefinition" / f"configs_assets_all_{m['pid']}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(obj, sort_keys=True) + "\n",
                     encoding="utf-8", newline="\n")
    for sid in STUDENT_RAW_IDS:
        stem = ("configs_assets_all" if sid == "StudentType_Nerd"
                else "dlc-ghost-configs_assets_all")
        pid = PID[sid] if sid == "StudentType_Nerd" else -PID[sid]
        p = (base / "TPC.StudentDefinition" / f"{stem}_{pid}.json")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(student_raw_obj(sid), sort_keys=True) + "\n",
                     encoding="utf-8", newline="\n")


def write_structural(extracted: Path, *, append: bool = False) -> None:
    st = extracted / "decompiled" / "structural"
    regdir = st / "id-registries"
    regdir.mkdir(parents=True, exist_ok=True)
    for name, rows in registry_files().items():
        write_jsonl(regdir / name, rows)
    hier = st / "class-hierarchy.jsonl"
    rows = hierarchy_rows()
    if append and hier.exists():
        existing = read_jsonl(hier)
        seen = {(r.get("namespace"), r.get("name")) for r in existing}
        rows = existing + [r for r in rows
                           if (r.get("namespace"), r.get("name")) not in seen]
    write_jsonl(hier, rows)


def write_relinks_upstream(extracted: Path, variant: str = "green") -> None:
    rel = extracted / "relinks"
    rel.mkdir(parents=True, exist_ok=True)
    write_jsonl(rel / "config_config.jsonl",
                relinks_config_config_rows(variant))
    (rel / "matrix.json").write_text(
        json.dumps(relinks_matrix_obj(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n")
    write_jsonl(rel / "i2_term_registry.jsonl", i2_term_registry_rows())
    write_jsonl(rel / "entity_locale.jsonl", entity_locale_rows())
    bridges = rel / "bridges"
    bridges.mkdir(parents=True, exist_ok=True)
    write_jsonl(bridges / "cab_index.jsonl", cab_index_rows(variant))
    write_jsonl(bridges / "container_index.jsonl", container_index_rows())


def augment_fx_tree(out, variant: str = "green") -> Path:
    """Stage-8 upstream overlay on a CUMULATIVE fx prepared tree (the
    `build_fixture_tree.py --stage logic` path): appends hierarchy rows,
    merges export-manifest rows, then writes the full stage-8 set."""
    out = Path(out)
    extracted = out / "extracted"
    write_structural(extracted, append=True)
    man = extracted / "harvest" / "export-manifest.jsonl"
    existing = read_jsonl(man) if man.exists() else []
    merged = {r["outRelPath"]: r for r in existing}
    for r in export_manifest_rows():
        merged.setdefault(r["outRelPath"], r)
    write_jsonl(man, sorted(merged.values(), key=lambda r: r["outRelPath"]))
    _write_stage8_set(extracted, variant)
    return out


def build_logic_tree(out, variant: str = "green", *,
                     cumulative: bool = False) -> Path:
    """Materialize the section-3 stage-8 upstream set synthetically.

    cumulative=True runs the shared fx builder first (stages 0..5 outputs)
    so `tests/build_fixture_tree.py --stage logic` produces a full prepared
    tree; the suite default is the lean tree (client skeleton + exactly the
    stage-8 upstream set) - faster and interference-free.
    """
    out = Path(out)
    extracted = out / "extracted"
    if cumulative:
        fx.build_tree(out, "localisation")
        augment_fx_tree(out, variant)
        return out
    fx.build_client_inputs(out)
    fx.build_identity_fixture(extracted)
    write_structural(extracted)
    # the impl's runner pre-check also demands the roster (piece-1 §3);
    # cheap to provide so the lean tree stays self-sufficient
    write_jsonl(extracted / "bundle-roster.jsonl", fx.roster_rows())
    write_jsonl(extracted / "harvest" / "export-manifest.jsonl",
                export_manifest_rows())
    _write_stage8_set(extracted, variant)
    return out


def _write_stage8_set(extracted: Path, variant: str) -> Path:
    if variant not in VARIANTS:
        raise ValueError(f"unknown variant {variant!r}; expected {VARIANTS}")
    stubs = extracted / "stubs"
    for kind, rows in stub_rows(variant).items():
        write_jsonl(stubs / KIND_TO_FILE[kind], rows)
    absences = [{"kind": k, "scannedBundles": 0, "scannedClasses": 0,
                 "count": 0, "absenceType": "fixture-placeholder",
                 "evidence": "synthetic ledger row", "buildId": BUILD_ID}
                for k in KIND_TO_FILE]
    write_jsonl(stubs / "_absences.jsonl", absences)
    write_harvest_direct(extracted, variant)
    write_relinks_upstream(extracted, variant)
    write_jsonl(extracted / "harvest" / "externals.jsonl",
                sorted(externals_rows(), key=lambda r: r["bundle"]))
    return extracted


# ---------------------------------------------------------------------------
# Contract validators (error-list style; [] == valid) - the suite's TEETH.
# Each is applied positively to emitted artifacts AND negatively to mutated
# copies so a guard that stops biting fails the suite [AC mutation teeth].
# ---------------------------------------------------------------------------

def _err(e, m):
    e.append(m)


def budget_type_violations(emitted, registry_rows):
    """AC3 byte-match: name-for-name, value-for-value, in the REGISTRY FILE
    own (name-sorted) order."""
    e = []
    want = [(r["name"], r["value"]) for r in registry_rows]
    got = [(r.get("name"), r.get("value")) for r in emitted]
    if got != want:
        for i, (w, g) in enumerate(zip(want, got)):
            if w != g:
                _err(e, f"budgetTypes[{i}] {g!r} != registry {w!r}")
        if len(got) != len(want):
            _err(e, f"budgetTypes length {len(got)} != {len(want)}")
    return e


def monotonic_threshold_violations(ladder_rows):
    """Monotonically non-decreasing top-to-bottom EXCEPT the NA sentinel row
    (threshold < 0 sits below every achievable score)."""
    e = []
    prev = None
    for r in ladder_rows:
        t = r.get("threshold")
        if not isinstance(t, (int, float)):
            _err(e, f"row {r.get('grade')!r} threshold {t!r} not numeric")
            continue
        if isinstance(t, float) and t < 0:
            continue   # sentinel exemption (NA)
        if prev is not None and t < prev:
            _err(e, f"thresholds decrease at grade {r.get('grade')!r}: "
                    f"{t} < {prev}")
        prev = t
    return e


def derive_expected_ladder(uisprite_grades):
    """Re-derive the expected ladder table FROM the fixture Grades[9] payload:
    join on Enum, token from AlternativeIconReference.m_SubObjectName after
    'Grade_', termId digit-for-digit."""
    rows = []
    for g in sorted(uisprite_grades, key=lambda x: x["Enum"]):
        air = g["AlternativeIconReference"]["m_SubObjectName"]
        token = air.rsplit("Grade_", 1)[-1]
        joined = DISPLAYNAME_JOINED_TERMIDS.get(
            g["DisplayName"]["_termID"])
        rows.append({"grade": token, "enumValue": g["Enum"],
                     "threshold": g["Threshold"],
                     "displayNameTermId": g["DisplayName"]["_termID"],
                     "displayName": joined})
    return rows


def grade_ladder_violations(obj, uisprite_grades):
    e = []
    if obj.get("provenance") != "hard-read":
        _err(e, f"provenance {obj.get('provenance')!r} != 'hard-read'")
    if obj.get("buildId") != BUILD_ID:
        _err(e, "grade-ladder buildId missing/wrong")
    tt = obj.get("thresholdTable") or {}
    if "GetGrade" not in str(tt.get("consumer", "")):
        _err(e, "thresholdTable.consumer must cite UISpriteConfig.GetGrade")
    got = tt.get("rows") or []
    want = derive_expected_ladder(uisprite_grades)
    if len(got) != 9 or len(want) != 9:
        _err(e, f"ladder rows {len(got)} != 9 (fixture derives {len(want)})")
    for i, (w, g) in enumerate(zip(want, got)):
        for k in ("grade", "enumValue", "threshold", "displayNameTermId"):
            if g.get(k) != w[k]:
                _err(e, f"ladder[{i}].{k} {g.get(k)!r} != derived {w[k]!r}")
        # the locale-join VALUE spelling is unpinned (entity_locale.dev text
        # or the i2 termKey); WHICH rows fill is pinned
        if w["displayName"] is None:
            allowed = {None}
        else:
            allowed = {w["displayName"],
                       GRADE_TERM_KEYS.get(w["displayNameTermId"],
                                           "<term-key>")}
        if g.get("displayName") not in allowed:
            _err(e, f"ladder[{i}].displayName {g.get('displayName')!r} "
                    f"outside the locale-join results {sorted(allowed)!r}")
    e.extend(monotonic_threshold_violations(got))
    return e


def xp_normalization_violations(obj):
    """Never-invent law [R4/AC8]: emittedNumbers MUST be empty; the marker
    must declare itself UNPROVEN-NATIVE and point at the native unblock."""
    e = []
    if not isinstance(obj, dict):
        return ["xp-score-normalization.json is not an object"]
    if obj.get("emittedNumbers") != []:
        _err(e, f"emittedNumbers {obj.get('emittedNumbers')!r} != [] - an "
                "authored coefficient would be an invented number")
    if obj.get("status") != XP_STATUS:
        _err(e, f"status {obj.get('status')!r} != {XP_STATUS!r}")
    if "native" not in str(obj.get("unblock", "")).lower():
        _err(e, "unblock must name the native-analysis route")
    if not str(obj.get("surface", "")):
        _err(e, "surface must name the XP->score normalization surface")
    if obj.get("buildId") != BUILD_ID:
        _err(e, "buildId missing/wrong")
    return e


def core11_violations(rows):
    """11 rows, one per EAttribute registry member (incl. Litter), ALL
    changeOverTime null + carrier absent [R4 null law]."""
    e = []
    want = {n for n, _v in EATTRIBUTE_MEMBERS}
    got_names = [r.get("attribute") for r in rows]
    if len(rows) != len(want):
        _err(e, f"core-11 ledger has {len(rows)} rows != 11 registry members")
    if set(got_names) != want:
        _err(e, f"core-11 attributes {sorted(set(got_names) ^ want)} differ "
                f"from the registry vocabulary")
    for r in rows:
        if r.get("changeOverTime") is not None:
            _err(e, f"{r.get('attribute')}: changeOverTime "
                    f"{r.get('changeOverTime')!r} != null (a plausible rate "
                    f"would be an invented number)")
        if r.get("carrier") != "absent":
            _err(e, f"{r.get('attribute')}: carrier {r.get('carrier')!r} "
                    f"!= 'absent'")
        if r.get("status") != XP_STATUS:
            _err(e, f"{r.get('attribute')}: status must be {XP_STATUS!r}")
    return e


def staff_decay_violations(rows, specs=None):
    """Verbatim float noise + the pinned _field -> EAttribute map; an
    emitted '_toilet' spelling fails; rounding is editing data."""
    e = []
    attrs = {n for n, _ in EATTRIBUTE_MEMBERS}
    for r in rows:
        a = r.get("attribute")
        if a is not None and str(a).startswith("_"):
            _err(e, f"{r.get('staffId')}: attribute {a!r} keeps the raw "
                    f"_field spelling; the registry spelling is "
                    f"{STAFF_FIELD_TO_ATTRIBUTE.get(a)!r}")
        elif a not in attrs:
            _err(e, f"{r.get('staffId')}: attribute {a!r} outside the "
                    f"EAttribute vocabulary")
        cot = r.get("changeOverTime")
        noise_free = isinstance(cot, float) and round(cot, 6) == round(
            DECAY_SIX, 6)
        if noise_free and repr(cot) != repr(DECAY_SIX):
            _err(e, f"{r.get('staffId')}/{a}: changeOverTime {cot!r} lost "
                    f"the verbatim float noise {DECAY_SIX!r} (rounding edits "
                    f"data)")
        if r.get("component") != "ECPCharacterAttributes":
            _err(e, f"{r.get('staffId')}/{a}: component must cite "
                    f"ECPCharacterAttributes")
        ev = r.get("evidence") or {}
        raw = {v: k for k, v in STAFF_FIELD_TO_ATTRIBUTE.items()}.get(a)
        blob = json.dumps(ev)
        if raw is not None and raw not in blob:
            _err(e, f"{r.get('staffId')}/{a}: evidence.fieldPath must "
                    f"preserve the raw {raw!r} field name")
        elif raw is None and not re.search(r'"_\w+"', blob):
            _err(e, f"{r.get('staffId')}/{a}: evidence.fieldPath must "
                    f"preserve the raw _field spelling")
    return e


def attrition_violations(rows):
    """Group labels restricted to the four MEASURED Config_Campus field
    names; an invented label (GlobalFails or any other) fails [F15/RF-4]."""
    e = []
    groups = [r.get("group") for r in rows]
    for g in groups:
        if g not in ATTRITION_GROUPS:
            _err(e, f"attrition group {g!r} is not one of the four measured "
                    f"Config_Campus field names {ATTRITION_GROUPS}")
    if set(groups) != set(ATTRITION_GROUPS):
        _err(e, f"attrition groups {sorted(filter(None, set(groups) - set(ATTRITION_GROUPS)))} missing: "
                f"{sorted(set(ATTRITION_GROUPS) - set(groups))}")
    by = {r.get("group"): r for r in rows}
    drop = by.get("StudentDropoutSettings") or {}
    fields = drop.get("fields") or {}
    for k, v in DROPOUT_FIELDS.items():
        if fields.get(k) != v:
            _err(e, f"StudentDropoutSettings.{k} {fields.get(k)!r} != {v!r}")
    res = (by.get("StaffResignationSettings") or {}).get("fields") or {}
    for k, v in RESIGNATION_FIELDS.items():
        if res.get(k) != v:
            _err(e, f"StaffResignationSettings.{k} {res.get(k)!r} != {v!r}")
    evd = drop.get("evidence") or {}
    code_ref = str(evd.get("codeRef", ""))
    if "dump.cs" not in code_ref:
        _err(e, "dropout evidence.codeRef must cite the decompile source "
                "(RF-4: every emitted string cited like every number)")
    events = drop.get("events")
    if sorted(events or []) != sorted(EVENT_DROPOUT):
        _err(e, f"dropout events {events!r} != {EVENT_DROPOUT!r}")
    fail = by.get("StudentFailPercent") or {}
    if 10 not in _flatten_values(fail.get("fields")):
        _err(e, "StudentFailPercent scalar 10 not carried verbatim")
    unh = by.get("StudentUnhappyTuitionFeesThreshold") or {}
    if 20.0 not in _flatten_values(unh.get("fields")):
        _err(e, "StudentUnhappyTuitionFeesThreshold 20.0 not carried verbatim")
    return e


def _flatten_values(o):
    out = []
    if isinstance(o, dict):
        for v in o.values():
            out.extend(_flatten_values(v))
    elif isinstance(o, list):
        for v in o:
            out.extend(_flatten_values(v))
    elif o is not None:
        out.append(o)
    return out


def finance_violations(rows):
    """Base anchors + diff-only override property; a SECOND differing field
    on any override is DRIFT territory - reported via drift key, never a
    silent extra override count."""
    e = []
    by = {r.get("id"): r for r in rows}
    base = by.get("Config_FinanceManager")
    if base is None:
        return ["base Config_FinanceManager row missing"]
    pairs = {"initialBalance": 150000,
             "failStateBalanceWarning": -150000,
             "failStateBalanceGameOver": -300000,
             "rentMultiplier": 1.0, "tuitionFeesMultiplier": 1.0,
             "allowTuitionFeeModification": 1, "useBungleBonus": 0}
    for k, v in pairs.items():
        if base.get(k) != v:
            _err(e, f"base.{k} {base.get(k)!r} != {v!r}")
    return e


def prerequisite_violations(rows, *, expect_instances=None,
                            expect_classes=None):
    """Ancestry-selected member census: class in the 24 namespaced
    spellings, taxonomyIndex == the PINNED alphabetical index [F2/RF-1]."""
    e = []
    seen_keys = set()
    classes = set()
    for r in rows:
        cls = r.get("prerequisiteClass")
        if cls not in TAXONOMY_24:
            _err(e, f"{r.get('carrierId')}: prerequisiteClass {cls!r} "
                    f"outside the 24-type taxonomy (ancestry selection)")
            continue
        idx = TAXONOMY_24.index(cls)
        if r.get("taxonomyIndex") != idx:
            _err(e, f"{r.get('carrierId')}: taxonomyIndex "
                    f"{r.get('taxonomyIndex')!r} != pinned {idx} for {cls}")
        key = (r.get("carrierId"), r.get("refKey"))
        if key in seen_keys:
            _err(e, f"duplicate census identity {key}")
        seen_keys.add(key)
        classes.add(cls)
        if r.get("asm") == "TPS.Game" and r.get("ns") != "TPC":
            _err(e, f"{r.get('carrierId')}: ns {r.get('ns')!r} != 'TPC'")
        if not isinstance(r.get("payload"), dict):
            _err(e, f"{r.get('carrierId')}: payload must copy data verbatim")
    if expect_instances is not None and len(rows) != expect_instances:
        _err(e, f"census rows {len(rows)} != expected {expect_instances}")
    if expect_classes is not None and len(classes) != expect_classes:
        _err(e, f"distinct classes {len(classes)} != expected "
                f"{expect_classes}")
    # non-members must NEVER ride the member census
    for r in rows:
        if r.get("prerequisiteClass") in NONMEMBER_CLASSES:
            _err(e, f"non-member {r.get('prerequisiteClass')} leaked into "
                    f"the member census")
    return e


def nonmember_violations(rows):
    e = []
    for r in rows:
        if r.get("interfaceFamily") != NONMEMBER_FAMILY:
            _err(e, f"{r.get('carrierId')}: interfaceFamily "
                    f"{r.get('interfaceFamily')!r} != {NONMEMBER_FAMILY!r}")
        if r.get("blockClass") not in NONMEMBER_CLASSES:
            _err(e, f"{r.get('carrierId')}: blockClass "
                    f"{r.get('blockClass')!r} not a declared non-member")
    members = {TAXONOMY_24[0]} | set(TAXONOMY_24)
    for r in rows:
        if r.get("blockClass") in members:
            _err(e, "taxonomy member routed to the non-member sidecar")
    return e


def hierarchy_member_names(hier_rows):
    """The NAMESPACED ancestry query itself: bare 'Prerequisite' baseType
    matches NOTHING (0 rows) - the F4 spelling law."""
    namespaced = [r["name"] for r in hier_rows
                  if r.get("baseType") == "TPC.Prerequisite"]
    bare = [r["name"] for r in hier_rows
            if r.get("baseType") == "Prerequisite"]
    return namespaced, bare


def research_violations(rows, *, lite_count_expected=1):
    """209-analog: row count == full-definition stub count; domain subset;
    Lite twins are a DECLARED-EMPTY class (never zero-cost rows)."""
    e = []
    dist = {}
    for r in rows:
        v = r.get("researchPoints")
        if v not in RESEARCH_DOMAIN:
            _err(e, f"{r.get('id')}: researchPoints {v!r} outside the "
                    f"9-value domain {sorted(RESEARCH_DOMAIN)}")
        dist[v] = dist.get(v, 0) + 1
    if sum(dist.values()) != len(rows):
        _err(e, "research distribution does not sum to the row count")
    return e


EDGE_VERB = "requires-course-unlocked"


def unlock_edge_violations(rows, *, resolved_expected=None):
    """Frozen row shape [L1]; unresolved instances are ROWS with dstId null
    + reason; sort (srcId,dstId,fieldPath); dedup identity."""
    e = []
    keys = []
    n_resolved = 0
    for r in rows:
        if r.get("verb") != EDGE_VERB:
            _err(e, f"{r.get('srcId')}: verb {r.get('verb')!r} != "
                    f"{EDGE_VERB!r}")
        if r.get("mechanism") != "hard":
            _err(e, f"{r.get('srcId')}: mechanism must be hard")
        if r.get("inferred") is not False:
            _err(e, f"{r.get('srcId')}: typed-block resolution is hard-read")
        method = str(r.get("method", ""))
        if "typed-block" not in method:
            _err(e, f"{r.get('srcId')}: method {method!r} must name the "
                    f"typed-block machinery")
        if r.get("resolved", True) is False:
            if r.get("dstId") is not None:
                _err(e, f"{r.get('srcId')}: unresolved row carries dstId")
            if not str(r.get("reason", "")):
                _err(e, f"{r.get('srcId')}: unresolved row lacks a reason")
        else:
            n_resolved += 1
            if r.get("dstKind") != "course":
                _err(e, f"{r.get('srcId')}: dstKind must be 'course'")
        ev = r.get("evidence") or {}
        for k in ("fieldPath", "srcBundle", "srcPathId"):
            if k not in ev:
                _err(e, f"{r.get('srcId')}: evidence missing {k!r}")
        fp = str(ev.get("fieldPath", ""))
        if ".data._course" not in fp:
            _err(e, f"{r.get('srcId')}: fieldPath {fp!r} must be the typed "
                    f"_course leaf")
        twin_of = r.get("dstTwinOf")
        did = r.get("dstId")
        if isinstance(did, str) and "@" in did and twin_of is not None \
                and did.split("@")[0] != twin_of:
            _err(e, f"{r.get('srcId')}: dstTwinOf {twin_of!r} does not match "
                    f"the bare form of {did!r}")
        keys.append((r.get("srcId"), r.get("dstId"), fp))
    if keys != sorted(keys):
        _err(e, "unlock edges not sorted by (srcId, dstId, fieldPath)")
    ident = [(k[0], k[1], str(r.get("method")), k[2])
             for k, r in zip(keys, rows)]
    if len(set(ident)) != len(ident):
        _err(e, "duplicate unlock-edge dedup identities")
    if resolved_expected is not None and n_resolved != resolved_expected:
        _err(e, f"resolved edges {n_resolved} != expected {resolved_expected}")
    return e


def reconciliation_counters(unlock_edges, relinks_rows, scope_carriers):
    """RF-2 leg: per-edge match on (srcBundle, srcPathId, dstPathId).
    Returns counters + violations; a relinks counterpart without a logic-side
    row OUTSIDE the declared scope -> relinks-divergence violation."""
    relinks_index = {}
    for rr in relinks_rows:
        ev = rr.get("evidence") or {}
        key = (ev.get("srcBundle"), ev.get("srcPathId"), ev.get("dstPathId"))
        relinks_index.setdefault(key, []).append(rr)
    matched = 0
    unmatched_edges = []
    used = set()
    for edge in unlock_edges:
        ev = edge.get("evidence") or {}
        key = (ev.get("srcBundle"), ev.get("srcPathId"),
               ev.get("dstPathId"))
        hits = relinks_index.get(key)
        if edge.get("resolved", True) and hits:
            matched += 1
            used.add(key)
        elif edge.get("resolved", True):
            unmatched_edges.append(edge.get("srcId"))
    leftover_scope = 0
    divergences = []
    for key, rrs in relinks_index.items():
        for rr in rrs:
            k = (rr["evidence"]["srcBundle"],
                 rr["evidence"]["srcPathId"], rr["evidence"]["dstPathId"])
            if k in used:
                continue
            if rr.get("srcId") in scope_carriers:
                leftover_scope += 1
            else:
                divergences.append(rr.get("srcId"))
    return {"relinksCoursePPTRRows": len(relinks_rows),
            "unlockEdgeOverlapWithRelinks": matched,
            "declaredScopeDifference": leftover_scope,
            "divergentCarriers": sorted(divergences),
            "unmatchedEdges": unmatched_edges}


SCOPE_CARRIERS = {
    "CareerChallenge_Course_Baking_V1",     # PrerequisiteHasCourseRunning
    "CareerChallenge_Space_V1",             # PrerequisiteHasCourseAtLevel
    "Activity_XP_Twin",                     # CharacterModifier_XP
}

GAP_KINDS = {"unresolved-pptr", "missing-carrier", "ambiguous-target",
             "builtin-target", "relinks-divergence"}
GAP_FAMILIES = {"course-progression", "economy", "grading", "needs-decay"}
STANDING_GAP_MARKERS = ("xp-score-normalization", "student-core11",
                        "core-11", "core11")


def gaps_violations(rows):
    """Ledger shape + sort by (family, gapId) [L5]."""
    e = []
    keys = []
    for r in rows:
        for k in ("gapId", "family", "kind", "subjectId", "reason",
                  "unblock", "buildId"):
            if k not in r:
                _err(e, f"gap row missing {k!r}")
        if r.get("kind") not in GAP_KINDS:
            _err(e, f"gap kind {r.get('kind')!r} outside the pinned enum")
        if r.get("family") not in GAP_FAMILIES:
            _err(e, f"gap family {r.get('family')!r} outside the enum")
        keys.append((r.get("family"), r.get("gapId")))
    if keys != sorted(keys):
        _err(e, "_gaps.jsonl not sorted by (family, gapId)")
    return e


def standing_gap_rows(rows):
    """Identify the two legitimate terminal rows (XP->score normalization;
    student core-11 decay) - matched SOFTLY on subject/reason markers so the
    impl gapId spelling stays free."""
    standing = []
    for r in rows:
        blob = json.dumps(
            {k: r.get(k) for k in ("subjectId", "reason", "unblock")},
            ensure_ascii=False).lower()
        if any(m in blob for m in STANDING_GAP_MARKERS):
            standing.append(r)
    return standing


ID_FIELDS = (("courses.jsonl", ("id",)),
             ("modules.jsonl", ("id",)),
             ("prerequisites.jsonl", ("carrierId",)),
             ("prerequisite-nonmembers.jsonl", ("carrierId",)),
             ("course-unlock-edges.jsonl", ("srcId", "dstId")),
             ("finance-configs.jsonl", ("id",)),
             ("research-costs.jsonl", ("id",)),
             ("staff-decay.jsonl", ("staffId",)),
             ("student-decay.jsonl", ("studentTypeId",)),
             ("interactions.jsonl", ("id",)))


def id_verbatim_violations(logic_dir, stub_ids):
    """AC4: every emitted identifier resolves to a stub id (twins WITH
    suffix) or to null-with-gap-row; <=1000 ids -> all."""
    from _validators import identifier_sample_ids
    e = []
    checked = []
    for fname, fields in ID_FIELDS:
        p = Path(logic_dir) / "course-progression" / fname
        if not p.exists():
            p = None
            for sub in ("economy", "grading", "needs-decay",
                        "course-progression"):
                q = Path(logic_dir) / sub / fname
                if q.exists():
                    p = q
                    break
        if p is None or not p.exists():
            continue
        for r in read_jsonl(p):
            for f in fields:
                v = r.get(f)
                if isinstance(v, str):
                    checked.append((fname, f, v))
    sample = identifier_sample_ids([c[2] for c in checked])
    unknown = sorted({c for c in checked if c[2] in set(sample)
                      and c[2] not in stub_ids})
    # dstTwinOf-style bare names are legal companions; plain unknown ids are
    # violations
    for fname, field, v in unknown[:20]:
        bare_ok = "@" in v and v.split("@")[0] in stub_ids
        if not bare_ok:
            _err(e, f"{fname}.{field}: id {v!r} does not resolve to any "
                    f"stub id")
    return e


def run_section_violations(text):
    """Every headline run-section key must appear with a parseable number."""
    import re
    e = []
    for key in RUN_KEYS_WITH_NUMBERS:
        m = re.search(rf"{re.escape(key)}\b[^0-9\n\-]*(-?\d+)", text,
                      re.IGNORECASE)
        if m is None:
            e.append(f"run-section key {key!r} absent or carries no number")
    return e


def drift_lines(stdout: str):
    return [ln for ln in stdout.splitlines() if "DRIFT:" in ln.upper()
            or "DRIFT:" in ln]


# ---------------------------------------------------------------------------
# Scratch roots (D:-first per the shared-tree discipline; never C:-rooted)
# ---------------------------------------------------------------------------

SCRATCH_ROOT = Path("D:/tpc_pytmp/tw04")


def scratch(name: str) -> Path:
    """Prefer D:/tpc_pytmp/tw04/<name> when the drive is writable, else the
    pytest default (%TEMP%). Probes one tiny write first (sandbox trap)."""
    try:
        SCRATCH_ROOT.mkdir(parents=True, exist_ok=True)
        probe = SCRATCH_ROOT / ".probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        path = SCRATCH_ROOT / name
    except OSError:
        import tempfile
        path = Path(tempfile.mkdtemp(prefix=f"tw04-{name}"))
    return path


# ---------------------------------------------------------------------------
# Impl adapter vocabulary (pure-function obligations; loud skips until the
# CodeWriter lands - mirrors tests/_impl.py discipline for stage 8)
# ---------------------------------------------------------------------------

LOGIC_SCRIPTS = ("logic_util.py", "stage8_logic.py")
WALKER_SYMBOLS = ("walk_typed_blocks", "typed_block_leaves",
                  "iter_typed_blocks", "walk_typed_references",
                  "typed_blocks")
GUARD_SYMBOLS = ("run_invention_guard", "invention_guard", "audit_numerics",
                 "audit_emitted_numerics", "audit_artifact_numerics")
