# Batch B — MUSE Android control & model re-skin (snapshot)

**Grain:** Batch B fan-out — re-skin the **control & model** Android screens
(control, devicecontrol, diagnostics, capability, model, modelroute) onto the
merged `Muse*` Compose component library. Visual-only craft refinement: swap raw
Material 3 for the branded `com.aci.hermes.ui.designsystem` components and add
empty states + tasteful motion. The app is already on the Singularity palette at
the theme level; this grain is presentation only. No ViewModel call, state hoist,
nav callback, test tag, or content description was changed.
**Branch:** `claude/muse-android-reskin-control`.
**Base commit:** `4c1c216850cf32554d59ac0078345c982dd54473` (`git rev-parse origin/main`).
**Worktree:** `/home/user/hermes-agent` (branch cut from `origin/main`).

## Owned files (only these were touched)

- `apps/android/app/src/main/java/com/aci/hermes/ui/screens/control/ControlScreen.kt`
- `apps/android/app/src/main/java/com/aci/hermes/ui/screens/devicecontrol/DeviceControlScreen.kt`
- `apps/android/app/src/main/java/com/aci/hermes/ui/screens/diagnostics/DiagnosticsScreen.kt`
- `apps/android/app/src/main/java/com/aci/hermes/ui/screens/capability/CapabilityScreen.kt`
- `apps/android/app/src/main/java/com/aci/hermes/ui/screens/model/ModelCenterScreen.kt`
- `apps/android/app/src/main/java/com/aci/hermes/ui/screens/modelroute/ModelRouteScreen.kt`
- `docs/launch/muse-app/bB-control.md` (this file)

No `*ViewModel.kt`, `ui/theme/**`, `ui/navigation/**`, `ui/designsystem/**`
(consumed read-only), `ui/components/**` (consumed read-only), `strings.xml`, or
build files were modified. The sibling helper files `control/AutonomyControlSection.kt`
and `capability/SkillCard.kt` are **out of owned scope** and were left byte-for-byte
unchanged (their call sites in the owned screens are preserved exactly).

## Screens re-skinned + components swapped (before → after)

### `ControlScreen.kt`
- Service card, device-control card, emergency-stop card: raw `Card`
  (surfaceVariant / errorContainer) → **`MuseCard`**.
- Service-state `Surface(CircleShape)` dot → **`MuseStatusDot`** (`Ok` running,
  `Off` stopped).
- Card titles `Text(titleMedium, primary)` → **`MuseSectionHeader`**.
- Start `Button` → **`MuseButton`** `Primary`; stop `OutlinedButton` →
  **`MuseButton`** `Secondary` (both kept always-present with their original
  `enabled = !running` / `enabled = running` gates — *not* collapsed to a single
  button). Device-control-open `Button` → `MuseButton` `Primary` (full-width).
- Emergency-stop `Button(error)` with inline `PowerSettingsNew` `Icon` →
  **`MuseButton`** `Danger` with `leadingIcon = Icons.Filled.PowerSettingsNew`
  (the built-in icon/label spacing replaces the manual `Modifier.padding(start=8.dp)`).
  Still raises `confirmStop = true`; the confirm `AlertDialog` flow (which calls
  `onEmergencyStop()` + `controlViewModel?.emergencyStopNow()`) is untouched.
- The `AutonomyControlSection(...)` call (its own file) is unchanged.
- Hardcoded `16.dp`/`8.dp` → `JarvisTokens.Space*`.

### `DeviceControlScreen.kt`
- Pending-approval actions inside the `CommandCard`: `Button` "Approve" →
  **`MuseButton`** `Approve` (owner-gate valence); `OutlinedButton` "Dismiss" →
  **`MuseButton`** `Secondary`. Both keep `Modifier.weight(1f)`.
- Emergency-stop "Request resume" `OutlinedButton` → **`MuseButton`** `Secondary`.
- `ActiveIndicator` `Surface(CircleShape)` dot → **`MuseStatusDot`** (`Live` when
  active, `Off` when halted/idle — the label text still distinguishes halted vs
  idle). `CapabilityRow` granted dot → `MuseStatusDot` (`Ok`/`Off`).
