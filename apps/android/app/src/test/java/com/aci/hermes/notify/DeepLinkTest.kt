package com.aci.hermes.notify

import com.aci.hermes.ui.navigation.Screen
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Verifies every [WorkEvent] deep-links to a real, existing destination —
 * approvals → Approvals, job lifecycle → Tasks, errors → Diagnostics.
 */
class DeepLinkTest {

    @Test
    fun `approval and blocked open the Approvals queue`() {
        assertEquals(Screen.Approvals.route, DeepLink.routeFor(WorkEvent.ApprovalRequired("a1", "")))
        assertEquals(Screen.Approvals.route, DeepLink.routeFor(WorkEvent.JobBlocked("j1", "")))
    }

    @Test
    fun `job lifecycle opens the Tasks list`() {
        assertEquals(Screen.Tasks.route, DeepLink.routeFor(WorkEvent.JobStarted("j1", "")))
        assertEquals(Screen.Tasks.route, DeepLink.routeFor(WorkEvent.JobCompleted("j1", "")))
        assertEquals(Screen.Tasks.route, DeepLink.routeFor(WorkEvent.ResearchComplete("j1", "")))
        assertEquals(Screen.Tasks.route, DeepLink.routeFor(WorkEvent.TestsFailed("j1", "", 1)))
    }

    @Test
    fun `failures, worker attention, and emergency open Diagnostics`() {
        assertEquals(Screen.Diagnostics.route, DeepLink.routeFor(WorkEvent.JobFailed("j1", "")))
        assertEquals(Screen.Diagnostics.route, DeepLink.routeFor(WorkEvent.WorkerNeedsAttention("w1", "")))
        assertEquals(Screen.Diagnostics.route, DeepLink.routeFor(WorkEvent.EmergencyStopTriggered("")))
    }

    @Test
    fun `every deep-link target is a known route`() {
        val known = setOf(Screen.Approvals.route, Screen.Tasks.route, Screen.Diagnostics.route)
        val events = listOf(
            WorkEvent.JobStarted("j", ""),
            WorkEvent.JobBlocked("j", ""),
            WorkEvent.ApprovalRequired("a", ""),
            WorkEvent.JobCompleted("j", ""),
            WorkEvent.JobFailed("j", ""),
            WorkEvent.WorkerNeedsAttention("w", ""),
            WorkEvent.ResearchComplete("j", ""),
            WorkEvent.TestsFailed("j", "", 2),
            WorkEvent.EmergencyStopTriggered(""),
        )
        events.forEach { assertTrue(DeepLink.routeFor(it) in known) }
    }
}
