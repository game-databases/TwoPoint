"""Synthetic upstream corpora + oracle helpers for the piece-07 stage-9
`locale-proof` blind test suite (TestWriter seat).

Everything here is built from
docs/specs/piece-07-locale-proof.mdx (Revision 3) +
docs/rulings/arbiter-piece07-spec.mdx ALONE — no implementation file is
read or imported. The fixture corpus satisfies §4's literal upstream set
(`locales/<locale>.jsonl` ×13 — the runner pre-check refuses anything less,
so the "mini roster" of §10 rides as a 3-locale HAND-COMPUTED CORE inside a
13-table layout):

  core ... de (comparator) + en (pivot) + ja carry the designed holes
  extras . the 10 remaining pinned locales hold EXACTLY the 8-key all-locales
           group with the EN text copied verbatim (deliberately untranslated
           filler: exercises identity-to-pivot without touching any core pin)
  kinds .. item, course, campus-level, unlockable, config populated;
           room/staff/student-type/metagame-node present but empty

Hand-derived census (verified twice, arbiter-style: Σ(rows) over locales ==
Σ(#locales-holding × keys) over the histogram):

  presenceHistogram        {"13": 8, "2": 6, "1": 5}         (union 19)
  rows/holes   en 18/1 · de 12/7 · ja 11/8 · each extra 8/11
               (Σ rows = 121 = 13·8 + 2·6 + 1·5 ✓)
  registry                 22 rows / 21 distinct keys (1 non-canonical dupe)
  emptyCellsSkipped        en 3 · de 9 · ja 10 · extras 13  (= registryKeys − rows)
  allThirteenShare         8/19 = "42.11%" ; registry universe 8/21 = "38.10%"
  shareOfUnion             en "94.74%" · de "63.16%" · ja "57.89%" · extras "42.11%"
  enMissingKeys            ["UI/General/NameSeparator"]
  baseOnlyVsEn             3 keys (Buildings/…, UI/EmptyString…, NameSeparator)
  singleLocaleKeys         count 5, allEn false
  enPlusKoCluster          Meta/CareerGoals ×2 held by en+ja (cluster ≥2 keys)
  identityToPivot          family 4 Items/*_Name keys;
                           en 4/3(residual Gamma) · de 1/0 STRUCTURAL ·
                           ja 3/2(residual Gamma); every extra mirrors the ja
                           shape (3/2, residual Gamma); identicalInEveryHolding 1 ea.
  entity census            instances 10 · sentinel 1 · resolved 7 · misses 2
                           coverageOnNonEmpty = 7/9        (locale-independent)
  stubRows 16              joined 5 (item 2, course 1, unlockable 1, config 1)
  unjoined 11              literal 4 · no-display 1 · kernel 2 · residue 4
  availabilityRows 5       == deduped registryHits (§2.2 formula)
  holes en 1 / de 7 / ja 8 / extras 11 per locale-file; holeNamespaces shift
  ledgerRows 5 (open tree) dangling 1 + closable 1 + unjoined + course-hole
                           + alias-absent  →  exit 2 steady state
  closed tree              ledger EMPTY → exit 0
"""
from __future__ import annotations

import json
import shutil
from contextlib import contextmanager
from pathlib import Path

from _validators import (
    BUILD_ID, KIND_TO_FILE, LOCALE_TABLE, read_json, read_jsonl, write_jsonl,
)

STAGE_ID = "locale-proof"
SCRIPT_REL = "tools/stage9_locale_proof.py"
SCRIPT_DEPS = ["stage9_locale_proof.py", "tpc_common.py", "log_util.py"]

# Canonical registry order below locale-proof (arbiter R1): index 9 sits
# AFTER relink (6) and BEFORE contracts=10 / media=11 / search-corpus=12.
PREDECESSOR_STAGE_IDS = ("verify-client", "decompile", "harvest-catalog",
                         "harvest-bundles", "localisation",
                         "emit-stub-datasets", "relink")
CANONICALLY_LATER_SIBLINGS = ("contracts", "media", "search-corpus")

PROOF_DIR = "locales/proof"
AVAILABILITY_JSONL = "relinks/locale_availability.jsonl"
AVAILABILITY_REPORT = "relinks/locale_availability.report.json"

# §L5 surface vocabulary — PINNED, 16 rows, none droppable; kind default
# `keyed`, the ONLY `prose` exceptions editorial-prose + seo-meta-templates.
CHROME_SURFACES = (
    "nav-labels", "buttons-actions", "filters-sort", "tooltips-help",
    "empty-states", "error-pages", "search-states", "pagination",
    "map-controls", "tool-ui", "ugc-surfaces", "consent-banner",
    "editorial-prose", "seo-meta-templates", "locale-switcher",
    "untranslated-filler",
)
PROSE_SURFACES = ("editorial-prose", "seo-meta-templates")

