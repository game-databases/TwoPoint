#!/usr/bin/env python3
"""Shared helpers for stage 12 `search-corpus` (piece-08, spec Revision 3).

docs/specs/piece-08-search-corpus.mdx is THE contract; this module holds
its pure, deterministic pieces so the TestWriter can drive them directly:

  - pinned vocabularies (name classes, variants, descriptions, weights,
    visibility roster, token map, analyzer table);
  - text cleaning (tags + placeholders) and the id-token rule;
  - the LocalisedString predicates and the deep stub-field walker;
  - the dual-universe recipes (S1 narrow carriers / expanded components);
  - the course-name resolver (S3.2 union-set staging, five families,
    seven-entry token map, curated rows);
  - the per-locale analyzer census (S4) and collision counters (S3.4);
  - document-schema + AC4 ratio-band validators.

PURELY DERIVED layer: no UnityPy import, no bundle IO, no game dir, no
wall-clock anything. Every seed figure lives in the SEEDS dict of the
stage script — here only RULES live (rules are contract, numbers are
measurements).
"""
from __future__ import annotations

import re
from collections import Counter
from statistics import median

# ---------------------------------------------------------------------------
# Pinned vocabularies (spec §S1.1 / §S2 / §S3 / §S4 — Rev 3 member sets)

PIVOT = "en"

KIND_FILES = {
    "item": "items.jsonl", "unlockable": "unlockables.jsonl",
    "room": "rooms.jsonl", "campus-level": "campus-levels.jsonl",
    "course": "courses.jsonl", "config": "configs.jsonl",
    "staff": "staff.jsonl", "metagame-node": "metagame-nodes.jsonl",
    "student-type": "student-types.jsonl",
}
KINDS = ["campus-level", "config", "course", "item", "metagame-node",
         "room", "staff", "student-type", "unlockable"]

# §S1.1 pinned NAME-CLASS paths per kind — the star notation denotes
# EXACTLY these members (reviewer F3 trap: reading `LocalisedName*` as the
# single field `LocalisedName` measures carriers 4,282 / union 7,172).
NAME_CLASS_FIELDS = {
    "config": ("Name",),
    "room": ("NameWhenBuilt",),
    "staff": ("LocalisedName",),
    "item": ("LocalisedName", "LocalisedNameFemale", "LocalisedNameMale"),
    "metagame-node": ("LocalisedName", "LocalisedNameFemale",
                      "LocalisedNameMale"),
    "unlockable": ("LocalisedName", "LocalisedNameFemale",
                   "LocalisedNameMale"),
    "student-type": ("LocalisedNameF", "LocalisedNameM"),
    "campus-level": (),   # plain non-empty `Name` string only
    "course": (),
}
# student-type: LocalisedNameF is THE name; LocalisedNameM rides as variant.
NAME_FIELD_OVERRIDE = {"student-type": ("LocalisedNameF",)}

# name-VARIANT alias sources (§S3.1 `name-variant` class): the §S1.1 member
# spellings other than the name itself, plus staff Ranks[].TitleM/F. These
# resolve through entity_locale EDGES (fieldPath space), never dev text.
VARIANT_EDGE_PATHS = {
    "item": ("LocalisedNameFemale", "LocalisedNameMale"),
    "metagame-node": ("LocalisedNameFemale", "LocalisedNameMale"),
    "unlockable": ("LocalisedNameFemale", "LocalisedNameMale"),
    "student-type": ("LocalisedNameM",),
    "staff": ("Ranks[].TitleMale", "Ranks[].TitleFemale"),
}

DESCRIPTION_EDGE_PATHS = {
    "config": ("Description", "FlavourDescriptions[]"),
    "item": ("Description",),
    "room": ("Description", "LongDescription"),
}

# §S5.1 frozen ranking hint (single authority; doc `weight` snapshots it)
KIND_WEIGHTS = {
    "item": 1.0, "room": 1.0, "course": 1.0, "staff": 1.0,
    "student-type": 0.9, "unlockable": 0.8, "metagame-node": 0.6,
    "config": 0.5, "campus-level": 0.3,
}

