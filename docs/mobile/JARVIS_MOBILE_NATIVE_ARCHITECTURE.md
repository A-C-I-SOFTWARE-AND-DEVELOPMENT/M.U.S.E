# MUSE — Mobile-Native Architecture (as-built)

> **Status:** authoritative, as-built. This document describes what the
> code in `apps/android/` and `gateway/` **actually does today**, with
> exact file and route citations. Where an older doc described an
> intended design that was never implemented (notably SSE streaming),
> that claim is flagged here as **superseded**.
>
> **Scope:** the native Android cockpit (`apps/android/`) and the M.U.S.E.
> backend surfaces it speaks to. The Python runtime — agent loop, skills,
> memory, tools, scheduling, orchestration ledger — is **unchanged** and
> remains the canonical backend. The phone is the **primary control
> surface**, not a re-implementation of the agent.
>
> **This document is descriptive, not aspirational.** It does not change
> runtime code. Gaps are listed in §8 as bounded follow-up tasks.

---

## 1. Purpose and principles

MUSE's mobile-native goal: **Android is the primary cockpit;
M.U.S.E. remains the canonical backend; no backend power is removed.**

Non-negotiable principles this architecture upholds:

1. **Mobile-first is not mobile-only.** The native cockpit exposes the
   backend's power, but the CLI (`muse`), the gateway, the worker
   engine, the orchestration stack, and the backend APIs all continue to
   work independently of the phone.
2. **The backend is the source of truth.** The app holds UI state and a
   single secret (the paired bearer token). Jobs, memory, the audit
   ledger, approvals, and verification gates live on the backend.
3. **Owner gates, emergency stop, audit ledger, rollback, approvals, and
   verification gates are preserved.** The app surfaces them; it never
   bypasses them. Approving an owner-gated action still requires the
   server-enforced authorization phrase (§7).
4. **Honest state.** An unreachable or unpaired gateway yields a typed
   `Unreachable`/`Mock` state — the app never fabricates a backend value.
   See `HermesCockpitClient` (`apps/android/app/src/main/java/com/aci/hermes/data/cockpit/HermesCockpitClient.kt`).

---

## 2. As-built layer model

Each layer talks only to the one below it. The transport layer is the
**only** place that touches the gateway or the Termux sandbox.

```
   USER, on phone   │  Compose UI (screens, theming)                 ui/screens/**, ui/theme/**
   ─────────────────┼───────────────────────────────────────────────
   ViewModel layer  │  StateFlow<UiState> per screen                 ui/screens/<name>/<Name>ViewModel.kt
   ─────────────────┼───────────────────────────────────────────────
   Domain layer     │  Repositories                                  data/cockpit/, data/memory/,
                    │  (Cockpit jobs, Memory, Audit, Approvals,        data/audit/, approval/state/,
                    │   Capability, Settings, Tasks)                   data/capability/, data/preferences/,
                    │                                                  data/orchestrator/
   ─────────────────┼───────────────────────────────────────────────
   Transport layer  │  HermesCockpitClient (JDK HTTP)  ·             data/cockpit/HermesCockpitClient.kt
                    │  HttpJarvisChatGateway (JSONL)   ·             data/jarvis/HttpJarvisChatGateway.kt
                    │  TermuxIntentBridge (RUN_COMMAND)             data/termux/TermuxIntentBridge.kt
   ─────────────────┼───────────────────────────────────────────────
   Persistence      │  DataStore + EncryptedSharedPreferences        data/preferences/SettingsRepository.kt
   ─────────────────┼───────────────────────────────────────────────
   OS               │  Foreground service · Keystore · Mic · TTS    service/**, voice/**
                    └───────────────────────────────────────────────
                                       │
                                       ▼
                    ┌─────────────────────────────────────────────┐
                    │  M.U.S.E. backend (Python, off-phone or Termux) │
                    │   • Cockpit REST   gateway/cockpit/server.py  │
                    │   • Chat (JSONL)   gateway/jarvis_local_http.py│
                    └─────────────────────────────────────────────┘
```

