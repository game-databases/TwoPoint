"""Synthetic upstream corpora + oracle helpers for the piece-08 stage-12
`search-corpus` blind test suite (TestWriter seat).

Built from docs/specs/piece-08-search-corpus.mdx (**Revision 3**) +
docs/rulings/arbiter-piece08-spec.mdx ALONE — no implementation file is
read or imported. The fixture materializes §4's COMPLETE upstream set
synthetically (identity.json + `.stage-stamps/{relink,localisation}.json`
+ `stubs/<kind>.jsonl` ×9 + `relinks/{entity_locale,i2_term_registry,
locale_term_entity,matrix,guid_bridge_report,locale_join_report}` +
`locales/<locale>.jsonl` ×13 + `locales/locale-matrix.json`). The §9
"mini roster of 2 locales + 3 kinds" rides as the hand-computed CORE
inside a 13-table layout (the runner pre-check refuses anything less —
piece-07 `_prooflib` precedent): core de/en/ja/ko/zh-Hans carry the
designed holes; the 8 extra locales hold EXACTLY the all-locales group
with the EN text copied verbatim.

HAND-COMPUTED CENSUS (the suite pins these literals AND cross-checks
them against the programmatic oracle, so a wrong oracle cannot pass
silently):

  stub rows            67 (config 19 · item 13 · unlockable 8 · course 13
                        · campus-level 6 · room 4 · student-type 2
                        · metagame-node 1 · staff 1)
  entity_locale edges  40 rows (name + description LS instances)
                        -> universe A = 30 distinct (srcKind,srcId)
  registry             41 canonical keys; reverse index 26 keys /
                        40 usages -> uiChromeTerms identity 41-26 = 15
  narrow carriers      32 rows (pinned expansion reading);
                        single-field trap reading 28
  narrow union         **41** ; trap union **37** — delta exactly the 4
                        dev-only F/M carriers outside A
                        (Item_Sorcerer_Forms, Item_Amazoness_Form,
                        Unlock_Female_Development, Student_Type_Developer)
  overlap A∩carriers   21
  expanded components  plainStringNames 7 = config 1 + unlockable 1 +
                        campus-level 5 · configLocalisedNamePresence 1
                        (nested States[0]) · titleCarrierInstances 2
                        (DRIFT-tracked DATA, never an equality gate) ·
                        displayNameScoped 2 (allClass 3) · roomName
                        presence 2 / text-bearing 1 (empty struct emits
                        nothing) · mTermRows 3 / resolved 1 ·
                        descriptiveName 1 · joins emitted 2 of 2005
  expanded union       **56** with the alias input, **54** without;
                        AC2 law expanded == distinctDocs(48|46) +
                        descriptionOnlyNoDoc(8) holds in BOTH states
  descriptionOnlyNoDoc total 8 = {config 6, item 1, room 1} — Title-
                        only / brush-scoped / unscoped-DisplayName /
                        nested-edge-only / description-only configs,
                        I9 (item Description-only), R2 (fields.Name is
                        NOT the room §S1.1 path). Empty structs (C11,
                        R3, R4) and never-resolved rows hold NO union
                        seat.
  idOnly               11 (aliased) / 13 (absent) of 67
  per-locale docs      en 46 · de 28 · ja 8 · ko 8 · zh-Hans 7 · each
                        extra 7 (Knight School + Grand Library ride the
                        all-group, Lab Work is core-wide; ja adds
                        Ghostbusting, ko adds Rocket Science); literal/
                        dev-fallback names ship in the EN SHARD ONLY;
                        absent-state drops K3/K4 (-1 doc in every
                        non-en locale, -2 in en).
  cleanedEmptyDropped  en 1 KEY-level (Sword_Name "{BLADE}" — carried by
                        I5/I7/I6; de "Klinge" survives everywhere)
  titleKeySets.narrow  edges 22 / keys 15 (pre-cleaning key census,
                        mirroring F9's 2993->2059) / enResolvePct "100%"
  id tokens            lowercased-rule vocab 105; case-sensitive
                        superset 106; caseFoldCollisions 1 (Item_Gem vs
                        GEM_Hunter — the single planted pair)
  devStrings           7 ROWS (I1 localized+dev, C16, I10, I12, I13,
                        S2, U6)
  collisions           collidingPairs 3 · top [(config,"Lab Work",5),
                        (config,"Specialist Book Report",4)] ·
                        ignoreKindCollisions 4 (Lab Work, Specialist
                        Book Report, Grand Library across room+item,
                        Construction Blocks Set across lite+variation) ·
                        withinLocaleDuplicateTexts {de 2, en 3, ja 0,
                        ko 2, zh-Hans 2, each extra 2}
  course ladder        9 TPC.CourseDefinition + 4 Marketing; mechanical 6
                        {Potions plural-fold, Computing token-map,
                        Ghostbusting last-segment, VeryHard token-map,
                        Clowns plural-fold, RocketScience family:*};
                        curated fixes KnightSchool_LordBlaggard +
                        PerformingArts -> seeded 8/9 (open SpaceExplorer);
                        marketing 3 resolved + Orphan_Box ledgered;
                        degraded (input absent): 6/9, open
                        {KnightSchool_LordBlaggard, SpaceExplorer}
  locale tables        en 41 rows (full) · de 34 · ja 8 · ko 7 ·
                        zh-Hans 6 · extras 6 each (all-group EN copies
                        + Lab Work pair)
  analyzers            vocab en 63 · de 34 · ko 10 · ja 9 · zh-Hans 4;
                        ko cjkRows 7 (Hangul-INCLUSIVE detector); ja
                        no-whitespace rows 7 (mixed latin+CJK row)
"""
from __future__ import annotations

import hashlib
import json
import re
import zlib
from contextlib import contextmanager
from pathlib import Path

from _validators import (
    BUILD_ID, KIND_TO_FILE, LOCALE_TABLE, write_jsonl,
)

STAGE_ID = "search-corpus"
SCRIPT_REL = "tools/stage12_search_corpus.py"
# §4 registration bullet — script-hash deps pinned verbatim.
SCRIPT_DEPS = ["stage12_search_corpus.py", "search_util.py",
               "tpc_common.py", "log_util.py"]

CORE_LOCALES = ("de", "en", "ja", "ko", "zh-Hans")
EXTRA_LOCALES = tuple(sorted(set(LOCALE_TABLE.values()) - set(CORE_LOCALES)))
ALL_LOCALES = tuple(sorted(CORE_LOCALES + EXTRA_LOCALES))
PIVOT = "en"

ALIAS_INPUT_REL = "data/sources/derived/course-name-aliases.jsonl"

SEARCH_DIR = "search"

# §S5.1 kindWeights — frozen ranking hint (manifest authority).
KIND_WEIGHTS = {
    "item": 1.0, "room": 1.0, "course": 1.0, "staff": 1.0,
    "student-type": 0.9, "unlockable": 0.8, "metagame-node": 0.6,
    "config": 0.5, "campus-level": 0.3,
}

# §S2 visibility roster (G8) — verbatim; public rows complete the set.
VISIBILITY_PUBLIC_NAMES = ("All buildings", "Knight Level")
VISIBILITY_INTERNAL_NAMES = (
    "Blank Level", "Free Play Level", "IL3 Video 1", "IL3 Video 2",
    "IL3 Video 3", "IL3 Video 4", "IL3 Video 5", "IL3 Demo Level",
    "Mark's Test Scenario", "September 2020 Milestone", "Test Level",
)

