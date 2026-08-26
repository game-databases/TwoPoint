#!/usr/bin/env python3
"""Stage 10 — check-contracts (piece-05): the contracts validator suite.

Runs the 44 pinned validators (piece-05 §8: S13 · I9 · X4 · U3 · L3 · D4 ·
R8) over `extracted/` at the pinned build, driven by the tracked layer at
`contracts/`:

    contracts/pins.json          machine source of truth (every constant,
                                 enum domain, reconciliation, ownership rule)
    contracts/red-registry.json  deliberately-red validators awaiting their
                                 fixing amendment (EXPECTED-RED, exit 2)
    contracts/families/*.mdx     human contracts; ```pins blocks kept honest
                                 BY execution (V-D3)
    contracts/counter-units.mdx  frozen unit vocabulary + transform registry

Exit codes (piece-05 §3.4): 0 all green · 1 contract broken (unexpected
FAIL, PIN-STALE, PIN-MISMATCH, unit-gate refusal) · 2 completed-with-known-
ledger (every failing validator is registered EXPECTED-RED) · 3 inputs
missing (cannot check).

Heavy-artifact policy: a default run NEVER opens `addressables/catalog.json`
— catalog-level pins verify against the persisted emit-time sidecar
(`addressables/catalog-mini-report.json`, written by stage 2 post-parse);
absent sidecar ⇒ exit 3. `--scan-catalog` is the audit lane that streams
catalog.json exactly once (incremental raw_decode, sha256 in the same pass),
re-derives the ENTIRE sidecar through the one shared derivation in
contracts_lib, and byte-compares it (bootstrap-writes it when absent).

ZERO-WRITE discipline: a default run creates/modifies nothing under
extracted/. No timestamps anywhere in stdout (byte-identical reruns).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import contracts_lib as cl
import log_util
import tpc_common as tc

STAGE_ID = "check-contracts"

# validator id → section, in pinned catalog order; rendering sorts by id.
VALIDATOR_IDS = (
    ["V-S%d" % i for i in range(1, 14)]
    + ["V-I%d" % i for i in range(1, 10)]
    + ["V-X%d" % i for i in range(1, 5)]
    + ["V-U%d" % i for i in range(1, 4)]
    + ["V-L%d" % i for i in range(1, 4)]
    + ["V-D%d" % i for i in range(1, 5)]
    + ["V-R%d" % i for i in range(1, 9)]
)

TWIN_RE = re.compile(r"@[0-9a-fA-F]{8}$")
GUID32_RE = re.compile(r"^[0-9a-f]{32}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class UnitGateRefusal(Exception):
    """V-U3 load-time refusal: a unit-differing reconciliation without a
    registered transform — exit 1 BEFORE any check runs."""

    def __init__(self, message: str):
        super().__init__(message)
        self.exit_code = 1


# ---------------------------------------------------------------------------
# Event model + output grammar (piece-05 §3.4)

class Ev:
    __slots__ = ("kind", "vid", "body")

    def __init__(self, kind: str, vid: str, body: str):
        self.kind = kind
        self.vid = vid
        self.body = body

    def render(self) -> str:
        return f"{self.kind} [{self.vid}] {self.body}"


def _q(v) -> str:
    return json.dumps(str(v), ensure_ascii=False)


class Outcome:
    """Primary status line plus any number of INFO side-lines."""

    def __init__(self):
        self.primary: Ev | None = None
        self.infos: list[Ev] = []

    def info(self, vid: str, text: str) -> None:
        self.infos.append(Ev("INFO", vid, text))


# ---------------------------------------------------------------------------
# Runner context (lazy artifact cache)

class Ctx:
    def __init__(self, extracted_root: Path, pack_dir: Path,
                 pins: dict, registry: dict, transforms: dict,
                 game_root: Path | None):
        self.extracted_root = extracted_root
        self.pack_dir = pack_dir
        self.tools_dir = pack_dir / "tools"
        self.contracts_dir = cl.contracts_dir(pack_dir)
        self.pins = pins
        self.registry = registry
        self.transforms = transforms
        self.game_root = game_root
        self.memo: dict = {}
        self.identity = self._load_json("identity.json") or {}

    # -- generic io ----------------------------------------------------------
    def _load_json(self, rel: str):
        p = self.extracted_root / rel
        if not p.is_file():
            return None
        return json.loads(p.read_text(encoding="utf-8"))

    def jlines(self, rel: str) -> list[dict]:
        key = "rows:" + rel
        if key not in self.memo:
            self.memo[key] = list(cl.iter_jsonl(self.extracted_root / rel))
        return self.memo[key]

    def has(self, rel: str) -> bool:
        return (self.extracted_root / rel).is_file()

    # -- shared loads --------------------------------------------------------
    def mini_report(self) -> dict:
        if "mini" not in self.memo:
            self.memo["mini"] = self._load_json(cl.MINI_REPORT_REL)
        return self.memo["mini"]

    def coverage(self) -> dict:
        if "coverage" not in self.memo:
            self.memo["coverage"] = self._load_json(
                "addressables/catalog-coverage.json") or {}
        return self.memo["coverage"]

    def matrix(self) -> dict:
        if "matrix" not in self.memo:
            self.memo["matrix"] = self._load_json("relinks/matrix.json") or {}
        return self.memo["matrix"]

    def roster_rows(self) -> list[dict]:
        return self.jlines("bundle-roster.jsonl")

    def stub_kinds(self) -> dict[str, int]:
        if "stub_counts" not in self.memo:
            out = {}
            for kind, fname in self.pins["families"]["stage5"][
                    "kindFiles"].items():
                rows = self.jlines("stubs/" + fname)
                out[kind] = len(rows)
            self.memo["stub_counts"] = out
        return self.memo["stub_counts"]

    def stub_index(self) -> dict[str, dict[str, dict]]:
        """kind → id → row-lite {axes, fields_id, twin} for X-legs."""
        if "stub_light" not in self.memo:
            light: dict[str, dict[str, dict]] = {}
            for kind, fname in self.pins["families"]["stage5"][
                    "kindFiles"].items():
                m: dict[str, dict] = {}
                for row in self.jlines("stubs/" + fname):
                    m[str(row["id"])] = {
                        "axes": row.get("axes"),
                        "fields_id": (row.get("fields") or {}).get("id"),
                        "bundle": (row.get("source") or {}).get("bundle"),
                    }
                light[kind] = m
            self.memo["stub_light"] = light
        return self.memo["stub_light"]

    def pair_files(self) -> dict[str, list[dict]]:
        """`<src>_<dst>.jsonl` pair datasets keyed by filename (competitor
        overlays and non-pair files excluded)."""
        if "pairs" not in self.memo:
            nodes = set(self.node_universe())
            files = sorted((self.extracted_root / "relinks").glob("*.jsonl"))
            out: dict[str, list[dict]] = {}
            for path in files:
                stem = path.name[:-len(".jsonl")]
                parts = stem.split("_")
                if len(parts) != 2:
                    continue
                src, dst = parts
                if src in nodes and dst in nodes:
                    out[path.name] = self.jlines("relinks/" + path.name)
            self.memo["pairs"] = out
        return self.memo["pairs"]

    def node_universe(self) -> list[str]:
        meta = self.matrix().get("meta") or {}
        return list(((meta.get("nodeUniverse") or {}).get("nodes")) or [])

    def registry_keys(self) -> set[str]:
        if "registry_keys" not in self.memo:
            keys = {str(r["termKey"]) for r in self.jlines(
                "relinks/i2_term_registry.jsonl")}
            self.memo["registry_keys"] = keys
        return self.memo["registry_keys"]

    def container_addresses(self) -> set[str]:
        if "container_addresses" not in self.memo:
            self.memo["container_addresses"] = {
                str(r["address"]) for r in self.jlines(
                    "relinks/bridges/container_index.jsonl")}
        return self.memo["container_addresses"]

    def locale_file_lines(self, label: str) -> int:
        """Line count of locales/<label>.jsonl (base-overlay spelled
        base-overlay.jsonl); 0 when absent."""
        name = "base-overlay.jsonl" if label == "BASE-OVERLAY" \
            else f"{label}.jsonl"
        p = self.extracted_root / "locales" / name
        if not p.is_file():
            return 0
        key = "lines:" + name
        if key not in self.memo:
            self.memo[key] = cl.count_jsonl_lines(p)
        return self.memo[key]

    def last_run_section(self, stage_id: str) -> tuple[list[str], str] | None:
        """(body lines, header) of the LAST run section for stage_id."""
        key = "log:" + stage_id
        if key not in self.memo:
            self.memo[key] = None
            path = self.extracted_root / "EXTRACTION-LOG.md"
            if path.is_file():
                current: list[str] | None = None
                header = ""
                found: tuple[list[str], str] | None = None
                pat = re.compile(r"^### \S+ — (.+)$")
                for line in path.read_text(encoding="utf-8").splitlines():
                    m = pat.match(line)
                    if m:
                        if current is not None and header == stage_id:
                            found = (current, header)
                        current = []
                        header = m.group(1).strip()
                    elif current is not None:
                        current.append(line)
                if current is not None and header == stage_id:
                    found = (current, header)
                self.memo[key] = found
        return self.memo[key]

    def build_matches_scope(self) -> bool:
        scope = int(self.pins.get("buildScope", {}).get("buildId", 0))
        return int(self.identity.get("buildId") or 0) == scope


# outcome helpers -----------------------------------------------------------

def ok(ctx: Ctx, vid: str, artifact: str, detail: str) -> Outcome:
    o = Outcome()
    o.primary = Ev("PASS", vid, f"{artifact} {detail}".strip())
    return o


def fail(ctx: Ctx, vid: str, artifact: str, expected, measured,
         hint: str) -> Outcome:
    o = Outcome()
    o.primary = Ev("FAIL", vid,
                   f"{artifact} expected={expected} measured={measured} "
                   f"hint={hint}")
    return o


def pin_mismatch(ctx: Ctx, vid: str, pin: str, expected, measured) -> Outcome:
    o = Outcome()
    o.primary = Ev("PIN-MISMATCH", vid,
                   f"pin={pin} expected={_q(expected)} "
                   f"measured={_q(measured)}")
    return o


def pin_stale(ctx: Ctx, vid: str) -> Outcome:
    o = Outcome()
    o.primary = Ev("PIN-STALE", vid,
                   f"pin=buildScope.buildId "
                   f"pinnedBuild={ctx.pins['buildScope']['buildId']} "
                   f"currentBuild={ctx.identity.get('buildId')}")
    return o


def stale_guarded(ctx: Ctx, vid: str, constant_scoped: bool):
    """Constant-scoped validators emit PIN-STALE instead of pretending when
    the corpus build leaves the pin's scope (piece-05 §3.5)."""
    if constant_scoped and not ctx.build_matches_scope():
        return pin_stale(ctx, vid)
    return None


# ---------------------------------------------------------------------------
# Schema pins (V-S)

def vs1_identity_keyset(ctx: Ctx) -> Outcome:
    g = stale_guarded(ctx, "V-S1", True)
    if g:
        return g
    fam = ctx.pins["families"]["stage0"]
    keys = sorted(ctx.identity.keys())
    if keys != sorted(fam["identityTopKeys"]):
        return fail(ctx, "V-S1", "identity.json",
                    f"{len(fam['identityTopKeys'])} pinned top-level keys "
                    f"{sorted(fam['identityTopKeys'])}",
                    f"{len(keys)} {keys}", "sorted(top-keys) == pinned list")
    if ctx.identity.get("buildId") != ctx.identity.get("targetBuildId"):
        return fail(ctx, "V-S1", "identity.json", "buildId == targetBuildId",
                    f"{ctx.identity.get('buildId')} vs "
                    f"{ctx.identity.get('targetBuildId')}",
                    "buildid-coverage anchor")
    return ok(ctx, "V-S1", "identity.json",
              f"{len(keys)}/{len(fam['identityTopKeys'])} pinned top-level "
              "keys; buildId anchored")


def vs2_roster_envelope(ctx: Ctx) -> Outcome:
    o = stale_guarded(ctx, "V-S2", True)
    if o:
        return o
    pin = ctx.pins["families"]["stage0"]["roster"]
    rows = ctx.roster_rows()
    keyset = set(pin["keyset"])
    for i, row in enumerate(rows):
        if set(row.keys()) != keyset:
            return fail(ctx, "V-S2", "bundle-roster.jsonl",
                        f"row keyset == {sorted(keyset)}",
                        f"row[{i}] {sorted(row.keys())}",
                        "every roster row carries the frozen 6-key envelope")
    measured = {}
    for dom in ("dirClass", "sceneFlag"):
        c: dict = {}
        for row in rows:
            c[str(row[dom])] = c.get(str(row[dom]), 0) + 1
        measured[dom] = c
    named = sum(1 for r in rows
                if r.get("localeFlag") not in (None, "", "base"))
    nulls = sum(1 for r in rows if r.get("localeFlag") is None)
    base = len(rows) - named - nulls
    measured["localeFlag"] = {"null": nulls, "base": base, "named": named}
    for dom in ("dirClass", "sceneFlag", "localeFlag"):
        want = pin[dom]
        got = measured[dom]
        if {k: v for k, v in got.items() if want.get(k)} != \
                {k: v for k, v in want.items() if got.get(k)} or \
                set(got) - set(want):
            exp = ",".join(f"{k}={v}" for k, v in sorted(want.items()))
            mea = ",".join(f"{k}={v}" for k, v in sorted(got.items()))
            return pin_mismatch(ctx, "V-S2",
                                f"families.stage0.roster.{dom}", exp,
                                mea.replace('"', ""))
    if len(rows) != pin["rows"]:
        return pin_mismatch(ctx, "V-S2", "families.stage0.roster.rows",
                            pin["rows"], len(rows))
    return ok(ctx, "V-S2", "bundle-roster.jsonl",
              f'{len(rows)}/{pin["rows"]} rows conform; domains pinned')


def _envelope_errors(ctx: Ctx, kind_files: dict) -> tuple[list[str], int]:
    """Stub envelope scan shared by V-S3; returns (errors, total)."""
    errors: list[str] = []
    total = 0
    env = {"buildId", "fields", "id", "inferred", "kind", "method",
           "provisional", "slug", "source"}
    axes_enum = set(tc.CONTENT_AXES)
    for kind, fname in kind_files.items():
        for i, row in enumerate(self_rows(ctx, fname)):
            total += 1
            extra = set(row.keys()) - env
            missing = env - set(row.keys())
            if extra - {"axes"} or missing:
                errors.append(
                    f"stubs/{fname} row[{i}] envelope off: "
                    + ", ".join(sorted(missing | (extra - {"axes"}))))
                continue
            if str(row["kind"]) != kind:
                errors.append(f"stubs/{fname} row[{i}] kind "
                              f"{row['kind']!r} != filename kind {kind!r}")
            src = row.get("source")
            if not isinstance(src, dict) or \
                    set(src.keys()) != {"bundle", "pathId", "class"}:
                errors.append(f"stubs/{fname} row[{i}] source envelope off")
            axes = row.get("axes")
            if axes is not None:
                if not isinstance(axes, list) or \
                        any(a not in axes_enum for a in axes):
                    errors.append(f"stubs/{fname} row[{i}] axes value "
                                  f"outside the axis enum")
    return errors, total


