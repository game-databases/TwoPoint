# Two Point Campus — media inventory and coverage status

**buildId:** `20226581`  
**Verdict:** catalogue complete for the recorded run; mandatory decoded-media
coverage **not yet proven**

## Recorded asset-class universe

| Class | Objects | Estimated serialized bytes | Policy |
|---|---:|---:|---|
| AnimationClip | 7,985 | 636,456,748 | staged; owner decision open |
| AudioClip | 5,624 | 1,014,532 | excluded target |
| Font | 24 | 39,626,688 | extract/reconcile |
| Mesh | 19,249 | 153,322,460 | extract non-location models under 50 MB; inventory others |
| Shader | 213 | 21,916,544 | preserve/inventory under Principle zero |
| Sprite | 6,789 | 5,867,972 | every image must be decoded/reconciled |
| SpriteAtlas | 47 | 545,172 | every constituent image must be decoded/reconciled |
| Texture2D | 7,977 | 209,500,708 | every image must be decoded/reconciled |
| VideoClip | 31 | 8,338 | excluded target |
| **Total** | **47,939** | **1,068,259,162** | |

Estimated serialized bytes are catalogue measurements, not file-output sizes.

## Current decoded web export

Tracked run evidence reports:

- 2,222 WebP files;
- 29 lossless PNG twins used for cross-checking;
- 2,151 of 2,158 named entity-media joins resolved;
- seven named absences;
- a 20-sample pixel comparison with no mismatch.

This is the entity-web subset. It does not by itself prove that every
Texture2D, Sprite, atlas entry, font, shader, and eligible model has a decoded
or deliberately excluded product.

## Current policy

The old catalogue-first deferral for images and small models is retired.

- audio and video remain excluded;
- location models and models over 200 MB remain excluded;
- every text and image is mandatory;
- every non-location model under 50 MB is mandatory;
- animations and non-location models from 50–200 MB remain staged and
  inventoried pending an owner decision.

No container counts as an extracted image/model merely because its
`.bundle`/serialized object was retained.

## Completion reconciliation owed

The reviewer must produce a machine table with, for every source object:

- stable source identity;
- class and container;
- decoded output path(s), or exact policy exclusion;
- byte size and SHA-256;
- entity/site usage where applicable;
- duplicate-of identity for byte-identical duplicates only.

Required checks:

1. every Sprite resolves through its render data and texture;
2. every atlas slot is enumerated;
3. every Texture2D is decoded or identified as a byte-identical backing object
   already represented by resolved sprites;
4. every mesh is classified by location/non-location and size;
5. all eligible outputs below the Git cap are committed;
6. larger staged outputs are listed in PROOF with local path and byte total.

Until that table reconciles to the class universe, this document remains a
coverage ledger rather than a completion certificate.

<!-- END OF extracted/MEDIA-CATALOGUE.md -->
