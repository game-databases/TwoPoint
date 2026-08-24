"""Adapter to the not-yet-landed implementation (CodeWriter works in parallel).

The suite's primary surface is black-box: `run_all.py` + emitted artifacts
(see conftest.run_pack). A handful of §8 obligations are pure-function level
(parsers, classifiers, splitters) whose effect is only partially observable
in artifacts; this adapter loads those modules by their SPEC-PINNED script
names (tools/stage*_*.py, tools/build_structural.py) and resolves functions
from short candidate-name lists derived from the spec's own vocabulary.

Nothing here ever silently passes: `skip_missing` raises pytest.skip with a
reason naming every candidate tried, and each such skip is counted so the
session summary prints an IMPL-MISSING banner. When CodeWriter lands with
different internal names, these tests skip loudly until a fixer aligns —
they never fake a pass.
"""
from __future__ import annotations

import importlib.util
import sys
import threading
from pathlib import Path

PACK_ROOT = Path(__file__).resolve().parents[1]
TOOLS = PACK_ROOT / "tools"

_lock = threading.Lock()
missing_symbols: list[str] = []
missing_modules: list[str] = []


def note_missing_module(name: str) -> None:
    with _lock:
        if name not in missing_modules:
            missing_modules.append(name)


def note_missing_symbol(desc: str) -> None:
    with _lock:
        if desc not in missing_symbols:
            missing_symbols.append(desc)


def impl_present() -> bool:
    return (PACK_ROOT / "run_all.py").exists() and TOOLS.exists()


def load_tool(script_name: str):
    """Load tools/<script_name> as a module; None (recorded) when absent."""
    path = TOOLS / script_name
    if not path.exists():
        note_missing_module(f"tools/{script_name}")
        return None
    modname = "_tw_impl_" + script_name.removesuffix(".py").replace("-", "_").replace(".", "_")
    if modname in sys.modules:
        return sys.modules[modname]
    spec = importlib.util.spec_from_file_location(modname, path)
    if spec is None or spec.loader is None:
        note_missing_module(f"tools/{script_name} (unimportable)")
        return None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[modname] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception as exc:  # import-time crash counts as impl-missing too
        note_missing_module(f"tools/{script_name} (import error: {exc!r})")
        return None
    return mod


def load_any(*script_names):
    """First successfully loaded module among the given tools/ scripts."""
    for name in script_names:
        path = TOOLS / name
        if path.exists():
            mod = load_tool(name)
            if mod is not None:
                return mod
    for name in script_names:
        note_missing_module(f"tools/{name}")
    return None


def get_sym(mod, *candidates, kinds=(str,)):
    """First present attribute among candidates; records absence otherwise.

    Also probes the module's `tc` alias (the shared tools/tpc_common import)
    so stage scripts that re-export nothing still resolve their helpers.
    """
    if mod is not None:
        aliases = [mod]
        tc = getattr(mod, "tc", None)
        if tc is not None:
            aliases.append(tc)
        for scope in aliases:
            for name in candidates:
                if hasattr(scope, name):
                    return getattr(scope, name)
    desc = f"{getattr(mod, '__name__', '?')}.{candidates[0]}"
    note_missing_symbol(desc + (f" (tried: {', '.join(candidates)})" if len(candidates) > 1 else ""))
    return None


def call_text_or_path(fn, text, suffix=".txt", tmp_path=None):
    """Invoke fn(text); on TypeError retry fn(path) with text spilled to disk."""
    try:
        return fn(text)
    except TypeError:
        pass
    if tmp_path is None:
        raise
    p = Path(tmp_path) / ("impl_call" + suffix)
    p.write_text(text, encoding="utf-8", newline="\n")
    return fn(p)


# --- per-script symbol vocabularies ------------------------------------------
# Ordered: implementation-actual names first (tools/ landed 2026-08-24), then
# spec-vocabulary-derived alternates so the adapter survives refactors.

ACF_PARSER_NAMES = ("parse_acf", "parse_appmanifest_acf", "parse_manifest_acf",
                    "read_appmanifest", "parse_appmanifest")
METADATA_READER_NAMES = ("read_metadata_header", "parse_metadata_header",
                         "read_metadata_header_bytes", "metadata_header",
                         "read_il2cpp_metadata_header")
SCENE_FLAG_NAMES = ("scene_flag_for", "classify_scene_flag", "scene_flag",
                    "classify_scene", "scene_flag_for_bundle")
LOCALE_TABLE_NAMES = ("LOCALE_SUFFIX_TABLE", "LOCALE_SUFFIX_TO_BCP47",
                      "LOCALE_TO_BCP47", "SUFFIX_TO_LOCALE", "LOCALE_SUFFIXES",
                      "BCP47_BY_SUFFIX", "LOCALE_TABLE")
LOCALE_FN_NAMES = ("locale_for_bundle", "locale_suffix_to_bcp47",
                   "suffix_to_locale", "to_bcp47", "bcp47_for_suffix")

STRUCTURAL_RUN_NAMES = ("run", "build_structural", "main")
ASSEMBLY_INDEX_NAMES = ("build_assembly_index", "make_assembly_index",
                        "assembly_index", "build_index")
HIERARCHY_NAMES = ("_fallback_hierarchy", "_primary_hierarchy",
                   "parse_class_hierarchy", "build_class_hierarchy",
                   "parse_dump_cs_types", "parse_dumpcs", "parse_dump_cs",
                   "extract_types", "parse_types")
TYPE_COUNT_NAMES = ("count_types", "enumerate_types", "type_count",
                    "count_top_level_types")
SAMPLE_NAMES = ("sample_for_check", "sample_ids", "identifier_sample")

MATCH_KEY_NAMES = ("normalize_ref", "normalize_match_key", "normalize_reference",
                   "match_key", "normalize_key", "normalize_bundle_reference")
COVERAGE_NAMES = ("map_catalog_keys", "compute_coverage", "build_coverage",
                  "coverage_universes", "catalog_coverage")

FAMILY_NAMES = ("split_family", "family_of_bundle", "parse_family",
                "split_family_name", "bundle_family")
RECONCILE_NAMES = ("reconcile_census", "check_reconciliation", "verify_census",
                   "reconcile", "reconcile_counts")
MEDIA_COMPLETE_NAMES = ("check_media_catalogue_completeness",
                        "media_catalogue_complete", "check_carveout_completeness",
                        "carveout_completeness", "media_completeness")

POLICY_CLASSIFIER_NAMES = ("classify_composition", "classify_composition_policy",
                           "classify_base_overlay", "composition_policy")
MATRIX_BUILDER_NAMES = ("build_locale_matrix", "build_matrix", "locale_matrix",
                        "make_locale_matrix")

KIND_MAP_NAMES = ("KIND_FILES", "KIND_TO_FILE", "KIND_FILENAMES",
                  "KIND_FILE_MAP", "KIND_TO_FILENAME", "SEEDED_KINDS")
STUB_VALIDATE_NAMES = ("validate_row", "validate_stub_row", "check_stub_row",
                       "validate_stub")
JOIN_NAMES = ("build_locale_availability", "join_locale", "join_loc_keys",
              "resolve_join", "join_entity_locale", "compute_availability")


def skip_if_none(value, what: str):
    """pytest.skip LOUDLY when an impl symbol/module is absent."""
    if value is None:
        import pytest
        pytest.skip(f"impl-missing: {what} not resolvable yet (CodeWriter pending)")
    return value
