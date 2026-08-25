"""R11 G1 — typetree synthesis input set (scout piece-02 §6 G1).

Route-2 synthesis had NEVER fired on this corpus: the synthesizer lacked
base-chain inheritance, unqualified-name resolution, generic handling,
Unity member-selection rules, and the measured managed-reference trailer.
These tests pin each fix at unit level with fixture dump.cs snippets; the
byte-exact proof over the real 732-dump population lives in the
client-gated heavy leg + the R11 re-proof run.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from _impl import load_tool  # noqa: E402


@pytest.fixture(scope="module")
def uu():
    mod = load_tool("unitypy_util.py")
    if mod is None:
        pytest.skip("impl-missing: tools/unitypy_util.py not loadable")
    return mod


def _write_dump(uu, tmp_path, text):
    p = tmp_path / "dump.cs"
    p.write_text(text, encoding="utf-8")
    return uu.DumpCsIndex(p)


# --- fixture dump.cs snippets ------------------------------------------------

DUMP_FULL = """// Namespace: TPS.Core.Localisation
[Serializable]
public struct LocalisedString // TypeDefIndex: 9108
{
\t// Fields
\t[SerializeField] // RVA: 0xAEF70 Offset: 0xAE570 VA: 0x1800AEF70
\tprivate string _dev; // 0x0
\t[SerializeField] // RVA: 0xAEF70 Offset: 0xAE570 VA: 0x1800AEF70
\tprivate int _termID; // 0x8
\tprivate static readonly string[] kPluralCodes; // 0x0
}

// Namespace: UnityEngine
public class Object // TypeDefIndex: 100
{
}

// Namespace: UnityEngine
public class ScriptableObject : Object // TypeDefIndex: 101
{
}

// Namespace: UnityEngine
public class Sprite : Object // TypeDefIndex: 102
{
}

// Namespace: TPC
public enum RoomType // TypeDefIndex: 1
{
\tpublic int value__; // 0x0
}

// Namespace: TPC
public class LiteBase : UnityEngine.ScriptableObject // TypeDefIndex: 2
{
\t// Fields
\t[SerializeField] // RVA: 0xAEF70 Offset: 0xAE570 VA: 0x1800AEF70
\tprivate int _baseField; // 0x10
}

// Namespace: TPC
public class WidgetLiteDefinition : LiteBase // TypeDefIndex: 3
{
\t// Fields
\tpublic LocalisedString Label; // 0x18
\tpublic RoomType Kind; // 0x20
\tpublic System.Collections.Generic.List<string> Aliases; // 0x28
\tpublic System.Collections.Generic.Dictionary<int, string> Lookup; // 0x30
\tpublic System.Nullable<int> Maybe; // 0x38
\tpublic System.Action OnDone; // 0x40
\tpublic UnityEngine.Sprite Icon; // 0x48
\tpublic string[] Names; // 0x50
}

// Namespace: TPC
public class WidgetDefinition : UnityEngine.ScriptableObject // TypeDefIndex: 4
{
\t// Fields
\tprivate static readonly int[] s_Cache; // 0x0
\tpublic int Size; // 0x18
\tpublic WidgetLiteDefinition Lite; // 0x20
}

// Namespace: Other
public class WidgetDefinition // TypeDefIndex: 5
{
}
"""

DUMP_AMBIG = """// Namespace: TPC
public class SMB_Listener : UnityEngine.MonoBehaviour // TypeDefIndex: 6
{
\t// Fields
\tpublic AnimParam BaseParam; // 0x18
}

// Namespace: TPC
public struct AnimParam // TypeDefIndex: 7
{
\tpublic string Name; // 0x0
}

