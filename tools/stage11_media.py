#!/usr/bin/env python3
"""Stage 11 — media export (piece-06).

ONE entrypoint stage (`media`, canonical registry position 11) exporting
the CLIENT-owned web-ready icon layer deterministically:

  S0  scratch discipline — decode scratch on D:/A: ONLY, never C:;
      free-space floors (>=4 GiB temp / >=2 GiB output), exit-3 refusal
      naming the RIGHT dial per leg; scratch removed on completion.
  E1  entity icon set — recursive walk over the nine stub kinds filtered
      to `m_SubObjectType startswith UnityEngine.Sprite`; join ladder
      catalog-GUID -> container_index -> media-catalogue Sprite name row;
      resolution predicate PINNED to name presence (chain steps stay
      `chainBreak` evidence, never gates).
  E2  standalone-Sprite route — plain-Sprite targets incl. the ~150
      empty-sub refs (address-basename naming, `namedBy` breadcrumbs,
      pass-through rule for rect-covers-texture sprites).
  E3  UI-chrome atlas crops — FLAG-GATED (`--include-ui-chrome`, default
      OFF per arbiter R2); one canonical file per sprite, deduped against
      E1/E2 emissions (`skippedAsAlreadyEmitted`).
  E4  render-data pairing + cross-check lane — NULL-texture sprites pair
      through the OWNING ATLAS's m_RenderDataMap matched by the sprite's
      OWN rounded rect SIZE (never index alignment — M9), with the pinned
      duplicate-size tiebreak (size filter -> home-bundle preference ->
      (pagePathId ASC, entryIndex ASC) first-wins) and `ambiguousPairings`
      auditing; AssetStudioModCLI pixel-exact lane with LOSSLESS exports
      ONLY (`--image-format png` — binding pin P3).
  E5  course-icon carrier probe — FLAG-GATED (`--probe-course-carrier`),
      REPORT-ONLY, NEVER emitting an icon (binding ruling R3).
  E6  icon PPtr residue scan — ALWAYS-ON canonical 122-basis ledger over
      nine kinds x all fields with the pinned `icon` substring vocabulary
      and per-ledger escape values (binding pin P2).

Outputs land under extracted/media/ (gitignored-local per the standing
`extracted/**` rule — NO `.gitignore` edit was made or permitted); the
TRACKED layer is exactly `extracted/media/MEDIA-EXPORT.md`.

HOSTLESS END-STATE (binding pin P1): `media` is CLIENT-GATED WHOLESALE —
when neither $TPC_GAME_DIR nor the default install resolves, the stage
auto-SKIPs (never exit 3, never a degraded run). Exit 3 fires only when
the game dir RESOLVES and an upstream ARTIFACT is missing. Hostless proof
runs through `--join-only`: the E1/E6 machinery over landed artifacts
ONLY — zero bundle opens, zero pixel decodes (the S0 decode-scoped gates
are measured-but-not-enforced in that lane because it creates no scratch)
— driving index.jsonl + _missing_icons.jsonl + _pptr_residue.jsonl
end-to-end.

Exit codes: 0 success · 1 mechanism failure · 2 completed-with-ledger
(EXPECTED steady state while the M16 absences stand) · 3 environment/
gate refusal (scoped per pin P1).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import log_util  # noqa: E402
import media_util as mu  # noqa: E402
import tpc_common as tc  # noqa: E402

STAGE_ID = "media"

# piece-01 §3 stage-5 kind ↔ filename map (pinned; schemas depend on it)
STUB_KIND_FILES = {
    "item": "items.jsonl",
    "unlockable": "unlockables.jsonl",
    "room": "rooms.jsonl",
    "campus-level": "campus-levels.jsonl",
    "course": "courses.jsonl",
    "config": "configs.jsonl",
    "staff": "staff.jsonl",
    "metagame-node": "metagame-nodes.jsonl",
    "student-type": "student-types.jsonl",
}
STUB_KINDS = tuple(STUB_KIND_FILES)

TARGET_MEDIA_CLASSES = ("Sprite", "SpriteAtlas")

COURSE_CONFIG_REL = "relinks/course_config.jsonl"

# Ledgered-skip families are the MEASURED populations of E1 rule 7 / M5:
# EditorFallbackIconReference x351 (guid-broken anywhere), VisualsPrefab x12
# on items, Meshes[0] x26 on unlockables, LevelConfig x7 on campus-levels.
# Scope + BROKEN-CHAIN gating keeps the ledger an ICON-absence surface:
# resolving Meshes/Material references on items/configs (thousands) are
# ordinary non-icon refs — counted in the M5 dangling cell when broken,
# never ledgered as icon absences.
FAMILY_KIND_SCOPES = {
    mu.REASON_VISUALS_PREFAB: frozenset({"item"}),
    mu.REASON_MESH_LIST: frozenset({"unlockable"}),
    mu.REASON_LEVEL_CONFIG: frozenset({"campus-level"}),
    mu.REASON_EDITOR_FALLBACK: None,    # any kind
}


def family_skip_reason(ref: "RefRecord") -> str | None:
    """The ledgered-skip reason for THIS ref, or None when it takes the
    normal chain path (pattern match alone is not sufficient: the reference
    must be CHAIN-BROKEN — a resolving VisualsPrefab/Meshes reference is
    not an icon absence)."""
    pattern = mu.family_reason_for(ref.field_path)
    if pattern is None:
        return None
    if ref.chain_break == "none":
        return None
    scopes = FAMILY_KIND_SCOPES.get(pattern)
    if scopes is not None and ref.kind not in scopes:
        return None
    return pattern
COURSES_QUAL_FAMILY_RE = re.compile(r"Courses[_-]T[_-]Icon|Qualifications[_-]Courses",
                                    re.IGNORECASE)
CONVENTION_PREFIX = "Course_"
CONVENTION_TMPL = "UI_InGame_Courses_T_Icon_{x}"

_BANNER_VERSION_RE = re.compile(r"(?:AssetStudioMod(?:CLI)?\s+v?)(\d[\w.\-]*)",
                                re.IGNORECASE)


# ---------------------------------------------------------------------------
# Input loading

def load_stub_rows(stubs_dir: Path) -> dict[str, list[dict]]:
    rows: dict[str, list[dict]] = {}
    for kind in STUB_KINDS:
        rows[kind] = mu.read_jsonl_rows(stubs_dir / STUB_KIND_FILES[kind])
    return rows


def load_build_id(extracted_root: Path) -> int:
    path = extracted_root / "identity.json"
    if not path.is_file():
        raise mu.MediaError(f"missing upstream artifact {path}", exit_code=3)
    data = json.loads(path.read_text(encoding="utf-8"))
    build_id = data.get("buildId")
    if not isinstance(build_id, int):
        raise mu.MediaError(f"{path} carries no integer buildId", exit_code=3)
    return build_id


def load_roster_scene_flags(extracted_root: Path) -> dict[str, str]:
    """roster relpath → sceneFlag — E6's resolved-scene evidence."""
    rows = tc.load_roster(extracted_root)
    return {r["relpath"]: r.get("sceneFlag") or "none" for r in rows}


# ---------------------------------------------------------------------------
# Client gate (binding pin P1 — hostless end-state)

def resolve_media_game_root(cli_arg: str | None) -> Path | None:
    """Explicit arg/$TPC_GAME_DIR first (invalid spelling ⇒ UNRESOLVED — a
    missing game dir never exits 3 here), then the spec-pinned default
    install. Returns None ⇒ wholesale auto-SKIP."""
    raw = cli_arg or os.environ.get("TPC_GAME_DIR")
    if raw:
        p = Path(raw).resolve()
        if tc._looks_like_install_root(p):
            return p
        if tc._looks_like_tpc_data(p):
            return p.parent
        return None
    for cand in mu.DEFAULT_INSTALL_CANDIDATES:
        p = Path(cand)
        if tc._looks_like_install_root(p):
            return p
    return None


# ---------------------------------------------------------------------------
# E1 — entity icon join (walk + resolution + route classification)

class RefRecord:
    __slots__ = ("kind", "src_id", "field_path", "asset_guid", "sub_name",
                 "sub_type", "family", "chain_break", "container_row",
                 "catalog_address")

    def __init__(self, kind, src_id, ref, family, chain_break,
                 container_row, catalog_address):
        self.kind = kind
        self.src_id = src_id
        self.field_path = ref["fieldPath"]
        self.asset_guid = ref["assetGuid"]
        self.sub_name = ref["subObjectName"]
        self.sub_type = ref["subObjectType"]
        self.family = family
        self.chain_break = chain_break
        self.container_row = container_row
        self.catalog_address = catalog_address

    @property
    def sprite_typed(self) -> bool:
        return self.is_sprite_universe

    @property
    def is_sprite_universe(self) -> bool:
        """E1 universe membership. PRIMARY: `m_SubObjectType startswith
        UnityEngine.Sprite` (the verification rounds' filter — reproduces
        3,728 sprite-typed refs / 2,158 names). EXTENDED (E2): references
        carrying NO sub-type whose resolved container target is a plain
        `Sprite`-class object (~150 empty-sub standalone refs the atlas path
        cannot express; M6 measures them by TARGET CLASS, never pinned)."""
        if mu.is_sprite_typed(self.sub_type):
            return True
        if self.sub_type:
            return False
        return (self.chain_break == "none"
                and (self.container_row or {}).get("class") == "Sprite")

    @property
    def sort_key(self):
        return (self.kind, self.src_id, self.field_path)


def classify_chain(guid: str, catalog_guid_index, container_index):
    """Chain evidence — NEVER a gate (F11 pin). Returns
    (chainBreak, address|None, container_row|None). A guid key may carry
    SEVERAL addresses (duplicate-guid keys are legal Addressables); the
    first address WITH a container row wins deterministically (sorted
    order), so a multi-address guid is not misread as dangling just because
    its alphabetically-first address is uninstalled DLC content."""
    entries = catalog_guid_index.get(guid)
    if not entries:
        return "guid", None, None
    addresses = sorted({str(e["address"]) for e in entries
                        if e.get("address")})
    if not addresses:
        return "address", None, None
    for addr in addresses:
        rows = container_index.get(addr)
        if rows:
            return "none", addr, rows[0]
    return "container", addresses[0], None


def walk_all_refs(stub_rows_by_kind, catalog_guid_index, container_index):
    refs: list[RefRecord] = []
    for kind in STUB_KINDS:
        for row in stub_rows_by_kind[kind]:
            for ref in mu.walk_asset_guid_refs(row.get("fields") or {}):
                family = mu.family_reason_for(ref["fieldPath"])
                chain_break, addr, crow = classify_chain(
                    ref["assetGuid"], catalog_guid_index, container_index)
                refs.append(RefRecord(kind, str(row.get("id")), ref, family,
                                      chain_break, crow, addr))
    refs.sort(key=lambda r: r.sort_key)
    return refs


