#!/usr/bin/env python3
"""Stage 4 — localisation.

All 14 locale bundles → per-locale string tables keyed by stable ids; the
unnamed base bundle is decoded AND persisted verbatim
(`locales/base-overlay.jsonl`); base-overlay composition is classified HERE
into the emitted `compositionPolicy` enum (arbiter-001 R2).

Locale bundles are content bundles: their UnityFS headers read `0.0.0` too,
so opens run under the SAME identity-sourced fallback-version seeding as
stage 3 (Revision 4), with the usage total recorded in the run section.

Revision 5 (measured client reality): the locale bundles are I2 Localization
sources, not flat string tables — the generic pair-walking decoder extracted
0 rows from them. Two storage shapes ship on this client, and both decode
here:
  • the unnamed BASE overlay carries 26 `LanguageSource` MonoBehaviours
    (embedded typetrees; dump.cs synthesis as fallback) — an I2 MASTER
    REGISTRY: 15k+ terms with `{ID, Term, TermType, TermStatus, Description,
    Languages[], Flags}` and a 13-row `mLanguages`; text lookup is per-term
    `Languages[i]` indexed by that source's own `mLanguages` order;
  • each of the 13 named locale bundles carries `I2LS_<Category>` TextAssets
    in I2's category text format: entries joined by `[i2t]`, each entry
    `Term=text` (first `=` splits; no newlines).
Per term the emitted row keeps the game's localization key VERBATIM as `id`
(doctrine Principle one) — the same key space the TextAsset spellings use,
so every decoded table joins. Cells absent/untranslated (empty matched
cell, or none at the matched index) are SKIPPED in locale tables and
COUNTED; the base overlay is the registry itself, so its rows persist under
the same `{id, text}` contract with the pivot cell verbatim (mostly empty on
this client — the registry holds keys+statuses, translations live in the
locale bundles). TermStatus distributions are reported as evidence counts.

Stage 5 is the SOLE OWNER of `relinks/locale_availability.jsonl`; this stage
never writes under relinks/ (R3).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import log_util
import tpc_common as tc
import unitypy_util as uu
from unitypy_util import seed_fallback_unity_version  # noqa: F401  (R4 shared stage-3+4 seeding seam, re-exported)

I2_CATEGORY_PREFIX = "i2ls_"          # TextAsset name prefix, case-insensitive
I2_ENTRY_SEPARATOR = "[i2t]"          # joins entries inside one category asset
PIVOT_MATCH_CODES = ("en",)           # base-overlay matched language (pivot)
_PIVOT_NAME_FALLBACK = "english"
# BCP-47 → the I2 `mLanguages` Code/Name spellings this client uses for it
# (measured: zh-CN / zh-TW / pt-BR rows); first hit wins, case-insensitive.
_I2_CODE_ALIASES = {
    "zh-Hans": ("zh-cn", "zh-hans"),
    "zh-Hant": ("zh-tw", "zh-hant"),
    "pt-BR": ("pt-br", "brazilian portuguese", "portuguese (brazil)"),
}

# TermStatus enum (dump.cs, I2.Loc): measured values reported verbatim.
TERM_STATUS_NOT_FOR_TRANSLATION = 0
TERM_STATUS_FOR_TRANSLATION = 1


def _evidence() -> dict:
    return {
        "languageSources": 0,
        "categoriesDecoded": 0,
        "termsWalked": 0,
        "rowsEmitted": 0,
        "cellsSkippedEmpty": 0,
        "cellsSkippedAbsent": 0,
        "malformedEntries": 0,
        "duplicateKeysOverwritten": 0,
        "ignoredTextAssets": 0,
    }


def _match_language_index(m_languages: list, wanted_codes) -> int | None:
    """Index into a source's mLanguages whose Code (then Name) matches one of
    the wanted spellings, case-insensitively. None when no row matches."""
    codes, names = [], []
    for row in m_languages or []:
        if not isinstance(row, dict):
            continue
        codes.append(str(row.get("Code") or "").casefold())
        names.append(str(row.get("Name") or "").casefold())
    for wanted in wanted_codes:
        w = str(wanted).casefold()
        if w in codes:
            return codes.index(w)
    for wanted in wanted_codes:
        w = str(wanted).casefold()
        if w in names:
            return names.index(w)
    return None


def _wanted_codes_for(locale: str | None) -> tuple[str, ...]:
    """Spellings that identify THIS table's language inside a source's
    mLanguages: the pivot for the base overlay, else the bundle's BCP-47 code
    plus its measured I2 aliases."""
    if locale is None:
        return PIVOT_MATCH_CODES + (_PIVOT_NAME_FALLBACK,)
    aliases = [locale] + list(_I2_CODE_ALIASES.get(locale, ()))
    if locale == "en":
        aliases.append(_PIVOT_NAME_FALLBACK)
    return tuple(aliases)


def decode_i2_language_source(payload: dict, wanted_codes, rows: dict,
                              evidence: dict, status_by_key: dict | None,
                              status_hist: dict | None,
                              drop_empty_cells: bool = True) -> bool:
    """One LanguageSource payload → `{id: text}` rows merged into `rows`.

    Returns True when the payload IS an I2 source (mTerms + mLanguages at top
    level or under mSource). Text lookup is per-term `Languages[i]`, i indexed
    by THIS source's mLanguages order matched against `wanted_codes`. Cells
    absent/untranslated are counted; with `drop_empty_cells=True` (locale
    tables) they emit nothing, with False (the master-registry caller) the
    `{id, text}` row persists with an empty cell verbatim. Term keys persist
    verbatim. When `status_by_key` is given, TermStatus per key is recorded
    there (base-registry evidence)."""
    src = payload.get("mSource") if isinstance(payload.get("mSource"), dict) \
        else payload
    if not isinstance(src, dict):
        return False
    m_terms = src.get("mTerms")
    m_languages = src.get("mLanguages")
    if not isinstance(m_terms, list) or not isinstance(m_languages, list):
        return False

    idx = _match_language_index(m_languages, wanted_codes)
    evidence["languageSources"] += 1
    for term in m_terms:
        if not isinstance(term, dict):
            evidence["malformedEntries"] += 1
            continue
        key = term.get("Term")
        if not isinstance(key, str) or not key:
            evidence["malformedEntries"] += 1
            continue
        evidence["termsWalked"] += 1
        status = term.get("TermStatus")
        if isinstance(status, int) and status_hist is not None:
            status_hist[status] = status_hist.get(status, 0) + 1
        if status_by_key is not None and key not in status_by_key \
                and isinstance(status, int):
            status_by_key[key] = status
        cells = term.get("Languages")
        text = None
        if not isinstance(cells, list) or idx is None or idx >= len(cells):
            evidence["cellsSkippedAbsent"] += 1
        else:
            cell = cells[idx]
            if isinstance(cell, str) and cell.strip():
                text = cell
            else:
                evidence["cellsSkippedEmpty"] += 1
        if text is None and drop_empty_cells:
            continue   # untranslated/absent cell — counted, never invented
        if key in rows:
            evidence["duplicateKeysOverwritten"] += 1   # a real overwrite below
        rows[key] = text or ""
        evidence["rowsEmitted"] += 1
    return True


def decode_i2_category_textasset(name: str, raw: bytes, rows: dict,
                                 evidence: dict) -> bool:
    """`I2LS_<Category>` TextAsset → `{id: text}` rows (entries joined by
    `[i2t]`, each `Term=text`). Returns True when the asset was treated as an
    I2 category payload (the caller counts non-category assets)."""
    if not name.lower().startswith(I2_CATEGORY_PREFIX):
        return False
    text = bytes(raw).decode("utf-8-sig", errors="replace") if raw else ""
    if not text:
        return True
    evidence["categoriesDecoded"] += 1
    for chunk in text.split(I2_ENTRY_SEPARATOR):
        if not chunk:
            continue
        if "=" not in chunk:
            evidence["malformedEntries"] += 1
            continue
        key, value = chunk.split("=", 1)
        if not value.strip():
            evidence["cellsSkippedEmpty"] += 1   # untranslated cell — skip
            continue
        if key in rows:
            evidence["duplicateKeysOverwritten"] += 1
        rows[key] = value
        evidence["rowsEmitted"] += 1
    return True


def decode_locale_bundle(abspath: Path, synth, wanted_codes,
                         keep_empty_rows: bool = False,
                         status_by_key: dict | None = None,
                         status_hist: dict | None = None
                         ) -> tuple[dict[str, str], dict]:
    """Decode ONE locale bundle into ({id: text}, evidence).

    Walks every object: I2 category TextAssets through the `[i2t]` grammar,
    LanguageSource MonoBehaviours through typetree (embedded preferred,
    dump.cs synthesis as fallback). `keep_empty_rows=True` marks the master-
    registry caller: matched-but-empty cells persist as "" rows instead of
    being dropped (they stay counted either way)."""
    UnityPy, _src = uu.ensure_unitypy()
    env = UnityPy.load(str(abspath))
    rows: dict[str, str] = {}
    evidence = _evidence()
    drop_empty = not keep_empty_rows
    for f in uu.iter_environment_files(env):
        for obj in uu.iter_objects_sorted(f):
            cls_name = getattr(getattr(obj, "type", None), "name", "")
            try:
                if cls_name == "TextAsset":
                    asset = obj.read()
                    name = getattr(asset, "m_Name", "") or ""
                    raw = getattr(asset, "m_Script", "")
                    if isinstance(raw, str):
                        raw = raw.encode("utf-8", "surrogatepass")
                    if not decode_i2_category_textasset(
                            name, bytes(raw), rows, evidence):
                        evidence["ignoredTextAssets"] += 1
                    continue
                if cls_name != "MonoBehaviour":
                    continue
                payload = _mono_payload(obj, f, synth)
                if payload is None:
                    continue
                decode_i2_language_source(
                    payload, wanted_codes, rows, evidence,
                    status_by_key, status_hist,
                    drop_empty_cells=drop_empty)
            except Exception:  # noqa: BLE001 — a bad object must not kill the table
                evidence["malformedEntries"] += 1
    return rows, evidence


def _mono_payload(obj, assets_file, synth) -> dict | None:
    """MonoBehaviour payload via embedded typetree first, then the staged
    dummy-DLL synthesis restricted to I2 LanguageSource spellings."""
    try:
        data = obj.read_typetree(wrap=False, check_read=False)
    except Exception:  # noqa: BLE001
        data = None
    if isinstance(data, dict) and _looks_like_i2_source(data):
        return data
    if synth is None:
        return None
    candidates: list[str] = []
    cls = _mono_script_class(obj, assets_file)
    for cand in (cls, "I2.Loc.LanguageSourceAsset",
                 "I2.Loc.LanguageSource"):
        if cand and cand not in candidates:
            candidates.append(cand)
    for cand in candidates:
        try:
            nodes = synth.monobehaviour_nodes(cand)
            data = obj.read_typetree(nodes=nodes, wrap=False, check_read=True)
        except Exception:  # noqa: BLE001 — try next spelling / give up
            continue
        if isinstance(data, dict) and _looks_like_i2_source(data):
            return data
    return None


def _mono_script_class(obj, assets_file) -> str | None:
    """Namespace-qualified MonoScript class name behind this MonoBehaviour."""
    try:
        mb = obj.read()
        pptr = getattr(mb, "m_Script", None)
        ms = assets_file.objects.get(getattr(pptr, "path_id", None)) \
            if pptr else None
        ns = getattr(ms, "m_Namespace", "") if ms else ""
        cn = getattr(ms, "m_ClassName", "") if ms else ""
        full = f"{ns}.{cn}" if ns and cn else cn
        return full or None
    except Exception:  # noqa: BLE001
        return None


def _looks_like_i2_source(payload: dict) -> bool:
    src = payload.get("mSource") if isinstance(payload.get("mSource"), dict) \
        else payload
    return isinstance(src, dict) and isinstance(src.get("mTerms"), list) \
        and isinstance(src.get("mLanguages"), list)


def classify_composition(base_rows: dict[str, str], english_rows: dict[str, str]) -> dict:
    """EMITTED ENUM (arbiter-001 R2): compositionPolicy selected by this
    deterministic classifier from observed evidence — consumers read the
    field, never prose."""
    base_keys, en_keys = set(base_rows), set(english_rows)
    shared = base_keys & en_keys
    identical = sum(1 for k in shared if base_rows[k] == english_rows[k])
    differing = len(shared) - identical
    base_only = len(base_keys - en_keys)
    en_only = len(en_keys - base_keys)

    # deterministic classification ladder: both sides unique → mixed;
    # any differing shared text → mixed; else the extending side names the
    # policy; identical key sets → base is redundant with english.
    if (base_only > 0 and en_only > 0) or differing > 0:
        policy = "mixed"
    elif base_only > 0:
        policy = "base-over-english"
    elif en_only > 0:
        policy = "english-over-base"
    else:
        policy = "english-only"
    evidence = {
        "baseRowCount": len(base_rows),
        "englishRowCount": len(english_rows),
        "sharedKeys": len(shared),
        "identicalTextSharedKeys": identical,
        "differingTextSharedKeys": differing,
        "baseOnlyKeys": base_only,
        "englishOnlyKeys": en_only,
    }
    return {"compositionPolicy": policy, "evidence": evidence}


def _table_keys(rows) -> list:
    """Key universe of one decoded table: {key: text} dicts contribute their
    keys; [{id,text}] row lists their ids."""
    if isinstance(rows, dict):
        return list(rows.keys())
    keys = []
    for row in rows or []:
        if isinstance(row, dict):
            kid = row.get("id", row.get("key"))
            if isinstance(kid, (str, int)) and not isinstance(kid, bool):
                keys.append(kid)
    return keys


def build_locale_matrix(tables: dict) -> dict[str, dict]:
    """Key universe for locale-matrix.json: per key, the locales whose tables
    contain it PLUS the base-overlay mark. Labels outside EMITTED_LOCALES are
    the base overlay — they mark keys but never grant a locale."""
    matrix_keys: dict[str, dict] = {}
    for locale in tc.EMITTED_LOCALES:
        for key in _table_keys(tables.get(locale)):
            entry = matrix_keys.setdefault(key,
                                           {"locales": [], "baseOverlay": False})
            if locale not in entry["locales"]:
                entry["locales"].append(locale)
    for label, rows in tables.items():
        if label in tc.EMITTED_LOCALES:
            continue
        for key in _table_keys(rows):
            entry = matrix_keys.setdefault(key,
                                           {"locales": [], "baseOverlay": False})
            entry["baseOverlay"] = True
    for entry in matrix_keys.values():
        entry["locales"].sort()
    return matrix_keys


def run(game_root: Path, extracted_root: Path) -> int:
    paths = tc.game_paths(game_root)
    roster = tc.load_roster(extracted_root)
    locale_rows = tc.roster_locale_rows(roster)
    if len(locale_rows) != tc.EXPECTED_LOCALE_ROWS:
        print(f"[localisation] WARNING: expected "
              f"{tc.EXPECTED_LOCALE_ROWS} locale-flagged roster rows, found "
              f"{len(locale_rows)}", file=sys.stderr)

    dump_cs = extracted_root / "decompiled" / "il2cppdumper" / "dump.cs"
    index = uu.DumpCsIndex(dump_cs) if dump_cs.is_file() else None
    synth = uu.TypetreeSynthesizer(index) if index is not None else None
    UnityPy, _unitypy_source = uu.ensure_unitypy()
    seeds = uu.FallbackVersionSeeder(extracted_root, UnityPy)

    tables: dict[str, dict[str, str]] = {}   # locale code | "BASE-OVERLAY" → rows
    per_locale_evidence: dict[str, dict] = {}
    status_hist: dict[int, int] = {}         # base-registry TermStatus counts
    status_by_key: dict[str, int] = {}       # loc key → TermStatus (registry)
    warnings: list[str] = []
    seeded_count = 0
    for row in sorted(locale_rows, key=lambda r: r["relpath"]):
        abspath = paths["root"] / row["relpath"]
        flag = row["localeFlag"]
        locale = None if flag == tc.BASE_OVERLAY_NAME else flag
        label = locale or "BASE-OVERLAY"
        if locale == "base":
            label = "BASE-OVERLAY"
        elif locale is not None and locale not in tc.EMITTED_LOCALES:
            warnings.append(f"unmapped locale flag '{flag}' on "
                            f"{row['relpath']} — skipped")
            continue
        keep_empty = label == "BASE-OVERLAY"   # master registry persists rows
        try:
            if seeds.seed_if_needed(abspath, row["relpath"]):
                seeded_count += 1
            rows, evidence = decode_locale_bundle(
                abspath, synth, _wanted_codes_for(locale),
                keep_empty_rows=keep_empty,
                status_by_key=status_by_key if keep_empty else None,
                status_hist=status_hist if keep_empty else None)
        except Exception as exc:  # noqa: BLE001 — loud ledgered failure below
            raise tc.StageError(
                f"failed to decode locale bundle {row['relpath']}: "
                f"{type(exc).__name__}: {exc}") from exc
        tables[label] = rows
        per_locale_evidence[label] = evidence

    english = tables.get("en")
    if english is None:
        raise tc.StageError("no `en` pivot table decoded from the locale bundles",
                            exit_code=1)
    base_overlay = tables.get("BASE-OVERLAY")

    locales_dir = extracted_root / "locales"
    emitted = []
    for locale in tc.EMITTED_LOCALES:  # exact 13-entry BCP-47 set
        rows = tables.get(locale)
        if not rows:
            raise tc.StageError(
                f"locale '{locale}' decoded to zero rows — refusing to emit "
                "an empty table", exit_code=1)
        path = locales_dir / f"{locale}.jsonl"
        log_util.write_jsonl(path, [{"id": k, "text": rows[k]}
                                    for k in sorted(rows)])
        emitted.append(locale)

    if base_overlay is None:
        raise tc.StageError(
            "no BASE-OVERLAY table decoded — the unnamed localisation bundle "
            "(the I2 master registry) is required", exit_code=1)
    if not base_overlay:
        raise tc.StageError(
            "base overlay decoded to zero registry rows — refusing to emit "
            "an empty base-overlay.jsonl", exit_code=1)
    log_util.write_jsonl(locales_dir / "base-overlay.jsonl",
                         [{"id": k, "text": base_overlay[k]}
                          for k in sorted(base_overlay)])

    report = classify_composition(base_overlay, english)
    ev = report["evidence"]
    # Revision 5 evidence counts (all ints): registry shape + what was skipped
    base_ev = per_locale_evidence.get("BASE-OVERLAY", {})
    ev["registrySources"] = base_ev.get("languageSources", 0)
    ev["registryTerms"] = base_ev.get("termsWalked", 0)
    ev["termStatusForTranslation"] = status_hist.get(
        TERM_STATUS_FOR_TRANSLATION, 0)
    ev["termStatusNotForTranslation"] = status_hist.get(
        TERM_STATUS_NOT_FOR_TRANSLATION, 0)
    ev["baseCellsSkippedEmpty"] = base_ev.get("cellsSkippedEmpty", 0)
    ev["baseCellsSkippedAbsent"] = base_ev.get("cellsSkippedAbsent", 0)
    ev["localeRowsEmittedTotal"] = sum(
        e.get("rowsEmitted", 0) for lbl, e in per_locale_evidence.items()
        if lbl != "BASE-OVERLAY")
    ev["localeCellsSkippedEmptyTotal"] = sum(
        e.get("cellsSkippedEmpty", 0) for lbl, e in per_locale_evidence.items()
        if lbl != "BASE-OVERLAY")
    log_util.write_json(locales_dir / "base-overlay-report.json", report)

    matrix_keys = build_locale_matrix(tables)
    log_util.write_json(locales_dir / "locale-matrix.json", {
        "meta": {
            "buildId": _build_id(extracted_root),
            "locales": list(tc.EMITTED_LOCALES),
            "includesBaseKeys": True,
        },
        "keys": {k: matrix_keys[k] for k in sorted(matrix_keys)},
    })

    lines = [
        "- exitCode: 0",
        f"- emittedLocales: {emitted}",
        f"- baseOverlayRows: {len(base_overlay)} (registry sources: "
        f"{ev['registrySources']}, terms walked: {ev['registryTerms']}); "
        f"englishRows: {report['evidence']['englishRowCount']}",
        f"- compositionPolicy: {report['compositionPolicy']} "
        f"(evidence: {report['evidence']})",
        f"- matrixKeys: {len(matrix_keys)}",
        f"- {seeds.run_section_note(len(locale_rows))}",
        "- relinksWrittenHere: false (stage 5 is sole owner)",
    ]
    # per-locale evidence lines, incl. TermStatus distribution joined against
    # the base registry (statuses live ONLY in the registry on this client)
    for label in sorted(per_locale_evidence):
        e = per_locale_evidence[label]
        line = (f"- {label}: rows={e.get('rowsEmitted', 0)} "
                f"skippedEmpty={e.get('cellsSkippedEmpty', 0)} "
                f"skippedAbsent={e.get('cellsSkippedAbsent', 0)} "
                f"categories={e.get('categoriesDecoded', 0)} "
                f"sources={e.get('languageSources', 0)} "
                f"malformed={e.get('malformedEntries', 0)}")
        if label != "BASE-OVERLAY":
            dist = _status_distribution(tables[label], status_by_key)
            line += f" termStatus={dist}"
        lines.append(line)
    lines += [f"- WARNING: {w}" for w in warnings]
    log_util.append_run_section(extracted_root, "localisation", lines)
    print(f"[localisation] locales={len(emitted)} baseOverlay="
          f"{len(base_overlay)} policy={report['compositionPolicy']} "
          f"matrixKeys={len(matrix_keys)} "
          f"fallbackVersioned={seeded_count}")
    for w in warnings:
        print(f"[localisation] WARNING: {w}", file=sys.stderr)
    return 0


def _status_distribution(rows: dict[str, str],
                         status_by_key: dict[str, int]) -> dict[str, int]:
    """TermStatus distribution of ONE locale's rows, joined against the base
    registry's per-key statuses (observed evidence counts, never inferred)."""
    dist = {"forTranslation": 0, "notForTranslation": 0, "unregistered": 0}
    for key in rows:
        st = status_by_key.get(key)
        if st == TERM_STATUS_FOR_TRANSLATION:
            dist["forTranslation"] += 1
        elif st == TERM_STATUS_NOT_FOR_TRANSLATION:
            dist["notForTranslation"] += 1
        else:
            dist["unregistered"] += 1
    return dist


def _build_id(extracted_root: Path):
    identity_path = extracted_root / "identity.json"
    if identity_path.is_file():
        try:
            return json.loads(identity_path.read_text(encoding="utf-8")).get("buildId")
        except ValueError:
            return None
    return None


def main(argv=None) -> int:
    log_util.bootstrap_console()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("game_dir", nargs="?", default=None)
    parser.add_argument("--extracted-root", default=None)
    args = parser.parse_args(argv)
    root = None
    try:
        pack_dir = tc.resolve_pack_dir()
        root = tc.resolve_extracted_root(pack_dir)
        if args.extracted_root:
            root = Path(args.extracted_root).resolve()
        game_root = tc.resolve_game_root(args.game_dir)
        return run(game_root, root)
    except tc.StageError as exc:
        log_util.append_failure_section(root, "localisation", exc.exit_code,
                                        [str(exc)])
        print(f"[localisation] ERROR: {exc}", file=sys.stderr)
        return exc.exit_code


if __name__ == "__main__":
    sys.exit(main())
