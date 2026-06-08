# M.U.S.E. mobile ↔ backend contract

This document is the **mobile-facing summary** of the wire format the
Android cockpit speaks. It points at the existing, authoritative
contract documents in [`docs/android/`](../android/) rather than
duplicating their bodies — duplication is exactly how the two specs
drift.

> **Authoritative sources:**
> - Cockpit API contract:
>   [`docs/android/hermes-apk-api-contract.md`](../android/hermes-apk-api-contract.md)
> - Termux intent bridge:
>   [`docs/android/termux-intent-bridge.md`](../android/termux-intent-bridge.md)
> - Existing chat / health wire:
>   [`apps/android/docs/ARCHITECTURE.md`](../../apps/android/docs/ARCHITECTURE.md)
>   §Wire format

This document explains **what changes** for the Phase 02 mobile client
and **which gateway endpoints** it depends on.

---

## 1. Transport at a glance

| Direction | Mechanism | Used for |
|---|---|---|
| Mobile → Gateway | HTTPS JSON | Health, jobs CRUD, dispatch, approvals, publish, settings reads. |
| Mobile → Gateway | HTTPS multipart / WebSocket frames (future) | Voice capture upload (chunked). |
| Gateway → Mobile | Server-Sent Events (SSE) | Job stream, event stream, chat token stream, TTS frames. |
| Mobile → Termux (on-device) | Android Intent | `com.termux.RUN_COMMAND` to start/stop the local gateway. |
| Mobile → Termux (on-device) | Android Intent | `ACTION_VIEW` into Termux:Files for the *Open job folder* affordance. |

Cleartext HTTP is permitted on debug builds for LAN/emulator testing.
Release builds use HTTPS only — see
[`hermes-mobile-architecture.md`](hermes-mobile-architecture.md) §12.

---

## 2. Authentication

- Gateway bearer token: `Authorization: Bearer <token>` on every cockpit
  route except `GET /v1/health`. Stored in
  EncryptedSharedPreferences on the device.
- Provider API keys (OpenAI / Anthropic / OpenRouter / …) live on the
  gateway, never on the phone. No cockpit route — including the live
  `POST /v1/jarvis/chat` — accepts a provider-key header; clients send
  only `Authorization: Bearer <token>`. (A retired pre-cockpit chat
  design once forwarded an `X-Hermes-Provider-Key`; it is gone.)
- 401 from any cockpit route routes the user to **Settings →
  Connection** with the explanation *"Gateway token rejected"*. The
  cockpit does not auto-retry on 401.

---

## 3. Endpoints by feature

The cockpit specification calls these out individually. This table is
the *mobile dependency view*: it tells you what mobile feature stops
working if the corresponding endpoint is absent.

### 3.1 Health (already live)

| Method | Path | Mobile dependency |
|---|---|---|
| GET | `/v1/health` | Status screen, Diagnostics screen, connection probes. **Required.** |

Treated by the cockpit as "is the gateway up at all?". The schema is in
the architecture doc; `ok=false` renders as *Backend reachable but
reporting unhealthy*.

### 3.2 Runtime introspection (Phase 18, spec only)

| Method | Path | Mobile dependency |
|---|---|---|
| GET | `/v1/cockpit/runtime/status` | Termux Control Panel: backend mode + queue snapshot. |
| GET | `/v1/cockpit/runtime/workers` | Settings → Worker detection. |
| GET | `/v1/cockpit/templates` | Prompt Command Center: prompt templates (optional; 404 → bundled defaults). |

### 3.3 Jobs (Phase 18, spec only)

| Method | Path | Mobile dependency |
|---|---|---|
| GET | `/v1/cockpit/jobs` | Worker Dashboard listing (paginated). |
| GET | `/v1/cockpit/jobs/stream` | Worker Dashboard live updates (SSE). |
| GET | `/v1/cockpit/jobs/{id}` | Worker Dashboard row detail / refresh. |
| POST | `/v1/cockpit/jobs` | Prompt Command Center dispatch. |
| POST | `/v1/cockpit/jobs/{id}/cancel` | Worker Dashboard swipe-cancel. |

### 3.4 Files and diff (Phase 18, spec only)

