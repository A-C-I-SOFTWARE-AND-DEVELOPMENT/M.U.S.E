# Scoring, merge, and quality council (Phase 14)

M.U.S.E. orchestrates several workers in parallel against the same task.
Phase 14 is the bookkeeper that runs *after* the workers finish: it
scores each one across sixteen categories, compares them, identifies
conflicts, picks the best candidate, and writes both a machine-readable
merge plan and a human-readable summary that a human (or the
orchestrator itself) can apply.

This page is the reference for three modules + one skill:

- [`hermes_cli/scoring.py`](../../hermes_cli/scoring.py) — turns worker
  artifacts on disk into a `Scorecard` per worker.
- [`hermes_cli/merge_engine.py`](../../hermes_cli/merge_engine.py) —
  consumes scorecards, applies the merge policy, and writes the six
  canonical output artifacts.
- [`skills/quality-council/SKILL.md`](../../skills/quality-council/SKILL.md)
  — the agent-facing playbook for invoking and interpreting the
  pipeline.

It supersedes the Phase 13 doc
[`scoring-and-merge-engine.md`](scoring-and-merge-engine.md), which
described the earlier 12-category schema.

## Worker artifacts

Each worker is expected to produce a directory with five files:

```
workers/<worker_id>/
    output.md              # human-readable narrative
    patch.diff             # unified diff against the repo root
    changed-files.txt      # newline-separated relative paths
    validation-output.txt  # captured stdout/stderr of validation/test run
    status.json            # structured metadata (see below)
```

Missing files do not raise — `load_artifact` records them in
`WorkerArtifact.missing` and the scoring layer downgrades the worker.
The legacy filename `test-output.txt` is accepted as an alias for
`validation-output.txt` so older worker adapters keep working.

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

### Optional pipeline inputs

`run_merge` (and the underlying `score_artifact`) accept two optional
inputs that flow through from the orchestrator:

- **`decision_ledger`** — a sequence of prior decision entries. The
  Council reads each entry's `worker_id` and `outcome` and surfaces a
  note when the same worker has been rejected before.
- **`user_profile`** — the project owner's preferences. A
  `category_preferences` mapping inside it can override any category
  on any worker. The most common use is biasing `jeremiah_fit` toward
  what the owner actually cares about that week.

## Scoring categories

`scoring.SCORE_CATEGORIES` is the single source of truth. The sixteen
Phase 14 categories and how they're derived:

| category | dominant signal |
| --- | --- |
| `correctness` | Did validation pass? Did the worker declare success? Is the patch non-empty? |
| `completeness` | Are all required artifacts present? Did the worker write meaningful prose? |
| `maintainability` | Diff size: small focused diffs score higher than sprawling ones. |
| `testability` | Were tests added? Did they pass? Is the change high-risk? |
| `architecture_fit` | Self-score, falling back to a heuristic on diff breadth and risk surface. |
| `repo_fit` | Does `patch.diff` actually look like a `diff --git` patch? Are claimed files reflected? |
| `security` | Combination of validation outcome, high-risk path touches, and diff size. |
| `secrets_safety` | Scans diff additions for AWS/GitHub/OpenAI/Slack tokens, PEM keys, `password = "..."` patterns. A hit gives 0.0. |
| `mobile_fit` | Did the change touch `apps/android`, `termux`, `ios`, `react-native`, `/mobile`? Did validation pass? |
| `voice_fit` | Did the change touch `voice`, `tts`, `stt`, `whisper`, `speech`, `audio`? Did validation pass? |
| `remote_execution_fit` | Penalises `os.isatty`, `127.0.0.1`/`localhost`, hard-coded `/home/<user>/` paths. |
| `developer_experience` | Output-narrative depth, plus a boost when docs/help/error paths were touched. |
| `ui_ux` | Self-score; falls back to legacy `ux_quality` self-score; finally falls back to output-narrative depth. |
| `speed` | Self-score, falling back to a curve over `elapsed_seconds`. |
| `cost_efficiency` | Self-score, falling back to a curve over `tokens`. |
| `jeremiah_fit` | Project-owner alignment. Defaults to `0.4 * secrets_safety + 0.3 * security + 0.3 * remote_execution_fit`; overridable via `user_profile.category_preferences.jeremiah_fit`. |

Every category is bounded to `[0.0, 1.0]`. A missing category resolves
to `0.5` (soft-neutral) rather than `0.0`, so a worker that omitted a
self-score is not punished as if it had failed it.

### Weighted ranking

The merge engine ranks workers by `weighted_total`. Weights are
defined in `_CATEGORY_WEIGHTS`:

```
correctness          = 3.0
secrets_safety       = 2.5
security             = 2.2
completeness         = 1.5
testability          = 1.5
maintainability      = 1.2
repo_fit             = 1.2
architecture_fit     = 1.2
ui_ux                = 1.0
developer_experience = 1.0
remote_execution_fit = 1.0
jeremiah_fit         = 1.0
mobile_fit           = 0.9
voice_fit            = 0.7
speed                = 0.8
cost_efficiency      = 0.8
```