// Namespace: TPS.Core.Utils
public struct AnimParam // TypeDefIndex: 8
{
\tpublic int Hash; // 0x0
}
"""


class TestDumpCsParser:
    def test_kind_base_namespace_captured(self, uu, tmp_path):
        idx = _write_dump(uu, tmp_path, DUMP_FULL)
        e = idx.types["TPC.WidgetLiteDefinition"]
        assert e["kind"] == "class"
        assert e["base"] == "LiteBase"
        assert e["namespace"] == "TPC"
        loc = idx.types["TPS.Core.Localisation.LocalisedString"]
        assert loc["kind"] == "struct"

    def test_attribute_flags_attach_to_members(self, uu, tmp_path):
        idx = _write_dump(uu, tmp_path, DUMP_FULL)
        members = {n: m for n, t, o, m in
                   idx.types["TPC.WidgetLiteDefinition"]["members"]}
        loc = idx.types["TPS.Core.Localisation.LocalisedString"]
        lm = {n: m for n, t, o, m in loc["members"]}
        assert "serializeField" in lm["_dev"].split()
        # static field keeps its modifiers verbatim in `members`
        assert "static" in idx.types[
            "TPS.Core.Localisation.LocalisedString"]["members"][2][3]

    def test_generic_params_captured(self, uu, tmp_path):
        text = DUMP_FULL + """
// Namespace: TPC
public class AssetReferenceT<T> // TypeDefIndex: 9
{
\tprotected internal string m_AssetGUID; // 0x10
}
"""
        idx = _write_dump(uu, tmp_path, text)
        assert idx.types["TPC.AssetReferenceT"]["generic_params"] == ["T"]


class TestResolveLadder:
    def test_exact_then_assembly_then_suffix(self, uu, tmp_path):
        idx = _write_dump(uu, tmp_path, DUMP_FULL)
        assert idx.resolve("TPC.WidgetLiteDefinition") == \
            "TPC.WidgetLiteDefinition"
        assert idx.resolve("TPC.WidgetLiteDefinition, Assembly-CSharp") == \
            "TPC.WidgetLiteDefinition"
        # unqualified spelling unique across the whole index
        assert idx.resolve("LocalisedString") == \
            "TPS.Core.Localisation.LocalisedString"

    def test_context_namespace_breaks_ties(self, uu, tmp_path):
        idx = _write_dump(uu, tmp_path, DUMP_AMBIG)
        # two AnimParam candidates; the referencing class lives in TPC
        assert idx.resolve("AnimParam", "TPC") == "TPC.AnimParam"
        assert idx.resolve("AnimParam", "TPS.Core.Utils") == \
            "TPS.Core.Utils.AnimParam"
        # no context → ambiguous → None (never a guess)
        assert idx.resolve("AnimParam") is None

    def test_unresolvable_is_none(self, uu, tmp_path):
        idx = _write_dump(uu, tmp_path, DUMP_FULL)
        assert idx.resolve("NoSuchTypeAnywhere") is None


class TestSynthesizerShapes:
    def _syn(self, uu, tmp_path, text=DUMP_FULL):
        idx = _write_dump(uu, tmp_path, text)
        return uu.TypetreeSynthesizer(idx), idx

    def _field_nodes(self, synth, cls):
        nodes = synth.monobehaviour_nodes(cls)
        return nodes

    def test_base_chain_inheritance(self, uu, tmp_path):
        synth, _ = self._syn(uu, tmp_path)
        nodes = self._field_nodes(synth, "TPC.WidgetDefinition")
        names = [n["m_Name"] for n in nodes]
        # ScriptableObject boundary contributes nothing; own fields present
        assert "Size" in names and "Lite" in names

    def test_unqualified_nested_struct_resolves(self, uu, tmp_path):
        synth, _ = self._syn(uu, tmp_path)
        nodes = self._field_nodes(synth, "TPC.WidgetLiteDefinition")
        i = next(i for i, n in enumerate(nodes) if n["m_Name"] == "Label")
        label = nodes[i]
        assert label["m_Type"] == "complex"
        # subtree = following nodes strictly deeper than the field node
        subtree = []
        for n in nodes[i + 1:]:
            if n["m_Level"] <= label["m_Level"]:
                break
            subtree.append(n)
        # LocalisedString = {_dev string, _termID int}; static excluded
        assert [(k["m_Name"], k["m_Type"]) for k in subtree] == \
            [("_dev", "string"), ("_termID", "int")]

    def test_enum_maps_to_int(self, uu, tmp_path):
        synth, _ = self._syn(uu, tmp_path)
        nodes = self._field_nodes(synth, "TPC.WidgetLiteDefinition")
        kind = next(n for n in nodes if n["m_Name"] == "Kind")
        assert kind["m_Type"] == "int"

    def test_list_becomes_vector_with_array_nesting(self, uu, tmp_path):
        synth, _ = self._syn(uu, tmp_path)
        nodes = self._field_nodes(synth, "TPC.WidgetLiteDefinition")
        i = next(i for i, n in enumerate(nodes) if n["m_Name"] == "Aliases")
        vec, arr, size, data = nodes[i], nodes[i + 1], nodes[i + 2], nodes[i + 3]
        assert vec["m_Type"] == "vector"
        assert arr["m_Type"] == "Array" and arr["m_Level"] == vec["m_Level"] + 1
        assert size["m_Name"] == "size" and size["m_Level"] == arr["m_Level"] + 1
        assert data["m_Name"] == "data" and data["m_Type"] == "string"

    def test_unserializable_members_omitted(self, uu, tmp_path):
        synth, _ = self._syn(uu, tmp_path)
        names = [n["m_Name"] for n in
                 self._field_nodes(synth, "TPC.WidgetLiteDefinition")]
        # Dictionary, Nullable and delegate fields are never serialized
        assert "Lookup" not in names
        assert "Maybe" not in names
        assert "OnDone" not in names
        # arrays serialize as vectors
        assert "Names" in names

    def test_engine_object_field_becomes_pptr(self, uu, tmp_path):
        synth, _ = self._syn(uu, tmp_path)
        nodes = self._field_nodes(synth, "TPC.WidgetLiteDefinition")
        icon = next(n for n in nodes if n["m_Name"] == "Icon")
        assert icon["m_Type"] == "PPtr<Object>"

    def test_serialize_reference_engine_object_still_pptr(self, uu, tmp_path):
        # measured R11 rule: the serializer PPtrs UnityEngine.Object-derived
        # types even when dump.cs prints [SerializeReference]
        text = DUMP_FULL + """
