#!/usr/bin/env python3
"""Shared machinery for stage 6 — relink (piece-02 contract,
docs/specs/piece-02-relinking.mdx).

Everything here is a pure, deterministic function of its inputs: bridges
(CAB + container indexes over the roster bundles), the PPtr/LocalisedString/
AssetGUID payload walkers, the cross-file resolver ladder (externals →
cab_index → stub index), the GUID bridge, the I2 term-registry builder,
the UI-link coverage builders, the competitor-model mapper, and the
matrix/RELATIONS.md assemblers. Stage 6 owns every emitted path in
`extracted/relinks/` EXCEPT `locale_availability.jsonl` (stage-5 SOLE
owner — R4 ownership pin; this module never writes it).

Determinism: sorted enumeration everywhere, no wall-clock inputs, atomic
temp+rename writes, UTF-8 + LF. Ids stay VERBATIM end to end (Principle
one) — twins keep their `@<contentHash8>` suffix.
"""
from __future__ import annotations

import bisect
import json
import os
import re
import tempfile
from array import array
from collections import Counter
from pathlib import Path

import log_util
import tpc_common as tc


# ---------------------------------------------------------------------------
# Frozen vocabularies (piece-02 §3 R2)

# Node universe order IS the matrix pairs[] row-major order (the AC5
# byte-determinism gate hashes this array — order is contract).
NODE_UNIVERSE = (
    "config", "item", "room", "course", "staff", "student-type",
    "unlockable", "metagame-node", "campus-level", "scene",
)
SCENE_NODE = "scene"
NODE_ARITHMETIC = ("10 nodes -> 100 ordered cells "
                   "= 90 off-diagonal + 10 diagonal")
DIAGONALS = frozenset((n, n) for n in NODE_UNIVERSE)

MECHANISMS = ("hard", "logic", "inferred")
STATUSES = ("modeled", "partial", "missing")

JOINKEY_PPTR = "PPtr(m_FileID,m_PathID)"
JOINKEY_GUID = "AssetGUID(m_AssetGUID)->catalog.guid->container-address->pathId"
JOINKEY_LOCALE = "LocalisedString(_termID)->I2-termID->Term-key"
JOINKEY_NONE = "none-established"

# Source-side scene cells ship missing with this unblock (piece-02 §3 R2:
# no stub-payload emitter exists for the scene node by design; the maps
# piece's scene-dump walk owns the probe). Single source of truth — the
# stage script aliases this name.
SCENE_SRC_UNBLOCK = (
    "no stub-payload emitter exists for the scene source node by design — "
    "scene objects have no stubs; owner: the maps piece's scene-dump walk "
    "(inherits this piece's scene node seam)")


def joinkey_name_equality(rule: str) -> str:
    return f"name-equality({rule})"


METHOD_PTR_SAME = "pptr-same-file"
METHOD_PTR_CROSS = "pptr-cross-file"
METHOD_GUID = "assetguid-catalog"
METHOD_I2 = "i2-termid-registry"
RESOLVED_VIA_BRIDGE = "externals+cab-index"

# stage-5 kind VALUE ↔ FILENAME map (piece-1 spec §3 stage 5 — restated here
# because stage5_emit_stubs.py is not in this stage's script-hash deps)
KIND_FILES = {
    "item": "items.jsonl",
    "unlockable": "unlockables.jsonl",
    "room": "rooms.jsonl",
    "campus-level": "campus-levels.jsonl",
    "course": "courses.jsonl",
    "config": "configs.jsonl",
    "staff": "staff.jsonl",
    "metagame-node": "metagame-nodes.jsonl",
    "student-type": "student-types.jsonl",
}
STUB_KINDS = tuple(KIND_FILES)

# I2 LanguageSource mLanguages codes → the pipeline's 13-code BCP-47 set
# (tc.EMITTED_LOCALES). The sources register zh as CLDR codes; stage 4's
# bundle table spells them zh-Hans/zh-Hant. Everything else passes through.
LOCALE_CODE_NORMALIZATION = {"zh-CN": "zh-Hans", "zh-TW": "zh-Hant"}

_GUID_RE = re.compile(r"^[0-9a-f]{32}$")
_TOPFIELD_LIMIT = 10


class RelinkError(tc.StageError):
    pass


# ---------------------------------------------------------------------------
# Atomic whole-file + streaming JSONL writers (log_util discipline)

