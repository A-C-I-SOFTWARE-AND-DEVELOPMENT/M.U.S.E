# TOKENJUICE-TRUNCATION-001

Tracking brief for a pre-existing, `main`-red test failure. **Standalone**
work item — intentionally separate from the muse learning-dataset
pipeline (PR #222), which did not cause and must not fix this.

## Symptom

The `test` job (`.github/workflows/tests.yml`) fails on two tool-result
truncation tests:

- `tests/run_agent/test_run_agent.py::TestExecuteToolCalls::test_result_truncation_over_100k`
- `tests/run_agent/test_run_agent.py::TestConcurrentToolExecution::test_concurrent_truncates_large_results`

Both assert a large tool result contains `"Truncated"` or
`"<persisted-output>"`, but the observed content ends in
`…[tokenjuice: clamped]`:

```
AssertionError: assert ('Truncated' in 'xxxx…\n…[tokenjuice: clamped]'
                         or '<persisted-output>' in 'xxxx…\n…[tokenjuice: clamped]')
```

## Root cause (hypothesis)

The TokenJuice plugin clamps an oversized tool result (appending
`…[tokenjuice: clamped]`) **before** `run_agent.py`'s truncation /
persist-to-disk path runs, so the result never receives the
`"Truncated"` / `"<persisted-output>"` marker the tests expect. This is an
**ordering** problem between two output-shrinking mechanisms, not a logic
bug in either alone.

## Evidence it is pre-existing (not from PR #222)

- `main` is already red: `tests.yml` run `26883901520` (sha `32263a86`,
  PR #212 merge) has the `test` job at conclusion **failure** on these
  same tests.
- PR #222 touches **none** of `run_agent.py`, `tokenjuice`,
  `model_tools.py`, or `toolset*` (`git diff --name-only origin/main...HEAD`),
  and its 23 new tests pass.

## Scope of the fix (to be done here, separately)

- [ ] Investigate the ordering between TokenJuice clamping and tool-result
      truncation/persistence in `run_agent.py` and the rules under
      `tools/tokenjuice/`.
- [ ] Decide the correct behavior, one of:
  - **(a)** TokenJuice **skips oversized tool results**, letting the
        truncation/persist path own them (so the marker is emitted), or
  - **(b)** relax the two tests to accept the `…[tokenjuice: clamped]`
        outcome as a valid clamped result.
- [ ] Add focused regression tests for the chosen behavior (oversized
      result → expected outcome, and the ordering guarantee).

## Non-goals

- No learning-dataset, gateway-cockpit, muse-CLI, or Android changes.
- Do not bundle this with PR #222.

## References

- PR #222 `test` job: run `26899541650`.
- `main` `test` job: run `26883901520`.