# §L6/R3 ledger code vocabulary (granularity pinned per arbiter R3).
LEDGER_CODE_DANGLING = "registry-miss-dangling"
LEDGER_CODE_CLOSABLE = "registry-miss-closable"
LEDGER_CODE_UNJOINED = "entity-unjoined"
LEDGER_CODE_COURSE_OPEN = "course-name-join-open"
LEDGER_CODE_ALIAS_ABSENT = "alias-input-absent"
LEDGER_CODE_G8 = "dlc-out-of-install-scope"
ALIAS_INPUT_REL = "data/sources/derived/course-name-aliases.jsonl"

# §L2 unjoined class vocabulary (pinned; consumer-warning label semantics).
CLASS_LITERAL = "english-only-literal"
CLASS_NO_DISPLAY = "no-display-field"
CLASS_KERNEL = "internal-kernel"
CLASS_RESIDUE = "unclassified-residue"
KERNEL_PREFIX_RE = r"^(Item_Editor.*|Unused_Item.*|Item_LS.*|A_LS_Variation.*|Variation_.*)$"

# §L4 pinned signature CONSTANTS (scout §4.4 + verifyB attack 4); the
# dumpCsLine VALUES are measured-per-run and never pinned.
FALLBACK_SYMBOL_SUBSTRINGS = (
    "TryGetFallbackTranslation",
    "LoadLanguageData",
    "GetTranslation",
    "TryGetTranslation",
)

# --- regressionVector spelling (arbiter R3: flat dotted paths, 57 members) ----

CORE_VECTOR_MEMBERS = (
    "unionKeys", "allThirteenKeys", "resolvedEdges", "registryMisses",
    "coverageNumerator", "availabilityRowCount", "registryRows",
    "registryDistinctKeys", "matrixKeyDiff", "orphansAKeys", "orphansB",
    "uiReferenced", "chromeSurfaces",
)
VECTOR_MEMBER_GRAMMAR = (
    r"^(unionKeys|allThirteenKeys|rows\.[A-Za-z-]+|holes\.[A-Za-z-]+|"
    r"resolvedEdges|registryMisses|coverageNumerator|availabilityRowCount|"
    r"joined\.[a-z-]+|availRows\.[a-z-]+|registryRows|registryDistinctKeys|"
    r"matrixKeyDiff|orphansAKeys|orphansB|uiReferenced|chromeSurfaces)$"
)
REAL_VECTOR_MEMBER_COUNT = 57

# --- real-corpus pins (client-gated legs only; spec §2 fact table) ------------

