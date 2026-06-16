# Known flaky tests

A durable log of intermittent (non-deterministic) test failures, their
diagnosis, and the recommended fix — so they aren't re-misdiagnosed and a
re-kick isn't mistaken for a real regression. GitHub Issues are disabled on
this repo, so known issues are tracked here.

---

## Android ViewModel tests — `Dispatchers.resetMain()` throws `IllegalStateException`

- **Status:** fix applied (awaiting CI confirmation) — the leaked-`viewModelScope`
  root cause below is now addressed: `MainDispatcherRule` cancels each
  registered ViewModel's `viewModelScope` (via a `ViewModelStore.clear()`) in
  `finished()` **before** `resetMain()`, and every ViewModel test wraps its VM
  construction in `mainDispatcherRule.register(...)`. **This could not be
  validated locally** (the change was authored in an environment without the
  Android SDK); the `Android JVM unit (testDebugUnitTest)` CI job is the
  validation gate, and because the failure is ~1-in-N a single green run is not
  proof — re-run the job several times before considering it closed.
- **Surface:** `Android JVM unit (testDebugUnitTest)` CI job
- **Observed on:** PR #262, #272 (`resetMain` side); PR #297 after #303
  (`setMain` side)
- **History:** #303 centralised set/reset in `MainDispatcherRule` (necessary,
  not sufficient); the follow-up adds per-VM scope cancellation to stop the leak
  at the source.

### Why #303 wasn't enough (refined root cause)

`MainDispatcherRule` guarantees `setMain`/`resetMain` are *paired per test method*,
but the tests construct ViewModels whose `init` starts **long-lived
`viewModelScope` coroutines** (e.g. an infinite settings-flow `collect`) and
never cancel them (no `onCleared`/scope cancel in the test). A leaked collector
from one class can still be live when the next class's rule installs a new Main
override, tripping `TestMainDispatcher`'s guard. The real fix is to stop the
leak, not just centralise the override:

- Cancel each ViewModel's `viewModelScope` at test end (e.g. a small helper that
  calls the VM's `onCleared`/closes the scope in `@After`/the rule's `finished()`),
  **or** inject the `CoroutineScope`/dispatcher into the ViewModels so tests own a
  scope they can cancel, **or** make `init` collectors structured so they end when
  the test scope ends.