- **DI:** hand-rolled `AppContainer`
  (`apps/android/app/src/main/java/com/aci/hermes/di/AppContainer.kt`).
  No Hilt/Dagger/Koin. ViewModel factories pull dependencies from the
  container; the cockpit endpoint and token are mirrored into volatile
  caches kept current by a long-lived collector, so config changes
  (pairing, endpoint edits) propagate without rebuilding the client.
- **Correction to the prior doc:** `muse-mobile-architecture.md` §2
  describes a `data/network/` package and `CockpitSseClient.kt`. **The
  live transport actually lives in `data/cockpit/`** and there is **no
  SSE client**. This document supersedes that section.

---

## 3. Backend topology (two servers)

The cockpit speaks to **two** loopback HTTP servers. Both default to
`http://127.0.0.1:8765`
(`SettingsRepository.DEFAULT_GATEWAY_ENDPOINT`,
`apps/android/app/src/main/java/com/aci/hermes/data/preferences/SettingsRepository.kt:318`).

| Server | File | Auth | What it serves |
|---|---|---|---|
| **Cockpit REST** | `gateway/cockpit/server.py` (`muse cockpit serve`) | Bearer token (`gateway/cockpit/auth.py`); all `/v1/cockpit/*` routes require it; `/v1/health` does not | ~28 routes: runtime status/workers, diagnostics, models, memory, events, audit + proof, jobs, approvals, proposals, skills, navigation, sessions, avatar persona/room. Routing table: `gateway/cockpit/server.py:46-73`; handlers: `gateway/cockpit/handlers.py`; wire contract: `gateway/cockpit/contract.py` |
| **Chat (JSONL)** | `gateway/jarvis_local_http.py` | loopback host check; bearer optional | One route `POST /v1/jarvis/chat` (`CHAT_PATH`, `gateway/jarvis_local_http.py:32`) streaming newline-delimited JSON chunks (`thinking`/`working`/`tone`/`body`/`detail`/`done`/`error`) |

**Pairing:** the app stores the bearer token in EncryptedSharedPreferences
and the endpoint in DataStore. `HermesCockpitClient.isPaired()` is
`token != null && endpoint != blank`. Until paired, repositories fall
back to mock/empty seeds (so previews, first-run, and tests work with no
daemon) and chat routes to `MockJarvisChatGateway`.

---

## 4. Transport — current, gap, future, migration

### 4.1 Current implemented transport

**Request/response over the JDK `HttpURLConnection`. No streaming push.**

- **Cockpit REST:** `HermesCockpitClient`
  (`data/cockpit/HermesCockpitClient.kt`) issues buffered
  GET/POST/DELETE calls through `CockpitHttp`/`CockpitHttpExecutor`
  (`data/cockpit/CockpitHttp.kt`). Every cockpit handler returns a
  **buffered `JsonResponse`** (`gateway/cockpit/handlers.py`) — there is
  no chunked/event response on any cockpit route.
- **Events are GET-poll, not push.** `GET /v1/cockpit/events`
  (`gateway/cockpit/server.py:54` → `handlers.py:238 audit_events`)
  returns a buffered JSON page. A client that wants fresh events must
  re-request. There is no `/events/stream`.
- **Chat is a JSONL HTTP stream.** `HttpJarvisChatGateway`
  (`data/jarvis/HttpJarvisChatGateway.kt`) POSTs to `/v1/jarvis/chat`
  and reads the response body line-by-line, emitting one
  `JarvisChatChunk` per JSON line. This is a streamed *response body*
  over plain HTTP — **not** SSE and **not** a WebSocket. Cancellation is
  honored between lines via `ensureActive`.

### 4.2 Known gap

- **No server-push for jobs, events, or approvals.** A screen that needs
  live updates must poll the relevant GET route on an interval. The
  foreground service (`service/HermesService.kt`) currently holds only a
  persistent notification; it does not own any live subscription.
