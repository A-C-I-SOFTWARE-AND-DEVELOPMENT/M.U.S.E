# muse — Memory Transparency

The Memory screen is the owner's window into everything muse
remembers. It exists so the owner can:

- **See** what Jarvis thinks it knows, broken down by category.
- **Correct** any item whose content is wrong.
- **Delete** any item Jarvis should forget.
- **Understand** where each item came from, how confident Jarvis is in
  it, and how long it is supposed to live.

Privacy and safety rules are enforced *at the display layer* so a bug
or stale gateway response cannot leak a secret or a stored identity
to the screen.

## Where it lives in the app

- Tap the overflow menu (`⋮`) on the Orchestrator dashboard and pick
  **Memory**.
- Behind the scenes: `Screen.Memory` in
  `app/src/main/java/com/aci/hermes/ui/navigation/Screen.kt`, routed
  from `HermesNavGraph.kt` to `MemoryScreen`.

## Data model

`apps/android/app/src/main/java/com/aci/hermes/data/memory/MemoryModels.kt`

| Type | Purpose |
|---|---|
| `MemoryItem` | One thing Jarvis remembers: id, category, title, content, durability, confidence, provenance, tags, timestamps, and the redacted/hidden flags applied at display time. |
| `MemoryCategory` | `OWNER_PREFERENCE`, `PROJECT_MEMORY`, `WORKFLOW_LESSON`, `TASK_CONTEXT`, `DECISION_RECORD`, `SOCIAL_SPEECH_PATTERN`, `SESSION_MEMORY`. |
| `MemoryDurability` | `EPHEMERAL`, `SESSION`, `SHORT_TERM`, `LONG_TERM`, `PERMANENT`. |
| `MemoryConfidence` | `LOW`, `MEDIUM`, `HIGH`, `CONFIRMED`. After an owner correction, confidence is set to `CONFIRMED`. |
| `MemoryProvenance` | Where this memory was captured: source label, optional session id, timestamp, and an optional human note. |
| `MemoryAction` | Owner action emitted as an event on the repository's `actions` `SharedFlow`. Today this is logged via `LogBuffer`; the runtime bridge subscribes here when the gateway sync ships. Variants: `Correct`, `Delete`, `Hide`, `Reveal`. |

## Categories

| Category | Example | Notes |
|---|---|---|
| Owner Preference | "Direct, plain English. Cut filler." | Permanent voice/style/stack defaults. |
| Project Memory | "Hermes orchestration uses five primitives." | Repository-scoped facts. |
| Workflow Lesson | "Tests live next to the code they cover." | Lessons learned, applied to future tasks. |
| Task Context | "Building Memory transparency UI." | Active task scratch space. |
| Decision Record | "No Hilt in the Android app." | Architectural decisions. |
| Social Speech Pattern | "Owner opens with a status sentence, not a salutation." | **Abstract patterns only — usernames/handles/identities are stripped.** |
| Session Memory | "Current focus." | Lives for one session. |

## Privacy filter (`MemoryRedactor`)

Every read goes through `MemoryRedactor.sanitize`, which enforces
three hard rules:

1. **No secrets are displayed.** Items whose content matches a known
   secret-key hint (`api_key=`, `bearer …`, `sk-…`, long
   mixed-alphanumeric tokens, etc.) are flagged `redacted = true`,
   their content replaced with `███ redacted ███`, and (except for
   `OWNER_PREFERENCE`) hidden from the list entirely.
2. **Social speech patterns carry abstract patterns, not
   identities.** Embedded emails, phone numbers, `@handles`, and
   `username: …` labels are replaced with `[identity]` /
   `[email]` / `[phone]` / `[handle]` placeholders before the
   content reaches the UI. Identities never appear next to a social
   pattern, even if the underlying store accidentally retained one.
3. **Temporary emotions stay ephemeral.** Items containing emotion
   words (`angry`, `frustrated`, `mood:`, …) that the runtime
   tagged as `LONG_TERM` or `PERMANENT` are demoted to `EPHEMERAL`
   at display time so a session-scoped mood spike cannot
   masquerade as durable memory.

These rules live in pure functions and are exercised by
`MemoryRedactorTest`.

## Screen anatomy

`apps/android/app/src/main/java/com/aci/hermes/ui/screens/memory/`

- `MemoryScreen.kt` — top-level Compose screen. Hosts the search
  field, filter row, list, and dialogs. Test tags exposed via
  `MemoryScreenTags` for instrumentation.
- `MemoryCard` (in `MemoryScreen.kt`) — one row in the list. Shows
  category pill, redaction badge if applicable, title, content
  preview, durability + confidence chips, and quick **correct** /
  **delete** icon buttons.
- `MemoryDetail.kt` — modal bottom sheet with the full item: full
  content, provenance, timestamps, tags, and actions.
- `MemoryDialogs.kt` —
  - `CorrectMemoryDialog`: edits the content, captures an optional
    reason, refuses to submit if the value is unchanged or blank.
  - `DeleteMemoryDialog`: requires the owner to type **DELETE** to
    confirm. Deletion is irreversible from the app.
- `MemoryFilter`, `MemorySearch` (in `MemoryScreen.kt`) — chip row
  for category filtering and an outlined text field for free-text
  search across title, content, tags, and category name.

## ViewModel and repository

- `MemoryViewModel` (`ui/screens/memory/MemoryViewModel.kt`) owns the
  `MemoryUiState` — query, active category, full list, visible
  (filtered) list, selected/correcting/deleting item, snackbar
  message. The filter logic lives in
  `MemoryViewModel.applyFilters`, a pure static function the unit
  tests target directly.
- `MemoryRepository` (`data/memory/MemoryRepository.kt`) wraps a
  `MutableStateFlow<List<MemoryItem>>` plus a `SharedFlow<MemoryAction>`
  for owner-side events. The repository ships with `MockMemorySeed`
  so the screen runs end-to-end before the gateway sync is wired;
  the seed deliberately includes a secret-looking entry, a
  username-bearing social pattern, and a "frustrated" long-term
  emotion so the redactor has work to do in development.

## Gateway/runtime hookup

The repository emits `MemoryAction` events on
`MemoryRepository.actions`. The current build:

- Logs every action to `LogBuffer` so they show up in Diagnostics.
- Leaves the gateway bridge as a TODO. When the gateway sync ships,
  subscribe to `memoryRepository.actions` from a service-scoped
  collector and forward each event to the gateway's memory endpoint.
  The action shape is already the contract.

Until then, mock data lives in-process only; corrections and
deletions reset on app restart.

## Tests

JVM unit tests under
`apps/android/app/src/test/java/com/aci/hermes/memory/`:

- `MemoryRedactorTest` — secret detection, identity stripping,
  emotion demotion, non-secret pass-through.
- `MemoryRepositoryTest` — `correct` emits a `Correct` action and
  bumps confidence; `delete` removes the item and emits a `Delete`
  action.
- `MemoryFiltersTest` — search by title/content/tag and category
  filter compose correctly.
- `MemoryViewModelTest` — list renders, secret entries don't reach
  the visible list, social patterns have no username, mood-spike
  demoted to ephemeral, detail opens/closes, correct/delete flows
  drive state changes correctly.

Run them:

```sh
cd apps/android
./gradlew :app:testDebugUnitTest
```

Assemble the APK:

```sh
cd apps/android
./gradlew assembleDebug
```

Both commands are green on this branch as of the initial check-in.
