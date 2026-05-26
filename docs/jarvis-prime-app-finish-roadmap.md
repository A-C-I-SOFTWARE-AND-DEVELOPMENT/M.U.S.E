# Jarvis Prime — finish roadmap (Android)

This document defines the **fastest safe build order** to take the
shipped *Hermes Agent* Android app to a faithful Jarvis Prime
cockpit. Five waves, each one small enough to ship as a single PR,
each one independently green on `assembleDebug` + `lintDebug`.

> No wave below implements gateway changes. The Python gateway side
> is tracked in `docs/android/hermes-apk-api-contract.md`. The
> Android-side roadmap below assumes the gateway side is being
> worked in parallel and treats every gateway endpoint as a
> contract that may not yet be live — every new screen is built
> behind an offline fallback.

---

## Wave 0 — rebrand only (low risk, immediate user value)

Goal: the user uninstalls *Hermes Agent* and reinstalls *Jarvis
Prime* and sees a single coherent product. Zero behavior change.

PR shape: one PR, ≤ 30 files touched, no manifest changes beyond
labels/icons.

1. **Strings.** Rebrand every user-visible string in
   `apps/android/app/src/main/res/values/strings.xml`. Keep the
   string **keys** stable (`orchestrator_*`) so Compose code does
   not move; only swap values.
2. **Splash.** Update `SplashScreen.kt:41,46` to show the new
   Jarvis Prime mark + label. Keep the 600 ms delay so existing UI
   tests (future) still match timing.
3. **Theme.** Rename `Theme.HermesAgent` → `Theme.JarvisPrime` in
   `themes.xml` and the manifest. Rename color tokens in
   `Color.kt` (`HermesGold` → `JarvisGold`, etc.) and propagate
   imports.
4. **Notification.** Update the channel **display name** (not the
   id) and notification title/body in
   `HermesService.kt:121-155`. The id `hermes_orchestrator` stays
   for user-customized importance compatibility.
5. **Icon.** Replace `ic_launcher_foreground.xml` and the
   `ic_launcher.xml` / `ic_launcher_round.xml` adaptive icon
   wrappers. Add a monochrome icon for the Android 13+
   themed-icons API.
6. **Project name.** `settings.gradle.kts:23` → `JarvisPrime`. CI
   cache key changes once; one cold build follows.
7. **Docs.** Rewrite `apps/android/README.md` and
   `apps/android/docs/ARCHITECTURE.md` to reflect the shipped
   reality: a local prompt-builder cockpit being uplifted to the
   Jarvis Prime cockpit. Move all stale "future network client"
   prose to the cockpit/gateway spec under `docs/android/`.
8. **Verification.** `./gradlew assembleDebug` + `lintDebug`
   green; install on emulator; eyeball the splash + dashboard.

Exit criteria:
- Zero references to "Hermes Agent" in user-visible strings,
  README, or ARCHITECTURE.md.
- Internal package id `com.aci.hermes` unchanged.
- Channel id `hermes_orchestrator` unchanged.
- DataStore name `hermes_settings` and file `hermes_tasks.json`
  unchanged.

Risk: LOW. Pure cosmetic. Rollback = `git revert`.

---

## Wave 1 — Jarvis Prime gateway client + cockpit skeleton

Goal: the app can read the gateway's health + job list + per-job
diff and validation summary. Approvals are read-only here; deciding
on them lands in Wave 2.

PR shape: 3–4 PRs, gated on whether the gateway-side endpoint is
already live (`/v1/health` is; others are spec-only per
`docs/android/hermes-apk-api-contract.md`).

1. **Manifest deltas.**
   - Add `<uses-permission android:name="android.permission.INTERNET" />`.
   - Add `<uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />`.
   - Add `<queries>` for `com.termux` and `com.termux.files`.
2. **Build config.**
   - Add `buildConfigField` for `DEFAULT_GATEWAY_URL` resolved
     from (in order) `-PhermesGatewayUrl`, `$HERMES_GATEWAY_URL`,
     `$ANDROID_API_BASE_URL`, then debug fallback
     `http://10.0.2.2:8080`, then release fallback `""`.
   - Add `okhttp` + `okhttp-sse` to `libs.versions.toml`.
