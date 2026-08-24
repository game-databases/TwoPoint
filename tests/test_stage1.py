"""Stage 1 `decompile` obligations (spec §8 stage-1 bullets + §3 acceptance,
Revision 4).

Hostless scope: the structural sub-artifacts — assembly-index builder
(present + stripped cases), the MULTI-IMAGE success gate (non-empty DummyDll
set covering every ScriptingAssemblies entry; Assembly-CSharp.dll NOT
required), class-hierarchy parsing on a dump.cs-format slice spanning more
than one assembly image, the script.json-enumerates-no-types rule, and the
primary/fallback source selection rule. Real Il2CppDumper execution and the
PRIMARY-vs-fallback equality over parseable DummyDll PE files are
client-gated (test_client_gated.py).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from _impl import (HIERARCHY_NAMES, MULTI_IMAGE_GATE_NAMES, get_sym, load_tool,
                   skip_if_none)

# Real Il2CppDumper dump.cs shape: zero-indent declarations, "// Namespace:"
# comment lines, no access modifiers. Revision 4: the slice SPANS MORE THAN
# ONE ASSEMBLY IMAGE (the `// Image N:` headers Il2CppDumper writes per
# image) — this client's game code lives in TPS.Game/TPS.Core images, and the
# hierarchy is built over ALL present game-code images.
DUMP_CS_SLICE = """\
// Image 11: mscorlib.dll - 0

// Image 47: TPS.Game.dll - 2
// Namespace: TPC.Items
class ItemConfig : ScriptableObject, ILocNamed // TypeDefIndex: 1001
{
\tstring id; // 0x18
\tstring nameLoc; // 0x20
\tint tier; // 0x28

\tvoid Init() { }
\tstring DisplayName() { return null; }
}

// Namespace: TPC.Items
interface ILocNamed // TypeDefIndex: 1002
{
\tstring NameKey();
}

// Image 48: TPS.Core.dll - 2
// Namespace: TPC.Rooms
class RoomConfig : RoomBase // TypeDefIndex: 1003
{
\tint slots; // 0x18
}

// Namespace: TPC.Rooms
class RoomBase : MonoBehaviour // TypeDefIndex: 1004
{
}

