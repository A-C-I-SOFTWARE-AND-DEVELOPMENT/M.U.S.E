# Architecture — Hermes Agent Android module

This document describes the **Android-side** architecture. The Python core
(agent loop, skills, memory, tools, scheduling) is unchanged and runs on
the gateway side; the Android app is a thin client over its REST surface.

## Module layout

```
apps/android/
├── app/
│   ├── build.gradle.kts                     # AGP config, deps, build types
│   ├── proguard-rules.pro
│   └── src/main/
│       ├── AndroidManifest.xml
│       ├── java/com/aci/hermes/
│       │   ├── HermesApplication.kt          # process-wide AppContainer
│       │   ├── MainActivity.kt               # entry point, hosts NavHost
│       │   ├── di/AppContainer.kt            # hand-rolled DI
│       │   ├── data/
│       │   │   ├── model/                    # domain models (jobs, approvals, memory, …)
│       │   │   ├── preferences/              # DataStore + EncryptedSharedPreferences (token)
│       │   │   ├── cockpit/                  # HermesCockpitClient + JDK HttpURLConnection
│       │   │   └── jarvis/                   # HttpJarvisChatGateway (NDJSON) + mock + routing
│       │   ├── ui/
│       │   │   ├── theme/                    # Material 3 colors / typography
│       │   │   ├── navigation/               # NavHost + route sealed class
│       │   │   └── screens/                  # one folder per screen, each with VM
│       │   └── util/LogBuffer.kt             # in-memory log ring for diagnostics
│       └── res/                              # strings, icons, themes, backup rules
├── gradle/libs.versions.toml                 # version catalog
├── gradle.properties
└── settings.gradle.kts
```

## MVVM pattern

Each screen is `<Name>Screen.kt` (Composable) + `<Name>ViewModel.kt`. The
ViewModel:

- Holds a single `StateFlow<UiState>` data class.
- Mutates state via `_state.update { it.copy(...) }`.
- Exposes side-effecting methods (`save()`, `refresh()`, etc.) that launch
  inside `viewModelScope`.

ViewModels are constructed by `AppContainer.<screen>VmFactory()` and handed
to `androidx.lifecycle.viewmodel.compose.viewModel(factory = ...)`. There's
no Hilt because the dependency graph is small enough that the indirection
costs more than the wiring.

## Data flow

```
 ┌─────────┐    suspend     ┌───────────────────────┐ HTTP + NDJSON ┌──────────┐
 │ Screen  │───────────────▶│   ViewModel           │──────────────▶│ Cockpit  │
 │ (Compose│  StateFlow     │   ↓                   │  bearer auth  │ gateway  │
 │  state) │◀───────────────│ AppContainer          │               │ (Python) │
 └─────────┘                │  ├ HermesCockpitClient│               └──────────┘
                            │  └ JarvisChatGateway  │
                            │      ├ Http (paired)  │
                            │      └ Mock (unpaired)│
                            └───────────────────────┘
                                      │
                                      ▼
                              SettingsRepository
                              (DataStore + EncryptedSharedPreferences)
```

The chat gateway routes **per `send()`** (not cached): `RoutingJarvisChatGateway`
uses the live HTTP client when paired (token + endpoint set) and a mock
otherwise, so pairing or changing the endpoint takes effect on the next send
without recreating ViewModels.

## Secure storage

Two stores, deliberate split:

- **DataStore (`hermes_settings`)** — non-secret prefs: gateway URL, theme,
  autonomy mode, mock-mode flag, onboarding flag, safety toggles. Never a
  token.
- **EncryptedSharedPreferences (`hermes_secure_prefs`)** — the one secret
  the app holds: the **cockpit bearer token**. Reached only through the
  `SecureTokenStore` abstraction (`data/preferences/SecureTokenStore.kt`,
  production impl `EncryptedPrefsSecureTokenStore`). Sealed with a
  hardware-backed master key when available
  (`MasterKey.KeyScheme.AES256_GCM`; `AES256_SIV` key names, `AES256_GCM`
  values). Excluded from cloud backup and device transfer via
  `data_extraction_rules.xml` and `backup_rules.xml`.

Provider API keys are **never** stored on the phone — they live only on the
gateway (`~/.hermes/.env`); the app authenticates to the loopback cockpit
with the bearer token and the gateway holds the model credentials.

**One-time migration.** Earlier builds briefly stored the cockpit token as a
plaintext DataStore key (`cockpit_token`). On construction,
`SettingsRepository` runs `CockpitTokenMigration`: if the encrypted store has
no token but a legacy plaintext key exists, the value is copied into the
encrypted store and the plaintext key is removed. The migration fails safe:
the encrypted store fails *soft* (a missing Keystore makes the write a silent
no-op, not an exception), so the plaintext copy is dropped **only after the
write is verified by reading it back** — if it didn't land, the plaintext is
kept and the next launch retries, so the pairing is never lost. If the
encrypted store already holds the token, any leftover plaintext copy from a
prior failed clear is still swept up so it never lingers.

