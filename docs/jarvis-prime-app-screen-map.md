# MUSE — Android App Screen Map

> **Status:** product spec, v1. Companion to
> [`jarvis-prime-app-product-spec.md`](jarvis-prime-app-product-spec.md),
> [`jarvis-prime-app-user-flows.md`](jarvis-prime-app-user-flows.md),
> [`jarvis-prime-app-onboarding-spec.md`](jarvis-prime-app-onboarding-spec.md),
> [`jarvis-prime-app-launch-standard.md`](jarvis-prime-app-launch-standard.md).
>
> Navigation graph, route table, deep-link surface, screen-to-existing-file
> mapping, component inventory per screen, and the global UI elements that
> appear on every screen.

---

## 1. Navigation model

MUSE uses a **single-activity, single-NavHost** architecture
on top of the existing `MainActivity` + `HermesNavGraph`. The nav
host renders inside a `Scaffold` that hosts the **global app shell**
(top bar, persistent banners, the interactive icon's floating
position when not on Home).

The navigation graph is intentionally flat. Every primary screen is
reachable from the **MUSE Home** screen in one tap, and every
primary screen has a path back to Home through the system back
gesture.

```
                     ┌──────────────────────────┐
                     │      Onboarding          │  (first launch only)
                     │  (5-step pager)          │
                     └────────────┬─────────────┘
                                  ▼
   ┌─────────────────────────────────────────────────────────────┐
   │                       MUSE Home                           │
   │  status header · interactive icon · 3 tiles · quick actions │
   └──┬────────┬─────────┬─────────┬─────────┬─────────┬─────────┘
      │        │         │         │         │         │
      ▼        ▼         ▼         ▼         ▼         ▼
   ┌──────┐ ┌──────┐ ┌────────┐ ┌──────┐ ┌──────┐ ┌────────┐
   │ Chat │ │Tasks │ │Approve │ │Memory│ │Audit │ │Control │
   └──┬───┘ └──┬───┘ └───┬────┘ └──┬───┘ └──┬───┘ └───┬────┘
      │        ▼         ▼         │        │         │
      │     Task         Approval  │        │         │
      │     detail       detail    │        │         │
      │      │            │        │        │         │
      ▼      ▼            ▼        ▼        ▼         ▼
   ┌─────────────────────────────────────────────────────────┐
   │                Settings  ·  Diagnostics                 │
   └─────────────────────────────────────────────────────────┘
```

The **interactive icon** appears on every non-Onboarding screen
(centered + large on Home; bottom-right floating elsewhere) and
exposes the global gestures — see §6.

---

## 2. Route table

Routes live in `ui/navigation/Screen.kt` (the existing sealed class
is extended in-place — no parallel module).

| # | Screen | Route | Composable | ViewModel |
|---|---|---|---|---|
| 1 | Onboarding | `onboarding` | `OnboardingPagerScreen` | `OnboardingViewModel` |
| 2 | MUSE Home | `home` | `JarvisHomeScreen` | `JarvisHomeViewModel` |
| 3 | Chat | `chat` | `JarvisChatScreen` | `JarvisChatViewModel` |
| 3a | Chat thread | `chat/{threadId}` | `JarvisChatScreen` | shared |
| 4 | Tasks | `tasks` | `TasksScreen` | `TasksViewModel` |
| 4a | Task detail | `tasks/{taskId}` | `TaskDetailScreen` | `TaskDetailViewModel` |
| 4b | Task drafts | `tasks/drafts` | `TaskDraftsScreen` | `TaskDraftsViewModel` |
| 5 | Approvals | `approvals` | `ApprovalsScreen` | `ApprovalsViewModel` |
| 5a | Approval detail | `approvals/{approvalId}` | `ApprovalDetailScreen` | `ApprovalDetailViewModel` |
| 6 | Memory | `memory` | `MemoryScreen` | `MemoryViewModel` |
| 6a | Memory detail / edit | `memory/{factId}` | `MemoryDetailScreen` | `MemoryDetailViewModel` |
| 7 | Audit / Proof | `audit` | `AuditScreen` | `AuditViewModel` |
| 7a | Audit entry detail | `audit/{entryId}` | `AuditDetailScreen` | `AuditDetailViewModel` |
| 8 | Control | `control` | `ControlScreen` | `ControlViewModel` |
| 9 | Settings | `settings` | `SettingsScreen` | `SettingsViewModel` |
| 9a | Settings section (deep) | `settings/{section}` | `SettingsScreen` (scrolled-to) | shared |
| 10 | Diagnostics | `diagnostics` | `DiagnosticsScreen` | `DiagnosticsViewModel` |
| — | Voice capture (modal) | `voice` | `VoiceCaptureScreen` | `VoiceCaptureViewModel` |
| — | Emergency stop confirm (sheet) | (sheet, not a route) | `EmergencyStopSheet` | hoisted state |
| — | Resume confirm (sheet) | (sheet, not a route) | `ResumeSheet` | hoisted state |
| — | Task draft (sheet) | (sheet, not a route) | `TaskDraftSheet` | hoisted state |

