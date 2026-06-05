package com.aci.hermes.testutil

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelStore
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
 * hand in `@Before`/`@After` (`setMain`/`resetMain`) is error-prone: ~24 classes
 * share one Robolectric JVM, and an inconsistency left by one class surfaces as
 * `resetMain()` throwing `IllegalStateException` in the next (see
 * `docs/testing/known-flaky-tests.md`). Centralising the set/reset in a single
 * `TestWatcher` makes the lifecycle uniform — `starting()` always pairs with
 * `finished()` — and gives exactly one owner of the global Main override.
 *
 * Use plain `runTest { ... }` inside tests that apply this rule: `runTest` picks
 * up the dispatcher installed as Main here, so passing the dispatcher to
 * `runTest` again would install a second, conflicting test main dispatcher.
 *
 * ## Why this also clears ViewModels
 *
 * Centralising set/reset was necessary but not sufficient (see #303): the
 * ViewModels under test start **long-lived `viewModelScope` collectors** in
 * `init` (e.g. an infinite settings-flow `collect`) that nothing cancels. A
 * leaked collector from one class is still live on the (now-reset) test Main
 * when the next class installs its own override, tripping `TestMainDispatcher`'s
 * guard — the residual flake. To stop the leak at the source, register each
 * ViewModel via [register]; the rule holds them in a [ViewModelStore] and
 * [ViewModelStore.clear] (which cancels each `viewModelScope`) runs in
 * `finished()` **before** `resetMain()`, while the test dispatcher is still
 * installed as Main. Registration is opt-in and additive — tests that don't
 * call [register] are unaffected.
 */
@OptIn(ExperimentalCoroutinesApi::class)
class MainDispatcherRule(
    val dispatcher: TestDispatcher = UnconfinedTestDispatcher(),
) : TestWatcher() {
    private val viewModelStore = ViewModelStore()
    private var registered = 0

    /**
     * Track [viewModel] so its `viewModelScope` is cancelled when the test
     * finishes (before Main is reset). Returns the same instance so call sites
     * can wrap construction inline: `val vm = rule.register(MyViewModel(...))`.
     */
    fun <T : ViewModel> register(viewModel: T): T {
        viewModelStore.put("vm-${registered++}", viewModel)
        return viewModel
    }

    override fun starting(description: Description) {
        Dispatchers.setMain(dispatcher)
    }

    override fun finished(description: Description) {
        // Cancel registered ViewModels' viewModelScope coroutines while the
        // test dispatcher is still Main, then hand Main back.
        viewModelStore.clear()
        Dispatchers.resetMain()
    }
}