- This **must** be validated by running `:app:testDebugUnitTest` many times on an
  Android-capable machine — the failure is ~1-in-N, so a single green run is not
  proof (that is exactly how #303 looked green before this recurrence).

### Symptom

A single ViewModel test fails intermittently (green on `main`, ~1-in-N runs
under CI parallel load), e.g.:

```
TaskDetailViewModelTest > a brand new task starts in the new state with a prompt preview FAILED
    java.lang.IllegalStateException at TaskDetailViewModelTest.kt:53
        Caused by: java.lang.Throwable at TestMainDispatcher.kt:71
777 tests completed, 1 failed
```

`TaskDetailViewModelTest.kt:53` is `Dispatchers.resetMain()` in `@After` — the
failure is in teardown, **not** in any assertion. (The fields that test asserts
are populated synchronously in `TaskDetailViewModel.init`, so it is not a
state/preview race — a closed PR, #278, misdiagnosed it as one; that change was
harmless but ineffective. Do not revive it.)

### Root cause

~21 ViewModel test classes each override the **process-global**
`Dispatchers.Main` via `setMain(...)`/`resetMain()` in `@Before`/`@After`
(`apps/android/app/src/test/.../*ViewModelTest.kt`). Run in one Robolectric JVM,
an inconsistency left by one class surfaces as `resetMain()` throwing in the
next. A likely contributor is mixing **`setMain(dispatcher)` with
`runTest(dispatcher)`** (e.g. `OrchestratorViewModelTest`): newer
kotlinx-coroutines-test installs its own test main dispatcher inside `runTest`,
which conflicts with an outer `setMain` and can leave the global override
inconsistent.

### Recommended fix (requires an env that can run the Android suite)

Validate by running `:app:testDebugUnitTest` repeatedly (intermittent):

1. A shared `MainDispatcherRule` (JUnit4 `TestWatcher`: `starting()`→`setMain`,
   `finished()`→`resetMain`) applied uniformly across the ViewModel tests.
2. Remove the `setMain` + `runTest(dispatcher)` overlap — let `runTest` own the
   Main dispatcher, or drop `runTest`'s dispatcher arg where `setMain` is used.

> Not patched blind during the cockpit build-out: that work ran in an
> environment without the Android SDK, and a wrong change to shared test
> infrastructure risks turning an intermittent flake into consistent failures
> across all 21 classes.

---

## Python — `tests/run_agent/test_primary_runtime_restore.py::...::test_wait_time_capped_at_8`

- **Status:** mitigated (hardened in the de-flake on the cockpit branch)

### Symptom & cause

The test patched the global `time.sleep` to a no-op, which made background
daemon threads in the 27k-test process busy-spin on `sleep`; under CI parallel
load that CPU starvation pushed the test into the 30s timeout (it passes in ~1s
in isolation). It earlier flaked as a call-count assertion (`assert_any_call`
fix) and later as a timeout.

### Mitigation applied

Gave the sleep mock a ~1 ms **real**-sleep `side_effect` so those threads yield
instead of busy-spinning, keeping the test fast and the assertion unchanged.
Sibling tests in the same class share the no-op-`time.sleep` pattern and could
flake similarly under enough load; apply the same `side_effect` if they do.

---

## Python — `tests/hermes_cli/test_web_server.py::TestPtyWebSocket::test_pub_broadcasts_to_events_subscribers`

- **Status:** documented, root-caused — **no product fix needed** (the server
  broadcast path is correct; this is a test-harness scheduling artifact under
  load).

### Symptom

Green on `main` and **8/8 in isolation (~1.4 s)**, but intermittently hits the
30 s global test timeout (`tests/conftest.py` `TimeoutError`) under
`pytest -n 4` full-suite load — observed in repeated back-to-back full-suite
runs locally:

```
FAILED tests/hermes_cli/test_web_server.py::TestPtyWebSocket::test_pub_broadcasts_to_events_subscribers
    TimeoutError: Test exceeded 30 second timeout   (tests/conftest.py)
```

### Root cause

Starlette's `TestClient.websocket_connect` runs the ASGI app on a background
`anyio` portal (a separate event-loop thread). The test performs a synchronous,
cross-thread websocket round-trip: `pub.send_text(...)` → server
`pub_ws` → `_broadcast_event` → `await sub.send_text(...)` →
`sub.receive_text()` **with no timeout**. Under CPU starvation (this test runs
inside the ~29k-test process on 4 workers) the portal's loop thread is scheduled
late, so the round-trip occasionally takes longer than the 30 s cap and the
no-timeout `receive_text()` blocks until the global timeout fires.

The frame is **delayed, not dropped**: `_broadcast_event`
(`hermes_cli/web_server.py`) copies the subscriber set under `_event_lock` and
`await sub.send_text(payload)` directly, and the test already waits up to 5 s for
the subscriber to register in `_event_channels` before publishing. There is no
lost-message race in the server once a subscriber is registered — so this is a
harness/scheduling artifact, **not** a pub/sub correctness bug. Do not "fix" the
broadcast code.

### Recommended fix (if it must be de-flaked)

Test-only, no product change — pick one: bound `sub.receive_text()` with an
explicit short receive timeout and `xfail`/skip on timeout; give the test a
longer per-test budget via `@pytest.mark.timeout(...)`; or move it to a
serial / low-parallelism lane. Leaving it as a documented load flake is also
acceptable — a re-kick is not a real regression.

### Sibling observations (same category, this sweep)

The same 27k-test CPU-starvation-vs-30 s-timeout pattern produced one-off
intermittent failures in
`tests/plugins/test_achievements_plugin.py::test_evaluate_all_stale_cache_serves_stale_and_refreshes_in_background`
(background cache-refresh thread timing; 8/8 in isolation). A *separate*,
genuine **test-isolation** bug surfaced in `tests/tui_gateway/test_goal_command.py`
(tests shared a hardcoded SessionDB key and raced across xdist workers) — that
one was a real defect and was fixed by giving each test a unique session key
(not a timeout flake).
