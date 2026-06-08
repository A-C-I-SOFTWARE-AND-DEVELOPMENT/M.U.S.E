# Scoring and merge engine (Phase 13)

M.U.S.E. orchestrates several workers in parallel against the same task.
Phase 13 is the bookkeeper that runs *after* the workers finish: it
scores each one, compares them, identifies conflicts, picks the best
candidate, and writes a merge plan that a human (or the orchestrator
itself) can apply.

This page covers two modules:

- [`hermes_cli/scoring.py`](../../hermes_cli/scoring.py) — turns worker
  artifacts on disk into a `Scorecard` per worker.
- [`hermes_cli/merge_engine.py`](../../hermes_cli/merge_engine.py) —
  consumes scorecards, applies the merge policy, and writes the five
  canonical output artifacts.

## Worker artifacts

Each worker is expected to produce a directory with five files:

```
workers/<worker_id>/
    output.md          # human-readable narrative
    patch.diff         # unified diff against the repo root
    changed-files.txt  # newline-separated relative paths
    test-output.txt    # captured stdout/stderr of the test run
    status.json        # structured metadata (see below)
```

Missing files do not raise — `load_artifact` records them in
`WorkerArtifact.missing` and the scoring layer downgrades the worker.

### `status.json` shape

The runtime expects an object. Recognised top-level keys:

| key | type | meaning |
| --- | --- | --- |
| `success` / `ok` | bool | Worker considered itself done. |
| `profile` / `model` / `agent` | string | Model or persona label. |
| `elapsed_seconds` | number | Wall-clock cost; feeds `speed`. |
| `tokens` / `total_tokens` | number | Token cost; feeds `cost_efficiency`. |
| `self_scores` | object | Worker's own scores per category (clamped to [0, 1]). |
| `<category>_score` | number | Flat alternative for self-scores. |

Anything else is preserved on the `Scorecard` for downstream tooling
but does not affect the score.

## Scoring categories

`scoring.SCORE_CATEGORIES` is the single source of truth. The twelve
categories and how they're derived:

| category | dominant signal |
| --- | --- |
| `correctness` | Did the tests pass? Did the worker declare success? Is the patch non-empty? |
| `completeness` | Are all required artifacts present? Did the worker write meaningful prose? |
| `testability` | Were tests added? Did they pass? Is the change high-risk? |
| `maintainability` | Diff size: small focused diffs score higher than sprawling ones. |
| `repo_fit` | Does `patch.diff` actually look like a `diff --git` patch? Are claimed files reflected? |
| `architecture_fit` | Self-score, falling back to a heuristic on diff breadth and risk surface. |
| `risk_control` | Combination of test outcome, high-risk path touches, and diff size. |
| `ux_quality` | Self-score, falling back to depth of `output.md`. |
| `speed` | Self-score, falling back to a curve over `elapsed_seconds`. |
| `cost_efficiency` | Self-score, falling back to a curve over `tokens`. |
| `local_first_fit` | Penalises external-network references in the patch (M.U.S.E. is local-first). |
| `jeremiah_fit` | Project-owner alignment: defaults to 0.5 * `local_first_fit` + 0.5 * `risk_control`. |

Every category is bounded to `[0.0, 1.0]`. A missing category resolves
to `0.5` (soft-neutral) rather than `0.0`, so a worker that omitted a
self-score is not punished as if it had failed it.

### Weighted ranking

The merge engine ranks workers by `weighted_total`. Weights are
defined in `_CATEGORY_WEIGHTS`:

```
correctness     = 3.0
risk_control    = 2.5
completeness    = 1.5
testability     = 1.5
maintainability = 1.2
repo_fit        = 1.2
architecture_fit= 1.2
ux_quality      = 1.0
local_first_fit = 1.0
jeremiah_fit    = 1.0
speed           = 0.8
cost_efficiency = 0.8
```

The intuition: a beautifully-written change that breaks its tests is
still worse than a clunky change that passes them.

## Merge policy

`merge_engine.run_merge` is the public entry point. Internally it
applies four rules in order:

1. **Reject high-risk workers without tests.** Any worker that
   touched a path matching one of the high-risk hints
   (`auth`, `secret`, `crypto`, `billing`, `payment`, `migration`,
   `schema`, `policy`, `permission`, `gateway`) and did not add tests
   is rejected outright — even if its weighted score is highest. The
   policy is hard-coded; flip `HIGH_RISK_TEST_REQUIRED` in the module
   if you ever want to disable it (don't).
2. **Apply a score floor.** Workers below `SCORE_FLOOR` (0.45) are
   rejected with a recorded reason.
3. **Rank survivors.** `scoring.rank` sorts by `weighted_total`, then
   by `correctness`, then by smaller diff size, then by worker id for
   determinism. The top entry wins.
4. **Detect conflicts.** Any file modified by two or more *surviving*
   candidates becomes a `FileConflict` and is recorded — but does not
   automatically block the winner. The conflict report instructs the
   human to verify the winning patch resolved the file correctly.

The engine never splices patches together. The intuition is the same
as for `git merge`: blindly combining diffs from independent agents is
how you get a Frankenstein patch that compiles but is wrong. If you
want pieces from two workers, lift them by hand.

### Manual-review gate

The final plan is marked `MANUAL REVIEW REQUIRED` when any of the
following holds:

- The winning worker scored below `MANUAL_REVIEW_FLOOR` (0.55).
- The winning worker's tests reported failures.
- There were conflicts between candidates.

When manual review is required, all five artifacts are still written,
including `final-patch.diff`. The orchestrator is expected to honour
the gate before running `git apply`.

## Output artifacts

`run_merge` writes five files under the `out_dir` it's given:

| file | purpose |
| --- | --- |
| `scorecard.json` | Machine-readable summary; schema `hermes.merge.scorecard.v1`. |
| `council-review.md` | Human-readable: winner, rejected, runners-up, conflicts, validation. |
| `conflict-report.md` | Per-file conflict details (or "no conflicts detected"). |
| `final-plan.md` | The application plan — what to apply, when manual review is needed, how. |
| `final-patch.diff` | The winning worker's diff verbatim; empty if no winner. |

A template scorecard lives at
[`templates/orchestration/scorecard.json`](../../templates/orchestration/scorecard.json)
and a template review at
[`templates/orchestration/council-review.md`](../../templates/orchestration/council-review.md).

## Usage example

```python
from pathlib import Path
from hermes_cli.merge_engine import run_merge

result = run_merge(
    workers_dir=Path("./run-123/workers"),
    out_dir=Path("./run-123/merge"),
)

if result.manual_review_required:
    raise SystemExit("merge needs a human; see ./run-123/merge/final-plan.md")

# Otherwise the orchestrator can:
#   git apply --3way ./run-123/merge/final-patch.diff
```

## Testing

- [`tests/test_scoring.py`](../../tests/test_scoring.py) covers
  artifact loading, the per-category scoring heuristics, the
  weighted-total math, and the rank tiebreakers.
- [`tests/test_merge_engine.py`](../../tests/test_merge_engine.py)
  covers the policy gates, conflict detection, manual-review
  triggering, and the five output artifacts.

Both suites are pure-Python — no subprocess, no LLM, no filesystem
state beyond `tmp_path` — so they run in well under a second.
