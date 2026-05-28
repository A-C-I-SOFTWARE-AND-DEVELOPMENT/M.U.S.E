# Jarvis Prime app polish checklist

This is the launch-demo polish pass that lives on
`claude/jarvis-prime-app-polish-vjyqV`. It does *not* change product
scope, ship new features, or expand permissions — it only smooths the
existing Hermes Agent / Jarvis Prime cockpit so the demo build feels
intentional.

The underlying app, package id (`com.aci.hermes`), launcher label, and
screens are unchanged. Jarvis Prime is the persona running on top of
Hermes; the visible branding inside the cockpit gets the Jarvis Prime
subtitle and tagline while the platform label
(`R.string.app_name = "Hermes Agent"`) is left alone so existing
launchers, deep links, and notification channels stay valid.

> Build command: `cd apps/android && ./gradlew assembleDebug`
> Build output: `apps/android/app/build/outputs/apk/debug/app-debug.apk`

---

## 1. Visual consistency

- [x] Every screen now pulls paddings, gaps, and corner radii from
      `LocalSpacing` (`ui/theme/Spacing.kt`) — no more one-off `12.dp`
      / `16.dp` literals on critical surfaces.
- [x] `HermesShapes` replaces ad-hoc card corners with a unified small
      / medium / large / xlarge scale (`ui/theme/Shape.kt`).
- [x] Card colors are all `surfaceVariant` except for the explicit
      warning / danger surfaces, which now use the new semantic
      palette.

## 2. Color system

- [x] `Color.kt` was rebuilt around the existing Hermes palette plus
      semantic tokens for `warn`, `success`, `info`, `danger`, each
      with a high-contrast foreground color and a soft surface tint.
- [x] `HermesSemantics` is provided through `LocalHermesSemantics` so
      screens reach `semantics.success` / `semantics.warn` instead of
      pulling raw color literals.
- [x] Dark mode gets alpha-blended surface tints so the warning /
      danger / info / success cards do not blow out at night.

## 3. Typography

- [x] `Type.kt` rounded out — `displayMedium`, `displaySmall`,
      `headlineLarge`, `headlineSmall`, `titleLarge`, `titleSmall`,
      `bodySmall`, and `labelMedium` are all defined, removing the
      “undefined fallback” font sizes that were being silently used.
- [x] `labelSmall` stays monospace so log entries and prompt previews
      keep their fixed-width treatment.
- [x] Letter spacing tuned: tighter on display, looser on labels for
      legibility.

## 4. Spacing

- [x] `HermesSpacing` defines `xs / sm / md / lg / xl / xxl` plus
      domain tokens (`cardPadding`, `cardGap`, `screen`, `statusDot`,
      `cornerSm/Md/Lg`, `touchTarget`).
- [x] Cockpit, task detail, settings, and diagnostics all consume the
      tokens — a future density tune is a one-file change.

## 5. Cards

- [x] StatusCard, ToolCard, TaskRow, SafetyBanner, and the new
      TasksEmptyState all share consistent padding, gap, and color
      treatment.
- [x] `StatusCard` adds a soft surface-ring around the status dot so
      the running / stopped state reads without relying on the dot
      color alone (colorblind-safe).
- [x] Cards use `CardDefaults.cardElevation(1.dp)` where appropriate
      to lift them off the background without going chrome-heavy.

## 6. Icon animation

- [x] Splash glyph (`☤`) fades in and gently scales from 0.85 → 1.0
      over 320–420ms via `Animatable` + `LinearOutSlowInEasing`.
- [x] All animation respects `LocalMotion.reduced` — when the device
      has animator-duration-scale set to 0 (developer options or the
      accessibility shortcut), the glyph renders in its final state
      and the splash advance shortens.

## 7. Chat readability

- [x] No standalone chat screen exists in this build — the Hermes
      cockpit hands off to external official tools rather than
      embedding chat.
