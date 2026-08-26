#!/usr/bin/env python3
"""Shared library for the piece-05 contract-pinning layer (stage 10).

Holds the pieces BOTH the stage-2 emitter and the check-contracts runner
need, so the catalog-mini-report sidecar has exactly one derivation:

  • pins.json / red-registry.json / counter-units.mdx loading (contracts/
    tracked layer at the pack root);
  • the unit-transform registry parser behind the V-U3 load-time gate;
  • `derive_mini_report` — the single sidecar derivation consumed by
    stage-2 post-parse (document already in memory) AND by the runner's
    --scan-catalog audit lane (streamed off catalog.json);
  • an incremental `raw_decode` streaming reader for catalog.json that
    computes sha256 + byte size in the SAME single pass (verifyA method —
    the 397,431,200 B heavy artifact is never parsed as one monolithic
    json.load; the text buffer peaks at roughly the file's char count).

Determinism: every render goes through log_util.dump_json (sorted keys,
UTF-8, LF). No wall-clock anywhere.
"""
from __future__ import annotations

import codecs
import hashlib
import json
import re
from pathlib import Path

import log_util

CONTRACTS_DIRNAME = "contracts"
MINI_REPORT_REL = "addressables/catalog-mini-report.json"
TRANSFORM_NAME_RE = re.compile(r"^([a-z0-9]+(?:-[a-z0-9]+)+)\s*:")


# ---------------------------------------------------------------------------
# Tracked-layer loading

def contracts_dir(pack_dir: Path) -> Path:
    return pack_dir / CONTRACTS_DIRNAME


def load_pins(pack_dir: Path) -> dict:
    path = contracts_dir(pack_dir) / "pins.json"
    if not path.is_file():
        raise FileNotFoundError(f"missing tracked pin manifest: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_red_registry(pack_dir: Path) -> dict:
    """validator-id → registry entry for deliberately-red validators."""
    path = contracts_dir(pack_dir) / "red-registry.json"
    if not path.is_file():
        return {}
    doc = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, dict] = {}
    for entry in doc.get("entries", []):
        for vid in entry.get("validators", []):
            out[vid] = entry
    return out


def parse_transform_registry(pack_dir: Path) -> dict[str, str]:
    """transform name → declaring line, parsed from every ```transforms
    fenced block in contracts/counter-units.mdx. The V-U3 gate refuses to
    LOAD any unit-differing reconciliation whose transform is absent here."""
    path = contracts_dir(pack_dir) / "counter-units.mdx"
    if not path.is_file():
        raise FileNotFoundError(f"missing unit registry document: {path}")
    text = path.read_text(encoding="utf-8")
    names: dict[str, str] = {}
    for block in re.findall(r"```transforms\n(.*?)```", text, re.DOTALL):
        for line in block.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            m = TRANSFORM_NAME_RE.match(line)
            if m:
                names[m.group(1)] = line
    return names


def canonical_json(obj) -> str:
    """Canonical JSON spelling used for byte-equality claims (sorted keys,
    compact separators, verbatim unicode)."""
    return json.dumps(obj, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))


def iter_jsonl(path: Path):
    with open(path, "r", encoding="utf-8", newline="\n") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def count_jsonl_lines(path: Path) -> int:
    n = 0
    with open(path, "r", encoding="utf-8", newline="\n") as fh:
        for line in fh:
            if line.strip():
                n += 1
    return n


# ---------------------------------------------------------------------------
# catalog.json streaming (single pass: hash + size + per-row decode)

class CatalogStream:
    """Result carriers for `stream_catalog`."""

    def __init__(self, meta: dict, sha256: str, size_bytes: int):
        self.meta = meta
        self.sha256 = sha256
        self.size_bytes = size_bytes


