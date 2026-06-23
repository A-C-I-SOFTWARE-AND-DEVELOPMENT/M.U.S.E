# Batch B PILOT — muse Android command-center re-skin (snapshot)

**Grain:** Batch B PILOT — re-skin the Home / Orchestrator / Jobs command-center
screens onto the merged `muse*` Compose component library. Visual-only craft
refinement: swap raw Material 3 for the branded `com.aci.hermes.ui.designsystem`
components and add empty states + tasteful motion. The app is already on the
Singularity palette at the theme level; this grain is presentation only.
**Branch:** `claude/muse-android-reskin-pilot`.
**Base commit:** `860a88b8e3473e4558c26a9f24dd02fe89f94e47` (`git rev-parse origin/main`).
**Worktree:** `/home/user/hermes-agent/.claude/worktrees/agent-a876183cfbae6acf8`.

## Owned files (only these were touched)

- `apps/android/app/src/main/java/com/aci/hermes/ui/screens/home/HomeScreen.kt`
- `apps/android/app/src/main/java/com/aci/hermes/ui/screens/home/JarvisPrimeHomeScreen.kt`
- `apps/android/app/src/main/java/com/aci/hermes/ui/screens/jobs/JobsScreen.kt`
- `apps/android/app/src/main/java/com/aci/hermes/ui/screens/jobs/JobDetailScreen.kt`
- `apps/android/app/src/main/java/com/aci/hermes/ui/screens/orchestrator/TaskDetailScreen.kt`
- `docs/launch/muse-app/bB-pilot-home-jobs.md` (this file)

No `*ViewModel.kt`, `ui/theme/**`, `ui/navigation/**`, `ui/designsystem/**`
(consumed read-only), `strings.xml`, or build files were modified.

## Screens re-skinned + components swapped (before → after)

### `HomeScreen.kt`
- `GreetingCard`: raw `Card` (surfaceVariant) → **`museCard`** + a **`museGlyph`**
  (48dp brand mark) leading the greeting Row. Title → `JarvisSignal`, subtitle →
  `JarvisSignalDim` (value ladder).
- `StatusCard`: `Card` → `museCard`; the service-state `Surface(CircleShape)` dot
  → **`museStatusDot`** (`Ok` when running, `Off` when stopped); start/stop
  `Button`/`OutlinedButton` → **`museButton`** (start = `Primary`, stop =
  `Secondary`).
- `SectionTitle` (Quick links, Tools): raw `Text` title → **`museSectionHeader`**.
- `QuickLinkCard`, `JarvisLiveEntryCard`, `ToolCard`, `SafetyBanner`: `Card` →
  `museCard` (clickable cards keep their tap via `Modifier.clickable`).
- Tool actions: prepare-handoff = `museButton` `Primary`, open-tool =
  `museButton` `Secondary`.
- Bottom "new task" `OutlinedButton` → **`museButton`** `Primary` (full-width
  hero CTA of the screen).
- Hardcoded `16.dp`/`12.dp`/`8.dp` spacings → `JarvisTokens.Space*`.

### `JarvisPrimeHomeScreen.kt`
- `JarvisPrimeIcon`: the `☤` caduceus glyph inside the presence-bordered circle
  → **`museGlyph`** (44dp). The presence-tinted ring stays on the surrounding
  Box border (the at-a-glance status tell), the brand mark blazes in its core.
- Emergency-stop confirm dialog: `Button(containerColor=HermesError)` →
  **`museButton`** `Danger` ("Engage", preserves `haptics.confirm()`); dismiss
  `OutlinedButton` → `museButton` `Secondary`.
- `EmergencyStopButton`: `Button` → **`museButton`** (`Danger` when armed,
  `Secondary` when engaged/deactivate), `PowerSettingsNew` moved to `leadingIcon`
  (the built-in icon/label spacing replaces the manual `Spacer`).
- Every status/content card (`ActiveTaskCard`, `PendingApprovalCard`,
  `WorkerStatusCard`, `MemoryPulseCard`, `SuggestedNextActionCard`,
  `ModelRouterCard`, `JobsCard`, `AuditEventsCard`, `EvidenceCard`,
  `VoiceStateCard`, `DeviceCapabilityCard`, `QuickActionsCard`,
  `BackendUnavailableBanner`): `Card` → **`museCard`**. `onClick` cards preserve
  the tap via `Modifier.clickable(onClick=…)`; `VoiceStateCard` preserves its
  emergency-stop disable via `Modifier.clickable(enabled = enabled, …)`. The
  risk-colored border on `PendingApprovalCard` and the gold-deep border on
  `BackendUnavailableBanner` are kept on the modifier.
- Display metadata chips in `ActiveTaskCard` / `PendingApprovalCard`:
  `AssistChip(onClick = onClick, …)` → **`museChip`** (display-only). The chips
  passed the *same* `onClick` as their parent card, so the redundant inner tap is
  removed; the card tap (the real navigation) is unchanged.
