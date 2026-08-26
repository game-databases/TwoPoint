"""Piece-08 blind TestWriter suite — stage 12 ``search-corpus``.

Written against docs/specs/piece-08-search-corpus.mdx (**Revision 3**) +
docs/rulings/arbiter-piece08-spec.mdx ALONE (§9 TestWriter contract);
tools/stage12_search_corpus.py and tools/search_util.py were never read.
Primary surface is black-box (``run_all.py <tree> --only search-corpus``
over synthetic prepared trees, conftest.run_pack) plus client-gated
exact-figure legs over the committed corpus. Expected RED against
not-yet-landed code — including the unregistered-stage rc 3 — is the
blind-pair interface; skips stay reserved for environment gating.

The stage is PURELY DERIVED (opens no bundles, needs no game dir): every
leg here is hostless except the explicitly marked client-gated ones,
which copy the committed corpus's upstream set into a D:/scratch root.

Fixture corpora come from tests/_searchlib.py (hand-computed mini roster:
de/en/ja/ko/zh-Hans core inside a 13-table layout, 9 populated kinds —
see its docstring for the derived census). Small trees ride pytest's
tmp_path_factory (default %TEMP% basetemp); the real-corpus scratch lives
under D:/tpc_pytmp/tw08/ (never a C:-rooted custom basetemp).

Blocks:
  A registration/entrypoint (AC1)       B upstream gate + exit-3 family
  C universe dual floors (AC2)          D document shards (AC3/AC4)
  E alias layer (AC5)                   F course resolution ladder
  G analyzers + census (AC6)            H manifest/hashes/ledger (AC9)
  I determinism (AC7)                   J exit-2 discrimination (AC8)
  K suite-side mutation teeth           N client-gated exact figures
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _impl  # noqa: E402
import _searchlib as sl  # noqa: E402
from _validators import (  # noqa: E402
    BUILD_ID, LOCALE_TABLE, read_json, read_jsonl,
    scan_tree_for_media_extensions, write_jsonl,
)

PACK_ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
PINNED_13 = set(LOCALE_TABLE.values())
STAGE_ID = "search-corpus"

# §5 output contract: EVERYTHING the stage writes lives under search/
# (+ the runner-owned log/stamps/meta trio). Nothing else.
ALLOWED_WRITES = ("search/", "EXTRACTION-LOG.md", ".stage-stamps",
                  ".pipeline-meta.json")

LEDGER_CODES = {
    "item-title-joins-absent", "course-name-open", "alias-input-absent",
    "dev-only-names", "mt-unresolved", "campus-level-scope",
}
DOC_KEYS = {"kind", "id", "slug", "visibility", "weight", "name",
            "aliases", "descriptions", "icon", "buildId"}
NAME_KEYS = {"text", "termKey", "basis"}
BASIS_ENUM = {"localized", "mterm", "literal", "dev-fallback",
              "convention", "curated"}
VISIBILITY_ENUM = {"public", "internal"}
ALIAS_CLASS_ENUM = {"id-token", "name-variant", "dev-string",
                    "convention", "curated"}
TITLES_KEYS = {"kind", "id", "t"}

# Hand-pinned fixture census (see _searchlib docstring for derivations).
PIN_NARROW = 41
PIN_TRAP = 37
PIN_EXPANDED_ALIASED = 56
PIN_EXPANDED_ABSENT = 54
PIN_IDONLY_ALIASED = 11
PIN_DESC_ONLY = {"config": 6, "item": 1, "room": 1}
PIN_DOCS = {"de": 28, "en": 46, "es": 7, "fr": 7, "it": 7, "ja": 8,
            "ko": 8, "pl": 7, "pt-BR": 7, "ru": 7, "tr": 7,
            "zh-Hans": 7, "zh-Hant": 7}
# RECONCILIATION RULING (interface round): the collision surface is the
# arbiter RF-C reproduction — narrow name-class edges + consumed join
# instances over RAW pivot texts (strip-empty only; texts that clean to
# empty still collide as raw strings — the basis that reproduces the real
# seeds 264/320 digit-for-digit; a cleaned or docs-surface reading
# measures 319/284 there). Under it the fixture measures FOUR colliding
# pairs / FIVE ignore-kind texts: the planted "{BLADE}" title carried by
# Item_Sword_Lite (edge) and Item_Sword_Full (join instance) IS a raw
# many-to-many truth.
PIN_COLLISION_PAIRS = 4
PIN_TOP_PAIRS = [(("config", "Lab Work"), 5),
                 (("config", "Specialist Book Report"), 4)]
PIN_IGNORE_KIND = 5
PIN_DUP_TEXTS = {"de": 2, "en": 3, "ja": 0, "ko": 2, "zh-Hans": 2}
PIN_TITLE_EDGES = 22
PIN_TITLE_KEYS = 15
PIN_TOKENS = 105
PIN_TOKEN_SUPERSET = 106
PIN_CASE_FOLD = 1
PIN_DEV_STRINGS = 7


# --- harness -----------------------------------------------------------------

def make_tree(tmp_path_factory, name: str) -> Path:
    """Leg-private prepared tree (fresh, mutable)."""
    out = tmp_path_factory.mktemp(name)
    from build_fixture_tree import check_source_root
    check_source_root(out)
    import _fixturelib as fx
    if STAGE_ID in getattr(fx, "STAGE_ARTIFACTS", ()):
        fx.build_tree(out, STAGE_ID)
    else:  # registration lost/raced — build the upstream set directly
        game_root = out / "steamapps" / "common" / "Two Point Campus"
        game_root.mkdir(parents=True, exist_ok=True)
        sl.build_search_upstream(out / "extracted")
    return out


def run12(tree: Path, ext: Path, *extra, timeout=600):
    from conftest import run_pack, tree_game
    Path(ext).mkdir(parents=True, exist_ok=True)
    return run_pack([tree_game(tree), "--only", STAGE_ID, *extra],
                    extracted_root=ext, timeout=timeout)


def search_dir(ext: Path) -> Path:
    return Path(ext) / sl.SEARCH_DIR


def require_completed(r, what="search-corpus run"):
    """Hostless stage must complete 0 or 2. Anything else is a LOUD
    failure — including the unregistered-stage rc 3 this suite expects
    while the CodeWriter lane is pending (blind-pair RED)."""
    assert r.returncode in (0, 2), (
        f"{what} did not complete: rc={r.returncode}\n"
        f"STDOUT:{r.stdout[-2000:]}\nSTDERR:{r.stderr[-2000:]}")


def load_json(ext: Path, rel: str):
    p = Path(ext) / rel
    assert p.is_file(), f"missing emitted artifact {rel}"
    return read_json(p)


def load_jsonl(ext: Path, rel: str):
    p = Path(ext) / rel
    assert p.is_file(), f"missing emitted artifact {rel}"
    return read_jsonl(p)


def last_run_section(ext: Path, stage_id: str = STAGE_ID) -> str:
    log_text = (Path(ext) / "EXTRACTION-LOG.md").read_text(
        encoding="utf-8", errors="replace")
    sections = [p for p in re.split(r"(?m)^#{1,3} ", log_text)
                if p.splitlines()[:1]
                and stage_id in p.splitlines()[0].lower()]
    assert sections, f"no {stage_id} run section in EXTRACTION-LOG.md"
    return sections[-1]


def regression_lines(text: str):
    """Containment match: console lines carry runner prefixes like
    "[search-corpus]" / "- PROBLEM:" before the verdict token."""
    out = []
    for ln in text.splitlines():
        u = ln.upper()
        if "RELINK-REGRESSION" in u or u.strip().startswith("REGRESSION"):
            out.append(ln)
    return out


def hash_entries(ext: Path) -> dict:
    """hashes.json reader: flat relpath->sha256 OR the envelope dialect
    ({algorithm, buildId, excluded, files{...}}); paths normalized to
    search-dir-relative."""
    raw = load_json(ext, f"{sl.SEARCH_DIR}/hashes.json")
    files = raw.get("files", raw) if isinstance(raw, dict) else raw
    out = {}
    for rel, digest in files.items():
        norm = rel[len(sl.SEARCH_DIR) + 1:] if rel.startswith(
            sl.SEARCH_DIR + "/") else rel
        out[norm] = digest
    return out


def astat(cell: dict, *names):
    """Analyzer stat reader: top-level OR nested under stats, with the
    spec-vocabulary and measured-dialect spellings."""
    scopes = [cell] + ([cell["stats"]] if isinstance(cell.get("stats"),
                                                     dict) else [])
    for scope in scopes:
        for n in names:
            if isinstance(scope, dict) and n in scope:
                return scope[n]
    return None


def narrow_per_kind(uni: dict) -> dict:
    for k in ("narrowPerKind", "perKind", "narrowByKind"):
        if isinstance(uni.get(k), dict):
            return uni[k]
    return {}


def comp_value(comp, *paths):
    """Tolerant component finder: each path is a tuple of candidate keys
    walked left to right; returns the first hit."""
    for path in paths:
        cur = comp
        ok = True
        for key in path:
            if isinstance(cur, dict) and key in cur:
                cur = cur[key]
            else:
                ok = False
                break
        if ok and not isinstance(cur, dict):
            return cur
    return None


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def snapshot_search(ext: Path) -> dict:
    root = search_dir(ext)
    if not root.exists():
        return {}
    return {p.relative_to(root).as_posix(): sha256_bytes(p.read_bytes())
            for p in sorted(root.rglob("*")) if p.is_file()}


def snapshot_readonly(ext: Path) -> dict:
    """Everything OUTSIDE the stage's allowed write set."""
    ext = Path(ext)
    out = {}
    for p in sorted(ext.rglob("*")):
        if p.is_dir():
            continue
        rel = p.relative_to(ext).as_posix()
        if any(rel == a.rstrip("/") or rel.startswith(a)
               for a in ALLOWED_WRITES):
            continue
        out[rel] = sha256_bytes(p.read_bytes())
    return out


def bump_buildid_everywhere(ext: Path, old=BUILD_ID, new=BUILD_ID + 1):
    for p in sorted(Path(ext).rglob("*")):
        if p.is_file():
            b = p.read_bytes()
            if str(old).encode() in b:
                p.write_bytes(b.replace(str(old).encode(), str(new).encode()))


def shard_lines(ext: Path, loc: str):
    return load_jsonl(ext, f"{sl.SEARCH_DIR}/shards/{loc}.jsonl")


def titles_lines(ext: Path, loc: str):
    return load_jsonl(ext, f"{sl.SEARCH_DIR}/titles/{loc}.jsonl")


@pytest.fixture(scope="module")
def aliased_run(tmp_path_factory):
    """One completed hostless run WITH the curated alias input present
    (the §9 'seed table landed' input state)."""
    tree = make_tree(tmp_path_factory, "tw08_aliased")
    ext = tree / "extracted"
    with sl.alias_input(PACK_ROOT, ext):
        r = run12(tree, ext)
    return r, ext, tree


@pytest.fixture(scope="module")
def degraded_run(tmp_path_factory):
    """One completed hostless run WITHOUT the optional alias input."""
    tree = make_tree(tmp_path_factory, "tw08_absent")
    ext = tree / "extracted"
    r = run12(tree, ext)
    return r, ext, tree


# ============================================================================
# A — registration / entrypoint (AC1: registry-aware, NO absolute count)
# ============================================================================

CANONICALLY_EARLIER = ("verify-client", "decompile", "harvest-catalog",
                       "harvest-bundles", "localisation",
                       "emit-stub-datasets", "relink", "locale-proof",
                       "logic", "contracts", "check-contracts", "maps",
                       "media")