# §S2 visibility roster (G8 scope decision; flipping = editing this list,
# never code — arbiter-piece08 R3). Measured campus-level dev roster ships
# `internal`; the 4 null-name campus-levels emit no document at all.
VISIBILITY_INTERNAL_ROSTER = (
    "Blank Level", "Free Play Level", "IL3 Video 1", "IL3 Video 2",
    "IL3 Video 3", "IL3 Video 4", "IL3 Video 5", "IL3 Demo Level",
    "Mark's Test Scenario", "September 2020 Milestone", "Test Level",
)

# §S3.2 token map (7 entries, frozen DATA, applied in this order)
COURSE_TOKEN_MAP = (
    ("Computing", "Computer"), ("Magic", "Wizardry"),
    ("Spy", "SpySchool"), ("VeryHard", "Hard"),
    ("Grease", "Greaser"), ("CheeseAlien", "AlienCheese"),
    ("HumanityAlien", "Alien"),
)

# §S3.2 family definitions, priority order. matcher(key) decides membership;
# tail(key) extracts the matched tail (last path segment after suffix strip).
def _tail_after(prefixes, suffix):
    def tail(key):
        s = key
        for p in prefixes:
            if s.startswith(p):
                s = s[len(p):]
                break
        if suffix and s.endswith(suffix):
            s = s[: -len(suffix)]
        return s.rsplit("/", 1)[-1]
    return tail


def _tail_marketing():
    """Marketing/Courses[/Minor]/[Long_]<X>_Name — the [Long_] segment is
    optional decoration per the pinned family grammar (spec §S3.2), so the
    family tail is <X> with a leading `Long_` stripped; `Minor/` paths are
    already handled by the final-segment split."""
    inner = _tail_after(("Marketing/Courses/",), "_Name")

    def tail(key):
        s = inner(key)
        if s.startswith("Long_"):
            s = s[len("Long_"):]
        return s
    return tail


COURSE_FAMILIES = (
    ("qualification",
     lambda k: k.startswith("Characters/")
     and k.endswith("_Qualification_Name"),
     _tail_after((), "_Qualification_Name")),
    ("courses-courses",
     lambda k: k.startswith("Courses/Courses/") and k.endswith("_Name"),
     _tail_after(("Courses/Courses/",), "_Name")),
    ("courses-dlc",
     lambda k: re.match(r"^Courses/DLC_(Space|Ghost)/", k) is not None
     and k.endswith("_Name"),
     _tail_after((), "_Name")),
    ("marketing-courses",
     lambda k: k.startswith("Marketing/Courses/") and k.endswith("_Name"),
     _tail_marketing()),
    ("research-courses",
     lambda k: k.startswith("Research/Courses/") and k.endswith("_Name"),
     _tail_after(("Research/Courses/",), "_Name")),
)

COURSE_ID_PREFIXES = ("Marketing_Minor_Course_", "Marketing_Course_",
                      "Course_")

# §S4.1 frozen 13-entry analyzer assignment
ANALYZER_TOKENIZERS = {
    "whitespace": ("de", "en", "es", "fr", "it", "ko", "pl", "pt-BR",
                   "ru", "tr"),
    "cjk-bigram": ("zh-Hans", "zh-Hant"),
    "mixed": ("ja",),
}
ANALYZER_COMMON = {
    "lowercase": True,
    "stripMarkupTags": True,
    "stripPlaceholders": True,
    "stoplist": [],
    "asciiFolding": "none",
}

# Whitelist guard (F12): text indexing may never touch these structural
# containers — mesh/bone/material/path strings are defect content, and a
# candidate whose fieldPath crosses one trips `bonesIndexed`.
BLACKLISTED_SEGMENTS = ("Bones", "Meshes", "GeometryList", "Materials",
                        "TexturePaths", "BonePaths")

TAG_RE = re.compile(r"<[^>]+>")
PLACEHOLDER_RE = re.compile(r"\{[^{}]+\}")
WORD_RUN_RE = re.compile(r"\w+")
NON_ALNUM_RE = re.compile(r"[^A-Za-z0-9]+")


# ---------------------------------------------------------------------------
# Cleaning + token rules

