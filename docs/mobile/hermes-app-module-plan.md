# M.U.S.E. Android app — module work plan

This is the **execution plan** for the Phase 02 decision recorded in
[`android-vs-flutter-decision.md`](android-vs-flutter-decision.md). It
turns the architecture in
[`hermes-mobile-architecture.md`](hermes-mobile-architecture.md) into
concrete units of work in
[`apps/android/`](../../apps/android/).

We are **not** spawning a new Gradle project, **not** introducing
Flutter, and **not** renaming the existing module. We are continuing
to build the cockpit on the Kotlin + Compose foundation already in the
tree.

---

## 1. Workstreams at a glance

| # | Workstream | Outcome | Blocking on |
|---|---|---|---|
| W1 | Cockpit transport | `HermesCockpitClient` + SSE consumer landed against the spec. | Nothing (mockable). |
| W2 | Cockpit screens | Phase 18 cockpit screens (Prompt, Dashboard, Folder, Diff, Validation, Publisher, Termux Panel, Events) navigable end-to-end. | W1 in mock mode. |
| W3 | Foreground service | `HermesService` extended to own SSE subscription + wake lock + approval notification rebroadcast. | W1. |
| W4 | Voice layer | `VoiceRecorder` + `VoicePlayer` + mic-permission flow, behind a feature flag. | Gateway-side voice routes (separate workstream). |
| W5 | Backend cockpit routes | `/v1/cockpit/*` on the Python gateway. | Out of mobile scope; tracked here for visibility. |
| W6 | Release hardening | Signing config template, HTTPS-only by default in release, F-Droid metadata, Play Store metadata. | None. |

W1–W4 are mobile-owned. W5 is the gateway team. W6 is a release-time
checklist.

---

## 2. Source-tree deltas

### 2.1 Existing files that stay untouched

- `MainActivity.kt`, `HermesApplication.kt`, `di/AppContainer.kt` —
  add new bindings, don't restructure.
- All `ui/theme/` files — Material 3 is already configured correctly.
- `service/HermesService.kt` — extended in W3, not rewritten.
- `data/orchestrator/` — preserved verbatim for the *Local handoff*
  fallback mode.
- `data/preferences/SettingsRepository.kt` — extended with new keys,
  not restructured.
- `data/termux/TermuxIntentBridge.kt` — already shaped correctly; the
  caller (W2 Termux Panel) lands new code.
- `data/cockpit/CockpitApi.kt` — the typed mirror is already in place.
  New fields land alongside spec changes, never independently.

### 2.2 New files this plan adds

```
apps/android/app/src/main/java/com/aci/hermes/
├── data/network/
│   ├── HermesCockpitClient.kt         # W1 — interface + OkHttp impl
│   ├── HermesCockpitClient.Mock.kt    # W1 — mock for UI sandbox
│   ├── CockpitSseClient.kt            # W1 — SSE consumer (OkHttp-SSE)
│   ├── RetryPolicy.kt                 # W1 — shared exponential backoff
│   └── CockpitException.kt            # W1 — typed exception for error envelope
├── data/cockpit/
│   ├── JobRepository.kt               # W1 — process-scoped cache + SharedFlow
│   ├── EventRepository.kt             # W1 — same shape for events stream
│   └── ApprovalRepository.kt          # W1 — pending approvals
├── data/voice/
│   ├── VoiceRecorder.kt               # W4 — AudioRecord wrapper, PCM Flow
│   ├── VoicePlayer.kt                 # W4 — AudioTrack playback
│   └── VoicePermission.kt             # W4 — RECORD_AUDIO lazy ask
├── service/
│   ├── CockpitStreamCoordinator.kt    # W3 — owns SSE lifecycle inside the service
│   ├── ApprovalNotifier.kt            # W3 — notification re-broadcast w/ deep links
│   └── WakeLockHolder.kt              # W3 — single source for partial wake locks
└── ui/screens/cockpit/
    ├── prompt/
    │   ├── PromptCommandCenterScreen.kt
    │   └── PromptCommandCenterViewModel.kt
    ├── jobs/
    │   ├── WorkerDashboardScreen.kt
    │   ├── WorkerDashboardViewModel.kt
    │   ├── JobFolderBrowserScreen.kt
    │   └── JobFolderBrowserViewModel.kt
    ├── diff/
    │   ├── DiffAndMergeReviewScreen.kt
    │   └── DiffAndMergeReviewViewModel.kt
    ├── validation/
    │   ├── ValidationGateScreen.kt
    │   └── ValidationGateViewModel.kt
    ├── publish/
    │   ├── GithubPublisherScreen.kt
    │   └── GithubPublisherViewModel.kt
    ├── termux/
    │   ├── TermuxControlPanelScreen.kt
    │   └── TermuxControlPanelViewModel.kt
    └── events/
        ├── LogsAndEventsScreen.kt
        └── LogsAndEventsViewModel.kt
```

