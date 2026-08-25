#!/usr/bin/env python3
"""UnityPy bootstrap + typetree synthesis for the Two Point Campus pipeline.

UnityPy import order: pack `.venv` first (make setup installs the pinned
version), then the vendored source clone under `<repo>/tools/UnityPy`. The
resolved source marker ("venv-pip" | "vendored-clone") is returned so stages
can record it in EXTRACTION-LOG.md run sections instead of silently guessing.

MonoBehaviour decoding (measured on the real corpus, Revision 6): most
bundles DO ship embedded typetrees — UnityPy reads those directly. For
typetree-less payloads the synthesized typetree fires, driven by the dump.cs
field tables under Unity's serialization rules (Revision 11: member
visibility/attribute filtering, base-chain inheritance, engine-object PPtr
mapping, and the measured managed-reference trailer — dump.cs `// 0x…`
offsets are RUNTIME MEMORY offsets and decide field ORDER/presence only,
never stream alignment). Script-class names come from
:class:`MonoScriptIndex` — m_Script PPtrs point into SEPARATE monoscript
bundles, resolved through each file's externals by ``(cab name,
path_id)``. Anything that fails to decode falls back to a raw typed dump
with `typetreeDecoded: false` + the exact reason — never a silent guess
(spec §3 stage 3).
"""
from __future__ import annotations

import io
import json
import re
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tpc_common import VENDORED_UNITYPY_CANDIDATES, resolve_pack_dir, resolve_repo_root  # noqa: E402


def ensure_unitypy():
    """Import UnityPy, falling back to the vendored clone. Returns
    (unitypy_module, source_marker)."""
    try:
        import UnityPy  # noqa: PLC0415
        return UnityPy, "venv-pip"
    except ImportError:
        pass
    pack_dir = resolve_pack_dir()
    repo_root = resolve_repo_root(pack_dir)
    for cand in VENDORED_UNITYPY_CANDIDATES:
        p = Path(cand)
        clone = p if p.is_absolute() else repo_root / cand
        if (clone / "UnityPy").is_dir():
            sys.path.insert(0, str(clone))
            import UnityPy  # noqa: PLC0415
            return UnityPy, "vendored-clone"
    raise ImportError(
        "UnityPy unavailable: neither installed in the active interpreter nor "
        f"vendored at {[str(c) for c in VENDORED_UNITYPY_CANDIDATES]} "
        "(run `make setup`)")


# ---------------------------------------------------------------------------
# dump.cs index — per-type ordered instance-field tables

_TYPE_DECL_RE = re.compile(
    r"^(\t*)((?:\[(?:[^\[\]]|\[[^\[\]]*\])*\]\s*)*)"
    r"((?:public|private|protected|internal|sealed|abstract|static|partial|new)\s+)*"
    r"(class|struct|interface|enum)\s+([A-Za-z_][\w.`]*)(<[^>]*>)?"
    r"\s*(?::\s*(.+?))?\s*(?://[^\n]*)?$")
_FIELD_RE = re.compile(
    r"^(\t*)((?:(?:public|private|protected|internal|static|readonly|const|volatile|new|extern|unsafe|sealed|event)\s+)+)"
    r"([\w.`<>,+\[\]()\s]+?)\s+([A-Za-z_][\w.]*)\s*(?:=[^;]*)?;"
    r"\s*(?://\s*(?:0x)?([0-9A-Fa-f]+))?\s*$")
_NAMESPACE_RE = re.compile(r"^// Namespace: (.+?)\s*$")
# Standalone serialization-affecting attribute lines (`[SerializeField] // RVA…`).
# Il2CppDumper prints them on their own line directly above the field they
# attach to; inline spellings do not occur in this corpus (measured R11).
_ATTR_LINE_RE = re.compile(r"^\[(SerializeField|SerializeReference|NonSerialized)\]")
# attribute class name → modifier word encoded into the member's mods string
_ATTR_TOKEN = {"SerializeField": "serializeField",
               "SerializeReference": "serializeReference",
               "NonSerialized": "nonSerialized"}