def run_e1_join(refs, sprite_name_index, persisted_sub_rows: int,
                persisted_total: int, build_id: int):
    """Returns (index_entries, missing_groups, plans, counters, drift_lines).

    index_entries: [(index_row, plan_key_or_None)] — ONE PER REF of the icon
    substrate (sprite-typed refs; family-flagged ones included with their
    ledgered-skip reason), ordered by (kind, srcId, fieldPath). The `file`
    cell is filled post-emission from the plan's canonical output.
    """
    index_entries: list[tuple[dict, tuple | None]] = []
    missing_groups: dict[tuple[str, str], dict] = {}
    plans: dict[tuple, dict] = {}
    route_split = Counter()
    distinct_names: set[str] = set()
    resolved_names: set[str] = set()
    cells: dict[str, Counter] = {k: Counter() for k in STUB_KINDS}
    drift: list[str] = []

    def ledger(sub_name, asset_guid, reason, sample) -> bool:
        key = (sub_name or f"guid:{asset_guid}", reason)
        grp = missing_groups.get(key)
        if grp is None:
            grp = {"subObjectName": sub_name, "assetGuid": asset_guid,
                   "reason": reason, "sampleRefs": [], "buildId": int(build_id)}
            missing_groups[key] = grp
        if len(grp["sampleRefs"]) < 5 and sample not in grp["sampleRefs"]:
            grp["sampleRefs"].append(sample)
        if reason not in mu.MISSING_REASONS:
            drift.append(
                f"DRIFT: _missing_icons reason '{reason}' outside the frozen "
                "enum — shipping escape value uncategorized-reason (pin P2)")
            return True
        return reason == mu.ESCAPE_REASON

    def reason_from_evidence(named: bool, name_known: bool,
                             chain_break: str, sprite_target: bool) -> str:
        if named and not name_known:
            # known-chain + absent name = stale name (Cheeseball shape);
            # broken chain = content this install cannot reach (DLC3 shape)
            return mu.REASON_STALE_NAME if chain_break == "none" \
                else mu.REASON_DLC_ABSENT
        if not named:
            return mu.REASON_EMPTY_SUB if chain_break == "none" \
                else mu.REASON_DLC_ABSENT
        if sprite_target:
            return mu.REASON_DLC_ABSENT if chain_break != "none" \
                else mu.ESCAPE_REASON
        return mu.REASON_DLC_ABSENT if chain_break != "none" \
            else mu.ESCAPE_REASON

    for ref in refs:
        cc = cells[ref.kind]
        sample = f"{ref.kind}:{ref.src_id}:{ref.field_path}"
        named = bool(ref.sub_name)
        if named and ref.sprite_typed:
            distinct_names.add(ref.sub_name)

        # --- ledgered-skip families (E1 rule 7) ----------------------------
        family_reason = family_skip_reason(ref)
        if family_reason:
            cc["dangling"] += 1
            ledger(ref.sub_name, ref.asset_guid, family_reason, sample)
            if ref.sprite_typed:
                index_entries.append((_index_row(ref, False, family_reason,
                                                 None, build_id), None))
            continue

        # --- M5 chain-outcome cells ----------------------------------------
        if ref.chain_break != "none":
            cc["dangling"] += 1
        elif (ref.container_row or {}).get("class") in TARGET_MEDIA_CLASSES:
            cc["spriteTyped"] += 1

        if not ref.sprite_typed:
            continue          # non-icon substrate — another stage's domain

        cc["refsTotal"] += 1
        target_class = (ref.container_row or {}).get("class")
        is_atlas_target = target_class == "SpriteAtlas"
        is_sprite_target = target_class == "Sprite"

        # M6 route split — reported fresh, never pinned to either basis
        if is_atlas_target and named:
            route_split["atlas-pair"] += 1
        elif is_sprite_target:
            route_split["standalone"] += 1

        # --- PINNED resolution predicate: name presence among catalogue
        #     Sprite rows (chain steps are evidence, never gates) -----------
        name_known = bool(named and ref.sub_name in sprite_name_index)
        if name_known:
            resolved_names.add(ref.sub_name)

        resolved = False
        reason: str | None = None
        route: str | None = None
        plan_key: tuple | None = None

        if is_atlas_target and named:
            route = mu.ROUTE_ATLAS_PAIR
            resolved = name_known
            if not resolved:
                reason = reason_from_evidence(named, name_known,
                                              ref.chain_break, True)
            else:
                home_rows = sprite_name_index[ref.sub_name]
                home = home_rows[0]
                plan_key = ("atlas", ref.sub_name)
                plan = plans.get(plan_key)
                if plan is None:
                    plan = {
                        "identity": plan_key,
                        "name": ref.sub_name,
                        "stem": None, "namedBy": "subObjectName",
                        "route": route,
                        "home": {"bundle": home["bundle"],
                                 "pathId": int(home["pathId"])},
                        "atlas": {"guid": ref.asset_guid,
                                  "bundle": ref.container_row["bundle"],
                                  "pathId": int(ref.container_row["pathId"])},
                        "assetGuid": ref.asset_guid,
                        "contentAxis": home.get("contentAxis"),
                        "refs": 0,
                    }
                    plans[plan_key] = plan
                plan["refs"] += 1
        elif is_sprite_target:
            route = mu.ROUTE_DIRECT_POINTER
            if named:
                # catalogue name row corroborates the object location
                resolved = name_known or ref.chain_break == "none"
            else:
                # E2 empty-sub route: the OBJECT is locatable through the
                # ref's own container row; emitted under the address-basename
                # ladder, never a fabricated name.
                resolved = ref.chain_break == "none"
            if not resolved:
                reason = reason_from_evidence(named, name_known,
                                              ref.chain_break, True)
            else:
                crow = ref.container_row
                axis_row = (sprite_name_index.get(ref.sub_name) or [{}])[0]
                if named:
                    stem = mu.emitted_stem(ref.sub_name)
                    named_by = "subObjectName"
                    display_name = ref.sub_name
                else:
                    stem, named_by = mu.standalone_naming(
                        ref.catalog_address, mu.bundle_stem(crow["bundle"]),
                        int(crow["pathId"]))
                    display_name = stem
                plan_key = ("standalone", display_name,
                            crow["bundle"], int(crow["pathId"]))
                plan = plans.get(plan_key)
                if plan is None:
                    plan = {
                        "identity": plan_key,
                        "name": display_name,
                        "stem": stem, "namedBy": named_by,
                        "route": route,
                        "home": {"bundle": crow["bundle"],
                                 "pathId": int(crow["pathId"])},
                        "atlas": None,
                        "assetGuid": ref.asset_guid,
                        "contentAxis": axis_row.get("contentAxis"),
                        "refs": 0,
                    }
                    plans[plan_key] = plan
                plan["refs"] += 1
                if not plan["assetGuid"]:
                    plan["assetGuid"] = ref.asset_guid
        else:
            resolved = False
            reason = reason_from_evidence(named, name_known,
                                          ref.chain_break, False)

        if not resolved:
            if reason is not None:
                ledger(ref.sub_name, ref.asset_guid, reason, sample)
            cc["unresolvedRefs"] += 1
        else:
            cc["resolvedRefs"] += 1
        index_entries.append((_index_row(ref, resolved,
                                         None if resolved else reason,
                                         None, build_id), plan_key))

    sprite_typed_total = sum(1 for r in refs if r.sprite_typed)
    counters = {
        "refsTotal": sprite_typed_total,
        "distinctNames": len(distinct_names),
        "resolvedNames": len(resolved_names),
        "unresolvedNames": len(distinct_names - resolved_names),
        "routeSplit": {
            "atlas-pair": route_split["atlas-pair"],
            "standalone": route_split["standalone"],
            "spriteTypedTotal": route_split["atlas-pair"]
            + route_split["standalone"],
        },
        "entityAssetGuidWalkVsPersisted": {
            "walk": sprite_typed_total,
            "persistedSub": persisted_sub_rows,
            "persistedTotal": persisted_total,
        },
    }
    return index_entries, missing_groups, plans, counters, cells, drift


def run_e1_cells(stub_rows_by_kind):
    """ROW-granular M5 cells (rows / rowsWithRefs / guidRefs); the
    REF-granular cells ride back from run_e1_join."""
    cells: dict[str, Counter] = {}
    for kind in STUB_KINDS:
        c = Counter()
        for row in stub_rows_by_kind[kind]:
            fields = row.get("fields") or {}
            refs = mu.walk_asset_guid_refs(fields)
            c["rows"] += 1
            if refs:
                c["rowsWithRefs"] += 1     # >=1 non-empty reference value
            if mu.reference_field_present(fields):
                c["rowsWithRefFields"] += 1  # reference SHAPE incl. empties
            c["guidRefs"] += len(refs)
        cells[kind] = c
    return cells


def assign_out_paths(plans: dict) -> dict:
    """Deterministic emitted-stem assignment; signed-pathId collision suffix
    when two identities would share one filename. Returns stem → plan."""
    used: dict[str, tuple] = {}
    for key in sorted(plans.keys(), key=lambda k: tuple(map(str, k))):
        plan = plans[key]
        base = plan.get("stem") or mu.emitted_stem(plan["name"])
        if base not in used:
            plan["stem"] = base
            used[base] = key
            continue
        pid = int(plan["home"]["pathId"])
        suffixed = mu.emitted_stem(base, pid)
        n = 2
        while suffixed in used:
            suffixed = f"{base}_{int(pid)}_{n}"
            n += 1
        plan["stem"] = suffixed
        used[suffixed] = key
    return {p["stem"]: p for p in plans.values()}


def _index_row(ref: RefRecord, resolved: bool, reason: str | None,
               out_file: str | None, build_id: int) -> dict:
    return {
        "kind": ref.kind,
        "srcId": ref.src_id,
        "fieldPath": ref.field_path,
        "assetGuid": ref.asset_guid,
        "subObjectName": ref.sub_name,
        "resolved": bool(resolved),
        "chainBreak": ref.chain_break,
        "file": out_file,
        "reason": reason,
        "buildId": int(build_id),
    }


# ---------------------------------------------------------------------------
# Decode layer (real mode) — bundle pool + page cache + emission

class BundlePool:
    """Read-only opener under the shared fallback-version seeding; tracks
    opened bundles (scope-containment proof) and fallback usage."""

    def __init__(self, game_root: Path, extracted_root: Path):
        self.game_root = Path(game_root)
        self.extracted_root = Path(extracted_root)
        self._by_basename: dict[str, str] = {}
        try:
            for row in tc.load_roster(extracted_root):
                self._by_basename.setdefault(
                    mu.bundle_stem(row["relpath"]).lower()
                    + ".bundle", row["relpath"])
        except tc.StageError:
            pass                     # roster absent → direct-path opens only
        import unitypy_util as uu  # noqa: PLC0415 — deferred (hostless lane
        self.uu = uu               # never imports UnityPy)
        self.UnityPy, source = uu.ensure_unitypy()
        self.unitypy_source = source
        self.seeder = uu.FallbackVersionSeeder(self.extracted_root,
                                               self.UnityPy)
        self.opened: dict[str, int] = {}
        self.fallback_seeded: list[str] = []
        self._envs: dict[str, object] = {}
        self._objects: dict[str, dict[int, object]] = {}
        self.cab_by_name = mu.load_cab_index(self.extracted_root)

    def cli_input_path(self, bundle_rel: str) -> Path:
        """Existing bundle file for the CLI lane (roster-basename
        resolution shared with open())."""
        p = self.abspath(bundle_rel)
        if p.is_file():
            return p
        rel = self._by_basename.get(
            mu.bundle_stem(bundle_rel).lower() + ".bundle")
        return self.game_root / rel if rel else p

    def abspath(self, bundle_rel: str) -> Path:
        return self.game_root / bundle_rel

    def open(self, bundle_rel: str):
        env = self._envs.get(bundle_rel)
        if env is not None:
            return env
        abspath = self.abspath(bundle_rel)
        if not abspath.is_file():
            # bare spellings (base aa bundles live under
            # TPC_Data/StreamingAssets/aa/StandaloneWindows64/) resolve
            # through the roster basename index
            rel = self._by_basename.get(
                mu.bundle_stem(bundle_rel).lower() + ".bundle")
            if rel is not None:
                abspath = self.game_root / rel
        if not abspath.is_file():
            raise mu.MediaError(
                f"referenced bundle missing on disk: {abspath} "
                "(grammar model broken — the join resolved to a bundle the "
                "client does not ship)", exit_code=1)
        if self.seeder.seed_if_needed(abspath, bundle_rel):
            if bundle_rel not in self.fallback_seeded:
                self.fallback_seeded.append(bundle_rel)
        env = self.UnityPy.load(str(abspath))
        self._envs[bundle_rel] = env
        self.opened[bundle_rel] = self.opened.get(bundle_rel, 0) + 1
        return env

    def objects(self, bundle_rel: str) -> dict[int, object]:
        idx = self._objects.get(bundle_rel)
        if idx is not None:
            return idx
        env = self.open(bundle_rel)
        idx = {}
        for f in self.uu.iter_environment_files(env):
            for o in self.uu.iter_objects_sorted(f):
                idx.setdefault(int(getattr(o, "path_id", 0) or 0), o)
        self._objects[bundle_rel] = idx
        return idx

    def find(self, bundle_rel: str, path_id: int):
        return self.objects(bundle_rel).get(int(path_id))

    def resolve_pointer(self, owner_obj, owner_bundle: str, ptr):
        """PPtr → (bundle_rel, path_id) | None. fileID indexes the OWNER's
        serialized-file externals (1-based; 0 = same file)."""
        if not isinstance(ptr, dict):
            return None
        fid = int(ptr.get("m_FileID", 0) or 0)
        pid = int(ptr.get("m_PathID", 0) or 0)
        if pid == 0:
            return None
        if fid == 0:
            return owner_bundle, pid
        af = getattr(owner_obj, "assets_file", None)
        exts = getattr(af, "externals", None) or []
        if fid < 1 or fid > len(exts):
            return None
        cab = mu.simplify_external_path(getattr(exts[fid - 1], "path", ""))
        entry = self.cab_by_name.get(cab)
        if entry is None:
            return None
        return entry["bundle"], pid