3. **Secure storage reintroduction.**
   - Add `androidx.security:security-crypto` dep.
   - Create `data/preferences/SecureGatewayPrefs.kt` storing **only**
     the gateway bearer token in `EncryptedSharedPreferences` under
     the existing `hermes_secure_prefs.xml` filename (matches the
     backup/data-extraction exclusion already in res/xml/).
   - Update `SettingsScreen` to expose a *Connection* section.
4. **Gateway client.**
   - `data/network/JarvisGatewayClient.kt` — OkHttp client + JSON
     serializer using the existing `CockpitApi` types.
   - `data/network/JarvisHealthProbe.kt` — 5 s connect / 8 s call
     timeout clone; surfaces `ConnectionState` (Unknown / Connecting
     / Connected / Failed).
   - All endpoints are behind a `JarvisCockpitRepository` that
     gracefully degrades to a "local-only" mode when the gateway is
     unreachable.
5. **Termux bridge fire path.**
   - Add `fireHermesIntent(intent: Intent): TermuxFireResult` to
     `TermuxIntentBridge`. Use `startService` + result code
     interpretation per `docs/android/termux-intent-bridge.md`.
   - Add the permission probe path described in §2 of that doc.
6. **Cockpit screens (read-only).**
   - `CockpitScreen` — job list, worker chips, dispatch FAB.
   - `JobDetailScreen` — diff + validation summary + (read-only)
     approval banner pointing at Wave 2.
   - Both screens render an offline state when the gateway is
     missing or the user picked Local handoff.
7. **Settings screen extensions.**
   - Connection section: gateway URL field + bearer token field
     (masked) + "Test connection" → `/v1/health`.
   - Local handoff toggle (default ON for upgrade users with no
     gateway configured; default OFF in fresh installs).
8. **Verification.**
   - `./gradlew assembleDebug` + `lintDebug` green.
   - Unit tests added under `app/src/test/` (see Wave 5 for the
     full test suite, but at minimum: `JarvisHealthProbeTest`,
     `JarvisCockpitRepositoryOfflineTest`,
     `TermuxIntentBridgeBuilderTest`).

Exit criteria:
- Health probe round-trips on emulator + Termux gateway.
- Job list renders for an authorized gateway.
- Local handoff path still works end-to-end (must not regress W0
  behavior).

Risk: MED. Networking, secure storage, manifest changes.
Rollback = ship the feature behind a `cockpit_enabled` flag and
default it OFF for one release before flipping.

---

## Wave 2 — approvals, gates, owner authorization, modes, memory

Goal: cockpit becomes a faithful Jarvis Prime surface — gates are
visible, approvals can be decided, owner authorization is captured
the way the Python runtime expects, modes are user-selectable.

PR shape: 2 PRs.

1. **Approvals.**
   - New routes: `approvals`, `approvals/{id}`.
   - New screens: `ApprovalsScreen` (list), `ApprovalDetailScreen`.
   - New notifications channel `jarvis_approvals` (importance
     HIGH); each pending approval posts a notification with two
     actions: *Approve* (opens owner-auth dialog) and *Defer*
     (queues to next launch). Deny stays in-app (intentionally not
     a notification action — too easy to mis-tap).
   - Owner-authorization dialog captures the exact phrase
     `Yes, with authorization.`; mirrors
     `hermes_cli/jarvis_prime/owner_auth.py:AUTHORIZATION_PHRASE`.
     Authorization is **not** persisted across launches.
2. **Gates panel.**
   - `GatesPanel.kt` Composable visualizing the 8 Jarvis Prime
     gates with `GateOutcome` colors and per-gate evidence link.
   - Embedded into `JobDetailScreen` and `TaskDetailScreen`.
3. **Memory.**
   - New route: `memory`.
   - `MemoryScreen` lists `MemoryRecord` items grouped by kind
     (decisions / preferences / lessons / goals).
   - Read-only on first ship; a follow-up wave adds save/forget
     verbs once the gateway side is ready.
   - Static "What does NOT get saved" card matches the Python
     runtime's Memory Rules (no secrets, no temporary emotions, no
     raw voice dumps, no stale issue numbers).
4. **Modes.**
   - Settings → Mode section: six-radio picker (Companion /
     Strategy / Critic / Operator / Builder / Mobile Voice).
   - Mode chip on the Orchestrator and Cockpit top bars.
   - Mode is persisted in DataStore (key: `jarvis_mode`).
   - Cockpit dispatch includes the active mode so the gateway can
     bind the right persona prompt.
