# Sprint 6 — Gateway Cockpit API and Durable Sessions

**Program:** Hermes 10/10 Productization  
**Target vertical slice:** Voice/Android cockpit -> gateway session -> job orchestration -> worker patch -> validation gate -> GitHub PR -> phone approval.  
**Operating rule:** do not add new capability lanes unless they directly close this loop.  
**Parallel execution model:** each sprint is split into independent agent lanes. Builder agents work in separate branches/worktrees. Reviewer agents consume patches after builders finish; they do not edit in parallel with the builder whose patch they review.

## Objective

Make the gateway a real backend for the Android cockpit: durable sessions, job APIs, event streaming, approval inbox, and replay after reconnect.

## Target API surface

```text
GET  /v1/health
POST /v1/cockpit/pair/start
POST /v1/cockpit/pair/confirm
GET  /v1/cockpit/session
POST /v1/cockpit/chat
GET  /v1/cockpit/jobs
POST /v1/cockpit/jobs
GET  /v1/cockpit/jobs/{id}
GET  /v1/cockpit/jobs/{id}/events?since=<cursor>
GET  /v1/cockpit/approvals
GET  /v1/cockpit/approvals/{id}
POST /v1/cockpit/approvals/{id}/decide
GET  /v1/cockpit/events?since=<cursor>
GET  /v1/cockpit/diagnostics
```

## Files likely touched

- `gateway/platforms/api_server.py`
- `gateway/session.py`
- `gateway/pairing.py`
- `gateway/run.py`
- `hermes_cli/orchestrator_api.py`
- `hermes_cli/job_controller.py`
- `hermes_state.py`
- `tests/gateway/*`
- `docs/api/cockpit_v1_openapi.md`

## Parallel agent lanes

| Lane | Agent | Branch | Mission |
|---|---|---|---|
| A | Gateway Agent | `sprint/6-routes` | Implement route handlers and route registration. |
| B | Session Agent | `sprint/6-cockpit-sessions` | Implement durable CockpitSession and cursor storage. |
| C | Event Agent | `sprint/6-sse-events` | Implement SSE/WebSocket or long-poll replayable event stream. |
| D | Approval Agent | `sprint/6-approval-api` | Wire approvals to decision engine store. |
| E | QA Agent | `sprint/6-gateway-tests` | Add route tests, auth tests, replay tests. |
| F | Security Agent | `sprint/6-api-security` | Pairing, token handling, revocation, redaction. |
| G | Reviewer Agent | `sprint/6-review` | Review API auth and replay consistency. |

## Session model

- Device receives a durable device ID.
- Pairing produces a scoped bearer token.
- Token is stored only on device secure storage.
- Gateway stores token hash, not raw token.
- Session has replay cursor.
- Reconnect returns missed events since cursor.
- Revocation invalidates device token immediately.

## Event-stream design

Event stream may be SSE first; WebSocket can follow.

Every event includes:

```json
{
  "event_id": "evt_...",
  "cursor": "...",
  "type": "job.validation.completed",
  "job_id": "job_...",
  "created_at": "...",
  "payload": {}
}
```

Payload must be redacted and bounded.

## Security requirements

- Localhost binding by default unless explicitly configured.
- Pairing endpoint has short-lived code.
- Rate-limit pairing attempts.
- No secret values in diagnostics.
- No raw worker logs without redaction.
- No raw chain-of-thought storage or return.
- Approval decisions require device auth plus exact phrase for gated actions.

## Acceptance criteria

- Android can create/rejoin a cockpit session.
- Jobs list and job detail return stable snapshots.
- Events replay from cursor after simulated reconnect.
- Approval list/detail/decide works against the decision store.
- Revoked device cannot call APIs.
- Gateway tests pass without real messaging providers.

## Reviewer prompt

```text
Review gateway cockpit API. Attempt auth bypass, event replay inconsistency, approval spoofing, token leakage, and unredacted diagnostics. Verify reconnect behavior is deterministic and device revocation works.
```

## Definition of done

The Android cockpit has a stable backend contract for sessions, jobs, approvals, and live event updates.