def clean_text(text: str) -> str:
    """Strip `<[^>]+>` tags and `{PLACEHOLDER}` braces, then strip outer
    whitespace. Texts cleaning to empty are DROPPED by callers — never
    indexed as ""."""
    return TAG_RE.sub("", PLACEHOLDER_RE.sub("", str(text))).strip()


def id_tokens(entity_id: str, lowercase: bool = True) -> list[str]:
    """§S3.1 `id-token` rule: verbatim internal id split on non-alphanumeric
    runs, LOWERCASED (pinned rule — arbiter RF-A), length >= 2, pure digits
    dropped, deduped, sorted."""
    parts = [p for p in NON_ALNUM_RE.split(str(entity_id))
             if len(p) >= 2 and not p.isdigit()]
    if lowercase:
        parts = [p.lower() for p in parts]
    return sorted(set(parts))


def is_locstr(value) -> bool:
    """A LocalisedString struct: dict carrying the `_termID` sentinel."""
    return isinstance(value, dict) and "_termID" in value


def locstr_bears_text(struct: dict) -> bool:
    """Narrow-carrier text predicate: `_termID != 0`, or `_termID == 0`
    with non-empty `_dev` (spec §S1.1)."""
    if not is_locstr(struct):
        return False
    if (struct.get("_termID") or 0) != 0:
        return True
    return bool(struct.get("_dev") or "")


def locstr_dev_only_text(struct: dict) -> str:
    """The `_dev` English fallback when `_termID == 0` (dev-fallback basis /
    `dev-string` alias source), else ""."""
    if is_locstr(struct) and (struct.get("_termID") or 0) == 0:
        return str(struct.get("_dev") or "")
    return ""


def path_is_blacklisted(path: str) -> bool:
    segs = set(re.split(r"\.|\[\]", path))
    return any(b in segs for b in BLACKLISTED_SEGMENTS)


# ---------------------------------------------------------------------------
# Deep stub-field walker (components + whitelist guard census)

def walk_stub_fields(fields):
    """One deterministic pass over a stub row's `fields` payload.

    Returns a dict with:
      rootKeys        Counter keyed by the IMMEDIATE dict-key name holding
                      a LocalisedString struct, at ANY nesting depth
                      (presence basis — the arbiter RF-B reproduction of
                      552/730/193 counts key occurrences at any depth);
      capableKeys     same keying, counting only TEXT-CAPABLE structs
                      (`_termID != 0`, or `_termID == 0` with non-empty
                      `_dev`). Component COUNTS publish the presence basis;
                      expanded-union SEATS use capability (an empty struct
                      can never yield text, so it holds no seat and no
                      descriptionOnlyNoDoc entry);
      boneStrings     count of string leaves under a blacklisted segment
                      (F12 census — measured garbage mass, never indexed);
      blacklistHits   count of LocalisedString structs found UNDER a
                      blacklisted segment (would-be index candidates from
                      defect content — must stay 0 after caller filtering).
    """
    root_keys: Counter = Counter()
    capable_keys: Counter = Counter()
    bone_strings = 0
    blacklist_hits = 0

    def note(key: str, path: str, node: dict) -> None:
        nonlocal blacklist_hits
        root_keys[key] += 1
        if locstr_bears_text(node):
            capable_keys[key] += 1
        if path_is_blacklisted(path):
            blacklist_hits += 1

    stack = [("", "", fields)]  # (holdingKey, dottedPath, node)
    while stack:
        hold, path, node = stack.pop()
        if isinstance(node, dict):
            if is_locstr(node) and hold:
                note(hold, path, node)
                continue
            for key, val in node.items():
                npath = f"{path}.{key}" if path else str(key)
                if isinstance(val, dict) and is_locstr(val):
                    note(key, npath, val)
                elif isinstance(val, (dict, list)):
                    stack.append((key, npath, val))
                elif isinstance(val, str) and path_is_blacklisted(npath):
                    bone_strings += 1
        elif isinstance(node, list):
            for item in node:
                if isinstance(item, dict) and is_locstr(item) and hold:
                    note(hold, path, item)
                elif isinstance(item, (dict, list)):
                    stack.append((hold, path + "[]", item))
                elif isinstance(item, str) and path_is_blacklisted(path):
                    bone_strings += 1
    return {"rootKeys": root_keys, "capableKeys": capable_keys,
            "boneStrings": bone_strings,
            "blacklistHits": blacklist_hits}


