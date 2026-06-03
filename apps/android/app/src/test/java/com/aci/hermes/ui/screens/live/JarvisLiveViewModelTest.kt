package com.aci.hermes.ui.screens.live

import android.app.Application
import androidx.test.core.app.ApplicationProvider
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/**
 * Smoke coverage for the living-avatar screen. We avoid virtual-time
 * advancement on purpose: the VM runs an unbounded ambient-life loop, so we
 * assert only the synchronous command / emergency-stop state transitions.
 */
@OptIn(ExperimentalCoroutinesApi::class)
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [33])
class JarvisLiveViewModelTest {

    private val dispatcher = UnconfinedTestDispatcher()

    private fun newVm(): JarvisLiveViewModel {
        val app = ApplicationProvider.getApplicationContext<Application>()
        // No avatar repo and no cockpit client → procedural body, no network.
        return JarvisLiveViewModel(app, avatarRepository = null, cockpitClient = null)
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
    fun `initial state is idle and ready for input`() {
        val vm = newVm()
        val state = vm.state.value
        assertEquals("", state.command)
        assertFalse(state.thinking)
        assertFalse(state.emergencyStop)
    }

    @Test
    fun `typing then sending moves into thinking`() {
        val vm = newVm()
        vm.onCommandChange("ship the build")
        assertEquals("ship the build", vm.state.value.command)
        vm.onSend()
        assertTrue(vm.state.value.thinking)
        assertFalse(vm.state.value.listening)
    }

    @Test
    fun `emergency stop confirm halts activity and release resumes`() {
        val vm = newVm()
        vm.onCommandChange("do work")
        vm.onSend()
        assertTrue(vm.state.value.thinking)

        vm.requestEmergencyConfirm()
        assertTrue(vm.showEmergencyConfirm.value)
        vm.confirmEmergencyStop()
        val stopped = vm.state.value
        assertTrue(stopped.emergencyStop)
        assertFalse("thinking must halt under emergency stop", stopped.thinking)
        assertFalse(vm.showEmergencyConfirm.value)

        vm.releaseEmergencyStop()
        assertFalse(vm.state.value.emergencyStop)
    }

    @Test
    fun `a blank command does not start thinking`() {
        val vm = newVm()
        vm.onSend()
        assertFalse(vm.state.value.thinking)
    }
}
