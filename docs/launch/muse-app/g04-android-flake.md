# G0.4 — stabilize the flaky `AvatarPickerViewModelTest` (snapshot)

**Grain:** G0.4 — de-flake the intermittently-failing Android test
`AvatarPickerViewModelTest.saving a previewed built-in persists it`.
**Branch:** `claude/muse-app-g04-android-flake`
**Base commit:** `d4c66c0927ea904187b697135111b75d1e2ca77e` (`git rev-parse origin/main`).
**Worktree:** `/home/user/hermes-agent/.claude/worktrees/agent-a87466bd0c145cb11`.
**Path taken:** **real stabilization** (not the `@Ignore` quarantine fallback).

## Intent

`saving a previewed built-in persists it` reddened multiple Android CI runs
(#398, #401) with an `AssertionError` around line 97 while passing in parallel
runs — a classic main-dispatcher / coroutine-timing flake. Make that one test
deterministic by mirroring the repo's existing passing pattern, without touching
the ViewModel, main sources, Gradle, or any other test.

## Root cause (by inspection)

The pre-change test used `MainDispatcherRule()` (its default
`UnconfinedTestDispatcher` as `Dispatchers.Main`) plus a **real-time**
`awaitUntil { … is Saved }` poll. The save path is:

```
vm.save() → viewModelScope.launch {           // Main == UnconfinedTestDispatcher
    repo.save(draft) → store.edit { … }        // DataStore actor
    _state.value = Saved
}
```

The injected DataStore was built with `PreferenceDataStoreFactory.create { prefsFile }`
— **no `scope` argument** — so its actor runs on DataStore's own internal
`CoroutineScope(Dispatchers.IO + SupervisorJob())`. The `store.edit` write (and
therefore the subsequent `_state.value = Saved`) completes on a **real wall-clock
IO timeline that no `TestScheduler` controls**. The test then polled in real time.
Under contended CI parallelism the DataStore write occasionally landed after the
poll deadline → the `as AvatarPickerState.Saved` cast/assert failed. This is
exactly the failure mode `apps/android/app/src/test/.../testutil/Await.kt` already
calls out by name (its 15s timeout bump was a prior partial mitigation, not a
fix).

Note this is a *different* flake from the `resetMain()`-teardown one in
`docs/testing/known-flaky-tests.md`; that one was already addressed by
`MainDispatcherRule` + `register(...)`. This grain fixes the **save-state timing
race** specifically.

## Fix — pin every coroutine consumer to one test scheduler

Mirror the deterministic pattern already used by `JobsViewModelTest` and
`DevicePairingViewModelTest` (one shared `StandardTestDispatcher`, injected
everywhere, driven by `runTest { … advanceUntilIdle() }`), and additionally pin
the **DataStore actor** to that same scheduler so the write is virtual too:

1. `private val dispatcher = StandardTestDispatcher()` — one scheduler `S`.
2. `MainDispatcherRule(dispatcher)` — installs `S` as `Dispatchers.Main`
   (so `viewModelScope` runs on `S`).
3. `private val dataStoreScope = CoroutineScope(dispatcher + Job())` passed via
   `PreferenceDataStoreFactory.create(scope = dataStoreScope) { prefsFile }` —
   the DataStore actor now runs its writes on `S` instead of real `Dispatchers.IO`.
   **This is the linchpin**: it puts `store.edit` on the scheduler so
   `advanceUntilIdle()` can drain it.
4. Cockpit `ioDispatcher = dispatcher` (was `Dispatchers.Unconfined`) — keeps the
   benign offline `init` work on `S` too (it still maps to `Unreachable`).
5. The `saving …` test is now `= runTest { … }`; the real-time `awaitUntil` poll
   is replaced with `advanceUntilIdle()` before asserting `Saved`. Per the
   `MainDispatcherRule` doc, plain `runTest {}` adopts the scheduler already
   installed as Main, so its `advanceUntilIdle()` advances `S`.
6. `@After tearDown { dataStoreScope.cancel() }` cancels the actor scope so no
   DataStore coroutine leaks onto the (shared, ~24-class) Robolectric JVM Main —
   the same no-global-Main-leak discipline `MainDispatcherRule` enforces for each
   registered `viewModelScope`. JUnit runs `@After` before the rule's
   `finished()` (`viewModelStore.clear()` → `resetMain()`), so by the time Main is
   reset both the actor scope and the `viewModelScope` are already cancelled.

The other two tests are unaffected in behavior:
- `starts idle …` reads the initial `Idle` value; the `init` `repo.current()`
  coroutine is merely queued on the un-advanced scheduler (fresh isolated
  DataStore ⇒ would stay `Idle` anyway). Added a clarifying comment only.
- `selecting a built-in …` sets `_state` synchronously (no coroutine); no advance
  needed. Comment only.

## Owned / changed files

- `apps/android/app/src/test/java/com/aci/hermes/ui/screens/avatar/AvatarPickerViewModelTest.kt`
  — the only code file changed (the fix above; imports swapped
  `Dispatchers`/`awaitUntil` → `CoroutineScope`/`Job`/`cancel`/`StandardTestDispatcher`/
  `advanceUntilIdle`/`runTest`/`After`).
- `docs/launch/muse-app/g04-android-flake.md` — this snapshot.

No edit to `AvatarPickerViewModel.kt`, `AvatarRepository.kt`, the shared
`testutil/` helpers, Gradle, or any sibling test. The shared `awaitUntil` helper
stays — four other tests still use it; only this file stops using it.

## Validation

- **JDK:** OpenJDK 21.0.10 — present.
- **Android SDK:** **NOT available** in this sandbox (`ANDROID_HOME` /
  `ANDROID_SDK_ROOT` unset, no `apps/android/local.properties`). The Android JVM
  unit suite (`:app:testDebugUnitTest`) **cannot be run locally**; CI is the gate
  — and because the failure is ~1-in-N, the orchestrator must re-run the Android
  job several times before considering it closed (same protocol as
  `docs/testing/known-flaky-tests.md`).
- **Self-review performed** (compensating for the missing SDK):
  - `PreferenceDataStoreFactory.create(scope = …) { produceFile }` — `scope` is a
    defaulted named parameter ahead of the trailing `produceFile` lambda in
    DataStore (pinned `datastore = "1.1.1"` in `apps/android/gradle/libs.versions.toml`);
    the call only **adds** the named `scope` arg to the trailing-lambda form the
    file already used.
  - The shared-`dispatcher`-everywhere + `runTest`/`advanceUntilIdle` shape is
    copied verbatim from `JobsViewModelTest` (lines 21-24, 41-52) and
    `DevicePairingViewModelTest`, which are green on `main`.
  - No ktlint/detekt/spotless plugin is applied in the Android Gradle build, so
    import ordering won't fail CI; ordering still follows the file's existing
    alphabetical-by-FQN convention.
  - `register(...)` is retained for the VM, so the existing per-VM
    `viewModelScope` cancellation still runs at `finished()`.

## Residual risks

1. **Compilation/execution unverified locally** (Android SDK absent). Mitigated
   by the self-review above and by copying a known-green sibling pattern; CI is
   the gate. The single load-bearing API assumption is the
   `PreferenceDataStoreFactory.create(scope = …)` overload — standard in
   DataStore 1.x and consistent with how the repo already calls `create`.
2. **`runTest` scheduler adoption** — the fix relies on plain `runTest {}` reusing
   the `TestDispatcher` installed as `Dispatchers.Main` (documented behavior, and
   exactly what the green sibling tests depend on). If a future coroutines-test
   bump changed that, `advanceUntilIdle()` would no longer drain `S`; but the same
   change would also break the existing sibling tests, so it would not be silent.
3. **Still Robolectric** — the test class keeps `@RunWith(RobolectricTestRunner)`
   / `@Config(sdk = [33])` because it constructs real `AndroidViewModel` /
   `AvatarImageStore` / DataStore objects. The fix removes the *timing* flake, not
   the Robolectric dependency.
4. **No behavior change to product code.** Default runtime paths are byte-for-byte
   unchanged; this is a test-only de-flake, so it is a strictly-additive /
   non-owner-gated follow-up.