5. **HermesTask schema additions (additive only).**
   - Add optional fields: `prUrl`, `commitSha`, `evidence`,
     `parentTaskId`. Envelope version bumps from 1 → 2; loader
     reads either.
6. **Verification.**
   - Add `PromptBuilderTest`, `HermesTaskRepositoryTest` (file
     round-trip across envelope versions), `OwnerAuthDialogTest`
     (the exact-phrase guard), `ApprovalsViewModelTest`.

Exit criteria:
- A pending approval on the gateway surfaces on the device as a
  high-priority notification within 30 s of posting.
- The owner-auth phrase is enforced character-exact (case
  sensitive, trailing period required).
- Memory screen shows the user's recorded facts and respects the
  expiry timestamps.

Risk: MED. Touches notification UX and the approval contract.
Rollback = feature flag per screen.

---

## Wave 3 — interactive icons, app shortcuts, awareness card

Goal: the cockpit feels alive without being noisy.

PR shape: 1 PR.

1. **App shortcuts.** Three static shortcuts in `res/xml/shortcuts.xml`:
   *Dispatch job*, *Approvals*, *Voice capture* (placeholder until
   W4 — opens the W4 onboarding card if voice is not yet enabled).
2. **Per-job notification updates.** Foreground service exposes a
   coroutine that updates the notification text with the active
   mode (Operator / Companion / …) and the count of pending
   approvals. The single foreground notification stays low priority;
   per-approval notifications stay on the W2 high-priority channel.
3. **Awareness card.** A small card on the Orchestrator dashboard
   showing a digest of `AwarenessSnapshot` from the gateway —
   gateway state, last job status, memory load. Tap-through opens
   the relevant screen.
4. **Stop-running-service polish.** Replace deprecated
   `ActivityManager.getRunningServices` with a `ServiceConnection`
   probe.
5. **Optional badge.** Settings toggle, default OFF; when ON, the
   launcher icon badges when at least one approval is pending.
6. **Verification.** `./gradlew assembleDebug` + `lintDebug` green;
   eyeball shortcuts on a long-press, badge appearance with a
   manual pending-approval injection.

Exit criteria:
- Three shortcuts visible on long-press.
- Foreground notification text reflects mode + approval count.
- Awareness card renders graceful empty state when gateway is
  offline.

Risk: LOW. Cosmetic polish.

---

## Wave 4 — voice intake (Mobile Voice Mode)

Goal: opt-in voice capture that mirrors the Python intake pipeline,
with explicit driving-mode behavior.

PR shape: 2 PRs.

1. **Manifest deltas (opt-in only).**
   - `<uses-permission android:name="android.permission.RECORD_AUDIO" />`.
   - Update service type: `foregroundServiceType="dataSync|microphone"`
     so the service can flip to mic capture only while actively
     recording.
2. **Voice plumbing.**
   - `data/voice/VoiceRecorder.kt` — `AudioRecord` wrapper; cold
     `Flow<ByteArray>` of 16 kHz mono PCM frames (matches
     `docs/mobile/app-voice-service.md`).
   - `data/voice/VoicePlayer.kt` — `AudioTrack` consumer for TTS
     readback frames from `/v1/cockpit/voice/tts`.
   - `data/voice/VoicePermission.kt` — lazy `RECORD_AUDIO` request,
     never on startup.
3. **Voice intake screen.**
   - Push-to-talk button + transcript readout + "send to gateway"
     action.
   - Always-on visible *Driving mode* toggle in the top bar; when
     ON, high-risk approval notifications are suppressed and
     queued.
4. **Mode-aware persona.**
   - When the active mode is Mobile Voice or driving mode is ON,
     dispatch requests include
     `persona = Persona.MOBILE_VOICE_FORMAT`.
5. **Settings.**
   - `voice_enabled` flag in `SettingsRepository` (default OFF)
     gates the whole voice surface.
   - The first time the user turns it ON, an explainer card cites
     `docs/voice/voice-first-architecture.md` §1 (Goals) and §3
     (Voice modes).
6. **Verification.**
   - `./gradlew assembleDebug` + `lintDebug` green.
   - Add `VoicePermissionTest`, `DrivingModeApprovalSuppressionTest`,
     `VoiceRecorderFlowTest` (Robolectric-shadow AudioRecord).

Exit criteria:
- Voice intake works end-to-end behind the `voice_enabled` flag.
- Driving mode suppresses high-priority approval notifications
  while ON.