def test_A_registry_entry_script_and_canonical_order():
    mod = _impl.load_tool("tpc_common.py")
    assert mod is not None, "impl-missing: tools/tpc_common.py"
    stages = list(getattr(mod, "STAGES", []))
    ids = [sid for sid, _s, _d in stages]
    assert STAGE_ID in ids, (
        f"registry-aware AC1: '{STAGE_ID}' not registered in "
        f"tpc_common.STAGES (ids={ids})")
    entry = next(e for e in stages if e[0] == STAGE_ID)
    _sid, script_rel, deps = entry
    assert script_rel.replace("\\", "/") == sl.SCRIPT_REL, (
        f"script must be {sl.SCRIPT_REL}, got {script_rel}")
    assert list(deps) == sl.SCRIPT_DEPS, (
        f"script-hash deps pinned {sl.SCRIPT_DEPS}, got {deps}")
    # ordering authority is the CANONICAL index (12), never append position:
    # after every canonically-earlier stage THAT IS REGISTERED, and LAST
    # among today's set (AC1 conditional wording — never a global count).
    for earlier in CANONICALLY_EARLIER:
        if earlier in ids:
            assert ids.index(STAGE_ID) > ids.index(earlier), (
                f"canonical order violated: {STAGE_ID} must follow "
                f"{earlier} (registry sentence relink=6 · maps=7 · logic=8 "
                f"· locale-proof=9 · contracts=10 · media=11 · "
                f"search-corpus=12)")
    assert ids[-1] == STAGE_ID, (
        f"AC1: search-corpus is LAST among today's stage set, got {ids}")


def test_A_list_shows_order_and_script(tmp_path_factory):
    from conftest import run_pack, seeded_extracted_root
    tree = make_tree(tmp_path_factory, "tw08_list")
    ext = seeded_extracted_root(tree, tmp_path_factory.mktemp("tw08_list_e"))
    r = run_pack(["--list"], extracted_root=ext)
    assert r.returncode == 0, f"--list failed rc={r.returncode}: {r.stderr}"
    rows, order_line = {}, ""
    for ln in r.stdout.splitlines():
        m = re.match(r"^(\S+)\s{2,}(\S+)\s{2,}", ln)
        if m:
            rows[m.group(1)] = m.group(2)
        if ln.startswith("order:"):
            order_line = ln
    assert rows.get(STAGE_ID) == sl.SCRIPT_REL, (
        f"--list must show {STAGE_ID} -> {sl.SCRIPT_REL}; got {rows}")
    listed = order_line.split("order:", 1)[-1].split()
    if listed:
        assert listed[-1] == STAGE_ID or STAGE_ID not in listed, (
            f"listed order must end with today's last stage "
            f"search-corpus: {listed}")


def test_A_only_isolation_on_fixture_tree(tmp_path_factory):
    """AC1: `--only search-corpus` runs in isolation on a prepared tree."""
    tree = make_tree(tmp_path_factory, "tw08_iso")
    ext = tree / "extracted"
    with sl.alias_input(PACK_ROOT, ext):
        r = run12(tree, ext)
    require_completed(r)
    assert search_dir(ext).is_dir(), \
        "isolation run produced no extracted/search/ directory"