- `QuickActionsCard` grid: `OutlinedButton` → `museButton` `Secondary`
  (`enabled` + `Modifier.weight(1f)` preserved).
- `BackendUnavailableBanner` actions: `Button` → `museButton` `Primary`.

### `JobsScreen.kt`
- Section headers ("Active (3)" etc.): raw `Text` → **`museSectionHeader`** with a
  **`museChip`** count in the trailing slot.
- `JobRow`: `Card(onClick)` → **`museCard`** + `Modifier.clickable`; wrapped in
  **`AnimatedVisibility`** with a `fadeIn + slideInVertically` enter on
  `museMotion.standard()` (subtle row appearance). The unblock action
  `OutlinedButton` → **`museButton`** (`Approve` variant when waiting-for-approval,
  `Secondary` when resume). `JobStatusChip` (a shared, already-branded component)
  left as-is.
- Empty / not-paired / error states: bare centered `Text` → **`museEmptyState`**
  (glyph + title + body). Test tags `EMPTY` / `NOT_PAIRED` moved onto the empty
  state's Box so existing selectors still resolve.

### `JobDetailScreen.kt`
- `sectionCard` helper: `Card` → **`museCard`**; section title `Text` →
  **`museSectionHeader`**.
- `ControlButton` helper: `OutlinedButton` → **`museButton`**; gained an optional
  `variant` (default `Secondary`). Call sites now pass `Danger` for **Cancel** and
  `Approve` for the owner-gated **Approve** control; the other six controls stay
  `Secondary`. Labels / `enabled` / `onClick` unchanged.
- `OwnerApproveDialog`: confirm `TextButton` → `museButton` `Approve`; dismiss
  `TextButton` → `museButton` `Secondary` (the owner-authorization phrase
  `OutlinedTextField` is untouched).

### `TaskDetailScreen.kt`
- Prompt-preview `Card` → **`museCard`**; its "Prompt preview" title `Text` →
  **`museSectionHeader`**.
- Bottom actions: mark-handed-off `Button` → `museButton` `Primary`; save
  `OutlinedButton` → `museButton` `Secondary` (`enabled = !state.saving`
  preserved).

## Deliberately left as-is (no muse equivalent, or out of scope)

- **`Scaffold` / `TopAppBar` / `IconButton` / `CircularProgressIndicator` /
  `AlertDialog`** (Job Detail, Task Detail) — structural M3 chrome with no
  designsystem counterpart.
- **`OutlinedTextField` + `ExposedDropdownMenu`/`EnumDropdown`** (Task Detail
  form, owner-approval phrase field, Ask bar) — there is no `museTextField` /
  `museDropdown` in the library yet.
- **`AskJarvisBar` `TextField` + send `IconButton`**, **`VoiceCaptureButton`**
  (circular mic FAB) — text-entry and the icon-only voice FAB have no muse
  equivalent; left untouched.
- **`GatewayStatusPill`** (a clickable `AssistChip` with a custom 4-way
  gateway/mock color and an `onClick` to Control) — not a 1:1 fit for
  `museStatusPill` (which maps a fixed `museStatus` enum → color and is not
  clickable). Converting it would change the status-color mapping and drop the
  tap, so it was left.
- **`JobStatusChip`** (shared `ui/components`) — already on the Singularity
  tokens; coarsens the wire `JobUiState` superset. No re-map (that would change
  semantics).
- **`BackendOfflineBanner` / `BackendStatusPill`** (shared `ui/components`,
  Home) — out of owned scope; consumed unchanged.
- The Task Detail **delete-confirm `AlertDialog`** keeps its `TextButton`
  actions (dialog idiom; no raw `Button`/`OutlinedButton` involved).
- The `@OptIn(ExperimentalMaterial3Api::class)` annotations on now-`museCard`
  composables were left in place (a redundant opt-in is at most a warning, never
  an error, and the project does not set `allWarningsAsErrors`).

## Design-language fidelity

- **White core is the hero**: the only hero fills are the `museButton.Primary`
  CTAs (one per surface) and the `museGlyph` core; spectral cyan→violet appears
  only inside the matte glyph ring and the cyan/jade `museStatusDot`.
- **Value, not effects**: every panel is now a `museCard` (void-3 fill + edge
  hairline, zero elevation/shadow). The risk / backend attention borders are the
  deliberate exception and ride on top of the frame.
- **≤3 color roles + value ladder**: body copy stepped to `JarvisSignal` /
  `JarvisSignalDim` / `JarvisSignalMute`; the per-card category eyebrows keep
  their existing `Hermes*` accent (unchanged semantics).
- **Generous spacing**: hardcoded dp replaced with `JarvisTokens.Space*` where a
  card/list was rewritten.
