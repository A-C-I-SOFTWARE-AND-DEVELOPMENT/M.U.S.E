# Sprint 7 — Android Cockpit Product Surface

**Program:** Hermes 10/10 Productization  
**Target vertical slice:** Voice/Android cockpit -> gateway session -> job orchestration -> worker patch -> validation gate -> GitHub PR -> phone approval.  
**Operating rule:** do not add new capability lanes unless they directly close this loop.  
**Parallel execution model:** each sprint is split into independent agent lanes. Builder agents work in separate branches/worktrees. Reviewer agents consume patches after builders finish; they do not edit in parallel with the builder whose patch they review.

## Objective

Turn the Android app from a thin/skeletal cockpit into the primary control surface for Hermes jobs, approvals, voice, diagnostics, and session recovery.

## Product surfaces

1. Pairing/onboarding.
2. Home command surface.
3. Job list.
4. Job detail with live event timeline.
5. Patch/PR summary.
6. Approval inbox.
7. Voice composer button available everywhere.
8. Diagnostics and connection health.
9. Settings: gateway URL, paired device, token rotation, notification preferences.
10. Foreground service for in-flight jobs.

## Files likely touched

- `apps/android/app/src/main/.../data/cockpit/CockpitApi.kt`
- `apps/android/app/src/main/.../data/cockpit/*`
- `apps/android/app/src/main/.../ui/screens/orchestrator/*`
- `apps/android/app/src/main/.../ui/screens/settings/*`
- `apps/android/app/src/main/.../service/HermesService.kt`
- `apps/android/app/src/main/AndroidManifest.xml`
- Android tests under `apps/android/app/src/test` and `androidTest`

## Parallel agent lanes

| Lane | Agent | Branch | Mission |
|---|---|---|---|
| A | Android Data Agent | `sprint/7-android-data` | Implement API client models, repository layer, secure token storage. |
| B | Android UI Agent | `sprint/7-android-ui` | Implement job list/detail, approval inbox, PR summary screens. |
| C | Android Service Agent | `sprint/7-foreground-service` | Keep event stream alive, reconnect, notification handoff. |
| D | Android Pairing Agent | `sprint/7-pairing` | Implement pairing flow and device trust UI. |
| E | QA Agent | `sprint/7-android-tests` | Unit tests for viewmodels, fake API, state restoration. |
| F | Security Agent | `sprint/7-android-security` | Review permissions, token storage, logging. |
| G | Reviewer Agent | `sprint/7-review` | Review UX/state and Android security. |

## State machines

### Connection state

```text
Unpaired -> PairingStarted -> Paired -> Connected -> Degraded -> Disconnected -> Reconnecting -> Connected
```

### Job state

```text
Created -> Planning -> WorkersRunning -> PatchReady -> Validating -> AwaitingApproval -> Publishing -> Completed
                                                          \-> Failed
```

### Approval state

```text
Pending -> Approved -> Rejected -> Expired -> Superseded
```

## UI requirements

- Job timeline must update live.
- Approval cards show action summary, risk tier, rationale, and required phrase.
- Dangerous actions require deliberate UI friction, not one-tap approve.
- Patch summary must include changed files and validation results.
- PR URL appears after publish.
- Voice button is present on command, job detail, and approval screens.
- Offline/reconnecting state is visible.
- App must not crash when gateway is unavailable.

## Android permission policy

Do not add new permissions without Security Agent review. Likely needed later:

- `RECORD_AUDIO` for voice sprint.
- `POST_NOTIFICATIONS` for approval push.
- Foreground service permission depending on API level.

Any permission change triggers protected-path review.

## Acceptance criteria

- User can pair phone to gateway.
- User can start a job from Android.
- User can watch job events live.
- User can approve/reject pending approval.
- User can open PR URL after publish.
- Reboot/reopen restores session and latest cursor.
- Token is stored securely and logs do not contain token.

## Reviewer prompt

```text
Review Android cockpit implementation. Verify secure token storage, no accidental permission creep, correct reconnect behavior, clear risky-action UX, and no unredacted logs. Check that the app remains usable when gateway is offline.
```

## Definition of done

The Android cockpit can drive the non-voice version of the full Hermes loop end to end.
