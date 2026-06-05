package com.aci.hermes.ui.screens.orchestrator

import android.app.Application
import androidx.test.core.app.ApplicationProvider
import com.aci.hermes.data.cockpit.HermesCockpitClient
import com.aci.hermes.data.orchestrator.HermesTaskRepository
import com.aci.hermes.data.orchestrator.PromptBuilder
import com.aci.hermes.testutil.MainDispatcherRule
import com.aci.hermes.testutil.isolatedSettings
import com.aci.hermes.util.LogBuffer
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@OptIn(ExperimentalCoroutinesApi::class)
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [33])
class OrchestratorViewModelTest {

    @get:Rule
    val mainDispatcherRule = MainDispatcherRule(UnconfinedTestDispatcher())

    private fun newVm(): OrchestratorViewModel {
        val app = ApplicationProvider.getApplicationContext<Application>()
        return mainDispatcherRule.register(OrchestratorViewModel(
            application = app,
            settings = isolatedSettings(app),
            tasksRepo = HermesTaskRepository(app),
            promptBuilder = PromptBuilder(),
            logBuffer = LogBuffer(),
            cockpitClient = HermesCockpitClient(endpointProvider = { "" }, tokenProvider = { null }),
        ))
    }

    @Test
    fun `initial state has the default tool profiles and no running service`() = runTest {
        val vm = newVm()
        advanceUntilIdle()
        val state = vm.state.value
        assertTrue("default tool profiles should be present", state.tools.isNotEmpty())
        assertFalse("no foreground service in a unit test", state.serviceRunning)
    }

    @Test
    fun `copying a prompt for an unknown task is a safe no-op`() {
        val vm = newVm()
        vm.copyPromptForTask("does-not-exist")
        // byId returns null → early return, no snackbar, no crash.
        assertNull(vm.state.value.snackbar)
    }

    @Test
    fun `snackbar can be consumed`() {
        val vm = newVm()
        vm.consumeSnackbar()
        assertNull(vm.state.value.snackbar)
    }
}