def self_rows(ctx: Ctx, rel: str) -> list[dict]:
    return ctx.jlines("stubs/" + rel)


def vs3_stub_envelope(ctx: Ctx) -> Outcome:
    o = stale_guarded(ctx, "V-S3", True)
    if o:
        return o
    fam = ctx.pins["families"]["stage5"]
    errors, total = _envelope_errors(ctx, fam["kindFiles"])
    if errors:
        return fail(ctx, "V-S3", "stubs/*.jsonl", "9-key envelope exact",
                    errors[0], errors[0])
    counts = ctx.stub_kinds()
    if counts != fam["rowsByKind"]:
        return pin_mismatch(ctx, "V-S3", "families.stage5.rowsByKind",
                            fam["rowsByKind"], counts)
    axes_measured: dict[str, int] = {}
    for kind, fname in fam["kindFiles"].items():
        n = sum(1 for r in self_rows(ctx, fname) if "axes" in r)
        if n:
            axes_measured[kind] = n
    if axes_measured != fam["axesRows"]:
        return pin_mismatch(ctx, "V-S3", "families.stage5.axesRows",
                            fam["axesRows"], axes_measured)
    return ok(ctx, "V-S3", "stubs/*.jsonl x9",
              f'{total}/{sum(fam["rowsByKind"].values())} rows conform')


def vs4_pair_envelope(ctx: Ctx) -> Outcome:
    o = stale_guarded(ctx, "V-S4", True)
    if o:
        return o
    fam = ctx.pins["families"]["stage6"]
    env = {"srcKind", "srcId", "dstKind", "dstId", "mechanism", "method",
           "inferred", "evidence", "buildId"}
    ev_shapes = fam["evidenceKeysets"]
    files = ctx.pair_files()
    total = 0
    axes_carriers = 0
    for fname, rows in sorted(files.items()):
        for i, row in enumerate(rows):
            total += 1
            extra = set(row.keys()) - env - {"sourceAxes"}
            missing = env - set(row.keys())
            if extra or missing:
                return fail(ctx, "V-S4", f"relinks/{fname} row[{i}]",
                            "frozen 9-key pair envelope (+sourceAxes)",
                            f"off: {sorted(missing | extra)}",
                            "pair rowshape")
            if "sourceAxes" in row:
                axes_carriers += 1
            shape = ev_shapes.get(str(row["method"]))
            if shape is None:
                return fail(ctx, "V-S4", f"relinks/{fname} row[{i}]",
                            str(sorted(ev_shapes)),
                            f'method {row["method"]!r} outside the measured '
                            "pair-method evidence shapes",
                            "evidence keyset per method")
            got = set((row.get("evidence") or {}).keys())
            want = set(shape)
            if not (want <= got) or (got - want):
                return fail(ctx, "V-S4", f"relinks/{fname} row[{i}]",
                            f"evidence keys == {sorted(want)}",
                            f"{sorted(got)}", "evidence keyset per method")
    if len(files) != fam["pairFiles"]:
        return pin_mismatch(ctx, "V-S4", "families.stage6.pairFiles",
                            fam["pairFiles"], len(files))
    if total != fam["pairRows"]:
        return pin_mismatch(ctx, "V-S4", "families.stage6.pairRows",
                            fam["pairRows"], total)
    if axes_carriers != fam["sourceAxesCarrierRows"]:
        return pin_mismatch(ctx, "V-S4",
                            "families.stage6.sourceAxesCarrierRows",
                            fam["sourceAxesCarrierRows"], axes_carriers)
    return ok(ctx, "V-S4", "relinks/<src>_<dst>.jsonl x24",
              f"{total}/{fam['pairRows']} rows conform")


def vs5_locale_rowshape(ctx: Ctx) -> Outcome:
    o = stale_guarded(ctx, "V-S5", True)
    if o:
        return o
    fam = ctx.pins["families"]["stage4"]
    want_counts = dict(fam["lineCounts"])
    measured: dict[str, int] = {}
    locales_dir = ctx.extracted_root / "locales"
    present = sorted(p.name for p in locales_dir.glob("*.jsonl"))
    expect_files = sorted([f"{code}.jsonl" for code in tc.EMITTED_LOCALES]
                          + ["base-overlay.jsonl"])
    if present != expect_files:
        return fail(ctx, "V-S5", "locales/", f"file set == {expect_files}",
                    f"{present}", "13 codes + base-overlay exactly")
    total = 0
    for name in expect_files:
        n = 0
        for row in cl.iter_jsonl(locales_dir / name):
            if set(row.keys()) != {"id", "text"}:
                return fail(ctx, "V-S5", f"locales/{name}",
                            "row keyset == ['id', 'text']",
                            f"{sorted(row.keys())}", "locale rowshape")
            n += 1
        label = "BASE-OVERLAY" if name == "base-overlay.jsonl" \
            else name[:-len(".jsonl")]
        measured[label] = n
        total += n
    drift = {k: v for k, v in measured.items() if want_counts.get(k) != v}
    if drift or set(measured) != set(want_counts):
        return pin_mismatch(ctx, "V-S5", "families.stage4.lineCounts",
                            want_counts, measured)
    if total != fam["linesTotal"]:
        return pin_mismatch(ctx, "V-S5", "families.stage4.linesTotal",
                            fam["linesTotal"], total)
    return ok(ctx, "V-S5", "locales/*.jsonl x14",
              f"{total}/{fam['linesTotal']} lines conform")


def vs6_flat_rowshapes(ctx: Ctx) -> Outcome:
    o = stale_guarded(ctx, "V-S6", True)
    if o:
        return o
    fam = ctx.pins["families"]["flat"]
    for rel, spec in fam.items():
        rows = ctx.jlines(rel)
        want_keys = set(spec["keyset"])
        optional = set(spec.get("optionalKeys", []))
        for i, row in enumerate(rows):
            keys = set(row.keys())
            if not (want_keys <= keys) or (keys - want_keys - optional):
                return fail(ctx, "V-S6", rel,
                            f"keyset ⊇ {sorted(want_keys)} "
                            f"(optional {sorted(optional)})",
                            f"row[{i}] {sorted(keys)}", "flat rowshape")
        if len(rows) != spec["rows"]:
            return pin_mismatch(ctx, "V-S6", f"families.flat.{rel}.rows",
                                spec["rows"], len(rows))
    return ok(ctx, "V-S6", "flat families x7",
              f'{sum(s["rows"] for s in fam.values())} rows conform')


