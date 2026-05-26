# Jarvis Live — Full-Screen Command Cockpit

A read-only, full-screen presence indicator. The operator can always
glance at this surface and see what Jarvis is doing in plain
language.

## What it shows

| Surface | Source |
|---|---|
| Avatar (192 dp) | `JarvisLivingAvatar` composable, fed `AvatarRenderSpec` from `JarvisLiveViewModel.renderSpec`. |
| Status text under avatar | `AvatarRenderSpec.statusStringResId`, resolved via `stringResource(...)`. |
| Top app bar | "Jarvis" + back arrow. |
| Background | Dark navy (`JarvisLiveColors.Background = #0A0F1F`). |
| Accents | Cyan (active), Gold (approval), Red (critical) — all reused from `JarvisPalette`. |

## Inputs the screen reacts to (today)

`JarvisLiveViewModel` collapses these into one `AvatarRenderSpec` via
`AvatarStateMapper.map(...)`:

1. **Orchestrator service liveness** (`serviceRunningFlag`) → drives
   `gatewayOnline`. When false, the screen routes to `IconState.OFFLINE`
   and shows "Jarvis is blocked." (the safety-relevant status — never
   silently hide a service-down signal).
2. **Emergency stop subsystem** (`EmergencyStopRepository.state`) →
   drives `blocked`. `INACTIVE` means the avatar runs normally; every
   other state (`SOFT_PAUSE`, `HARD_STOP`, `LOCKDOWN`) routes to
   `IconState.BLOCKED`.
3. **Activity hint** (`MutableStateFlow<AvatarActivity>`) — what the
   chat / orchestration layer is currently doing. Pushable via
   `setActivity(...)`.
4. **Reduced-motion flag** (`reducedMotionFlag`) — when true, the
   avatar's breathing animation collapses to a static frame.

Listening / thinking / speaking / approval signals are not wired yet
— that's the next iteration. The safety floor is the must-have:
service down → offline, emergency stop engaged → blocked.

## Nav

- Route: `jarvis_live` (declared in
  `com.aci.hermes.ui.navigation.Screen.JarvisLive`).
- Full-screen push (not in the bottom nav). Reachable via deep link
  or a future "Open Live Cockpit" affordance from the home surface.
- The route does not require a permission. Emergency-stop UI is
  surfaced declaratively (the screen renders the BLOCKED state) —
  the screen does not try to mutate the emergency-stop subsystem.

## Theme

`JarvisLiveColors` is derived entirely from `JarvisPalette` plus one
navy background — there is no parallel palette. If the icon's color
contract is retuned (e.g. cyan shifts), the Live screen tracks
automatically.

| Token | Value | Where used |
|---|---|---|
| `Background` | `#0A0F1F` | Scaffold + Box background |
| `Surface` | `#111933` | Elevated cards / pills (reserved) |
| `Active` | `JarvisPalette.Cyan` | Listening / active accent |
| `Approval` | `JarvisPalette.Gold` | Approval-pending accent |
| `Critical` | `JarvisPalette.Red` | Critical / blocked accent |
| `OnBackground` | `#EDF1FA` | Primary text |
| `OnBackgroundMuted` | `#B6C0E0` | Idle / secondary text |

## Reduced motion

The screen reads the platform's reduced-motion preference via
`reducedMotionFlag` (provided by `AppContainer`) and pushes it down
the composition through `LocalReduceMotion`. `JarvisLivingAvatar`
respects the flag by collapsing its breathing animation to a static
frame.

## Tests

- `JarvisLiveViewModelTest` (7 tests): online-idle, service-down,
  emergency-stop / lockdown, coding-activity-survives, reduced-motion
  propagation, repeated activity updates.
- `JarvisLivePaletteTest` (4 tests): all three accents trace back to
  `JarvisPalette`; background is dark navy, not pure black.

A Robolectric Compose-render test (`JarvisLiveScreenStateTest`) is
intentionally **not** shipped here — the screen's contract is
exercised end-to-end via the VM tests plus the per-state status text
checks in `AvatarStateMapperTest`. Adding Robolectric pulls in a
heavy test dependency we have not yet adopted on this branch.

## What was **not** touched

- Owner-gated actions (`OWNER_GATED_ACTIONS`, in-app authorization phrase).
- Emergency-stop *controller* — the live screen only reads the
  repository's `state` flow.
- Redaction modules.
- `AndroidManifest.xml` permissions.
- Package identity (`applicationId = "com.aci.hermes"`).