The intuition: a beautifully-written change that breaks its
tests is still worse than a clunky change that passes them — and a
change that leaks a secret is unshippable no matter how good it looks
otherwise.

## Merge policy

`merge_engine.run_merge` is the public entry point. Internally it
applies five rules in order:

1. **Reject high-risk workers without tests.** Any worker that
   touched a path matching one of the high-risk hints
   (`auth`, `secret`, `crypto`, `billing`, `payment`, `migration`,
   `schema`, `policy`, `permission`, `gateway`) and did not add tests
   is rejected outright — even if its weighted score is highest. The
   policy is hard-coded; flip `HIGH_RISK_TEST_REQUIRED` in the module
   if you ever want to disable it (don't).
2. **Reject leaked secrets.** Any worker whose `secrets_safety` falls
   below `SECRETS_SAFETY_FLOOR` (0.5) is rejected outright. The
   secret-pattern scanner runs only against diff additions, so adding
   a regression test for a known leak doesn't trigger the gate.
3. **Apply a score floor.** Workers below `SCORE_FLOOR` (0.45) are
   rejected with a recorded reason.
4. **Rank survivors.** `scoring.rank` sorts by `weighted_total`, then
   by `correctness`, then by smaller diff size, then by worker id for
   determinism. The top entry wins.
5. **Detect conflicts.** Any file modified by two or more *surviving*
   candidates becomes a `FileConflict` and is recorded — but does not
   automatically block the winner. The conflict report instructs the
   human to verify the winning patch resolved the file correctly.

The engine never splices patches together. The intuition is the same
as for `git merge`: blindly combining diffs from independent agents is
how you get a Frankenstein patch that compiles but is wrong. If you
want pieces from two workers, lift them by hand — and the
`council-review.md` is structured to make that easy.

### Manual-review gate

The final plan is marked `MANUAL REVIEW REQUIRED` when any of the
following holds:

- The winning worker scored below `MANUAL_REVIEW_FLOOR` (0.55).
- The winning worker's validation reported failures.
- There were conflicts between candidates.

When manual review is required, all six artifacts are still written,
including `final-patch.diff`. The orchestrator is expected to honour
the gate before running `git apply`.

## Output artifacts

`run_merge` writes six files under the `out_dir` it's given:

| file | purpose |
| --- | --- |
| `scorecard.json` | Machine-readable summary; schema `hermes.merge.scorecard.v2`. |
| `council-review.md` | Human-readable: winner, full score table, rejected, runners-up, conflicts, validation. |
| `conflict-report.md` | Per-file conflict details (or "no conflicts detected"). |
| `final-plan.md` | The application plan — what to apply, when manual review is needed, how. |
| `final-patch.diff` | The winning worker's diff verbatim; empty if no winner. |
| `plain-english-summary.md` | One-page jargon-free summary for the project owner on their phone. |

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
    user_profile={"category_preferences": {"jeremiah_fit": 0.9}},
    decision_ledger=[
        {"worker_id": "alpha", "outcome": "rejected", "reason": "leak"},
    ],
)

if result.manual_review_required:
    raise SystemExit("merge needs a human; see ./run-123/merge/final-plan.md")

# Otherwise the orchestrator can:
#   git apply --3way ./run-123/merge/final-patch.diff
```

## Migrating from Phase 13

Phase 13 used twelve categories. Phase 14's sixteen are a superset plus
two renames:

| Phase 13 | Phase 14 |
| --- | --- |
| `risk_control` | split into `security` + `secrets_safety` |
| `ux_quality` | renamed to `ui_ux` (legacy `ux_quality` self-scores still honoured) |
| `local_first_fit` | renamed and rebaselined as `remote_execution_fit` |
| _(new)_ | `mobile_fit` |
| _(new)_ | `voice_fit` |
| _(new)_ | `developer_experience` |

The JSON schema bumped from `hermes.merge.scorecard.v1` to
`hermes.merge.scorecard.v2`. Old workers that emit `test-output.txt`
instead of `validation-output.txt` keep working — the loader accepts
both.

## Testing

- [`tests/test_scoring.py`](../../tests/test_scoring.py) covers
  artifact loading (including the legacy filename alias), the
  per-category scoring heuristics, user_profile + decision_ledger
  pass-through, the weighted-total math, and the rank tiebreakers.
- [`tests/test_merge_engine.py`](../../tests/test_merge_engine.py)
  covers the policy gates (high-risk, secrets, score floor),
  conflict detection, manual-review triggering, the six output
  artifacts, and `user_profile` / `decision_ledger` plumbing
  through `run_merge`.

Both suites are pure-Python — no subprocess, no LLM, no filesystem
state beyond `tmp_path` — so they run in well under a second.
