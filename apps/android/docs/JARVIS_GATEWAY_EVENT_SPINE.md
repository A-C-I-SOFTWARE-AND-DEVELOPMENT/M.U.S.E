# JARVIS Prime Gateway — Event Spine alignment (Android)

This document describes the Android-side contract for the
**Jarvis Prime gateway event spine**, the rules the app enforces around
that spine, and how to extend it without breaking the safety
invariants.

The Python core that produces these events is unchanged. The Android
app is a thin, type-checked subscriber that:

- Models every signal as a [`GatewayEvent`](../app/src/main/java/com/aci/hermes/data/gateway/GatewayEvent.kt) variant.
- Reduces them through a pure
  [`GatewayEventReducer`](../app/src/main/java/com/aci/hermes/data/gateway/GatewayEventReducer.kt)
  into a single `GatewayUiState`.
- Talks to either a
  [`MockGatewayClient`](../app/src/main/java/com/aci/hermes/data/gateway/MockGatewayClient.kt)
  (default) or a future
  [`HttpJarvisGatewayClient`](../app/src/main/java/com/aci/hermes/data/gateway/HttpJarvisGatewayClient.kt)
  selectable from Settings.

The intent is to keep mock mode fully navigable for offline demos and
to make the safety rules — approval gating, two-step serious
confirmation, impact-report-required critical actions, and emergency
stop — testable rather than aspirational.

## Non-goals

- **Do not embed Python in the APK.** The gateway is reached over the
  spine; the runtime that produces events stays where it already
  lives.
- **Do not store gateway-side secrets in the app.** No bearer tokens,
  refresh tokens, API keys, or session cookies live in any event field
  or in `EncryptedSharedPreferences`. Authentication headers (when the
  real transport lands) are set on the underlying HTTP request and
  never inside an event payload.
- **Do not bypass the runtime / permission kernel.** The app does not
  perform destructive side effects directly. Every destructive intent
  is expressed as an `approval_requested` event; the gateway is the
  one that executes.

## Event list

The spine carries 22 event types. The Kotlin sealed hierarchy in
`GatewayEvent.kt` is a one-to-one mirror; the `type` JSON
discriminator matches the names below.

| Type | Direction | Purpose |
|------|-----------|---------|
| `user_message` | app → gw | A user utterance. |
| `jarvis_response` | gw → app | A complete reply. |
| `response_delta` | gw → app | Streamed partial chunk of a reply. |
| `task_created` | gw → app | A new task is on the spine. |
| `task_updated` | gw → app | Existing task state changed. |
| `approval_requested` | app → gw | App asks the gateway for permission to execute. |
| `approval_granted` | app → gw | One confirmation (index 1..N). |
| `approval_rejected` | app → gw | User said no. |
| `serious_confirmation_required` | gw → app | Gateway needs two distinct confirmations. |
| `critical_confirmation_required` | gw → app | Gateway needs a confirmation that carries an impact report. |
| `memory_updated` | gw → app | New or refreshed durable memory entry. |
| `memory_corrected` | gw → app | Existing memory entry rewritten. |
| `memory_deleted` | gw → app | Memory entry removed. |
| `audit_record_created` | gw → app | Append-only audit log entry. |
| `icon_state_changed` | gw → app | Drives the presence icon. |
| `emergency_stop_triggered` | both | Halts all in-flight work. |
| `gateway_connected` | gw → app | Spine attached. |
| `gateway_disconnected` | gw → app | Spine dropped. |
| `worker_started` | gw → app | A worker (builder/reviewer/etc.) started. |
| `worker_progress` | gw → app | Worker reports progress. |
| `worker_completed` | gw → app | Worker finished. |
| `worker_failed` | gw → app | Worker hit a terminal error. |

Adding a new type means:

1. Add a `@SerialName("foo_event")`-annotated subclass to
   `GatewayEvent.kt`.
2. Handle it in `GatewayEventReducer.reduce` (the `when` is exhaustive
   over the sealed class — the compiler refuses to forget).
3. Add it to the spec set in `GatewayEventSerializationTest`.
4. Update this doc table.

## Safety rules

These are the four invariants that map to the explicit rules in the
mission brief. Each has tests in
`apps/android/app/src/test/java/com/aci/hermes/data/gateway/`.

### 1. App emits approval events, not destructive actions

The `GatewayClient` interface has no `deleteX`, `dropY`, or similar
side-effecting method. The destructive verbs are all expressed as
`approval_requested` events with an `action_id` the gateway
understands. The gateway is the one that decides whether and how to
execute.

The mock client refuses to short-circuit this rule: `grantApproval`
throws `IllegalStateException` if called on a serious or critical
approval — see `SeriousAndCriticalActionTest`.

### 2. Serious actions require two separate confirmation events

`MockGatewayClient.confirmSerious(approvalId, confirmationToken)` must
be called twice with two **different** tokens for the approval to
clear. Re-using the same token is rejected.

On the wire, this produces two `approval_granted` events with
`confirmation_index = 1` then `2`. The reducer counts those events and
keeps the approval pending until the required count is reached.