class DumpCsIndex:
    """fullname → {'fields': [(name, type_string, offset_or_None)],
    'members': [(name, type_string, offset_or_None, modifiers)],
    'kind': 'class'|'struct'|'interface'|'enum', 'base': raw base spelling,
    'namespace': declaring namespace}.

    ``fields`` keeps its pre-R11 shape (every instance-or-static field line
    with its memory offset) for backward compatibility; the synthesizer
    reads the richer ``members``/``kind``/``base`` records."""

    def __init__(self, dump_cs_path: Path):
        text = Path(dump_cs_path).read_text(encoding="utf-8", errors="replace")
        self.types: dict[str, dict] = {}
        self._parse(text)

    def _parse(self, text: str) -> None:
        namespace = ""
        # stacks of (indent, fullname)
        type_stack: list[tuple[int, str]] = []
        cur_fields: list[tuple[str, str, int | None]] = []
        cur_members: list[tuple[str, str, int | None, str]] = []
        cur_kind = ""
        cur_base = ""
        cur_generic = ""
        cur_abstract = False
        cur_ns = ""
        pending_ns = ""
        pending_attrs: set[str] = set()

        def commit(fullname: str, ftype_ns: str) -> None:
            if fullname in self.types and cur_members:
                return
            entry = self.types.setdefault(fullname, {
                "fields": [], "members": [], "kind": None,
                "base": None, "namespace": ftype_ns})
            if cur_members:
                entry["fields"] = [(n, t, o) for (n, t, o, _m) in cur_members]
                entry["members"] = list(cur_members)
            if cur_kind:
                entry["kind"] = cur_kind
            if cur_base:
                entry["base"] = cur_base
            if cur_abstract:
                entry["abstract"] = True
            if cur_generic:
                entry["generic_params"] = [
                    p.strip() for p in cur_generic.strip("<>").split(",")]

        def close_one() -> None:
            nonlocal cur_fields, cur_members, cur_kind, cur_base, \
                cur_generic, cur_abstract
            done_fullname = type_stack.pop()[1]
            commit(done_fullname, cur_ns)
            cur_fields = []
            cur_members = []
            cur_kind = ""
            cur_base = ""
            cur_generic = ""
            cur_abstract = False

        for raw in text.splitlines():
            line = raw.rstrip()
            if not line.strip():
                continue
            stripped = line.strip()
            ns_m = _NAMESPACE_RE.match(stripped)
            if ns_m:
                pending_ns = ns_m.group(1)
                continue
            attr_m = _ATTR_LINE_RE.match(stripped)
            if attr_m and type_stack:
                pending_attrs.add(attr_m.group(1))
                continue
            decl = _TYPE_DECL_RE.match(line)
            if decl and "(" not in line.split("//")[0]:
                while type_stack and len(decl.group(1)) <= type_stack[-1][0]:
                    close_one()
                namespace = pending_ns
                name = decl.group(5)
                if type_stack and len(decl.group(1)) > type_stack[-1][0]:
                    base = type_stack[-1][1] + "+"
                    type_ns = self.types.get(type_stack[-1][1], {}).get("namespace") or namespace
                elif not type_stack:
                    base = f"{namespace}." if namespace else ""
                    if base == ".":
                        base = ""
                    type_ns = namespace
                else:
                    base = ""
                    type_ns = namespace
                fullname = base + name
                # group(6) is the optional `<T, …>` parameter list; group(7)
                # the base-type list
                base_spelling = (decl.group(7) or "").strip()
                cur_kind = decl.group(4)
                cur_base = base_spelling.split("<")[0].split(",")[0].strip() \
                    if base_spelling else ""
                cur_generic = (decl.group(6) or "").strip()
                cur_abstract = "abstract " in (" " + (decl.group(3) or ""))
                cur_ns = type_ns
                type_stack.append((len(decl.group(1)), fullname))
                cur_fields = []
                cur_members = []
                pending_attrs = set()
                continue
            if type_stack:
                fld = _FIELD_RE.match(line)
                if fld and "(" not in line.split(";")[0]:
                    indent = len(fld.group(1))
                    top_indent = type_stack[-1][0] if type_stack else 0
                    if indent > top_indent:  # member of the innermost type
                        mods = fld.group(2) or ""
                        if pending_attrs:
                            # standalone [SerializeField] / [SerializeReference]
                            # / [NonSerialized] lines attach to THIS field,
                            # encoded as lower-camel modifier words
                            mods = (mods.rstrip() + " " + " ".join(sorted(
                                _ATTR_TOKEN[a] for a in pending_attrs)))
                        off_txt = fld.group(5)
                        offset = int(off_txt, 16) if off_txt else None
                        fname = fld.group(4)
                        ftype = fld.group(3).strip()
                        cur_fields.append((fname, ftype, offset))
                        cur_members.append((fname, ftype, offset, mods))
                        pending_attrs = set()
                        continue
                # any other member construct (methods, properties, section
                # comments) invalidates attributes aimed at a field
                if "(" in stripped.split("//")[0] \
                        or stripped.startswith("//") \
                        or stripped.startswith("{") or stripped.startswith("}"):
                    pending_attrs = set()
        while type_stack:
            close_one()

    def fields(self, fullname: str) -> list[tuple[str, str, int | None]] | None:
        t = self.types.get(fullname)
        if t is None:
            # tolerate assembly-qualified spellings `Ns.Type, Assembly`
            stem = fullname.split(",")[0].strip()
            t = self.types.get(stem)
        if t is None:
            resolved = self.resolve(fullname)
            t = self.types.get(resolved) if resolved else None
        return list(t["fields"]) if t is not None else None

    # -- R11: deterministic name resolution ----------------------------------

    def resolve(self, spelling: str, context_ns: str = "") -> str | None:
        """Member-type spelling from dump.cs → indexed fullname, or None.

        Ladder (deterministic at every step):
          1. exact key;
          2. assembly-qualified stem (`Ns.Type, Assembly`);
          3. unique suffix match on the full spelling (`Outer.Inner` forms);
          4. unique leaf match on the bare name;
          5. ambiguous leaf → the candidate declared in ``context_ns``
             wins; still ambiguous → None (caller raises, never guesses)."""
        s = str(spelling).strip()
        if not s:
            return None
        if s in self.types:
            return s
        stem = s.split(",")[0].strip()
        if stem != s and stem in self.types:
            return stem
        norm = stem.replace("+", ".")
        cands = sorted(k for k in self.types
                       if k.replace("+", ".").endswith("." + norm)
                       or k.replace("+", ".") == norm)
        if len(cands) == 1:
            return cands[0]
        leaf = norm.rsplit(".", 1)[-1]
        cands = sorted(k for k in self.types
                       if k.rsplit(".", 1)[-1].replace("+", ".") == leaf)
        if len(cands) > 1 and context_ns:
            same = [k for k in cands
                    if self.types[k].get("namespace") == context_ns]
            if len(same) == 1:
                return same[0]
            if len(same) > 1:
                # several same-namespace declarations: C# scope order takes
                # the OUTERMOST (e.g. TPC.WallPiece shadows the nested
                # TPC.WallMesh.WallPiece); ambiguous only on a depth tie
                depths = sorted((k.count("."), k) for k in same)
                if depths[0][0] < depths[1][0]:
                    return depths[0][1]
        if len(cands) == 1:
            return cands[0]
        return None


# ---------------------------------------------------------------------------
# Typetree synthesis from dump.cs field tables

_PRIMITIVE_NODES = {
    "void": None,
    "bool": ("bool", 1),
    "byte": ("UInt8", 1),
    "sbyte": ("SInt8", 1),
    "char": ("char", 1),
    "short": ("short", 2),
    "ushort": ("unsigned short", 2),
    "int": ("int", 4),
    "uint": ("unsigned int", 4),
    "long": ("long long", 8),
    "ulong": ("unsigned long long", 8),
    "float": ("float", 4),
    "double": ("double", 8),
    "decimal": ("double", 8),
    "string": ("string", None),
    "Byte": ("UInt8", 1),
    "Int16": ("short", 2),
    "UInt16": ("unsigned short", 2),
    "Int32": ("int", 4),
    "UInt32": ("unsigned int", 4),
    "Int64": ("long long", 8),
    "UInt64": ("unsigned long long", 8),
    "Single": ("float", 4),
    "Double": ("double", 8),
    "Boolean": ("bool", 1),
    "String": ("string", None),
}

_ALIGN_FLAG = 0x4000  # kAlignEditorOnly bit used by Unity typetrees


class SynthesisError(Exception):
    pass


def _cs_type_stem(t: str) -> str:
    """Normalize a C# spelling from dump.cs to a PRIMITIVE lookup key.
    Structural decisions (List/Dictionary/generics) go through
    :func:`_norm_cs`/:func:`_generic_args`, which KEEP the arguments."""
    t = str(t).replace(" ", "").split(",")[0]
    t = re.sub(r"<.*>", "", t)
    t = t.replace("+", ".")
    return t


def _norm_cs(t: str) -> str:
    """Normalize spelling KEEPING generic args: whitespace out, assembly
    qualifier stripped, nested-type `+` flattened to `.`."""
    return str(t).replace(" ", "").split(",")[0].replace("+", ".")


def _generic_args(norm: str) -> tuple[str, str] | None:
    """`Head<args>` → (bare Head, args-string); non-generic → None."""
    if not norm.endswith(">") or "<" not in norm:
        return None
    idx = norm.index("<")
    return norm[:idx].rsplit(".", 1)[-1], norm[idx + 1:-1]


def _split_top_args(s: str) -> list[str]:
    """Split a generic argument list on top-level commas only."""
    parts, depth, cur = [], 0, ""
    for ch in s:
        if ch == "<":
            depth += 1
        elif ch == ">":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    if cur:
        parts.append(cur)
    return [p.strip() for p in parts]


def _subst_token(cs_type: str, subst: dict[str, str]) -> str:
    """Substitute generic TYPE PARAMETER names inside a member-type
    spelling (exact-token at top level, recursively inside generics)."""
    if not subst:
        return cs_type
    norm = _norm_cs(cs_type)
    hit = subst.get(norm)
    if hit is not None:
        suffix = "[]" if norm.endswith("[]") else ""
        return hit + suffix
    g = _generic_args(norm)
    if g:
        head, args = g
        parts = [_subst_token(p, subst) for p in _split_top_args(args)]
        return f"{head}<{','.join(parts)}>" + ("[]" if norm.endswith("[]") else "")
    return cs_type