// Namespace: TPC
public class WeightedList : UnityEngine.ScriptableObject // TypeDefIndex: 10
{
	// Fields
	public int X; // 0x18
}

// Namespace: TPC
public class HolderDefinition : UnityEngine.ScriptableObject // TypeDefIndex: 11
{
	// Fields
	[SerializeReference] // RVA: 0xAEF70 Offset: 0xAE570 VA: 0x1800AEF70
	public WeightedList Weighted; // 0x18
}
"""
        synth, idx = self._syn(uu, tmp_path, text)
        assert idx.resolve("HolderDefinition") == "TPC.HolderDefinition"
        nodes = self._field_nodes(synth, "TPC.HolderDefinition")
        w = next(n for n in nodes if n["m_Name"] == "Weighted")
        assert w["m_Type"] == "PPtr<Object>"

    def test_serialize_reference_interface_is_id(self, uu, tmp_path):
        text = DUMP_FULL.replace(
            "\tpublic System.Action OnDone; // 0x40",
            "\tpublic IReward Reward; // 0x40").replace(
            "public class WidgetDefinition : UnityEngine.ScriptableObject",
            "public interface IReward // TypeDefIndex: 12\n{\n}\n\n"
            "public class WidgetDefinition : UnityEngine.ScriptableObject")
        synth, idx = self._syn(uu, tmp_path)
        idx.types["TPC.WidgetLiteDefinition"]["members"] = [
            ("Label", "LocalisedString", 0x18, "public"),
            ("Kind", "RoomType", 0x20, "public"),
            ("Reward", "IReward", 0x28, "public serializeReference"),
        ]
        nodes = self._field_nodes(synth, "TPC.WidgetLiteDefinition")
        i = next(i for i, n in enumerate(nodes) if n["m_Name"] == "Reward")
        rw = nodes[i]
        # game-measured shape: `managedReference` with one int `id`
        assert rw["m_Type"] == "managedReference"
        assert nodes[i + 1]["m_Name"] == "id"
        assert nodes[i + 1]["m_Type"] == "int"

    def test_align_flags_bools_strings_vectors(self, uu, tmp_path):
        synth, _ = self._syn(uu, tmp_path)
        text = DUMP_FULL.replace(
            "\tpublic string[] Names; // 0x50",
            "\tpublic string[] Names; // 0x50\n\tpublic bool Flagged; // 0x58")
        synth2, _ = self._syn(uu, tmp_path, text)
        nodes = self._field_nodes(synth2, "TPC.WidgetLiteDefinition")
        align = 0x4000
        flag = next(n for n in nodes if n["m_Name"] == "Flagged")
        assert flag["m_MetaFlag"] & align      # sub-4-byte scalar self-pads
        label = next(n for n in nodes if n["m_Name"] == "Label")
        assert label["m_MetaFlag"] & align     # complex containing a string

    def test_monobehaviour_header_and_mr_trailer(self, uu, tmp_path):
        synth, _ = self._syn(uu, tmp_path)
        nodes = self._field_nodes(synth, "TPC.WidgetDefinition")
        assert nodes[0]["m_Type"] == "MonoBehaviour"
        names = [n["m_Name"] for n in nodes]
        for header in ("m_GameObject", "m_Enabled", "m_Script", "m_Name"):
            assert header in names
        # measured managed-reference table closes every synthesized payload
        assert names[-1] == "assembly"
        reg = nodes[-7]
        assert reg["m_Type"] == "ManagedReferencesRegistry"

    def test_recursion_cycle_raises(self, uu, tmp_path):
        # a NON-engine self-reference: engine-derived field types become
        # PPtrs (no recursion), so the cycle must be a plain class
        text = """