def stream_catalog(path: Path):
    """Stream catalog.json ONCE (verifyA method): sha256 over the raw bytes
    and byte size accumulate while members decode one-by-one through an
    incremental `json.JSONDecoder().raw_decode` buffer.

    Yields ("row", <catalog key row>) events for every element of the
    `keys` array; the trailing CatalogStream (meta/sha256/size) arrives as
    the final ("done", stream) event.
    """
    decoder = json.JSONDecoder()
    state = {"hasher": hashlib.sha256(), "size": 0, "buf": "", "eof": False}
    fh = open(path, "rb")
    incremental = codecs.getincrementaldecoder("utf-8")("strict")

    def fill() -> bool:
        chunk = fh.read(1 << 20)
        state["size"] += len(chunk)
        state["hasher"].update(chunk)
        if not chunk:
            state["eof"] = True
            state["buf"] += incremental.decode(b"", True)
            return False
        try:
            state["buf"] += incremental.decode(chunk)
        except UnicodeDecodeError as exc:
            raise ValueError(f"{path}: invalid UTF-8 in catalog stream: {exc}")
        return True

    def skip_ws(i: int) -> int:
        while True:
            buf = state["buf"]
            n = len(buf)
            while i < n and buf[i] in " \t\r\n":
                i += 1
            if i < n:
                return i
            if not fill():
                return i

    def expect(i: int, ch: str, what: str) -> int:
        i = skip_ws(i)
        if i >= len(state["buf"]) or state["buf"][i] != ch:
            raise ValueError(f"{path}: expected {what} in catalog stream")
        return i + 1

    def decode_at(i: int):
        while True:
            try:
                return decoder.raw_decode(state["buf"], i)
            except json.JSONDecodeError:
                if fill():
                    continue
                raise ValueError(
                    f"{path}: truncated or malformed JSON in catalog stream")

    try:
        i = expect(0, "{", "'{'")
        meta: dict = {}
        while True:
            i = skip_ws(i)
            if i >= len(state["buf"]):
                if not fill():
                    raise ValueError(f"{path}: unexpected end of catalog")
                continue
            ch = state["buf"][i]
            if ch == "}":
                break
            if ch == ",":
                i = skip_ws(i + 1)
                continue
            key, end = decode_at(i)
            if not isinstance(key, str):
                raise ValueError(f"{path}: non-string member name")
            i = expect(end, ":", "':'")
            i = skip_ws(i)
            if i >= len(state["buf"]):
                if not fill():
                    raise ValueError(f"{path}: unexpected end of catalog")
                continue
            if key == "keys":
                i = expect(i, "[", "'[' opening the keys array")
                while True:
                    i = skip_ws(i)
                    if i >= len(state["buf"]):
                        if not fill():
                            raise ValueError(
                                f"{path}: truncated keys array")
                        continue
                    c = state["buf"][i]
                    if c == "]":
                        i += 1
                        break
                    if c == ",":
                        i = skip_ws(i + 1)
                        continue
                    row, end_row = decode_at(i)
                    i = end_row
                    yield "row", row
            else:
                val, end_val = decode_at(i)
                i = end_val
                if key == "meta" and isinstance(val, dict):
                    meta = val
        yield "done", CatalogStream(meta, state["hasher"].hexdigest(),
                                    state["size"])
    finally:
        fh.close()


# ---------------------------------------------------------------------------
# The ONE sidecar derivation (stage-2 post-parse AND --scan-catalog)

