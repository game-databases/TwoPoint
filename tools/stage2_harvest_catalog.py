#!/usr/bin/env python3
"""Stage 2 — harvest-catalog.

Decodes the Addressables catalog bundle into the full key → bundle/address
index (the backbone of every later join). The OUTPUT contract is fixed
(spec §3 stage 2) regardless of decode route.

PRIMARY route (spec §3 stage 2, Revision 4 — measured client reality):
the bundle's payload is a single TextAsset named `"catalog"` holding ~11.7 MB
of JSON with `m_LocatorId` "AddressablesMainContentCatalog" plus base64
blobs `m_KeyDataString` / `m_BucketDataString` / `m_EntryDataString`; the
JSON is parsed directly and tools/aa_catalog.py decodes the three blobs.
The MonoBehaviour/typetree route is the SECONDARY/absent path, probed only
when the TextAsset is missing or malformed — never the primary.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import aa_catalog
import log_util
import tpc_common as tc
import unitypy_util as uu

_GUID_RE = re.compile(r"^[0-9a-fA-F]{32}$")
AA_CLASS_SPELLINGS = (
    "UnityEngine.AddressableAssets.ContentCatalogData",
    "ContentCatalogData",
)
CATALOG_TEXTASSET_NAMES = ("catalog",)


def classify_key(key) -> str:
    if isinstance(key, bool):
        return "integer"
    if isinstance(key, int):
        return "integer"
    if isinstance(key, str) and _GUID_RE.match(key):
        return "guid"
    return "address"


def _decode_catalog_textasset(env) -> tuple[dict | None, str]:
    """PRIMARY decode route (Revision 4): find the TextAsset named
    "catalog" (or any TextAsset whose JSON carries m_LocatorId
    "AddressablesMainContentCatalog"), parse its JSON, and decode the three
    base64 blobs via aa_catalog. Returns (decoded_model | None, note); None
    means absent-or-malformed and the caller probes the SECONDARY route —
    a malformed candidate never yields silent garbage decode."""
    reasons: list[str] = []
    for f in uu.iter_environment_files(env):
        for obj in uu.iter_objects_sorted(f):
            if getattr(obj.type, "name", "") != "TextAsset":
                continue
            name = ""
            try:
                asset = obj.read()
                name = getattr(asset, "m_Name", "") or ""
                raw = getattr(asset, "m_Script", "")
            except Exception as exc:  # noqa: BLE001 — unreadable object is not the catalog
                reasons.append(f"path_id {getattr(obj, 'path_id', '?')} "
                               f"unreadable: {type(exc).__name__}: {exc}")
                continue
            if isinstance(raw, str):
                raw = raw.encode("utf-8", "surrogatepass")
            if not isinstance(raw, (bytes, bytearray)):
                reasons.append(f"TextAsset {name!r}: payload neither str nor bytes")
                continue
            try:
                payload = json.loads(bytes(raw))
            except ValueError as exc:
                reasons.append(f"TextAsset {name!r}: not valid JSON ({exc})")
                continue
            locator = payload.get("m_LocatorId") \
                if isinstance(payload, dict) else None
            if name.lower() not in CATALOG_TEXTASSET_NAMES \
                    and locator != "AddressablesMainContentCatalog":
                continue  # unrelated TextAsset — neither candidate nor defect
            if not isinstance(payload, dict):
                reasons.append(f"TextAsset {name!r}: top-level JSON is not an object")
                continue
            try:
                decoded = aa_catalog.decode_catalog_payload(payload)
            except aa_catalog.CatalogDecodeError as exc:
                reasons.append(f"TextAsset {name!r}: blob decode failed ({exc})")
                continue
            return decoded, (f"textasset-json primary (TextAsset {name!r}, "
                             f"{len(raw)} B, m_LocatorId={locator!r})")
    return None, ("no decodable catalog TextAsset: "
                  + ("; ".join(reasons) if reasons else "none present"))


def _find_catalog_monobehaviour(env, synth):
    """SECONDARY/absent route (demoted by Revision 4): probe for a
    ContentCatalogData MonoBehaviour payload through the dump.cs-synthesized
    typetree. Reached only when the primary TextAsset route is missing or
    malformed."""
    for f in uu.iter_environment_files(env):
        objs = uu.iter_objects_sorted(f)
        for obj in objs:
            if getattr(obj.type, "name", "") != "MonoBehaviour":
                continue
            cls_name = None
            try:
                mb = obj.read()
                pptr = getattr(mb, "m_Script", None)
                if pptr is not None:
                    ms = f.objects.get(getattr(pptr, "path_id", None))
                    cls_name = getattr(ms, "m_ClassName", None) if ms else None
            except Exception:  # noqa: BLE001 — fall through to spellings
                cls_name = None
            candidates = [c for c in (cls_name,) if c] or list(AA_CLASS_SPELLINGS)
            for cand in candidates:
                if not any(cand.endswith(s) for s in ("ContentCatalogData",)):
                    continue
                try:
                    nodes = synth.monobehaviour_nodes(cand)
                except Exception:  # noqa: BLE001
                    continue
                data = obj.read_typetree(nodes=nodes, wrap=False, check_read=True)
                if "m_KeyDataString" in data or "m_InternalIds" in data:
                    return data
    raise tc.StageError(
        "catalog.bundle decoded via NEITHER route: the primary TextAsset "
        '"catalog" is absent or malformed AND no decodable '
        "ContentCatalogData MonoBehaviour exists — the secondary typetree "
        "route needs stage-1 dump.cs (decompiled/il2cppdumper/dump.cs)",
        exit_code=1)


def _bundle_reference(entry_row: dict) -> str | None:
    dep = entry_row.get("dependencyKey")
    if isinstance(dep, str) and dep.lower().endswith(".bundle"):
        return dep
    iid = entry_row.get("internalId") or ""
    if iid.lower().endswith(".bundle"):
        return iid
    return None


def map_catalog_keys(decoded: dict, norm_to_relpath: dict[str, str]) -> tuple[list[dict], set[str]]:
    """Pure mapping layer: decoded catalog model → sorted key rows +
    set of normalized references that failed to resolve into the roster."""
    keys_out: list[dict] = []
    unresolved: set[str] = set()

    def resolve(ref: str) -> str | None:
        norm = tc.normalize_ref(ref)
        rel = norm_to_relpath.get(norm)
        if rel is None:
            unresolved.add(norm)
            return None
        return rel

    for slot in decoded["keys"]:
        key = slot["key"]
        bundles: set[str] = set()
        deps: set[str] = set()
        providers: set[str] = set()
        address = None
        for entry in slot["entries"]:
            providers.add(entry["provider"].rsplit(".", 1)[-1])
            ref = _bundle_reference(entry)
            if ref is not None:
                rel = resolve(ref)
                if rel:
                    bundles.add(rel)
                continue
            # non-bundle entry → its internalId is the addressable location
            if address is None and entry.get("internalId"):
                address = entry["internalId"]
            dep_key = entry.get("dependencyKey")
            if isinstance(dep_key, str):
                rel = resolve(dep_key)
                if rel:
                    deps.add(rel)
        if len(bundles) == 1:
            bundle_out = next(iter(bundles))
        elif bundles:
            bundle_out = sorted(bundles)[0]
            deps |= bundles - {bundle_out}
        else:
            bundle_out = None
        keys_out.append({
            "key": key,
            "kind": classify_key(key),
            "bundle": bundle_out,
            "address": address,
            "dependencies": sorted(deps),
            "providerIds": sorted(providers),
        })
    keys_out.sort(key=lambda r: json.dumps(r["key"], ensure_ascii=False,
                                           sort_keys=True))
    return keys_out, unresolved


def run(game_root: Path, extracted_root: Path) -> int:
    paths = tc.game_paths(game_root)
    roster = tc.load_roster(extracted_root)

    if not paths["catalog_bundle"].is_file():
        raise tc.StageError(f"missing required input: {paths['catalog_bundle']}",
                            exit_code=3)
    if not paths["settings_json"].is_file():
        raise tc.StageError(f"missing required input: {paths['settings_json']}",
                            exit_code=3)

    build_id = None
    identity_path = extracted_root / "identity.json"
    if identity_path.is_file():
        build_id = json.loads(identity_path.read_text(encoding="utf-8")).get("buildId")

    UnityPy, unitypy_source = uu.ensure_unitypy()
    dump_cs = extracted_root / "decompiled" / "il2cppdumper" / "dump.cs"
    index = uu.DumpCsIndex(dump_cs) if dump_cs.is_file() else None
    synth = uu.TypetreeSynthesizer(index) if index is not None else None

    env = UnityPy.load(str(paths["catalog_bundle"]))
    decoded, primary_note = _decode_catalog_textasset(env)
    if decoded is not None:
        decode_route = "textasset-json(primary)"
    else:
        print(f"[harvest-catalog] primary TextAsset route unavailable "
              f"({primary_note}) — probing secondary MonoBehaviour/typetree "
              "route", file=sys.stderr)
        decoded = aa_catalog.decode_catalog_payload(
            _find_catalog_monobehaviour(env, synth))
        decode_route = "monobehaviour-typetree(secondary)"

    # roster universe normalized once
    norm_to_relpath: dict[str, str] = {}
    for row in roster:
        norm_to_relpath[tc.normalize_ref(row["relpath"])] = row["relpath"]

    keys_out, unresolved = map_catalog_keys(decoded, norm_to_relpath)

    # MATCH KEY hard gate BEFORE any output write (no partial finals):
    # every normalized reference must resolve into the roster.
    if unresolved:
        sample = ", ".join(sorted(unresolved)[:8])
        raise tc.StageError(
            f"{len(unresolved)} catalog reference(s) outside the roster "
            f"(match key = case-folded basename after prefix stripping); "
            f"first few: {sample}", exit_code=1)
    if not keys_out:
        raise tc.StageError("catalog decoded to zero keys", exit_code=1)

    referenced = {b for k in keys_out for b in ([k["bundle"]] if k["bundle"] else [])
                  + k["dependencies"]}
    unreferenced = sorted(r["relpath"] for r in roster
                          if r["relpath"] not in referenced)

    raw_settings = paths["settings_json"].read_text(encoding="utf-8")
    settings_parsed = {}
    try:
        parsed = json.loads(raw_settings)
        # client key casing drifts across builds (measured install carries
        # `m_buildTarget`; other snapshots spell it `m_BuildTarget`) —
        # resolve the pinned snapshot keys case-insensitively so the
        # machine-readable half never carries a permanent null
        by_fold = ({str(k).casefold(): v for k, v in parsed.items()}
                   if isinstance(parsed, dict) else {})
        settings_parsed = {k: by_fold.get(k.casefold()) for k in sorted((
            "m_AddressablesVersion", "m_SettingsHash", "m_IsLocalCatalogInBundle",
            "m_BuildTarget"))}
    except ValueError:
        pass

    out_dir = extracted_root / "addressables"
    log_util.write_json(out_dir / "catalog.json", {
        "meta": {
            "buildId": build_id,
            "addressablesVersion": settings_parsed.get("m_AddressablesVersion"),
            "settingsHash": settings_parsed.get("m_SettingsHash"),
            "providerIds": sorted({p for k in keys_out for p in k["providerIds"]}),
        },
        "keys": keys_out,
    })
    log_util.write_json(out_dir / "settings.snapshot.json", {
        "verbatim": raw_settings, "parsed": settings_parsed})
    coverage = {
        "keysTotal": len(keys_out),
        "distinctBundlesReferenced": len(referenced),
        "bundlesUnreferenced": unreferenced,
    }
    log_util.write_json(out_dir / "catalog-coverage.json", coverage)

    lines = [
        "- exitCode: 0",
        f"- unitypySource: {unitypy_source}",
        f"- decodeRoute: {decode_route} ({primary_note})",
        f"- keysTotal: {len(keys_out)}; distinctBundlesReferenced: "
        f"{len(referenced)} of {len(roster)} roster rows; "
        f"bundlesUnreferenced: {len(unreferenced)}",
    ]
    lines += [f"- UNRESOLVED-REFERENCE: {u}" for u in sorted(unresolved)]
    log_util.append_run_section(extracted_root, "harvest-catalog", lines)
    print(f"[harvest-catalog] keys={len(keys_out)} route={decode_route} "
          f"bundles_referenced={len(referenced)}/{len(roster)} "
          f"unreferenced={len(unreferenced)}")
    return 0


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
    except aa_catalog.CatalogDecodeError as exc:
        print(f"[harvest-catalog] DECODE FAILURE: {exc}", file=sys.stderr)
        return 1
    except tc.StageError as exc:
        print(f"[harvest-catalog] ERROR: {exc}", file=sys.stderr)
        return exc.exit_code


if __name__ == "__main__":
    sys.exit(main())
