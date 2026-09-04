# Two Point Campus — current validation report

**Scope:** repository and tracked evidence review  
**Date:** 2026-09-04  
**Overall verdict:** **DATA GATE FAIL; REVIEW PR MERGEABLE AFTER HANDOFF
EVIDENCE IS RECORDED**

## Validation matrix

| Gate | Verdict | Basis |
|---|---|---|
| client identity and 176-bundle roster | PASS in tracked evidence | extraction log and roster counts |
| thirteen client locales + base overlay | PASS in tracked evidence | localization run and locale-proof outputs |
| single thirteen-stage entrypoint | PASS by source inspection | `run_all.py` registry |
| structural decompile | PASS in tracked evidence | 101 dummy DLL images, hierarchy and registries |
| deterministic stage/output contracts | PARTIAL | multiple stages report byte-stable runs; final reviewed-tree rerun outstanding |
| relation matrix emitted | PASS | 100 cells present |
| relation exhaustion | FAIL | 73 missing, 3 partial, unresolved ledgers, competitor sources not applied |
| map data correctness | FAIL | identity collisions and broken reverse joins in latest review |
| logic reconstruction | PARTIAL | four families emitted; two native carriers remain |
| locale availability ownership | PASS by source inspection | stage 9 owns current file; old stage-5 wording retired |
| mandatory image/model coverage | FAIL | partial entity-web export is not full class reconciliation |
| corpus Git/Mac/prod staging | NOT PROVEN | old blanket ignore prevented inventory from being visible here |
| PROOF document present | PASS | placeholder replaced with measured evidence and explicit failure verdict |
| protocol inventory | PASS for current known surface | no gameplay server plane; Steamworks/crash/Ansel inventory |
| site/frontend gate | PASS as a guard | premature site implementation removed |
| production/SEO/browser/CWV | NOT APPLICABLE | site phase has not opened |

## Static documentation review

The canonical pack documents have been rewritten around one current phase and
one evidence chain. Superseded review and verification transcript directories
are removed after consolidation. `docs/README.mdx` classifies retained scouts,
piece specs, and rulings as historical evidence/contracts rather than live
status.

`tools/check_documentation.py` and `tests/test_documentation.py` guard:

- required canonical documents;
- stage-list documentation;
- retired placeholder and bootstrap claims;
- retired tier/hub-placement language in canonical pack state;
- absence of a `site/` tree while the data gate is closed;
- removal of superseded review/verification directories.

## Review findings that remain load-bearing

### Map implementation

- post-demotion uniqueness not guaranteed;
- placement room IDs and layer plot IDs do not reliably follow demoted
  identities;
- door-gate enforcement lacks emitter-path mutation teeth;
- dual ID-space sweep results lack result-level teeth;
- closed generation vocabulary refusal is tested through the wrong gate;
- fabricated fallback provenance and crash-log coverage require correction.

### Cross-stage

- media implementation predates the current mandatory extraction policy;
- competitor models are harvested but not applied;
- search, media, logic, and contract build reviews need a final follow-up after
  shared fixes;
- host source-hash parity and current full rerun are not recorded.

## Required final evidence

The exact commands, measurements, mutation tests, corpus-size audit, and
documentation updates are in
[`../docs/reviewer-handoff.mdx`](../docs/reviewer-handoff.mdx). The reviewing
agent must replace each pending row there with observed results before merge.
No chat-only result closes a gate.

<!-- END OF extracted/VALIDATION-REPORT.md -->
