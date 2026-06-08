# MUSE — Mobile-Native Full-Build Audit

- **Repo:** `A-C-I-SOFTWARE-AND-DEVELOPMENT/hermes-agent`
- **Branch:** `claude/jarvis-prime-android-ZtoB7`
- **Generated:** 2026-06-03T14:40:53Z
- **Method:** Read-only static inspection (grep/find/read). **No functional
  code edited.** Android build/lint not run (`ANDROID_HOME` unset in this
  environment — CI runs it via `.github/workflows/android-build.yml`).
- **Machine-readable mirror:** [`jarvis_mobile_native_full_build_audit.json`](./jarvis_mobile_native_full_build_audit.json)

---

## 1. Executive summary

The goal is to finish MUSE as a mobile-first/mobile-native Android
cockpit **without losing Hermes backend power**. The single most important
finding is that **this is mostly a *wiring* problem, not a *building* problem.**

- The Android app (`apps/android`) is a mature Compose app: a full navigation
  shell, ~17 routes, real ViewModels, services, voice loop, and a "living
  avatar" Den. Chat, Memory, Audit, Approvals, Control, Persona, and Room are
  **already wired end-to-end** to the live loopback cockpit API.
- The cockpit API (`gateway/cockpit/`) already serves a **broad, real** surface
  (~25 routes) backed by the actual MUSE runtime, `JobQueue`,
  orchestrator, and decision ledger.
- **The gap:** several real backend capabilities are exposed by the server but
  **consumed by no Android screen**. The biggest is the **orchestration Job
  Queue** (contract §4: list/dispatch/run/cancel). The generic `getRaw`
  passthrough on the client is used **only in a unit test**, so `models`,
  `sessions`, `navigation`, `proposals`, `events`, and `diagnostics` endpoints
  are also unwired on mobile.
- Some powers are not exposed by the cockpit **at all** (backend/CLI-only):
  **Research Vault, TokenJuice, model scorecards, ledger replay**.

**Bottom line:** to make the phone a true command center, *extend the existing
app to consume the endpoints that already exist* (start with the Job Queue +
an owner-gated `run`), then add a small number of new read routes for the
vault/replay. Do **not** build a third API surface or a second task model.

---

## 2. Current architecture map

| Layer | Location | Notes |
|---|---|---|
| Android cockpit | `apps/android` (Kotlin/Compose) | Single `NavHost` in `ui/navigation/HermesNavGraph.kt`; routes in `Screen.kt`; hand-rolled DI in `di/AppContainer.kt`. |
| Cockpit transport | `data/cockpit/HermesCockpitClient.kt`, `CockpitHttp.kt`, wire models `CockpitApi.kt` | Bearer token, typed `CockpitResult`, honest `Unreachable`. |
| Cockpit API server | `gateway/cockpit/{server,handlers,contract,auth,agent}.py` | Stdlib HTTP (Termux-safe), loopback-only by default. Launched by `hermes cockpit serve` (`hermes_cli/main.py:5868`). |
| MUSE runtime | `hermes_cli/jarvis_prime/` | `__main__.py` (perceive/classify/gate/handle/stop/forget/remember/recollect/tick), `memory.py`, `research_vault.py`, `avatar.py`. |
| Orchestration | `hermes_cli/job_queue.py`, `orchestrator.py`, `orchestrator_api.py`, `orchestrator_replay.py`, `workers.py` | Real job execution + replay. |
| Decision ledger | `hermes_cli/decision_ledger.py` | Source for cockpit audit/proof. |
| Desktop web UI | `hermes_cli/web_server.py` | **Separate** FastAPI `/api/*` surface (status/sessions/config/model mgmt). |
| Channel gateway | `gateway/` (`run.py`, platforms) | Telegram/Discord/Slack/etc bridge. |

---

## 3. Mobile app — current state

**Routes (all map to real screens; none are stubs in the graph):** Splash,
Onboarding, Home, Tasks, Chat, Approvals, Memory, Audit, Capability, Control,
Settings, Diagnostics, TaskDetail, AuditDetail, JarvisLive, AvatarPicker, Voice.
(`ui/navigation/Screen.kt`, `HermesNavGraph.kt`.)

