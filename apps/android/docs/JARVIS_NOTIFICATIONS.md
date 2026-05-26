# Jarvis Prime Notifications Command Center

This module is the platform-agnostic core for the Jarvis Prime Android notification
surface. It owns the rules for **what** to notify about, **when** to notify, **how
to ask for permission**, **where each notification routes**, and **how an
emergency stop is invoked safely from a notification action**.

The Android UI layer (Activity / Composable / Service / BroadcastReceiver) is a
thin binding that implements the four platform interfaces in
`com.jarvisprime.notifications.platform`:

| Interface | Android binding |
|-----------|-----------------|
| `PermissionGate` | `ActivityResultContracts.RequestPermission(POST_NOTIFICATIONS)` + `NotificationManagerCompat.areNotificationsEnabled()` |
| `Navigator` | `NavController.navigate` + deep-link `Intent` for cold start |
| `NotificationPresenter` | `NotificationManagerCompat.notify` / `cancel` + `NotificationCompat.Builder` |
| `EmergencyStopController` | Signed local broadcast → gateway cancel call → `WorkManager` cancel |

Keeping the core JVM-only means every safety rule is unit-tested on the JVM
without spinning up an emulator.

## Components

### `NotificationPermissionEducation`
State machine that enforces the "education before request" contract:

- First launch never triggers the OS prompt.
- Education must be shown first.
- The user must explicitly accept inside the education screen for the OS prompt
  to fire.
- If the user dismisses, the app keeps working — `hasUserOptedOut()` is true,
  no re-prompt, ever.
- If the OS denies, a denial timestamp is recorded and the next step becomes
  `OFFER_SETTINGS_DEEP_LINK` (the UI offers a one-tap deep link to system
  settings; it does not auto-prompt).

### `NotificationSettings` + `NotificationSettingsStore`
User-controlled toggles. One master switch plus a per-type switch for each of
the eight notification types. The store is an interface so the UI binding can
plug into `DataStore`; tests use `InMemoryNotificationSettingsStore`.

`EMERGENCY_STOP_ACTIVE` cannot be disabled. The data class refuses the mutation
and `isAllowed(EMERGENCY_STOP_ACTIVE)` always returns true. This is the only
hard-coded safety carve-out.

### `NotificationEventMapper`
Single source of truth for type → (channel, priority, target screen, inline
actions). Both the dispatcher (which posts notifications) and the action router
(which handles taps) read from the same mapper, so the screen a notification
opens cannot drift from the screen its action button opens.

| Type | Channel | Priority | Target | Actions |
|------|---------|----------|--------|---------|
| `APPROVAL_NEEDED` | approvals | HIGH | Approvals | Open Approval, Dismiss |
| `SERIOUS_ACTION_PENDING` | approvals | HIGH | Approvals | Open Approval, Open Audit, Dismiss |
| `CRITICAL_ACTION_PENDING` | approvals | MAX | Approvals | Open Approval, Open Audit, **Emergency Stop** |
| `TASK_COMPLETE` | tasks | DEFAULT | Tasks | Open Task, Dismiss |
| `WORKER_FAILED` | system | HIGH | Tasks | Open Task, Open Audit, Dismiss |
| `GATEWAY_DISCONNECTED` | system | HIGH | Gateway Status | Open Audit, Dismiss |
| `EMERGENCY_STOP_ACTIVE` | emergency | MAX | Emergency Stop | Open Audit, Dismiss |
| `MEMORY_CORRECTED` | memory | LOW | Memory Log | Open Audit, Dismiss |

### `NotificationActionRouter`
Resolves a tap on an action. Safety rule: **emergency stop is the only action
that mutates worker state from a notification.** Tapping `EMERGENCY_STOP`
navigates the user to the Emergency Stop screen and returns
`RouteResult.NeedsConfirmation`. The actual `EmergencyStopController.trigger`
call only fires after `confirmEmergencyStop(event, reason)` is invoked from the
explicit-confirmation UI. There is no path from a single notification tap to a
triggered emergency stop. (`TestOnlyImmediate` exists for tests only.)

### `NotificationSpamGuard`
Time-windowed deduplication keyed on `(type, dedupeKey)`. Default window is
30 s; the dispatcher integrates it. Workers that emit progressive updates set
`payload["dedupeKey"]` to a stable id (e.g. the task id) so the user sees one
notification, not five. `EMERGENCY_STOP_ACTIVE` bypasses the guard.

### `NotificationDispatcher`
Top-level orchestrator. Order of checks for each incoming event:

1. `NotificationSettings.isAllowed(type)` — respects master + per-type toggles
   (except for the safety carve-out).
2. `NotificationSpamGuard.allow(event)` — drops in-window duplicates.
3. `PermissionGate.currentState()` — if not granted, returns
   `DispatchResult.InAppFallback`. The Android binding listens for the
   fallback and shows a top-of-screen banner inside the app while it is in the
   foreground.
4. Otherwise posts via `NotificationPresenter`.

## Notification Types

Source-of-truth list. Adding a new type means updating the enum **and** the
mapper — the dispatcher and router will fail to compile until the mapping is
complete.

- `APPROVAL_NEEDED`
- `SERIOUS_ACTION_PENDING`
- `CRITICAL_ACTION_PENDING`
- `TASK_COMPLETE`
- `WORKER_FAILED`
- `GATEWAY_DISCONNECTED`
- `EMERGENCY_STOP_ACTIVE`
- `MEMORY_CORRECTED`

## Actions

- `OPEN_APPROVAL` → Approvals
- `OPEN_TASK` → Tasks
- `OPEN_AUDIT` → Audit log
- `EMERGENCY_STOP` → Emergency Stop screen, then explicit confirmation
- `DISMISS` → cancel the notification, no navigation

## Safety Contract

1. **No OS prompt on first launch.** `PermissionGate.requestPermission` is only
   called from `NotificationPermissionEducation.onUserAcceptedEducation`.
2. **App works if denied.** The dispatcher returns `InAppFallback` and the UI
   surfaces in-app banners. Settings, approvals, tasks, audit and emergency
   stop all remain reachable.
3. **No spam.** The spam guard collapses duplicates within a configurable
   window; `EMERGENCY_STOP_ACTIVE` is exempt.
4. **Notifications open the correct screen.** `NotificationEventMapper.target`
   is the single source of truth; the dispatcher reads it for the content
   intent and the router reads it for action taps.
5. **Emergency stop is two-step.** Tap → navigate + show confirmation →
   confirm → trigger. No single-tap kill switch on a notification.

## Test Surface

JVM tests live under `apps/android/src/test/kotlin/...`:

- `NotificationPermissionEducationTest` — education ordering, denial fallback,
  opt-out persistence.
- `NotificationDispatcherTest` — approval routes to Approvals, task routes to
  Tasks, denied permission falls back, duplicates suppressed, settings
  honoured, emergency stop overrides master toggle.
- `NotificationActionRouterTest` — open approval / task / audit navigation,
  dismiss behaviour, emergency stop requires confirmation.
- `NotificationEventMapperTest` — every type mapped, approval-class share
  channel, only `CRITICAL_ACTION_PENDING` exposes the emergency stop inline.
- `NotificationSettingsTest` — master toggle behaviour, emergency stop cannot
  be disabled, per-type honoured.
- `NotificationSpamGuardTest` — window enforcement, dedupe key, emergency
  bypass.

## Build

```bash
cd apps/android && ./gradlew assembleDebug
```

`assembleDebug` is wired as an alias of `assemble` + `test`. The full Android
app module that consumes this core lives in a downstream repository — that
build invokes the same gradle target.