# §S4 analyzer assignments — frozen 13-entry table (ko UNDER whitespace).
ANALYZER_ASSIGNMENTS = {
    "whitespace": ("de", "en", "es", "fr", "it", "ko", "pl", "pt-BR",
                   "ru", "tr"),
    "cjk-bigram": ("zh-Hans", "zh-Hant"),
    "mixed": ("ja",),
}

# §S3.2 token map (7 entries, frozen DATA).
TOKEN_MAP = {
    "Computing": "Computer", "Magic": "Wizardry", "Spy": "SpySchool",
    "VeryHard": "Hard", "Grease": "Greaser",
    "CheeseAlien": "AlienCheese", "HumanityAlien": "Alien",
}

# §S3.3 curated seed rows (shared with piece-07; sorted by courseId).
SEED_ALIAS_ROWS = [
    {"courseId": "Course_KnightSchool_LordBlaggard",
     "method": "curated",
     "termKey": "Courses/Courses/KnightSchool_Name",
     "inferred": True,
     "sourceRefs": ["fixtures/_searchlib", "verifyB A1"]},
    {"courseId": "Course_PerformingArts",
     "method": "curated",
     "termKey": "Characters/Qualifications/Teacher/Music_Qualification_Name",
     "inferred": True,
     "sourceRefs": ["fixtures/_searchlib"]},
]
DANGLING_ALIAS_ROW = {"courseId": "Course_Dangling_Probe",
                      "method": "curated",
                      "termKey": "Courses/Missing/Dangling_Name",
                      "inferred": True,
                      "sourceRefs": ["fixtures/_searchlib"]}

JOIN_CEILING_VARIATION = 353
JOIN_CEILING_TWIN = 1652
JOIN_CEILING_TOTAL = JOIN_CEILING_VARIATION + JOIN_CEILING_TWIN  # 2005


# ============================================================================
# locale key model
# ============================================================================

def _k(key, en, de=None, ja=None, ko=None, zh=None, holders=None):
    """(termKey, {coreLocale: text}); holders=None -> all five cores."""
    texts = {}
    for loc in (holders if holders is not None else CORE_LOCALES):
        val = {"en": en, "de": de, "ja": ja, "ko": ko, "zh-Hans": zh}[loc]
        if val is not None:
            texts[loc] = val
    return key, texts


KEYS_ALL_GROUP = [
    # held by ALL 13 locales (extras copy EN verbatim)
    _k("Rooms/Rooms/Room_Library_Name", "Grand Library",
       "Große Bibliothek", "グランド図書館", "그랜드 도서관", "大图书馆"),
    _k("Courses/Courses/KnightSchool_Name", "Knight School",
       "Ritterschule", "ナイトスクール", "기사 학교", "骑士学校"),
    _k("Configs/Names/Campus_Store_A", "Campus Store", "Campusladen",
       "キャンパス商店", "캠퍼스 상점", "校园商店"),
    _k("Configs/Names/Campus_Store_B", "Campus Store", "Campusladen",
       "店舗のほう", "캠퍼스 상점", "校园商店"),
]

KEYS_CORE = [
    _k("Configs/Names/Lab_Work", "Lab Work", "Laborarbeit",
       ja="ラボワーク", ko="실험 실습", zh="实验工作"),
    _k("Configs/Names/Lab_Work_Copy", "Lab Work", "Laborarbeit",
       ja="別ラボ", ko="실험 실습", zh="实验工作"),
    _k("Configs/Names/Specialist_Book_Report", "Specialist Book Report",
       "Fachbuchbericht"),
    _k("Configs/Titles/Honorary_Title", '<style="a"></style>{Kit}',
       "Ehrentitel"),
    _k("Configs/States/Nested_State_Name", "Nested State",
       "Verschachtelter Zustand"),
    _k("Configs/Texts/Lab_Desc", "A laboratory description",
       "Laborbeschreibung"),
    _k("Brushes/Names/Brush_Alpha_Name", "Hedge Brush", "Heckenbürste"),
    _k("Brushes/Names/Brush_Beta_Name", "Flower Brush", "Blumenbürste"),
    _k("Misc/Names/NonBrush_Name", "Unscoped Display", "Ungenutzt"),
    _k("Items/Alpha/Stone_Name", "Testing Stone", "Prüfstein"),
    _k("Items/Gem/Gem_Name", "Emerald Gem", "Smaragd"),
    _k("Items/Hunter/Hunter_Name", "Gem Hunter Badge", "Jägerabzeichen"),
    _k("Items/Build/Construction_Blocks_Name", "Construction Blocks Set",
       "Bauklötze"),
    _k("Items/Sword/Sword_Name", "{BLADE}", "Klinge"),
    _k("Items/Gendered/Neutral_Name", "Grand Library", "Auftretende"),
    _k("Items/Alpha/Stone_Description", "A stone description",
       "Steinbeschreibung"),
    _k("Unlockables/Kudoch/Male_Name", "Kudosh Crate", "Kudoshkiste"),
    _k("Students/Nerd/F_Name", "Nerd Student", "Streber"),
    _k("Students/Nerd/M_Name", "Nerd Boy", "Streberjunge"),
    _k("Staff/Professor/Name", "Professor", "Professorin"),
    _k("Staff/Ranks/Senior_M", "Senior Lecturer", "Dozent"),
    _k("Staff/Ranks/Senior_F", "Senior Lecturer Female", "Dozentin"),
    _k("Rooms/Extra/Room_Name", "Backstage Room", "Hinterbühne"),
    _k("Unlockables/Kudosh/Title", "Kudosh Bundle", "Kudoshpaket"),
    _k("Items/DLC_Space/Telescope_Name", "Telescope", "Teleskop"),
    _k("Meta/Nodes/Research_Label", "Research Node", "Forschungsknoten"),
    _k("Courses/Courses/Potion_Name", "Potions", "Tränke"),
    _k("Courses/Courses/Clown_Name", "Clowning", "Clownerei"),
    _k("Characters/Qualifications/Teacher/Computer_Qualification_Name",
       "Computer Science", holders=("en",)),
    _k("Characters/Qualifications/Teacher/Music_Qualification_Name",
       "Performing Arts", holders=("en",)),
    _k("Courses/DLC_Ghost/GhostBusting_Name", en="Ghostbusting",
       ja="ゴーストバスティング", holders=("en", "ja")),
    _k("Research/Courses/Hard_Name", "Hard Mode", holders=("en",)),
    _k("Marketing/Courses/Funny_Name", "Funny Business", "Komik"),
    _k("Marketing/Courses/Minor/Chess_Name", "Chess Club",
       holders=("en",)),
    _k("Marketing/Courses/Long_Summer_Name", "Summer School",
       holders=("en",)),
    _k("Courses/DLC_Space/RocketScience_Name", en="Rocket Science",
       ko="로켓 과학", holders=("en", "ko")),
    _k("Marketing/Courses/Funny_Description", "Marketing description",
       "Marketingtext", ja="マーケティング text"),
]

KEY_TEXTS = {}
for _key, _texts in KEYS_ALL_GROUP + KEYS_CORE:
    KEY_TEXTS[_key] = _texts

