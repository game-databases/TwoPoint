# Two Point Campus — Game Spec (template v2.2; DRAFT 2026-08-24)

Filled from the verified research pack (`docs/scout-report-001.mdx` +
`docs/verifications/`) by documentator-001. Entity kinds below are seeded
from bundle-name families and are **PROVISIONAL** until pipeline piece 1
opens the bundles (stage 2 catalog + stage 3 dumps confirm or replace
them). Spec freezes after Tier 0 closes those gaps ([FRAMEWORK §7]
step 2). Facts are measured-on-disk unless marked otherwise.

```yaml
game: Two Point Campus
folder: TwoPoint
tier: OWNER-ITEM                  # D3 owner-only; QUESTION-QUEUE #1. Localhost-first proceeds regardless.
lifecycle: live                   # shipped, purchasable title; content-complete; last client update 2025-12-19
domain: OWNER-ITEM                # hub path TBD; production deploy waits on owner (domain-doctrine tiers)
stack: next                       # §2.20 default profile — Next.js App Router + React 19 + TS

identity:
  steam:
    apps:
      - { appid: 1649080, role: primary, lifecycle: live }   # buildid 20226581 = TargetBuildID (install at target)
      - { appid: 1884560, role: dlc }    # depot 1884561 — "Space Academy" (public name VERIFIED-FROM-STOREFRONT
                                         #   2026-08-25) → installed at DLCs/space/ (dlc1_* scenes)
      - { appid: 1907450, role: dlc }    # depot 1907451 — "School Spirits" (VERIFIED-FROM-STOREFRONT 2026-08-25)
                                         #   → installed at DLCs/ghost/ (dlc2_ghosts_optimised)
      - { appid: 2312070, role: dlc, owned: no }   # "Two Point Campus Soundtrack" — storefront-listed, not installed
      - { appid: 2195430, role: dlc, owned: no }   # "Medical School" — catalog-KNOWN (base catalog references
                                                   #   dlc-hospital-* bundles out-of-roster) but not owned;
                                                   #   acquisition is QUESTION-QUEUE #3 (non-blocking)
    # Dir-codename note: Steam's internal dir codenames do NOT track marketing names here —
    # DLCs/space/ carries Space Academy (1884560), DLCs/ghost/ carries School Spirits (1907450);
    # the association is measured from bundle content, never from the codename.
    store-cc: us                    # appdetails FIRED 2026-08-25 (locale corroboration + DLC public names;
                                    #   raw at data/sources/steam-appdetails-1649080.json, MANIFEST row appended)

locales:                          # §2.4 launch-blocking — VERIFIED-FROM-CLIENT 2026-08-24 (14 loc bundles on disk)
  official: [en, pt-BR, zh-Hans, zh-Hant, fr, de, it, ja, ko, pl, ru, es, tr]   # 13 text locales
  canonical: en                   # pivot at bare paths per [DR-2026-08-20-locale-urls]
  ui-locales: []                  # none identified
  community: []                   # none declared
  source-per-locale:
    all: client-extraction        # one localisation_assets_localisation*.bundle per locale (stage 4)
  base-overlay: >-
    a 14th unnamed bundle localisation_assets_localisation.bundle ships beside the 13;
    existence VERIFIED-FROM-CLIENT, semantics (shared key registry vs default-string table)
    resolved as a stage-4 output — not a 14th locale
  locale-cells: spoken audio in exactly 3 languages (english, german, mandarin radio/tannoy bundles);
    mandarin voice maps to BOTH zh-Hans and zh-Hant text — voice availability never inferred from text support

axes:
  regions: []                     # single-player offline — no shards
  platforms: [pc-windows]         # Steam Windows x64 install is the sole acquired cell
  version-eras: [10.3-2024-12]    # one era on disk; per-row buildid stamps if a patch ever lands
  game-modes: [campaign, sandbox] # sandbox/remix scenes present in aa roster (scenes_scenes_sandbox, _remix)
  variant-axes:
    content: [base, dlc1-space, dlc2-ghost]   # DLC bundles live OUTSIDE StreamingAssets in DLCs/{space,ghost}/

entities:                         # ALL KINDS PROVISIONAL until stages 2–5 open the bundles
  item:            { key: game-id, sources: [{ class: client-extraction, container: UnityFS,
                     readiness: on-disk, family-hint: "items-general, items-courses-*_assets_all" }] }
  room:            { key: game-id, sources: [{ class: client-extraction, container: UnityFS,
                     readiness: on-disk, family-hint: "rooms_assets_all (137 MiB)" }] }
  course:          { key: game-id, sources: [{ class: client-extraction, container: UnityFS,
                     readiness: on-disk, family-hint: "items-courses-* + animations-character-courses" }] }
  staff:           { key: game-id, sources: [{ class: client-extraction, container: UnityFS,
                     readiness: unverified, family-hint: "character-shared*, staff-named families expected in catalog" }] }
  student-type:    { key: game-id, sources: [{ class: client-extraction, container: UnityFS,
                     readiness: unverified, family-hint: "character-* bundles + configs" }] }
  unlockable:      { key: game-id, sources: [{ class: client-extraction, container: UnityFS,
                     readiness: on-disk, family-hint: "unlockables_assets_all (146 MiB)" }] }
  campus-level:    { key: game-id, sources: [{ class: client-extraction, container: UnityFS,
                     readiness: on-disk, family-hint: "12 base *_optimised.unity + 3 dlc1 + 1 dlc2 scenes +
                     scenes_scenes_config_level_databases.unity (machine-readable level DB)" }] }
  config:          { key: game-id, sources: [{ class: client-extraction, container: UnityFS,
                     readiness: on-disk, family-hint: "configs_assets_all, configs-app/common/metagame/levels-prefabs" }] }
  metagame-node:   { key: game-id, sources: [{ class: client-extraction, container: UnityFS,
                     readiness: unverified, family-hint: "configs-metagame (research tree / progression expected)" }] }

relations:                        # PROVISIONAL pair seeds — full ordered-pair matrix lands in pieces ≥2 [DR-2026-08-17-relink]
  - course ↔ room ↔ item (requirement chains; the site's core join)
  - course ↔ campus-level (which course runs where)
  - staff ↔ course (trait/speed edges expected)
  - student-type ↔ course ↔ need (happiness/grade model from configs)
  - unlockable ↔ item/room/decoration (Kudosh-purchased vs earned)
  - metagame-node ↔ course/room (research/unlock tree)
  - entity ↔ locale-string (loc-key joins, every kind)

maps:                             # §2.6 — path D primary (FRAMEWORK §2.6 evidence rows MIR4/RF4 precedent)
  imagery-path: authored          # authored cartography over client coordinates; loadingscreen/environment art as raw imagery material
  layers: [per-campus plot maps]  # one map per playable scene; CEILING = 26 scene-carrying bundles =
                                  #   25 strict *.unity (21 base aa + 3 dlc1 + 1 dlc2) + 1 seasonal
                                  #   (scenes-seasonalcontent_scenes_all.bundle carries scenes WITHOUT the .unity suffix);
                                  #   frontend/meta/registry scenes map to UI layers, not plots
  coordinate-transform: rect-per-map
  coordinate-sources: { plot-marker: unknown-P0 }   # flips to `client` after scene transforms extract
  readiness: ACHIEVABLE           # needs stage 3 scene/config dumps; no tile CDN signal (path A ruled out),
                                  #   no radar tiles (path B partial fit only), no community dataset found (path C unproven)

economy:
  npc-prices: PROVISIONAL         # Kudosh-priced shop items expected in configs_*; confirmed at stage 5
  market-feed: none               # single-player; no player market
  streaming: none                 # no live class declared for this pack

live:
  steam:
    enabled: no                   # no live plane; update tripwire is the LOCAL appmanifest watcher + optional news poll

tools:                            # details + scoring: tools-plan.md (≥5 scored ideas present; re-scored post-Tier-1)
  - { name: course-requirement calculator (course→room→item), type: calculator, evidence: tools-plan §T1 }
  - { name: campus layout planner/builder, type: planner, evidence: tools-plan §T2 }
  - { name: student happiness simulator, type: simulator, evidence: tools-plan §T3 }
  - { name: Kudosh economy planner, type: planner, evidence: tools-plan §T4 }
  - { name: research-tree explorer, type: data-product, evidence: tools-plan §T5 }
  - { name: staff-trait matcher, type: calculator, evidence: tools-plan §T6 }

automation:
  update-trigger: manual          # finished single-player title; buildid-diff fires when run_all re-runs against a changed manifest
  patch-cadence: dormant-observed # LastUpdated epoch 1766136803 = 2025-12-19; ISteamNews/GetNewsForApp pull FIRED
                                  #   2026-08-25 (verifyB carry 1.8 closed): latest items are 2026-08 store events,
                                  #   no patch-cadence signal — last build 2025-12-19 stands
  staleness-model: per-record     # buildId stamp on every emitted row
  watches: [appmanifest-buildid-change, engine-bump, dlc-release]

satellite:                        # §2.17
  platform: none
  status: no                      # offline single-player — no live surface for an overlay to consume
  gep-check: n-a                  # no GEP-relevant events exist; revisit only if an online mode ever ships

legal:                            # FRAMEWORK §4 template block — factual rows only; never analyzed (AGENTS rule 2)
  data: provenance recorded repo-only per AGENTS rule 3 two-class rule; user surfaces carry buildId + coverage scope
  tooling: repo arsenal per toolchain.md (Cpp2IL/Il2CppDumper/UnityPy/AssetStudioMod verdicts cited there)
  fan-program: none               # per-database decision at build time [DR-2026-08-15 D6]
  personal-data: none             # no leaderboards/names ingested
  malware-policy: n-a             # no forum/leaked artifacts in any source

external-dependencies: []
content-policy-holes:             # [DR-2026-08-18-media-scope]
  - video/audio NOT extracted into extracted/: video-intro-hi (256 MiB), audio-music (252 MiB), audio-sfx (221 MiB),
    audio-radio_{english,german,mandarin} (100/96/88 MiB), audio-tannoy_* — catalogued in MEDIA-CATALOGUE.md +
    media-catalogue.jsonl with byte totals, offload decision later
  - 3D models/animations catalogue-first: animations-character-courses (132 MiB), character-shared* — same catalogue path
missing-data:
  - entity rosters + attribute schemas: PROVISIONAL kinds above until stages 2–5 land
  - base localisation overlay semantics: stage-4 output
  - metadata-version/dumper pin: RESOLVED pre-stage — global-metadata.dat sanity 0xFAB11BAF @0, version 27 @offset 4
    (measured 2026-08-24); below the v38/v39 Il2CppDumper wall
status: { research: done, spec-frozen: false, adapter: not-started, full-pull: not-started,
          site: not-started, maps: not-started, locales-complete: false, seo-layer: not-started,
          verified: false }
```

