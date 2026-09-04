# Two Point Campus — extraction toolchain

## Client profile

| Property | Value |
|---|---|
| engine | Unity `2020.3.47f1` |
| backend | IL2CPP, Windows x64 |
| metadata | version `27`, sanity `0xFAB11BAF` |
| Addressables | `1.21.10`, local catalog-in-bundle |
| corpus | 176 installed bundles |
| Python dependency | UnityPy `1.25.3` pin |
| structural dumper | staged Il2CppDumper; Cpp2IL is the method-body escalation |

## Stage registry

| Index | Stage | Primary implementation | Tool class | Current state |
|---:|---|---|---|---|
| 0 | `verify-client` | `tools/stage0_verify_client.py` | stdlib | implemented |
| 1 | `decompile` | `tools/stage1_decompile.py` | Il2CppDumper | implemented |
| 2 | `harvest-catalog` | `tools/stage2_harvest_catalog.py` | UnityPy + catalog decoder | implemented |
| 3 | `harvest-bundles` | `tools/stage3_harvest_bundles.py` | UnityPy | implemented; media policy follow-up required |
| 4 | `localisation` | `tools/stage4_localisation.py` | UnityPy | implemented |
| 5 | `emit-stub-datasets` | `tools/stage5_emit_stubs.py` | stdlib | implemented |
| 6 | `relink` | `tools/stage6_relink.py` | UnityPy + derived indexes | implemented; competitor floor open |
| 7 | `maps` | `tools/stage7_maps.py` | derived client geometry | implemented; review-blocked |
| 8 | `logic` | `tools/stage8_logic.py` | derived data/code structure | implemented with two ledgers |
| 9 | `locale-proof` | `tools/stage9_locale_proof.py` | derived | implemented |
| 10 | `check-contracts` | `tools/stage10_check_contracts.py` | validator suite | implemented |
| 11 | `media` | `tools/stage11_media.py` | UnityPy + Pillow | partial policy coverage |
| 12 | `search-corpus` | `tools/stage12_search_corpus.py` | derived | implemented; stage follow-up after relation/locale changes |

`run_all.py --list` is the authoritative runtime order. The old six-stage
“piece 1” description is retired.

## Structural and asset tools

- **Il2CppDumper** emits dummy assemblies, `dump.cs`, `script.json`, and
  string-literal structure.
- **Cpp2IL** is used only when a player-facing requirement needs method-body
  semantics that the current structural dump cannot supply.
- **UnityPy** opens catalog, bundles, typetrees, localization objects, sprites,
  textures, and serialized references.
- **AssetStudioModCLI** is a cross-check for lossless image decoding, not a
  second source of truth.
- **Pillow** encodes web media after the client asset has been resolved.

Tool/version/build pins and every historical run remain append-only in
`extracted/EXTRACTION-LOG.md`.

## Host procedure

The Windows extraction host is the data origin. Its SSH logon cannot use the
interactive desktop's Git credential helper, so a failed `git pull` over SSH
does not prove repository credentials are broken. More importantly, it allows
source drift.

Before execution, relay the reviewed tree and compare hashes. A reproducible
result means the exact committed versions of `run_all.py`, every
`tools/stage*.py`, and their helper modules produced the documented output.

Bulk writes use a drive with freshly measured capacity. The complete corpus
then syncs to the Mac staging copy and is split between Git-eligible artifacts
and explicitly inventoried local-large artifacts.

## Verification commands

```bash
python run_all.py --list
python -m pytest tests -q
python tools/check_documentation.py
python tools/stage10_check_contracts.py
python run_all.py "A:\SteamLibrary\steamapps\common\Two Point Campus" --force
```

A return code of `2` is not success-equivalent: it means the stage completed
with named ledger contributors. The final PROOF must preserve those
contributors and their exact unblocks.

## Current toolchain risks

- the map stage has an unresolved real-corpus identity defect and missing test
  teeth;
- the media implementation predates the mandatory all-image/under-50-MB-model
  policy and does not yet inventory the owner-open animation class completely;
- current tracked evidence does not prove the full emitted corpus came from
  the latest reviewed source hashes;
- contract and search stages need new stage-specific reviews after the
  map/media/relation changes that affect their inputs.

These are project implementation risks, not unresolved findings on the
current repository-reconciliation PR.

<!-- END OF toolchain.md -->