UNRESOLVED_MTERM_KEYS = ("Items/Missing/Term_A", "Items/Missing/Term_B")

_TERM_ID_SEED = -1200000000
TERM_IDS = {key: _TERM_ID_SEED - i
            for i, key in enumerate(sorted(KEY_TEXTS))}
KEY_BY_TERM_ID = {tid: key for key, tid in TERM_IDS.items()}


def _ls(term_id, dev):
    """LocalisedString payload shape ({_dev,_termID}) as harvested."""
    return {"_dev": dev, "_termID": term_id}


DEV_PLACEHOLDER = "Brief description of the item…"


def icon_ref(sub):
    return {"m_SubObjectName": sub}


# ============================================================================
# entity model — (kind, id, source.class, fields)
# ============================================================================

def _lab_configs():
    rows = []
    for suffix in "ABCDE":
        rows.append(("config", f"Config_Laboratory_Hub_{suffix}",
                     "TPC.LabHubDefinition",
                     {"Name": _ls(TERM_IDS["Configs/Names/Lab_Work"], ""),
                      "Description": _ls(
                          TERM_IDS["Configs/Texts/Lab_Desc"], "")}))
    return rows


def _report_configs():
    rows = []
    for suffix in "ABCD":
        rows.append(("config", f"Config_Report_Station_{suffix}",
                     "TPC.AssignmentDefinition",
                     {"Name": _ls(
                         TERM_IDS["Configs/Names/Specialist_Book_Report"],
                         "")}))
    return rows


COURSE_DEFINITION_IDS = (
    "Course_Potions", "Course_Computing",
    "Course_KnightSchool_LordBlaggard", "Course_PerformingArts",
    "Course_Ghost_Ghostbusting", "Course_VeryHard",
    "Course_SpaceExplorer", "Course_Clowns", "Course_RocketScience",
)
MARKETING_COURSE_IDS = (
    "Marketing_Course_Funny", "Marketing_Minor_Course_Chess",
    "Marketing_Course_Summer_Long", "Marketing_Course_Orphan_Box",
)

ENTITIES = [
    # --- config ---------------------------------------------------------
    *_lab_configs(),
    *_report_configs(),
    ("config", "Config_Title_Carrier_One", "TPC.CareerGoalDefinition",
     {"Title": _ls(TERM_IDS["Configs/Titles/Honorary_Title"], "")}),
    ("config", "Config_Title_Empty_Struct", "TPC.CareerGoalDefinition",
     {"Title": _ls(0, "")}),
    ("config", "Config_Brush_Definition_Alpha",
     "TPC.LandscapeBrushDefinition",
     {"DisplayName": _ls(TERM_IDS["Brushes/Names/Brush_Alpha_Name"], ""),
      "IconReference": icon_ref("UI_InGame_T_Icon_Brush_Hedge")}),
    ("config", "Config_State_Nested_Carrier", "TPC.StateMachineDefinition",
     {"States": [{"LocalisedName":
                  _ls(TERM_IDS["Configs/States/Nested_State_Name"], "")}]}),
    ("config", "Config_Plain_Literal_Row", "TPC.PlainNameDefinition",
     {"Name": "Plain Config Literal Row"}),
    ("config", "Config_Description_Only_Row", "TPC.FlavourDefinition",
     {"Description": _ls(TERM_IDS["Configs/Texts/Lab_Desc"], "")}),
    ("config", "Config_Development_Name_Row", "TPC.DevNameDefinition",
     {"Name": _ls(0, "Development Config Title")}),
    ("config", "Config_Meshes_Bone_Carrier", "TPC.MeshHolderDefinition",
     {"Meshes": [{"GeometryList":
                  [{"Bones": ["bone_alpha", "bone_beta"]}]}],
      "MaterialPath": "assets/materials/mat_floor"}),
    ("config", "Config_Brush_Definition_Beta",
     "TPC.LandscapeBrushDefinition",
     {"DisplayName": _ls(TERM_IDS["Brushes/Names/Brush_Beta_Name"], "")}),
    ("config", "Config_Display_Unscoped_Row", "TPC.OtherDisplayDefinition",
     {"DisplayName": _ls(TERM_IDS["Misc/Names/NonBrush_Name"], "")}),
    # --- item -----------------------------------------------------------
    ("item", "Item_Testing_Stone", "TPC.GameItemLiteDefinition",
     {"LocalisedName": _ls(TERM_IDS["Items/Alpha/Stone_Name"],
                           "Testing Stone Dev")}),
    ("item", "Item_Gem", "TPC.GameItemLiteDefinition",
     {"LocalisedName": _ls(TERM_IDS["Items/Gem/Gem_Name"], "")}),
    ("item", "GEM_Hunter", "TPC.GameItemLiteDefinition",
     {"LocalisedName": _ls(TERM_IDS["Items/Hunter/Hunter_Name"], "")}),
    ("item", "Item_Variation_Construction",
     "TPC.GameItemVariationDefinition", {"GameItem": 7001}),
    ("item", "Item_Construction_Lite", "TPC.GameItemLiteDefinition",
     {"LocalisedName": _ls(
         TERM_IDS["Items/Build/Construction_Blocks_Name"], ""),
      "DefinitionID": 7001}),
    ("item", "Item_Sword_Full", "TPC.GameItemDefinition", {}),
    ("item", "Item_Sword_Lite", "TPC.GameItemLiteDefinition",
     {"LocalisedName": _ls(TERM_IDS["Items/Sword/Sword_Name"], "")}),
    ("item", "Item_Pointer_Related", "TPC.ItemPtrDefinition", {}),
    ("item", "Item_Description_Only_Row", "TPC.ItemDescDefinition",
     {"Description": _ls(TERM_IDS["Items/Alpha/Stone_Description"], "")}),
    ("item", "Item_Development_Blade", "TPC.GameItemLiteDefinition",
     {"LocalisedName": _ls(0, "Development Blade")}),
    ("item", "Item_Performer_Posters", "TPC.GameItemLiteDefinition",
     {"LocalisedName": _ls(TERM_IDS["Items/Gendered/Neutral_Name"], ""),
      "IconReference": icon_ref("UI_InGame_T_Icon_Item_Posters")}),
    ("item", "Item_Sorcerer_Forms", "TPC.GameItemGenderedDefinition",
     {"LocalisedNameFemale": _ls(0, "Sorceress"),
      "LocalisedNameMale": _ls(0, "Sorcerer")}),
    ("item", "Item_Amazoness_Form", "TPC.GameItemGenderedDefinition",
     {"LocalisedNameFemale": _ls(0, "Amazoness")}),
    # --- student-type ----------------------------------------------------
    ("student-type", "Student_Type_Nerd", "TPC.StudentTypeDefinition",
     {"LocalisedNameF": _ls(TERM_IDS["Students/Nerd/F_Name"], ""),
      "LocalisedNameM": _ls(TERM_IDS["Students/Nerd/M_Name"], "")}),
    ("student-type", "Student_Type_Developer", "TPC.StudentTypeDefinition",
     {"LocalisedNameF": _ls(0, "Developer (F)"),
      "LocalisedNameM": _ls(0, "Developer (M)")}),
    # --- staff -----------------------------------------------------------
    ("staff", "Staff_Professor_Row", "TPC.StaffDefinition",
     {"LocalisedName": _ls(TERM_IDS["Staff/Professor/Name"], ""),
      "Ranks": [{"TitleM": _ls(TERM_IDS["Staff/Ranks/Senior_M"], ""),
                 "TitleF": _ls(TERM_IDS["Staff/Ranks/Senior_F"], "")}]}),
    # --- room ------------------------------------------------------------
    ("room", "Room_Library_Main", "TPC.RoomDefinition",
     {"NameWhenBuilt": _ls(TERM_IDS["Rooms/Rooms/Room_Library_Name"], ""),
      "Description": _ls(TERM_IDS["Configs/Texts/Lab_Desc"], ""),
      "LongDescription": _ls(TERM_IDS["Items/Alpha/Stone_Description"],
                             "")}),
    ("room", "Room_Backstage_Extra", "TPC.RoomDefinition",
     {"Name": _ls(TERM_IDS["Rooms/Extra/Room_Name"], "")}),
    ("room", "Room_Empty_WhenBuilt", "TPC.RoomDefinition",
     {"NameWhenBuilt": _ls(0, "")}),
    ("room", "Room_Empty_Name_Field", "TPC.RoomDefinition",
     {"Name": _ls(0, "")}),
    # --- unlockable -------------------------------------------------------
    ("unlockable", "Unlock_Kudosh_Bundle", "TPC.UnlockableDefinition",
     {"LocalisedName": _ls(TERM_IDS["Unlockables/Kudosh/Title"], "")}),
    ("unlockable", "Unlock_Telescope_Scope", "TPC.UnlockableDefinition",
     {"DisplayName": {"mTerm": "Items/DLC_Space/Telescope_Name"}}),
    ("unlockable", "Unlock_Missing_Term_Alpha", "TPC.UnlockableDefinition",
     {"DisplayName": {"mTerm": "Items/Missing/Term_A"}}),
    ("unlockable", "Unlock_Missing_Term_Beta", "TPC.UnlockableDefinition",
     {"DisplayName": {"mTerm": "Items/Missing/Term_B"}}),
    ("unlockable", "Unlock_Descriptive_Row", "TPC.UnlockableDefinition",
     {"DescriptiveName": "Kudosh Descriptive Row"}),
    ("unlockable", "Unlock_Female_Development", "TPC.UnlockableDefinition",
     {"LocalisedNameFemale": _ls(0, "Kudosh Chest (F)")}),
    ("unlockable", "Unlock_Male_Crate_Row", "TPC.UnlockableDefinition",
     {"LocalisedNameMale": _ls(TERM_IDS["Unlockables/Kudoch/Male_Name"],
                               "")}),
    ("unlockable", "Unlock_Plain_Name_Label", "TPC.UnlockableDefinition",
     {"Name": "Plain Unlock Label"}),
    # --- metagame-node ------------------------------------------------------
    ("metagame-node", "Metagame_Node_Research",
     "TPC.ResearchNodeDefinition",
     {"LocalisedName": _ls(TERM_IDS["Meta/Nodes/Research_Label"], "")}),
    # --- campus-level -----------------------------------------------------
    ("campus-level", "Config_GameMode_All_Buildings",
     "TPC.LevelScenarioDefinition", {"Name": "All buildings"}),
    ("campus-level", "Config_GameMode_Blank_Level",
     "TPC.LevelScenarioDefinition", {"Name": "Blank Level"}),
    ("campus-level", "Config_GameMode_Test_Level",
     "TPC.LevelScenarioDefinition", {"Name": "Test Level"}),
    ("campus-level", "Config_GameMode_Free_Play",
     "TPC.LevelScenarioDefinition", {"Name": "Free Play Level"}),
    ("campus-level", "LevelScenarioV2_Knight_Level",
     "TPC.LevelScenarioDefinition", {"Name": "Knight Level"}),
    ("campus-level", "LevelScenarioV2_Null_Name",
     "TPC.LevelScenarioDefinition", {"Name": None}),
]

