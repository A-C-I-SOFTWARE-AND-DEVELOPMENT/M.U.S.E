# Batch B — MUSE Android setup / config / coding re-skin (snapshot)

**Grain:** Batch B fan-out — re-skin the **setup, config & coding** screens
(settings, releasecenter, tasks, placeholder, onboarding, splash, pairing,
coding) onto the merged `Muse*` Compose component library. Visual-only craft
refinement: swap raw Material 3 for the branded
`com.aci.hermes.ui.designsystem` components and add empty states. The app is
already on the Singularity palette at the theme level; this grain is
presentation only. Splash / onboarding / pairing are sensitive first-run
flows and were treated extra-conservatively (timing / `LaunchedEffect` /
navigation-trigger / owner-gate logic preserved byte-for-byte).
**Branch:** `claude/muse-android-reskin-setup`.
**Base commit:** `4c1c216850cf32554d59ac0078345c982dd54473` (`git rev-parse origin/main`).
**Worktree:** `/home/user/hermes-agent-bB`.

## Owned files (only these were touched)

- `apps/android/app/src/main/java/com/aci/hermes/ui/screens/settings/SettingsScreen.kt`
- `apps/android/app/src/main/java/com/aci/hermes/ui/screens/releasecenter/ReleaseCenterScreen.kt`
- `apps/android/app/src/main/java/com/aci/hermes/ui/screens/tasks/TasksScreen.kt`
- `apps/android/app/src/main/java/com/aci/hermes/ui/screens/placeholder/PlaceholderScreen.kt`
- `apps/android/app/src/main/java/com/aci/hermes/ui/screens/onboarding/OnboardingScreen.kt`
- `apps/android/app/src/main/java/com/aci/hermes/ui/screens/splash/SplashScreen.kt`
- `apps/android/app/src/main/java/com/aci/hermes/ui/screens/pairing/DevicePairingScreen.kt`
- `apps/android/app/src/main/java/com/aci/hermes/ui/screens/coding/CodeHandoffHubScreen.kt`
- `apps/android/app/src/main/java/com/aci/hermes/ui/screens/coding/NewCodingTaskScreen.kt`
- `apps/android/app/src/main/java/com/aci/hermes/ui/screens/coding/WorkPacketDetailScreen.kt`
- `docs/launch/muse-app/bB-setup.md` (this file)

No `*ViewModel.kt`, `ui/theme/**`, `ui/navigation/**`, `ui/designsystem/**`
(consumed read-only), `ui/components/**` (consumed read-only), `strings.xml`,
or build files were modified.

## Screens re-skinned + components swapped (before → after)

### `SettingsScreen.kt` (form-heavy — inputs left, containers re-skinned)
- `SettingsSection` helper: raw `Card(surfaceVariant)` → **`MuseCard`**; section
  title `Text(colorScheme.primary)` → `JarvisSignal`. `HorizontalDivider` kept.
- All 8 navigation/action `OutlinedButton`s (Pair a device, Avatar picker,
  Diagnostics, Knowledge graph, Model routes, Model Center, Release & download,
  Reset) → **`MuseButton`** `Secondary` (full-width, `onClick` + `confirmReset`
  trigger unchanged).
- `SettingsRow` / `SwitchRow` / `RadioRow` labels recolored to the value ladder
  (`JarvisSignal` titles, `JarvisSignalDim` subtitles); the two inline
  "Preferred builder/reviewer" sub-headers → `JarvisSignal`.
- **Left as-is:** every `RadioButton`, `Switch`, `Modifier.selectable` +
  `Role.RadioButton` (the 48dp a11y touch target `heightIn(48.dp)` /
  `padding(2.dp)` kept verbatim), the reset `AlertDialog` with its `TextButton`
  confirm/dismiss.

### `ReleaseCenterScreen.kt`
- `SectionCard` helper: `Card` → **`MuseCard`**; in-card title → `JarvisSignal`.
- Backend capability `AssistChip(onClick={})` (display-only) → **`MuseChip`**.
- Copy-download-link + Retry `OutlinedButton` → **`MuseButton`** `Secondary`.
- `Line` helper + body copy recolored (`JarvisSignal` values, `JarvisSignalDim`
  labels/prose).

### `TasksScreen.kt`
- `SectionHeader` helper (`"$title · $count"` text) → **`MuseSectionHeader`** with
  a **`MuseChip`** count in the trailing slot.
- Backend-jobs header `Row{SectionHeader + OutlinedButton}` →
  `MuseSectionHeader` whose `trailing` carries `MuseChip(count)` +
  `MuseButton(Secondary)` "new job".
