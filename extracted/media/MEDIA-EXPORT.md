# Two Point Campus — entity web-export report

**buildId:** `20226581`  
**Stage:** `media` (canonical index 11)  
**Tracked artifact:** this file only  
**Verdict:** **entity-web subset — not all-image or eligible-model completion**

This is the tracked media-stage human report. Binaries and machine
provenance under `extracted/media/` stay local (`web/**`,
`export-manifest.jsonl`, `index.jsonl`, `hashes.sha256`,
`crosscheck-report.json`, ledgers). This GitHub checkout does not contain
those files. Counts below are copied from already tracked measurements in
`extracted/MEDIA-CATALOGUE.md`, `extracted/PROOF.md`, and
`docs/specs/piece-06-media.mdx`. They are not a fresh decode of this clone
and they do not invent SHA-256 values or byte totals that this tree cannot
recompute.

`extracted/EXTRACTION-LOG.md` has no dated `media` run section. Until a
reviewed-tree media rerun lands, this report remains a subset ledger.

## Encoder pins

| Pin | Value | Status on this checkout |
|---|---|---|
| primary format | WebP lossy **q80** + alpha | intent from piece-06; local files absent |
| PNG twins | max-dim **≤ 64 px**, plus alpha-roundtrip failures (tolerance ≤ 1/255) | **29** twins reported in the referenced set |
| AVIF | not emitted | unchanged |
| UnityPy / Pillow | `1.25.3` / `12.3.0` (`features.check('webp')=True`) | toolchain pin; not re-run here |
| fallback Unity | `2020.3.47f1` assigned (env var alone is insufficient) | toolchain pin |
| AssetStudioModCLI cross-check | v0.19.0, `--unity-version 2020.3.47f1`, lossless PNG | used for the 20-sample pixel lane |

No upscaling. Canonical assets stay native resolution (median max-dim ≈233 px).

## Scope of this report

This file reports the **entity-referenced web export** (piece-06 E1/E2):

- **2,222** WebP files;
- **29** lossless PNG twins;
- **2,151 of 2,158** named entity-media joins resolved;
- **seven** named absences;
- a **20-sample** pixel comparison with **no mismatch**.

It does **not** claim:

- every Sprite / SpriteAtlas slot / Texture2D decoded;
- UI-chrome atlas crops (E3, flag-gated; not reported as on in tracked evidence);
- thumbnail plane (default off);
- font, shader, mesh, or animation export;
- `[DR-2026-08-29-media-scope-amended]` completion (every text/image plus
  every non-location model under 50 MB).

Catalogue inventory remains in `extracted/MEDIA-CATALOGUE.md`. Completeness
owed to C2-MEDIA is unchanged.

## Catalogue universe (stage-3 census, not decoded products)

| Class | Objects | Estimated serialized bytes | Downstream duty |
|---|---:|---:|---|
| AnimationClip | 7,985 | 636,456,748 | inventory completely; owner retain/offload/drop still open |
| AudioClip | 5,624 | 1,014,532 | excluded |
| Font | 24 | 39,626,688 | extract/reconcile |
| Mesh | 19,249 | 153,322,460 | non-location models under 50 MB mandatory; 50–200 MB per-model confirmation |
| Shader | 213 | 21,916,544 | preserve/inventory |
| Sprite | 6,789 | 5,867,972 | every image mandatory |
| SpriteAtlas | 47 | 545,172 | every constituent image mandatory |
| Texture2D | 7,977 | 209,500,708 | every image mandatory |
| VideoClip | 31 | 8,338 | excluded |
| **Total** | **47,939** | **1,068,259,162** | |

`bytesEstimate` is serialized size, not shipped WebP/PNG bytes. Stage-3
catalogue rows are inputs to mandatory downstream decoding, not completion.

## Entity-web counts (tracked subset)

| Measure | Count | Plane / note |
|---|---:|---|
| WebP files | 2,222 | tracked total; local `web/` absent here so per-plane bytes cannot be summed |
| PNG twins | 29 | ≤64 px / alpha sanity in the referenced set |
| Distinct referenced sprite names | 2,158 | stub-side E1 universe |
| Resolved names | 2,151 | 99.676% |
| Named absences | 7 | full enum below |
| Pixel sample | 20 | `pixelMatchRate == 1.0`, `maxDelta == 0` |
| Thumbs plane | not reported | `--with-thumbs` default off |
| UI-chrome plane | not reported | E3 flag-gated |

Shipped-volume **estimate** from piece-06 for the default referenced set is
8–25 MiB WebP q80. That estimate is not a hashable byte total for this clone.

### Per-kind join seeds (E1 universe)

Tracked piece-06 M5 cells (rows / rows with non-empty refs / GUID refs /
sprite-typed targets / dangling):

| Kind | Rows | Non-empty refs | GUID refs | Sprite-typed | Dangling |
|---|---:|---:|---:|---:|---:|
| items | 3,885 | 3,875 | 8,140 | 1,919 | 363 |
| configs | 8,430 | 3,406 | 11,422 | 1,412 atlasv2 + 153 plain-Sprite | 3,664 |
| metagame-nodes | 454 | 344 | 202 | 202 | 0 |
| rooms | 116 | 106 | 115 | 115 | 0 |
| student-types | 54 | 27 | 27 | 27 | 0 |
| staff | 3 | 3 | 15 | 9 | 0 |
| unlockables | 415 | 63 | 201 | 33 | 26 |
| courses | 69 | 0 | 0 | 0 | 0 |
| campus-levels | 17 | 13 | 20 | 0 | 7 |

