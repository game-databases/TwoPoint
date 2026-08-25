"""piece-02 §8 client-gated integration — stage `relink` on the REAL corpus.

Auto-SKIP — loudly, never failing — when neither TPC_GAME_DIR nor the
default install exists, or the piece-1 upstream artifacts are not on this
host. The relink run itself is paid ONCE per session (module-scoped
fixture): the stage-6 upstream set is copied from the real extraction root
into a private temp root (`_relinklib.copy_upstream_set`), the R1 bridge
passes open the 176 real bundles READ-ONLY from the install, and every
write lands in the temp root — the shared `extracted/` tree is never
touched by this lane. Expect minutes per run (UnityPy over ~4 GiB); the
double-run idempotence leg additionally requires TPC_IT_HEAVY=1 (the
piece-1 precedent: real-tree double runs are the optional-slow mark).

Reconciliation seeds (F7/F8/F9) are drift-tolerant BY CONTRACT: fresh
measured numbers win and the test PRINTS a DRIFT line on movement; only
the mechanical identities (internal arithmetic, diff-vs-matrix == 0,
ledger completeness) hard-fail.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _relinklib as rl  # noqa: E402
from _validators import (  # noqa: E402
    LOCALE_TABLE, TOTAL_BUNDLES, diff_manifests, hash_tree, read_json,
    read_jsonl,
)

pytestmark = pytest.mark.client_gated

PACK_ROOT = Path(__file__).resolve().parent.parent
LOCALE_13 = set(LOCALE_TABLE.values())

# F9 scout-time seeds (reconciliation distance; fresh numbers win)
F9_SEEDS = {"guidRefsTotal": 20042, "distinctGuids": 5548,
            "resolveRateAddress": 0.797, "danglingDistinctGuids": 1137}
# F7 registry triple + F8's five measured non-registry IDs
F7_ROWS, F7_KEYS = 15675, 15672
KNOWN_UNRESOLVED_TERM_IDS = set(rl.KNOWN_UNRESOLVED_TERM_IDS)


def _game_or_skip():
    from conftest import game_dir
    g = game_dir()
    if g is None:
        pytest.skip(
            "client-gated: neither TPC_GAME_DIR nor "
            r"A:\SteamLibrary\steamapps\common\Two Point Campus exists")
    return g


class _Run:
    """The one paid-for live-corpus relink run + tolerant fact readers."""

    def __init__(self, ext: Path, rc: int, out: str, err: str):
        self.ext, self.rc, self.out, self.err = ext, rc, out, err

    @property
    def combined(self):
        return self.out + self.err

    def ok(self):
        assert self.rc in (0, 2), (
            f"relink failed on the live corpus rc={self.rc}\n"
            f"{self.combined[:2000]}…[{len(self.combined)} chars total]")
        return self

    def _sources(self):
        yield self.combined
        log = self.ext / "EXTRACTION-LOG.md"
        if log.exists():
            yield log.read_text(encoding="utf-8", errors="replace")

    def counter(self, key: str):
        """Pinned run-section key -> int (same-line digits, any prose/table
        separator between key and value), else None."""
        pat = re.compile(rf"{key}\b[^0-9\n]*(\d+)")
        for src in self._sources():
            m = pat.search(src)
            if m:
                return int(m.group(1))
        return None

    def flag(self, key: str):
        """Pinned boolean run-section key -> True/False, else None."""
        pat = re.compile(rf"{key}\b[^a-z0-9\n]*(true|false|1|0)\b",
                         re.IGNORECASE)
        for src in self._sources():
            m = pat.search(src)
            if m:
                return m.group(1).lower() in ("true", "1")
        return None


@pytest.fixture(scope="module")
def real_run(tmp_path_factory):
    game = _game_or_skip()
    rl.require_relink_registered()   # loud impl-lagging gate (cached)
    from conftest import run_pack
    from _relinklib import copy_upstream_set
    base = tmp_path_factory.mktemp("cg-relink")
    ext = base / "ext"
    try:
        copy_upstream_set(PACK_ROOT / "extracted", ext)
    except AssertionError as exc:
        pytest.skip(f"client-gated: real upstream artifacts missing ({exc})")
    r = run_pack([str(game), "--only", "relink"], extracted_root=ext,
                 timeout=3600)
    return _Run(ext, r.returncode, r.stdout, r.stderr)


def _roster(ext: Path):
    rows = read_jsonl(ext / "bundle-roster.jsonl")
    scenes = {r["relpath"] for r in rows if r["sceneFlag"] != "none"}
    return rows, scenes


def _pptr_leaves(fields):
    """(leafKey, m_FileID, m_PathID) for every exact {m_FileID, m_PathID}
    int leaf under a payload — deliberately NOT the implementation's walker,
    so the accounting identity below independently audits it."""
    out = []
    stack = [("", fields)]
    while stack:
        key, node = stack.pop()
        if isinstance(node, dict):
            if len(node) == 2 and set(node) == {"m_FileID", "m_PathID"} \
                    and all(isinstance(v, int) for v in node.values()):
                out.append((key.rsplit(".", 1)[-1],
                            node["m_FileID"], node["m_PathID"]))
                continue
            stack.extend(node.items())
        elif isinstance(node, list):
            stack.extend((key, v) for v in node)
    return out


# --- R1 ------------------------------------------------------------------------------

def test_r1_bridges_cover_all_176_bundles(real_run):
    ns = real_run.ok()
    cab = read_jsonl(ns.ext / "relinks" / "bridges" / "cab_index.jsonl")
    cont = read_jsonl(ns.ext / "relinks" / "bridges" / "container_index.jsonl")
    assert cab, "cab_index.jsonl empty"
    assert cont, "container_index.jsonl empty"
    roster_rows, _scenes = _roster(ns.ext)
    bridged = {row["bundle"] for row in cab}
    want = {Path(r["relpath"]).name for r in roster_rows}
    missing = sorted(want - bridged)[:8]
    assert bridged == want and len(bridged) == TOTAL_BUNDLES == 176, (
        f"bundlesBridged {len(bridged)} != roster {len(want)}; first missing: {missing}")
    keys = [(r["bundle"], r["cab"]) for r in cab]
    assert keys == sorted(keys), "cab_index sort order violated"
    # arbiter F8 (CR5): the run-section cabRows key must equal its artifact
    # — serialized files, not summed objects; objects report as cabObjects
    cabrows = ns.counter("cabRows")
    assert cabrows is not None, "run section lost cabRows"
    assert cabrows == len(cab), \
        f"cabRows {cabrows} != cab_index.jsonl rows {len(cab)}"
    cab_objects = ns.counter("cabObjects")
    if cab_objects is not None:
        assert cab_objects > cabrows, \
            f"cabObjects {cab_objects} must exceed the file-row count {cabrows}"
    ckeys = [(r["bundle"], r["address"]) for r in cont]
    assert ckeys == sorted(ckeys), "container_index sort order violated"
    for row in cab[:200]:
        assert rl.validate_cab_row(row) == []
    fallback = ns.counter("fallbackVersionUsedBundles")
    assert fallback is not None, (
        "run section never states fallbackVersionUsedBundles (pinned R1 key)")
    # every content bundle ships a 0.0.0 header on this client → 176/176;
    # movement prints as drift, a partial bridge pass fails
    if fallback != 176:
        print(f"DRIFT: fallbackVersionUsedBundles={fallback} (seed expectation 176)")
    assert fallback > 0


# --- R2 ------------------------------------------------------------------------------

def _pair_files(ext: Path):
    out = {}
    for p in sorted((ext / "relinks").glob("*.jsonl")):
        kind = rl.classify_pair_filename(p.name)
        if kind and kind[0] != "INVALID" and not kind[2]:
            out[p.name] = read_jsonl(p)
    return out


def test_r2_same_file_scale_anchors_and_ledger_counts(real_run):
    """Same-file scale + anchors + the unresolved-ledger accounting.

    ADAPTED 2026-08-25 (blind-pair repair): the original floor transcribed
    F4's `~27,386 genuine candidate edges` seed as a hard emitted-row
    minimum. Re-walking the current tree splits F4's 40,829 same-file
    leaves as 13,443 zero-target m_GameObject leaves + **15,154 NULL
    non-GameObject optional PPtrs** (`Icon`, `SpawnLimitCategory`, … —
    pid==0, no target an edge could name) + **12,232 genuine** (fid==0,
    pid!=0). The scout's "genuine" bucket had swallowed the nulls; the
    spec's own R2 procedure says to SKIP zero-targets, so ≥27,000 emitted
    pptr-same-file rows was unsatisfiable by ANY conforming implementation.
    The stale absolute is replaced by the mechanical identity the spec does
    pin — every genuine leaf becomes exactly one resolved raw ref
    (refCount-summed), one ledger row, or a named exclusion — plus a
    drift-printed fresh scale. Fresh numbers win; identities hard-fail.
    """
    ns = real_run.ok()
    pairs = _pair_files(ns.ext)

    def total(method):
        return sum(1 for rows in pairs.values() for r in rows
                   if r.get("method") == method)

    same_file = total("pptr-same-file")
    MEASURED_SAME_FILE_ROWS = 11_980   # re-measured 2026-08-25, buildId 20226581
    if same_file != MEASURED_SAME_FILE_ROWS:
        print(f"DRIFT: pptr-same-file emitted rows={same_file} "
              f"(re-measured seed {MEASURED_SAME_FILE_ROWS})")
    assert same_file >= 10_000, \
        f"same-file edges {same_file} below walker-alive scale (genuine " \
        f"population re-measured at 12,232 raw refs / ~12k deduped rows)"
    cross_file = total("pptr-cross-file")
    assert cross_file > 0, "cross-file resolution emitted nothing (G2 unfixed?)"

    # -- the accounting identity: walked candidates == resolved + ledgered --
    genuine = named_nonzero = 0
    stubs_dir = ns.ext / "stubs"
    for kind in ("campus-levels", "configs", "courses", "items",
                 "metagame-nodes", "rooms", "staff", "student-types",
                 "unlockables"):
        for r in read_jsonl(stubs_dir / f"{kind}.jsonl"):
            for leaf_key, fid, pid in _pptr_leaves(r.get("fields") or {}):
                if leaf_key in ("m_GameObject", "m_Script"):
                    if fid == 0 and pid != 0:
                        named_nonzero += 1   # excluded BY NAME per §R2
                    continue
                if fid == 0 and pid != 0:
                    genuine += 1
    raw_emitted = sum(r["evidence"]["refCount"] for rows in pairs.values()
                      for r in rows if r.get("method") == "pptr-same-file")
    unresolved = read_jsonl(ns.ext / "relinks" / "_unresolved_pptrs.jsonl")
    assert unresolved, "_unresolved_pptrs ledger empty while gapped refs exist?"
    ledger_samefile = sum(1 for u in unresolved if u["extFileId"] == 0)
    assert raw_emitted + ledger_samefile + named_nonzero == genuine, (
        f"same-file accounting broke: raw resolved {raw_emitted} + ledgered "
        f"{ledger_samefile} + named-excluded {named_nonzero} != walked "
        f"genuine {genuine}")

    def has_edge(fname, src_id, dst_id, method):
        for row in pairs.get(fname, []):
            if (row.get("srcId") == src_id and row.get("dstId") == dst_id
                    and row.get("method") == method):
                return True
        return False

    # FIXED 2026-08-25 (blind-pair repair): the anchor was asserted against
    # `configs_config.jsonl` — the bundle FAMILY spelling — but §R2 pins
    # pair-dataset filenames to the NODE-UNIVERSE kinds (`<srcKind>_<dstKind>
    # .jsonl`), i.e. `config_config.jsonl`; masked until the scale gate
    # above stopped failing first.
    assert has_edge("config_config.jsonl",
                    rl.ANCHOR_GRAPH_SRC, rl.ANCHOR_GRAPH_DST, "pptr-same-file"), \
        "§2 Caterer participants-graph anchor edge missing from config_config.jsonl"
    assert has_edge("room_item.jsonl", rl.ANCHOR_ROOM, rl.ANCHOR_ITEM,
                    "pptr-same-file"), \
        "§2 Archaeology_Display anchor edge missing from room_item.jsonl"

    for u in unresolved:
        assert rl.validate_unresolved_row(u) == []
    # ADAPTED 2026-08-25: the merged ledger carries cross-file residue AND
    # same-file residue AND builtin skips; the pinned counter identity is
    # the three run-section keys summing to the ledger length, each key
    # matching its own partition — not unresolvedCrossFile == len(ledger).
    c_cross = ns.counter("unresolvedCrossFile")
    c_builtin = ns.counter("builtinExternalsSkipped")
    c_same = ns.counter("unresolvedSameFile")
    # arbiter F10: the counter identity is verified or the test FAILS — a
    # missing run-section key can no longer silently skip the check
    assert None not in (c_cross, c_builtin, c_same), (
        f"run-section counter(s) missing: unresolvedCrossFile={c_cross} "
        f"builtinExternalsSkipped={c_builtin} unresolvedSameFile={c_same}")
    assert c_cross + c_builtin + c_same == len(unresolved), (
        f"run-section counters {c_cross}+{c_builtin}+{c_same} != ledger "
        f"rows {len(unresolved)}")
    assert c_same == ledger_samefile, (
        f"run-section unresolvedSameFile={c_same} != ledger's "
        f"{ledger_samefile} extFileId==0 rows")
    keys = [(u["srcKind"], u["srcId"], u["fieldPath"], u["extPath"], u["m_PathID"])
            for u in unresolved]
    assert keys == sorted(keys), "_unresolved_pptrs pinned sort order violated"


def test_r2_scene_edges_resolve_against_roster_ids(real_run):
    """Every dstKind=='scene' edge's dstId must resolve against the roster
    scene-id set (verbatim relpath or basename-without-.bundle spelling).

    ADAPTED 2026-08-25 (blind-pair repair): `checked > 0` was a hard floor
    with no measured basis — neither F1–F12 nor §R2's conditional attribution
    rule promises that any stub-payload reference resolves into a
    scene-flagged bundle. Measured on buildId 20226581: ZERO do (all 26
    scene bundles are bridged; every cross-file CAB home and every GUID
    candidate was checked — none is scene-flagged; the campus-level GUIDs
    resolve to config stubs, not scenes). The id-partition assertion stays
    unconditional — an emitted scene edge may never invent an id — while
    occurrence prints as drift. The attribution MACHINERY itself is covered
    hostless by the fixture lane."""
    ns = real_run.ok()
    _, scene_relpaths = _roster(ns.ext)
    assert scene_relpaths, "no sceneFlag != none roster rows on the live corpus"
    scene_base = {Path(p).name.removesuffix(".bundle") for p in scene_relpaths}
    spellings = {"relpath": 0, "basename": 0, "UNRESOLVED": []}
    checked = 0
    for p in sorted((ns.ext / "relinks").glob("*.jsonl")):
        kind = rl.classify_pair_filename(p.name)
        if not kind or kind[0] == "INVALID":
            continue
        for row in read_jsonl(p):
            if row.get("dstKind") != "scene":
                continue
            checked += 1
            dst = row["dstId"]
            if dst in scene_relpaths:
                spellings["relpath"] += 1
            elif dst in scene_base:
                spellings["basename"] += 1
            else:
                spellings["UNRESOLVED"].append(dst)
    assert not spellings["UNRESOLVED"], (
        f"scene edges invent ids outside the roster: {spellings['UNRESOLVED'][:5]}")
    if checked == 0:
        print("DRIFT: no dstKind=='scene' edges emitted — measured "
              "2026-08-25 at buildId 20226581: no stub-payload PPtr or GUID "
              "reference resolves into a scene-flagged bundle on this "
              "install; occurrence may move with corpus changes")


# --- R6 ------------------------------------------------------------------------------

def test_run_section_names_every_pinned_key(real_run):
    """Arbiter F10 (TR8) on the real pass: every pinned RUN_SECTION_KEYS
    key must appear with a parseable value in the run output or the log —
    a missing key fails this lane instead of skipping the checks that need
    it."""
    ns = real_run.ok()
    text = "\n".join(ns._sources())
    errs = rl.run_section_key_violations(text)
    assert not errs, errs[:8]


def test_ac9_no_overlay_methods_in_client_datasets(real_run):
    """Arbiter F7/AC9: community overlays live ONLY in *.competitor.jsonl
    siblings — every client pair dataset must be free of
    competitor-model:* methods."""
    ns = real_run.ok()
    checked = 0
    for name, rows in _pair_files(ns.ext).items():
        bad = [r for r in rows
               if str(r.get("method", "")).startswith("competitor-model:")]
        assert not bad, \
            f"{name} carries {len(bad)} overlay methods on client rows"
        checked += len(rows)
    assert checked > 0, "no client pair rows found to audit"


# --- R3 ------------------------------------------------------------------------------

def test_ac4_identifier_verbatim_on_real_pair_datasets(real_run):
    """Arbiter F6 on real bytes: every emitted pair dataset sweeps clean —
    srcIds verbatim stub ids, dstIds within the AC4 exception set."""
    ns = real_run.ok()
    errs = rl.ac4_pair_dataset_sweep(ns.ext)
    assert not errs, errs[:8]
    # arbiter F11 on real bytes: every rejected/INVALID relinks/*.jsonl name
    # must be one of the pinned non-pair artifacts — nothing unaccounted
    errs = rl.invalid_pair_filename_violations(ns.ext)
    assert not errs, errs[:8]


def test_r3_guid_report_arithmetic_and_campus_level_modeled(real_run):
    ns = real_run.ok()
    report = read_json(ns.ext / "relinks" / "guid_bridge_report.json")
    errs = rl.validate_guid_report(report)
    assert not errs, errs
    for k, seed in F9_SEEDS.items():
        got = report[k]
        moved = abs(got - seed) > (0.02 if isinstance(seed, float) else 0)
        print(f"{'DRIFT:' if moved else 'match: '} guid_bridge_report.{k}={got} "
              f"(scout-time F9 seed {seed})")
    matrix = read_json(ns.ext / "relinks" / "matrix.json")
    # arbiter F2 on real bytes: every cell's cardinality must reconcile to
    # the emitted pair datasets (rows == edges, distinct srcIds, no phantom)
    errs = rl.reconcile_matrix_to_pair_files(matrix, ns.ext / "relinks")
    assert not errs, errs[:8]
    cell = next(p for p in matrix["pairs"]
                if p["srcKind"] == "campus-level" and p["dstKind"] == "config")
    pair_path = ns.ext / "relinks" / "campus-level_config.jsonl"
    assert pair_path.exists(), (
        "campus-level_config.jsonl not emitted — GUID pair cells need the "
        "container_index bridge (R1), which currently emits nothing")
    # FIXED 2026-08-25 (blind-pair repair): read_jsonl, not read_json — this
    # is a JSONL pair dataset (the read_json call was masked by the file
    # never existing before the negative-pathId bridge fix landed)
    pair_rows = read_jsonl(pair_path)
    via_guid = [r for r in pair_rows if r.get("method") == "assetguid-catalog"]
    assert via_guid, "campus-level_config has no GUID-resolved stub target"
    assert cell["status"] == "modeled", (
        f"campus-level→config status {cell['status']!r} despite GUID carrier "
        f"({len(via_guid)} rows)")


def test_r7_campus_meta_carrier_cell_and_drift_line(real_run):
    """Arbiter F5 (CR4) on real bytes: the seeded 13-row pair fact measures
    0 in the metagame-node cell — the cell must read PARTIAL with the
    carrier-found unblock (never missing/"no carrier found"), and the
    F12 reconciliation line beside F9 must name seed vs measured with the
    seed's landing place."""
    ns = real_run.ok()
    matrix = read_json(ns.ext / "relinks" / "matrix.json")
    # arbiter F12: validate_matrix carries the scene-source terminal pin —
    # all ten scene→* cells on the REAL tree ship missing|partial, zero
    # edges, and the SCENE_SRC_UNBLOCK marker
    errs = rl.validate_matrix(matrix)
    assert not errs, errs[:8]
    assert sum(1 for p in matrix["pairs"]
               if p["srcKind"] == "scene") == 10
    cell = next(p for p in matrix["pairs"]
                if p["srcKind"] == "campus-level"
                and p["dstKind"] == "metagame-node")
    assert cell["status"] == "partial", cell
    unblock = cell.get("unblock") or ""
    assert "Config_Metagame" in unblock, unblock
    assert "no carrier found" not in unblock, unblock
    # the landing place carries the seed's rows
    rows = read_jsonl(ns.ext / "relinks" / "campus-level_config.jsonl")
    landing = [r for r in rows if r["dstId"] == "Config_Metagame"]
    assert landing, "seed-carrier rows absent from campus-level_config.jsonl"
    # F12 reconciliation line: seeded 13 vs measured 0, landing named
    assert "campus-level->metagame-node" in ns.combined, ns.combined[-2000:]
    assert str(len(landing)) in ns.combined or "DRIFT" in ns.combined


