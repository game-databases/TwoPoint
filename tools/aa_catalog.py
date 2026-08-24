#!/usr/bin/env python3
"""Addressables 1.21 binary ContentCatalogData decoders.

Stage 2 hands THIS module the raw catalog payload dict — m_KeyDataString /
m_BucketDataString / m_EntryDataString base64 blobs plus m_InternalIds /
m_ProviderIds / m_resourceTypes — from either route (spec §3 stage 2,
Revision 4): PRIMARY = the TextAsset "catalog" JSON parsed directly;
SECONDARY = a ContentCatalogData MonoBehaviour decoded through the
dump.cs-synthesized typetree. This module parses the blobs themselves.

Blob layouts are NOT guessed: they were reverse-engineered and validated
2026-08-20 against two shipped catalogs — Disco Elysium (Unity 2020.3 /
Addressables 1.x, same engine family as this client) and Zero Parades
(AA 1.22.3) — with stated-count == parsed reconciliation
(zero-parades/work/scripts/parse_aa_catalog.py). Self-validation here
re-derives the same invariants on every run: bucket count == key-slot
count, entry-blob byte length == 4 + 28·n, key-blob fully consumed.
"""
from __future__ import annotations

import base64
import binascii
import io
import struct


class CatalogDecodeError(Exception):
    pass


def _take(r: io.BytesIO, n: int, what: str) -> bytes:
    """Read exactly n bytes or raise the typed decode error — a truncated
    blob is a malformed catalog, never a raw struct.error/IndexError past
    the handler that routes it to the secondary path (spec Revision 4)."""
    b = r.read(n)
    if len(b) != n:
        raise CatalogDecodeError(
            f"{what}: blob truncated ({len(b)} of {n} bytes at offset "
            f"{r.tell() - len(b)})")
    return b


def parse_keys(blob: bytes) -> list[dict]:
    """Key slots: [{key, kind, a}]; type-4 entries occupy TWO slots."""
    r = io.BytesIO(blob)
    (count,) = struct.unpack("<i", _take(r, 4, "m_KeyDataString slot count"))
    entries: list[tuple[str, object, int | None]] = []
    while r.tell() < len(blob):
        t = _take(r, 1, "m_KeyDataString type tag")[0]
        if t == 0:
            (ln,) = struct.unpack("<i", _take(r, 4, "string key length"))
            entries.append(("str", _take(r, ln, "string key").decode("utf-8", "replace"), None))
        elif t == 1:
            (ln,) = struct.unpack("<i", _take(r, 4, "u16 key length"))
            entries.append(("u16", _take(r, ln, "u16 key").decode("utf-16-le", "replace"), None))
        elif t == 4:
            (a,) = struct.unpack("<i", _take(r, 4, "type-4 auxiliary id"))
            z = r.read(1)
            if not z:
                entries.append(("t4_truncated", "", a))
                break
            (ln,) = struct.unpack("<i", _take(r, 4, "type-4 key length"))
            entries.append(("t4", _take(r, ln, "type-4 key").decode("utf-8", "replace"), a))
        else:
            raise CatalogDecodeError(
                f"unknown key type {t} at offset {r.tell() - 1} of m_KeyDataString")
    slots: list[dict] = []
    for i, (kind, val, a) in enumerate(entries):
        slots.append({"key": val, "kind": kind, "a": a})
        if kind == "t4":
            pair = entries[i + 1][1] if i + 1 < len(entries) else None
            slots.append({"key": pair, "kind": "t4_pair", "a": a})
        elif kind == "t4_truncated":
            slots.append({"key": None, "kind": "t4_pair", "a": a})
    if count != len(slots):
        raise CatalogDecodeError(
            f"key slot mismatch: stated {count} != parsed {len(slots)}")
    return slots


def parse_buckets(blob: bytes) -> list[tuple[int, list[int]]]:
    r = io.BytesIO(blob)
    (count,) = struct.unpack("<i", _take(r, 4, "m_BucketDataString bucket count"))
    if count < 0:
        raise CatalogDecodeError(f"negative bucket count {count}")
    buckets = []
    for _ in range(count):
        off, n = struct.unpack("<2i", _take(r, 8, "bucket header"))
        if n < 0:
            raise CatalogDecodeError(f"negative bucket entry count {n}")
        ents = list(struct.unpack(
            f"<{n}i", _take(r, 4 * n, "bucket entry indexes"))) if n else []
        buckets.append((off, ents))
    if r.tell() != len(blob):
        raise CatalogDecodeError(
            f"bucket blob residue {len(blob) - r.tell()} bytes")
    return buckets


