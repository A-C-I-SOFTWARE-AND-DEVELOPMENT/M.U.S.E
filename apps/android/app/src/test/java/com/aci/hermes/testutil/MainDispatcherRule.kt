package com.aci.hermes.testutil

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.TestDispatcher
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.setMain
import org.junit.rules.TestWatcher
import org.junit.runner.Description

/**
 * A JUnit4 rule that installs a [TestDispatcher] as `Dispatchers.Main` for the
 * duration of each test and removes it afterwards.
 *
 * ViewModel tests here override the **process-global** `Dispatchers.Main` so
 * their `viewModelScope` work runs on a controllable dispatcher. Doing that by
 * hand in `@Before`/`@After` (`setMain`/`resetMain`) is error-prone: ~21 classes
 * share one Robolectric JVM, and an inconsistency left by one class surfaces as
 * `resetMain()` throwing `IllegalStateException` in the next (see
 * `docs/testing/known-flaky-tests.md`). Centralising the set/reset in a single
 * `TestWatcher` makes the lifecycle uniform — `starting()` always pairs with
 * `finished()` — and gives exactly one owner of the global Main override.
 *
 * Use plain `runTest { ... }` inside tests that apply this rule: `runTest` picks
 * up the dispatcher installed as Main here, so passing the dispatcher to
 * `runTest` again would install a second, conflicting test main dispatcher.
 */
@OptIn(ExperimentalCoroutinesApi::class)
class MainDispatcherRule(
    val dispatcher: TestDispatcher = UnconfinedTestDispatcher(),
) : TestWatcher() {
    override fun starting(description: Description) {
        Dispatchers.setMain(dispatcher)
    }

    override fun finished(description: Description) {
        Dispatchers.resetMain()
    }
}