class SpritePixels:
    """Resolved pixels + provenance for one planned sprite."""

    __slots__ = ("rgba", "w", "h", "route", "bounds", "raw_rect",
                 "page_bundle", "page_path_id", "page_name", "atlas_name",
                 "null_pointer_paired", "ambiguous_pairing", "fractional",
                 "bc7_page")

    def __init__(self, **kw):
        for k in self.__slots__:
            setattr(self, k, kw.get(k))


def resolve_sprite_pixels(plan: dict, pool: BundlePool,
                          page_cache: mu.PageCache) -> SpritePixels:
    """THE mechanism sub-pass (E4) applied to one plan: locate the sprite
    object, pick its page, and produce the cropped RGBA8 buffer. Page
    selection ladder: (1) render-data pairing through the OWNING ATLAS when
    the sprite's texture pointer is NULL — the atlas comes from the ref's
    target or, failing that, the sprite object's own m_SpriteAtlas pointer;
    (2) the sprite's direct texture pointer; (3) the E2-sanctioned UnityPy
    Sprite.image fallback. Crop geometry: the ENTRY rect for paired sprites
    (the rect that actually lives in PAGE space — proven pixel-exact vs
    AssetStudioModCLI; M9 pins only the sprite-rect SIZE for the pairing),
    the sprite's own m_RD.textureRect otherwise. Bottom-origin flip +
    half-away-from-zero rounding apply everywhere."""
    home_rel = plan["home"]["bundle"]
    home_pid = int(plan["home"]["pathId"])
    sprite_obj = pool.find(home_rel, home_pid)
    if sprite_obj is None:
        raise mu.MediaError(
            f"referenced Sprite object not found: {plan['name']} "
            f"({home_rel}#{home_pid})", exit_code=1)
    sd = _typetree(sprite_obj)
    rd = sd.get("m_RD") or {}
    raw_rect = rd.get("textureRect") or sd.get("m_Rect")
    if not isinstance(raw_rect, dict) or not raw_rect:
        raise mu.MediaError(
            f"referenced sprite carries no usable rect: {plan['name']} "
            f"({home_rel}#{home_pid})", exit_code=1)
    rx, ry, rw, rh = mu.parse_rect(raw_rect)
    fractional = any(abs(v - round(v)) > 1e-9 for v in (rx, ry, rw, rh))
    tex_ptr = rd.get("texture") or {"m_FileID": 0, "m_PathID": 0}

    route = plan["route"]
    null_paired = False
    ambiguous = False
    bc7_page = False
    page_bundle = None
    page_pid = None
    page_name = None
    page_fmt = None
    atlas_name = None

    def pair_through_atlas(atlas_rel: str, atlas_pid: int):
        """Render-data pairing + page decode + entry-rect crop. Pairing
        ladder: (1) EXACT match through the sprite's own m_RenderDataKey
        (the game's pointer into this very map — resolves same-page
        same-size collisions the size ladder cannot); (2) the pinned
        size filter + home-bundle preference + (pagePathId ASC,
        entryIndex ASC) first-wins tiebreak, flagged ambiguous. Returns
        (buf, pw, ph, fmt, bounds, chosen, atlas_name, ambiguous)."""
        atlas_obj = pool.find(atlas_rel, atlas_pid)
        if atlas_obj is None:
            raise mu.MediaError(
                f"referenced atlas object not found: {plan['name']} "
                f"({atlas_rel}#{atlas_pid})", exit_code=1)
        ad = _typetree(atlas_obj)
        entries = mu.normalize_render_entries(ad.get("m_RenderDataMap"))
        for e in entries:
            e["pageBundleKey"] = _pointer_bundle_from_atlas_context(
                pool, atlas_obj, atlas_rel, e["pageFileId"])
        chosen = mu.select_entry_by_render_key(entries,
                                               sd.get("m_RenderDataKey"))
        amb = False
        if chosen is not None:
            via_render_key.append(True)
        else:
            chosen, amb = mu.select_page_entry(entries, (rw, rh),
                                               home_bundle_keys={home_rel})
        if chosen is None:
            raise mu.MediaError(
                f"pairing match failure on referenced sprite "
                f"'{plan['name']}': no render-data entry sized "
                f"{mu.round_half_away(rw)}x{mu.round_half_away(rh)} in atlas "
                f"{ad.get('m_Name') or atlas_rel}#{atlas_pid}", exit_code=1)
        p_rel = chosen.get("pageBundleKey") or atlas_rel
        p_pid = int(chosen["pagePathId"])
        buf, pw, ph, fmt = _page_rgba(pool, page_cache, p_rel, p_pid)
        entry_rect = {"x": chosen["x"], "y": chosen["y"],
                      "width": chosen["w"], "height": chosen["h"]}
        bnds = mu.rounded_crop_bounds(entry_rect, page_h=int(ph),
                                      page_w=int(pw))
        return buf, pw, ph, fmt, bnds, chosen, ad.get("m_Name") or "", amb

    via_render_key = []
    null_texture = int(tex_ptr.get("m_PathID", 0) or 0) == 0 \
        and int(tex_ptr.get("m_FileID", 0) or 0) == 0

    atlas_ctx = None
    if route == mu.ROUTE_ATLAS_PAIR and plan.get("atlas"):
        atlas_ctx = (plan["atlas"]["bundle"], int(plan["atlas"]["pathId"]))
    else:
        atlas_ptr = sd.get("m_SpriteAtlas")
        if isinstance(atlas_ptr, dict) \
                and int(atlas_ptr.get("m_PathID", 0) or 0) != 0:
            resolved = pool.resolve_pointer(sprite_obj, home_rel, atlas_ptr)
            if resolved is not None:
                atlas_ctx = resolved

    if atlas_ctx is not None:
        buf, pw, ph, page_fmt, bounds, chosen, atlas_name, ambiguous = \
            pair_through_atlas(atlas_ctx[0], atlas_ctx[1])
        page_bundle = chosen.get("pageBundleKey") or atlas_ctx[0]
        page_pid = int(chosen["pagePathId"])
        page_name = _texture_name(pool, page_bundle, page_pid)
        bc7_page = page_fmt == 25   # Unity TextureFormat.BC7 (M11 special)
        if null_texture:
            null_paired = True      # the M8 46% population
        rx, ry, rw, rh = mu.parse_rect(
            {"x": chosen["x"], "y": chosen["y"], "width": chosen["w"],
             "height": chosen["h"]})
        fractional = any(abs(v - round(v)) > 1e-9 for v in (rx, ry, rw, rh))
    else:
        resolved_ptr = pool.resolve_pointer(sprite_obj, home_rel, tex_ptr)
        if resolved_ptr is None and not null_texture:
            resolved_ptr = None
        if resolved_ptr is not None:
            page_bundle, page_pid = resolved_ptr
            page_name = _texture_name(pool, page_bundle, page_pid)
            buf, pw, ph, page_fmt = _page_rgba(pool, page_cache, page_bundle,
                                               page_pid)
            bc7_page = page_fmt == 25
        else:
            # E2 sanctioned fallback for sprites without a usable texture
            # pointer and no locatable atlas: UnityPy's Sprite.image path.
            page_bundle, page_pid = home_rel, home_pid
            buf, pw, ph = _sprite_rgba_fallback(pool, page_cache, sprite_obj,
                                                home_rel, home_pid,
                                                plan["name"])
        if mu.rect_covers_texture(raw_rect, int(pw), int(ph)):
            return SpritePixels(
                rgba=buf, w=int(pw), h=int(ph),
                route=mu.ROUTE_PASS_THROUGH,
                bounds={"left": 0, "top": 0, "w": int(pw), "h": int(ph)},
                raw_rect=(rx, ry, rw, rh), page_bundle=page_bundle,
                page_path_id=page_pid, page_name=page_name,
                atlas_name=None,
                null_pointer_paired=null_paired,
                ambiguous_pairing=ambiguous, fractional=fractional,
                bc7_page=bool(bc7_page))
        bounds = mu.rounded_crop_bounds(raw_rect, page_h=int(ph),
                                        page_w=int(pw))

    rgba = mu.crop_rgba_bytes(buf, int(pw), int(ph), bounds)
    return SpritePixels(rgba=rgba, w=int(bounds["w"]), h=int(bounds["h"]),
                        route=route, bounds=bounds,
                        raw_rect=(rx, ry, rw, rh), page_bundle=page_bundle,
                        page_path_id=page_pid, page_name=page_name,
                        atlas_name=atlas_name,
                        null_pointer_paired=null_paired,
                        ambiguous_pairing=ambiguous, fractional=fractional,
                        bc7_page=bool(bc7_page))


def _typetree(obj) -> dict:
    try:
        data = obj.read_typetree(wrap=False)
        return data if isinstance(data, dict) else {}
    except Exception as exc:  # noqa: BLE001 — loud, named mechanism failure
        raise mu.MediaError(
            f"typetree read failed for {getattr(obj, 'path_id', '?')}: "
            f"{type(exc).__name__}: {exc}", exit_code=1) from None


def _pointer_bundle_from_atlas_context(pool, atlas_obj, atlas_rel, file_id):
    """Renderdata page pointers are relative to the ATLAS's serialized file:
    fileID 0 ⇒ the atlas's own bundle; otherwise its externals → cab →
    cab_index bundle (home-bundle preference evidence for the tiebreak)."""
    if int(file_id or 0) == 0:
        return atlas_rel
    af = getattr(atlas_obj, "assets_file", None)
    exts = getattr(af, "externals", None) or []
    if 1 <= int(file_id) <= len(exts):
        cab = mu.simplify_external_path(getattr(exts[int(file_id) - 1],
                                                "path", ""))
        entry = pool.cab_by_name.get(cab)
        if entry is not None:
            return entry["bundle"]
    return None


def _texture_name(pool, bundle_rel, path_id) -> str | None:
    obj = pool.find(bundle_rel, path_id)
    if obj is None:
        return None
    try:
        d = obj.read_typetree(wrap=False)
        return d.get("m_Name")
    except Exception:  # noqa: BLE001 — name stays optional provenance
        return None


def _page_rgba(pool, page_cache, bundle_rel, path_id):
    """Decode-once cache: pages enter as raw RGBA8 buffers in the temp root
    and are cropped N times. BC1/BC3/BC7/RGBA32 all arrive through the same
    Texture2D.image path (the single BC7 page decodes here too — M11).
    Returns (rgba_bytes, w, h, texture_format_int|None)."""
    key = mu.PageCache.key_for(bundle_rel, path_id)
    hit = page_cache.get(key)
    if hit is not None:
        return hit
    obj = pool.find(bundle_rel, path_id)
    if obj is None:
        raise mu.MediaError(
            f"referenced atlas page not found: {bundle_rel}#{path_id}",
            exit_code=1)
    fmt = None
    try:
        head = obj.read_typetree(wrap=False)
        fmt = head.get("m_TextureFormat")
        if isinstance(fmt, str):
            fmt = None
    except Exception:  # noqa: BLE001 — provenance-only read
        fmt = None
    try:
        img = obj.read().image.convert("RGBA")
    except Exception as exc:  # noqa: BLE001 — loud decode failure (EC row)
        raise mu.MediaError(
            f"page decode failed: {bundle_rel}#{path_id} "
            f"(format={fmt}): {type(exc).__name__}: {exc}", exit_code=1
        ) from None
    buf = img.tobytes()
    w, h = img.size
    page_cache.put(key, buf, w, h,
                   int(fmt) if isinstance(fmt, int) else None)
    return buf, w, h, (int(fmt) if isinstance(fmt, int) else None)


def _sprite_rgba_fallback(pool, page_cache, sprite_obj, bundle_rel, path_id,
                          sprite_name):
    """E2 sanctioned decode fallback (spec §3 E2): UnityPy's own Sprite.image
    path for standalone sprites whose texture pointer is NULL."""
    key = mu.PageCache.key_for(bundle_rel + ":sprite", path_id)
    hit = page_cache.get(key)
    if hit is not None:
        return hit[0], hit[1], hit[2]
    try:
        img = sprite_obj.read().image.convert("RGBA")
    except Exception as exc:  # noqa: BLE001
        raise mu.MediaError(
            f"pairing match failure on referenced sprite '{sprite_name}' "
            f"({bundle_rel}#{path_id}): no texture pointer and the UnityPy "
            f"Sprite.image fallback failed: {type(exc).__name__}: {exc}",
            exit_code=1) from None
    buf = img.tobytes()
    w, h = img.size
    page_cache.put(key, buf, w, h)
    return buf, w, h


