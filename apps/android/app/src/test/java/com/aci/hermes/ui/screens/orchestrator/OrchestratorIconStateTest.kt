package com.aci.hermes.ui.screens.orchestrator

import com.aci.hermes.ui.components.JarvisIconState
import org.junit.Assert.assertEquals
import org.junit.Test

class OrchestratorIconStateTest {

    @Test fun engaged_emergency_stop_takes_priority_over_everything() {
        val s = OrchestratorViewModel.computeIconState(
            engaged = true, pendingCritical = true, pendingAny = true, queueRunning = true,
        )
        assertEquals(JarvisIconState.CRITICAL, s)
    }

    @Test fun pending_critical_approval_drives_critical_even_without_emergency_stop() {
        val s = OrchestratorViewModel.computeIconState(
            engaged = false, pendingCritical = true, pendingAny = true, queueRunning = false,
        )
        assertEquals(JarvisIconState.CRITICAL, s)
    }

    @Test fun any_pending_approval_drives_alert_when_not_critical() {
        val s = OrchestratorViewModel.computeIconState(
            engaged = false, pendingCritical = false, pendingAny = true, queueRunning = false,
        )
        assertEquals(JarvisIconState.ALERT, s)
    }

    @Test fun running_queue_drives_working_when_no_approvals_pending() {
        val s = OrchestratorViewModel.computeIconState(
            engaged = false, pendingCritical = false, pendingAny = false, queueRunning = true,
        )
        assertEquals(JarvisIconState.WORKING, s)
    }

    @Test fun otherwise_idle() {
        val s = OrchestratorViewModel.computeIconState(
            engaged = false, pendingCritical = false, pendingAny = false, queueRunning = false,
        )
        assertEquals(JarvisIconState.IDLE, s)
    }
}
