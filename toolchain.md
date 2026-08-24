# Two Point Campus — Extraction Toolchain

Formalizes scout §3 with the verifyB carries closed (2.4 dumper-build
decision, 1.1 metadata gate — both now measured, not hedged). Companion
to `spec.md` + `data-acquisition.md`. Confidence marks: ✅ measured on
disk this session · ◐ pinned-by-precedent (stamped at first pipeline
run) · ❓ resolved by a named stage output.

## Client profile (pins)

| Property | Value |
|---|---|
| Engine / backend | Unity **2020.3.47f1**, IL2CPP, Windows x64 ✅ |
| IL2CPP inputs | `GameAssembly.dll` 311,226,368 B + `TPC_Data/il2cpp_data/Metadata/global-metadata.dat` 14,284,260 B ✅ |
| **Metadata version** | **27** (int32 LE @ offset 4; sanity word `0xFAB11BAF` @ offset 0) ✅ measured 2026-08-24 — far below the v38/v39 Il2CppDumper wall → **both dumpers in range** |
| Addressables | 1.21.10 · settings hash `ff59c4d7914829f354d3efeefc3819f0` · local catalog in bundle ✅ |
| Corpus | 158 aa bundles ≈ 3.5 GiB + `catalog.bundle` 1,704,718 B + 18 DLC bundles ✅ |

## Primary dumper decision (verifyB 2.4 — resolved)

**Primary for piece 1: the staged compiled `Il2CppDumper`.** Upgrade path
(not piece-1 default): **Cpp2IL built locally from its source clone.**

Rationale, stated honestly:

- The scout's "no new downloads needed" hid a dependency: Cpp2IL exists
  ONLY as source under `tools/Cpp2IL/`; the staged binaries are
  Il2CppDumper's. Promoting the already-compiled dumper gives piece 1 a
  zero-build stage 1.
- Metadata v27 is comfortably inside Il2CppDumper's supported range (the
  KB failure mode `does-not-work/il2cppdumper-new-metadata.md` is scoped
  to metadata v38/v39, Unity 6000.x only).
- Il2CppDumper emits everything stage 1's contract needs: dummy
  assemblies per assembly, `dump.cs`, `script.json`, `stringliteral.json`
  — class hierarchy + id registries come from these.
- Cpp2IL stays pinned as the escalation when richer code recovery is
  needed (cast-n-chill precedent: its logic layer ran Cpp2IL
  2022.1.0-pre-release.21 because stable 2022.0.7 was too old for its
  metadata; IL-recovered bodies fed ISIL analysis). Trigger: a later
  piece needs method-body semantics Il2CppDumper's output cannot give,
  or stage 1 acceptance fails on the staged binary. The build step is
  then `dotnet publish` on `tools/Cpp2IL` (dotnet IS on this host);
  version chosen against the measured metadata version per Cpp2IL's own
  compatibility notes, and whatever was built gets pinned in
  `EXTRACTION-LOG.md`. Restore may pull NuGet packages — that is a
  declared build cost, not a silent download.

## Tool matrix

