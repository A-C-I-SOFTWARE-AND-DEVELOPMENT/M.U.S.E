package com.aci.hermes.ui.screens.home

import com.aci.hermes.data.jarvis.ApprovalRisk
import com.aci.hermes.data.jarvis.JarvisHomeState
import com.aci.hermes.data.jarvis.JarvisPresence
import com.aci.hermes.data.jarvis.PendingApproval
import com.aci.hermes.data.model.TargetTool
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The cockpit invariant: the emergency stop is always visible on
 * Home — never hidden, especially during serious/critical contexts.
 * The Compose screen routes its EmergencyStopButton visibility
 * through [HomeEmergencyStopGuard.shouldShowEmergencyStop], so this
 * test pins the contract from the JVM side.
 */
class HomeEmergencyStopVisibilityTest {

    @Test
    fun `idle quiet day still shows the emergency stop`() {
        val state = JarvisHomeState(presence = JarvisPresence.IDLE)
        assertTrue(HomeEmergencyStopGuard.shouldShowEmergencyStop(state))
    }

    @Test
    fun `serious approval pending still shows the emergency stop`() {
        val state = JarvisHomeState(
            presence = JarvisPresence.SERIOUS_ACTION_PENDING,
            pendingApprovals = listOf(seriousApproval()),
        )
        assertTrue(HomeEmergencyStopGuard.shouldShowEmergencyStop(state))
    }

    @Test
    fun `critical approval pending still shows the emergency stop`() {
        val state = JarvisHomeState(
            presence = JarvisPresence.CRITICAL_ACTION_PENDING,
            pendingApprovals = listOf(criticalApproval()),
        )
        assertTrue(HomeEmergencyStopGuard.shouldShowEmergencyStop(state))
    }

    @Test
    fun `gateway disconnected still shows the emergency stop`() {
        val state = JarvisHomeState(presence = JarvisPresence.GATEWAY_DISCONNECTED)
        assertTrue(HomeEmergencyStopGuard.shouldShowEmergencyStop(state))
    }

    @Test
    fun `emergency stop already engaged still shows the emergency stop`() {
        val state = JarvisHomeState(
            presence = JarvisPresence.EMERGENCY_STOP_ACTIVE,
            emergencyStopActive = true,
        )
        // The stop must always be visible — otherwise the owner has no
        // way to release it.
        assertTrue(HomeEmergencyStopGuard.shouldShowEmergencyStop(state))
    }

    @Test
    fun `every presence enum value passes the visibility guard`() {
        // Cheap exhaustive check: if a new presence enum is added
        // later, this test forces a deliberate decision about
        // visibility — the default must still be "shown".
        for (presence in JarvisPresence.entries) {
            val state = JarvisHomeState(presence = presence)
            assertTrue(
                "emergency stop must be visible in presence $presence",
                HomeEmergencyStopGuard.shouldShowEmergencyStop(state),
            )
        }
    }

    @Test
    fun `quiet day is detected when there is no task or approval or suggestion`() {
        assertTrue(HomeEmergencyStopGuard.isQuietDay(JarvisHomeState()))
    }

    @Test
    fun `quiet day is not detected when an approval is pending`() {
        val state = JarvisHomeState(pendingApprovals = listOf(seriousApproval()))
        assertFalse(HomeEmergencyStopGuard.isQuietDay(state))
    }

    @Test
    fun `confirm-dialog copy uses explicit owner-control language`() {
        assertTrue(
            "title must be a question",
            HomeEmergencyStopGuard.EMERGENCY_STOP_CONFIRM_TITLE.endsWith("?"),
        )
        val body = HomeEmergencyStopGuard.EMERGENCY_STOP_CONFIRM_BODY
        assertTrue("body must name owner action", body.contains("Owner action"))
        assertTrue("body must explain pause", body.contains("halt", ignoreCase = true))
        assertTrue("body must reassure about pending tasks", body.contains("Pending tasks"))
    }

    @Test
    fun `approval risk maps to the right presence`() {
        assertEquals(
            JarvisPresence.WAITING_FOR_APPROVAL,
            HomeEmergencyStopGuard.expectedPresenceFor(ApprovalRisk.LOW),
        )
        assertEquals(
            JarvisPresence.SERIOUS_ACTION_PENDING,
            HomeEmergencyStopGuard.expectedPresenceFor(ApprovalRisk.SERIOUS),
        )
        assertEquals(
            JarvisPresence.CRITICAL_ACTION_PENDING,
            HomeEmergencyStopGuard.expectedPresenceFor(ApprovalRisk.CRITICAL),
        )
    }

    private fun seriousApproval(): PendingApproval = PendingApproval(
        taskId = "t-serious",
        title = "Delete branch",
        target = TargetTool.CLAUDE_CODE,
        risk = ApprovalRisk.SERIOUS,
        reason = "Owner approval required before remote delete.",
    )

    private fun criticalApproval(): PendingApproval = PendingApproval(
        taskId = "t-critical",
        title = "Push to main",
        target = TargetTool.CLAUDE_CODE,
        risk = ApprovalRisk.CRITICAL,
        reason = "Force-push to main requires explicit owner consent.",
    )
}
