package com.aci.hermes.data.gateway

import kotlinx.coroutines.flow.toList
import kotlinx.coroutines.launch
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test

/**
 * Encodes the spec-level invariants for serious and critical
 * confirmations. Read these tests if anyone proposes loosening the
 * approval flow — they describe what users are guaranteed.
 */
@OptIn(ExperimentalCoroutinesApi::class)
class SeriousAndCriticalActionTest {

    @Test
    fun `serious action requires two separate confirmation events`() = runTest(UnconfinedTestDispatcher()) {
        val client = MockGatewayClient()
        val collected = mutableListOf<GatewayEvent>()
        val job = launch { client.events.toList(collected) }

        client.connect()

        val requested = client.requestApproval(
            actionId = "delete_branch",
            summary = "Delete the long-lived feature branch.",
            riskClass = ApprovalRiskClass.SERIOUS,
        )

        // One confirmation is NOT enough — the reducer must still show
        // the approval pending.
        client.confirmSerious(requested.approvalId, "token-a")
        val afterFirst = GatewayEventReducer.reduceAll(GatewayUiState(), collected)
        val stillPending = afterFirst.pendingApprovals
            .firstOrNull { it.approvalId == requested.approvalId }
        assertNotNull(
            "After only one serious confirmation the approval must remain pending",
            stillPending,
        )
        assertEquals(
            "Reducer must show 1 of 2 confirmations after the first event",
            1,
            stillPending!!.confirmationsSeen,
        )

        // Same token twice is rejected — guards against a double-tap
        // accidentally satisfying both confirmations.
        try {
            client.confirmSerious(requested.approvalId, "token-a")
            fail("Re-using the same confirmation token must throw IllegalStateException")
        } catch (_: IllegalStateException) {
            // expected
        }

        // A *different* token completes the serious approval.
        client.confirmSerious(requested.approvalId, "token-b")
        val afterSecond = GatewayEventReducer.reduceAll(GatewayUiState(), collected)
        assertNull(
            "After two distinct serious confirmations the approval must clear",
            afterSecond.pendingApprovals.firstOrNull { it.approvalId == requested.approvalId },
        )

        // Two ApprovalGrantedEvents with confirmation_index 1 and 2 must
        // appear on the spine.
        val grants = collected.filterIsInstance<ApprovalGrantedEvent>()
            .filter { it.approvalId == requested.approvalId }
        assertEquals(2, grants.size)
        assertEquals(listOf(1, 2), grants.map { it.confirmationIndex })

        job.cancel()
    }

    @Test
    fun `critical action requires impact report and rejects empty reports`() = runTest(UnconfinedTestDispatcher()) {
        val client = MockGatewayClient()
        val collected = mutableListOf<GatewayEvent>()
        val job = launch { client.events.toList(collected) }

        client.connect()

        val requested = client.requestApproval(
            actionId = "rotate_signing_key",
            summary = "Rotate Play Store signing key.",
            riskClass = ApprovalRiskClass.CRITICAL,
        )

        // Confirm method *requires* an impact report at compile time.
        // The runtime validates non-empty fields.
        try {
            client.confirmCritical(
                requested.approvalId,
                ImpactReport(
                    summary = "  ",
                    blastRadius = "all_releases",
                    reversibility = "irreversible",
                    rollbackPlan = "open ticket",
                ),
            )
            fail("Empty impact summary must throw IllegalArgumentException")
        } catch (_: IllegalArgumentException) {
            // expected
        }

        try {
            client.confirmCritical(
                requested.approvalId,
                ImpactReport(
                    summary = "rotate",
                    blastRadius = "all_releases",
                    reversibility = "irreversible",
                    rollbackPlan = "  ",
                ),
            )
            fail("Empty rollback plan must throw IllegalArgumentException")
        } catch (_: IllegalArgumentException) {
            // expected
        }

        val impact = ImpactReport(
            summary = "Rotate Play signing key.",
            blastRadius = "all_releases",
            reversibility = "irreversible",
            affectedResources = listOf("play_store"),
            rollbackPlan = "Open emergency Play Console support ticket.",
        )
        client.confirmCritical(requested.approvalId, impact)

        // The grant event carries the blast radius in the note so an
        // auditor can correlate without reconstructing the report.
        val grant = collected.filterIsInstance<ApprovalGrantedEvent>()
            .last { it.approvalId == requested.approvalId }
        assertTrue(
            "Critical grant note must reference the impact report",
            grant.note?.contains(impact.blastRadius) == true,
        )

        val state = GatewayEventReducer.reduceAll(GatewayUiState(), collected)
        assertNull(
            "Critical approval must clear once confirmed with an impact report",
            state.pendingApprovals.firstOrNull { it.approvalId == requested.approvalId },
        )

        job.cancel()
    }

    @Test
    fun `grantApproval on a serious approval is refused`() = runTest(UnconfinedTestDispatcher()) {
        // Protects against a future UI bug that wires the "Grant"
        // standard-class button to a serious-class approval.
        val client = MockGatewayClient()
        client.connect()

        val req = client.requestApproval("force_push", "force push branch", ApprovalRiskClass.SERIOUS)
        try {
            client.grantApproval(req.approvalId)
            fail("grantApproval must reject a serious-class approval")
        } catch (_: IllegalStateException) {
            // expected
        }
    }

    @Test
    fun `grantApproval on a critical approval is refused`() = runTest(UnconfinedTestDispatcher()) {
        val client = MockGatewayClient()
        client.connect()

        val req = client.requestApproval("rotate_key", "rotate key", ApprovalRiskClass.CRITICAL)
        try {
            client.grantApproval(req.approvalId)
            fail("grantApproval must reject a critical-class approval")
        } catch (_: IllegalStateException) {
            // expected
        }
    }
}
