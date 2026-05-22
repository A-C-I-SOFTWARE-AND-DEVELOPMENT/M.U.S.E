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
│       │   │   ├── model/                    # ChatMessage, Provider, HermesStatus
│       │   │   ├── preferences/              # DataStore + EncryptedSharedPreferences
│       │   │   └── network/                  # HermesClient + Mock + Gateway impl
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
 ┌─────────┐    suspend     ┌──────────────────────┐    HTTP/SSE    ┌──────────┐
 │ Screen  │───────────────▶│   ViewModel          │───────────────▶│ Gateway  │
 │ (Compose│  StateFlow     │   ↓                  │                │ (Python) │
 │  state) │◀───────────────│ HermesClientFactory  │                └──────────┘
 └─────────┘                │  → HermesClient      │
                            │      ├ Gateway       │
                            │      └ Mock          │
                            └──────────────────────┘
                                      │
                                      ▼
                              SettingsRepository
                              (DataStore + EncryptedSharedPreferences)
```

The factory is queried **per request** (not cached): it inspects the latest
settings snapshot, so toggling mock mode or changing gateway URL takes
effect on the next `send()` without recreating ViewModels.

## Secure storage

Two stores, deliberate split:

- **DataStore (`hermes_settings`)** — non-secret prefs: gateway URL, theme,
  default provider id, mock-mode flag, onboarding flag.
- **EncryptedSharedPreferences (`hermes_secure_prefs.xml`)** — secrets:
  gateway bearer token, provider API key. Sealed with a hardware-backed
  master key when available (`MasterKey.KeyScheme.AES256_GCM`). Excluded
  from cloud backup and device transfer via `data_extraction_rules.xml`
  and `backup_rules.xml`.

Both stores are wiped by **Settings → Reset all settings**.

## Wire format

The Android app talks to the gateway over HTTP. Two endpoints are used
today:

### `GET /v1/health`

Plain JSON, no auth required (gateway choice). Response:

```json
{
  "ok": true,
  "version": "0.14.0",
  "provider_id": "openrouter",
  "model": "anthropic/claude-3.5-sonnet",
  "message": null
}
```

All fields except `ok` are optional. The Android client treats `ok=false`
as "show as disconnected" without crashing.

### `POST /v1/chat`

Request body:

```json
{
  "provider_id": "openrouter",
  "messages": [
    { "role": "user", "content": "hello" },
    { "role": "assistant", "content": "hi there" },
    { "role": "user", "content": "summarize my last week of cron runs" }
  ]
}
```

Headers:

- `Authorization: Bearer <gateway-token>` (optional)
- `X-Hermes-Provider-Key: <provider-api-key>` (optional — forwarded so the
  gateway can call the provider without storing the user's key)
- `X-Hermes-Provider-Id: <provider-id>` (optional — convenience for the
  gateway to route to the right backend)
- `Accept: text/event-stream`

Response: a Server-Sent Events stream. Each event is JSON in the data
field. Three event types are consumed by the app today:

```
event: message
data: {"type":"delta","text":"Of course — "}

event: message
data: {"type":"delta","text":"here is your summary…"}

event: message
data: {"type":"done"}
```

On error the gateway emits `{"type":"error","message":"..."}` and the app
renders it as a red note under the partial reply rather than discarding
the accumulated content.

**Gateway TODO:** The Python gateway in this repo currently exposes a
similar but not identical surface (it serves WebSocket gateway connections
for chat platforms). Wiring up `/v1/chat` SSE specifically for the Android
client is tracked as future work; until then the mobile app is most useful
in mock mode or against a thin REST shim sitting in front of the gateway.

## Build types

| Build type | App id | Default mock mode | Default gateway URL |
|---|---|---|---|
| `debug` | `com.aci.hermes.debug` | ON | `http://10.0.2.2:8080` (emulator → host) |
| `release` | `com.aci.hermes` | OFF | `""` (user must enter) |

Both are configured in `app/build.gradle.kts` via `buildConfigField`.

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
