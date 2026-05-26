# Jarvis Prime — Emergency Stop

> Visible, reliable, app-wide kill switch for Jarvis Prime. Lives next
> to the orchestrator code in the native Android module.

## States

| State        | Severity | Blocks                                                                 | Notes |
|--------------|----------|------------------------------------------------------------------------|-------|
| `INACTIVE`   | 0        | nothing                                                                 | default |
| `SOFT_PAUSE` | 1        | new task starts                                                         | in-flight work continues |
| `HARD_STOP`  | 2        | new task starts, sends, deletes, pushes, deploys                        | reads still allowed |
| `LOCKDOWN`   | 3        | everything except status, audit, export, resume                         | strict read-only floor |

The level only goes up via `engage` / `escalate`; coming back to
`INACTIVE` requires the **approval-gated resume flow** described below.

## Entry points

The button is reachable from anywhere a Jarvis surface lives:

1. **Home (`OrchestratorScreen`)** — persistent circular icon in the
   top-app-bar, plus an inline **Critical action card** that shows the
   live state and direct-engage / escalate / request-resume controls.
2. **Control screen (`EmergencyStopScreen`)** — dedicated screen at
   `Screen.Control.route`. Long form of the dashboard card with the
   full audit log and an export-audit action.
3. **`CriticalActionCard`** — composable embedded on the home; clicking
   `Emergency Stop` goes straight to the confirmation dialog.
4. **Interactive icon long-press** — long-pressing the top-bar icon
   escalates one level (INACTIVE → SOFT_PAUSE → HARD_STOP → LOCKDOWN).
5. **Notification action** — the foreground-service notification now
   carries an "Emergency Stop" / "Escalate to …" action. Tapping it
   posts an `ACTION_EMERGENCY_STOP` intent that the service routes
   into `EmergencyStopController.engage` / `escalate`.

## Architecture

Files under `app/src/main/java/com/aci/hermes/`:

```
data/emergency/
  EmergencyStopState.kt        — sealed enum + GuardedAction enum
  EmergencyStopAuditEvent.kt   — append-only audit row + ResumeApproval
  EmergencyStopRepository.kt   — JSON persistence in filesDir
  EmergencyStopController.kt   — state machine, audit, guard(), resume

ui/components/
  EmergencyStopButton.kt       — top-bar icon with tap + long-press
  EmergencyStopDialog.kt       — engage + resume-approval dialogs
  EmergencyStopBanner.kt       — blocked / lockdown banners
  CriticalActionCard.kt        — home-screen kill switch card

ui/screens/emergency/
  EmergencyStopViewModel.kt    — UI wrapper, single UiState flow
  EmergencyStopScreen.kt       — dedicated Jarvis Control screen
```

The controller is held in `AppContainer` and lives for the lifetime of
the process. State and the audit log are persisted to
`<filesDir>/jarvis_emergency_stop.json` so an engaged stop survives
process death and reboot.

## Resume flow (approval gate)

Returning to `INACTIVE` requires two steps and is always audited:

1. `controller.requestResume(requestedBy, reason)` →
   creates a `ResumeApproval` (id + timestamp + originating state) and
   writes a `RESUME_REQUESTED` audit event. The stop level is **not**
   lowered yet.
2. `controller.approveResume(approvalId, approver)` →
   matches the pending approval id, transitions state to `INACTIVE`,
   writes `RESUME_APPROVED` and `RESUME` audit events.

Denial is symmetric: `controller.denyResume(approvalId, approver,
reason)` clears the pending request, writes `RESUME_DENIED`, and
leaves the stop at its current level.

Stale or replayed approval ids are rejected — the controller checks
the pending approval id before applying the transition.

## Action gating

The rest of the app asks `controller.guard(action, source)` before
performing anything mutating. The matrix is:

| `GuardedAction` | INACTIVE | SOFT_PAUSE | HARD_STOP | LOCKDOWN |
|-----------------|----------|------------|-----------|----------|
| START_TASK      | ✅       | ⛔          | ⛔         | ⛔        |
| SEND            | ✅       | ✅          | ⛔         | ⛔        |
| DELETE          | ✅       | ✅          | ⛔         | ⛔        |
| PUSH            | ✅       | ✅          | ⛔         | ⛔        |
| DEPLOY          | ✅       | ✅          | ⛔         | ⛔        |
| MUTATE          | ✅       | ✅          | ✅         | ⛔        |
| READ            | ✅       | ✅          | ✅         | ✅        |
| STATUS          | ✅       | ✅          | ✅         | ✅        |

`guard(...)` audits the rejection with a `BLOCKED_ACTION` row that
records the source tag — useful for forensic review.

`OrchestratorViewModel` and `TaskDetailViewModel` consume the
controller directly: new-task FAB, prompt-copy, tool-open, save,
delete, mark-handed-off all run through `guard(...)` and short-circuit
with a snackbar if blocked.

## Audit log

The audit log is bounded at `EmergencyStopAuditEvent.MAX_AUDIT_ENTRIES`
(500) entries — older entries roll off. Event types:

- `ENGAGE` — first transition out of `INACTIVE`.
- `ESCALATE` — climbing levels.
- `DEESCALATE` — stepping down (but never to `INACTIVE`).
- `RESUME_REQUESTED` — open approval request.
- `RESUME_APPROVED` / `RESUME` — paired success transitions.
- `RESUME_DENIED` — rejected approval.
- `BLOCKED_ACTION` — `guard(...)` refused an action.

`EmergencyStopController.snapshotJsonForExport()` returns the full
state + audit + pending-approval as a single JSON document that the
Control screen exports via the clipboard `ContentCopy` action.

## Tests

JVM unit tests (`app/src/test/.../data/emergency/`):
- `EmergencyStopStateTest` — severity ordering / four-state contract.
- `EmergencyStopRepositoryTest` — JSON round-trip, atomic commit, snapshot.
- `EmergencyStopControllerTest` — every transition, gating matrix, audit, persistence across process restart, audit log bound.

Compose UI tests (`app/src/androidTest/.../ui/emergency/`):
- emergency button visible
- confirmation dialog appears and emits the chosen target
- hard stop banner renders
- lockdown banner renders
- resume dialog requires approver identifier before enabling Approve
- icon visibly updates when state changes
- critical card emergency-stop click fires `onEngageStop`
- critical card in lockdown only offers `Request resume`
- long-press on the button escalates

Run from the module root:

```bash
cd apps/android
./gradlew :app:testDebugUnitTest            # JVM unit tests
./gradlew :app:connectedDebugAndroidTest    # Compose UI tests (needs device/emulator)
./gradlew assembleDebug                     # APK build
```
