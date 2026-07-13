# Sprint 9 — Phone Approval Push, Recovery, and Lock-Screen Workflow

**Program:** Hermes 10/10 Productization  
**Target vertical slice:** Voice/Android cockpit -> gateway session -> job orchestration -> worker patch -> validation gate -> GitHub PR -> phone approval.  
**Operating rule:** do not add new capability lanes unless they directly close this loop.  
**Parallel execution model:** each sprint is split into independent agent lanes. Builder agents work in separate branches/worktrees. Reviewer agents consume patches after builders finish; they do not edit in parallel with the builder whose patch they review.

## Objective

Make owner approvals reliable when the phone is locked, the app is backgrounded, or the network reconnects.

## Target behavior

- Risky action creates an approval request.
- Gateway emits approval event.
- Android foreground service or push receives it.
- User gets notification.
- Tapping notification opens approval detail.
- Approval/rejection is sent with device auth and phrase if required.
- If offline, app shows pending state and reconciles on reconnect.

## Files likely touched

- `gateway/platforms/api_server.py`
- `gateway/session.py`
- new notification subscription backend
- Android notification manager
- Android foreground service
- Android approval screens
- Android WorkManager/retry layer
- tests for approval recovery

## Parallel agent lanes

| Lane | Agent | Branch | Mission |
|---|---|---|---|
| A | Gateway Push Agent | `sprint/9-push-backend` | Implement notification subscription abstraction and pending approval queue. |
| B | Android Notification Agent | `sprint/9-android-notifications` | Implement approval notifications and deep links. |
| C | Recovery Agent | `sprint/9-recovery` | Offline queue, retry, cursor reconciliation, pending inbox. |
| D | Security Agent | `sprint/9-approval-security` | Prevent notification spoofing and stale approvals. |
| E | QA Agent | `sprint/9-tests` | Simulate disconnect, expired approvals, duplicate decisions. |
| F | Reviewer Agent | `sprint/9-review` | Review recovery and approval race conditions. |

## Notification strategy

Support two layers:

1. **Foreground/local polling/SSE:** works without third-party push while app/service is alive.
2. **Optional push provider:** FCM or UnifiedPush for lock-screen delivery.

Do not make Google services mandatory if the project wants local/private mode. Implement a provider interface:

```python
class NotificationProvider:
    def subscribe(device_id, token_or_endpoint): ...
    def notify_approval(approval): ...
```

## Approval race rules

- Approval can be decided once.
- Expired approval rejects late decisions.
- Superseded approval rejects late decisions.
- Duplicate approve request returns existing decision.
- Device revocation blocks decision.
- Phrase mismatch returns failure and audit event.

## Acceptance criteria

- Approval notification appears from a backend event.
- Tapping opens exact approval screen.
- Decision syncs and updates job timeline.
- Offline decision queues or fails clearly depending on risk config.
- Expired approvals cannot be approved.
- Duplicate submissions are idempotent.
- Approval inbox persists after app restart.

## Reviewer prompt

```text
Review phone approval push/recovery. Look for stale approval acceptance, notification spoofing, duplicate submit bugs, offline queue hazards, and any route that approves without device auth plus decision verdict.
```

## Definition of done

Owner approvals are reliable and auditable even when the phone is not actively open to the Hermes app.