REAL = {
    "unionKeys": 15666,
    "allThirteenKeys": 15369,
    "histogram": {"13": 15369, "12": 46, "11": 27, "10": 1, "9": 2,
                  "3": 1, "2": 15, "1": 205},
    "rate_union": "98.10%",
    "rate_registry": "98.07%",
    "rows": {"en": 15665, "ko": 15457, "zh-Hant": 15446, "zh-Hans": 15445,
             "fr": 15445, "de": 15445, "it": 15445, "pl": 15445,
             "pt-BR": 15443, "tr": 15443, "es": 15440, "ru": 15422,
             "ja": 15371},
    "holes": {"en": 1, "ko": 209, "zh-Hant": 220, "zh-Hans": 221, "fr": 221,
              "de": 221, "it": 221, "pl": 221, "pt-BR": 223, "tr": 223,
              "es": 226, "ru": 244, "ja": 295},
    "challenge_holes_non_en": 115,
    "challenge_holes_ja": 119,
    "levels_holes_non_en": 32,
    "instancesTotal": 20070,
    "sentinelZero": 9101,
    "resolvedEdges": 10964,
    "registryMisses": 5,
    "coverageNumerator": 10959,
    "ruByteIdentical": 301,
    "ruIdenticalDeDiffers": 297,
    "residualFour": [
        "Items/DLC_Ghost/Mausoleum_Name",
        "Items/DLC_Space/Planetarium_Name",
        "Items/Ghost_DLC/Dolly_Name",
        "Items/Ghost_DLC/Theremin_Name",
    ],
    "workedExampleKey": "Items/Library/Reception_Giant_Name",
    "workedExampleText": "Giant Library Reception",
    "stubRowsTotal": 13443,
    "joinedTotal": 5850,
    "availabilityRowCount": 5850,
    "unjoinedTotal": 7593,
    "unjoinedPerKind": {"config": 5252, "item": 1850, "unlockable": 372,
                        "metagame-node": 64, "course": 28,
                        "campus-level": 17, "room": 10, "student-type": 0,
                        "staff": 0},
    "kernelRowsItem": 1438,
    "registryRows": 15675,
    "registryDistinctKeys": 15672,
    "nonCanonicalRows": 3,
    "statusForTranslation": 15400,
    "statusNotForTranslation": 275,
    "referencedKeys": 6526,
    "usageEdges": 10964,
    "distinctEntities": 5850,
    "orphansARows": 9148,
    "orphansAKeys": 9146,
    "codeRefTerms": 586,
    # AC8 pins MEMBERSHIP + en.jsonl presence, not order; the emitted array
    # is sorted (piece-1 console/write discipline: sorted enumeration), so
    # the oracle list is sorted to match.
    "closableKeys": [
        "Code/InspectorItem_TooltipCancelUpgrade",
        "Code/InspectorItem_TooltipRequiresJanitorMechanics",
        "Code/Staff_Unassigned",
    ],
    # ONE ROW PER termId, ASCENDING numeric sort (F3 / arbiter ruling:
    # "-1451566921 < -1172386361 holds")
    "danglingRows": [
        {"termId": -1451566921, "fieldPath": "WantsMessage",
         "dev": "Wants a {ITEM}", "srcKind": "item",
         "onIds": ["Unused_PersonalGoal_Item_Gym_Vaulting_Horse"]},
        {"termId": -1172386361, "fieldPath": "WantsMessage",
         "dev": "Wants a {ITEM}", "srcKind": "item",
         "onIds": ["Unused_PersonalGoal_Item_AnyExterior"]},
    ],
    "baseOverlayRows": 15672,
    "baseOverlayEmptyTextRows": 0,
    "languageSources": 26,
    "termBearingSources": 25,
    "rawTermsDecoded": 15677,
    "baseOnlyKeysVsEn": [
        "Buildings/BuildingGeneric_Description",
        "Levels/DLC_Hospital/LakeHospital/Inbox_Fires_Title_Unused",
        "UI/EmptyStringNoTranslate",
        "UI/General/DLC/MSStore",
        "UI/General/NameSeparator",
        "UI/Messages/MissionStatus",
        "UI/Messages/Suggestion",
    ],
    "enMissingKeys": ["UI/General/NameSeparator"],
    "uiRegistryKeys": 2218,
    "uiReferenced": 532,
    "uiFree": 1686,
    "inputNamespace": 164,
    "generalNamespace": 143,
    "uiSettingsSource": 187,
    "topLevelNamespaces": 52,
    "localizeBindings": 11312,
    "freeNarrativeKeys": 9146,
    "ledgerRows": 7,
    "chromeSurfaces": 16,
    "identitySeeds": {  # F13 pinned-rule exact percentages
        ("item", "ja"): "10.96%", ("item", "ru"): "23.03%",
        ("unlockable", "ja"): "86.96%", ("unlockable", "ru"): "91.30%",
        ("room", "ru"): "19.05%", ("student-type", "ru"): "37.04%",
        ("metagame-node", "ru"): "28.21%",
    },
}
REAL_LEDGER_CODES = {
    LEDGER_CODE_DANGLING: 2,
    LEDGER_CODE_CLOSABLE: 1,
    LEDGER_CODE_UNJOINED: 1,
    LEDGER_CODE_COURSE_OPEN: 1,
    LEDGER_CODE_ALIAS_ABSENT: 1,
    LEDGER_CODE_G8: 1,
}


# ============================================================================
# fixture corpus definition (hand-computed; see module docstring)
# ============================================================================

FIXTURE_LOCALES = ("de", "en", "ja")
# the 10 filler locales: pinned vocabulary minus the hand-computed core
EXTRA_LOCALES = tuple(sorted(set(LOCALE_TABLE.values()) - set(FIXTURE_LOCALES)))
ALL_FIXTURE_LOCALES = tuple(sorted(FIXTURE_LOCALES + EXTRA_LOCALES))

# termKey -> {locale: text}; locales absent from the dict MISS the key.
KEYS_ALL3 = {
    "UI/General/Greeting": {"de": "Hallo", "en": "Hello", "ja": "こんにちは"},
    "Items/Alpha/Thing_Name": {"de": "Stein", "en": "Stone", "ja": "Stone"},
    "Items/Alpha/Thing_Description": {"de": "Ein Stein", "en": "A stone",
                                      "ja": "Stone (desc)"},
    "Items/Beta/Gadget_Name": {"de": "Lampe", "en": "Lamp", "ja": "Lamp"},
    "Items/Gamma/Residual_Name": {"de": "Doll", "en": "Doll", "ja": "Doll"},
    "Courses/Courses/Clowns_Description": {"de": "Komik", "en": "Comedy",
                                           "ja": "コメディ"},
    "Meta/Global_Tagline": {"de": "Welt", "en": "World", "ja": "ワールド"},
    "UI/Kudosh_Title": {"de": "Kudosch", "en": "Kudosh", "ja": "クドシュ"},
}
KEYS_PAIR2 = {
    "Items/Delta/Hole_Name": {"de": "Maulwurf", "en": "Mole"},
    "Challenge/Evt01/Title": {"de": "Ereignis 1", "en": "Event 1"},
    "Challenge/Evt02/Title": {"de": "Ereignis 2", "en": "Event 2"},
    "Levels/L1/Name": {"de": "Ebene 1", "en": "Level 1"},
    "Meta/CareerGoals/Club_A": {"en": "Chess Club", "ja": "チェス部"},
    "Meta/CareerGoals/Club_B": {"en": "Drama Club", "ja": "演劇部"},
}
KEYS_SOLO = {
    "UI/General/NameSeparator": {"ja": "・"},
    "Solo/Advisor/Note": {"en": "Note"},
    "Items/Beta/Gadget_Description": {"en": "Bright"},
    "Code/Staff_Unassigned": {"en": "Staff Unassigned"},
    "Code/InspectorItem_TooltipCancelUpgrade": {"en": "Cancel upgrade"},
}
KEYS_BASE_ONLY = ("Buildings/BuildingGeneric_Description",
                  "UI/EmptyStringNoTranslate")