`setCockpitToken` writes the encrypted store; `clearCockpitToken` clears the
encrypted store **and** removes any residual plaintext key. Both stores are
wiped by **Settings → Reset all settings**.

## Wire format

The app talks to the cockpit gateway over HTTP. The two endpoints used
directly by this module today:

### `GET /v1/health`

Plain JSON, no auth required (gateway choice). Response:

```json
{
  "ok": true,
  "service": "hermes-cockpit",
  "api_version": "1.0.0",
  "gateway_version": "0.14.0",
  "time": "2026-05-23T18:45:00Z"
}
```

All fields except `ok` are optional. The client also tolerates an older/
alternate shape (`{"ok","version","message",…}`), preferring `gateway_version`
and falling back to `version`. `ok=false` renders as "reachable but unhealthy".

### `POST /v1/jarvis/chat`

The streaming chat turn. Request body:

```json
{
  "prompt": "summarize my last week of cron runs",
  "history": [
    { "role": "user", "content": "hello" },
    { "role": "assistant", "content": "hi there" }
  ]
}
```

Headers:

- `Content-Type: application/json`
- `Accept: application/x-ndjson`
- `Authorization: Bearer <cockpit-token>` (sent when paired)

Response: a **newline-delimited JSON** stream (`application/x-ndjson`, chunked).
Each line is one event from the real muse turn — `thinking`, `phase`,
`tone`, `working`, `body`, `detail`, `done`, `error`. `HttpJarvisChatGateway`
renders `body` deltas as the reply and surfaces `error` inline rather than
discarding the accumulated text. There are **no provider-key headers**: the
gateway holds the provider credentials and makes the model call.

Every other cockpit surface (jobs, approvals, memory, evidence/research,
autonomy, voice intake, …) uses the authenticated `/v1/cockpit/*` REST routes
via `HermesCockpitClient`. See
[`../../../docs/android/hermes-apk-api-contract.md`](../../../docs/android/hermes-apk-api-contract.md)
for the full route contract and live-vs-planned status.

## Build types

| Build type | App id | Default endpoint | Until paired |
|---|---|---|---|
| `debug` | `com.aci.hermes.debug` | `http://127.0.0.1:8765` | chat falls back to mock |
| `release` | `com.aci.hermes` | `http://127.0.0.1:8765` | chat falls back to mock |

The default endpoint (`SettingsRepository.DEFAULT_GATEWAY_ENDPOINT`) is the
loopback cockpit. **No** gateway URL, provider key, or backend secret is
injected at build time — the endpoint is set in **Settings → Connection** and
the bearer token is pasted during pairing. Cleartext loopback HTTP is expected
for an on-device or Termux gateway; point the endpoint at an `https://` address
(e.g. behind Caddy or Tailscale) for a remote backend.

## Connection state model

`ConnectionState` (in `data/model/HermesStatus.kt`) is the single source
of truth the status, diagnostics, and provider screens render from:

| State                   | Meaning                                                          |
|-------------------------|------------------------------------------------------------------|
| `Unknown`               | Nothing has been probed yet.                                     |
| `Connecting`            | `/v1/health` probe in flight.                                    |
| `Connected(status)`     | Probe returned 2xx; `status` carries version/model/etc.          |
| `Failed(reason, kind)`  | Probe failed. `kind` ∈ {UNREACHABLE, WRONG_URL, TLS, HTTP, UNKNOWN} |

The `/v1/health` probe uses short connect/read timeouts on the JDK
`HttpURLConnection` transport so the UI surfaces a real error quickly instead
of waiting out the OS-default connect timeout.

## Why not embed a Python runtime?

A few times a year someone asks. The short answer:

- Android sandboxes (`/data/data/<pkg>`) cannot host the toolchain CPython
  needs to load extension modules built for arbitrary ABIs.
- Chaquopy, BeeWare/Briefcase, and pyodide-on-Android all exist but each
  has significant compromises (limited wheel availability, slow startup,
  no `ffmpeg`/`ripgrep`, voice deps unbuildable).
- Hermes already has a tested manual path on Android via Termux — that
  *is* the embedded option, just sandboxed properly under
  `/data/data/com.termux/files/...`.

If a future Hermes core ever ships an Android-native runtime (e.g. via a
Rust port of a subset, or a Termux-prebuilt bundle the APK can extract),
the `HermesClient` interface is intentionally narrow enough that a
`LocalHermesClient` can be added without touching the UI.