# ---------------------------------------------------------------------------
# Emission — encode + manifest rows + twins + thumbs (format rule §4)

def _content_axis_of(plan) -> str:
    axis = plan.get("contentAxis")
    if axis in tc.CONTENT_AXES:
        return axis
    return tc.axis_for_bundle_name(mu.bundle_stem(plan["home"]["bundle"]))


def _source_block(plan, pixels, atlas_name: str | None) -> dict:
    rx, ry, rw, rh = pixels.raw_rect
    src = {
        "bundle": plan["home"]["bundle"],
        "pathId": int(plan["home"]["pathId"]),
        "class": "Sprite",
        "subObjectName": plan["name"],
        "assetGuid": plan.get("assetGuid") or "",
        "rect": {"x": float(rx), "y": float(ry), "w": float(rw),
                 "h": float(rh)},
        "rounded": {"left": int(pixels.bounds["left"]),
                    "top": int(pixels.bounds["top"]),
                    "w": int(pixels.bounds["w"]),
                    "h": int(pixels.bounds["h"])},
        "contentAxis": _content_axis_of(plan),
    }
    if plan["route"] == mu.ROUTE_ATLAS_PAIR and plan.get("atlas"):
        src.update({
            "atlasName": atlas_name or "",
            "atlasGuid": plan["atlas"].get("guid") or "",
            "pageBundle": pixels.page_bundle or "",
            "pageName": pixels.page_name or "",
            "pagePathId": int(pixels.page_path_id or 0),
        })
    return src


def emit_sprite(plan: dict, pixels: SpritePixels, media_dir: Path,
                opts, build_id: int, plane: str = "icons",
                subdir: str = "icons") -> tuple[list[dict], Counter]:
    """Write ONE canonical native-res asset (+PNG twin rules, +thumbs tier)
    and return its manifest rows. Binary encodes go temp-first and rename
    like every other output (log_util discipline)."""
    counters = Counter()
    rows: list[dict] = []
    stem = plan["stem"]
    base_rel = f"web/{subdir}/{stem}"
    img = mu.image_from_rgba(pixels.rgba, pixels.w, pixels.h)
    src = _source_block(plan, pixels, getattr(pixels, "atlas_name", None))
    named_by = plan.get("namedBy") or "subObjectName"

    def row_for(out_rel: str, fmt: str, quality, payload: bytes,
                w: int, h: int) -> dict:
        return {
            "outRelPath": out_rel,
            "plane": plane,
            "format": fmt,
            "quality": quality,
            "bytes": len(payload),
            "sha256": log_util.sha256_bytes(payload),
            "route": pixels.route,
            "namedBy": named_by,
            "source": src,
            "dims": {"w": int(w), "h": int(h)},
            "buildId": int(build_id),
        }

    webp_bytes = mu.encode_webp(img, quality=mu.WEBP_QUALITY)
    out_rel = base_rel + ".webp"
    log_util.atomic_write_bytes(media_dir / out_rel, webp_bytes)
    rows.append(row_for(out_rel, "webp", mu.WEBP_QUALITY, webp_bytes,
                        pixels.w, pixels.h))

    alpha_delta = mu.alpha_roundtrip_max_delta(webp_bytes, img)
    want_png = bool(opts.png_all) \
        or max(int(pixels.w), int(pixels.h)) <= mu.PNG_TWIN_MAX_DIM
    if alpha_delta > mu.ALPHA_TOLERANCE:
        want_png = True
        counters["alphaSanityFallbacks"] += 1
    if want_png:
        png_bytes = mu.encode_png(img)
        out_png = base_rel + ".png"
        log_util.atomic_write_bytes(media_dir / out_png, png_bytes)
        rows.append(row_for(out_png, "png", None, png_bytes, pixels.w,
                            pixels.h))
        counters["pngTwins"] += 1

    for dim in opts.thumb_dims or ():
        tbytes = mu.encode_thumb(img, dim)
        trel = f"web/thumbs/{stem}@{dim}.webp"
        log_util.atomic_write_bytes(media_dir / trel, tbytes)
        tw, th = thumb_dims_of(tbytes)
        rows.append(row_for(trel, "webp", mu.WEBP_QUALITY, tbytes, tw, th))
        counters["thumbsEmitted"] += 1
    return rows, counters


def thumb_dims_of(webp_bytes: bytes) -> tuple[int, int]:
    import io as _io  # noqa: PLC0415
    Image = mu.load_pil()
    with Image.open(_io.BytesIO(webp_bytes)) as im:
        return im.size


def emit_plans(stem_plans: dict, pool: BundlePool, page_cache: mu.PageCache,
               media_dir: Path, opts, build_id: int,
               plane: str = "icons", subdir: str = "icons",
               ) -> tuple[list[dict], Counter]:
    """Decode + emit every planned sprite (sorted stems — determinism);
    returns (manifest_rows, counters). Pairing match failures and rect
    breaches raise MediaError(exit 1) loudly named (EC row)."""
    rows: list[dict] = []
    counters: Counter = Counter()
    for stem in sorted(stem_plans):
        plan = stem_plans[stem]
        pixels = resolve_sprite_pixels(plan, pool, page_cache)
        plan["route"] = pixels.route
        plan["ambiguousPairing"] = bool(pixels.ambiguous_pairing)
        plan["fractionalRect"] = bool(pixels.fractional)
        plan["nullPointerPaired"] = bool(pixels.null_pointer_paired)
        plan["bc7Page"] = bool(getattr(pixels, "bc7_page", False))
        if pixels.null_pointer_paired:
            counters["nullTexturePointersPaired"] += 1
        if pixels.ambiguous_pairing:
            counters["ambiguousPairings"] += 1
        prows, pcounters = emit_sprite(plan, pixels, media_dir, opts,
                                       build_id, plane=plane, subdir=subdir)
        rows.extend(prows)
        counters.update(pcounters)
        counters["spritesEmitted"] += 1
    return rows, counters


# ---------------------------------------------------------------------------
# E3 — UI-chrome atlas crops (flag-gated; arbiter R2: OFF in v1)

def iter_atlas_defs(container_index) -> list[tuple[str, int]]:
    seen = set()
    for rows in container_index.values():
        for row in rows:
            if row.get("class") == "SpriteAtlas":
                seen.add((row["bundle"], int(row["pathId"])))
    return sorted(seen)




def run_e3_ui_chrome(pool, page_cache, sprite_name_index, emitted_stems,
                     media_dir: Path, opts, build_id: int,
                     container_index) -> tuple[list[dict], Counter]:
    """Scope-ladder second step — ONLY with --include-ui-chrome (arbiter R2
    pins flag-OFF in v1; the flip is an orchestrator scheduling call over
    this machinery, never a code change). One canonical file per sprite:
    slots already emitted by E1/E2 are skipped, never duplicated."""
    rows: list[dict] = []
    counters: Counter = Counter()
    seen_names: set[str] = set(emitted_stems)
    for atlas_bundle, atlas_pid in iter_atlas_defs(container_index):
        counters["atlasesProcessed"] += 1
        atlas_obj = pool.find(atlas_bundle, atlas_pid)
        if atlas_obj is None:
            continue
        ad = _typetree(atlas_obj)
        atlas_name = ad.get("m_Name") or mu.sanitize_component(
            mu.bundle_stem(atlas_bundle))
        entries = mu.normalize_render_entries(ad.get("m_RenderDataMap"))
        for e in entries:
            e["pageBundleKey"] = _pointer_bundle_from_atlas_context(
                pool, atlas_obj, atlas_bundle, e["pageFileId"])
        for name in sorted(ad.get("m_PackedSpriteNamesToIndex") or []):
            if not isinstance(name, str) or not name or name in seen_names:
                counters["skippedAsAlreadyEmitted"] += 1
                continue
            home_rows = sprite_name_index.get(name)
            if not home_rows:
                # packed slot without a catalogue Sprite object: nothing to
                # key provenance on; counted, never fabricated
                counters["skippedAsAlreadyEmitted"] += 1
                continue
            home = home_rows[0]
            plan = {
                "identity": ("e3", atlas_bundle, int(atlas_pid), name),
                "name": name,
                "stem": None,
                "namedBy": "subObjectName",
                "route": mu.ROUTE_ATLAS_PAIR,
                "home": {"bundle": home["bundle"],
                         "pathId": int(home["pathId"])},
                "atlas": {"guid": "", "bundle": atlas_bundle,
                          "pathId": int(atlas_pid)},
                "assetGuid": "",
                "contentAxis": home.get("contentAxis"),
                "refs": 0,
            }
            stem = mu.emitted_stem(name)
            n = 2
            while stem in seen_names:
                stem = mu.emitted_stem(name, int(home["pathId"])) \
                    + ("" if n == 2 else f"_{n}")
                n += 1
            plan["stem"] = stem
            seen_names.add(stem)
            try:
                prows, pcounters = emit_plans({stem: plan}, pool, page_cache,
                                              media_dir, opts, build_id,
                                              plane="ui",
                                              subdir=f"ui/{atlas_name}")
            except mu.MediaError as exc:
                if exc.exit_code == 1 and "pairing match failure" in str(exc):
                    # a non-referenced chrome slot failing to pair is a skip,
                    # not a grammar break — the exit-1 rule names REFERENCED
                    # sprites only
                    counters.setdefault("slotsSkippedUnpairable", 0)
                    counters["slotsSkippedUnpairable"] += 1
                    continue
                raise
            rows.extend(prows)
            counters.update(pcounters)
            counters["cropsEmitted"] += 1
    return rows, counters


# ---------------------------------------------------------------------------
# E4(3) — AssetStudioModCLI cross-check lane (acceptance surface)

def resolve_cli_version(cli_exe, extracted_root: Path) -> str:
    defaults = log_util.read_stage_defaults(extracted_root) or {}
    pinned = (defaults.get("assetStudioModCli") or {}).get("version")
    if pinned:
        return str(pinned)
    if cli_exe is None:
        return "unknown"
    try:
        proc = subprocess.run([str(cli_exe), "--help"], capture_output=True,
                              text=True, timeout=120)
        blob = f"{proc.stdout}\n{proc.stderr}"
    except Exception:  # noqa: BLE001 — explicit unknown, never a guess
        return "unknown"
    m = _BANNER_VERSION_RE.search(blob)
    return m.group(1) if m else "unknown"


def _routes_in_scope(stem_plans: dict) -> set:
    return {p.get("route") for p in stem_plans.values()
            if p.get("route") in mu.ROUTES}

def _quotas_satisfied(sampled_ok: list[str], stem_plans: dict) -> bool:
    q = _quota_report(sampled_ok, stem_plans)
    # '>=1 per route' scopes to the routes this run's emission set
    # actually contains: standalone-pass-through exists only when a
    # referenced sprite's rect covers its whole texture (measured:
    # none in the referenced universe of buildId 20226581).
    routes = set(q["routesCovered"])
    # Availability-scoped: the sprite m_RenderDataKey pairing resolves
    # same-size collisions EXACTLY, so ambiguity-flagged plans exist
    # only where key evidence was missing (measured: ~1 per run).
    amb_avail = sum(1 for p in stem_plans.values()
                    if p.get("ambiguousPairing"))
    frac_avail = sum(1 for p in stem_plans.values()
                     if p.get("fractionalRect"))
    return (routes == _routes_in_scope(stem_plans)
            and q["ambiguousTiebreakSamples"] >= min(3, amb_avail)
            and q["fractionalRectSamples"] >= min(2, frac_avail))


