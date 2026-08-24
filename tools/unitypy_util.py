#!/usr/bin/env python3
"""UnityPy bootstrap + typetree synthesis for the Two Point Campus pipeline.

UnityPy import order: pack `.venv` first (make setup installs the pinned
version), then the vendored source clone under `<repo>/tools/UnityPy`. The
resolved source marker ("venv-pip" | "vendored-clone") is returned so stages
can record it in EXTRACTION-LOG.md run sections instead of silently guessing.

IL2CPP bundles ship MonoBehaviours WITHOUT embedded typetrees. Decoding is
attempted through a synthesized typetree driven by the dump.cs field tables
(Il2CppDumper emits exact `// 0x…` instance-field offsets, which double as
ground truth for alignment flags). Anything that fails to synthesize or
decode falls back to a raw typed dump with `typetreeDecoded: false` — never
a silent guess (spec §3 stage 3).
"""
from __future__ import annotations

import io
import json
import re
import struct
import sys
from pathlib import Path

from tpc_common import VENDORED_UNITYPY_CANDIDATES, resolve_pack_dir, resolve_repo_root


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
    r"(class|struct|interface|enum)\s+([A-Za-z_][\w.`]*)(?:<[^>]*>)?"
    r"\s*(?::\s*(.+?))?\s*(?://[^\n]*)?$")
_FIELD_RE = re.compile(
    r"^(\t*)((?:public|private|protected|internal|static|readonly|const|volatile|new|extern|unsafe|sealed|event)\s+)*"
    r"([\w.`<>,+\[\]()\s]+?)\s+([A-Za-z_][\w.]*)\s*(?:=[^;]*)?;"
    r"\s*(?://\s*(?:0x)?([0-9A-Fa-f]+))?\s*$")
_NAMESPACE_RE = re.compile(r"^// Namespace: (.+?)\s*$")


class DumpCsIndex:
    """fullname → {'fields': [(name, type_string, offset_or_None)]}."""

    def __init__(self, dump_cs_path: Path):
        text = Path(dump_cs_path).read_text(encoding="utf-8", errors="replace")
        self.types: dict[str, dict] = {}
        self._parse(text)

    def _parse(self, text: str) -> None:
        namespace = ""
        # stacks of (indent, fullname)
        type_stack: list[tuple[int, str]] = []
        cur_fields: list[tuple[str, str, int | None]] = []
        pending_ns = ""

        def commit(fullname: str) -> None:
            if fullname in self.types and cur_fields:
                return
            if fullname not in self.types:
                self.types[fullname] = {"fields": []}
            self.types[fullname]["fields"] = list(cur_fields)

        for raw in text.splitlines():
            line = raw.rstrip()
            if not line.strip():
                continue
            ns_m = _NAMESPACE_RE.match(line.strip())
            if ns_m:
                pending_ns = ns_m.group(1)
                continue
            decl = _TYPE_DECL_RE.match(line)
            if decl and "(" not in line.split("//")[0]:
                indent = len(decl.group(1))
                name = decl.group(5)
                while type_stack and indent <= type_stack[-1][0]:
                    done_fullname = type_stack.pop()[1]
                    commit(done_fullname)
                    cur_fields.clear()
                namespace = pending_ns
                base = ""
                if type_stack and indent > type_stack[-1][0]:
                    base = type_stack[-1][1] + "+"
                elif not type_stack:
                    base = f"{namespace}." if namespace else ""
                    if base == ".":
                        base = ""
                fullname = base + name
                type_stack.append((indent, fullname))
                cur_fields.clear()
                continue
            if type_stack:
                fld = _FIELD_RE.match(line)
                if fld and "(" not in line.split(";")[0]:
                    indent = len(fld.group(1))
                    top_indent = type_stack[-1][0] if type_stack else 0
                    if indent > top_indent:  # member of the innermost type
                        mods = fld.group(2) or ""
                        off_txt = fld.group(5)
                        offset = int(off_txt, 16) if off_txt else None
                        cur_fields.append((fld.group(4), fld.group(3).strip(), offset))
        while type_stack:
            commit(type_stack.pop()[1])
            cur_fields.clear()

    def fields(self, fullname: str) -> list[tuple[str, str, int | None]] | None:
        t = self.types.get(fullname)
        if t is None:
            # tolerate assembly-qualified spellings `Ns.Type, Assembly`
            stem = fullname.split(",")[0].strip()
            t = self.types.get(stem)
        return list(t["fields"]) if t is not None else None


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
    """Normalize a C# spelling from dump.cs to a lookup key."""
    t = t.replace(" ", "").split(",")[0]
    t = re.sub(r"<.*>", "", t)
    t = t.replace("+", ".")
    return t