# alias-input term keys (exist ONLY when the alias input is supplied)
KEYS_ALIAS = {
    "Marketing/Courses/Clowns_Name": {"de": "Clowns", "en": "Clowns",
                                      "ja": "クラウン"},
    "Marketing/Courses/Magic_Name": {"de": "Magie", "en": "Magic",
                                     "ja": "魔法"},
}

DUPE_KEY = "Items/Gamma/Residual_Name"      # non-canonical second row
NOT_FOR_TRANSLATION = set(KEYS_BASE_ONLY)

TERM_IDS = {  # termKey -> canonical termId (stable, negative, distinct)
    "UI/General/Greeting": -1100000001,
    "Items/Alpha/Thing_Name": -1100000002,
    "Items/Alpha/Thing_Description": -1100000003,
    "Items/Beta/Gadget_Name": -1100000004,
    "Items/Gamma/Residual_Name": -1100000005,
    "Courses/Courses/Clowns_Description": -1100000006,
    "Meta/Global_Tagline": -1100000007,
    "UI/Kudosh_Title": -1100000008,
    "Items/Delta/Hole_Name": -1100000009,
    "Challenge/Evt01/Title": -1100000010,
    "Challenge/Evt02/Title": -1100000011,
    "Levels/L1/Name": -1100000012,
    "Meta/CareerGoals/Club_A": -1100000013,
    "Meta/CareerGoals/Club_B": -1100000023,
    "UI/General/NameSeparator": -1100000014,
    "Solo/Advisor/Note": -1100000015,
    "Items/Beta/Gadget_Description": -1100000016,
    "Code/Staff_Unassigned": -1100000017,
    "Code/InspectorItem_TooltipCancelUpgrade": -1100000018,
    "Buildings/BuildingGeneric_Description": -1100000019,
    "UI/EmptyStringNoTranslate": -1100000020,
    "Marketing/Courses/Clowns_Name": -1100000021,
    "Marketing/Courses/Magic_Name": -1100000022,
}
DUPE_TERM_ID = -1100000900                  # second row for DUPE_KEY

MISSING_DANGLING_TERMID = -999999901        # no registry row anywhere
MISSING_CLOSABLE_TERMID = -999999902


def _ls(term_id, dev):
    """LocalisedString payload shape ({_dev,_termID}) as harvested."""
    return {"_dev": dev, "_termID": term_id}


# (kind, id, fields, axes-or-None); fields mix LS payloads and plain literals.
ENTITIES_OPEN = [
    ("item", "Item_Alpha_Display",
     {"Name": _ls(TERM_IDS["Items/Alpha/Thing_Name"], "Stone"),
      "Description": _ls(TERM_IDS["Items/Alpha/Thing_Description"],
                         "A stone")},
     ["base"]),
    ("item", "Item_Editor_Kernel_One", {"Name": "Editor Thing"}, None),
    ("item", "Unused_Item_Kernel_Two", {"Tier": 3}, None),
    ("item", "Item_Plain_Unjoined", {"Flavor": "plain text"}, None),
    ("item", "Item_Partial_Join",
     {"Name": _ls(TERM_IDS["Items/Alpha/Thing_Name"], "Stone"),
      "Description": _ls(TERM_IDS["Items/Beta/Gadget_Description"],
                         "Bright")},
     None),
    ("item", "Item_Miss_Dangling",
     {"Name": _ls(MISSING_DANGLING_TERMID, "Wants a {FIXTURE}")}, None),
    ("course", "Course_Clowns",
     {"Description": _ls(TERM_IDS["Courses/Courses/Clowns_Description"],
                         "Comedy")},
     None),
    ("course", "Course_Magic", {}, None),
    ("campus-level", "Campus_Level_NoDisplay", {"SortOrder": 1}, None),
    ("campus-level", "Campus_Level_Blank", {"Name": "Blank Level"}, None),
    ("campus-level", "Campus_Level_Test", {"Name": "Test Level"}, None),
    ("unlockable", "Unlock_Bright_Literal", {"Name": "Bright"}, None),
    ("unlockable", "Unlock_Cupid", {"Name": "Cupid Relationship"}, None),
    ("unlockable", "Unlock_Kudosh",
     {"Name": _ls(TERM_IDS["UI/Kudosh_Title"], "Kudosh")}, None),
    ("config", "Config_Global",
     {"Name": _ls(TERM_IDS["Meta/Global_Tagline"], "World"),
      "FlavorText": _ls(0, "")},
     None),
    ("config", "Config_CodeRef",
     {"Tooltip": _ls(MISSING_CLOSABLE_TERMID,
                     "InspectorItem_TooltipCancelUpgrade")},
     None),
]
# closed tree: every remaining entity joins; no miss, no unjoined rows
CLOSED_ENTITY_IDS = {
    "Item_Alpha_Display", "Item_Partial_Join", "Course_Clowns",
    "Unlock_Kudosh", "Config_Global",
}