def test_A_builder_cli_materializes_upstream_set(tmp_path_factory):
    """AC1 hostless smoke: `tests/build_fixture_tree.py --stage
    search-corpus` materializes §4's upstream set — mini stubs + relink
    JSONLs + 13 locale tables + stamps; NO Unity bytes."""
    out = tmp_path_factory.mktemp("tw08_cli")
    r = subprocess.run(
        [sys.executable, str(HERE / "build_fixture_tree.py"),
         "--stage", STAGE_ID, "--out", str(out)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(PACK_ROOT), timeout=300)
    assert r.returncode == 0, (
        f"builder CLI failed rc={r.returncode}: {r.stdout}{r.stderr}")
    ext = out / "extracted"
    for rel in ("identity.json", "stubs/items.jsonl",
                "stubs/configs.jsonl", "relinks/entity_locale.jsonl",
                "relinks/i2_term_registry.jsonl",
                "relinks/matrix.json", "locales/en.jsonl",
                "locales/pt-BR.jsonl", "locales/locale-matrix.json",
                ".stage-stamps/relink.json",
                ".stage-stamps/localisation.json"):
        assert (ext / rel).is_file(), f"builder CLI missed upstream {rel}"
    # NO real Unity bytes anywhere (the cumulative base carries tiny
    # SYNTHETIC .bundle name-fakes like every sibling tree; anything
    # larger than a filler would mean real corpus bytes rode along)
    for p in out.rglob("*"):
        if p.is_file() and p.stat().st_size > 256 * 1024:
            raise AssertionError(
                f"oversized file in fixture tree (real bytes?): {p}")


def test_A_make_list_equivalent():
    make = shutil.which("make")
    if not make:
        pytest.skip("environment: no make binary on PATH")
    try:
        r = subprocess.run([make, "list"], cwd=str(PACK_ROOT),
                           capture_output=True, text=True, timeout=600,
                           encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        pytest.skip("environment: make list timed out (real-corpus hashing)")
    if r.returncode != 0:
        pytest.skip(f"environment: make list failed rc={r.returncode}")
    assert STAGE_ID in r.stdout, "`make list` must enumerate search-corpus"


# ============================================================================
# B — upstream gate + exit-3 family (§4 Inputs / §S5.3 existence class)
# ============================================================================

def test_B_missing_required_input_exits3_naming_it(tmp_path_factory):
    tree = make_tree(tmp_path_factory, "tw08_b1")
    ext = tree / "extracted"
    (ext / "relinks" / "entity_locale.jsonl").unlink()
    r = run12(tree, ext)
    assert r.returncode == 3, (
        f"ANY missing required input => exit 3 naming it; got "
        f"rc={r.returncode}\n{r.stdout[-800:]}{r.stderr[-800:]}")
    combined = r.stdout + r.stderr
    assert "entity_locale.jsonl" in combined, (
        f"exit-3 output must NAME the missing input file: {combined[-600:]}")


def test_B_relink_stamp_exitCode_not_in_0_2_exits3(tmp_path_factory):
    tree = make_tree(tmp_path_factory, "tw08_b2")
    ext = tree / "extracted"
    stamp = read_json(ext / ".stage-stamps" / "relink.json")
    stamp["exitCode"] = 3
    write_json = lambda p, o: p.write_text(
        json.dumps(o, indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n")
    write_json(ext / ".stage-stamps" / "relink.json", stamp)
    r = run12(tree, ext)
    combined = r.stdout + r.stderr
    assert r.returncode == 3, (
        f"relink.exitCode=3 (∉ {{0,2}}) must refuse exit 3, got "
        f"{r.returncode}\n{combined[-700:]}")
    assert "relink.json" in combined, (
        f"exit-3 must name the offending stamp artifact: {combined[-500:]}")
    # exit 2 is relink's DECLARED steady state — never a refusal reason
    tree_ok = make_tree(tmp_path_factory, "tw08_b2ok")
    r2 = run12(tree_ok, tree_ok / "extracted")
    assert r2.returncode != 3, (
        "relink.exitCode=2 (steady state) must NOT be a refusal reason")


def test_B_localisation_stamp_exitCode_1_exits3(tmp_path_factory):
    tree = make_tree(tmp_path_factory, "tw08_b3")
    ext = tree / "extracted"
    stamp = read_json(ext / ".stage-stamps" / "localisation.json")
    stamp["exitCode"] = 1
    (ext / ".stage-stamps" / "localisation.json").write_text(
        json.dumps(stamp, indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n")
    r = run12(tree, ext)
    combined = r.stdout + r.stderr
    assert r.returncode == 3, (
        f"localisation.exitCode != 0 must refuse exit 3, got "
        f"{r.returncode}\n{combined[-700:]}")
    assert "localisation.json" in combined, combined[-500:]


def test_B_missing_relink_stamp_exits3(tmp_path_factory):
    tree = make_tree(tmp_path_factory, "tw08_b4")
    ext = tree / "extracted"
    (ext / ".stage-stamps" / "relink.json").unlink()
    r = run12(tree, ext)
    assert r.returncode == 3, (
        f"absent relink stamp => exit 3, got {r.returncode}\n"
        f"{r.stdout[-600:]}{r.stderr[-600:]}")


def test_B_no_partial_writes_before_gate(tmp_path_factory):
    tree = make_tree(tmp_path_factory, "tw08_b5")
    ext = tree / "extracted"
    (ext / "relinks" / "matrix.json").unlink()
    r = run12(tree, ext)
    assert r.returncode == 3, f"expected gate refusal 3, got {r.returncode}"
    assert not search_dir(ext).exists() or not any(search_dir(ext).iterdir()), \
        "stage wrote search outputs before the upstream pre-check passed"


# ============================================================================
# C — universe dual floors (AC2) — narrow/trap/expanded/components
# ============================================================================

def test_C_narrow_union_exact_with_per_kind(aliased_run):
    """§S1.1 pinned recipe: universeNarrow == hand value 41 under the
    EXPANDED member sets; the single-field misreading measures 37 — a
    naive implementation trips this assert day one (reviewer F3 trap)."""
    r, ext, _tree = aliased_run
    require_completed(r)
    uni = load_json(ext, f"{sl.SEARCH_DIR}/manifest.json")["universe"]
    assert uni["narrow"] == PIN_NARROW, (
        f"universeNarrow {uni.get('narrow')} != {PIN_NARROW} (a "
        f"single-field LocalisedName misreading measures {PIN_TRAP})")
    orc = sl.SearchOracle(aliased=True)
    per_kind = narrow_per_kind(uni)
    oracle_per_kind = Counter(k for k, _i in orc.narrow_union())
    assert {k: v for k, v in per_kind.items() if v} == dict(oracle_per_kind), (
        f"per-kind narrow decomposition {per_kind} != oracle "
        f"{dict(oracle_per_kind)}")
    section = last_run_section(ext)
    assert re.search(r"universeNarrow\s*=\s*41\b", section), section[-800:]
    assert re.search(r"stubRows\s*=\s*67\b", section), section[-800:]


def test_C_trap_reading_discriminates_suite_side():
    """Mutation-teeth proof that the fixture DISCRIMINATES the warned
    single-field misreading: delta == exactly the four dev-only F/M
    carriers outside A (suite-side arithmetic, runnable now)."""
    orc = sl.SearchOracle(aliased=True)
    narrow, trap = orc.narrow_union(), orc.trap_reading()
    assert len(narrow) == PIN_NARROW and len(trap) == PIN_TRAP
    delta = narrow - trap
    assert {(k, i) for k, i in delta} == {
        ("item", "Item_Sorcerer_Forms"), ("item", "Item_Amazoness_Form"),
        ("unlockable", "Unlock_Female_Development"),
        ("student-type", "Student_Type_Developer"),
    }, f"trap delta must be exactly the dev-only F/M carriers: {delta}"


def test_C_expanded_dual_floor_and_idOnly_law(aliased_run, tmp_path_factory):
    r, ext, _tree = aliased_run
    require_completed(r)
    man = load_json(ext, f"{sl.SEARCH_DIR}/manifest.json")
    uni = man["universe"]
    assert uni["expanded"] == PIN_EXPANDED_ALIASED, (
        f"expanded {uni.get('expanded')} != {PIN_EXPANDED_ALIASED}")
    assert uni["idOnly"] == uni["totalRows"] - uni["expanded"], (
        "idOnly == totalRows − expanded broken")
    assert uni["idOnly"] == PIN_IDONLY_ALIASED
    pf = uni["planningFloor"]
    assert pf["value"] == 10200 and pf["share"] == "75.9%", pf
    section = last_run_section(ext)
    assert "DRIFT:" in section and "10200" in section, (
        f"planning-floor DRIFT line must print IFF expanded != 10200 "
        f"(fixture expanded={uni['expanded']}):\n{section[-900:]}")
    assert re.search(r"idOnlyRemainder\s*=\s*11\b", section), section[-800:]


def test_C_ac2_identity_law_artifact_derived(aliased_run):
    """AC2: descriptionOnlyNoDoc reconciles —
    expanded == distinctDocs(across all 13 shards) + ΣdescriptionOnlyNoDoc.
    Both sides derived FROM THE ARTIFACTS, so the law binds whatever the
    emitter books into the residual bucket."""
    r, ext, _tree = aliased_run
    require_completed(r)
    man = load_json(ext, f"{sl.SEARCH_DIR}/manifest.json")
    uni = man["universe"]
    distinct = set()
    for loc in sl.ALL_LOCALES:
        for doc in shard_lines(ext, loc):
            distinct.add((doc["kind"], doc["id"]))
    don = uni.get("descriptionOnlyNoDoc") or {}
    total_don = sum(don.values()) if isinstance(don, dict) else don
    assert uni["expanded"] == len(distinct) + total_don, (
        f"AC2 identity law broken: expanded {uni['expanded']} != "
        f"distinctDocs {len(distinct)} + descriptionOnlyNoDoc {total_don}")
    assert don == PIN_DESC_ONLY, (
        f"descriptionOnlyNoDoc per kind {don} != hand pins {PIN_DESC_ONLY}")


def test_C_expanded_components_on_pinned_bases(aliased_run):
    """RF-B: every equality-asserted component ON ITS PINNED BASIS;
    titleCarrierInstances rides as DRIFT-tracked DATA beside them."""
    r, ext, _tree = aliased_run
    require_completed(r)
    comp = load_json(ext, f"{sl.SEARCH_DIR}/manifest.json")[
        "universe"].get("components") or {}
    blob = json.dumps(comp)

    def find_int(*names):
        for n in names:
            v = comp.get(n)
            if isinstance(v, int):
                return v
        return None

    plain = comp.get("plainStringNames") or comp.get("plainNameLiterals")
    if isinstance(plain, dict):
        assert plain == {"config": 1, "unlockable": 1, "campus-level": 5}, \
            f"plain-literal decomposition drifted: {plain}"
    assert find_int("configLocalisedNamePresenceInstances",
                    "configLocalisedNamePresence") == 1, blob[:400]
    scoped = comp_value(comp, ("configDisplayName", "landscapeBrushScoped"),
                        ("configDisplayNameScoped",),
                        ("displayNameScopedInstances",))
    assert scoped == 2, f"LandscapeBrush-scoped DisplayName must be 2: {blob[:400]}"
    room = comp.get("roomNameLocstr") or comp.get("roomNameRows") or {}
    if isinstance(room, dict):
        assert room.get("presence") == 2 and room.get("textBearing") == 1, room
    mterm_rows = comp_value(comp, ("unlockableMTerm", "rows"),
                            ("unlockableMTermRows",), ("mTermRows",))
    mterm_res = comp_value(comp, ("unlockableMTerm", "resolvingInEn"),
                           ("unlockableMTermResolved",), ("mTermResolved",))
    assert mterm_rows == 3 and mterm_res == 1, blob[:400]
    assert find_int("unlockableDescriptiveNameNonEmpty",
                    "unlockableDescriptiveName", "descriptiveName") == 1
    # titleCarrierInstances: PRESENT, integer, and its movement between
    # trees never flips the verdict (see the dedicated -extra leg below).
    tci = find_int("titleCarrierInstances")
    assert isinstance(tci, int) and tci >= 0, (
        "titleCarrierInstances must be emitted as DRIFT-tracked data")


def test_C_titleCarrier_instances_move_without_verdict_flip(
        tmp_path_factory):
    """RF-B teeth: +2 Title carrier structs -> the reported figure moves
    2->4 while the run STILL completes (data, never an equality gate)."""
    def count_titles(ext):
        return sum(
            1 for row in read_jsonl(ext / "stubs" / "configs.jsonl")
            if "Title" in row.get("fields", {}))

    results = []
    for tag, add in (("tw08_tci_base", False), ("tw08_tci_extra", True)):
        tree = make_tree(tmp_path_factory, tag)
        ext = tree / "extracted"
        if add:
            stubs = read_jsonl(ext / "stubs" / "configs.jsonl")
            new_key_a = "Configs/Titles/Injected_Title_A"
            new_key_b = "Configs/Titles/Injected_Title_B"
            for i, key in enumerate((new_key_a, new_key_b)):
                tid = sl.TERM_IDS["Configs/Titles/Honorary_Title"] - 50 - i
                stubs.append({
                    "buildId": BUILD_ID, "id": f"Config_Title_Inject_{i}",
                    "kind": "config", "slug": None, "provisional": True,
                    "inferred": False, "method": "verbatim-copy",
                    "fields": {"Title": sl._ls(tid, "")},
                    "source": {"bundle": "fixtures.bundle",
                               "class": "TPC.CareerGoalDefinition",
                               "pathId": -777000 - i}})
            write_jsonl(ext / "stubs" / "configs.jsonl", stubs)
            edges = read_jsonl(ext / "relinks" / "entity_locale.jsonl")
            for i, key in enumerate((new_key_a, new_key_b)):
                tid = sl.TERM_IDS["Configs/Titles/Honorary_Title"] - 50 - i
                edges.append({
                    "buildId": BUILD_ID, "dstId": key,
                    "dstKind": "locale-term",
                    "evidence": {"dev": "", "fieldPath": "Title",
                                 "locales": [], "termId": tid},
                    "inferred": False, "mechanism": "hard",
                    "method": "i2-termid-registry",
                    "srcId": f"Config_Title_Inject_{i}", "srcKind": "config"})
            edges.sort(key=lambda e: (e["srcKind"], e["srcId"],
                                      e["evidence"]["fieldPath"]))
            write_jsonl(ext / "relinks" / "entity_locale.jsonl", edges)
            reg = read_jsonl(ext / "relinks" / "i2_term_registry.jsonl")
            for i, key in enumerate((new_key_a, new_key_b)):
                reg.append({"buildId": BUILD_ID, "canonical": True,
                            "locales": [], "sourceAsset": "I2LS_Fixture",
                            "termId":
                                sl.TERM_IDS["Configs/Titles/Honorary_Title"]
                                - 50 - i,
                            "termKey": key, "termStatus": 1, "termType": 0})
            reg.sort(key=lambda x: x["termKey"])
            write_jsonl(ext / "relinks" / "i2_term_registry.jsonl", reg)
            # keep the consumed stamp honest: refresh its output hashes
            sl.write_stamps(ext)
        with sl.alias_input(PACK_ROOT, ext):
            r = run12(tree, ext, "--force")
        require_completed(r, f"titleCarrier tree ({tag})")
        comp = load_json(ext, f"{sl.SEARCH_DIR}/manifest.json")[
            "universe"].get("components") or {}
        tci = next((comp[k] for k in comp if k == "titleCarrierInstances"
                    and isinstance(comp[k], int)), None)
        results.append((count_titles(ext), tci))
    assert results[0][1] == 2 and results[1][1] == 4, (
        f"titleCarrierInstances must track the struct count as data: "
        f"{results}")
    assert results[0][0] == 2 and results[1][0] == 4


def test_C_whitelist_guard_bones_never_indexed(aliased_run):
    """§S1.5: mesh/bone strings are defects, not content — bonesIndexed==0
    and the planted bone/material strings appear nowhere in search/."""
    r, ext, _tree = aliased_run
    require_completed(r)
    section = last_run_section(ext)
    assert re.search(r"bonesIndexed\s*=\s*0\b", section), section[-800:]
    banned = ("bone_alpha", "bone_beta", "mat_floor", "GeometryList")
    for p in search_dir(ext).rglob("*"):
        if p.is_file():
            text = p.read_text(encoding="utf-8", errors="replace")
            for b in banned:
                assert b not in text, f"{b} leaked into {p.name}"
    exc = load_json(ext, f"{sl.SEARCH_DIR}/manifest.json").get("excluded") or {}
    assert exc.get("bonesIndexed") == 0, exc
    sprites = exc.get("spriteNameCarriers")
    assert isinstance(sprites, int) and sprites >= 1, (
        f"excluded.spriteNameCarriers must be measured (>0 here): {exc}")
    # sprite names are NOT aliases
    for doc in shard_lines(ext, "en"):
        for alias in doc.get("aliases", []):
            assert "UI_InGame" not in alias.get("text", ""), doc


def test_C_ui_chrome_identity(aliased_run):
    r, ext, _tree = aliased_run
    require_completed(r)
    exc = load_json(ext, f"{sl.SEARCH_DIR}/manifest.json")["excluded"]
    assert exc["uiChromeTerms"] == len(sl.KEY_TEXTS) - 26, exc


# ============================================================================
# D — document shards (AC3 schema/purity + AC4 ratio bands)
# ============================================================================

def test_D_shard_file_set_character_exact(aliased_run):
    r, ext, _tree = aliased_run
    require_completed(r)
    for plane, n in (("shards", 13), ("titles", 13)):
        d = search_dir(ext) / plane
        files = sorted(p.name for p in d.glob("*.jsonl"))
        assert files == sorted(f"{loc}.jsonl" for loc in sl.ALL_LOCALES), (
            f"{plane} file set not the 13 route-coded BCP-47 tags: {files}")
    section = last_run_section(ext)
    assert re.search(r"shardFiles\s*=\s*26\b", section), section[-800:]


def test_D_doc_schema_exact_keys_and_enums(aliased_run):
    r, ext, _tree = aliased_run
    require_completed(r)
    seen_kinds = set()
    for loc in sl.ALL_LOCALES:
        prev = None
        for doc in shard_lines(ext, loc):
            assert set(doc) == DOC_KEYS, (
                f"frozen row shape violated ({sorted(set(doc) ^ DOC_KEYS)}): "
                f"{doc}")
            assert doc["slug"] is None, f"F1: slug stays null: {doc}"
            assert doc["buildId"] == BUILD_ID
            assert doc["visibility"] in VISIBILITY_ENUM
            assert doc["weight"] == sl.KIND_WEIGHTS[doc["kind"]], (
                f"F6: weight must equal kindWeights[{doc['kind']}] "
                f"({sl.KIND_WEIGHTS[doc['kind']]}), got {doc['weight']}")
            nm = doc["name"]
            assert set(nm) == NAME_KEYS and nm["basis"] in BASIS_ENUM, nm
            assert isinstance(nm["text"], str) and nm["text"].strip(), (
                "cleaned-to-empty titles are dropped, never indexed")
            seen_kinds.add(doc["kind"])
            key = (doc["kind"], doc["id"])
            assert prev is None or prev < key, (
                f"shard {loc} not sorted by (kind,id) at {key}")
            prev = key
            classes = [a["class"] for a in doc["aliases"]]
            assert all(c in ALIAS_CLASS_ENUM for c in classes), doc
            ali = [(a["class"], a["text"]) for a in doc["aliases"]]
            assert ali == sorted(ali), f"aliases not sorted by (class,text)"
    assert seen_kinds == set(sl.KIND_WEIGHTS), seen_kinds


def test_D_per_locale_doc_counts_and_purity(aliased_run):
    """Membership == oracle derivation per locale (clause 1-4 semantics,
    unresolved-in-L miss, pivot-only literals/dev). localePureViolations
    stays 0 BY CONSTRUCTION of the comparison."""
    r, ext, _tree = aliased_run
    require_completed(r)
    orc = sl.SearchOracle(aliased=True)
    for loc in sl.ALL_LOCALES:
        rows = shard_lines(ext, loc)
        assert len(rows) == PIN_DOCS[loc], (
            f"{loc}: docs {len(rows)} != hand pin {PIN_DOCS[loc]}")
        expected = orc.name_resolution(loc)
        got = {(d["kind"], d["id"]) for d in rows}
        assert got == set(expected), (
            f"{loc}: membership differs from oracle; missing="
            f"{sorted(set(expected) - got)[:6]}, extra="
            f"{sorted(got - set(expected))[:6]}")
        titles = titles_lines(ext, loc)
        assert len(titles) == len(rows)
        for t, d in zip(titles, rows):
            assert set(t) == TITLES_KEYS, t
            assert (t["kind"], t["id"]) == (d["kind"], d["id"])
            assert t["t"] == d["name"]["text"], (
                "titles projection must derive row-for-row from the shard")
    section = last_run_section(ext)
    assert re.search(r"localePureViolations\s*=\s*0\b", section)
    assert re.search(r"docsEmitted\s*=\s*\d+", section)


def test_D_dev_and_literal_names_ship_en_only(aliased_run):
    r, ext, _tree = aliased_run
    require_completed(r)
    orc = sl.SearchOracle(aliased=True)
    pivot_only = set()
    for loc in sl.ALL_LOCALES:
        for key, (basis, _k2, _t) in orc.name_resolution(loc).items():
            if basis in ("literal", "dev-fallback"):
                pivot_only.add(key)
    for loc in sl.ALL_LOCALES:
        ids = {(d["kind"], d["id"]) for d in shard_lines(ext, loc)}
        if loc == sl.PIVOT:
            assert pivot_only <= ids, (
                f"pivot must carry literal/dev names: "
                f"{sorted(pivot_only - ids)[:6]}")
        else:
            leak = pivot_only & ids
            assert not leak, (
                f"pivot-fill banned: {loc} shard carries literal/dev docs "
                f"{sorted(leak)[:6]}")


def test_D_visibility_roster_applied(aliased_run):
    r, ext, _tree = aliased_run
    require_completed(r)
    man = load_json(ext, f"{sl.SEARCH_DIR}/manifest.json")
    roster = man.get("visibilityRoster")
    assert roster is not None and set(
        roster.get("internal", [])) == set(sl.VISIBILITY_INTERNAL_NAMES), (
        f"visibilityRoster must carry the pinned 11-name internal list "
        f"verbatim: {roster}")
    vis = {}
    for doc in shard_lines(ext, "en"):
        if doc["kind"] == "campus-level":
            vis[doc["name"]["text"]] = doc["visibility"]
    assert vis.get("Blank Level") == "internal"
    assert vis.get("Test Level") == "internal"
    assert vis.get("Free Play Level") == "internal"
    assert vis.get("All buildings") == "public"
    assert vis.get("Knight Level") == "public"
    # the null-name campus-level emits NOTHING anywhere
    for loc in sl.ALL_LOCALES:
        for doc in shard_lines(ext, loc):
            assert doc["id"] != "LevelScenarioV2_Null_Name"


def test_D_cleaning_tags_placeholders_empty_drop(aliased_run):
    r, ext, _tree = aliased_run
    require_completed(r)
    for loc in sl.ALL_LOCALES:
        for doc in shard_lines(ext, loc):
            text = doc["name"]["text"]
            assert "<" not in text and ">" not in text, doc
            assert not re.search(r"\{[^{}]+\}", text), doc
    # Sword_Name "{BLADE}" cleans to empty in EN -> dropped there, alive de
    en_ids = {(d["kind"], d["id"]) for d in shard_lines(ext, "en")}
    de_ids = {(d["kind"], d["id"]) for d in shard_lines(ext, "de")}
    assert ("item", "Item_Sword_Lite") not in en_ids
    assert ("item", "Item_Sword_Lite") in de_ids
    section = last_run_section(ext)
    assert re.search(r"cleanedEmptyDropped\s*=\s*1\b", section), (
        f"cleanedEmptyDropped must count KEY-level drops (Sword_Name): "
        f"{section[-600:]}")


def test_D_descriptions_resolved_edges_only_never_dev_prose(aliased_run):
    r, ext, _tree = aliased_run
    require_completed(r)
    orc = sl.SearchOracle(aliased=True)
    allowed_desc_texts = set()
    tbl = orc.table("en")
    for kind, eid, path, payload in orc.ls_instances():
        fp = path.split(".")[0]
        if "Description" in path and payload["_termID"] != 0:
            key = sl.KEY_BY_TERM_ID[payload["_termID"]]
            if key in tbl and sl.clean_text(tbl[key]):
                allowed_desc_texts.add(sl.clean_text(tbl[key]))
    for doc in shard_lines(ext, "en"):
        for d in doc.get("descriptions", []):
            assert d["text"] in allowed_desc_texts, (
                f"description outside the resolved Description-class edges: "
                f"{d}")
    for p in search_dir(ext).rglob("*.jsonl"):
        assert sl.DEV_PLACEHOLDER not in p.read_text(encoding="utf-8",
                                                     errors="replace"), (
            "dev placeholder prose must never become a description")


def test_D_ratio_bands_over_emitter_denominators(aliased_run):
    """AC4: for EVERY locale, 60·D ≤ B ≤ 120·D (titles) and
    380·D ≤ B ≤ 650·D (full), over each shard's own counts."""
    r, ext, _tree = aliased_run
    require_completed(r)
    tot_docs = tot_bytes = 0
    for loc in sl.ALL_LOCALES:
        d_full = len(shard_lines(ext, loc))
        b_full = (search_dir(ext) / "shards" / f"{loc}.jsonl").stat().st_size
        d_t = len(titles_lines(ext, loc))
        b_t = (search_dir(ext) / "titles" / f"{loc}.jsonl").stat().st_size
        assert sl.ratio_band_ok(b_t, d_t, 60, 120), (
            f"{loc} titles band breached: {b_t}B / {d_t} docs = "
            f"{b_t / max(d_t, 1):.0f} B/doc")
        assert sl.ratio_band_ok(b_full, d_full, 380, 650), (
            f"{loc} full band breached: {b_full}B / {d_full} docs = "
            f"{b_full / max(d_full, 1):.0f} B/doc")
        tot_docs += d_full
        tot_bytes += b_full
    assert tot_bytes <= 650 * tot_docs, "aggregate Σ law breached"


# ============================================================================
# E — alias layer (AC5)
# ============================================================================

def test_E_id_token_vocabulary_lowercase_rule(aliased_run):
    """RF-A: vocabulary == the LOWERCASED-rule count; the case-sensitive
    superset and fold-collisions ride beside as provenance DATA."""
    r, ext, _tree = aliased_run
    require_completed(r)
    av = load_json(ext, f"{sl.SEARCH_DIR}/manifest.json")["aliasVolumes"]
    assert av["idTokens"] == PIN_TOKENS, av
    sup = av.get("idTokensCaseSensitiveSuperset")
    col = av.get("caseFoldCollisions")
    assert isinstance(sup, int) and isinstance(col, int), (
        f"provenance data must ride beside the seed: {av}")
    assert sup >= av["idTokens"] and col == sup - av["idTokens"], av
    assert col == PIN_CASE_FOLD and sup == PIN_TOKEN_SUPERSET, (
        f"planted single case-fold pair (Item_Gem/GEM_Hunter) must measure "
        f"superset {PIN_TOKEN_SUPERSET} / collisions {PIN_CASE_FOLD}: {av}")
    assert av["devStrings"] == PIN_DEV_STRINGS, av
    assert av["mTermRows"] == 3 and av["mTermResolved"] == 1, av
    section = last_run_section(ext)
    assert re.search(rf"idTokenVocab\s*=\s*{PIN_TOKENS}\b", section), \
        section[-800:]


def test_E_id_token_aliases_are_lowercase_split_runs(aliased_run):
    r, ext, _tree = aliased_run
    require_completed(r)
    checked = 0
    for doc in shard_lines(ext, "en"):
        expected = {t for t in re.split(r"[^0-9A-Za-z]+", doc["id"])
                    if len(t) >= 2 and not t.isdigit()}
        got = {a["text"] for a in doc.get("aliases", [])
               if a["class"] == "id-token"}
        if not expected:
            continue
        assert got == {t.lower() for t in expected}, (
            f"id-token rule violated for {doc['id']}: {got} vs "
            f"{expected}")
        checked += 1
    assert checked >= 20, f"id-token alias coverage too thin: {checked}"


def test_E_dev_string_alias_attaches_only_when_localized_name_exists(
        aliased_run):
    r, ext, _tree = aliased_run
    require_completed(r)
    by_id = {(d["kind"], d["id"]): d for d in shard_lines(ext, "en")}
    stone = by_id[("item", "Item_Testing_Stone")]
    dev_aliases = [a for a in stone["aliases"]
                   if a["class"] == "dev-string"]
    assert any(a["text"] == "Testing Stone Dev" for a in dev_aliases), stone
    # C16's dev text IS the name (dev-fallback basis) — never also an alias
    dev_row = by_id[("config", "Config_Development_Name_Row")]
    assert dev_row["name"]["basis"] == "dev-fallback"
    assert dev_row["name"]["text"] == "Development Config Title"
    assert not [a for a in dev_row["aliases"]
                if a["class"] == "dev-string"], dev_row


def test_E_name_variant_aliases_F_M_and_ranks(aliased_run):
    r, ext, _tree = aliased_run
    require_completed(r)
    by_id = {(d["kind"], d["id"]): d for d in shard_lines(ext, "en")}
    nerd = by_id[("student-type", "Student_Type_Nerd")]
    assert nerd["name"]["termKey"] == "Students/Nerd/F_Name", (
        "student-type: LocalisedNameF is THE name")
    variants = {a["text"] for a in nerd["aliases"]
                if a["class"] == "name-variant"}
    assert "Nerd Boy" in variants, nerd
    prof = by_id[("staff", "Staff_Professor_Row")]
    ranks = {a["text"] for a in prof["aliases"]
             if a["class"] == "name-variant"}
    assert {"Senior Lecturer", "Senior Lecturer Female"} <= ranks, prof


def test_E_mterm_is_name_basis_not_alias(aliased_run):
    r, ext, _tree = aliased_run
    require_completed(r)
    en = {(d["kind"], d["id"]): d for d in shard_lines(ext, "en")}
    tele = en[("unlockable", "Unlock_Telescope_Scope")]
    assert tele["name"]["basis"] == "mterm", tele
    assert tele["name"]["termKey"] == "Items/DLC_Space/Telescope_Name"
    assert not [a for a in tele["aliases"] if a["class"] == "curated"
                and "Telescope" in a.get("text", "")], tele
    # the two UNRESOLVED mTerm rows ledger, never doc
    for uid in ("Unlock_Missing_Term_Alpha", "Unlock_Missing_Term_Beta"):
        for loc in sl.ALL_LOCALES:
            ids = {(d["kind"], d["id"]) for d in shard_lines(ext, loc)}
            assert ("unlockable", uid) not in ids
    ledger = load_jsonl(ext, f"{sl.SEARCH_DIR}/_ledger.jsonl")
    mt = [row for row in ledger if row["code"] == "mt-unresolved"]
    assert len(mt) == 2, mt


def test_E_curated_dangling_termKey_fails_exit1(tmp_path_factory):
    """§S3.3: bad data is louder than missing data — a dangling curated
    key fails validation exit 1 naming it."""
    tree = make_tree(tmp_path_factory, "tw08_dangling")
    ext = tree / "extracted"
    with sl.alias_input(PACK_ROOT, ext, dangling=True):
        r = run12(tree, ext)
    combined = r.stdout + r.stderr
    assert r.returncode == 1, (
        f"dangling curated termKey must exit 1, got {r.returncode}\n"
        f"{combined[-800:]}")
    assert "Courses/Missing/Dangling_Name" in combined, combined[-500:]
    assert not search_dir(ext).exists() or not any(search_dir(ext).rglob("*")), \
        "failed validation wrote artifacts"


def test_E_collision_block_equals_fixture_seeds(aliased_run):
    """RF-C basis: collidingPairs counts (kind,title) PAIRS with
    multiplicity > 1; ignoreKindCollisions counts DISTINCT TITLE TEXTS
    carried by >1 ENTITY ignoring kind."""
    r, ext, _tree = aliased_run
    require_completed(r)
    col = load_json(ext, f"{sl.SEARCH_DIR}/manifest.json")["collisions"]
    assert col["collidingPairs"] == PIN_COLLISION_PAIRS, col
    top = [((p["kind"], p["title"]), p["count"]) for p in col["topPairs"]]
    # the pin names the TOP two; deeper tail entries are emitter freedom
    assert top[:2] == PIN_TOP_PAIRS, col
    assert col["ignoreKindCollisions"] == PIN_IGNORE_KIND, col
    wl = col["withinLocaleDuplicateTexts"]
    for loc, n in PIN_DUP_TEXTS.items():
        assert wl[loc] == n, (loc, wl)
    section = last_run_section(ext)
    assert re.search(rf"collisionPairs\s*=\s*{PIN_COLLISION_PAIRS}\b", section), \
        section[-800:]


# ============================================================================
# F — course resolution ladder (§S3.2)
# ============================================================================

def _course_block(ext):
    man = load_json(ext, f"{sl.SEARCH_DIR}/manifest.json")
    block = man.get("courseResolution") or {}
    assert block, "manifest.courseResolution missing"
    return block


def _course_methods(block) -> dict:
    """courseId -> method string, wherever the block maps them
    (uniformResolver.methodsByCourse dialect or any flat mapping)."""
    for holder in ("uniformResolver", "resolutions", "courses"):
        sub = block.get(holder)
        if isinstance(sub, dict):
            m = sub.get("methodsByCourse") or sub.get("byCourse")
            if isinstance(m, dict) and m:
                return m
    for key in ("methodsByCourse", "byCourse"):
        if isinstance(block.get(key), dict) and block[key]:
            return block[key]
    raise AssertionError(
        f"no per-course method map in courseResolution: "
        f"{json.dumps(block)[:400]}")


def _course_open_ids(block):
    out = set()
    cd = block.get("courseDefinitions") or {}
    for row in cd.get("open") or []:
        out.add(row["courseId"] if isinstance(row, dict) else row)
    ur = block.get("uniformResolver") or {}
    out |= set(ur.get("marketingOpen") or [])
    return out


def test_F_resolution_ladder_methods_and_targets(aliased_run):
    """Pinned union-set staging outcomes per course: family priority,
    plural fold BOTH directions, last-segment rule, token map (all 7
    entries), curated rows. Methods read from the manifest's per-course
    map; the resolution TARGET is proven through the en shard docs'
    name.termKey."""
    r, ext, _tree = aliased_run
    require_completed(r)
    block = _course_block(ext)
    methods = _course_methods(block)
    for cid, (state, method, key) in sl.course_expectations(True).items():
        got_method = methods.get(cid)
        if state == "open":
            continue  # open courses have no method entry to pin
        assert got_method is not None, f"course {cid} missing a method"
        if method == "family:":
            assert got_method.startswith("family:"), (cid, got_method)
        else:
            assert got_method == method, (cid, got_method, method)
    # targets: every resolved course doc carries its family/curated termKey
    by_id = {(d["kind"], d["id"]): d for d in shard_lines(ext, "en")}
    for cid, (state, method, key) in sl.course_expectations(True).items():
        if state != "resolved":
            continue
        doc = by_id.get(("course", cid))
        assert doc is not None, f"resolved course {cid} emitted no en doc"
        assert doc["name"]["termKey"] == key, (cid, doc["name"])
        basis = doc["name"]["basis"]
        expected_basis = "curated" if method == "curated" else "convention"
        assert basis == expected_basis, (cid, basis)


def test_F_seeded_gate_open_set_and_marketing(aliased_run):
    r, ext, _tree = aliased_run
    require_completed(r)
    section = last_run_section(ext)
    m = re.search(r"courseMechanical\s*=\s*(\d+)", section)
    m2 = re.search(r"courseWithSeedTable\s*=\s*(\d+)", section)
    assert m and m2, section[-800:]
    assert int(m.group(1)) == 6, (
        f"pinned staging mechanical yield 6/9, got {m.group(1)}")
    assert int(m2.group(1)) >= 8, (
        f"seeded gate analog (>= proportional 24/28) failed: "
        f"{m2.group(1)}/9")
    block = _course_block(ext)
    open_ids = _course_open_ids(block)
    assert "Course_SpaceExplorer" in open_ids, open_ids
    ledger = load_jsonl(ext, f"{sl.SEARCH_DIR}/_ledger.jsonl")
    ledgered = " ".join(row.get("detail", "")
                        for row in ledger
                        if row["code"] == "course-name-open")
    for cid in open_ids:
        assert cid in ledgered, (
            f"zero silent drops: open course {cid} not ledgered")
    mr = re.search(r"marketingResolved\s*=\s*(\d+)", section)
    mo = re.search(r"marketingOpen\s*=\s*(\d+)", section)
    assert mr and int(mr.group(1)) == 3, section[-600:]
    assert mo and int(mo.group(1)) == 1, section[-600:]
    assert "Marketing_Course_Orphan_Box" in ledgered


def test_F_degraded_mode_without_alias_input(degraded_run):
    """Alias input ABSENT -> alias-input-absent ledgered, mechanical floor
    holds (cross-reading bound), curated courses go OPEN."""
    r, ext, _tree = degraded_run
    require_completed(r)
    section = last_run_section(ext)
    assert re.search(r"courseMechanical\s*=\s*6\b", section), section[-800:]
    ledger = load_jsonl(ext, f"{sl.SEARCH_DIR}/_ledger.jsonl")
    codes = {row["code"] for row in ledger}
    assert "alias-input-absent" in codes, codes
    block = _course_block(ext)
    open_ids = _course_open_ids(block)
    for cid in ("Course_KnightSchool_LordBlaggard", "Course_PerformingArts"):
        assert cid in open_ids, (cid, sorted(open_ids))
    # per-locale draw shrinks by exactly the two curated courses
    orc_off = sl.SearchOracle(aliased=False)
    for loc in sl.ALL_LOCALES:
        got = {(d["kind"], d["id"]) for d in shard_lines(ext, loc)}
        assert got == set(orc_off.name_resolution(loc)), loc


def test_F_pending_join_consumption_degraded_universe_line(aliased_run):
    """Pre-ruling 4: joins consumed IF present, ledger-degraded when
    short — loud DEGRADED-UNIVERSE line quantifying the 2,005 ceiling."""
    r, ext, _tree = aliased_run
    require_completed(r)
    section = last_run_section(ext)
    assert "DEGRADED-UNIVERSE:" in section or "DEGRADED-UNIVERSE:" in (
        r.stdout + r.stderr), (
        "pending joins must print the loud DEGRADED-UNIVERSE line")
    combined = r.stdout + r.stderr + section
    m = re.search(r"short by (\d+) of 2005", combined)
    assert m, f"ceiling delta not quantified: {combined[-600:]}"
    assert int(m.group(1)) == 2003, m.group(0)
    jr = re.search(r"joinState\s*=?\s*(\w+)", section)
    assert jr and jr.group(1) == "pending", section[-600:]
    vr = re.search(r"variationRefs\s*=\s*(\d+)", section)
    tw = re.search(r"twinEdges\s*=\s*(\d+)", section)
    pj = re.search(r"pendingJoinCandidates\s*=\s*(\d+)", section)
    assert vr and int(vr.group(1)) == 1, section[-600:]
    assert tw and int(tw.group(1)) == 1, section[-600:]
    assert pj and int(pj.group(1)) == 2003, section[-600:]
    ledger = load_jsonl(ext, f"{sl.SEARCH_DIR}/_ledger.jsonl")
    assert any(row["code"] == "item-title-joins-absent" for row in ledger)
    # the joined titles DO ship: variation+twin docs exist with joined text
    en = {(d["kind"], d["id"]): d for d in shard_lines(ext, "en")}
    assert en[("item", "Item_Variation_Construction")][
        "name"]["text"] == "Construction Blocks Set"


def test_F_join_scanner_classifies_unrelated_pptr_rows():
    """Suite-side teeth for the §S1.4 classifier shapes (runnable now):
    GameItem-path rows vs name-convention twins vs unrelated PPtr noise."""
    rows = [
        {"srcKind": "item", "dstKind": "item", "srcId": "v", "dstId": "l",
         "evidence": {"fieldPath": "GameItem"}, "method": "pptr-int-ref"},
        {"srcKind": "item", "dstKind": "item", "srcId": "f", "dstId": "l2",
         "method": "name-convention:_Lite-twin",
         "evidence": {"fieldPath": "DefinitionID", "twin": "l2"}},
        {"srcKind": "item", "dstKind": "item", "srcId": "x", "dstId": "y",
         "evidence": {"fieldPath": "Item"}, "method": "pptr-object"},
        {"srcKind": "room", "dstKind": "item", "srcId": "r", "dstId": "y",
         "evidence": {"fieldPath": "GameItem"}, "method": "pptr-int-ref"},
    ]
    variation = [r_ for r_ in rows
                 if r_.get("srcKind") == "item" and r_.get("dstKind") ==
                 "item" and r_.get("evidence", {}).get("fieldPath") ==
                 "GameItem"]
    twin = [r_ for r_ in rows
            if r_.get("method", "").startswith("name-convention:")
            and r_.get("evidence", {}).get("twin")]
    assert len(variation) == 1 and len(twin) == 1


# ============================================================================
# G — analyzers + census (§S4 / AC6)
# ============================================================================

def test_G_analyzer_table_frozen_assignments(aliased_run):
    r, ext, _tree = aliased_run
    require_completed(r)
    ana = load_json(ext, f"{sl.SEARCH_DIR}/manifest.json")["analyzers"]
    assert set(ana) == set(PINNED_13), sorted(ana)
    for tok, locs in sl.ANALYZER_ASSIGNMENTS.items():
        for loc in locs:
            got = ana[loc]
            got_tok = got.get("tokenizer") if isinstance(got, dict) else got
            assert got_tok == tok, (loc, got_tok)
    ko = ana["ko"]
    assert (ko.get("tokenizer") if isinstance(ko, dict) else ko) == \
        "whitespace", "ko is WHITESPACE — the Hangul/Han distinction is " \
        "contractual (F18)"
    for loc, cfg in ana.items():
        if isinstance(cfg, dict):
            assert cfg.get("lowercase") is True, (loc, cfg)
            assert cfg.get("stripMarkupTags") is True, (loc, cfg)
            assert cfg.get("stripPlaceholders") is True, (loc, cfg)
            assert cfg.get("stoplist") == [], (loc, cfg)
            assert cfg.get("asciiFolding") in (None, "none"), (loc, cfg)


def test_G_vocab_census_matches_oracle(aliased_run):
    r, ext, _tree = aliased_run
    require_completed(r)
    ana = load_json(ext, f"{sl.SEARCH_DIR}/manifest.json")["analyzers"]
    orc = sl.SearchOracle(aliased=True)
    for loc in ("en", "de", "ja", "ko", "zh-Hans"):
        cell = ana[loc]
        assert cell["rows"] == len(orc.table(loc)), (loc, cell)
        assert cell["vocab"] == len(orc.vocab(loc)), (
            f"{loc}: vocab {cell['vocab']} != oracle {len(orc.vocab(loc))}")
        assert cell["cjkRows"] == orc.cjk_rows(loc), (loc, cell)
        assert cell["noWhitespaceRows"] == orc.no_whitespace_rows(loc), \
            (loc, cell)
    section = last_run_section(ext)
    assert "vocabPerLocale" in section, section[-800:]
    assert "markupRowsStripped" in section, section[-800:]


def test_G_hangul_inclusive_detector_ko_whitespace(aliased_run):
    """ko's CJK column counts HANGUL-bearing rows (7 here) while its
    analyzer stays whitespace — the F18/C4 distinction is contractual."""
    r, ext, _tree = aliased_run
    require_completed(r)
    ana = load_json(ext, f"{sl.SEARCH_DIR}/manifest.json")["analyzers"]
    assert astat(ana["ko"], "cjkRows", "cjkBearingRows") == 7, ana["ko"]
    assert astat(ana["zh-Hans"], "noWhitespaceRows") == 6, ana["zh-Hans"]
    assert astat(ana["ja"], "noWhitespaceRows") == 7, ana["ja"]


def test_G_typo_budget_block(aliased_run):
    r, ext, _tree = aliased_run
    require_completed(r)
    tb = load_json(ext, f"{sl.SEARCH_DIR}/manifest.json")["typoBudget"]
    orc = sl.SearchOracle(aliased=True)
    max_vocab = max(len(orc.vocab(l)) for l in sl.ALL_LOCALES)
    assert tb["maxVocabObserved"] == max_vocab, (tb, max_vocab)
    assert tb["ceilingAssumed"] == 30000
    assert tb["strategy"] == "client-side levenshtein-d2"
    assert tb["feasibility"] == "measured"
    assert tb["infra"] == "none-hosted"


# ============================================================================
# H — manifest completeness / hashes / ledger (AC9)
# ============================================================================

def test_H_manifest_blocks_present(aliased_run):
    r, ext, _tree = aliased_run
    require_completed(r)
    man = load_json(ext, f"{sl.SEARCH_DIR}/manifest.json")
    for block in ("meta", "universe", "shards", "analyzers", "aliasVolumes",
                  "titleKeySets", "sizes", "kindWeights", "visibilityRoster",
                  "collisions", "courseResolution", "typoBudget",
                  "joinState", "excluded"):
        assert block in man, f"manifest block missing: {block}"
    assert man["meta"]["buildId"] == BUILD_ID
    stamps = man["meta"]["sourceStamps"]
    assert set(stamps) >= {"relinkIdentity", "localisationIdentity"}, stamps
    assert stamps["relinkIdentity"] == read_json(
        ext / ".stage-stamps" / "relink.json")["identity"]
    assert stamps["localisationIdentity"] == read_json(
        ext / ".stage-stamps" / "localisation.json")["identity"]
    assert man["kindWeights"] == sl.KIND_WEIGHTS
    tk = man["titleKeySets"]["narrow"]
    assert tk["edges"] == PIN_TITLE_EDGES and tk["keys"] == PIN_TITLE_KEYS, tk
    sizes_blob = json.dumps(man["sizes"]).lower()
    for metric in ("text", "keyline", "doc"):
        assert metric in sizes_blob, (
            f"sizes must label all three F14/F15/F16 metrics: {sizes_blob}")


def test_H_sha256_agreement_and_hashes_self_exclusion(aliased_run):
    r, ext, _tree = aliased_run
    require_completed(r)
    man = load_json(ext, f"{sl.SEARCH_DIR}/manifest.json")
    for loc, cell in man["shards"].items():
        shard = search_dir(ext) / "shards" / f"{loc}.jsonl"
        titles = search_dir(ext) / "titles" / f"{loc}.jsonl"
        assert cell["docs"] == len(read_jsonl(shard)), (loc, cell)
        assert cell["sha256"] == sha256_bytes(shard.read_bytes()), loc
        assert cell["titlesSha256"] == sha256_bytes(titles.read_bytes()), loc
        assert cell["titlesDocs"] == len(read_jsonl(titles)), loc
    hashes = hash_entries(ext)
    on_disk = {p.relative_to(search_dir(ext)).as_posix()
               for p in search_dir(ext).rglob("*") if p.is_file()}
    covered = set(hashes)
    assert "hashes.json" not in covered, "hashes.json excludes ITSELF"
    assert covered <= on_disk, f"phantom hashes: {sorted(covered - on_disk)}"
    uncovered = on_disk - {"hashes.json"}
    assert covered >= uncovered, (
        f"every emitted file hashed; missing {sorted(uncovered - covered)}")
    for rel, digest in hashes.items():
        assert re.fullmatch(r"[0-9a-f]{64}", digest), rel
        assert digest == sha256_bytes(
            (search_dir(ext) / rel).read_bytes()), rel
    assert list(hashes) == sorted(hashes)


def test_H_ledger_codes_shape_and_states(aliased_run, degraded_run):
    _r1, ext_a, _t1 = aliased_run
    _r2, ext_d, _t2 = degraded_run
    require_completed(_r1)
    require_completed(_r2)
    led_a = load_jsonl(ext_a, f"{sl.SEARCH_DIR}/_ledger.jsonl")
    led_d = load_jsonl(ext_d, f"{sl.SEARCH_DIR}/_ledger.jsonl")
    for ledger, aliased in ((led_a, True), (led_d, False)):
        codes = set()
        for row in ledger:
            assert row["code"] in LEDGER_CODES, row
            assert row["severity"] in ("info", "gap"), row
            assert row["buildId"] == BUILD_ID
            assert row["detail"] and row["unblock"], row
            codes.add(row["code"])
        keys = [(row["code"], row["detail"]) for row in ledger]
        assert keys == sorted(keys), "ledger sorts by (code,detail)"
        assert ("mt-unresolved" in codes)
        assert ("dev-only-names" in codes)
        assert ("campus-level-scope" in codes)
        assert ("item-title-joins-absent" in codes)
        assert ("alias-input-absent" in codes) != aliased, codes
    by_code = Counter(row["code"] for row in led_a)
    assert by_code["mt-unresolved"] == 2
    section = last_run_section(ext_a)
    m = re.search(r"ledgerRows\s*=\s*(\d+)", section)
    assert m and int(m.group(1)) == len(led_a), section[-600:]


def test_H_dev_only_docs_reported_per_kind(aliased_run):
    r, ext, _tree = aliased_run
    require_completed(r)
    uni = load_json(ext, f"{sl.SEARCH_DIR}/manifest.json")["universe"]
    dev = uni.get("devOnlyDocs")
    assert isinstance(dev, dict) and dev, (
        "G4 population must report devOnlyDocs per kind")
    assert dev.get("item") == 3 and dev.get("config") == 1, dev
    assert dev.get("student-type") == 1 and dev.get("unlockable") == 1, dev
    section = last_run_section(ext)
    assert "devOnlyDocs" in section, section[-600:]


def test_H_manifest_carries_no_timestamps(aliased_run):
    r, ext, _tree = aliased_run
    require_completed(r)
    for rel in ("manifest.json", "hashes.json", "_ledger.jsonl",
                "shards/en.jsonl", "titles/en.jsonl"):
        text = (search_dir(ext) / rel).read_text(encoding="utf-8")
        assert not sl.scan_for_timestamps(text), (
            f"wall-clock timestamp inside {rel}")


def test_H_run_section_all_pass_counters(aliased_run):
    r, ext, _tree = aliased_run
    require_completed(r)
    section = last_run_section(ext)
    pinned_tokens = (
        "stubRows=", "universeNarrow=", "universeExpanded=",
        "planningFloorDelta", "joinState=", "variationRefs=", "twinEdges=",
        "pendingJoinCandidates=", "idOnlyRemainder=",
        "docsEmitted=", "perLocaleDocs", "cleanedEmptyDropped=",
        "devOnlyDocs", "localePureViolations=", "bonesIndexed=",
        "idTokenVocab=", "devAliases=", "mTermResolved=",
        "courseMechanical=", "courseWithSeedTable=", "courseOpen=",
        "marketingResolved=", "marketingOpen=", "collisionPairs=",
        "analyzerAssignments", "vocabPerLocale", "markupRowsStripped",
        "shardFiles=", "manifestBytes=", "hashesCount=", "ledgerRows=",
        "rebuildTrigger", "upstreamVerdict",
    )
    missing = [t for t in pinned_tokens if t not in section]
    assert not missing, f"pinned run-section counters missing: {missing}"


# ============================================================================
# I — determinism (AC7)
# ============================================================================

def test_I_double_run_byte_identical(tmp_path_factory):
    tree = make_tree(tmp_path_factory, "tw08_det")
    ext = tree / "extracted"
    with sl.alias_input(PACK_ROOT, ext):
        r1 = run12(tree, ext)
        require_completed(r1)
        snap1 = snapshot_search(ext)
        h1 = (search_dir(ext) / "hashes.json").read_bytes()
        r2 = run12(tree, ext, "--force")
        require_completed(r2)
    assert (search_dir(ext) / "hashes.json").read_bytes() == h1, \
        "double-run hashes.json differs — determinism broken"
    snap2 = snapshot_search(ext)
    assert snap1 == snap2, (
        "rerun mutated declared outputs: "
        f"{[k for k in set(snap1) | set(snap2) if snap1.get(k) != snap2.get(k)]}")
    assert not list(Path(ext).rglob("*.tmp")), "temp files left behind"


def test_I_twin_root_byte_identical(tmp_path_factory):
    tree = make_tree(tmp_path_factory, "tw08_twin")
    ext1 = tree / "extracted"
    with sl.alias_input(PACK_ROOT, ext1):
        require_completed(run12(tree, ext1))
        h1 = (search_dir(ext1) / "hashes.json").read_bytes()
    ext2 = tree / "extracted_twin"
    # consumed stamps RIDE ALONG: they are stage-12 INPUTS (their
    # identities feed manifest.meta.sourceStamps), so a twin lacking them
    # is not the same upstream set — only the runner-owned log/meta are
    # excluded.
    shutil.copytree(
        ext1, ext2, ignore=shutil.ignore_patterns("EXTRACTION-LOG.md"))
    (ext2 / ".pipeline-meta.json").unlink(missing_ok=True)
    with sl.alias_input(PACK_ROOT, ext2):
        r = run12(tree, ext2, "--force")
    require_completed(r)
    assert (search_dir(ext2) / "hashes.json").read_bytes() == h1


# ============================================================================
# J — exit-2 discrimination matrix (§S5.3 / AC8, self-relative fixtures)
# ============================================================================

def _baseline_tree(tmp_path_factory, name):
    """A completed baseline run whose search/ tree we can defend."""
    tree = make_tree(tmp_path_factory, name)
    ext = tree / "extracted"
    with sl.alias_input(PACK_ROOT, ext):
        r = run12(tree, ext)
        require_completed(r)
    return tree, ext, snapshot_search(ext)


def _rewrite_json(path: Path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2,
                               sort_keys=True) + "\n",
                    encoding="utf-8", newline="\n")


def test_J_steady_rerun_at_bound_has_no_false_positive(tmp_path_factory):
    """INCLUSIVE brackets: a member sitting ON its measured value is IN
    the steady state — unchanged reruns proceed (never exit 1). The
    rerun restores the baseline INPUT STATE (alias input present), since
    an input-state flip is a legitimate output change, not a rerun."""
    tree, ext, snap = _baseline_tree(tmp_path_factory, "tw08_j1")
    with sl.alias_input(PACK_ROOT, ext):
        r = run12(tree, ext, "--force")
    require_completed(r)
    assert not regression_lines(r.stdout + r.stderr), (
        "unchanged rerun produced a false RELINK-REGRESSION positive")
    assert snapshot_search(ext) == snap


def _assert_regression_exit1(tree, ext, before_snap, member_fragments):
    """member_fragments: alternative spellings accepted in the
    RELINK-REGRESSION member name (camelCase vs snake_case is impl
    freedom; the MEMBER must be named either way)."""
    if isinstance(member_fragments, str):
        member_fragments = (member_fragments,)
    r = run12(tree, ext)
    combined = r.stdout + r.stderr
    assert r.returncode == 1, (
        f"same-buildId bound breach must exit 1, got {r.returncode}\n"
        f"{combined[-900:]}")
    regs = regression_lines(combined)
    assert regs, f"RELINK-REGRESSION line missing:\n{combined[-700:]}"
    assert any(f in ln for ln in regs for f in member_fragments), regs[:4]
    assert snapshot_search(ext) == before_snap, (
        "breached run OVERWROTE a healthy index — anti-masking violated")


def test_J_dangling_guid_increase_same_buildid_is_regression(
        tmp_path_factory):
    tree, ext, snap = _baseline_tree(tmp_path_factory, "tw08_j2")
    report = read_json(ext / "relinks" / "guid_bridge_report.json")
    report["danglingDistinctGuids"] += 1          # worsened at SAME buildId
    _rewrite_json(ext / "relinks" / "guid_bridge_report.json", report)
    sl.write_stamps(ext)
    _assert_regression_exit1(tree, ext, snap,
                             ("dangling", "danglingDistinctGuids"))


def test_J_entity_locale_decrement_same_buildid_is_regression(
        tmp_path_factory):
    tree, ext, snap = _baseline_tree(tmp_path_factory, "tw08_j3")
    rows = read_jsonl(ext / "relinks" / "entity_locale.jsonl")
    write_jsonl(ext / "relinks" / "entity_locale.jsonl", rows[1:])
    sl.write_stamps(ext)
    _assert_regression_exit1(tree, ext, snap,
                             ("entity_locale", "entityLocaleRows",
                              "entityLocale"))


def test_J_locale_table_decrement_same_buildid_is_regression(
        tmp_path_factory):
    tree, ext, snap = _baseline_tree(tmp_path_factory, "tw08_j4")
    path = ext / "locales" / "de.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    path.write_text("".join(lines[1:]), encoding="utf-8", newline="\n")
    sl.write_stamps(ext)
    _assert_regression_exit1(tree, ext, snap, "de")


def test_J_improved_member_drifts_and_rebases(tmp_path_factory):
    """Improved member (fewer holes): informational DRIFT, fresh value
    becomes the seed — never a regression verdict."""
    tree, ext, _snap = _baseline_tree(tmp_path_factory, "tw08_j5")
    rows = read_jsonl(ext / "locales" / "ja.jsonl")
    have = {r_["id"] for r_ in rows}
    # any pivot-resolved key missing from ja is a legitimate backfill
    new_key = next(k for k in sorted(sl.KEY_TEXTS)
                   if k not in have and sl.PIVOT in sl.KEY_TEXTS[k])
    rows.append({"id": new_key,
                 "text": sl.KEY_TEXTS[new_key]["en"] + "_fix"})
    write_jsonl(ext / "locales" / "ja.jsonl",
                sorted(rows, key=lambda r_: r_["id"]))
    sl.write_stamps(ext)
    r = run12(tree, ext)
    require_completed(r)
    assert not regression_lines(r.stdout + r.stderr), (
        "improvement flagged as regression")
    assert "DRIFT:" in (r.stdout + r.stderr), (
        "improved member must print the informational DRIFT line")


def test_J_buildid_bump_is_drift_never_regression(tmp_path_factory):
    tree, ext, _snap = _baseline_tree(tmp_path_factory, "tw08_j6")
    bump_buildid_everywhere(ext)
    r = run12(tree, ext, "--force")
    combined = r.stdout + r.stderr
    assert r.returncode != 1, (
        f"a DIFFERENT buildId is NEVER a regression verdict: "
        f"rc={r.returncode}\n{combined[-700:]}")
    assert "DRIFT:" in combined, f"DRIFT summary missing:\n{combined[-700:]}"


def test_J_matrix_structural_break_is_exit1(tmp_path_factory):
    """Structural validity: matrix must parse with cellsTotal == 100."""
    for tag, mutator in (
            ("tw08_j7a", lambda m: m["pairs"].pop()),
            ("tw08_j7b", lambda m: m.update(pairs=[])),
    ):
        tree = make_tree(tmp_path_factory, tag)
        ext = tree / "extracted"
        matrix = read_json(ext / "relinks" / "matrix.json")
        mutator(matrix)
        _rewrite_json(ext / "relinks" / "matrix.json", matrix)
        r = run12(tree, ext)
        combined = r.stdout + r.stderr
        assert r.returncode == 1, (
            f"structural break ({tag}) must exit 1, got {r.returncode}\n"
            f"{combined[-700:]}")


# ============================================================================
# K — suite-side mutation teeth
# ============================================================================

def test_K_band_checker_has_teeth():
    assert sl.ratio_band_ok(90 * 100, 100, 60, 120)
    assert not sl.ratio_band_ok(30 * 100, 100, 60, 120), \
        "checker must flag a low-side band breach"
    assert not sl.ratio_band_ok(200 * 100, 100, 60, 120), \
        "checker must flag a high-side band breach"


def test_K_timestamp_scanner_detects_iso_and_finishedAt():
    assert sl.scan_for_timestamps('{"finishedAt": "2026-08-26T00:00:00Z"}')
    assert not sl.scan_for_timestamps('{"buildId": 20226581}')
    assert not sl.scan_for_timestamps('{"t": "Knight School"}')


def test_K_cleaning_rules_match_the_pinned_regexes():
    assert sl.clean_text('<style="x">Lab</style> {ITEM} Work') == \
        "Lab  Work"          # tags + braces stripped; whitespace untouched
    assert sl.clean_text("{ONLY_PLACEHOLDERS}") is None
    assert sl.clean_text("<br></br>") is None
    assert sl.clean_text("Große Bibliothek") == "Große Bibliothek"


def test_K_oracle_collisions_react_to_multiplicity_change():
    base = sl.SearchOracle(aliased=True)
    _col, top, ig, _dup = base.collisions()
    mutated_entities = [e for e in sl.ENTITIES
                        if not (e[0] == "config"
                                and e[1] == "Config_Laboratory_Hub_E")]
    less = sl.SearchOracle(mutated_entities, aliased=True)
    _col2, top2, ig2, _dup2 = less.collisions()
    assert top2[0] == (("config", "Lab Work"), 4), top2[0]
    assert ig2 == ig - 1 or ig2 == ig, (ig, ig2)


# ============================================================================
# N — client-gated integration (auto-skips without the committed corpus)
# ============================================================================

def _real_corpus_available():
    ext = PACK_ROOT / "extracted"
    needed = list(sl.REAL_INPUT_FILES) + ["stubs/items.jsonl",
                                          "locales/en.jsonl",
                                          "locales/locale-matrix.json"]
    missing = [rel for rel in needed
               if not (ext / rel).is_file()]
    if missing:
        pytest.skip(f"client-gated: real corpus inputs missing: {missing}")
    return True


def _pick_scratch_base(tag: str) -> Path:
    env = os.environ.get("TPC_TW08_SCRATCH", "").strip()
    candidates = ([Path(env)] if env
                  else [Path("D:/tpc_pytmp/tw08") / tag,
                        Path("A:/tpc_pytmp/tw08") / tag])
    for base in candidates:
        try:
            base.mkdir(parents=True, exist_ok=True)
            probe = base / ".write_probe"
            probe.write_text("ok", encoding="ascii")
            probe.unlink()
            free = shutil.disk_usage(base).free
            if free >= 2 ** 30:
                return base
        except OSError:
            continue
    pytest.skip("environment: no legal scratch root with >=1 GiB free "
                "(D:/A: or $TPC_TW08_SCRATCH)")


import atexit


# Spent real-corpus copies are removed when the session ends — the D:/A:
# scratch roots are shared and space-capped (NE8K drive-pressure rule).
_SCRATCH_COPIES: list[Path] = []


def _fresh_ext(src: Path, name: str) -> Path:
    ext = Path(src).parent / name
    if ext.exists():
        shutil.rmtree(ext)
    shutil.copytree(src, ext)
    _SCRATCH_COPIES.append(ext)
    return ext


def _purge_scratch_copies():
    for d in _SCRATCH_COPIES:
        shutil.rmtree(d, ignore_errors=True)
    _SCRATCH_COPIES.clear()


atexit.register(_purge_scratch_copies)


@pytest.fixture(scope="module")
def real_scratch(tmp_path_factory):
    """Pristine scratch extraction root = exactly stage-12's upstream set
    copied from the committed real corpus (hostless; no game dir)."""
    _real_corpus_available()
    base = _pick_scratch_base(_session_tag())
    dst = base / "scratch_ext"
    if not dst.exists():
        sl.selective_real_scratch(PACK_ROOT / "extracted", dst)
    tree = make_tree(tmp_path_factory, "tw08_real_tree")
    return tree, dst


def _session_tag() -> str:
    return os.environ.get("TPC_TW08_TAG", "s")


REAL_SEEDS = {
    "stubRows": 13443,
    "universeNarrow": 7178,
    "perKind": {"campus-level": 13, "config": 3856, "course": 41,
                "item": 2649, "metagame-node": 406, "room": 107,
                "staff": 3, "student-type": 54, "unlockable": 49},
    "collisionPairs": 264,
    "topPair1": ("config", "Lab Work", 53),
    "topPair2": ("config", "Specialist Book Report", 51),
    "ignoreKindCollisions": 320,
    "dupTexts": {"en": 1570, "zh-Hans": 1668, "ko": 1702, "tr": 1625},
    "cleanedEmpty": 23,
    "idTokens": 3166,
    "devStrings": 3874,
    "mTermRows": 55,
    "mTermResolved": 53,
}


def _with_alias_if_available(ext: Path):
    """Contextmanager honoring whichever alias-input state the pack is in
    (the Documentator's curated file may land mid-session; both states
    are contract-valid — see reviewer F7)."""
    pack_file = PACK_ROOT / sl.ALIAS_INPUT_REL
    if pack_file.exists():
        import contextlib
        return contextlib.nullcontext()
    return sl.alias_input(PACK_ROOT, ext)


@pytest.mark.client_gated
def test_N_real_universe_exact_figures(real_scratch, tmp_path_factory):
    """AC2 as written on the committed corpus (buildId 20226581)."""
    tree, src = real_scratch
    ext = _fresh_ext(src, "run_universe_ext")
    with _with_alias_if_available(ext):
        r = run12(tree, ext, "--force", timeout=1800)
    require_completed(r, "real-corpus search-corpus run")
    uni = load_json(ext, f"{sl.SEARCH_DIR}/manifest.json")["universe"]
    assert uni["narrow"] == REAL_SEEDS["universeNarrow"], (
        f"conservative universe must assert 7,178 digit-for-digit, got "
        f"{uni.get('narrow')}")
    per_kind = narrow_per_kind(uni)
    for kind, want in REAL_SEEDS["perKind"].items():
        assert per_kind.get(kind) == want, (kind, per_kind.get(kind))
    comp = uni.get("components") or {}

    def num(*names):
        return next((comp[n] for n in names if isinstance(comp.get(n), int)),
                    None)

    plain = comp.get("plainStringNameLiterals") or \
        comp.get("plainStringNames") or comp.get("plainNameLiterals")
    if isinstance(plain, dict) and plain.get("total") is not None:
        assert plain["total"] == 1456, plain
        got = plain.get("perKind") or {}
        assert got == {"config": 1402, "unlockable": 41,
                       "campus-level": 13}, got
    elif isinstance(num("plainStringNames", "plainNameLiterals"), int):
        assert num("plainStringNames", "plainNameLiterals") == 1456
    assert num("configLocalisedNamePresenceInstances",
               "configLocalisedNamePresence") == 552
    scoped = comp_value(
        comp, ("configDisplayName", "landscapeBrushScoped"),
        ("configDisplayName", "brushRows"), ("configDisplayNameScoped",),
        ("displayNameScopedInstances",))
    assert scoped == 170, (
        f"LandscapeBrush-scoped DisplayName seed 170, got {scoped}")
    room = comp.get("roomNameLocstr") or comp.get("roomNameRows") or {}
    if isinstance(room, dict):
        assert room.get("presence") == 49 and room.get("textBearing") == 48, \
            room
    mterm_rows = comp_value(comp, ("unlockableMTerm", "rows")) or \
        num("unlockableMTermRows", "mTermRows")
    mterm_res = comp_value(comp, ("unlockableMTerm", "resolvingInEn")) or \
        num("unlockableMTermResolved", "mTermResolved")
    assert mterm_rows == 55 and mterm_res == 53
    assert (num("unlockableDescriptiveNameNonEmpty",
                "unlockableDescriptiveName", "descriptiveName")) == 27
    tci = num("titleCarrierInstances")
    assert isinstance(tci, int) and tci > 0, (
        "titleCarrierInstances is DRIFT-tracked data (730 today), never "
        "equality-asserted")
    # join ceilings + pending bookkeeping (pre-ruling 4)
    section = last_run_section(ext)
    vr = re.search(r"variationRefs\s*=\s*(\d+)", section)
    tw = re.search(r"twinEdges\s*=\s*(\d+)", section)
    assert vr and int(vr.group(1)) <= 353
    assert tw and int(tw.group(1)) <= 1652
    assert "DEGRADED-UNIVERSE:" in section or re.search(
        r"joinState\s*=?\s*emitted", section), (
        "pending joins must degrade loudly (or be fully emitted)")
    assert re.search(r"universeNarrow\s*=\s*7178\b", section)
    assert re.search(r"stubRows\s*=\s*13443\b", section)


@pytest.mark.client_gated
def test_N_real_shards_ac3_ac4(real_scratch):
    tree, src = real_scratch
    ext = _fresh_ext(src, "run_shards_ext")
    with _with_alias_if_available(ext):
        require_completed(run12(tree, ext, "--force", timeout=1800))
    man = load_json(ext, f"{sl.SEARCH_DIR}/manifest.json")
    for plane in ("shards", "titles"):
        files = sorted(p.name for p in
                       (search_dir(ext) / plane).glob("*.jsonl"))
        assert files == sorted(f"{loc}.jsonl" for loc in sl.ALL_LOCALES)
    weights = man["kindWeights"]
    en_docs = shard_lines(ext, "en")
    for doc in en_docs:
        assert doc["slug"] is None
        assert doc["weight"] == weights[doc["kind"]]
        assert set(doc) == DOC_KEYS
    assert len(en_docs) >= 5000, (
        f"join-state-aware floor (pending): en docs {len(en_docs)} < 5000")
    for loc in sl.ALL_LOCALES:
        if loc == "en":
            continue
        n = len(shard_lines(ext, loc))
        # RECONCILIATION RULING (interface round): the spec's >=4,500
        # non-en floor descends from F16's prototype probe, which predates
        # the Rev-2 name-required + pivot-only membership pins — under the
        # pinned rules a non-en shard carries ONLY locale-resolved
        # name-class docs (measured ~2,995–3,014 across all twelve), so
        # 4,500 contradicts the spec's own §S2 semantics. The floor stays
        # a SECOND net above the measured plateau with collapse headroom.
        assert n >= 2800, (
            f"{loc}: {n} docs below the re-based second-net floor")
        d = len(shard_lines(ext, loc))
        b = (search_dir(ext) / "shards" / f"{loc}.jsonl").stat().st_size
        bt = (search_dir(ext) / "titles" / f"{loc}.jsonl").stat().st_size
        dt = len(titles_lines(ext, loc))
        assert sl.ratio_band_ok(bt, dt, 60, 120), (loc, bt, dt)
        assert sl.ratio_band_ok(b, d, 380, 650), (loc, b, d)
    section = last_run_section(ext)
    assert re.search(r"cleanedEmptyDropped\s*=\s*23\b", section), section[-600:]
    assert re.search(r"bonesIndexed\s*=\s*0\b", section)
    assert re.search(r"localePureViolations\s*=\s*0\b", section)


@pytest.mark.client_gated
def test_N_real_alias_and_collision_seeds(real_scratch):
    tree, src = real_scratch
    ext = _fresh_ext(src, "run_alias_ext")
    with _with_alias_if_available(ext):
        r = run12(tree, ext, "--force", timeout=1800)
    require_completed(r)
    man = load_json(ext, f"{sl.SEARCH_DIR}/manifest.json")
    av = man["aliasVolumes"]
    assert av["idTokens"] == REAL_SEEDS["idTokens"], (
        "RF-A: lowercased-rule vocabulary == 3,166")
    sup = av["idTokensCaseSensitiveSuperset"]
    col = av["caseFoldCollisions"]
    assert isinstance(sup, int) and isinstance(col, int)
    assert sup >= av["idTokens"] and col == sup - av["idTokens"], (
        "provenance pair must stay internally consistent (3,224/58 today), "
        "never equality-asserted")
    assert av["devStrings"] == REAL_SEEDS["devStrings"]
    assert av["mTermRows"] == REAL_SEEDS["mTermRows"]
    assert av["mTermResolved"] == REAL_SEEDS["mTermResolved"]
    c = man["collisions"]
    assert c["collidingPairs"] == REAL_SEEDS["collisionPairs"]
    top = [(p["kind"], p["title"], p["count"]) for p in c["topPairs"]]
    assert top[0] == REAL_SEEDS["topPair1"], top
    assert top[1] == REAL_SEEDS["topPair2"], top
    assert c["ignoreKindCollisions"] == REAL_SEEDS["ignoreKindCollisions"]
    for loc, want in REAL_SEEDS["dupTexts"].items():
        assert c["withinLocaleDuplicateTexts"][loc] == want, (loc, c)
    ledger = load_jsonl(ext, f"{sl.SEARCH_DIR}/_ledger.jsonl")
    mt = [row for row in ledger if row["code"] == "mt-unresolved"]
    assert len(mt) == 2, mt
    # course gates are INPUT-STATE aware (reviewer F7)
    section = last_run_section(ext)
    seeded = re.search(r"courseWithSeedTable\s*=\s*(\d+)", section)
    mech = re.search(r"courseMechanical\s*=\s*(\d+)", section)
    assert mech and int(mech.group(1)) >= 16, (
        f"degraded mechanical floor >=16/28 must hold under every tried "
        f"reading: {mech and mech.group(1)}")
    if (PACK_ROOT / sl.ALIAS_INPUT_REL).exists():
        assert seeded and int(seeded.group(1)) >= 24, (
            f"seeded gate >=24/28 failed: {seeded and seeded.group(1)}")
    mo = re.search(r"marketingOpen\s*=\s*(\d+)", section)
    mr = re.search(r"marketingResolved\s*=\s*(\d+)", section)
    assert mr and mo and int(mr.group(1)) + int(mo.group(1)) == 41, (
        "zero silent drops: marketing resolved+open must cover all 41")


@pytest.mark.client_gated
def test_N_real_analyzers_and_typo_budget(real_scratch):
    tree, src = real_scratch
    ext = _fresh_ext(src, "run_ana_ext")
    with _with_alias_if_available(ext):
        require_completed(run12(tree, ext, "--force", timeout=1800))
    ana = load_json(ext, f"{sl.SEARCH_DIR}/manifest.json")["analyzers"]
    assert set(ana) == set(PINNED_13)
    vocabs = {}
    for loc, cell in ana.items():
        tok = cell.get("tokenizer") if isinstance(cell, dict) else cell
        expected = next(t for t, ls in sl.ANALYZER_ASSIGNMENTS.items()
                        if loc in ls)
        assert tok == expected, (loc, tok)
        vocabs[loc] = astat(cell, "vocab", "vocabDistinctTokens")
    assert vocabs["ko"] == 28594, (
        f"ko vocab endpoint seed (fresh-wins on drift): {vocabs['ko']}")
    assert vocabs["en"] == 11897, vocabs["en"]
    tb = load_json(ext, f"{sl.SEARCH_DIR}/manifest.json")["typoBudget"]
    assert tb["maxVocabObserved"] == max(vocabs.values()) == 28594
    assert tb["ceilingAssumed"] == 30000
    assert tb["strategy"] == "client-side levenshtein-d2"
    assert tb["infra"] == "none-hosted"


@pytest.mark.client_gated
def test_N_real_exit2_steady_state_and_envelope(real_scratch,
                                                tmp_path_factory):
    """AC8 branches on the real corpus: (b) the eight members sit ON
    their INCLUSIVE bounds -> proceeds exit 2 with ledgers."""
    tree, src = real_scratch
    ext = _fresh_ext(src, "run_env_ext")
    with _with_alias_if_available(ext):
        r = run12(tree, ext, "--force", timeout=1800)
    require_completed(r, "real steady-state run")
    assert r.returncode == 2, (
        f"real corpus steady state is exit 2 (completed-with-ledger), got "
        f"{r.returncode}\n{(r.stdout + r.stderr)[-900:]}")
    ledger = load_jsonl(ext, f"{sl.SEARCH_DIR}/_ledger.jsonl")
    assert ledger, "exit 2 requires open ledgers"
    for row in ledger:
        assert row["code"] in LEDGER_CODES, row

    # (a) stamp exitCode ∉ {0,2} -> exit 3 naming it
    ext_a = src.parent / "run_stamp_ext"
    if ext_a.exists():
        shutil.rmtree(ext_a)
    shutil.copytree(src, ext_a)
    stamp = read_json(ext_a / ".stage-stamps" / "relink.json")
    stamp["exitCode"] = 3
    _rewrite_json(ext_a / ".stage-stamps" / "relink.json", stamp)
    ra = run12(tree, ext_a, "--force", timeout=1800)
    assert ra.returncode == 3, f"branch (a) wants exit 3, got {ra.returncode}"
    assert "relink.json" in (ra.stdout + ra.stderr)

    # (c) dangling GUIDs one step WORSE at the same buildId -> exit 1 +
    # RELINK-REGRESSION + artifacts unwritten (anti-masking)
    ext_c = src.parent / "run_reg_ext"
    if ext_c.exists():
        shutil.rmtree(ext_c)
    shutil.copytree(src, ext_c)
    with _with_alias_if_available(ext_c):
        require_completed(run12(tree, ext_c, "--force", timeout=1800))
    before = snapshot_search(ext_c)
    report = read_json(ext_c / "relinks" / "guid_bridge_report.json")
    report["danglingDistinctGuids"] = 1138
    _rewrite_json(ext_c / "relinks" / "guid_bridge_report.json", report)
    rc_ = run12(tree, ext_c, "--force", timeout=1800)
    combined = rc_.stdout + rc_.stderr
    assert rc_.returncode == 1, (
        f"branch (c) 1,138th dangling GUID must exit 1, got "
        f"{rc_.returncode}\n{combined[-800:]}")
    assert any("dangling" in ln for ln in regression_lines(combined)), \
        combined[-500:]
    assert snapshot_search(ext_c) == before, (
        "regressed run rewrote extracted/search/ — WRITE NOTHING violated")

    # (d) entity_locale 10,963 at the same buildId -> exit 1
    ext_d = src.parent / "run_reg2_ext"
    if ext_d.exists():
        shutil.rmtree(ext_d)
    shutil.copytree(src, ext_d)
    with _with_alias_if_available(ext_d):
        require_completed(run12(tree, ext_d, "--force", timeout=1800))
    before_d = snapshot_search(ext_d)
    rows = read_jsonl(ext_d / "relinks" / "entity_locale.jsonl")
    assert len(rows) == 10964
    write_jsonl(ext_d / "relinks" / "entity_locale.jsonl", rows[1:])
    rd = run12(tree, ext_d, "--force", timeout=1800)
    assert rd.returncode == 1, (
        f"branch (d) 10,963 edges must exit 1, got {rd.returncode}")
    assert snapshot_search(ext_d) == before_d

    # (e) buildId bump with moved counts -> DRIFT + rebase, never exit 1
    ext_e = src.parent / "run_drift_ext"
    if ext_e.exists():
        shutil.rmtree(ext_e)
    shutil.copytree(src, ext_e)
    with _with_alias_if_available(ext_e):
        require_completed(run12(tree, ext_e, "--force", timeout=1800))
    bump_buildid_everywhere(ext_e)
    re_ = run12(tree, ext_e, "--force", timeout=1800)
    combined_e = re_.stdout + re_.stderr
    assert re_.returncode != 1, (
        f"branch (e): a different buildId is NEVER a regression: "
        f"{re_.returncode}\n{combined_e[-700:]}")
    assert "DRIFT:" in combined_e, combined_e[-500:]


@pytest.mark.client_gated
def test_N_real_double_run_idempotent(real_scratch):
    tree, src = real_scratch
    ext = _fresh_ext(src, "run_det_ext")
    with _with_alias_if_available(ext):
        require_completed(run12(tree, ext, "--force", timeout=1800))
        s1 = snapshot_search(ext)
        h1 = (search_dir(ext) / "hashes.json").read_bytes()
        r = run12(tree, ext, "--force", timeout=1800)
    require_completed(r)
    assert (search_dir(ext) / "hashes.json").read_bytes() == h1
    assert snapshot_search(ext) == s1


@pytest.mark.client_gated
def test_N_real_write_scope_and_carveout(real_scratch):
    """AC10: nothing outside extracted/search/ (+ runner-owned trio) is
    written; the piece-1 media-extension grep stays green."""
    tree, src = real_scratch
    ext = _fresh_ext(src, "run_scope_ext")
    before = snapshot_readonly(ext)
    with _with_alias_if_available(ext):
        require_completed(run12(tree, ext, "--force", timeout=1800))
    after = snapshot_readonly(ext)
    changed = sorted(k for k in set(before) | set(after)
                     if before.get(k) != after.get(k))
    legal = tuple(a.rstrip("/") for a in ALLOWED_WRITES)
    illegal = [c for c in changed
               if not any(c == lg or c.startswith(lg + "/")
                          or c.split("/")[0] == lg for lg in legal)]
    assert not illegal, f"writes outside scope: {illegal[:8]}"
    assert not scan_tree_for_media_extensions(search_dir(ext)), \
        "media carve-out regressions inside search/"