// Namespace: TPC.Core
enum Rarity // TypeDefIndex: 1005
{
\tCommon = 0,
\tRare = 1,
}
"""

SLICE_TYPES = {"ItemConfig", "ILocNamed", "RoomConfig", "RoomBase", "Rarity"}
SLICE_IMAGES = {"TPS.Game", "TPS.Core"}  # the game-code images in the slice

SCRIPT_JSON_SLICE = json.dumps({
    "ScriptMethod": [{"Address": 1, "Name": "TPC.Items.ItemConfig.Init()"}],
    "ScriptString": [{"Index": 0, "Value": "item_alpha_name"}],
    "Addresses": [],
})

ASSEMBLIES_FIXTURE = ["Assembly-CSharp", "mscorlib",
                      "Assembly-CSharp-firstpass", "TPC.Stripped"]


def _structural_mod():
    return skip_if_none(load_tool("build_structural.py"), "tools/build_structural.py")


def _write_inputs(tmp_path: Path, *, with_dump_cs=True):
    dummy_out = tmp_path / "decompiled-out"
    dll_dir = dummy_out / "DummyDll"
    dll_dir.mkdir(parents=True)
    for name in ("Assembly-CSharp.dll", "mscorlib.dll"):
        (dll_dir / name).write_bytes(b"MZ" + b"\x00" * 64)  # fake PE — structure only
    sa = tmp_path / "ScriptingAssemblies.json"
    sa.write_text(json.dumps({"Names": [a + ".dll" for a in ASSEMBLIES_FIXTURE]}),
                  encoding="utf-8", newline="\n")
    if with_dump_cs:
        (dummy_out / "dump.cs").write_text(DUMP_CS_SLICE, encoding="utf-8", newline="\n")
    ext = tmp_path / "extracted"
    ext.mkdir(parents=True, exist_ok=True)
    return dummy_out, sa, ext


def test_assembly_index_builder_present_and_stripped(tmp_path):
    mod = _structural_mod()
    run_fn = skip_if_none(get_sym(mod, *("run", "build_structural")),
                          "structural run()/builder entrypoint")
    dummy_out, sa, ext = _write_inputs(tmp_path, with_dump_cs=False)
    try:
        run_fn(dummy_out, sa, ext)
    except TypeError:
        run_fn(dummy_out=dummy_out, scripting_assemblies_path=sa,
               extracted_root=ext)
    idx_path = ext / "decompiled" / "structural" / "assembly-index.json"
    assert idx_path.exists(), "run() did not emit assembly-index.json"
    obj = json.loads(idx_path.read_text(encoding="utf-8"))
    rows = obj.get("assemblies") if isinstance(obj, dict) else obj
    assert rows, "assembly-index is empty"
    by_assembly = {r["assembly"]: r["status"] for r in rows}
    for asm in ASSEMBLIES_FIXTURE:
        assert asm in by_assembly, (
            f"every ScriptingAssemblies.json entry must be classified; missing {asm!r}")
    assert by_assembly["Assembly-CSharp"] == "dummy-present"
    assert by_assembly["mscorlib"] == "dummy-present"
    stripped = [a for a, s in by_assembly.items() if "stripped" in s or "absent" in s]
    assert set(stripped) == {"Assembly-CSharp-firstpass", "TPC.Stripped"}, \
        f"stripped classification wrong: {sorted(stripped)}"


def test_class_hierarchy_parser_fallback_dumpcs_slice(tmp_path):
    mod = _structural_mod()
    fn = skip_if_none(get_sym(mod, *HIERARCHY_NAMES),
                      "dump.cs hierarchy parser")
    p = tmp_path / "dump.cs"
    p.write_text(DUMP_CS_SLICE, encoding="utf-8", newline="\n")
    try:
        rows = fn(p)
    except TypeError:
        rows = fn(p.read_text(encoding="utf-8"))
    assert isinstance(rows, list) and rows, f"parser returned no types: {rows!r}"
    names = {r.get("name") for r in rows if isinstance(r, dict)}
    missing = SLICE_TYPES - names
    extra = names - SLICE_TYPES - {"Serializable", "MonoBehaviour", "ScriptableObject"}
    assert not missing, f"dump.cs slice types missed by parser: {sorted(missing)}"
    assert not extra, f"parser invented non-top-level types: {sorted(extra)}"
    row = next(r for r in rows if r.get("name") == "ItemConfig")
    # pinned per-type row shape (spec §3 stage 1)
    for k in ("assembly", "namespace", "name", "baseType", "interfaces",
              "methodCount", "fieldCount"):
        assert k in row, f"hierarchy row missing pinned field {k!r}: {row}"
    assert row["namespace"] == "TPC.Items"
    assert sorted(row["interfaces"]) == ["ILocNamed", "ScriptableObject"] or \
        row["interfaces"] == ["ILocNamed"], f"interface extraction off: {row!r}"


def test_script_json_enumerates_no_types(tmp_path):
    """Pinned rule: script.json is a method/string-literal artifact and
    enumerates NO types — feeding it to the hierarchy source yields zero."""
    mod = _structural_mod()
    fn = get_sym(mod, *HIERARCHY_NAMES)
    if fn is None:
        pytest.skip(f"impl-missing: hierarchy parser (tried {HIERARCHY_NAMES})")
    p = tmp_path / "script.json"
    p.write_text(SCRIPT_JSON_SLICE, encoding="utf-8", newline="\n")
    try:
        rows = fn(p)
    except TypeError:
        rows = fn(p.read_text(encoding="utf-8"))
    n = len(rows) if isinstance(rows, list) else int(rows or 0)
    assert n == 0, f"script.json yielded {n} types — it enumerates no types (pinned)"


def test_hierarchy_source_selection_prefers_parseable_dummydll(tmp_path):
    """Selection rule: PRIMARY = DummyDll typedef enumeration; FALLBACK only
    when the reader resolves nothing. With fake (unparseable) DLL bytes plus a
    dump.cs present, the fallback must be chosen and STAMPED."""
    mod = _structural_mod()
    run_fn = get_sym(mod, *("run", "build_structural"))
    if run_fn is None:
        pytest.skip("impl-missing: structural run() entrypoint")
    dummy_out, sa, ext = _write_inputs(tmp_path, with_dump_cs=True)
    summary = run_fn(dummy_out, sa, ext)
    stamp = json.loads(
        (ext / "decompiled" / "structural" / "assembly-index.json").read_text(encoding="utf-8"))
    meta = stamp.get("meta", {})
    src = str(meta.get("hierarchySource", summary.get("hierarchySource", "")))
    assert "dumpcs" in src.lower() or "fallback" in src.lower(), (
        f"unparseable DummyDll bytes must route to the dump.cs fallback; "
        f"hierarchySource stamped {src!r}")
    hier = (ext / "decompiled" / "structural" / "class-hierarchy.jsonl").read_text(
        encoding="utf-8").splitlines()
    assert len([ln for ln in hier if ln.strip()]) == len(SLICE_TYPES), (
        f"fallback hierarchy rows != {len(SLICE_TYPES)} top-level declarations")


# --- Revision 4: multi-image gate fixtures ------------------------------------------

GAME_CODE_IMAGES = ("TPS.Game", "TPS.Core", "TPS.Core.Cpp")
GATE_ASSEMBLY_LIST = ["Assembly-CSharp", "mscorlib", *GAME_CODE_IMAGES,
                      "TPC.Stripped"]
ABSENT_MARKERS = ("absent", "stripped")


def _gate_fn():
    mod = skip_if_none(load_tool("stage1_decompile.py"),
                       "tools/stage1_decompile.py")
    return skip_if_none(get_sym(mod, *MULTI_IMAGE_GATE_NAMES),
                        "stage-1 multi-image gate")


def _call_gate(gate, structural_dir: Path, dummy_dll: Path):
    try:
        return gate(structural_dir, dummy_dll)
    except TypeError:
        pass
    try:
        return gate(structural_dir=structural_dir, dummy_dll=dummy_dll)
    except TypeError:
        pass
    try:
        return gate(structural_dir=structural_dir, dummy_dll_dir=dummy_dll)
    except TypeError:
        return gate(dummy_dll_dir=dummy_dll, structural_dir=structural_dir)


def _write_multi_image_inputs(tmp_path: Path):
    """A DummyDll set of several game-code images and NO Assembly-CSharp.dll
    (this client ships none) plus a ScriptingAssemblies.json that still lists
    Assembly-CSharp — it must classify absent-with-marker."""
    bs = skip_if_none(load_tool("build_structural.py"),
                      "tools/build_structural.py")
    run_fn = skip_if_none(get_sym(bs, *("run", "build_structural")),
                          "structural run()/builder entrypoint")
    dummy_out = tmp_path / "decompiled-out"
    dll_dir = dummy_out / "DummyDll"
    dll_dir.mkdir(parents=True)
    for name in GAME_CODE_IMAGES:
        (dll_dir / f"{name}.dll").write_bytes(b"MZ" + b"\x00" * 64)
    sa = tmp_path / "ScriptingAssemblies.json"
    sa.write_text(json.dumps({"Names": [a + ".dll" for a in GATE_ASSEMBLY_LIST]}),
                  encoding="utf-8", newline="\n")
    ext = tmp_path / "extracted"
    ext.mkdir(parents=True, exist_ok=True)
    try:
        run_fn(dummy_out, sa, ext)
    except TypeError:
        run_fn(dummy_out=dummy_out, scripting_assemblies_path=sa,
               extracted_root=ext)
    structural_dir = ext / "decompiled" / "structural"
    idx_path = structural_dir / "assembly-index.json"
    return dummy_out, dll_dir, structural_dir, idx_path


def test_multi_image_gate_passes_without_assembly_csharp(tmp_path):
    """Revision 4 gate: several game-code images and NO Assembly-CSharp.dll
    PASS; every ScriptingAssemblies entry is classified, Assembly-CSharp
    absent-with-marker, ≥1 dummy-present backed by a real image."""
    gate = _gate_fn()
    dummy_out, dll_dir, structural_dir, idx_path = _write_multi_image_inputs(
        tmp_path)
    problems = list(_call_gate(gate, structural_dir, dll_dir))
    assert not problems, (
        f"a DummyDll set of {len(GAME_CODE_IMAGES)} game-code images with NO "
        f"Assembly-CSharp.dll must PASS the multi-image gate; got: {problems}")
    obj = json.loads(idx_path.read_text(encoding="utf-8"))
    rows = obj.get("assemblies") if isinstance(obj, dict) else obj
    by_assembly = {r["assembly"]: r["status"] for r in rows}
    for asm in GATE_ASSEMBLY_LIST:
        assert asm in by_assembly, (
            f"every ScriptingAssemblies.json entry must be classified; "
            f"missing {asm!r}")
    assert by_assembly["TPS.Game"] == "dummy-present", (
        f"game-code image TPS.Game classified {by_assembly['TPS.Game']!r}")
    for absent_asm in ("Assembly-CSharp", "TPC.Stripped"):
        status = by_assembly[absent_asm]
        assert any(m in status for m in ABSENT_MARKERS), (
            f"{absent_asm} (no image shipped) must classify present-or-"
            f"absent-WITH-MARKER; got {status!r}")
    backed = [a for a in GAME_CODE_IMAGES
              if by_assembly[a] == "dummy-present"
              and (dll_dir / f"{a}.dll").is_file()]
    assert backed, "at least one dummy-present entry must be backed by a real image"


def test_multi_image_gate_empty_dummydll_set_fails(tmp_path):
    """Revision 4 gate: an EMPTY DummyDll set FAILS it (spec §8 stage 1)."""
    bs = skip_if_none(load_tool("build_structural.py"),
                      "tools/build_structural.py")
    run_fn = skip_if_none(get_sym(bs, *("run", "build_structural")),
                          "structural run()/builder entrypoint")
    dummy_out = tmp_path / "empty-out"
    dll_dir = dummy_out / "DummyDll"
    dll_dir.mkdir(parents=True)  # EMPTY set — no images at all
    sa = tmp_path / "ScriptingAssemblies.json"
    sa.write_text(json.dumps({"Names": [a + ".dll" for a in GATE_ASSEMBLY_LIST]}),
                  encoding="utf-8", newline="\n")
    ext = tmp_path / "extracted"
    ext.mkdir(parents=True, exist_ok=True)
    try:
        run_fn(dummy_out, sa, ext)
    except TypeError:
        run_fn(dummy_out=dummy_out, scripting_assemblies_path=sa,
               extracted_root=ext)
    gate = _gate_fn()
    raised = False
    problems = []
    try:
        problems = list(_call_gate(gate, ext / "decompiled" / "structural",
                                   dll_dir) or [])
    except Exception:  # a raised stage error also counts as failing the gate
        raised = True
    assert raised or problems, (
        "an EMPTY DummyDll set must FAIL the multi-image gate (non-empty "
        "problem list or a raised stage error)")


def test_hierarchy_parser_spans_multiple_images(tmp_path):
    """Revision 4 §8: the dump.cs slice spans more than one assembly image;
    the parsed hierarchy must carry that distinction in the pinned `assembly`
    row field (hierarchy over ALL present game-code images), never collapse
    onto one label."""
    mod = _structural_mod()
    fn = skip_if_none(get_sym(mod, *HIERARCHY_NAMES), "dump.cs hierarchy parser")
    p = tmp_path / "dump.cs"
    p.write_text(DUMP_CS_SLICE, encoding="utf-8", newline="\n")
    try:
        rows = fn(p)
    except TypeError:
        rows = fn(p.read_text(encoding="utf-8"))
    assert isinstance(rows, list) and rows, f"parser returned no types: {rows!r}"
    names = {r.get("name") for r in rows if isinstance(r, dict)}
    assert SLICE_TYPES <= names, f"multi-image slice types missed: {sorted(SLICE_TYPES - names)}"
    assemblies = {str(r.get("assembly") or "").strip() for r in rows
                  if isinstance(r, dict)}
    assemblies.discard("")
    lowered = {a.lower().removesuffix(".dll") for a in assemblies}
    hits = {img.lower() for img in SLICE_IMAGES if any(img.lower() in a for a in lowered)}
    assert len(hits) == len(SLICE_IMAGES), (
        f"hierarchy rows must span the slice's assembly images "
        f"{sorted(SLICE_IMAGES)} (Revision 4: hierarchy over ALL present "
        f"game-code images); attributed assemblies were {sorted(assemblies)}")