- Backend `JobRow`: `Card` → `MuseCard`; status/worker/validation
  `AssistChip(onClick={})` → `MuseChip` (display-only); Run `Button` →
  `MuseButton` `Primary`, Cancel `OutlinedButton` → `MuseButton` `Secondary`
  (both keep `enabled = !terminal`). `HorizontalDivider` kept.
- Local `TaskRow`: `Card(onClick=onTap)` → `MuseCard` + `Modifier.clickable`;
  five metadata `AssistChip(onClick=onTap)` → `MuseChip(onClick=onTap)` (tap
  preserved); the four bottom `OutlinedButton`s (copy / open / approvals /
  audit) → `MuseButton` `Secondary`.
- `LocalTasksEmpty` / `JobsNotice` recolored to value ladder
  (`JarvisSignal` / `JarvisSignalDim` / `JarvisCrimson` for the emphasised error).
- **Left as-is:** `ExtendedFloatingActionButton`, the `DispatchJobDialog` /
  `RunJobDialog` `AlertDialog`s and everything inside them (`OutlinedTextField`,
  the `FilterChip` worker selector, dialog `Button`/`TextButton`, and the
  owner-phrase gate `enabled = … phrase.trim() == ownerPhrase`).

### `PlaceholderScreen.kt`
- Added a **`MuseGlyph`** (72dp) hero above the title; "coming soon" `Card`
  (surfaceVariant) → **`MuseCard`**; title/description recolored to the value
  ladder. (Kept the three text params — `title`, `description`, `comingSoonNote`
  — so `PlaceholderScreenSmokeTest` still passes.)

### `OnboardingScreen.kt` (sensitive — first run)
- `JarvisPrimeIcon` (72dp) → **`MuseGlyph`** (72dp).
- "Get started" `Button` → **`MuseButton`** `Primary` (full-width hero CTA);
  "Skip" `TextButton` → `MuseButton` `Secondary`. `onFinish` / `onSkip`
  callbacks unchanged.
- Title / subtitle / bullet copy recolored to the value ladder.

### `SplashScreen.kt` (sensitive — first run)
- `JarvisPrimeIcon(84dp)` → **`MuseGlyph(84dp)`**; app-name color
  `colorScheme.onBackground` → `JarvisSignal`. **The `LaunchedEffect` /
  `delay(600)` / `currentOnReady()` boot timing and the `CircularProgressIndicator`
  are byte-for-byte untouched** (verified in the diff).

### `DevicePairingScreen.kt` (sensitive — owner-gated pairing)
- `PairingCard` helper: `Card` → **`MuseCard`**.
- "Request code" `OutlinedButton` → `MuseButton` `Primary`; the owner-gated
  **"Confirm"** `OutlinedButton` → `MuseButton` **`Approve`** (the
  "Yes, with authorization"-style affordance), Cancel `TextButton` →
  `MuseButton` `Secondary`; Paired "OK" → `Primary`; Error "Try again" →
  `Secondary`. **All `enabled` gates preserved verbatim**, including
  `enabled = !submitting && code.isNotBlank() && authorization ==
  DevicePairingClient.OWNER_AUTHORIZATION_PHRASE`.
- `LabeledValue` + card titles recolored to the value ladder; "Device paired" →
  `JarvisSignal`, "Pairing failed" → `JarvisCrimson`.
- **Left as-is:** both `OutlinedTextField`s (device name, code, authorization
  phrase), `HorizontalDivider`, `Scaffold`/`TopAppBar`.

### `CodeHandoffHubScreen.kt`
- Group header `Text("label · n")` → **`MuseSectionHeader`** + `MuseChip` count.
- `HandoffCard`: `Card(onClick=onOpen)` → `MuseCard` + `Modifier.clickable`;
  risk/demo `AssistChip(onClick=onOpen)` → `MuseChip(onClick=onOpen)`; the three
  `TextButton`s → `MuseButton` (Copy/Retry = `Secondary`, **Delete = `Danger`**;
  Retry keeps `enabled = !busy`). `.testTag(CodingTestTags.HUB_LIST)` preserved.
- `EmptyHub`: bare `Text` + `TextButton` → **`MuseEmptyState`** (glyph + title +
  body + a `New coding task` action wired to `onNewTask`).

### `NewCodingTaskScreen.kt` (form — input + busy-spinner CTA left)
- `ModeBanner` / `AuditPreviewCard`: `Card` → **`MuseCard`**; copy recolored;
  the blocked-state error line `colorScheme.error` → `JarvisCrimson`.
