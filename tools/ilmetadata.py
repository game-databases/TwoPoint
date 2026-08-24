#!/usr/bin/env python3
"""Minimal pure-Python reader for .NET (ECMA-335) metadata tables — the
stage-1 ".NET metadata reader" that enumerates typedefs across Il2CppDumper's
DummyDll/*.dll outputs (spec §3 stage 1 acceptance, PRIMARY source).

Reads only the metadata tables needed for structural artifacts:
Module, TypeRef, TypeDef, Field, MethodDef, InterfaceImpl, Constant,
NestedClass (+ every table whose row size must be known to reach them).
No reflection runtime, no external dependency.

Returns per-type rows: namespace, name, resolved base type, interfaces,
method/field counts and literal-constant members (enum registries).
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field as dc_field
from pathlib import Path


@dataclass
class TypeInfo:
    namespace: str
    name: str
    fullname: str
    base_fullname: str | None
    interfaces: list[str] = dc_field(default_factory=list)
    method_count: int = 0
    field_count: int = 0
    nested: bool = False
    is_enum: bool = False
    members: dict | None = None  # literal constants: member name -> python value


# --- fixed/simplified table schema -----------------------------------------
# column kinds: ("u1",), ("u2",), ("u4",), ("str",), ("guid",), ("blob",),
# ("idx", table_no), ("coded", group_name)

# table-number lookup (SCHEMAS keys are ECMA table ids)
TABLES_BY_NAME = {
    "Module": 0x00, "TypeRef": 0x01, "TypeDef": 0x02, "FieldPtr": 0x03,
    "Field": 0x04, "MethodPtr": 0x05, "MethodDef": 0x06, "ParamPtr": 0x07,
    "Param": 0x08, "InterfaceImpl": 0x09, "MemberRef": 0x0A,
    "Constant": 0x0B, "CustomAttribute": 0x0C, "DeclSecurity": 0x0E,
    "StandAloneSig": 0x11, "Event": 0x14, "Property": 0x17,
    "ModuleRef": 0x1A, "TypeSpec": 0x1B, "Assembly": 0x20,
    "AssemblyRef": 0x23, "File": 0x26, "ExportedType": 0x27,
    "ManifestResource": 0x28, "GenericParam": 0x2A, "MethodSpec": 0x2B,
    "GenericParamConstraint": 0x2C, "PropertyPtr": 0x16, "EventPtr": 0x13,
}

CODED_GROUPS = {
    "TypeDefOrRef": (["TypeDef", "TypeRef", "TypeSpec"], 2),
    "HasConstant": (["Field", "Param", "Property"], 2),
    "HasCustomAttribute": (
        ["MethodDef", "Field", "TypeRef", "TypeDef", "Param", "InterfaceImpl",
         "MemberRef", "Module", "DeclSecurity", "Property", "Event",
         "StandAloneSig", "ModuleRef", "TypeSpec", "Assembly", "AssemblyRef",
         "File", "ExportedType", "ManifestResource", "GenericParam",
         "GenericParamConstraint", "MethodSpec"], 5),
    "HasFieldMarshal": (["Field", "Param"], 1),
    "HasDeclSecurity": (["TypeDef", "MethodDef", "Assembly"], 2),
    "MemberRefParent": (["TypeDef", "TypeRef", "ModuleRef", "MethodDef",
                         "TypeSpec"], 3),
    "HasSemantics": (["Event", "Property"], 1),
    "MethodDefOrRef": (["MethodDef", "MemberRef"], 1),
    "MemberForwarded": (["Field", "MethodDef"], 1),
    "Implementation": (["File", "AssemblyRef", "ExportedType"], 2),
    "CustomAttributeType": ([], 3),  # tags: None, None, MethodDef, MemberRef, None
    "ResolutionScope": (["Module", "ModuleRef", "AssemblyRef", "TypeRef"], 2),
    "TypeOrMethodDef": (["TypeDef", "MethodDef"], 1),
}

# Full schema map (table -> columns). Tables we don't consume still need a
# schema so preceding-table offsets stay correct.
SCHEMAS = {
    0x00: [("u2",), ("str",), ("guid",), ("guid",), ("guid",)],                       # Module
    0x01: [("coded", "ResolutionScope"), ("str",), ("str",)],                          # TypeRef
    0x02: [("u4",), ("str",), ("str",), ("coded", "TypeDefOrRef"),
           ("idx", 0x04), ("idx", 0x06)],                                              # TypeDef
    0x03: [("idx", 0x04)],                                                             # FieldPtr
    0x04: [("u2",), ("str",), ("blob",)],                                              # Field
    0x05: [("idx", 0x06)],                                                             # MethodPtr
    0x06: [("u4",), ("u2",), ("u2",), ("str",), ("blob",), ("idx", 0x08)],             # MethodDef
    0x07: [("idx", 0x08)],                                                             # ParamPtr
    0x08: [("u2",), ("u2",), ("str",)],                                                # Param
    0x09: [("idx", 0x02), ("coded", "TypeDefOrRef")],                                  # InterfaceImpl
    0x0A: [("coded", "MemberRefParent"), ("str",), ("blob",)],                         # MemberRef
    0x0B: [("u1",), ("u1",), ("coded", "HasConstant"), ("blob",)],                     # Constant
    0x0C: [("coded", "HasCustomAttribute"), ("coded", "CustomAttributeType"),
           ("blob",)],                                                                 # CustomAttribute
    0x0D: [("coded", "HasFieldMarshal"), ("blob",)],                                   # FieldMarshal
    0x0E: [("u2",), ("coded", "HasDeclSecurity"), ("blob",)],                          # DeclSecurity
    0x0F: [("u2",), ("u4",), ("idx", 0x02)],                                           # ClassLayout
    0x10: [("u4",), ("idx", 0x04)],                                                    # FieldLayout
    0x11: [("blob",)],                                                                 # StandAloneSig
    0x12: [("idx", 0x02), ("idx", 0x14)],                                              # EventMap
    0x13: [("idx", 0x14)],                                                             # EventPtr
    0x14: [("u2",), ("str",), ("coded", "TypeDefOrRef")],                              # Event
    0x15: [("idx", 0x02), ("idx", 0x17)],                                              # PropertyMap
    0x16: [("idx", 0x17)],                                                             # PropertyPtr
    0x17: [("u2",), ("str",), ("blob",)],                                              # Property
    0x18: [("u2",), ("idx", 0x06), ("coded", "HasSemantics")],                         # MethodSemantics
    0x19: [("idx", 0x02), ("coded", "MethodDefOrRef"), ("coded", "MethodDefOrRef")],   # MethodImpl
    0x1A: [("str",)],                                                                  # ModuleRef
    0x1B: [("blob",)],                                                                 # TypeSpec
    0x1C: [("u2",), ("coded", "MemberForwarded"), ("str",), ("idx", 0x1A)],            # ImplMap
    0x1D: [("u4",), ("idx", 0x04)],                                                    # FieldRVA
    0x1E: [("u4",), ("u4",)],                                                          # ENCLog
    0x1F: [("u4",), ("u4",)],                                                          # ENCMap
    0x20: [("u4",), ("u2",), ("u2",), ("u2",), ("u2",), ("u4",), ("blob",),
           ("str",), ("str",)],                                                        # Assembly
    0x21: [("u4",)],                                                                   # AssemblyProcessor
    0x22: [("u4",), ("u4",), ("u4",)],                                                 # AssemblyOS
    0x23: [("u2",), ("u2",), ("u2",), ("u2",), ("u4",), ("blob",), ("str",),
           ("str",), ("blob",)],                                                       # AssemblyRef
    0x24: [("u4",), ("idx", 0x23)],                                                    # AssemblyRefProcessor
    0x25: [("u4",), ("u4",), ("u4",), ("idx", 0x23)],                                  # AssemblyRefOS
    0x26: [("u4",), ("str",), ("blob",)],                                              # File
    0x27: [("u4",), ("u4",), ("str",), ("str",), ("coded", "Implementation")],         # ExportedType
    0x28: [("u4",), ("u4",), ("str",), ("coded", "Implementation")],                   # ManifestResource
    0x29: [("idx", 0x02), ("idx", 0x02)],                                              # NestedClass
    0x2A: [("u2",), ("u2",), ("coded", "TypeOrMethodDef"), ("str",)],                  # GenericParam
    0x2B: [("coded", "MethodDefOrRef"), ("blob",)],                                    # MethodSpec
    0x2C: [("idx", 0x2A), ("coded", "TypeDefOrRef")],                                  # GenericParamConstraint
}

FIELD_LITERAL_FLAG = 0x40  # FieldAttributes.Literal


def _read_compressed_uint(data: bytes, pos: int) -> tuple[int, int]:
    b0 = data[pos]
    if b0 & 0x80 == 0:
        return b0, pos + 1
    if b0 & 0xC0 == 0x80:
        return ((b0 & 0x3F) << 8) | data[pos + 1], pos + 2
    return (((b0 & 0x1F) << 24) | (data[pos + 1] << 16)
            | (data[pos + 2] << 8) | data[pos + 3]), pos + 4


class MetadataReader:
    def __init__(self, path: Path):
        data = Path(path).read_bytes()
        self.data = data
        self._parse_pe(data)
        self._parse_metadata_root()
        self._parse_tables_stream()
        self.row_counts = {t: self._read_table_count(t) for t in SCHEMAS}

    # -- PE / CLI headers ---------------------------------------------------

    def _parse_pe(self, data: bytes) -> None:
        if data[:2] != b"MZ":
            raise ValueError("not a PE image (missing MZ)")
        e_lfanew = struct.unpack_from("<I", data, 0x3C)[0]
        if data[e_lfanew:e_lfanew + 4] != b"PE\0\0":
            raise ValueError("not a PE image (missing PE signature)")
        coff = e_lfanew + 4
        num_sections = struct.unpack_from("<H", data, coff + 2)[0]
        opt_size = struct.unpack_from("<H", data, coff + 16)[0]
        opt = coff + 20
        magic = struct.unpack_from("<H", data, opt)[0]
        dd_off = opt + (96 if magic == 0x10B else 112)  # PE32 vs PE32+
        clr_rva = struct.unpack_from("<I", data, dd_off + 14 * 8)[0]
        if clr_rva == 0:
            raise ValueError("no CLR runtime header — not a managed assembly")
        cor = self._rva_to_offset(clr_rva, data, coff, num_sections, opt_size)
        md_rva, md_size = struct.unpack_from("<II", data, cor + 8)
        self.md_off = self._rva_to_offset(md_rva, data, coff, num_sections, opt_size)

    @staticmethod
    def _rva_to_offset(rva, data, coff, num_sections, opt_size) -> int:
        sec = coff + 20 + opt_size
        for i in range(num_sections):
            base = sec + i * 40
            vsize, vaddr, rsize, roff = struct.unpack_from("<IIII", data, base + 8)
            if vaddr <= rva < vaddr + max(vsize, rsize):
                return roff + (rva - vaddr)
        raise ValueError(f"RVA {rva:#x} outside any section")

    # -- metadata root + streams ---------------------------------------------

    def _parse_metadata_root(self) -> None:
        off = self.md_off
        if struct.unpack_from("<I", self.data, off)[0] != 0x424A5342:
            raise ValueError("bad metadata signature (BSJB)")
        ver_len = struct.unpack_from("<I", self.data, off + 12)[0]
        p = off + 16 + ver_len
        flags, n_streams = struct.unpack_from("<HH", self.data, p)
        p += 4
        self.streams: dict[str, tuple[int, int]] = {}
        for _ in range(n_streams):
            s_off, s_size = struct.unpack_from("<II", self.data, p)
            p += 8
            name_start = p
            while self.data[p] != 0:
                p += 1
            name = self.data[name_start:p].decode("ascii")
            p += 1
            p += (-p) % 4
            self.streams[name] = (off + s_off, s_size)
        self.str_heap_off = self.streams.get("#Strings", (0, 0))[0]
        self.us_heap_off = self.streams.get("#US", (0, 0))[0]
        self.blob_heap_off = self.streams.get("#Blob", (0, 0))[0]

    def string_at(self, offset: int) -> str:
        start = self.str_heap_off + offset
        end = self.data.index(b"\0", start)
        return self.data[start:end].decode("utf-8", "replace")

    def blob_at(self, offset: int) -> bytes:
        start = self.blob_heap_off + offset
        length, consumed = self._read_blob_length(start)
        return self.data[start + consumed:start + consumed + length]

    def us_at(self, offset: int) -> str:
        start = self.us_heap_off + offset
        length, consumed = self._read_blob_length(start)
        raw = self.data[start + consumed:start + consumed + length]
        return raw[:-1].decode("utf-16-le", "replace") if raw.endswith(b"\x01") \
            else raw.decode("utf-16-le", "replace")

    def _read_blob_length(self, start: int) -> tuple[int, int]:
        b0 = self.data[start]
        if b0 & 0x80 == 0:
            return b0, 1
        if b0 & 0xC0 == 0x80:
            return ((b0 & 0x3F) << 8) | self.data[start + 1], 2
        return (((b0 & 0x1F) << 24) | (self.data[start + 1] << 16)
                | (self.data[start + 2] << 8) | self.data[start + 3]), 4

    # -- tables stream ---------------------------------------------------------

    def _parse_tables_stream(self) -> None:
        if "#~" not in self.streams:
            raise ValueError("no #~ tables stream (compressed metadata required)")
        base = self.streams["#~"][0]
        d = self.data
        self.heap_sizes = d[base + 6]
        valid = struct.unpack_from("<Q", d, base + 8)[0]
        p = base + 24
        self.present_tables = [t for t in range(64) if valid >> t & 1]
        counts = {}
        for t in self.present_tables:
            counts[t] = struct.unpack_from("<I", d, p)[0]
            p += 4
        self.table_counts = counts
        self.table_offsets = {}
        for t in self.present_tables:
            self.table_offsets[t] = p
            p += self._row_size(t) * counts[t]

    def _col_size(self, col) -> int:
        kind = col[0]
        if kind == "u1":
            return 1
        if kind == "u2":
            return 2
        if kind == "u4":
            return 4
        if kind == "str":
            return 4 if self.heap_sizes & 1 else 2
        if kind == "guid":
            return 4 if self.heap_sizes & 2 else 2
        if kind == "blob":
            return 4 if self.heap_sizes & 4 else 2
        if kind == "idx":
            return self._table_index_size(col[1])
        if kind == "coded":
            names, tag_bits = CODED_GROUPS[col[1]]
            if not names:
                # CustomAttributeType: tags are None/None/MethodDef/MemberRef/
                # None → only the two member tables can be referenced
                max_rows = max(self.table_counts.get(TABLES_BY_NAME[n], 0)
                               for n in ("MethodDef", "MemberRef"))
            else:
                max_rows = max(self.table_counts.get(TABLES_BY_NAME.get(n, -1), 0)
                               for n in names)
            return 2 if max_rows < (1 << (16 - tag_bits)) else 4
        raise ValueError(f"unknown column kind {kind}")

    def _table_index_size(self, table: int) -> int:
        return 2 if self.table_counts.get(table, 0) < (1 << 16) else 4

    def _row_size(self, table: int) -> int:
        cols = SCHEMAS.get(table)
        if cols is None:
            raise ValueError(f"unsupported metadata table 0x{table:02x} present "
                             "(schema unknown — cannot compute row layout)")
        return sum(self._col_size(c) for c in cols)

    def _read_table_count(self, table: int) -> int:
        return self.table_counts.get(table, 0)

    def iter_table(self, table: int):
        """Yield per-row lists of decoded column values."""
        cols = SCHEMAS[table]
        sizes = [self._col_size(c) for c in cols]
        off = self.table_offsets[table]
        d = self.data
        n = self.table_counts.get(table, 0)
        for _row in range(n):
            vals = []
            for col, size in zip(cols, sizes):
                kind = col[0]
                if kind == "u1":
                    vals.append(d[off])
                elif kind == "u2":
                    vals.append(struct.unpack_from("<H", d, off)[0])
                elif kind == "u4":
                    vals.append(struct.unpack_from("<I", d, off)[0])
                elif kind == "str":
                    raw = struct.unpack_from(("<I" if size == 4 else "<H"), d, off)[0]
                    vals.append(raw)
                elif kind == "guid":
                    vals.append(struct.unpack_from(("<I" if size == 4 else "<H"), d, off)[0])
                elif kind == "blob":
                    vals.append(struct.unpack_from(("<I" if size == 4 else "<H"), d, off)[0])
                elif kind in ("idx", "coded"):
                    vals.append(struct.unpack_from(("<I" if size == 4 else "<H"), d, off)[0])
                off += size
            yield vals


class _Tables:
    """Resolved views over the tables a structural pass needs."""

    def __init__(self, mr: MetadataReader):
        self.mr = mr
        self.typedef_rows = list(mr.iter_table(0x02)) if mr.row_counts[0x02] else []
        self.typeref_rows = list(mr.iter_table(0x01)) if mr.row_counts[0x01] else []
        self.typespec_rows = list(mr.iter_table(0x1B)) if mr.row_counts[0x1B] else []
        self.field_rows = list(mr.iter_table(0x04)) if mr.row_counts[0x04] else []
        self.method_counts = mr.row_counts[0x06]
        self.iface_rows = list(mr.iter_table(0x09)) if mr.row_counts[0x09] else []
        self.const_rows = list(mr.iter_table(0x0B)) if mr.row_counts[0x0B] else []
        self.nested_rows = list(mr.iter_table(0x29)) if mr.row_counts[0x29] else []

    def _typedef_or_ref_name(self, coded: int) -> str | None:
        if coded == 0:
            return None
        tag = coded & 0x3
        idx = coded >> 2
        try:
            if tag == 0:  # TypeDef — schema col 1 = Name, col 2 = Namespace
                ns_i, name_i = self.typedef_rows[idx - 1][2], self.typedef_rows[idx - 1][1]
            elif tag == 1:  # TypeRef
                ns_i, name_i = self.typeref_rows[idx - 1][2], self.typeref_rows[idx - 1][1]
            elif tag == 2:  # TypeSpec
                sig = self.mr.blob_at(self.typespec_rows[idx - 1][0])
                return _peek_signature_name(sig, self)
            else:
                return None
        except IndexError:
            return None
        ns = self.mr.string_at(ns_i) if ns_i else ""
        name = self.mr.string_at(name_i) if name_i else ""
        return f"{ns}.{name}" if ns else (name or None)


def _peek_signature_name(sig: bytes, tables: "_Tables") -> str | None:
    """Resolve a TypeSpec signature blob to a readable base name (pragmatic
    subset: CLASS/VALUETYPE tokens, GENERICINST wrappers, SZARRAY)."""
    try:
        pos = 0
        if sig[pos] == 0x10:  # GENERICINST
            pos += 2
        head = sig[pos]
        if head in (0x11, 0x12):  # VALUETYPE / CLASS followed by coded token
            token, nxt = _read_compressed_uint(sig, pos + 1)
            tag = token & 0x3
            idx = token >> 2
            if tag == 0 and 0 < idx <= len(tables.typedef_rows):
                r = tables.typedef_rows[idx - 1]
                return _full_name(tables.mr, r[2], r[1])
            if tag == 1 and 0 < idx <= len(tables.typeref_rows):
                r = tables.typeref_rows[idx - 1]
                return _full_name(tables.mr, r[2], r[1])
        if head == 0x1D:  # SZARRAY
            inner = _peek_signature_name(sig[pos + 1:], tables)
            return f"{inner}[]" if inner else None
        if head == 0x13 or head == 0x1E:  # VAR / MVAR
            return "!var"
    except (IndexError, struct.error):
        return None
    return "<typespec>"


def _full_name(mr: MetadataReader, ns_idx: int, name_idx: int) -> str:
    ns = mr.string_at(ns_idx) if ns_idx else ""
    name = mr.string_at(name_idx) if name_idx else ""
    return f"{ns}.{name}" if ns else name


def _constant_value(tables: _Tables, parent_field_row: int):
    """Constant-table lookup keyed by HasConstant(parent=Field) coded index.
    The element type comes from the row's Type column; Value is raw."""
    coded = (parent_field_row << 2) | 0  # tag 0 == Field
    for ctype, _pad, parent, blob_off in tables.const_rows:
        if parent == coded:
            try:
                val = tables.mr.blob_at(blob_off)
                if ctype == 0x02:
                    return bool(val[0])
                if ctype == 0x03:  # CHAR
                    return struct.unpack("<H", val[:2])[0]
                if ctype in (0x04, 0x05):
                    return struct.unpack("<b" if ctype == 0x04 else "<B", val[:1])[0]
                if ctype in (0x06, 0x07):
                    return struct.unpack("<h" if ctype == 0x06 else "<H", val[:2])[0]
                if ctype in (0x08, 0x09):
                    return struct.unpack("<i" if ctype == 0x08 else "<I", val[:4])[0]
                if ctype in (0x0A, 0x0B):
                    return struct.unpack("<q" if ctype == 0x0A else "<Q", val[:8])[0]
                if ctype == 0x0C:
                    return struct.unpack("<f", val[:4])[0]
                if ctype == 0x0D:
                    return struct.unpack("<d", val[:8])[0]
                if ctype == 0x0E:  # string constant: UTF-16LE in the Blob heap
                    return val.decode("utf-16-le", "replace")
                return None  # class/enum-typed nulls etc.
            except (struct.error, IndexError):
                return None
    return "__MISSING__"


