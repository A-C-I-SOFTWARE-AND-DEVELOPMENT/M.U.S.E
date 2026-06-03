# JARVIS Mobile (native) — architecture

How the native Android app and the Hermes backend fit together, for
developers extending either side. This is the integration-level view;
for the in-app module layout see
[`../../apps/android/docs/ARCHITECTURE.md`](../../apps/android/docs/ARCHITECTURE.md)
and [`hermes-mobile-architecture.md`](hermes-mobile-architecture.md).

---

## The two halves

```
┌────────────────────────────┐         loopback HTTP / NDJSON          ┌──────────────────────────┐
│  Android app (cockpit)      │  ─────────────────────────────────────▶ │  Hermes cockpit backend  │
│  com.aci.hermes             │   Bearer <token> on every route          │  gateway/cockpit/        │
│                             │ ◀───────────────────────────────────── │  (real JARVIS subsystems)│
│  Compose UI → ViewModels →  │   JSON / streamed NDJSON                 │                          │
│  AppContainer (DI) →        │                                          │  chat · jobs · memory ·  │
│  Cockpit/Chat clients       │                                          │  audit · approvals ·     │
└────────────────────────────┘                                          │  models · diagnostics    │
                                                                         └──────────────────────────┘
```

The app holds **no** model, no Python, no kanban DB. It is a window,
input path, approval surface, and launcher. The backend
(`hermes cockpit serve`) exposes the real subsystems over a tiny
stdlib HTTP server (no web framework — Termux-safe).

## Backend: the cockpit API

Source: [`gateway/cockpit/`](../../gateway/cockpit/). The server is
`gateway/cockpit/server.py`; handlers are `gateway/cockpit/handlers.py`.

**Binding & exposure.** `serve(host="127.0.0.1", port=8765, ...)` refuses
to bind a non-loopback host unless `allow_external=True` (which also
warns and is required for the agentic execute lanes to be *disabled* —
see below). Default is loopback-only.

**Auth.** Every route except `GET /v1/health` requires
`Authorization: Bearer <token>`. The token is generated once and stored
owner-only (`0600`) at `${HERMES_HOME}/cockpit/token`
(`gateway/cockpit/auth.py`): `load_or_create_token`, `rotate_token`,
constant-time `token_matches`, `extract_bearer`.