class TypetreeSynthesizer:
    """Builds UnityPy node lists ([{m_Level,m_Type,m_Name,m_MetaFlag}, …])
    from a DumpCsIndex, honoring measured field offsets for align flags."""

    MAX_DEPTH = 24

    def __init__(self, index: DumpCsIndex | None):
        self.index = index

    def monobehaviour_nodes(self, class_fullname: str) -> list[dict]:
        """Full MonoBehaviour node list: fixed header + synthesized payload."""
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
        return nodes

    def class_nodes(self, fullname: str, level: int,
                    _seen: frozenset[str] = frozenset()) -> list[dict]:
        if self.index is None:
            raise SynthesisError("no dump.cs index loaded")
        if len(_seen) >= self.MAX_DEPTH or fullname in _seen:
            raise SynthesisError(f"recursion/cycle limit reached at {fullname}")
        fields = self.index.fields(fullname)
        if fields is None:
            raise SynthesisError(f"type '{fullname}' not present in dump.cs")
        instance = [(n, t, o) for (n, t, o) in fields if o is not None]
        if not instance:
            raise SynthesisError(f"no instance fields with offsets for {fullname}")
        nodes: list[dict] = []
        for i, (fname, ftype, off) in enumerate(instance):
            nxt_off = instance[i + 1][2] if i + 1 < len(instance) else None
            meta = _ALIGN_FLAG if self._needs_align(ftype, off, nxt_off) else 0
            nodes.append({"m_Level": level, "m_Type": self._node_type(ftype),
                          "m_Name": fname, "m_MetaFlag": meta})
            nodes += self._child_nodes(ftype, level + 1, _seen | {fullname})
        return nodes

    # -- internals -----------------------------------------------------------

    def _node_type(self, cs_type: str) -> str:
        stem = _cs_type_stem(cs_type)
        prim = _PRIMITIVE_NODES.get(cs_type.strip()) or _PRIMITIVE_NODES.get(stem)
        if prim:
            return prim[0]
        if cs_type.endswith("[]"):
            return "vector"
        if stem.startswith(("List<", "IReadOnlyList<")):
            return "vector"
        if stem.startswith(("Dictionary<",)):
            return "vector"
        if stem.startswith(("PPtr<", "UnityEngine.PPtr<")):
            return "PPtr<Object>"
        if stem.startswith("UnityEngine.Object"):
            return "PPtr<Object>"
        return "complex"

    def _needs_align(self, cs_type: str, off: int, nxt_off: int | None) -> bool:
        if nxt_off is None:
            return False
        stem = _cs_type_stem(cs_type)
        prim = _PRIMITIVE_NODES.get(cs_type.strip()) or _PRIMITIVE_NODES.get(stem)
        if prim is None or prim[1] is None:
            return True  # variable-length payloads are followed by alignment
        size = prim[1] if prim[0] != "vector" else 4
        end = off + size
        padded = end + ((-end) % 4)
        return nxt_off > end and nxt_off >= padded

    def _child_nodes(self, cs_type: str, level: int,
                     seen: frozenset[str]) -> list[dict]:
        stem = _cs_type_stem(cs_type)
        prim = _PRIMITIVE_NODES.get(cs_type.strip()) or _PRIMITIVE_NODES.get(stem)
        if prim:
            return []
        if cs_type.endswith("[]"):
            elem = cs_type[:-2]
            return self._vector_children(elem, level, seen)
        if stem.startswith(("List<", "IReadOnlyList<")):
            elem = cs_type[cs_type.index("<") + 1:cs_type.rindex(">")]
            return self._vector_children(elem, level, seen)
        if stem.startswith("Dictionary<"):
            kv = cs_type[cs_type.index("<") + 1:cs_type.rindex(">")]
            depth, k, v = _split_generic_args(kv)
            arr = [{"m_Level": level, "m_Type": "Array", "m_Name": "Array", "m_MetaFlag": 0},
                   {"m_Level": level + 1, "m_Type": "int", "m_Name": "size", "m_MetaFlag": 0}]
            pair = [{"m_Level": level + 1, "m_Type": "pair", "m_Name": "data", "m_MetaFlag": 0}]
            pair.append({"m_Level": level + 2, "m_Type": self._node_type(k),
                         "m_Name": "key", "m_MetaFlag": 0})
            pair += self._child_nodes(k, level + 3, seen)
            pair.append({"m_Level": level + 2, "m_Type": self._node_type(v),
                         "m_Name": "value", "m_MetaFlag": 0})
            pair += self._child_nodes(v, level + 3, seen)
            return arr + pair
        if stem.startswith(("PPtr<", "UnityEngine.PPtr<")):
            return [{"m_Level": level, "m_Type": "UInt32", "m_Name": "m_FileID", "m_MetaFlag": 0},
                    {"m_Level": level, "m_Type": "SInt64", "m_Name": "m_PathID", "m_MetaFlag": 0}]
        if stem.startswith("UnityEngine.Object") or stem == "UnityEngine.Object":
            return [{"m_Level": level, "m_Type": "UInt32", "m_Name": "m_FileID", "m_MetaFlag": 0},
                    {"m_Level": level, "m_Type": "SInt64", "m_Name": "m_PathID", "m_MetaFlag": 0}]
        if "<" in stem:  # unhandled generic instantiation
            raise SynthesisError(f"unsupported generic type '{cs_type}'")
        return self.class_nodes(cs_type, level, seen)

    def _vector_children(self, elem: str, level: int, seen: frozenset[str]) -> list[dict]:
        return [
            {"m_Level": level, "m_Type": "Array", "m_Name": "Array", "m_MetaFlag": 0},
            {"m_Level": level + 1, "m_Type": "int", "m_Name": "size", "m_MetaFlag": 0},
            {"m_Level": level + 1, "m_Type": self._node_type(elem),
             "m_Name": "data", "m_MetaFlag": 0},
        ] + self._child_nodes(elem, level + 2, seen)


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