def read_types(path: Path) -> list[TypeInfo]:
    """Enumerate every TypeDef row of one dummy assembly as TypeInfo rows,
    in metadata row order (callers sort for determinism)."""
    mr = MetadataReader(Path(path))
    t = _Tables(mr)
    n_types = len(t.typedef_rows)
    out: list[TypeInfo] = []
    iface_by_class: dict[int, list[str]] = {}
    for cls, iface_coded in t.iface_rows:
        name = t._typedef_or_ref_name(iface_coded)
        if name:
            iface_by_class.setdefault(cls, []).append(name)
    nested_set = {row[0] for row in t.nested_rows}
    const_by_field = {}
    for ctype, _pad, parent, blob_off in t.const_rows:
        if parent and (parent & 0x3) == 0:
            const_by_field[parent >> 2] = (ctype, blob_off)

    for i, row in enumerate(t.typedef_rows):
        flags, name_i, ns_i, extends_coded, field_list, method_list = row
        ns = mr.string_at(ns_i) if ns_i else ""
        name = mr.string_at(name_i) if name_i else ""
        base = t._typedef_or_ref_name(extends_coded)
        field_end = t.typedef_rows[i + 1][4] if i + 1 < n_types else len(t.field_rows) + 1
        method_end = t.typedef_rows[i + 1][5] if i + 1 < n_types else t.method_counts + 1
        fields = range(field_list, min(field_end, len(t.field_rows) + 1))
        members: dict = {}
        for frow in fields:
            fflags, fname_i, fsig_i = t.field_rows[frow - 1]
            if fflags & FIELD_LITERAL_FLAG:
                fname = mr.string_at(fname_i)
                members[fname] = _constant_value(tables=t, parent_field_row=frow)
        is_enum = base == "System.Enum"
        if members:
            members.pop("value__", None)
        out.append(TypeInfo(
            namespace=ns,
            name=name,
            fullname=f"{ns}.{name}" if ns else name,
            base_fullname=base,
            interfaces=sorted(iface_by_class.get(i + 1, [])),
            method_count=max(method_end - method_list, 0),
            field_count=len(fields),
            nested=(i + 1) in nested_set,
            is_enum=is_enum,
            members=members or None,
        ))
    return out