// Namespace: TPC
public class LoopA // TypeDefIndex: 13
{
	public LoopA Self; // 0x0
}
"""
        synth, _ = self._syn(uu, tmp_path, text)
        with pytest.raises(uu.SynthesisError):
            synth.class_nodes("TPC.LoopA", 1)

    def test_root_without_serialized_fields_raises(self, uu, tmp_path):
        text = DUMP_FULL + """
// Namespace: TPC
public class EmptyDefinition : UnityEngine.ScriptableObject // TypeDefIndex: 14
{
\tprivate int hidden; // 0x18
}
"""
        synth, _ = self._syn(uu, tmp_path, text)
        with pytest.raises(uu.SynthesisError):
            synth.monobehaviour_nodes("TPC.EmptyDefinition")


class TestUnityPyRoundTrip:
    """Mechanical proof that synthesized node lists are structurally valid:
    write a payload through UnityPy's writer and read it back byte-exact."""

    def _syn(self, uu, tmp_path):
        idx = _write_dump(uu, tmp_path, DUMP_FULL)
        return uu.TypetreeSynthesizer(idx), idx

    def test_roundtrip_widget_lite(self, uu, tmp_path):
        UnityPy = pytest.importorskip("UnityPy")
        synth, _ = self._syn(uu, tmp_path)
        nodes = synth.monobehaviour_nodes("TPC.WidgetLiteDefinition")
        payload = {
            "m_GameObject": {"m_FileID": 0, "m_PathID": 0},
            "m_Enabled": True,
            "m_Script": {"m_FileID": 1, "m_PathID": -42},
            "m_Name": "w1",
            "_baseField": 5,
            "Label": {"_dev": "Hello", "_termID": -7},
            "Kind": 3,
            "Aliases": ["a", "bb"],
            "Names": ["n"],
            "Icon": {"m_FileID": 0, "m_PathID": 0},
            "_managedRefTypes": [
                {"class": "Terminus", "namespace": "UnityEngine.DMAT",
                 "assembly": "FAKE_ASM"}],
        }
        from UnityPy.helpers.TypeTreeHelper import write_typetree, read_typetree
        from UnityPy.helpers.TypeTreeNode import TypeTreeNode
        node = TypeTreeNode.from_list(nodes)
        from UnityPy.streams import EndianBinaryWriter, EndianBinaryReader
        writer = EndianBinaryWriter(endian="<")
        write_typetree(payload, node, writer, None)
        data = writer.bytes
        reader = EndianBinaryReader(data, endian="<")
        back = read_typetree(node, reader, as_dict=True, byte_size=len(data),
                             check_read=True, assetsfile=None)
        assert back["m_Name"] == "w1"
        assert back["Label"] == {"_dev": "Hello", "_termID": -7}
        assert back["Aliases"] == ["a", "bb"]
