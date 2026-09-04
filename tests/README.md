# Two Point Campus test suite

The suite covers the thirteen-stage pipeline, fixture builders, contracts,
maps, logic, locales, media, search, runner behavior, and documentation
alignment.

## Commands

```bash
python -m pytest tests -q
python -m pytest tests -m "not client_gated" -q
python tools/check_documentation.py
```

Real-client legs use `TPC_GAME_DIR`. Heavy extraction legs also require
`TPC_IT_HEAVY=1`. Tests write to private fixture/extraction roots, never the
pack's production corpus.

## Result semantics

- **FAIL** means an asserted contract or guard is broken.
- **SKIP `client_gated`** means the installed game or explicit opt-in is
  unavailable.
- **SKIP `environment-missing`** names an absent tool such as `make`.
- An implementation-missing skip is not acceptable after the corresponding
  stage exists.
- Pipeline exit code `2` means named ledgered incompleteness, not clean
  success.

## Current review debt

The last committed map review demonstrated that several important behaviors
were not mutation-protected even though the suite was green:

- removing in-stage door-gate enforcement did not fail a test;
- deleting dual ID-space sweep results did not fail a test;
- the fifth-generation refusal path was exercised through the wrong gate;
- corpus-scale post-demotion uniqueness and reverse-join closure were absent.

The final fix must add tests that fail under each of those mutations and must
run against the real corpus. Passing the existing suite alone cannot close the
map blocker.

Search, media, logic, and contract suites also require one final review after
map/media policy changes. The durable closeout protocol is in
[`../docs/reviewer-handoff.mdx`](../docs/reviewer-handoff.mdx).

## Documentation guard

`tests/test_documentation.py` invokes the repository checker. It verifies the
canonical document set, retired placeholder/status phrases, documentation
classification, stage registry documentation, absence of the premature site
tree, and removal of superseded review/verification directories.

<!-- END OF tests/README.md -->