ALIAS_ROWS = [
    {"courseId": "Course_Clowns", "termKey": "Marketing/Courses/Clowns_Name",
     "method": "marketing-campaign-hard-join", "inferred": True,
     "sourceRefs": ["fixtures/_prooflib"]},
    {"courseId": "Course_Magic", "termKey": "Marketing/Courses/Magic_Name",
     "method": "marketing-campaign-hard-join", "inferred": True,
     "sourceRefs": ["fixtures/_prooflib"]},
]


class FixtureInfo:
    """What the builder wrote + independent (oracle) derivations."""

    def __init__(self, extracted: Path, locales, keys, entities, closed,
                 aliased):
        self.extracted = Path(extracted)
        self.locales = tuple(sorted(locales))
        self.keys = keys              # termKey -> {locale: text}
        self.entities = entities      # (kind, id, fields, axes)
        self.closed = closed
        self.aliased = aliased
        self.pivot = "en"
        self.comparator = "de"

        held = {loc: {k for k, texts in keys.items() if loc in texts}
                for loc in self.locales}
        self.held = held
        self.union = set(keys)        # union of the named tables
        self.registry_keys = set(keys) | set(KEYS_BASE_ONLY)
        self.name_family = sorted(
            k for k in self.registry_keys
            if k.startswith("Items/") and k.endswith("_Name"))

    # -- L1 oracle -----------------------------------------------------------
    def histogram(self):
        out = {}
        for k in self.union:
            n = sum(1 for loc in self.locales if k in self.held[loc])
            out[n] = out.get(n, 0) + 1
        return {str(n): c for n, c in sorted(out.items(), reverse=True)}

    def per_locale(self):
        rows = {loc: len(self.held[loc]) for loc in self.locales}
        holes = {loc: len(self.union - self.held[loc])
                 for loc in self.locales}
        return rows, holes

    def empty_cells_skipped(self):
        return {loc: len(self.registry_keys) - len(self.held[loc])
                for loc in self.locales}

    def hole_namespaces(self):
        out = {}
        for loc in self.locales:
            ns = {}
            for k in self.union - self.held[loc]:
                seg = k.split("/", 1)[0]
                ns[seg] = ns.get(seg, 0) + 1
            out[loc] = ns
        return out

    def base_only_vs_en(self):
        return sorted(self.registry_keys - self.held[self.pivot])

    def identity_tier(self, loc):
        """The frozen predicates: byteIdenticalToEn / identicalAndDeDiffers
        (de comparator FROZEN for every row) over HELD keys."""
        piv = self.pivot
        cmp_ = self.comparator
        identical, de_differs, residual, every = [], [], [], []
        for k in self.name_family:
            if k not in self.held[loc] or k not in self.held[piv]:
                continue
            if self.keys[k][loc] == self.keys[k][piv]:
                identical.append(k)
                holding = [l for l in self.locales if l in self.keys[k]]
                if cmp_ in self.keys[k] and self.keys[k][cmp_] != \
                        self.keys[k][piv]:
                    de_differs.append(k)
                else:
                    residual.append(k)
                if all(self.keys[k].get(l) == self.keys[k][piv]
                       for l in holding):
                    every.append(k)
        return {"keysHeld": sum(1 for k in self.name_family
                                if k in self.held[loc]),
                "byteIdenticalToEn": len(identical),
                "identicalAndDeDiffers": len(de_differs),
                "identicalInEveryHoldingLocale": len(every),
                "_residual": sorted(residual)}

    # -- L2/L3 oracle ---------------------------------------------------------
    def ls_instances(self):
        """(kind, id, fieldPath, payload) for every LocalisedString field."""
        out = []
        for kind, eid, fields, _axes in self.entities:
            for fname in sorted(fields):
                v = fields[fname]
                if isinstance(v, dict) and "_termID" in v and "_dev" in v:
                    out.append((kind, eid, fname, v))
        return out

    def resolved_edges(self):
        """Sorted (srcKind,srcId,fieldPath,dstId) edges whose termId resolves."""
        by_id = {TERM_IDS[k]: k for k in self.registry_keys}
        by_id[DUPE_TERM_ID] = DUPE_KEY
        edges = []
        for kind, eid, fpath, payload in self.ls_instances():
            key = by_id.get(payload["_termID"])
            if key is not None:
                edges.append((kind, eid, fpath, key))
        return sorted(edges)

    def joined_pairs(self):
        return sorted({(k, e) for k, e, _f, _t in self.resolved_edges()})

    def name_bearing(self):
        """First fieldPath containing 'name' per entity (case-insensitive
        substring, per the pinned metricRule), in sorted-edge order."""
        seen = {}
        for kind, eid, fpath, key in self.resolved_edges():
            if "name" in fpath.lower() and (kind, eid) not in seen:
                seen[(kind, eid)] = (fpath, key)
        return seen

    def unjoined_rows(self):
        """Zero-resolved-edge stub rows. Class labels are asserted ONLY where
        the spec pins them: item kernel prefixes (L2 prefix map), plain
        non-empty Name literals (+ the coincidence flag), and campus-level
        rows with no Name field. Everything else is the spec's own
        'everything else' bucket — its exact label is implementation
        freedom the suite does not pin (see §10 L2)."""
        import re

        joined = set(self.joined_pairs())
        en_texts = {t.get(self.pivot, "") for t in self.keys.values()}
        rows = []
        for kind, eid, fields, _axes in self.entities:
            if (kind, eid) in joined:
                continue
            row = {"kind": kind, "id": eid}
            if re.match(KERNEL_PREFIX_RE, eid):
                row["class"] = CLASS_KERNEL
            elif isinstance(fields.get("Name"), str) and \
                    fields["Name"].strip():
                row["class"] = CLASS_LITERAL
                row["nameLiteral"] = fields["Name"]
                row["coincidesWithEnTermText"] = \
                    fields["Name"] in en_texts
            elif "Name" not in fields:
                row["class"] = CLASS_NO_DISPLAY
            rows.append(row)
        rows.sort(key=lambda r: (r["kind"], r["id"]))
        return rows