# Unity serializes only public members plus [SerializeField] /
# [SerializeReference] ones. These modifier words (verbatim from dump.cs
# member lines) force exclusion — measured R11: statics DO carry offset
# comments (e.g. LocalisedString.kPluralCodes `// 0x0`), so offset presence
# alone cannot separate them.
_NONSERIALIZED_MODS = frozenset({"static", "const", "event"})
_SERIALIZING_FLAGS = frozenset({"serializeField", "serializeReference"})


class _Shape:
    """Serialized node plan for one field type: typetree type string plus
    the ABSOLUTE-LEVEL child nodes it expands to (``child_base`` records
    the level they start at, so containers can re-base element plans)."""

    __slots__ = ("node_type", "children", "child_base")

    def __init__(self, node_type: str, children: list | None = None,
                 child_base: int = 0):
        self.node_type = node_type
        self.children = children if children is not None else []
        self.child_base = child_base


_PPTR_CHILDREN = [
    {"m_Level": 0, "m_Type": "UInt32", "m_Name": "m_FileID", "m_MetaFlag": 0},
    {"m_Level": 0, "m_Type": "SInt64", "m_Name": "m_PathID", "m_MetaFlag": 0}]

_ENUM_UNDERLYING = {
    "byte": "UInt8", "sbyte": "SInt8",
    "short": "short", "ushort": "unsigned short",
    "int": "int", "uint": "unsigned int",
    "long": "long long", "ulong": "unsigned long long",
}
# (the module-level _PPTR_SHAPE constant was folded into
#  TypetreeSynthesizer._pptr_shape(level) in R11)


