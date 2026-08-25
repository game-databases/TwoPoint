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

Revision 5 (measured client reality): dependency keys live in KEY SPACE —
Addressables serializes them as CRC-style decimal STRINGS naming other
catalog keys (a slot literally named `-1064046067` exists), so resolving
string dependencyKeys against the file roster was a category error.
`map_catalog_keys` therefore resolves in TWO PASSES: each slot's own
FILE-FORM references first (`internalId`/`dependencyKey` strings ending
`.bundle`, matched directly or after stripping a trailing `_<32-hex>` hash
suffix the on-disk filename does not carry), then the remaining string
dependencyKeys through the key-name → bundle-set index built over ALL slots
(one level suffices — every decimal key resolves transitively on the real
payload). The hard gate NARROWS to FILE-FORM references matching neither
ladder and lacking external-content evidence; everything else is
warning-ledger in catalog-coverage.json: `danglingDependencyKeys`
(key-space deps naming no known key) and `outOfRosterFileReferences`
(references to bundles absent from this install — measured: 19 distinct,
uninstalled optional DLC `dlc-hospital-*` / `dlc-preorder-*`). Coverage
still reconciles at 176/176 roster bundles referenced.
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


def _find_catalog_monobehaviour(env, synth, primary_note: str | None = None):
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
        "route needs stage-1 dump.cs (decompiled/il2cppdumper/dump.cs)"
        + (f" | primary-route candidate reasons: {primary_note}"
           if primary_note else ""),
        exit_code=1)


def _is_file_form(value) -> bool:
    """FILE-FORM reference (Revision 5): a string spelling a bundle file,
    i.e. ending `.bundle` case-insensitively."""
    return isinstance(value, str) and value.lower().endswith(".bundle")