def run_crosscheck(sample_stems: list[str], stem_plans: dict,
                   pool: "BundlePool", page_cache: mu.PageCache,
                   cli_exe, cli_dir: Path, extracted_root: Path,
                   build_id: int) -> dict:
    """Pixel-exact acceptance lane. CLI exports are LOSSLESS png (pin P3)
    and confined to the temp root. A genuine pixel mismatch (dimensions
    differ or maxDelta != 0 on an EXPORTED pair) is EC exit 1 with the
    diagnostic pair written to the temp root - never a silent retry. The
    CLI cannot export every packed-sprite stub (measured: it finds the
    asset but exports nothing when the home object carries no texture), so
    non-exportable samples are EXCLUDED and deterministically replaced from
    the stride pool until >=20 successful comparisons AND all quotas hold;
    exhaustion below that is a lane failure."""
    Image = mu.load_pil()
    cli_version = resolve_cli_version(cli_exe, extracted_root)
    candidates: list[str] = list(sample_stems)
    for stem in sorted(stem_plans):
        if stem not in candidates:
            candidates.append(stem)      # deterministic replacement pool
    results: list[dict] = []
    matched = 0
    failures: list[dict] = []
    excluded: list[dict] = []
    sampled_ok: list[str] = []
    attempts = 0
    MAX_ATTEMPTS = 300   # bounds the replacement sweep on real runs
    for stem in candidates:
        if attempts >= MAX_ATTEMPTS:
            break
        if matched >= mu.CROSSCHECK_MIN_SAMPLE and                 _quotas_satisfied(sampled_ok, stem_plans):
            break
        attempts += 1
        plan = stem_plans[stem]
        entry: dict = {"sprite": stem, "route": plan.get("route")}
        try:
            pixels = resolve_sprite_pixels(plan, pool, page_cache)
            ours = mu.image_from_rgba(pixels.rgba, pixels.w, pixels.h)
            entry["route"] = pixels.route
        except mu.MediaError as exc:
            entry.update({"error": "recompute-failed", "detail": str(exc)})
            failures.append(entry)
            results.append(entry)
            continue
        out_dir = cli_dir / mu.sanitize_component(stem)
        out_dir.mkdir(parents=True, exist_ok=True)
        argv = mu.cli_export_argv(
            cli_exe, pool.cli_input_path(plan["home"]["bundle"]), out_dir,
            unity_version=mu.CLI_UNITY_VERSION_PIN, image_format="png",
            name_filter=plan["name"])
        proc = subprocess.run(argv, capture_output=True, text=True,
                              timeout=600)
        exported = sorted(out_dir.rglob("*.png"))
        # EXACT-stem match first - the name filter is a substring
        # filter and sibling assets (_Plus variants, numbered
        # families) export alongside the target.
        exact = [c for c in exported
                 if c.stem.lower() == plan["name"].lower()]
        pool_c = [c for c in exported if c not in exact]
        pool_c.sort(key=lambda c: (len(c.stem), str(c)))
        if not exact:
            # the filter found siblings but not THE sprite: the CLI
            # cannot export this asset (packed stub) - exclude, never
            # compare against a different sprite
            entry.update({"excluded": "cli-not-exportable",
                          "siblingsExported": [c.stem for c in pool_c[:5]]})
            excluded.append(entry)
            results.append(entry)
            continue
        hit = exact[0]
        if hit is None:
            # CLI limitation on this sprite (found-but-not-exportable):
            # exclusion with evidence, never a pixel verdict
            entry.update({"excluded": "cli-not-exportable",
                          "cliReturnCode": proc.returncode})
            excluded.append(entry)
            results.append(entry)
            continue
        theirs = Image.open(hit).convert("RGBA")
        cmp_result = mu.compare_rgba8(ours, theirs)
        entry.update(cmp_result)
        entry["cliExport"] = str(hit.relative_to(cli_dir))
        results.append(entry)
        if cmp_result["dimensionsMatch"] and cmp_result["maxDelta"] == 0:
            matched += 1
            sampled_ok.append(stem)
        else:
            failures.append(entry)
            diag = cli_dir / "diagnostics" / mu.sanitize_component(stem)
            diag.mkdir(parents=True, exist_ok=True)
            ours.save(diag / "ours.png")
            try:
                (diag / "cli_export.png").write_bytes(hit.read_bytes())
            except OSError:
                pass
            (diag / "README.txt").write_text(
                f"sprite: {plan['name']}"
                + "home: {" + str(plan["home"]) + "}"
                + "compare: " + str(cmp_result), encoding="utf-8",
                newline=chr(10))
    total = len(sampled_ok)
    rate = 1.0 if total and total == matched else (
        (matched / float(len(results))) if results else 0.0)
    max_delta = 0 if not failures else (
        max([int(f.get("maxDelta") or 255) for f in failures
             if f.get("maxDelta") is not None] + [0]))
    report = {
        "ran": True,
        "sampleStems": sampled_ok,
        "sampleSize": total,
        "matchedSamples": matched,
        "pixelMatchRate": round(rate, 6),
        "maxDelta": int(max_delta),
        "cliVersion": cli_version,
        "cliUnityVersion": mu.CLI_UNITY_VERSION_PIN,
        "cliExportFormat": "png",
        "comparatorPath": ("CLI export -> PIL convert('RGBA') -> elementwise "
                           "RGBA8 vs our crop bytes"),
        "quotas": _quota_report(sampled_ok, stem_plans),
        "excluded": excluded[:40],
        "failures": failures[:20],
        "buildId": int(build_id),
    }
    quotas_ok = _quotas_satisfied(sampled_ok, stem_plans)
    report["pass"] = bool(total >= mu.CROSSCHECK_MIN_SAMPLE
                          and total == matched
                          and max_delta == 0
                          and quotas_ok)
    if not report["pass"]:
        raise mu.MediaError(
            f"cross-check lane FAILED: samples={total} matched={matched} "
            f"pixelMatchRate={report['pixelMatchRate']} "
            f"maxDelta={report['maxDelta']} quotasOk={quotas_ok} "
            f"(failures: {[f.get('sprite') for f in failures][:10]}); "
            "diagnostic pairs written under the temp root", exit_code=1)
    return report


def _quota_report(sample_stems: list[str], stem_plans: dict) -> dict:
    routes_seen = {stem_plans[s].get("route") for s in sample_stems}
    return {
        "routesCovered": sorted(r for r in routes_seen if r),
        "ambiguousTiebreakSamples": sum(
            1 for s in sample_stems if stem_plans[s].get("ambiguousPairing")),
        "fractionalRectSamples": sum(
            1 for s in sample_stems if stem_plans[s].get("fractionalRect")),
        "bc7PageSamples": sum(
            1 for s in sample_stems if stem_plans[s].get("bc7Page")),
        "anchorsPresent": [a for a in mu.CROSSCHECK_ANCHORS
                           if any(stem_plans[s].get("name") == a
                                  for s in sample_stems)],
    }


# ---------------------------------------------------------------------------
# E5 — course-icon carrier probe (flag-gated, REPORT-ONLY — ruling R3)

def run_e5_probe(extracted_root: Path, stub_rows_by_kind,
                 sprite_name_index, build_id: int):
    """Answers scout §9 Q1 from landed artifacts. NEVER emits an icon and
    NEVER writes outside extracted/media/ (binding ruling R3: turning this
    probe into emission — or deleting it as gold-plating — violates the
    ruling)."""
    courses = stub_rows_by_kind.get("course") or []
    configs = stub_rows_by_kind.get("config") or []
    counters: Counter = Counter()

    populated_ids = []
    for row in courses:
        q = (row.get("fields") or {}).get("Qualification")
        hit = False
        if isinstance(q, dict):
            guid = q.get("m_AssetGUID")
            pid = q.get("m_PathID")
            hit = bool(isinstance(guid, str) and guid.strip()) or bool(pid)
        if hit:
            populated_ids.append(str(row.get("id")))
    counters["pptrPopulated"] = len(populated_ids)

    chain_ids: set[str] = set()
    edges_path = extracted_root / COURSE_CONFIG_REL
    edge_count = 0
    for edge in mu.read_jsonl_rows(edges_path, required=False):
        edge_count += 1
        if edge.get("srcKind") == "course":
            chain_ids.add(str(edge.get("srcId")))
    counters["qualificationChainHits"] = len(
        chain_ids & {str(r.get("id")) for r in courses})

    convention_matches = []
    for row in courses:
        cid = str(row.get("id"))
        if not cid.startswith(CONVENTION_PREFIX):
            continue
        candidate = CONVENTION_TMPL.format(x=cid[len(CONVENTION_PREFIX):])
        if candidate in sprite_name_index:
            convention_matches.append({"courseId": cid,
                                       "spriteName": candidate})
    counters["conventionYield"] = len(convention_matches)

    inventory = sorted(n for n in sprite_name_index
                       if re.search(r"Courses[_-]T[_-]Icon", n))
    config_family_refs = []
    for row in configs:
        for ref in mu.walk_asset_guid_refs(row.get("fields") or {}):
            sub = ref["subObjectName"]
            if sub and COURSES_QUAL_FAMILY_RE.search(sub):
                config_family_refs.append({
                    "configId": str(row.get("id")),
                    "fieldPath": ref["fieldPath"],
                    "subObjectName": sub,
                })
    counters["courseRowsWalked"] = len(courses)
    counters["configRefsIntoFamily"] = len(config_family_refs)

    report = {
        "purpose": ("scout piece-06 §9 Q1 carrier probe — REPORT-ONLY "
                    "(arbiter-piece06 R3): the course-to-art carrier "
                    "question belongs to the data layer; consuming this "
                    "report into actual icons stays a non-goal routed to a "
                    "relink-piece revision"),
        "buildId": int(build_id),
        "courseRowsWalked": len(courses),
        "qualificationPptrPopulated": len(populated_ids),
        "qualificationPopulatedCourseIds": sorted(populated_ids),
        "courseConfigEdges": edge_count,
        "qualificationChainHits": counters["qualificationChainHits"],
        "strictConventionYield": {
            "template": CONVENTION_TMPL,
            "matched": len(convention_matches),
            "of": len(courses),
            "matches": convention_matches,
        },
        "coursesFamilySpriteInventory": {
            "regex": "Courses[_-]T[_-]Icon",
            "count": len(inventory),
            "names": inventory,
        },
        "configSideRefsIntoCoursesQualificationsFamily": {
            "count": len(config_family_refs),
            "rows": config_family_refs[:200],
        },
        "emissionPolicy": "none — this probe NEVER emits an icon (R3)",
    }
    out_path = extracted_root / "media" / "course-icon-carrier-report.json"
    return report, counters, out_path


# ---------------------------------------------------------------------------
# E6 — icon PPtr residue scan (canonical 122-basis, ALWAYS-ON)

def bundle_key(name: str) -> str:
    """Bare-stem lowercase key: stub rows spell source.bundle BARE while the
    R1 bridges key bundles by roster relpath — one normalizer joins them."""
    return mu.bundle_stem(str(name)).replace("\\", "/").rsplit("/", 1)[-1]         .lower()


def build_residue_indexes(cab_by_name, externals_index):
    """basename-keyed views over the R1 bridges for offline PPtr resolution."""
    externals_by_key = {bundle_key(b): tbl
                        for b, tbl in externals_index.items()}
    objects_by_key: dict[str, dict] = {}
    for entry in cab_by_name.values():
        objects_by_key.setdefault(bundle_key(entry["bundle"]), {}).update(
            entry["objects"])
    return externals_by_key, objects_by_key


def classify_residue_target(file_id: int, path_id: int, src_bundle: str,
                            leaf_name: str, externals_by_key,
                            objects_by_key, cab_by_name, scene_flags) -> str:
    """piece-02 §R3 verdict vocabulary + its non-entity address termination.
    Evidence-based and honest: without bridge evidence a slot stays
    unresolved-open rather than being guessed into resolution."""
    if file_id != 0 and path_id == 0:
        return "removed-content"       # external pointer naming no object
    key = bundle_key(src_bundle)
    if file_id == 0:
        # same-file target: any serialized file of the SOURCE bundle holding
        # this pathId is resolution evidence at offline granularity
        if path_id in objects_by_key.get(key, {}):
            return "resolved-address"
        if leaf_name.startswith("Editor"):
            return "resolved-editor-only"
        return "unresolved-open"
    table = externals_by_key.get(key) or {}
    cab = table.get(int(file_id))
    entry = cab_by_name.get(cab) if cab else None
    if entry is None:
        # unknown fileId / external whose CAB the bridges did not index —
        # an OPEN question (verifyB A7a: inner-CAB dependency walking), not
        # evidence of removal; engine-builtin paths stay removed-content
        if cab and ("builtin" in cab or "resource" in cab):
            return "removed-content"
        return "unresolved-open"
    if path_id in entry["objects"]:
        hosting = entry["bundle"]
        if scene_flags.get(hosting, "none") != "none":
            return "resolved-scene"
        return "resolved-address"
    if leaf_name.startswith("Editor"):
        return "resolved-editor-only"
    return "unresolved-open"