class TypetreeSynthesizer:
    """Builds UnityPy node lists ([{m_Level,m_Type,m_Name,m_MetaFlag}, …])
    from a DumpCsIndex.

    R11 serialization model (the input-set fix behind the scout piece-02
    decode-failure census — route 2 had NEVER fired on this corpus):
    dump.cs lists every instance field with RUNTIME MEMORY offsets, but
    Unity serializes only a subset of them, and the stream is packed
    independently of memory layout (a reference field is an 8-byte pointer
    in memory, an inline value in the stream). The synthesized tree
    therefore follows Unity's serialization rules instead of offsets:

    - member selection: public / [SerializeField] / [SerializeReference]
      instance fields only; static, const, event and [NonSerialized]
      members are excluded;
    - base-chain inheritance: classes declaring no serialized fields of
      their own (e.g. TPC.SocialActivityDefinition) read them from the
      chain below, stopping at the UnityEngine serialization boundary;
    - engine objects (transitively UnityEngine.Object-derived, decided
      from the indexed hierarchy rather than a hand list) become
      PPtr<Object> nodes;
    - enums serialize as their underlying integer type;
    - Dictionaries, Nullable, delegates and plain interface fields are
      omitted exactly where Unity omits them; [SerializeReference] fields
      carry their managed-reference id;
    - name resolution is the deterministic DumpCsIndex.resolve ladder
      (exact → assembly-qualified → unique suffix → context-namespace
      tie-break); an unresolved REQUIRED type raises a cause-distinct
      SynthesisError so the dump falls back to raw bytes instead of a
      silent misparse (UnityPy ``check_read`` demands the tree consume
      exactly byte_size, so any residual misfit fails loudly)."""

    MAX_DEPTH = 24

    # the serialization boundary: chains stop once they reach these
    # UnityEngine bases — their serialized form IS the MonoBehaviour header
    _ENGINE_BOUNDARY = {"UnityEngine.Object", "UnityEngine.MonoBehaviour",
                        "UnityEngine.ScriptableObject"}

    def __init__(self, index: DumpCsIndex | None):
        self.index = index
        self._engine_obj_cache: dict[str, bool] = {}

    # Measured R11 on the real corpus: EVERY typetree-less MonoBehaviour
    # payload ends with an embedded managed-reference type table —
    # `[SInt32 count=1][string "Terminus"][string "UnityEngine.DMAT"]
    # [string "FAKE_ASM"]`, byte-identical across all 732 census payloads.
    # (These are exactly the SerializeReference-bearing classes, whose
    # typetrees the bundler strips — the instance's MR type table travels
    # inline instead.) Underscore names keep the block out of stage-5 stub
    # fields and payload hashes (both filter `_`-prefixed keys).
    _MR_TRAILER_TEMPLATE = [
        {"m_Level": 0, "m_Type": "ManagedReferencesRegistry",
         "m_Name": "_managedRefTypes", "m_MetaFlag": _ALIGN_FLAG},
        {"m_Level": 1, "m_Type": "Array", "m_Name": "Array", "m_MetaFlag": 0},
        {"m_Level": 2, "m_Type": "int", "m_Name": "size", "m_MetaFlag": 0},
        {"m_Level": 2, "m_Type": "complex", "m_Name": "data", "m_MetaFlag": 0},
        {"m_Level": 3, "m_Type": "string", "m_Name": "class", "m_MetaFlag": 0},
        {"m_Level": 3, "m_Type": "string", "m_Name": "namespace", "m_MetaFlag": 0},
        {"m_Level": 3, "m_Type": "string", "m_Name": "assembly", "m_MetaFlag": 0},
    ]

    def monobehaviour_nodes(self, class_fullname: str) -> list[dict]:
        """Full MonoBehaviour node list: fixed header + synthesized payload +
        the measured managed-reference table trailer."""
        nodes: list[dict] = [{"m_Level": 0, "m_Type": "MonoBehaviour",
                              "m_Name": "Base", "m_MetaFlag": 0}]
        nodes += [
            {"m_Level": 1, "m_Type": "PPtr<GameObject>", "m_Name": "m_GameObject", "m_MetaFlag": 0},
            {"m_Level": 2, "m_Type": "UInt32", "m_Name": "m_FileID", "m_MetaFlag": 0},
            {"m_Level": 2, "m_Type": "SInt64", "m_Name": "m_PathID", "m_MetaFlag": 0},
            {"m_Level": 1, "m_Type": "bool", "m_Name": "m_Enabled", "m_MetaFlag": _ALIGN_FLAG},
            {"m_Level": 1, "m_Type": "PPtr<MonoScript>", "m_Name": "m_Script", "m_MetaFlag": 0},
            {"m_Level": 2, "m_Type": "UInt32", "m_Name": "m_FileID", "m_MetaFlag": 0},
            {"m_Level": 2, "m_Type": "SInt64", "m_Name": "m_PathID", "m_MetaFlag": 0},
            {"m_Level": 1, "m_Type": "string", "m_Name": "m_Name", "m_MetaFlag": _ALIGN_FLAG},
        ]
        nodes += self.class_nodes(class_fullname, level=1)
        nodes += self._shift(self._MR_TRAILER_TEMPLATE, 1)
        return nodes

    # -- entry ---------------------------------------------------------------

    def class_nodes(self, fullname: str, level: int,
                    _seen: frozenset[str] = frozenset(),
                    _subst: dict[str, str] | None = None,
                    _allow_empty: bool = False) -> list[dict]:
        if self.index is None:
            raise SynthesisError("no dump.cs index loaded")
        subst = _subst or {}
        resolved = self._resolve_required(
            fullname, self._context_of(fullname))
        if resolved in _seen or len(_seen) >= self.MAX_DEPTH:
            raise SynthesisError(f"recursion/cycle limit reached at {fullname}")
        members = self._serialized_members(resolved, subst)
        if not members:
            if _allow_empty:
                # a NESTED type with no serialized members consumes zero
                # stream bytes (Unity emits the node, the serializer writes
                # nothing) — e.g. Unity.Entities native containers inside a
                # job struct pulled into a definition's field graph
                return []
            raise SynthesisError(
                f"no serialized instance fields with offsets for {resolved}")
        ns = self.index.types[resolved].get("namespace") or ""
        nodes: list[dict] = []
        for fname, ftype, _off, flags in members:
            shape = self.field_shape(ftype, flags, ns,
                                     _seen | {resolved}, level + 1, subst)
            if shape is None:
                continue          # Unity omits this field — so does the tree
            nodes.append({"m_Level": level, "m_Type": shape.node_type,
                          "m_Name": fname,
                          "m_MetaFlag": self._meta_of(shape)})
            # shape children are already ABSOLUTE at level+1 (field_shape
            # contract) — no re-shift here
            nodes += shape.children
        return nodes

    # -- member selection (what Unity actually writes) ------------------------

    def _serialized_members(self, fullname: str,
                            subst: dict[str, str]) -> list[tuple]:
        """Serialized members of one type INCLUDING its base chain
        (root first — derived fields follow base fields in both memory
        layout and stream order)."""
        out: list[tuple] = []
        for ancestor in self._base_chain(fullname):
            entry = self.index.types[ancestor]
            for (fname, ftype, off, mods) in entry.get("members") or []:
                mod_words = set(mods.split())
                if mod_words & _NONSERIALIZED_MODS:
                    continue          # static/const/event never serialize
                if off is None:
                    continue          # no memory placement → not serialized
                flags = frozenset(mod_words & _SERIALIZING_FLAGS)
                if "public" not in mod_words \
                        and not (flags & _SERIALIZING_FLAGS):
                    continue          # private/protected without attributes
                ftype = _subst_token(ftype, subst)
                out.append((fname, ftype, off, flags))
        return out

    def _base_chain(self, fullname: str) -> list[str]:
        """fullname → [root ancestor, …, fullname]; stops at the engine
        serialization boundary (engine bases contribute no payload fields)
        and tolerates chains that leave the indexed surface."""
        chain = [fullname]
        seen = {fullname}
        cur = fullname
        while True:
            entry = self.index.types.get(cur) or {}
            base_spelling = entry.get("base")
            if not base_spelling:
                break
            nxt = self.index.resolve(base_spelling,
                                     entry.get("namespace") or "")
            if nxt is None or nxt in seen or nxt in self._ENGINE_BOUNDARY:
                break
            chain.insert(0, nxt)
            seen.add(nxt)
            cur = nxt
        return chain

    def _is_engine_object(self, fullname: str) -> bool:
        """True when the type derives from UnityEngine.Object — such fields
        serialize as PPtr<Object>. Cached chain walk over the index."""
        cached = self._engine_obj_cache.get(fullname)
        if cached is not None:
            return cached
        seen: set[str] = set()
        cur = fullname
        result = False
        while cur and cur not in seen:
            seen.add(cur)
            if cur in self._ENGINE_BOUNDARY:
                result = True
                break
            entry = self.index.types.get(cur) or {}
            base = entry.get("base")
            if not base:
                break
            nxt = self.index.resolve(base, entry.get("namespace") or "")
            if nxt is None:
                # unresolvable link: a UnityEngine leaf spelling settles it
                result = base.rsplit(".", 1)[-1] in (
                    "Object", "MonoBehaviour", "ScriptableObject",
                    "Component", "Behaviour") \
                    and base.startswith("UnityEngine.")
                break
            cur = nxt
        self._engine_obj_cache[fullname] = result
        return result

    # -- field-type planning ---------------------------------------------------

    def field_shape(self, cs_type: str, flags: frozenset, owner_ns: str,
                    seen: frozenset[str], level: int,
                    subst: dict[str, str] | None = None) -> _Shape | None:
        """Node plan for one member type, or None when Unity does not
        serialize it. ``level`` is the ABSOLUTE level this field's expansion
        starts at; every child node in the returned shape carries its final
        absolute m_Level."""
        subst = subst or {}
        norm = _norm_cs(cs_type)

        # managed-reference collections: vector of {int id} items
        # (node shape measured from the game's own trees R11:
        #  `managedRefArrayItem` with a single int `id` child)
        if "serializeReference" in flags and (
                norm.endswith("[]") or (_generic_args(norm) or ("", ""))[0]
                == "List"):
            return _Shape("vector", [
                {"m_Level": level, "m_Type": "Array", "m_Name": "Array",
                 "m_MetaFlag": 0},
                {"m_Level": level + 1, "m_Type": "int", "m_Name": "size",
                 "m_MetaFlag": 0},
                {"m_Level": level + 1, "m_Type": "managedRefArrayItem",
                 "m_Name": "data", "m_MetaFlag": 0},
                {"m_Level": level + 2, "m_Type": "int", "m_Name": "id",
                 "m_MetaFlag": 0},
            ], level)

        if norm.endswith("[]"):                      # single-dim arrays only
            elem = self.field_shape(norm[:-2], flags, owner_ns, seen,
                                    level + 2, subst)
            return self._vector_shape(elem, level) \
                if elem is not None else None

        g = _generic_args(norm)
        if g:
            head, args = g
            if head == "List":
                elem = self.field_shape(args, flags, owner_ns, seen,
                                        level + 2, subst)
                return self._vector_shape(elem, level) \
                    if elem is not None else None
            if head == "PPtr":
                return self._pptr_shape(level)
            if head in ("Dictionary", "HashSet", "Nullable", "IReadOnlyList",
                        "IEnumerable", "ICollection", "IList", "Action",
                        "Func", "UnityAction"):
                return None           # never Unity-serialized
            # concrete generic instantiation → synthesize the definition
            defname = norm[:norm.index("<")]
            r = self.index.resolve(defname, owner_ns)
            if r is None or self.index.types[r].get("kind") == "interface":
                return None
            params = self.index.types[r].get("generic_params") or []
            sub_map = {p: a for p, a in zip(params, _split_top_args(args))}
            merged = dict(subst)
            merged.update(sub_map)
            if self._is_engine_object(r):
                return self._pptr_shape(level)
            children = self.class_nodes(r, level, seen, merged,
                                        _allow_empty=True)
            return _Shape("complex", children, level)

        prim = _PRIMITIVE_NODES.get(cs_type.strip()) \
            or _PRIMITIVE_NODES.get(_cs_type_stem(cs_type))
        if prim:
            return None if prim[0] is None else _Shape(prim[0])
        if norm in ("object", "System.Object"):
            return None               # plain object refs are not serialized

        r = self.index.resolve(norm, owner_ns)
        entry = self.index.types[r] if r is not None else {}
        kind = entry.get("kind")
        # managed references ([SerializeReference]): the serialized value is
        # its registry id — EXCEPT engine-object types, which the serializer
        # PPtrs regardless of the printed attribute (measured R11:
        # InteractionDefinition's SR'd ScriptableObjectWithID-typed fields
        # carry 12-byte PPtrs, not 8-byte ids)
        if kind == "enum":
            und = (entry.get("base") or "int").strip()
            return _Shape(_ENUM_UNDERLYING.get(und, "int"))
        if kind == "interface":
            if "serializeReference" in flags:
                return self._managed_ref_shape(level)
            return None               # plain interface refs are not written
        if r is not None and self._is_engine_object(r):
            return self._pptr_shape(level)
        if "serializeReference" in flags:
            return self._managed_ref_shape(level)
        if r is None:
            return None               # unresolvable → treated as not-written
        children = self.class_nodes(r, level, seen, subst, _allow_empty=True)
        return _Shape("complex", children, level)

    def _managed_ref_shape(self, level: int) -> _Shape:
        """Single managed reference: the game's own trees name the node
        `managedReference` with one int `id` child (measured R11) — a
        4-byte registry id, not the 8-byte id an earlier draft assumed."""
        return _Shape("managedReference", [
            {"m_Level": level, "m_Type": "int", "m_Name": "id",
             "m_MetaFlag": 0}], level)

    # -- internals -----------------------------------------------------------

    @staticmethod
    def _context_of(fullname: str) -> str:
        return fullname.rsplit(".", 1)[0] if "." in fullname else ""

    def _resolve_required(self, spelling: str, context_ns: str) -> str:
        r = self.index.resolve(spelling, context_ns)
        if r is None:
            raise SynthesisError(f"type '{spelling}' not present in dump.cs")
        return r

    def _vector_shape(self, elem: _Shape, level: int) -> _Shape:
        data_level = level + 1
        children = [
            {"m_Level": level, "m_Type": "Array", "m_Name": "Array",
             "m_MetaFlag": 0},
            {"m_Level": data_level, "m_Type": "int", "m_Name": "size",
             "m_MetaFlag": 0},
            {"m_Level": data_level, "m_Type": elem.node_type, "m_Name": "data",
             "m_MetaFlag": 0},
        ] + self._shift(elem.children,
                        (level + 2) - elem.child_base)
        return _Shape("vector", children, level)

    def _pptr_shape(self, level: int) -> _Shape:
        return _Shape("PPtr<Object>",
                      self._shift(_PPTR_CHILDREN, level), level)

    @staticmethod
    def _shift(children: list[dict], delta: int) -> list[dict]:
        return [dict(c, m_Level=c["m_Level"] + delta) for c in children]

    # Scalars narrower than 4 bytes self-pad to 4 in the serialized stream
    # (measured R11 on TPC.QualificationDefinition: two adjacent-in-memory
    # bools occupy 8 stream bytes, exactly like the m_Enabled header bool).
    _SUB4_TYPES = ("bool", "UInt8", "SInt8", "char", "short", "unsigned short")

    @staticmethod
    def _meta_of(shape: _Shape) -> int:
        """kAlign on exactly the nodes the game's own serializer pads:
        variable-width payloads (strings, vectors, complexes containing
        either) and sub-4-byte scalars. 4/8-byte scalars and PPtrs stay
        packed — a stray align there would inject phantom padding into
        the byte-exact read."""
        t = shape.node_type
        if t in ("string", "vector") or t in TypetreeSynthesizer._SUB4_TYPES:
            return _ALIGN_FLAG
        if t == "complex":
            stack = list(shape.children)
            while stack:
                c = stack.pop()
                if c["m_Type"] in ("string", "vector", "Array") \
                        or c["m_Type"] in TypetreeSynthesizer._SUB4_TYPES:
                    return _ALIGN_FLAG
            return 0
        return 0

    def _needs_align(self, cs_type: str, off, nxt_off) -> bool:  # legacy API
        return False

    def _child_nodes(self, cs_type: str, level: int,
                     seen: frozenset[str]) -> list[dict]:  # legacy API
        shape = self.field_shape(cs_type, frozenset(), "", seen, level)
        return [] if shape is None else self._shift(shape.children, level)

    def _node_type(self, cs_type: str) -> str:  # legacy API
        shape = self.field_shape(cs_type, frozenset(), "", frozenset(), 1)
        return shape.node_type if shape is not None else "complex"