def read_unityfs_header_revision(abspath: Path) -> tuple[bool, str | None]:
    """(is_unityfs, revision_text | None) read straight from the UnityFS
    container header: signature, big-endian format int, then two
    length-prefixed strings — player version, engine revision. Content
    bundles on this client carry the literal string `0.0.0` there while
    catalog.bundle reports the true engine version (measured, Revision 4)."""
    try:
        with open(abspath, "rb") as fh:
            head = fh.read(256)
    except OSError:
        return False, None
    if not head.startswith(_UNITYFS_MAGIC):
        return False, None
    pos = len(_UNITYFS_MAGIC) + 4   # skip the big-endian format version int

    def _read_str(p: int) -> tuple[bytes | None, int]:
        if p + 4 > len(head):
            return None, p
        (ln,) = struct.unpack(">i", head[p:p + 4])
        p += 4
        if ln < 0 or p + ln > len(head):
            return None, p
        return head[p:p + ln], p + ln

    _player, pos = _read_str(pos)
    rev, _pos = _read_str(pos)
    if rev is None:
        return True, None
    try:
        return True, rev.decode("ascii")
    except UnicodeDecodeError:
        return True, None


def header_needs_fallback(abspath: Path) -> bool:
    """True when a UnityFS container's revision header literally reads
    `0.0.0` or cannot be parsed — the measured content-bundle condition.
    Non-UnityFS files never need the seed; their open failures are different
    defects and stay unfiltered in the ledger."""
    is_unityfs, rev = read_unityfs_header_revision(abspath)
    if not is_unityfs:
        return False
    if rev is None:
        return True
    text = rev.strip()
    if not _UNITY_REV_OK_RE.match(text):
        return True
    return text == "0.0.0"