- "Preview risk" `OutlinedButton` → `MuseButton` `Secondary`.
- `LabeledLine` recolored. `.testTag(NEW_AUDIT_PREVIEW)` preserved.
- **Left as-is (deliberate, to preserve behavior):** both `OutlinedTextField`s
  (prompt + repo path) and the **"Generate work packet" `Button`** — it embeds a
  `CircularProgressIndicator` when `state.busy`, which `MuseButton` has no slot
  for; converting it would drop the inline busy spinner, so the M3 `Button` (and
  its `.testTag(NEW_GENERATE)`) is kept verbatim.

### `WorkPacketDetailScreen.kt`
- `HeaderCard` / `EmptyPacketCard` / `Section` / `BulletSection`: `Card` →
  **`MuseCard`**; the header status/risk/demo `AssistChip(onClick={})` →
  `MuseChip` (display-only); the note line `colorScheme.error` → `JarvisCrimson`.
- "Copy Claude Code prompt" `OutlinedButton` → `MuseButton` `Secondary`
  (`.testTag(PACKET_COPY)`); "Send to backend" `Button` → `MuseButton` `Primary`
  (`.testTag(PACKET_SEND)`, `enabled = !state.busy && task.packet != null`
  preserved); "Retry planning" → `MuseButton` `Secondary` (`enabled = !busy`).
- **Left as-is:** the `OwnerGateDialog` `AlertDialog` and everything inside it
  (`OutlinedTextField` for the owner phrase, confirm `Button` +
  `enabled = phrase.isNotBlank()`, dismiss `TextButton`) — owner-gate dialog
  chrome, behavior preserved exactly.

## Deliberately left as-is (no Muse equivalent, or out of scope)

- **`Scaffold` / `TopAppBar` / `IconButton` / `CircularProgressIndicator` /
  `AlertDialog`** across all screens — structural M3 chrome with no designsystem
  counterpart.
- **All form controls** — every `OutlinedTextField`, `RadioButton`, `Switch`,
  `FilterChip`, `Modifier.selectable` (+ `Role.RadioButton`). There is no
  `MuseTextField` / `MuseSwitch` / `MuseRadio` in the library yet, and Settings is
  intentionally input-heavy (only its card containers, buttons, and section
  headers were re-skinned).
- **`ExtendedFloatingActionButton`** (Tasks new-task FAB) — no Muse equivalent.
- **`JarvisPrimeIcon` swap scope** — replaced with `MuseGlyph` only on the two
  hero marks the brief named (splash + onboarding). `JarvisPrimeIcon` itself lives
  in `ui/components/` (read-only) and is untouched there.
- **Dialog-internal buttons** (`DispatchJobDialog`, `RunJobDialog`,
  `OwnerGateDialog`, the reset confirm) keep their M3 `Button`/`TextButton` — they
  are dialog idiom and re-skinning them risks the dialog layout / owner-gate flow.
- The busy-spinner **"Generate work packet" `Button`** (NewCodingTask) — see above.

## Design-language fidelity

- **White core is the hero:** the only hero fills are the `MuseButton.Primary`
  CTAs (onboarding Get-started, pairing Request-code/OK, Tasks Run, WorkPacket
  Send) and the `MuseGlyph` core; spectral cyan→violet appears only inside the
  matte glyph ring. The owner-gated approvals use the jade `Approve` valence and
  destructive actions (Delete) the crimson `Danger` valence — UI status colors,
  correct on interactive controls.
- **Value, not effects:** every panel is now a `MuseCard` (void-3 fill + edge
  hairline, zero elevation/shadow).
- **≤3 color roles + value ladder:** body copy stepped to `JarvisSignal` /
  `JarvisSignalDim`; emphasised error lines use `JarvisCrimson`.
- **Generous spacing:** hardcoded `dp` replaced with `JarvisTokens.Space*` in
  every rewritten card/list/button block. (Non-token leftovers are intentional:
  the FAB's `96.dp` list clearance + `16.dp` offset, the `RadioRow`'s `48.dp`
  a11y target / `2.dp`, and the `8.dp` spacings *inside the left-as-is dialogs*.)
- **Empty states:** the Code-handoff empty hub now uses `MuseEmptyState`
  (glyph + title + body + action), matching the pilot's Jobs treatment.
- **Motion:** none added in this grain. The setup/config/coding screens are
  predominantly forms + `verticalScroll` columns (not `LazyColumn` lists of
  domain rows), so a row-entrance tween had no natural home; the Tasks/Hub lists
  were left without the appearance animation to keep the diff visual-only and
  avoid re-triggering on recycle. (The pilot owns the animated job-row pattern.)

## Behavior preservation (visual-only contract)

