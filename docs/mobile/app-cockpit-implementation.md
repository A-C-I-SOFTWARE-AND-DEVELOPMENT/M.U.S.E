# Mobile cockpit — Phase 20 implementation plan

> **Status:** implementation plan. Phase 18 produced the cockpit spec
> ([`docs/android/hermes-apk-cockpit.md`](../android/hermes-apk-cockpit.md))
> and the API contract
> ([`docs/android/hermes-apk-api-contract.md`](../android/hermes-apk-api-contract.md)).
> Phase 20 turns those into a concrete build plan against the existing
> native Android scaffold at [`apps/android/`](../../apps/android/).

## 1. Decision: native scaffold, not Flutter

The repository already ships a Kotlin + Jetpack Compose scaffold under
[`apps/android/`](../../apps/android/) (package `com.aci.hermes`,
min SDK 26, target SDK 35, Material 3). That scaffold has:

- a working DI container ([`AppContainer`](../../apps/android/app/src/main/java/com/aci/hermes/di/AppContainer.kt)),
- a foreground service shell ([`HermesService`](../../apps/android/app/src/main/java/com/aci/hermes/service/HermesService.kt)),
- DataStore + EncryptedSharedPreferences wiring,
- the Phase 18 typed payloads in
  [`data/cockpit/CockpitApi.kt`](../../apps/android/app/src/main/java/com/aci/hermes/data/cockpit/CockpitApi.kt),
- the Termux intent bridge in
  [`data/termux/TermuxIntentBridge.kt`](../../apps/android/app/src/main/java/com/aci/hermes/data/termux/TermuxIntentBridge.kt),
- and a starter nav graph ([`HermesNavGraph`](../../apps/android/app/src/main/java/com/aci/hermes/ui/navigation/HermesNavGraph.kt)).

A parallel Flutter or React-Native app would re-implement DI, secret
storage, the Termux bridge, and the Kotlin-native OkHttp/SSE client
without giving muse anything it doesn't already have. Phase 20
**does not introduce a second mobile stack**. Future cross-platform
work — iPad, desktop Linux — should be evaluated in its own phase.

The `mobile/` top-level directory is therefore **intentionally absent**.
If you find yourself wanting to add one, write that decision up first
(in this file) so the reasoning is auditable.

## 2. Goals and non-goals

### 2.1 Goals

1. Ship the 12 cockpit screens listed in `app-screens.md` as Compose
   destinations under `ui/screens/*`, wired into `HermesNavGraph`.
2. Establish a single typed API client
   ([`app-api-client.md`](app-api-client.md)) so every screen reads from
   the same source of truth.
3. Add an on-device voice capture service
   ([`app-voice-service.md`](app-voice-service.md)) that turns spoken
   prompts into `POST /v1/cockpit/jobs` dispatches without the user
   having to look at the screen.
4. Promote `HermesService` to a real foreground worker that owns the
   SSE subscriptions and the offline-queue replay
   ([`app-background-service.md`](app-background-service.md)).
5. Lock the state model so screens cannot bypass the repositories
   ([`app-state-model.md`](app-state-model.md)).

### 2.2 Non-goals

- **No embedded Python.** The cockpit is a thin client. See
  [`apps/android/README.md`](../../apps/android/README.md).
- **No on-device skill execution.** Skills run on the gateway.
- **No client-side provider keys.** Provider keys live on the gateway;
  the cockpit holds the gateway bearer token only.
- **No bespoke crypto.** Use `EncryptedSharedPreferences` for secrets;
  do not invent a key wrapping scheme.
- **No analytics from the APK.** Zero telemetry, per the Phase 18
  rule.

## 3. Milestones

The work is split into four milestones so a partial release is always
shippable to internal testers.

### M20.1 — Read-only cockpit (one sprint)

Outcome: a tester can connect to a gateway and *watch* what it is
doing without being able to break anything.

