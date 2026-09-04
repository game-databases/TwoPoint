# Two Point Campus — data acquisition and corpus policy

## Primary client

| Field | Measured value |
|---|---|
| install | `A:\SteamLibrary\steamapps\common\Two Point Campus` on `NE8K` |
| appid | `1649080` |
| buildId | `20226581` |
| version | `10.3.169253+2024-12-06.1241` |
| engine | Unity `2020.3.47f1`, IL2CPP |
| metadata | `global-metadata.dat` version `27` |
| base depot | `1649081` |
| installed DLC | Space Academy (`1884560`), School Spirits (`1907450`) |
| uninstalled content | Medical School (`2195430`) |
| bundle universe | 176: 158 base + 10 Space Academy + 8 School Spirits |

The install is readable without a container-encryption wall. The authoritative
inputs are the game client and first-party Steam metadata. Community sources
are relationship-model research only and are never named on public surfaces.

**Latest-run precedence:** `extracted/EXTRACTION-LOG.md` is append-only.
Historical failed or earlier runs stay in that log. Current policy documents
cite the latest ledgered run for each stage.

## Source inventory

### Addressables and bundles

- `TPC_Data/StreamingAssets/aa/catalog.bundle`
- 158 base bundles under `aa/StandaloneWindows64/`
- 18 installed DLC bundles under `DLCs/space/` and `DLCs/ghost/`
- 14 localization bundles: 13 locales plus a base overlay
- `GameAssembly.dll` and `global-metadata.dat`
- appmanifest, version, app-info, boot, and runtime sidecars

The decoded catalog contains 56,660 key slots, 66,129 entries, and 81,146
bucket memberships. It resolves all 176 installed bundle basenames and records
19 out-of-roster references, primarily Medical School plus preorder material.

### First-party metadata

The repository stores kickoff Steam app-details and news responses under
`data/sources/` with an append-only manifest. These corroborate product names,
DLC identities, and update cadence. They do not replace client extraction.

The checked-in storefront response advertises 11 text languages. Japanese and
Russian are absent from that storefront field even though the client ships
both; the 13 client localization bundles remain the capability authority. No
`es-419` variant is advertised or present in the acquired client.

### Competitor relationship models

The repository contains one harvested Fandom model and one Steam-guide model,
plus a recorded wiki.gg access wall. They are repo-only relationship research.
Current application status and the missing third-source floor are in
[`competitor-research.md`](competitor-research.md).

## Pipeline and ownership

`run_all.py` is the only entrypoint. Stage ownership is summarized in
[`docs/architecture.mdx`](docs/architecture.mdx). Every run stamps buildId,
tool versions, source paths, and derived methods into machine-plane artifacts
and `extracted/EXTRACTION-LOG.md`.

Before a reproducibility claim:

1. relay the reviewed scripts from the orchestrating checkout to `NE8K`;
2. compare every committed pipeline-script hash;
3. run the entrypoint against the installed client;
4. sync the complete extracted corpus to the Mac staging copy;
5. reconcile and publish it under the current Git-size policy.

## Current media policy

The old “catalogue textures/models now, decide later” rule is retired by
`[DR-2026-08-29-media-scope-amended]`.

Target-set rules now are:

- exclude audio and video;
- exclude location models and any model over 200 MB;
- extract every text occurrence;
- extract every image;
- extract every non-location model under 50 MB;
- inventory animations completely and stage them until the owner chooses
  retain/offload/drop;
- classify every 50–200 MB non-location model individually. The parent census
  found the band very likely empty, so no owner choice is currently required,
  but that conclusion is not proven until withheld containers are opened.

The current media stage has a verified entity-web export but has not yet proven
full class coverage. `extracted/media/MEDIA-EXPORT.md` is the tracked subset
report (2,222 WebP, 29 PNG twins, 2,151/2,158 joins). `extracted/MEDIA-CATALOGUE.md`
is the class-universe coverage ledger, not a completion certificate.

## Publication policy

Every individual file below approximately 95 MB and every commit below
approximately 1 GB is committed and pushed. Files above that boundary remain
complete on the local machine, git-ignored in an explicit large-artifact
staging directory, and ready for production sync. Large logical streams are
sharded on record boundaries whenever that preserves byte-equivalent
reconstruction.

The historical blanket ignore of `extracted/**` is removed.

Physical corpus publication is required **before Phase D / before a green
project data gate**. It is not a precondition for merging a documentation
reconciliation. Before that data gate can close, the corpus-owning agent must
size-audit the live corpus, stage every eligible artifact, shard any eligible
over-cap stream, and list every intentionally local artifact with exact path
and byte count in `extracted/PROOF.md`.

## Current residue

- Medical School payload is absent.
- map identity and reverse joins fail the latest corpus-scale review.
- media policy coverage is not reconciled.
- animation disposition remains an owner decision.
- the 50–200 MB model band still needs per-model confirmation.
- competitor relationship application is below the three-source floor.
- two native-logic carriers remain unresolved.
- complete Git/Mac/prod staging coverage is not yet proven.

The exact ledger and unblocks are maintained in
[`missingdata.md`](missingdata.md) and [`extracted/PROOF.md`](extracted/PROOF.md).

<!-- END OF data-acquisition.md -->