- **The prior doc's SSE design is unimplemented.**
  `muse-mobile-architecture.md` §4 references
  `/v1/cockpit/jobs/stream`, `/v1/cockpit/events/stream`, and an SSE
  chat response, plus a `CockpitSseClient.kt`. **None of these exist in
  `gateway/cockpit/server.py` or `apps/android/`.** Treat that section as
  a design sketch, superseded by this document.

### 4.3 Future target transport (NOT canonical, NOT implemented)

Mobile-native streaming may later be added so the cockpit reflects
job/event/approval changes without polling. Candidate mechanisms — SSE,
WebSocket, or long-poll over the existing JSONL convention — are **not**
part of the current implemented architecture and must not be described
as if they were. Any such work is tracked as **MOBILE-STREAMING-001**
(§8).

### 4.4 Migration path

When streaming lands, it should slot in **behind the existing repository
interfaces** so screens do not change:

1. Add a server route (e.g. `GET /v1/cockpit/events/stream`) alongside
   the existing poll route — never replacing it.
2. Add a transport method on `HermesCockpitClient` returning a
   `Flow<…>`, with the buffered poll call kept as the fallback when the
   stream is unavailable or the device is backgrounded.
3. Let repositories (`CockpitJobsRepository`, `AuditRepository`, the
   approvals repo) prefer the stream and degrade to poll. ViewModels keep
   collecting the same repository `Flow`.
4. Update this document's §4.1/§4.2 **only after** the implementation
   ships with tests.

---

## 5. Navigation map (as-built)

Source of truth: `ui/navigation/Screen.kt` and `ui/navigation/HermesNavGraph.kt`.
Start destination is `Splash`; after onboarding the app lands on
`JarvisLive` (the avatar "Den"). Shell destinations render inside
`JarvisShell` with shared bottom nav + a global emergency-stop bar.

| Route | Kind | Screen file | ViewModel | Backing data / transport |
|---|---|---|---|---|
| `splash` | pre-shell | `ui/screens/splash/SplashScreen.kt` | — | — |
| `onboarding` | pre-shell | `ui/screens/onboarding/OnboardingScreen.kt` | — | `SettingsRepository` (local) |
| `home` | shell | `ui/screens/home/HomeScreen.kt` | `OrchestratorViewModel` | `HermesTaskRepository` (local handoff, DataStore) |
| `tasks` | shell | `ui/screens/tasks/TasksScreen.kt` | `OrchestratorViewModel` | `HermesTaskRepository` (local handoff) |
| `jobs` | shell | `ui/screens/jobs/JobsScreen.kt` | `JobsViewModel` | `CockpitJobsRepository` → `/v1/cockpit/jobs` (live; NotPaired/empty/error+retry) |
| `chat` | shell | `ui/screens/chat/JarvisChatScreen.kt` | `JarvisChatViewModel` | `RoutingJarvisChatGateway` → `/v1/jarvis/chat` (JSONL) or mock |
| `approvals` | shell | `approval/ui/screens/ApprovalsScreen.kt` | `ApprovalViewModel` | `CockpitApprovalsRepository` → `/v1/cockpit/approvals` |
| `memory` | shell | `ui/screens/memory/MemoryScreen.kt` | `MemoryViewModel` | `MemoryRepository` → `/v1/cockpit/memory` |
| `audit` | shell | `ui/screens/audit/AuditScreen.kt` | `AuditViewModel` | `AuditRepository` → `/v1/cockpit/audit` |
| `capability` | shell | `ui/screens/capability/CapabilityScreen.kt` | `CapabilityViewModel` | `CapabilityRepository` (curated **in-app** catalog — not server-backed) |
| `control` | shell | `ui/screens/control/ControlScreen.kt` | `ControlViewModel` | `HermesCockpitClient` (runtime status/workers) + local emergency stop |
| `settings` | push | `ui/screens/settings/SettingsScreen.kt` | `SettingsViewModel` | `SettingsRepository` (local) |
| `diagnostics` | push | `ui/screens/diagnostics/DiagnosticsScreen.kt` | `DiagnosticsViewModel` | `LogBuffer` (in-memory ring buffer — **not** `/v1/cockpit/diagnostics`) |
| `task_detail/{taskId}?target={target}` | push | `ui/screens/orchestrator/TaskDetailScreen.kt` | `TaskDetailViewModel` | `HermesTaskRepository` + `PromptBuilder` (local handoff) |
| `audit_detail/{auditId}` | push | `ui/screens/audit/AuditDetailScreen.kt` | `AuditDetailViewModel` | `AuditRepository` → `/v1/cockpit/audit/{id}/proof` |
| `jarvis_live` | push | `ui/screens/live/JarvisLiveScreen.kt` | `JarvisLiveViewModel` | `HermesCockpitClient` avatar persona/room |
| `avatar_picker` | push | `ui/screens/avatar/AvatarPickerScreen.kt` | `AvatarPickerViewModel` | `AvatarRepository` + `HermesCockpitClient` persona |
| `voice` | push | `ui/screens/voice/VoiceCaptureScreen.kt` | `VoiceCaptureViewModel` | `JarvisTaskSink` (local) + `VoiceLoopService` → chat gateway |

