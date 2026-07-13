# Sprint 13 — Multi-Host Orchestration and Failure Isolation

**Program:** Hermes 10/10 Productization  
**Target vertical slice:** Voice/Android cockpit -> gateway session -> job orchestration -> worker patch -> validation gate -> GitHub PR -> phone approval.  
**Operating rule:** do not add new capability lanes unless they directly close this loop.  
**Parallel execution model:** each sprint is split into independent agent lanes. Builder agents work in separate branches/worktrees. Reviewer agents consume patches after builders finish; they do not edit in parallel with the builder whose patch they review.

## Objective

Scale Hermes orchestration beyond local threadpool execution while preserving job replay, lease ownership, artifact integrity, and safe failure behavior.

## Target architecture

```text
Orchestrator Controller
  -> Worker Lease Store
  -> Host Registry
  -> Artifact Store
  -> Worker Runtime Adapters
     - local
     - docker
     - ssh
     - modal/daytona/vercel sandbox where available
     - windows bridge
  -> Event Stream
```

## Files likely touched

- `hermes_cli/orchestrator_parallel.py`
- `hermes_cli/orchestrator.py`
- `tools/environments/*`
- `hermes_cli/job_controller.py`
- `hermes_cli/kanban_db.py`
- `gateway/platforms/api_server.py`
- tests for lease/retry/artifact sync

## Parallel agent lanes

| Lane | Agent | Branch | Mission |
|---|---|---|---|
| A | Runtime Agent | `sprint/13-runtime-abstraction` | Define worker runtime interface and host registry. |
| B | Lease Agent | `sprint/13-worker-leases` | Implement durable leases, heartbeats, retry semantics. |
| C | Artifact Agent | `sprint/13-artifact-store` | Implement artifact addressing, checksums, redacted export. |
| D | Gateway Agent | `sprint/13-scale-events` | Expose multi-host worker status to cockpit. |
| E | QA Agent | `sprint/13-scale-tests` | Simulate worker crash, lease expiry, duplicate completion, artifact loss. |
| F | Security Agent | `sprint/13-host-security` | Review host trust, credential scoping, remote artifact handling. |
| G | Reviewer Agent | `sprint/13-review` | Review failure isolation and replay correctness. |

## Lease model

```python
WorkerLease:
  lease_id: str
  job_id: str
  worker_id: str
  host_id: str
  acquired_at: datetime
  heartbeat_at: datetime
  expires_at: datetime
  status: pending|running|completed|expired|cancelled
```

## Failure rules

- Lost heartbeat expires lease.
- Expired lease can be retried if idempotent.
- Duplicate completion after expiry is rejected or marked late.
- Artifact checksum mismatch refuses artifact.
- Host failure does not corrupt job state.
- Cancellation emits event and terminates known child processes where possible.

## Acceptance criteria

- Two workers can run on separate runtime adapters in test/mocked mode.
- Lease expiry is deterministic.
- Late completion does not overwrite winning result.
- Artifact checksums are verified.
- Cockpit shows host/worker status.
- Failure can be replayed from events.

## Reviewer prompt

```text
Review multi-host orchestration. Check lease races, duplicate completion, artifact tampering, host trust assumptions, secret propagation, and whether failed hosts can corrupt job state or publish stale patches.
```

## Definition of done

Hermes can distribute jobs across multiple worker runtimes with durable leases and safe failure isolation.
