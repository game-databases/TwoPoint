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

# Revision 4: the stage-1 gate is multi-image (non-empty DummyDll set covering
# every ScriptingAssemblies entry, ≥1 backed dummy-present; Assembly-CSharp.dll
# NOT required).
MULTI_IMAGE_GATE_NAMES = ("_multi_image_gate", "multi_image_gate",
                          "evaluate_dummydll_gate", "check_dummydll_gate",
                          "dummydll_gate", "evaluate_gate")
TEXTASSET_DECODE_NAMES = ("_decode_catalog_textasset", "decode_catalog_textasset",
                          "find_catalog_textasset", "decode_textasset_catalog")
SECONDARY_PROBE_NAMES = ("_find_catalog_monobehaviour", "find_catalog_monobehaviour",
                         "_find_catalog_object")
FALLBACK_SEED_NAMES = ("seed_fallback_unity_version", "ensure_fallback_unity_version",
                       "seed_fallback_version", "apply_fallback_version_seed",
                       "seed_unitypy_fallback", "prepare_bundle_open",
                       "open_bundle_with_fallback", "resolve_bundle_version")

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

# piece-02 relink stage (spec §3 pins tools/stage6_relink.py + relink_util.py).
# Ordered: plausible implementation names first, spec-vocabulary alternates after.
RELINK_WALKER_NAMES = ("walk_pptr_refs", "iter_pptr_refs", "find_pptr_leaves",
                       "collect_pptr_refs", "pptr_leaves", "walk_pptrs")
CAB_INDEX_NAMES = ("build_cab_index", "cab_index_rows", "bridge_cab_index",
                   "emit_cab_index", "index_cabs")
CONTAINER_INDEX_NAMES = ("build_container_index", "container_index_rows",
                         "bridge_container_index", "emit_container_index")
STUB_INDEX_NAMES = ("build_stub_index", "load_stub_index", "stub_index",
                    "index_stubs")
CROSSFILE_RESOLVER_NAMES = ("resolve_cross_file", "resolve_pptr_cross_file",
                            "resolve_external_ref", "cross_file_resolver",
                            "resolve_ext_ref")
UNRESOLVED_ATTRIBUTION_NAMES = ("attribute_unresolved_residue",
                                "attribute_unresolved",
                                "classify_unresolved_residue",
                                "unresolved_residue_charges")
GUID_BRIDGE_NAMES = ("run_guid_bridge", "bridge_guids", "guid_bridge",
                     "resolve_asset_guid_refs", "build_guid_bridge")
REGISTRY_BUILDER_NAMES = ("build_i2_term_registry", "build_term_registry",
                          "i2_term_registry_rows", "build_registry")
ENTITY_LOCALE_NAMES = ("emit_entity_locale", "entity_locale_rows",
                       "build_entity_locale", "localised_instances",
                       "walk_localised_strings")
REVERSE_INDEX_NAMES = ("build_locale_term_entity", "locale_term_entity_rows",
                       "reverse_locale_index", "build_reverse_index")
JOIN_REPORT_NAMES = ("build_locale_join_report", "locale_join_report",
                     "join_report_counts")
COVERAGE_VALIDATE_NAMES = ("validate_ui_link_coverage", "coverage_violations",
                           "check_ui_link_coverage", "validate_coverage_map")
TOOLTIP_CENSUS_NAMES = ("tooltip_target_census", "enumerate_tooltip_targets",
                        "tooltip_targets", "tooltip_target_classes")
DISCOVERY_FLOOR_NAMES = ("discover_ui_classes", "ui_class_discovery",
                         "menu_ui_inspector_classes", "discovery_floor_classes")
COMPETITOR_APPLY_NAMES = ("apply_competitor_model", "apply_model",
                          "map_competitor_rows", "competitor_dispositions")
FLOOR_GATE_NAMES = ("floor_met", "competitor_floor_met", "evaluate_floor",
                    "floor_status")
MATRIX_ASSEMBLER_NAMES = ("assemble_matrix", "build_relation_matrix",
                          "matrix_from_datasets", "build_matrix")
RELATIONS_GEN_NAMES = ("render_relations_md", "generate_relations_md",
                       "build_relations_md", "relations_markdown",
                       "write_relations_md")
STAGE6_SCRIPTS = ("stage6_relink.py", "relink_util.py")


def skip_if_none(value, what: str):
    """pytest.skip LOUDLY when an impl symbol/module is absent."""
    if value is None:
        import pytest
        pytest.skip(f"impl-missing: {what} not resolvable yet (CodeWriter pending)")
    return value


def try_call_shapes(fn, *shapes):
    """Call an impl function whose exact signature is unknown: each shape is
    (args, kwargs); the first non-TypeError result wins. Raises AssertionError
    naming every tried shape when none matches."""
    last = None
    for args, kw in shapes:
        try:
            return fn(*args, **kw)
        except TypeError as exc:
            last = exc
    name = getattr(fn, "__name__", repr(fn))
    raise AssertionError(
        f"{name} matched none of its expected call shapes "
        f"({len(shapes)} tried); last TypeError: {last}")