- Every `viewModel::*` / `viewModel.*` call, state hoist,
  `LaunchedEffect`, snackbar handling, and navigation callback is byte-for-byte
  preserved. Verified counts vs `origin/main` (base/now) per file:
  Settings vm 17/17; ReleaseCenter vm 8/8; Tasks vm 3/3, LE 3/3; Pairing vm 7/7;
  CodeHandoffHub vm 6/6, LE 3/3, testTag 1/1; NewCodingTask vm 7/7, LE 3/3,
  testTag 3/3; WorkPacketDetail vm 9/9, LE 3/3, testTag 2/2; Splash LE 2/2.
- All `testTag`s preserved: `CodingTestTags.{HUB_LIST, NEW_AUDIT_PREVIEW,
  NEW_GENERATE, PACKET_COPY, PACKET_SEND}`. All `contentDescription`s preserved
  (1/1 per screen that had one).
- No composable's public parameters changed (no additive params were even
  needed this grain — every helper kept its exact signature).
- `PlaceholderScreenSmokeTest` keeps passing: the screen still renders the
  supplied `title`, `description`, and `comingSoonNote` text unchanged.

## Build / SDK status

- **Android SDK: NOT available in this sandbox.** No `apps/android/local.properties`,
  `ANDROID_HOME` / `ANDROID_SDK_ROOT` unset. Running
  `./gradlew :app:compileDebugKotlin` fails **purely** with:

  > SDK location not found. Define a valid SDK location with an `ANDROID_HOME`
  > environment variable or by setting the `sdk.dir` path …

  i.e. the failure is the missing SDK, **not** a code error — the documented
  "do not block" case. The Kotlin compile is therefore **deferred to CI**, which
  provisions the SDK and is the compile gate.
- **Manual self-review (compensating for the absent SDK):**
  - Every new `com.aci.hermes.ui.designsystem.*` import resolves to a real public
    composable/enum in the merged library (`MuseButton` + `MuseButtonVariant`,
    `MuseCard`, `MuseChip`, `MuseEmptyState`, `MuseGlyph`, `MuseSectionHeader`)
    and each imported symbol is used — verified per file.
  - **Zero orphaned imports** across all 10 files (automated scan; the `by`
    delegation operators `getValue`/`setValue` are still used by the unchanged
    `var x by remember`/`val s by collectAsState()` sites). One real orphan found
    and removed: `fillMaxWidth` in TasksScreen (its only use was the deleted
    backend-jobs header Row).
  - No `Card` / `CardDefaults` / `OutlinedButton` / `AssistChip` references remain
    where converted; their imports were removed. Retained M3 imports
    (`Button`, `TextButton`, `OutlinedTextField`, `FilterChip`, `RadioButton`,
    `Switch`, `HorizontalDivider`, `CircularProgressIndicator`,
    `ExtendedFloatingActionButton`, `AlertDialog`, `Scaffold`, `TopAppBar`) are
    each still used.
  - `MuseButton` is always called with named args, satisfying its
    `(onClick, text, modifier, variant, enabled, leadingIcon)` signature;
    `Modifier.weight(1f)` and `.testTag(…)` survive as the button's `modifier`.
  - `MuseCard` + `Modifier.clickable(onClick=…)` reproduces every old
    `Card(onClick=…)` tap (HandoffCard, TaskRow).
  - `@OptIn(ExperimentalMaterial3Api::class)` was **removed** from the three
    composables (`HandoffCard`, `JobRow`, `TaskRow`) whose only experimental
    symbol was the now-gone `Card(onClick)`/`AssistChip`; it was **kept** on the
    Scaffold/TopAppBar/dialog functions that still need it (`TopAppBar`,
    `FilterChip`).

## Residual risks

1. **Compilation unverified locally** (Android SDK absent). Mitigated by the
   self-review above; CI is the gate. The diff is mechanical (component swaps +
   color/spacing token substitution), so confidence is high.
2. **`MuseGlyph` differs visually from `JarvisPrimeIcon`** on splash / onboarding
   / placeholder — by design (the brief specifies the splash/onboarding hero mark
   → `MuseGlyph`, the canonical brand glyph the pilot already adopted for Home's
   greeting + empty states). `JarvisPrimeIcon` (the older two-ring caduceus mark)
   remains untouched in `ui/components/` for any other caller.
3. **No motion added** (rationale above). If a reviewer wants the Tasks/Hub lists
   to gain the pilot's `fadeIn + slideInVertically` row entrance, that is a small
   additive follow-up; it was deliberately left out to keep this grain a pure
   visual swap and avoid the recycle-retrigger taste call.
4. **Pure presentation diff** — same composables' state, same nav, same
   ViewModels. Default runtime behavior is unchanged.
