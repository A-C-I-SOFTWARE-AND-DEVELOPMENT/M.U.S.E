# Implementation Packet — Authorized Android Action Broker

## Mission

Build the private local JARVIS companion action broker so a mini avatar can visibly work across Android apps and execute owner-authorized gestures.

## Scope

Allowed areas:

- `apps/android/app/src/main/AndroidManifest.xml`
- `apps/android/app/src/main/res/xml/jarvis_accessibility_service.xml`
- `apps/android/app/src/main/java/com/aci/hermes/automation/**`
- `apps/android/app/src/main/java/com/aci/hermes/overlay/**`
- `apps/android/app/src/main/java/com/aci/hermes/attention/**`
- `hermes_cli/jarvis_prime/personal_action_authority.py`
- tests/docs for this lane

## Required Android capabilities

- `android.permission.SYSTEM_ALERT_WINDOW` for the mini avatar overlay.
- Accessibility service with `android.permission.BIND_ACCESSIBILITY_SERVICE`.
- Accessibility metadata:
  - `canRetrieveWindowContent=true`
  - `canPerformGestures=true`
  - relevant event types for window/content changes
- `<queries>` for known target apps instead of broad package visibility wherever possible.
- Optional MediaProjection foreground service only when screen capture is needed.

## Behavior contract

Example request: `click on Facebook`.

1. JARVIS classifies this as cross-app navigation.
2. Mini avatar acknowledges the task.
3. Broker checks package visibility and whether Facebook is installed.
4. Overlay avatar runs toward Facebook or the current launcher target.
5. Accessibility broker performs `ACTION_CLICK` on a matching node if available.
6. If node action fails, broker uses `dispatchGesture` at the resolved coordinate.
7. Avatar reports success, blocked, or needs capability grant.

## Acceptance criteria

- Missing overlay/accessibility grants produce a clear blocked state, not a fake action.
- Navigation/tap actions execute directly when standing authorization and Android grants are present.
- External send/post/payment/security/destructive actions pause at final gesture by default.
- Emergency stop disables execution immediately.
- Avatar choreography mirrors the broker state.
- No raw camera frames are persisted.
- No cloud upload is required for attention sensing.

## Verification

- Python unit tests for `personal_action_authority.py` pass.
- Android unit tests cover planner classification and capability state.
- Manual Android test: Facebook installed, overlay enabled, accessibility enabled, command `click on Facebook` opens or taps Facebook.