# ============================================================================
# builders
# ============================================================================

def _write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2,
                               sort_keys=True) + "\n", encoding="utf-8",
                    newline="\n")


def build_locale_proof_upstream(extracted: Path, *, closed=False,
                                aliased=False,
                                locales=FIXTURE_LOCALES) -> FixtureInfo:
    """Materialize §4's COMPLETE upstream set synthetically (no Unity bytes):
    identity.json + bundle-roster.jsonl + locales/{tables,base-overlay,
    report,matrix} + stubs/<kind>.jsonl ×9 + relinks/{entity_locale,
    i2_term_registry,locale_term_entity,locale_join_report}."""
    extracted = Path(extracted)
    keys = {}
    for src in (KEYS_ALL3, KEYS_PAIR2, KEYS_SOLO):
        keys.update(src)
    if aliased:
        keys.update(KEYS_ALIAS)
    entities = [e for e in ENTITIES_OPEN
                if not closed or e[1] in CLOSED_ENTITY_IDS]
    if closed and not aliased:      # closed trees ship the alias input too
        aliased = True
        keys.update(KEYS_ALIAS)

    # §4 gate compliance: every one of the 13 pinned locales gets a table.
    # Extras hold exactly the all-locales group (plus alias keys when present),
    # with EN text copied verbatim — untranslated filler by construction.
    allgroup = dict(KEYS_ALL3)
    if aliased:
        allgroup.update(KEYS_ALIAS)
    tables = {}
    for loc in ALL_FIXTURE_LOCALES:
        if loc in EXTRA_LOCALES:
            tables[loc] = {k: texts["en"] for k, texts in allgroup.items()}
        else:
            tables[loc] = {k: texts[loc] for k, texts in keys.items()
                           if loc in texts}
    # FixtureInfo sees the FULL 13-locale key map (extras included) so every
    # oracle derivation matches what the tables actually hold.
    full_keys = {k: {} for k in keys}
    for k in full_keys:
        for loc, rows in tables.items():
            if k in rows:
                full_keys[k][loc] = rows[k]
    info = FixtureInfo(extracted, ALL_FIXTURE_LOCALES, full_keys, entities,
                       closed, aliased)
    locales = ALL_FIXTURE_LOCALES

    # identity.json + bundle-roster.jsonl (mini roster, stage-0 shapes)
    _write_json(extracted / "identity.json", {
        "appid": 1649080, "buildId": BUILD_ID, "targetBuildId": BUILD_ID,
        "localeBundleCount": len(locales) + 1,
        "expectedBundles": {"aa": 158, "dlc-space": 10, "dlc-ghost": 8},
    })
    aa_rel = "TPC_Data/StreamingAssets/aa/StandaloneWindows64"
    roster = [{"relpath": f"{aa_rel}/localisation_assets_localisation.bundle",
               "dirClass": "base", "bytes": 2048, "sceneFlag": "none",
               "localeFlag": "base", "buildId": BUILD_ID}]
    for loc in locales:
        roster.append({
            "relpath": f"{aa_rel}/localisation_assets_localisation_{loc}.bundle",
            "dirClass": "base", "bytes": 2048, "sceneFlag": "none",
            "localeFlag": loc, "buildId": BUILD_ID})
    write_jsonl(extracted / "bundle-roster.jsonl", roster)

    # all 13 pinned locales get a table (§4 gate); core locales carry the
    # designed holes, extras carry the en-copied all-locales group.
    locales_dir = extracted / "locales"
    for loc in ALL_FIXTURE_LOCALES:
        write_jsonl(locales_dir / f"{loc}.jsonl",
                    [{"id": k, "text": tables[loc][k]}
                     for k in sorted(tables[loc])])
    # base overlay: PURE master registry — keys/statuses, every text empty
    write_jsonl(locales_dir / "base-overlay.jsonl",
                [{"id": k, "text": ""}
                 for k in sorted(info.registry_keys)])
    _write_json(locales_dir / "base-overlay-report.json", {
        "compositionPolicy": "mixed",
        "differingTextSharedKeys": len(info.union),
        "evidence": {
            "baseCellsSkippedAbsent": 0,
            "baseCellsSkippedEmpty": len(info.registry_keys),
            "baseOnlyKeys": len(KEYS_BASE_ONLY),
            "baseRowCount": len(info.registry_keys),
            "registrySources": 26,
            "registryTerms": len(info.registry_keys),
            "termStatusForTranslation":
                len(info.registry_keys) - len(NOT_FOR_TRANSLATION),
            "termStatusNotForTranslation": len(NOT_FOR_TRANSLATION),
        },
    })
    matrix_keys = {}
    for k in sorted(info.registry_keys):
        matrix_keys[k] = {"baseOverlay": True,
                          "locales": sorted(l for l in locales
                                            if k in info.held[l])}
    _write_json(locales_dir / "locale-matrix.json",
                {"buildId": BUILD_ID, "keys": matrix_keys,
                 "locales": sorted(locales)})

    # stubs/<kind>.jsonl ×9 (populated kinds + empty companions)
    by_kind = {}
    for kind, eid, fields, axes in entities:
        row = {
            "id": eid, "kind": kind, "slug": None, "fields": fields,
            "source": {"bundle": "fixtures.bundle", "pathId": abs(hash(eid)) % 10**6,
                       "class": "FixtureConfig"},
            "provisional": True, "inferred": False,
            "method": "verbatim-copy", "buildId": BUILD_ID,
        }
        if axes:
            row["axes"] = list(axes)
        by_kind.setdefault(kind, []).append(row)
    for kind, fname in sorted(KIND_TO_FILE.items()):
        write_jsonl(extracted / "stubs" / fname,
                    sorted(by_kind.get(kind, []),
                           key=lambda r: r["id"]))

    # relinks side (stage-6 OUTPUT shapes, verbatim dialect)
    reg_rows = []
    for k in sorted(info.registry_keys):
        reg_rows.append({
            "buildId": BUILD_ID, "canonical": True,
            "locales": [], "sourceAsset": "I2LS_Fixture",
            "termId": TERM_IDS[k],
            "termKey": k,
            # measured I2 enum: 1 = ForTranslation, 0 = NotForTranslation
            "termStatus": 0 if k in NOT_FOR_TRANSLATION else 1,
            "termType": 0,
        })
    reg_rows.append({  # non-canonical duplicate (canonical-on-key, +1 row)
        "buildId": BUILD_ID, "canonical": False, "locales": [],
        "sourceAsset": "I2LS_Fixture", "termId": DUPE_TERM_ID,
        "termKey": DUPE_KEY, "termStatus": 1, "termType": 0,
    })
    write_jsonl(extracted / "relinks" / "i2_term_registry.jsonl", reg_rows)

    edges = []
    miss_refs = {}
    by_tid = {r["termId"]: r["termKey"] for r in reg_rows}
    for kind, eid, fpath, payload in info.ls_instances():
        tid = payload["_termID"]
        if tid == 0:
            # stage-6 dialect: sentinel-zero instances are EXCLUDED from
            # rows and COUNTED (declared-empty class G4) — never misses
            continue
        key = by_tid.get(tid)
        if key is None:
            # stage-6 dialect (`build_entity_locale`): registry MISSES land
            # ONLY in locale_join_report.unresolvedIds — entity_locale.jsonl
            # carries RESOLVED rows exclusively.
            miss_refs.setdefault(tid, []).append(
                {"srcKind": kind, "srcId": eid, "fieldPath": fpath})
            continue
        edges.append({
            "buildId": BUILD_ID, "dstId": key,
            "dstKind": "locale-term",
            "evidence": {"dev": payload["_dev"], "fieldPath": fpath,
                         "locales": [], "termId": tid},
            "inferred": False, "mechanism": "hard",
            "method": "i2-termid-registry", "srcId": eid, "srcKind": kind,
        })
    edges.sort(key=lambda r: (r["srcKind"], r["srcId"],
                              r["evidence"]["fieldPath"]))
    write_jsonl(extracted / "relinks" / "entity_locale.jsonl", edges)

    usages = {}
    for kind, eid, fpath, key in info.resolved_edges():
        usages.setdefault(key, []).append(
            {"fieldPath": fpath, "srcId": eid, "srcKind": kind})
    reverse = [{"buildId": BUILD_ID, "locales": [], "termKey": k,
                "usages": sorted(usages[k],
                                 key=lambda u: (u["srcKind"], u["srcId"],
                                                u["fieldPath"]))}
               for k in sorted(usages)]
    write_jsonl(extracted / "relinks" / "locale_term_entity.jsonl", reverse)

    inst = info.ls_instances()
    sentinel = sum(1 for *_a, p in inst if p["_termID"] == 0)
    resolved = len(info.resolved_edges())
    misses = len(inst) - sentinel - resolved
    _write_json(extracted / "relinks" / "locale_join_report.json", {
        "buildId": BUILD_ID,
        "codeRefTerms": {"auditPath": "fixtures/_prooflib", "note": "fixture"},
        "coverageOnNonEmpty": round(resolved / (resolved + misses), 6)
                              if (resolved + misses) else 1.0,
        "instancesTotal": len(inst), "matrixKeyDiff": 0,
        "perKindHits": {}, "registryHits": resolved,
        "registryMisses": misses, "sentinelZero": sentinel,
        "unresolvedIds": [{"termId": tid, "sampleRefs": miss_refs[tid]}
                          for tid in sorted(miss_refs)],
    })
    return info