def parse_entries(blob: bytes) -> list[tuple[int, int, int, int, int, int, int]]:
    """Per entry: internalIdIdx, providerIdx, dependencyKeyIdx, hashCode,
    dataOffset, primaryKeyIdx, resourceTypeIdx."""
    r = io.BytesIO(blob)
    (count,) = struct.unpack("<i", _take(r, 4, "m_EntryDataString entry count"))
    if count < 0:
        raise CatalogDecodeError(f"negative entry count {count}")
    if r.tell() + 28 * count != len(blob):
        raise CatalogDecodeError(
            f"entry blob length mismatch: {len(blob)} bytes vs "
            f"{count} declared entries")
    return [struct.unpack("<7i", _take(r, 28, "entry record"))
            for _ in range(count)]


def decode_catalog_payload(payload: dict) -> dict:
    """payload = already-decoded ContentCatalogData fields → structured
    catalog model:

    {"keys":[{key, kind, entries:[{internalId, provider, resourceType,
              dependencyKey, primaryKey}]}],
     "internalIds":[…], "providerIds":[…]}
    """
    for required in ("m_InternalIds", "m_ProviderIds"):
        if required not in payload:
            present = sorted(k for k in payload if isinstance(k, str))
            raise CatalogDecodeError(
                f"catalog payload missing '{required}' (present keys: "
                f"{present[:12]})")
    internal_ids = [s.replace("\\", "/") if isinstance(s, str) else str(s)
                    for s in payload["m_InternalIds"]]
    provider_ids = [str(s) for s in payload["m_ProviderIds"]]
    rtypes_raw = payload.get("m_resourceTypes") or []
    rtypes = []
    for t in rtypes_raw:
        rtypes.append(t.get("m_ClassName", "?") if isinstance(t, dict) else str(t))

    def b64(name: str) -> bytes:
        raw = payload.get(name)
        if isinstance(raw, (bytes, bytearray)):
            return bytes(raw)
        if isinstance(raw, str):
            try:
                return base64.b64decode(raw)
            except (binascii.Error, ValueError) as exc:
                raise CatalogDecodeError(
                    f"catalog payload field '{name}': invalid base64 ({exc})")
        raise CatalogDecodeError(f"catalog payload field '{name}' missing")

    slots = parse_keys(b64("m_KeyDataString"))
    buckets = parse_buckets(b64("m_BucketDataString"))
    entries = parse_entries(b64("m_EntryDataString"))
    if len(buckets) != len(slots):
        raise CatalogDecodeError(
            f"{len(buckets)} buckets != {len(slots)} key slots")

    keys_out: list[dict] = []
    entry_total = 0
    for i, slot in enumerate(slots):
        bucket_off, eidxs = buckets[i]
        rows = []
        for ei in eidxs:
            if not 0 <= ei < len(entries):
                raise CatalogDecodeError(f"entry index {ei} out of range")
            iid, prov, dep, _hsh, _data, prim, rt = entries[ei]
            rows.append({
                "internalId": internal_ids[iid] if 0 <= iid < len(internal_ids) else str(iid),
                "provider": provider_ids[prov] if 0 <= prov < len(provider_ids) else str(prov),
                "resourceType": rtypes[rt] if 0 <= rt < len(rtypes) else str(rt),
                "dependencyKey": slots[dep]["key"] if 0 <= dep < len(slots) else None,
                "primaryKey": slots[prim]["key"] if 0 <= prim < len(slots) else None,
            })
        entry_total += len(rows)
        keys_out.append({
            "key": slot["key"], "kind": slot["kind"],
            "bucketOffset": bucket_off, "a": slot["a"], "entries": rows})
    if entry_total != len(entries):
        raise CatalogDecodeError(
            f"bucket entry total {entry_total} != parsed entries {len(entries)}")
    return {"keys": keys_out, "internalIds": internal_ids, "providerIds": provider_ids}