Voice capture is a **route** (full-screen) so the foreground service
notification stays consistent and the device's gesture region can
be reserved. Emergency stop, resume, and task draft are **bottom
sheets** so they can rise from any screen without losing context.

---

## 3. Deep links

Deep links arrive from notifications, the lock-screen widget, and
URL handlers. All deep links resolve through the single NavHost and
respect emergency-stop state (links to write-paths show the stopped
banner and disable confirm buttons).

| Source | Deep link | Resolves to |
|---|---|---|
| Notification: *approval pending* | `jarvis://approvals/{approvalId}` | Approval detail |
| Notification: *validation failed* | `jarvis://tasks/{taskId}` | Task detail filtered to validation |
| Notification: *emergency stop engaged* | `jarvis://control` | Control |
| Notification: *gateway lost* | `jarvis://diagnostics` | Diagnostics |
| Notification: *daily summary* | `jarvis://audit?range=1d` | Audit (last 24h) |
| Widget tap: Ready | `jarvis://chat` | Chat |
| Widget tap: Listening | `jarvis://voice` | Voice Capture |
| Widget tap: Thinking | `jarvis://tasks` | Tasks |
| Widget tap: Waiting on you | `jarvis://approvals` | Approvals |
| Widget tap: Paused | `jarvis://diagnostics` | Diagnostics |
| Widget tap: Stopped | `jarvis://control` | Control |
| Voice phrase: *"MUSE, stop everything"* | (sheet) | Emergency stop confirm |
| Voice phrase: *"MUSE, resume"* | (sheet over `control`) | Resume confirm |

The `jarvis://` scheme is declared in `AndroidManifest.xml`
alongside the existing intent filter. Deep-link resolution never
performs a write — it always lands on a screen where the owner
can choose to act.

---

## 4. Mapping to existing files

The transformation reuses every existing screen file under
`apps/android/app/src/main/java/com/aci/hermes/ui/screens/`. New
files are created only where no equivalent exists.