def seed_v2_availability(extracted: Path, info: FixtureInfo):
    """Pre-populate the canonical path with VALID v2 rows (post-stage-9
    state) for the single-writer / refusal-guard legs."""
    avail = extracted / AVAILABILITY_JSONL
    rows = []
    for kind, eid in info.joined_pairs():
        rows.append({
            "kind": kind, "id": eid,
            "availableLocales": sorted(info.locales),
            "partialLocales": [], "namedLocales": sorted(info.locales),
            "identityToPivotLocales": [], "fieldPresence": {},
            "buildId": BUILD_ID,
        })
    rows.sort(key=lambda r: (r["kind"], r["id"]))
    write_jsonl(avail, rows)
    return avail


@contextmanager
def alias_input(pack_dir: Path, extracted: Path):
    """Expose the OPTIONAL alias input at its contracted data/sources/
    derived/ location for the alias-PRESENT legs; restored after.

    Resolution base (rec-07 interface reconciliation): the stage resolves
    the input BESIDE THE EXTRACTION ROOT (`<root>/../data/`), which equals
    the pack-relative repo convention on real runs — so the leg-private
    copy is written to ``extracted.parent`` (inside the fixture tree),
    keeping hostless legs hermetic against concurrent sibling activity at
    the shared pack path. The ``pack_dir`` argument is retained for
    signature compatibility and deliberately NOT touched.
    """
    written = []
    p = Path(extracted).parent / ALIAS_INPUT_REL
    if not p.exists():                   # never clobber foreign state
        p.parent.mkdir(parents=True, exist_ok=True)
        write_jsonl(p, ALIAS_ROWS)
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