# --- R4 ------------------------------------------------------------------------------

def _term_instances(fields):
    """termIds of verbatim {_dev,_termID} structs anywhere in a payload;
    sentinel 0 excluded (declared-empty class, G4)."""
    out = []
    stack = [fields]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            tid = cur.get("_termID")
            if isinstance(tid, int) and tid != 0 and set(cur) <= {"_dev", "_termID"}:
                out.append(tid)
                continue
            stack.extend(cur.values())
        elif isinstance(cur, list):
            stack.extend(cur)
    return out


def test_r4_registry_triple_diff_zero_and_kind_coverage(real_run):
    ns = real_run.ok()
    reg = read_jsonl(ns.ext / "relinks" / "i2_term_registry.jsonl")
    assert reg, "i2_term_registry.jsonl empty"
    for row in reg[:500]:
        assert rl.validate_registry_row(row) == []
    distinct = {r["termKey"] for r in reg}
    if (len(reg), len(distinct)) != (F7_ROWS, F7_KEYS):
        print(f"DRIFT: registry {len(reg)} rows / {len(distinct)} keys "
              f"(F7 seeds {F7_ROWS}/{F7_KEYS})")
    canon_bad = sorted({r["termKey"] for r in reg
                        if sum(1 for x in reg if x["termKey"] == r["termKey"]
                               and x.get("canonical")) != 1})
    assert not canon_bad, f"G10 canonical-on-key violated: {canon_bad[:5]}"
    bad_locale = sorted({loc for r in reg for loc in r.get("locales", [])
                         if loc not in LOCALE_13})
    assert not bad_locale, f"registry locales outside the 13-code set: {bad_locale}"

    # bidirectional diff vs the locale-matrix key space == 0 (the F7 identity)
    mx = read_json(ns.ext / "locales" / "locale-matrix.json")
    mx_keys = set(mx["keys"])
    assert distinct == mx_keys, (
        f"registry-vs-matrix diff nonzero: missing={sorted(mx_keys - distinct)[:5]} "
        f"extra={sorted(distinct - mx_keys)[:5]}")

    el = read_jsonl(ns.ext / "relinks" / "entity_locale.jsonl")
    hits = {(x["srcId"], x["evidence"]["termId"]) for x in el}
    # arbiter F14: the emitted rows' locale evidence is swept against the
    # 13-code set too (previously only registry rows were)
    bad_el_locales = sorted({loc for x in el for loc in
                             (x.get("evidence") or {}).get("locales") or ()
                             if loc not in LOCALE_13})
    assert not bad_el_locales, \
        f"entity_locale locales outside the 13-code set: {bad_el_locales[:5]}"
    stubs = ns.ext / "stubs"
    for kind in ("staff", "course", "student-type"):
        rows = read_jsonl(stubs / rl.fx_roster_style_kind_file(kind))
        want = {(r["id"], tid) for r in rows
                for tid in _term_instances(r.get("fields") or {})}
        miss = sorted(want - hits)[:5]
        assert not miss, (
            f"{kind}: non-empty localised strings below 100% registry coverage; "
            f"first missing (id, termId): {miss}")
    jr = read_json(ns.ext / "relinks" / "locale_join_report.json")
    errs = rl.validate_join_report(jr)
    assert not errs, errs
    unresolved = {e["termId"] for e in jr["unresolvedIds"]}
    missing_known = sorted(KNOWN_UNRESOLVED_TERM_IDS - unresolved)
    assert not missing_known, (
        f"F8's measured non-registry IDs absent from the miss ledger: "
        f"{missing_known} (five known 2026-08-25)")
    if jr["registryMisses"] != len(KNOWN_UNRESOLVED_TERM_IDS):
        print(f"drift: registryMisses={jr['registryMisses']} "
              f"(five known 2026-08-25)")


