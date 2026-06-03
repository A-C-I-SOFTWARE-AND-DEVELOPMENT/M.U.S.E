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
encrypted store and the plaintext key is removed. The migration fails safe —
if the encrypted write throws (e.g. Keystore unavailable), the plaintext copy
is left in place so the pairing is never lost, and the next launch retries.

`setCockpitToken` writes the encrypted store; `clearCockpitToken` clears the
encrypted store **and** removes any residual plaintext key. Both stores are
wiped by **Settings → Reset all settings**.

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
| `debug` | `com.aci.hermes.debug` | ON | `$HERMES_GATEWAY_URL`, else `http://10.0.2.2:8080` (emulator → host) |
| `release` | `com.aci.hermes` | OFF | `$HERMES_GATEWAY_URL`, else `""` (user must enter) |

The default URL is resolved at build time from (in order):

1. `-PhermesGatewayUrl=...` (Gradle property)
2. `$HERMES_GATEWAY_URL` (env var)
3. `$ANDROID_API_BASE_URL` (env var alias)
4. Build-type fallback above.

It is exposed via `BuildConfig.DEFAULT_GATEWAY_URL` and only used as the
seed value on first launch — once the user touches the URL field on the
**Provider** screen, the override is persisted in DataStore and the
build-time default no longer applies.

> `10.0.2.2` is an Android-emulator-only loopback alias. The
> `data/network` layer detects it and refuses to dial it from a real
> device (see `util/GatewayUrl.kt`), surfacing a **"Wrong backend URL"**
> banner instead of waiting out the OS-level TCP connect timeout.

## Connection state model

`ConnectionState` (in `data/model/HermesStatus.kt`) is the single source
of truth the status, diagnostics, and provider screens render from:

| State                   | Meaning                                                          |
|-------------------------|------------------------------------------------------------------|
| `Unknown`               | Nothing has been probed yet.                                     |
| `Connecting`            | `/v1/health` probe in flight.                                    |
| `Connected(status)`     | Probe returned 2xx; `status` carries version/model/etc.          |
| `Failed(reason, kind)`  | Probe failed. `kind` ∈ {UNREACHABLE, WRONG_URL, TLS, HTTP, UNKNOWN} |

`HermesGatewayClient.status()` uses a *short-timeout* OkHttp client
clone (5s connect, 8s call timeout) so the UI can show a real error
in ~8 seconds instead of waiting the OS default ~100 seconds.

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
