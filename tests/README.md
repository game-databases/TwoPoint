# Two Point Campus test suite

The suite covers the thirteen-stage pipeline, fixture builders, contracts,
maps, logic, locales, media, search, and runner behavior.

## Commands

```bash
python -m pytest tests -q
python -m pytest tests -m "not client_gated" -q
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

## Current stage-review debt

The last committed map review demonstrated that several important behaviors
were not mutation-protected even though the suite was green:

- removing in-stage door-gate enforcement did not fail a test;
- deleting dual ID-space sweep results did not fail a test;
- the fifth-generation refusal path was exercised through the wrong gate;
- corpus-scale post-demotion uniqueness and reverse-join closure were absent.

The map identity repair must be re-proven with the existing suite, a
disposable working tree that deletes each of those behaviors, and a real-corpus
run. Do not add tests to this pack for that review. Passing the existing suite
alone cannot close the map blocker.

Search, media, logic, and contract suites also receive new stage reviews after
the map/media/relation changes that affect their inputs. The durable data-host
closeout protocol is in
[`../docs/reviewer-handoff.mdx`](../docs/reviewer-handoff.mdx). This debt is
separate from pull-request documentation review.

<!-- END OF tests/README.md -->