**Bottom-nav tabs** (`Screen.bottomTabs`): Home, Tasks, Chat, Approvals,
Control. Jobs, Memory, Audit, and Capability are shell destinations reached
from **Home quick-links**, not bottom tabs. Quick-links are now rendered
data-driven from `Screen.homeQuickLinks` (the single source of truth), so a
shell route can no longer become deep-link-only — a reachability invariant
enforced by `ScreenTest`. (This fixed Capability, which was previously
registered but had no UI entry point.)

---

## 6. Backend API coverage map

Each cockpit route (`gateway/cockpit/server.py:46-73`) + the chat route,
mapped to its typed client method and consuming screen. Status legend:
**Live** = typed client method wired to a screen; **getRaw/unwired** =
server route exists and is reachable via `HermesCockpitClient.getRaw()`
but has no typed accessor and no screen; **client-only** = typed method
exists but no screen consumes it yet; **local** = handled on-device,
backend route not used.

| Backend route | Method | Typed client method | Consuming screen | Status |
|---|---|---|---|---|
| `/v1/health` | GET | `health()` | negotiation / Control | **Live** |
| `/v1/cockpit/runtime/status` | GET | `runtimeStatus()` | Control, JarvisLive | **Live** |
| `/v1/cockpit/runtime/workers` | GET | `runtimeWorkers()` | Control | **Live** |
| `/v1/cockpit/diagnostics` | GET | — (getRaw) | Diagnostics uses local `LogBuffer` | **getRaw/unwired** |
| `/v1/cockpit/models` | GET | — (getRaw) | none | **getRaw/unwired** |
| `/v1/cockpit/memory` | GET/POST | `memoryList()`, `memoryCreate()` | Memory | **Live** |
| `/v1/cockpit/memory/{id}` | DELETE | `memoryDelete()` | Memory | **Live** |
| `/v1/cockpit/events` | GET | — (getRaw) | none (Audit uses `/audit`) | **getRaw/unwired** |
| `/v1/cockpit/audit` | GET | `auditList()` | Audit | **Live** |
| `/v1/cockpit/audit/{id}/proof` | GET | `auditProof()` | AuditDetail | **Live** |
| `/v1/cockpit/jobs` | GET/POST | `jobsList()`, `jobDispatch()` | Jobs (`JobsScreen`/`JobsViewModel`) | **Live** |
| `/v1/cockpit/jobs/{id}` | GET | `jobGet()` | — (repository method, not yet surfaced as a detail screen) | **client-only** |
| `/v1/cockpit/jobs/{id}/run` | POST | — | — | **getRaw/unwired** |
| `/v1/cockpit/jobs/{id}/cancel` | POST | `jobCancel()` | Jobs (confirmation-gated cancel) | **Live** |
| `/v1/cockpit/approvals` | GET | `approvalsList()` | Approvals | **Live** |
| `/v1/cockpit/approvals/{id}` | POST | `approvalsDecide()` | Approvals | **Live** |
| `/v1/cockpit/proposals` | GET | — (getRaw) | none | **getRaw/unwired** |
| `/v1/cockpit/skills` | GET | — (getRaw) | Capability uses in-app catalog | **getRaw/unwired** |
| `/v1/cockpit/navigation` | GET | — (getRaw) | none | **getRaw/unwired** |
| `/v1/cockpit/sessions` | GET | — (getRaw) | none | **getRaw/unwired** |
| `/v1/cockpit/avatar/persona` | GET/POST | `personaGet()`, `personaSet()` | JarvisLive, AvatarPicker | **Live** |
| `/v1/cockpit/avatar/room` | GET/POST | `roomList()`, `roomGenerate()` | JarvisLive | **Live** |
| `/v1/cockpit/avatar/room/{id}` | DELETE | — | — | **getRaw/unwired** |
| `/v1/cockpit/avatar/room/{id}/place` | POST | `roomPlace()` | JarvisLive | **Live** |
| `/v1/jarvis/chat` | POST | `HttpJarvisChatGateway` (JSONL) | Chat, Voice | **Live** |