for _cid in COURSE_DEFINITION_IDS:
    ENTITIES.append(("course", _cid, "TPC.CourseDefinition",
                     {"Description": _ls(0, DEV_PLACEHOLDER)}))
ENTITIES.append(("course", "Marketing_Course_Funny",
                 "TPC.MarketingCourseDefinition",
                 {"Description": _ls(
                     TERM_IDS["Marketing/Courses/Funny_Description"], "")}))
for _cid in ("Marketing_Minor_Course_Chess", "Marketing_Course_Summer_Long",
             "Marketing_Course_Orphan_Box"):
    ENTITIES.append(("course", _cid, "TPC.MarketingCourseDefinition",
                     {"Description": _ls(0, DEV_PLACEHOLDER)}))

# Expected resolution ladder: id -> (state, method, termKey).
COURSE_MECHANICAL = {
    "Course_Potions": ("plural-fold", "Courses/Courses/Potion_Name"),
    "Course_Computing": ("token-map",
                         "Characters/Qualifications/Teacher/"
                         "Computer_Qualification_Name"),
    "Course_Ghost_Ghostbusting": ("last-segment",
                                  "Courses/DLC_Ghost/GhostBusting_Name"),
    "Course_VeryHard": ("token-map", "Research/Courses/Hard_Name"),
    "Course_Clowns": ("plural-fold", "Courses/Courses/Clown_Name"),
}
MARKETING_MECHANICAL = {
    "Marketing_Course_Funny": ("family:", "Marketing/Courses/Funny_Name"),
    "Marketing_Minor_Course_Chess": (
        "family:", "Marketing/Courses/Minor/Chess_Name"),
    "Marketing_Course_Summer_Long": (
        "family:", "Marketing/Courses/Long_Summer_Name"),
}
COURSE_CURATED = {
    "Course_KnightSchool_LordBlaggard": (
        "curated", "Courses/Courses/KnightSchool_Name"),
    "Course_PerformingArts": (
        "curated",
        "Characters/Qualifications/Teacher/Music_Qualification_Name"),
}
COURSE_OPEN_ALWAYS = {"Course_SpaceExplorer": "unreferenced"}
MARKETING_OPEN = {"Marketing_Course_Orphan_Box": "unreferenced"}

# §S1.4 join-consumed titles on the PENDING fixture: variation→Lite
# (GameItem) and full→`_Lite` twin rows each resolve to the target Lite's
# LocalisedName key. The stage consumes them AS EMITTED; the oracle models
# their doc membership + union seats (basis spelling is impl freedom).
JOIN_TITLE_SOURCES = {
    "Item_Variation_Construction": "Items/Build/Construction_Blocks_Name",
    "Item_Sword_Full": "Items/Sword/Sword_Name",
}


def course_expectations(aliased):
    """Full expected ladder for the given alias-input state."""
    out = {}
    for cid, (method, key) in COURSE_MECHANICAL.items():
        out[cid] = ("resolved", method, key)
    out["Course_RocketScience"] = ("resolved", "family:",
                                   "Courses/DLC_Space/RocketScience_Name")
    for cid, (method, key) in MARKETING_MECHANICAL.items():
        out[cid] = ("resolved", method, key)
    if aliased:
        for cid, (method, key) in COURSE_CURATED.items():
            out[cid] = ("resolved", method, key)
    else:
        for cid in COURSE_CURATED:
            out[cid] = ("open", None, None)
    for cid in COURSE_OPEN_ALWAYS:
        out[cid] = ("open", None, None)
    for cid in MARKETING_OPEN:
        out[cid] = ("open", None, None)
    return out


