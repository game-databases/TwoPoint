#!/usr/bin/env python3
"""Logging + write-discipline helpers for the Two Point Campus pipeline.

Determinism rules implemented here (spec §4): every declared output is
written to a temp file and atomically renamed into place; JSON is dumped
with sorted keys; text files are utf-8 with newline="\n". Wall-clock
timestamps are allowed ONLY in EXTRACTION-LOG.md run sections,
.stage-stamps/ and .pipeline-meta.json (all excluded from byte-identity
comparisons).
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

STAGE_DEFAULTS_BEGIN = "<!-- stage-defaults-begin -->"
STAGE_DEFAULTS_END = "<!-- stage-defaults-end -->"


def bootstrap_console() -> None:
    """Force UTF-8 stdout/stderr (Windows cp1252 crash lesson) and set the
    env so child processes inherit it."""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name)
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # non-reconfigurable stream — proceed anyway
            pass
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    os.environ.setdefault("PYTHONUTF8", "1")


def utc_now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Atomic writes

def atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp",
                               dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.replace(tmp, str(path))
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def atomic_write_text(path: Path, text: str) -> None:
    atomic_write_bytes(path, text.encode("utf-8"))


def dump_json(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def dump_jsonl_row(row) -> str:
    return json.dumps(row, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))


def write_json(path: Path, obj) -> None:
    atomic_write_text(path, dump_json(obj))


def write_jsonl(path: Path, rows) -> None:
    """Whole-file jsonl write (never OS-append: reruns must be
    byte-identical). rows are serialized in the given order."""
    payload = "".join(dump_jsonl_row(r) + "\n" for r in rows)
    atomic_write_text(path, payload)


def append_line(path: Path, line: str) -> None:
    """Single-line appends are only used on files outside byte-identity
    comparisons (EXTRACTION-LOG.md)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(line.rstrip("\n") + "\n")


# ---------------------------------------------------------------------------
# Hashing / identity

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def identity_hash(payload) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                           separators=(",", ":")).encode("utf-8")
    return sha256_bytes(canonical)


def file_fingerprint(path: Path) -> dict:
    """Cheap identity input: size + mtime_ns (no full read)."""
    st = path.stat()
    return {"size": st.st_size, "mtimeNs": st.st_mtime_ns}


# ---------------------------------------------------------------------------
# EXTRACTION-LOG.md

LOG_NAME = "EXTRACTION-LOG.md"


def log_path(extracted_root: Path) -> Path:
    return extracted_root / LOG_NAME


def seed_extraction_log(extracted_root: Path, header_pins: dict, defaults: dict) -> bool:
    """Seed the log if absent. Returns True when a new log was written.
    The stage-defaults JSON block sits between sentinel comments and is the
    source of truth the entrypoint reads its defaults from (embedded
    fallback pins live in code and apply only while the block is absent)."""
    path = log_path(extracted_root)
    if path.is_file():
        return False
    pins_lines = "\n".join(f"- **{k}:** {v}" for k, v in sorted(header_pins.items()))
    body = (
        "# Two Point Campus — Extraction Log\n\n"
        "Seeded by pipeline piece 1 (`run_all.py`). Per doctrine this log is\n"
        "the source of truth for tool paths and versions: the\n"
        "`stage-defaults` block below is read by every run, and tooling\n"
        "changes land in it in the same commit that changes the entrypoint.\n\n"
        "## Header pins\n\n"
        f"{pins_lines}\n\n"
        f"{STAGE_DEFAULTS_BEGIN}\n```json\n"
        + json.dumps(defaults, ensure_ascii=False, sort_keys=True, indent=2)
        + "\n```\n"
        f"{STAGE_DEFAULTS_END}\n\n"
        "## Run sections\n\n"
        "(appended per executed stage below)\n"
    )
    atomic_write_text(path, body)
    return True


def read_stage_defaults(extracted_root: Path) -> dict | None:
    """Parse the stage-defaults JSON block; None when absent/unparseable."""
    path = log_path(extracted_root)
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    begin = text.find(STAGE_DEFAULTS_BEGIN)
    end = text.find(STAGE_DEFAULTS_END)
    if begin < 0 or end < 0 or end < begin:
        return None
    chunk = text[begin + len(STAGE_DEFAULTS_BEGIN):end]
    fence_start = chunk.find("```")
    if fence_start >= 0:
        chunk = chunk[fence_start + 3:]
        if chunk.lstrip().startswith("json"):
            chunk = chunk.lstrip()[4:]
        close = chunk.rfind("```")
        if close >= 0:
            chunk = chunk[:close]
    try:
        data = json.loads(chunk)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def append_run_section(extracted_root: Path, stage_id: str, lines: list[str]) -> None:
    stamp = utc_now_iso()
    body = [f"### {stamp} — {stage_id}"]
    body.extend(lines)
    append_line(log_path(extracted_root), "\n".join(body) + "\n")


