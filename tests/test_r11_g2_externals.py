"""R11 G2 — per-bundle externals tables (scout piece-02 §6 G2).

Stage 3 now emits `harvest/externals.jsonl` — one row per serialized file
carrying its Unity externals list (m_FileID → path/guid/type) — plus an
additive `_sourceFile` marker on each MonoBehaviour dump payload. These
tests pin the sidecar shape, the additive-only dump contract (the new
underscore keys never reach stub fields or payload hashes), and the
1-based fileId semantics cross-file PPtr resolution depends on.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from _impl import load_tool  # noqa: E402


@pytest.fixture(scope="module")
def s3():
    mod = load_tool("stage3_harvest_bundles.py")
    if mod is None:
        pytest.skip("impl-missing: tools/stage3_harvest_bundles.py not loadable")
    return mod


@pytest.fixture(scope="module")
def s5():
    mod = load_tool("stage5_emit_stubs.py")
    if mod is None:
        pytest.skip("impl-missing: tools/stage5_emit_stubs.py not loadable")
    return mod


class _FakeExternal:
    def __init__(self, path, guid=b"\x01\x02", ext_type=0):
        self.path = path
        self.guid = guid
        self.type = ext_type


class TestExternalsRows:
    def test_row_shape_and_1_based_fileids(self, s3):
        row = s3.externals_row(
            "TPC_Data/StreamingAssets/aa/StandaloneWindows64/configs_assets_all.bundle",
            "cab-abc123",
            [_FakeExternal("archive:/CAB-a/CAB-a"),
             _FakeExternal("archive:/CAB-b/CAB-b",
                           guid=bytes(range(16)), ext_type=0)])
        assert row["bundle"].endswith("configs_assets_all.bundle")
        assert row["sourceFile"] == "cab-abc123"
        exts = row["externals"]
        assert [e["fileId"] for e in exts] == [1, 2]
        assert exts[0]["path"] == "archive:/CAB-a/CAB-a"
        assert exts[0]["guid"] is None or isinstance(exts[0]["guid"], str)
        assert exts[1]["guid"] == bytes(range(16)).hex()
        assert all(isinstance(e["type"], int) for e in exts)

    def test_empty_externals_list_keeps_file_mapping(self, s3):
        # a serialized file with no externals still gets its row so the
        # (bundle, sourceFile) index stays complete for consumers
        row = s3.externals_row("b.bundle", "cab-x", [])
        assert row == {"bundle": "b.bundle", "sourceFile": "cab-x",
                       "externals": []}

    def test_none_externals_tolerated(self, s3):
        row = s3.externals_row("b.bundle", "cab-x", None)
        assert row["externals"] == []

    def test_m_FileID_resolves_through_row(self, s3):
        # the consumer contract: a PPtr {m_FileID: k} names externals[k-1]
        exts = [_FakeExternal(f"archive:/CAB-{i}/CAB-{i}") for i in range(3)]
        row = s3.externals_row("b.bundle", "cab-y", exts)
        k = 2
        assert row["externals"][k - 1]["path"] == "archive:/CAB-1/CAB-1"


class TestAdditiveOnlyDumpContract:
    PAYLOAD = {"m_Name": "thing", "_id": 7,
               "_scriptClass": "TPC.WidgetDefinition",
               "_decoded": {"typetreeDecoded": True},
               "_sourceFile": "cab-zz"}

    def test_source_file_never_enters_stub_fields(self, s5):
        fields = s5.payload_fields(self.PAYLOAD)
        # payload_fields exposes the raw block; stage-5's emission filter
        # is the underscore-prefix comprehension in run() — the same plane
        # payload_hash reads — so the marker can never reach a stub row
        assert "_sourceFile" in fields
        raw_fields = {k: v for k, v in fields.items()
                      if not str(k).startswith("_")}
        assert set(raw_fields) == {"m_Name"}   # even "_id" is bookkeeping

    def test_source_file_does_not_change_payload_hash(self, s5):
        base = {"m_Name": "thing", "_id": 7}
        with_marker = dict(base, _sourceFile="cab-zz",
                           _managedRefTypes=[["Terminus",
                                              "UnityEngine.DMAT",
                                              "FAKE_ASM"]])
        assert s5.payload_hash(base) == s5.payload_hash(with_marker)

    def test_stub_row_fields_exclude_all_underscore_keys(self, s5):
        payload = {"m_ID": "x", "m_Name": "n", "_sourceFile": "cab",
                   "_managedRefTypes": [["c", "ns", "asm"]]}
        raw_fields = {k: v for k, v in s5.payload_fields(payload).items()
                      if not str(k).startswith("_")}
        assert raw_fields == {"m_ID": "x", "m_Name": "n"}
