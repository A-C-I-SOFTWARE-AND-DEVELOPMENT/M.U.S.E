# Job controller (Phase 12)

The **job controller** is the Python module that turns the
`hermes_cli.orchestrator` module-level API into the safe, auditable
phase loop documented in the [orchestration README](README.md).  It is
the thing that actually drives a job from "user said *do this*" to
"PR body sitting in the publish folder."

This document is a contract: anything described here is part of the
controller's public surface.  Things not described here are
implementation detail and may change.

## Where it lives

| File | Purpose |
|---|---|
| `hermes_cli/orchestrator.py` | Module-level controller API + slash command surface |
| `hermes_cli/orchestrator_models.py` | `Job` / `WorkerSpec` / `JobState` dataclasses |
| `hermes_cli/workflows.py` | Phase definitions, ordering, approval-gate metadata |
| `hermes_cli/decision_ledger.py` | Append-only JSONL ledger per job |
| `hermes_cli/model_router.py` | Stub-quality `route_for(phase, mode)` decision |
| `hermes_cli/job_queue.py` | Persisted FIFO queue of job ids |
| `hermes_cli/job_controller.py` | Lower-level filesystem-only `JobController` class |

## On-disk layout

The controller keeps every job under `$HERMES_HOME/orchestrator/`:

```
$HERMES_HOME/orchestrator/
    jobs.json                       # legacy flat record (status, prompt, ...)
    queue.json                      # FIFO queue of job ids
    decision_ledger.json            # legacy slash-command ledger
    jobs/
        <job-id>/
            README.md
            ledger.jsonl            # the Phase 12 decision ledger
            phases/
                intake.md
                research.md
                planning.md
                implementation.md
                validation.md
                publish/             # written by prepare_publish_phase
                    pr_body.md
                    manifest.json
            workers/
                <worker-id>/
                    prompt.md
                    artifacts/
```

Everything is plain text or JSON.  `cat`-friendly by design.

## Phases

```
intake → research → planning → implementation → validation → publish → retrospective
                              ^^^^^^^^^^^^^^                 ^^^^^^^
                              approval-gated                 approval-gated
```

| Phase            | Mutates local | Mutates remote | Approval required |
|------------------|:-------------:|:--------------:|:-----------------:|
| intake           |       —       |        —       |        —          |
| research         |       —       |        —       |        —          |
| planning         |       —       |        —       |        —          |
| **implementation** |     yes     |        —       |       **yes**     |
| validation       |       —       |        —       |        —          |
| **publish**      |       —       |       yes      |       **yes**     |
| retrospective    |       —       |        —       |        —          |

Definitions live in `hermes_cli/workflows.py` —
`PHASES_ORDERED`, `APPROVAL_GATED_PHASES`,
`NEVER_AUTO_IN_LISTENING_MODE`, `PHASE_SPECS`.

## Public API

All controller functions are exported from
`hermes_cli.orchestrator`.  See the module docstring for the full
list; the highlights:

### Job lifecycle

```python
from hermes_cli import orchestrator as orch

job = orch.create_job(
    prompt="Add a /healthz endpoint and a smoke test",
    repo_root="/srv/example",
    mode="build",
    trusted_local=True,
)
orch.load_job(job.id)               # raises if missing
orch.list_jobs()                    # newest first
orch.update_job_status(job.id, "running")
orch.cancel_job(job.id, reason="user pressed ESC")
orch.resume_job(job.id)             # re-queues a paused/failed job
```

`create_job` also calls `initialize_job_artifacts` so the job's
`phases/`, `workers/`, and `publish/` directories exist before the
first phase runs.

### Phase loop

```python
orch.run_intake_phase(job.id)
orch.run_research_phase(job.id)
orch.run_planning_phase(job.id)

# Approval gate
orch.request_approval(job.id, "implementation")
orch.grant_approval(job.id, "implementation")
orch.run_implementation_phase(job.id)

orch.run_validation_phase(job.id)

# Second approval gate
orch.request_approval(job.id, "publish")
orch.grant_approval(job.id, "publish")
orch.prepare_publish_phase(job.id)

orch.run_retrospective_phase(job.id)
```

