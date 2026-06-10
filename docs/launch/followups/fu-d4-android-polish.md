# FU-D4: Android cockpit polish — Singularity motion, tonal-elevation fix, haptics, empty states (Wave D G4)

- **Status:** in-review (draft PR)
- **Risk class:** behavior-change (UI polish; default visual/motion behavior changes, no logic/data changes) — owner-gated
- **Branch:** `claude/fu-d4-android-polish` · **Base:** `main` @ `e283d39ea` (includes PR #433 persona sweep)
- **PR:** TBD (draft; number recorded after open)
- **Owner-gate required to merge?** yes — changes default runtime UI behavior; awaiting `Yes, with authorization.`

## Intent (one paragraph)

Apple-quality polish on the Android cockpit, strictly inside the Singularity
design language (`docs/brand/muse-design-language.md` §6; `MuseMotion.kt`
tokens; `design-system/tokens.json` consumed, never edited). Before: the
NavHost used the default crossfade for every navigation; the M3
`surfaceTint = JarvisGold` (pure white) washed elevated surfaces grey,
violating the tonal-elevation rule; the top bar sat on `surface` with no
scroll response; tab taps and the emergency-stop entry had no haptic
acknowledgement; empty-state icons floated bare; `displayLarge` was 34sp
against the canonical 40sp display token. After: tab swaps fade through
(standard in / fast out), detail pushes arrive with an emphasized fade + a
1/24-height upward settle and pop with the exact mirror (tweens only — no
springs); `surfaceTint` is transparent in both schemes so the explicit
`surfaceContainer*` ink/paper ladders carry all elevation; the pinned top bar
animates `JarvisInkAbyss → JarvisInkNight` on content scroll and the
NavigationBar is a flat `JarvisInkNight` at 0dp tonal elevation; `tick()`
haptics fire on tab navigation and on opening the e-stop confirm dialog; the
shared `EmptyState` icon sits in a 64dp matte ring (1dp `JarvisInkEdge`
hairline, no glow, no shadow); `displayLarge` is 40/600/-0.5/48 per
`tokens.json`; the design-system gallery gains a "Motion + EmptyState"
section documenting the motion spec and showing the new treatment.

## Owned files (the ONLY files this task may write)

- `apps/android/app/src/main/java/com/aci/hermes/ui/navigation/HermesNavGraph.kt`
- `apps/android/app/src/main/java/com/aci/hermes/ui/navigation/JarvisShell.kt`
- `apps/android/app/src/main/java/com/aci/hermes/ui/theme/Theme.kt`
- `apps/android/app/src/main/java/com/aci/hermes/ui/theme/Type.kt`
- `apps/android/app/src/main/java/com/aci/hermes/ui/components/EmptyState.kt`
- `apps/android/app/src/main/java/com/aci/hermes/ui/designsystem/DesignSystemGallery.kt`
- `docs/launch/followups/fu-d4-android-polish.md` (this snapshot)

> Disjoint from every other in-flight Wave-D task per the ledger ownership
> map. No collisions discovered mid-flight.

## What changed, item by item

1. **NavHost motion** (`HermesNavGraph.kt`): `NavHost` now declares
   `enterTransition` / `exitTransition` / `popEnterTransition` /
   `popExitTransition`. Top-level routes (`Screen.shellRoutes` + Splash +
   Onboarding + JarvisLive) fade through: `fadeIn(MuseMotion.standard())` in,
   `fadeOut(MuseMotion.fast())` out. Everything else is a detail push:
   `fadeIn(MuseMotion.emphasized()) + slideInVertically(emphasized) { it / 24 }`,
   popped with the mirror (`fadeOut(emphasized) + slideOutVertically(emphasized)
   { it / 24 }`). Tweens only — no springs.
2. **Tonal-elevation fix** (`Theme.kt`): dark scheme `surfaceTint` JarvisGold
   (pure white, caused the grey M3 elevation wash) → `Color.Transparent`. The
   light scheme had the same class of bug (`JarvisGoldDeep` tint over an
   explicit paper ladder) → also `Color.Transparent`. The explicit
   `surfaceContainer*` ladders carry all elevation, per the brand rule
   "value, not effects".
3. **Shell chrome** (`JarvisShell.kt`): `TopAppBarDefaults.pinnedScrollBehavior()`
   wired through `Scaffold(modifier = Modifier.nestedScroll(...))` with
   `containerColor = JarvisInkAbyss`, `scrolledContainerColor = JarvisInkNight`
   (M3 animates between them on content scroll). `NavigationBar(containerColor =
   JarvisInkNight, tonalElevation = 0.dp)`.
4. **Haptics** (`JarvisShell.kt`): `rememberJarvisHaptics().tick()` on
   bottom-tab navigation (unselected taps only) and on opening the
   emergency-stop confirm dialog. The e-stop dialog lives inside JarvisShell
   (an owned file), so both haptics landed — no deviation needed.
5. **EmptyState ring** (`EmptyState.kt`): the 48dp icon now sits centered in a
   64dp `Box` with a 1dp `JarvisInkEdge` `CircleShape` border — matte ring,
   no glow, no shadow.
6. **Type scale** (`Type.kt`): `displayLarge` 34sp/42sp → **40sp/48sp**
   (canonical `tokens.json` display 40/600/-0.5/48). Weight and tracking were
   already correct; only that one style touched.
7. **Gallery** (`DesignSystemGallery.kt`): new "Motion + EmptyState" section —
   a `MuseCard` textual spec card quoting the `MuseMotion` durations, plus the
   shared `EmptyState` rendered with the new ring treatment.

## Deviations from the work order

- Item 2: the light scheme's `surfaceTint = JarvisGoldDeep` was judged the
  same bug (a tint stacked on an explicit container ladder) and set to
  `Color.Transparent` as the work order's "check the light scheme" directed.
- Item 1: `JarvisLive` (the Den) and the pre-shell flow (Splash, Onboarding)
  are classified as top-level fade-through rather than detail pushes — the
  Den is documented in-code as "the home", so sliding it in like a detail
  sheet would misread its role. Everything else not in `shellRoutes` (TaskDetail,
  JobDetail, ModelCenter, Settings, Diagnostics, Voice, …) is a push.
- No other deviations; `design-system/tokens.json` untouched (FROZEN).

## Validation (CI-verified posture, same as FU-17)

No Android SDK is available locally, so the gate is compile-correctness by
careful reading plus CI:

- All animation symbols imported from `androidx.compose.animation.*`
  (`EnterTransition`, `ExitTransition`, `fadeIn`, `fadeOut`,
  `slideInVertically`, `slideOutVertically`); navigation-compose is 2.8.5
  (NavHost transition params available since 2.7.0).
- Referenced symbols grep-verified: `Screen.shellRoutes`,
  `rememberJarvisHaptics` / `tick()`, `JarvisInkAbyss` / `JarvisInkNight` /
  `JarvisInkEdge` (Color.kt), `MuseMotion.fast/standard/emphasized` +
  `Duration*` constants, `MuseCard(modifier, content)`,
  `MuseSectionHeader(title, modifier, subtitle, trailing)`,
  `TopAppBarDefaults.pinnedScrollBehavior` (file already
  `@OptIn(ExperimentalMaterial3Api::class)`).
- No unit test references `displayLarge` or `surfaceTint` (grep over
  `apps/android/app/src/test`).
- `python3 scripts/scan_secrets.py --base origin/main` → exit 0
  ("ok: no high-confidence secrets").
- **CI lanes that are the merge gate:** *Build debug APK* (`assembleDebug`),
  *Lint* (`gradlew lint`), *Android JVM unit* (`testDebugUnitTest`) — all in
  `.github/workflows/android-build.yml`.

## Residual / follow-on

- Per-call-site reduced-motion handling (MuseMotion documents that policy
  belongs at the call site); NavHost transitions currently don't read the
  system animator-scale preference (the platform scales Compose animations
  globally when animations are disabled, so this is acceptable).
- `MuseEmptyState` (designsystem) keeps its own treatment; only the shared
  `ui/components/EmptyState.kt` gained the ring, per file ownership. Unifying
  the two empty-state components is a candidate follow-up.
- The e-stop *confirm* action could use `haptics.reject()` (destructive
  vocabulary) — out of scope here; only the dialog-open `tick()` was in the
  work order.
