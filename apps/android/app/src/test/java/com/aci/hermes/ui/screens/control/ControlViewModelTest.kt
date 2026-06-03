package com.aci.hermes.ui.screens.control

import android.app.Application
import androidx.test.core.app.ApplicationProvider
import com.aci.hermes.testutil.awaitUntil
import com.aci.hermes.testutil.isolatedSettings
import com.aci.hermes.util.LogBuffer
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.resetMain
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
 *
 * The VM's `init` runs a one-shot `refresh()` that reads the settings store on
 * Dispatchers.IO and then replaces the whole state via the projector. We bind
 * Main to the real `Dispatchers.Unconfined` and **wait for that refresh to land
 * before mutating** (the projector populates `connectedServices`), so the
 * refresh can never clobber a subsequently-staged warning — the timing race
 * that previously only surfaced under CI's scheduler.
 */
@OptIn(ExperimentalCoroutinesApi::class)
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [33])
class ControlViewModelTest {

    private fun newVm(): ControlViewModel {
        val app = ApplicationProvider.getApplicationContext<Application>()
        // Isolated settings store → each test starts from a clean baseline.
        return ControlViewModel(app, isolatedSettings(app), LogBuffer(), cockpitClient = null)
    }

    /** Block until the one-shot init refresh has projected state (services set). */
    private fun ControlViewModel.awaitRefreshed() =
        awaitUntil(message = "init refresh projected state") {
            state.value.connectedServices.isNotEmpty()
        }

    @Before
    fun setUp() {
        Dispatchers.setMain(Dispatchers.Unconfined)
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    @Test
    fun `emergency stop is gated behind a confirmation warning`() {
        val vm = newVm()
        vm.awaitRefreshed()
        assertNull("no warning until requested", vm.state.value.pendingWarning)

        // Requesting the stop only stages a warning — it does NOT engage yet.
        vm.requestEmergencyStop()
        assertNotNull("emergency stop must confirm first", vm.state.value.pendingWarning)
        assertFalse("must not engage before confirmation", vm.state.value.emergencyStopEngaged)

        // Confirming commits the stop.
        vm.confirmPendingWarning()
        assertTrue(vm.state.value.emergencyStopEngaged)
        assertNull(vm.state.value.pendingWarning)
    }

    @Test
    fun `dismissing a pending warning aborts the change`() {
        val vm = newVm()
        vm.awaitRefreshed()
        vm.requestEmergencyStop()
        assertNotNull(vm.state.value.pendingWarning)
        vm.dismissPendingWarning()
        assertNull(vm.state.value.pendingWarning)
        assertFalse(vm.state.value.emergencyStopEngaged)
    }

    @Test
    fun `releasing an engaged emergency stop clears it`() {
        val vm = newVm()
        vm.awaitRefreshed()
        vm.requestEmergencyStop()
        vm.confirmPendingWarning()
        assertTrue(vm.state.value.emergencyStopEngaged)
        vm.releaseEmergencyStop()
        assertFalse(vm.state.value.emergencyStopEngaged)
    }
}