| Method | Path | Mobile dependency |
|---|---|---|
| GET | `/v1/cockpit/jobs/{id}/tree` | Job Folder Browser drill-down. |
| GET | `/v1/cockpit/jobs/{id}/file` | Job Folder Browser file preview. |
| GET | `/v1/cockpit/jobs/{id}/diff` | Diff and Merge Review body. |
| GET | `/v1/cockpit/jobs/{id}/files-changed` | Diff and Merge Review file strip. |
| POST | `/v1/cockpit/jobs/{id}/approve` | Diff and Merge Review approve / reject. |

### 3.5 Validation (Phase 18, spec only)

| Method | Path | Mobile dependency |
|---|---|---|
| GET | `/v1/cockpit/jobs/{id}/validation` | Validation Gate screen. |
| POST | `/v1/cockpit/jobs/{id}/revalidate` | Validation Gate *Re-run gates* action. |
| POST | `/v1/cockpit/jobs/{id}/override` | Validation Gate *Override and continue* (when policy permits). |

### 3.6 Publish (Phase 18, spec only)

| Method | Path | Mobile dependency |
|---|---|---|
| GET | `/v1/cockpit/jobs/{id}/publish/preview` | GitHub Publisher pre-fill. |
| POST | `/v1/cockpit/jobs/{id}/publish` | GitHub Publisher *Publish* action. |

### 3.7 Events (Phase 18, spec only)

| Method | Path | Mobile dependency |
|---|---|---|
| GET | `/v1/cockpit/events` | Logs and Events backfill page. |
| GET | `/v1/cockpit/events/stream` | Logs and Events live tail (SSE). |

### 3.8 Pending approvals (Phase 18, spec only)

| Method | Path | Mobile dependency |
|---|---|---|
| GET | `/v1/cockpit/approvals` | Termux Control Panel *Approve destructive command* shortcut. |
| POST | `/v1/cockpit/approvals/{id}/decide` | Same screen's decide action. |

### 3.9 Voice (planned, mobile-side optional)

The voice surface is not yet wired into the cockpit contract. When it
lands, the mobile expectation is:

| Method | Path | Mobile dependency |
|---|---|---|
| POST (multipart) | `/v1/cockpit/voice/transcribe` | Voice prompt capture (chunked PCM upload + streamed transcript SSE). |
| GET (SSE) | `/v1/cockpit/voice/tts` | TTS playback of assistant responses (base64 PCM frames). |

These routes are reserved here; the gateway-side voice feature will
finalise them. The mobile client must degrade gracefully — voice
affordances stay hidden when the gateway doesn't advertise the routes.

---

## 4. SSE conventions

All cockpit SSE streams follow the same envelope:

```
event: <event-name>
data: <json-payload>
```

- Heartbeats: `event: heartbeat`, `data: { "ts": "<iso>" }`, emitted by
  the gateway every 15s on each stream.
- Reconnection: the cockpit reconnects with exponential backoff
  (2s → 30s, capped) after >45s without a heartbeat.
- Resume: streams **do not** support `Last-Event-Id` resume in Phase 18.
  The cockpit re-reads the corresponding REST endpoint on reconnect to
  catch up.

---

## 5. Idempotency

`POST` routes that mutate accept an optional `Idempotency-Key` header.
The gateway stores the resulting status for at least 24h keyed on
`(token, key)`. The cockpit:

- generates a UUIDv4 for every dispatch / approve / publish /
  override / cancel request,
- replays the **same key** on retry (whether the retry is automatic or
  user-driven via the offline-queue banner),
- treats a 2xx response with a previously-seen key as success — it does
  not change UI state again.

---

## 6. Error envelope

Every non-2xx response uses the envelope:

```json
{
  "error": {
    "code": "validation_failed",
    "message": "Human-readable summary",
    "details": { "field_name": "what's wrong with it" }
  }
}
```

HTTP status mirrors the class:

