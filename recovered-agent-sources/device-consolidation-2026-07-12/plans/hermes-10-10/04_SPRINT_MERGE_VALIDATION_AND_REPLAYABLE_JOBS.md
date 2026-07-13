# Sprint 4 — Merge Engine, Validation Gates, and Replayable Jobs

**Program:** Hermes 10/10 Productization  
**Target vertical slice:** Voice/Android cockpit -> gateway session -> job orchestration -> worker patch -> validation gate -> GitHub PR -> phone approval.  
**Operating rule:** do not add new capability lanes unless they directly close this loop.  
**Parallel execution model:** each sprint is split into independent agent lanes. Builder agents work in separate branches/worktrees. Reviewer agents consume patches after builders finish; they do not edit in parallel with the builder whose patch they review.

## Objective

Turn worker patches into a deterministic, validated job result with full replay history.

## Architecture

```text
WorkerArtifact(s)
  -> score candidates
  -> select winner or merge compatible patches
  -> apply to integration worktree
  -> run validation gates
  -> create validated patch artifact
  -> create DecisionVerdict
  -> record replayable job events
```

## Files likely touched

- `hermes_cli/merge_engine.py`
- `hermes_cli/scoring.py`
- `hermes_cli/validation.py`
- `hermes_cli/job_controller.py`
- `hermes_cli/orchestrator_models.py`
- `hermes_cli/orchestrator.py`
- `hermes_cli/kanban_db.py`
- `tests/test_merge_engine*.py`
- `tests/test_validation*.py`
- `tests/test_job_replay*.py`

## Parallel agent lanes

| Lane | Agent | Branch | Mission |
|---|---|---|---|
| A | Merge Agent | `sprint/4-merge-engine` | Apply winning or compatible patches into integration worktree. |
| B | Validation Agent | `sprint/4-validation-gates` | Expand gates: structure, tests, secrets, unicode, policy, protected paths, dependency lock, Android manifest. |
| C | State Agent | `sprint/4-job-events` | Implement append-only JobEvent stream and replay cursor. |
| D | Scoring Agent | `sprint/4-scoring` | Score diffs with correctness, validation, risk, size, and prior worker reliability. |
| E | QA Agent | `sprint/4-tests` | Conflict fixtures, validation fixtures, replay tests. |
| F | Reviewer Agent | `sprint/4-review` | Review determinism and unsafe merge paths. |

## Merge policy

1. If one worker passes all validations and others fail, choose the passing worker.
2. If multiple pass and modify disjoint files, merge if risk is acceptable.
3. If multiple pass and overlap, choose highest score unless a deterministic 3-way merge succeeds and tests pass.
4. If no patch passes validation, produce a failure artifact and no publishable result.
5. Never auto-merge protected-file changes without an `ask` verdict.
6. Never publish a patch with secret findings.

## Validation gates

Required gates for 10/10 loop:

| Gate | Purpose | Blocking? |
|---|---|---|
| Structure | Artifact schema, patch presence, valid paths. | Yes |
| Tests | Run requested test commands. | Yes for code patches |
| Secrets | Scan diff/logs/artifacts for credentials. | Yes |
| Unicode/encoding | Prevent Windows/locale regressions. | Yes |
| Policy | Decision engine risk verdict. | Yes |
| Protected paths | Detect sensitive file mutation. | Ask/refuse |
| Dependency lock | Ensure pyproject/lock consistency. | Yes when deps change |
| Android manifest | Detect permission additions. | Ask/refuse |

## Replayable state

Every job event must be persisted:

```text
job.created
worker.started
worker.completed
worker.failed
patch.collected
score.completed
merge.selected
validation.started
validation.completed
decision.created
approval.requested
approval.resolved
publish.created
job.completed
job.failed
```

The event store must support:

```text
GET events since cursor
GET latest job snapshot
rebuild job snapshot from events
redacted event export
```

## Acceptance criteria

- Merge engine can apply a patch from a fake worker into an integration worktree.
- Conflicting patches produce deterministic outcome.
- Validation gates block bad patches.
- Job state can be reconstructed from event log.
- Approval events survive process restart.
- Failed jobs produce useful artifacts.

## Reviewer prompt

```text
Review merge/validation/replay implementation. Check for nondeterministic merge behavior, missing validation gates, unredacted event payloads, and cases where a failed validation can still publish. Verify job replay reconstructs the same snapshot after restart.
```

## Definition of done

Hermes can produce one validated patch artifact from multiple worker attempts, explain why it won, and replay the entire job history after restart.
