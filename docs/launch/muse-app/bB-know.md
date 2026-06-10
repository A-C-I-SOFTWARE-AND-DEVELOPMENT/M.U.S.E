# Batch B — MUSE Android knowledge & observability re-skin (snapshot)

**Grain:** Batch B fan-out — re-skin the **knowledge & observability** Android
screens (memory, evidence, knowledge graph, research, audit, ledger) onto the
merged `Muse*` Compose component library. Visual-only craft refinement: swap raw
Material 3 for the branded `com.aci.hermes.ui.designsystem` components and add
empty states + tasteful motion. The app is already on the Singularity palette at
the theme level; this grain is presentation only. No ViewModel call, state hoist,
nav callback, test tag, or content description was changed.
**Branch:** `claude/muse-android-reskin-know`.
**Base commit:** `4c1c216850cf32554d59ac0078345c982dd54473` (`git rev-parse origin/main`).
**Worktree:** `/home/user/hermes-agent` (branch cut from `origin/main`).

## Owned files (only these were touched)

- `apps/android/app/src/main/java/com/aci/hermes/ui/screens/memory/MemoryScreen.kt`
- `apps/android/app/src/main/java/com/aci/hermes/ui/screens/evidence/EvidenceScreen.kt`
- `apps/android/app/src/main/java/com/aci/hermes/ui/screens/knowledge/KnowledgeGraphScreen.kt`
- `apps/android/app/src/main/java/com/aci/hermes/ui/screens/research/ResearchScreen.kt`
- `apps/android/app/src/main/java/com/aci/hermes/ui/screens/audit/AuditScreen.kt`
- `apps/android/app/src/main/java/com/aci/hermes/ui/screens/audit/AuditDetailScreen.kt`
- `apps/android/app/src/main/java/com/aci/hermes/ui/screens/ledger/LedgerTimelineScreen.kt`
- `apps/android/app/src/main/java/com/aci/hermes/ui/screens/ledger/LedgerEventDetailScreen.kt`
- `docs/launch/muse-app/bB-know.md` (this file)

No `*ViewModel.kt`, `ui/theme/**`, `ui/navigation/**`, `ui/designsystem/**`
(consumed read-only), `ui/components/**` (consumed read-only), `strings.xml`, or
build files were modified. The sibling helper files in the owned directories that
are **out of owned scope** — `memory/MemoryDetail.kt`, `memory/MemoryDialogs.kt`,
`memory/MemoryTreeSections.kt` (`MemoryTabs` / `ProposedInboxSection` /
`ContradictionsSection` / `FreshnessSection`), `memory/SocialPatternCard.kt`,
`memory/SocialPatternProjection.kt`, `audit/AuditFormatting.kt`
(`colorOn`/`displayLabel`/`confidenceLabel`/`formatTimestamp`),
`ledger/LedgerFormatting.kt` (`formatLedgerTimestamp`/`RISK_FILTER_OPTIONS`),
`knowledge/KnowledgeRelated.kt` (`KnowledgeRelatedCard`), and all `*ViewModel.kt`
(incl. `GRAPH_QUERY_MODES`, `RollbackRequestState`) — were left byte-for-byte
unchanged; their call sites in the owned screens are preserved exactly.

## Screens re-skinned + components swapped (before → after)