def append_failure_section(extracted_root: Path, stage_id: str,
                           exit_code: int, problems) -> None:
    """Failing stages append their run section too (Revision 4): exitCode +
    PROBLEM lines — the ledger never depends on success. Best-effort: a
    logging error here must never mask the original failure being reported."""
    try:
        append_run_section(
            extracted_root, stage_id,
            [f"- exitCode: {int(exit_code)} (failed)"]
            + [f"- PROBLEM: {p}" for p in problems])
    except Exception:  # noqa: BLE001 — see docstring
        pass


# ---------------------------------------------------------------------------
# Stage stamps + pipeline meta

# Per-stage DECLARED final artifacts. The up-to-date decision requires every
# one of them to exist with its stamped content, so a deleted or truncated
# output forces re-execution even when the stamp itself matches
# (interrupted-run convergence). The determinism-excluded files
# (EXTRACTION-LOG.md, .stage-stamps/, .pipeline-meta.json) are deliberately
# not listed. localisation's per-locale tables are appended in
# stage_outputs() from the shared EMITTED_LOCALES table.
STAGE_OUTPUTS = {
    "verify-client": ["identity.json", "bundle-roster.jsonl"],
    "decompile": ["decompiled/structural/assembly-index.json",
                  "decompiled/structural/class-hierarchy.jsonl"],
    "harvest-catalog": ["addressables/catalog.json",
                        "addressables/settings.snapshot.json",
                        "addressables/catalog-coverage.json"],
    "harvest-bundles": ["harvest/export-manifest.jsonl",
                        "harvest/census/unreadable.jsonl",
                        "media-catalogue.jsonl", "MEDIA-CATALOGUE.md"],
    "localisation": ["locales/locale-matrix.json",
                     "locales/base-overlay-report.json"],
    "emit-stub-datasets": [
        "stubs/items.jsonl", "stubs/unlockables.jsonl", "stubs/rooms.jsonl",
        "stubs/campus-levels.jsonl", "stubs/courses.jsonl",
        "stubs/configs.jsonl", "stubs/staff.jsonl",
        "stubs/metagame-nodes.jsonl", "stubs/student-types.jsonl",
        "stubs/_absences.jsonl", "stubs/_unmapped-families.jsonl",
    ],
    # piece-07 locale-proof (canonical index 9). SOLE writer of the
    # canonical availability path since piece-01 Revision 8 (arbiter R4) —
    # deliberately removed from emit-stub-datasets above. `.baseline.json`
    # is excluded like the other determinism-excluded files.
    "locale-proof": [
        "locales/proof/key_plane.json",
        "locales/proof/kind_locale_matrix.json",
        "locales/proof/unjoined_entities.jsonl",
        "locales/proof/fallback_law.json",
        "locales/proof/site_ui_gap_manifest.json",
        "locales/proof/registry_completeness.json",
        "locales/proof/summary.json",
        "locales/proof/hashes.json",
        "locales/proof/_ledger.jsonl",
        "relinks/locale_availability.jsonl",
        "relinks/locale_availability.report.json",
    ],
    # stage 6 (piece-02): every stage-6-OWNED path of the §4 layout. The
    # pair/overlay datasets are data-dependent (one file per cell with ≥1
    # edge) so their CLOSED universe — all ordered pairs over the 10-node
    # universe — is generated; absent files hash "" like any born-empty
    # artifact. `locale_availability.jsonl` is deliberately NOT here: it is
    # stage-5's sole property and this stage never writes it.
    "relink": [
        "RELATIONS.md",
        "relinks/matrix.json",
        "relinks/entity_asset_guid.jsonl",
        "relinks/guid_bridge_report.json",
        "relinks/_dangling_guids.jsonl",
        "relinks/i2_term_registry.jsonl",
        "relinks/entity_locale.jsonl",
        "relinks/locale_term_entity.jsonl",
        "relinks/locale_join_report.json",
        "relinks/ui_link_coverage.jsonl",
        "relinks/competitor_applied.jsonl",
        "relinks/_unresolved_pptrs.jsonl",
        "relinks/bridges/cab_index.jsonl",
        "relinks/bridges/container_index.jsonl",
    ],
    # stage 7 (piece-03 maps, canonical index 7): the FIXED declared-output
    # universe of extracted/maps/** (piece-03 §4) — every path always
    # emitted (empty ledgers valid). `_manifest.sha256` hashes these very
    # inputs, so it is fingerprinted too and rerun-equality reads it.
    "maps": [
        "maps/coordinate_law.json",
        "maps/loadassets_read.json",
        "maps/levels.jsonl",
        "maps/scenarios.jsonl",
        "maps/plots.jsonl",
        "maps/plots_tiletypes.jsonl",
        "maps/rooms.jsonl",
        "maps/rooms_tiles.jsonl",
        "maps/item_placements.jsonl",
        "maps/students.jsonl",
        "maps/staff_records.jsonl",
        "maps/landscape_layers.jsonl",
        "maps/landscape_maps.jsonl",
        "maps/terrain_decode.json",
        "maps/door_validators.jsonl",
        "maps/door_placement_index.jsonl",
        "maps/door_id_space.json",
        "maps/named_plots.jsonl",
        "maps/imagery_candidates.jsonl",
        "maps/imagery_predicates.json",
        "maps/join_report.json",
        "maps/_manifest.sha256",
        "maps/_absences.jsonl",
        "maps/_unresolved_placements.jsonl",
    ],
    # stage 8 (piece-04): the FIXED declared-output universe of
    # `extracted/logic/**` — every path is always emitted (empty ledgers
    # valid), so the closed set is static. LOGIC.md is the tracked layer;
    # digests land in the EXTRACTION-LOG run section, never inside logic/.
    "logic": [
        "logic/LOGIC.md",
        "logic/_gaps.jsonl",
        "logic/course-progression/prerequisite-taxonomy.json",
        "logic/course-progression/courses.jsonl",
        "logic/course-progression/modules.jsonl",
        "logic/course-progression/prerequisites.jsonl",
        "logic/course-progression/prerequisite-nonmembers.jsonl",
        "logic/course-progression/course-unlock-edges.jsonl",
        "logic/course-progression/attrition.jsonl",
        "logic/economy/money-taxonomy.json",
        "logic/economy/finance-configs.jsonl",
        "logic/economy/kudosh-ledger.jsonl",
        "logic/economy/research-costs.jsonl",
        "logic/grading/grade-ladder.json",
        "logic/grading/term-pass-grades.jsonl",
        "logic/grading/assessment-scoring.jsonl",
        "logic/grading/xp-score-normalization.json",
        "logic/needs-decay/staff-decay.jsonl",
        "logic/needs-decay/student-decay.jsonl",
        "logic/needs-decay/student-core11-decay.jsonl",
        "logic/needs-decay/interactions.jsonl",
    ],
    # stage 11 (piece-06): the always-on text artifacts + the tracked layer
    # (MEDIA-EXPORT.md). web/** binaries are covered through hashes.sha256;
    # the flag-gated course-icon-carrier-report.json is deliberately not a
    # declared output (its presence rides the --probe-course-carrier flag,
    # like the data-dependent relink pair files ride their closed universe).
    "media": [
        "media/export-manifest.jsonl",
        "media/index.jsonl",
        "media/hashes.sha256",
        "media/crosscheck-report.json",
        "media/_missing_icons.jsonl",
        "media/_pptr_residue.jsonl",
        "media/_skipped_classes.jsonl",
        "media/MEDIA-EXPORT.md",
    ],
    # stage 12 (piece-08): the fixed trio plus the per-locale shard/title
    # planes, appended in stage_outputs() from the shared EMITTED_LOCALES
    # table (a hostless mini fixture names fewer than 13 — absent files
    # hash "" like any born-empty artifact).
    "search-corpus": [
        "search/manifest.json",
        "search/hashes.json",
        "search/_ledger.jsonl",
    ],
}


