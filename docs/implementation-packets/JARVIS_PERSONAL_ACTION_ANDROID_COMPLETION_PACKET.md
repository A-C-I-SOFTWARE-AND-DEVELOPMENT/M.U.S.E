# Implementation Packet — Personal Action / Android Completion

Status: **scaffolded.** The Python policy/state layer
(`companion_presence.py`) and Kotlin services exist and are test-covered;
**real device-action execution is intentionally not implemented** in this
PR and remains owner- and permission-gated.

## What exists today
- `hermes_cli/jarvis_prime/companion_presence.py` — presence state machine,
  avatar traits, task animation plan, accessibility-gesture risk gating.
  Tests: `tests/test_jarvis_prime_companion_presence.py`,
  `tests/test_jarvis_prime_cli_audit_lanes.py` (presence lane).
- Android services under `apps/android/.../service/` (accessibility,
  overlay, voice loop) and chat screens — present in the repo.
- The packetizer routes avatar/device requests to `RC3` with the
  `android_accessibility_gesture` owner gate.

## Bounded follow-ups (the personal-action broker)
Implement a broker that, for each requested action, returns exactly one of:
`direct_execute`, `blocked_missing_capability`, `requires_final_confirmation`,
`blocked_by_policy`. Rules:
1. No action without the corresponding Android permission/capability.
2. External post/send/purchase/security/destructive actions always
   `requires_final_confirmation` before the irreversible step.
3. Emergency stop blocks execution unconditionally.
4. Missing accessibility service blocks gestures
   (`blocked_missing_capability`).
5. Avatar animation can run **without** any real gesture (separation of
   animation from device control).

## Kotlin tests to add (when the Android toolchain runs)
- no action without permission/capability
- final confirmation for irreversible actions
- emergency stop blocks execution
- missing accessibility service blocks gestures
- avatar animation runs without a real gesture

## Commands
```bash
cd apps/android && ./gradlew test   # record exact failure if the toolchain is unavailable
python -m hermes_cli.jarvis_prime presence --mission "open Facebook" --target-app Facebook --real-action --json
```

## Owner gates / rollback / risks
- Owner gates: accessibility gesture, external message, purchase, app-store
  release — all deferred to `Yes, with authorization.` and Android system
  permissions.
- Rollback: no runtime behavior changed for Android in this PR.
- Risk: do **not** add background camera/microphone behavior without an
  explicit, documented opt-in. No spyware-like behavior.