# ---------------------------------------------------------------------------
# S1 — universe recipes

NARROW_TRAP_READING = (
    "reading `LocalisedName*` as the single field `LocalisedName` measures "
    "carriers 4282 / union 7172 — the pinned member-set expansion above is "
    "LOAD-BEARING (reviewer F3)")


def narrow_carrier(kind: str, fields: dict) -> bool:
    """§S1.1 pinned conservative carrier test for one stub row."""
    if kind == "campus-level":
        v = fields.get("Name")
        return isinstance(v, str) and bool(v)
    for path in sorted(NAME_CLASS_FIELDS[kind]):
        if locstr_bears_text(fields.get(path)):
            return True
    return False


def course_candidates(course_id: str) -> list[tuple[str, str]]:
    """§S3.2 union-set candidate construction, PINNED staging (reviewer
    F12): strip the Course_/Marketing_Course_/Marketing_Minor_Course_
    prefix; strip a trailing `_Long`; then generate ALL forms as ONE set
    {tail, tail±plural-s, LAST underscore segment, last±s}. Returns
    [(form, method-tag)] in evaluation order (direct > plural-fold >
    last-segment); deduped on form keeping the first method."""
    t = str(course_id)
    for p in COURSE_ID_PREFIXES:
        if t.startswith(p):
            t = t[len(p):]
            break
    if t.endswith("_Long"):
        t = t[: -len("_Long")]
    last = t.rsplit("_", 1)[-1]
    forms: list[tuple[str, str]] = []

    def add(form: str, method: str) -> None:
        if form and not any(f == form for f, _m in forms):
            forms.append((form, method))

    add(t, "family")
    if t.endswith("s"):
        add(t[:-1], "plural-fold")
    else:
        add(t + "s", "plural-fold")
    add(last, "last-segment")
    if last.endswith("s"):
        add(last[:-1], "plural-fold")
    else:
        add(last + "s", "plural-fold")
    return forms