| MUSE screen | Existing file (reused / renamed) | New file (if any) |
|---|---|---|
| Onboarding | (none — current Hermes flow is splash → setup → provider) | `ui/screens/onboarding/OnboardingPagerScreen.kt` + `OnboardingViewModel.kt` |
| MUSE Home | (none — current Hermes module has no home screen) | `ui/screens/home/JarvisHomeScreen.kt` + `JarvisHomeViewModel.kt` |
| Chat | existing `ui/screens/chat/ChatScreen.kt` (per `app-screens.md`) | (reused; rename Composable to `JarvisChatScreen` in-place; legacy class kept as deprecated alias) |
| Tasks | existing `ui/screens/orchestrator/OrchestratorScreen.kt` + `OrchestratorViewModel.kt` | (folded — `OrchestratorScreen` becomes `TasksScreen`; the orchestrator role is the source of tasks) |
| Task detail | existing `ui/screens/orchestrator/TaskDetailScreen.kt` + `TaskDetailViewModel.kt` | (reused; ViewModel unchanged structurally) |
| Approvals | (currently surfaced only inside task detail) | `ui/screens/approvals/ApprovalsScreen.kt` + `ApprovalsViewModel.kt`, `ApprovalDetailScreen.kt` + `ApprovalDetailViewModel.kt`, `ImpactReportSection.kt`, `ApprovalConfirmSheet.kt` |
| Memory | (none) | `ui/screens/memory/MemoryScreen.kt` + `MemoryViewModel.kt`, `MemoryDetailScreen.kt`, `PendingInferencesTile.kt` |
| Audit / Proof | (none — `LogBuffer` is the closest analog and stays for Diagnostics) | `ui/screens/audit/AuditScreen.kt` + `AuditViewModel.kt`, `AuditDetailScreen.kt`, `LedgerTimeline.kt` |
| Control | (none — `HermesService` start/stop is internal today) | `ui/screens/control/ControlScreen.kt` + `ControlViewModel.kt`, `EmergencyStopSheet.kt`, `ResumeSheet.kt`, `GatewayLifecycleCard.kt` |
| Settings | existing `ui/screens/settings/SettingsScreen.kt` + `SettingsViewModel.kt` | (extended; section list per product spec §4.9) |
| Diagnostics | existing `ui/screens/diagnostics/DiagnosticsScreen.kt` + `DiagnosticsViewModel.kt` | (reused; adds *Export diagnostics bundle*) |
| Voice capture | (none — voice is future work per current Hermes module) | `ui/screens/voice/VoiceCaptureScreen.kt` + `VoiceCaptureViewModel.kt`, bound to `service/VoiceCaptureService.kt` |
| Splash | existing `ui/screens/splash/SplashScreen.kt` | (kept as the bootstrap surface that routes to Onboarding or Home) |

Supporting infrastructure (reused, names unchanged for compatibility):

- `HermesApplication`, `MainActivity`, `HermesNavGraph` — host the
  new graph.
- `HermesService` — runs the foreground service; user-facing
  notification title is "MUSE — listening".
- `HermesGatewayClient` / `HermesClientFactory` — wire format
  unchanged; extended to consume task / approval / memory / audit
  / control SSE streams.
- `SettingsRepository` (DataStore + EncryptedSharedPreferences) —
  storage shape unchanged; new keys added.
- `LogBuffer` — feeds Diagnostics screen and audit export.
- `TermuxIntentBridge` / `HandoffLauncher` — Termux gateway
  lifecycle in Control.
- `PromptBuilder` — server-side safety block reflected as the
  *"Safety block applied"* footer in Chat / Task draft.
- `HermesTaskRepository` — backs Tasks and Task detail.

No file under `apps/android/app/src/main/java/com/aci/hermes/` is
deleted in the spec — the rename map above is implementation
guidance for the build phase.

---

## 5. Global app shell (every non-Onboarding screen)

The shell is hoisted in `MainActivity` so every screen inherits it.

### 5.1 Top bar

- **Left.** Screen title (plain English: *"MUSE Home"*, *"Chat"*,
  *"Tasks"*, etc.).
- **Center.** **Status pill** — current `ConnectionState` rendered
  as Connected · Connecting · Degraded · Offline · Mock ·
  Emergency-stopped. The pill is the same component across all
  screens.
- **Right (cluster).**
  - **Outbox badge** — visible only when ≥ 1 pending write is
    queued. Count.
  - **Mode chip** — current MUSE mode (Auto / Companion /
    Strategy / Critic / Operator / Builder / Mobile Voice). Tap to
    override.
  - **Overflow menu** — *Open in Diagnostics*, *Settings*, *About*,
    *Help*.

### 5.2 Persistent banners

Stack at the top of the content area, below the top bar. Mutually
exclusive — at most one is visible per priority order below:

1. **Emergency stop banner** — red, *"MUSE is stopped. Tap to
   resume."* Tap → Control.
2. **Mock mode banner** — purple, *"Mock mode is on — MUSE is
   not connected to a real gateway."*
3. **Offline banner** — amber, *"Offline — showing cached state
   from HH:MM. Writes queued in outbox."*
4. **Degraded banner** — yellow, *"Live updates paused —
   reconnecting."*
5. **Permission-missing banner** (contextual) — *"<feature> needs
   <permission>. Tap to fix."* — only on screens that depend on
   the missing permission.

### 5.3 Interactive icon

