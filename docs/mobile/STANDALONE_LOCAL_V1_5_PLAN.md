# Hermes / JARVIS Android — Standalone Local v1.5 Plan

> **Status:** living plan for the v1.5 *Standalone Local Coding Cockpit*.
> v1.5 is **local-first**, has **no central cloud proxy**, ships **no bundled
> provider keys**, and keeps every risky action **owner-gated**. This is
> **not** the v2 "Standalone Cloud" track.

## 1. What v1.5 is

A real, daily-usable, standalone-local coding control plane on Android:

- create coding tasks, inspect repo/CI/PR/release state (when configured),
- generate bounded **work packets**, route coding work to local / Gemma /
  Hermes / Claude / Codex handoffs,
- view model status + scorecards, approve memory, check guardrails,
- operate offline (local notes, drafts, queues, last-known snapshots),
- never proxy provider traffic through a company backend, never exfiltrate.

### Connection modes
- **A — Mock/Demo.** No backend, no network, no keys. Demonstrates the full
  flow with clearly-labelled demo data (`SavedCodingTask.demo = true`).
- **B — Local device.** Termux Hermes / `localhost` cockpit on the same phone.
- **C — Owner backend.** Owner-controlled LAN/VPS Hermes gateway (base URL +
  bearer token in Android Keystore).
- **D — BYO cloud/provider.** Opt-in only, no bundled keys, secrets in the
  secure store. Kept behind a documented future flag where not yet safe.

## 2. Audit findings (what already exists)

This is a **mature** codebase; v1.5 is gap-closing + coding specialization +
honesty + docs, not a rewrite.

**Android app** (`apps/android/`, ~190 Kotlin files): Compose + Material 3,
MVVM, hand-rolled DI (`di/AppContainer.kt`), `EncryptedSharedPreferences`
(Android Keystore) for the **only** secret (cockpit bearer token), 110 JVM
unit tests, 25+ screens (Home, Jobs, Approvals, Memory, Audit, Control,
Diagnostics, Settings, Model Route, …). A tolerant `HermesCockpitClient`
(73 suspend methods) over the JDK HTTP stack, `MockJarvisChatGateway` +
`RoutingJarvisChatGateway` (live↔mock on pairing).

**Backend** (`gateway/cockpit/`, `hermes_cli/jarvis_prime/`): a loopback
cockpit HTTP server with ~70 `/v1/cockpit/*` routes (bearer-auth except
`/v1/health`), NDJSON chat streaming, JARVIS runtime (task router, scorecards,
memory tree, 8 gates, owner auth with the exact phrase `Yes, with
authorization.`, launch doctor), the `WorkPacket` schema, and Ollama /
llama.cpp / vLLM adapters. The coding lanes `/v1/cockpit/coding/{audit,plan,
execute}` already exist.

**CI / release** (`.github/workflows/`): `android-build.yml` (debug APK +
`testDebugUnitTest` + `lintDebug`) and `android-release.yml` (signed release →
rolling `android-latest` GitHub Release with a stable download URL; **falls
back to debug-signing** when the four `ANDROID_KEYSTORE_*` secrets are unset).

### Key gaps v1.5 closes
1. The coding DTOs + client methods (`codingAudit/Plan/Execute`,
   `CodingPacket`) existed but **nothing consumed them** → a real
   New-Coding-Task → Work-Packet → Code-Handoff flow.
2. **No Gemma/Ollama status surface** on Android and **no backend
   local-runtime status endpoint** with honest labels.
3. Mock-mode-first coding flow + offline queue.
4. The v1.5 standalone-local doc set + Data Safety mapping.

## 3. Files changed (high level)

- **New (Android coding cockpit):**
  `data/coding/{CodingModels,CodingTaskStore,CodingPromptBuilder,MockCodingSource,CodingRepository}.kt`,
  `ui/screens/coding/{NewCodingTask,WorkPacketDetail,CodeHandoffHub}{Screen,ViewModel}.kt`.
- **Wiring:** `ui/navigation/Screen.kt`, `ui/navigation/HermesNavGraph.kt`,
  `di/AppContainer.kt`, `ui/screens/home/JarvisPrimeHomeScreen.kt`.
- **Model Center + Gemma status (WS2):** backend `models/local` endpoint
  (`gateway/cockpit/`), Android `data/model/CockpitLocalModelsRepository.kt` +
  `ui/screens/model/ModelCenter*`.
- **Docs:** this plan, plus `apps/android/docs/{STANDALONE_LOCAL_MODE,
  API_CONTRACT,SECURITY_PRIVACY,GEMMA_LOCAL_MODE,RELEASE_DOWNLOAD}.md`.
- **Tests:** `data/coding/*Test.kt`, `ui/screens/coding/*Test.kt`, and Python
  tests for any new backend endpoint.

## 4. Risks
- **No emulator** in CI/web containers (no `/dev/kvm`) → instrumented UI tests
  can't run; compile + JVM unit tests + `assembleDebug` are the verification
  floor. Live-device behaviour is sideload-verified by the owner.
- **JDK drift:** the build targets 17; the container ships 21. AGP runs; the
  Kotlin/Java toolchain compiles to 17.
- **Backend feature drift:** unknown JSON keys are tolerated; unsupported
  capabilities surface as honest "not supported", never fabricated.

## 5. Testing strategy
- Pure-logic + ViewModel JVM tests (no emulator), fake `CockpitHttpExecutor`
  for the client, temp-dir stores for persistence.
- `./gradlew testDebugUnitTest lintDebug assembleDebug` after SDK provision
  (`scripts/setup-android-sdk.sh`).
- Python: `scripts/run_tests.sh <touched paths>` + `python -m compileall`.

## 6. Release strategy
- Debug APK on every change (artifact). Signed release + rolling
  `android-latest` download when the owner sets the four `ANDROID_KEYSTORE_*`
  secrets (named, never valued). Until then: debug-signed sideload, clearly
  labelled. See `apps/android/docs/RELEASE_DOWNLOAD.md`.

## 7. Rollback strategy
- All work lands on `claude/hermes-v1-5-standalone-local-te5uk` via a **draft**
  PR; nothing merges without owner approval. The coding cockpit is additive
  (new routes/screens) — reverting the branch removes it cleanly with no
  migration. Local data lives in a separate JSON file
  (`hermes_coding_tasks.json`); "Clear local data" in Settings/Diagnostics
  removes it.

## 8. Acceptance criteria (tracked to completion or documented blocker)
See the master mission Phase 16. Highlights: app launches; Mock mode works
with no backend; New-Coding-Task → Work-Packet → copy-prompt / gated-send
works; offline queue works; honest backend-unavailable states; Gemma appears
as a local option but is never required; memory/guardrail posture unchanged;
release path verified or blocked only by named owner secrets; focused tests +
Android unit tests + debug APK green. Anything below bar is named in the
final report's **10/10 gap list**.