def _split_generic_args(s: str) -> tuple[int, str, str]:
    depth = 0
    for i, ch in enumerate(s):
        if ch == "<":
            depth += 1
        elif ch == ">":
            depth -= 1
        elif ch == "," and depth == 1:
            return 2, s[:i], s[i + 1:]
    raise SynthesisError(f"cannot split generic args in '{s}'")


# ---------------------------------------------------------------------------
# Identity-sourced FALLBACK_UNITY_VERSION seeding (spec Revision 4, item 3)

_UNITYFS_MAGIC = b"UnityFS\x00"
_UNITY_REV_OK_RE = re.compile(r"^\d+\.\d+\.\d+([fpab]\d+)?$")

# Measured client engine revision (ASCII at ~0x30 of globalgamemanagers;
# README / data-acquisition.md). Last-resort seed source ONLY for hostless
# probes with no extraction root to read identity.json from — pipeline runs
# always carry identity.json (stage 0), so a real stage never rides on this.
MEASURED_CLIENT_UNITY_VERSION = "2020.3.47f1"

_UNSET = object()   # distinguishes "no explicit version" from an explicit None


def _unityfs_header_versions(abspath) -> tuple[bool, str | None, str | None]:
    """(is_unityfs, player_version, engine_revision) straight from the
    container header: signature, big-endian format int, then the player
    version and engine revision strings. The canonical spelling is two
    length-prefixed strings; containers written with the NUL-terminated
    spelling are parsed by the same rule before giving up (None).
    Content bundles on this client carry the literal string `0.0.0` there
    while catalog.bundle reports the true engine version (measured,
    Revision 4)."""
    try:
        with open(abspath, "rb") as fh:
            head = fh.read(256)
    except OSError:
        return False, None, None
    if not head.startswith(_UNITYFS_MAGIC):
        return False, None, None

    def _lpstr(p: int) -> tuple[bytes | None, int]:
        if p + 4 > len(head):
            return None, p
        (ln,) = struct.unpack(">i", head[p:p + 4])
        p += 4
        if ln < 0 or p + ln > len(head):
            return None, p
        return head[p:p + ln], p + ln

    def _cstr(p: int) -> tuple[bytes | None, int]:
        end = head.find(b"\x00", p)
        if end < 0 or end == p:
            return None, p
        return head[p:end], end + 1

    def _decode(raw: bytes | None) -> str | None:
        if raw is None:
            return None
        try:
            return raw.decode("ascii")
        except UnicodeDecodeError:
            return None

    for reader in (_lpstr, _cstr):
        pos = len(_UNITYFS_MAGIC) + 4   # skip the big-endian format version int
        player_raw, pos = reader(pos)
        if player_raw is None:
            continue
        rev_raw, _pos = reader(pos)
        player, rev = _decode(player_raw), _decode(rev_raw)
        if player is not None:
            return True, player, rev
    return True, None, None


def read_unityfs_header_revision(abspath: Path) -> tuple[bool, str | None]:
    """(is_unityfs, revision_text | None) — the engine-revision half of
    :func:`_unityfs_header_versions`."""
    is_unityfs, _player, rev = _unityfs_header_versions(abspath)
    return is_unityfs, rev


def _version_looks_real(text: str | None) -> bool:
    return text is not None and text.strip() != "0.0.0" \
        and bool(_UNITY_REV_OK_RE.match(text.strip()))


def header_needs_fallback(abspath: Path) -> bool:
    """True when a UnityFS container carries no usable version pair: either
    header version string (player version, engine revision) reads `0.0.0`,
    is malformed, or is missing — the measured content-bundle condition
    (UnityPy keys its UnityVersionFallbackError on these strings).
    Non-UnityFS files never need the seed; their open failures are different
    defects and stay unfiltered in the ledger."""
    is_unityfs, player, rev = _unityfs_header_versions(abspath)
    if not is_unityfs:
        return False
    return not (_version_looks_real(player) and _version_looks_real(rev))