def _mechanical_resolutions():
    """Mechanically resolvable map used by the oracle's name walker."""
    out = {}
    for cid, (method, key) in COURSE_MECHANICAL.items():
        out[cid] = (method, key)
    out["Course_RocketScience"] = ("family:",
                                   "Courses/DLC_Space/RocketScience_Name")
    for cid, (method, key) in MARKETING_MECHANICAL.items():
        out[cid] = (method, key)
    return out


# §S1.1 pinned narrow name-class fieldPaths per kind (EXACT member sets).
NARROW_PATHS = {
    "config": ("Name",),
    "room": ("NameWhenBuilt",),
    "staff": ("LocalisedName",),
    "item": ("LocalisedName", "LocalisedNameFemale", "LocalisedNameMale"),
    "metagame-node": ("LocalisedName", "LocalisedNameFemale",
                      "LocalisedNameMale"),
    "unlockable": ("LocalisedName", "LocalisedNameFemale",
                   "LocalisedNameMale"),
    "student-type": ("LocalisedNameF", "LocalisedNameM"),
}
TRAP_PATHS = {  # the single-field misreading (reviewer F3 trap figure)
    "config": ("Name",),
    "room": ("NameWhenBuilt",),
    "staff": ("LocalisedName",),
    "item": ("LocalisedName",),
    "metagame-node": ("LocalisedName",),
    "unlockable": ("LocalisedName",),
    "student-type": ("LocalisedName",),
}


def walk_ls(fields, prefix=""):
    """Yield (dottedPath, payload) for every LocalisedString struct:
    dicts recurse (LS-shaped terminate), lists recurse with indices."""
    if isinstance(fields, dict):
        if "_termID" in fields and "_dev" in fields:
            yield prefix.lstrip("."), fields
            return
        for name in sorted(fields):
            yield from walk_ls(fields[name], f"{prefix}.{name}")
    elif isinstance(fields, list):
        for i, item in enumerate(fields):
            yield from walk_ls(item, f"{prefix}.{i:08d}")


def mterm_refs(fields):
    """Yield (dottedPath, termKey) for DisplayName.mTerm direct refs."""
    def _walk(obj, prefix):
        if isinstance(obj, dict):
            for name in sorted(obj):
                child = obj[name]
                if name == "DisplayName" and isinstance(child, dict) \
                        and isinstance(child.get("mTerm"), str):
                    yield f"{prefix}.{name}.mTerm".lstrip("."), child["mTerm"]
                else:
                    yield from _walk(child, f"{prefix}.{name}")
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                yield from _walk(item, f"{prefix}.{i:08d}")
    yield from _walk(fields, "")


TAG_RE = re.compile(r"<[^>]+>")
PLACEHOLDER_RE = re.compile(r"\{[^{}]+\}")


def clean_text(text):
    """§S2 cleaning: strip tags + placeholders; empty result -> None."""
    cleaned = PLACEHOLDER_RE.sub("", TAG_RE.sub("", text or ""))
    return cleaned if cleaned.strip() else None


def id_tokens(entity_ids):
    """§S3.1 id-token rule: split on non-alphanumeric runs, LOWERCASE,
    length >= 2, pure digits dropped, deduped."""
    lowered, sensitive = set(), set()
    for eid in entity_ids:
        for run in re.split(r"[^0-9A-Za-z]+", eid):
            if len(run) < 2 or run.isdigit():
                continue
            sensitive.add(run)
            lowered.add(run.lower())
    return lowered, sensitive