def stream_jsonl(path: Path, rows) -> None:
    """Write an iterable of dict rows as UTF-8 LF JSONL through a temp file
    and one atomic rename (interrupted-run convergence). Rows must already
    be in their final sorted order."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp",
                               dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            for row in rows:
                fh.write(log_util.dump_jsonl_row(row))
                fh.write("\n")
        os.replace(tmp, str(path))
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def clear_owned_outputs(relinks_dir: Path) -> None:
    """Remove every stage-6-owned child of relinks/ before regeneration.
    `locale_availability.jsonl` is stage-5 SOLE property (R4 pin) and is
    never touched — not deleted, not rewritten."""
    if not relinks_dir.is_dir():
        relinks_dir.mkdir(parents=True, exist_ok=True)
        return
    protected = {"locale_availability.jsonl"}
    for child in sorted(relinks_dir.iterdir()):
        if child.name in protected:
            continue
        if child.is_dir():
            import shutil
            shutil.rmtree(child)
        else:
            child.unlink()


# ---------------------------------------------------------------------------
# Payload walkers

def normalize_field_path(path: str) -> str:
    """'.RequiredItems[0].DefaultItem' → 'RequiredItems[].DefaultItem' —
    the repeat-collapse spelling used by dedup identity, evidence.topFields
    and the unresolved ledger."""
    s = path[1:] if path.startswith(".") else path
    return re.sub(r"\[\d+\]", "[]", s)


def bundle_base(rel: str) -> str:
    """Roster relpath → bare bundle filename. Stage-5 stub rows spell
    `source.bundle` as the bare filename (measured: `configs_assets_all.bundle`
    while the roster sidecars carry `TPC_Data/.../configs_assets_all.bundle`),
    and the piece-02 row examples pin that bare spelling for evidence — so
    resolution canonicalizes to the roster relpath internally and evidence
    spells bundles back as basenames. Basenames are unique across the 176-row
    roster (DLC files carry dlc-*- prefixes), so the round-trip is lossless."""
    return str(rel).replace("\\", "/").rsplit("/", 1)[-1]


def _is_pptr_leaf(node: dict) -> bool:
    return len(node) == 2 and "m_FileID" in node and "m_PathID" in node \
        and isinstance(node["m_FileID"], int) \
        and isinstance(node["m_PathID"], int)


def walk_pptr_leaves(fields):
    """Yield (leaf_key, field_path, m_FileID, m_PathID) for every exact
    `{m_FileID, m_PathID}` leaf under a stub field block, EXCLUDING the
    three non-relation families the piece-02 procedure names: zero-targets
    (`m_FileID == 0 && m_PathID == 0`), `m_GameObject` leaves and
    `m_Script` leaves (script identity already ships in-band as
    `_scriptClass`). Nested dicts/lists are descended iteratively;
    signed int64 path_ids pass through verbatim."""
    stack = [("", "", fields)]
    while stack:
        key, path, node = stack.pop()
        if isinstance(node, dict):
            if _is_pptr_leaf(node):
                leaf_key = key
                if leaf_key in ("m_GameObject", "m_Script"):
                    continue
                fid, pid = node["m_FileID"], node["m_PathID"]
                if fid == 0 and pid == 0:
                    continue          # zero-target null PPtr
                yield leaf_key, path, fid, pid
                continue
            prefix = f"{path}." if path else ""
            for k, v in node.items():
                stack.append((k, prefix + k, v))
        elif isinstance(node, list):
            for i, v in enumerate(node):
                stack.append((key, f"{path}[{i}]", v))


def walk_pptr_refs(fields_or_row):
    """Materialized PPtr-leaf walk — same exclusions as
    :func:`walk_pptr_leaves`, returned as a LIST of dicts (never a
    generator) so callers can serialize/len() it directly. Accepts either a
    bare fields block or a whole stub row (its `fields` member is walked):

        {"fieldPath": "RequiredItems[].DefaultItem", "leaf": "DefaultItem",
         "m_FileID": 0, "m_PathID": 3001}
    """
    fields = fields_or_row
    if isinstance(fields_or_row, dict) and "fields" in fields_or_row \
            and not _is_pptr_leaf(fields_or_row):
        fields = fields_or_row.get("fields") or {}
    out = []
    for leaf_key, raw_path, fid, pid in walk_pptr_leaves(fields or {}):
        out.append({"fieldPath": normalize_field_path(raw_path),
                    "leaf": leaf_key, "m_FileID": fid, "m_PathID": pid})
    return out


def walk_localised_strings(fields):
    """Yield (field_path, dev, term_id) for every two-key
    `{_dev, _termID}` LocalisedString struct under a stub field block."""
    stack = [("", fields)]
    while stack:
        path, node = stack.pop()
        if isinstance(node, dict):
            if "_dev" in node and "_termID" in node and len(node) <= 3 \
                    and isinstance(node.get("_termID"), int):
                yield path, str(node.get("_dev") or ""), int(node["_termID"])
                continue
            prefix = f"{path}." if path else ""
            for k, v in node.items():
                stack.append((prefix + k, v))
        elif isinstance(node, list):
            for i, v in enumerate(node):
                stack.append((f"{path}[{i}]", v))


def walk_guid_refs(fields):
    """Yield (field_path, guid, sub_object_name) for every AssetGUID-shaped
    reference: a 32-hex string under a guid-named dict member
    (`IconReference` shapes carry {m_AssetGUID, m_SubObjectName, …}); bare
    string fields whose name carries GUID/Guid count too."""
    results = []
    stack = [("", "", fields)]
    while stack:
        key, path, node = stack.pop()
        if isinstance(node, dict):
            sub = node.get("m_SubObjectName") if "m_AssetGUID" in node else None
            guid_val = node.get("m_AssetGUID")
            if isinstance(guid_val, str) and _GUID_RE.match(guid_val):
                results.append((path, guid_val,
                                sub if isinstance(sub, str) else ""))
                continue
            prefix = f"{path}." if path else ""
            for k, v in node.items():
                if isinstance(v, str):
                    if _GUID_RE.match(v) and "guid" in k.lower() \
                            and k != "m_AssetGUID":
                        results.append((prefix + k, v, ""))
                    continue
                stack.append((k, prefix + k, v))
        elif isinstance(node, list):
            for i, v in enumerate(node):
                stack.append((key, f"{path}[{i}]", v))
    results.reverse()
    return results


# ---------------------------------------------------------------------------
# R1 — bridge indexes

class CabTable:
    """Per-(bundle, serialized file) object table: parallel sorted arrays of
    path_ids and class-table indexes. Membership is bisect; class lookup is
    O(log n) + a shared intern table — ~24 bytes/object across the 2M-object
    corpus instead of per-object dicts."""

    __slots__ = ("pids", "cidx")

    def __init__(self, pairs):
        pairs = sorted(pairs)
        self.pids = array("q", (p for p, _ in pairs))
        self.cidx = array("i", (c for _, c in pairs))

    def has(self, path_id: int) -> bool:
        i = bisect.bisect_left(self.pids, path_id)
        return i < len(self.pids) and self.pids[i] == path_id

    def class_of(self, path_id: int):
        i = bisect.bisect_left(self.pids, path_id)
        if i < len(self.pids) and self.pids[i] == path_id:
            return self.cidx[i]
        return None


class BridgeIndexes:
    """The two R1 identity indexes plus the in-memory lookup structures the
    resolvers need. Emitted files: relinks/bridges/cab_index.jsonl (one row
    per serialized file) and relinks/bridges/container_index.jsonl (one row
    per address), both sorted by their pinned keys."""

    def __init__(self, build_id):
        self.build_id = build_id
        self.class_table: list[str] = []
        self._class_idx: dict[str, int] = {}
        self.cabs: dict[tuple[str, str], CabTable] = {}
        self.bundle_cabs: dict[str, list[str]] = {}
        self.cab_owners: dict[str, list[tuple[str, str]]] = {}
        self.container: dict[tuple[str, str], tuple[str, int, int]] = {}
        self.address_multi: dict[str, list[tuple[str, str, int, int]]] = {}
        # counters
        self.fallback_bundles: list[str] = []
        self.container_collisions = 0
        self.unreadable: list[tuple[str, str]] = []

    def class_idx(self, cls: str) -> int:
        idx = self._class_idx.get(cls)
        if idx is None:
            idx = len(self.class_table)
            self._class_idx[cls] = idx
            self.class_table.append(cls)
        return idx

    def class_name(self, idx: int) -> str:
        return self.class_table[idx]

    def add_bundle(self, bundle_rel: str, cab_objects, container_entries,
                   seeded: bool) -> tuple[list[dict], list[dict]]:
        """Register one opened bundle. `cab_objects` yields
        (cab_name_lower, [(path_id, class_name), …]); `container_entries`
        yields (cab_name_lower, address, path_id_or_None). Returns the
        (cab_rows, container_rows) emitted for this bundle, already sorted —
        the caller streams them so the full-corpus index never sits in one
        buffer. Bundle relpaths arrive in roster sort order, so appending
        per-bundle sorted rows keeps both files globally sorted."""
        if seeded:
            self.fallback_bundles.append(bundle_rel)
        cab_rows: list[dict] = []
        # Serialized-file identities are emitted VERBATIM (`CAB-<hex>` —
        # spec R1 spells the inner names as the client writes them) while
        # every INTERNAL key stays lowered, matching the externals sidecar's
        # normalization (simplify_external_path).
        per_cab: list[tuple[str, list[tuple[int, str]]]] = \
            [(cab, list(objs)) for cab, objs in cab_objects]
        per_cab.sort(key=lambda t: t[0].lower())
        tables: dict[str, CabTable] = {}
        for cab, objs in per_cab:
            cab_key = cab.lower()
            pairs = [(int(pid), self.class_idx(str(cls))) for pid, cls in objs]
            table = CabTable(pairs)
            tables[cab_key] = table
            self.cabs[(bundle_rel, cab_key)] = table
            self.cab_owners.setdefault(cab_key, []).append((bundle_rel, cab_key))
            cab_rows.append({
                "bundle": bundle_base(bundle_rel), "cab": cab,
                "objects": [{"pathId": pid, "class": self.class_table[c]}
                            for pid, c in pairs],
                "buildId": self.build_id})
        owners = self.bundle_cabs.setdefault(bundle_rel, [])
        owners.extend(cab.lower() for cab, _ in per_cab)

        seen_addr: set[str] = set()
        cont_rows: list[dict] = []
        entries: list[tuple[str, str, int, int]] = []
        ordered = sorted(container_entries,
                         key=lambda t: (str(t[0]), str(t[1]),
                                        int(t[2]) if t[2] is not None else -1))
        for cab, address, pid in ordered:
            ci = None
            tbl = tables.get(cab)
            if tbl is not None and pid is not None:
                ci = tbl.class_of(int(pid))
            if address in seen_addr:
                self.container_collisions += 1
                continue
            seen_addr.add(address)
            if ci is None:
                ci = self.class_idx("Unknown")
            # Unity path_ids are SIGNED int64 on this corpus (measured:
            # Config_Metagame dumps at -7582490196546434521), so a missing
            # pid must not be spelled -1 — that value is a legal pathId.
            # Unknown stays None internally; the emitted row spells -1 only
            # because the row contract needs an integer.
            pid_val = None if pid is None else int(pid)
            self.container[(bundle_rel, address)] = (cab, pid_val, ci)
            entries.append((address, cab, pid_val, ci))
        entries.sort(key=lambda t: t[0])
        for address, cab, pid, ci in entries:
            cont_rows.append({"bundle": bundle_base(bundle_rel),
                              "address": address,
                              "pathId": -1 if pid is None else pid,
                              "class": self.class_table[ci],
                              "buildId": self.build_id})
            self.address_multi.setdefault(address, []).append(
                (bundle_rel, cab, pid, ci))
        return cab_rows, cont_rows

    # -- lookups -------------------------------------------------------------

    def cab_of(self, bundle_rel: str, path_id: int):
        """The owning serialized file of `(bundle, path_id)`, or None."""
        for cab in self.bundle_cabs.get(bundle_rel, ()):
            if self.cabs[(bundle_rel, cab)].has(path_id):
                return cab
        return None

    def resolve_cab_path(self, cab: str, path_id: int):
        """All (bundle, cab) homes of an external `(cab, path_id)` target,
        roster-sorted. Unity path_ids are per-serialized-file while CAB names
        are corpus-wide unique in practice — multiple hits are legal and all
        are returned deterministically."""
        out = []
        for bundle_rel, owner_cab in self.cab_owners.get(cab, ()):
            if self.cabs[(bundle_rel, owner_cab)].has(path_id):
                out.append((bundle_rel, owner_cab))
        return out

    def container_exact(self, bundle_rel: str, address: str):
        hit = self.container.get((bundle_rel, address))
        # signed pathIds are legal (see add_bundle) — only None means unknown
        return None if hit is None or hit[1] is None else hit

    def container_by_address(self, address: str) -> list:
        return [e for e in self.address_multi.get(address, ())
                if e[2] is not None]


def extract_container_entries(env_file):
    """(cab, address, path_id) triples off one loaded serialized file's
    container map (UnityPy: `file.container.container` = [(address,
    AssetInfo)] where `.asset` is a PPtr or an ObjectReader)."""
    out = []
    cab = (getattr(env_file, "name", "") or "").lower()
    container = getattr(env_file, "container", None)
    entries = getattr(container, "container", None) or []
    for entry in entries:
        if not isinstance(entry, tuple) or len(entry) < 2:
            continue
        address, info = entry[0], entry[1]
        asset = getattr(info, "asset", None)
        pid = None
        if asset is not None:
            pid = getattr(asset, "path_id", None)
            if pid is None:
                pid = getattr(asset, "m_PathID", None)
        if pid is None:
            # fall back to the first object with a matching name? No —
            # unresolvable addresses still emit with pathId -1? The row
            # contract needs pathId; skip unresolvable ones and count them
            # via the caller's collision counter instead of inventing ids.
            continue
        out.append((cab, str(address), int(pid)))
    return out


def _env_items(envs):
    """(bundle, env) pairs from a mapping OR a sequence of pairs."""
    if hasattr(envs, "items"):
        return [(str(k), v) for k, v in envs.items()]
    return [(str(k), v) for k, v in envs]


def _iter_env_files(env):
    """Every serialized-file-like object under an opened environment,
    descending nested `.files` levels (same shape UnityPy environments
    present; duck-typed so synthetic stand-ins work identically)."""
    files = getattr(env, "files", None) or {}
    values = list(files.values()) if isinstance(files, dict) else list(files)
    stack = [f for f in values if f]
    out = []
    guard = 0
    while stack and guard < 4096:
        f = stack.pop(0)
        guard += 1
        out.append(f)
        child = getattr(f, "files", None)
        if isinstance(child, dict):
            stack.extend(g for g in child.values() if g)
    return out


def build_cab_index(envs, buildId=None):
    """R1 cab rows over ANY mapping/sequence of `bundle -> environment`:
    one row per serialized file
    `{bundle, cab, objects:[{pathId, class}], buildId}` sorted by
    (bundle, cab). Duck-typed on `.files`/`.objects`/`.type.name`, so it
    drives real UnityPy environments and lightweight stand-ins alike.
    `buildId` spells the emitted-row contract's key."""
    bid = tc.BUILD_ID if buildId is None else int(buildId)
    rows = []
    for bundle, env in _env_items(envs):
        for f in _iter_env_files(env):
            objs = getattr(f, "objects", None) or {}
            entries = []
            for pid in sorted(objs, key=int):
                cls = getattr(getattr(objs[pid], "type", None), "name",
                              "Unknown")
                entries.append({"pathId": int(pid), "class": str(cls)})
            rows.append({"bundle": bundle_base(bundle),
                         "cab": str(getattr(f, "name", "") or ""),
                         "objects": entries, "buildId": bid})
    rows.sort(key=lambda r: (r["bundle"], r["cab"]))
    return rows