def open_needs_fallback(abspath) -> bool:
    """Shared-seam predicate: does THIS bundle open need the fallback seed?
    A UnityFS container with a 0.0.0/malformed/absent version pair needs it,
    and so do bytes that are not a recognizable UnityFS container at all —
    nothing usable to read a version from (spec Revision 4 §8: 0.0.0 AND
    unparseable headers both trigger the identity-sourced seed). A
    well-formed header reporting real versions never does."""
    if header_needs_fallback(abspath):
        return True
    return not _unityfs_header_versions(abspath)[0]


def _identity_unity_version(extracted_root) -> str | None:
    """identity.json's unityVersion, or None when absent/unparseable."""
    identity_path = Path(extracted_root) / "identity.json"
    if identity_path.is_file():
        try:
            raw = json.loads(
                identity_path.read_text(encoding="utf-8")).get("unityVersion")
            if isinstance(raw, str) and raw.strip():
                return raw.strip()
        except ValueError:
            pass
    return None


def _seedable_unitypy():
    """The UnityPy module whose config knob stages and the suite read."""
    try:
        import UnityPy  # noqa: PLC0415
        return UnityPy
    except ImportError:
        return ensure_unitypy()[0]


def seed_fallback_unity_version(bundle_path, extracted_root=None,
                                fallback_version=_UNSET) -> bool:
    """THE shared stage-3+4 seeding seam (spec Revision 4 item 3, §8 "shared
    helper with stage 4"). Inspect ONE bundle's UnityFS header immediately
    before its ``UnityPy.load()``; when the header is `0.0.0`/unparseable,
    seed ``UnityPy.config.FALLBACK_UNITY_VERSION`` and return True so the
    caller marks that open as fallback-used. False when the header already
    reports a real version — such opens are never counted.

    Version resolution order: explicit ``fallback_version`` >
    ``extracted_root``/identity.json's ``unityVersion`` > the measured
    client revision (reachable only when no extraction root is supplied).
    An explicit ``fallback_version=None`` means exactly that: nothing is
    seeded and UnityPy fails loudly into the ledger instead of being masked.
    """
    abspath = Path(bundle_path)
    if fallback_version is _UNSET:
        fallback_version = (_identity_unity_version(extracted_root)
                            if extracted_root is not None
                            else MEASURED_CLIENT_UNITY_VERSION)
    if fallback_version is None:
        return False
    if not open_needs_fallback(abspath):
        return False
    _seedable_unitypy().config.FALLBACK_UNITY_VERSION = str(fallback_version)
    return True


class FallbackVersionSeeder:
    """Seeds ``UnityPy.config.FALLBACK_UNITY_VERSION`` from identity.json's
    ``unityVersion`` whenever a bundle header is 0.0.0/unparseable, and
    counts every seeded open so the run section can record the usage total —
    recorded fact, never gloss (spec §3 stages 3+4). Thin per-run wrapper
    over :func:`seed_fallback_unity_version` adding identity resolution and
    the insertion-ordered usage list."""

    def __init__(self, extracted_root: Path, unitypy_module):
        self.UnityPy = unitypy_module
        self.identity_version: str | None = _identity_unity_version(extracted_root)
        self.seeded_bundles: list[str] = []   # insertion-ordered, counted only

    @property
    def seeded_count(self) -> int:
        return len(self.seeded_bundles)

    def seed_if_needed(self, abspath: Path, rel: str | None = None) -> bool:
        """Call immediately before ``UnityPy.load()``. True when THIS open
        rides on the identity-sourced fallback version. With no usable
        identity version nothing is seeded — UnityPy fails loudly and the
        failure lands in the ledger instead of being masked."""
        if not seed_fallback_unity_version(
                abspath, fallback_version=self.identity_version):
            return False
        if rel is not None and rel not in self.seeded_bundles:
            self.seeded_bundles.append(rel)
        return True

    def run_section_note(self, attempted: int) -> str:
        src = ("identity.json unityVersion " +
               (self.identity_version or "?")) if self.identity_version \
            else "identity.json carried NO unityVersion — NOT seeded"
        return (f"fallbackVersionUsedBundles: {self.seeded_count}/{attempted} "
                f"(FALLBACK_UNITY_VERSION source: {src})")


# ---------------------------------------------------------------------------
# MonoBehaviour decoding with honest fallback

def _simplify_external_path(path: str) -> str:
    """`archive:/CAB-xxx/CAB-xxx` → `cab-xxx` (PPtr external match key)."""
    p = str(path).replace("\\", "/")
    if p.startswith("archive:/"):
        p = p[len("archive:/"):]
    if p.startswith("assets/"):
        p = p[len("assets/"):]
    return p.rsplit("/", 1)[-1].lower()


# FIXED MonoBehaviour header layout over the raw object bytes (CR#3/F4):
# m_GameObject PPtr (UInt32 m_FileID + SInt64 m_PathID = 12 B) ·
# m_Enabled bool (1 B) aligned to the next multiple of 4 (+3 pad) ·
# m_Script PPtr (12 B) → 28 bytes total. The endianness char is prepended
# at unpack time from the owning serialized file's header.
_MONO_RAW_HEADER_FMT = "IqB3xIq"
_MONO_RAW_HEADER_LEN = struct.calcsize("<" + _MONO_RAW_HEADER_FMT)


def monoscript_pptr_from_raw(obj) -> dict | None:
    """Recover the `m_Script` PPtr `{m_FileID, m_PathID}` off a
    MonoBehaviour's RAW bytes by parsing the fixed header layout above.

    For typetree-less payloads the embedded read raises BEFORE `m_Script`
    is reachable, which left route-2 synthesis unreachable for exactly its
    target population (CR#3: 0 firings / all residues mislabeled as a
    client fact). The recovered PPtr is fed into
    :meth:`MonoScriptIndex.resolve` as a `head`-equivalent; resolve's
    externals/cab logic handles the rest. None when the raw bytes are
    missing/too short or unreadable. Endianness comes from the owning
    serialized file's header, little-endian fallback (the Windows target
    platform — every file on this client)."""
    try:
        raw = obj.get_raw_data()
    except Exception:  # noqa: BLE001 — caller ledgers the cause
        return None
    if not isinstance(raw, (bytes, bytearray)) or len(raw) < _MONO_RAW_HEADER_LEN:
        return None
    af = getattr(obj, "assets_file", None)
    endian = getattr(getattr(af, "header", None), "endian", "<")
    if endian not in ("<", ">"):
        endian = "<"
    go_fid, go_pid, enabled, ms_fid, ms_pid = struct.unpack(
        endian + _MONO_RAW_HEADER_FMT, raw[:_MONO_RAW_HEADER_LEN])
    # layout discriminator: m_Enabled serializes as a 0/1 bool byte — any
    # other value means these bytes are not the fixed MonoBehaviour header
    if enabled > 1:
        return None
    return {"m_FileID": int(ms_fid), "m_PathID": int(ms_pid)}