def stamp_path(extracted_root: Path, stage_id: str) -> Path:
    safe = stage_id.replace("/", "_")
    return extracted_root / ".stage-stamps" / f"{safe}.json"


def load_stamp(extracted_root: Path, stage_id: str) -> dict | None:
    p = stamp_path(extracted_root, stage_id)
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def save_stamp(extracted_root: Path, stage_id: str, identity: str,
               exit_code: int, extra: dict | None = None) -> None:
    row = {
        "stage": stage_id,
        "identity": identity,
        "exitCode": int(exit_code),
        "finishedAt": utc_now_iso(),
    }
    # completed runs fingerprint their declared outputs so a later run can
    # tell "stamp matches" from "outputs actually survived intact". Exit 2
    # (completed-with-ledger) fingerprints too: its ledger IS the honest
    # terminal state, so an unchanged rerun must skip execution
    # (piece-02 runner contract — stamp identity on stage 6).
    if row["exitCode"] in (0, 2) and STAGE_OUTPUTS.get(stage_id):
        row["outputs"] = declared_output_state(extracted_root, stage_id)
    if extra:
        row.update(extra)
    write_json(stamp_path(extracted_root, stage_id), row)


def stage_outputs(stage_id: str) -> list[str]:
    """Declared final artifacts of a stage (spec §3/§4). The localisation
    per-locale tables come from the shared locale table; stage 6's
    pair/overlay datasets generate their closed universe from the pinned
    10-node matrix order. Lazy imports keep this module dependency-free."""
    outs = list(STAGE_OUTPUTS.get(stage_id, ()))
    if stage_id == "localisation":
        import tpc_common as tc
        outs += [f"locales/{locale}.jsonl" for locale in tc.EMITTED_LOCALES]
    if stage_id == "locale-proof":
        import tpc_common as tc
        outs += [f"locales/proof/key_holes/{locale}.jsonl"
                 for locale in tc.EMITTED_LOCALES]
    if stage_id == "search-corpus":
        import tpc_common as tc
        outs += [f"search/shards/{locale}.jsonl"
                 for locale in tc.EMITTED_LOCALES]
        outs += [f"search/titles/{locale}.jsonl"
                 for locale in tc.EMITTED_LOCALES]
    if stage_id == "relink":
        import relink_util
        outs += [f"relinks/{s}_{d}.jsonl"
                 for s in relink_util.NODE_UNIVERSE
                 for d in relink_util.NODE_UNIVERSE]
        outs += [f"relinks/{s}_{d}.competitor.jsonl"
                 for s in relink_util.NODE_UNIVERSE
                 for d in relink_util.NODE_UNIVERSE]
    return outs


