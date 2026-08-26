#!/usr/bin/env python3
"""Stage 9 — locale-proof (piece-07).

Turns the verified locale inventory into the proof artifacts extraction-
doctrine Principle two demands — completeness is PROVEN from primary
artifacts, never claimed (docs/specs/piece-07-locale-proof.mdx Rev 3):

  L1 key-plane census      — locales/proof/key_plane.json +
                             key_holes/<locale>.jsonl x13
  L2 kind x locale matrix  — kind_locale_matrix.json + unjoined_entities.jsonl
  L3 availability rebuild  — relinks/locale_availability.jsonl (SOLE writer,
                             v2 schema) + locale_availability.report.json
  L4 fallback law          — fallback_law.json
  L5 site-UI split         — site_ui_gap_manifest.json
  L6 completeness +        — registry_completeness.json + summary.json
     assembly + tripwire     + _ledger.jsonl + hashes.json + .baseline.json

PURELY DERIVED stage: opens NO bundles, needs NO game dir, imports NO
UnityPy. Its entire upstream set is committed extracted/ artifacts (§4).
Emission roots: extracted/locales/proof/ plus the ONE amended canonical
path extracted/relinks/locale_availability.jsonl (+ its report sidecar) —
ownership transferred from stage 5 by piece-07 §5 / arbiter-piece07 R4.

Exit codes (piece-1 contract): 0 success · 1 stage failure (schema/
self-validation breakage OR a coverage REGRESSION vs the same-buildId
baseline; precedence 1 > 2 > 0) · 2 completed-with-ledger (EXPECTED
steady state on today's corpus: 7 open ledger rows) · 3 environment/gate
refusal (missing upstream, named).

Determinism: byte-identical reruns (sorted enumeration, sorted JSON keys,
UTF-8 + LF, temp-file + atomic-rename writes, no wall-clock timestamps in
outputs); hashes.json manifests every emitted file of BOTH roots and
excludes itself and .baseline.json. Seeds from spec §2 print a `DRIFT:`
line when the fresh measurement differs — the fresh number wins, never a
silent stale constant.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import log_util
import tpc_common as tc

STAGE_ID = "locale-proof"

# Pinned vocabularies (tpc_common import rule — never re-declared).
# EXPECTED_LOCALES is the pinned 13-entry BCP-47 universe: it VALIDATES the
# roster's named locales (an unknown code is a failure) and anchors the
# drift seed, but the WORKING locale set resolves from the roster per run,
# so a hostless mini fixture (e.g. 3 locales + base, spec §10) drives the
# same code path as the 13-locale real corpus.
EXPECTED_LOCALES = sorted(tc.EMITTED_LOCALES)
EXPECTED_LOCALE_SET = frozenset(tc.EMITTED_LOCALES)
PIVOT = "en"
DE_COMPARATOR = "de"                          # frozen comparator for ALL rows
KINDS = ["config", "item", "room", "course", "staff", "student-type",
         "unlockable", "metagame-node", "campus-level"]
KIND_FILES = {
    "item": "items.jsonl", "unlockable": "unlockables.jsonl",
    "room": "rooms.jsonl", "campus-level": "campus-levels.jsonl",
    "course": "courses.jsonl", "config": "configs.jsonl",
    "staff": "staff.jsonl", "metagame-node": "metagame-nodes.jsonl",
    "student-type": "student-types.jsonl",
}

PROOF_DIR = "locales/proof"
AVAILABILITY_REL = "relinks/locale_availability.jsonl"
AVAILABILITY_REPORT_REL = "relinks/locale_availability.report.json"
ALIAS_REL_PACK = Path("data") / "sources" / "derived" / \
    "course-name-aliases.jsonl"

# ---------------------------------------------------------------------------
# Spec §2 seeds — reconcile, never trust: any divergence prints `DRIFT:`
# and the fresh measurement wins.

SEEDS = {
    "unionKeys": 15_666,
    "allThirteenKeys": 15_369,
    "registryRows": 15_675,
    "registryDistinctKeys": 15_672,
    "allThirteenShareUnion": "98.10%",
    "allThirteenShareRegistryUniverse": "98.07%",
    "perLocaleRows": {"de": 15_445, "en": 15_665, "es": 15_440, "fr": 15_445,
                      "it": 15_445, "ja": 15_371, "ko": 15_457, "pl": 15_445,
                      "pt-BR": 15_443, "ru": 15_422, "tr": 15_443,
                      "zh-Hans": 15_445, "zh-Hant": 15_446},
    "presenceHistogram": {"13": 15_369, "12": 46, "11": 27, "10": 1,
                          "9": 2, "3": 1, "2": 15, "1": 205},
    "ruByteIdenticalToEn": 301,
    "ruIdenticalAndDeDiffers": 297,
    "instancesTotal": 20_070,
    "sentinelZero": 9_101,
    "resolvedEdges": 10_964,
    "registryMisses": 5,
    "availabilityRows": 5_850,
    "joinedPerKind": {"config": 3_178, "item": 2_035, "room": 106,
                      "course": 41, "staff": 3, "student-type": 54,
                      "unlockable": 43, "metagame-node": 390,
                      "campus-level": 0},
    # F11 name-bearing seeds — INCLUDING the one figure the corpus outgrew:
    # spec F11/F13/AC4 pin config at 2,627, but the same pinned rule measures
    # 2,613 on buildId 20226581 (every other kind matches F11 exactly). The
    # seed stays at the written-contract value so the divergence is
    # SELF-ANNOUNCING: each real run prints
    #   DRIFT: nameBearingPerKind[config] seed 2627 vs measured 2613 — fresh wins
    # and the governance note rides its pinned location
    # kinds.config.nameRoleNote (build fix-round F2).
    "nameBearingPerKind": {"config": 2_627, "item": 1_077, "room": 105,
                           "course": 0, "staff": 3, "student-type": 27,
                           "unlockable": 23, "metagame-node": 195,
                           "campus-level": 0},
    "stubRowsPerKind": {"config": 8_430, "item": 3_885, "room": 116,
                        "course": 69, "staff": 3, "student-type": 54,
                        "unlockable": 415, "metagame-node": 454,
                        "campus-level": 17},
    "unjoinedPerKind": {"config": 5_252, "item": 1_850, "unlockable": 372,
                        "metagame-node": 64, "course": 28,
                        "campus-level": 17, "room": 10,
                        "student-type": 0, "staff": 0},
    "itemKernelPrefixRows": 1_438,
    "campusLevelEnglishLiteralRows": 13,
    "campusLevelNoDisplayFieldRows": 4,
    "unlockableEnglishLiteralRows": 41,
    "unlockableCoincideRows": 3,
    "statusSplit": {"ForTranslation": 15_400, "NotForTranslation": 275},
    "referencedKeys": 6_526,
    "usageEdges": 10_964,
    "orphansARows": 9_148,
    "orphansAKeys": 9_146,
    "orphansB": 0,
    "codeRefTerms": 586,
    "uiRegistryKeys": 2_218,
    "uiReferenced": 532,
    "uiFree": 1_686,
    "inputNamespaceKeys": 164,
    "generalNamespaceKeys": 143,
    "uiSettingsSourceTerms": 187,
    "topLevelNamespaces": 52,
    "localizeBindings": 11_312,
    "baseOverlayRows": 15_672,
    "baseOverlayRowsWithNonEmptyText": 0,
    "languageSources": 26,
    "rawTermsDecoded": 15_677,
    "emptyCellsSkippedTotal": 2_824,
    "dlcHospitalKeys": 753,
    "rosterLocaleRows": 14,
    "rosterLocalePayloadBytes": 6_541_486,
}

# L5 surface vocabulary PINNED — 16 rows, all present, none droppable.
CHROME_SURFACES = [
    "nav-labels", "buttons-actions", "filters-sort", "tooltips-help",
    "empty-states", "error-pages", "search-states", "pagination",
    "map-controls", "tool-ui", "ugc-surfaces", "consent-banner",
    "editorial-prose", "seo-meta-templates", "locale-switcher",
    "untranslated-filler",
]
CHROME_PROSE_SURFACES = {"editorial-prose", "seo-meta-templates"}

IDENTITY_METRIC_RULE = (
    "byteIdenticalToEn := non-empty text(locale) == text(en); "
    "identicalAndDeDiffers := byteIdenticalToEn AND text(de) != text(en) "
    f"— the {DE_COMPARATOR} comparator is FROZEN for all 13 rows; "
    "counters range over HELD keys only")
NAME_METRIC_RULE = ("first fieldPath containing 'name', sorted "
                    "(srcKind,srcId,fieldPath,dstId) order")

CONFIG_NAME_ROLE_NOTE = (
    "DRIFT: scout printed config name-identity 30.95% ru / 18.39% ja over "
    "an implied 2613 denominator; the pinned rule (first fieldPath "
    "containing 'name', sorted (srcKind,srcId,fieldPath,dstId) order) does "
    "NOT reproduce them under any tried tie-break (F13) — the columns "
    "here are the pinned-rule values and fresh wins. Denominator doctrine "
    "(build fix-round F2): spec F11/AC4 pin 2,627 name-bearing configs but "
    "the same pinned rule measures 2,613 on this corpus (every other kind "
    "matches F11 exactly), so the 2,627 seed is kept and every run "
    "announces `DRIFT: nameBearingPerKind[config] seed 2627 vs measured "
    "2613 — fresh wins` — the divergence from the written contract is "
    "never silent")

COURSE_NAME_ROLE_NOTE_BASE = (
    "course name hole (F15): all {edges} course edges carry "
    "fieldPath:\"Description\"; ZERO name-role terms in the client join; "
    "naive id-stem convention resolves 0/{courses}; candidate key families "
    "exist (Courses/Courses/*_Name, Courses/DLC_*, Marketing/Courses/*_Name, "
    "Meta/CareerChallenges/Course_*_Name); shared lever: the optional input "
    "data/sources/derived/course-name-aliases.jsonl closes G2 for this "
    "piece AND piece-08's search")

UNJOINED_RESIDUE_WARNING = (
    "unclassified-residue means only 'no join, not otherwise classified' — "
    "site IA consumers must NOT read the label as 'not player-facing'")

# Unjoined internal-kernel prefixes (F14) — first match wins; disjoint set.
ITEM_KERNEL_PREFIXES = ("Item_Editor", "Unused_Item", "Item_LS",
                        "A_LS_Variation", "Variation_")

CAMPUS_NO_DISPLAY_IDS_SEED = [
    "Config_UniversityLevel", "Config_UniversityLevel_Puzzle_Remix",
    "Config_UniversityLevel_ZeroMoney_Remix", "LevelScenarioV2_FreePlay_City",
]

# L4 pinned symbol declarations (scout §4.4 + verifyB attack 4). Signature
# strings are PINNED constants; the dumpCsLine VALUES are MEASURED each run.
FALLBACK_SYMBOLS = [
    {
        "name": "LanguageSourceData.TryGetFallbackTranslation(TermData, "
                "out string Translation, int langIndex, string "
                "overrideSpecialization, bool skipDisabled)",
        "token": r"\bTryGetFallbackTranslation\s*\(",
        "anchor": None,
    },
    {
        "name": "LanguageSourceData.LoadLanguageData(int languageIndex, "
                "string langData, bool UnloadOtherLanguages, bool "
                "useFallback, bool onlyCurrentSpecialization, bool "
                "forceLoad)",
        "token": r"\bLoadLanguageData\s*\(",
        "anchor": None,
    },
    {
        "name": "LocalizationManager.GetTranslation(...) / "
                "TryGetTranslation(...)",
        "token": r"\b(?:TryGetTranslation|GetTranslation)\s*\(",
        "anchor": r"\bclass\s+LocalizationManager\b",
    },
    {
        "name": "TermData.GetTranslation(int idx, string specialization, "
                "bool editMode)",
        "token": r"\bGetTranslation\s*\(",
        "anchor": r"\bclass\s+TermData\b",
    },
]
RUNTIME_FALLBACK_ORDER_TEXT = (
    "UNPROVABLE at the data layer - Il2CppDumper emits no method bodies; "
    "keys missing from a locale demonstrably render in-game, so resolution "
    "runs through this declared path, priority order unknown")
BASE_STORAGE_SHAPE = (
    "26 LanguageSourceAsset MonoBehaviours (mTerms[] keys/statuses/columns); "
    "named bundles instead hold 25 category TextAssets per locale")
BASE_MEASURED_SEMANTICS = (
    "base carries NO text; 'mixed' encodes the key-set delta only "
    "(G7 caveat)")
BORROWING_RULE = ("none - no locale table ever holds another locale's "
                  "text; absence is preserved verbatim")
CONSUMER_WARNINGS = [
    "entity_locale.evidence.locales is [] on every row - never read as "
    "'available in no locale'",
]

# Regression-vector directions (arbiter R3: coverage higher-better; hole
# counts and misses lower-better; structural counts exact-match).
VECTOR_EXACT = frozenset({"unionKeys", "registryRows",
                          "registryDistinctKeys", "matrixKeyDiff",
                          "chromeSurfaces"})
VECTOR_LOWER = frozenset({"registryMisses", "orphansAKeys", "orphansB"})


def vector_direction(member: str) -> str:
    if member in VECTOR_EXACT:
        return "exact"
    if member in VECTOR_LOWER:
        return "lower"
    if member.startswith("holes."):
        return "lower"
    return "higher"

LEDGER_CODES_DOC = {
    "alias-input-absent": "produce the shared course-id -> term-key alias "
                          "table at data/sources/derived/"
                          "course-name-aliases.jsonl (piece-08 shared lever)",
    "course-name-join-open": "measure + land "
                             "data/sources/derived/course-name-aliases.jsonl "
                             "(shared with piece-08's search convention lane)",
    "dlc-out-of-install-scope": "state install scope beside coverage claims; "
                                "re-measure when the DLC roster changes",
    "entity-unjoined": "grow the relink surface (piece-02 family probes); "
                       "classes are data, never silence",
    "registry-miss-closable": "extend the registry walk so the Code/ dev "
                              "strings resolve as terms (piece-2-family "
                              "probe; spec §8 non-goal here)",
    "registry-miss-dangling": "extend the registry walk to cover the "
                              "WantsMessage IDs (piece-2-family probe; "
                              "spec §8 non-goal here)",
}


# ---------------------------------------------------------------------------
# Small deterministic helpers

class Drift:
    """Collects `DRIFT:` lines (fresh measurement wins over a seed).
    seed=None means 'no seed for this member' (mini fixture) — no line."""

    def __init__(self) -> None:
        self.lines: list[str] = []

    def check(self, label: str, seed, measured) -> None:
        if seed is not None and measured != seed:
            self.lines.append(
                f"DRIFT: {label} seed {seed!r} vs measured {measured!r} — "
                "fresh wins")


def pct(num: int, den: int) -> str:
    """Percent string, HALF-UP at 2 dp from integer counts."""
    if den <= 0:
        return "0.00%"
    q = (Decimal(num) * 100 / Decimal(den)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{q:.2f}%"


def rate5(num: int, den: int) -> str:
    """coverageOnNonEmpty-style decimal rate string at 5 dp, HALF-UP."""
    if den <= 0:
        return "0.00000"
    return str((Decimal(num) / Decimal(den)).quantize(
        Decimal("0.00001"), rounding=ROUND_HALF_UP))


def common_namespace(keys: list[str]) -> str:
    """Longest common `/`-aligned namespace prefix of the given keys."""
    if not keys:
        return ""
    prefix = keys[0]
    for k in keys[1:]:
        while not k.startswith(prefix + "/") and prefix:
            prefix = prefix[:prefix.rfind("/")]
        if not prefix:
            break
    return prefix


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with open(path, "r", encoding="utf-8", newline="\n") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


# ---------------------------------------------------------------------------
# Inputs (upstream gate — ANY missing ⇒ exit 3 naming it)

REQUIRED_INPUTS = (
    ["identity.json", "bundle-roster.jsonl",
     "locales/base-overlay.jsonl", "locales/base-overlay-report.json",
     "locales/locale-matrix.json"]
    + [f"stubs/{f}" for f in KIND_FILES.values()]
    + ["relinks/entity_locale.jsonl", "relinks/i2_term_registry.jsonl",
       "relinks/locale_term_entity.jsonl", "relinks/locale_join_report.json"]
)
# per-locale tables are required too, but the REQUIRED SET is resolved from
# the roster inside load_inputs (a mini fixture names fewer locales)

# OPTIONAL input (absence is a zero, never a failure — build fix-round F4
# declares it so the input contract is complete): stage-6's committed
# `relinks/ui_link_coverage.jsonl` is L5's localizeBindings substrate (the
# measured-OPTIONAL F20 figure; a declared stage-6 output, consumed
# UPSTREAMS-free exactly like the alias input below — never in run_all.UPSTREAMS).
OPTIONAL_INPUTS = ("relinks/ui_link_coverage.jsonl",)


def precheck_inputs(extracted_root: Path) -> None:
    missing = [rel for rel in REQUIRED_INPUTS
               if not (extracted_root / rel).is_file()]
    if missing:
        raise tc.StageError(
            f"stage '{STAGE_ID}' is missing upstream artifacts "
            f"({', '.join(missing)}) — prepare the tree first "
            "(client mode: run the pipeline without this stage; hostless "
            "smoke: tests/build_fixture_tree.py --stage locale-proof)",
            exit_code=3)


def load_inputs(extracted_root: Path, drift: Drift) -> dict:
    inputs: dict = {}
    inputs["build_id"] = json.loads(
        (extracted_root / "identity.json").read_text(encoding="utf-8")
    )["buildId"]
    roster = load_jsonl(extracted_root / "bundle-roster.jsonl")
    locale_rows = [r for r in roster if r.get("localeFlag")]
    named = sorted({str(r["localeFlag"]) for r in locale_rows} - {"base"})
    unknown = sorted(set(named) - EXPECTED_LOCALE_SET)
    if unknown:
        raise tc.StageError(
            f"bundle-roster names locales outside the pinned BCP-47 table: "
            f"{unknown} (pinned universe: {EXPECTED_LOCALES})", exit_code=1)
    if PIVOT not in named:
        raise tc.StageError(
            f"pivot locale '{PIVOT}' missing from the roster's named "
            "locales — the identity-to-pivot tier is undefined", exit_code=1)
    inputs["locales"] = named
    inputs["roster_locale_rows"] = locale_rows
    drift.check("roster localeFlag row count", SEEDS["rosterLocaleRows"],
                len(locale_rows))
    drift.check("named locale count", len(EXPECTED_LOCALES), len(named))
    missing_tables = [f"locales/{loc}.jsonl" for loc in named
                      if not (extracted_root / f"locales/{loc}.jsonl")
                      .is_file()]
    if missing_tables:
        raise tc.StageError(
            f"stage '{STAGE_ID}' is missing upstream artifacts "
            f"({', '.join(missing_tables)}) — prepare the tree first",
            exit_code=3)
    payload_bytes = sum(int(r.get("bytes") or 0) for r in locale_rows)
    drift.check("roster locale payload byte sum",
                SEEDS["rosterLocalePayloadBytes"], payload_bytes)

    tables: dict[str, dict[str, str]] = {}
    for loc in named:
        t: dict[str, str] = {}
        for row in load_jsonl(extracted_root / f"locales/{loc}.jsonl"):
            t[row["id"]] = row.get("text") or ""
        tables[loc] = t
    inputs["tables"] = tables

    base_overlay = load_jsonl(extracted_root / "locales/base-overlay.jsonl")
    inputs["base_overlay"] = base_overlay
    inputs["base_overlay_report"] = json.loads(
        (extracted_root / "locales/base-overlay-report.json")
        .read_text(encoding="utf-8"))
    matrix = json.loads(
        (extracted_root / "locales/locale-matrix.json").read_text(
            encoding="utf-8"))
    inputs["matrix_keys"] = set(matrix.get("keys") or {})

    stubs: dict[str, list[dict]] = {}
    for kind in KINDS:
        stubs[kind] = load_jsonl(extracted_root / f"stubs/{KIND_FILES[kind]}")
    inputs["stubs"] = stubs
    stub_axes = {}
    for kind in KINDS:
        for row in stubs[kind]:
            if isinstance(row.get("axes"), list):
                stub_axes[(kind, str(row["id"]))] = sorted(
                    str(a) for a in row["axes"])
    inputs["stub_axes"] = stub_axes

    inputs["edges"] = load_jsonl(
        extracted_root / "relinks/entity_locale.jsonl")
    registry = load_jsonl(
        extracted_root / "relinks/i2_term_registry.jsonl")
    inputs["registry"] = registry
    inputs["reverse"] = load_jsonl(
        extracted_root / "relinks/locale_term_entity.jsonl")
    inputs["join_report"] = json.loads(
        (extracted_root / "relinks/locale_join_report.json").read_text(
            encoding="utf-8"))
    return inputs


def load_alias_input(pack_side_base: Path) -> list[dict] | None:
    """OPTIONAL input (absence is a ledger row, never a failure): the shared
    course-id -> term-key alias table closing G2 for this piece and
    piece-08's search.

    Resolved BESIDE THE EXTRACTION ROOT (`<root>/../data/sources/derived/`),
    which is byte-identical to the pack-relative repo convention on real
    runs (the default extracted root sits inside the pack) while keeping
    hostless fixture/scratch roots hermetic against concurrent sibling
    activity at the shared pack path (rec-07 interface reconciliation)."""
    path = pack_side_base / ALIAS_REL_PACK
    if not path.is_file():
        return None
    return load_jsonl(path)


# ---------------------------------------------------------------------------
# L1 — key-plane census

def pass_l1(inputs: dict, drift: Drift, locs: list[str]) -> dict:
    tables = inputs["tables"]
    registry_keys = {r["termKey"] for r in inputs["registry"]}
    union = set()
    for loc in locs:
        union |= set(tables[loc])

    hist = Counter(sum(1 for loc in locs if k in tables[loc]) for k in union)
    histogram = {str(n): hist[n] for n in sorted(hist, reverse=True)}
    all_holding = hist[len(locs)]
    drift.check("presenceHistogram", SEEDS["presenceHistogram"], histogram)
    drift.check("unionKeys", SEEDS["unionKeys"], len(union))
    drift.check("allThirteenKeys", SEEDS["allThirteenKeys"], all_holding)
    drift.check("registryDistinctKeys", SEEDS["registryDistinctKeys"],
                len(registry_keys))
    share_union = pct(all_holding, len(union))
    share_registry = pct(all_holding, len(registry_keys))
    drift.check("allThirteenShareUnion",
                SEEDS["allThirteenShareUnion"], share_union)
    drift.check("allThirteenShareRegistryUniverse",
                SEEDS["allThirteenShareRegistryUniverse"], share_registry)

    per_locale = {}
    holes_by_locale: dict[str, list[str]] = {}
    hole_namespaces: dict[str, dict] = {}
    empty_cell_identity_holds = True
    for loc in locs:
        rows = len(tables[loc])
        holes = sorted(union - set(tables[loc]))
        holes_by_locale[loc] = holes
        ns = Counter(k.split("/")[0] for k in holes)
        hole_namespaces[loc] = {k: ns[k] for k in sorted(ns)}
        # F6 identity: stage-4 skip-empty counts are recoverable arithmetically
        empty_cells = len(registry_keys) - rows
        if empty_cells < 0:
            empty_cell_identity_holds = False
        per_locale[loc] = {
            "rows": rows,
            "unionHoles": len(holes),
            "shareOfUnion": pct(rows, len(union)),
            "registryDelta": max(empty_cells, 0),
            "emptyCellsSkipped": empty_cells,
        }
        drift.check(f"perLocaleRows[{loc}]", SEEDS["perLocaleRows"].get(loc),
                    rows)
    if not empty_cell_identity_holds:
        raise tc.StageError(
            "F6 identity violated: emptyCellsSkipped == registryKeys − "
            "tableRows went negative for at least one locale", exit_code=1)

    en_missing = sorted(union - set(tables[PIVOT]))
    singles = [k for k in union
               if sum(1 for loc in locs if k in tables[loc]) == 1]
    singles_all_en = all(k in tables[PIVOT] for k in singles)
    en_ko = sorted(k for k in union
                   if {loc for loc in locs if k in tables[loc]}
                   == {PIVOT, "ko"})
    base_only_vs_en = sorted(registry_keys - set(tables[PIVOT]))
    drift.check("enMissingKeys", ["UI/General/NameSeparator"], en_missing)
    drift.check("singleLocaleKeys.count", 205, len(singles))

    # Identity-to-pivot tier — SAME frozen predicates for every row; the de
    # comparator is FROZEN (a mini fixture without a de table reads the
    # comparator as always-differing, which is the honest degenerate read).
    family = sorted(k for k in union
                    if k.startswith("Items/") and k.endswith("_Name"))
    de_texts = tables.get(DE_COMPARATOR) or {}
    en_texts = tables[PIVOT]
    identity_rows = {}
    # residualIdenticalInDe generalizes the seed's ru-residual-4 framing to
    # EVERY row under the SAME frozen predicates (no locale special case):
    # per locale, the byteIdenticalToEn keys the de comparator does NOT
    # differ on — i.e. bie − identicalAndDeDiffers — so the 301−297 delta is
    # data. Only non-empty lists are emitted.
    residual_by_locale: dict[str, list[str]] = {}
    for loc in locs:
        held = [k for k in family if k in tables[loc]]
        bie = [k for k in held
               if k in en_texts and en_texts[k]
               and tables[loc][k] == en_texts[k]]
        didd = [k for k in bie if de_texts.get(k) != en_texts.get(k)]
        iehl = [k for k in held
                if all(k not in tables[h] or tables[h].get(k) == en_texts[k]
                       for h in locs)]
        resid = sorted(set(bie) - set(didd))
        if resid:
            residual_by_locale[loc] = resid
        identity_rows[loc] = {
            "keysHeld": len(held),
            "byteIdenticalToEn": len(bie),
            "identicalAndDeDiffers": len(didd),
            "identicalInEveryHoldingLocale": len(iehl),
        }
    ru_row = identity_rows.get("ru")
    drift.check("ru.byteIdenticalToEn", SEEDS["ruByteIdenticalToEn"],
                ru_row and ru_row["byteIdenticalToEn"])
    drift.check("ru.identicalAndDeDiffers",
                SEEDS["ruIdenticalAndDeDiffers"],
                ru_row and ru_row["identicalAndDeDiffers"])

    artifact = {
        "meta": {
            "buildId": inputs["build_id"],
            "universes": {
                f"unionOf{len(locs)}Tables": len(union),
                "registry": len(registry_keys),
            },
            "localeRoster": list(locs),
        },
        "presenceHistogram": histogram,
        "allThirteenShare": {
            "numerator": all_holding,
            "denominator": len(union),
            "rate": share_union,
            "registryUniverseRate": share_registry,
        },
        "perLocale": per_locale,
        "holeNamespaces": hole_namespaces,
        "quirks": {
            "enMissingKeys": en_missing,
            "singleLocaleKeys": {"count": len(singles),
                                 "allEn": singles_all_en},
            "enPlusKoCluster": {
                "namespace": common_namespace(en_ko),
                "count": len(en_ko),
            },
            "baseOnlyVsEn": base_only_vs_en,
        },
        "identityToPivot": {
            "namespace": "Items/*_Name",
            "familyKeysTotal": len(family),
            "metricRule": IDENTITY_METRIC_RULE,
            "residualIdenticalInDe": {loc: residual_by_locale[loc]
                                      for loc in sorted(residual_by_locale)},
            **identity_rows,
        },
    }

    hole_files = {}
    for loc in locs:
        hole_files[loc] = [
            {"termKey": k,
             "namespace": k.split("/")[0],
             "alsoMissingIn": sorted(h for h in locs
                                     if h != loc and k not in tables[h]),
             "buildId": inputs["build_id"]}
            for k in holes_by_locale[loc]]

    run = {
        "pass": "L1",
        "localeRosterSize": len(locs),
        "unionKeys": len(union),
        "allThirteenKeys": all_holding,
        "perLocaleRows": {l: per_locale[l]["rows"] for l in locs},
        "perLocaleUnionHoles": {l: per_locale[l]["unionHoles"] for l in locs},
        "holeFilesEmitted": len(hole_files),
        "emptyCellIdentityHold": empty_cell_identity_holds,
    }
    return {"artifact": artifact, "holeFiles": hole_files, "run": run,
            "union": union, "registryKeys": registry_keys}


# ---------------------------------------------------------------------------
# Shared join-chain helpers (L2/L3)

def group_edges(edges: list[dict]) -> dict:
    """(srcKind, srcId) -> sorted edge list, keyed deterministically."""
    grouped: dict[tuple, list] = defaultdict(list)
    for e in edges:
        grouped[(e["srcKind"], str(e["srcId"]))].append(e)
    for v in grouped.values():
        v.sort(key=lambda e: (e["srcKind"], str(e["srcId"]),
                              str((e.get("evidence") or {}).get("fieldPath")
                                 or ""),
                              str(e.get("dstId") or "")))
    return grouped


def is_name_field(field_path: str) -> bool:
    return "name" in str(field_path).lower()


def first_name_edge(sorted_edges: list) -> tuple | None:
    """PINNED rule: first edge whose evidence.fieldPath contains 'name',
    in sorted (srcKind,srcId,fieldPath,dstId) order (edges arrive sorted)."""
    for e in sorted_edges:
        if is_name_field((e.get("evidence") or {}).get("fieldPath") or ""):
            fp = (e["evidence"] or {}).get("fieldPath") or ""
            return (e["srcKind"], str(e["srcId"]), str(fp), e["dstId"])
    return None


def build_name_edges(grouped: dict, stubs_by_kind: dict,
                     alias_map: dict | None, registry_keys: set) -> dict:
    """Effective name edge per entity. Non-course kinds use the pinned
    first-name-edge rule; course entities route THROUGH the optional alias
    input when present (inferred:true; method recorded per cell). A genuine
    name-role term in the client join outranks the convention alias."""
    out: dict[tuple, dict] = {}
    for key, edges in grouped.items():
        ne = first_name_edge(edges)
        if ne is not None:
            out[key] = {"termKey": ne[3], "source": "fieldPath",
                        "fieldPath": ne[2], "method": None,
                        "inferred": False}
    if alias_map:
        for row in stubs_by_kind.get("course", []):
            cid = str(row["id"])
            key = ("course", cid)
            if key in out:
                continue
            hit = alias_map.get(cid)
            if not hit:
                continue
            term_key = str(hit.get("termKey") or "")
            if term_key not in registry_keys:
                continue
            out[key] = {
                "termKey": term_key,
                "source": "alias-input",
                "fieldPath": f"aliases:{hit.get('method') or ''}",
                "method": str(hit.get("method") or ""),
                "inferred": True,
            }
    return out


# ---------------------------------------------------------------------------
# L2 — entity-plane kind x locale matrix

def classify_unjoined(kind: str, row: dict, en_text_values: set) -> dict:
    """Pinned class vocabulary: english-only-literal · no-display-field ·
    internal-kernel · unclassified-residue (label ≠ 'not player-facing')."""
    fields = row.get("fields") if isinstance(row.get("fields"), dict) else {}
    name = fields.get("Name")
    literal = name.strip() if isinstance(name, str) else ""
    info: dict = {"class": "unclassified-residue"}
    if kind == "campus-level":
        if literal:
            info = {"class": "english-only-literal", "nameLiteral": literal}
        else:
            info = {"class": "no-display-field"}
    elif kind == "unlockable" and literal:
        info = {"class": "english-only-literal", "nameLiteral": literal}
        if literal in en_text_values:
            info["coincidesWithEnTermText"] = True
    elif kind == "item":
        for prefix in ITEM_KERNEL_PREFIXES:
            if row_id(row).startswith(prefix):
                info = {"class": "internal-kernel", "kernelPrefix": prefix}
                break
    return info


def row_id(row: dict) -> str:
    return str(row["id"])


def pass_l2(inputs: dict, drift: Drift, name_edges: dict,
            alias_map: dict | None, locs: list[str]) -> dict:
    tables = inputs["tables"]
    edges = inputs["edges"]
    grouped = group_edges(edges)
    join_report = inputs["join_report"]
    stubs = inputs["stubs"]

    instances_total = join_report.get("instancesTotal")
    sentinel_zero = join_report.get("sentinelZero")
    registry_misses = len(join_report.get("unresolvedIds") or [])
    resolved_edges = len(edges)
    drift.check("instancesTotal", SEEDS["instancesTotal"], instances_total)
    drift.check("sentinelZero", SEEDS["sentinelZero"], sentinel_zero)
    drift.check("resolvedEdges", SEEDS["resolvedEdges"], resolved_edges)
    drift.check("registryMisses", SEEDS["registryMisses"], registry_misses)
    coverage_num = resolved_edges - registry_misses
    coverage = {"numerator": coverage_num,
                "denominator": resolved_edges,
                "rate": rate5(coverage_num, resolved_edges)}

    en_text_values = {t for t in tables[PIVOT].values() if t}
    kinds_out = {}
    unjoined_rows = []
    class_counter: Counter = Counter()
    per_kind_class: dict[str, Counter] = {k: Counter() for k in KINDS}
    joined_per_kind = {}
    name_bearing_per_kind = {}

    for kind in KINDS:
        stub_rows = stubs[kind]
        ent_ids = {(e[0], e[1]) for e in grouped if e[0] == kind}
        joined = sorted(i for (_k, i) in ent_ids)
        joined_per_kind[kind] = len(joined)
        drift.check(f"joinedPerKind[{kind}]",
                    SEEDS["joinedPerKind"][kind], len(joined))

        # name-bearing ranges over STUB entities holding an EFFECTIVE name
        # edge: a course named only through the alias input carries no
        # locale edge of its own yet still names its page
        named_ids = [row_id(r) for r in stub_rows
                     if (kind, row_id(r)) in name_edges]
        nb = len(named_ids)
        drift.check(f"nameBearingPerKind[{kind}]",
                    SEEDS["nameBearingPerKind"][kind], nb)

        # §L2 (build fix-round F6): `inferred:true` rides the RESOLUTION
        # PATH — the optional alias input — never the kind. A course whose
        # effective name edge came from the client fieldPath rule, or a kind
        # with no alias-resolved name edge at all, must not claim inferred.
        alias_named = sum(1 for (k, _i), ne in name_edges.items()
                          if k == kind and ne.get("source") == "alias-input")
        fieldpath_named = sum(
            1 for (k, _i), ne in name_edges.items()
            if k == kind and ne.get("source") == "fieldPath")
        inferred_flag = bool(alias_map) and alias_named > 0 \
            and fieldpath_named == 0
        per_locale = {}
        for loc in locs:
            any_present = all_present = 0
            for eid in joined:
                ent_edges = grouped[(kind, eid)]
                keys = [e["dstId"] for e in ent_edges]
                texts = [tables[loc].get(k) for k in keys]
                held = [t for t in texts if t]
                if held:
                    any_present += 1
                if len(held) == len(keys):
                    all_present += 1
            ident = 0
            for eid in named_ids:
                ne = name_edges.get((kind, eid))
                if ne is None:
                    continue
                nk = ne["termKey"]
                if nk and tables[loc].get(nk) and tables[PIVOT].get(nk) \
                        and tables[loc][nk] == tables[PIVOT][nk]:
                    ident += 1
            per_locale[loc] = {
                "anyTermPresent": any_present,
                "allTermsPresent": all_present,
                "anyRate": pct(any_present, len(joined)),
                "fullRate": pct(all_present, len(joined)),
                "nameBearingEntities": nb,
                "nameIdenticalToEn": ident,
                "nameIdentityRate": pct(ident, nb),
                "inferred": inferred_flag,
            }
        name_bearing_per_kind[kind] = nb

        name_role_note = None
        if kind == "config":
            name_role_note = CONFIG_NAME_ROLE_NOTE
        elif kind == "course":
            note = COURSE_NAME_ROLE_NOTE_BASE.format(
                edges=sum(1 for e in edges if e["srcKind"] == "course"),
                courses=len(stub_rows))
            if alias_map:
                methods = sorted({
                    ne["method"] for (k, _i), ne in name_edges.items()
                    if k == "course" and ne.get("method")})
                unresolved = sum(
                    1 for row in stub_rows
                    if ("course", row_id(row)) not in name_edges)
                note += (f"; CLOSED through "
                         f"data/sources/derived/course-name-aliases.jsonl "
                         f"({len(stub_rows) - unresolved}/{len(stub_rows)} "
                         f"course ids resolved"
                         + (f", methods: {', '.join(methods)}"
                            if methods else "") + ")")
            name_role_note = note

        kinds_out[kind] = {
            "stubRows": len(stub_rows),
            "joinedEntities": len(joined),
            "perLocale": per_locale,
            "nameRoleNote": name_role_note,
        }
        drift.check(f"stubRowsPerKind[{kind}]",
                    SEEDS["stubRowsPerKind"][kind], len(stub_rows))

        joined_set = ent_ids
        for row in stub_rows:
            if (kind, row_id(row)) in joined_set:
                continue
            cls_info = classify_unjoined(kind, row, en_text_values)
            entry = {"kind": kind, "id": row_id(row),
                     "class": cls_info["class"],
                     "buildId": inputs["build_id"]}
            if "nameLiteral" in cls_info:
                entry["nameLiteral"] = cls_info["nameLiteral"]
            if cls_info.get("coincidesWithEnTermText"):
                entry["coincidesWithEnTermText"] = True
            if "kernelPrefix" in cls_info:
                entry["kernelPrefix"] = cls_info["kernelPrefix"]
            unjoined_rows.append(entry)
            class_counter[cls_info["class"]] += 1
            per_kind_class[kind][cls_info["class"]] += 1

    unjoined_rows.sort(key=lambda r: (r["kind"], r["id"]))
    drift.check("unjoinedPerKind", SEEDS["unjoinedPerKind"],
                {k: sum(per_kind_class[k].values()) for k in KINDS})
    drift.check("itemKernelPrefixRows", SEEDS["itemKernelPrefixRows"],
                per_kind_class["item"]["internal-kernel"])
    drift.check("campusLevelEnglishLiteralRows",
                SEEDS["campusLevelEnglishLiteralRows"],
                per_kind_class["campus-level"]["english-only-literal"])
    drift.check("campusLevelNoDisplayFieldRows",
                SEEDS["campusLevelNoDisplayFieldRows"],
                per_kind_class["campus-level"]["no-display-field"])
    drift.check("unlockableEnglishLiteralRows",
                SEEDS["unlockableEnglishLiteralRows"],
                per_kind_class["unlockable"]["english-only-literal"])
    coincide_rows = sum(
        1 for r in unjoined_rows if r.get("coincidesWithEnTermText"))
    drift.check("unlockableCoincideRows", SEEDS["unlockableCoincideRows"],
                coincide_rows)

    metric_rule = NAME_METRIC_RULE
    appendix = None
    if alias_map:
        methods = sorted({
            ne.get("method") or "" for ne in name_edges.values()
            if ne.get("source") == "alias-input"})
        appendix = (
            "course name columns computed THROUGH "
            "data/sources/derived/course-name-aliases.jsonl "
            "(inferred:true; methods: " + ", ".join(methods) + ")")

    artifact = {
        "meta": {
            "buildId": inputs["build_id"],
            "kinds": list(KINDS),
            "metricRule": metric_rule,
        },
        "census": {
            "instancesTotal": instances_total,
            "sentinelZero": sentinel_zero,
            "resolvedEdges": resolved_edges,
            "registryMisses": registry_misses,
            "coverageOnNonEmpty": coverage,
        },
        "kinds": kinds_out,
    }
    if appendix is not None:
        artifact["meta"]["metricRuleAppendix"] = appendix

    run = {
        "pass": "L2",
        "instancesTotal": instances_total,
        "sentinelZero": sentinel_zero,
        "resolvedEdges": resolved_edges,
        "registryMisses": registry_misses,
        "coverageOnNonEmpty": coverage["rate"],
        "kindCellsEmitted": len(KINDS) * len(locs),
        "unjoinedRows": len(unjoined_rows),
        "unjoinedClasses": dict(sorted(class_counter.items())),
        "unjoinedPerKindClass": {
            k: dict(sorted(per_kind_class[k].items()))
            for k in KINDS},
        "configIdentityDriftNoted": True,
        "residueConsumerWarning": UNJOINED_RESIDUE_WARNING,
    }
    return {"artifact": artifact, "unjoinedRows": unjoined_rows, "run": run,
            "joinedPerKind": joined_per_kind,
            "nameBearingPerKind": name_bearing_per_kind}


# ---------------------------------------------------------------------------
# L3 — availability regeneration (SOLE writer of the canonical path)

def pass_l3(inputs: dict, drift: Drift, name_edges: dict,
            locs: list[str]) -> dict:
    tables = inputs["tables"]
    grouped = group_edges(inputs["edges"])
    stub_axes = inputs["stub_axes"]
    rows = []
    rows_with_axes = 0
    per_kind: Counter = Counter()

    for (kind, eid) in sorted(grouped):
        ent_edges = grouped[(kind, eid)]
        keys = [e["dstId"] for e in ent_edges]
        available = [l for l in locs if any(tables[l].get(k) for k in keys)]
        partial = [l for l in available
                   if not all(tables[l].get(k) for k in keys)]
        name_keys = {
            e["dstId"] for e in ent_edges
            if is_name_field((e.get("evidence") or {}).get("fieldPath") or "")
        }
        # the EFFECTIVE name edge counts for naming too: a course whose name
        # column exists only through the alias input still names its page
        ne_eff = name_edges.get((kind, eid))
        if ne_eff and ne_eff.get("termKey"):
            name_keys.add(ne_eff["termKey"])
        name_keys = sorted(name_keys)
        named = [l for l in locs if any(tables[l].get(k)
                                        for k in name_keys)]
        identity_locs = []
        ne = name_edges.get((kind, eid))
        if ne and ne["termKey"]:
            nk = ne["termKey"]
            identity_locs = [
                l for l in locs
                if l != PIVOT and tables[l].get(nk)
                and tables[PIVOT].get(nk) == tables[l][nk]]
        field_presence = {}
        for loc in available:
            fps = sorted({
                str((e.get("evidence") or {}).get("fieldPath") or "")
                for e in ent_edges if tables[loc].get(e["dstId"])})
            field_presence[loc] = fps
        entry = {
            "kind": kind,
            "id": eid,
            "availableLocales": available,
            "partialLocales": partial,
            "namedLocales": named,
            "identityToPivotLocales": sorted(identity_locs),
            "fieldPresence": field_presence,
        }
        axes = stub_axes.get((kind, eid))
        if axes is not None:
            entry["axes"] = axes
            rows_with_axes += 1
        entry["buildId"] = inputs["build_id"]
        # membership assertions (AC6 subset relations)
        if not set(partial) <= set(available):
            raise tc.StageError(
                f"availability row {kind}/{eid}: partialLocales not a subset "
                "of availableLocales", exit_code=1)
        if not set(identity_locs) <= set(named):
            raise tc.StageError(
                f"availability row {kind}/{eid}: identityToPivotLocales not "
                "a subset of namedLocales", exit_code=1)
        if not set(field_presence) <= set(available):
            raise tc.StageError(
                f"availability row {kind}/{eid}: fieldPresence keys not a "
                "subset of availableLocales", exit_code=1)
        bad = [l for l in available + partial + named + identity_locs
               if l not in locs]
        if bad:
            raise tc.StageError(
                f"availability row {kind}/{eid}: locale outside the pinned "
                f"13-entry set: {sorted(set(bad))}", exit_code=1)
        rows.append(entry)
        per_kind[kind] += 1

    rows.sort(key=lambda r: (r["kind"], r["id"]))
    drift.check("availabilityRows", SEEDS["availabilityRows"], len(rows))
    drift.check("availPerKind(seed)", SEEDS["joinedPerKind"],
                {k: per_kind.get(k, 0) for k in KINDS})
    # §2.2 formula asserted programmatically: emitted rows == the DISTINCT
    # (srcKind,srcId) universe holding >=1 registry-resolved edge. AC6's
    # wording ("== registryHits deduplicated") cannot be an equality against
    # the raw counter: locale_join_report.registryHits is the RAW EDGE count
    # (10,964), not a deduplicated entity count (5,850), so the load-bearing
    # guard here is the dedup equality above plus this <= bound; the pinned
    # 5,850 figure is guarded by the availabilityRows DRIFT seed (build
    # fix-round F5 — deviation from AC6-as-written recorded, not silent).
    if len(rows) != len(grouped):
        raise tc.StageError(
            "availability formula broken: emitted rows != distinct "
            "(srcKind,srcId) universe", exit_code=1)
    jr_hits = inputs["join_report"].get("registryHits")
    if jr_hits is not None:
        resolved_seen = sum(1 for _k, edges in grouped.items() if edges)
        if resolved_seen > int(jr_hits):
            raise tc.StageError(
                f"entity universe ({resolved_seen}) exceeds "
                f"locale_join_report.registryHits ({jr_hits})", exit_code=1)

    report = {
        "schemaVersion": 2,
        "rowCount": len(rows),
        "perKindRowCounts": {k: per_kind[k] for k in sorted(per_kind)},
        "formula": "distinct (srcKind,srcId) in entity_locale.jsonl with "
                   ">=1 registry-resolved edge",
        "localeSet": list(locs),
        "buildId": inputs["build_id"],
    }
    run = {
        "pass": "L3",
        "availabilityRows": len(rows),
        "perKindAvailabilityRows": {k: per_kind[k] for k in sorted(per_kind)},
        "rowsWithAxes": rows_with_axes,
    }
    return {"rows": rows, "report": report, "run": run}


# ---------------------------------------------------------------------------
# L4 — fallback law artifact

def measure_symbol_lines(dump_cs: Path,
                         drift: Drift | None = None) -> tuple[list[dict], str]:
    """Deterministic substring pass over dump.cs. Signature strings stay
    pinned; dumpCsLine values are MEASURED this run (~L<lineno>, 1-based).

    The symbolCheck enum stays the pinned two-value set
    (`verified|skipped-no-dump.cs`); a dump.cs that is PRESENT yet missing a
    declared token surfaces as a DRIFT line instead of a third verdict value
    (build fix-round F3 — the loss is announced, never silent)."""
    symbols = []
    if not dump_cs.is_file():
        for sym in FALLBACK_SYMBOLS:
            symbols.append({"name": sym["name"], "dumpCsLine": None})
        return symbols, "skipped-no-dump.cs"
    lines = dump_cs.read_text(encoding="utf-8", errors="replace").splitlines()
    token_res = [(re.compile(s["token"]), re.compile(s["anchor"]) if s["anchor"]
                  else None) for s in FALLBACK_SYMBOLS]
    for idx, sym in enumerate(FALLBACK_SYMBOLS):
        token_re, anchor_re = token_res[idx]
        start = 0
        if anchor_re is not None:
            start = next((i for i, ln in enumerate(lines)
                          if anchor_re.search(ln)), 0)
        hit = next((i for i in range(start, len(lines))
                    if token_re.search(lines[i])), None)
        if hit is None and start:
            hit = next((i for i in range(0, len(lines))
                        if token_re.search(lines[i])), None)
        symbols.append({
            "name": sym["name"],
            "dumpCsLine": (f"~L{hit + 1}" if hit is not None else None),
        })
        if hit is None and drift is not None:
            short = sym["name"].split("(")[0]
            drift.check(f"fallbackSymbol[{short}] dumpCsLine",
                        "matched-in-dump.cs", "token-not-found")
    return symbols, "verified"


def pass_l4(inputs: dict, drift: Drift, base_only_vs_en: list[str],
            empty_cells: dict, locs: list[str]) -> dict:
    base_overlay = inputs["base_overlay"]
    report = inputs["base_overlay_report"]
    registry = inputs["registry"]

    rows = len(base_overlay)
    non_empty = sum(1 for r in base_overlay if r.get("text"))
    evidence = report.get("evidence") or {}
    language_sources = evidence.get("registrySources")
    raw_terms = evidence.get("registryTerms")
    # the registry holds only TERM rows, so every distinct sourceAsset in it
    # is term-bearing (the 0-term I2LS_TEMPLATE source never appears)
    term_bearing = len({r.get("sourceAsset") for r in registry})
    drift.check("baseOverlayRows", SEEDS["baseOverlayRows"], rows)
    drift.check("baseOverlayRowsWithNonEmptyText",
                SEEDS["baseOverlayRowsWithNonEmptyText"], non_empty)
    drift.check("languageSources", SEEDS["languageSources"], language_sources)
    drift.check("rawTermsDecoded", SEEDS["rawTermsDecoded"], raw_terms)
    skipped_total = sum(empty_cells.values())
    drift.check("emptyCellsSkippedTotal",
                SEEDS["emptyCellsSkippedTotal"], skipped_total)

    symbols, symbol_check = measure_symbol_lines(
        inputs.get("dump_cs") or Path("nonexistent"), drift)

    artifact = {
        "meta": {"buildId": inputs["build_id"]},
        "baseOverlay": {
            "role": "master-registry",
            "rows": rows,
            "rowsWithNonEmptyText": non_empty,
            "languageSources": language_sources,
            "termBearingSources": term_bearing,
            "rawTermsDecoded": raw_terms,
            "storageShape": BASE_STORAGE_SHAPE,
            "compositionPolicyEmitted": report.get("compositionPolicy"),
            "measuredSemantics": BASE_MEASURED_SEMANTICS,
            "baseOnlyKeysVsEn": base_only_vs_en,
        },
        "namedBundles": {
            "selfContained": True,
            "emptyCellsSkippedPerLocale": {l: empty_cells[l]
                                           for l in locs},
            "borrowingRule": BORROWING_RULE,
        },
        "runtimeFallback": {
            "pathExistence": "PROVEN (declarations; bodies absent from "
                             "dump.cs)",
            "symbols": symbols,
            "fallbackOrder": RUNTIME_FALLBACK_ORDER_TEXT,
            "symbolCheck": symbol_check,
        },
        "siteSemantics": {
            "policy": "omit | declared-filler",
            "authority": "localization-architecture.md §5.5",
            "pivotFillBanned": True,
            "fillerKeyReserved": "site-chrome namespace, never game data",
        },
    }
    run = {
        "pass": "L4",
        "baseOverlayRows": rows,
        "baseOverlayEmptyTextRows": non_empty,
        "symbolCheck": symbol_check,
    }
    return {"artifact": artifact, "run": run}


# ---------------------------------------------------------------------------
# L5 — site-UI namespace split + chrome gap manifest

def pass_l5(inputs: dict, drift: Drift, orphans_a_keys: set,
            locs: list[str]) -> dict:
    registry = inputs["registry"]
    ref_keys = {e["dstId"] for e in inputs["edges"]}
    # DISTINCT-key universes (registry is canonical-on-key but carries
    # non-canonical twin rows — F16: the 3 extra rows are all UI/* — so
    # counting rows here would inflate every namespace census)
    keys = sorted({r["termKey"] for r in registry})

    ui = [k for k in keys if k.startswith("UI/")]
    ui_ref = sum(1 for k in ui if k in ref_keys)
    input_ns = sum(1 for k in keys if k.startswith("Input/"))
    general_ns = sum(1 for k in keys if k.startswith("General/"))
    settings_src = sum(1 for r in registry
                       if r.get("sourceAsset") == "I2LS_UI_Settings")
    top_level = {k.split("/")[0] for k in keys}

    bindings = 0
    for row in (inputs.get("ui_coverage_rows") or []):
        if row.get("surfaceId") == "i2-localize-bindings":
            try:
                bindings = int(row.get("exportedCount") or 0)
            except (TypeError, ValueError):
                bindings = 0
    drift.check("uiRegistryKeys", SEEDS["uiRegistryKeys"], len(ui))
    drift.check("uiReferenced", SEEDS["uiReferenced"], ui_ref)
    drift.check("inputNamespaceKeys", SEEDS["inputNamespaceKeys"], input_ns)
    drift.check("generalNamespaceKeys", SEEDS["generalNamespaceKeys"],
                general_ns)
    drift.check("uiSettingsSourceTerms", SEEDS["uiSettingsSourceTerms"],
                settings_src)
    drift.check("topLevelNamespaces", SEEDS["topLevelNamespaces"],
                len(top_level))
    drift.check("localizeBindings", SEEDS["localizeBindings"], bindings)

    artifact = {
        "meta": {"buildId": inputs["build_id"]},
        "gameDataSide": {
            "uiNamespace": {
                "registryKeys": len(ui),
                "referencedByEntities": ui_ref,
                "free": len(ui) - ui_ref,
                "universe": "distinct registry keys under 'UI/'",
            },
            "reusableNamespaces": {
                "Input": input_ns,
                "General": general_ns,
                "UI_Settings_source": settings_src,
            },
            "topLevelNamespaces": len(top_level),
            "localizeBindings": bindings,
            "freeNarrativeKeys": len(orphans_a_keys),
            "note": "game UI strings describe GAME screens; reusable as "
                    "game-faithful labels, never as site chrome",
        },
        "siteChromeSide": {
            "clientCoverageKeys": 0,
            "localesRequired": len(locs),
            "shipRule": "chrome-complete per locale (localization-arch §4)",
            "surfaces": [
                {"surfaceId": sid,
                 "kind": "prose" if sid in CHROME_PROSE_SURFACES
                 else "keyed",
                 "clientCoverageKeys": 0,
                 "locales": len(locs)}
                for sid in CHROME_SURFACES],
        },
    }
    run = {
        "pass": "L5",
        "uiRegistryKeys": len(ui),
        "uiReferenced": ui_ref,
        "uiFree": len(ui) - ui_ref,
        "localizeBindings": bindings,
        "chromeSurfaces": len(CHROME_SURFACES),
    }
    return {"artifact": artifact, "run": run}


# ---------------------------------------------------------------------------
# L6 — registry completeness + assembly + tripwire

STATUS_NAMES = {1: "ForTranslation", 0: "NotForTranslation"}


def derive_misses(inputs: dict, registry_keys: set) -> tuple[list[str], list[dict]]:
    """Split join-report unresolvedIds into closableViaCodeDev and dangling
    rows — ONE ROW PER termId, enriched from the stub payloads.

    Closability rule (reproducible from committed artifacts): the miss
    spells a registered key under the Code/ namespace — `Code/<fieldPath>`
    OR `Code/<_dev>` present in i2_term_registry, probed IN THAT ORDER
    (F18 wording is "_dev string IS the key under Code/", while the
    measured LocalisedStringCodeRef cells carry the key as their
    fieldPath; probing both reproduces the pinned 3-closable/2-dangling
    split under either spelling). The two WantsMessage misses match
    neither (`Code/WantsMessage` / `Code/Wants a {ITEM}` are not keys), so
    they stay dangling. All closable keys are verified present in
    locales/en.jsonl at emit time."""
    join_report = inputs["join_report"]
    stub_lookup: dict[tuple, dict] = {}
    for kind in KINDS:
        for row in inputs["stubs"][kind]:
            stub_lookup[(kind, row_id(row))] = row

    grouped: dict[int, dict] = {}
    for miss in join_report.get("unresolvedIds") or []:
        tid = miss.get("termId")
        refs = miss.get("sampleRefs") or []
        g = grouped.setdefault(int(tid), {
            "termId": int(tid), "fieldPath": None, "dev": None,
            "srcKind": None, "onIds": [], "_devs": set()})
        for ref in refs:
            src_id = str(ref.get("srcId"))
            src_kind = ref.get("srcKind")
            g["onIds"].append(src_id)
            g["srcKind"] = g["srcKind"] or src_kind
            g["fieldPath"] = g["fieldPath"] or ref.get("fieldPath")
            stub = stub_lookup.get((src_kind, src_id))
            fields = (stub or {}).get("fields") \
                if isinstance((stub or {}).get("fields"), dict) else {}
            for fname, fval in fields.items():
                if isinstance(fval, dict) and fval.get("_termID") == tid:
                    g["_devs"].add(str(fval.get("_dev") or ""))
                    g["fieldPath"] = g["fieldPath"] or fname
        for dev in sorted(g["_devs"]):
            g["dev"] = dev

    closable: list[str] = []
    dangling: list[dict] = []
    for tid in sorted(grouped):
        g = grouped[tid]
        dev = g["dev"]
        code_candidates = [
            f"Code/{name}" for name in (g["fieldPath"], dev) if name]
        code_key = next(
            (c for c in code_candidates if c in registry_keys), None)
        if code_key is not None:
            closable.append(code_key)
            continue
        dangling.append({
            "termId": int(tid),
            "fieldPath": g["fieldPath"],
            "dev": dev,
            "srcKind": g["srcKind"],
            "onIds": sorted(set(g["onIds"])),
        })
    closable.sort()
    dangling.sort(key=lambda d: d["termId"])
    return closable, dangling


def pass_l6(inputs: dict, drift: Drift, locs: list[str]) -> dict:
    registry = inputs["registry"]
    edges = inputs["edges"]
    tables = inputs["tables"]
    registry_keys = {r["termKey"] for r in registry}

    rows_n = len(registry)
    distinct = len(registry_keys)
    non_canonical = sum(1 for r in registry if not r.get("canonical"))
    status_split = Counter()
    for r in registry:
        name = STATUS_NAMES.get(r.get("termStatus"))
        if name is None:
            raise tc.StageError(
                f"unexpected termStatus {r.get('termStatus')!r} in "
                "i2_term_registry.jsonl (pinned enum: 0|1)", exit_code=1)
        status_split[name] += 1
    term_types = {r.get("termType") for r in registry}
    if len(term_types) != 1:
        raise tc.StageError(
            f"termType not uniform: {sorted(term_types)!r}", exit_code=1)
    term_type_value = next(iter(term_types))
    locales_projection_empty = all(r.get("locales") == [] for r in registry)
    if not locales_projection_empty:
        raise tc.StageError(
            "locales projection no longer empty on i2_term_registry rows — "
            "the consumer warning would be stale", exit_code=1)

    mx = inputs["matrix_keys"]
    reg_minus_mx = registry_keys - mx
    mx_minus_reg = mx - registry_keys
    if reg_minus_mx or mx_minus_reg:
        raise tc.StageError(
            f"matrixKeyDiff asserted 0 both directions at emit time: "
            f"registry\\matrix={len(reg_minus_mx)} "
            f"matrix\\registry={len(mx_minus_reg)}", exit_code=1)
    matrix_key_diff = len(reg_minus_mx) + len(mx_minus_reg)

    ref_keys = {e["dstId"] for e in edges}
    entities = {(e["srcKind"], str(e["srcId"])) for e in edges}
    usage_edges_reverse = sum(len(r.get("usages") or [])
                              for r in inputs["reverse"])
    drift.check("usageEdges(reverse index)", SEEDS["usageEdges"],
                usage_edges_reverse)
    drift.check("referencedKeys", SEEDS["referencedKeys"], len(ref_keys))
    drift.check("registryRows", SEEDS["registryRows"], rows_n)
    drift.check("statusSplit", SEEDS["statusSplit"], dict(status_split))

    orphans_a_keys = registry_keys - ref_keys
    orphans_a_rows = sum(1 for r in registry if r["termKey"] in orphans_a_keys)
    orphans_b = ref_keys - registry_keys
    drift.check("orphansARows", SEEDS["orphansARows"], orphans_a_rows)
    drift.check("orphansAKeys", SEEDS["orphansAKeys"], len(orphans_a_keys))
    drift.check("orphansB", SEEDS["orphansB"], len(orphans_b))

    top_ns = {k.split("/")[0] for k in registry_keys}
    ns_counts = Counter(k.split("/")[0] for k in orphans_a_keys)
    namespaces = sorted(
        ({"namespace": ns, "count": ns_counts.get(ns, 0)}
         for ns in top_ns),
        key=lambda d: (-d["count"], d["namespace"]))

    closable, dangling = derive_misses(inputs, registry_keys)
    en_keys = set(tables[PIVOT])
    missing_closable = [k for k in closable if k not in en_keys]
    if missing_closable:
        raise tc.StageError(
            "closableViaCodeDev keys absent from locales/en.jsonl: "
            f"{missing_closable}", exit_code=1)
    drift.check("registryMisses(total)",
                SEEDS["registryMisses"], len(closable) + len(dangling))
    code_ref_terms = sum(1 for r in registry
                         if r.get("sourceAsset") == "I2LS_CodeRef")
    drift.check("codeRefTerms", SEEDS["codeRefTerms"], code_ref_terms)

    artifact = {
        "rows": rows_n,
        "distinctKeys": distinct,
        "nonCanonicalRows": non_canonical,
        "statusSplit": {"ForTranslation": status_split["ForTranslation"],
                        "NotForTranslation":
                            status_split["NotForTranslation"]},
        "termTypeUniform": term_type_value,
        "localesProjectionEmpty": locales_projection_empty,
        "matrixKeyDiff": matrix_key_diff,
        "referencedKeys": len(ref_keys),
        "usageEdges": len(edges),
        "distinctEntities": len(entities),
        "orphansA": {
            "rows": orphans_a_rows,
            "keys": len(orphans_a_keys),
            "countConvention": "distinct-keys",
            "namespaces": namespaces,
        },
        "orphansB": len(orphans_b),
        "codeRefTerms": code_ref_terms,
        "registryMisses": {
            "total": len(closable) + len(dangling),
            "closableViaCodeDev": closable,
            "dangling": dangling,
        },
        "consumerWarnings": list(CONSUMER_WARNINGS),
    }

    empty_cells = {l: len(registry_keys) - len(tables[l]) for l in locs}
    run = {
        "pass": "L6",
        "registryRows": rows_n,
        "registryDistinctKeys": distinct,
        "matrixKeyDiff": matrix_key_diff,
        "orphansAKeys": len(orphans_a_keys),
        "orphansB": len(orphans_b),
    }
    return {"artifact": artifact, "run": run, "orphansAKeys": orphans_a_keys,
            "emptyCells": empty_cells, "closable": closable,
            "dangling": dangling, "registryKeys": registry_keys}


def build_ledger(inputs: dict, l2: dict, l6: dict, alias_map: dict | None,
                 name_edges: dict) -> list[dict]:
    """ONE ROW PER UNDERLYING OPEN ITEM for enumerable IDs; ONE AGGREGATE
    ROW for counted populations (arbiter R3). Sorted by (code, detail)."""
    build_id = inputs["build_id"]
    rows: list[dict] = []

    def add(code: str, severity: str, detail: str,
            unblock: str | None = None):
        rows.append({"code": code, "severity": severity, "detail": detail,
                     "unblock": unblock
                     or LEDGER_CODES_DOC.get(code, ""), "buildId": build_id})

    for d in l6["dangling"]:
        add("registry-miss-dangling", "gap",
            f"termId={d['termId']} srcKind={d['srcKind']} "
            f"id={','.join(d['onIds'])} fieldPath={d['fieldPath']} "
            f"dev={d['dev']!r}")
    closable = l6["closable"]
    if closable:
        add("registry-miss-closable", "info",
            "dev strings ARE registered keys under Code/: "
            + "; ".join(closable))
    per_kind = {}
    for r in l2["unjoinedRows"]:
        per_kind[r["kind"]] = per_kind.get(r["kind"], 0) + 1
    breakdown = "; ".join(
        f"{k}:{per_kind.get(k, 0)}" for k in KINDS if per_kind.get(k))
    if l2["unjoinedRows"]:
        classes = dict(sorted(Counter(
            r["class"] for r in l2["unjoinedRows"]).items()))
        add("entity-unjoined", "gap",
            f"{len(l2['unjoinedRows'])} zero-join stub rows "
            f"[{breakdown}] classes={json.dumps(classes, sort_keys=True)} "
            f"({UNJOINED_RESIDUE_WARNING})")

    courses_total = len(inputs["stubs"]["course"])
    unresolved_courses = sum(
        1 for row in inputs["stubs"]["course"]
        if ("course", row_id(row)) not in name_edges)
    if alias_map is None:
        add("alias-input-absent", "info",
            f"{ALIAS_REL_PACK.as_posix()} absent — course name-columns ship "
            "open (F15); G2 stays unclosed for this piece and piece-08")
        add("course-name-join-open", "gap",
            COURSE_NAME_ROLE_NOTE_BASE.format(
                edges=sum(1 for e in inputs["edges"]
                          if e["srcKind"] == "course"),
                courses=courses_total))
    elif unresolved_courses:
        # ABSENT when the alias input is present AND total (spec §L6)
        methods = sorted({str(a.get("method") or "")
                          for a in alias_map.values()})
        add("course-name-join-open", "gap",
            f"alias input present ({len(alias_map)} rows, methods: "
            f"{', '.join(methods) or 'none'}) but {unresolved_courses} of "
            f"{courses_total} course stub ids have no resolving alias row")

    hospital = sum(1 for r in inputs["registry"]
                   if r["termKey"].startswith("Items/DLC_Hospital/"))
    preorder = sum(1 for r in inputs["registry"]
                   if "preorder" in r["termKey"].lower())
    drift = Drift()
    drift.check("dlcHospitalKeys", SEEDS["dlcHospitalKeys"], hospital)
    if hospital or preorder:
        add("dlc-out-of-install-scope", "info",
            f"locale tables ship text for content this install lacks: "
            f"Items/DLC_Hospital/* ({hospital} keys) + dlc-preorder-* "
            f"({preorder} keys) exist while Medical School/preorder are "
            "out-of-roster; coverage claims state install scope (G8)")

    rows.sort(key=lambda r: (r["code"], r["detail"]))
    return rows


def build_vector(inputs: dict, l1: dict, l2: dict, l3: dict,
                 l5: dict, l6: dict) -> dict:
    union_key = next(k for k in l1["artifact"]["meta"]["universes"]
                     if k.startswith("unionOf"))
    vector: dict = {
        "unionKeys": l1["artifact"]["meta"]["universes"][union_key],
        "allThirteenKeys": l1["artifact"]["allThirteenShare"]["numerator"],
        "resolvedEdges": l2["artifact"]["census"]["resolvedEdges"],
        "registryMisses": l2["artifact"]["census"]["registryMisses"],
        "coverageNumerator":
            l2["artifact"]["census"]["coverageOnNonEmpty"]["numerator"],
        "availabilityRowCount": len(l3["rows"]),
        "registryRows": l6["artifact"]["rows"],
        "registryDistinctKeys": l6["artifact"]["distinctKeys"],
        "matrixKeyDiff": l6["artifact"]["matrixKeyDiff"],
        "orphansAKeys": len(l6["orphansAKeys"]),
        "orphansB": l6["artifact"]["orphansB"],
        "uiReferenced":
            l5["artifact"]["gameDataSide"]["uiNamespace"][
                "referencedByEntities"],
        "chromeSurfaces": len(CHROME_SURFACES),
    }
    locs = l1["artifact"]["meta"]["localeRoster"]
    for loc in locs:
        vector[f"rows.{loc}"] = l1["artifact"]["perLocale"][loc]["rows"]
        vector[f"holes.{loc}"] = l1["artifact"]["perLocale"][loc][
            "unionHoles"]
    for kind in KINDS:
        vector[f"joined.{kind}"] = l2["artifact"]["kinds"][kind][
            "joinedEntities"]
        vector[f"availRows.{kind}"] = l3["report"]["perKindRowCounts"].get(
            kind, 0)
    return vector


def worse_members(old: dict, new: dict) -> list[tuple]:
    """Members that got WORSE under their pinned direction. Exact-match
    members count ANY change as worse (a structural invariant moving is
    never an improvement)."""
    out = []
    for member in sorted(new):
        if member not in old:
            continue
        o, n = old[member], new[member]
        direction = vector_direction(member)
        if direction == "exact":
            worse = n != o
        elif direction == "lower":
            worse = n > o
        else:  # higher-better coverage counts
            worse = n < o
        if worse:
            out.append((member, o, n))
    return out


def evaluate_baseline(proof_dir: Path, build_id, vector: dict) -> dict:
    """Tripwire state machine (§L6.3). Returns verdict/action/lines; NEVER
    writes — the caller decides (a regression leaves the baseline
    untouched)."""
    path = proof_dir / ".baseline.json"
    state = None
    if path.is_file():
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            state = None
    if state is None:
        return {"verdict": "first-run", "action": "create", "lines": [],
                "regression": False,
                "new_baseline": {"buildId": build_id, "vector": vector,
                                 "previousVerdict": "first-run"}}
    old_build = state.get("buildId")
    old_vector = state.get("vector") or {}
    if old_build != build_id:
        changed = [m for m in sorted(vector)
                   if m in old_vector and old_vector[m] != vector[m]]
        lines = [
            f"DRIFT: baseline buildId {old_build} vs measured {build_id} — "
            "different build, fresh wins (never a regression verdict "
            "across builds)"]
        for m in changed[:50]:
            lines.append(
                f"DRIFT: {m} {old_vector[m]}->{vector[m]}")
        if len(changed) > 50:
            lines.append(f"DRIFT: ... and {len(changed) - 50} more members")
        return {"verdict": "drift", "action": "rewrite", "lines": lines,
                "regression": False,
                "new_baseline": {"buildId": build_id, "vector": vector,
                                 "previousVerdict": "drift"}}
    worsened = worse_members(old_vector, vector)
    if worsened:
        lines = [f"REGRESSION: {m} {o}->{n}" for (m, o, n) in worsened]
        return {"verdict": "regression", "action": "untouched",
                "lines": lines, "regression": True, "new_baseline": None}
    improved = [m for m in sorted(vector)
                if m in old_vector and old_vector[m] != vector[m]]
    if not improved:
        # Equal rerun: §L6.3 bullet 1 — baseline UNTOUCHED (neither worse
        # nor DRIFT; rewriting would churn previousVerdict bytes while
        # nothing changed, breaking byte-stable tripwire state).
        return {"verdict": "ok", "action": "untouched", "lines": [],
                "regression": False, "new_baseline": None}
    return {"verdict": "improved", "action": "rewrite", "lines": [],
            "regression": False,
            "new_baseline": {"buildId": build_id, "vector": vector,
                             "previousVerdict": "improved"}}


def build_summary(inputs: dict, l1: dict, l2: dict, l3: dict, l5: dict,
                  l6: dict, ledger_rows: list[dict], vector: dict,
                  locs: list[str]) -> dict:
    kp = l1["artifact"]
    census = l2["artifact"]["census"]
    union_key = next(k for k in kp["meta"]["universes"]
                     if k.startswith("unionOf"))
    ru_row = kp["identityToPivot"].get("ru") or {}
    return {
        "meta": {"buildId": inputs["build_id"]},
        "headline": {
            "unionKeys": kp["meta"]["universes"][union_key],
            "registryUniverse": kp["meta"]["universes"]["registry"],
            "allThirteenKeys": kp["allThirteenShare"]["numerator"],
            "allThirteenShareUnion": kp["allThirteenShare"]["rate"],
            "allThirteenShareRegistryUniverse":
                kp["allThirteenShare"]["registryUniverseRate"],
            "localeCount": len(locs),
            "pivot": PIVOT,
            "resolvedEdges": census["resolvedEdges"],
            "coverageOnNonEmpty": census["coverageOnNonEmpty"],
            "availabilityRows": len(l3["rows"]),
            "unjoinedRows": len(l2["unjoinedRows"]),
            "ledgerRows": len(ledger_rows),
            "ruByteIdenticalToEn": ru_row.get("byteIdenticalToEn"),
            "ruIdenticalAndDeDiffers":
                ru_row.get("identicalAndDeDiffers"),
            "uiRegistryKeys":
                l5["artifact"]["gameDataSide"]["uiNamespace"][
                    "registryKeys"],
            "chromeSurfaces": len(CHROME_SURFACES),
        },
        "regressionVectorDirections": {
            "higher-better": sorted(m for m in vector
                                    if vector_direction(m) == "higher"),
            "lower-better": sorted(m for m in vector
                                   if vector_direction(m) == "lower"),
            "exact-match": sorted(m for m in vector
                                  if vector_direction(m) == "exact"),
        },
        "regressionVector": dict(sorted(vector.items())),
    }


# ---------------------------------------------------------------------------
# Emission

def emit(extracted_root: Path, artifacts: dict) -> list[str]:
    """Temp-file + atomic-rename writes for EVERY declared output. Returns
    the emitted relpaths (relative to the extracted root)."""
    proof_dir = extracted_root / PROOF_DIR
    relpaths: list[str] = []

    def put(rel: str, obj) -> None:
        p = extracted_root / rel
        log_util.write_json(p, obj)
        relpaths.append(rel)

    def put_jsonl(rel: str, rows) -> None:
        p = extracted_root / rel
        log_util.write_jsonl(p, rows)
        relpaths.append(rel)

    put(f"{PROOF_DIR}/key_plane.json", artifacts["key_plane"])
    for loc in artifacts["locales"]:
        put_jsonl(f"{PROOF_DIR}/key_holes/{loc}.jsonl",
                  artifacts["holeFiles"][loc])
    put(f"{PROOF_DIR}/kind_locale_matrix.json", artifacts["matrix"])
    put_jsonl(f"{PROOF_DIR}/unjoined_entities.jsonl",
              artifacts["unjoinedRows"])
    put(f"{PROOF_DIR}/fallback_law.json", artifacts["fallback_law"])
    put(f"{PROOF_DIR}/site_ui_gap_manifest.json",
        artifacts["site_ui_manifest"])
    put(f"{PROOF_DIR}/registry_completeness.json",
        artifacts["registry_completeness"])
    put(f"{PROOF_DIR}/summary.json", artifacts["summary"])
    put_jsonl(AVAILABILITY_REL, artifacts["availability_rows"])
    put(AVAILABILITY_REPORT_REL, artifacts["availability_report"])
    put_jsonl(f"{PROOF_DIR}/_ledger.jsonl", artifacts["ledger_rows"])

    files = {}
    for rel in sorted(relpaths):
        files[rel] = log_util.sha256_file(extracted_root / rel)
    put(f"{PROOF_DIR}/hashes.json", {
        "algorithm": "sha256",
        "buildId": artifacts["build_id"],
        "excluded": [f"{PROOF_DIR}/.baseline.json",
                     f"{PROOF_DIR}/hashes.json"],
        "files": files,
    })
    return relpaths


# ---------------------------------------------------------------------------
# Entrypoint

def run(game_root: Path | None, extracted_root: Path) -> int:
    del game_root  # purely derived stage: opens NO bundles, needs NO game dir
    drift = Drift()
    precheck_inputs(extracted_root)
    inputs = load_inputs(extracted_root, drift)
    alias_rows = load_alias_input(extracted_root.parent)
    alias_map = None
    if alias_rows is not None:
        alias_map = {str(r["courseId"]): r for r in alias_rows}

    dump_cs = extracted_root / "decompiled" / "il2cppdumper" / "dump.cs"
    inputs["dump_cs"] = dump_cs
    # R5 census rides the committed ui_link_coverage rows (OPTIONAL_INPUTS[0]:
    # absence ⇒ bindings 0 — never a gate failure)
    coverage_path = extracted_root / OPTIONAL_INPUTS[0]
    inputs["ui_coverage_rows"] = (load_jsonl(coverage_path)
                                  if coverage_path.is_file() else [])

    registry_keys_seed = {r["termKey"] for r in inputs["registry"]}
    grouped = group_edges(inputs["edges"])
    name_edges = build_name_edges(grouped, inputs["stubs"], alias_map,
                                  registry_keys_seed)

    problems: list[str] = []

    locs = inputs["locales"]
    l1 = pass_l1(inputs, drift, locs)
    l2 = pass_l2(inputs, drift, name_edges, alias_map, locs)
    l3 = pass_l3(inputs, drift, name_edges, locs)
    # L6 first among the tail passes: L4 reuses its empty-cell map and L5
    # its orphan universe
    l6 = pass_l6(inputs, drift, locs)
    l4 = pass_l4(inputs, drift, l1["artifact"]["quirks"]["baseOnlyVsEn"],
                 l6["emptyCells"], locs)
    l5 = pass_l5(inputs, drift, l6["orphansAKeys"], locs)
    ledger_rows = build_ledger(inputs, l2, l6, alias_map, name_edges)
    vector = build_vector(inputs, l1, l2, l3, l5, l6)
    summary = build_summary(inputs, l1, l2, l3, l5, l6, ledger_rows, vector,
                            locs)

    proof_dir = extracted_root / PROOF_DIR
    trip = evaluate_baseline(proof_dir, inputs["build_id"], vector)

    for line in drift.lines:
        print(f"[{STAGE_ID}] {line}", file=sys.stderr)
    for line in trip["lines"]:
        print(f"[{STAGE_ID}] {line}")
        print(f"[{STAGE_ID}] {line}", file=sys.stderr)

    if trip["regression"]:
        problems.extend(trip["lines"])
    if problems:
        # AC13 precedence 1 > 2 > 0 (F7): a run with open ledgers AND a
        # regression exits 1 and NAMES BOTH in the run section.
        log_util.append_run_section(extracted_root, STAGE_ID,
                                    ["- exitCode: 1 (failed)"]
                                    + [f"- PROBLEM: {p}" for p in problems]
                                    + ["ledgerCodes: "
                                       + json.dumps(dict(sorted(Counter(
                                           r["code"] for r in
                                           ledger_rows).items())),
                                           sort_keys=True)]
                                    + [f"- ledgerRows={len(ledger_rows)}"]
                                    + [f"- {code}="
                                       f"{sum(1 for r in ledger_rows if r['code'] == code)}"
                                       for code in sorted({r["code"] for r in ledger_rows})]
                                    + ["- regressionVerdict: "
                                       + trip["verdict"],
                                       "- baselineAction: "
                                       + trip["action"]])
        print(f"[{STAGE_ID}] PROBLEM: " + "; ".join(problems[:5]),
              file=sys.stderr)
        return 1

    artifacts = {
        "build_id": inputs["build_id"],
        "locales": locs,
        "key_plane": l1["artifact"],
        "holeFiles": l1["holeFiles"],
        "matrix": l2["artifact"],
        "unjoinedRows": l2["unjoinedRows"],
        "availability_rows": l3["rows"],
        "availability_report": l3["report"],
        "fallback_law": l4["artifact"],
        "site_ui_manifest": l5["artifact"],
        "registry_completeness": l6["artifact"],
        "summary": summary,
        "ledger_rows": ledger_rows,
    }
    emit(extracted_root, artifacts)
    if trip["new_baseline"] is not None:
        log_util.write_json(proof_dir / ".baseline.json",
                            trip["new_baseline"])

    run_lines = (
        [f"- exitCode: {2 if ledger_rows else 0}"]
        # §4 Run-section keys are PINNED tokens spelled `key=value`; values
        # that are dicts ride as compact JSON beside their key.
        + [f"- {k}={json.dumps(v, sort_keys=True, ensure_ascii=False)}"
           for k, v in l1["run"].items() if k != "pass"]
        + [f"- {k}={json.dumps(v, sort_keys=True, ensure_ascii=False)}"
           for k, v in l2["run"].items() if k != "pass"]
        + [f"- {k}={json.dumps(v, sort_keys=True, ensure_ascii=False)}"
           for k, v in l3["run"].items() if k != "pass"]
        + [f"- {k}={json.dumps(v, sort_keys=True, ensure_ascii=False)}"
           for k, v in l4["run"].items() if k != "pass"]
        + [f"- {k}={json.dumps(v, sort_keys=True, ensure_ascii=False)}"
           for k, v in l5["run"].items() if k != "pass"]
        + [f"- {k}={json.dumps(v, sort_keys=True, ensure_ascii=False)}"
           for k, v in l6["run"].items() if k != "pass"]
        + ["ledgerCodes: "
           + json.dumps(dict(sorted(Counter(
               r["code"] for r in ledger_rows).items())), sort_keys=True)]
        + [f"- ledgerRows={len(ledger_rows)}"]
        + [f"- {code}={sum(1 for r in ledger_rows if r['code'] == code)}"
           for code in sorted({r["code"] for r in ledger_rows})]
        + ["- regressionVerdict: " + trip["verdict"],
           "- baselineAction: " + trip["action"]]
    )
    log_util.append_run_section(extracted_root, STAGE_ID, run_lines)

    union_key = next(k for k in l1["artifact"]["meta"]["universes"]
                     if k.startswith("unionOf"))
    print(f"[{STAGE_ID}] locales={len(locs)} "
          f"union={l1['artifact']['meta']['universes'][union_key]} "
          f"allHolding="
          f"{l1['artifact']['allThirteenShare']['numerator']} "
          f"({l1['artifact']['allThirteenShare']['rate']} union / "
          f"{l1['artifact']['allThirteenShare']['registryUniverseRate']} "
          f"registry universe)")
    print(f"[{STAGE_ID}] availabilityRows={len(l3['rows'])} "
          f"unjoined={len(l2['unjoinedRows'])} "
          f"symbolCheck={l4['run']['symbolCheck']} "
          f"chromeSurfaces={len(CHROME_SURFACES)}")
    print(f"[{STAGE_ID}] ledger: "
          + ", ".join(
              f"{code}={sum(1 for r in ledger_rows if r['code'] == code)}"
              for code in sorted({r['code'] for r in ledger_rows}))
          + f" (rows={len(ledger_rows)})")
    print(f"[{STAGE_ID}] regressionVerdict={trip['verdict']} "
          f"baselineAction={trip['action']}")
    return 2 if ledger_rows else 0


def main(argv=None) -> int:
    log_util.bootstrap_console()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("game_dir", nargs="?", default=None,
                        help="ignored: this stage opens no bundles")
    parser.add_argument("--extracted-root", default=None)
    args = parser.parse_args(argv)
    extracted_root = None
    try:
        pack_dir = tc.resolve_pack_dir()
        extracted_root = tc.resolve_extracted_root(pack_dir)
        if args.extracted_root:
            extracted_root = Path(args.extracted_root).resolve()
        return run(None, extracted_root)
    except tc.StageError as exc:
        try:
            log_util.append_failure_section(
                extracted_root if extracted_root
                else tc.resolve_extracted_root(tc.resolve_pack_dir()),
                STAGE_ID, exc.exit_code, [str(exc)])
        except Exception:  # noqa: BLE001 — logging must not mask the failure
            pass
        print(f"[{STAGE_ID}] ERROR: {exc}", file=sys.stderr)
        return exc.exit_code


if __name__ == "__main__":
    sys.exit(main())