def vs7_matrix_cellshape(ctx: Ctx) -> Outcome:
    o = stale_guarded(ctx, "V-S7", True)
    if o:
        return o
    mx = ctx.matrix()
    nodes = ctx.node_universe()
    pins_fam = ctx.pins["families"]["stage6"]["matrix"]
    pairs = mx.get("pairs") or []
    if sorted(mx.keys()) != ["meta", "pairs"]:
        return fail(ctx, "V-S7", "relinks/matrix.json",
                    "top-level keys == ['meta', 'pairs']",
                    f"{sorted(mx.keys())}", "matrix doc shape")
    if len(nodes) != pins_fam["nodes"] or len(pairs) != pins_fam["cells"]:
        return pin_mismatch(ctx, "V-S7", "families.stage6.matrix.cells",
                            f'nodes={pins_fam["nodes"]} '
                            f'cells={pins_fam["cells"]}',
                            f"nodes={len(nodes)} cells={len(pairs)}")
    enums = ((mx.get("meta") or {}).get("enums")) or {}
    joinkey_vocab = set(enums.get("joinKey")
                        or pins_fam["joinKeyVocabulary"])
    mech_vocab = set(enums.get("mechanism") or [])
    status_vocab = set(enums.get("status") or [])
    base_keys = {"srcKind", "dstKind", "status", "mechanism", "joinKey",
                 "cardinality"}
    for idx, cell in enumerate(pairs):
        want_src = nodes[idx // len(nodes)]
        want_dst = nodes[idx % len(nodes)]
        if cell.get("srcKind") != want_src or cell.get("dstKind") != want_dst:
            return fail(ctx, "V-S7", "relinks/matrix.json",
                        f"pairs[{idx}] == ({want_src!r}, {want_dst!r}) "
                        "(row-major over nodeUniverse)",
                        f"({cell.get('srcKind')!r}, {cell.get('dstKind')!r})",
                        "programmatic permutation check")
        status = cell.get("status")
        required = base_keys | ({"unblock"} if status in
                                ("partial", "missing") else set())
        if status == "modeled":
            required |= {"pairFiles"}
        missing = required - set(cell.keys())
        if missing:
            return fail(ctx, "V-S7", f"matrix cell {want_src}->{want_dst}",
                        f"required keys {sorted(required)}",
                        f"missing {sorted(missing)}",
                        "per-status required keys")
        if status not in status_vocab:
            return fail(ctx, "V-S7", f"matrix cell {want_src}->{want_dst}",
                        f"status ∈ {sorted(status_vocab)}",
                        f"{status!r}", "frozen vocabulary")
        if cell.get("mechanism") not in mech_vocab:
            return fail(ctx, "V-S7", f"matrix cell {want_src}->{want_dst}",
                        f"mechanism ∈ {sorted(mech_vocab)}",
                        f"{cell.get('mechanism')!r}", "frozen vocabulary")
        if cell.get("joinKey") not in joinkey_vocab:
            return fail(ctx, "V-S7", f"matrix cell {want_src}->{want_dst}",
                        f"joinKey ∈ {sorted(joinkey_vocab)}",
                        f"{cell.get('joinKey')!r}", "frozen vocabulary")
    return ok(ctx, "V-S7", "relinks/matrix.json",
              f'{len(pairs)} cells row-major over {len(nodes)} nodes; '
              "per-status keys + vocabularies hold")


MINI_REPORT_KEYS = ["bundleUniverse", "counts", "duplicateKeys", "guidIndex",
                    "meta", "nullBundleAddresses"]
CU_ADDITIVE_KEY = "counterUnits"


def _require_superset(ctx: Ctx, vid: str, artifact: str, doc,
                      required: list[str], additive: set[str],
                      hint: str) -> Outcome | None:
    keys = set(doc.keys()) if isinstance(doc, dict) else set()
    missing = [k for k in required if k not in keys]
    unknown = [k for k in keys if k not in required and k not in additive]
    if missing:
        return fail(ctx, vid, artifact, f"fields ⊇ {required}",
                    f"missing {missing}", hint)
    if unknown:
        return fail(ctx, vid, artifact, f"unknown fields absent ≤ {sorted(additive)}",
                    f"unexpected {sorted(unknown)}", hint)
    return None


def vs8_report_shapes(ctx: Ctx) -> Outcome:
    o = stale_guarded(ctx, "V-S8", False)
    if o:
        return o
    mini = ctx.mini_report()
    if mini is None:
        return fail(ctx, "V-S8", cl.MINI_REPORT_REL,
                    "six-key schema present", "artifact absent",
                    "emit via stage 2 post-parse or --scan-catalog bootstrap")
    if sorted(mini.keys()) != MINI_REPORT_KEYS:
        return fail(ctx, "V-S8", cl.MINI_REPORT_REL,
                    f"top-level keys == {MINI_REPORT_KEYS}",
                    f"{sorted(mini.keys())}", "pinned six-key schema")
    sha = (mini.get("meta") or {}).get("catalogSha256")
    if not isinstance(sha, str) or not SHA256_RE.match(sha):
        return fail(ctx, "V-S8", f"{cl.MINI_REPORT_REL} meta.catalogSha256",
                    "64-hex sha256 digest present", f"{sha!r}",
                    "ties the sidecar to its source document")

    cov = ctx.coverage()
    r = _require_superset(ctx, "V-S8", "addressables/catalog-coverage.json",
                          cov,
                          ["keysTotal", "distinctBundlesReferenced",
                           "bundlesUnreferenced", "danglingDependencyKeys",
                           "outOfRosterFileReferences"], set(),
                          "coverage field list")
    if r:
        return r
    snap = ctx._load_json("addressables/settings.snapshot.json") or {}
    r = _require_superset(ctx, "V-S8", "addressables/settings.snapshot.json",
                          snap, ["parsed", "verbatim"], set(),
                          "snapshot field list")
    if r:
        return r

    overlay = ctx._load_json("locales/base-overlay-report.json") or {}
    r = _require_superset(
        ctx, "V-S8", "locales/base-overlay-report.json", overlay,
        ["compositionPolicy", "evidence"], {CU_ADDITIVE_KEY},
        "overlay report shape (+ counterUnits after RED-3)")
    if r:
        return r
    pol = overlay.get("compositionPolicy")
    policy_enum = ctx.pins["enums"]["overlay.compositionPolicy"]
    if pol not in policy_enum:
        return fail(ctx, "V-S8", "base-overlay-report.compositionPolicy",
                    f"∈ {policy_enum}", f"{pol!r}", "emitted 4-value enum")
    evidence = overlay.get("evidence") or {}
    missing_counters = [n for n in ctx.pins["families"]["stage4"][
        "evidenceCounterNames"] if n not in evidence]
    if missing_counters:
        return fail(ctx, "V-S8", "base-overlay-report.evidence",
                    f"counters ⊇ pinned {len(ctx.pins['families']['stage4']['evidenceCounterNames'])} names",
                    f"missing {missing_counters}",
                    "evidence counter names (superset allowed — RED-2 adds "
                    "duplicateKeysOverwritten)")

    bridge = ctx._load_json("relinks/guid_bridge_report.json") or {}
    r = _require_superset(ctx, "V-S8", "relinks/guid_bridge_report.json",
                          bridge, ctx.pins["families"]["stage6"][
                              "bridgeReportFields"],
                          {CU_ADDITIVE_KEY}, "bridge report field list")
    if r:
        return r
    join = ctx._load_json("relinks/locale_join_report.json") or {}
    r = _require_superset(ctx, "V-S8", "relinks/locale_join_report.json",
                          join, ctx.pins["families"]["stage6"][
                              "joinReportFields"],
                          {CU_ADDITIVE_KEY}, "join report field list")
    if r:
        return r
    ai = ctx._load_json("decompiled/structural/assembly-index.json") or {}
    meta_block = ai.get("meta") or {}
    need = {"buildId", "hierarchyCountMethod", "hierarchyRowCount",
            "hierarchySource"}
    if not need <= set(meta_block.keys()):
        return fail(ctx, "V-S8", "decompiled/structural/assembly-index.json",
                    f"stamp block ⊇ {sorted(need)}",
                    f"{sorted(meta_block.keys())}",
                    "hierarchy-equality evidence lives IN the artifact")
    return ok(ctx, "V-S8", "reports x6",
              "shapes conform (mini-report six-key schema included)")


def vs9_relation_ledger_rowshapes(ctx: Ctx) -> Outcome:
    o = stale_guarded(ctx, "V-S9", False)
    if o:
        return o
    specs = ctx.pins["families"]["relations"]

    def check(rel: str, required: list[str], optional: set[str] | None = None,
              predicate=None):
        opt = optional or set()
        for i, row in enumerate(ctx.jlines(rel)):
            keys = set(row.keys())
            if not (set(required) <= keys) or (keys - set(required) - opt):
                return fail(ctx, "V-S9", rel,
                            f"keyset ⊇ {sorted(required)} "
                            f"(optional {sorted(opt)})",
                            f"row[{i}] {sorted(keys)}", "relation rowshape")
            if predicate is not None:
                problem = predicate(i, row)
                if problem:
                    return fail(ctx, "V-S9", rel, problem[0], problem[1],
                                "declared vocabulary / discriminator")
        return None

    for rel, spec in specs.items():
        r = check(rel, spec["required"], set(spec.get("optional", [])),
                  spec.get("predicate") and _make_predicate(spec["predicate"]))
        if r:
            return r

    # competitor measured-shape legs (G5 pinned HERE): samples/terminal/
    # floorRequired/sourcesApplied/unblock present where measured; the
    # spec'd wall{} object occurs on 0 rows.
    comp = ctx.jlines("relinks/competitor_applied.jsonl")
    terminal = [r_ for r_ in comp if r_.get("terminal")]
    sampled = [r_ for r_ in comp if "samples" in r_]
    walls = [r_ for r_ in comp if "wall" in r_]
    if not sampled:
        return fail(ctx, "V-S9", "relinks/competitor_applied.jsonl",
                    "≥1 row carrying samples (measured shape)",
                    "none", "G5 supersession leg")
    if not terminal:
        return fail(ctx, "V-S9", "relinks/competitor_applied.jsonl",
                    "exactly 1 terminal floor-unmet row",
                    "none", "G5 supersession leg")
    t = terminal[0]
    for k in ("floorRequired", "sourcesApplied", "unblock"):
        if k not in t:
            return fail(ctx, "V-S9", "relinks/competitor_applied.jsonl",
                        f"terminal row carries {k}", "missing",
                        "measured terminal shape")
    if walls:
        return fail(ctx, "V-S9", "relinks/competitor_applied.jsonl",
                    'spec\'d wall{} object on 0 rows',
                    f"{len(walls)} row(s) carry it",
                    "piece-02 §R6 superseded-as-measured (RF-2)")

    # RED-1's new ledger is a DECLARED family whose shape pin activates when
    # the file exists (absent ⇒ V-L1 owns the complaint; no double red).
    uncontained_rel = "relinks/_uncontained_addresses.jsonl"
    out = Outcome()
    if ctx.has(uncontained_rel):
        spec = ctx.pins["families"]["ledgers"]["_uncontained_addresses"]
        r = check(uncontained_rel, spec["required"],
                  set(spec.get("optional", [])))
        if r:
            return r
    else:
        out.info("V-S9", f"ledger {uncontained_rel} absent — shape pin "
                         "dormant until the RED-1 amendment lands")
    out.primary = Ev("PASS", "V-S9", "relations + ledgers rowshapes conform")
    return out


def _make_predicate(name: str):
    if name == "entity_locale-locale-term":
        def p(_i, row):
            if row.get("dstKind") != "locale-term":
                return ('dstKind == "locale-term"', row.get("dstKind"))
            ev = row.get("evidence") or {}
            if not {"dev", "fieldPath", "locales", "termId"} <= set(ev):
                return ("evidence ⊇ dev/fieldPath/locales/termId",
                        sorted(ev))
            return None
        return p
    if name == "asset-guid":
        def p(_i, row):
            if row.get("dstKind") != "asset":
                return ('dstKind == "asset"', row.get("dstKind"))
            ev = row.get("evidence") or {}
            if not {"assetGuid", "fieldPath", "resolvedVia"} <= set(ev):
                return ("evidence ⊇ assetGuid/fieldPath/resolvedVia",
                        sorted(ev))
            return None
        return p
    return None


def vs10_filename_grammars(ctx: Ctx) -> Outcome:
    o = stale_guarded(ctx, "V-S10", True)
    if o:
        return o
    bad = 0
    first_bad = ""
    manifest = ctx.jlines("harvest/export-manifest.jsonl")
    for row in manifest:
        stem = str(row["outRelPath"]).replace("\\", "/").rsplit("/", 1)[-1]
        if tc.parse_harvest_stem(stem) is None:
            bad += 1
            first_bad = first_bad or stem
            if bad == 1:
                break
    if bad:
        return fail(ctx, "V-S10", "harvest/export-manifest.jsonl",
                    "every export stem matches _(\\|-)\\d+$",
                    f"{first_bad!r}", "signed-pathId grammar (Rev 6 lesson)")
    for tree in ("harvest/textassets", "harvest/monobehaviours"):
        root = ctx.extracted_root / tree
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if tc.parse_harvest_stem(path.name) is None:
                return fail(ctx, "V-S10", f"{tree}/…/{path.name}",
                            "filename matches <stem>_(|-)<digits>[.<ext>]",
                            path.name, "harvest tree grammar")
    owned = set(log_util.stage_outputs("relink"))
    owned |= set(ctx.pins["families"]["owned"]["relinks"])
    existing = set()
    relinks = ctx.extracted_root / "relinks"
    for path in relinks.rglob("*"):
        if path.is_file():
            existing.add(path.relative_to(ctx.extracted_root).as_posix())
    strays = sorted(existing - owned)
    if strays:
        return fail(ctx, "V-S10", "relinks/",
                    f"only the owned emission tree ({len(existing)} files)",
                    f"strays: {strays[:5]}",
                    "owned-set equality (sibling-spec files are never strays)")
    return ok(ctx, "V-S10", "filenames",
              f"{len(manifest)} stems conform; relinks owned-set holds")


def vs11_enum_domains(ctx: Ctx) -> Outcome:
    o = stale_guarded(ctx, "V-S11", True)
    if o:
        return o
    out = Outcome()
    declared_all = ctx.pins["enums"]
    cold_expected = ctx.pins["coldArms"]
    infos: list[str] = []

    occ: dict[str, set] = {}

    def add(family: str, value):
        s = occ.setdefault(family, set())
        s.add(json.dumps(value, ensure_ascii=False, sort_keys=True))

    for row in ctx.roster_rows():
        add("roster.dirClass", row["dirClass"])
        add("roster.sceneFlag", row["sceneFlag"])
    for kind, fname in ctx.pins["families"]["stage5"]["kindFiles"].items():
        for row in self_rows(ctx, fname):
            add("stub.method", row["method"])
            add("stub.kind", row["kind"])
            if "axes" in row:
                for a in row["axes"]:
                    add("stub.axes", a)
    for rows in ctx.pair_files().values():
        for row in rows:
            add("pair.method", row["method"])
    mx = ctx.matrix()
    for cell in mx.get("pairs") or []:
        add("matrix.mechanism", cell["mechanism"])
        add("matrix.status", cell["status"])
        add("matrix.joinKey", cell["joinKey"])
    for row in ctx.jlines("stubs/_absences.jsonl"):
        add("absences.absenceType", row.get("absenceType"))
    for row in ctx.jlines("stubs/_unmapped-families.jsonl"):
        ev = row.get("evidence") or ""
        add("_unmapped.evidence", ev.split(" — ")[0].split(" (")[0])
    for row in ctx.jlines("relinks/_dangling_guids.jsonl"):
        add("dangling.verdict", row["verdict"])
    for row in ctx.jlines("relinks/_unresolved_pptrs.jsonl"):
        add("pptrs.reason", row["reason"])
    for row in ctx.jlines("relinks/ui_link_coverage.jsonl"):
        add("ui.status", row["status"])
    reg = ctx.jlines("relinks/i2_term_registry.jsonl")
    for row in reg:
        add("registry.termType", row["termType"])
        add("registry.termStatus", row["termStatus"])
    for row in ctx.jlines("relinks/entity_asset_guid.jsonl"):
        add("asset.resolvedVia", (row.get("evidence") or {}).get("resolvedVia"))
    overlay = ctx._load_json("locales/base-overlay-report.json") or {}
    add("overlay.compositionPolicy", overlay.get("compositionPolicy"))
    media_classes = {str(r["class"]) for r in ctx.jlines(
        "media-catalogue.jsonl")}
    for m in media_classes:
        add("media.class", m)
    for r in ctx.jlines("media-catalogue.jsonl"):
        add("media.contentAxis", r["contentAxis"])
    kinds = ((ctx.mini_report() or {}).get("counts") or {}).get("kindCounts")
    if isinstance(kinds, dict):
        for k in kinds:
            add("catalog.kind", k)

    failures: list[str] = []
    for family, values in sorted(occ.items()):
        domain = set(declared_all.get(family, []))
        rendered_domain = {json.dumps(v, ensure_ascii=False, sort_keys=True)
                           for v in domain}
        off = sorted(values - rendered_domain)
        if off:
            failures.append(f"{family}: off-vocabulary {off[:3]}")
    if failures:
        return fail(ctx, "V-S11", "enum-bearing families",
                    "∀ values ∈ declared domain",
                    "; ".join(failures), "out-of-vocabulary FAILS")
    for family, arms in cold_expected.items():
        occurring = occ.get(family, set())
        rendered = {json.dumps(v, ensure_ascii=False, sort_keys=True)
                    for v in arms}
        if rendered & occurring:
            return fail(ctx, "V-S11", family,
                        f"arms expected cold: {sorted(rendered)}",
                        "one of them now OCCURRING",
                        "growth into an arm prints INFO, never silently — "
                        "update pins.coldArms")
    for family, arms in sorted(cold_expected.items()):
        infos.append(f"enum arm {arms!r} declared, 0 occurrences ({family})")
    el_methods = {(r.get("method")) for r in ctx.jlines(
        "relinks/entity_locale.jsonl")}
    if el_methods != {"i2-termid-registry"}:
        return fail(ctx, "V-S11", "relinks/entity_locale.jsonl",
                    'method == "i2-termid-registry" on all rows '
                    "(NEVER listed cold)",
                    f"{sorted(m for m in el_methods if m)}",
                    "F5 scoping correction")
    out.primary = Ev("PASS", "V-S11",
                     f"{len(occ)} enum families within declared domains")
    for text in infos:
        out.info("V-S11", text)
    return out


def vs12_buildid_coverage(ctx: Ctx) -> Outcome:
    build = ctx.identity.get("buildId")
    checked = 0
    offenders: list[str] = []

    def rows_check(rel: str):
        nonlocal checked
        for i, row in enumerate(ctx.jlines(rel)):
            checked += 1
            if row.get("buildId") != build:
                offenders.append(f"{rel} row[{i}]={row.get('buildId')}")

    for fname in ctx.pins["families"]["stage5"]["kindFiles"].values():
        rows_check("stubs/" + fname)
    for rel in ctx.pair_files():
        rows_check("relinks/" + rel)
    for rel in ("bundle-roster.jsonl", "relinks/i2_term_registry.jsonl",
                "relinks/entity_locale.jsonl",
                "relinks/locale_term_entity.jsonl",
                "relinks/entity_asset_guid.jsonl",
                "relinks/_dangling_guids.jsonl",
                "relinks/_unresolved_pptrs.jsonl",
                "relinks/ui_link_coverage.jsonl",
                "relinks/competitor_applied.jsonl",
                "stubs/_absences.jsonl",
                "relinks/bridges/cab_index.jsonl",
                "relinks/bridges/container_index.jsonl"):
        rows_check(rel)
    artifacts = {
        "relinks/matrix.json": lambda d: (d.get("meta") or {}).get("buildId"),
        "relinks/guid_bridge_report.json": lambda d: d.get("buildId"),
        "relinks/locale_join_report.json": lambda d: d.get("buildId"),
        "decompiled/structural/assembly-index.json":
            lambda d: (d.get("meta") or {}).get("buildId"),
        "locales/locale-matrix.json":
            lambda d: (d.get("meta") or {}).get("buildId"),
    }
    for rel, getter in artifacts.items():
        doc = ctx._load_json(rel)
        checked += 1
        if doc is None or getter(doc) != build:
            offenders.append(f"{rel}={None if doc is None else getter(doc)}")
    mini = ctx.mini_report()
    if mini is not None:
        checked += 1
        if (mini.get("meta") or {}).get("buildId") != build:
            offenders.append(
                f"{cl.MINI_REPORT_REL}={(mini.get('meta') or {}).get('buildId')}")
    if offenders:
        return fail(ctx, "V-S12", "buildId-bearing families",
                    f"100% == identity.buildId {build}",
                    f"{len(offenders)} offender(s): {offenders[:3]}",
                    "present ∧ == identity.buildId on every carrier")
    return ok(ctx, "V-S12", "buildId-bearing families",
              f"{checked} carriers all == {build}")


def vs13_sort_orders(ctx: Ctx) -> Outcome:
    o = stale_guarded(ctx, "V-S13", False)
    if o:
        return o

    def pair_key(r):
        return (str(r["srcKind"]), str(r["srcId"]), str(r["dstKind"]),
                str(r["dstId"]), str(r["method"]),
                str((r.get("evidence") or {}).get("fieldPath")))

    for fname, rows in sorted(ctx.pair_files().items()):
        keys = [pair_key(r) for r in rows]
        if keys != sorted(keys):
            return fail(ctx, "V-S13", f"relinks/{fname}",
                        "lexicographic by dedup tuple",
                        "unsorted at row "
                        f"{next(i for i in range(1, len(keys)) if keys[i - 1] > keys[i])}",
                        "pair sort contract")

    def check_sorted(rel: str, keyfn, label: str):
        keys = [keyfn(r) for r in ctx.jlines(rel)]
        if keys != sorted(keys):
            return fail(ctx, "V-S13", rel, f"lexicographic by {label}",
                        "unsorted", "sort-order pin")
        return None

    checks = [
        ("relinks/_unresolved_pptrs.jsonl",
         lambda r: (str(r["srcKind"]), str(r["srcId"]),
                    str(r["fieldPath"]), str(r["extPath"]),
                    int(r["m_PathID"])), "5-tuple"),
        ("relinks/_dangling_guids.jsonl", lambda r: str(r["assetGuid"]),
         "assetGuid"),
        ("bundle-roster.jsonl", lambda r: str(r["relpath"]), "relpath"),
        ("relinks/bridges/container_index.jsonl",
         lambda r: (str(r["bundle"]), str(r["address"])), "(bundle,address)"),
        ("relinks/bridges/cab_index.jsonl",
         lambda r: (str(r["bundle"]), str(r["cab"])), "(bundle,cab)"),
    ]
    if ctx.has("relinks/_uncontained_addresses.jsonl"):
        checks.append(("relinks/_uncontained_addresses.jsonl",
                       lambda r: str(r["address"]), "address"))
    for rel, fn, label in checks:
        r = check_sorted(rel, fn, label)
        if r:
            return r

    mini = ctx.mini_report()
    if mini is not None:
        arrays = [
            ("nullBundleAddresses",
             (mini.get("nullBundleAddresses") or [])),
            ("bundleUniverse.referencedRelpaths",
             ((mini.get("bundleUniverse") or {}).get("referencedRelpaths")
              or [])),
            ("bundleUniverse.bundlesUnreferenced",
             ((mini.get("bundleUniverse") or {}).get("bundlesUnreferenced")
              or [])),
            ("bundleUniverse.outOfRosterFileReferences",
             ((mini.get("bundleUniverse") or {})
              .get("outOfRosterFileReferences") or [])),
        ]
        for label, arr in arrays:
            if list(arr) != sorted(arr):
                return fail(ctx, "V-S13", f"mini-report {label}",
                            "sorted array", "unsorted",
                            "sidecar determinism")
        gi = mini.get("guidIndex") or {}
        if list(gi.keys()) != sorted(gi.keys()):
            return fail(ctx, "V-S13", "mini-report guidIndex",
                        "sorted object keys", "unsorted",
                        "sidecar determinism")
    return ok(ctx, "V-S13", "sorted families x9", "all sorted")


# ---------------------------------------------------------------------------
# Invariant pins (V-I)

def vi1_natural_key_uniqueness(ctx: Ctx) -> Outcome:
    o = stale_guarded(ctx, "V-I1", True)
    if o:
        return o
    problems: list[str] = []

    def dup(label: str, values) -> int:
        seen = set()
        dups = 0
        for v in values:
            if v in seen:
                dups += 1
                if dups == 1:
                    problems.append(f"{label}: duplicate {v!r}")
            seen.add(v)
        return dups

    for kind, fname in ctx.pins["families"]["stage5"]["kindFiles"].items():
        dup(f"stub id[{kind}]", (str(r["id"]) for r in self_rows(ctx, fname)))
    dup("roster.relpath", (r["relpath"] for r in ctx.roster_rows()))
    dup("export-manifest.outRelPath",
        (r["outRelPath"] for r in ctx.jlines("harvest/export-manifest.jsonl")))
    dup("container.address",
        (r["address"] for r in ctx.jlines(
            "relinks/bridges/container_index.jsonl")))
    dup("cab.(bundle,cab)",
        ((r["bundle"], r["cab"]) for r in ctx.jlines(
            "relinks/bridges/cab_index.jsonl")))
    dup("externals.(bundle,sourceFile)",
        ((r["bundle"], r["sourceFile"]) for r in ctx.jlines(
            "harvest/externals.jsonl")))
    locales_dir = ctx.extracted_root / "locales"
    locale_lines = 0
    for name in sorted(p.name for p in locales_dir.glob("*.jsonl")):
        ids = []
        for row in cl.iter_jsonl(locales_dir / name):
            ids.append(row.get("id"))
        locale_lines += len(ids)
        dup(f"locale id[{name}]", ids)
    dup("registry.termId",
        (r["termId"] for r in ctx.jlines("relinks/i2_term_registry.jsonl")))

    def dedup_tuple(r):
        return (r["srcKind"], r["srcId"], r["dstKind"], r["dstId"],
                r["method"], (r.get("evidence") or {}).get("fieldPath"))

    for fname, rows in sorted(ctx.pair_files().items()):
        dup(f"pair dedup tuple[{fname}]", (dedup_tuple(r) for r in rows))
    if problems:
        return fail(ctx, "V-I1", "natural keys", "duplicates == 0 per key",
                    f"{len(problems)} duplicate class(es): {problems[:3]}",
                    "uniqueness domains")
    return ok(ctx, "V-I1", "natural keys x9 classes",
              f"0 duplicates (Σ locale lines {locale_lines})")


def vi2_catalog_duplicate_exception(ctx: Ctx) -> Outcome:
    o = stale_guarded(ctx, "V-I2", True)
    if o:
        return o
    mini = ctx.mini_report()
    if mini is None:
        return fail(ctx, "V-I2", cl.MINI_REPORT_REL, "sidecar present",
                    "absent", "heavy-artifact policy")
    counts = mini.get("counts") or {}
    dupes = mini.get("duplicateKeys") or []
    pin = ctx.pins["families"]["stage2"]
    total_minus_distinct = counts.get("keysTotal", 0) - \
        counts.get("distinctKeys", 0)
    overflow = sum(e.get("rowCount", 0) - 1 for e in dupes)
    if overflow != total_minus_distinct:
        return fail(ctx, "V-I2", f"{cl.MINI_REPORT_REL} counts",
                    "distinct(key) == rows − Σ(dupes−1)",
                    f"keysTotal−distinctKeys={total_minus_distinct} but "
                    f"dupe overflow={overflow}",
                    "duplicate-key arithmetic")
    if len(dupes) != pin["duplicateKeyCount"]:
        return pin_mismatch(ctx, "V-I2",
                            "families.stage2.duplicateKeyCount",
                            pin["duplicateKeyCount"], len(dupes))
    d = dupes[0]
    if d.get("rowCount", 0) < 2 or not d.get("rowsByteIdentical"):
        return fail(ctx, "V-I2", f"{cl.MINI_REPORT_REL} duplicateKeys",
                    "≥2 rows, canonical-JSON byte-identical",
                    json.dumps(d, sort_keys=True)[:160],
                    "legal Addressables duplicate registration")
    if d.get("key") != pin["duplicateKeyValue"]:
        return pin_mismatch(ctx, "V-I2", "families.stage2.duplicateKeyValue",
                            pin["duplicateKeyValue"], d.get("key"))
    return ok(ctx, "V-I2", f"{cl.MINI_REPORT_REL}",
              f'{counts.get("keysTotal")}/{counts.get("distinctKeys")} '
              f'keys/distinct; dupe {d.get("key")} ×{d.get("rowCount")} '
              "byte-identical")


def vi3_ui_coverage_xor(ctx: Ctx) -> Outcome:
    o = stale_guarded(ctx, "V-I3", True)
    if o:
        return o
    mapped = gap = violations = 0
    first = ""
    for row in ctx.jlines("relinks/ui_link_coverage.jsonl"):
        joins = row.get("joins") or []
        gap_reason = row.get("gapReason")
        unblock = row.get("unblock")
        if row.get("status") == "mapped-schema":
            mapped += 1
            if not joins or gap_reason or unblock:
                violations += 1
                first = first or json.dumps(row, sort_keys=True)[:160]
        elif row.get("status") == "documented-gap":
            gap += 1
            if joins or not gap_reason or not unblock:
                violations += 1
                first = first or json.dumps(row, sort_keys=True)[:160]
        else:
            violations += 1
            first = first or json.dumps(row, sort_keys=True)[:160]
    if violations:
        return fail(ctx, "V-I3", "relinks/ui_link_coverage.jsonl",
                    "mapped XOR gap with gapReason+unblock on gaps only",
                    f"{violations} violation(s): {first}",
                    "status XOR gate")
    pin = ctx.pins["families"]["stage6"]["uiCoverage"]
    if mapped != pin["mappedSchema"] or gap != pin["documentedGap"]:
        return pin_mismatch(ctx, "V-I3", "families.stage6.uiCoverage",
                            f'mapped={pin["mappedSchema"]} '
                            f'gap={pin["documentedGap"]}',
                            f"mapped={mapped} gap={gap}")
    return ok(ctx, "V-I3", "relinks/ui_link_coverage.jsonl",
              f"XOR holds ({mapped} mapped / {gap} gap)")


def vi4_matrix_structural_rules(ctx: Ctx) -> Outcome:
    o = stale_guarded(ctx, "V-I4", False)
    if o:
        return o
    violations = []
    for cell in ctx.matrix().get("pairs") or []:
        status = cell.get("status")
        if status in ("partial", "missing") and not cell.get("unblock"):
            violations.append(f'{cell["srcKind"]}->{cell["dstKind"]} '
                              "partial/missing without unblock")
        if status == "modeled" and not (cell.get("pairFiles") or []):
            violations.append(f'{cell["srcKind"]}->{cell["dstKind"]} '
                              "modeled without pairFiles")
    if violations:
        return fail(ctx, "V-I4", "relinks/matrix.json",
                    "unblock on partial∨missing; pairFiles on modeled",
                    f"{violations[:3]}", "structural rules")
    return ok(ctx, "V-I4", "relinks/matrix.json", "structural rules hold")


def vi5_twin_bijection(ctx: Ctx) -> Outcome:
    o = stale_guarded(ctx, "V-I5", True)
    if o:
        return o
    twins_by_kind: dict[str, int] = {}
    fields_id_by_kind: dict[str, int] = {}
    breaks: list[str] = []
    for kind, fname in ctx.pins["families"]["stage5"]["kindFiles"].items():
        for row in self_rows(ctx, fname):
            is_twin = bool(TWIN_RE.search(str(row["id"])))
            has_fid = isinstance((row.get("fields") or {}).get("id"), str) \
                and bool((row["fields"]).get("id"))
            if is_twin:
                twins_by_kind[kind] = twins_by_kind.get(kind, 0) + 1
                bare = re.sub(r"@[0-9a-fA-F]{8}$", "", str(row["id"]))
                if (row["fields"] or {}).get("id") != bare:
                    breaks.append(
                        f"{kind}:{row['id']} fields.id "
                        f"{(row['fields'] or {}).get('id')!r} != "
                        f"suffix-stripped {bare!r}")
            if has_fid:
                fields_id_by_kind[kind] = fields_id_by_kind.get(kind, 0) + 1
            if is_twin != has_fid:
                breaks.append(f"{kind}:{row['id']} twin⇔fields.id violated "
                              f"(twin={is_twin}, fields.id={has_fid})")
    if breaks:
        return fail(ctx, "V-I5", "stubs/*.jsonl",
                    "id ∋ @<8hex> ⟺ fields.id present ∧ equal to stripped",
                    f"{breaks[:2]}", "twin bijection")
    pin = ctx.pins["families"]["stage5"]["twinsByKind"]
    measured = {k: v for k, v in twins_by_kind.items() if v}
    if measured != pin:
        return pin_mismatch(ctx, "V-I5", "families.stage5.twinsByKind",
                            pin, measured)
    total_twins = sum(twins_by_kind.values())
    total_fields = sum(fields_id_by_kind.values())
    if total_twins != total_fields:
        return fail(ctx, "V-I5", "stubs/*.jsonl",
                    f"{total_twins} ⇔ {total_fields}", "counts differ",
                    "17 ⇔ 17 bijection")
    return ok(ctx, "V-I5", "stubs/*.jsonl",
              f"{total_twins} ⇔ {total_fields} twins/fields.id "
              f"({', '.join(f'{k} {v}' for k, v in sorted(measured.items()))})")


def vi6_byte_match_nonempty(ctx: Ctx) -> Outcome:
    section = ctx.last_run_section("emit-stub-datasets")
    if section is None:
        return fail(ctx, "V-I6", "EXTRACTION-LOG emit-stub-datasets section",
                    "identifierByteMatch line present", "section absent",
                    "Rev 6 amendment 3 incident guard")
    lines, _header = section
    checked = mismatches = None
    for line in lines:
        m = re.search(r"identifierByteMatch:\s*checked=(\d+)\s+"
                      r"mismatches=(\d+)", line)
        if m:
            checked, mismatches = int(m.group(1)), int(m.group(2))
    if checked is None:
        return fail(ctx, "V-I6", "EXTRACTION-LOG emit-stub-datasets section",
                    "identifierByteMatch line present", "not found",
                    "Rev 6 amendment 3 incident guard")
    if checked <= 0 or mismatches != 0:
        return fail(ctx, "V-I6", "EXTRACTION-LOG emit-stub-datasets section",
                    "checked > 0 ∧ mismatches == 0",
                    f"checked={checked} mismatches={mismatches}",
                    "silent-pass regression guard")
    return ok(ctx, "V-I6", "EXTRACTION-LOG emit-stub-datasets section",
              f"checked={checked} mismatches=0")


def vi7_sample_caps(ctx: Ctx) -> Outcome:
    o = stale_guarded(ctx, "V-I7", True)
    if o:
        return o
    caps = ctx.pins["sampleCaps"]
    over: list[str] = []
    for row in ctx.jlines("relinks/_dangling_guids.jsonl"):
        if len(row.get("sampleRefs") or []) > caps["danglingSampleRefs"]:
            over.append(f'_dangling_guids {row["assetGuid"]}')
    join = ctx._load_json("relinks/locale_join_report.json") or {}
    for entry in join.get("unresolvedIds") or []:
        if len(entry.get("sampleRefs") or []) > caps[
                "joinUnresolvedSampleRefs"]:
            over.append(f'locale_join_report termId {entry.get("termId")}')
    for row in ctx.jlines("stubs/_absences.jsonl"):
        if len(row.get("samples") or []) > caps["absenceSamples"]:
            over.append(f'_absences {row.get("kind")}')
    if over:
        return fail(ctx, "V-I7", "sample arrays",
                    f"lengths ≤ {caps}", f"{over[:3]}",
                    "samples are bounded evidence, never census")
    return ok(ctx, "V-I7", "sample arrays",
              "caps hold (≤5 · ≤5 · ≤25)")


def vi8_exitcode_ledger_contract(ctx: Ctx) -> Outcome:
    o = stale_guarded(ctx, "V-I8", False)
    if o:
        return o
    members = ctx.pins["exitCodeContributors"]["members"]
    sizes = _computed_contributor_sizes(ctx)
    nonempty = {name for name, size in sizes.items() if size > 0}

    section = ctx.last_run_section("relink")
    if section is None:
        return fail(ctx, "V-I8", "EXTRACTION-LOG relink section",
                    "last relink run section present", "absent",
                    "exit-code ledger contract")
    lines, _hdr = section
    exit_code = None
    for line in lines:
        m = re.match(r"-\s*exitCode:\s*(\d+)", line)
        if m:
            exit_code = int(m.group(1))
    if exit_code is None:
        return fail(ctx, "V-I8", "EXTRACTION-LOG relink section",
                    "exitCode line present", "not found", "contract leg c")
    want_code = 2 if nonempty else 0
    if exit_code != want_code:
        return fail(ctx, "V-I8", "EXTRACTION-LOG relink section",
                    f"exitCode == {want_code} iff declared set "
                    f"{sorted(nonempty)} non-empty",
                    f"exitCode={exit_code} with non-empty={sorted(nonempty)}",
                    "exit 2 iff the declared contributor set is non-empty")
    named: dict[str, str] = {}
    for line in lines:
        if line.strip().startswith("- LEDGER-CONTRIBUTORS"):
            payload = line.split("(exit 2):", 1)[-1]
            for token in _split_outside_parens(payload, ";"):
                if not token:
                    continue
                member = None
                for prefix, name in (
                        ("_dangling_guids.jsonl", "dangling-guids-open"),
                        ("_unresolved_pptrs", "unresolved-pptrs"),
                        ("_uncontained_addresses", "uncontained-addresses"),
                        ("registryMisses", "registry-misses"),
                        ("competitor floor unmet", "competitor-floor-unmet"),
                        ("outOfRosterFileReferences",
                         "catalog-out-of-roster-or-dangling"),
                        ("bridge-unreadable bundles",
                         "bridge-unreadable-bundles"),
                ):
                    if token.startswith(prefix):
                        member = name
                        break
                if member is None:
                    return fail(ctx, "V-I8",
                                "EXTRACTION-LOG relink section",
                                f"every named contributor ∈ {sorted(members)}",
                                f"undeclared token {token!r}",
                                "run section names an undeclared contributor")
                named[member] = token
    problems = []
    for member, token in sorted(named.items()):
        if member not in members and member != "bridge-unreadable-bundles":
            problems.append(f"{token!r} not a §7 declared contributor")
            continue
        m = re.search(r":\s*(\d+)\s*$", token)
        if m and member in sizes:
            spelled = int(m.group(1))
            if member == "competitor-floor-unmet":
                continue
            if spelled != sizes[member]:
                problems.append(f"{token!r} spells {spelled}, measured "
                                f"{sizes[member]}")
    if problems:
        return fail(ctx, "V-I8", "EXTRACTION-LOG relink section",
                    "named contributors consistent with computed sizes",
                    "; ".join(problems[:3]),
                    "declared-vs-computed desync (watch item 1: implemented "
                    "against the ACTUAL log spelling)")
    return ok(ctx, "V-I8", "exit-code ledger contract",
              f"exitCode {exit_code} iff {sorted(nonempty)}; run section "
              f"names {len(named)} declared contributor(s)")


def _split_outside_parens(payload: str, sep: str) -> list[str]:
    """Split on `sep` only at paren-depth 0 — the run section spells
    contributors with embedded semicolons inside parentheses
    (`competitor floor unmet (<3 applied sources; terminal ledger row
    ~floor)`)."""
    toks: list[str] = []
    buf = ""
    depth = 0
    for ch in payload:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        if ch == sep and depth == 0:
            toks.append(buf.strip())
            buf = ""
        else:
            buf += ch
    if buf.strip():
        toks.append(buf.strip())
    return [t for t in toks if t]


def _computed_contributor_sizes(ctx: Ctx) -> dict[str, int]:
    sizes: dict[str, int] = {}
    sizes["dangling-guids-open"] = sum(
        1 for r in ctx.jlines("relinks/_dangling_guids.jsonl")
        if r.get("verdict") == "unresolved-open")
    sizes["unresolved-pptrs"] = len(
        ctx.jlines("relinks/_unresolved_pptrs.jsonl"))
    sizes["uncontained-addresses"] = \
        len(ctx.jlines("relinks/_uncontained_addresses.jsonl")) \
        if ctx.has("relinks/_uncontained_addresses.jsonl") else 0
    join = ctx._load_json("relinks/locale_join_report.json") or {}
    sizes["registry-misses"] = int(join.get("registryMisses") or 0)
    cov = ctx.coverage()
    dd = (cov.get("danglingDependencyKeys") or {}).get("count") or 0
    oor = (cov.get("outOfRosterFileReferences") or {}).get("count") or 0
    sizes["catalog-out-of-roster-or-dangling"] = int(dd) + int(oor)
    terminal = any(r.get("terminal") for r in
                   ctx.jlines("relinks/competitor_applied.jsonl"))
    sizes["competitor-floor-unmet"] = 1 if terminal else 0
    return sizes


def vi9_ownership_exactly_one_writer(ctx: Ctx) -> Outcome:
    sources: dict[str, str] = {}
    for path in sorted(ctx.tools_dir.glob("stage*.py")):
        try:
            sources[path.name] = path.read_text(encoding="utf-8")
        except OSError:
            continue
    problems: list[str] = []
    checked = 0
    for rel, entry in sorted(ctx.pins["pathOwner"]["paths"].items()):
        checked += 1
        candidates = []
        for script, pattern in entry.get("writers", []):
            src = sources.get(script)
            if src is not None and re.search(pattern, src):
                candidates.append(script)
        expect = entry.get("expect")
        if len(candidates) > 1:
            problems.append(f"{rel}: TWO concurrent writers {candidates} "
                            "(mid-handover hazard)")
        elif len(candidates) == 0:
            problems.append(f"{rel}: ZERO writers (half-applied handover)")
        elif expect and candidates[0] != expect:
            problems.append(f"{rel}: writer {candidates[0]} != canonical "
                            f"{expect}")
    if problems:
        return fail(ctx, "V-I9", "pins.pathOwner",
                    "exactly ONE writer per mapped path",
                    "; ".join(problems[:3]),
                    "INVARIANT, not incumbent (RF-1; handover-aware)")
    return ok(ctx, "V-I9", "pins.pathOwner",
              f"{checked} mapped paths each have exactly one writer")


# ---------------------------------------------------------------------------
# Cross-family pins (V-X)

def vx1_stub_id_closure(ctx: Ctx) -> Outcome:
    o = stale_guarded(ctx, "V-X1", True)
    if o:
        return o
    light = ctx.stub_index()
    misses: list[str] = []
    checked = 0
    special = {"locale-term", "asset", "scene"}
    for fname, rows in sorted(ctx.pair_files().items()):
        for row in rows:
            checked += 1
            sk, dk = str(row["srcKind"]), str(row["dstKind"])
            if str(row["srcId"]) not in light.get(sk, {}):
                misses.append(f'{fname}:{row["srcKind"]}/{row["srcId"]}')
            if dk not in special and str(row["dstId"]) not in light.get(dk, {}):
                misses.append(f'{fname}:{row["dstKind"]}/{row["dstId"]}')
    if misses:
        return fail(ctx, "V-X1", "pairs ↔ stubs",
                    f"0 misses / {checked}", f"{len(misses)} miss(es) "
                    f"{misses[:3]}",
                    "twins matched WITH suffix (ids stored verbatim)")
    return ok(ctx, "V-X1", "pairs ↔ stubs", f"0 misses / {checked}")


def vx2_special_dstkind_closure(ctx: Ctx) -> Outcome:
    out = Outcome()
    misses: list[str] = []
    term_ids = {str(r["dstId"]) for rows in ctx.pair_files().values()
                for r in rows if r["dstKind"] == "locale-term"}
    keys = ctx.registry_keys()
    misses += [f"locale-term/{t}" for t in sorted(term_ids - keys)]

    scene_files = [f for f in ctx.pair_files()
                   if f.split("_")[0] in ctx.node_universe()
                   and f[:-len(".jsonl")].split("_")[1] == "scene"]
    scene_ids = {str(r["dstId"]) for rows in ctx.pair_files().values()
                 for r in rows if r["dstKind"] == "scene"}
    if scene_ids or scene_files:
        roster_scenes = {r["relpath"] for r in ctx.roster_rows()
                         if r.get("sceneFlag", "none") != "none"}
        misses += [f"scene/{s}" for s in sorted(scene_ids - roster_scenes)]
    else:
        out.info("V-X2", "dstKind 'scene' unexercised (no *_scene.jsonl) — "
                         "absence tolerated (scout G7)")

    asset_rows = [r for r in ctx.jlines("relinks/entity_asset_guid.jsonl")]
    containers = ctx.container_addresses()
    edge_rows = [r for r in asset_rows
                 if str(r["dstId"]) not in containers]
    carve_out = {str(r["dstId"]) for r in edge_rows}
    mini = ctx.mini_report() or {}
    null_bundle = set(mini.get("nullBundleAddresses") or [])
    outside = sorted(carve_out - null_bundle)
    if outside:
        misses += [f"asset/{a}" for a in outside]

    fam = ctx.pins["families"]["stage6"].get("uncontainedCarveOut", {})
    if carve_out and fam:
        if len(carve_out) != fam.get("addresses") or \
                len(edge_rows) != fam.get("edgeRows"):
            pm = pin_mismatch(ctx, "V-X2",
                              "families.stage6.uncontainedCarveOut",
                              f'addresses={fam.get("addresses")} '
                              f'edgeRows={fam.get("edgeRows")}',
                              f"addresses={len(carve_out)} "
                              f"edgeRows={len(edge_rows)}")
            pm.infos.extend(out.infos)
            return pm
    ledger_rel = "relinks/_uncontained_addresses.jsonl"
    if ctx.has(ledger_rel):
        ledger_addrs = {str(r["address"])
                        for r in ctx.jlines(ledger_rel)}
        if ledger_addrs != carve_out:
            return _with_infos(fail(
                ctx, "V-X2", ledger_rel,
                "ledger population == carve-out set exactly",
                f"ledger-only={sorted(ledger_addrs - carve_out)[:3]} "
                f"carve-out-only={sorted(carve_out - ledger_addrs)[:3]}",
                "carve-out set == _uncontained_addresses population"),
                out.infos)
    else:
        out.info("V-X2", f"ledger {ledger_rel} absent — equality leg dormant "
                         "(RED-1 pending; V-L1 owns the complaint)")
    if misses:
        r = fail(ctx, "V-X2", "pairs ↔ registry/container/roster/sidecar",
                 "0 misses", f"{len(misses)} miss(es) {misses[:3]}",
                 "special-dstkind closure")
        r.infos.extend(out.infos)
        return r
    out.primary = Ev("PASS", "V-X2", "special dstKinds close; carve-out "
                     f"{len(carve_out)} addresses / {len(edge_rows)} edge rows")
    return out


def _with_infos(o: Outcome, infos) -> Outcome:
    o.infos.extend(infos)
    return o


def vx3_bundle_name_closure(ctx: Ctx) -> Outcome:
    o = stale_guarded(ctx, "V-X3", True)
    if o:
        return o

    def norm(name) -> str:
        return str(name).replace("\\", "/").rsplit("/", 1)[-1].casefold()

    roster_names = {norm(r["relpath"]) for r in ctx.roster_rows()}
    groups: dict[str, set] = {
        "stub source.bundle": set(),
        "manifest sourceBundle": set(),
        "pair evidence bundles": set(),
    }
    groups["stub source.bundle"] = ctx.stub_light_bundles()
    for row in ctx.jlines("harvest/export-manifest.jsonl"):
        groups["manifest sourceBundle"].add(norm(row["sourceBundle"]))
    for rows in ctx.pair_files().values():
        for row in rows:
            ev = row.get("evidence") or {}
            for k in ("srcBundle", "dstBundle"):
                if ev.get(k):
                    groups["pair evidence bundles"].add(norm(ev[k]))
    counts = {k: len(v) for k, v in groups.items()}
    orphans: list[str] = []
    for label, bundles in groups.items():
        for b in sorted(bundles):
            if b not in roster_names:
                orphans.append(f"{label}:{b}")
    pin = ctx.pins["families"]["stage6"]["bundleClosure"]
    if orphans:
        return fail(ctx, "V-X3", "bundle references",
                    "normalized basename ∈ roster relpaths",
                    f"{len(orphans)} orphan(s): {orphans[:3]}",
                    "bundle-name closure")
    drift = {k: v for k, v in counts.items() if pin.get(k) not in (None, v)}
    if drift:
        return pin_mismatch(ctx, "V-X3", "families.stage6.bundleClosure",
                            pin, counts)
    return ok(ctx, "V-X3", "bundle references",
              "0 orphans ("
              + ", ".join(f"{k.split()[0]} {v}" for k, v in sorted(counts.items()))
              + ")")


def vx4_axes_consistency(ctx: Ctx) -> Outcome:
    o = stale_guarded(ctx, "V-X4", True)
    if o:
        return o
    light = ctx.stub_index()
    carriers = 0
    violations: list[str] = []
    for fname, rows in sorted(ctx.pair_files().items()):
        for row in rows:
            axes_endpoints = []
            for k, i in ((str(row["srcKind"]), str(row["srcId"])),
                         (str(row["dstKind"]), str(row["dstId"]))):
                meta = light.get(k, {}).get(i)
                if meta is not None and meta.get("axes"):
                    axes_endpoints.extend(meta["axes"])
            union = sorted(set(axes_endpoints))
            if "sourceAxes" in row:
                carriers += 1
                if sorted(row["sourceAxes"]) != union or not union:
                    violations.append(
                        f'{fname}:{row["srcId"]}->{row["dstId"]} '
                        f'sourceAxes={row["sourceAxes"]} endpoint union={union}')
            elif union:
                violations.append(
                    f'{fname}:{row["srcId"]}->{row["dstId"]} endpoints carry '
                    f"axes {union} without sourceAxes")
    pin = ctx.pins["families"]["stage6"]["sourceAxesCarrierRows"]
    if violations:
        return fail(ctx, "V-X4", "pairs ↔ stubs",
                    "sourceAxes ⟺ ≥1 endpoint carries axes ∧ value == union",
                    f"{violations[:2]}", "axes consistency")
    if carriers != pin:
        return pin_mismatch(ctx, "V-X4",
                            "families.stage6.sourceAxesCarrierRows",
                            pin, carriers)
    return ok(ctx, "V-X4", "pairs ↔ stubs",
              f"holds on the {carriers} carrier row(s)")


# ---------------------------------------------------------------------------
# Counter-unit pins (V-U)

UNIT_VOCAB_FALLBACK = ["bytes", "deduped-rows", "distinct-keys",
                       "emission-events", "objects", "reference-events",
                       "skipped-cells", "walked-terms"]


def _numeric_leaves(obj, prefix="", depth=0, out=None):
    if out is None:
        out = []
    if isinstance(obj, bool):
        return out
    if isinstance(obj, dict):
        if depth >= 3:
            return out
        for k, v in obj.items():
            p = f"{prefix}.{k}" if prefix else str(k)
            _numeric_leaves(v, p, depth + 1, out)
        return out
    if isinstance(obj, (int, float)):
        out.append(prefix)
    return out


def _covered(path: str, cu_keys: set) -> bool:
    if path in cu_keys:
        return True
    parts = path.split(".")
    for i in range(1, len(parts)):
        if ".".join(parts[:i]) + ".*" in cu_keys:
            return True
    return False


def vu1_units_inline_in_artifacts(ctx: Ctx) -> Outcome:
    o = stale_guarded(ctx, "V-U1", False)
    if o:
        return o
    vocab = set(ctx.pins.get("unitVocabulary") or UNIT_VOCAB_FALLBACK)
    exempt = set(ctx.pins.get("counterUnitExemptFields") or ["buildId"])
    artifacts = [
        "addressables/catalog-coverage.json",
        "locales/base-overlay-report.json",
        "relinks/guid_bridge_report.json",
        "relinks/locale_join_report.json",
    ]
    problems: list[str] = []
    for rel in artifacts:
        doc = ctx._load_json(rel)
        if doc is None:
            problems.append(f"{rel}: artifact absent")
            continue
        cu = doc.get("counterUnits")
        if not isinstance(cu, dict) or not cu:
            problems.append(f"{rel}: counterUnits ABSENT")
            continue
        bad_units = sorted({str(v) for v in cu.values()} - vocab)
        if bad_units:
            problems.append(f"{rel}: unit(s) outside frozen vocabulary "
                            f"{bad_units}")
        required = [p for p in _numeric_leaves(doc)
                    if p.split(".")[-1] not in exempt
                    and not p.startswith("counterUnits")]
        uncovered = [p for p in required if not _covered(p, set(cu))]
        if uncovered:
            problems.append(f"{rel}: {len(uncovered)} numeric field(s) "
                            f"without a unit, e.g. {uncovered[:3]}")
    bridge = ctx._load_json("relinks/guid_bridge_report.json") or {}
    cu = bridge.get("counterUnits") or {}
    for field in ("guidRefsTotal", "resolvedToAddress", "resolvedToStub",
                  "resolveRateAddress", "resolveRateStub"):
        if cu and cu.get(field) != "reference-events":
            problems.append(f"guid_bridge_report.{field} must declare "
                            f"'reference-events' (got {cu.get(field)!r})")
    if problems:
        return fail(ctx, "V-U1", "counterUnits in four reports",
                    "present · vocabulary-complete · covers every numeric "
                    "field",
                    f"{len(problems)} problem(s): {problems[:4]}",
                    "units live IN the artifact (§6 item 1; RED-3)")
    return ok(ctx, "V-U1", "counterUnits in four reports",
              "vocab-complete across every numeric field")


def vu2_duplicate_keys_printed_and_persisted(ctx: Ctx) -> Outcome:
    o = stale_guarded(ctx, "V-U2", True)
    if o:
        return o
    section = ctx.last_run_section("localisation")
    if section is None:
        return fail(ctx, "V-U2", "EXTRACTION-LOG localisation section",
                    "run section present", "absent", "counter surface")
    lines, _hdr = section
    terms_walked = None
    ev_total_events = None
    for line in lines:
        m = re.match(r"-\s*compositionPolicy:\s*\S+\s*\(evidence:\s*(.*)\)\s*$",
                     line.strip())
        if m:
            import ast
            try:
                evidence = ast.literal_eval(m.group(1))
            except (ValueError, SyntaxError):
                continue
            terms_walked = evidence.get("registryTerms")
            ev_total_events = evidence.get("localeRowsEmittedTotal")
    printed: dict[str, dict] = {}
    unmatched: list[str] = []
    pat = re.compile(
        r"^-\s*(?P<label>\S+):\s*rows=(?P<rows>\d+)\(emission-events\)\s+"
        r"skippedEmpty=(?P<se>\d+)\s+skippedAbsent=(?P<sa>\d+)"
        r"(?P<mid>.*?)duplicateKeysOverwritten=(?P<dup>\d+)")
    for line in lines:
        m = pat.match(line.strip())
        if m:
            printed[m.group("label")] = m.groupdict()
        elif re.match(r"^-\s*(?:BASE-OVERLAY|"
                      + "|".join(re.escape(c) for c in tc.EMITTED_LOCALES)
                      + r"):\s*rows=", line.strip()):
            unmatched.append(line.strip()[:120])
    if not printed or unmatched:
        return fail(ctx, "V-U2", "EXTRACTION-LOG localisation run section",
                    "per-locale rows(emission-events) + "
                    "duplicateKeysOverwritten printed",
                    f"{len(printed)} parsed / {len(unmatched)} unparsed, "
                    f"first unparsed: {unmatched[:1]}",
                    "counter invisible today (F9) — RED-2 amendment prints "
                    "it beside the unit annotation")
    problems = []
    for label, d in sorted(printed.items()):
        rows, se, sa, dup = (int(d["rows"]), int(d["se"]), int(d["sa"]),
                             int(d["dup"]))
        if terms_walked is None:
            problems.append("registryTerms not parseable from the evidence "
                            "line")
            break
        want = terms_walked - sa if label == "BASE-OVERLAY" \
            else terms_walked - se - sa
        if rows != want:
            problems.append(f"{label}: rowsLogged {rows} != walked "
                            f"{terms_walked} − skipped {se + sa}")
        file_lines = ctx.locale_file_lines(label)
        if dup != rows - file_lines:
            problems.append(f"{label}: duplicateKeysOverwritten {dup} != "
                            f"logged {rows} − fileLines {file_lines}")
    overlay = ctx._load_json("locales/base-overlay-report.json") or {}
    evidence = overlay.get("evidence") or {}
    persisted = evidence.get("duplicateKeysOverwritten")
    if not isinstance(persisted, dict) or \
            "byLocale" not in persisted or "total" not in persisted:
        problems.append("base-overlay-report.evidence."
                        "duplicateKeysOverwritten (per-locale map + total) "
                        "not persisted")
    else:
        by_locale = persisted["byLocale"]
        for label in tc.EMITTED_LOCALES:
            want = printed.get(label, {}).get("dup")
            got = by_locale.get(label)
            if want is None or got is None or int(want) != int(got):
                problems.append(f"persisted map[{label}]={got} != printed "
                                f"{want}")
        if int(persisted["total"]) != sum(
                int(v) for v in by_locale.values()):
            problems.append("persisted total != Σ map")
    if ev_total_events is not None and printed:
        events_sum = sum(int(d["rows"]) for lbl, d in printed.items()
                         if lbl != "BASE-OVERLAY")
        if events_sum != int(ev_total_events):
            problems.append(f"Σ per-locale events {events_sum} != "
                            f"localeRowsEmittedTotal {ev_total_events}")
    if problems:
        return fail(ctx, "V-U2", "duplicateKeysOverwritten surfaces",
                    "printed AND persisted; both identities hold per locale",
                    f"{len(problems)} problem(s): {problems[:3]}",
                    "F9 bridge (RED-2); mixed-unit identity licensed by "
                    "events-minus-distinct-lines")
    return ok(ctx, "V-U2", "duplicateKeysOverwritten surfaces",
              f"{len(printed)} labels printed+persisted, identities hold "
              f"(+{printed.get('de', {}).get('dup', '?')}/locale class)")


def vu3_unit_typed_reconciliations(ctx: Ctx) -> Outcome:
    o = stale_guarded(ctx, "V-U3", False)
    if o:
        return o
    vocab = set(ctx.pins.get("unitVocabulary") or UNIT_VOCAB_FALLBACK)
    problems = []
    for rec in ctx.pins.get("reconciliations", []):
        lu, ru_ = rec.get("leftUnit"), rec.get("rightUnit")
        if lu not in vocab or ru_ not in vocab:
            problems.append(f'{rec.get("id")}: unit outside vocabulary')
        if lu != ru_ and rec.get("transform") not in ctx.transforms:
            problems.append(f'{rec.get("id")}: mixes {lu}/{ru_} without a '
                            "registered transform")
    if problems:
        return fail(ctx, "V-U3", "pins.reconciliations",
                    "typed units; differing units carry registered transforms",
                    f"{problems[:2]}", "naive rows==wc-l pins are forbidden")
    n_mixed = sum(1 for r in ctx.pins.get("reconciliations", [])
                  if r.get("leftUnit") != r.get("rightUnit"))
    return ok(ctx, "V-U3", "pins.reconciliations",
              f"{n_mixed} mixed-unit registration(s), all transform-licensed")


# ---------------------------------------------------------------------------
# Ledger-gap pins (V-L)

def vl1_uncontained_address_ledger(ctx: Ctx) -> Outcome:
    o = stale_guarded(ctx, "V-L1", True)
    if o:
        return o
    containers = ctx.container_addresses()
    edges = [r for r in ctx.jlines("relinks/entity_asset_guid.jsonl")
             if str(r["dstId"]) not in containers]
    addrs = {str(r["dstId"]) for r in edges}
    mini = ctx.mini_report() or {}
    null_bundle = set(mini.get("nullBundleAddresses") or [])
    reason = ctx.pins["families"]["ledgers"]["_uncontained_addresses"][
        "reason"]
    ledger_rel = "relinks/_uncontained_addresses.jsonl"
    if not ctx.has(ledger_rel):
        return fail(ctx, "V-L1", ledger_rel,
                    f"ledger present: {len(addrs)} rows covering "
                    f"{len(edges)} edge rows",
                    "ledger MISSING today",
                    "address-terminal uncontained GUID terminations are "
                    "silent (F12/RED-1)")
    rows = ctx.jlines(ledger_rel)
    problems = []
    ledger_addrs = {str(r["address"]) for r in rows}
    if ledger_addrs != addrs:
        problems.append(f"population mismatch: ledger-only="
                        f"{sorted(ledger_addrs - addrs)[:3]} "
                        f"edge-only={sorted(addrs - ledger_addrs)[:3]}")
    for r in rows:
        if r.get("reason") != reason:
            problems.append(f'{r.get("address")}: reason '
                            f"{r.get('reason')!r} != {reason!r}")
    covered = set()
    for r in rows:
        for ref in r.get("sampleRefs") or []:
            covered.add(str(ref.get("srcKind")))
    if not addrs <= ledger_addrs:
        problems.append("some uncontained address lacks its ledger row")
    fam = ctx.pins["families"]["stage6"].get("uncontainedCarveOut", {})
    if fam:
        if len(rows) != fam.get("addresses") or \
                len(edges) != fam.get("edgeRows"):
            return pin_mismatch(ctx, "V-L1",
                                "families.stage6.uncontainedCarveOut",
                                f'rows={fam.get("addresses")} '
                                f'edges={fam.get("edgeRows")}',
                                f"rows={len(rows)} edges={len(edges)}")
    if problems:
        return fail(ctx, "V-L1", ledger_rel,
                    f"{fam.get('addresses')} rows covering "
                    f"{fam.get('edgeRows')} edges, reason pinned",
                    "; ".join(problems[:3]), "RED-1 green condition")
    return ok(ctx, "V-L1", ledger_rel,
              f"{len(rows)} rows cover {len(edges)} edge rows over "
              f"{len(addrs)} addresses ({len(null_bundle)} null-bundle "
              "catalog addresses consulted)")


def vl2_ledger_sorts_and_shapes(ctx: Ctx) -> Outcome:
    o = stale_guarded(ctx, "V-L2", True)
    if o:
        return o
    pin = ctx.pins["families"]["stage6"]["ledgers"]
    reasons: dict[str, int] = {}
    for r in ctx.jlines("relinks/_unresolved_pptrs.jsonl"):
        reasons[r["reason"]] = reasons.get(r["reason"], 0) + 1
    want_reasons = pin["pptrReasonCounts"]
    if reasons != want_reasons:
        return pin_mismatch(ctx, "V-L2",
                            "families.stage6.ledgers.pptrReasonCounts",
                            want_reasons, reasons)
    verdict_vocab = set(ctx.pins["enums"]["dangling.verdict"])
    verdicts: dict[str, int] = {}
    for r in ctx.jlines("relinks/_dangling_guids.jsonl"):
        v = r["verdict"]
        if v not in verdict_vocab:
            return fail(ctx, "V-L2", "relinks/_dangling_guids.jsonl",
                        f"verdicts ⊆ {sorted(verdict_vocab)}", repr(v),
                        "declared 4-value enum")
        verdicts[v] = verdicts.get(v, 0) + 1
    if verdicts.get("unresolved-open") != \
            pin["danglingUnresolvedOpen"]:
        return pin_mismatch(ctx, "V-L2",
                            "families.stage6.ledgers.danglingUnresolvedOpen",
                            pin["danglingUnresolvedOpen"],
                            verdicts.get("unresolved-open"))
    return ok(ctx, "V-L2", "ledgers",
              f'pptr reasons {sum(reasons.values())}='
              f'{ "+".join(str(v) for v in reasons.values()) }; '
              f'dangling {verdicts.get("unresolved-open")} all unresolved-open')


def vl3_registry_misses_exit2_contributor(ctx: Ctx) -> Outcome:
    o = stale_guarded(ctx, "V-L3", True)
    if o:
        return o
    join = ctx._load_json("relinks/locale_join_report.json") or {}
    pin = ctx.pins["families"]["stage6"]["joinReport"]
    if join.get("registryMisses") != pin["registryMisses"]:
        return pin_mismatch(ctx, "V-L3",
                            "families.stage6.joinReport.registryMisses",
                            pin["registryMisses"], join.get("registryMisses"))
    ids = join.get("unresolvedIds") or []
    if len(ids) != pin["unresolvedIdCount"]:
        return pin_mismatch(ctx, "V-L3",
                            "families.stage6.joinReport.unresolvedIdCount",
                            pin["unresolvedIdCount"], len(ids))
    cap = ctx.pins["sampleCaps"]["joinUnresolvedSampleRefs"]
    for e in ids:
        if len(e.get("sampleRefs") or []) > cap:
            return fail(ctx, "V-L3", "locale_join_report.unresolvedIds",
                        f"sampleRefs ≤ {cap}",
                        f'termId {e.get("termId")} over cap',
                        "bounded samples")
    members = ctx.pins["exitCodeContributors"]["members"]
    if "registry-misses" not in members:
        return fail(ctx, "V-L3", "pins.exitCodeContributors.members",
                    "registry-misses inventoried as a §7 contributor",
                    "absent", "surfaced via locale_join_report.json")
    return ok(ctx, "V-L3", "relinks/locale_join_report.json",
              f'registryMisses={pin["registryMisses"]} counted as exit-2 '
              "contributor")


# ---------------------------------------------------------------------------
# Doc/routing pins (V-D)

def vd1_availability_routing_note(ctx: Ctx) -> Outcome:
    o = stale_guarded(ctx, "V-D1", False)
    if o:
        return o
    doc_pins = ctx.pins["docPins"]
    stmt = doc_pins["routingStatement"]
    proj = doc_pins["faithfulProjection"]
    targets = [
        ("contracts/families/exceptions.mdx",
         ctx.contracts_dir / "families" / "exceptions.mdx"),
        ("extracted/RELATIONS.md", ctx.extracted_root / "RELATIONS.md"),
    ]
    problems = []
    for label, path in targets:
        if not path.is_file():
            problems.append(f"{label}: file absent")
            continue
        text = path.read_text(encoding="utf-8")
        if stmt not in text:
            problems.append(f"{label}: routing statement absent")
        if proj not in text:
            problems.append(f"{label}: faithful-projection sentence absent")
    if problems:
        return fail(ctx, "V-D1", "availability-routing note",
                    f"both files contain the pinned statement + projection",
                    f"{len(problems)} problem(s): {problems[:2]}",
                    "consumers must be told before building loaders "
                    "(G4; RELATIONS.md leg = RED-3 bundle)")
    return ok(ctx, "V-D1", "availability-routing note",
              "present in exceptions sheet + RELATIONS.md")


def vd2_exception_sheet_numbers(ctx: Ctx) -> Outcome:
    o = stale_guarded(ctx, "V-D2", True)
    if o:
        return o
    sheet = ctx.contracts_dir / "families" / "exceptions.mdx"
    if not sheet.is_file():
        return fail(ctx, "V-D2", "contracts/families/exceptions.mdx",
                    "exception sheet ships with the layer", "file absent",
                    "four §5 exceptions")
    text = sheet.read_text(encoding="utf-8")
    problems = []
    for exc in ctx.pins["exceptions"]:
        if exc["anchor"] not in text:
            problems.append(f'{exc["id"]}: anchor missing')
            continue
        for num in exc["numbers"]:
            if str(num) not in text:
                problems.append(f'{exc["id"]}: number {num} not interpolated')
    if problems:
        return fail(ctx, "V-D2", "contracts/families/exceptions.mdx",
                    "anchors + interpolated numbers equal their pins",
                    f"{problems[:3]}", "sheet ↔ pins.json")
    return ok(ctx, "V-D2", "contracts/families/exceptions.mdx",
              f'{len(ctx.pins["exceptions"])} exceptions pinned with numbers')


def vd3_pins_blocks_sync(ctx: Ctx) -> Outcome:
    o = stale_guarded(ctx, "V-D3", True)
    if o:
        return o
    mapping = ctx.pins["docPins"]["familyBlocks"]
    problems = []
    for fname, slice_name in sorted(mapping.items()):
        path = ctx.contracts_dir / "families" / fname
        if not path.is_file():
            problems.append(f"{fname}: family contract absent")
            continue
        text = path.read_text(encoding="utf-8")
        blocks = re.findall(r"```pins\s*\n(.*?)```", text, re.DOTALL)
        if not blocks:
            problems.append(f"{fname}: no ```pins block")
            continue
        try:
            rendered = json.loads(blocks[0])
        except json.JSONDecodeError as exc:
            problems.append(f"{fname}: pins block does not parse ({exc})")
            continue
        want = ctx.pins["families"][slice_name]
        if cl.canonical_json(rendered) != cl.canonical_json(want):
            problems.append(f"{fname}: pins block != pins.families."
                            f"{slice_name} (stale prose numbers)")
    if problems:
        return fail(ctx, "V-D3", "contracts/families/*.mdx",
                    "canonical sorted-keys JSON equality per family",
                    f"{problems[:3]}", "generated-and-checked layer")
    return ok(ctx, "V-D3", "contracts/families/*.mdx",
              f"{len(mapping)} pins blocks canonically equal their slices")


def vd4_buildscope_freshness(ctx: Ctx, warn_stale: bool = False) -> Outcome:
    if ctx.build_matches_scope():
        return ok(ctx, "V-D4", "identity.json ↔ pins.buildScope",
                  f"both at {ctx.identity.get('buildId')}")
    if warn_stale:
        o = Outcome()
        o.primary = Ev("INFO", "V-D4",
                       f"PIN-STALE downgraded by --warn-stale: corpus at "
                       f"{ctx.identity.get('buildId')}, pins scoped to "
                       f"{ctx.pins['buildScope']['buildId']}")
        return o
    return pin_stale(ctx, "V-D4")


# ---------------------------------------------------------------------------
# Reconciliation pins (V-R)

def vr1_matrix_edges_pair_rows(ctx: Ctx) -> Outcome:
    o = stale_guarded(ctx, "V-R1", False)
    if o:
        return o
    edges_sum = sum(int(((c.get("cardinality")) or {}).get("edges") or 0)
                    for c in ctx.matrix().get("pairs") or [])
    pair_rows = sum(len(rows) for rows in ctx.pair_files().values())
    if edges_sum != pair_rows:
        return fail(ctx, "V-R1", "matrix.cells ↔ pair files",
                    f"Σ cardinality.edges == Σ pair rows",
                    f"{edges_sum} != {pair_rows}", "arithmetic identity")
    return ok(ctx, "V-R1", "matrix.cells ↔ pair files",
              f"{edges_sum} == {pair_rows}")


def vr2_cab_census(ctx: Ctx) -> Outcome:
    o = stale_guarded(ctx, "V-R2", False)
    if o:
        return o
    cab_objects = sum(len(r.get("objects") or []) for r in ctx.jlines(
        "relinks/bridges/cab_index.jsonl"))
    census_dir = ctx.extracted_root / "harvest" / "census" / "bundles"
    census_objects = 0
    files = 0
    fallback_true = 0
    for path in sorted(census_dir.glob("*.json")) if census_dir.is_dir() else []:
        doc = json.loads(path.read_text(encoding="utf-8"))
        files += 1
        census_objects += sum(doc.get("objectsByClass").values())
        if doc.get("fallbackVersionUsed") is True:
            fallback_true += 1
    if cab_objects != census_objects:
        return fail(ctx, "V-R2", "cab_index ↔ census",
                    "Σ objectsByClass == Σ cab objects",
                    f"{cab_objects} != {census_objects}",
                    "identity over the serialized-file universe")
    return ok(ctx, "V-R2", "cab_index ↔ census",
              f"{census_objects} == {census_objects} over {files} files "
              f"(fallbackVersionUsed:true on {fallback_true})")


def vr3_media_carved_census(ctx: Ctx) -> Outcome:
    o = stale_guarded(ctx, "V-R3", False)
    if o:
        return o
    media: dict[str, int] = {}
    for r in ctx.jlines("media-catalogue.jsonl"):
        media[r["class"]] = media.get(r["class"], 0) + 1
    census_dir = ctx.extracted_root / "harvest" / "census" / "bundles"
    census: dict[str, int] = {}
    for path in sorted(census_dir.glob("*.json")) if census_dir.is_dir() else []:
        doc = json.loads(path.read_text(encoding="utf-8"))
        for cls, n in (doc.get("objectsByClass") or {}).items():
            census[cls] = census.get(cls, 0) + int(n)
    carved = {c: n for c, n in census.items()
              if c in tc.CARVE_OUT_CLASSES and n > 0}
    drift = {c: (media.get(c, 0), n) for c, n in carved.items()
             if media.get(c, 0) != n}
    extra = sorted(set(media) - set(carved))
    if drift or extra:
        return fail(ctx, "V-R3", "media-catalogue ↔ carved census",
                    f"per-class equality on {len(carved)} classes",
                    f"drift={drift} extra-classes={extra[:3]}",
                    "media rows cover every carved-class object")
    return ok(ctx, "V-R3", "media-catalogue ↔ carved census",
              f"equal on all {len(carved)} classes")


def vr4_registry_matrix_keys(ctx: Ctx) -> Outcome:
    o = stale_guarded(ctx, "V-R4", True)
    if o:
        return o
    reg = ctx.registry_keys()
    matrix_doc = ctx._load_json("locales/locale-matrix.json") or {}
    keys = set((matrix_doc.get("keys") or {}).keys())
    only_reg = sorted(reg - keys)
    only_matrix = sorted(keys - reg)
    if only_reg or only_matrix:
        return fail(ctx, "V-R4", "i2_term_registry ↔ locale-matrix",
                    "bidirectional set diff == 0",
                    f"registry-only={only_reg[:3]} "
                    f"matrix-only={only_matrix[:3]}",
                    "key universes agree")
    return ok(ctx, "V-R4", "i2_term_registry ↔ locale-matrix",
              f"diff == 0 both ways over {len(reg)} distinct termKeys")


def vr5_reverse_index_entity_locale(ctx: Ctx) -> Outcome:
    o = stale_guarded(ctx, "V-R5", False)
    if o:
        return o
    usages = sum(len(r.get("usages") or []) for r in ctx.jlines(
        "relinks/locale_term_entity.jsonl"))
    rows = len(ctx.jlines("relinks/entity_locale.jsonl"))
    if usages != rows:
        return fail(ctx, "V-R5", "reverse index ↔ entity_locale",
                    "Σ usages == row count", f"{usages} != {rows}",
                    "reverse index reconciles exactly")
    return ok(ctx, "V-R5", "reverse index ↔ entity_locale",
              f"{usages} == {rows}")


def vr6_catalog_mini_internal(ctx: Ctx) -> Outcome:
    o = stale_guarded(ctx, "V-R6", True)
    if o:
        return o
    mini = ctx.mini_report()
    if mini is None:
        return fail(ctx, "V-R6", cl.MINI_REPORT_REL, "sidecar present",
                    "absent", "heavy-artifact policy")
    counts = mini.get("counts") or {}
    universe = mini.get("bundleUniverse") or {}
    cov = ctx.coverage()
    problems = []
    if sum(counts.get("kindCounts", {}).values()) != counts.get("keysTotal"):
        problems.append("keysTotal != Σ kindCounts")
    dupe_overflow = sum(e.get("rowCount", 0) - 1
                        for e in mini.get("duplicateKeys") or [])
    if counts.get("distinctKeys") != counts.get("keysTotal") - dupe_overflow:
        problems.append("distinctKeys arithmetic off")
    nb = counts.get("nullBundleRows") or {}
    if nb.get("total") != nb.get("guidKind", 0) + nb.get("addressKind", 0):
        problems.append("nullBundleRows split does not sum")
    roster_set = {r["relpath"] for r in ctx.roster_rows()}
    ref_paths = universe.get("referencedRelpaths") or []
    if not set(ref_paths) <= roster_set:
        problems.append("referencedRelpaths escape the roster")
    if cov.get("distinctBundlesReferenced") != len(ref_paths):
        problems.append("referencedRelpaths != coverage.distinctBundles"
                        "Referenced")
    if (universe.get("bundlesUnreferenced") or []) != \
            (cov.get("bundlesUnreferenced") or []):
        problems.append("bundlesUnreferenced disagrees with catalog-coverage")
    dd = (cov.get("danglingDependencyKeys") or {}).get("count")
    if len(universe.get("danglingDependencyKeys") or []) != (dd or 0):
        problems.append("danglingDependencyKeys disagrees with coverage")
    oor = (cov.get("outOfRosterFileReferences") or {}).get("count")
    if len(universe.get("outOfRosterFileReferences") or []) != (oor or 0):
        problems.append("outOfRosterFileReferences disagrees with coverage")
    gi = mini.get("guidIndex") or {}
    if gi and not all(GUID32_RE.match(g) for g in list(gi)[:50]):
        problems.append("guidIndex keys are not lowercase 32-hex guids")
    if problems:
        return fail(ctx, "V-R6", cl.MINI_REPORT_REL,
                    "internal sums + catalog-coverage agreement (zero "
                    "catalog touch)",
                    f"{problems[:3]}", "sidecar internal consistency")
    return ok(ctx, "V-R6", cl.MINI_REPORT_REL,
              f'internal sums hold at keysTotal={counts.get("keysTotal")} '
              f"({len(ref_paths)} referenced relpaths; zero catalog touch)")


def vr7_roster_enumerated_bundles(ctx: Ctx) -> Outcome:
    o = Outcome()
    game_root = ctx.game_root
    if game_root is None or not Path(game_root).is_dir():
        o.info("V-R7", "client-gated leg skipped hostless (game dir not "
                       "given) — filesystem enumeration runs on NE8K")
        o.primary = Ev("PASS", "V-R7", "roster ↔ enumerated bundles "
                                        "(hostless skip)")
        return o
    paths = tc.game_paths(Path(game_root))
    enumerated = [(rel, cls) for rel, cls, _p in
                  tc.enumerate_bundle_files(paths)]
    rows = ctx.roster_rows()
    row_map = {r["relpath"]: r["dirClass"] for r in rows}
    missing = [rel for rel, _cls in enumerated if rel not in row_map]
    extra = [rel for rel in row_map if rel not in
             {rel2 for rel2, _c in enumerated}]
    class_drift = [(rel, cls, row_map[rel]) for rel, cls in enumerated
                   if rel in row_map and row_map[rel] != cls]
    if missing or extra or class_drift:
        return _with_infos(fail(
            ctx, "V-R7", "bundle-roster ↔ filesystem",
            "row set == enumerated *.bundle set; dirClass == dir",
            f"missing={missing[:2]} extra={extra[:2]} "
            f"class-drift={class_drift[:2]}",
            "enumeration identity"), o.infos)
    expected = ctx.identity.get("expectedBundles") or {}
    by_class: dict[str, int] = {}
    for _rel, cls in enumerated:
        key = "aa" if cls == "base" else cls  # expectedBundles spells the
        # aa dir 'aa'; the roster dirClass vocabulary spells it 'base'
        by_class[key] = by_class.get(key, 0) + 1
    if by_class != expected:
        o.info("V-R7", f"live counts {by_class} differ from expectedBundles "
                       f"{expected} — DRIFT-warning semantics, never a gate")
    o.primary = Ev("PASS", "V-R7",
                   f"{len(rows)} rows == {len(enumerated)} enumerated bundles")
    return o


def vr8_guid_bridge_replay(ctx: Ctx) -> Outcome:
    o = stale_guarded(ctx, "V-R8", False)
    if o:
        return o
    mini = ctx.mini_report()
    if mini is None:
        return fail(ctx, "V-R8", "guid bridge replay", "sidecar present",
                    "absent", "CLIENT-GATED lane replays off guidIndex")
    import relink_util as ru

    stubs = ru.load_stubs(ctx.extracted_root / "stubs")
    # The pure seam takes a PLANE (bare bundle filename, pathId) →
    # (kind, id): container_index spells bundle as the BARE filename WITH
    # its .bundle extension and stub source.bundle uses the same spelling,
    # so the raw (un-normalized) rows key it directly.
    stub_plane: dict[tuple[str, int], tuple[str, str]] = {}
    for kind, rows in stubs.rows_by_kind.items():
        for row in rows:
            src = row.get("source") or {}
            b = str(src.get("bundle") or "")
            pid = src.get("pathId")
            if not b or pid is None:
                continue
            stub_plane[(b, int(pid))] = (kind, str(row["id"]))
    refs = []
    for kind in ru.STUB_KINDS:
        for row in sorted(stubs.rows_by_kind.get(kind, []),
                          key=lambda r: str(r["id"])):
            for raw_path, guid, sub in ru.walk_guid_refs(
                    row.get("fields") or {}):
                refs.append({
                    "srcKind": kind,
                    "srcId": str(row["id"]),
                    "fieldPath": raw_path,
                    "assetGuid": guid,
                    **({"subObjectName": sub} if sub else {}),
                })
    catalog_keys = [
        {"key": g, "kind": "guid", "address": e.get("address"),
         "bundle": None}
        for g, entries in sorted((mini.get("guidIndex") or {}).items())
        for e in entries
    ]
    container_rows = ctx.jlines("relinks/bridges/container_index.jsonl")
    scene_bundles = {r["relpath"] for r in ctx.roster_rows()
                     if r.get("sceneFlag", "none") != "none"}
    replay = ru.run_guid_bridge(refs, catalog_keys, container_rows,
                                stub_plane,
                                scene_bundles=scene_bundles,
                                buildId=ctx.identity.get("buildId"))
    emitted = ctx._load_json("relinks/guid_bridge_report.json") or {}
    problems = []
    rep = replay["report"]
    for field, value in rep.items():
        if emitted.get(field) != value:
            problems.append(f"{field}: replayed {value!r} != emitted "
                            f"{emitted.get(field)!r}")
    asset_membership = {(r["srcKind"], str(r["srcId"]), str(r["dstId"]))
                        for r in replay["assetRows"]}
    emitted_asset_rows = ctx.jlines("relinks/entity_asset_guid.jsonl")
    emitted_assets = {(r["srcKind"], str(r["srcId"]), str(r["dstId"]))
                      for r in emitted_asset_rows}
    if asset_membership != emitted_assets or \
            len(replay["assetRows"]) != len(emitted_asset_rows):
        problems.append(f"asset-row universe differs: replayed "
                        f"{len(replay['assetRows'])} rows / "
                        f"{len(asset_membership)} tuples vs emitted "
                        f"{len(emitted_asset_rows)} rows / "
                        f"{len(emitted_assets)} tuples")
    replay_pairs = {(r["srcKind"], str(r["srcId"]), str(r["dstKind"]),
                     str(r["dstId"]),
                     (r.get("evidence") or {}).get("fieldPath"))
                    for r in replay["pairRows"]}
    emitted_pairs = set()
    for rows in ctx.pair_files().values():
        for r in rows:
            if r.get("method") == "assetguid-catalog":
                emitted_pairs.add((
                    r["srcKind"], str(r["srcId"]), r["dstKind"],
                    str(r["dstId"]),
                    (r.get("evidence") or {}).get("fieldPath")))
    if replay_pairs != emitted_pairs:
        problems.append(f"pair-row universe differs: replayed "
                        f"{len(replay_pairs)} vs emitted {len(emitted_pairs)}")
    if problems:
        return fail(ctx, "V-R8", "guid-bridge replay",
                    "7 fields bit-exact (floats included) + universes "
                    "reproduced",
                    f"{problems[:3]}",
                    "pure seam relink_util.run_guid_bridge over sidecar "
                    "guidIndex")
    return ok(ctx, "V-R8", "guid-bridge replay",
              f'bit-exact ({rep.get("guidRefsTotal")} refs / '
              f'{rep.get("resolveRateAddress")} rate; '
              f"{len(asset_membership)} asset rows, "
              f"{len(replay_pairs)} pair rows)")


# ---------------------------------------------------------------------------
# Dispatch + main

def build_dispatch() -> dict:
    d = {
        "V-S1": vs1_identity_keyset,
        "V-S2": vs2_roster_envelope,
        "V-S3": vs3_stub_envelope,
        "V-S4": vs4_pair_envelope,
        "V-S5": vs5_locale_rowshape,
        "V-S6": vs6_flat_rowshapes,
        "V-S7": vs7_matrix_cellshape,
        "V-S8": vs8_report_shapes,
        "V-S9": vs9_relation_ledger_rowshapes,
        "V-S10": vs10_filename_grammars,
        "V-S11": vs11_enum_domains,
        "V-S12": vs12_buildid_coverage,
        "V-S13": vs13_sort_orders,
        "V-I1": vi1_natural_key_uniqueness,
        "V-I2": vi2_catalog_duplicate_exception,
        "V-I3": vi3_ui_coverage_xor,
        "V-I4": vi4_matrix_structural_rules,
        "V-I5": vi5_twin_bijection,
        "V-I6": vi6_byte_match_nonempty,
        "V-I7": vi7_sample_caps,
        "V-I8": vi8_exitcode_ledger_contract,
        "V-I9": vi9_ownership_exactly_one_writer,
        "V-X1": vx1_stub_id_closure,
        "V-X2": vx2_special_dstkind_closure,
        "V-X3": vx3_bundle_name_closure,
        "V-X4": vx4_axes_consistency,
        "V-U1": vu1_units_inline_in_artifacts,
        "V-U2": vu2_duplicate_keys_printed_and_persisted,
        "V-U3": vu3_unit_typed_reconciliations,
        "V-L1": vl1_uncontained_address_ledger,
        "V-L2": vl2_ledger_sorts_and_shapes,
        "V-L3": vl3_registry_misses_exit2_contributor,
        "V-D1": vd1_availability_routing_note,
        "V-D2": vd2_exception_sheet_numbers,
        "V-D3": vd3_pins_blocks_sync,
        "V-D4": lambda c: vd4_buildscope_freshness(c, c.warn_stale),
        "V-R1": vr1_matrix_edges_pair_rows,
        "V-R2": vr2_cab_census,
        "V-R3": vr3_media_carved_census,
        "V-R4": vr4_registry_matrix_keys,
        "V-R5": vr5_reverse_index_entity_locale,
        "V-R6": vr6_catalog_mini_internal,
        "V-R7": vr7_roster_enumerated_bundles,
        "V-R8": vr8_guid_bridge_replay,
    }
    assert sorted(d) == sorted(VALIDATOR_IDS), (
        f"validator catalog drifted: {len(d)} implementations vs "
        f"{len(VALIDATOR_IDS)} ids")
    return d


def stub_light_bundles(self: Ctx) -> set:
    """distinct normalized stub source.bundle spellings (V-X3 group)."""

    def norm(name) -> str:
        return str(name).replace("\\", "/").rsplit("/", 1)[-1].casefold()

    return {norm(meta.get("bundle"))
            for kind_map in self.stub_index().values()
            for meta in kind_map.values()
            if meta.get("bundle")}


Ctx.stub_light_bundles = stub_light_bundles  # type: ignore[attr-defined]


def unit_gate(ctx: Ctx) -> None:
    """V-U3's LOAD-TIME refusal (piece-05 §6 item 4): fires BEFORE any
    validator runs — there is no code path left that can express the naive
    pin."""
    vocab = set(ctx.pins.get("unitVocabulary") or UNIT_VOCAB_FALLBACK)
    for rec in ctx.pins.get("reconciliations", []):
        lu, ru_ = rec.get("leftUnit"), rec.get("rightUnit")
        if lu not in vocab or ru_ not in vocab:
            raise UnitGateRefusal(
                f"reconciliation '{rec.get('id')}' declares unit(s) outside "
                f"the frozen vocabulary {sorted(vocab)}")
        if lu != ru_ and rec.get("transform") not in ctx.transforms:
            raise UnitGateRefusal(
                f"reconciliation '{rec.get('id')}' mixes units {lu!r}/{ru_!r} "
                f"without a transform registered in "
                f"contracts/counter-units.mdx (registered: "
                f"{sorted(ctx.transforms)})")


REQUIRED_INPUTS = [
    "identity.json",
    "EXTRACTION-LOG.md",
    "bundle-roster.jsonl",
    cl.MINI_REPORT_REL,
    "addressables/catalog-coverage.json",
    "addressables/settings.snapshot.json",
    "decompiled/structural/assembly-index.json",
    "harvest/export-manifest.jsonl",
    "harvest/externals.jsonl",
    "media-catalogue.jsonl",
    "locales/base-overlay-report.json",
    "locales/locale-matrix.json",
    "stubs/_absences.jsonl",
    "stubs/_unmapped-families.jsonl",
    "relinks/matrix.json",
    "relinks/entity_asset_guid.jsonl",
    "relinks/guid_bridge_report.json",
    "relinks/_dangling_guids.jsonl",
    "relinks/_unresolved_pptrs.jsonl",
    "relinks/i2_term_registry.jsonl",
    "relinks/entity_locale.jsonl",
    "relinks/locale_term_entity.jsonl",
    "relinks/locale_join_report.json",
    "relinks/ui_link_coverage.jsonl",
    "relinks/competitor_applied.jsonl",
    "relinks/bridges/cab_index.jsonl",
    "relinks/bridges/container_index.jsonl",
]


def check_inputs(extracted_root: Path, need_sidecar: bool = True) -> list[str]:
    required = [rel for rel in REQUIRED_INPUTS if rel != cl.MINI_REPORT_REL
                or need_sidecar]
    missing = [rel for rel in required
               if not (extracted_root / rel).is_file()]
    for code in tc.EMITTED_LOCALES:
        rel = f"locales/{code}.jsonl"
        if not (extracted_root / rel).is_file() and rel not in missing:
            missing.append(rel)
    if not (extracted_root / "locales/base-overlay.jsonl").is_file():
        missing.append("locales/base-overlay.jsonl")
    if not (extracted_root / "stubs").is_dir():
        missing.append("stubs/")
    return missing


def run_scan_catalog(ctx: Ctx, events: list[Ev]) -> bool:
    """--scan-catalog audit lane: stream catalog.json ONCE (sha256 + byte
    size accumulate in the SAME pass through contracts_lib.stream_catalog),
    rebuild the ENTIRE mini-report through the shared derivation, and
    canonical-JSON byte-compare it against the persisted sidecar.
    Bootstrap-writes the sidecar when absent — the only write this tool can
    ever make under extracted/. Returns False when the suite must exit 1."""
    catalog_path = ctx.extracted_root / "addressables/catalog.json"
    if not catalog_path.is_file():
        events.append(Ev("FAIL", "V-I2", "addressables/catalog.json "
                         "expected=present measured=absent "
                         "hint=--scan-catalog audit lane"))
        return False
    holder = {"meta": {}, "sha": "", "size": 0}
    rows: list[dict] = []
    for event, payload in cl.stream_catalog(catalog_path):
        if event == "row":
            rows.append(payload)
        else:
            holder["meta"] = payload.meta
            holder["sha"] = payload.sha256
            holder["size"] = payload.size_bytes

    rebuilt = cl.derive_mini_report(
        rows,
        [r["relpath"] for r in ctx.roster_rows()],
        ctx.coverage(), holder["size"], holder["sha"], meta=holder["meta"])
    rebuilt_bytes = cl.render_mini_report(rebuilt)
    persisted_path = ctx.extracted_root / cl.MINI_REPORT_REL
    if not persisted_path.is_file():
        cl.write_mini_report_atomic(ctx.extracted_root, rebuilt)
        events.append(Ev(
            "INFO", "V-S8",
            f"{cl.MINI_REPORT_REL} emitted (--scan-catalog bootstrap; "
            f"{rebuilt['counts']['keysTotal']} keys, "
            f"{len(rebuilt.get('guidIndex') or {})} guidIndex entries)"))
        events.append(Ev(
            "INFO", "V-I2",
            "--scan-catalog streamed catalog.json once "
            f"({holder['size']} B, sha256 {holder['sha'][:12]}…) and wrote "
            "the sidecar"))
        return True
    persisted = persisted_path.read_bytes()
    if persisted != rebuilt_bytes:
        events.append(Ev(
            "FAIL", "V-I2",
            f"{cl.MINI_REPORT_REL} expected=persisted:"
            f"{log_util.sha256_bytes(persisted)[:16]}… "
            f"measured=rebuild:{log_util.sha256_bytes(rebuilt_bytes)[:16]}… "
            "hint=catalog.json moved since emit — re-run stage 2 or "
            "re-bootstrap --scan-catalog"))
        return False
    events.append(Ev(
        "INFO", "V-I2",
        "--scan-catalog agreement: rebuilt sidecar byte-identical "
        f"({rebuilt['counts']['keysTotal']} keys, {holder['size']} B hashed "
        "once)"))
    return True


def main(argv=None) -> int:
    log_util.bootstrap_console()
    parser = argparse.ArgumentParser(
        prog="stage10_check_contracts.py",
        description="piece-05 contracts validator suite (44 validators)")
    parser.add_argument("game_dir", nargs="?", default=None,
                        help="optional install root — enables the "
                             "client-gated V-R7 enumeration leg")
    parser.add_argument("--root", "--extracted-root", dest="root",
                        default=None, help="extraction root "
                                           "(default <pack>/extracted)")
    parser.add_argument("--scan-catalog", action="store_true",
                        help="audit lane: stream catalog.json once, "
                             "re-derive the mini-report sidecar byte-for-byte")
    parser.add_argument("--warn-stale", action="store_true",
                        help="downgrade PIN-STALE to INFO (exploratory runs)")
    args = parser.parse_args(argv)

    pack_dir = tc.resolve_pack_dir()
    extracted_root = tc.resolve_extracted_root(pack_dir)
    if args.root:
        extracted_root = Path(args.root).resolve()

    game_root = None
    if args.game_dir:
        game_root = Path(args.game_dir).resolve()

    events: list[Ev] = []
    try:
        pins = cl.load_pins(pack_dir)
        registry = cl.load_red_registry(pack_dir)
        transforms = cl.parse_transform_registry(pack_dir)
    except FileNotFoundError as exc:
        print(f"ERROR: tracked contracts layer unreadable: {exc}",
              file=sys.stderr)
        return 3
    except json.JSONDecodeError as exc:
        print(f"ERROR: tracked contracts layer malformed: {exc}",
              file=sys.stderr)
        return 1

    ctx = Ctx(extracted_root, pack_dir, pins, registry, transforms, game_root)
    ctx.warn_stale = bool(args.warn_stale)  # type: ignore[attr-defined]

    try:
        unit_gate(ctx)
    except UnitGateRefusal as exc:
        print(f"UNIT-GATE [V-U3] {exc} hint=add the transform to "
              f"contracts/counter-units.mdx", file=sys.stderr)
        return 1

    if not (extracted_root / cl.MINI_REPORT_REL).is_file() and \
            not args.scan_catalog:
        print(f"ERROR: {cl.MINI_REPORT_REL} is absent — default runs verify "
              "catalog pins solely against the persisted emit-time sidecar "
              "(heavy-artifact policy); bootstrap it once with "
              "`--scan-catalog` or rerun stage 2",
              file=sys.stderr)
        return 3

    if args.scan_catalog:
        # the audit lane runs BEFORE the remaining input gate: it may
        # bootstrap the sidecar this suite then verifies against.
        if not run_scan_catalog(ctx, events):
            info_n = sum(1 for e in events if e.kind == "INFO")
            for ev in events:
                print(ev.render())
            print(json.dumps({"passed": 0, "failed": 1, "expectedRed": 0,
                              "stale": 0, "info": info_n, "exit": "1"},
                             sort_keys=True))
            return 1

    missing = check_inputs(extracted_root,
                           need_sidecar=(extracted_root /
                                         cl.MINI_REPORT_REL).is_file())
    if missing:
        for rel in missing:
            print(f"MISSING [inputs] {rel}", file=sys.stderr)
        print(f"ERROR: stage '{STAGE_ID}' cannot check — inputs missing "
              f"({len(missing)}); prepare the tree first (client mode: run "
              "the pipeline; hostless smoke: tests/build_fixture_tree.py "
              f"--stage {STAGE_ID})", file=sys.stderr)
        return 3

    dispatch = build_dispatch()
    outcomes: list[tuple[str, Outcome]] = []
    for vid in VALIDATOR_IDS:
        outcomes.append((vid, dispatch[vid](ctx)))
    for vid, outcome in outcomes:
        if outcome.primary is not None:
            events.append(outcome.primary)
        events.extend(outcome.infos)
    order = {vid: i for i, vid in enumerate(VALIDATOR_IDS)}
    kind_rank = {"PASS": 0, "EXPECTED-RED": 1, "INFO": 2, "FAIL": 3,
                 "PIN-MISMATCH": 3, "PIN-STALE": 3}
    events.sort(key=lambda e: (order.get(e.vid, 99), kind_rank.get(e.kind, 9)))

    passed = failed = expected_red = stale_n = info_n = 0
    hard_fail = False
    for ev in events:
        if ev.kind == "FAIL" and ev.vid in registry:
            entry = registry[ev.vid]
            ev.kind = "EXPECTED-RED"
            ev.body = (f"red-registry entry={entry.get('key')} "
                       f"fix={entry.get('fix')}")
        if ev.kind == "PIN-STALE" and args.warn_stale:
            ev.kind = "INFO"
            ev.body = f"downgraded by --warn-stale: {ev.body}"
        if ev.kind == "PASS":
            passed += 1
        elif ev.kind == "EXPECTED-RED":
            expected_red += 1
        elif ev.kind == "INFO":
            info_n += 1
        elif ev.kind == "PIN-STALE":
            stale_n += 1
            hard_fail = True
        else:
            failed += 1
            hard_fail = True
    for ev in events:
        print(ev.render())
    if hard_fail:
        exit_code = 1
    elif expected_red:
        exit_code = 2
    else:
        exit_code = 0
    print(json.dumps({
        "passed": passed, "failed": failed, "expectedRed": expected_red,
        "stale": stale_n, "info": info_n, "exit": str(exit_code)},
        sort_keys=True))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())