**Wired live to the backend** (via `di/AppContainer.kt`):

| Feature | Evidence |
|---|---|
| Chat (SSE streaming, routed live↔mock by pairing) | `HttpJarvisChatGateway` + `RoutingJarvisChatGateway` |
| Memory CRUD | `MemoryRepository(client=cockpitClient)` → `memoryList/Create/Delete` |
| Audit + proof | `AuditRepository(client=cockpitClient)` → `auditList/auditProof` |
| Approvals (owner phrase) | `CockpitApprovalsRepository`; `OWNER_PHRASE`; `approvalsDecide(authorization=…)` |
| Control / runtime + workers | `ControlViewModel.kt:55` `client.runtimeWorkers()`, `runtimeStatus()` |
| Avatar persona + Room | `personaGet/Set`, `roomList/Generate/Place` |
| Voice → agent | `AppContainer.voiceDispatchToAgent` → `jarvisChatGateway` |

**Local-only stores (not backend-backed):**

- **Tasks** use `HermesTaskRepository` (clipboard handoff to ChatGPT/Codex) via
  `OrchestratorViewModel` — **not** the cockpit `JobQueue`.
- **Capability** is a curated in-app catalog (`CapabilityRepository`), explicitly
  not server-backed.
- **Diagnostics** reads the local `LogBuffer`, not `GET /v1/cockpit/diagnostics`.

**Permissions/services:** `POST_NOTIFICATIONS`, `FOREGROUND_SERVICE(+DATA_SYNC/
SPECIAL_USE/MICROPHONE)`, `SYSTEM_ALERT_WINDOW` (overlay), `RECORD_AUDIO`,
`BLUETOOTH_CONNECT`, `QUERY_ALL_PACKAGES`, an **accessibility service**
(`res/xml/jarvis_accessibility.xml`, `canRetrieveWindowContent=true`). Powerful
automation surface — see §11 risk table.

---

## 4. Backend — current state

**Cockpit routes (live; `gateway/cockpit/server.py`):** `health`,
`runtime/status`, `runtime/workers`, `diagnostics`, `models`, `memory` (GET/POST/
DELETE), `events`, `audit` + `audit/{id}/proof`, `jobs` (GET/POST) +
`jobs/{id}` + `jobs/{id}/run` + `jobs/{id}/cancel`, `approvals` (+ decide),
`proposals`, `skills`, `navigation`, `sessions`, `avatar/persona`,
`avatar/room` (+ place/delete), and `POST /v1/jarvis/chat` (SSE).

**Owner gates (preserved, verified):**
- `job_run` is **double-gated** — exact owner phrase **and** loopback-only
  refusal when bound externally (`handlers.py:389`).
- `approvals_decide` approve requires the exact owner phrase (`handlers.py:679`).
- Secrets stay backend-side; the cockpit holds **only** the bearer token
  (`docs/android/hermes-apk-api-contract.md`).

---

## 5. Already-built-but-not-wired

> `getRaw` (the only generic accessor for un-typed routes) is referenced **only**
> in `HermesCockpitClientTest.kt:149` — so everything below is unreachable from
> the running app today.

| Backend capability | Server | Android consumer | Severity |
|---|---|---|---|
| **Orchestration Job Queue** (list/dispatch/run/cancel) | live (`handlers.py:295–555`) | **none** — `CockpitJobsRepository` built at `AppContainer.kt:140`, consumed nowhere; client has no `jobRun` | **High** |
| Model scorecards / `models` | live (`handlers.py:140`) | none | Medium |
| Live `events` stream | live (`handlers.py:238`) | none (only via unused `getRaw`) | Medium |
| Backend `diagnostics` (launch doctor) | live (`handlers.py:127`) | none (app shows local logs) | Low |
| `sessions` | live | none | Low |
| `navigation` (HyperAgent decisions) | live (`handlers.py:655`) | none | Low |
| `proposals` (self-update view) | live (`handlers.py:625`) | none (approvals card view overlaps) | Low |

