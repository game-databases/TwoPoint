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
        "relinks/locale_availability.jsonl",
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
    # successful runs fingerprint their declared outputs so a later run can
    # tell "stamp matches" from "outputs actually survived intact"
    if row["exitCode"] == 0 and STAGE_OUTPUTS.get(stage_id):
        row["outputs"] = declared_output_state(extracted_root, stage_id)
    if extra:
        row.update(extra)
    write_json(stamp_path(extracted_root, stage_id), row)


def stage_outputs(stage_id: str) -> list[str]:
    """Declared final artifacts of a stage (spec §3/§4). The localisation
    per-locale tables come from the shared locale table; the lazy import
    keeps this module dependency-free."""
    outs = list(STAGE_OUTPUTS.get(stage_id, ()))
    if stage_id == "localisation":
        import tpc_common as tc
        outs += [f"locales/{locale}.jsonl" for locale in tc.EMITTED_LOCALES]
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
    run exited 0 — exit-2 ledger completions re-run — AND every declared
    output still exists with its stamped content: a deleted or truncated
    final must be regenerated, never skipped past."""
    stamp = load_stamp(extracted_root, stage_id)
    return bool(stamp) and stamp.get("identity") == identity \
        and stamp.get("exitCode") == 0 \
        and outputs_current(extracted_root, stage_id, stamp)


def write_pipeline_meta(extracted_root: Path, ctx: dict) -> None:
    write_json(extracted_root / ".pipeline-meta.json", ctx)
