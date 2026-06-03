# JARVIS avatar — top-tier art + float-over-apps guide

Everything in the app is **wired**; the only thing that turns the breathing
pixel character into a fully-rigged, expressive avatar is **art** authored to a
fixed contract. This guide is the checklist to produce it, plus how the
float-over-everything overlay works.

The renderer is **data-driven**: it feeds the renderer-neutral `AvatarInputs`
(`pose`, `energy`, `motion`) to whatever body is active. Finished art that
honors the contract drops in with **zero Kotlin changes**.

---

## A) Rive (2D, recommended) — `res/raw/jarvis.riv`

Rive (https://rive.app) is a free editor for interactive, state-machine-driven
2D animation. Highest quality-for-effort and already wired (`JarvisRiveAvatar`).

### Build it in the Rive editor
1. Create/import a character artboard (the [Rive marketplace](https://rive.app/marketplace)
   has rigged characters you can adapt).
2. Add a **State Machine** named exactly **`JarvisStateMachine`** with three inputs:
   | Input | Type | Range | Drives |
   |---|---|---|---|
   | `pose` | Number | 0–16 | which animation/expression (see ordinals below) |
   | `energy` | Number | 0–100 | speed / brightness / liveliness |
   | `motion` | Boolean | — | `false` ⇒ hold still (reduced motion / sleep) |
3. Wire transitions so each `pose` value plays its animation, and **blend**
   between poses (don't hard-cut) — continuous motion is what reads as alive.
   Use `energy` to scale playback speed/glow; freeze when `motion` is false.
4. **Export → Runtime (.riv)**.

### Drop it in
- Save to `apps/android/app/src/main/res/raw/jarvis.riv`, rebuild. It
  **auto-activates** (priority: photo → Rive → pixel character → orb). No code
  change. The breathing/physics/state-reactions all map through automatically.

### `AvatarPose` ordinals (source of truth — `ui/screens/live/AvatarAnimation.kt`)
`0 IDLE · 1 LISTEN · 2 THINK · 3 WORK · 4 SPEAK · 5 APPROVE · 6 BLOCKED ·
7 EMERGENCY · 8 RUN · 9 PUSH · 10 PAGE_TURN · 11 SCROLL · 12 POINT · 13 WANDER ·
14 SLEEP · 15 WAKE · 16 RECOMMEND`

> Pixel-art tip if you draw frames yourself: silhouette-readability first, ~32px,
> 6–12 colours (2–3 per part). The same applies to any sprite-sheet body.

---

## B) 3D (glTF) — `res/raw/jarvis.glb` (heavier; on request)

For a 3D character the contract is: a **`.glb`** containing one animation clip
**named after the lowercase `AvatarPose`** (`idle`, `listen`, `think`, `speak`,
`run`, `push`, `page_turn`, …). `JarvisFilamentAvatar` looks the clip up by name
and crossfades on `pose` changes, scaling speed by `energy`.

**Status:** the contract is fixed and the `Character3D` slot is reserved, but the
**Filament 3D engine itself is a deliberately-deferred heavy native dependency**
(~20 MB of `.so`, on top of Rive's). It's not worth doubling the APK for art that
doesn't exist yet. When you have a `.glb` rigged to the pose-clip names, say so
and the Filament renderer gets wired (same `AvatarInputs` contract, auto-activate
like Rive). Until then `Character3D` falls back to the breathing pixel character.

**Recommendation:** prefer **Rive** — smaller, free editor, richer interactivity,
already live. Use 3D only if you specifically need a 3D model.

---

## C) Float JARVIS over every app (the system overlay)

The Live screen has a **picture-in-picture toggle** (top-right). Tapping it:
1. Requests the **draw-over-other-apps** permission (`SYSTEM_ALERT_WINDOW`) via
   Settings if not yet granted — a high-risk permission you grant once.
2. Starts `JarvisOverlayService`, a foreground service that draws the **living
   avatar in a `TYPE_APPLICATION_OVERLAY` window** floating over all apps, and
   **mirrors JARVIS's live state** (idle/think/speak…) onto it.
3. Tap again to stop.

Per platform guidance the overlay is small, unobtrusive, and dismissible; it runs
inside a foreground service so it survives app backgrounding, and is torn down
cleanly on stop. Keep the Termux runtime alive so the floating avatar reflects a
real agent.

> One-device setup: grant "Display over other apps" for Jarvis Prime in
> Settings → Apps → Jarvis Prime → Advanced, then tap the toggle.
