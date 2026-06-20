# muse Android device control — safety hardening plan (findings #4 & #5)

Diff-level implementation plan for the two **pre-Play** safety findings from
[`jarvis-android-automation-privacy-review.md`](./jarvis-android-automation-privacy-review.md).
Both are **fail-safe by construction**: they only ever *add* a gate, keep the
broker the single chokepoint, and keep "deny by default" precedence intact.

> **Status (2026-06-05): both implemented and unit-verified against the
> installed Android SDK** (`:app:testDebugUnitTest` full suite green).
> - **#4** (non-disableable IRREVERSIBLE confirmation floor) — PR #324.
> - **#5** (emergency-stop unification — device halt is now a read-only
>   projection of the audited `EmergencyStopController`, no device-local
>   release) — this branch, stacked on #324.
>
> Verified by JVM/Robolectric unit tests only (broker pure-function tests +
> a Robolectric controller projection test). The instrumented smoke
> (overlay/voice teardown on a real device, halt surviving a process restart)
> still needs an emulator/device run before Play release.

Paths are under `apps/android/app/src/main/java/com/aci/hermes/`.

---

## Finding #5 — unify device-control emergency stop with the audited global stop

### Gap

- `ui/navigation/HermesNavGraph.kt:109-114` fires two independent stops, and
  calls `orchestratorServiceController.emergencyStop()` **directly** rather than
  `container.emergencyStop()` (`di/AppContainer.kt`), so this path doesn't drive
  `EmergencyStopController` at all (a second, smaller bug).
- `data/devicecontrol/DeviceControlController.kt` owns a private
  `_halted: MutableStateFlow<Boolean>` that is the sole gate behind
  `gesturesAllowed()` and the broker's `emergencyEngaged` arg.
- `DeviceControlController.releaseEmergencyStop()` flips `_halted = false` with
  **no approval gate and no audit row**, whereas the audited path requires
  `EmergencyStopController.requestResume()` → `approveResume()` (replay-protected).

So an engaged global stop can be released for device control alone, silently,
while `EmergencyStopController` still reports stopped — the two can disagree, and
`_halted` resets to `false` on process restart while the audited stop persists.

### Design — make the device halt a projection of `EmergencyStopController.state`

1. **`DeviceControlController`** takes `emergencyStop: EmergencyStopController`.
   Replace the writable `_halted` with a read-only projection:
   `halted = emergencyStop.state.map { it.isActive }.stateIn(...)`, and a
   `@Volatile haltedSnapshot` the synchronous `gestureGuard` reads. In `init`,
   collect `state.isActive`; on `active`, stop the overlay + voice loop (so any
   engaged stop — from any surface — tears them down, not just the device button).
   `gesturesAllowed()` and the broker call read `haltedSnapshot`.
2. **Delete the unguarded `releaseEmergencyStop()` flag flip.** Resume routes
   through `emergencyStop.requestResume()` → `approveResume()` only — or, simpler,
   have the device screen navigate to the existing global resume UI (the one
   `ControlViewModel.releaseEmergencyStop` uses) and delete device-local resume
   code entirely.
3. **`di/AppContainer.kt`** — pass the already-constructed
   `emergencyStopController` into `DeviceControlController` (no reorder needed).
4. **`HermesNavGraph.kt`** — collapse the lambda to a single audited entry:
   `container.emergencyStop()` (which engages `EmergencyStopController` + stops
   the orchestrator; device control halts via the state projection). Remove the
   separate `deviceControlController.engageEmergencyStop()` call.
5. **`ui/screens/devicecontrol/DeviceControlViewModel.kt` / `DeviceControlScreen.kt`**
   — the "Release halt" button becomes "Request resume" (or routes to the global
   resume surface); resume cannot complete without owner approval.

### Why fail-safe

Single source of truth (no `_halted` to diverge); the only path back to
`INACTIVE` is the replay-protected approved resume; any active level
(`SOFT_PAUSE`/`HARD_STOP`/`LOCKDOWN`) halts gestures; the halt now survives a
reboot (state is persisted) instead of resetting to `false`.

---

## Finding #4 — non-disableable confirmation floor for irreversible/external actions

### Gap

- `data/devicecontrol/DeviceActionPacket.kt` — sensitivity is binary
  (`STANDARD`/`SENSITIVE`).
- `data/devicecontrol/DeviceConsentState.kt` — `confirmSensitiveActions` can be
  turned **off** (owner-gated).
- `data/devicecontrol/DeviceActionBroker.kt` requires confirmation only
  `if (sensitivity == SENSITIVE && consent.confirmSensitiveActions)` — so with
  the toggle off, every SENSITIVE action auto-runs, and there is no floor for a
  future irreversible/external action (send/post/purchase/share/call/delete).