## Full deconstruction scope (doctrine-mandated)

How the four doctrine layers map onto this client — Unity **2020.3.47f1,
IL2CPP**, Addressables **1.21.10** (`m_IsLocalCatalogInBundle: true`,
settings hash `ff59c4d7914829f354d3efeefc3819f0`), no custom encryption
observed at any layer. Corpus: `TPC_Data/StreamingAssets/aa/` = 158
bundles ≈ 3.5 GiB under `StandaloneWindows64/` + `catalog.bundle`
(1,704,718 B) + `settings.json`; `DLCs/{space,ghost}/` = 18 more bundles
(556 MiB). Evidence + counts land in `extracted/PROOF.md`; stages in
[docs/specs/piece-01-extraction-pipeline.mdx](docs/specs/piece-01-extraction-pipeline.mdx).

- **Data layer** — every addressables bundle harvested raw (stage 3):
  MonoBehaviour/ScriptableObject dumps, Texture2D/Sprite catalogue rows
  (byte decode deferred to a later owner-approved export pass per
  [DR-2026-08-18-media-scope]), TextAssets, grouped by bundle family;
  14 loc bundles → 13 per-locale string tables keyed by stable ids +
  `relinks/locale_availability.jsonl` (stage-5 sole owner,
  entity-granular); canonical JSONL skeletons per entity family
  contract-pinned even where fields are partially understood (stage 5).
- **Logic layer** — IL2CPP dummy assemblies + structural artifacts from
  `GameAssembly.dll` + `global-metadata.dat` (metadata v27; stage 1);
  derived formulas/costs/unlock trees under `extracted/logic/` land in a
  later piece once stage-1/3 outputs exist.
- **Relink layer** — piece 1 emits only `relinks/locale_availability.jsonl`;
  the complete ordered-pair matrix (`relinks/*.jsonl` + `RELATIONS.md`,
  hard/logic/inferred mechanisms) is a later-piece consumer of the
  directory contracts this spec fixes.
- **Protocol layer** — single-player: the owed section proves/inventories
  the surface instead. Observed plugins fix it: `steam_api64.dll`
  (Steamworks achievements/DLC/overlay/cloud-saves), BacktraceCrashpad
  (`BacktraceCrashpadWindows.dll` + `crashpad_handler`, crash telemetry),
  NVIDIA Ansel (`AnselPlugin64`/`AnselSDK64`). Inventory lands in
  `extracted/protocol/` + the PROOF protocol section in a later piece.

Residue policy: everything reachable gets extracted (Principle zero);
the media carve-out above is the only standing exception and it
catalogues what it excludes.

END OF spec.md
