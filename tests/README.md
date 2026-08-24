# TwoPoint piece-1 test suite (TestWriter contract, spec §8)

Run: `python -m pytest tests/ -q` from the pack root. Stdlib-only; no game
bytes anywhere — fixtures are tiny synthetic files built in-repo.

## Result semantics

- **FAIL** — a spec-pinned contract broke (or the implementation is absent
  where absence is not excusable).
- **SKIP `impl-missing: …`** — the CodeWriter deliverable this test drives
  (`run_all.py`, `tools/stage*.py` symbols) is not present yet. Expected while
  implementation lands; every such skip names what it tried and is counted in
  the session-end `IMPL-MISSING SUMMARY` banner.
- **SKIP `client-gated…`** — real-install legs: auto-skipped when neither
  `TPC_GAME_DIR` nor `A:\SteamLibrary\steamapps\common\Two Point Campus`
  exists. Heavy legs additionally require `TPC_IT_HEAVY=1`.
- **SKIP `interruption-window-not-caught`** — the kill landed outside the
  write window after retries (convergence harness, R10).

## Surfaces

- Black-box primary surface: `python run_all.py <game> [--only <id>] [--force]`
  with `TPC_EXTRACTED_ROOT` pointed at a temp dir (never at the pack's own
  `extracted/`). Exit codes 0/1/2/3 per spec §4.
- Unit-level obligations whose effect isn't artifact-observable are driven
  through `tests/_impl.py`, which loads the spec-pinned script names under
  `tools/` and resolves functions from candidate-name lists derived from the
  spec's vocabulary. If CodeWriter used different internal names, those tests
  skip loudly (`impl-missing`) rather than guess or fake a pass — aligning the
  names (or accepting an adapter tweak) is a one-file fixer pass.
- Fixture trees: `python tests/build_fixture_tree.py --stage <id> [--full]
  [--metadata-version N]` (spec §5.2 hostless mode). Builders live in
  `tests/_fixturelib.py`; contract pins + validators in `tests/_validators.py`.

## Fixture shapes proposed as de-facto contracts

The synthetic upstream artifacts the builder emits follow the spec's output
shapes wherever pinned. Where the spec leaves shape open, the builder fixes a
concrete proposal that stage 5 must read:

- `harvest/monobehaviours/**/<family>/<class>/<bundle-stem>_<pathId>.json` →
  `{"_scriptClass": str, "class": str, "typetreeDecoded": bool,
  "fields": {…}}`
- `locales/locale-matrix.json` →
  `{"buildId", "locales": [13 BCP-47], "keys": {"<key>": {"locales": [...],
  "inBase": bool}}}`
- Roster `localeFlag` resolves to `'base'` or the BCP-47 code (the pipeline's
  convention), never the raw bundle suffix.
- Monobehaviour fixture entities carry string fields designed to exercise all
  three join outcomes: exact matrix-key equality (`joinInferred:false`),
  `<entityId>_<role>` convention shapes (`true` + `joinMethod`), prose-only
  (no join). `staff` has zero dumps (absence ledger); `WidgetConfig` has no
  seeded kind (`_unmapped-families`); `ItemBigConfig` has 1,200 rows
  (>1,000 → sorted-500 identifier sample).

Hostless runs read upstreams from AND write outputs into ONE extraction root:
each black-box test gets a private copy of the prepared tree's `extracted/`
(`conftest.seeded_extracted_root`) so session-shared trees stay pristine.

## Environment knobs

| Var | Effect |
|---|---|
| `TPC_GAME_DIR` | client-gated tests target this install root |
| `TPC_IT_HEAVY=1` | opt in to real-corpus stages 1–5 integration legs |
| `TPC_EXTRACTED_ROOT` | set by the suite per-run; outputs stay out of the repo |
