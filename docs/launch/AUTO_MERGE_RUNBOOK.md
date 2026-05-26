# LaunchGate — Auto-Merge Runbook

How an operator (or an agent acting on the operator's behalf) enables
GitHub auto-merge once a PR has cleared the LaunchGate criteria in
[`AUTOMATED_MERGE_POLICY.md`](AUTOMATED_MERGE_POLICY.md).

Auto-merge **queues** the merge: GitHub holds the merge until every
required check passes, then fires it. If a check goes red while the
queue is waiting, the merge does **not** fire and auto-merge stays
queued until the operator addresses the failure or disables the
queue.

## 1. Inspect the PR

```
gh pr view <PR> --json mergeable,reviewDecision,statusCheckRollup
```

What to look for:

- `"mergeable": "MERGEABLE"` — no conflicts, base is up to date
  enough for the configured merge strategy.
- `"reviewDecision": "APPROVED"` — branch protection's required-
  reviewer count is satisfied. (If branch protection doesn't require
  reviews, this may be `null`; that's fine.)
- `"statusCheckRollup"` — every required check is `SUCCESS`. If any
  required check is `FAILURE`, `CANCELLED`, or `PENDING`, do not
  enable auto-merge yet.

## 2. Confirm the required checks individually

```
gh pr checks <PR>
```

Cross-reference the output against the LaunchGate criteria:

- `Tests` (`.github/workflows/tests.yml`) — Python pytest.
- `Orchestration tests` (`.github/workflows/orchestration-tests.yml`).
- `Lint (ruff + ty)` → `ruff enforcement (blocking)`
  (`.github/workflows/lint.yml`).
- `Android build` → `Build debug APK` and `Lint`
  (`.github/workflows/android-build.yml`).

If `testDebugUnitTest` is required by policy but not yet a job in
`android-build.yml`, attach the local Gradle report:

```
cd apps/android && ./gradlew --no-daemon --stacktrace testDebugUnitTest
```

Paste the result summary into the PR before enabling auto-merge. Do
not silently lower the bar.

## 3. Enable auto-merge

Once the criteria are satisfied, enable GitHub auto-merge with squash
strategy:

```
gh pr merge <PR> --auto --squash
```

This queues the merge. GitHub will:

1. Wait for every required check to report success.
2. Wait for branch protection (review approvals, conversation
   resolution, signed commits if required) to be satisfied.
3. Fire the merge automatically.

If any condition flips back to failing, the queued merge will not
fire until the condition is addressed and re-evaluated.

## 4. Watch the queue

```
gh pr view <PR> --json autoMergeRequest,mergeStateStatus
```

- `autoMergeRequest` is non-null while the queue is active.
- `mergeStateStatus`:
  - `CLEAN` → will merge.
  - `BLOCKED` → branch protection is holding it (missing review,
    missing check, draft state, etc.); **branch protection wins** —
    fix the block, don't bypass it.
  - `BEHIND` → base advanced; allow GitHub to auto-update the branch
    or run `gh pr update-branch <PR>`.
  - `UNSTABLE` → non-required check is failing; queue still valid,
    but worth investigating.

## 5. If auto-merge must be cancelled

```
gh pr merge <PR> --disable-auto
```

Use this if a regression is discovered after queuing, the PR needs
significant changes, or the launch checklist has been invalidated.

## Hard "don'ts"

- **No** `gh pr merge --merge` / `--rebase` / `--squash` without
  `--auto` when the LaunchGate criteria are not yet satisfied. That's
  a manual merge of a red or unreviewed PR and is exactly what this
  policy replaces.
- **No** `git push --force` to `main` or to a release branch. The
  `force_push` runtime gate still requires the owner phrase.
- **No** branch-protection bypass, **no** admin override merges,
  **no** disabling required checks to clear a queue.
- **No** auto-closing of superseded/duplicate PRs from this flow; a
  cleanup workflow is a separate, individually approved change.

## Quick reference

| Command | Purpose |
|---|---|
| `gh pr view <PR> --json mergeable,reviewDecision,statusCheckRollup` | LaunchGate readiness snapshot |
| `gh pr checks <PR>` | Per-check status, including Android + Python + ruff |
| `gh pr merge <PR> --auto --squash` | Enable auto-merge |
| `gh pr view <PR> --json autoMergeRequest,mergeStateStatus` | Watch the queue |
| `gh pr merge <PR> --disable-auto` | Cancel queued auto-merge |

For the gate criteria themselves, see
[`AUTOMATED_MERGE_POLICY.md`](AUTOMATED_MERGE_POLICY.md).
