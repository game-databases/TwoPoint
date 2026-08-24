#!/usr/bin/env python3
"""Stage 4 — localisation.

All 14 locale bundles → per-locale string tables keyed by stable ids; the
unnamed base bundle is decoded AND persisted verbatim
(`locales/base-overlay.jsonl`); base-overlay composition is classified HERE
into the emitted `compositionPolicy` enum (arbiter-001 R2).

Locale bundles are content bundles: their UnityFS headers read `0.0.0` too,
so opens run under the SAME identity-sourced fallback-version seeding as
stage 3 (Revision 4), with the usage total recorded in the run section.

Stage 5 is the SOLE OWNER of `relinks/locale_availability.jsonl`; this stage
never writes under relinks/ (R3).
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import log_util
import tpc_common as tc
import unitypy_util as uu


def _walk_string_pairs(node, out: dict, depth=0):
    """Collect plausible (loc-id → text) pairs from any decoded tree."""
    if depth > 8:
        return
    if isinstance(node, dict):
        vals = {k: v for k, v in node.items() if isinstance(k, str)}
        low = {k.lower(): v for k, v in vals.items()}
        # Unity Localization shapes: {m_Id, m_Key} / {m_Id, m_Localized}
        for id_k in ("m_id", "m_key_id", "key"):
            for txt_k in ("m_localized", "m_value", "value", "text"):
                if id_k in low and txt_k in low \
                        and isinstance(low[txt_k], str) and isinstance(low[id_k], (str, int)):
                    kid = low[id_k]
                    out[str(kid)] = low[txt_k]
        for v in node.values():
            _walk_string_pairs(v, out, depth + 1)
    elif isinstance(node, list):
        for item in node:
            _walk_string_pairs(item, out, depth + 1)


def _shared_keys_map(node, out: dict, depth=0):
    """SharedTableData shape: lists of {m_Id: int, m_Key: str}."""
    if depth > 8:
        return
    if isinstance(node, dict):
        low = {k.lower(): v for k, v in node.items()
               if isinstance(k, str)}
        if "m_id" in low and "m_key" in low and isinstance(low["m_key"], str):
            out[low["m_id"]] = low["m_key"]
        for v in node.values():
            _shared_keys_map(v, out, depth + 1)
    elif isinstance(node, list):
        for item in node:
            _shared_keys_map(item, out, depth + 1)


def _textasset_pairs(raw: bytes) -> dict:
    """TextAsset payloads: CSV (Unity Localization export) or JSON dict.
    JSON rows carrying {m_Id, m_Key} registries join numeric ids to keys."""
    text = raw.decode("utf-8-sig", errors="replace")
    pairs: dict[str, str] = {}
    stripped = text.lstrip()
    if stripped.startswith(("{", "[")):
        try:
            data = json.loads(text)
        except ValueError:
            return {}
        shared: dict[int, str] = {}
        _shared_keys_map(data, shared)
        fresh: dict[str, str] = {}
        _walk_string_pairs(data, fresh)
        for kid, val in fresh.items():
            if kid.isdigit() and int(kid) in shared and shared[int(kid)]:
                pairs[shared[int(kid)]] = val
            else:
                pairs[kid] = val
        return pairs
    header = text.splitlines()[0] if text.splitlines() else ""
    if "," not in header:
        return {}
    try:
        reader = csv.DictReader(io.StringIO(text))
        cols = {c.lower(): c for c in (reader.fieldnames or [])}
        key_col = next((cols[c] for c in ("key", "m_key", "id") if c in cols), None)
        val_col = next((cols[c] for c in tuple(cols) if c not in ("key", "m_key", "id")),
                       None)
        if key_col is None or val_col is None:
            return {}
        for row in reader:
            kid = row.get(key_col)
            val = row.get(val_col)
            if kid and isinstance(val, str):
                pairs[kid] = val
    except csv.Error:
        return {}
    return pairs


def decode_locale_bundle(abspath: Path, synth) -> dict[str, str]:
    UnityPy, _src = uu.ensure_unitypy()
    env = UnityPy.load(str(abspath))
    shared: dict[int, str] = {}       # SharedTableData: numeric id → loc key
    direct: dict[str, str] = {}       # string-keyed rows, verbatim
    numeric: dict[int, str] = {}      # StringTable rows keyed by numeric id
    for f in uu.iter_environment_files(env):
        for obj in uu.iter_objects_sorted(f):
            cls_name = getattr(getattr(obj, "type", None), "name", "")
            try:
                if cls_name == "TextAsset":
                    asset = obj.read()
                    raw = getattr(asset, "m_Script", "")
                    if isinstance(raw, str):
                        raw = raw.encode("utf-8")
                    direct.update(_textasset_pairs(bytes(raw)))
                elif cls_name == "MonoBehaviour":
                    cls = _mono_payload_class(obj, f)
                    if cls and synth is not None:
                        payload, _ok, _m = uu.decode_monobehaviour(obj, synth)
                    else:
                        payload = obj.read_typetree(wrap=False, check_read=False)
                    if not isinstance(payload, dict):
                        continue
                    _shared_keys_map(payload, shared)
                    fresh: dict[str, str] = {}
                    _walk_string_pairs(payload, fresh)
                    for kid, val in fresh.items():
                        if kid.isdigit():
                            numeric[int(kid)] = val  # joins through `shared`
                        else:
                            direct[kid] = val
            except Exception:  # noqa: BLE001 — a bad object must not kill the table
                continue
    resolved = dict(direct)
    for kid, val in numeric.items():   # numeric table ids → shared key registry
        if kid in shared and shared[kid]:
            resolved[shared[kid]] = val
    return resolved


def _mono_payload_class(obj, assets_file) -> str | None:
    try:
        mb = obj.read()
        pptr = getattr(mb, "m_Script", None)
        ms = assets_file.objects.get(getattr(pptr, "path_id", None)) if pptr else None
        ns = getattr(ms, "m_Namespace", "") if ms else ""
        cn = getattr(ms, "m_ClassName", "") if ms else ""
        full = f"{ns}.{cn}" if ns and cn else cn
        return full or None
    except Exception:  # noqa: BLE001
        return None


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
        try:
            if seeds.seed_if_needed(abspath, row["relpath"]):
                seeded_count += 1
            rows = decode_locale_bundle(abspath, synth)
        except Exception as exc:  # noqa: BLE001 — loud ledgered failure below
            raise tc.StageError(
                f"failed to decode locale bundle {row['relpath']}: "
                f"{type(exc).__name__}: {exc}") from exc
        tables[label] = rows

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

    base_written = False
    if base_overlay:
        log_util.write_jsonl(locales_dir / "base-overlay.jsonl",
                             [{"id": k, "text": base_overlay[k]}
                              for k in sorted(base_overlay)])
        base_written = True
    report = classify_composition(base_overlay or {}, english)
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
        f"- baseOverlayRows: {report['evidence']['baseRowCount']} "
        f"(written={base_written}); englishRows: "
        f"{report['evidence']['englishRowCount']}",
        f"- compositionPolicy: {report['compositionPolicy']} "
        f"(evidence: {report['evidence']})",
        f"- matrixKeys: {len(matrix_keys)}",
        f"- {seeds.run_section_note(len(locale_rows))}",
        "- relinksWrittenHere: false (stage 5 is sole owner)",
    ]
    lines += [f"- WARNING: {w}" for w in warnings]
    log_util.append_run_section(extracted_root, "localisation", lines)
    print(f"[localisation] locales={len(emitted)} baseOverlay="
          f"{report['evidence']['baseRowCount']} "
          f"policy={report['compositionPolicy']} matrixKeys={len(matrix_keys)} "
          f"fallbackVersioned={seeded_count}")
    for w in warnings:
        print(f"[localisation] WARNING: {w}", file=sys.stderr)
    return 0


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