def run_e6_scan(stub_rows_by_kind, scene_flags, cab_by_name,
                externals_index, build_id: int):
    externals_by_key, objects_by_key = build_residue_indexes(
        cab_by_name, externals_index)
    """Population: nine kinds x ALL fields (the E1 walk WITHOUT the sprite
    type filter); vocabulary = case-insensitive `icon` substring on the LEAF
    NAME; admission = NON-null PPtr AND paired *Reference GUID empty/absent.
    The rule is canonical; the NUMBER follows the rule (seed 122@20226581,
    DRIFT on movement — never a silent constant, never a failure)."""
    rows: list[dict] = []
    drift: list[str] = []
    cc: Counter = Counter()
    for kind in STUB_KINDS:
        for row in stub_rows_by_kind[kind]:
            fields = row.get("fields") or {}
            for slot in mu.walk_pptr_slots(fields):
                cc["scanned"] += 1
                leaf = slot["leafName"]
                if not mu.is_icon_named(leaf):
                    continue
                fid, pid = slot["fileId"], slot["pathID"]
                if fid == 0 and pid == 0:
                    cc["nullSkipped"] += 1     # dead-weight majority
                    continue
                if not mu.paired_reference_empty(slot["parent"], leaf):
                    continue               # data rides the Reference plane
                src_bundle = str((row.get("source")
                                  or {}).get("bundle") or "")
                verdict = classify_residue_target(
                    fid, pid, src_bundle, leaf, externals_by_key,
                    objects_by_key, cab_by_name, scene_flags)
                row_out, row_drift = mu.make_residue_row(
                    kind, str(row.get("id")), slot["fieldPath"], fid, pid,
                    verdict, build_id)
                drift.extend(row_drift)
                rows.append(row_out)
                cc["external" if fid != 0 else "samefile"] += 1
                if verdict in ("resolved-address", "resolved-scene",
                               "resolved-editor-only"):
                    cc["targetResolved"] += 1
                elif verdict != "removed-content":
                    cc["targetUnresolved"] += 1
    rows.sort(key=lambda r: (r["kind"], r["srcId"], r["fieldPath"]))
    counters = Counter({
        "pptrSlotsScanned": cc["scanned"],
        "pptrSlotsNullSkipped": cc["nullSkipped"],
        "pptrResidueRows": len(rows),
        "pptrResidueExternalSubset": cc["external"],
        "pptrResidueSameFileSubset": cc["samefile"],
        "pptrTargetResolved": cc["targetResolved"],
        "pptrTargetUnresolved": cc["targetUnresolved"],
    })
    return rows, counters, drift


# ---------------------------------------------------------------------------
# _skipped_classes.jsonl — census carve-outs as rows (M19/M21)

def build_skipped_rows(extracted_root: Path, build_id: int):
    census_dir = extracted_root / "harvest" / "census" / "bundles"
    sums: Counter = Counter()
    census_files = 0
    if census_dir.is_dir():
        for fp in sorted(census_dir.glob("*.json")):
            try:
                data = json.loads(fp.read_text(encoding="utf-8"))
            except ValueError:
                continue
            census_files += 1
            for cls, n in (data.get("objectsByClass") or {}).items():
                sums[str(cls)] += int(n or 0)
    rows = []
    drift = []
    fresh_cubemap = sums.get("Cubemap", 0)
    fresh_t2da = sums.get("Texture2DArray", 0)
    seed_map = {cls: n for cls, n in mu.SEED_SKIP_CLASSES}
    if census_files and fresh_cubemap != seed_map["Cubemap"]:
        drift.append(f"DRIFT: Cubemap census measures {fresh_cubemap} "
                     f"(seed {seed_map['Cubemap']} @20226581)")
    if census_files and fresh_t2da != seed_map["Texture2DArray"]:
        drift.append(f"DRIFT: Texture2DArray census measures {fresh_t2da} "
                     f"(seed {seed_map['Texture2DArray']} @20226581)")
    zero_size = seed_map["Texture2D"]
    rows.append({
        "class": "Cubemap", "censusCount": fresh_cubemap,
        "policy": ("container-visible but catalogue-uncarved - census-only "
                   "carve-out; stage 11 never decodes cubemaps"),
        "buildId": int(build_id)})
    rows.append({
        "class": "Texture2DArray", "censusCount": fresh_t2da,
        "policy": ("container-visible but catalogue-uncarved - census-only "
                   "carve-out; stage 11 never decodes texture arrays"),
        "buildId": int(build_id)})
    rows.append({
        "class": "Texture2D", "censusCount": zero_size,
        "policy": ("zero-size font-atlas rows - pixel payload streams and "
                   "fonts stay out of scope (M19 seed carried @20226581; a "
                   "fresh count needs per-texture header reads, which would "
                   "be the forbidden corpus-wide sweep)"),
        "buildId": int(build_id)})
    rows.sort(key=lambda r: r["class"])
    return rows, drift


# ---------------------------------------------------------------------------
# EXTRACTION-LOG stage-defaults encoder-pin stamp (additive merge)

ENCODER_DEFAULTS_KEY = "mediaEncoder"


def stamp_encoder_defaults(extracted_root: Path, pins: dict) -> bool:
    defaults = log_util.read_stage_defaults(extracted_root)
    if defaults is None:
        return False
    if defaults.get(ENCODER_DEFAULTS_KEY) == pins:
        return False
    defaults[ENCODER_DEFAULTS_KEY] = pins
    log_path = log_util.log_path(extracted_root)
    text = log_path.read_text(encoding="utf-8")
    begin = text.index(log_util.STAGE_DEFAULTS_BEGIN)
    end = text.index(log_util.STAGE_DEFAULTS_END) + \
        len(log_util.STAGE_DEFAULTS_END)
    block = (log_util.STAGE_DEFAULTS_BEGIN + "\n```json\n"
             + json.dumps(defaults, ensure_ascii=False, sort_keys=True,
                          indent=2) + "\n```\n"
             + log_util.STAGE_DEFAULTS_END)
    log_util.atomic_write_text(log_path, text[:begin] + block + text[end:])
    return True


_CURRENT_BUILD_ID_VALUE = 0


# ---------------------------------------------------------------------------
# Orchestration

def parse_thumb_dims(raw: str) -> tuple[int, ...]:
    raw = str(raw or "").strip()
    if not raw:
        return ()
    dims = []
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        val = int(chunk)
        if val <= 0:
            raise mu.MediaError(f"--with-thumbs dims must be positive: {raw}",
                                exit_code=3)
        dims.append(val)
    return tuple(dims)


def seed_drift_lines(e1_counters, missing_rows, persisted_total) -> list[str]:
    drift = []
    if e1_counters["distinctNames"] != mu.SEED_DISTINCT_NAMES:
        drift.append(f"DRIFT: distinct referenced sprite names measure "
                     f"{e1_counters['distinctNames']} "
                     f"(seed {mu.SEED_DISTINCT_NAMES} @20226581)")
    if e1_counters["resolvedNames"] != mu.SEED_RESOLVED_NAMES:
        drift.append(f"DRIFT: resolved sprite names measure "
                     f"{e1_counters['resolvedNames']} "
                     f"(seed {mu.SEED_RESOLVED_NAMES} @20226581)")
    fresh_missing = sorted(
        g["subObjectName"] for g in missing_seed_param
        if g["subObjectName"] and g["reason"] in
        (mu.REASON_DLC_ABSENT, mu.REASON_STALE_NAME))
    seed_missing = sorted(mu.SEED_MISSING_NAMES)
    if fresh_missing != seed_missing:
        drift.append("DRIFT: unresolved-name set differs from the M16 seed "
                     f"({len(fresh_missing)} fresh vs {len(seed_missing)} "
                     "seeded)")
    rs = e1_counters["routeSplit"]
    if rs["atlas-pair"] != mu.SEED_ATLAS_ROUTE_REFS:
        drift.append(f"DRIFT: atlas-route refs measure {rs['atlas-pair']} "
                     f"(seed {mu.SEED_ATLAS_ROUTE_REFS} @20226581)")
    if rs["spriteTypedTotal"] != mu.SEED_SPRITE_TYPED_REFS:
        drift.append(f"DRIFT: sprite-typed refs measure "
                     f"{rs['spriteTypedTotal']} "
                     f"(seed {mu.SEED_SPRITE_TYPED_REFS} @20226581)")
    if persisted_total != mu.SEED_ENTITY_ASSET_GUID_ROWS:
        drift.append(f"DRIFT: entity_asset_guid.jsonl holds {persisted_total} "
                     f"rows (seed {mu.SEED_ENTITY_ASSET_GUID_ROWS})")
    return drift


def per_kind_cell_map(row_cells, ref_cells) -> dict:
    """M5 per-kind cells. The `rows w/ non-empty refs` column carries a MIXED
    measurement basis in the seed table itself (verifyA recount: the same
    column measures 124 on unlockables when empty reference FIELDS count;
    M5 keeps the non-empty 63 while items/configs/etc. reproduce ONLY on the
    field-shape basis). Both bases are emitted fresh; the seed reconciles
    against whichever it was measured on."""
    out = {}
    for kind in STUB_KINDS:
        rc, fc = row_cells[kind], ref_cells[kind]
        out[kind] = {
            "rows": rc.get("rows", 0),
            "rowsWithRefs": rc.get("rowsWithRefs", 0),
            "rowsWithRefFields": rc.get("rowsWithRefFields", 0),
            "guidRefs": rc.get("guidRefs", 0),
            "spriteTypedTargets": fc.get("spriteTyped", 0),
            "dangling": fc.get("dangling", 0),
        }
    return out


def kind_seed_drift(cell_map) -> list[str]:
    drift = []
    for kind, seed in sorted(mu.SEED_PER_KIND_CELLS.items()):
        fresh = cell_map.get(kind)
        if fresh is None:
            continue
        got_nonempty = (fresh["rows"], fresh["rowsWithRefs"],
                        fresh["guidRefs"], fresh["spriteTypedTargets"],
                        fresh["dangling"])
        got_anyshape = (fresh["rows"], fresh["rowsWithRefFields"],
                        fresh["guidRefs"], fresh["spriteTypedTargets"],
                        fresh["dangling"])
        if tuple(seed) not in (got_nonempty, got_anyshape):
            drift.append(f"DRIFT: per-kind cell {kind} measures "
                         f"{got_nonempty}/{got_anyshape} "
                         f"(M5 seed {tuple(seed)})")
    return drift


def run(extracted_root: Path, game_root: Path | None, opts) -> int:
    global _CURRENT_BUILD_ID_VALUE
    log_util.bootstrap_console()
    extracted_root = Path(extracted_root)
    media_dir = extracted_root / "media"
    build_id = load_build_id(extracted_root)
    _CURRENT_BUILD_ID_VALUE = int(build_id)
    opts.thumb_dims = parse_thumb_dims(opts.with_thumbs)
    drift: list[str] = []

    # ---- upstream artifacts (exit 3 naming them while the game dir resolves;
    #      in --join-only the fixture tree carries them)
    stubs_dir = extracted_root / "stubs"
    stub_rows = load_stub_rows(stubs_dir)
    sprite_index = mu.load_sprite_name_index(
        extracted_root / "media-catalogue.jsonl")
    catalog_guid_index = mu.load_catalog_guid_index(
        extracted_root / "addressables" / "catalog.json")
    container_index = mu.load_container_index(extracted_root)
    scene_flags = load_roster_scene_flags(extracted_root)
    cab_by_name = mu.load_cab_index(extracted_root)
    externals_path = extracted_root / "harvest" / "externals.jsonl"
    externals_index = mu.load_externals_index(externals_path) \
        if externals_path.is_file() else {}
    entity_rows = mu.read_jsonl_rows(
        extracted_root / "relinks" / "entity_asset_guid.jsonl",
        required=False)
    persisted_total = len(entity_rows)
    persisted_sub = sum(
        1 for r in entity_rows
        if ((r.get("subObjectName")
             or (r.get("evidence") or {}).get("subObjectName") or "").strip()))

    # ---- S0 scratch discipline (runs FIRST)
    temp_root = mu.resolve_temp_root(opts.temp_root, extracted_root)
    join_only = bool(opts.join_only)
    if join_only:
        s0 = {
            "tempRoot": str(temp_root),
            "tempRootDrive": mu.drive_of(temp_root),
            "outputRootDrive": mu.drive_of(extracted_root),
            "tempFreeGiB": round(mu.free_gib(temp_root), 3),
            "outputFreeGiB": round(mu.free_gib(extracted_root), 3),
        }
        pages_dir = None
        cli_dir = None
    else:
        s0 = mu.s0_preflight(temp_root, extracted_root)
        pages_dir = temp_root / "pages"
        cli_dir = temp_root / "cli-export"

    try:
        return _run_body(extracted_root, media_dir, game_root, opts,
                         build_id, stub_rows, sprite_index,
                         catalog_guid_index, container_index, scene_flags,
                         cab_by_name, externals_index, persisted_total,
                         persisted_sub, s0, temp_root, pages_dir, cli_dir,
                         join_only, drift)
    finally:
        if not join_only and temp_root.is_dir():
            import shutil  # noqa: PLC0415
            shutil.rmtree(temp_root, ignore_errors=True)