def selective_real_scratch(src_extracted: Path, dst: Path) -> Path:
    """Scratch extraction root holding EXACTLY stage-9's upstream set copied
    from the real committed corpus (hostless client-gated legs; no game
    dir, no bundle opens)."""
    dst = Path(dst)
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True)
    src_extracted = Path(src_extracted)
    for rel in ("identity.json", "bundle-roster.jsonl"):
        s = src_extracted / rel
        if s.is_file():
            shutil.copy2(s, dst / rel)
    for dirname in ("locales", "stubs"):
        s = src_extracted / dirname
        if s.is_dir():
            shutil.copytree(s, dst / dirname)
    (dst / "relinks").mkdir(parents=True, exist_ok=True)
    for name in ("entity_locale.jsonl", "i2_term_registry.jsonl",
                 "locale_term_entity.jsonl", "locale_join_report.json",
                 # NOT in §4's gate set (measured-OPTIONAL L5 substrate):
                 # present on the real corpus, absent on hostless fixtures;
                 # copied so the client-gated L5 census measures the real
                 # 11,312 I2.Loc.Localize bindings (F20/AC11).
                 "ui_link_coverage.jsonl"):
        s = src_extracted / "relinks" / name
        if s.is_file():
            shutil.copy2(s, dst / "relinks" / name)
    dump = src_extracted / "decompiled" / "il2cppdumper" / "dump.cs"
    if dump.is_file():                   # optional symbolCheck substrate
        ddst = dst / "decompiled" / "il2cppdumper"
        ddst.mkdir(parents=True, exist_ok=True)
        shutil.copy2(dump, ddst / "dump.cs")
    # OPTIONAL alias input, resolved beside the extraction root (rec-07):
    # mirrored when present so the scratch measures the true current state
    # (absent on today's corpus) without touching the shared pack path.
    alias_src = src_extracted.parent / ALIAS_INPUT_REL
    if alias_src.is_file():
        adst = dst / ALIAS_INPUT_REL
        adst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(alias_src, adst)
    return dst
