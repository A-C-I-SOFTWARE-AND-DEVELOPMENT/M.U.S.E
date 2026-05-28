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
| **Body / renderers** | `ui/screens/live/` | Draws the character with **self-contained Compose** renderers: `JarvisPixelAvatar` (animated sprite, default body), `JarvisCharacterAvatar` (procedural humanoid — runs/pushes/sleeps), `JarvisLivingAvatar` (orb fallback). `LivingAvatarHost` picks one via `DeviceCapability`. The `Rive` / `Character3D` kinds map to the procedural character today; a finished Rive/3D body is a documented drop-in behind the same `AvatarInputs` contract (no external SDK in the compile path yet). |
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

- **Renderers are Compose-only today.** The body is a procedural
  character / animated sprite, not finished art. Real **Rive** (vector)
  and **Filament** (3D glb) bodies are documented drop-ins behind the
  same `AvatarInputs` contract (`res/raw/README.md`,
  `docs/avatar/rive-state-contract.md`) — adding them is a new renderer +
  one Gradle dep, with no call-site change. Dropped from this PR to keep
  the module compiling without unverifiable external-SDK API calls.
- **Voice engines** (`WakeWordEngine` / `SttEngine` / `TtsEngine`) are
  interfaces with `Wiring` factory slots; the Porcupine/Vosk/TTS concrete
  impls bind in `AppContainer` as a follow-up (same reason).
- **Image-to-3D** conversion path is request-shaped (`tools/avatar_conversion.py`)
  but the 3D body it would feed is the drop-in above.
- **Live gateway** is wired in DI (`AppContainer.liveJarvisChatGateway`,
  pure JDK `HttpURLConnection`) but defaults to the mock
  (`useLiveGateway = false`) for offline-safe first run; flip it (or bind
  it to a setting) once the daemon runs.
- **Android build not verified in this container** (no SDK) — pure-logic
  Kotlin units + the Python endpoint/catalog tests are.