### Design — add an `IRREVERSIBLE` tier with a floor the toggle cannot lower

1. **`DeviceActionPacket.kt`** — add a third, highest tier
   `IRREVERSIBLE` (ordered `STANDARD < SENSITIVE < IRREVERSIBLE`). Keep
   `sensitivityOf(...)` an **exhaustive** `when` (no `else`) so any *new* intent
   forces a compile error until its author classifies it — that is the
   enforcement mechanism. Today's five intents stay STANDARD/SENSITIVE, so
   existing flows are byte-for-byte unchanged.
2. **`DeviceActionBroker.kt`** — the confirmation floor. Give `evaluate(...)` an
   explicit `confirmationObtained: Boolean = false` input so the floor requires
   confirmation **once** but does not deadlock the post-approval re-run:
   ```
   needsConfirm = when (sensitivity) {
       IRREVERSIBLE -> !confirmationObtained         // floor: confirm once
       SENSITIVE    -> consent.confirmSensitiveActions
       STANDARD     -> false
   }
   ```
   - Normal dispatch passes `confirmationObtained = false` → IRREVERSIBLE ⇒
     `NeedsConfirmation` (held as a `PendingDeviceAction`).
   - `DeviceControlController.approvePending` re-evaluates after the owner taps
     Approve and **must pass `confirmationObtained = true`** (the card tap *is*
     the one per-action confirmation). Emergency/consent/permission re-checks
     still run on that path and can still block — only the confirmation
     requirement is satisfied, so the approved IRREVERSIBLE action can execute.
   > ⚠️ This corrects an earlier draft (flagged in review): if IRREVERSIBLE
   > returned `NeedsConfirmation` *unconditionally*, `approvePending` — which
   > executes only on `BrokerDecision.Approved` — would refuse the action even
   > after approval, so it could never run. The `confirmationObtained` input is
   > required; do **not** reuse the `confirmSensitiveActions = false` re-check
   > copy to mean "already confirmed" (IRREVERSIBLE ignores that flag by design).
3. **`DeviceConsentState.kt`** — KDoc only: state that `confirmSensitiveActions`
   governs SENSITIVE only and **cannot** disable confirmation for IRREVERSIBLE.
4. **UI** — distinguish IRREVERSIBLE visually (e.g. red tier) on the pending card,
   and state the non-disableable floor in the confirm-toggle owner-gate dialog.

### Migration risk

- Adding the enum value makes every exhaustive `when (sensitivity)` a compile
  error until handled — the *desired* fail-closed property (few sites: broker,
  any UI coloring, tests).
- `DeviceActionSensitivity` is persisted in the action ledger; ensure the
  serializer round-trips the new constant (old rows only contain the old two).
- No DataStore migration (the toggle key/semantics are unchanged).

---

## Validation (requires an Android suite / emulator)

These are pure-logic changes at the broker/controller seams the codebase already
unit-tests off-device (`DeviceActionBroker` is a pure function;
`DeviceControlController` accepts injectable `clock`/`idGenerator`/`scope`). Run:

1. **Broker units (JVM):** IRREVERSIBLE ⇒ `NeedsConfirmation` even with
   `confirmSensitiveActions = false`; SENSITIVE ⇒ `Approved` with toggle off;
   emergency precedence still wins.
2. **Controller halt-projection:** engaging `EmergencyStopController` (any active
   level) flips `halted` and makes `gesturesAllowed()` false; `approveResume`
   restores; verify **no** path sets halt false without an approved resume.
   (Existing `releaseEmergencyStop` tests in `JarvisLiveViewModelTest` /
   `ControlViewModelTest` are the *global* resume and should keep passing.)
3. **Approval re-check:** a held SENSITIVE action runs after the owner tap; a held
   IRREVERSIBLE action is refused until approval and then **runs** when
   `approvePending` re-evaluates with `confirmationObtained = true` (and is still
   blocked if emergency/consent/permission changed in the meantime); without that
   flag IRREVERSIBLE is never `Approved`.
4. **Instrumented smoke:** global Emergency Stop stops orchestrator + overlay +
   voice loop + drops the accessibility gesture guard in one tap; resume requires
   approval; the halt survives a process restart.

## Files in scope

`data/devicecontrol/{DeviceControlController,DeviceActionBroker,DeviceActionPacket,DeviceConsentState}.kt`,
`data/emergency/EmergencyStopController.kt` (read-only dep), `di/AppContainer.kt`,
`ui/navigation/HermesNavGraph.kt`,
`ui/screens/devicecontrol/{DeviceControlViewModel,DeviceControlScreen}.kt`.