def _run_body(extracted_root, media_dir, game_root, opts, build_id,
              stub_rows, sprite_index, catalog_guid_index, container_index,
              scene_flags, cab_by_name, externals_index, persisted_total,
              persisted_sub, s0, temp_root, pages_dir, cli_dir, join_only,
              drift):
    problems: list[str] = []

    # ---- E1 join ---------------------------------------------------------
    web_dir = media_dir / "web"
    refs = walk_all_refs(stub_rows, catalog_guid_index, container_index)
    index_entries, missing_groups, plans, e1_counters, ref_cells, e1_drift = \
        run_e1_join(refs, sprite_index, persisted_sub, persisted_total,
                    build_id)
    row_cells = run_e1_cells(stub_rows)
    cell_map = per_kind_cell_map(row_cells, ref_cells)
    drift.extend(e1_drift)
    drift.extend(kind_seed_drift(cell_map))
    stem_plans = assign_out_paths(plans)

    manifest_rows: list[dict] = []
    e2c: Counter = Counter()
    e3c: Counter = Counter()
    e5c = None
    e5_report_path = None
    e4c = None
    crosscheck_report = {"ran": False,
                         "reason": "join-only lane (decode legs not run)"}
    pool = None

    if not join_only:
        web_dir.mkdir(parents=True, exist_ok=True)
        pool = BundlePool(game_root, extracted_root)
        page_cache = mu.PageCache(pages_dir)
        manifest_rows, emitters = emit_plans(
            stem_plans, pool, page_cache, media_dir, opts, build_id)
        e2c.update(emitters)
        for plan in stem_plans.values():
            if plan["identity"][0] == "standalone":
                e2c["standaloneRefs"] += plan["refs"]
                if plan.get("namedBy") == "address-basename":
                    e2c["emptySubNamedByAddress"] += plan["refs"]
            if plan.get("route") == mu.ROUTE_PASS_THROUGH:
                e2c["passThroughSprites"] += 1
            elif plan.get("route") == mu.ROUTE_DIRECT_POINTER:
                e2c["subrectSprites"] += 1
        # index rows learn their canonical output now (many-to-one mapping)
        file_by_plan = {}
        for r in manifest_rows:
            pk = _plan_key_of_stem(stem_plans, r)
            if pk is not None and pk not in file_by_plan:
                file_by_plan[pk] = r["outRelPath"]
        for row, plan_key in index_entries:
            if row["resolved"] and plan_key in file_by_plan:
                row["file"] = file_by_plan[plan_key]
        e3c["pagesDecoded"] = getattr(page_cache, "decoded", 0)

        # ---- E3 (flag-gated; arbiter R2 keeps v1 OFF) --------------------
        if opts.include_ui_chrome:
            emitted_stems = {r["outRelPath"].rsplit("/", 1)[-1].rsplit(".", 1)[0]
                             for r in manifest_rows}
            ui_rows, e3c_ui = run_e3_ui_chrome(
                pool, page_cache, sprite_index, emitted_stems, media_dir,
                opts, build_id, container_index)
            manifest_rows.extend(ui_rows)
            e3c.update(e3c_ui)
            e3c["pagesDecoded"] = getattr(page_cache, "decoded", 0)

        # ---- E4(3) cross-check lane --------------------------------------
        sample = mu.compose_crosscheck_sample(stem_plans,
                                              min_total=max(
                                                  mu.CROSSCHECK_MIN_SAMPLE * 2,
                                                  len(stem_plans)))
        cli_exe = mu.resolve_cli_exe(extracted_root)
        cc_report = run_crosscheck(sample, stem_plans, pool, page_cache,
                                   cli_exe, cli_dir, extracted_root,
                                   build_id)
        crosscheck_report = cc_report
        e4c = {
            "nullTexturePointersPaired": e2c.get("nullTexturePointersPaired", 0),
            "ambiguousPairings": e2c.get("ambiguousPairings", 0),
            "pairingFailures": 0,
            "crossCheckSample": cc_report["sampleSize"],
            "pixelMatchRate": cc_report["pixelMatchRate"],
            "maxDelta": cc_report["maxDelta"],
            "cliVersion": cc_report["cliVersion"],
            "cliUnityVersion": cc_report["cliUnityVersion"],
            "cliExportFormat": cc_report["cliExportFormat"],
        }

    # ---- ledgers ----------------------------------------------------------
    missing_rows = sorted(missing_groups.values(),
                          key=lambda r: (r["subObjectName"], r["reason"],
                                         r["assetGuid"]))
    for row in missing_rows:
        mu.validate_missing_row(row)
    index_rows = [row for row, _pk in index_entries]
    index_rows.sort(key=lambda r: (r["kind"], r["srcId"], r["fieldPath"]))
    for row in index_rows:
        mu.validate_index_row(row)
    skipped_rows, skip_drift = build_skipped_rows(extracted_root, build_id)
    drift.extend(skip_drift)
    residue_rows, e6_counters, e6_drift = run_e6_scan(
        stub_rows, scene_flags, cab_by_name, externals_index, build_id)
    drift.extend(e6_drift)
    # rule-canonical / number-follows-rule seed policy (E6(2)): the fresh
    # measurement becomes the recorded seed going forward
    if e6_counters["pptrResidueRows"] != mu.SEED_E6_TOTAL:
        drift.append(f"DRIFT: E6 canonical scan measures "
                     f"{e6_counters['pptrResidueRows']} icon-named non-null "
                     f"PPtr slots (seed {mu.SEED_E6_TOTAL} @20226581)")
    if e6_counters["pptrResidueExternalSubset"] != mu.SEED_E6_EXTERNAL:
        drift.append(f"DRIFT: E6 external subset measures "
                     f"{e6_counters['pptrResidueExternalSubset']} "
                     f"(seed {mu.SEED_E6_EXTERNAL})")

    manifest_rows.sort(key=lambda r: r["outRelPath"])
    for row in manifest_rows:
        mu.validate_manifest_row(row)
    log_util.write_jsonl(media_dir / "export-manifest.jsonl",
                        manifest_rows)
    log_util.write_jsonl(media_dir / "_missing_icons.jsonl", missing_rows)
    log_util.write_jsonl(media_dir / "index.jsonl", index_rows)
    log_util.write_jsonl(media_dir / "_skipped_classes.jsonl", skipped_rows)
    log_util.write_jsonl(media_dir / "_pptr_residue.jsonl", residue_rows)

    # ---- E5 carrier probe (flag-gated, report-only) -----------------------
    if opts.probe_course_carrier:
        e5_report, e5c, e5_report_path = run_e5_probe(
            extracted_root, stub_rows, sprite_index, build_id)
        log_util.write_json(e5_report_path, e5_report)

    env_pins = mu.pil_versions()
    env_pins["fallbackVersionUsedBundles"] = (
        len(pool.fallback_seeded) if pool is not None else 0)

    # ---- real-mode artifacts (hashes, ceilings, tracked layer) ------------
    if not join_only:
        entries = mu.tree_hash_entries(web_dir)
        # relpaths share the export-manifest namespace (web/-rooted) so
        # one vocabulary spans binaries + provenance
        mu.write_hashes_sha256(media_dir / "hashes.sha256",
                              [("web/" + rel, sha) for rel, sha in entries])
        web_bytes = sum(r["bytes"] for r in manifest_rows)
        ceiling_mib = (mu.SCOPE_CEILING_MIB_UI_CHROME
                       if opts.include_ui_chrome
                       else mu.SCOPE_CEILING_MIB_DEFAULT)
        if web_bytes > ceiling_mib * 1024 * 1024:
            raise mu.MediaError(
                f"scope ceiling breached: web/ totals {web_bytes} B > "
                f"{ceiling_mib} MiB — accidental bulk decode suspected",
                exit_code=1)
        # bundle-containment proof (AC7): no corpus-wide sweep slipped in
        opened = set(pool.opened.keys())
        for r in manifest_rows:
            src = r["source"]
            if src["bundle"] not in opened:
                raise mu.MediaError(
                    f"containment breach: manifest row {r['outRelPath']} "
                    f"names unopened bundle {src['bundle']}", exit_code=1)
            pb = src.get("pageBundle")
            if pb and pb not in opened:
                raise mu.MediaError(
                    f"containment breach: manifest row {r['outRelPath']} "
                    f"names unopened page bundle {pb}", exit_code=1)
        log_util.write_json(media_dir / "crosscheck-report.json",
                            crosscheck_report)
        stamp_encoder_defaults(extracted_root, {
            "pillowVersion": env_pins["pillowVersion"],
            "webpFeatureVersion": env_pins["webpFeatureVersion"],
            "quality": mu.WEBP_QUALITY,
            "pngTwinMaxDim": mu.PNG_TWIN_MAX_DIM,
            "alphaTolerance": mu.ALPHA_TOLERANCE,
        })

    # ---- MEDIA-EXPORT.md (THE tracked artifact) ---------------------------
    hash_summary = []
    for name, rows_n in (("export-manifest.jsonl", len(manifest_rows)),
                         ("index.jsonl", len(index_rows)),
                         ("_missing_icons.jsonl", len(missing_rows)),
                         ("_pptr_residue.jsonl", len(residue_rows)),
                         ("_skipped_classes.jsonl", len(skipped_rows))):
        p = media_dir / name
        if p.is_file():
            hash_summary.append({
                "artifact": name,
                "sha256": log_util.sha256_file(p),
                "count": f"{rows_n} rows"})
    hpath = media_dir / "hashes.sha256"
    if hpath.is_file() and not join_only:
        hash_summary.append({
            "artifact": "hashes.sha256",
            "sha256": log_util.sha256_file(hpath),
            "count": f"{len(entries)} files"})
    ccp = media_dir / "crosscheck-report.json"
    if ccp.is_file():
        hash_summary.append({
            "artifact": "crosscheck-report.json",
            "sha256": log_util.sha256_file(ccp),
            "count": "1 object"})
    if join_only:
        web_summary = []
    else:
        web_files = sum(1 for _rel, _sha in entries)
        web_total = sum(r["bytes"] for r in manifest_rows)
        web_summary = [{"icons+thumbs+ui": {
            "files": web_files, "bytes": web_total}}]
    planes: dict[str, dict] = {}
    if not join_only:
        for r in manifest_rows:
            st = planes.setdefault(r["plane"], {"files": 0, "bytes": 0})
            st["files"] += 1
            st["bytes"] += r["bytes"]
    md_text = mu.render_media_export_md({
        "buildId": build_id,
        "uiChrome": bool(opts.include_ui_chrome),
        "courseProbe": bool(opts.probe_course_carrier),
        "env": {
            "pillowVersion": env_pins["pillowVersion"],
            "webpFeatureVersion": env_pins["webpFeatureVersion"],
            "fallbackUnityVersion": _fallback_version_note(extracted_root),
            "fallbackVersionUsedBundles":
                env_pins["fallbackVersionUsedBundles"],
        },
        "counters": {
            "E1.distinctNames": e1_counters["distinctNames"],
            "E1.resolvedNames": e1_counters["resolvedNames"],
            "E1.unresolvedNames": e1_counters["unresolvedNames"],
            "E1.refsTotal": e1_counters["refsTotal"],
            "E1.routeSplit": e1_counters["routeSplit"],
            "E2.spritesEmitted": e2c.get("spritesEmitted", 0),
            "E2.pngTwins": e2c.get("pngTwins", 0),
            "E2.alphaSanityFallbacks": e2c.get("alphaSanityFallbacks", 0),
            "E3.cropsEmitted": e3c.get("cropsEmitted", 0),
            "E3.skippedAsAlreadyEmitted":
                e3c.get("skippedAsAlreadyEmitted", 0),
            "E4.nullTexturePointersPaired":
                (e4c or {}).get("nullTexturePointersPaired", 0),
            "E4.ambiguousPairings": (e4c or {}).get("ambiguousPairings", 0),
            "E6.pptrResidueRows": e6_counters["pptrResidueRows"],
        },
        "planes": planes,
        "perKindIndexRows": {k: sum(1 for r in index_rows if r["kind"] == k)
                             for k in STUB_KINDS},
        "ledgers": {
            "missing": len(missing_rows),
            "residue": len(residue_rows),
            "skipped": len(skipped_rows),
        },
        "hashSummary": hash_summary + [
            {"artifact": "web/", "sha256": "(see hashes.sha256)",
             "count": json.dumps(ws)} for ws in web_summary],
        "crosscheck": {
            "ran": bool(crosscheck_report.get("ran")),
            "reason": crosscheck_report.get("reason"),
            "cliVersion": crosscheck_report.get("cliVersion"),
            "cliUnityVersion": crosscheck_report.get("cliUnityVersion"),
            "cliExportFormat": crosscheck_report.get("cliExportFormat"),
            "sample": crosscheck_report.get("sampleSize"),
            "pixelMatchRate": crosscheck_report.get("pixelMatchRate"),
            "maxDelta": crosscheck_report.get("maxDelta"),
            "pass": crosscheck_report.get("pass"),
        },
    })
    log_util.atomic_write_text(media_dir / "MEDIA-EXPORT.md", md_text)

    # ---- exit-code assembly (EC table) -------------------------------------
    contributors = []
    escape_rows = sum(1 for r in missing_rows
                      if r["reason"] == mu.ESCAPE_REASON)
    escape_slots = sum(1 for r in residue_rows
                       if r["slotClass"] == mu.ESCAPE_SLOT
                       or r["targetResolution"] == mu.ESCAPE_SLOT)
    if missing_rows:
        contributors.append(f"_missing_icons.jsonl rows={len(missing_rows)}")
    if escape_rows:
        contributors.append(f"uncategorized-reason escape rows={escape_rows}")
    if residue_rows:
        contributors.append(f"_pptr_residue.jsonl rows={len(residue_rows)}")
    if escape_slots:
        contributors.append(f"uncategorized-slot escape rows={escape_slots}")

    if problems:
        exit_code = 1
    elif contributors:
        exit_code = 2
    else:
        exit_code = 0

    lines = run_section_lines(
        s0, e1_counters, cell_map, manifest_rows, e2c, e3c, e4c, e5c,
        e5_report_path, e6_counters, env_pins, drift, problems, contributors,
        join_only, opts)
    lines[0] = (
        f"- exitCode: {exit_code}" if not problems
        else f"- exitCode: 1 ({'; '.join(problems)})")
    log_util.append_run_section(extracted_root, STAGE_ID, lines)

    print(f"[{STAGE_ID}] E1 names={e1_counters['resolvedNames']}/"
          f"{e1_counters['distinctNames']} refs={e1_counters['refsTotal']} "
          f"sprites={e2c.get('spritesEmitted', 0)} "
          f"(pngTwins={e2c.get('pngTwins', 0)}, alphaFb="
          f"{e2c.get('alphaSanityFallbacks', 0)})")
    print(f"[{STAGE_ID}] ledgers: missing={len(missing_rows)} "
          f"residue={len(residue_rows)} skipped={len(skipped_rows)}")
    for d in drift[-8:]:
        print(f"[{STAGE_ID}] {d}", file=sys.stderr)
    for p in problems:
        print(f"[{STAGE_ID}] PROBLEM: {p}", file=sys.stderr)
    return exit_code