---

## 6. Dead ends / placeholders

- **`PlaceholderScreen.kt`** — exists (`ui/screens/placeholder/`) but is **not
  referenced** in the nav graph; harmless preview/test aid.
- **`TermuxIntentBridge`** — a **documented stub** (`data/termux/…`,
  `docs/android/termux-intent-bridge.md`); intentional until the on-phone Termux
  runtime path is prioritized.
- **Files/Diff/Validation/Publish workflow** — wire models exist in
  `CockpitApi.kt` (`TreeListing`, `DiffSnapshot`, `ValidationSnapshot`,
  `PublishPreview`, `PublishResult`) but there is **no server route and no client
  method**. Spec-only; the largest follow-up.
- **`NotImplementedError` (~59 in Python)** — sampling shows these are **mostly
  legitimate** abstract-method contracts (`agent/memory_provider.py:137`,
  `agent/tts_provider.py:238`, `agent/web_search_provider.py`) and POSIX/Windows
  signal guards (`gateway/run.py:18119`), **not** dead stubs. `0` `TODO/FIXME`
  in Kotlin; 27 in Python.

---

## 7. Bugs / likely UX failures

- **Two "task" mental models on mobile (medium).** Local `HermesTask`
  (clipboard handoff) vs backend `CockpitJob`. Only the local one is shown, so a
  user who dispatches backend work has nowhere on the phone to see it → "where's
  my job?" confusion.
- **Capability catalog can drift (low).** In-app `CapabilityRepository` vs the
  server's real installed skills (`/v1/cockpit/skills`) — two sources of truth.
- **Diagnostics shows local logs, not backend health (low).** On a connectivity
  problem the user can't see the backend's own launch-doctor result.

---

## 8. Missing mobile-native capabilities

- Dispatch/run/cancel a real orchestration job (see §5).
- **Research Vault** access — `hermes_cli/jarvis_prime/research_vault.py` has
  **no** cockpit route.
- **TokenJuice** usage/budget — `tokenjuice` in `agent/tool_executor.py` +
  jarvis_prime, no cockpit route.
- **Model scorecards** — `hermes_cli/scoring.py`; `/v1/cockpit/models` exists but
  unconsumed; no scorecard projection.
- **Ledger replay** — `orchestrator_replay.replay_job`, `orchestrator_api.replay`
  — no cockpit route, no mobile view.
- **On-device live event/log streaming** — `/v1/cockpit/events` unconsumed.

---

## 9. RAG / evidence / coding-agent gaps

- **No dedicated code index** — no `code_index` module exists; coding-agent
  retrieval relies on `gateway/cockpit/grounding.py` + `model_tools.py`, not a
  persistent index.
- **Research Vault evidence not surfaced** — citations/evidence the vault
  captures are not viewable in the cockpit (backend-only).
- **Grounding/retrieval is backend-internal** — mobile cannot inspect what
  context was retrieved for a turn.

---

## 10. Testing / CI gaps

- **No instrumented/Compose UI tests** — only JVM unit tests under
  `app/src/test`; no `androidTest` sources found.
- **Job Queue UI/VM coverage gap** — `CockpitJobsRepositoryTest` exists but there
  is no consuming ViewModel/screen to test.
- **Unwired endpoints lack typed client tests** — `models/sessions/navigation/
  proposals/events` have no typed accessors (only `getRaw`, tested once).
- **CI present:** `android-build.yml`, `android-release.yml`, `tests.yml`,
  `orchestration-tests.yml`, `launch-gate.yml`, `lint.yml`. Android tests run in
  CI (not in this sandbox — `ANDROID_HOME` unset).

---

## 11. Risk table