- Hardcoded `16.dp`/`8.dp`/`4.dp`/`2.dp` → `JarvisTokens.Space*` in rewritten rows.

### `DiagnosticsScreen.kt`
- `DiagInfoCard`, `BackendReadinessCard`, `RecentSessionsCard`, `LogsCard`: raw
  `Card` (surfaceVariant / errorContainer) → **`MuseCard`**.
- Card titles `Text(titleMedium/primary)` → **`MuseSectionHeader`**.
- Hardcoded `16.dp`/`12.dp`/`8.dp`/`6.dp` → `JarvisTokens.Space*`.

### `CapabilityScreen.kt`
- `HeaderBlurb`, `InstalledSkillsCard`, and the `InvocationSheet` staged-prompt
  card: raw `Card` (surfaceVariant / surface) → **`MuseCard`**.
- `CategoryFilters`: `FilterChip` (the "All" + per-category selection chips) →
  **`MuseChip`** (`selected` + `onClick` preserved 1:1 — `MuseChip` carries the
  selected/core-fill treatment natively).
- Card / sheet titles `Text(titleSmall, primary)` → **`MuseSectionHeader`**.
- `CapabilityList` empty state: bare centered `Text(capability_empty)` →
  **`MuseEmptyState`** (glyph + title + the existing body string).
- `InvocationSheet` actions: stage-prompt `Button` → **`MuseButton`** `Primary`;
  close `OutlinedButton` → **`MuseButton`** `Secondary`.
- Hardcoded `16.dp`/`24.dp`/`8.dp`/`4.dp` → `JarvisTokens.Space*`.
- `SkillCard(...)` rows are rendered via the **separate `SkillCard.kt`** file
  (out of scope) — the call is unchanged.

### `ModelCenterScreen.kt`
- `UnavailableCard`, `RuntimeCard`, `ModelCard`, `PromotionsCard`, `RuntimesCard`:
  raw `Card` (surfaceVariant) → **`MuseCard`**.
- `AssistChip(onClick = {})` display-only status labels (runtime label, per-model
  status label) → **`MuseChip`** (display-only, no `onClick`).
- "Installed models" / "Route by task (local tier)" list-section `Text(titleSmall)`
  → **`MuseSectionHeader`**.
- No-models-installed list item: bare `Text` (two message variants) →
  **`MuseEmptyState`** (the reachable / unreachable strings become the body).
- "Run smoke test" `OutlinedButton` → **`MuseButton`** `Secondary`
  (`enabled = !busy` preserved).
- `ModelCard` rows wrapped in **`AnimatedVisibility`** (`fadeIn + slideInVertically`
  on `MuseMotion.standard()`) — the same subtle list-row entrance as `JobsScreen`.
- Hardcoded `16.dp`/`10.dp`/`8.dp`/`4.dp` → `JarvisTokens.Space*`.

### `ModelRouteScreen.kt`
- `PaidRoutingCard`, `RouteCard`: raw `Card` (surfaceVariant) → **`MuseCard`**.
- The `local_first` `AssistChip(enabled=false)` → **`MuseChip`**, hoisted into the
  **`MuseSectionHeader`** `trailing` slot alongside the `taskClass` title (replaces
  the manual `Row(SpaceBetween)` title+chip).
- "Owner override" `Text(titleSmall)` → **`MuseSectionHeader`**.
- Override-save `OutlinedButton` → **`MuseButton`** `Primary`
  (`enabled = pin.isNotBlank()`); override-clear `TextButton` → **`MuseButton`**
  `Secondary` (`enabled = decision.isOverridden`). Both still flow through
  `onPin(pin)` / `pin = ""; onClear()`.
- Not-paired state: bare `Text(model_route_not_paired)` → **`MuseEmptyState`**.
- `RouteCard` rows wrapped in **`AnimatedVisibility`** (`MuseMotion.standard()`).
- Hardcoded `16.dp`/`12.dp`/`8.dp`/`4.dp`/`2.dp` → `JarvisTokens.Space*`.

