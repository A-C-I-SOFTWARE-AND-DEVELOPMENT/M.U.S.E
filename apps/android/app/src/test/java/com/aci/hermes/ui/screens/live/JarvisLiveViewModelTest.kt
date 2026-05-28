package com.aci.hermes.ui.screens.live

import android.app.Application
import androidx.test.core.app.ApplicationProvider
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/**
 * Pins the live-screen view-model's command/emergency-stop state
 * machine. The VM is a thin holder over [JarvisLiveUiState]; these
 * tests are guard-rails so a refactor can't silently let a send slip
 * past an engaged emergency stop or leave a stale activity flag set.
 *
 * Avatar/icon projection lives in [JarvisLiveStateMapper] and is
 * covered by its own mapper test — this file only exercises the VM's
 * own transitions.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [33])
class JarvisLiveViewModelTest {

    private lateinit var vm: JarvisLiveViewModel

    @Before
    fun setUp() {
        val app = ApplicationProvider.getApplicationContext<Application>()
        vm = JarvisLiveViewModel(app)
    }

    @Test
    fun initial_state_has_no_flags_set() {
        val s = vm.state.value
        assertFalse(s.listening)
        assertFalse(s.thinking)
        assertFalse(s.working)
        assertFalse(s.speaking)
        assertFalse(s.approvalNeeded)
        assertFalse(s.blocked)
        assertFalse(s.emergencyStop)
        assertEquals("", s.command)
    }

    @Test
    fun on_command_change_updates_command_text() {
        vm.onCommandChange("audit the repo")
        assertEquals("audit the repo", vm.state.value.command)
    }

    @Test
    fun send_with_blank_command_is_a_no_op() {
        vm.onCommandChange("   ")
        vm.onSend()
        assertFalse(vm.state.value.thinking)
    }

    @Test
    fun send_with_command_starts_thinking() {
        vm.onCommandChange("ship the release")
        vm.onSend()
        val s = vm.state.value
        assertTrue(s.thinking)
        assertFalse(s.listening)
    }

    @Test
    fun send_is_blocked_while_emergency_stopped() {
        vm.confirmEmergencyStop()
        vm.onCommandChange("do the thing")
        vm.onSend()
        assertFalse(vm.state.value.thinking)
    }

    @Test
    fun confirm_emergency_stop_sets_flag_and_clears_activity() {
        vm.onCommandChange("work")
        vm.onSend()
        assertTrue(vm.state.value.thinking)

        vm.requestEmergencyConfirm()
        assertTrue(vm.showEmergencyConfirm.value)

        vm.confirmEmergencyStop()
        val s = vm.state.value
        assertTrue(s.emergencyStop)
        assertFalse(s.thinking)
        assertFalse(s.working)
        assertFalse(s.speaking)
        assertFalse(s.listening)
        assertFalse(vm.showEmergencyConfirm.value)
    }

    @Test
    fun release_emergency_stop_clears_the_flag() {
        vm.confirmEmergencyStop()
        assertTrue(vm.state.value.emergencyStop)
        vm.releaseEmergencyStop()
        assertFalse(vm.state.value.emergencyStop)
    }

    @Test
    fun status_sheet_open_and_dismiss_toggle_visibility() {
        assertFalse(vm.showStatusSheet.value)
        vm.openStatusSheet()
        assertTrue(vm.showStatusSheet.value)
        vm.dismissStatusSheet()
        assertFalse(vm.showStatusSheet.value)
    }

    @Test
    fun dismiss_emergency_confirm_hides_the_dialog_without_stopping() {
        vm.requestEmergencyConfirm()
        assertTrue(vm.showEmergencyConfirm.value)
        vm.dismissEmergencyConfirm()
        assertFalse(vm.showEmergencyConfirm.value)
        assertFalse(vm.state.value.emergencyStop)
    }

    @Test
    fun approve_approval_clears_gate_and_starts_working() {
        vm.approveApproval()
        val s = vm.state.value
        assertFalse(s.approvalNeeded)
        assertTrue(s.working)
    }
}