class SearchOracle:
    """Independent derivation of every gated fixture quantity."""

    def __init__(self, entities=None, aliased=True):
        self.entities = list(ENTITIES if entities is None else entities)
        self.aliased = aliased
        self.mechanical = _mechanical_resolutions()
        self.ids_by_kind = {}
        for kind, eid, _cls, _f in self.entities:
            self.ids_by_kind.setdefault(kind, []).append(eid)
        self.total_rows = len(self.entities)

    # -- locale tables ---------------------------------------------------
    def table(self, loc):
        if loc in EXTRA_LOCALES:
            return {k: t[PIVOT] for k, t in KEY_TEXTS.items()
                    if set(t) >= set(CORE_LOCALES)}
        return {k: t[loc] for k, t in KEY_TEXTS.items() if loc in t}

    def registry_keys(self):
        return sorted(KEY_TEXTS)

    # -- LS walks --------------------------------------------------------
    def ls_instances(self):
        out = []
        for kind, eid, _cls, fields in self.entities:
            for path, payload in walk_ls(fields):
                out.append((kind, eid, path, payload))
        return out

    def edges(self):
        """entity_locale rows: every _termID!=0 instance."""
        rows = []
        for kind, eid, path, payload in self.ls_instances():
            tid = payload["_termID"]
            if tid == 0:
                continue
            rows.append((kind, eid, path, tid, KEY_BY_TERM_ID[tid]))
        return sorted(rows)

    def universe_a(self):
        return {(k, i) for k, i, _p, _t, _key in self.edges()}

    def carriers(self, paths=NARROW_PATHS):
        out = set()
        for kind, eid, _cls, fields in self.entities:
            allowed = paths.get(kind)
            if not allowed:
                if kind == "campus-level":
                    name = fields.get("Name")
                    if isinstance(name, str) and name.strip():
                        out.add((kind, eid))
                continue
            for path, payload in walk_ls(fields):
                if path.split(".")[0] in allowed and (
                        payload["_termID"] != 0
                        or str(payload["_dev"]).strip()):
                    out.add((kind, eid))
                    break
        return out

    def narrow_union(self, paths=NARROW_PATHS):
        return self.universe_a() | self.carriers(paths)

    def trap_reading(self):
        """The warned single-field misreading (union 37, not 41)."""
        return self.narrow_union(TRAP_PATHS)

    # -- expanded components (values on their PINNED bases, RF-B) --------
    def component_plain_literals(self):
        per_kind = {}
        for kind, eid, _cls, fields in self.entities:
            name = fields.get("Name")
            if isinstance(name, str) and name.strip():
                per_kind[kind] = per_kind.get(kind, 0) + 1
        return per_kind

    def component_title_carriers(self):
        n = 0
        for kind, eid, _cls, fields in self.entities:
            if kind != "config":
                continue
            for path, _payload in walk_ls(fields):
                if path.rsplit(".", 1)[-1] == "Title":
                    n += 1
        return n

    def component_display_name(self):
        scoped = all_class = 0
        for kind, eid, cls, fields in self.entities:
            for path, payload in walk_ls(fields):
                if path.rsplit(".", 1)[-1] == "DisplayName" \
                        and "_termID" in payload:
                    all_class += 1
                    if cls == "TPC.LandscapeBrushDefinition":
                        scoped += 1
        return scoped, all_class

    def component_room_name(self):
        presence = text_bearing = 0
        for kind, eid, _cls, fields in self.entities:
            if kind != "room":
                continue
            for path, payload in walk_ls(fields):
                seg = path.rsplit(".", 1)[-1]
                if seg == "Name" and "_termID" in payload:
                    presence += 1
                    if payload["_termID"] != 0 or str(payload["_dev"]).strip():
                        text_bearing += 1
        return presence, text_bearing

    def component_localised_name_presence(self):
        """config LocalisedName instances, PRESENCE basis, any depth."""
        n = 0
        for kind, eid, _cls, fields in self.entities:
            if kind != "config":
                continue
            for path, _payload in walk_ls(fields):
                if path.rsplit(".", 1)[-1].startswith("LocalisedName"):
                    n += 1
        return n

    def component_mterm(self):
        rows = resolved = 0
        for kind, eid, _cls, fields in self.entities:
            for _path, key in mterm_refs(fields):
                rows += 1
                if "en" in KEY_TEXTS.get(key, {}):
                    resolved += 1
        return rows, resolved

    def component_descriptive(self):
        return sum(1 for kind, eid, _cls, fields in self.entities
                   if isinstance(fields.get("DescriptiveName"), str)
                   and fields["DescriptiveName"].strip())

    # -- names, docs -------------------------------------------------------
    def name_resolution(self, locale=PIVOT):
        """(kind,id) -> (basis, termKey|None, text) under the pinned
        priority: localized §S1.1 edge > mTerm > literal > convention/
        curated; dev-fallback last. Literal/dev names exist ONLY in the
        pivot (en shard); convention draws TEXT per locale (unresolved-in-L
        = membership miss)."""
        tbl = self.table(locale)
        narrow_top = {k: set(v) for k, v in NARROW_PATHS.items()}
        edges_by_entity = {}
        for kind, eid, path, tid, key in self.edges():
            if path.split(".")[0] in narrow_top.get(kind, set()):
                edges_by_entity.setdefault((kind, eid), []).append((path, key))
        res = {}
        for kind, eid, _cls, fields in self.entities:
            slot = edges_by_entity.get((kind, eid))
            if slot:
                _path, key = sorted(slot)[0]
                text = tbl.get(key)
                cleaned = clean_text(text) if text is not None else None
                if cleaned is not None:
                    res[(kind, eid)] = ("localized", key, cleaned)
                    continue
            mterm = next(mterm_refs(fields), None)
            if mterm is not None:
                key = mterm[1]
                cleaned = clean_text(tbl[key]) if key in tbl else None
                if cleaned is not None:
                    res[(kind, eid)] = ("mterm", key, cleaned)
                    continue
            if kind == "item" and eid in JOIN_TITLE_SOURCES:
                key = JOIN_TITLE_SOURCES[eid]
                cleaned = clean_text(tbl[key]) if key in tbl else None
                if cleaned is not None:
                    res[(kind, eid)] = ("localized", key, cleaned)
                    continue
            if kind == "course":
                # clause 4: family/curated keys are locale-independent;
                # TEXT draws per locale (unresolved-in-L = miss)
                mech = self.mechanical.get(eid)
                curated = COURSE_CURATED.get(eid) if self.aliased else None
                for cand in (mech, curated):
                    if not cand:
                        continue
                    method, key = cand
                    cleaned = clean_text(tbl[key]) if key in tbl else None
                    if cleaned is not None:
                        basis = "curated" if method == "curated" \
                            else "convention"
                        res[(kind, eid)] = (basis, key, cleaned)
                        break
                if (kind, eid) in res:
                    continue
            if locale != PIVOT:
                continue  # literal/dev names never leave the pivot shard
            name = fields.get("Name")
            if isinstance(name, str) and name.strip():
                res[(kind, eid)] = ("literal", None, name.strip())
                continue
            dev_texts = []
            for path, payload in walk_ls(fields):
                if path.split(".")[0] in narrow_top.get(kind, set()) \
                        and payload["_termID"] == 0 \
                        and str(payload["_dev"]).strip():
                    dev_texts.append((path, str(payload["_dev"]).strip()))
            if dev_texts:
                dev_texts.sort()
                res[(kind, eid)] = ("dev-fallback", None, dev_texts[0][1])
        return res

    def docs_per_locale(self):
        return {loc: len(self.name_resolution(loc)) for loc in ALL_LOCALES}

    def distinct_doc_entities(self):
        seen = set()
        for loc in ALL_LOCALES:
            seen |= set(self.name_resolution(loc))
        return seen

    # -- alias volumes -----------------------------------------------------
    def alias_volumes(self):
        lowered, sensitive = id_tokens(
            [e for ids in self.ids_by_kind.values() for e in ids])
        narrow_top = {k: set(v) for k, v in NARROW_PATHS.items()}
        dev_rows = 0
        for kind, eid, _cls, fields in self.entities:
            hit = any(
                path.split(".")[0] in narrow_top.get(kind, set())
                and str(payload["_dev"]).strip()
                for path, payload in walk_ls(fields))
            dev_rows += 1 if hit else 0
        mterm_rows, mterm_resolved = self.component_mterm()
        return {
            "idTokens": len(lowered),
            "idTokensCaseSensitiveSuperset": len(sensitive),
            "caseFoldCollisions": len(sensitive) - len(lowered),
            "devStrings": dev_rows,
            "mTermRows": mterm_rows,
            "mTermResolved": mterm_resolved,
        }

    # -- titles / collisions -----------------------------------------------
    def title_edges_narrow(self):
        """Narrow display-name EDGES + DISTINCT KEYS resolving to pivot
        text (pre-cleaning census, mirroring F9's 2,993 -> 2,059)."""
        narrow_top = {k: set(v) for k, v in NARROW_PATHS.items()}
        edges, keys = 0, set()
        for kind, eid, path, tid, key in self.edges():
            if path.split(".")[0] in narrow_top.get(kind, set()) \
                    and PIVOT in KEY_TEXTS[key]:
                edges += 1
                keys.add(key)
        return edges, keys

    def cleaned_empty_titles(self, locale=PIVOT):
        """DISTINCT KEYS whose pivot text cleans to empty (F9 analog)."""
        narrow_top = {k: set(v) for k, v in NARROW_PATHS.items()}
        bad = set()
        for kind, eid, path, tid, key in self.edges():
            if path.split(".")[0] in narrow_top.get(kind, set()) \
                    and key in self.table(locale):
                if clean_text(self.table(locale)[key]) is None:
                    bad.add(key)
        return bad

    def collisions(self):
        res = self.name_resolution(PIVOT)
        pair_mult = {}
        text_entities = {}
        for (kind, eid), (_basis, _key, text) in res.items():
            pair_mult[(kind, text)] = pair_mult.get((kind, text), 0) + 1
            text_entities.setdefault(text, set()).add(eid)
        colliding = {kv: v for kv, v in pair_mult.items() if v > 1}
        top = sorted(colliding.items(), key=lambda kv: (-kv[1], kv[0]))
        ignore_kind = sum(1 for ents in text_entities.values()
                          if len(ents) > 1)
        dup_texts = {}
        for loc in ALL_LOCALES:
            seen = {}
            for text in self.table(loc).values():
                seen[text] = seen.get(text, 0) + 1
            dup_texts[loc] = sum(1 for v in seen.values() if v > 1)
        return colliding, top, ignore_kind, dup_texts

    # -- analyzers -----------------------------------------------------------
    def vocab(self, loc):
        """Distinct word-char-run tokens, tokenize-then-lowercase GLOBAL
        (unicode \\w runs — Hangul/CJK tokens count, mirroring scout §3)."""
        tokens = set()
        for text in self.table(loc).values():
            for run in re.split(r"\W+", TAG_RE.sub("", text), flags=re.UNICODE):
                if run:
                    tokens.add(run.lower())
        return tokens

    def cjk_rows(self, loc):
        n = 0
        for text in self.table(loc).values():
            for ch in text:
                cp = ord(ch)
                if 0x4E00 <= cp <= 0x9FFF or 0x3040 <= cp <= 0x30FF \
                        or 0xAC00 <= cp <= 0xD7A3:
                    n += 1
                    break
        return n

    def no_whitespace_rows(self, loc):
        return sum(1 for t in self.table(loc).values()
                   if not any(ch.isspace() for ch in t))