class MonoScriptIndex:
    """Cross-bundle MonoScript resolution table (Revision 6 fix lane).

    IL2CPP bundles ship MonoBehaviours whose ``m_Script`` PPtr points at a
    MonoScript object living in a SEPARATE monoscript bundle — UnityPy's
    per-bundle environment cannot dereference it, and UnityPy 1.25.3 exposes
    no ``mono_script`` helper at all. The index is built by scanning the
    roster bundles for MonoScript objects BEFORE the export pass and keyed by
    ``(serialized-file cab name lowercased, path_id)``, which is exactly what
    an external PPtr names: ``m_FileID`` indexes the referring file's
    ``externals`` list (1-based; 0 = same file), each entry spelling
    ``archive:/<cab>/<cab>``."""

    def __init__(self):
        self._entries: dict[tuple[str, int], str] = {}
        self.bundles_with_scripts: list[str] = []   # insertion-ordered rels
        self.scripts_indexed = 0

    def index_environment(self, env, rel: str | None = None) -> int:
        """Index every MonoScript of an already-loaded environment.
        Returns the count added."""
        added = 0
        for f in iter_environment_files(env):
            cab = (getattr(f, "name", "") or "").lower()
            for obj in iter_objects_sorted(f):
                if getattr(getattr(obj, "type", None), "name", "") != "MonoScript":
                    continue
                try:
                    d = obj.read_typetree(wrap=False)
                except Exception:  # noqa: BLE001 — unreadable script stays absent
                    continue
                ns = d.get("m_Namespace") or ""
                cn = d.get("m_ClassName") or ""
                full = f"{ns}.{cn}" if ns else cn
                if not full:
                    continue
                self._entries.setdefault((cab, obj.path_id), full)
                added += 1
        if added and rel:
            if rel not in self.bundles_with_scripts:
                self.bundles_with_scripts.append(rel)
        self.scripts_indexed += added
        return added

    def scan_bundle(self, UnityPy, abspath) -> int:
        """Load one bundle and index its MonoScripts. Returns count added."""
        env = UnityPy.load(str(abspath))
        rel = abspath.as_posix() if hasattr(abspath, "as_posix") else None
        return self.index_environment(env, rel)

    def resolve(self, obj, head: dict | None = None) -> str | None:
        """Resolved script fullname for one MonoBehaviour object, or None.
        `head` is the embedded-typetree payload when one was already read —
        it carries ``m_Script`` without a second decode."""
        ms = (head or {}).get("m_Script")
        if not isinstance(ms, dict):
            try:
                ms = obj.read_typetree(wrap=False, check_read=False).get("m_Script")
            except Exception:  # noqa: BLE001
                return None
            if not isinstance(ms, dict):
                return None
        try:
            fid = int(ms.get("m_FileID", 0) or 0)
            pid = int(ms.get("m_PathID", 0) or 0)
        except (TypeError, ValueError):
            return None
        if pid == 0:
            return None
        if fid == 0:
            cab = (getattr(getattr(obj, "assets_file", None), "name", "")
                   or "").lower()
        else:
            exts = getattr(getattr(obj, "assets_file", None), "externals",
                           None) or []
            if fid < 1 or fid > len(exts):
                return None
            cab = _simplify_external_path(getattr(exts[fid - 1], "path", ""))
        return self._entries.get((cab, pid))

    def stats(self) -> dict:
        return {"scriptsIndexed": self.scripts_indexed,
                "bundlesWithScripts": len(self.bundles_with_scripts),
                "distinctEntries": len(self._entries)}


class EmbeddedTreeOracle:
    """Cross-file embedded-typetree lender (R11 G1).

    Unity strips typetrees per SERIALIZED FILE, not per build: the same
    script class carries its game-generated tree in most files and none in
    a few (measured: TPC.GameItemDefinition decodes embedded in 1,654
    dumps while 44 payloads across other files carry no tree). For those
    few, the honest decode is the GAME'S OWN tree of a same-CLASS object
    from another file — keyed by the RESOLVED script class fullname via the
    :class:`MonoScriptIndex` (different files reference different MonoScript
    objects for one class, so the script PPtr itself cannot be the key).

    Captured during stage-3 phase A (the monoscript scan already loads
    every bundle); consulted by :func:`decode_monobehaviour` between the
    local-embedded route and synthesis."""

    def __init__(self, script_index: MonoScriptIndex | None = None):
        self.script_index = script_index
        self._by_script: dict[tuple[str, int], object] = {}
        self._by_class: dict[str, object] = {}
        self.classes_captured: list[str] = []
        self.captured = 0
        self._finalized = False

    def _script_key(self, obj) -> tuple[str, int] | None:
        """(script-cab, path_id) for THIS object's m_Script off the fixed
        raw header — no typetree read needed."""
        pptr = monoscript_pptr_from_raw(obj)
        if not isinstance(pptr, dict):
            return None
        fid = int(pptr.get("m_FileID", 0) or 0)
        pid = int(pptr.get("m_PathID", 0) or 0)
        if pid == 0:
            return None
        af = getattr(obj, "assets_file", None)
        if fid == 0:
            cab = (getattr(af, "name", "") or "").lower()
        else:
            exts = getattr(af, "externals", None) or []
            if fid < 1 or fid > len(exts):
                return None
            cab = _simplify_external_path(getattr(exts[fid - 1], "path", ""))
        return cab, pid

    def capture(self, env) -> int:
        """Index one loaded environment's MonoBehaviour trees, keyed by the
        m_Script PPtr target. Returns the number of NEW script keys
        captured. Class resolution is DEFERRED to :meth:`finalize` because
        a bundle's scripts may live in monoscript bundles the phase-A scan
        has not reached yet."""
        added = 0
        for f in iter_environment_files(env):
            cab_own = (getattr(f, "name", "") or "").lower()
            exts = getattr(f, "externals", None) or []
            for obj in iter_objects_sorted(f):
                if getattr(getattr(obj, "type", None), "name", "") \
                        != "MonoBehaviour":
                    continue
                node = getattr(getattr(obj, "serialized_type", None),
                               "node", None)
                if node is None:
                    continue
                pptr = monoscript_pptr_from_raw(obj)
                if not isinstance(pptr, dict):
                    continue
                fid = int(pptr.get("m_FileID", 0) or 0)
                pid = int(pptr.get("m_PathID", 0) or 0)
                if pid == 0:
                    continue
                if fid == 0:
                    cab = cab_own
                elif 1 <= fid <= len(exts):
                    cab = _simplify_external_path(
                        getattr(exts[fid - 1], "path", ""))
                else:
                    continue
                key = (cab, pid)
                if key not in self._by_script:
                    self._by_script[key] = node
                    added += 1
        self.captured += added
        return added

    def finalize(self) -> int:
        """Resolve captured script keys to class fullnames through the
        finished MonoScriptIndex. Call ONCE after the phase-A scan."""
        self._finalized = True
        if self.script_index is None:
            return 0
        for (cab, pid), cls in self.script_index._entries.items():
            node = self._by_script.get((cab, pid))
            if node is not None and cls not in self._by_class:
                self._by_class[cls] = node
                self.classes_captured.append(cls)
        return len(self._by_class)

    def get(self, obj, script_class: str | None = None):
        """The game-generated tree for THIS object's class, or None.
        ``script_class`` skips the header lookup when the caller already
        resolved the class."""
        if not self._finalized:
            self.finalize()
        cls = script_class
        if cls is None:
            key = self._script_key(obj)
            if key is None:
                return None
            cls = (self.script_index or MonoScriptIndex())._entries.get(key)
        return self._by_class.get(cls) if cls else None