| # | Data target | Tool | Staged location / state | Status |
|---|---|---|---|---|
| 1 | Dummy assemblies + structural artifacts | **Il2CppDumper (compiled)** | `disco-elysium/zero-parades/work/_tooling/il2cppdumper/Il2CppDumper.exe` (+ `-x86`, `config.json`, `ghidra.py`, `ida_py3.py`) ✅ and second copy at `D:\unpacked_game_data\albion-online\_tooling\il2cppdumper\` ✅; source clone `tools/Il2CppDumper/` (KB record v6.7.46) | PRIMARY ◐ (exe version read from its own banner at stage-0 run and stamped into EXTRACTION-LOG.md) |
| 2 | Richer IL recovery (upgrade path) | **Cpp2IL + LibCpp2IL** | `tools/Cpp2IL/` full source clone incl. plugin projects ✅ — source only, no binary | ESCALATION ◐ (build step above) |
| 3 | Bundle/asset ripper of record | **UnityPy** (+ TypeTreeGeneratorAPI for IL2CPP typetree synthesis) | source clone `tools/UnityPy/` ✅; prior in-repo runs at 1.25.2–1.25.3 ◐; installed into the pack `.venv` at setup | PRIMARY for stages 2–3 (KB `works/unitypy-asset-ripping.md`) |
| 4 | Sprite/Texture2D batch export | **AssetStudioModCLI** (net8 portable) | `zero-parades/work/_tooling/AssetStudioModCLI/AssetStudioModCLI_net8_portable/` ✅ | SECONDARY batch exporter (UnityPy drives; CLI cross-checks icon batches) |
| 5 | Reading dummy DLLs | ILSpy / dnSpyEx clones (`tools/`) | present ✅ | manual inspection only |
| 6 | Low-level bundle surgery | AssetsTools.NET (+ .Cpp2IL variant) | source clone ✅ | only if UnityPy hits a format wall |
| 7 | GUI survey | AssetRipper | source clone; KB dead-end: 1.3.14 win-x64 ships GUI-only, no headless batch | NOT a pipeline driver (KB `does-not-work/assetripper-gui.md`) |
| 8 | Media catalogue rows | UnityPy census (no decode for audio/video) | #3 | carve-out enforcement [DR-2026-08-18-media-scope] |

UE-side arsenal does not apply (this is a Unity title). No new tool
downloads are required for the primary path; the Cpp2IL trigger path is
a local build as declared above.

## Knowledge-base verdicts that bind tool choice

- `works/unitypy-asset-ripping.md` — UnityPy reads SerializedFiles +
  UnityFS, exposes objects by `path_id`, decodes Texture2D/Sprite →
  ripper of record.
- `does-not-work/il2cppdumper-new-metadata.md` — fails only on metadata
  v38/v39; TPC is v27 → in range (measured, not assumed).
- `does-not-work/assetripper-gui.md` — GUI-only → excluded from headless
  batch.

## Scene tally (authoritative — verifyB 1.4 recount, mechanical, 2026-08-24)

Strict `*.unity.bundle` count via directory listing; this table replaces
scout §5's tildes everywhere. Base dir =
`TPC_Data/StreamingAssets/aa/StandaloneWindows64/`.

| Group | Bundles | Count |
|---|---|---|
| Frontend / boot | `scenes_scenes_main.unity.bundle` · `…_mainmenu.` · `…_frontend_cameras.` · `…_levelhud.` | 4 |
| Meta layers | `scenes_scenes_metagame.unity.bundle` · `…_metagame_nostate.` · `…_remix.` · `…_sandbox.` | 4 |
| Level registry | `scenes_scenes_config_level_databases.unity.bundle` (machine-readable campus/level DB) | 1 |
| Campus levels — short prefix | `scenes_scenes_knightlevel_optimised.unity.bundle` · `…_mittonlevel_` · `…_partylevel_` (NOTE: no `scene_` infix) | 3 |
| Campus levels — long prefix | `scenes_scenes_scene_{tutoriallevel,archaeologylevel,gastronomylevel,magiclevel,performingartslevel,roboticslevel,sportslevel,spylevel,finallevel}_optimised.unity.bundle` | 9 |
| Seasonal | `scenes-seasonalcontent_scenes_all.bundle` — scene-carrying but NO `.unity` suffix (suffix nuance; there is also a non-scene `items-seasonalcontent_assets_all.bundle`) | 1 |
| **Base total** | | **22 scene-carrying (21 strict `.unity` + 1 seasonal)** |
| DLC space | `dlc-space-scenes_scenes_scene_dlc1_{launchpadlevel,moonbaselevel,spaceportcitylevel}_optimised.unity.bundle` | 3 |
| DLC ghost | `dlc-ghost-scenes_scenes_scene_dlc2_ghosts_optimised.unity.bundle` | 1 |
| **Install totals** | | **25 strict `.unity` · 26 scene-carrying** |

Maps ceiling therefore reads **26 playable-scene-carrying bundles**
(25 strict `.unity` + 1 seasonal), of which the 16 campus/DLC levels are
plot-map candidates and the rest are frontend/meta/registry layers.

## Host realities (NE8K)

Extraction runs here, in place. Available: git 2.40.1, node v22.23.2,
Python 3.14 (`C:\Python314`), dotnet; **no `7z` on PATH** (archive
tooling lives under `tools/`); bash available via git-bash. Writes of
tens of GB prefer `D:` or `A:` over `C:` (drive map in
[`_foundation/extraction-host.md`](../_foundation/extraction-host.md)).
The entrypoint hardcodes no machine paths; staged-tool locations are
resolved from `EXTRACTION-LOG.md` defaults with the paths above as
fallbacks.

## Full deconstruction scope (doctrine-mandated)

Layer → tool → output mapping for this client:

- **Data layer** — UnityPy over catalog + all 176 bundles → raw asset
  export grouped by bundle family; Texture2D/Sprite decode;
  TextAsset/MonoBehaviour dumps; 14 loc bundles → 13 per-locale tables +
  `relinks/locale_availability.jsonl`; canonical JSONL skeletons per
  entity family. Audio/video catalogued only (carve-out).
- **Logic layer** — Il2CppDumper primary (metadata v27) → dummy
  assemblies + `dump.cs`/`script.json`/`stringliteral.json` under
  `extracted/decompiled/il2cppdumper/`; Cpp2IL escalation reserved for
  method-body work; derived formulas/unlock trees land under
  `extracted/logic/` in later pieces.
- **Relink layer** — piece 1 ships `relinks/locale_availability.jsonl`
  only; the ordered-pair join matrix + `RELATIONS.md` are later-piece
  consumers of the directory contracts fixed in the piece-1 spec.
- **Protocol layer** — single-player inventory (steam_api64 cloud-saves/
  achievements surface, Backtrace crash telemetry, Ansel) →
  `extracted/protocol/` + PROOF protocol section in later pieces.

END OF toolchain.md
