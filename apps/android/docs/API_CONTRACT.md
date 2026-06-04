# Android ↔ Cockpit API Contract (v1.5)

The canonical, full wire contract lives at
[`docs/android/hermes-apk-api-contract.md`](../../../docs/android/hermes-apk-api-contract.md);
the Kotlin mirror is `data/cockpit/CockpitApi.kt`. This file documents the
**coding-cockpit** surface v1.5 adds/consumes and the conventions the app
relies on.

## Conventions

- Base URL is owner-configured (default loopback `http://127.0.0.1:8765`).
- All routes except `GET /v1/health` require `Authorization: Bearer <token>`.
- Decoding is **tolerant**: unknown keys are ignored, absent nullable fields
  stay null — an evolving gateway never crashes the app.
- Every call resolves to a typed `CockpitResult`: `Success`, `Failure(code,
  status)`, or `Unreachable` (no endpoint/token, or transport failure). The UI
  branches on intent, never on a raw HTTP status.
- Owner-gated writes require the exact phrase `Yes, with authorization.`,
  verified **server-side**. The app never stores or fabricates it.

## Coding lanes (consumed by the v1.5 coding cockpit)

### `POST /v1/cockpit/coding/audit` — classify + route (read-only)
Request `CodingRequest { prompt, repo_root?, worker_id?, authorization? }`.
Response `CodingAuditResult { intent, risk_class, primary_worker,
reviewer_worker, model_lane_hint, owner_gates[], blocked, rationale, mission,
owner_gate_required }`. Builds nothing, runs nothing.

### `POST /v1/cockpit/coding/plan` — build + validate a work packet (stage only)
Response `CodingPlanResult { packet: CodingPacket, validation: { ok,
findings[] }, markdown, owner_gate_required }`. `CodingPacket` carries
`mission, intent, branch, risk_class, repo_root, allowed_files[],
forbidden_files[], acceptance_criteria[], verification_plan[], rollback_plan[],
owner_gates[], primary_worker, model_lane_hint, blocked`.

### `POST /v1/cockpit/coding/execute` — gated dispatch
Response `CodingExecuteResult { status, job?, packet, worker_id, risk_class?,
authorization_required, authorization_hint?, error? }`. Without the owner
phrase, `status = "approval_required"` and the job is staged (the app shows the
owner gate). With a valid phrase and a runnable lane, `status = "dispatched"`.

## App behaviour when a capability is missing

If a route is absent or the gateway returns an honest empty/`error` payload,
the corresponding screen shows **"not supported by this backend"** or
**"pair a gateway"** — never a fabricated value. An unreachable gateway leaves
coding tasks **queued offline** (the prompt is still copyable).

## Planned (v1.5 WS2): local model status

`GET /v1/cockpit/models/local` (and an explicit `POST .../smoke`) will report
detected runtimes, installed Gemma/Ollama variants, and per-task promotion with
the honest status vocabulary in [`GEMMA_LOCAL_MODE.md`](GEMMA_LOCAL_MODE.md).
Until that lands, the app surfaces routing via `GET /v1/cockpit/model-routes`
and `GET /v1/cockpit/models` (Model Route screen) and labels Gemma status as
"not yet probed".