- **Motion is deliberate, not gaudy**: a single subtle `fadeIn + slideInVertically`
  on job-row appearance using the shared `museMotion.standard()` tween. No
  springs, no bounce.

## Behavior preservation (visual-only contract)

- Every `viewModel::*` call, state hoist, `LaunchedEffect`/`DisposableEffect`
  lifecycle wiring, snackbar handling, and navigation callback is byte-for-byte
  preserved. No composable's public parameters were changed (the only signature
  touch is an **additive, defaulted, private** `variant` param on Job Detail's
  `ControlButton`).
- All `testTag`s preserved: `JobsScreenTags.{EMPTY,NOT_PAIRED,row,unblock}`,
  every `JarvisHomeTestTags.*` (ICON, EMERGENCY_STOP, ACTIVE_TASK,
  PENDING_APPROVAL, WORKER_STATUS, MEMORY_PULSE, SUGGESTED_ACTION, MODEL_ROUTER,
  JOBS, AUDIT_EVENTS, EVIDENCE, VOICE_STATE, DEVICE_CAPABILITY, QUICK_ACTIONS,
  BACKEND_BANNER), and the semantics `contentDescription`s.

## Build / SDK status

- **JDK:** OpenJDK 21.0.10 (`/usr/lib/jvm/java-21-openjdk-amd64`) — present.
- **Android SDK: NOT available in this sandbox.** No `apps/android/local.properties`,
  `ANDROID_HOME` / `ANDROID_SDK_ROOT` unset, no SDK at the usual locations.
  Running `./gradlew :app:compileDebugKotlin` (online, so AGP 8.7.3 resolved)
  fails **purely** with:

  > SDK location not found. Define a valid SDK location with an `ANDROID_HOME`
  > environment variable or by setting the `sdk.dir` path in your project's
  > `local.properties` …

  i.e. the failure is the missing SDK, **not** a code error — the documented
  "do not block" case. The Kotlin compile + the screen smoke tests are therefore
  **deferred to CI**, which provisions the SDK and is the compile gate.
- **Manual self-review (compensating for the absent SDK):**
  - Every new `com.aci.hermes.ui.designsystem.*` import resolves to a public
    composable in the merged library (`museButton` + `museButtonVariant`,
    `museCard`, `museChip`, `museEmptyState`, `museGlyph`, `museMotion`,
    `museSectionHeader`, `museStatus` + `museStatusDot`) and each imported symbol
    is used (verified per file).
  - No `Card` / `CardDefaults` / `Button(` / `ButtonDefaults` / `OutlinedButton`
    / `TextButton` (where converted) references remain; the matching imports were
    removed so no orphaned imports were introduced. Unused-`width` (JarvisPrime)
    and `Surface`/`CircleShape` (Home) imports were dropped too.
  - `museButton` is always called with named args, so its
    `(onClick, text, modifier, variant, enabled, leadingIcon)` order is satisfied;
    `Modifier.weight(1f)` (QuickActions) and `testTag` survive as the button's
    `modifier`.
  - The `AnimatedVisibility` + `fadeIn` + `slideInVertically` +
    `core.MutableTransitionState` imports come from the same
    `androidx.compose.animation` artifact as `AnimatedVisibility` (already used in
    `JarvisChatScreen.kt`); the generic `museMotion.standard<T>()` infers
    `Float`/`IntOffset` at the two call sites.
  - `museCard` + `Modifier.clickable` reproduces the old `Card(onClick=…)` tap;
    `VoiceStateCard`'s `enabled` gate is preserved via
    `clickable(enabled = enabled)`.

## Residual risks

1. **Compilation unverified locally** (Android SDK absent). Mitigated by the
   self-review above; CI is the gate. Lowest-confidence line is JobsScreen's
   `AnimatedVisibility` enter expression — the APIs are standard and on the
   classpath, but if CI ever flags it, the row can fall back to a plain
   `museCard` with no animation (one-line change).
2. **Per-row `MutableTransitionState` in a `LazyColumn`** re-triggers the
   appearance animation when rows recycle on scroll. This is intentional and
   subtle (a 250ms fade/rise), not a correctness issue, but is a visual taste
   call a reviewer may want to tune (e.g. animate only on first composition).
3. **Redundant `@OptIn(ExperimentalMaterial3Api::class)`** now sits on a few
   `museCard`-only composables. Harmless (warning at most; no
   `allWarningsAsErrors`), left to keep the diff focused; a follow-up can prune
   them.
4. **`GatewayStatusPill` not re-skinned** — deliberately (clickable + 4-way
   status color has no `museStatusPill` fit). A future `museStatusPill` with an
   `onClick` + custom-color overload would let it adopt the brand component.
5. **No screens were structurally changed** — same composables, same state, same
   nav. Default runtime behavior is unchanged; this is a pure presentation diff.