# --- R5 ------------------------------------------------------------------------------

def test_r5_nine_seeded_surfaces_and_localize_census(real_run):
    ns = real_run.ok()
    cov = read_jsonl(ns.ext / "relinks" / "ui_link_coverage.jsonl")
    assert cov, "ui_link_coverage.jsonl empty"
    blobs = [f"{r.get('uiClass')} {r.get('surfaceId')}" for r in cov]
    for seeded in rl.SEEDED_SURFACE_UI_CLASSES:
        assert any(seeded in b for b in blobs), \
            f"scout-§4 surface {seeded!r} has no coverage row"
    localize = ns.counter("localizeBindings")
    assert localize is not None and localize > 0, \
        "I2.Loc.Localize binding census never reported"
    if abs(localize - 11312) > 0.20 * 11312:
        print(f"DRIFT: localizeBindings={localize} (scout seed ≈ 11,312)")


def test_r5_tooltip_row_honesty_and_partition_on_real_census(real_run):
    """Arbiter F3 + TR6: the tooltip-spawner row ships only meaningful
    (script-class) definitions — Unity-generic containers noted separately,
    never justifying a mapped row or riding as definitions — and the anchor
    partition executes on the real emitted output."""
    ns = real_run.ok()
    cov = read_jsonl(ns.ext / "relinks" / "ui_link_coverage.jsonl")
    trow = next(r for r in cov if r["surfaceId"] == "tooltip-spawner")
    errs = rl.validate_coverage_row(trow)
    assert not errs, errs
    script = [d["class"] for d in trow["definitionClasses"]]
    generic = trow.get("genericContainerClasses") or []
    counter = ns.counter("tooltipTargetClasses")
    assert counter is not None, "run section lost tooltipTargetClasses"
    assert counter == len(script), (counter, len(script))
    generic_counter = ns.counter("tooltipGenericContainers")
    assert generic_counter is not None, \
        "run section lost tooltipGenericContainers (F3 split)"
    assert generic_counter == len(generic), (generic_counter, len(generic))
    engine_names = {"MonoBehaviour", "Transform", "RectTransform",
                    "GameObject", "MonoScript"}
    assert not set(script) & engine_names, \
        f"Unity-generic containers ride as tooltip definitions: {sorted(set(script) & engine_names)[:5]}"
    if trow["status"] == "mapped-schema":
        assert script, "mapped tooltip row carries no meaningful classes"
        assert trow["joins"], "mapped tooltip row names no joins"
        matrix = read_json(ns.ext / "relinks" / "matrix.json")
        cells = {f"{p['srcKind']}_{p['dstKind']}" for p in matrix["pairs"]}
        stray = sorted(set(trow["joins"]) - cells)
        assert not stray, f"joins name non-measured cells: {stray[:5]}"
        # the partition executes on the REAL census and holds
        viol = rl.coverage_partition_violations(cov, script, [])
        assert not viol, viol[:4]
    else:
        assert not trow["joins"], "gap tooltip row carries joins"
        assert trow["gapReason"], trow


