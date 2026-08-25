# Two Point Campus — Data Acquisition

Companion to `spec.md` + `toolchain.md`. Research basis:
`docs/scout-report-001.mdx` §2/§4/§9 (verifyA 21/21 CONFIRMED) plus the
2026-08-24 recounts by documentator-001 (scene tally, metadata version,
DLC rosters — noted inline where they supersede scout figures). All
figures measured on this host; the only downloads are the two kickoff
corroboration pulls that landed 2026-08-25 under `data/sources/`
(§"Queued external pulls" below).

## Client (primary source, in hand)

| Fact | Value |
|---|---|
| Install dir | `A:\SteamLibrary\steamapps\common\Two Point Campus` |
| SizeOnDisk (manifest) | 4,694,205,668 B ≈ 4.37 GiB |
| Steam appid | 1649080 |
| buildid | **20226581** (= `TargetBuildID` — install is at target) |
| LastUpdated | epoch 1766136803 = 2025-12-19 |
| In-game version | `version.txt`: `10.3.169253+2024-12-06.1241` (27 B) |
| Engine | Unity 2020.3.47f1 (ASCII at ~0x30 of `globalgamemanagers`; verifyA #2) |
| Backend | IL2CPP — `GameAssembly.dll` 311,226,368 B + `TPC_Data/il2cpp_data/Metadata/global-metadata.dat` 14,284,260 B |
| Metadata header | sanity word `0xFAB11BAF` @ offset 0; **metadata version 27** @ offset 4 (int32 LE; measured by documentator-001 2026-08-24 — verifyB carry 1.1 closed pre-stage; the version int follows the sanity word, so "offset 0" in verifyB reads as offset 4) |
| Developer / title strings | `TPC_Data/app.info`: "Two Point Studios" / "Two Point Campus" |
| Steam language setting | `"language" "english"` sits in `appmanifest_1649080.acf` (twice; no `userdata/` on `A:`) — install setting, not a capability row |

Content is Unity AssetBundles with standard LZ4/LZMA block compression;
no depot-level or container-level encryption observed. No technical
reachability wall exists for any planned source — every byte of the
corpus is locally readable.

## Depot map (`appmanifest_1649080.acf`)

| Depot | DLC appid → public name | Size (B) | Manifest gid |
|---|---|---|---|
| 1649081 (base) | — | 4,112,128,282 | 289369811377342695 |
| 1907451 ("ghost") | 1907450 — "School Spirits" | 212,055,024 | 3622833373893779274 |
| 1884561 ("space") | 1884560 — "Space Academy" | 370,022,362 | 6004916305044431883 |

**Association CORRECTED 2026-08-25** against
`data/sources/steam-appdetails-1649080.json` (an earlier draft paired
these backwards): **appid 1884560 = "Space Academy"** → depot 1884561 →
`DLCs/space/` (`dlc1_launchpadlevel`, `dlc1_moonbaselevel`,
`dlc1_spaceportcitylevel`); **appid 1907450 = "School Spirits"** → depot
1907451 → `DLCs/ghost/` (`dlc2_ghosts_optimised`). Steam's internal dir
codenames do not track marketing names here — `space`/`ghost` stay as
folder nicknames and as the frozen `contentAxis` enum values
(`dlc-space`/`dlc-ghost`); only the appid/depot↔dir association text
corrected.

Shared Steamworks depot 228989 (standard redistributable). The two DLC
depot sizes do not sum to the 556 MiB `DLCs/` dir on disk — disk shows
post-install expansion; both are recorded facts, not an error.

## Source inventory

### S1 — Addressables store (`TPC_Data/StreamingAssets/aa/`)

161 files total under `aa/`: the corpus below plus `AddressablesLink/`.

- `aa/settings.json` — runtime config. Pinned values: `m_AddressablesVersion`
  **1.21.10**, settings hash `ff59c4d7914829f354d3efeefc3819f0`,
  `m_IsLocalCatalogInBundle: true`, provider `ContentCatalogProvider`,
  build target `StandaloneWindows64`.
- `aa/catalog.bundle` — **1,704,718 B** (1.63 MiB; the scout's "1.7 MiB"
  rounds up). Machine-readable key → bundle/address index over the whole
  store; first extraction artifact (pipeline stage 2).
- `aa/StandaloneWindows64/` — **158 bundles ≈ 3.5 GiB apparent**
  (du 3560 MiB). Human-readable domain-partitioned names,
  `{family}-{subfamily}_{kind}_{scope}.bundle`, plus a few hash-prefixed
  ones (e.g. `041ed57f…_monoscripts.bundle`,
  `…_unitybuiltinshaders.bundle`). Largest: video-intro-hi 256 MiB ·
  audio-music 252 · audio-sfx 221 · environment-landscape 204 ·
  character-shared-textures 170 · unlockables 146 · rooms 137 ·
  animations-character-courses 132 · environment 108 ·
  character-shared 103 · audio-radio en/de/zh-Hans 100/96/88 ·
  items-general 85.
  - Locales: exactly **14** `localisation_assets_localisation*.bundle`
    = 1 unnamed base overlay + 13 named languages (list character-exact
    in spec.md; verifyA #5b).
  - Scenes: **21 strict `*.unity.bundle`** + `scenes-seasonalcontent_scenes_all.bundle`
    (scene-carrying, NO `.unity` suffix — the suffix nuance that made
    scout §5's table sum to 22). The authoritative scene table lives in
    `toolchain.md` §"Scene tally" and is re-verified by piece-1 stage 0;
    never cite scout §5's tildes.

### S2 — DLC packs (`DLCs/{space,ghost}/`, loose bundles)

Counted 2026-08-24 (these exact figures supersede scout §2's `~9/~11`
tildes; they reconcile with §9 and the 176-bundle total):

| Dir | Bundles | Scene bundles |
|---|---|---|
| `DLCs/space/` | **10**: art, audio, configs, environment-debug, loadingscreen, ui, ui-spriteatlas + scenes | 3 × `.unity`: `dlc1_launchpadlevel`, `dlc1_moonbaselevel`, `dlc1_spaceportcitylevel` |
| `DLCs/ghost/` | **8**: same families minus scenes except one | 1 × `.unity`: `dlc2_ghosts_optimised` |

Total corpus: **176 bundles** (158 aa + 18 DLC). DLC handling rule: DLC
bundles are harvested by the same stage 3 pass as base aa bundles — same
UnityPy path, family grouping carries the piece-1 pinned `contentAxis`
enum tag (`dlc-space`/`dlc-ghost`; spec.md's site-plane
`dlc1-space`/`dlc2-ghost` map onto it) per row. No separate
acquisition work exists: both DLCs are installed.

Two further DLC exist beyond the install (appdetails 2026-08-25):
**2312070 "Two Point Campus Soundtrack"** and **2195430 "Two Point
Campus: Medical School"** — not owned, nothing on disk. Medical School
is nonetheless catalog-KNOWN: the base catalog references
`dlc-hospital-*` bundles 19× out-of-roster, so the catalog anticipates
content this install can never satisfy. Acquiring either is an owner
question (QUESTION-QUEUE #3, non-blocking).

### S3 — Native image + metadata (decompile inputs)

`GameAssembly.dll` (297 MiB) + `global-metadata.dat` (~14 MiB,
metadata v27) under the install dir; assembly list in
`TPC_Data/ScriptingAssemblies.json`. Consumed by pipeline stage 1.

### S4 — Metadata sidecars (provenance + tripwire)

`appmanifest_1649080.acf` (buildid/depots/language),
`version.txt`, `boot.config`, `app.info`,
`RuntimeInitializeOnLoads.json`. Read-only; re-read on every pipeline run
for the buildid stamp.

## Media carve-out clause [DR-2026-08-18-media-scope]

Video and audio are catalogued, never held inline in `extracted/`:

- **Video:** `video-intro-hi` (256 MiB — largest single bundle) and any
  other VideoClip-bearing bundle are opened only to count/list their
  assets; zero video bytes are emitted into `extracted/`.
- **Audio:** `audio-music` (252 MiB), `audio-sfx` (221 MiB),
  `audio-radio_assets_{english,german,mandarin}` (100/96/88 MiB),
  `audio-tannoy_assets_{english,german,mandarin}`, and every
  `*-audio_*` DLC bundle — same treatment.
- Both classes land as rows in `extracted/MEDIA-CATALOGUE.md` +
  `media-catalogue.jsonl` (bundle, asset name/class, byte totals);
  offload vs keep is a later owner pick on that catalogue.
- **Catalogue-first heavy classes:** 3D models and animations
  (`animations-character-courses` 132 MiB, `character-shared*`) and
  textures are listed in the same catalogue with counts+bytes before any
  bulk retention decision.

## Protocol surface (single-player inventory, verifyB carry 1.3)

No gameplay client↔server plane exists. The owed protocol section
inventories what the plugins expose instead: `steam_api64.dll`
(Steamworks — achievements, DLC checks, overlay, cloud-saves),
crash telemetry (`BacktraceCrashpadWindows.dll` + `crashpad_handler`),
NVIDIA Ansel capture (`AnselPlugin64`/`AnselSDK64`). Inventory +
no-surface proof land in `extracted/protocol/` and the PROOF protocol
section in a later piece; piece 1 fixes the directory contract only.

## Kickoff external pulls — DONE 2026-08-25 (not pipeline stages)

One-shot corroboration calls at pack kickoff, outside `run_all`. Both
fired 2026-08-25; raw JSON + MANIFEST rows are in `data/sources/`.

1. **Steam `appdetails` (store-cc us)** — DONE (`steam-appdetails-1649080.json`).
   - DLC public names settled: **1884560 = "Space Academy"**,
     **1907450 = "School Spirits"**, plus two not-owned listings,
     **2312070 = Soundtrack**, **2195430 = Medical School** (drives the
     depot-map correction above).
   - verifyB carry 1.7 RESOLVED: the storefront row has **no
     `es-419`/latam entry** — no locale variant exists beyond the
     client's set, and the client's single `spanish→es` bundle maps to
     the storefront's "Spanish - Spain". Precision note: the storefront
     `supported_languages` string names **11 of the client's 13 text
     locales** (Japanese and Russian absent from the storefront row;
     re-checked live against the endpoint 2026-08-25) — the client's 14
     loc bundles remain the sole authority for locale capability.
2. **Steam `ISteamNews/GetNewsForApp`** — DONE (`steam-news-1649080.json`);
   latest items are 2026-08 store events, no patch-cadence signal →
   verifyB carry 1.8 closed; last build 2025-12-19 stands.

Neither blocked extraction; both wrote their provenance rows into
`data/sources/MANIFEST.md` on firing.

## Provenance fields (per dataset, repo-only per AGENTS rule 3)

Every emitted artifact carries: `source_class` (client-extraction /
official-api / …), `container` (bundle path or endpoint), `appid`,
`buildId` (**20226581** stamped everywhere user-visible truth is
derived), tool + tool_version, extraction timestamp (machine plane
only), and — for anything derived rather than hard-read — `inferred:
true` + method string. Repo-only provenance fields stay out of
user-facing surfaces entirely.

END OF data-acquisition.md