| Screen | Wiring |
|---|---|
| Worker Dashboard | `GET /v1/cockpit/jobs` + SSE on `/v1/cockpit/jobs/stream` |
| Job Folder Browser | `GET /v1/cockpit/jobs/{id}/tree`, `…/file` |
| Decision Ledger Viewer | `GET /v1/cockpit/jobs/{id}/ledger` |
| Logs / Events | `GET /v1/cockpit/events` + SSE on `…/events/stream` |
| Remote Windows Worker Status | `GET /v1/cockpit/runtime/workers` filtered to `kind=windows` |
| Settings / Secrets / Integrations | already partly built; add backend-workers card |

Acceptance:

- Cockpit boots, lists running jobs, tails events live.
- Killing the gateway flips every screen's status pill to amber within
  ≤5 s.
- Zero `POST` routes are wired yet, so the worst a misconfigured tester
  can do is read stale data.

### M20.2 — Write actions, behind explicit taps (one sprint)

Outcome: approval, validation, and publishing gates are usable, with
the destructive-action confirmation flow from Phase 18 §4.2.

| Screen | Wiring |
|---|---|
| Prompt Command Center | `POST /v1/cockpit/jobs`; uses `PromptBuilder` server-side |
| Approval Gate | `POST /v1/cockpit/jobs/{id}/approve` |
| Validation Gate | `POST /v1/cockpit/jobs/{id}/revalidate` / `…/override` |
| GitHub Publisher | `GET /v1/cockpit/jobs/{id}/publish/preview`, `POST …/publish` |
| Supabase/Vercel Deploy Planner | `POST /v1/cockpit/jobs/{id}/deploy/plan`, `…/deploy/apply` |

Acceptance:

- Every destructive POST goes through `ConfirmSheet` before firing.
- Every successful POST writes a row into the local
  `DecisionLedgerCache` so the Decision Ledger Viewer reflects the
  user's last action even before the SSE event replays.
- `Idempotency-Key` is generated per tap; double-tap on flaky network
  cannot create a duplicate job.

### M20.3 — Hands-free mode (one sprint)

Outcome: the user can dispatch and approve a job entirely by voice
while driving (`app-voice-service.md`).

| Surface | Wiring |
|---|---|
| Voice Capture / Driving Mode | `VoiceCaptureService` (foreground) + `PromptDictationVm` |
| Foreground status tile | `HermesService` notification with *Pause / Resume* |
| In-car shortcut | `MediaSessionCompat` hooks so the steering-wheel button toggles dictation |

Acceptance:

- A long-press on the headset button starts dictation; releasing it
  dispatches the prompt.
- Voice confirmation is read aloud before every destructive POST
  ("approve publishing job 92? Say *confirm publish*").
- Without network, the prompt sits in the offline queue and the
  notification reflects `pending_send`.

### M20.4 — Resilience and polish (one sprint)

Outcome: the app is something an operator can hand to a colleague
without an instruction sheet.

- Offline queue UI (a chip on every screen showing pending writes).
- Wake-lock toggle on the Termux Control Panel actually held by
  `HermesService`.
- Mock-mode parity for *every* M20.1–M20.3 screen so demos work
  without a backend.
- Accessibility pass: TalkBack labels, 4.5:1 contrast on every status
  glyph, scalable font sizes up to 200 %.
- Crash + ANR taps a local file (`hermes_crashes.log`) — nothing is
  sent off-device.

## 4. Module layout (Kotlin packages)