def derive_mini_report(keys, roster_relpaths, coverage_doc: dict,
                       source_bytes: int, catalog_sha256: str,
                       meta: dict | None = None) -> dict:
    """Derive `extracted/addressables/catalog-mini-report.json` content per
    the pinned six-key schema (piece-05 §3.3):

      {meta:{buildId,addressablesVersion,settingsHash,sourceBytes,
             catalogSha256},
       counts:{keysTotal,distinctKeys,kindCounts{address,guid},
               nullBundleRows{total,guidKind,addressKind},nullAddressRows,
               rowsWithNoDependencies,dependencyEdgesTotal},
       duplicateKeys:[{key,rowCount,rowsByteIdentical,kind,address}],
       bundleUniverse:{referencedRelpaths,bundlesUnreferenced,
                       outOfRosterFileReferences,danglingDependencyKeys},
       guidIndex:{guid:[{address,kind}]},
       nullBundleAddresses:[…]}

    `keys` is an iterable of catalog key rows ({key,kind,bundle,address,
    dependencies}); both callers feed the same shape, so a streamed rebuild
    and the emit-time document compare byte-for-byte under canonical JSON.
    `nullBundleAddresses` holds DISTINCT sorted addresses (an O(1)
    membership set for V-X2/V-L1); `outOfRosterFileReferences` and
    `danglingDependencyKeys` mirror catalog-coverage's ledgers (full lists
    today — a truncated future sample surfaces loudly as a scan
    disagreement under AC6).
    """
    keys_total = 0
    kind_counts: dict[str, int] = {}
    null_bundle_rows = 0
    null_bundle_by_kind: dict[str, int] = {}
    null_address_rows = 0
    zero_dep_rows = 0
    dep_edges = 0
    canon_first: dict[str, str] = {}
    dup_meta: dict[str, dict] = {}
    guid_index: dict[str, list[dict]] = {}
    null_bundle_addresses: set[str] = set()
    referenced: set[str] = set()

    for row in keys:
        keys_total += 1
        kind = str(row.get("kind"))
        kind_counts[kind] = kind_counts.get(kind, 0) + 1
        key = row.get("key")
        deps = row.get("dependencies") or []
        dep_edges += len(deps)
        if not deps:
            zero_dep_rows += 1
        bundle = row.get("bundle")
        address = row.get("address")
        if address is None:
            null_address_rows += 1
        if bundle is None:
            null_bundle_rows += 1
            null_bundle_by_kind[kind] = null_bundle_by_kind.get(kind, 0) + 1
            if address is not None:
                null_bundle_addresses.add(str(address))
        else:
            referenced.add(str(bundle))
        referenced.update(str(d) for d in deps)
        spelled = canonical_json(row)
        if key in dup_meta:
            dup_meta[key]["rowCount"] += 1
            if spelled != canon_first[key]:
                dup_meta[key]["rowsByteIdentical"] = False
        else:
            canon_first[key] = spelled
            dup_meta[key] = {"key": key, "rowCount": 1,
                             "rowsByteIdentical": True,
                             "kind": kind,
                             "address": address}
        if kind == "guid":
            guid_index.setdefault(str(key), []).append(
                {"address": address, "kind": "guid"})
    del canon_first

    duplicate_keys = [e for e in dup_meta.values() if e["rowCount"] > 1]
    duplicate_keys.sort(key=lambda e: e["key"])

    roster_set = set(roster_relpaths)
    referenced_relpaths = sorted(referenced & roster_set)
    unreferenced = sorted(roster_set - referenced)
    dangling = (coverage_doc.get("danglingDependencyKeys") or {})
    oor = (coverage_doc.get("outOfRosterFileReferences") or {})

    def _ledger_strings(cell, count) -> list[str]:
        sample = cell.get("sample") if isinstance(cell, dict) else cell
        items = list(sample or [])
        if isinstance(cell, dict) and len(items) < (count or 0):
            raise ValueError(
                "catalog-coverage warning ledger is SAMPLED "
                f"({len(items)} of {count}) — the sidecar needs the full "
                "list; widen the emitter sample cap")
        out = []
        for item in items:
            out.append(str(item.get("reference"))
                       if isinstance(item, dict) else str(item))
        return sorted(out)

    meta_src = meta or {}

    return {
        "meta": {
            "buildId": meta_src.get("buildId"),
            "addressablesVersion": meta_src.get("addressablesVersion"),
            "settingsHash": meta_src.get("settingsHash"),
            "sourceBytes": source_bytes,
            "catalogSha256": catalog_sha256,
        },
        "counts": {
            "keysTotal": keys_total,
            "distinctKeys": len(dup_meta),
            "kindCounts": {"address": kind_counts.get("address", 0),
                           "guid": kind_counts.get("guid", 0)},
            "nullBundleRows": {"total": null_bundle_rows,
                               "guidKind": null_bundle_by_kind.get("guid", 0),
                               "addressKind": null_bundle_by_kind.get(
                                   "address", 0)},
            "nullAddressRows": null_address_rows,
            "rowsWithNoDependencies": zero_dep_rows,
            "dependencyEdgesTotal": dep_edges,
        },
        "duplicateKeys": duplicate_keys,
        "bundleUniverse": {
            "referencedRelpaths": referenced_relpaths,
            "bundlesUnreferenced": unreferenced,
            "outOfRosterFileReferences": _ledger_strings(oor, oor.get("count")),
            "danglingDependencyKeys": _ledger_strings(
                dangling, dangling.get("count")),
        },
        "guidIndex": {g: guid_index[g] for g in sorted(guid_index)},
        "nullBundleAddresses": sorted(null_bundle_addresses),
    }


def render_mini_report(doc: dict) -> bytes:
    """Canonical persisted bytes: sorted keys, UTF-8, LF, indent=2."""
    return log_util.dump_json(doc).encode("utf-8")


def write_mini_report_atomic(extracted_root: Path, doc: dict) -> Path:
    path = extracted_root / MINI_REPORT_REL
    log_util.atomic_write_bytes(path, render_mini_report(doc))
    return path