| Status | Class | Cockpit behaviour |
|---|---|---|
| 400 | Validation | Inline field error if `details` carries a field name; otherwise top snackbar. |
| 401 | Auth | Route to Settings → Connection; do not auto-retry. |
| 403 | Policy | Block the action; render the gateway's `message` verbatim. |
| 404 | Missing | Empty-state card; offer *Refresh*. |
| 409 | State mismatch | Refresh the screen's data, then resurface the action only if still applicable. |
| 5xx | Backend bug | Snackbar with *Retry* and *Copy to clipboard*. Never silent retry. |

The cockpit branches on `error.code`, not on the human-readable
`error.message`. Future codes are reserved for the gateway; an
unrecognised code falls through to *"Backend returned an error
(`<code>`)"* and surfaces the `message` underneath.

---

## 7. Mode-specific transport notes

The cockpit supports three connection modes (see
[`apps/android/README.md`](../../apps/android/README.md) §Runtime modes
and [`docs/android/hermes-apk-cockpit.md`](../android/hermes-apk-cockpit.md)
§"Two operating modes"). The wire is the **same** across modes; only
the URL changes:

| Mode | URL | Notes |
|---|---|---|
| Remote gateway | `https://<host>` | Production deployment, HTTPS required. |
| On-device Termux gateway | `http://127.0.0.1:8080` | Loopback only. Cleartext is fine because nothing leaves the device. |
| Mock (UI sandbox) | n/a | No network calls. Canned responses inside the APK. |

There is a deliberate **fallback** mode — *Local handoff* — that does
**not** speak this contract. It runs entirely on-device, copies
prompts to the clipboard, and launches Codex / Claude / ChatGPT
intents. See
[`docs/hermes-local-orchestrator.md`](../hermes-local-orchestrator.md).

---

## 8. Why the cockpit contract, not the legacy chat contract

The Android app historically spoke a legacy `POST /v1/chat` + SSE wire;
it now speaks the cockpit contract plus the live `POST /v1/jarvis/chat`
NDJSON stream (`apps/android/docs/ARCHITECTURE.md`). Phase 18 replaced
that with the cockpit contract for **everything except** plain chat —
the cockpit's job is to drive orchestrated jobs end-to-end, not to be a
chat shell.

Migration order on the mobile side:

1. Land the cockpit screens against the spec, behind a feature flag.
   They render correctly in mock mode without a live backend.
2. Land the gateway-side `/v1/cockpit/*` routes (separate workstream).
3. Flip the flag once `runtime_status.gateway.version` advertises
   cockpit support.
4. Keep the chat surface and the *Local handoff* mode untouched as the
   fallback experience for users on older gateways.

This sequencing means the mobile and gateway teams don't have to land
the same commit on the same day.

---

## 9. What the cockpit must not do over the wire

- **No telemetry from the APK.** Backend events the user views in
  *Logs and Events* are read on demand. Nothing is phoned home.
- **No silent retries on mutating routes.** Every retry is either the
  user's tap or the offline-queue banner the user can see.
- **No background streams when the user isn't watching a job.** The
  foreground service tears down SSE the moment its only consumer
  disappears.
- **No provider API keys in any request body.** Provider credentials
  are gateway-side.
- **No automatic Termux intents.** The user must tap to fire any
  RUN_COMMAND. The cockpit never fires an intent in response to a
  network response or a push.

---

## 10. Cross-references

- [`docs/android/hermes-apk-api-contract.md`](../android/hermes-apk-api-contract.md)
  — the authoritative wire format for cockpit routes.
- [`docs/android/hermes-apk-cockpit.md`](../android/hermes-apk-cockpit.md)
  — which mobile screen uses which route.
- [`docs/android/termux-intent-bridge.md`](../android/termux-intent-bridge.md)
  — the on-device intent path.
- [`apps/android/docs/ARCHITECTURE.md`](../../apps/android/docs/ARCHITECTURE.md)
  — the existing chat / health wire and Kotlin client structure.
- [`docs/hermes-local-orchestrator.md`](../hermes-local-orchestrator.md)
  — the *Local handoff* fallback.
- [`apps/android/app/src/main/java/com/aci/hermes/data/cockpit/CockpitApi.kt`](../../apps/android/app/src/main/java/com/aci/hermes/data/cockpit/CockpitApi.kt)
  — Kotlin mirror of the cockpit shapes.
