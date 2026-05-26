# Jarvis Prime — Android launch stabilization report

Branch: `claude-build/launch-android-stabilization` (off PR #131 head
`claude/hopeful-bardeen-KBVqi`).
Date: 2026-05-26.

PR #131 was a deliberate selective cherry-pick of new files from seven
feature PRs (commit `8769342` — "selective cherry-pick of new files from
7 feature PRs"). The cherry-pick skipped the centralized-config edits
(`Screen.kt`, `HermesNavGraph.kt`, `AppContainer.kt`, `strings.xml`,
`SettingsRepository.kt`) and the follow-up wiring commit never properly
landed. The Android module on PR #131 head therefore failed to compile.
This branch is that wiring commit.

## Build result

```
$ ./gradlew --no-daemon assembleDebug
BUILD SUCCESSFUL in 1m 1s
37 actionable tasks: 15 executed, 22 up-to-date
```

The debug APK is produced at
`apps/android/app/build/outputs/apk/debug/app-debug.apk`.

Two Kotlin compile warnings (both pre-existing, both in
`TaskDetailScreen.kt`):
deprecated `Icons.Filled.OpenInNew` and `Modifier.menuAnchor()`. Not
blockers, not addressed here — they belong to a follow-up that touches
the orchestrator screens.

## Unit-test result

```
$ ./gradlew --no-daemon testDebugUnitTest
BUILD SUCCESSFUL in 29s
24 actionable tasks: 5 executed, 19 up-to-date

236 tests completed, 0 failed
```

Test classes that ran (30):

```
com.aci.hermes.approval.ApprovalStoreTest
com.aci.hermes.approval.NoDirectDestructiveActionTest
com.aci.hermes.backup.BackupRulesTest
com.aci.hermes.data.audit.AuditRepositoryTest
com.aci.hermes.data.audit.SecretRedactorTest
com.aci.hermes.data.capability.CapabilityCatalogTest
com.aci.hermes.data.capability.CapabilityRepositoryTest
com.aci.hermes.data.jarvis.AutonomyModeTest
com.aci.hermes.data.jarvis.ControlWarningsTest
com.aci.hermes.data.jarvis.JarvisControlProjectorTest
com.aci.hermes.data.jarvis.JarvisHomeStateDeriverTest
com.aci.hermes.data.social.PrivacyRedactorTest
com.aci.hermes.data.social.SocialPatternRepositoryTest
com.aci.hermes.handoff.HandoffSafetyContractTest
com.aci.hermes.manifest.AppIdentityTest                ← new
com.aci.hermes.manifest.ManifestPermissionsTest        ← new
com.aci.hermes.manifest.PackageUniquenessTest          ← new
com.aci.hermes.memory.MemoryFiltersTest
com.aci.hermes.memory.MemoryRedactorTest
com.aci.hermes.memory.MemoryRepositoryTest
com.aci.hermes.memory.MemoryViewModelTest
com.aci.hermes.orchestrator.HermesTaskSerializationTest
com.aci.hermes.orchestrator.PromptBuilderTest
com.aci.hermes.termux.TermuxIntentBridgeConstantsTest
com.aci.hermes.ui.jarvis.IconStateAccessibilityTest
com.aci.hermes.ui.jarvis.IconStateMapperTest
com.aci.hermes.ui.jarvis.OrchestratorIconStateMappingTest
com.aci.hermes.ui.navigation.ScreenTest                ← updated
com.aci.hermes.ui.screens.audit.AuditFormattingTest
com.aci.hermes.ui.screens.control.JarvisControlStateTest
```

Launch-mission tests (new):

| Test | What it pins |
|---|---|
| `ManifestPermissionsTest.manifest declares exactly the allowed permission set` | `POST_NOTIFICATIONS`, `FOREGROUND_SERVICE`, `FOREGROUND_SERVICE_DATA_SYNC` — nothing else |
| `ManifestPermissionsTest.manifest never requests a forbidden permission` | `RECORD_AUDIO`, `SYSTEM_ALERT_WINDOW`, SMS / contacts / call-log / phone / camera / location / storage are NOT requested |
| `ManifestPermissionsTest.manifest preserves the com_aci_hermes application name` | `.HermesApplication` + `@string/app_name` |
| `ManifestPermissionsTest.emergency stop is reachable from the orchestrator service controller` | Compile-time pin on `OrchestratorServiceController.emergencyStop` |
| `AppIdentityTest.app_name in strings_xml is exactly Jarvis Prime` | User-facing label |
| `AppIdentityTest.application id is com_aci_hermes and appears exactly once` | Package preserved + uniqueness |
| `AppIdentityTest.namespace is com_aci_hermes` | Module namespace preserved |
| `PackageUniquenessTest.every kotlin source file declares a com_aci_hermes package` | No second app package leaked in |
| `ScreenTest.emergency_stop_path_exists_via_orchestrator_service_controller` | Nav-side compile-time pin on emergency stop |

## Lint result

```
$ ./gradlew --no-daemon lintDebug
BUILD SUCCESSFUL in 1m 7s
28 actionable tasks: 9 executed, 1 from cache, 18 up-to-date

0 errors, 92 warnings
```

HTML report: `apps/android/app/build/reports/lint-results-debug.html`.

Warning breakdown by category:

| Count | Category | Notes |
|---|---|---|
| 51 | `UnusedResources` | Strings + colors that aren't referenced yet by the cherry-picked screens. Expected; these unblock future PRs. |
| 30 | `GradleDependency` | Newer versions of androidx libs available. Out of scope. |
| 3 | `AndroidGradlePluginVersion` | AGP 8.7.3 → 9.2.1 available. Out of scope. |
| 2 | `SdCardPath` | `/data/data/com.termux/...` — intentional Termux bridge paths. |
| 2 | `ObsoleteSdkInt` | `SDK_INT < O` checks on `minSdk=26` — defensive, harmless. |
| 1 | `PluralsCandidate` | Cosmetic. |
| 1 | `ModifierParameter` | Cosmetic. |
| 1 | `ConstantLocale` | `SimpleDateFormat` with `Locale.getDefault()` at class load. |
| 1 | `AuthLeak` | False positive — mock seed data inside `AuditRepository.kt` (fake `postgres://…` example string). |

No errors. No new warnings introduced by this branch.

## Permission audit

Manifest declares:

```xml
<uses-permission android:name="android.permission.POST_NOTIFICATIONS" />
<uses-permission android:name="android.permission.FOREGROUND_SERVICE" />
<uses-permission android:name="android.permission.FOREGROUND_SERVICE_DATA_SYNC" />
```

Forbidden — confirmed absent (pinned by
`ManifestPermissionsTest.manifest never requests a forbidden permission`):

`RECORD_AUDIO`, `SYSTEM_ALERT_WINDOW`, `READ_SMS`, `SEND_SMS`,
`RECEIVE_SMS`, `READ_CONTACTS`, `WRITE_CONTACTS`, `READ_CALL_LOG`,
`WRITE_CALL_LOG`, `PROCESS_OUTGOING_CALLS`, `READ_PHONE_STATE`, `CAMERA`,
`ACCESS_FINE_LOCATION`, `ACCESS_COARSE_LOCATION`,
`ACCESS_BACKGROUND_LOCATION`, `READ_EXTERNAL_STORAGE`,
`WRITE_EXTERNAL_STORAGE`, `MANAGE_EXTERNAL_STORAGE`.

Package: `com.aci.hermes` (preserved).
User-facing label: "Jarvis Prime" (from `strings.xml` `app_name`).

## Files changed

| # | File | Why |
|---|---|---|
| 1 | `app/src/main/java/com/aci/hermes/data/model/audit/AuditRecord.kt` | NEW — defines the `com.aci.hermes.data.model.audit` package (`AuditRecord`, `ProofRecord`, `EvidenceItem`, `RouteSummary`, `VerificationResult`, `ApprovalHistoryItem`, `RollbackPlan`, `WorkerRun` data classes + `ActionResult`, `ApprovalState`, `EvidenceKind`, `RiskTier`, `RouteDestination`, `VerificationStatus` enums). The cherry-picked `AuditRepository.kt` / audit screens / audit tests all imported from this package but the package was missing. |
| 2 | `app/src/main/java/com/aci/hermes/data/preferences/SettingsRepository.kt` | Added the Control / Home dashboard preferences (`autonomyMode`, `responseLength`, `mobileMode`, `notificationsEnabled`, `voiceEnabled`, `interactiveIconEnabled`, `gatewayEndpoint`, `mockMode`, `termuxGatewayMode`, `approvalsRequired`, `safetyGatesEnabled`, `privacyLocalOnlyMemory`, `emergencyStopEngaged`) — Flow getters, suspend setters, `Snapshot` data-class fields, and `DEFAULT_GATEWAY_ENDPOINT = "http://127.0.0.1:8765"` constant. Exposes `emergencyStopActive` / `setEmergencyStopActive` as Home-screen-friendly aliases over the same key. |
| 3 | `app/src/main/res/values/strings.xml` | Added `audit_*` (21 strings), `capability_*` (14 strings), `action_back`, `action_close`. All other strings unchanged. `app_name` still "Jarvis Prime". |
| 4 | `app/src/test/java/com/aci/hermes/manifest/ManifestPermissionsTest.kt` | NEW — pins the manifest permission allow-list, the forbidden-permission deny-list, the application name, and the emergency-stop service controller path. |
| 5 | `app/src/test/java/com/aci/hermes/manifest/AppIdentityTest.kt` | NEW — pins user-facing app name ("Jarvis Prime") and technical identifiers (`applicationId = "com.aci.hermes"`, `namespace = "com.aci.hermes"`, single occurrence). |
| 6 | `app/src/test/java/com/aci/hermes/manifest/PackageUniquenessTest.kt` | NEW — walks the module tree and asserts no second app package was introduced (every Kotlin/Java file declares a `com.aci.hermes.**` package). |
| 7 | `app/src/test/java/com/aci/hermes/ui/navigation/ScreenTest.kt` | Updated `all_main_destinations_are_shell_routes` to include `Capability` (the nav graph wraps it in `ShellHost`, so it IS a shell route — the prior expectation set was stale). Added `emergency_stop_path_exists_via_orchestrator_service_controller`. |
| 8 | `gradle/libs.versions.toml` | Added `kotlinx-coroutines-test` library entry (re-uses the existing `kotlinxCoroutines = 1.9.0` version). |
| 9 | `app/build.gradle.kts` | Added `testImplementation(libs.kotlinx.coroutines.test)`. Added `testOptions { unitTests.isReturnDefaultValues = true }` so unit tests don't crash on `android.util.Log` calls (standard JVM unit-test configuration). |
| 10 | _deleted_ `app/src/main/java/com/aci/hermes/ui/screens/memory/SocialPatternDetail.kt` | Orphaned by the cherry-pick — not referenced by `MemoryScreen`, the nav graph, any test, or anywhere else. Called `viewModel.selectPattern(...)`, `viewModel.detailState`, `viewModel.correct(...)`, `viewModel.delete(...)` which never existed on `MemoryViewModel`, and used a large block of `memory_section_*` / `memory_field_*` / `memory_high_risk_*` / `memory_provenance_*` strings that no live screen needs. The underlying `SocialPattern` model, `SocialPatternRepository`, `PrivacyRedactor`, and `SocialPatternCard` all remain; the orphaned detail screen alone was removed. |
| 11 | `apps/android/docs/ANDROID_LAUNCH_STABILIZATION_REPORT.md` | NEW — this file. |

## Remaining launch risks

1. **Approval gateway sink is in-memory.** `RecordingApprovalEventSink` is
   used in `AppContainer.kt`; production approvals never reach a real
   gateway today. Replacing this is a follow-up — comments in
   `AppContainer.kt` already flag the swap-in point.

2. **Emergency-stop scaffolding is orphaned.**
   `EmergencyStopController`, `EmergencyStopRepository`,
   `EmergencyStopState`, and `EmergencyStopAuditEvent` were
   cherry-picked but never wired into `AppContainer` or any ViewModel.
   The live emergency-stop path the operator actually uses is
   `OrchestratorServiceController.emergencyStop()` (called from the
   shell + Control screen + `ControlViewModel.commitEmergencyStop` —
   the latter also flips `SettingsRepository.setEmergencyStopEngaged`).
   That path is functional and pinned by the new tests; the orphaned
   controller can land or be removed in a follow-up.

3. **Chat tab is a placeholder.** `Screen.Chat` exists, is on the
   bottom nav, and renders `PlaceholderScreen` with "coming soon" copy.
   That ships as-is for launch — preserved per `ScreenTest.requiredScreens`.
   No live chat surface.

4. **Capability is a shell route but not a bottom-nav tab — by design.**
   Capability is reached via Home quick-links and Settings. The
   updated `all_main_destinations_are_shell_routes` test reflects this.

5. **Pre-existing Kotlin deprecation warnings** in
   `TaskDetailScreen.kt` (`Icons.Filled.OpenInNew`, `Modifier.menuAnchor()`)
   — not fixed here. Cosmetic; doesn't block release.

6. **Mock seed data triggers a false-positive `AuthLeak` lint warning**
   in `AuditRepository.kt` line 414. The value is illustrative mock
   content for the audit screen, not a real credential. Suppress or
   relocate to a test fixture in a follow-up if launch surface still
   shows it.

7. **Default gateway endpoint** is now
   `http://127.0.0.1:8765` (Termux loopback). If the operator hasn't
   started the Termux gateway, the Control screen will render
   `GatewayState.DISCONNECTED` rather than `UNCONFIGURED`. That's the
   intended honest state — see the `JarvisControlProjectorTest`
   "gateway disconnected is visible when service unreachable" case.

## Verification commands (reproducible)

From the repository root, after checking out
`claude-build/launch-android-stabilization`:

```bash
cd apps/android
./gradlew --no-daemon assembleDebug
./gradlew --no-daemon testDebugUnitTest
./gradlew --no-daemon lintDebug
```

All three exit with `BUILD SUCCESSFUL`.