def decode_monobehaviour(obj, synth: TypetreeSynthesizer | None,
                         script_index: MonoScriptIndex | None = None,
                         tree_oracle: EmbeddedTreeOracle | None = None,
                         ) -> tuple[dict, bool, str]:
    """Returns (payload_dict, typetree_decoded, method_note). Never raises —
    falls back to the raw typed dump.

    Decode routes, first fit wins (spec §3 stage 3: typetree-decoded fields
    where possible, `typetreeDecoded:false` marking only genuine residue):
      1. embedded typetree — UnityPy reads the tree the bundle itself ships;
      2. borrowed embedded tree (R11) — the game-generated tree of a
         same-script object from another serialized file
         (:class:`EmbeddedTreeOracle`);
      3. synthesized typetree — typetree-less payloads driven through the
         dump.cs field tables for the RESOLVED script class; resolution for
         those recovers the m_Script PPtr from the fixed raw MonoBehaviour
         header (:func:`monoscript_pptr_from_raw`) when the embedded read
         fails, so synthesis stays reachable for its target population
         (CR#3);
      4. raw typed dump with `_raw.typetreeDecoded:false` + a CAUSE-DISTINCT
         reason (`m_Script pptr unreadable` / `m_Script pptr null` /
         `monoscript not in index` / `synthesis failed for <class>` / the
         wiring facts) — never one blanket string reading as a client fact.

    The resolved script class rides along as `_scriptClass` on EVERY route
    where it is known (Rev 6: the class discriminator downstream must not
    depend on which decode route fired)."""
    try:
        head = obj.read_typetree(wrap=False, check_read=False)
    except Exception:
        head = {}
    embedded_ok = isinstance(head, dict) and bool(head)

    script_class = None
    residue_reason: str | None = None
    if script_index is None:
        residue_reason = "no monoscript index provided"
    else:
        script_class = script_index.resolve(
            obj, head if embedded_ok else None)
        if script_class is None and not embedded_ok:
            # CR#3/F4: typetree-less payload — recover the m_Script PPtr off
            # the raw fixed header so resolution (and route-2 synthesis)
            # fires for exactly the population it exists for.
            ms_pptr = monoscript_pptr_from_raw(obj)
            if ms_pptr is None:
                residue_reason = "m_Script pptr unreadable"
            elif int(ms_pptr.get("m_PathID", 0) or 0) == 0:
                residue_reason = "m_Script pptr null (path_id 0)"
            else:
                residue_reason = "monoscript not in index"
            script_class = script_index.resolve(obj, {"m_Script": ms_pptr})
    if script_class is None:
        legacy = _script_class_name(obj)   # legacy best-effort
        if legacy:
            script_class = legacy
            residue_reason = None

    # Route 1: embedded typetree — the bundle's own authoritative layout.
    if embedded_ok:
        payload = dict(head)
        if script_class:
            payload["_scriptClass"] = script_class
        payload["_decoded"] = {"typetreeDecoded": True,
                               "method": "embedded-typetree"}
        return payload, True, "embedded-typetree"

    # Route 2 (R11): borrowed embedded tree — the game's own typetree of a
    # same-script object from another serialized file. Unity strips trees
    # per FILE, not per build, so a few files hold payloads whose class has
    # game-generated trees everywhere else; those are decoded with the real
    # thing rather than a reconstruction.
    last_error = residue_reason or "script class unresolved"
    if tree_oracle is not None:
        oracle_node = tree_oracle.get(obj, script_class)
        if oracle_node is not None:
            try:
                data = obj.read_typetree(nodes=oracle_node, wrap=False,
                                         check_read=True)
                data.setdefault("_synthesis", {
                    "method": "embedded-tree-oracle",
                    "class": script_class or "?"})
                if script_class:
                    data["_scriptClass"] = script_class
                data.setdefault("_decoded", {
                    "typetreeDecoded": True, "method": "embedded-tree-oracle"})
                return data, True, "embedded-tree-oracle"
            except Exception as exc:  # noqa: BLE001 — fall through to synth
                last_error = (f"oracle tree mismatch for {script_class}: "
                              f"{type(exc).__name__}: {exc}")

    # Route 3: synthesized typetree over the dump.cs field tables.
    # Every failure to reach synthesis carries its OWN cause-distinct reason
    # (CR#3/F4) — a wiring fact (`no dump.cs index`, `no monoscript index`)
    # never masquerades as a client fact, and an unresolved script is
    # reported per cause instead of one blanket string.
    if synth is None:
        last_error = "no serialized typetree and no dump.cs index available"
    else:
        last_error = residue_reason or "script class unresolved"
    if synth is not None and script_class:
        try:
            nodes = synth.monobehaviour_nodes(script_class)
            data = obj.read_typetree(nodes=nodes, wrap=False, check_read=True)
            data.setdefault("_synthesis", {
                "method": "dumpcs-typetree-synthesis", "class": script_class})
            data["_scriptClass"] = script_class
            data.setdefault("_decoded", {
                "typetreeDecoded": True,
                "method": "dumpcs-typetree-synthesis"})
            return data, True, "dumpcs-typetree-synthesis"
        except Exception as exc:  # noqa: BLE001 — fallback is contractual
            last_error = (f"synthesis failed for {script_class}: "
                          f"{type(exc).__name__}: {exc}")

    # Route 3: genuine raw-typed residue.
    raw = obj.get_raw_data()
    payload = dict(head) if isinstance(head, dict) else {}
    payload["_raw"] = {
        "typetreeDecoded": False,
        "rawBytesBase64": __import__("base64").b64encode(raw).decode("ascii"),
        "rawByteCount": len(raw),
        "reason": last_error,
    }
    if script_class:
        payload["_scriptClass"] = script_class
    return payload, False, "raw-typed-dump"


def _script_class_name(obj) -> str | None:
    """Legacy best-effort: UnityPy ≥1.20 exposes no `mono_script` attribute,
    so this only fires when an environment happens to carry one — kept as a
    fallback behind :meth:`MonoScriptIndex.resolve`, never the primary."""
    try:
        script = getattr(obj, "mono_script", None) or getattr(getattr(obj, "object", None),
                                                             "mono_script", None)
        if script is not None:
            ns = getattr(script, "m_Namespace", None) or ""
            cn = getattr(script, "m_ClassName", None)
            if cn:
                return f"{ns}.{cn}" if ns else cn
            return None
    except Exception:  # noqa: BLE001
        return None
    return None


def iter_objects_sorted(env_file):
    """Objects of one serialized file sorted by path_id — deterministic."""
    objs = list((getattr(env_file, "objects", None) or {}).values())
    objs.sort(key=lambda o: (getattr(o, "path_id", 0) or 0,))
    return objs


def iter_environment_files(env):
    """Yield every SerializedFile under a loaded environment, descending
    through nested container levels (a UnityFS BundleFile holds its
    SerializedFiles one level down; deeper nestings exist in the wild)."""
    stack = [f for f in (getattr(env, "files", None) or {}).values() if f]
    seen = 0
    while stack:
        f = stack.pop(0)
        seen += 1
        if seen > 4096:  # pathological nesting guard
            break
        if getattr(f, "objects", None):
            yield f
        child_files = getattr(f, "files", None)
        if isinstance(child_files, dict):
            stack.extend(f2 for f2 in child_files.values() if f2)