class FallbackVersionSeeder:
    """Seeds ``UnityPy.config.FALLBACK_UNITY_VERSION`` from identity.json's
    ``unityVersion`` whenever a bundle header is 0.0.0/unparseable, and
    counts every seeded open so the run section can record the usage total —
    recorded fact, never gloss (spec §3 stages 3+4). Shared by stage 3 and
    stage 4 (locale bundles are content bundles too)."""

    def __init__(self, extracted_root: Path, unitypy_module):
        self.UnityPy = unitypy_module
        self.identity_version: str | None = None
        identity_path = extracted_root / "identity.json"
        if identity_path.is_file():
            try:
                raw = json.loads(
                    identity_path.read_text(encoding="utf-8")).get("unityVersion")
                if isinstance(raw, str) and raw.strip():
                    self.identity_version = raw.strip()
            except ValueError:
                pass
        self.seeded_bundles: list[str] = []   # insertion-ordered, counted only

    @property
    def seeded_count(self) -> int:
        return len(self.seeded_bundles)

    def seed_if_needed(self, abspath: Path, rel: str | None = None) -> bool:
        """Call immediately before ``UnityPy.load()``. True when THIS open
        rides on the identity-sourced fallback version. With no usable
        identity version nothing is seeded — UnityPy fails loudly and the
        failure lands in the ledger instead of being masked."""
        if not header_needs_fallback(abspath):
            return False
        if self.identity_version is None:
            return False
        self.UnityPy.config.FALLBACK_UNITY_VERSION = self.identity_version
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

def decode_monobehaviour(obj, synth: TypetreeSynthesizer | None) -> tuple[dict, bool, str]:
    """Returns (payload_dict, typetree_decoded, method_note). Never raises —
    falls back to the raw typed dump."""
    try:
        head = obj.read_typetree(wrap=False, check_read=False)
    except Exception:
        head = {}
    script_class = _script_class_name(obj)
    if synth is not None and script_class:
        try:
            nodes = synth.monobehaviour_nodes(script_class)
            data = obj.read_typetree(nodes=nodes, wrap=False, check_read=True)
            data.setdefault("_synthesis", {
                "method": "dumpcs-typetree-synthesis", "class": script_class})
            return data, True, "dumpcs-typetree-synthesis"
        except Exception as exc:  # noqa: BLE001 — fallback is contractual
            last_error = f"{type(exc).__name__}: {exc}"
        else:
            last_error = None
    else:
        last_error = "no dump.cs index available"
    raw = obj.get_raw_data()
    payload = dict(head) if isinstance(head, dict) else {}
    payload["_raw"] = {
        "typetreeDecoded": False,
        "rawBytesBase64": __import__("base64").b64encode(raw).decode("ascii"),
        "rawByteCount": len(raw),
        "reason": last_error,
    }
    return payload, False, "raw-typed-dump"


def _script_class_name(obj) -> str | None:
    """Best-effort MonoBehaviour payload class: UnityPy exposes m_Script as a
    PPtr; the MonoScript name sits in objects cache — resolve via bundle
    objects when possible, else fall back to the object's own name."""
    try:
        script = getattr(obj, "mono_script", None) or getattr(getattr(obj, "object", None),
                                                             "mono_script", None)
        if script is not None:
            return getattr(script, "m_ClassName", None)
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
