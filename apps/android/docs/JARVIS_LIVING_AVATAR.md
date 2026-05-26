# Jarvis Living Avatar — Architecture Note

The avatar layer extends the existing **icon state machine**
(`ui/jarvis/IconState`, `IconStateMapper`, `JarvisIconColors`,
`OrchestratorIconStateMapping`) into a full-screen presence indicator
that tells the operator what Jarvis is doing in plain language.

It **never** re-implements the icon's safety contract. The colors,
rings, and accessibility labels still come from `JarvisIconColors`
and `IconState`; the avatar layer only adds:

- **Finer-grained activity overlay** (Coding, Testing) on top of the
  existing safety-relevant icon states.
- **Plain-language status text** so the operator always sees what
  Jarvis is doing.
- **Reduced-motion support** for accessibility.

## New types

| Type | Purpose |
|---|---|
| `AvatarActivity` (enum) | Idle, Thinking, Talking, Working, Coding, Testing, Blocked, WaitingForApproval. |
| `JarvisAvatarProfile` | The currently-selected avatar identity (built-in drawable or user-generated app-private file). |
| `AvatarRenderSpec` | Resolved render output: `iconState`, `appearance`, `activity`, `statusStringResId`, `reducedMotion`. |
| `AvatarStateMapper` | Pure collapse of `(IconStateInputs, AvatarActivity, reducedMotion)` → `AvatarRenderSpec`. |
| `JarvisLivingAvatar` | Compose composable that renders an `AvatarRenderSpec`. |
| `LocalReduceMotion` | Composition-local for the device's reduced-motion preference. |

## Precedence — the safety floor always wins

`AvatarStateMapper.map(inputs, activity, reducedMotion)`:

1. **Safety floor states** (`CRITICAL_ACTION_PENDING`,
   `SERIOUS_ACTION_PENDING`, `WAITING_FOR_APPROVAL`, `BLOCKED`,
   `OFFLINE`, `WARNING`) always override any activity hint. The
   operator must always see safety-relevant state first.
2. Otherwise, if `IconStateMapper.map(inputs)` returns a non-`IDLE`
   icon-state, the inputs win — the actual session state is more
   trustworthy than a stale activity hint.
3. Only when the inputs collapse to `IDLE` does the activity hint
   drive the icon state.
4. For `WORKING`-tier states, `Coding` / `Testing` survive as a
   refinement of `Working` so the operator gets the more specific
   status text.

## Activity → status string

| Activity | `strings_avatar.xml` entry | User-facing string |
|---|---|---|
| `Idle` | `avatar_status_idle` | "Jarvis is here." |
| `Thinking` | `avatar_status_thinking` | "Jarvis is thinking…" |
| `Talking` | `avatar_status_talking` | "Jarvis is talking." |
| `Working` | `avatar_status_working` | "Jarvis is working." |
| `Coding` | `avatar_status_coding` | "Jarvis is coding." |
| `Testing` | `avatar_status_testing` | "Jarvis is testing." |
| `Blocked` | `avatar_status_blocked` | "Jarvis is blocked." |
| `WaitingForApproval` | `avatar_status_waiting_for_approval` | "Jarvis is waiting for your approval." |

The strings are first-person-from-Jarvis so the surface reads as a
presence indicator, not a debug log.

## Reduced-motion contract

- `AvatarRenderSpec.effectivePulseAmplitude` returns `0f` whenever
  `reducedMotion == true`, no matter what the icon's appearance
  recipe says.
- `JarvisLivingAvatar` collapses the breathing animation to a static
  frame in that case.
- The composition-local `LocalReduceMotion` is resolved in the
  screen layer (probably from `AccessibilityManager.isReducedMotionEnabled`
  on Android 13+ or `Settings.Global.ANIMATOR_DURATION_SCALE == 0f`
  on older releases) and pushed down via `CompositionLocalProvider`.
- The default is `false`. Tests use the default or override directly.

## What we did **not** change

- `IconState`, `IconStateMapper`, `JarvisIconColors`, and
  `OrchestratorIconStateMapping` — read-only dependencies.
- `EmergencyStopController`, `EmergencyStopRepository` — runtime
  safety subsystem is untouched.
- `AndroidManifest.xml` — zero new permissions.
- Owner-gated actions, the in-app authorization phrase, redaction
  layer — all untouched.

## Tests

| Test file | Coverage |
|---|---|
| `AvatarActivityTest` | enum shape + status-string-resource-id contract + icon-state mapping |
| `AvatarStateMapperTest` | every activity, every safety-floor override, reduced-motion, appearance reuse |
| `JarvisAvatarProfileTest` | both `Source` variants, identity-agnostic shape, default name |

Compose-UI tests for `JarvisLivingAvatar` and `JarvisLiveScreen` ship
on the same branch under `JarvisLiveScreenStateTest` etc. (commit 4).