### `MemoryScreen.kt`
- `MemoryCard` (the screen's own card, distinct from `ui/components/MemoryCard.kt`):
  clickable `Card(onClick = onOpen, colors = surfaceVariant)` →
  **`MuseCard(modifier = …​.clickable(onClick = onOpen))`**.
- Durability + confidence `AssistChip(onClick = onOpen)` → **`MuseChip`** with
  **`onClick = onOpen` preserved** (these chips were tap-to-open, not display-only).
- `MemoryFilter`: the "All" + per-category `FilterChip` → **`MuseChip`**
  (`selected` + `onClick` 1:1; per-chip `testTag(filter(...))` kept).
- Hardcoded `16.dp`/`12.dp`/`8.dp`/`6.dp`/`4.dp`/`2.dp` → `JarvisTokens.Space*`
  in rewritten blocks.

### `EvidenceScreen.kt`
- `EvidenceCard`: clickable `Card(onClick, surfaceVariant)` →
  **`MuseCard(…​.clickable(onClick))`**.
- Trust / Stale / Fresh `AssistChip(onClick = {})` (display-only) → **`MuseChip`**
  (no `onClick`). The Stale chip's decorative `leadingIcon`
  (`Icon(contentDescription = null)`) is dropped — `MuseChip` has no icon slot; a
  null-CD decorative icon, no a11y loss.
- `EvidenceDetail` actions: `OutlinedButton` "Verify" → **`MuseButton`** `Secondary`;
  `Button` "Promote to memory" → **`MuseButton`** `Primary`; `OutlinedButton`
  "Close" → **`MuseButton`** `Secondary`.
- `OwnerAuthorizationDialog`: `Button` "Authorize & promote" → **`MuseButton`**
  `Approve` (owner-gate valence); `TextButton` "Cancel" → **`MuseButton`** `Secondary`.
- Bare empty `Text("No evidence yet.")` (inside the `EMPTY`-tagged `Box`) →
  **`MuseEmptyState`** (glyph + title + new inline body; the `Box` keeps its
  `testTag(EMPTY)`).
- Hardcoded dp → `JarvisTokens.Space*`.

### `KnowledgeGraphScreen.kt`
- Graph-mode `FilterChip` (coding/local/global) → **`MuseChip`** (`selected` +
  `onClick` 1:1).
- "Query" `Button` → **`MuseButton`** `Primary`; "Rebuild" `OutlinedButton` →
  **`MuseButton`** `Secondary` (both keep `enabled = !loading` / `query.isNotBlank()`).
- Related-node `Card` and `CommunityCard`'s `Card` → **`MuseCard`**.
- "Clusters" / "Related nodes" / "Sources" list-section `Text(titleMedium)` →
  **`MuseSectionHeader`**.
- Hardcoded `16.dp`/`12.dp`/`8.dp`/`4.dp` → `JarvisTokens.Space*`.

### `ResearchScreen.kt`
- Final-answer card, `EvidenceCardView`, `ContradictionView`, and `HintCard`
  (unpaired / error / idle / no-sources banners): raw `Card`
  (surfaceVariant / errorContainer) → **`MuseCard`**.
- Uncertainty / evidenceStrength / sourceType `AssistChip(onClick = {})`
  (display-only) → **`MuseChip`**.
- `SectionTitle(...)` (`Text titleMedium`, used for Answer/Evidence/Contradictions,
  with the count baked into the string) → **`MuseSectionHeader`**.
- "Create coding task" `Button` (plain label) → **`MuseButton`** `Primary`
  (`enabled = !creatingTask`, `testTag(CREATE_TASK)` kept).
- `ContradictionView` lost its `errorContainer` fill (→ `MuseCard`); the **error
  signal is preserved** by coloring the subject `Text` with `colorScheme.error`.
  `HintCard(error = true)` likewise colors its text `error` (the red container is
  gone; the text now carries the signal).
- Hardcoded `16.dp` → `JarvisTokens.Space*` in rewritten blocks (the `18.dp`/`16.dp`
  spinner sizes are kept literal — see "Deliberately left").

### `AuditScreen.kt`
- `AuditCard`: clickable `Card(onClick, surfaceVariant / errorContainer)` →
  **`MuseCard(…​.clickable(onClick))`**.
- Empty state: bare `Text(audit_empty)` (inside the `EMPTY`-tagged `Box`) →
  **`MuseEmptyState`** (the `R.string.audit_empty` becomes the title; new inline body).
- `AuditCard` rows wrapped in **`AnimatedVisibility`** (`fadeIn + slideInVertically`
  on `MuseMotion.standard()`) — the same subtle list-row entrance as `JobsScreen`.
- Hardcoded `16.dp`/`12.dp`/`8.dp`/`6.dp`/`4.dp` → `JarvisTokens.Space*`.

### `AuditDetailScreen.kt`
- `SummaryCard`, `ProofDetail`, `FailedVerificationCard`, `ApprovalHistoryCard`,
  `WorkerRunCard`, `RollbackCard`, `ImpactReportCard`: raw `Card`
  (surfaceVariant / errorContainer / secondaryContainer / tertiaryContainer) →
  **`MuseCard`** (uniform void-3, matching the pilot's `JobDetailScreen` `sectionCard`
  — sections are uniform framed panels; state is carried by text/icon color, not by
  card tint, per the brand "value not effects" rule).
- Not-found state: bare `Text(audit_detail_missing)` → **`MuseEmptyState`**
  (the `NOT_FOUND`-tagged `Box` keeps its tag).
- `FailedVerificationCard`: title + `ErrorOutline` icon stay `colorScheme.error`;
  body / failing-check text moved from `onErrorContainer` → `colorScheme.onSurface`
  / `colorScheme.error` so they stay legible (and the failing-checks list keeps its
  red signal) on the now-void card.
- Hardcoded dp → `JarvisTokens.Space*` (the `10.dp`/`12.dp` status-dot diameters
  kept literal).

### `LedgerTimelineScreen.kt`
- `LedgerRow`: clickable `Card(onClick, surfaceVariant)` →
  **`MuseCard(…​.clickable(onClick))`**.
- Bottom-row worker / Diff / Evidence / Rollback `AssistChip(onClick = onClick)` →
  **`MuseChip(onClick = onClick)`** (these forwarded the row tap — `onClick`
  preserved).
- `LedgerFilterPanel`: Risk `FilterChip` → **`MuseChip`** (`selected` + toggle
  `onClick` 1:1); Apply `TextButton` → **`MuseButton`** `Primary`; Clear
  `TextButton` → **`MuseButton`** `Secondary` (both still flow through
  `onApply(draft)` / `draft = LedgerFilters(); onClear()`).
- Empty state: bare `Text("No activity yet.")` → **`MuseEmptyState`** (the
  `EMPTY`-tagged `Box` keeps its tag).
- `LedgerRow` rows wrapped in **`AnimatedVisibility`** (`MuseMotion.standard()`).
- Hardcoded `16.dp`/`12.dp`/`10.dp`/`8.dp`/`6.dp` → `JarvisTokens.Space*`.

### `LedgerEventDetailScreen.kt`
- `Section(...)` helper: `Card(CardDefaults.cardColors())` → **`MuseCard`** with the
  section title `Text(labelLarge, primary)` → **`MuseSectionHeader`** (exactly the
  pilot's `JobDetailScreen` `sectionCard` shape).
- Not-found state: bare `Text("Event not found.")` → **`MuseEmptyState`** (the
  `NOT_FOUND`-tagged `Box` keeps its tag).
- "Request rollback" `OutlinedButton` → **`MuseButton`** `Danger` (rollback is a
  reversal/cautionary path; full-width + `testTag(ROLLBACK_BUTTON)` kept).
- `RollbackDialog`: "Queue request" `Button` → **`MuseButton`** `Danger`
  (consistent reversal valence); "Cancel" `TextButton` → **`MuseButton`** `Secondary`.
- Hardcoded `16.dp`/`12.dp`/`8.dp`/`6.dp` → `JarvisTokens.Space*`.

## Deliberately left as-is (no Muse equivalent, or signal-preserving)

- **`Scaffold` / `TopAppBar` / `IconButton` / `AlertDialog` /
  `CircularProgressIndicator` / `HorizontalDivider`** chrome across all screens —
  structural M3 with no designsystem counterpart.
- **`OutlinedTextField`** (Memory search, Evidence search, Knowledge "ask the
  graph", Research query, Ledger filter fields + rollback reason) — form controls;
  no `MuseTextField` in the library yet. The shared `ui.components.EmptyState`
  (Memory STORED-tab filtered-empty) is **already** a branded icon+title empty-state
  component (carries the `Search` icon), so it was kept rather than swapped for the
  glyph-based `MuseEmptyState`.
- **Research "Run" `Button` and per-card "Save to memory" `OutlinedButton`** kept as
  raw M3: their content is a **conditional `CircularProgressIndicator`-or-`Text`**
  toggle (in-button progress spinner), which `MuseButton`'s `text: String` API
  cannot host. Converting them would drop the in-button progress affordance — a
  behavior change. The paired "Saved" `TextButton(enabled = false)` (a disabled
  `Check`-icon affordance, the other branch of the same `if/else`) is kept with it
  for a coherent two-state control. Raw `Button`/`OutlinedButton` still pick up the
  Singularity palette + `JarvisShapes` from the theme.
- **Audit / Ledger status `AssistChip`s with `labelColor = …​.colorOn(scheme)`**
  (approval-state, result, the SERIOUS/CRITICAL "required" chip) kept as
  `AssistChip` — they are the audit-domain analog of the already-branded
  `JobStatusChip` the brief says to leave; their **label color is a load-bearing
  semantic signal** that `MuseChip` (dim/void text only) cannot express. The plain
  route-destination / kind / rollback-state / confidence `AssistChip(onClick = {})`
  in the same rows are kept alongside them so the chip rows stay visually coherent
  (a half-swapped row would mix two chip vocabularies).
- **`Surface(CircleShape)` status dots** in `AuditScreen`/`AuditDetailScreen`
  (`record.result.colorOn`), `WorkerRunCard` (`run.status.colorOn`), and
  `LedgerTimelineScreen` (`event.category.colorOn`) kept as tinted `Surface` dots:
  they encode **domain result/category palettes** (success/failure/blocked, per-
  category colors) from the formatting layer, far richer than `MuseStatusDot`'s
  `Off`/`Ok`/`Live`/`Connecting` vocabulary — forcing the enum would collapse those
  signals. (`MuseStatusDot` is the connection/liveness tell; these are not liveness.)
- **`Memory` redacted badge** (`Surface(errorContainer, RoundedCornerShape(50))`
  + `Lock` icon) and **`CategoryPill`** (`Box.background(category-color)`) kept: both
  are semantic **colored badges** (not `CircleShape` status dots), and the category
  pill's per-category container color is the signal.
- The `@OptIn(ExperimentalMaterial3Api::class)` annotations that remain
  (every screen top-level for `TopAppBar`; `MemorySearch` as in the original) are
  still required by surviving experimental APIs / preserved verbatim.

## Design-language fidelity

- **White core is the hero**: the only hero fills are the `MuseButton.Primary`
  CTAs (one per surface: Knowledge "Query", Evidence "Promote", Research "Create
  task", Ledger "Apply") and the `MuseEmptyState` glyph core; spectral cyan→violet
  appears only inside the matte glyph ring.
- **Valence on the control, not the label**: owner-gate approve = `Approve`
  (Evidence "Authorize & promote"); reversal/cautionary = `Danger` (Ledger
  rollback request + queue); quiet/cancel/secondary = `Secondary` — mirroring the
  pilot's Job-Detail `ControlButton` and `OwnerApproveDialog`.
- **Value, not effects**: every converted panel is a `MuseCard` (void-3 fill + edge
  hairline, zero elevation/shadow). Semantically-tinted source cards
  (`errorContainer`/`secondary`/`tertiaryContainer`) become uniform void cards with
  the state re-expressed via text/icon color (matching `JobDetailScreen`).
- **Generous spacing**: hardcoded dp replaced with `JarvisTokens.Space*` where a
  card / list / row was rewritten. Dot/icon *diameters* (`Surface` dots `10.dp`/
  `12.dp`, the `16.dp`/`18.dp` in-button spinners, the `RoundedCornerShape(50)`
  pills) keep their original literal value to preserve byte-exact sizing.
- **Motion is deliberate, not gaudy**: a single subtle `fadeIn + slideInVertically`
  on audit-row / ledger-row appearance using the shared `MuseMotion.standard()`
  tween. No springs, no bounce. (Memory/Evidence/Research/Knowledge keep their
  existing list/scroll behavior — entrance motion was only added to the two pure
  `LazyColumn` row lists, exactly mirroring `JobsScreen`.)

## Behavior preservation (visual-only contract)

- Verified by diffing `origin/main` vs the working tree per file: the set of
  `viewModel::*` / `viewModel.*` calls, every `testTag(...)`, and the public
  composable signatures are **byte-for-byte identical** (zero delta on all eight
  files; the only `git diff` on declaration lines is line-number position).
- `onClick`/`onOpen`/`contentDescription` count deltas were each inspected and are
  **non-behavioral**: every dropped `onClick` was an empty `onClick = {}` on a
  display-only `AssistChip` (now a display-only `MuseChip`); the one dropped
  `contentDescription` was the Evidence Stale chip's decorative `null`. **Real**
  nav callbacks that lived on chips were preserved by passing `onClick` to
  `MuseChip` (Memory durability/confidence → `onOpen`; Ledger worker/Diff/Evidence/
  Rollback → row `onClick`).
- No composable's public parameters were changed (no additive params were even
  needed — `MuseButton`'s built-in `variant`/`enabled`/`leadingIcon` and
  `MuseChip`'s `selected`/`onClick` covered every case). State hoists,
  `LaunchedEffect`/`DisposableEffect` wiring, `remember`/`mutableStateOf` blocks,
  snackbar handling, the owner-auth + rollback dialogs, and all nav callbacks are
  unchanged.
- New empty-state titles ("No evidence yet", "No activity yet", "Event not found",
  …) are inline String literals; where a string id already existed
  (`audit_empty`, `audit_detail_missing`) it is reused as the title, so
  `strings.xml` needs no change (and was not touched).

## Build / SDK status

- **Android SDK: NOT available in this sandbox.** `./gradlew :app:compileDebugKotlin`
  fails **purely** with `SDK location not found … ANDROID_HOME …` — the documented
  "do not block" case (missing SDK, not a code error). The Kotlin compile + screen
  smoke tests are therefore **deferred to CI**, the compile gate.
- **Manual self-review (compensating for the absent SDK):**
  - Every new `com.aci.hermes.ui.designsystem.*` import resolves to a public
    composable in the merged library (`MuseButton` + `MuseButtonVariant`, `MuseCard`,
    `MuseChip`, `MuseEmptyState`, `MuseSectionHeader`, `MuseMotion`) with the exact
    signatures read on `main`, and each imported symbol is used (grep-verified per
    file: import-count vs use-count balanced for every Muse symbol).
  - No orphaned imports: every removed Material 3 symbol (`Card`/`CardDefaults`,
    `Button`/`OutlinedButton`/`TextButton` where converted, `FilterChip`/
    `FilterChipDefaults`, `AssistChip`/`AssistChipDefaults` where converted, and
    `dp` where fully tokenized) has **zero** remaining usages and its import was
    dropped (grep-verified, 0 refs). Retained `AssistChip`/`AssistChipDefaults`
    (audit/ledger) and `Button`/`OutlinedButton`/`TextButton` (Research spinners)
    each still resolve to ≥1 usage. `getValue`/`setValue` are kept (property-delegate
    operators for `by` — used by every `val state by …​collectAsState()` /
    `var … by remember { mutableStateOf(…) }`).
  - `dp` is re-imported wherever a literal diameter/spinner size survives
    (`AuditScreen`, `AuditDetailScreen`, `LedgerTimelineScreen`, `ResearchScreen`,
    `MemoryScreen`) and dropped where every dp became a token (`EvidenceScreen`,
    `KnowledgeGraphScreen`, `LedgerEventDetailScreen`) — verified `0.dp`-literal vs
    import balance per file.
  - `MuseButton`/`MuseChip` are called with named args, so their parameter order is
    satisfied; `Modifier.fillMaxWidth()`/`testTag(...)` survive as the component's
    `modifier`.
  - `AnimatedVisibility` + `fadeIn` + `slideInVertically` + `MutableTransitionState`
    come from `androidx.compose.animation` (already on the classpath, used by the
    pilot's `JobsScreen`); generic `MuseMotion.standard<T>()` infers `Float`/
    `IntOffset` at the two call sites.
  - Brace/paren balance and top-level declaration text verified identical to
    `origin/main` (ignoring line position) for all eight files.

## Residual risks

1. **Compilation unverified locally** (Android SDK absent). Mitigated by the
   self-review above; CI is the gate. Lowest-confidence lines are the two
   `AnimatedVisibility` entrance expressions (`AuditScreen.AuditCard`,
   `LedgerTimelineScreen.LedgerRow`) — standard APIs on the classpath; if CI ever
   flags one, the row falls back to a plain `MuseCard` (one-line change).
2. **Per-row `MutableTransitionState` in a `LazyColumn`** re-triggers the appearance
   animation when rows recycle on scroll (same intentional, subtle behavior the pilot
   shipped in `JobsScreen`). A reviewer may prefer animate-on-first-composition — a
   taste call, not a correctness issue.
3. **Semantic-color preservation by design choice.** Audit/Ledger status
   `AssistChip`s and `Surface(CircleShape)` `colorOn` dots were **kept** (not forced
   into `MuseChip`/`MuseStatusDot`) precisely because those components can't carry the
   domain result/approval/category color the formatting layer computes. If the brief
   intended a hard "all chips → MuseChip", these are the lines to revisit — but doing
   so would silently drop failure-red / approval-state / category signals.
4. **Tinted source cards lose their fill** (`errorContainer`/`secondary`/
   `tertiaryContainer` → uniform `MuseCard`). The state signal was re-expressed via
   text/icon color (`FailedVerificationCard`, `ImpactReportCard`, Research
   `ContradictionView`/`HintCard`). This matches the brand "value not effects" rule
   and the pilot's `JobDetailScreen`, but is a deliberate visual change a reviewer
   should eyeball on a real device.
5. **Section titles shift from M3 `primary` to `JarvisSignal`** (signal-bright) when a
   `Text(...primary)` becomes a `MuseSectionHeader` (Knowledge, Research,
   LedgerEventDetail) — the intended branded treatment (matches the pilot), a pure
   presentation change.
6. **No screens were structurally changed** — same composables, same state, same nav,
   same test tags. Default runtime behavior is unchanged; this is a pure presentation
   diff. Strictly additive / opt-in by nature.