A future UI bug that wires up only one tap, or a buggy gateway that
counts a single-token replay as two confirmations, is caught by
`SeriousAndCriticalActionTest.serious action requires two separate
confirmation events`.

### 3. Critical actions require an impact report

`confirmCritical(approvalId, impactReport)` takes the
[`ImpactReport`](../app/src/main/java/com/aci/hermes/data/gateway/GatewayEvent.kt)
as a **required, type-checked** parameter. There is no overload that
omits it. At runtime, the report's `summary` and `rollbackPlan` must
both be non-blank — empty reports raise `IllegalArgumentException`.

The granted event records the impact report's `blastRadius` in the
`note` field so an auditor can trace the decision without
reconstructing the full report.

### 4. Emergency stop overrides pending work

`triggerEmergencyStop(reason)` emits `emergency_stop_triggered` and
then immediately emits an `icon_state_changed` to `ERROR`. The reducer
responds by:

- Wiping `pendingApprovals` (you cannot accidentally confirm something
  after the stop).
- Marking every in-flight `WorkerRuntime` as `TerminalState.FAILED`.
- Setting `iconState = ERROR` and populating
  `GatewayUiState.emergencyStop`.

The flag clears only on a fresh `gateway_connected` event — the user
or the gateway has to take a positive action to resume.

## No secrets, ever

Two complementary guards protect this rule:

1. **Static**: every event sample is serialized to JSON in
   `NoSecretsLoggedTest.no event class exposes a secret-shaped field`
   and scanned for `token`, `bearer`, `api_key`, `password`,
   `session_id`, `cookie`, `refresh_token`, `access_token`,
   `private_key`, and `client_secret`. None of those words may appear
   as a field name.
2. **Runtime**: `NoSecretsLoggedTest.GatewayController never logs raw
   event bodies` drives a full session through `GatewayController`
   with deliberately distinctive sentinel strings in user-message text
   and emergency-stop reasons, and asserts they never reach
   `LogBuffer`. The controller logs only event *type* names.

When the real HTTP transport lands, it must keep this property:
authentication headers belong on the underlying request, never on a
`GatewayEvent` field, and never in any log line.

## Connection state model

[`GatewayConnectionState`](../app/src/main/java/com/aci/hermes/data/gateway/GatewayConnectionState.kt)
is the UI's single source of truth:

| State | Meaning |
|-------|---------|
| `Idle` | Nothing has tried to connect. |
| `Connecting(mode)` | Attach attempt in flight. |
| `Connected(gatewayId, protocolVersion, mode)` | Live spine, demo or real. |
| `Disconnected(reason)` | Spine dropped. |
| `Failed(reason)` | Connect attempt failed. |

`gateway_connected` and `gateway_disconnected` events feed
`Connected`/`Disconnected` transitions through the reducer.
`HttpJarvisGatewayClient` immediately reports `Failed
("real_transport_not_implemented")` so the UI surfaces a clear banner
rather than silently doing nothing.

## Mock mode

`MockGatewayClient` is selected by default
(`SettingsRepository.gatewayMode = MOCK`). On `connect()` it replays
the fixture in
[`FakeData.kt`](../app/src/main/java/com/aci/hermes/data/gateway/FakeData.kt),
which provides:

- Two seed tasks (a planner draft, a Claude-Code builder refactor).
- Two memory entries (preference + decision).
- An audit record.
- A worker running at 75% progress.
- Three approvals — standard, serious, and critical — so the demo
  screen exercises every confirmation path.
- A `WAITING_APPROVAL` icon state.

Anything the user types goes through a fake streaming response: an
`icon_state_changed → response_delta… → jarvis_response →
icon_state_changed` sequence that mirrors the real protocol.

## Switching to the real transport

The `HttpJarvisGatewayClient` skeleton exists so the rest of the app
already depends on `GatewayClient` rather than a concrete mock. When
the real transport lands:

1. Implement `connect()` against the chosen wire (WebSocket / SSE).
   Deserialize each frame as `GatewayEvent` through `GatewayJson`.
2. For each outbound call, emit the corresponding event on `events`
   **before** the suspending call returns. The mock does this; the
   reducer assumes it.
3. Pass HTTP authentication headers on the underlying request. Do
   not invent a `token` field on any event.
4. Log only `event::class.simpleName` at INFO. Never log raw bodies
   or even the `event_id` — future field additions could carry user
   text.

The Settings screen already has the toggle wired
(`SettingsRepository.GatewayModePref.REAL`); the user can switch as
soon as a working implementation is shipped.

## Running the build and tests

From the repo root:

```bash
cd apps/android
./gradlew assembleDebug
./gradlew testDebugUnitTest
```

The unit tests run on the JVM (no emulator needed) and cover:

- event serialization round-trip + spec drift detection
- mock client demo fixture + streaming reply
- two-event serious confirmation
- impact-report-required critical confirmation
- emergency stop overriding pending work
- no-secrets static and runtime guards
- pure reducer edge cases (delta buffering, memory correction, worker
  lifecycle, mode wire field, disconnect → offline icon)