# ============================================================================
# builders
# ============================================================================

def _stable_path_id(eid: str, cls: str) -> int:
    return zlib.crc32(f"{eid}|{cls}".encode()) - 2 ** 31


def stub_row(kind, eid, cls, fields):
    return {
        "buildId": BUILD_ID, "fields": fields, "id": eid, "kind": kind,
        "inferred": False, "method": "verbatim-copy", "provisional": True,
        "slug": None,
        "source": {"bundle": "fixtures.bundle", "class": cls,
                   "pathId": _stable_path_id(eid, cls)},
    }


def write_stubs(extracted: Path, entities=None):
    entities = ENTITIES if entities is None else entities
    by_kind = {}
    for kind, eid, cls, fields in entities:
        by_kind.setdefault(kind, []).append(stub_row(kind, eid, cls, fields))
    for kind, fname in sorted(KIND_TO_FILE.items()):
        write_jsonl(extracted / "stubs" / fname,
                    sorted(by_kind.get(kind, []), key=lambda r: r["id"]))


def write_registry(extracted: Path):
    rows = [{
        "buildId": BUILD_ID, "canonical": True, "locales": [],
        "sourceAsset": "I2LS_Fixture", "termId": TERM_IDS[k],
        "termKey": k, "termStatus": 1, "termType": 0,
    } for k in sorted(KEY_TEXTS)]
    write_jsonl(extracted / "relinks" / "i2_term_registry.jsonl", rows)


def write_entity_locale(extracted: Path, orc: SearchOracle):
    dev_by_edge = {}
    for kind, eid, path, payload in orc.ls_instances():
        if payload["_termID"] != 0:
            dev_by_edge[(kind, eid, path)] = str(payload["_dev"])
    rows = [{
        "buildId": BUILD_ID, "dstId": key, "dstKind": "locale-term",
        "evidence": {"dev": dev_by_edge[(kind, eid, path)],
                     "fieldPath": path,
                     "locales": [], "termId": tid},
        "inferred": False, "mechanism": "hard",
        "method": "i2-termid-registry", "srcId": eid, "srcKind": kind,
    } for kind, eid, path, tid, key in orc.edges()]
    write_jsonl(extracted / "relinks" / "entity_locale.jsonl", rows)


def write_reverse_index(extracted: Path, orc: SearchOracle):
    usages = {}
    for kind, eid, path, tid, key in orc.edges():
        usages.setdefault(key, []).append(
            {"fieldPath": path, "srcId": eid, "srcKind": kind})
    rows = [{"buildId": BUILD_ID, "locales": [], "termKey": k,
             "usages": sorted(usages[k], key=lambda u: (
                 u["srcKind"], u["srcId"], u["fieldPath"]))}
            for k in sorted(usages)]
    write_jsonl(extracted / "relinks" / "locale_term_entity.jsonl", rows)