Test mirrors live under `app/src/test/java/com/aci/hermes/` and
`app/src/androidTest/java/com/aci/hermes/`. The repo rule is **tests
mirror the directory of the code they cover**.

### 2.3 Manifest changes

| Change | Why |
|---|---|
| Add `<uses-permission android:name="android.permission.RECORD_AUDIO" />` (guarded; requested lazily). | W4 voice capture. |
| Add `<uses-permission android:name="android.permission.WAKE_LOCK" />`. | W3 wake-lock hold during watched jobs. |
| Add `<queries><package android:name="com.termux" /></queries>` and `<package android:name="com.termux.files" />`. | Required on Android 11+ for `PackageManager.getPackageInfo` to see Termux. |
| Add `<service ... android:foregroundServiceType="dataSync|microphone" />`. | W4 voice capture during prompt entry while the service is up. |
| Flip `usesCleartextTraffic` off on `release` build type. | W6 hardening. |

We deliberately don't enable cleartext on `release` and don't request
RECORD_AUDIO at install time — both are runtime / build-type concerns.

---

## 3. State management plan

- **One `StateFlow<UiState>` per ViewModel.** No second source of truth.
- **Repositories own data caches**, not ViewModels. ViewModels are
  re-rendered when a repo emits.
- **Cross-screen broadcasts** go through `SharedFlow<UpdateEvent>` on
  the repository, not through a singleton event bus.
- **No global state** outside `SettingsRepository` (which is an explicit
  config store) and the three cockpit repos (`Job`, `Event`, `Approval`).

---

## 4. Foreground service plan

`HermesService` evolves in three steps:

1. **Promote stream ownership** — when at least one job is "watched",
   the service starts a `CockpitStreamCoordinator` that owns the SSE
   client. ViewModels subscribe via `EventRepository.observe(jobId)`,
   not by opening their own SSE connection.
2. **Hold a partial wake lock** for the duration of an active watched
   job. `WakeLockHolder` is the only place a wake lock is acquired or
   released — accounting bugs become impossible by construction.
3. **Re-broadcast approval-pending events** as notifications with
   *Approve* / *Reject* action buttons. Tapping an action opens
   `MainActivity` deep-linked to the Diff and Merge Review confirmation
   sheet — never approves in place from the notification.

The service tears all of that down (streams, wake lock, notification
actions) the moment the last watched job leaves
`waiting_for_approval` or `running`.

---

## 5. Voice layer plan

W4 is gated on the gateway-side voice routes (W5) but the mobile-side
shape is settled here so the work can start in parallel:

- `VoiceRecorder` exposes a cold `Flow<ByteArray>` of PCM frames at
  16 kHz mono, started on `start()` and stopped on `stop()`.
- `VoicePlayer` accepts a `Flow<ByteArray>` of PCM frames decoded
  from the SSE TTS stream, plays via `AudioTrack`.
- `VoicePermission.request()` issues the RECORD_AUDIO prompt
  lazily, the **first** time the user taps the mic affordance.