def build_container_index(envs, buildId=None):
    """R1 container rows over the same environment shapes: one row per
    address `{bundle, address, pathId, class, buildId}` sorted by
    (bundle, address)."""
    bid = tc.BUILD_ID if buildId is None else int(buildId)
    rows = []
    for bundle, env in _env_items(envs):
        container = getattr(env, "container", None) or {}
        items = container.items() if hasattr(container, "items") else []
        for address, obj in items:
            pid = getattr(obj, "path_id", None)
            if pid is None:
                pid = getattr(obj, "m_PathID", None)
            cls = getattr(getattr(obj, "type", None), "name", "Unknown")
            rows.append({"bundle": bundle_base(bundle), "address": str(address),
                         "pathId": int(pid) if pid is not None else -1,
                         "class": str(cls), "buildId": bid})
    rows.sort(key=lambda r: (r["bundle"], r["address"]))
    return rows


def simplify_external_path(path: str) -> str:
    """`archive:/CAB-xxx/CAB-xxx` → `cab-xxx` — the externals match key
    (same normalization stage-3's sidecar consumers use)."""
    p = str(path).replace("\\", "/")
    if p.startswith("archive:/"):
        p = p[len("archive:/"):]
    if p.startswith("assets/"):
        p = p[len("assets/"):]
    return p.rsplit("/", 1)[-1].lower()


def load_externals(path: Path) -> dict:
    """harvest/externals.jsonl → {(bundle, sourceFile): {fileId: path}}."""
    table: dict[tuple[str, str], dict[int, str]] = {}
    with open(path, "r", encoding="utf-8", newline="\n") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            entries = {}
            for ext in row.get("externals") or []:
                entries[int(ext["fileId"])] = str(ext.get("path") or "")
            table[(row["bundle"], str(row["sourceFile"]).lower())] = entries
    return table


def builtin_external(path: str) -> bool:
    """True when an external path is a Unity built-in resource
    (`Library/unity default resources`, `Resources/unity_builtin_extra`, …)
    rather than an in-bundle `archive:/CAB-…` reference. Built-ins are not
    entity targets: counted, ledgered, never resolved into pairs."""
    return not str(path).startswith("archive:")


# ---------------------------------------------------------------------------
# Stub loading + resolution indexes

class StubIndex:
    """Emitted-entity universe: (bundle, pathId) → (kind, id) plus the
    per-kind id sets the AC4 verbatim check resolves against."""

    def __init__(self):
        self.by_location: dict[tuple[str, int], tuple[str, str]] = {}
        self.ids_by_kind: dict[str, set[str]] = {k: set() for k in STUB_KINDS}
        self.rows_by_kind: dict[str, list[dict]] = {k: [] for k in STUB_KINDS}
        self.axes: dict[tuple[str, str], list[str]] = {}

    def add_row(self, row: dict) -> None:
        kind = row["kind"]
        eid = str(row["id"])
        src = row.get("source") or {}
        bundle, pid = src.get("bundle"), src.get("pathId")
        self.rows_by_kind[kind].append(row)
        self.ids_by_kind[kind].add(eid)
        axes = row.get("axes")
        if isinstance(axes, list) and axes:
            self.axes[(kind, eid)] = sorted(str(a) for a in axes)
        if bundle is not None and pid is not None:
            self.by_location[(str(bundle), int(pid))] = (kind, eid)

    def at(self, bundle: str, path_id: int):
        return self.by_location.get((str(bundle), int(path_id)))

    def source_axes(self, kind: str, eid: str) -> list[str]:
        return self.axes.get((kind, eid), [])


def load_stubs(stubs_dir: Path,
               bundle_map: dict[str, str] | None = None) -> StubIndex:
    """Load the 9 emitted kind files. `bundle_map` (bare bundle filename →
    roster relpath) canonicalizes `source.bundle` so every resolver downstream
    shares ONE spelling with the roster/externals/bridge keys; the bare name
    stays reachable through bundle_base() for evidence emission."""
    idx = StubIndex()
    for kind in STUB_KINDS:
        path = stubs_dir / KIND_FILES[kind]
        if not path.is_file():
            continue   # absence-ledgered family — upstream set checked elsewhere
        with open(path, "r", encoding="utf-8", newline="\n") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    row = json.loads(line)
                    if bundle_map:
                        src = row.get("source") or {}
                        orig = src.get("bundle")
                        if orig is not None:
                            src["bundle"] = bundle_map.get(
                                str(orig), str(orig))
                            row["source"] = src
                    idx.add_row(row)
    return idx


# ---------------------------------------------------------------------------
# Pair-edge accumulator (dedup identity pinned by piece-02 §3 R2)

