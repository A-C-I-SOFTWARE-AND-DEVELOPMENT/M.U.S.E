# Sprint 1 — Canonical System Architecture and Contracts

**Program:** Hermes 10/10 Productization  
**Target vertical slice:** Voice/Android cockpit -> gateway session -> job orchestration -> worker patch -> validation gate -> GitHub PR -> phone approval.  
**Operating rule:** do not add new capability lanes unless they directly close this loop.  
**Parallel execution model:** each sprint is split into independent agent lanes. Builder agents work in separate branches/worktrees. Reviewer agents consume patches after builders finish; they do not edit in parallel with the builder whose patch they review.

## Objective

Create the formal architecture that every later sprint implements. This sprint prevents the product from becoming a pile of separate features.

## 10/10 target architecture

```text
Android Cockpit / Voice Surface
        |
        | HTTPS + SSE/WebSocket + signed approval envelopes
        v
Gateway API + Pairing + Cockpit Sessions
        |
        | durable events + auth context
        v
Hermes Conversation Session
        |
        | work packet + risk request
        v
Decision Engine -----> Audit Ledger
        |
        | auto / ask / refuse
        v
Orchestrator Job Controller
        |
        | worktree leases + worker prompts
        v
Worker Actuators: Claude Code / Codex / Aider / Goose / Hermes Local
        |
        | git diff + artifacts + logs
        v
Merge Engine + Validation Gates
        |
        | validated patch + verdict
        v
GitHub Publisher
        |
        | draft/live PR behind allowlist
        v
Phone Approval / Push / Replayable History
```

## Contracts to produce

1. `docs/architecture/10_10_system_architecture.md`
2. `docs/api/cockpit_v1_openapi.md`
3. `docs/api/event_stream_contract.md`
4. `docs/orchestration/work_packet_schema.md`
5. `docs/orchestration/artifact_contract.md`
6. `docs/security/decision_verdict_contract.md`
7. `docs/android/cockpit_state_model.md`
8. `docs/adr/ADR-10-10-product-loop.md`

## Canonical data models

### CockpitSession

```python
CockpitSession:
  session_id: str
  device_id: str
  user_id: str
  created_at: datetime
  last_seen_event_id: str | None
  auth_scope: list[str]
  trusted_until: datetime | None
  revoked_at: datetime | None
```

### WorkPacket

```python
WorkPacket:
  id: str
  user_goal: str
  repo_root: str
  branch: str
  risk_class: str
  allowed_files: list[str]
  forbidden_files: list[str]
  acceptance_criteria: list[str]
  verification_commands: list[str]
  rollback_plan: str
  requested_workers: list[str]
  owner_gate_required: bool
  source_session_id: str
```

### DecisionVerdict

```python
DecisionVerdict:
  id: str
  tier: Literal["auto", "ask", "refuse"]
  action_type: str
  rationale: str
  inputs: list[DecisionInput]
  required_owner_phrase: str | None
  allowed_until: datetime | None
  audit_id: str
```

### JobEvent

```python
JobEvent:
  event_id: str
  job_id: str
  session_id: str
  type: str
  created_at: datetime
  cursor: str
  payload_redacted: dict
```

### WorkerArtifact

```python
WorkerArtifact:
  worker_id: str
  worktree_path: str
  branch: str
  patch_path: str
  diffstat: dict
  logs_path: str
  tests_path: str
  notes_path: str
  risk_report_path: str
```

## Parallel agent lanes

| Lane | Agent | Branch | Mission | Output |
|---|---|---|---|---|
| A | Architecture Agent | `sprint/1-contracts` | Write canonical architecture and ADR. | Architecture docs |
| B | Backend Agent | `sprint/1-openapi` | Draft Cockpit API contract. | OpenAPI-like docs and route matrix |
| C | Android Agent | `sprint/1-android-state` | Define Android state machines. | Cockpit state model |
| D | Orchestrator Agent | `sprint/1-work-packet` | Define work packet and artifact schemas. | Schema docs + fixtures |
| E | Security Agent | `sprint/1-decision-contract` | Define DecisionVerdict and audit contract. | Decision contract |
| F | QA Agent | `sprint/1-contract-tests` | Create schema fixture tests. | Contract tests |
| G | Reviewer Agent | `sprint/1-review` | Ensure contracts are coherent. | Review report |

## Required implementation

Minimal code may be added only for schemas and fixtures. This sprint should not yet implement product behavior. It should create stable contracts.

Create fixtures:

```text
tests/fixtures/cockpit/session_created.json
tests/fixtures/cockpit/job_events.jsonl
tests/fixtures/orchestration/work_packet.json
tests/fixtures/orchestration/worker_artifact.json
tests/fixtures/security/decision_verdict_ask.json
```

## Acceptance criteria

- Every later sprint can cite a contract from this sprint.
- Android and gateway agree on route names, auth headers, and event shapes.
- Orchestrator and workers agree on artifact paths and diff format.
- Decision engine has one canonical verdict type.
- All contract fixtures validate in tests.

## Reviewer prompt

```text
Review the 10/10 architecture contracts. Look for hidden coupling, missing state transitions, ambiguous auth, replay problems, and unsafe remote-execution assumptions. Return a patch plan, not implementation code.
```

## Definition of done

The repo has a stable contract layer that prevents backend, Android, worker, and security agents from inventing incompatible local designs.