- A `voice_enabled` flag in `SettingsRepository` gates the entire
  surface. Default off. When off, the Prompt Command Center hides the
  mic affordance entirely.

The voice surface is opt-in until both ends are stable.

---

## 6. Local API client plan

Wraps `HermesCockpitClient` exactly as described in
[`hermes-mobile-architecture.md`](hermes-mobile-architecture.md) §8.
Implementation order:

1. **Interface** + **mock** — lands first so screens can render in
   mock mode (workstream W1).
2. **OkHttp implementation** + retry policy + idempotency-key
   handling.
3. **SSE consumer** for job and event streams.
4. **Integration tests** against a gateway harness that replays
   recorded SSE fixtures.

Concrete dependency adds in `app/build.gradle.kts`:

| Library | Purpose |
|---|---|
| `com.squareup.okhttp3:okhttp-sse` | SSE client. |
| `androidx.security:security-crypto` | EncryptedSharedPreferences. Already implied by docs; pin the version explicitly. |
| `androidx.work:work-runtime-ktx` (deferred) | WorkManager for retried offline-queue replay. Land in a follow-up; the in-process replay is sufficient for the first cut. |

Nothing new on the AGP / Kotlin compose side — the toolchain in
`gradle/libs.versions.toml` already covers it.

---

## 7. Secure storage plan

Already in the right shape; the work plan only touches three things:

- **Token rotation** — add a hook in `SettingsRepository.setGatewayUrl()`
  that wipes the stored token when the URL changes.
- **Token mask UX** — the gateway-token field is masked input by
  default with a one-tap *show* that auto-hides after 5 s.
- **Master key fallback** — when hardware-backed key generation fails
  (very old devices), fall back to a software key without
  exposing the failure to the user beyond a Diagnostics-screen note.

No new file is needed; these are surgical edits to
`SettingsRepository` and the Settings screen.

---

## 8. Offline queueing plan

Two persistent queues, both in DataStore:

| Queue | Schema | Drained by |
|---|---|---|
| `drafts.*` | `{id: uuid, title, body, worker_id, created_at}` | User opens a draft from the Prompt Command Center drawer. |
| `pending_decisions.*` | `{id: uuid, job_id, kind, payload, idempotency_key, queued_at}` | Worker Dashboard *"N approvals pending"* banner on the next successful health probe. |

Both queues are wiped by **Settings → Reset all settings**.

---

## 9. Phase 18 backend dependencies (W5, for visibility)

The mobile side does not block on these landing simultaneously — the
cockpit screens render in mock mode by design. They become live when
the gateway lands:

- `/v1/cockpit/runtime/{status,workers}`
- `/v1/cockpit/templates` (optional)
- `/v1/cockpit/jobs` CRUD + `/stream`
- `/v1/cockpit/jobs/{id}/tree` + `/file`
- `/v1/cockpit/jobs/{id}/{diff,files-changed,approve,validation,revalidate,override}`
- `/v1/cockpit/jobs/{id}/publish/{preview}` + `/publish`
- `/v1/cockpit/events` + `/stream`
- `/v1/cockpit/approvals` + `/approvals/{id}/decide`

Voice routes (W4 backend half) are reserved but not specced here:

- `POST /v1/cockpit/voice/transcribe`
- `GET /v1/cockpit/voice/tts`

Tracking on the Python side is out of scope for this doc.

---

## 10. Build, CI, release plan (W6)

- **Debug builds** continue on every push under `apps/android/` via
  `.github/workflows/android-build.yml`. No change needed.
- **Release signing** — add a `keystore.properties` schema doc to
  `apps/android/README.md` and a `signingConfigs { release { ... } }`
  block in `app/build.gradle.kts` (currently a TODO in the README).
  We deliberately do not commit a sample keystore.
- **HTTPS-only release** — Flip `usesCleartextTraffic` for `release`
  in `network_security_config.xml`. Debug builds keep cleartext for
  LAN testing.
- **F-Droid metadata** — `apps/android/metadata/com.aci.hermes/`
  with `en-US/full_description.txt`, screenshots, fastlane structure.
