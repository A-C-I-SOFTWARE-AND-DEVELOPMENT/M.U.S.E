# Sprint 2 — Unified Decision Engine and Owner Gates

**Program:** Hermes 10/10 Productization  
**Target vertical slice:** Voice/Android cockpit -> gateway session -> job orchestration -> worker patch -> validation gate -> GitHub PR -> phone approval.  
**Operating rule:** do not add new capability lanes unless they directly close this loop.  
**Parallel execution model:** each sprint is split into independent agent lanes. Builder agents work in separate branches/worktrees. Reviewer agents consume patches after builders finish; they do not edit in parallel with the builder whose patch they review.

## Objective

Replace scattered approval decisions with one risk-tiered decision engine that returns a single verdict: `auto`, `ask`, or `refuse`.

## Why this sprint matters

The phone cockpit cannot safely approve or reject work if Hermes cannot explain the decision in one place. Today, safety decisions are spread across command guards, approval prompts, enterprise policy, and validation gates. This sprint creates one verdict pipeline.

## Target architecture

```text
Action Request
   |
   v
DecisionInput collectors
   - shell risk scanner
   - file path policy
   - repo protected-path policy
   - secret/redaction scanner
   - remote execution policy
   - GitHub publish policy
   - Android permission policy
   - validation gate status
   |
   v
Decision Engine
   |
   +--> auto   -> execute and log
   +--> ask    -> create ApprovalRequest and notify cockpit
   +--> refuse -> block and log rationale
```

## Files likely touched

- `enterprise/decision.py` or `hermes_cli/decision_engine.py` new canonical engine.
- `enterprise/policy.py`
- `enterprise/judge.py`
- `tools/tirith_security.py`
- `tools/approval.py`
- `tools/slash_confirm.py`
- `hermes_cli/validation.py`
- `hermes_cli/orchestrator.py`
- `gateway/platforms/api_server.py`
- `tests/test_decision_engine*.py`

## Parallel agent lanes

| Lane | Agent | Branch | Mission |
|---|---|---|---|
| A | Security Agent | `sprint/2-verdict-model` | Implement `DecisionVerdict`, `DecisionInput`, tier merge rules, refusal reasons. |
| B | Backend Agent | `sprint/2-approval-store` | Implement durable approval request store with audit IDs. |
| C | Orchestrator Agent | `sprint/2-orchestrator-verdicts` | Call decision engine before worker execution, merge, publish, remote actions. |
| D | Gateway Agent | `sprint/2-approval-api` | Expose approval list/detail/decide routes for cockpit. |
| E | QA Agent | `sprint/2-decision-tests` | Add table-driven tests for auto/ask/refuse scenarios. |
| F | Reviewer Agent | `sprint/2-security-review` | Review for bypasses and downgrade paths. |

## Decision merge rules

- Any `refuse` input makes the final verdict `refuse`.
- Any `ask` input makes the final verdict `ask` unless a `refuse` exists.
- `auto` is valid only if all inputs are `auto`.
- Missing required policy input is `ask`, not `auto`.
- Unknown file path risk is `ask`.
- Protected path mutation is `ask` or `refuse` based on path.
- Secrets detected in patch/log output are `refuse` until redacted.
- Remote execution is never `auto` in early release.
- Live GitHub publish is never `auto` unless repo allowlist and action allowlist both pass.

## Owner approval envelope

```json
{
  "approval_id": "appr_...",
  "verdict_id": "dv_...",
  "job_id": "job_...",
  "action_type": "github.publish_pr",
  "summary": "Create PR from validated patch",
  "risk_tier": "ask",
  "required_phrase": "Yes, with authorization.",
  "expires_at": "...",
  "diff_preview": "redacted summary",
  "audit_id": "audit_..."
}
```

## Implementation tasks

### Security Agent

- Define canonical dataclasses/Pydantic models.
- Implement `merge_decision_inputs(inputs) -> DecisionVerdict`.
- Implement reason code enum:
  - `PROTECTED_PATH`
  - `SECRET_DETECTED`
  - `REMOTE_EXECUTION`
  - `LIVE_PUBLISH`
  - `VALIDATION_FAILED`
  - `UNKNOWN_RISK`
  - `OWNER_REQUIRED`
  - `POLICY_REFUSAL`
- Add redacted serialization.

### Backend Agent

- Add durable approval store under Hermes home.
- Store approval requests as JSONL or SQLite with append-only audit events.
- Add replay query by job/session.
- Ensure concurrent writes are locked.

### Orchestrator Agent

- Add decision checks at:
  - job creation;
  - worker execution;
  - patch merge;
  - validation failure override;
  - live GitHub publish;
  - remote bridge dispatch.

### Gateway Agent

Expose:

```text
GET  /v1/cockpit/approvals
GET  /v1/cockpit/approvals/{id}
POST /v1/cockpit/approvals/{id}/decide
GET  /v1/cockpit/decisions/{id}
```

Decision body must include `approved`, `phrase`, optional `note`, and `device_id`.

### QA Agent

Add tests for:

- protected path -> ask;
- secret in diff -> refuse;
- failed tests -> refuse unless configured as ask-for-override;
- live publish with allowlist -> ask;
- live publish without allowlist -> refuse;
- remote bridge -> ask/refuse depending on bridge trust;
- missing policy input -> ask;
- redaction in serialized verdict.

## Acceptance criteria

- One engine returns all mutation decisions.
- Cockpit can render one verdict and rationale.
- No legacy approval path can bypass the engine for target vertical-slice actions.
- Decision ledger is durable and replayable.
- Tests cover each tier and reason code.

## Reviewer prompt

```text
Review the unified decision engine. Attempt to find bypasses where a worker, publisher, gateway route, shell command, or remote bridge dispatch can mutate state without a DecisionVerdict. Flag any downgrade from refuse to ask or ask to auto. Do not weaken tests.
```

## Definition of done

Every high-risk mutation in the 10/10 loop passes through a single, auditable decision verdict.