| Area | Severity | Issue | Evidence | Mitigation |
|---|---|---|---|---|
| Privacy/permissions | **High** | Accessibility can read window content; overlay; query all packages | `AndroidManifest.xml` (`SYSTEM_ALERT_WINDOW`, `QUERY_ALL_PACKAGES`), `res/xml/jarvis_accessibility.xml` (`canRetrieveWindowContent`) | Keep automation behind explicit per-session consent; document data handling; ensure `PrivacyRedactor`/`SecretRedactor` cover captured content; never persist screen content to memory/training |
| Owner gate | **High** | Execute-lane job runs are irreversible/external | `handlers.py:389` | Surface `jobRun` only with the exact owner phrase prompt + loopback; mirror the existing approvals flow |
| Duplication | Medium | Two HTTP API surfaces (`/v1/cockpit` vs `web_server /api`) and two task models | `hermes_cli/web_server.py`; `HermesTask` vs `CockpitJob` | Don't build a third; extend the cockpit for mobile; treat web_server as desktop-only |
| UX trust | Medium | App looks connected while key powers are invisible | §5 | Wire JobQueue first; keep honest `NotPaired`/empty states (already the pattern) |
| Secrets | Low | Token handling on device | contract + `EncryptedSharedPreferences` | Preserve; never accept provider keys in cockpit bodies |

---

## 12. Recommended implementation sequence

1. **Wire the orchestration Job Queue into the Tasks tab (low risk, additive).**
   Add `jobRun` to `HermesCockpitClient` + `CockpitJobsRepository.run` (owner
   phrase; mirror `approvalsDecide`); new `CockpitJobsViewModel`; extend
   `TasksScreen` with a *Backend Jobs* section (list/dispatch/run/cancel) reusing
   `runtimeWorkers()`. **Preserve** the local handoff flow. Tests: repo `run()`,
   client `jobRun` body carries the owner phrase, VM states.
2. **Surface live events + backend diagnostics.** Typed `events` accessor;
   Diagnostics reads `GET /v1/cockpit/diagnostics` + the event feed; replace
   `getRaw` with typed methods.
3. **Model scorecards + sessions (read-only views).** Consume `/v1/cockpit/models`
   and `/v1/cockpit/sessions`.
4. **Reconcile Capability catalog with `/v1/cockpit/skills`.**
5. **Expose Research Vault + ledger replay** via new read-only cockpit routes
   (use the existing adapter pattern in `contract.py`), then mobile views.
6. **Build → diff → validate → publish-PR workflow** (contract §Files/Diff/
   Validation/Publish) on server + client + UI. Largest; gate publish on GitHub
   PAT + owner approval.

---

## 13. Do-not-overwrite list

- `gateway/cockpit/contract.py` — canonical schema source of truth.
- `gateway/cockpit/handlers.py` + `server.py` route table — live API.
- `apps/android/.../data/cockpit/CockpitApi.kt` — wire mirror; keep in lockstep
  with the contract.
- `apps/android/.../data/orchestrator/HermesTaskRepository.kt` +
  `OrchestratorViewModel` — the local handoff flow must stay.
- `apps/android/.../approval/state/CockpitApprovalsRepository.kt` — `OWNER_PHRASE`
  + owner gate.
- Decision ledger files + `hermes_cli/decision_ledger.py` — never silently
  rewrite ledger entries.
- `SettingsRepository` `EncryptedSharedPreferences` token storage path.

---

## 14. Extend-rather-than-replace list

| Target | Why |
|---|---|
| `ui/screens/tasks/TasksScreen.kt` | Add the Backend Jobs section here — no new tab |
| `data/cockpit/HermesCockpitClient.kt` + `CockpitJobsRepository.kt` | Add `jobRun`/`run`; reuse transport + tested repo |
| `di/AppContainer.kt` | Add factories; `cockpitJobsRepository` already constructed |
| `ui/screens/diagnostics/DiagnosticsViewModel.kt` | Augment with backend diagnostics/events instead of a new screen |
| `data/capability/CapabilityRepository.kt` | Merge with `/v1/cockpit/skills` instead of a parallel screen |
| `gateway/cockpit/handlers.py` + `contract.py` | Add new read routes (vault/replay) via the existing adapter pattern |

---

*This audit changed no functional code. The only writes are this file and its
JSON mirror under `docs/audits/`.*
