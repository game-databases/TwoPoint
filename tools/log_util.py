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
    if extra:
        row.update(extra)
    write_json(stamp_path(extracted_root, stage_id), row)


def is_up_to_date(extracted_root: Path, stage_id: str, identity: str) -> bool:
    """A stamp counts as done ONLY when identity matches AND the recorded
    run exited 0 — exit-2 ledger completions re-run."""
    stamp = load_stamp(extracted_root, stage_id)
    return bool(stamp) and stamp.get("identity") == identity \
        and stamp.get("exitCode") == 0


def write_pipeline_meta(extracted_root: Path, ctx: dict) -> None:
    write_json(extracted_root / ".pipeline-meta.json", ctx)