Each `run_*_phase` enforces its precondition: research requires
intake to be complete, planning requires research, etc.  Calling them
out of order raises `orch.PhaseError`.

### Approval shortcuts

```python
# Equivalent to request_approval + grant_approval + run_implementation_phase
orch.run_implementation_phase(job.id, approve=True)
```

`approve=True` records the approval at the same time it runs the
phase; useful in scripts where the human approval is implicit.

### Remote execution

The `remote=True` keyword tells the controller that the phase will
reach off-device infrastructure (a CI runner, a hosted code-edit
session, a cloud Modal job).  Remote phases **always** require an
explicit approval — `approve=True` works, but the controller refuses
to auto-run them otherwise, regardless of `trusted_local`.

```python
# Always raises ApprovalRequired the first time:
orch.run_implementation_phase(job.id, remote=True)

# Approved + remote:
orch.run_implementation_phase(job.id, remote=True, approve=True)
```

### Continuous-listening mode

The gateway flips on continuous-listening mode whenever muse is
running as a passive listener (Telegram, Discord, Signal, etc.).  In
that mode the controller refuses to auto-run `implementation` or
`publish` even if the caller forgets the `approve=False` default:

```python
orch.set_continuous_listening(True)
orch.run_implementation_phase(job.id)   # → ApprovalRequired
```

Tests reset this flag between cases via the `_reset_phase12_state`
fixture in `tests/test_orchestrator_job_controller.py`.

### Decision ledger

Every transition records two entries:

1. A line in `$HERMES_HOME/orchestrator/decision_ledger.json` (the
   legacy slash-command surface, read by `/decision-ledger show`).
2. A JSONL line in `$HERMES_HOME/orchestrator/jobs/<id>/ledger.jsonl`
   (the Phase 12 audit log, read by `hermes_cli.decision_ledger.open_ledger`).

The Phase 12 ledger captures: `create_job`, `phase_enter`,
`phase_complete`, `approval_requested`, `approval_granted`, `route`,
`status`, `publish_prepared`, `cancel`.  Add new kinds rather than
mutating existing ones.

## Safe-by-default rules

The controller enforces these rules in code; they're not just
convention:

1. **Implementation and publish are approval-gated.**
   Without a recorded approval (or `approve=True`), the call raises
   `ApprovalRequired`.
2. **Remote execution always requires approval.**
   `trusted_local=True` does NOT bypass this.
3. **Continuous-listening mode disables auto-implementation.**
   Even if a job has prior approvals, the controller refuses to
   auto-run while listening passively — the gateway must surface an
   approval prompt to the user.
4. **Phases run in order.**
   `PhaseError` fires if a precondition isn't satisfied (e.g., publish
   before validation).
5. **Cancellation is one-way.**
   `cancel_job` is idempotent on jobs that already reached
   `succeeded` / `published` / `cancelled`.

## Stubs and TODOs

These integrations land their interface in Phase 12 and will get
proper bodies in later phases:

- **workers** — `run_implementation_phase` enumerates registered
  worker adapters but does not actually dispatch them; it writes a
  TODO note instead.  See `hermes_cli/workers/registry.py` and
  `docs/orchestration/worker-adapter-interface.md`.
- **scoring + validation** — `run_validation_phase` checks that
  `hermes_cli.scoring` and `hermes_cli.validation` import cleanly,
  but does not yet invoke them against implementation artifacts.
- **merge engine** — `prepare_publish_phase` writes a hand-rolled
  `pr_body.md` / `manifest.json`; the richer
  `hermes_cli.merge_engine.run_merge` output is not yet plugged in.
- **model router** — `hermes_cli/model_router.py` is a static map;
  config-driven routing rules from `~/.hermes/config.yaml` are TODO.
- **workflow customization** — `hermes_cli/workflows.py` only ships
  the default linear workflow.  User-defined workflows are TODO.

Each TODO is annotated at the relevant call site; grep for `TODO` in
the controller files to find them.

## Testing

The Phase 12 controller is fully unit-tested.  Run:

```bash
python -m pytest tests/test_orchestrator_job_controller.py -q
```

Tests use the `_hermetic_environment` fixture (see
`tests/conftest.py`) which redirects `HERMES_HOME` to a per-test
tempdir, so the controller's persisted state never leaks between
tests.
