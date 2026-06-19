# Batch B — Converse & Live re-skin snapshot

**Task id:** `bB-converse`
**Branch:** `claude/muse-android-reskin-converse`
**Base commit:** `4c1c216850cf32554d59ac0078345c982dd54473` (`origin/main` tip, PR #412 pilot merged)
**Owner:** this task is the only writer of this file.

## Intent

Visual-only re-skin of the **conversation & live** Android screens onto the merged
`muse*` Compose component library (the same target pattern the pilot proved on
`home/`, `jobs/`, `orchestrator/`). Swap raw Material 3 controls for the branded
`museButton` / `museCard` / `museChip`, with correct button valence. **No behavior
change**: every `viewModel::*` call, state hoist, nav callback, `.testTag(...)`,
`contentDescription`, and `enabled` gate is preserved byte-for-byte. The app is
already on the Singularity palette at the theme level; this only changes the
component surface.

## Owned files (the only files this task creates/modifies)

- `apps/android/app/src/main/java/com/aci/hermes/ui/screens/chat/JarvisChatScreen.kt`
- `apps/android/app/src/main/java/com/aci/hermes/ui/screens/live/JarvisLiveScreen.kt`
- `apps/android/app/src/main/java/com/aci/hermes/ui/screens/voice/VoiceCaptureScreen.kt`
- `apps/android/app/src/main/java/com/aci/hermes/ui/screens/avatar/AvatarPickerScreen.kt`
- `docs/launch/muse-app/bB-converse.md` (this snapshot)

`designsystem/**`, `components/**`, `theme/**`, `navigation/**`, all `*ViewModel.kt`,
`strings.xml`, and build files were **consumed read-only / untouched**.

## Before → after component swaps, per file

### `VoiceCaptureScreen.kt`
- Transcript `Card(colors = surfaceVariant)` → `museCard`.
- Save `Button` → `museButton(Primary)` (keeps `enabled = !saving`, `weight(1f)`, `testTag(SAVE_TASK)`).
- Clear `OutlinedButton` → `museButton(Secondary)` (keeps `enabled`, `weight(1f)`).
- Hardcoded `dp` in the rewritten card block → `JarvisTokens.Space{Lg,Md,Sm}`.
- **Left:** Scaffold/TopAppBar; the circular mic-capture FAB (`Surface` + `CircleShape`);
  the inline privacy/listening/error `Text` (inline status beside the mic, not a
  full-screen empty/error panel — `museEmptyState` would wrongly hide the mic).

### `AvatarPickerScreen.kt`
- "Choose photo" `Button` → `museButton(Primary, fillMaxWidth)`.
- Save `Button` → `museButton(Primary)`; Delete/Reset `OutlinedButton` → `museButton(Secondary)`.
- `RoomEditor` Generate `Button` → `museButton(Primary)` (dynamic "Generating…"/"Generate" label preserved).
- `PersonaCreator` Become `Button` → `museButton(Primary)` (dynamic label); Reset `OutlinedButton` → `museButton(Secondary)`.
- `BuiltInCard` `Card(onClick=…)` → `museCard(modifier = …height(96.dp).border(selectionStroke, RoundedCornerShape(12.dp)).clickable(onClick=…))`
  — preserves the selection ring (primary/outline) on top of the card's own edge
  hairline, mirroring the pilot's `PendingApprovalCard` bordered-museCard pattern.
- **Left:** Scaffold/TopAppBar; every `OutlinedTextField`; `SingleChoiceSegmentedButtonRow`/`SegmentedButton`;
  `CircularProgressIndicator`; the `CharacterGrid` sprite-selection `Surface` thumbnails
  and the `PreviewArea` bordered `Box` (image selection tiles, not content panels); `Image`.

### `JarvisChatScreen.kt`
- `ErrorBubble` Retry `Button(gold)` → `museButton(Primary, leadingIcon = Refresh)` (drops manual `Icon+Spacer`).
- `TaskCardView`: two display `AssistChip(onClick = {})` (taskType, targetTool) → `museChip(label = …)`;
  "Add to orchestrator" `Button(cyan)` → `museButton(Primary)`.
- `ApprovalCardView`: approve `Button(jade)` → `museButton(Approve)` (jade = the owner-gate valence, exact);
  deny/hold `OutlinedButton` → `museButton(Secondary)`.
- `CriticalCardView`: "Acknowledge" `Button(crimson, enabled = typed.isNotBlank())` → `museButton(Danger, enabled = …)`.
- `ChatInputArea`: streaming-abort `Stop OutlinedButton` → `museButton(Danger, leadingIcon = Stop)` (drops manual `Icon+Spacer`).
- **Left (deliberate):** all chat bubbles (`User` gold bubble, `Jarvis` bubble with
  asymmetric corners + tone accent border, `IndicatorBubble`, `ErrorBubble` outer
  `Surface`) — these are bubbles, not panels; `museCard` would flatten the tail and
  drop the gold fill. `InlineCardFrame` (`Surface` + per-tone accent border) stays —
  it is already a branded accent frame and `museCard` cannot carry the cyan/gold/amber/
  crimson tone border. `ToolCallChip` (specialized expandable tool row) stays.
  `MockModeBanner` (`Surface` banner) stays. The "Show detail" + `RecordRow` `AssistChip`s
  carry a leading icon / disclosure chevron with no `museChip` equivalent → left.
  `ActionTextButton` (Copy/Continue/Create-job) — quiet inline icon+label toolbar actions
  inside a bubble; converting 3-across to bordered secondary buttons would visually
  overweight the bubble, so left as `TextButton`. The compose bar (`AskJarvisBar`) and
  the critical-ack `OutlinedTextField` stay.

### `JarvisLiveScreen.kt`
- Avatar CTAs: `showApprovalCta Button(gold)` → `museButton(Primary)`; `showFixCta Button(crimson)` → `museButton(Danger)`;
  `showWarningCta Button(gold)` → `museButton(Primary)` (gold = brand core, no warn-button variant exists);
  `showEmergencyReleaseCta Button(crimson)` → `museButton(Danger)`.
- Emergency-confirm `AlertDialog`: confirm `Button(crimson)` → `museButton(Danger)`; dismiss `TextButton` →
  `museButton(Secondary)` (mirrors the pilot's `OwnerApproveDialog` dialog-button pattern).
- **Left:** Scaffold + the custom `JarvisTopBar`; `CircleIconButton` (`Surface`+`CircleShape`);
  the custom `JarvisStatusPill` (branded `Surface` pill, GatewayStatusPill-class); the
  `JarvisCommandBar` compose/command bar; `PixelRoom`/`DenFurnitureLayer`/particles/avatar
  hosts; `ModalBottomSheet` status sheet; the privacy-indicator `Surface`. The status-sheet
  `AssistChip`s carry a colored On/Off trailing value with no `museChip` equivalent → left.

No list-entrance motion was added: none of the four screens has a `LazyColumn` of
homogeneous item rows in the rewritten regions (chat transcript items are bubbles
left as-is; avatar/voice are `verticalScroll` columns), so the optional `fadeIn +
slideInVertically` row entrance from the pilot's `JobsScreen` did not apply.

## Validation status

- **Compile gate:** `cd apps/android && ./gradlew :app:compileDebugKotlin` →
  `FAILURE … SDK location not found` (no Android SDK in this environment). This is
  the documented do-not-block case; **CI is the compile gate.** Proceeded on self-review.
- **Self-review (every file):**
  - *Orphaned imports removed:* `VoiceCaptureScreen` dropped `Card`, `CardDefaults`,
    `Button`, `OutlinedButton`. `AvatarPickerScreen` dropped `Card`, `Button`,
    `OutlinedButton`. `JarvisChatScreen` dropped `Button`, `ButtonDefaults`,
    `OutlinedButton`. `JarvisLiveScreen` dropped `Button`, `ButtonDefaults`,
    `TextButton`. Each removed symbol verified to have **zero** remaining usages
    (grep per file). All retained Material 3 imports (`Surface`, `CircleShape`,
    `AssistChip`/`AssistChipDefaults`, `OutlinedTextField`, `Icon`, `IconButton`,
    `Text`, `CircularProgressIndicator`, `SegmentedButton*`, layout `size`/`dp`,
    `Color`, the `Hermes*`/`Jarvis*` color tokens) verified **still used**.
  - *New imports resolve + used:* `museButton`/`museButtonVariant` (all 4),
    `museCard` (voice, avatar), `museChip` (chat), `JarvisTokens` (voice). Each
    matches a real designsystem signature and is used ≥1×.
  - *Behavior parity vs base:* marker counts vs `origin/main` —
    `testTag` (chat 0/0, live 0/0, voice 3/3, avatar 0/0),
    `viewModel::` (8/8, 8/8, 2/2, 8/8) all **unchanged**;
    `contentDescription` unchanged except chat 10→8: the only two removed were the
    `contentDescription = null` **decorative** icons folded into `museButton.leadingIcon`
    (Retry, Stop). `museButton` renders `leadingIcon` with `contentDescription = null`
    too, and the accessible name is the preserved button text — semantics are equivalent,
    no a11y regression.
  - *No signature changes:* no public/private signatures changed; no new params added
    (the pilot's `ControlButton`-style additive defaulted param was not needed here).

## Residual risks

- **Visual-only judgment calls** (documented above): kept `ActionTextButton`
  (Copy/Continue/Create-job), the disclosure/record `AssistChip`s, the status-sheet
  trailing-value `AssistChip`s, and the avatar sprite-selection `Surface` thumbnails
  on raw Material 3 because no `muse*` component carries their affordance (icon slot /
  colored trailing value / image tile) and forcing a swap would *worsen* craft. A
  reviewer wanting maximal coverage could revisit these, but they are out of the
  mechanical swap set.
- `showWarningCta` maps to `museButton(Primary)` (the original used the gold core);
  there is no dedicated "warn" button variant. If a warn valence is later added to
  `museButton`, this call should switch to it.
- Compile not locally verified (no SDK). Mitigated by: exhaustive per-file orphan/usage
  grep, signature-checked muse calls against the real component sources, and structural
  diff review (every removed `{ … }` button body fully replaced by a self-closing
  `museButton(...)`). CI must confirm.

## PR

Not opened (per task scope: do **not** open a PR; do **not** merge). Pushed to
`origin/claude/muse-android-reskin-converse` for review.