## Deliberately left as-is (no Muse equivalent, or signal-preserving)

- **`Scaffold` / `TopAppBar` / `IconButton` / `AlertDialog`** chrome across all
  screens — structural M3 with no designsystem counterpart. Their `TextButton`
  actions inside dialogs are kept (dialog idiom).
- **`OutlinedTextField`** (Capability search, ModelRoute override + paid-auth
  phrase) and **`Switch`** (DeviceControl toggles, Capability advanced toggle,
  ModelRoute paid switch) — form controls; no `MuseTextField` / `MuseSwitch`
  in the library yet.
- **`CommandCard`** + **`EmergencyStopButton`** (shared `ui/components`, DeviceControl)
  — already-branded shared components; consumed unchanged.
- **`SkillCard.kt`** and **`AutonomyControlSection.kt`** — sibling files outside
  owned scope; untouched.
- **`OwnerGatedBanner`** (CapabilityScreen) kept as a raw `Card(errorContainer)`:
  the red container *is* the owner-gate warning signal (no icon carries it
  otherwise) and it has the `contentDescription = "Owner-gated warning"` a11y hook.
  `MuseCard` has no danger fill, so converting it would silently drop the warning
  valence — preserved instead.
- **`ActionLogRow` outcome dot** (DeviceControl) kept as a tinted
  `Surface(CircleShape)`: it encodes **three** distinct outcome colors
  (ok / needs-confirmation / error). `MuseStatusDot`'s vocabulary
  (`Off`/`Ok`/`Live`/`Connecting`) can't express all three without collapsing the
  blocked-vs-needs-confirmation signal, so it was preserved.
- The `@OptIn(ExperimentalMaterial3Api::class)` annotations that remain
  (ModelCenter/Capability/ModelRoute top-level, for `Scaffold`/`TopAppBar`/
  `ModalBottomSheet`) are still required by surviving experimental APIs.

## Design-language fidelity

- **White core is the hero**: the only hero fills are the `MuseButton.Primary`
  CTAs (one per surface) and the `MuseEmptyState` glyph core; spectral cyan→violet
  appears only inside the matte glyph ring and the cyan/jade `MuseStatusDot`.
- **Valence on the control, not the label**: emergency-stop = `Danger`; owner-gate
  approve = `Approve`; quiet/cancel = `Secondary` — directly mirroring the pilot's
  `EmergencyStopButton` and Job-Detail `ControlButton`.
- **Value, not effects**: every converted panel is a `MuseCard` (void-3 fill + edge
  hairline, zero elevation/shadow).
- **Generous spacing**: hardcoded dp replaced with `JarvisTokens.Space*` where a
  card / list / row was rewritten. Icon + dot *diameters* (e.g. `MuseStatusDot
  size = 8.dp/12.dp`, the 20.dp diagnostics status icon, the 8.dp action-log dot)
  keep their original literal value to preserve byte-exact sizing.
- **Motion is deliberate, not gaudy**: a single subtle `fadeIn + slideInVertically`
  on model-row / route-row appearance using the shared `MuseMotion.standard()`
  tween. No springs, no bounce.

## Behavior preservation (visual-only contract)

- Verified by diffing `origin/main` vs the working tree per file: the set of
  `viewModel::*` / `controlViewModel::*` calls, every `testTag(...)`, every
  `contentDescription = "..."`, and every `R.string.*` id is **byte-for-byte
  identical** (zero delta on all six files).
- No composable's public parameters were changed (no additive params were even
  needed — `MuseButton`'s built-in `variant`/`enabled`/`leadingIcon` covered every
  case). State hoists, `LaunchedEffect` wiring, `remember`/`mutableStateOf` blocks,
  snackbar handling, the emergency-stop confirm dialog, and all nav callbacks are
  unchanged.