---

## 7. Security and control invariants

- **Owner gates.** `approvalsDecide()` sends an `authorization` phrase for
  approve decisions; the gateway returns **403** if it is missing or
  wrong (`HermesCockpitClient.approvalsDecide` doc; enforced server-side).
  The owner gate is never bypassed by the app.
- **Emergency stop.** Globally reachable from `JarvisShell` and the
  Control screen → `OrchestratorServiceController.emergencyStop()`
  (`service/OrchestratorServiceController.kt`),
  `data/emergency/EmergencyStopController.kt`. **Today this is a
  local/on-device stop; there is no backend emergency-stop route.** See
  gap MOBILE-CONTROL-001 (§8).
- **Audit ledger + proof.** Read-only on mobile via `/v1/cockpit/audit`
  and `/v1/cockpit/audit/{id}/proof`. Secrets are redacted before display
  (`data/audit/SecretRedactor.kt`, `data/memory/MemoryRedactor.kt`).
- **Destructive-action friction.** Approve/cancel/override require an
  explicit confirmation sheet; none are reachable directly from a
  notification action (notifications only open the app to the sheet).
- **Two-store secure storage.** DataStore (`hermes_settings`, no secrets,
  backed up) vs EncryptedSharedPreferences (bearer token only, excluded
  from backup). Changing the endpoint clears the token — no token is
  inherited across hosts. Provider API keys never leave the gateway
  (`~/.hermes/.env`); the phone carries no provider credential.
- **No secrets / raw chain-of-thought / cookies in memory datasets** —
  the memory store rejects secret-like / low-confidence items (422).

---

## 8. Gaps → implementation backlog

Each item is bounded, references this doc, and updates §5/§6 on landing.
None are part of this (docs-only) task.

- **MOBILE-API-001 — typed cockpit accessors.** Add typed methods on
  `HermesCockpitClient` for `diagnostics`, `models`, `events`,
  `proposals`, `skills`, `navigation`, `sessions`, and `jobs/{id}/run`,
  replacing `getRaw` use. Files: `data/cockpit/HermesCockpitClient.kt`,
  `data/cockpit/CockpitApi.kt`. Tests:
  `app/src/test/.../data/cockpit/`. Verify: unit tests assert request
  shape + decode against fixtures.
- **MOBILE-JOBS-001 — bind cockpit jobs to a screen. ✅ DONE.** A `Jobs` shell
  destination (`ui/screens/jobs/JobsScreen.kt` + `JobsViewModel`) now consumes
  the existing `CockpitJobsRepository` → `/v1/cockpit/jobs`, with status pill,
  NotPaired/empty/loading/error+retry states, and a confirmation-gated cancel.
  Reachable via a Home quick-link. The local-handoff `Tasks` screen is
  untouched (distinct subsystem). Follow-up: a job *detail* screen over
  `jobGet()` and dispatch UI (`jobDispatch()`) — currently repository-only.