- Disabling `voice_enabled` revokes the audible UI and never
  fires the permission prompt again.

Risk: MED. Mic permission, foreground service type change. Strict
opt-in posture keeps risk bounded.

---

## Wave 5 — test suite buildout

Goal: bring the Android side up to the same standard the Python
side already enjoys (159 tests green).

PR shape: rolling — one test PR per ViewModel + one Compose UI
test PR per screen.

1. **Unit (JVM):** `PromptBuilder`, `HermesTaskRepository`,
   `SettingsRepository`, `LogBuffer`, `HandoffLauncher`
   (Robolectric), `JarvisHealthProbe`, `TermuxIntentBridge` builders
   and fire path, `OwnerAuth` exact-phrase guard.
2. **Compose UI (androidTest):** smoke test per screen
   (Splash, Orchestrator, TaskDetail, Settings, Diagnostics,
   Cockpit, JobDetail, Approvals, Memory, VoiceIntake).
3. **Integration:** end-to-end "open app → dispatch job → approve
   → see done" against a mock gateway running inside the
   instrumented test process.
4. **CI updates:** extend `.github/workflows/android-build.yml`
   with a `test` job running `./gradlew testDebugUnitTest` and an
   `instrumented` job using an Android emulator action (gated
   behind label so PRs that don't touch Android skip the heavy
   emulator step).

Exit criteria:
- `./gradlew testDebugUnitTest connectedDebugAndroidTest` green.
- Test coverage for ViewModels ≥ 80%.

Risk: LOW. Tests cannot regress runtime behavior.

---

## Blockers

| # | Blocker | Decision needed before | Recommendation |
|---|---|---|---|
| BLK-01 | Keep `com.aci.hermes` package id, or migrate? | W0 | **Keep**. User-visible label can read "Jarvis Prime" without breaking install upgrade path. |
| BLK-02 | Keep `hermes_orchestrator` notification channel id, or migrate? | W0 | **Keep**. Renaming the id orphans user-customized importance settings. |
| BLK-03 | Keep `hermes_secure_prefs.xml` exclusion in backup_rules.xml + data_extraction_rules.xml? | W1 | **Keep**. Forward compat — the file is the natural home for the gateway token when W1 lands. |
| BLK-04 | When to add `INTERNET`? | W1 | First commit of W1 — adding it earlier (e.g. in W0) without using it triggers Play Console scrutiny without benefit. |
| BLK-05 | When to add `RECORD_AUDIO`? | W4 | At the start of W4 only, behind the `voice_enabled` flag. Never declare without using. |
| BLK-06 | Gateway URL defaults — debug vs release | W1 | Debug seeds `http://10.0.2.2:8080`; release seeds `""` and requires user input on Connection screen. |
| BLK-07 | EncryptedSharedPreferences — keep removed, or re-add? | W1 | **Re-add** for the gateway bearer token only. The exclusion XML already protects it from backups. |
| BLK-08 | `HermesTask` schema evolution policy | W2 | Additive only. Bump envelope `version` field; loader reads both 1 and 2. Never drop fields. |
| BLK-09 | Mode persistence across reinstall | W2 | Persist mode in DataStore (`jarvis_mode`); on fresh install default to Operator. |
| BLK-10 | Owner authorization persistence | W2 | **Never persist**. In-memory cache only, cleared on process death. Mirrors the Python runtime. |

## Test status snapshot (as of this audit)

| Surface | Tests | Status |
|---|---|---|
| Jarvis Prime Python runtime (`hermes_cli/jarvis_prime/`) | 159 | All passing in 2.91 s |
| Android unit tests | 0 | Directory does not exist |
| Android instrumented tests | 0 | Directory does not exist |
| CI `assembleDebug` | 1 workflow | Green on main (last run on PR #89 chore/trigger-android-build) |
| CI `lintDebug` | 1 workflow | Green on main |

## Cross-references

- Audit body: [`jarvis-prime-app-deep-audit.md`](jarvis-prime-app-deep-audit.md)
- Gap map: [`jarvis-prime-app-final-gap-map.md`](jarvis-prime-app-final-gap-map.md)
- Permission register: [`jarvis-prime-app-permission-risk-register.md`](jarvis-prime-app-permission-risk-register.md)
- Python ↔ Android translation: [`jarvis-prime-app-research-translation-map.md`](jarvis-prime-app-research-translation-map.md)