class EdgeAccumulator:
    """Dedup identity: (srcKind, srcId, dstKind, dstId, method, fieldPath).
    Repeats inside one array field collapse into refCount; evidence of a
    merged group keeps the lexicographically smallest location triple so
    walk order can never change bytes. `build_id` stamps the frozen row
    contract's `buildId` key at finalize time (piece-1 provenance rule:
    buildId on 100% of rows)."""

    def __init__(self, build_id=None):
        self.groups: dict[tuple, dict] = {}
        self.build_id = build_id

    def add(self, src_kind, src_id, dst_kind, dst_id, method, field_path,
            evidence, inferred, mechanism="hard"):
        key = (src_kind, src_id, dst_kind, dst_id, method, field_path)
        g = self.groups.get(key)
        raw_loc = (str(evidence.get("dstBundle", "")),
                   int(evidence.get("dstPathId", 0) or 0),
                   str(evidence.get("dstCab", "")))
        if g is None:
            ev = dict(evidence)
            ev["refCount"] = 1
            self.groups[key] = {
                "srcKind": src_kind, "srcId": src_id,
                "dstKind": dst_kind, "dstId": dst_id,
                "mechanism": mechanism, "method": method,
                "inferred": bool(inferred),
                "evidence": ev,
                "_loc": raw_loc,
            }
        else:
            g["evidence"]["refCount"] += 1
            if raw_loc < g["_loc"]:
                keep_refcount = g["evidence"]["refCount"]
                g["evidence"] = dict(evidence)
                g["evidence"]["refCount"] = keep_refcount
                g["_loc"] = raw_loc

    def by_cell(self) -> dict:
        cells: dict[tuple[str, str], list[dict]] = {}
        for (sk, _si, dk, _di, _m, _fp), g in self.groups.items():
            cells.setdefault((sk, dk), []).append(g)
        return cells

    def rows_for_cell(self, src_kind: str, dst_kind: str) -> list[dict]:
        out = []
        for (sk, _si, dk, _di, method, fp), g in self.groups.items():
            if sk == src_kind and dk == dst_kind:
                out.append(g)
        out.sort(key=lambda g: (g["srcKind"], g["srcId"], g["dstKind"],
                                g["dstId"], g["method"],
                                g["evidence"]["fieldPath"]))
        return [self.finalize(g) for g in out]

    def finalize(self, g: dict) -> dict:
        row = {k: g[k] for k in ("srcKind", "srcId", "dstKind", "dstId",
                                 "mechanism", "method", "inferred")}
        row["evidence"] = {k: v for k, v in sorted(g["evidence"].items())}
        if self.build_id is not None:
            row["buildId"] = self.build_id
        return row

    def all_sorted_rows(self) -> list[dict]:
        out = [self.finalize(g) for g in self.groups.values()]
        out.sort(key=lambda r: (r["srcKind"], r["srcId"], r["dstKind"],
                                r["dstId"], r["method"],
                                r["evidence"]["fieldPath"]))
        return out


def attach_source_axes(rows, stubs: StubIndex) -> list[dict]:
    """Axes provenance (scout §3): a row inherits `sourceAxes` from its
    endpoint rows' `axes` when present (omitted when both absent — most
    rows). Twin endpoints keep the `@hash8` id; nothing collapses."""
    out = []
    for row in rows:
        axes = set(stubs.source_axes(row["srcKind"], row["srcId"]))
        dst_kind, dst_id = row["dstKind"], row["dstId"]
        if dst_kind in stubs.ids_by_kind:
            axes |= set(stubs.source_axes(dst_kind, dst_id))
        if axes:
            row = dict(row)
            row["sourceAxes"] = sorted(axes)
        out.append(row)
    return out


# ---------------------------------------------------------------------------
# Cross-file PPtr resolution (R2) — the externals → cab-index ladder

class CrossFileResolver:
    """Resolve `{m_FileID ≥ 1, m_PathID}` leaves through
    harvest/externals.jsonl → cab_index membership → stub index / scene
    attribution. Every failure mode returns a structured outcome; nothing
    is swallowed."""

    def __init__(self, bridges: BridgeIndexes, externals: dict,
                 stubs: StubIndex, scene_bundles: dict[str, str]):
        self.bridges = bridges
        self.externals = externals
        self.stubs = stubs
        self.scene_bundles = scene_bundles   # relpath → sceneFlag (!= none)

    def same_file_target(self, bundle: str, path_id: int):
        """{'status':'stub',…} | {'status':'scene',…} | None for a
        same-file reference."""
        hit = self.stubs.at(bundle, path_id)
        if hit is not None:
            return {"status": "stub", "kind": hit[0], "id": hit[1],
                    "bundle": bundle, "cab": ""}
        if bundle in self.scene_bundles:
            return {"status": "scene", "relpath": bundle,
                    "bundle": bundle, "cab": ""}
        return None

    def resolve(self, src_bundle: str, src_cab: str, ext_file_id: int,
                path_id: int) -> dict:
        """{'status':'stub'|'scene'|'builtin'|'unresolved', …} — every
        failure mode names its cause; nothing swallowed."""
        exts = self.externals.get((src_bundle, src_cab)) \
            if src_cab is not None else None
        if exts is None:
            return {"status": "unresolved",
                    "reason": "owning serialized file unknown for source "
                              "dump", "extPath": ""}
        path = exts.get(ext_file_id)
        if path is None:
            return {"status": "unresolved",
                    "reason": f"external fileId {ext_file_id} not in the "
                              "serialized file's externals table",
                    "extPath": ""}
        if builtin_external(path):
            return {"status": "builtin", "extPath": str(path),
                    "reason": f"built-in external is not an entity "
                              f"target: {path}"}
        cab = simplify_external_path(path)
        homes = self.bridges.resolve_cab_path(cab, path_id)
        if not homes:
            return {"status": "unresolved",
                    "reason": "external CAB/pathId not found in any indexed "
                              "serialized file", "extPath": cab}
        for bundle_rel, _home_cab in homes:
            hit = self.stubs.at(bundle_rel, path_id)
            if hit is not None:
                return {"status": "stub", "kind": hit[0], "id": hit[1],
                        "bundle": bundle_rel, "cab": cab}
        for bundle_rel, _home_cab in homes:
            if bundle_rel in self.scene_bundles:
                return {"status": "scene", "relpath": bundle_rel,
                        "bundle": bundle_rel, "cab": cab}
        return {"status": "unresolved",
                "reason": "pathId exists in the resolved file but is not an "
                          "emitted stub entity", "extPath": cab}

    def scene_attribution(self, bundle_rel: str) -> bool:
        """True when a target bundle carries a roster scene flag (R2
        attribution rule)."""
        return bundle_rel in self.scene_bundles


def resolve_cross_file(externals_by_bundle, cab_index_rows, stub_index,
                       source, ext_file_id=None, path_id=None,
                       field_path="", scene_bundles=None):
    """Pure-data cross-file ladder (piece-02 §3 R2): externals fileId →
    external CAB → owning serialized files → stub id / scene attribution /
    structured failure. Mirrors :class:`CrossFileResolver` for callers
    holding RAW rows instead of loaded indexes:

    - ``externals_by_bundle``: bundle → list of `{fileId, path}` entries
      (the merged per-bundle view of harvest/externals.jsonl) or a
      `{fileId: path}` mapping;
    - ``cab_index_rows``: cab_index rows (`{bundle, cab, objects[]}`);
    - ``stub_index``: `(bare bundle filename, pathId) -> (kind, id)`;
    - ``source``: the source bundle filename, or a dict carrying
      `bundle` / `m_FileID` / `m_PathID` (+ optional `fieldPath`);
    - ``scene_bundles``: optional roster relpath/basename set (or mapping)
      of scene-flagged bundles for the attribution rule.

    Returns one structured outcome dict; every failure mode names its
    cause and nothing is swallowed.
    """
    if isinstance(source, dict):
        bundle = str(source.get("bundle"))
        ext_file_id = source.get("m_FileID", ext_file_id)
        path_id = source.get("m_PathID", path_id)
        field_path = source.get("fieldPath") or field_path
    else:
        bundle = str(source)

    def out(status, **kw):
        kw.update({"status": status, "fieldPath": field_path})
        if kw.get("extPath") is None:
            kw.pop("extPath", None)
        return kw

    entry = externals_by_bundle.get(bundle)
    exts: dict[int, str] = {}
    if isinstance(entry, dict):
        exts = {int(k): str(v) for k, v in entry.items()}
    elif isinstance(entry, list):
        for e in entry:
            exts[int(e["fileId"])] = str(e.get("path") or "")
    if entry is None:
        return out("unresolved", reason=f"no externals table for bundle "
                                        f"{bundle}", extPath="")
    path = exts.get(int(ext_file_id))
    if path is None:
        return out("unresolved",
                   reason=f"external fileId {ext_file_id} not in the "
                          "serialized file's externals table", extPath="")
    if builtin_external(path):
        return out("builtin", extPath=str(path),
                   reason=f"built-in external is not an entity target: "
                          f"{path}")
    cab = simplify_external_path(path)
    homes = []
    for row in cab_index_rows:
        if str(row.get("cab", "")).lower() != cab:
            continue
        pids = {int(o["pathId"]) for o in row.get("objects") or []}
        if int(path_id) in pids:
            homes.append(str(row["bundle"]))
    # scene_bundles carries ONLY flagged bundles whether it is a set of
    # relpaths or a relpath->flag mapping, so membership decides either way
    scenes = scene_bundles or {}
    for b in homes:
        hit = stub_index.get((b, int(path_id)))
        if hit is not None:
            return out("stub", kind=hit[0], id=hit[1], bundle=b, cab=cab,
                       extFileId=int(ext_file_id))
    for b in homes:
        if b in scenes:
            return out("scene", relpath=b, bundle=b, cab=cab,
                       extFileId=int(ext_file_id))
    if not homes:
        return out("unresolved",
                   reason="dangling-path-id: external CAB/pathId not found "
                          "in any indexed serialized file", extPath=cab)
    return out("unresolved",
               reason="pathId exists in the resolved serialized file but "
                      "is not an emitted stub entity", extPath=cab)


