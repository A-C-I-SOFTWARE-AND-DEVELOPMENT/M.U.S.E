package com.aci.hermes.ui.screens.control

import android.app.Application
import androidx.test.core.app.ApplicationProvider
import com.aci.hermes.testutil.isolatedSettings
import com.aci.hermes.util.LogBuffer
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/**
 * Control screen is where the owner flips autonomy / safety gates / emergency
 * stop — every irreversible toggle must surface a confirmation warning before
 * it commits. These tests lock that gate in place.
 */
@OptIn(ExperimentalCoroutinesApi::class)
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [33])
class ControlViewModelTest {

    private val dispatcher = UnconfinedTestDispatcher()

    private fun newVm(): ControlViewModel {
        val app = ApplicationProvider.getApplicationContext<Application>()
        // Isolated settings store → each test starts from a clean baseline,
        // so a sibling test's committed emergency-stop never leaks in.
        val settings = isolatedSettings(app)
        // Null cockpit client → honest "disconnected" placeholders, no network.
        return ControlViewModel(app, settings, LogBuffer(), cockpitClient = null)
    }

    @Before
    fun setUp() {
        Dispatchers.setMain(dispatcher)
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    @Test
    fun `emergency stop is gated behind a confirmation warning`() = runTest(dispatcher) {
        val vm = newVm()
        advanceUntilIdle()
        assertNull("no warning until requested", vm.state.value.pendingWarning)

        // Requesting the stop only stages a warning — it does NOT engage yet.
        vm.requestEmergencyStop()
        val warning = vm.state.value.pendingWarning
        assertNotNull("emergency stop must confirm first", warning)
        assertFalse("must not engage before confirmation", vm.state.value.emergencyStopEngaged)

        // Confirming commits the stop.
        vm.confirmPendingWarning()
        advanceUntilIdle()
        assertTrue(vm.state.value.emergencyStopEngaged)
        assertNull(vm.state.value.pendingWarning)
    }

    @Test
    fun `dismissing a pending warning aborts the change`() = runTest(dispatcher) {
        val vm = newVm()
        advanceUntilIdle()
        vm.requestEmergencyStop()
        assertNotNull(vm.state.value.pendingWarning)
        vm.dismissPendingWarning()
        assertNull(vm.state.value.pendingWarning)
        assertFalse(vm.state.value.emergencyStopEngaged)
    }

    @Test
    fun `releasing an engaged emergency stop clears it`() = runTest(dispatcher) {
        val vm = newVm()
        advanceUntilIdle()
        vm.requestEmergencyStop()
        vm.confirmPendingWarning()
        advanceUntilIdle()
        assertTrue(vm.state.value.emergencyStopEngaged)
        vm.releaseEmergencyStop()
        advanceUntilIdle()
        assertFalse(vm.state.value.emergencyStopEngaged)
    }
}