# --- R6 ------------------------------------------------------------------------------

def test_r6_floor_state_reported_truthfully(real_run):
    """Bar-3 honesty: whatever competitor inputs are committed (maybe none),
    the reported floor state must EQUAL the ledger arithmetic — never glossed.
    Absent inputs may only lower the floor result; they can NEVER fabricate it."""
    ns = real_run.ok()
    ledger_path = ns.ext / "relinks" / "competitor_applied.jsonl"
    assert ledger_path.exists(), "competitor_applied.jsonl missing"
    ledger = read_jsonl(ledger_path)
    for row in ledger:
        assert rl.validate_competitor_ledger_row(row) == []
    by_source = {}
    for row in ledger:
        if row.get("rung") == "wall":
            continue
        disp = row.get("dispositions") or {}
        acc = by_source.setdefault(row["sourceId"], {})
        for k, v in disp.items():
            acc[k] = acc.get(k, 0) + int(v)
    met, n_sources = rl.floor_gate(by_source)
    reported_met = ns.flag("floorMet")
    assert reported_met is not None, \
        "run section never states floorMet (pinned R6 key)"
    assert reported_met == met, (
        f"floorMet reported {reported_met}, ledger arithmetic says {met} "
        f"({n_sources} disposition-carrying sources)")
    applied, read_ = ns.counter("sourcesApplied"), ns.counter("sourcesRead")
    if applied is not None and read_ is not None:
        assert applied <= read_, "sourcesApplied > sourcesRead (untruthful)"
        # sourcesApplied counts disposition-carrying sources; the floor needs
        # >=3 of them — 1..2 applied with floor unmet is a truthful state
        assert applied == n_sources, (
            f"sourcesApplied={applied} != ledger's {n_sources} "
            "disposition-carrying sources")


# --- idempotence ----------------------------------------------------------------------

@pytest.mark.heavy
def test_idempotence_double_run_hash_equal_on_real_tree(real_run):
    """§8: `--only relink` double-run hash-equal on the real tree (declared
    outputs; EXTRACTION-LOG/.stage-stamps/.pipeline-meta exempt per §4)."""
    ns = real_run.ok()
    from conftest import run_pack
    before = hash_tree(ns.ext)
    r2 = run_pack([str(_game_or_skip()), "--only", "relink", "--force"],
                  extracted_root=ns.ext, timeout=3600)
    assert r2.returncode in (0, 2), r2.stdout + r2.stderr
    only_before, only_after, changed = diff_manifests(before, hash_tree(ns.ext))
    volatile = changed or only_after   # a conforming rerun adds nothing either
    assert not volatile, \
        f"--only relink double-run not byte-identical on the live corpus: {volatile[:8]}"