# ---------------------------------------------------------------------------
# R4 — I2 term registry

def normalize_locale_code(code: str) -> str:
    return LOCALE_CODE_NORMALIZATION.get(str(code), str(code))


def build_i2_registry(source_paths, build_id) -> tuple[list[dict], dict]:
    """One row per (termId, termKey) FROM THE LanguageSource dumps (F7 glob)
    — never from the scout scratch seed. canonical:true marks the primary ID
    when a key registered under multiple IDs (G10: canonicalize on Term KEY,
    keep every ID). Sorted by (termKey, termId)."""
    raw: list[dict] = []
    stats = {"sourcesRead": 0, "termRowsRaw": 0}
    for path in sorted(source_paths):
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
        except ValueError:
            continue
        stats["sourcesRead"] += 1
        source = payload.get("mSource") or {}
        lang_codes = [normalize_locale_code(l.get("Code"))
                      for l in (source.get("mLanguages") or [])
                      if isinstance(l, dict)]
        source_asset = str(payload.get("m_Name")
                           or Path(path).stem)
        for term in source.get("mTerms") or []:
            term_key = term.get("Term")
            term_id = term.get("ID")
            if not isinstance(term_key, str) or not term_key:
                continue
            texts = term.get("Languages") or []
            locales = sorted({lang_codes[i] for i in range(min(len(texts),
                             len(lang_codes))) if texts[i]})
            raw.append({
                "termId": int(term_id),
                "termKey": term_key,
                "sourceAsset": source_asset,
                "termType": term.get("TermType"),
                "termStatus": term.get("TermStatus"),
                "locales": locales,
                "_path": str(path),
            })
            stats["termRowsRaw"] += 1

    merged: dict[tuple[int, str], dict] = {}
    for r in raw:
        key = (r["termId"], r["termKey"])
        cur = merged.get(key)
        if cur is None:
            merged[key] = r
            continue
        # duplicate registration across source dumps: union the locale
        # projection, keep the lexicographically-first source asset
        cur["locales"] = sorted(set(cur["locales"]) | set(r["locales"]))
        if r["sourceAsset"] < cur["sourceAsset"]:
            cur["sourceAsset"] = r["sourceAsset"]

    keys_min_id: dict[str, int] = {}
    for (tid, tk) in merged:
        if tk not in keys_min_id or tid < keys_min_id[tk]:
            keys_min_id[tk] = tid

    rows = []
    for (tid, tk) in sorted(merged, key=lambda k: (k[1], k[0])):
        r = merged[(tid, tk)]
        rows.append({
            "termId": tid, "termKey": tk,
            "sourceAsset": r["sourceAsset"],
            "termType": r["termType"], "termStatus": r["termStatus"],
            "locales": r["locales"],
            "canonical": tid == keys_min_id[tk],
            "buildId": build_id,
        })
    stats["registryRows"] = len(rows)
    stats["registryDistinctKeys"] = len(keys_min_id)
    return rows, stats


class TermRegistry:
    """ID → row lookup over the built registry (canonical row wins when a
    key registered under several IDs — every ID stays a valid lookup)."""

    def __init__(self, registry_rows):
        self.by_id: dict[int, dict] = {}
        self.keys: set[str] = set()
        self.locales_by_key: dict[str, list[str]] = {}
        canonical_by_key: dict[str, dict] = {}
        for r in registry_rows:
            self.by_id[r["termId"]] = r
            self.keys.add(r["termKey"])
            cur = canonical_by_key.get(r["termKey"])
            if cur is None or (r["canonical"] and not cur["canonical"]):
                canonical_by_key[r["termKey"]] = r
        for k, r in canonical_by_key.items():
            self.locales_by_key[k] = r["locales"]

    def get(self, term_id: int):
        return self.by_id.get(int(term_id))

    def locales_for_key(self, term_key: str) -> list[str]:
        return self.locales_by_key.get(term_key, [])


def build_entity_locale(stub_fields_source, registry: TermRegistry, build_id):
    """Walk ALL stub payloads for `{_dev, _termID}` structs →
    (entity_locale rows, reverse-index rows, report dict). Sentinel
    `_termID == 0` instances are EXCLUDED from rows and COUNTED
    (declared-empty class G4). Misses land only in the report."""
    instances_total = sentinel_zero = registry_hits = registry_misses = 0
    misses: dict[int, list] = {}
    per_kind_hits: Counter = Counter()
    loc_rows: list[dict] = []
    for src_kind, src_id, field_path, dev, term_id in stub_fields_source:
        instances_total += 1
        if term_id == 0:
            sentinel_zero += 1
            continue
        reg = registry.get(term_id)
        if reg is None:
            registry_misses += 1
            refs = misses.setdefault(term_id, [])
            if len(refs) < 5:
                refs.append({"srcKind": src_kind, "srcId": src_id,
                             "fieldPath": field_path})
            continue
        registry_hits += 1
        per_kind_hits[src_kind] += 1
        loc_rows.append({
            "srcKind": src_kind, "srcId": src_id,
            "dstKind": "locale-term", "dstId": reg["termKey"],
            "mechanism": "hard", "method": METHOD_I2,
            "inferred": False,
            "evidence": {"fieldPath": field_path, "termId": term_id,
                         "dev": dev, "locales": list(reg["locales"])},
            "buildId": build_id,
        })
    loc_rows.sort(key=lambda r: (r["srcKind"], r["srcId"],
                                 r["evidence"]["fieldPath"], r["dstId"]))

    grouped: dict[str, list[dict]] = {}
    for r in loc_rows:
        grouped.setdefault(r["dstId"], []).append(
            {"srcKind": r["srcKind"], "srcId": r["srcId"],
             "fieldPath": r["evidence"]["fieldPath"]})
    reverse_rows = []
    for term_key in sorted(grouped):
        usages = sorted(grouped[term_key],
                        key=lambda u: (u["srcKind"], u["srcId"],
                                       u["fieldPath"]))
        reverse_rows.append({
            "termKey": term_key, "usages": usages,
            "locales": registry.locales_for_key(term_key),
            "buildId": build_id})

    non_empty = registry_hits + registry_misses
    report = {
        "instancesTotal": instances_total,
        "sentinelZero": sentinel_zero,
        "registryHits": registry_hits,
        "registryMisses": registry_misses,
        "unresolvedIds": [{"termId": tid, "sampleRefs": misses[tid]}
                          for tid in sorted(misses)],
        "coverageOnNonEmpty": (registry_hits / non_empty) if non_empty else 0.0,
        "perKindHits": {k: per_kind_hits[k] for k in sorted(per_kind_hits)},
        "buildId": build_id,
    }
    return loc_rows, reverse_rows, report


def iter_stub_localised(stubs: StubIndex):
    """(srcKind, srcId, fieldPath, dev, termId) for every LocalisedString
    instance in every emitted stub row — deterministic order."""
    for kind in STUB_KINDS:
        for row in sorted(stubs.rows_by_kind[kind],
                          key=lambda r: str(r["id"])):
            src_id = str(row["id"])
            for path, dev, term_id in walk_localised_strings(
                    row.get("fields") or {}):
                yield kind, src_id, normalize_field_path(path), dev, term_id


def _normalize_i2_sources(sources):
    """Registry source spec → list of dump paths. Accepts a directory
    (str/Path), a glob string, or an explicit path sequence."""
    if isinstance(sources, (list, tuple)):
        return [Path(p) for p in sources]
    if isinstance(sources, (str, Path)):
        s = str(sources)
        if any(ch in s for ch in "*?["):
            import glob as _glob
            return [Path(p) for p in sorted(_glob.glob(s))]
        p = Path(sources)
        if p.is_dir():
            return sorted(p.glob("*.json"))
        return [p]
    raise TypeError(f"unsupported I2 LanguageSource spec: {sources!r}")


def build_i2_term_registry(sources, build_id=None):
    """One row per (termId, termKey) from the F7 LanguageSource dumps,
    accepting the dump DIRECTORY (str/Path), a glob string, or an explicit
    path list. canonical-on-key per G10; every ID stays a row."""
    if build_id is None:
        build_id = tc.BUILD_ID
    rows, _stats = build_i2_registry(_normalize_i2_sources(sources), build_id)
    return rows