- On **Home** the icon is large and centered (see §6).
- On every other screen the icon floats bottom-right with a 16 dp
  safe margin from the edge and from the system gesture region.
- The icon never overlaps a screen's primary action button — if a
  collision is detected at layout time, the icon shifts to bottom-
  left for that screen.

### 5.4 Bottom navigation (none)

There is intentionally **no bottom nav bar**. The interactive icon's
five gestures + the Home tile actions are the navigation surface.
This keeps the bottom area free for the primary action of each
screen (Send, Dispatch, Approve, etc.).

---

## 6. The interactive icon — placement and gesture map per screen

The icon's six states, five gestures, and lock-screen widget
mapping are defined in
[`jarvis-prime-app-product-spec.md`](jarvis-prime-app-product-spec.md)
§5. The placement varies per screen:

| Screen | Icon placement | Notes |
|---|---|---|
| Onboarding | Hidden | Onboarding has its own brand mark on the welcome step. |
| MUSE Home | Centered, large (96 dp) | The hero element. |
| Chat | Bottom-right floating (56 dp) | Stays out of composer / Send button. |
| Tasks | Bottom-right floating (56 dp) | Stays out of New task FAB; if collision, FAB extends to a labelled chip and the icon stays. |
| Approvals | Bottom-right floating (56 dp) | Stays well above the bottom action bar. |
| Approval detail | Bottom-left floating (56 dp) | Shifted left to keep the *Reject* button reachable. |
| Memory | Bottom-right floating (56 dp) | Stays out of the *Add memory* FAB. |
| Audit / Proof | Bottom-right floating (56 dp) | — |
| Control | Bottom-right floating (56 dp) | Stays out of Emergency stop tile. |
| Settings | Bottom-right floating (56 dp) | — |
| Diagnostics | Bottom-right floating (56 dp) | — |
| Voice capture | Hidden | The 200 dp mic button is the voice surface; the global icon would be redundant. |

Gestures are identical on every screen where the icon is visible.

---

## 7. Component inventory per screen

This section enumerates the named components each screen uses, so
the implementation has a stable contract and code review can check
"every screen uses every required component."

### 7.1 Onboarding

- `OnboardingPager` (5 pages)
- `WelcomeCard`
- `ConnectionCard` (URL + token + *Test connection*)
- `ConnectionStatePill` (same component used in the shell)
- `ModeChooser` (Live · Termux · Mock)
- `PermissionsList` (mic · notifications · foreground · BT · widget)
- `PermissionRationaleSheet`
- `SkipForNowButton`
- `OnboardingCompleteCard`

### 7.2 MUSE Home

- `StatusHeader` (pill + gateway label + provider/model)
- `InteractiveIconLarge`
- `ActiveTasksTile` (max 3 rows)
- `ApprovalsTile`
- `LastConsequentialActionTile`
- `QuickActionsRow` (Chat · Voice · Memory · Audit · Control · Diagnostics)
- `CachedStateBanner` (when offline)

### 7.3 Chat

- `ChatHeader` (mode chip · thread title · *New chat*)
- `MessageList`
  - `UserBubble`
  - `JarvisBubble` (streaming, with agent attribution chips)
  - `StreamErrorInline`
  - `RiskyActionProposedCard` (deep-links to Approvals)
  - `ConvertToTaskChip`
- `Composer`
  - `TextInput`
  - `MicButton` (push-to-talk on long-press; open Voice on tap)
  - `SendButton`
  - `AbortButton` (visible during stream)
- `OutboxQueuedBanner` (when offline)

### 7.4 Tasks

- `FilterChipRow` (all · running · waiting · done · failed · cancelled)
- `LiveUpdatesPill` (green · amber when SSE drops)
- `TaskRow`
  - `TaskTitle`
  - `WorkerChip`
  - `StatusBadge`
  - `RelativeTime`
- `SwipeActions` (right: shortcut to Approvals; left: cancel confirm)
- `NewTaskFab`
- `TaskDraftSheet` (modal)
- `TaskDetailScreen` sub-components:
  - `PlanSummary`
  - `FilesAffectedList`
  - `ValidationGateStatus` (per-gate ✅ / ❌ / ⏳ / ⚠️)
  - `DecisionLedgerSummary`
  - `OpenInApprovalsButton`

