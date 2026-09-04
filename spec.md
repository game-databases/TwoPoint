# Two Point Campus — current game and product specification

This specification describes the current build contract. Dated piece
specifications under `docs/specs/` remain implementation evidence, but they do
not own current phase or policy.

```yaml
game: Two Point Campus
folder: TwoPoint
lifecycle: live
domain: TBD
stack: next
site-phase: blocked-by-data
client:
  platform: pc-windows
  steam-appid: 1649080
  buildId: 20226581
  version: 10.3.169253+2024-12-06.1241
  engine: Unity 2020.3.47f1
  backend: IL2CPP
  metadata-version: 27

content-scope:
  held:
    - { id: base, appid: 1649080, bundles: 158 }
    - { id: dlc-space, appid: 1884560, name: Space Academy, bundles: 10 }
    - { id: dlc-ghost, appid: 1907450, name: School Spirits, bundles: 8 }
  unheld:
    - { id: dlc-hospital, appid: 2195430, name: Medical School,
        evidence: 19 catalog references with no installed payload }
  excluded-target:
    - { appid: 2312070, name: Two Point Campus Soundtrack, reason: audio-only }

locales:
  pivot: en
  official: [en, pt-BR, zh-Hans, zh-Hant, fr, de, it, ja, ko, pl, ru, es, tr]
  base-overlay: present-not-a-locale
  page-model: pivot-bare-path; localized-prefix-and-localized-slugs-for-others
  chrome: required-for-all-13-before-site-release
  source: client-localization-bundles
  storefront-advertised-count: 11
  storefront-omits: [ja, ru]
  availability-owner: stage9-locale-proof

axes:
  content: [base, dlc-space, dlc-ghost]
  platforms: [pc-windows]
  game-modes: [campaign, sandbox]
  version-eras: [build-20226581]

entities:
  config: { key: stable-emitted-id }
  item: { key: stable-emitted-id }
  room: { key: stable-emitted-id }
  course: { key: stable-emitted-id }
  staff: { key: stable-emitted-id }
  student-type: { key: stable-emitted-id }
  unlockable: { key: stable-emitted-id }
  metagame-node: { key: stable-emitted-id }
  campus-level: { key: stable-emitted-id }
  scene: { key: bundle-scene-identity, relation-node: true }

relations:
  matrix: 10x10-ordered-pairs
  mechanisms: [hard, logic, inferred]
  statuses: [modeled, partial, missing]
  locale-join: LocalisedString-termID-to-I2-term-key
  competitor-floor: three-independent-models-applied
  current-summary: extracted/RELATIONS.md

maps:
  form: per-campus interactive plot map
  geometry-source: client-scenes-and-configs
  imagery-path: authored
  imagery-condition: only-after-proving-no-usable-client-map-imagery
  dedicated-route: /map
  entity-linking: bidirectional
  handheld: link-to-map-only
  desktop-tv: interactive
  current-status: review-blocked-map-identity-defect

logic:
  course-progression: emitted
  economy: emitted
  grading: emitted-with-native-normalization-gap
  needs-decay: emitted-with-student-core11-gap

economy:
  npc-prices: client-derived-where-present
  market-feed: none
  streaming: none

live:
  steam:
    enabled: false
    reason: offline-single-player-no-live-product-plane

accounts:
  required-eventually: true
  phase: after-data-gate
  development-adapter: local-only-stub
  providers-at-public-origin: [Discord, Twitch, Steam, Google]
  unified-signin-signup: true
  minimum-session: 3-months
  stored-features:
    [saved-layouts, favorites, ratings, comments, corrections, screenshots,
     moderation]

satellite:
  platform: none
  status: no
  gep-check: not-applicable-offline-single-player

media:
  excluded: [audio, video, location-models, models-over-200MB]
  mandatory: [all-text, all-images, non-location-models-under-50MB]
  owner-decision-open: [animations]
  per-model-confirmation-open: [non-location-models-50MB-to-200MB]
  model-band-50-to-200-note: very-likely-empty-on-parent-census-but-unproven-until-withheld-containers-open
  current-status: catalogue-and-partial-web-export-not-yet-completeness-proven

tools:
  - course prerequisite and room requirement explorer
  - campus layout planner
  - Kudosh economy planner
  - research and unlock tree
  - grading calculator
  - needs and decay simulator
  - localized entity and text search

automation:
  update-trigger: build-id
  staleness-model: per-record
  watches: [appmanifest-buildid-change, engine-bump, dlc-release]

legal:
  data: provenance-recorded-repo-only
  tooling: versions-and-inputs-pinned-in-extraction-log
  fan-program: none
  personal-data: none-in-static-plane
  credentials: never-in-git

external-dependencies: []

content-policy-holes:
  - audio-and-video-excluded
  - location-models-and-models-over-200MB-excluded
  - animations-owner-disposition-open
  - non-location-models-50MB-to-200MB-per-model-confirmation-open
  - Medical-School-payload-not-held

status:
  research: done
  spec-frozen-for-build-20226581: true
  adapter: implemented
  full-pull: ledgered-not-proven-complete
  relinks: implemented-not-exhausted
  maps: review-blocked
  logic: implemented-with-two-gaps
  media: policy-reconciliation-required
  locales: emitted-proof-pending
  site: blocked-by-data
  seo-layer: not-started
  verified: false
```

## Data gate

Merging a documentation reconciliation does not open this gate. Phase D may
begin only after all of the following are true:

- the map identity and join defect is fixed on the real corpus;
- every relation pair is either modeled or carries a concrete, current unblock;
- three independent competitor relationship models have been applied;
- all mandatory images and eligible models are decoded and reconciled;
- animations are fully inventoried and carry the owner-selected disposition;
- the current reviewed source tree reproduces the corpus;
- eligible artifacts are committed and larger artifacts are staged and
  inventoried;
- `extracted/PROOF.md` and `extracted/VALIDATION-REPORT.md` are regenerated
  from that run and report no unaccepted data-completeness failure.

## Site contract

Once the gate opens, the site follows
[`docs/site-plan.mdx`](docs/site-plan.mdx) and meets the visual bar in
[`docs/design-direction.mdx`](docs/design-direction.mdx). It must use one
locale-aware route generator, server-render every crawlable relation, and use
game-sourced content and imagery. A generic shell, analytics-only page, or
English-only island cannot satisfy this specification.

## Fill and collision policy

A missing localized game string is omitted or represented by a localized
site-chrome missing state; pivot-language game prose is never mixed into
another locale. Entity slug collisions are resolved deterministically with the
stable entity id, documented by the future route manifest. Site chrome is
authored and translated separately from game content.

## FIT-section decisions

- builds/loadouts become the campus planner and saved campus layouts;
- tier lists are not launch scope because no client fact plane establishes a
  canonical ranking; community voting may be added after accounts;
- event timers and leaderboards do not fit this offline single-player title;
- economy means the client-defined money/Kudosh systems, not a player market;
- lore/story ships where the extracted text corpus provides meaningful
  entries;
- media contains permitted game-sourced images and user screenshots only.

<!-- END OF spec.md -->