- **Play Store metadata** — same skeleton, separate keystore. The Play
  Store path is a future deliverable and not part of this phase's
  acceptance.

---

## 11. Test plan

Test scope per workstream:

| Workstream | Unit tests | Instrumentation tests | Manual smoke |
|---|---|---|---|
| W1 Transport | `HermesCockpitClient` against `MockWebServer`; error-envelope decoding; idempotency-key replay. | SSE reconnect across network flap. | Hit a real gateway with `curl` parity. |
| W2 Screens | ViewModel state machine tests with fake repos. | Screenshot tests (Paparazzi or Roborazzi) for the eight cockpit screens. | Tap-through in mock mode on a real device. |
| W3 Foreground service | `CockpitStreamCoordinator` lifecycle, `WakeLockHolder` reference counting. | Service survives Doze on Android 14. | Watch a job overnight on a real phone. |
| W4 Voice | Recorder PCM byte-count math, player jitter buffer. | RECORD_AUDIO permission flow on Android 13+. | Real-world latency check on the user's device. |
| W6 Release | Lint and ABI checks on CI. | Smoke on the release APK before each tag. | Manual install on the user's daily-driver phone. |

The repo rule "don't write change-detector tests" applies — assertions
must be about user-visible behaviour, not field-by-field state shapes.

---

## 12. Acceptance for this phase

This phase (Phase 02) is done when:

1. ✅ The four mobile docs under `docs/mobile/` are landed.
2. ✅ `apps/android/` remains a working Kotlin + Compose module
   (Phase 02 does not regress it).
3. ✅ The cockpit's Kotlin contract mirror (`CockpitApi.kt`) is
   referenced from both the architecture doc and the backend-contract
   doc.
4. ✅ The decision in
   [`android-vs-flutter-decision.md`](android-vs-flutter-decision.md)
   is explicit and unambiguous.

Phase 18 (cockpit screens going live) and the voice / publisher
workstreams have their own acceptance criteria.

---

## 13. Open risks

- **Gateway-side cockpit routes are spec-only.** Mobile can build
  against the mock indefinitely, but the value to the user appears
  only when the gateway lands them.
- **Termux RUN_COMMAND permission flow** depends on the user toggling
  *Run external apps* in Termux's settings. We cannot script this and
  must rely on instruction cards.
- **EncryptedSharedPreferences master-key API** has been deprecated by
  Google in favour of newer Keystore-direct usage. We track the
  migration as a future item; the deprecation is not yet breaking.
- **Voice ASR latency over LTE** is unknown until the gateway-side
  voice surface ships. The cockpit's UX must remain usable without
  voice; we treat voice as an enhancement, not a load-bearing path.
- **Foreground-service policy on Android 15+.** Google has been
  tightening rules around long-lived `dataSync` services. We monitor
  release notes and may need to graduate to a `userInitiatedDataTransfer`
  type before Android 15.

---

## 14. Cross-references

- [`android-vs-flutter-decision.md`](android-vs-flutter-decision.md)
  — the decision this plan executes.
- [`hermes-mobile-architecture.md`](hermes-mobile-architecture.md)
  — the architecture this plan implements.
- [`hermes-mobile-backend-contract.md`](hermes-mobile-backend-contract.md)
  — the wire surface this plan depends on.
- [`docs/android/hermes-apk-cockpit.md`](../android/hermes-apk-cockpit.md)
  — Phase 18 cockpit spec.
- [`docs/android/hermes-apk-api-contract.md`](../android/hermes-apk-api-contract.md)
  — authoritative cockpit wire format.
- [`docs/android/termux-intent-bridge.md`](../android/termux-intent-bridge.md)
  — Termux RUN_COMMAND specifics.
- [`apps/android/README.md`](../../apps/android/README.md)
  — current build / run instructions.
- [`apps/android/docs/ARCHITECTURE.md`](../../apps/android/docs/ARCHITECTURE.md)
  — current module architecture.
