# G0.3 — Android design-system module (snapshot)

**Grain:** G0.3 — Android Compose design-system module for the MUSE app.
**Branch:** `claude/muse-app-g03-android-ds`
**Base commit:** `d22c3e4a1efe779e234b0428f82484f8b457f9ce` (`git rev-parse origin/main`).
**Worktree:** `/home/user/hermes-agent/.claude/worktrees/agent-a778aff2779dd2739`.

## Intent

Express the MUSE visual design language (`docs/brand/muse-design-language.md`
— the Singularity look: one white core in the void, one thin spectral
cyan→violet ring, value-not-effects hierarchy, no drop shadows, bloom the core
only) as a **reusable Jetpack Compose component library**, built **only** from
the existing `Jarvis*` Singularity color tokens (`ui/theme/Color.kt`),
Material 3, and Compose Canvas/animation. No new Gradle dependencies; no edits
to any existing file (theme, screens, Gradle, ledger).

## Owned / created files

New Compose package `com.aci.hermes.ui.designsystem`:

- `apps/android/app/src/main/java/com/aci/hermes/ui/designsystem/MuseMotion.kt`
  — motion tokens: durations 150 / 250 / 350 ms + `StandardEasing` /
  `EmphasizedEasing` (`CubicBezierEasing`) and `fast()` / `standard()` /
  `emphasized()` `tween` factories.
- `.../MuseGlyph.kt` — Canvas mark: white core + stacked cool-white radial
  bloom (core only) + matte spectral cyan→violet ring (arc with a single gap),
  rotated -32°. No ring glow. Cool-white bloom tints are defined *locally* as
  derived glows (the brand doc explicitly calls these derived, not tokens) so
  `Color.kt` is untouched; the brand colors (`JarvisGold`/`JarvisCyan`/
  `JarvisViolet`) are reused.
- `.../MuseButton.kt` — `MuseButton` + `MuseButtonVariant` (Primary = white
  core fill / void text; Secondary = void-3 + edge hairline border; Danger;
  Approve). Optional leading icon.
- `.../MuseCard.kt` — void-3 fill, edge hairline, 12dp radius, zero
  shadow/tonal elevation (value-not-effects).
- `.../MusePill.kt` — `MuseStatusPill` (dot + label capsule) and `MuseChip`
  (neutral / selected core-fill / clickable).
- `.../MuseStatusDot.kt` — `MuseStatus` (Off / Ok / Live / Connecting) + the
  glowing dot; Connecting pulses (freezable via `animate = false`).
- `.../MusePhaseRail.kt` — `MusePhase` / `MusePhaseState` + the rail:
  done = cyan ring, current = white core (tight bloom), failed = danger,
  pending = muted hollow, connecting bars lit cyan once reached.
- `.../MuseSectionHeader.kt` — title + optional subtitle + optional trailing
  slot.
- `.../MuseEmptyState.kt` — glyph + title + body + optional primary action.
- `.../DesignSystemGallery.kt` — `@Preview`-annotated catalog rendering every
  component on the void background.

New tests under `com.aci.hermes.ui.designsystem`:

- `apps/android/app/src/test/java/com/aci/hermes/ui/designsystem/MuseComponentsSmokeTest.kt`
  — Robolectric/Compose smoke tests (button variants, card, pill, chip,
  section header, empty state, phase rail) asserting render + basic semantics.
- `.../MuseGlyphSmokeTest.kt` — composes the canvas-only marks (glyph, status
  dot in every state) and the full gallery, asserting they build and lay out
  without crashing.
- `.../MuseMotionTest.kt` — pure-JVM checks of the motion durations and that
  the `tween` factories carry them.

Snapshot: `docs/launch/muse-app/g03-android-ds.md` (this file).

## Design-language fidelity

- **White core is the hero**; spectral color is a sparing accent (the ring,
  the cyan status states). Primary button = the core rendered as a CTA.
- **Bloom the core only; ring is matte** — `MuseGlyph` blooms the core with
  stacked cool-white radial halos and draws the ring as a plain
  cyan→violet-gradient arc with round caps and **no** glow.
- **Value, not effects** — `MuseCard` uses zero elevation + an edge hairline;
  no drop shadows anywhere.
- **Motion is deliberate, not bouncy** — `tween`s only, no springs.

## Validation results

- **JDK:** OpenJDK 21.0.10 (`/usr/lib/jvm/java-21-openjdk-amd64`) — present and
  used.
- **Android SDK:** **NOT available** in this sandbox. There is no
  `apps/android/local.properties`, `ANDROID_HOME`/`ANDROID_SDK_ROOT` are unset,
  and no SDK exists at the usual locations. `cd apps/android && ./gradlew
  :app:compileDebugKotlin` (with network so the Android Gradle Plugin 8.7.3
  resolved) failed **purely** with:

  > SDK location not found. Define a valid SDK location with an `ANDROID_HOME`
  > environment variable or by setting the `sdk.dir` path in your project's
  > `local.properties` …

  i.e. the failure is the missing SDK, **not** a code error. Per the grain
  instructions, this is the documented "do not block" case.
- **Full compilation + `./gradlew testDebugUnitTest --tests "*designsystem*"`
  are therefore deferred to CI**, where the Android SDK is provisioned. The
  full repo test suite was intentionally **not** run (unrelated flaky
  `AvatarPickerViewModelTest`).
- **Manual self-review performed** (compensating for the missing SDK):
  - Every `Jarvis*` color reference (13 of them) confirmed to resolve to a
    `val` in `ui/theme/Color.kt`; no brand color redefined.
  - Every `JarvisTokens.*` reference (10) confirmed present in
    `ui/theme/Tokens.kt`; `JarvisPrimeTheme` confirmed in `Theme.kt`.
  - Compose draw/gradient/card/button APIs cross-checked against patterns that
    already compile in the repo (`JarvisLivingAvatar.kt`'s `drawArc` /
    `Brush.radialGradient(colors, center, radius)`; `SeriousActionCard.kt`'s
    `Card(colors, border)`; `PixelSpriteAvatar.kt`'s `tween` usage).
  - Tests mirror the existing Robolectric harness exactly
    (`RobolectricTestRunner`, `@GraphicsMode(NATIVE)`, `@Config(sdk = [33])`,
    `createComposeRule()`, `onNodeWithText` / `assertIsDisplayed`); the
    canvas-only tests add the core `testTag` / `onNodeWithTag` /
    `assertExists` APIs (part of the same `ui-test-junit4` artifact).
  - Unused-import scan: clean (the lone `getValue` flag is the `by`-delegate
    import, used implicitly — same as the existing avatar files).

## Residual risks

1. **Compilation unverified locally** (Android SDK absent). Mitigated by the
   self-review above; CI is the gate. Highest-risk surface is `MuseGlyph`'s
   arc geometry — it will *compile* for certain (APIs match repo usage); the
   exact gap angle / bloom radii are visual-tuning knobs, not correctness.
2. **`@Preview` in `main`** relies on `ui-tooling-preview` being on the
   `implementation` classpath — confirmed in `apps/android/app/build.gradle.kts`
   (line 144) and the Android `libs.versions.toml`. Safe.
3. **Robolectric NATIVE canvas render** of the gallery (a scrolling column of
   canvases) is heavier than the existing single-screen smoke tests; if CI
   flags flakiness, the gallery test can be narrowed to individual components
   (the per-component tests already cover them).
4. **Not yet wired into any screen** — by design (G0.3 ships the library only;
   adoption is a separate grain). No existing file was touched, so default
   runtime behavior is byte-for-byte unchanged.