def _fallback_version_note(extracted_root: Path) -> str:
    identity = extracted_root / "identity.json"
    if identity.is_file():
        try:
            data = json.loads(identity.read_text(encoding="utf-8"))
            ver = data.get("unityVersion")
            if isinstance(ver, str) and ver.strip():
                return ver.strip()
        except ValueError:
            pass
    return "n/a"


def _plan_key_of_stem(stem_plans, manifest_row):
    """Reverse lookup: which plan produced this manifest row (by its primary
    outRelPath)? Only icons-plane .webp primaries identify a plan — twins
    and thumbs map onto their plan through the same stem."""
    if manifest_row.get("plane") != "icons"             or manifest_row.get("format") != "webp":
        return None
    name = manifest_row["outRelPath"].rsplit("/", 1)[-1]
    stem = name.rsplit(".", 1)[0]
    plan = stem_plans.get(stem)
    return plan["identity"] if plan else None


# ---------------------------------------------------------------------------
# Run-section assembly (key names PINNED per pass — spec §3)

def run_section_lines(s0, e1_counters, cell_map, manifest_rows, e2c, e3c,
                      e4c, e5c, e5_report_path, e6c, env_pins, drift_lines,
                      problems, contributors, join_only, opts) -> list[str]:
    mode_note = (" (join-only lane: decode-scoped S0 gates measured, not "
                 "enforced — no scratch created)" if join_only else "")
    lines = ["- exitCode: pending"]
    if s0 is not None:
        lines.append(
            f"- S0: tempRoot={s0['tempRoot']} "
            f"tempRootDrive={s0['tempRootDrive']} "
            f"outputRootDrive={s0['outputRootDrive']} "
            f"tempFreeGiB={s0['tempFreeGiB']} "
            f"outputFreeGiB={s0['outputFreeGiB']}{mode_note}")
    walk_vs = e1_counters["entityAssetGuidWalkVsPersisted"]
    lines.append(
        "- E1: refsTotal={refsTotal} distinctNames={distinctNames} "
        "resolvedNames={resolvedNames} unresolvedNames={unresolvedNames} "
        "perKindCells={cells} routeSplit={rsplit} spritesEmitted={spr} "
        "pngTwins={twins} alphaSanityFallbacks={alpha} "
        "entityAssetGuidWalkVsPersisted={{\"walk\": {walk}, "
        "\"persistedSub\": {psub}, \"persistedTotal\": {ptot}}}".format(
            refsTotal=e1_counters["refsTotal"],
            distinctNames=e1_counters["distinctNames"],
            resolvedNames=e1_counters["resolvedNames"],
            unresolvedNames=e1_counters["unresolvedNames"],
            cells=json.dumps(cell_map, sort_keys=True),
            rsplit=json.dumps(e1_counters["routeSplit"], sort_keys=True),
            spr=e2c.get("spritesEmitted", 0),
            twins=e2c.get("pngTwins", 0),
            alpha=e2c.get("alphaSanityFallbacks", 0),
            walk=walk_vs["walk"], psub=walk_vs["persistedSub"],
            ptot=walk_vs["persistedTotal"]))
    lines.append(
        "- E2: standaloneRefs={sa} passThroughSprites={pt} "
        "subrectSprites={sr} emptySubNamedByAddress={es}".format(
            sa=e2c.get("standaloneRefs", 0),
            pt=e2c.get("passThroughSprites", 0),
            sr=e2c.get("subrectSprites", 0),
            es=e2c.get("emptySubNamedByAddress", 0)))
    if opts.include_ui_chrome:
        lines.append(
            "- E3: atlasesProcessed={ap} pagesDecoded={pd} cropsEmitted={ce}"
            " skippedAsAlreadyEmitted={sk}".format(
                ap=e3c.get("atlasesProcessed", 0),
                pd=e3c.get("pagesDecoded", 0),
                ce=e3c.get("cropsEmitted", 0),
                sk=e3c.get("skippedAsAlreadyEmitted", 0)))
    if e4c is not None:
        lines.append(
            "- E4: nullTexturePointersPaired={np} ambiguousPairings={am} "
            "pairingFailures={pf} crossCheckSample={cs} "
            "pixelMatchRate={pmr} maxDelta={md} cliVersion={cv} "
            "cliUnityVersion={cu} cliExportFormat={cf}".format(
                np=e4c["nullTexturePointersPaired"],
                am=e4c["ambiguousPairings"], pf=e4c["pairingFailures"],
                cs=e4c["crossCheckSample"], pmr=e4c["pixelMatchRate"],
                md=e4c["maxDelta"], cv=e4c["cliVersion"],
                cu=e4c["cliUnityVersion"], cf=e4c["cliExportFormat"]))
    if opts.probe_course_carrier and e5c is not None:
        lines.append(
            "- E5: courseRowsWalked={cw} qualificationChainHits={qh} "
            "conventionYield={cy} pptrPopulated={pp} reportPath={rp}".format(
                cw=e5c.get("courseRowsWalked", 0),
                qh=e5c.get("qualificationChainHits", 0),
                cy=e5c.get("conventionYield", 0),
                pp=e5c.get("pptrPopulated", 0),
                rp=e5_report_path))
    lines.append(
        "- E6: pptrSlotsScanned={sc} pptrSlotsNullSkipped={ns} "
        "pptrResidueRows={rr} pptrResidueExternalSubset={ex} "
        "pptrResidueSameFileSubset={sf} pptrTargetResolved={tr} "
        "pptrTargetUnresolved={tu}".format(
            sc=e6c.get("pptrSlotsScanned", 0),
            ns=e6c.get("pptrSlotsNullSkipped", 0),
            rr=e6c.get("pptrResidueRows", 0),
            ex=e6c.get("pptrResidueExternalSubset", 0),
            sf=e6c.get("pptrResidueSameFileSubset", 0),
            tr=e6c.get("pptrTargetResolved", 0),
            tu=e6c.get("pptrTargetUnresolved", 0)))
    lines.append(
        "- env: pillowVersion={pv} webpFeatureVersion={wv} "
        "fallbackVersionUsedBundles={fb}".format(
            pv=env_pins.get("pillowVersion"),
            wv=env_pins.get("webpFeatureVersion"),
            fb=env_pins.get("fallbackVersionUsedBundles", 0)))
    lines.extend(f"- {d}" for d in drift_lines)
    lines.extend(f"- PROBLEM: {p}" for p in problems)
    if contributors and not problems:
        lines.append("- LEDGER-CONTRIBUTORS (exit 2): "
                     + "; ".join(contributors))
    return lines


# ---------------------------------------------------------------------------
# Entrypoint

def main(argv=None) -> int:
    log_util.bootstrap_console()
    parser = argparse.ArgumentParser(
        description="stage 11 — media export (piece-06): entity icons via "
                    "catalog-GUID/container-index/media-catalogue join, "
                    "atlas crops per the m_RD.textureRect grammar, pixel-"
                    "exact AssetStudioModCLI cross-check, residue ledgers")
    parser.add_argument("game_dir", nargs="?", default=None,
                        help="install root or TPC_Data child "
                             "(default $TPC_GAME_DIR; UNRESOLVABLE means "
                             "wholesale auto-SKIP — client-gated stage, "
                             "binding pin P1)")
    parser.add_argument("--extracted-root", default=None)
    parser.add_argument("--temp-root", default=None,
                        help="decode scratch root ($TPC_MEDIA_TMP > "
                             "$TPC_TEMP_ROOT > <extracted>/.tmp-stage11); "
                             "a C: resolution refuses with exit 3")
    parser.add_argument("--include-ui-chrome", action="store_true",
                        help="E3: crop ALL SpriteAtlas packed slots "
                             "(default OFF — arbiter R2)")
    parser.add_argument("--probe-course-carrier", action="store_true",
                        help="E5: report-only course-icon carrier probe "
                             "(default OFF; NEVER emits an icon — R3)")
    parser.add_argument("--with-thumbs", default="",
                        help='derived thumbnail tier, e.g. "96,128" '
                             "(default off)")
    parser.add_argument("--png-all", action="store_true",
                        help="emit a PNG twin for every sprite (site-plane "
                             "worst-case escape hatch)")
    parser.add_argument("--join-only", action="store_true",
                        help="HOSTLESS LANE: run the E1/E6 join machinery "
                             "over landed artifacts ONLY — zero bundle "
                             "opens, zero decodes; emits index.jsonl + "
                             "_missing_icons.jsonl + _pptr_residue.jsonl")
    args = parser.parse_args(argv)

    pack_dir = tc.resolve_pack_dir()
    extracted_root = tc.resolve_extracted_root(pack_dir)
    if args.extracted_root:
        extracted_root = Path(args.extracted_root).resolve()

    game_root = None
    if not args.join_only:
        game_root = resolve_media_game_root(args.game_dir)
        if game_root is None:
            print(f"[{STAGE_ID}] SKIP (client-gated wholesale): neither "
                  "$TPC_GAME_DIR nor the default install resolves — no "
                  "partial outputs written, no degraded join run (pin P1)")
            return 0

    try:
        return run(extracted_root, game_root, args)
    except tc.StageError as exc:
        log_util.append_failure_section(extracted_root, STAGE_ID,
                                        exc.exit_code, [str(exc)])
        print(f"[{STAGE_ID}] ERROR: {exc}", file=sys.stderr)
        return exc.exit_code


if __name__ == "__main__":
    sys.exit(main())
