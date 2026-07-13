# Sprint 3 — Worker Actuators That Produce Real Diffs

**Program:** Hermes 10/10 Productization  
**Target vertical slice:** Voice/Android cockpit -> gateway session -> job orchestration -> worker patch -> validation gate -> GitHub PR -> phone approval.  
**Operating rule:** do not add new capability lanes unless they directly close this loop.  
**Parallel execution model:** each sprint is split into independent agent lanes. Builder agents work in separate branches/worktrees. Reviewer agents consume patches after builders finish; they do not edit in parallel with the builder whose patch they review.

## Objective

Convert orchestration from proposal generation into actual implementation work. Workers must run inside isolated worktrees and return real `git diff` artifacts.

## Current gap

The orchestrator can fan out work and collect proposals, but a proposal-only worker cannot complete the Prompt -> PR loop. This sprint makes workers mutate files safely and measurably.

## Target worker lifecycle

```text
WorkPacket
  -> create isolated worktree
  -> render worker-specific prompt
  -> run worker command with timeout/resource policy
  -> capture stdout/stderr/logs
  -> collect git diff
  -> run worker-local tests if requested
  -> produce WorkerArtifact
  -> hand artifact to scoring/merge engine
```

## Files likely touched

- `hermes_cli/workers/base.py`
- `hermes_cli/workers/claude_code.py`
- `hermes_cli/workers/codex.py`
- `hermes_cli/workers/aider.py`
- `hermes_cli/workers/goose.py`
- `hermes_cli/workers/hermes_local.py`
- `hermes_cli/orchestrator.py`
- `hermes_cli/orchestrator_parallel.py`
- `hermes_cli/scoring.py`
- `tests/test_worker_*.py`
- `tests/fixtures/workers/*`

## Parallel agent lanes

| Lane | Agent | Branch | Mission |
|---|---|---|---|
| A | Worker Agent | `sprint/3-worker-contract` | Define `WorkerArtifact`, `WorkerResult`, timeout, patch collection utilities. |
| B | Claude Worker Agent | `sprint/3-claude-worker` | Implement Claude Code execution mode with proposal fallback. |
| C | Codex Worker Agent | `sprint/3-codex-worker` | Implement Codex CLI execution mode with proposal fallback. |
| D | Aider/Goose Agent | `sprint/3-aider-goose-workers` | Implement Aider and Goose actuators. |
| E | Hermes Local Agent | `sprint/3-hermes-local-worker` | Upgrade local worker from analysis to bounded patch mode where safe. |
| F | Security Agent | `sprint/3-worker-sandbox-policy` | Enforce allowed files, forbidden files, env scrubbing, command allowlists. |
| G | QA Agent | `sprint/3-worker-tests` | Build fake-worker fixtures that mutate repos deterministically. |
| H | Reviewer Agent | `sprint/3-review` | Review worker safety and patch determinism. |

## Required worker interface

```python
class WorkerAdapter:
    worker_id: str
    supports_execution: bool
    supports_proposal: bool

    def prepare(self, packet: WorkPacket, worktree: Path) -> WorkerPrepared: ...
    def execute(self, prepared: WorkerPrepared) -> WorkerArtifact: ...
    def collect(self, prepared: WorkerPrepared) -> WorkerArtifact: ...
```

`execute` must not return raw shell text directly to the UI. It returns structured status and redacted logs.

## Execution policy

- Each worker gets its own branch and worktree.
- No worker runs in the repo root.
- No worker gets secrets unless explicitly scoped.
- Allowed/forbidden file policies are enforced before and after execution.
- Timeout and max-log-size are mandatory.
- Network access defaults to inherited environment policy, not automatic.
- Proposal fallback is allowed only when the worker CLI is missing or execution is disabled.
- A worker that touches forbidden files returns `refuse` through the decision engine.

## Worker prompts

Every worker prompt must include:

- mission;
- repo root;
- allowed files;
- forbidden files;
- acceptance criteria;
- tests to run;
- output contract;
- rollback instructions;
- reminder not to change protected files without approval.

## Artifact layout

```text
~/.hermes/jobs/<job_id>/workers/<worker_id>/
  prompt.md
  stdout.log
  stderr.log
  status.json
  diff.patch
  diffstat.json
  test-output.txt
  notes.md
  risk-report.json
```

## QA fixtures

Create tiny repos for deterministic tests:

```text
tests/fixtures/repos/python_tiny/
tests/fixtures/repos/node_tiny/
tests/fixtures/repos/protected_file_repo/
tests/fixtures/workers/fake_success_worker.py
tests/fixtures/workers/fake_forbidden_file_worker.py
tests/fixtures/workers/fake_noop_worker.py
```

## Acceptance criteria

- At least one real worker path creates a real patch in tests.
- Fake workers verify patch collection independent of external CLIs.
- Missing external CLI degrades to proposal mode without crashing.
- Forbidden file changes are detected and blocked.
- Worker logs are redacted and size-capped.
- Scoring can compare diffs, not just prose proposals.

## Reviewer prompt

```text
Review worker actuator implementation. Verify each worker executes only in isolated worktrees, collects git diffs reliably, enforces allowed/forbidden paths, redacts logs, and degrades safely when external tools are missing. Try to find a path where a worker changes the main working tree or protected files.
```

## Definition of done

Hermes can run a coding worker against a fixture repo and produce a real patch artifact that later sprints can validate and publish.