def emit_entity_locale(stub_fields_source, registry, build_id=None):
    """entity_locale emission seam. Accepts EITHER `(stubs_dir, rows)` or
    `(rows, stubs_dir)` — where rows is any TermRegistry-rows list — or a
    ready iterable of `(srcKind, srcId, fieldPath, dev, termId)` tuples as
    the first argument with a registry second. Returns
    (loc_rows, reverse_rows, report) exactly like
    :func:`build_entity_locale`; sentinel `_termID == 0` instances are
    excluded from rows and counted in the report."""
    if build_id is None:
        build_id = tc.BUILD_ID

    def is_rows(v):
        return isinstance(v, (list, tuple)) and bool(v) \
            and isinstance(v[0], dict) and "termKey" in v[0]

    def is_dir_arg(v):
        return isinstance(v, (str, os.PathLike))

    src, reg_arg = stub_fields_source, registry
    if is_rows(src) and is_dir_arg(reg_arg):
        src, reg_arg = reg_arg, src
    reg = reg_arg if isinstance(reg_arg, TermRegistry) else TermRegistry(reg_arg)
    if isinstance(src, (str, os.PathLike)):
        src = iter_stub_localised(load_stubs(Path(src)))
    return build_entity_locale(src, reg, build_id)


# ---------------------------------------------------------------------------
# Row validators (AC3 — exact key sets, enums, frozen vocabularies)

_PAIR_TOP_REQUIRED = frozenset({
    "srcKind", "srcId", "dstKind", "dstId", "mechanism", "method",
    "inferred", "evidence", "buildId"})
_PAIR_TOP_ALLOWED = _PAIR_TOP_REQUIRED | {"sourceAxes"}

_EVIDENCE_BY_METHOD = {
    METHOD_PTR_SAME: frozenset({"fieldPath", "srcBundle", "srcPathId",
                                "dstBundle", "dstPathId", "refCount"}),
    METHOD_PTR_CROSS: frozenset({"fieldPath", "srcBundle", "srcPathId",
                                 "dstBundle", "dstPathId", "refCount",
                                 "extFileId", "dstCab", "resolvedVia"}),
    METHOD_GUID: frozenset({"fieldPath", "assetGuid", "catalogAddress"}),
}


def validate_pair_row(row: dict, node_universe=frozenset(NODE_UNIVERSE)) -> None:
    top = set(row)
    missing = _PAIR_TOP_REQUIRED - top
    extra = top - _PAIR_TOP_ALLOWED
    if missing:
        raise RelinkError(f"pair row missing keys {sorted(missing)}: "
                          f"{row.get('srcKind')}/{row.get('srcId')}", 1)
    if extra:
        raise RelinkError(f"pair row carries unknown keys {sorted(extra)}: "
                          f"{row.get('srcKind')}/{row.get('srcId')}", 1)
    if row["mechanism"] not in MECHANISMS:
        raise RelinkError(f"pair row mechanism '{row['mechanism']}' outside "
                          "the frozen enum", 1)
    known_methods = {METHOD_PTR_SAME, METHOD_PTR_CROSS, METHOD_GUID,
                     METHOD_I2}
    method = row["method"]
    is_overlay = method.startswith("competitor-model:")
    is_convention = method.startswith("name-convention:")
    if not (is_overlay or is_convention or method in known_methods):
        raise RelinkError(f"pair row method '{method}' outside the frozen "
                          "vocabulary", 1)
    for key in ("srcId", "dstId"):
        if not isinstance(row[key], str) or not row[key]:
            raise RelinkError(f"pair row {key} must be a non-empty verbatim "
                              "string (never slugified)", 1)
    if row["dstKind"] == SCENE_NODE and row["dstKind"] not in node_universe:
        raise RelinkError("scene destination without the scene node", 1)
    ev = row["evidence"]
    if not isinstance(ev, dict):
        raise RelinkError("pair row evidence must be an object", 1)
    optional_keys: frozenset = frozenset()
    if is_overlay:
        want = {"claim", "sourcePage"}
        # the accumulator stamps refCount on every merged group (AC3: int ≥ 1)
        optional_keys = frozenset({"refCount"})
    elif is_convention:
        want = {"fieldPath"}
        optional_keys = frozenset({"refCount"})
    elif method == METHOD_I2:
        want = {"fieldPath", "termId", "dev", "locales"}
    elif method == METHOD_GUID and row["dstKind"] == "asset":
        want = None  # asset rows validated separately
    else:
        want = _EVIDENCE_BY_METHOD.get(method)
        if want is None:
            raise RelinkError(f"pair row method '{method}' has no evidence "
                              "contract", 1)
    if want is not None:
        got = set(ev)
        if got != set(want) and got != set(want) | set(optional_keys):
            raise RelinkError(
                f"pair row evidence keys {sorted(got)} != contract "
                f"{sorted(want)} (+optional {sorted(optional_keys)})"
                f" for method {method}", 1)
    rc = ev.get("refCount")
    if rc is not None and (not isinstance(rc, int) or rc < 1):
        raise RelinkError("refCount must be an int >= 1", 1)


def validate_guid_asset_row(row: dict) -> None:
    if set(row) != {"srcKind", "srcId", "dstKind", "dstId", "mechanism",
                    "method", "inferred", "evidence", "buildId"}:
        raise RelinkError("entity_asset_guid row shape violated", 1)
    if row["dstKind"] != "asset" or row["method"] != METHOD_GUID \
            or row["inferred"] is not False or row["mechanism"] != "hard":
        raise RelinkError("entity_asset_guid row vocabulary violated", 1)
    want = {"fieldPath", "assetGuid", "resolvedVia"}
    got = set(row["evidence"])
    if got != want and got != want | {"subObjectName"}:
        raise RelinkError(f"entity_asset_guid evidence keys {sorted(got)} "
                          f"!= contract {sorted(want)} (+optional "
                          "subObjectName)", 1)


def validate_matrix(matrix: dict) -> None:
    meta = matrix.get("meta") or {}
    nodes = ((meta.get("nodeUniverse") or {}).get("nodes"))
    if nodes != list(NODE_UNIVERSE):
        raise RelinkError("matrix nodeUniverse does not match the pinned "
                          "10-node universe/order", 1)
    if (meta.get("nodeUniverse") or {}).get("arithmetic") != NODE_ARITHMETIC:
        raise RelinkError("matrix arithmetic string mismatch", 1)
    pairs = matrix.get("pairs") or []
    if len(pairs) != 100:
        raise RelinkError(f"matrix pairs length {len(pairs)} != 100", 1)
    expected = [(a, b) for a in NODE_UNIVERSE for b in NODE_UNIVERSE]
    for cell, (want_s, want_d) in zip(pairs, expected):
        if cell.get("srcKind") != want_s or cell.get("dstKind") != want_d:
            raise RelinkError(f"matrix pairs[] ordering broken at "
                              f"{want_s}->{want_d}", 1)
        status = cell.get("status")
        if status not in STATUSES:
            raise RelinkError(f"cell {want_s}->{want_d} status "
                              f"'{status}' outside the enum", 1)
        if status in ("partial", "missing") \
                and not str(cell.get("unblock") or "").strip():
            raise RelinkError(f"cell {want_s}->{want_d} is {status} without "
                              "an unblock", 1)
        for req in ("joinKey", "mechanism", "cardinality", "pairFiles"):
            if req not in cell:
                raise RelinkError(f"cell {want_s}->{want_d} missing "
                                  f"'{req}'", 1)


# ---------------------------------------------------------------------------
# Competitor application (R6)

SOURCE_IDS = ("fandom", "wiki-gg", "steam-guides", "reddit", "ign",
              "game8", "neoseeker")

# community kind → our node universe (declared convention; anything absent
# is not an entity kind and flags-missing on the object side)
COMMUNITY_KIND_MAP = {
    "item": "item",
    "course": "course",
    "room": "room",
    "campus": "campus-level",
    "archetype": "student-type",
    "event": "config",
    "research-project": "metagame-node",
    "assignment": "config",
}

_FLOOR_SOURCES = 3


def _norm_community(name: str) -> str:
    return re.sub(r"[\s\-]+", "_", str(name).strip()).casefold()


class CommunityResolver:
    """Community names → internal ids: exact verbatim match against the
    stub id space first, then the declared casefold/_↔space convention
    (flagged inferred). Unresolvable names do NOT vanish."""

    def __init__(self, stubs: StubIndex):
        exact: dict[str, dict[str, str]] = {}
        folded: dict[str, dict[str, list[str]]] = {}
        for kind, ids in stubs.ids_by_kind.items():
            for i in ids:
                exact.setdefault(kind, {})[i] = i
                folded.setdefault(kind, {}).setdefault(
                    _norm_community(i), []).append(i)
        self.exact = exact
        self.folded = {k: {f: v[0] if len(v) == 1 else sorted(v)[0]
                           for f, v in m.items()}
                       for k, m in folded.items()}
        self.all_folded = {k: sorted(m) for k, m in folded.items()}

    def resolve(self, kind: str, name: str):
        """(id, inferred_flag) | (None, closest_candidates)."""
        ids = self.exact.get(kind)
        if ids is None:
            return None, []
        if name in ids:
            return name, False
        hit = self.folded.get(kind, {}).get(_norm_community(name))
        if hit is not None:
            return hit, True
        nf = _norm_community(name)
        tokens = set(nf.split("_"))
        scored = []
        for cand in self.all_folded.get(kind, ()):  # deterministic order
            ct = set(cand.split("_"))
            overlap = len(tokens & ct)
            if overlap:
                scored.append((-overlap, len(cand), cand))
        closest = []
        for neg, _l, cand in sorted(scored)[:3]:
            base = self.folded.get(kind, {}).get(cand, cand)
            closest.append(base)
        return None, closest