def map_catalog_keys(decoded: dict, norm_to_relpath: dict[str, str],
                     details: dict | None = None) -> tuple[list[dict], set[str]]:
    """Pure mapping layer (Revision 5 two-pass resolution): decoded catalog
    model → sorted key rows + set of normalized FILE-FORM references that
    matched neither a roster relpath directly nor via hash-suffix stripping.

    Pass 1 resolves every slot's own FILE-FORM references (`internalId` /
    `dependencyKey` strings ending `.bundle`) through the match ladder and
    builds the `key-name → bundle-set` index over ALL slots. Pass 2 resolves
    the remaining string `dependencyKey`s — Addressables serializes those as
    CRC-style decimal strings naming OTHER CATALOG KEYS, so resolving them
    against the file roster was a category error — through the key index
    (one level is sufficient, measured on the real payload: every decimal
    key resolves transitively).

    `details`, when a dict is supplied, receives the warning-ledger evidence:
    `danglingDependencyKeys` (sorted distinct key-space deps matching no
    known key), `outOfRosterFileReferences` ({normalized, reference} rows for
    file-form misses), `keySpaceResolutions` (entry-level hit count), and
    `hashSuffixMatches` (references resolved by the strip mapping).
    """
    keys_out: list[dict] = []
    unresolved: set[str] = set()
    dangling: set[str] = set()
    out_of_roster: dict[str, str] = {}   # normalized key -> raw spelling
    key_space_hits = 0
    hash_suffix_hits = 0

    def record_miss(raw_ref: str, norm: str) -> None:
        unresolved.add(norm)
        out_of_roster.setdefault(norm, raw_ref)

    # ---- pass 1: each slot's own FILE-FORM references -----------------------
    slot_bundles: dict[int, set[str]] = {}
    for slot in decoded["keys"]:
        bundles: set[str] = set()
        for entry in slot["entries"]:
            for cand in (entry.get("internalId"), entry.get("dependencyKey")):
                if not _is_file_form(cand):
                    continue
                kind, rel, norm = tc.resolve_file_form_reference(
                    cand, norm_to_relpath)
                if kind == "direct":
                    bundles.add(rel)
                elif kind == "hash-suffix":
                    bundles.add(rel)
                    hash_suffix_hits += 1
                else:
                    record_miss(cand, norm)
        slot_bundles[id(slot)] = bundles

    # key-name → bundle-set index over ALL slots (string keys only — the
    # key-space dependency population is strings by construction)
    key_index: dict[str, set[str]] = {}
    for slot in decoded["keys"]:
        key = slot["key"]
        if not isinstance(key, str) or not key:
            continue
        hits = slot_bundles[id(slot)]
        if hits:
            key_index.setdefault(key, set()).update(hits)

    # ---- pass 2: key-space dependencyKeys resolve through the index ---------
    for slot in decoded["keys"]:
        key = slot["key"]
        bundles = set(slot_bundles[id(slot)])
        deps: set[str] = set()
        providers: set[str] = set()
        address = None
        for entry in slot["entries"]:
            providers.add(entry["provider"].rsplit(".", 1)[-1])
            iid = entry.get("internalId")
            if not _is_file_form(iid):
                # non-bundle entry → its internalId is the addressable location
                if address is None and isinstance(iid, str) and iid:
                    address = iid
            dep_key = entry.get("dependencyKey")
            if isinstance(dep_key, str) and not _is_file_form(dep_key):
                resolved = key_index.get(dep_key)
                if resolved:
                    deps |= resolved
                    key_space_hits += 1
                else:
                    dangling.add(dep_key)
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
    if details is not None:
        details["danglingDependencyKeys"] = sorted(dangling)
        details["outOfRosterFileReferences"] = [
            {"normalized": norm, "reference": out_of_roster[norm]}
            for norm in sorted(out_of_roster)]
        details["keySpaceResolutions"] = key_space_hits
        details["hashSuffixMatches"] = hash_suffix_hits
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
            _find_catalog_monobehaviour(env, synth, primary_note=primary_note))
        decode_route = "monobehaviour-typetree(secondary)"

    # roster universe normalized once. Two roster rows normalizing to the
    # SAME case-folded basename would make this map last-write-wins and
    # silently mis-join every catalog reference to the loser — fail loudly
    # naming the collisions instead (CR#7; zero collisions on the measured
    # 176-row roster).
    by_norm: dict[str, list[str]] = {}
    for row in roster:
        by_norm.setdefault(tc.normalize_ref(row["relpath"]), []) \
            .append(row["relpath"])
    collided = {n: rels for n, rels in by_norm.items() if len(rels) > 1}
    if collided:
        sample = "; ".join(f"{n!r} <- {rels}"
                           for n, rels in sorted(collided.items())[:8])
        raise tc.StageError(
            f"{sum(len(v) for v in collided.values())} roster rows collide "
            f"on {len(collided)} normalized basename(s) — the match key is "
            "the case-folded basename after prefix stripping, so these rows "
            f"cannot be distinguished and the join would be silent "
            f"last-write-wins; first few: {sample}", exit_code=1)
    norm_to_relpath: dict[str, str] = {n: rels[0]
                                       for n, rels in by_norm.items()}

    details: dict = {}
    keys_out, unresolved = map_catalog_keys(decoded, norm_to_relpath, details)

    # NARROWED FILE-FORM hard gate (Revision 5) BEFORE any output write (no
    # partial finals): exit 1 ONLY when a FILE-FORM reference matches neither
    # a roster relpath directly nor via hash-suffix stripping AND carries no
    # external-content evidence. Evidence classes are honest absences,
    # never fatal (measured on this install: 19 distinct references to
    # uninstalled optional DLC `dlc-hospital-*` / `dlc-preorder-*`, spelled
    # either under a braced RuntimeDLCPath* provider prefix or as catalog
    # keys of their own) — they land in the warning ledger below.
    catalog_key_norms = {
        tc.normalize_ref(slot["key"]) for slot in decoded["keys"]
        if isinstance(slot["key"], str)}
    gate_failures = []
    for miss in details["outOfRosterFileReferences"]:
        if re.search(r"\{[^}]*\}", miss["reference"]):
            continue   # braced provider/scheme prefix → remote-delivery content
        if miss["normalized"] in catalog_key_norms:
            continue   # the catalog indexes the absent bundle itself
        gate_failures.append(miss)
    if gate_failures:
        sample = ", ".join(m["reference"] for m in gate_failures[:8])
        raise tc.StageError(
            f"{len(gate_failures)} FILE-FORM catalog reference(s) resolve "
            f"neither to a roster relpath nor via hash-suffix stripping "
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
    danglers = details["danglingDependencyKeys"]
    out_of_roster = details["outOfRosterFileReferences"]
    coverage = {
        "keysTotal": len(keys_out),
        "distinctBundlesReferenced": len(referenced),
        "bundlesUnreferenced": unreferenced,
        # Revision 5 warning ledgers — honest absences, never fatal
        "danglingDependencyKeys": {
            "count": len(danglers), "sample": danglers[:20]},
        "outOfRosterFileReferences": {
            "count": len(out_of_roster), "sample": out_of_roster[:20]},
    }
    log_util.write_json(out_dir / "catalog-coverage.json", coverage)

    lines = [
        "- exitCode: 0",
        f"- unitypySource: {unitypy_source}",
        f"- decodeRoute: {decode_route} ({primary_note})",
        f"- keysTotal: {len(keys_out)}; distinctBundlesReferenced: "
        f"{len(referenced)} of {len(roster)} roster rows; "
        f"bundlesUnreferenced: {len(unreferenced)}",
        f"- keySpaceResolutions: {details['keySpaceResolutions']} "
        f"(dependencyKey strings resolved through the key-name index); "
        f"hashSuffixMatches: {details['hashSuffixMatches']} "
        f"(file-form references resolved after stripping `_<32-hex>`)",
        f"- danglingDependencyKeys: {len(danglers)} "
        f"(warning ledger, sample: {danglers[:8]})",
        f"- outOfRosterFileReferences: {len(out_of_roster)} "
        "(warning ledger — references to bundles absent from this install; "
        "never fatal)",
    ]
    stats = decoded.get("meta") or {}
    if stats:
        lines.append(
            "- decodeStats: keySlots={keySlotCount}; buckets={bucketCount}; "
            "entries={entryCount}; bucketMemberships={bucketMembershipTotal} "
            "(multi-key entries put memberships above entries); "
            "distinctEntriesReferenced={distinctEntriesReferenced}; "
            "unreferencedEntries={unreferencedEntryCount}".format(**stats))
    lines += [f"- OUT-OF-ROSTER-REFERENCE: {m['reference']}"
              for m in out_of_roster[:20]]
    if len(out_of_roster) > 20:
        lines.append(f"- OUT-OF-ROSTER-REFERENCE: …and "
                     f"{len(out_of_roster) - 20} more (bounded ledger)")
    log_util.append_run_section(extracted_root, "harvest-catalog", lines)
    print(f"[harvest-catalog] keys={len(keys_out)} route={decode_route} "
          f"bundles_referenced={len(referenced)}/{len(roster)} "
          f"unreferenced={len(unreferenced)} "
          f"dangling_keyspace_deps={len(danglers)} "
          f"out_of_roster_refs={len(out_of_roster)}")
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
        log_util.append_failure_section(root, "harvest-catalog", 1,
                                        [f"DECODE FAILURE: {exc}"])
        print(f"[harvest-catalog] DECODE FAILURE: {exc}", file=sys.stderr)
        return 1
    except tc.StageError as exc:
        log_util.append_failure_section(root, "harvest-catalog",
                                        exc.exit_code, [str(exc)])
        print(f"[harvest-catalog] ERROR: {exc}", file=sys.stderr)
        return exc.exit_code


if __name__ == "__main__":
    sys.exit(main())