**Route table** (from `server.py`, abridged):

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/v1/health` | no | Liveness; the only open route. |
| POST | `/v1/jarvis/chat` | yes | Stream a real JARVIS turn (NDJSON / chunked). |
| GET | `/v1/cockpit/runtime/status` | yes | Runtime + worker status. |
| GET/POST/DELETE | `/v1/cockpit/memory[/{id}]` | yes | List / add / delete memory. |
| GET/POST | `/v1/cockpit/jobs[...]` | yes | List, dispatch, run, cancel jobs. |
| GET/POST | `/v1/cockpit/approvals[/{id}]` | yes | Owner-gate queue + decide. |
| GET | `/v1/cockpit/proposals` | yes | JARVIS proposal queue. |
| GET | `/v1/cockpit/audit[/{id}/proof]` | yes | Audit ledger + proofs. |
| GET/POST/DELETE | `/v1/cockpit/avatar/*` | yes | Persona + Den room. |

See [`hermes-mobile-backend-contract.md`](hermes-mobile-backend-contract.md),
[`../api/local-orchestrator-api.md`](../api/local-orchestrator-api.md), and
[`../api/websocket-events.md`](../api/websocket-events.md) for the full
contract.

**Gated execute lanes.** `jobs_dispatch` / `job_run`
(`handlers.py`) are double-gated when a worker lane runs Codex/Claude
against the repo: (1) the **owner phrase** must equal the exact
authorization phrase, and (2) agentic execution is **refused on a
non-loopback cockpit** (`configure_runtime(allow_remote_execute=...)`).
Non-gated lanes (local planner / handoff) dispatch directly. This is the
backbone of [coding from the phone](JARVIS_CODING_FROM_PHONE_GUIDE.md).

**Response hygiene.** Handlers return curated JSON; backend logging runs
through the secret redactor (`agent/redact.py`,
`RedactingFormatter` / `redact_sensitive_text`), so tokens and keys never
reach logs or tool output. The cockpit token itself is never echoed in a
response body.

## App: structure & wiring

Hand-rolled DI in `di/AppContainer.kt` (no Hilt — the graph is small).
Each screen is `<Name>Screen.kt` (Compose) + `<Name>ViewModel.kt` holding
one `StateFlow<UiState>`.

**Client selection (mock vs. real).** `AppContainer` reads the latest
settings each request and wires either the live HTTP client or the mock:

- Chat: `HttpJarvisChatGateway` (real, streams NDJSON from
  `/v1/jarvis/chat`) vs. `MockJarvisChatGateway`.
- Cockpit data: `HermesCockpitClient` over `CockpitHttp`. An unpaired or
  unreachable gateway yields a typed `Unreachable`, never a stub.

Both receive the endpoint and token through provider lambdas
(`endpointProvider`, `tokenProvider`) so no client touches storage
directly. Toggling mock mode or the endpoint takes effect on the next
call without recreating ViewModels.

## State & storage model

`data/preferences/SettingsRepository.kt` is the single settings surface.
Defaults encode the **safety floor**: lockdown off, approvals required,
safety gates on, local-only mode on, mock mode off.

**Two stores, deliberate split:**

- **DataStore (`hermes_settings`)** — non-secret prefs only: gateway URL,
  theme, autonomy mode, mock flag, onboarding, safety toggles.
- **Encrypted store (`hermes_secure_prefs`)** — the **cockpit bearer
  token**, the one secret the app holds. Reached only through the
  `SecureTokenStore` interface (`data/preferences/SecureTokenStore.kt`);
  the production impl `EncryptedPrefsSecureTokenStore` is backed by
  AndroidX `EncryptedSharedPreferences` (Keystore master key,
  `AES256_GCM`). `SettingsRepository.cockpitToken` is a `StateFlow`
  seeded from that store.

**Provider API keys never reach the phone** — they live on the gateway
(`~/.hermes/.env`). The phone authenticates with the bearer token; the
gateway holds the model credentials.

**Legacy migration.** Earlier builds stored the token as a plaintext
DataStore key. On construction `SettingsRepository` runs
`CockpitTokenMigration.migrate(...)`: if the encrypted store is empty but
the legacy plaintext key exists, the value is copied into the encrypted
store and the plaintext key is removed. It fails safe — an encrypted-write
failure leaves the plaintext copy in place (no lost pairing) and retries
next launch. `clearCockpitToken()` clears the encrypted store **and** any
residual plaintext key; `resetAll()` wipes both. Covered by
`SecureTokenMigrationTest`.

## Background & device-control services

Declared in `apps/android/app/src/main/AndroidManifest.xml`, each as a
typed foreground service so the OS shows the user what's running:

| Service | FGS type | Purpose | User-visible indicator |
|---|---|---|---|
| `HermesService` | `dataSync` | Backend sync / job watch | Foreground notification |
| `VoiceLoopService` | `microphone` | Hands-free voice loop | Mic FGS notification + in-app indicator |
| `JarvisOverlayService` | `specialUse` (`on_screen_assistant_avatar`) | Floating avatar body | Overlay + FGS notification |
| `JarvisAccessibilityService` | `BIND_ACCESSIBILITY_SERVICE` | Taps/swipes/app launch ("hands") | System accessibility toggle |

Permission rationale and the consent flow are in the
[Capability & Permission guide](JARVIS_CAPABILITY_AND_PERMISSION_GUIDE.md).

## Data flow (one request)

```
Compose screen ──user action──▶ ViewModel.method() ──suspend──▶ Client (real|mock)
      ▲                              │                              │ Bearer token
      │   StateFlow<UiState>         ▼                              ▼ (from SecureTokenStore)
      └──────────────────────  _state.update{…}  ◀──parsed──  cockpit backend
```

## Where to extend

- **New backend endpoint** → add a route in `server.py`, a handler in
  `handlers.py`, then a client method in `HermesCockpitClient` + a
  ViewModel call. Keep auth `requires_auth=True` unless it's truly public.
- **New capability in the picker** → add to
  `data/capability/CapabilityCatalog.kt` (visibility only; the lane must
  already exist on the gateway).
- **New secret** → it goes through `SecureTokenStore`, never DataStore.
  Do not add plaintext token/key persistence.
