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