Sprite-targeted refs sum **3,870**. Atlas-route share seed: **3,717/3,870**
target `.spriteatlasv2`; ~153 refs target plain Sprite (E2), 150 with empty
sub. A media rerun must remeasure; fresh numbers win.

## Named absences (complete M16 set)

| `subObjectName` | Reason class |
|---|---|
| `DLC3_UI_Icons_Objective_Pirates` | `dlc-content-absent` (unowned DLC 2195430) |
| `DLC3_UI_Icons_Objective_Volcano` | `dlc-content-absent` |
| `Gorge_UI_Icons_Objectives_DLC3_Emergency` | `dlc-content-absent` |
| `UI_HUD_Room_T_Icon_DLC3_plot` | `dlc-content-absent` |
| `UI_InGame_DLC3_Icon_studentArchetype_Doctors` | `dlc-content-absent` |
| `UI_InGame_DLC3_Icon_studentArchetype_Nurses` | `dlc-content-absent` |
| `UI_InGame_T_Icon_Item_Teamsports_Cheeseball` | `stale-name` (unused BASE event config vs installed atlas) |

These are honest missing states, not silently dropped rows.

## Ledger enums and sizes

Local ledger files are **absent on this checkout**. Expected shapes and
frozen enums (so a clone knows what to request from the data host):

### `_missing_icons.jsonl`

- Sort: `subObjectName`
- Keys: `{subObjectName, assetGuid, reason, sampleRefs[≤5], buildId}`
- `reason` enum (complete): `dlc-content-absent` · `stale-name` ·
  `empty-sub-name` · `editor-only-fallback` · `visuals-prefab-target` ·
  `mesh-list-target` · `level-config-target` · `uncategorized-reason`
- Tracked size: **7** rows matching the table above
- Related skip families (not the seven names): EditorFallbackIconReference ×351,
  VisualsPrefab ×12, Meshes[0] ×26, LevelConfig ×7

### `_pptr_residue.jsonl`

- Sort: `(kind, srcId, fieldPath)`
- Keys: `{kind, srcId, fieldPath, pptr{fileId, pathID}, pairedReferenceEmpty:true, slotClass, targetResolution, basis:"122-basis", buildId}`
- Canonical seed: **122** nonzero icon-named PPtr slots; external subset **24**
  (`slotClass: external` iff `m_FileID != 0`)
- File not present here; counts not rehashed

### `_skipped_classes.jsonl`

Expected skip-policy rows:

| Class | Census | Policy |
|---|---:|---|
| Cubemap | 138 | skip (census only) |
| Texture2DArray | 9 | skip (census only) |
| zero-size font-atlas Texture2D | 29 | skip (fonts out of this piece) |

## Local artifact row schemas (request these from the data host)

None of these files exist in this clone. Schemas are the piece-06 contract.

| Artifact | Sort / bijection | Frozen keys |
|---|---|---|
| `export-manifest.jsonl` | one row per emitted file under `web/`; bijection with files | `outRelPath`, `plane`, `format`, `quality`, `bytes`, `sha256`, `route`, `namedBy`, `source{bundle,pathId,class,subObjectName,assetGuid,atlas…,rect,rounded,contentAxis}`, `dims`, `buildId` |
| `index.jsonl` | `(kind, srcId, fieldPath)` — one row per REF including unresolved | `kind`, `srcId`, `fieldPath`, `assetGuid`, `subObjectName`, `resolved`, `chainBreak`, `file`, `reason`, `buildId` |
| `hashes.sha256` | `"<sha256>  <relpath>"` LF, sorted by relpath | file digest list |
| `crosscheck-report.json` | sample ≥20 with composition quotas | sample, rates, CLI version/flags, `pixelMatchRate`, `maxDelta` |
| `course-icon-carrier-report.json` | E5 flag-gated | report-only; not claimed present |

`plane` ∈ `icons | thumbs | ui`. Collision suffix is signed int64 `pathId`.

## Hash summary

**Unavailable on this checkout.** Local files, per-file SHA-256, and
row/file counts of `export-manifest.jsonl` / `hashes.sha256` cannot be
recomputed without the gitignored (or unpublished) media tree.

A later data-host run must fill:

- WebP count / PNG count / total bytes;
- `export-manifest.jsonl` row count == `web/` file count;
- `hashes.sha256` regeneration identity;
- SHA-256 of this Markdown after a deterministic generator rewrite.

Until then, drift between clones cannot be detected from GitHub alone.

## Cross-check verdict

Tracked evidence: 20-sample pixel comparison, **no mismatch**
(`pixelMatchRate == 1.0`, `maxDelta == 0`) against AssetStudioModCLI
lossless PNG on the pinned RGBA8 path. Sample composition quotas from
piece-06 (routes, ≥3 ambiguous-tiebreak, ≥2 fractional, BC7-page sprite if
referenced, both probe anchors) are **not re-proven on this clone**.

## Completion statement

This report is a **subset**. It proves an entity-web export was measured. It
does not close C2-MEDIA. Required remaining work is the source-object →
decoded-output table in `extracted/MEDIA-CATALOGUE.md` (every Sprite, atlas
slot, Texture2D, eligible mesh, animation disposition).

<!-- END OF extracted/media/MEDIA-EXPORT.md -->