- **MOBILE-RESEARCH-001 — first-class Research/Evidence mobile surface.**
  Research/Evidence is required for the finished cockpit, but **no backend
  route** (`/v1/cockpit/research|evidence|vault`) and **no Android screen**
  exist today. It must **not** be faked, and Memory search / SIA proposals must
  **not** masquerade as it. Required work:
  - Audit existing ResearchVault, Memory Tree, RAG, citation, web-search, and
    evidence-related backend modules.
  - Add/expose backend Evidence/Research route(s): search / detail /
    verification, and an EvidenceVault/ResearchVault API surface.
  - Add an Android Research/Evidence screen + repository/client layer (mirror
    the cockpit-backed pattern: `HermesCockpitClient` typed accessor →
    repository `sync` state → ViewModel → screen).
  - Display source title, excerpt, **trust level, freshness, citations,
    contradictions**, and a promote-to-memory action.
  - Tests for the backend route, the Android ViewModel, and the
    citation/evidence display.
  Current partial support (only — **not** the canonical implementation): the
  Memory screen exposes recollection over `/v1/cockpit/memory?q=`.
- **MOBILE-DIAG-001 — wire Diagnostics to the backend.** Diagnostics renders
  only the local `LogBuffer`; add a path that surfaces
  `/v1/cockpit/diagnostics` (depends on MOBILE-API-001). Keep the local log
  view.
- **MOBILE-CAP-001 — reconcile Capability with `/v1/cockpit/skills`.** The
  Capability screen uses a curated in-app catalog; decide whether to merge
  the server skills list in (depends on MOBILE-API-001).
- **MOBILE-UX-001 — unify the status-first pattern across cockpit screens.**
  `JobsScreen` establishes the full status-pill + NotPaired/empty/loading/
  error+retry pattern. Memory/Approvals/Control already carry empty/error
  affordances but do not yet show a uniform `GatewayStatusPill` or distinguish
  *NotPaired* from *empty*. Roll the pattern out (additive, no refactor of
  passing behaviour). Deferred from the Jobs PR to keep that diff small.

- **MOBILE-CONTROL-001 — backend-aware emergency stop.** Emergency stop is
  local-only. Evaluate a backend stop route + wire
  `EmergencyStopController` to it while keeping the local stop as a
  fallback. Verify: tests prove the local stop still fires if the backend
  is unreachable.
- **MOBILE-STREAMING-001 — mobile-native streaming.** Per §4.3/§4.4:
  1. Evaluate **SSE vs WebSocket vs polling/JSONL**.
  2. Implement the server route (alongside the existing poll route).
  3. Implement the Android client method (`Flow`, poll fallback).
  4. Add tests (server + client).
  5. Update §4.1/§4.2 of this doc **only after** the implementation
     passes.

---

## 9. Cross-references

- [`muse-mobile-architecture.md`](muse-mobile-architecture.md) —
  prior native-Android design. **Superseded** on the transport (§4):
  its SSE endpoints and `data/network/`/`CockpitSseClient.kt` are not
  implemented; the live transport is in `data/cockpit/` and is
  poll/JSONL.
- [`muse-mobile-backend-contract.md`](muse-mobile-backend-contract.md)
  — mobile↔backend wire summary; see also `gateway/cockpit/contract.py`.
- [`app-screens.md`](app-screens.md),
  [`app-api-client.md`](app-api-client.md),
  [`app-state-model.md`](app-state-model.md),
  [`app-background-service.md`](app-background-service.md),
  [`app-voice-service.md`](app-voice-service.md) — per-area
  implementation notes.
- [`../android/muse-apk-api-contract.md`](../android/muse-apk-api-contract.md),
  [`../android/muse-apk-cockpit.md`](../android/muse-apk-cockpit.md) —
  cockpit behavioural/API contracts.
- [`../../apps/android/docs/ARCHITECTURE.md`](../../apps/android/docs/ARCHITECTURE.md)
  — the module's own architecture notes (secure storage, wire format).
- **Capability matrix:** `JARVIS_MOBILE_CAPABILITY_MATRIX.md` (follow-up
  task — full capability × endpoint × surface × status matrix).