def apply_competitor_sources(competitor_root: Path, stubs: StubIndex,
                             measured_cells: set, build_id):
    """Consume data/sources/competitor/<source-id>/model.jsonl bytes
    deterministically. Returns (ledger_rows, overlay_edges, counters).
    Absent inputs read as FLOOR-UNMET, never as exit-3."""
    resolver = CommunityResolver(stubs)
    ledger: list[dict] = []
    overlays = EdgeAccumulator(build_id=build_id)
    counts = {"sourcesRead": 0, "confirmsHard": 0, "addsDerived": 0,
              "flagsMissing": 0, "wallsRecorded": 0}
    for sid in SOURCE_IDS:
        model = competitor_root / sid / "model.jsonl"
        if not model.is_file():
            wall = competitor_root / sid / "wall.json"
            if wall.is_file():
                try:
                    w = json.loads(wall.read_text(encoding="utf-8"))
                except ValueError:
                    w = {}
                counts["wallsRecorded"] += 1
                ledger.append({
                    "sourceId": sid, "rung": str(w.get("rung", "wall")),
                    "dispositions": {"confirms-hard": 0, "adds-derived": 0,
                                     "flags-missing": 0},
                    "wall": {"httpStatus": w.get("httpStatus"),
                             "oneQuestionItWouldHaveAnswered":
                                 w.get("oneQuestionItWouldHaveAnswered")},
                    "buildId": build_id})
            continue
        counts["sourcesRead"] += 1
        disp = {"confirms-hard": 0, "adds-derived": 0, "flags-missing": 0}
        with open(model, "r", encoding="utf-8", newline="\n") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                claim = json.loads(line)
                subj_kind = COMMUNITY_KIND_MAP.get(str(claim.get("subjectKind")))
                obj_kind = COMMUNITY_KIND_MAP.get(str(claim.get("objectKind")))
                subj_id, _ = (resolver.resolve(str(claim.get("subjectKind")),
                                               str(claim.get("subjectName")))
                              if subj_kind else (None, []))
                obj_id, obj_close = (resolver.resolve(str(claim.get("objectKind")),
                                                      str(claim.get("objectName")))
                                     if obj_kind else (None, []))
                if subj_kind is None or obj_kind is None or subj_id is None \
                        or obj_id is None:
                    disp["flags-missing"] += 1
                    counts["flagsMissing"] += 1
                    continue
                cell = (subj_kind, obj_kind)
                edge_id = (subj_kind, subj_id, obj_kind, obj_id)
                if edge_id in measured_cells:
                    disp["confirms-hard"] += 1
                    counts["confirmsHard"] += 1
                else:
                    disp["adds-derived"] += 1
                    counts["addsDerived"] += 1
                    overlays.add(
                        subj_kind, subj_id, obj_kind, obj_id,
                        f"competitor-model:{sid}",
                        str(claim.get("relationVerb") or ""),
                        {"claim": str(claim.get("relationVerb") or ""),
                         "sourcePage": str(claim.get("sourcePage") or "")},
                        True, mechanism="inferred")
        artifact = f"data/sources/competitor/{sid}/model.jsonl"
        row = {"sourceId": sid, "rung": "F1",
               "artifactRelPath": artifact,
               "dispositions": disp, "buildId": build_id}
        ledger.append(row)
    ledger.sort(key=lambda r: (str(r.get("sourceId")), str(r.get("rung"))))
    applied = sum(1 for r in ledger
                  if any(v for v in r.get("dispositions", {}).values()))
    floor_met = applied >= _FLOOR_SOURCES
    if not floor_met:
        ledger.append({
            "sourceId": "~floor", "rung": "wall",
            "terminal": "floor-unmet",
            "floorRequired": _FLOOR_SOURCES,
            "sourcesApplied": applied,
            "unblock": "owner-directed corpus acquisition into "
                       "data/sources/competitor/<source-id>/ (model.jsonl + "
                       "PROVENANCE.md) per competitor-research.md ladder "
                       "F1-F5; the stage consumes committed bytes only",
            "buildId": build_id})
    return ledger, overlays, counts, floor_met


# ---------------------------------------------------------------------------
# GUID bridge — pure-data seam (R3)

def run_guid_bridge(refs, catalog_keys, container_rows, stub_index,
                    scene_bundles=None, buildId=None):
    """Pure-data GUID bridge (piece-02 §3 R3): guid → catalog address →
    container object → stub entity / scene node / address termination.
    Drives the same ladder as the stage pass for callers holding RAW rows:

    - ``refs``: `{srcKind, srcId, fieldPath, assetGuid[, subObjectName]}``;
    - ``catalog_keys``: catalog rows (guid-kind keys filtered internally);
    - ``container_rows``: container_index rows
      (`{bundle, address, pathId, class}`);
    - ``stub_index``: `(bare bundle filename, pathId) -> (kind, id)`;
    - ``scene_bundles``: optional flagged-bundle set/mapping for step 3b.

    Returns `{"report", "assetRows", "pairRows", "sceneRows"}` where the
    report carries the F9 arithmetic as emitted facts (rates over REFS,
    dangling over DISTINCT guids).
    """
    bid = tc.BUILD_ID if buildId is None else int(buildId)
    guid_index: dict[str, list[dict]] = {}
    for key in catalog_keys or []:
        if key.get("kind") != "guid":
            continue
        guid_index.setdefault(str(key["key"]), []).append({
            "address": key.get("address"),
            "bundle": key.get("bundle"),
        })
    by_address: dict[str, list[tuple[str, int]]] = {}
    for row in container_rows or []:
        pid = row.get("pathId")
        # signed pathIds are legal on this corpus; only None means unknown
        if pid is None:
            continue
        by_address.setdefault(str(row["address"]), []).append(
            (str(row["bundle"]), int(pid)))
    scenes = scene_bundles or {}

    refs_total = 0
    distinct: set[str] = set()
    resolved_addr_refs = 0
    resolved_stub_refs = 0
    dangling: dict[str, list] = {}
    asset_rows_dedup: dict[tuple, dict] = {}
    cell_rows: dict[tuple, dict] = {}
    for ref in refs:
        guid = str(ref["assetGuid"])
        refs_total += 1
        distinct.add(guid)
        src_kind, src_id = str(ref["srcKind"]), str(ref["srcId"])
        fp = normalize_field_path(str(ref.get("fieldPath") or ""))
        sub = ref.get("subObjectName")
        entries = guid_index.get(guid)
        if not entries:
            samples = dangling.setdefault(guid, [])
            if len(samples) < 5:
                samples.append({"srcKind": src_kind, "srcId": src_id,
                                "fieldPath": fp})
            continue
        resolved_addr_refs += 1
        hit_stub = False
        addresses = sorted({str(e.get("address")) for e in entries
                            if e.get("address") is not None})
        for address in addresses:
            akey = (src_kind, src_id, fp, address)
            if akey not in asset_rows_dedup:
                ev = {"fieldPath": fp, "assetGuid": guid,
                      "resolvedVia": "catalog-guid+container-index"}
                if sub:
                    ev["subObjectName"] = str(sub)
                asset_rows_dedup[akey] = {
                    "srcKind": src_kind, "srcId": src_id,
                    "dstKind": "asset", "dstId": address,
                    "mechanism": "hard", "method": METHOD_GUID,
                    "inferred": False, "evidence": ev, "buildId": bid}
            # pass 1 — stub-entity targets win; pass 2 — first scene-flagged
            # candidate takes the edge (the R2/R3-3b attribution rule)
            candidates = sorted(by_address.get(address, ()))
            for b, pidv in candidates:
                hit = stub_index.get((b, pidv))
                if hit is not None:
                    hit_stub = True
                    k = (src_kind, src_id, hit[0], hit[1], fp)
                    cell_rows.setdefault(k, {
                        "srcKind": src_kind, "srcId": src_id,
                        "dstKind": hit[0], "dstId": hit[1],
                        "mechanism": "hard", "method": METHOD_GUID,
                        "inferred": False,
                        "evidence": {"fieldPath": fp, "assetGuid": guid,
                                     "catalogAddress": address},
                        "buildId": bid})
                    break
            if not hit_stub:
                for b, _pidv in candidates:
                    if b in scenes:
                        k = (src_kind, src_id, SCENE_NODE, b, fp)
                        cell_rows.setdefault(k, {
                            "srcKind": src_kind, "srcId": src_id,
                            "dstKind": SCENE_NODE, "dstId": b,
                            "mechanism": "hard", "method": METHOD_GUID,
                            "inferred": False,
                            "evidence": {"fieldPath": fp, "assetGuid": guid,
                                         "catalogAddress": address},
                            "buildId": bid})
                        break
        if hit_stub:
            resolved_stub_refs += 1

    def _sorted(rows, key):
        return [r for _, r in sorted(((key(r), r) for r in rows),
                                     key=lambda t: t[0])]

    asset_rows = _sorted(asset_rows_dedup.values(),
                         lambda r: (r["srcKind"], r["srcId"],
                                    r["evidence"]["fieldPath"], r["dstId"]))
    pair_rows = _sorted(cell_rows.values(),
                        lambda r: (r["srcKind"], r["srcId"], r["dstKind"],
                                   r["dstId"], r["evidence"]["fieldPath"]))
    report = {
        "guidRefsTotal": refs_total,
        "distinctGuids": len(distinct),
        "resolvedToAddress": resolved_addr_refs,
        "resolvedToStub": resolved_stub_refs,
        "danglingDistinctGuids": len(dangling),
        "resolveRateAddress": (resolved_addr_refs / refs_total)
        if refs_total else 0.0,
        "resolveRateStub": (resolved_stub_refs / refs_total)
        if refs_total else 0.0,
        "buildId": bid,
    }
    return {"report": report, "assetRows": asset_rows, "pairRows": pair_rows}