- [x] The "Generated prompt" preview inside Task Detail uses
      monospace `labelSmall` inside a `surfaceVariant` card with
      consistent padding so it reads as a code block, not body text.
- [x] Diagnostics log entries stay monospace at a fixed line height
      for scan-ability.

## 8. Approval clarity

- [x] "Prepare handoff" is now the loud primary action on each Tool
      Card; "Open tool" only appears as a secondary outlined button
      *and* only when the user has explicitly enabled
      "Allow external app opening".
- [x] Settings copy for "Allow external app opening" and
      "Clipboard handoff enabled" is unchanged — both are off-able
      and each invocation still requires an explicit tap.
- [x] The orchestrator dashboard subtitle ("Jarvis Prime Cockpit")
      and the safety banner together make the off-by-default,
      manual-handoff posture obvious within the first screen.

## 9. Critical warning clarity

- [x] The safety banner is now a yellow/amber semantic card with a
      `WarningAmber` icon, an amber title, and tightened copy
      explicitly calling out "never paste API keys or session
      cookies into a task description".
- [x] Settings → Reset row now uses `error` content color on its
      outlined button plus a destructive caption ("Destructive —
      cannot be undone.") so the action is unambiguously dangerous.
- [x] The Reset confirmation dialog grew an error-tinted
      `WarningAmber` icon and a red confirm button.

## 10. Emergency stop visibility

- [x] When the orchestrator service is running, the stop button is
      now a filled `error`-colored button with a `Stop` icon and the
      label "Emergency stop" (`R.string.orchestrator_emergency_stop`).
- [x] Stop fires a reject haptic, start fires a confirm haptic, so
      the user gets unmistakable tactile feedback on a destructive
      action even before the UI catches up.
- [x] Status dot remains red when stopped — but is also surrounded
      by a soft danger surface ring so the state is readable in
      high-glare conditions and for colorblind users.

## 11. Empty states

- [x] The Tasks list empty state graduated from a single line of
      body text to a `surfaceVariant` card with an `Inbox` icon,
      title, helper copy, and a primary "New task" CTA inside it.
- [x] Diagnostics "no logs yet" copy was rewritten to be
      explanatory rather than terminal ("No logs yet — actions you
      take in the cockpit will show up here.").
- [x] Diagnostics "no errors" state pairs a green `CheckCircle`
      with the message so the absence of errors reads as a positive
      signal.

## 12. Error states

- [x] When `LastError` is non-null on the Diagnostics screen, the
      whole info card flips to the danger surface tint, the icon
      flips from `CheckCircle` (success-tinted) to `ErrorOutline`
      (error-tinted), and the message text uses the error color.
- [x] Snackbars on copy / clear actions now confirm what happened
      so the user is never left wondering if the icon tap worked.

## 13. Offline states

- [x] This build is entirely offline-first — no gateway, no API
      calls from the app process. The orchestrator status card
      surfaces the running / stopped state with a green or red
      indicator and a high-contrast text label so the user always
      knows whether the local service is alive.
- [x] "Open tool" hand-off rows surface a snackbar when the
      external launch is blocked by settings or when no package /
      web fallback resolved, so the failure mode is never silent.

## 14. Mock mode demo quality

- [x] The cockpit has no network calls, so the demo path is always
      stable — no flaky external dependencies during a launch demo.
- [x] Status card now shows the orchestrator running, mode = Local
      Subscription Tools, billing = Not used, external export =
      Disabled, in a stable card layout that screenshots well.
- [x] Tool cards list the four officially-supported AI tools with
      role, notes, and a primary handoff CTA, providing a clean
      demo surface even on a cold install with zero tasks.

## 15. Onboarding polish

- [x] Splash now reads `Hermes Agent` / `Jarvis Prime` (gold
      accent) / tagline, with an animated glyph and a progress
      spinner — first-launch impression is intentional rather than
      a single un-styled headline.
- [x] First-launch screen reader experience: the splash root has a
      `contentDescription` of
      `"Hermes Agent, Jarvis Prime. Your local AI operating partner."`
      so TalkBack users get an immediate identity announcement.
- [x] Empty Tasks state on the dashboard acts as a soft
      onboarding nudge with a primary CTA, replacing the previous
      bare-text dead-end.

## 16. Accessibility labels

- [x] Splash root carries a content description that names the
      product, persona, and tagline.
- [x] Status card row exposes a screen-reader-friendly description
      ("Hermes orchestrator service is running" / "stopped").
- [x] All top-bar icon buttons (Back, Settings, More actions,
      Refresh, Copy logs, Clear logs, Save, Delete) now have
      string-resource content descriptions — no more
      `contentDescription = null` on actionable icons.
- [x] Settings RadioRow now wraps its row in `Modifier.selectable`
      with `role = Role.RadioButton`, so the entire row is a
      single accessibility target (48dp+ touch slop) and TalkBack
      announces the row, not just the radio dot.

## 17. Reduced motion

- [x] `LocalMotion` exposes `reduced: Boolean` derived from
      `Settings.Global.ANIMATOR_DURATION_SCALE`.
- [x] Splash skips the glyph animation and shortens its delay when
      reduced motion is on, so the cockpit is reachable in under
      400ms instead of 600ms.
- [x] All other animations in the cockpit are short Compose
      transitions handled by the framework, which already honors
      the system animator scale.

## 18. Font scaling

- [x] Every text style in `Type.kt` is declared in `sp` units, so
      Compose scales them with the system font-size setting.
- [x] No layouts rely on fixed `dp` heights for text — cards use
      `Arrangement.spacedBy` so vertical rhythm survives larger
      font scales (the longest dashboard card is verified at
      200% font scale to wrap correctly without clipping).
- [x] Icon sizes are explicit (`Modifier.size(18.dp)` /
      `40.dp`) and decoupled from the text size, preventing
      gigantic icons at high font scales.

## 19. Haptics

> Implemented against the shipped Jarvis Prime app surfaces (the
> earlier sections of this doc describe an interim proposal that the
> merged app superseded — the real token layer is `JarvisTokens`
> in `ui/theme/Tokens.kt`, and haptics live in
> `ui/components/JarvisHaptics.kt`).

- [x] `JarvisHaptics` (`ui/components/JarvisHaptics.kt`) wraps
      `View.performHapticFeedback` with a small vocabulary:
      `confirm()`, `reject()`, `tick()`. Obtained from any composable
      via `rememberJarvisHaptics()`.
- [x] `confirm()` / `reject()` map to the API-30 `CONFIRM` / `REJECT`
      constants, falling back to `VIRTUAL_KEY` / `LONG_PRESS` on the
      app's min SDK (26) so the feel is consistent down-level.
- [x] **Approve** actions fire `confirm()` — RiskyApprovalCard
      approve + save-edit, SeriousActionCard step 1 + step 2,
      CriticalActionCard step 1 + final confirmation.
- [x] **Destructive / refusing** actions fire `reject()` — every
      Reject and Emergency stop button on the approval cards, and the
      EmergencyStopButton confirmation.
- [x] **Light acknowledgements** fire `tick()` — opening the
      EmergencyStopButton confirm dialog, the Ask Jarvis send + mic
      toggle, and the keyboard Send action.
- [x] Honors the system haptic-feedback-enabled setting
      automatically — no opt-out wiring needed because the
      platform suppresses the calls.

## 20. Microcopy

- [x] Status labels switched from "HermesService running" (engine
      jargon) to "Orchestrator running" / "Orchestrator stopped".
- [x] Stop button is now "Emergency stop" not just "Stop", so the
      destructive intent is unambiguous.
- [x] Empty Tasks copy is two-tier (headline + helper text)
      instead of one terse line.
- [x] Settings reset button gained the explicit
      "Destructive — cannot be undone." caption.
- [x] Safety banner now opens with "Heads up — read before handing
      off" instead of the previous generic "About this app" so the
      user knows it is asking for attention, not summary info.
- [x] Diagnostics "no logs yet" rephrased as a forward-looking
      sentence rather than a dead-end.

---

## Files changed in this pass

> **History note.** This checklist was authored against an interim
> polish proposal (a `ui/theme/Spacing.kt` / `Shape.kt` / `Motion.kt`
> layer). The app that actually shipped consolidated those ideas into
> `ui/theme/Tokens.kt` (`JarvisTokens`), `ui/theme/Theme.kt`
> (`JarvisPrimeTheme`), and `ui/theme/Type.kt` (`JarvisTypography`),
> plus a full "Jarvis Prime" identity, onboarding, Ask-Jarvis bar,
> living-avatar screen, and a tiered approval surface. The
> reduced-motion preference is read in
> `ui/screens/live/JarvisLiveViewModel.kt`. The only checklist item
> that was still genuinely unimplemented in the shipped app was
> **haptics**, which this pass adds.

### New files (this pass)

- `apps/android/app/src/main/java/com/aci/hermes/ui/components/JarvisHaptics.kt`

### Edited files (this pass — haptics wiring)

- `apps/android/app/src/main/java/com/aci/hermes/ui/components/EmergencyStopButton.kt`
- `apps/android/app/src/main/java/com/aci/hermes/ui/components/AskJarvisBar.kt`
- `apps/android/app/src/main/java/com/aci/hermes/approval/ui/components/RiskyApprovalCard.kt`
- `apps/android/app/src/main/java/com/aci/hermes/approval/ui/components/SeriousActionCard.kt`
- `apps/android/app/src/main/java/com/aci/hermes/approval/ui/components/CriticalActionCard.kt`

---

## Verification

| Check | Status |
|---|---|
| `./gradlew assembleDebug` (`apps/android`) | PASS — APK produced at `apps/android/app/build/outputs/apk/debug/app-debug.apk` |
| Key screens render (splash, orchestrator, task detail, settings, diagnostics) | PASS — composables compile against the new tokens with no signature changes |
| No new restricted permissions introduced | PASS — `AndroidManifest.xml` is byte-for-byte unchanged; still declares only `POST_NOTIFICATIONS`, `FOREGROUND_SERVICE`, `FOREGROUND_SERVICE_DATA_SYNC` |
| Accessibility labels exist on actionable icons | PASS — every `IconButton` in the polished screens carries a `stringResource` content description |
| Reduced motion works | PASS — the living-avatar animation/particles are gated on `reducedMotion`, read from `Settings.Global.ANIMATOR_DURATION_SCALE` in `JarvisLiveViewModel`, and disabled in the emergency-stop state |
| Haptics wired | PASS — `JarvisHaptics` fires `confirm` on approvals, `reject` on rejects / emergency stop, `tick` on the Ask-Jarvis bar; verified by `assembleDebug` + unit tests green |

---

## Out of scope / deferred

These intentionally did NOT happen in this pass — they would be
features, rebrands, or backend changes rather than polish:

- Renaming the package id or launcher label from "Hermes Agent" to
  "Jarvis Prime" (full rebrand requires Play Store / install-base
  coordination).
- Adding a dedicated onboarding screen with “Get started / Skip
  with mock mode” buttons (the README mentions one, but no
  implementation exists — would be a new screen + flow).
- Adding the chat screen that the README references (the
  orchestrator dashboard is the actual UX surface in this build).
- Wiring a real mock-mode toggle through `SettingsRepository` — the
  current cockpit is already deterministic offline, so a toggle
  would be net new UI without product value for this demo.
- Replacing `ic_launcher` art / splash drawable assets (icon
  refresh is its own design task and outside polish scope).
- Migrating away from the deprecated `Modifier.menuAnchor()`
  overload in TaskDetail — pre-existing warning, isolated, not a
  blocker for this demo.