def declared_output_state(extracted_root: Path, stage_id: str) -> dict[str, str]:
    """rel -> sha256 for every declared output ('' when absent). Both the
    saved stamp and the live check render through this same function, so a
    deleted/truncated/rewritten final mismatches the stamp while a file
    legitimately born empty (e.g. _absences.jsonl with every family
    populated) stays consistent instead of forcing perpetual re-runs."""
    state: dict[str, str] = {}
    for rel in stage_outputs(stage_id):
        p = extracted_root / rel
        state[rel] = sha256_file(p) if p.is_file() else ""
    return state


def outputs_current(extracted_root: Path, stage_id: str, stamp: dict) -> bool:
    """Every declared output must exist with its stamped content. Stamps
    predating output fingerprinting (no 'outputs' block) count as stale so
    the next run re-fingerprints them."""
    if not STAGE_OUTPUTS.get(stage_id):
        return True
    recorded = stamp.get("outputs")
    if not isinstance(recorded, dict):
        return False
    return recorded == declared_output_state(extracted_root, stage_id)


def is_up_to_date(extracted_root: Path, stage_id: str, identity: str) -> bool:
    """A stamp counts as done ONLY when identity matches AND the recorded
    run COMPLETED — exit 0, or exit 2 (completed-with-ledger: the ledgered
    gaps are the honest terminal state, and re-executing an unchanged run
    would breach the piece-02 runner contract's stamp identity) — AND every
    declared output still exists with its stamped content: a deleted or
    truncated final must be regenerated, never skipped past. Stamps saved
    before output fingerprinting (no 'outputs' block) stay stale."""
    stamp = load_stamp(extracted_root, stage_id)
    return bool(stamp) and stamp.get("identity") == identity \
        and stamp.get("exitCode") in (0, 2) \
        and outputs_current(extracted_root, stage_id, stamp)


def write_pipeline_meta(extracted_root: Path, ctx: dict) -> None:
    write_json(extracted_root / ".pipeline-meta.json", ctx)