# ---------------------------------------------------------------------------
# Matrix assembly (R7)

class CellState:
    __slots__ = ("edges", "raw_by_field", "src_entities", "methods",
                 "unresolved_shared", "probe_note")

    def __init__(self):
        self.edges = 0
        self.raw_by_field: Counter = Counter()
        self.src_entities: set = set()
        self.methods: set = set()
        self.unresolved_shared = 0
        self.probe_note = ""


def assemble_matrix(relinks_source, build_id=None) -> dict:
    """Reconstruct `matrix.json` FROM EMITTED DATASETS (piece-02 §3 R7 —
    counts recomputed from rows, never accumulated mutably). Accepts a
    relinks/ directory (str/Path) or a `{"relinksDir": ...}` mapping.
    Client pair files (`<src>_<dst>.jsonl`) rebuild each cell's state;
    competitor overlays never enter the counts (community claims are not
    measured truth). Reconstruction cannot re-derive per-cell unresolved
    residue (the ledger rows name no destination cell), so cells with
    edges ship `modeled`; the live stage pass remains the authoritative
    assembler for partial-cell attribution."""
    if isinstance(relinks_source, dict):
        relinks_source = relinks_source.get("relinksDir")
    d = Path(relinks_source)
    cell_states: dict[tuple[str, str], CellState] = {}
    for f in sorted(d.glob("*.jsonl")):
        name = f.name
        if name.startswith("_") or name.endswith(".competitor.jsonl"):
            continue
        stem = name[:-len(".jsonl")]
        src, _sep, dst = stem.partition("_")
        if src not in NODE_UNIVERSE or dst not in NODE_UNIVERSE:
            continue
        st = CellState()
        with open(f, "r", encoding="utf-8", newline="\n") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                st.edges += 1
                st.methods.add(str(row.get("method")))
                st.src_entities.add(str(row.get("srcId")))
                ev = row.get("evidence") or {}
                fp = ev.get("fieldPath")
                if fp:
                    st.raw_by_field[str(fp)] += int(ev.get("refCount") or 1)
                if build_id is None and isinstance(row.get("buildId"), int):
                    build_id = row["buildId"]
        cell_states[(src, dst)] = st
    if build_id is None:
        build_id = tc.BUILD_ID
    return assemble_cell_matrix(cell_states, SCENE_SRC_UNBLOCK, {},
                                build_id)


def assemble_cell_matrix(cell_states, scene_src_unblock, probe_cells,
                         build_id) -> dict:
    """pairs[] row-major over NODE_UNIVERSE from in-memory cell states —
    counts recomputed from the emitted datasets' states, never accumulated
    mutably across passes. (The directory-driven seam is
    :func:`assemble_matrix`.)"""
    pairs = []
    for src in NODE_UNIVERSE:
        for dst in NODE_UNIVERSE:
            st = cell_states.get((src, dst)) or CellState()
            edges = st.edges
            join_key = JOINKEY_NONE
            if METHOD_PTR_SAME in st.methods or METHOD_PTR_CROSS in st.methods:
                join_key = JOINKEY_PPTR
            elif METHOD_GUID in st.methods:
                join_key = JOINKEY_GUID
            else:
                for m in sorted(st.methods):
                    if m.startswith("name-convention:"):
                        join_key = joinkey_name_equality(
                            m.split(":", 1)[1])
                        break
            if src == SCENE_NODE:
                status, unblock = "missing", scene_src_unblock
                mechanism = "inferred"
            elif edges > 0:
                hard_only = st.methods <= {METHOD_PTR_SAME, METHOD_PTR_CROSS,
                                           METHOD_GUID}
                mechanism = "hard" if hard_only else "inferred"
                if st.unresolved_shared > 0:
                    status = "partial"
                    # a named probe cell states its own concrete next probe;
                    # the generic sentence is the fallback
                    unblock = probe_cells.get((src, dst)) or (
                        f"{st.unresolved_shared} unresolved PPtr refs are "
                        "attributed to this destination (target lands here "
                        "or its field-path leaf key names it) — see relinks/"
                        "_unresolved_pptrs.jsonl")
                else:
                    status = "modeled"
                    unblock = None
            elif (src, dst) in probe_cells:
                status = "partial"
                mechanism = "inferred"
                unblock = probe_cells[(src, dst)]
            else:
                status = "missing"
                mechanism = "inferred"
                unblock = ("no carrier found in client data today; probe "
                           "candidates: cross-file PPtr growth (_unresolved_"
                           "pptrs.jsonl), GUID-carried references (guid "
                           "bridge), decompiled code analysis (decompiled/"
                           "structural/class-hierarchy.jsonl)")
            cell = {
                "srcKind": src, "dstKind": dst,
                "joinKey": join_key, "mechanism": mechanism,
                "status": status,
                "cardinality": {
                    "perSrc": "0..N" if edges else "0",
                    "perDst": "0..M" if edges else "0",
                    "srcEntitiesWithEdges": len(st.src_entities),
                    "edges": edges},
                "pairFiles": [f"{src}_{dst}.jsonl"] if edges else [],
            }
            evidence = {}
            if st.raw_by_field:
                evidence["topFields"] = {
                    f: n for f, n in sorted(
                        st.raw_by_field.most_common(_TOPFIELD_LIMIT))}
            if st.unresolved_shared:
                evidence["unresolvedRefs"] = st.unresolved_shared
            if evidence:
                cell["evidence"] = evidence
            if unblock:
                cell["unblock"] = unblock
            pairs.append(cell)
    return {
        "meta": {
            "buildId": build_id,
            "nodeUniverse": {"nodes": list(NODE_UNIVERSE),
                             "arithmetic": NODE_ARITHMETIC},
            "enums": {"mechanism": list(MECHANISMS),
                      "status": list(STATUSES)},
        },
        "pairs": pairs,
    }


# ---------------------------------------------------------------------------
# RELATIONS.md renderer (R7) — deterministic markdown, fixed section order

def render_relations_md(matrix, relations_lines, build_id) -> str:
    lines = [
        "# Relations",
        "",
        f"- buildId: {build_id}",
        "- generated mechanically from relinks/matrix.json + ledgers by the "
        "`relink` stage (piece-02); reruns are byte-identical",
        "",
        "## Node universe",
        "",
        f"- nodes: {', '.join(NODE_UNIVERSE)}",
        f"- arithmetic: {NODE_ARITHMETIC}",
        "",
        "## Ordered-pair matrix (100 cells)",
        "",
        "| src | dst | joinKey | mechanism | status | edges | "
        "srcEntities | pairFile |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for cell in matrix["pairs"]:
        card = cell["cardinality"]
        pf = cell["pairFiles"][0] if cell["pairFiles"] else ""
        lines.append(
            f"| {cell['srcKind']} | {cell['dstKind']} | {cell['joinKey']} | "
            f"{cell['mechanism']} | {cell['status']} | {card['edges']} | "
            f"{card['srcEntitiesWithEdges']} | {pf} |")
    lines.extend(relations_lines)
    return "\n".join(lines) + "\n"