def write_matrix(extracted: Path, *, cells=100, missing=73, modeled=24,
                 partial=3):
    nodes = ["config", "item", "room", "course", "staff", "student-type",
             "unlockable", "metagame-node", "campus-level", "scene"]
    statuses = (["missing"] * missing + ["modeled"] * modeled
                + ["partial"] * partial)
    assert len(statuses) == cells, "fixture matrix cells/status mismatch"
    pairs = []
    for i, status in enumerate(statuses):
        src = nodes[i % len(nodes)]
        dst = nodes[(i // len(nodes)) % len(nodes)]
        pairs.append({
            "cardinality": {"edges": 0 if status == "missing" else 3,
                            "perDst": "0..M", "perSrc": "0..N",
                            "srcEntitiesWithEdges":
                                0 if status == "missing" else 2},
            "dstKind": dst,
            "evidence": {"topFields":
                         {} if status == "missing"
                         else {"FixtureField": 3}},
            "joinKey": "fixture-key",
            "mechanism": "logic" if status == "missing" else "hard",
            "pairFiles": [] if status == "missing"
            else [f"relinks/{src}_{dst}.jsonl"],
            "srcKind": src, "status": status, "unblock": "fixture",
        })
    _write_json(extracted / "relinks" / "matrix.json", {
        "meta": {"buildId": BUILD_ID,
                 "enums": {"mechanism": ["hard", "logic", "inferred"],
                           "status": ["modeled", "partial", "missing"]},
                 "nodeUniverse": {"arithmetic":
                                  "10 nodes -> 100 ordered cells",
                                  "nodes": nodes}},
        "pairs": pairs,
    })


def write_guid_bridge(extracted: Path, *, dangling=1137):
    _write_json(extracted / "relinks" / "guid_bridge_report.json", {
        "buildId": BUILD_ID, "danglingDistinctGuids": dangling,
        "distinctGuids": 5584, "guidRefsTotal": 20170,
        "resolveRateAddress": 0.798, "resolveRateStub": 0.185,
        "resolvedToAddress": 16110, "resolvedToStub": 3747,
    })


def write_locale_join_report(extracted: Path, orc: SearchOracle):
    inst = orc.ls_instances()
    sentinel = sum(1 for *_a, p in inst if p["_termID"] == 0)
    resolved = len(orc.edges())
    _write_json(extracted / "relinks" / "locale_join_report.json", {
        "buildId": BUILD_ID,
        "codeRefTerms": {"auditPath": "fixtures/_searchlib",
                         "note": "fixture"},
        "coverageOnNonEmpty": round(resolved / (resolved + 2), 6),
        "instancesTotal": len(inst), "matrixKeyDiff": 0,
        "perKindHits": {}, "registryHits": resolved,
        "registryMisses": 2, "sentinelZero": sentinel,
        "unresolvedIds": [],
    })


def write_locales(extracted: Path, orc: SearchOracle):
    locales_dir = extracted / "locales"
    for loc in ALL_LOCALES:
        table = orc.table(loc)
        write_jsonl(locales_dir / f"{loc}.jsonl",
                    [{"id": k, "text": table[k]} for k in sorted(table)])
    write_jsonl(locales_dir / "base-overlay.jsonl",
                [{"id": k, "text": ""}
                 for k in sorted(KEY_TEXTS)])
    _write_json(locales_dir / "base-overlay-report.json", {
        "compositionPolicy": "mixed",
        "evidence": {"baseCellsSkippedAbsent": 0,
                     "baseCellsSkippedEmpty": len(KEY_TEXTS),
                     "baseOnlyKeys": 0, "baseRowCount": len(KEY_TEXTS),
                     "registrySources": 25, "registryTerms": len(KEY_TEXTS),
                     "termStatusForTranslation": len(KEY_TEXTS),
                     "termStatusNotForTranslation": 0}})
    matrix_keys = {}
    for k in sorted(KEY_TEXTS):
        matrix_keys[k] = {"baseOverlay": True,
                          "locales": sorted(l for l in ALL_LOCALES
                                            if k in orc.table(l))}
    _write_json(locales_dir / "locale-matrix.json",
                {"buildId": BUILD_ID, "keys": matrix_keys,
                 "locales": sorted(ALL_LOCALES)})


def write_identity(extracted: Path):
    _write_json(extracted / "identity.json", {
        "appid": 1649080, "buildId": BUILD_ID, "targetBuildId": BUILD_ID,
        "localeBundleCount": len(ALL_LOCALES) + 1,
    })


def _sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def write_stamps(extracted: Path, *, relink_exit=2, localisation_exit=0):
    stamps = extracted / ".stage-stamps"
    relink_files = ["relinks/entity_locale.jsonl",
                    "relinks/i2_term_registry.jsonl",
                    "relinks/locale_term_entity.jsonl",
                    "relinks/matrix.json",
                    "relinks/guid_bridge_report.json",
                    "relinks/locale_join_report.json"]
    outputs = {rel: _sha_file(extracted / rel) for rel in relink_files}
    identity = hashlib.sha256("\n".join(
        f"{k}:{v}" for k, v in sorted(outputs.items())).encode()).hexdigest()
    _write_json(stamps / "relink.json", {
        "exitCode": relink_exit, "finishedAt": "2026-08-26T00:00:00Z",
        "identity": identity, "outputs": outputs})
    loc_files = ([f"locales/{loc}.jsonl" for loc in ALL_LOCALES]
                 + ["locales/locale-matrix.json"])
    outputs_l = {rel: _sha_file(extracted / rel) for rel in loc_files}
    identity_l = hashlib.sha256("\n".join(
        f"{k}:{v}" for k, v in sorted(outputs_l.items())).encode()).hexdigest()
    _write_json(stamps / "localisation.json", {
        "exitCode": localisation_exit, "finishedAt": "2026-08-26T00:00:00Z",
        "identity": identity_l, "outputs": outputs_l})


def write_item_joins(extracted: Path):
    """relinks/item_item.jsonl — the OPTIONAL pre-ruling-4 input, PENDING
    shape: 1 GameItem variation edge + 1 name-convention twin edge + 2
    unrelated PPtr rows (the real file's 155-row noise analog)."""
    rows = [
        {"buildId": BUILD_ID, "dstId": "Item_Construction_Lite",
         "dstKind": "item", "evidence": {"fieldPath": "GameItem"},
         "inferred": False, "mechanism": "hard", "method": "pptr-int-ref",
         "srcId": "Item_Variation_Construction", "srcKind": "item"},
        {"buildId": BUILD_ID, "dstId": "Item_Sword_Lite",
         "dstKind": "item",
         "evidence": {"fieldPath": "DefinitionID",
                      "twin": "Item_Sword_Lite"},
         "inferred": True, "mechanism": "inferred",
         "method": "name-convention:_Lite-twin",
         "srcId": "Item_Sword_Full", "srcKind": "item"},
        {"buildId": BUILD_ID, "dstId": "Item_Testing_Stone",
         "dstKind": "item", "evidence": {"fieldPath": "Item"},
         "inferred": False, "mechanism": "hard", "method": "pptr-object",
         "srcId": "Item_Pointer_Related", "srcKind": "item"},
        {"buildId": BUILD_ID, "dstId": "Item_Gem", "dstKind": "item",
         "evidence": {"fieldPath": "references.00000000._item"},
         "inferred": False, "mechanism": "hard", "method": "pptr-object",
         "srcId": "Item_Pointer_Related", "srcKind": "item"},
    ]
    rows.sort(key=lambda r: (r["srcId"], r["dstId"]))
    write_jsonl(extracted / "relinks" / "item_item.jsonl", rows)


def _write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2,
                               sort_keys=True) + "\n",
                    encoding="utf-8", newline="\n")


def build_search_upstream(extracted: Path) -> SearchOracle:
    """Materialize §4's COMPLETE stage-12 upstream set synthetically
    (pending-join steady state; the alias input rides separately via
    alias_input())."""
    extracted = Path(extracted)
    orc = SearchOracle()
    write_identity(extracted)
    write_locales(extracted, orc)
    write_stubs(extracted)
    write_registry(extracted)
    write_entity_locale(extracted, orc)
    write_reverse_index(extracted, orc)
    write_matrix(extracted)
    write_guid_bridge(extracted)
    write_locale_join_report(extracted, orc)
    write_item_joins(extracted)
    write_stamps(extracted)
    return orc


@contextmanager
def alias_input(pack_dir: Path, extracted: Path, *,
                dangling=False, rows=None):
    """Expose the OPTIONAL curated alias input at its contracted
    pack-relative path (+ extraction-root copy) for the alias-PRESENT
    legs; restored after. Never clobbers foreign state."""
    payload = list(SEED_ALIAS_ROWS if rows is None else rows)
    if dangling:
        payload = payload + [dict(DANGLING_ALIAS_ROW)]
    written = []
    for base in (pack_dir, extracted):
        p = Path(base) / ALIAS_INPUT_REL
        if p.exists():
            continue
        p.parent.mkdir(parents=True, exist_ok=True)
        write_jsonl(p, sorted(payload, key=lambda r: r["courseId"]))
        written.append(p)
    try:
        yield
    finally:
        for p in written:
            p.unlink(missing_ok=True)
            try:
                p.parent.rmdir()
            except OSError:
                pass


# --- real-corpus scratch (client-gated legs; hostless, no game dir) -------

REAL_INPUT_FILES = (
    "identity.json",
    "relinks/entity_locale.jsonl",
    "relinks/i2_term_registry.jsonl",
    "relinks/locale_term_entity.jsonl",
    "relinks/matrix.json",
    "relinks/guid_bridge_report.json",
    "relinks/locale_join_report.json",
    ".stage-stamps/relink.json",
    ".stage-stamps/localisation.json",
)


def selective_real_scratch(src_extracted: Path, dst: Path) -> Path:
    """Scratch extraction root holding EXACTLY stage-12's upstream set
    copied from the committed real corpus (plus stubs/ and locales/)."""
    import shutil

    dst = Path(dst)
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True)
    src_extracted = Path(src_extracted)
    for rel in REAL_INPUT_FILES:
        s = src_extracted / rel
        if s.is_file():
            (dst / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(s, dst / rel)
    for dirname in ("stubs", "locales"):
        s = src_extracted / dirname
        if s.is_dir():
            shutil.copytree(s, dst / dirname)
    return dst


# --- suite-side helpers -----------------------------------------------------

def ratio_band_ok(lines_bytes: int, docs: int, low: int, high: int) -> bool:
    """AC4 band: low·D ≤ B ≤ high·D (D = the shard's own doc count)."""
    if docs <= 0:
        return lines_bytes == 0
    return low * docs <= lines_bytes <= high * docs


ISO_STAMP_RE = re.compile(r"\d{4}-\d{2}-\d{2}T")


def scan_for_timestamps(text: str):
    hits = [m.group(0) for m in ISO_STAMP_RE.finditer(text)]
    if '"finishedAt"' in text or '"finished"' in text:
        hits.append("finishedAt")
    return hits