### 7.5 Approvals

- `PendingApprovalsList`
  - `ApprovalCard`
    - `ClassificationBadge` (Risky / Serious / Critical)
    - `PlainEnglishAction`
    - `FilesEndpointsAffected`
    - `RequestedByChip`
    - `TimePendingChip`
    - `ReviewButton`
- `ApprovalDetailScreen` sub-components:
  - `ClassificationBadge`
  - `ImpactReportSection` (critical only — 5 mandatory subsections)
  - `EvidenceCard` (serious + critical)
  - `UnifiedDiffViewer`
  - `ValidationGateStatus`
  - `ApprovalActionBar` (Approve · Reject · Approve with note overflow)
  - `ApprovalConfirmSheet` (two-step phrases)
  - `RejectConfirmSheet` (optional *Why?* field)
- `ApprovalsBlockedBanner` (when emergency stop or offline)

### 7.6 Memory

- `MemorySearchBar`
- `MemoryFilterChips` (Preference · Decision · Mission · Lesson · Skill hint · Environment fact)
- `MemoryRow`
  - `MemoryTitle`
  - `CategoryChip`
  - `LastConfirmedDate`
  - `SourceChip`
  - `CorrectButton`
  - `DeleteButton`
  - `WhyButton`
- `MemoryDetailScreen` sub-components:
  - `InlineEditField`
  - `CategoryDropdown`
  - `OriginatingEventCard`
- `PendingInferencesTile`
  - `InferenceCandidate`
  - `ConfirmButton`
  - `RejectButton`
- `AddMemoryFab`
- `BulkSelectModeBar` (long-press to enter)
- `SecretShapedRejectionInline`

### 7.7 Audit / Proof

- `LedgerTimeline`
  - `DaySeparator`
  - `LedgerEntry`
    - `Timestamp`
    - `ActorChip` (MUSE · AOS · worker · gateway · hook · owner)
    - `ActionSummary`
    - `ClassificationChip` (info · decision · approval · publish · deploy · memory · stop)
    - `ShowDetailsAffordance`
- `AuditFilterChips`
- `DateRangePicker`
- `AuditDetailScreen` sub-components:
  - `FullStructuredEntry`
  - `OriginatingTaskLink`
  - `OriginatingApprovalLink`
  - `MemoryFactsReferencedList`
  - `OwnerAnnotateButton` (adds new linked entry)
- `ExportFilteredRangeButton`
- `CachedAuditBanner`

### 7.8 Control

- `EmergencyStopTile` (top, large, red)
- `EmergencyStopSheet` (modal)
- `ResumeTile` (visible when stopped)
- `ResumeSheet` (modal, includes self-check view)
- `ModeOverrideChips` (Auto · Companion · Strategy · Critic · Operator · Builder · Mobile Voice)
- `VoiceModeChips` (Off · Push-to-talk · Continuous · Driving)
- `MockModeToggle` (with switch-to-live confirm)
- `GatewayLifecycleCard` (Termux-only)
  - `StartTermuxGatewayButton`
  - `StopTermuxGatewayButton`
  - `TermuxLogAffordance`
- `GatewayStateSummary`

### 7.9 Settings

- `SettingsSearchBar`
- `CollapsibleSection` (one per group below)
  - **Connection** — `UrlField`, `TokenField (write-only)`, `TestConnectionButton`, `MockModeShortcut`
  - **Provider & model** — `ProviderChipRow`, `ApiKeyField (write-only)`, `DefaultProviderSelector`
  - **Backend secrets (read-only)** — `SecretRow` (glyph + id + last-rotated)
  - **Voice** — `SttEngineSelector`, `TtsConfirmToggle`, `PushToTalkMapping`, `WakeWordToggle`, `DrivingAutoEnterToggle`
  - **Notifications** — `NotificationClassToggle` × N (with disabled "routine progress")
  - **Memory** — `VerbositySelector`, `StaleThresholdField`, `ExportMemoryButton`, `ClearMemoryButton`
  - **Audit** — `DefaultRangeSelector`, `ExportAuditButton`, `PinWidgetAuditModeToggle`
  - **Lock-screen widget** — `PinWidgetToggle`, `LayoutChooser`
  - **Theme** — `ThemeSelector` (System · Light · Dark · High contrast)
  - **Behavior** — `AutoSubscribeToggle`, `AlwaysShowDetailsToggle`, `PlainEnglishWhyToggle`, `ConfirmBeforeModeSwitchToggle`
  - **About** — `BuildInfoCard`, `GatewayVersionCard`, `CleartextAllowedBadge`, `DocsLinkList`
  - **Reset** — `ClearSecretsButton`, `ClearSettingsButton`, `ClearEverythingButton` (typed-RESET gate)

