# Known flaky tests

A durable log of intermittent (non-deterministic) test failures, their
diagnosis, and the recommended fix — so they aren't re-misdiagnosed and a
re-kick isn't mistaken for a real regression. GitHub Issues are disabled on
this repo, so known issues are tracked here.

---

## Android ViewModel tests — `Dispatchers.resetMain()` throws `IllegalStateException`

- **Status:** open (pre-existing test-infra debt; not a product bug)
- **Surface:** `Android JVM unit (testDebugUnitTest)` CI job
- **Observed on:** PR #262 (`OrchestratorViewModelTest`), PR #272
  (`TaskDetailViewModelTest`)

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