```
com.aci.hermes
├── HermesApplication.kt              # already exists
├── MainActivity.kt                   # already exists
├── di/
│   └── AppContainer.kt               # extend with cockpit + voice deps
├── data/
│   ├── api/                          # NEW
│   │   ├── CockpitClient.kt          # OkHttp + Retrofit-style wrappers
│   │   ├── SseClient.kt              # OkHttp-SSE EventSource helpers
│   │   └── IdempotencyKeys.kt
│   ├── cockpit/
│   │   └── CockpitApi.kt             # already exists; expand payloads
│   ├── ledger/                       # NEW
│   │   ├── DecisionLedgerCache.kt
│   │   └── LedgerEntry.kt
│   ├── queue/                        # NEW
│   │   ├── OfflineQueue.kt           # disk-backed PendingWrites
│   │   └── PendingWrite.kt
│   ├── voice/                        # NEW
│   │   ├── VoiceRecognizer.kt
│   │   ├── VoicePromptBuilder.kt
│   │   └── ConfirmationPlayer.kt     # text-to-speech
│   ├── preferences/                  # already exists; add VoiceSettings
│   └── termux/                       # already exists
├── service/
│   ├── HermesService.kt              # already exists; promote
│   ├── VoiceCaptureService.kt        # NEW
│   └── notifications/                # NEW
│       ├── CockpitChannelIds.kt
│       └── CockpitNotifications.kt
└── ui/
    ├── navigation/
    │   ├── HermesNavGraph.kt         # already exists; add 8 new routes
    │   └── Screen.kt                 # already exists; add routes
    └── screens/
        ├── command/                  # Prompt Command Center
        ├── voice/                    # Voice / Driving Mode
        ├── dashboard/                # Worker Dashboard
        ├── jobs/
        │   ├── folder/               # Job Folder Browser
        │   └── ledger/               # Decision Ledger Viewer
        ├── gates/
        │   ├── approval/
        │   └── validation/
        ├── publish/
        │   ├── github/
        │   └── deploy/               # Supabase / Vercel
        ├── remote/                   # Remote Windows Worker Status
        ├── settings/                 # already exists; expand
        ├── logs/                     # Logs / Events
        ├── orchestrator/             # legacy local-handoff; keep
        └── splash/                   # already exists
```

## 5. Dependency budget

We do **not** add a new networking library, a new DI framework, or a
new architecture pattern in Phase 20. The diffs land on top of what's
already wired up in `apps/android/app/build.gradle.kts`. The only new
dependencies expected:

| Purpose | Library | Why |
|---|---|---|
| On-device speech-to-text | `androidx.speech` (`SpeechRecognizer`) | Already on every Android 8+ device; no extra APK weight. |
| Text-to-speech for confirmations | `android.speech.tts.TextToSpeech` | Built-in. |
| Disk queue for offline writes | `androidx.datastore:datastore-preferences` (already present) | Reuse what's there. |

If a screen genuinely needs a library that isn't on the list above,
add it in a PR with the line-count of the screen as justification, not
a hypothetical future use case.

## 6. Test plan

- **Unit tests** for every repository class under `data/` go beside
  the code (`apps/android/app/src/test/...`). Mirror the package
  layout.
- **Mock-mode contract tests** ensure every screen renders without a
  backend. CI runs these in headless emulator on `:app:connectedCheck`.
- **API replay tests** exercise `CockpitClient` against fixture JSON
  in `apps/android/app/src/test/resources/cockpit/` so a contract
  change on the gateway side breaks the build, not production.
- **No change-detector tests.** If a test would only fail when the
  code is intentionally edited, delete it. See AGENTS.md.

## 7. Out-of-scope (parked for later phases)

- iPad / web parity. Tracked separately.
- Per-job push notifications from the gateway (FCM/WebPush). Phase
  18 §6 lists this as not-yet-wired. Phase 21 candidate.
- Multi-user cockpit (one phone, multiple gateway tokens / households).
  Today the app supports one bearer token at a time.
- Watch face / Wear OS surface. Worth doing but only after the phone
  cockpit is stable; voice mode covers most of the same ergonomics.

## 8. Cross-references

- [`app-screens.md`](app-screens.md) — every required screen in detail.
- [`app-state-model.md`](app-state-model.md) — repositories,
  view-models, and the state flow rules.
- [`app-api-client.md`](app-api-client.md) — `CockpitClient`, retries,
  SSE handling.
- [`app-voice-service.md`](app-voice-service.md) — driving-mode
  pipeline.
- [`app-background-service.md`](app-background-service.md) — foreground
  service, notifications, offline queue replay.
- [`docs/android/hermes-apk-cockpit.md`](../android/hermes-apk-cockpit.md)
  — Phase 18 spec (still authoritative for screen *behaviour*).
- [`docs/android/hermes-apk-api-contract.md`](../android/hermes-apk-api-contract.md)
  — wire contract.
- [`docs/android/termux-intent-bridge.md`](../android/termux-intent-bridge.md)
  — on-device Termux interop.