### 7.10 Diagnostics

- `ConnectionCard` (live `ConnectionState`, latency, last probe outcome, health echo)
- `BuildCard` (version, build type, fingerprint, base URL, cleartext flag, Termux detected)
- `ModeCard` (mock, voice, driving, MUSE mode override)
- `LogBufferList` (filter by level + source; chronological)
- `LastErrorsList` (top 5 with Copy buttons)
- `ExportDiagnosticsBundleButton` (scrubbed)

### 7.11 Voice capture

- `LargeMicButton` (200 dp)
- `PhaseLabel`
- `LivePartialTranscript` (32 sp)
- `BottomActionBar` (Confirm & dispatch · Cancel)
- `MicHotIndicator` (always visible while listening)
- `CloudSttBanner` (only visible when cloud STT in use)
- `STTFailedInline`

---

## 8. Cross-screen invariants (asserted in code)

These are bugs the moment they happen — encode them as assertions
in the implementation:

1. **Status pill source.** Every screen reads the status pill from
   the same `ConnectionState` flow. No screen re-probes
   `/v1/health` on its own.
2. **Outbox badge source.** Every screen reads the outbox badge
   from `OfflineQueue.flow`. A single top-bar badge component
   subscribes once.
3. **Approval write path.** No screen issues an approval write
   except via `ApprovalsRepository.approve(...)` /
   `.reject(...)`, which inject `Idempotency-Key` and respect
   emergency-stop state.
4. **Memory write path.** No screen writes memory except via
   `MemoryRepository`, which classifies secret-shaped content and
   surfaces rejections.
5. **Audit reads only.** No screen writes to the audit ledger; the
   only writes come from `ApprovalsRepository`, `MemoryRepository`,
   `ControlRepository`, and `GatewayClient` itself.
6. **Emergency stop is global.** When `ControlRepository.state ==
   Stopped`, every screen's approve / reject / memory-write /
   send-queued action is disabled at the binding layer, not just
   visually.
7. **Voice goes through service.** No screen calls
   `SpeechRecognizer` directly. Voice flows go through
   `VoiceCaptureService` so the foreground notification stays
   consistent.
8. **No silent error.** Every `Result.Failure` from a repository
   surfaces in the UI — banner, snackbar, or inline note. No
   empty placeholder.
9. **No silent mode swap.** The mode (Live · Termux · Mock) is
   never changed except by an owner-initiated action with a
   visible banner / confirm.
10. **Single nav host.** Every navigation goes through
    `HermesNavGraph`. Deep links never bypass it.

---

## 9. Cross-references

- [`jarvis-prime-app-product-spec.md`](jarvis-prime-app-product-spec.md)
  — the product promise, the ten-screen spec, the icon, the
  approval system, and the trust anchors.
- [`jarvis-prime-app-user-flows.md`](jarvis-prime-app-user-flows.md)
  — the twenty primary flows that traverse the routes above.
- [`jarvis-prime-app-onboarding-spec.md`](jarvis-prime-app-onboarding-spec.md)
  — the Onboarding route's per-step spec.
- [`jarvis-prime-app-launch-standard.md`](jarvis-prime-app-launch-standard.md)
  — the launch readiness checklist.
- [`apps/android/docs/ARCHITECTURE.md`](../apps/android/docs/ARCHITECTURE.md)
  — the Android module architecture (unchanged structurally).
- [`apps/android/README.md`](../apps/android/README.md)
  — the technical compatibility README (legacy Hermes name).
