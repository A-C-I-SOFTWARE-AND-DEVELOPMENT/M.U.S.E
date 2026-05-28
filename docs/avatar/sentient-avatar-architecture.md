# Sentient Avatar — architecture

This is JARVIS Prime's **living body**: a character that lives on your
screen, physically operates the phone, talks to you hands-free, and
keeps itself busy (idles, wanders, sleeps, offers ideas) when you're
away. It's the personal-tool fork, so the usual permission restraint is
intentionally lifted — the emergency stop stays as a kill switch.

This doc is the map. It is implemented across the Android app
(`apps/android/`) and the Python agent (`gateway/`, `config/`, `tools/`).

## The five organs

| Organ | Where | What it does |
|---|---|---|
| **Body / renderers** | `ui/screens/live/` | Draws the character: `JarvisRiveAvatar` (default, vector state-machine), `JarvisFilamentAvatar` (3D glb, high-end only), `JarvisPixelAvatar` (animated sprite), `JarvisLivingAvatar` (orb fallback). `LivingAvatarHost` picks one via `DeviceCapability`. |
| **Hands** | `service/JarvisAccessibilityService` | Performs the real taps/swipes, launches apps, reads the on-screen node tree. |
| **Presence** | `service/JarvisOverlayService` | Floats the body over other apps (`TYPE_APPLICATION_OVERLAY`), animates the "run", runs the life loop, executes `MotionPlan`s. |
| **Voice** | `service/VoiceLoopService` + `voice/` | Wake word → STT → agent → TTS over a Bluetooth headset. |
| **Mind feed** | `data/jarvis/HttpJarvisChatGateway` + `gateway/jarvis_local_http.py` | Streams the real agent's state/reply so the body reacts to what the agent is actually doing. |

## How "Jarvis runs to Facebook and pushes it" works

1. You say/type **"open Facebook."**
2. `AutomationIntentParser` (pure) classifies it → `OpenApp("facebook")`.
3. `AppTargetResolver` (pure) fuzzy-matches → `com.facebook.katana`
   (+ the icon's on-screen rect if the launcher is visible).
4. `JarvisChoreographer` (pure) builds a `MotionPlan`:
   `RUN` to the icon → `PUSH` (the press that makes the app "click")
   → `SETTLE`. The real gesture rides on the `PUSH` step.
5. `JarvisOverlayService.execute(plan)` eases the avatar across the
   screen, plays the push clip, and asks
   `JarvisAccessibilityService.perform(gesture)` to fire the real tap /
   launch at that moment.
6. **"Next screen"** → `TurnPage(LEFT)` → run to the right edge,
   `PAGE_TURN` clip + a wide right-to-left swipe = the page flips.

Every decision step above is pure and unit-tested
(`JarvisChoreographerTest`, `AppTargetResolverTest`,
`AutomationIntentParserTest`) — the Android services are thin drivers.

## "Feels alive" when idle

`BehaviorScheduler` (pure, `BehaviorSchedulerTest`) decides the ambient
behavior each tick: fresh→`IDLE`, bored→`WANDER`, night or deep
inactivity→`SLEEP`, a ready suggestion past its cooldown→`RECOMMEND`.
`RecommendationQueue` holds proactive ideas the agent pushes via the
state feed. `AvatarAnimation` (pure, `AvatarAnimationTest`) blends the
agent work-state, the ambient behavior, and any active device-driving
clip into the renderer-neutral `AvatarInputs` every body consumes.

## Voice loop

`VoiceLoop` (pure state machine, `VoiceLoopTest`) drives
`DORMANT → WAITING_FOR_WAKE → LISTENING → THINKING → SPEAKING`, with
barge-in returning straight to `LISTENING`. Engines are pluggable
(`WakeWordEngine`=Porcupine, `SttEngine`=Vosk on-device, `TtsEngine`=
Android TTS), so on-device ↔ cloud is a swap. Transcripts run through
the **same** pipeline as chat (`JarvisIntentClassifier` /
`AutomationIntentParser`), so anything you can type you can say —
including the device-driving commands.

## Permissions (personal-tool fork)

Added to the manifest and pinned by the re-baselined invariant tests
(`ManifestPermissionsTest`, `ManifestPermissionAuditTest`):
`SYSTEM_ALERT_WINDOW`, `FOREGROUND_SERVICE_SPECIAL_USE`,
`FOREGROUND_SERVICE_MICROPHONE`, `RECORD_AUDIO`, `BLUETOOTH_CONNECT`,
`QUERY_ALL_PACKAGES`. The user grants the overlay permission
(`Settings.canDrawOverlays`) and enables the accessibility service the
first time they ask Jarvis onto the screen (education strings:
`jarvis_overlay_enable_*`, `jarvis_accessibility_enable_*`,
`jarvis_voice_enable_*`).

## Emergency stop

`JarvisAccessibilityService.gestureGuard` is wired to the existing
emergency-stop state. When engaged, every gesture is dropped before
dispatch — the body can move but cannot touch the device.

## Known rough edges (honest TODO)

- **`res/raw/jarvis.riv` is a placeholder** — drop in real art (same
  filename, the `JarvisStateMachine` input contract below).
- **3D glb + image-to-3D quality** — the Filament renderer + the
  `CHARACTER_3D` conversion path are scaffolded against a clip-name
  contract; final art/model tuning is follow-up.
- **Live gateway** is wired in DI (`AppContainer.liveJarvisChatGateway`)
  but defaults to the mock (`useLiveGateway = false`) for offline-safe
  first run; flip it (or bind it to a setting) once the daemon runs.
- **Android build not verified in CI here** (no SDK in the build
  container) — pure-logic units + the Python endpoint/catalog tests are.