def apply_token_map(forms: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Token-map rewrites (frozen DATA, applied in order) appended AFTER the
    plain forms: exact match first, then case-insensitive substring
    replacement across every occurrence."""
    out = list(forms)
    for src, dst in COURSE_TOKEN_MAP:
        for form, method in forms:
            if form == src:
                out.append((dst, "token-map"))
            elif src.casefold() in form.casefold():
                rewritten = re.sub(re.escape(src), dst, form,
                                   flags=re.IGNORECASE)
                out.append((rewritten, "token-map"))
    deduped: list[tuple[str, str]] = []
    for form, method in out:
        if not any(f == form for f, _m in deduped):
            deduped.append((form, method))
    return deduped


def build_course_family_index(locale_table: dict[str, str]) -> list[tuple]:
    """Family tail indexes over ONE locale's table (keys are
    locale-independent; resolution computes ONCE against en, but the index
    builder stays per-table so fixtures can prove clause-4 semantics)."""
    fams = []
    for name, matcher, tail_fn in COURSE_FAMILIES:
        tails: dict[str, str] = {}
        for key, text in locale_table.items():
            if matcher(key) and text:
                tails.setdefault(tail_fn(key).casefold(), key)
        fams.append((name, tails))
    return fams


def resolve_course(course_id: str, family_index, use_token_map: bool = True,
                   curated: dict | None = None):
    """First-hit-wins resolution: families in priority order; within a
    family, candidate forms in construction order (direct tail > plural
    fold > last segment > token map). Curated rows close the residue AFTER
    mechanics (spec §S3.2: they are authored for exactly the mechanical
    residue; validation of every row is the stage's job regardless).
    Returns {termKey, method, form?} or None."""
    forms = course_candidates(course_id)
    if use_token_map:
        forms = apply_token_map(forms)
    for fname, tails in family_index:
        for form, tag in forms:
            hit = tails.get(form.casefold())
            if hit is not None:
                method = {"family": f"family:{fname}",
                          "plural-fold": "plural-fold",
                          "last-segment": "last-segment",
                          "token-map": "token-map"}[tag]
                return {"termKey": hit, "method": method, "form": form}
    if curated and course_id in curated:
        row = curated[course_id]
        return {"termKey": str(row["termKey"]),
                "method": str(row.get("method") or "curated")}
    return None


# ---------------------------------------------------------------------------
# S4 — analyzer census (column definitions PINNED, reviewer F8)

def _is_cjk(ch: str) -> bool:
    o = ord(ch)
    return (0x4E00 <= o <= 0x9FFF          # Han
            or 0x3040 <= o <= 0x30FF       # Kana
            or 0xAC00 <= o <= 0xD7A3)      # Hangul (ko measures under THIS
    # Hangul-inclusive detector; a pure-Han detector would measure ~0)


def analyze_locale_table(table: dict[str, str]) -> dict:
    """Per-locale vocab census. Tokenization order GLOBAL: tokenize-then-
    lowercase (the tr 23,445 basis; lowercase-first gives 23,420)."""
    vocab: set[str] = set()
    counts: list[int] = []
    cjk_rows = 0
    no_ws_rows = 0
    tag_rows = 0
    ph_rows = 0
    for text in table.values():
        runs = WORD_RUN_RE.findall(text)
        counts.append(len(runs))
        vocab.update(r.lower() for r in runs)
        if any(_is_cjk(c) for c in text):
            cjk_rows += 1
        if not any(c.isspace() for c in text):
            no_ws_rows += 1
        if TAG_RE.search(text):
            tag_rows += 1
        if PLACEHOLDER_RE.search(text):
            ph_rows += 1
    rows = len(counts)
    avg = round(sum(counts) / rows, 2) if rows else 0.0
    med = median(counts) if rows else 0
    # Column names are the PINNED census vocabulary (reviewer F8: two
    # implementers must emit identical manifest.analyzers cells) — flat,
    # top-level, no nested dialect.
    return {
        "rows": rows,
        "vocab": len(vocab),
        "medianTokensPerRow": med,
        "avgTokensPerRow": avg,
        "cjkRows": cjk_rows,
        "noWhitespaceRows": no_ws_rows,
        "markupTagRows": tag_rows,
        "placeholderRows": ph_rows,
    }


def tokenizer_for(locale: str) -> str:
    for tok, locales in ANALYZER_TOKENIZERS.items():
        if locale in locales:
            return tok
    return "whitespace"


# ---------------------------------------------------------------------------
# S3.4 — collision counters

def collision_block(resolved_pairs, within_locale_dup_texts: dict) -> dict:
    """resolved_pairs: iterable of (srcKind, srcId, RAW pivot title) over
    the PINNED collision surface — narrow name-class edges plus consumed
    item-title join instances (arbiter RF-C basis; reconciles the seed
    block digit-for-digit on the real corpus: pairs 264 / x53 / x51 /
    ignoreKind 320).

      collidingPairs      (kind,title) PAIRS with multiplicity > 1;
      topPairs            highest-multiplicity pairs;
      ignoreKindCollisions TITLE TEXTS carried by more than one carrying
                          INSTANCE ignoring kind (instance multiplicity —
                          the reading that reproduces the pinned 320; the
                          distinct-KIND alternative is carried beside as
                          `distinctKindTexts`);
      withinLocaleDuplicateTexts  texts mapping to >1 KEY per full locale
                          table.
    """
    pair_counts: Counter = Counter()
    text_counts: Counter = Counter()
    kinds_by_text: dict[str, set] = {}
    for kind, sid, title in resolved_pairs:
        if not title:
            continue
        pair_counts[(kind, title)] += 1
        text_counts[title] += 1
        kinds_by_text.setdefault(title, set()).add(kind)
    colliding = {k: v for k, v in pair_counts.items() if v > 1}
    top = sorted(colliding.items(), key=lambda kv: (-kv[1], kv[0]))[:10]
    return {
        "collidingPairs": len(colliding),
        "topPairs": [{"kind": k, "title": t, "count": c}
                     for (k, t), c in top],
        "ignoreKindCollisions": sum(1 for v in text_counts.values() if v > 1),
        "distinctKindTexts": sum(1 for v in kinds_by_text.values()
                                 if len(v) > 1),
        "withinLocaleDuplicateTexts": dict(sorted(
            within_locale_dup_texts.items())),
    }


# ---------------------------------------------------------------------------
# Validators

DOC_TOP_KEYS = frozenset({"kind", "id", "slug", "visibility", "weight",
                          "name", "aliases", "descriptions", "icon",
                          "buildId"})
NAME_KEYS = frozenset({"text", "termKey", "basis"})
ICON_KEYS = frozenset({"subObjectName", "guid"})
BASIS_ENUM = frozenset({"localized", "mterm", "literal", "dev-fallback",
                        "convention", "curated"})
VISIBILITY_ENUM = frozenset({"public", "internal"})
ALIAS_CLASS_ENUM = frozenset({"id-token", "name-variant", "dev-string",
                              "convention", "curated"})


def validate_document(doc: dict) -> None:
    """Exact-key-set schema check (AC3): NO additional or missing keys;
    enums for basis/visibility/alias class; weight == kindWeights[kind]."""
    if set(doc) != DOC_TOP_KEYS:
        raise ValueError(
            f"document key set mismatch: {sorted(set(doc) ^ DOC_TOP_KEYS)}")
    if set(doc["name"]) != NAME_KEYS:
        raise ValueError("name key set mismatch")
    if doc["name"]["basis"] not in BASIS_ENUM:
        raise ValueError(f"bad basis {doc['name']['basis']!r}")
    if doc["visibility"] not in VISIBILITY_ENUM:
        raise ValueError(f"bad visibility {doc['visibility']!r}")
    if doc["slug"] is not None:
        raise ValueError("slug must stay null (F1: 100% null)")
    expected = KIND_WEIGHTS[doc["kind"]]
    if doc["weight"] != expected:
        raise ValueError(
            f"weight {doc['weight']!r} != kindWeights[{doc['kind']}] "
            f"{expected!r} (reviewer F6 derivation)")
    if set(doc["icon"]) != ICON_KEYS:
        raise ValueError("icon key set mismatch")
    prev = None
    for alias in doc["aliases"]:
        if set(alias) != {"text", "class"}:
            raise ValueError("alias key set mismatch")
        if alias["class"] not in ALIAS_CLASS_ENUM:
            raise ValueError(f"bad alias class {alias['class']!r}")
        cur = (alias["class"], alias["text"])
        if prev is not None and cur < prev:
            raise ValueError("aliases not sorted by (class,text)")
        prev = cur
    prev_k = None
    for d in doc["descriptions"]:
        if set(d) != {"text", "termKey"}:
            raise ValueError("description key set mismatch")
        cur = (d["termKey"] or "", d["text"])
        if prev_k is not None and cur < prev_k:
            raise ValueError("descriptions not sorted by (termKey,text)")
        prev_k = cur


def ratio_band_check(locale: str, docs: int, full_bytes: int,
                     titles_bytes: int) -> None:
    """AC4 gates as RATIO bands over each shard's own denominators:
    titles 60·D ≤ B ≤ 120·D ; full 380·D ≤ B ≤ 650·D."""
    if docs <= 0:
        return
    if not (60 * docs <= titles_bytes <= 120 * docs):
        raise ValueError(
            f"titles projection band breach for {locale}: {titles_bytes}B "
            f"outside [{60 * docs}, {120 * docs}] at D={docs}")
    if not (380 * docs <= full_bytes <= 650 * docs):
        raise ValueError(
            f"full shard band breach for {locale}: {full_bytes}B outside "
            f"[{380 * docs}, {650 * docs}] at D={docs}")


def serialize_doc(doc: dict) -> str:
    """Compact separators + sorted keys + UTF-8/LF JSONL row."""
    import json
    return json.dumps(doc, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))


def serialize_title_row(doc: dict) -> str:
    import json
    row = {"kind": doc["kind"], "id": doc["id"], "t": doc["name"]["text"]}
    return json.dumps(row, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))