- New empty-state titles ("No installed models", "No capabilities", "No gateway
  paired") are inline String literals paired with the **existing** `stringResource`
  bodies, so `strings.xml` needs no change (and was not touched).

## Build / SDK status

- **JDK:** OpenJDK 21.0.10 — present.
- **Android SDK: NOT available in this sandbox.** `./gradlew :app:compileDebugKotlin`
  fails **purely** with `SDK location not found … ANDROID_HOME …` — the
  documented "do not block" case (missing SDK, not a code error). The Kotlin
  compile + screen smoke tests are therefore **deferred to CI**, the compile gate.
- **Manual self-review (compensating for the absent SDK):**
  - Every new `com.aci.hermes.ui.designsystem.*` import resolves to a public
    composable in the merged library (`MuseButton` + `MuseButtonVariant`,
    `MuseCard`, `MuseChip`, `MuseEmptyState`, `MuseMotion`, `MuseSectionHeader`,
    `MuseStatus` + `MuseStatusDot`) with the exact signatures read on `main`, and
    each imported symbol is used (verified per file).
  - No orphaned imports: every removed Material 3 symbol (`Card` / `CardDefaults`
    / `Button` / `ButtonDefaults` / `OutlinedButton` / `TextButton` where
    converted / `Surface` / `CircleShape` / layout `size` / unit `dp` /
    `AssistChip` / `AssistChipDefaults` / `FilterChip` / `FilterChipDefaults`) has
    **zero** remaining usages and its import was dropped (grep-verified, 0 refs);
    every retained import still resolves to ≥1 usage. `getValue`/`setValue` are
    kept (property-delegate operators for `by`).
  - `MuseButton` is always called with named args, so its
    `(onClick, text, modifier, variant, enabled, leadingIcon)` order is satisfied;
    `Modifier.weight(1f)` (DeviceControl Approve/Dismiss) survives as the button's
    `modifier` inside `RowScope`.
  - `MuseStatus` mapping uses the real enum (`Off`/`Ok`/`Live`/`Connecting`) — the
    prompt's "Active" maps to `Live`.
  - `MuseSectionHeader`'s `trailing` (ModelRoute) is passed a
    `(@Composable () -> Unit)?` via `if (localFirst) { { MuseChip(...) } } else null`.
  - `AnimatedVisibility` + `fadeIn` + `slideInVertically` +
    `MutableTransitionState` come from `androidx.compose.animation` (already on the
    classpath, used by the pilot's `JobsScreen`); generic `MuseMotion.standard<T>()`
    infers `Float`/`IntOffset` at the call sites.
  - Brace/paren balance verified per file.

## Residual risks

1. **Compilation unverified locally** (Android SDK absent). Mitigated by the
   self-review above; CI is the gate. Lowest-confidence lines are the two
   `AnimatedVisibility` entrance expressions (ModelCenter `ModelCard`, ModelRoute
   `RouteCard`) — standard APIs on the classpath; if CI ever flags one, the row
   falls back to a plain `MuseCard` (one-line change).
2. **Per-row `MutableTransitionState` in a `LazyColumn`** re-triggers the
   appearance animation when rows recycle on scroll (same intentional, subtle
   behavior the pilot shipped in `JobsScreen`). A reviewer may want to animate only
   on first composition — a taste call, not a correctness issue.
3. **`MuseStatusDot` color collapse** where the source used three semantic colors:
   - DeviceControl `ActiveIndicator` halted-vs-idle both map to `Off` (the red
     "halted" dot becomes inert); the **text label** still says "Halted …" vs
     "Idle …", so meaning is preserved, only the dot color is unified.
   - The DeviceControl `ActionLogRow` 3-color outcome dot was therefore **kept** as
     a `Surface` rather than forced into `MuseStatusDot`.
4. **`OwnerGatedBanner` left as a raw `Card(errorContainer)`** (CapabilityScreen) —
   deliberate, to keep the warning valence (`MuseCard` has no danger fill). A future
   `MuseCard` "danger"/"warning" variant could adopt it.
5. **Section titles shift from M3 `primary` to `JarvisSignal`** (signal-bright) when
   a `Text(...primary)` becomes a `MuseSectionHeader` — the intended branded
   treatment (matches the pilot), a pure presentation change.
6. **No screens were structurally changed** — same composables, same state, same
   nav. Default runtime behavior is unchanged; this is a pure presentation diff.
