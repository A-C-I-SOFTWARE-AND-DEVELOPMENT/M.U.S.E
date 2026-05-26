package com.aci.hermes.approvals

import com.aci.hermes.events.EventSpine
import com.aci.hermes.events.JarvisEvent
import com.aci.hermes.safety.EmergencyStop
import com.aci.hermes.safety.RiskTier
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ApprovalQueueTest {

    private fun newQueue(): Triple<ApprovalQueue, EventSpine, EmergencyStop> {
        val spine = EventSpine()
        val stop = EmergencyStop()
        return Triple(ApprovalQueue(spine, stop), spine, stop)
    }

    @Test fun risky_approves_with_one_tap() {
        val (queue, _, _) = newQueue()
        val ap = Approval(summary = "rename branch", description = "x", tier = RiskTier.RISKY)
        queue.enqueue(ap)
        // The UI's "Approve" tap also counts as a confirmation in the
        // ViewModel — exercise the queue API in the same order.
        queue.confirm(ap.id)
        assertTrue(queue.approve(ap.id))
        assertEquals(Approval.Decision.APPROVED, queue.approvals.value.single().decision)
    }

    @Test fun serious_requires_two_taps() {
        val (queue, _, _) = newQueue()
        val ap = Approval(summary = "delete branch", description = "x", tier = RiskTier.SERIOUS)
        queue.enqueue(ap)
        queue.confirm(ap.id)
        // Only one confirmation yet — approve must refuse.
        assertFalse(queue.approve(ap.id))
        assertEquals(Approval.Decision.PENDING, queue.approvals.value.single().decision)
        queue.confirm(ap.id)
        assertTrue(queue.approve(ap.id))
    }

    @Test fun critical_requires_impact_report_at_construction() {
        val ex = runCatching {
            Approval(
                summary = "drop database",
                description = "x",
                tier = RiskTier.CRITICAL,
                impact = null,
            )
        }.exceptionOrNull()
        assertTrue(ex is IllegalArgumentException)
    }

    @Test fun critical_with_impact_takes_two_confirmations() {
        val (queue, _, _) = newQueue()
        val ap = Approval(
            summary = "drop prod table",
            description = "force-push and reset",
            tier = RiskTier.CRITICAL,
            impact = Approval.ImpactReport(
                summary = "Drops the `events` table in production.",
                affectedSurfaces = listOf("prod-db", "dashboards"),
                rollback = "Restore from yesterday's snapshot.",
            ),
        )
        queue.enqueue(ap)
        queue.confirm(ap.id)
        assertFalse(queue.approve(ap.id))
        queue.confirm(ap.id)
        assertTrue(queue.approve(ap.id))
    }

    @Test fun confirm_caps_at_required_count() {
        val (queue, _, _) = newQueue()
        val ap = Approval(summary = "x", description = "x", tier = RiskTier.SERIOUS)
        queue.enqueue(ap)
        repeat(5) { queue.confirm(ap.id) }
        assertEquals(2, queue.approvals.value.single().confirmationsCollected)
    }

    @Test fun reject_records_decision_and_emits_event() {
        val (queue, spine, _) = newQueue()
        val ap = Approval(summary = "x", description = "x", tier = RiskTier.RISKY)
        queue.enqueue(ap)
        queue.reject(ap.id, reason = "not now")
        assertEquals(Approval.Decision.REJECTED, queue.approvals.value.single().decision)
        assertTrue(
            spine.events.value.any {
                it.source == JarvisEvent.Source.APPROVAL && it.message.startsWith("Rejected")
            }
        )
    }

    @Test fun emergency_stop_cancels_every_pending_approval() {
        val (queue, spine, stop) = newQueue()
        val ap1 = Approval(summary = "a", description = "a", tier = RiskTier.RISKY)
        val ap2 = Approval(summary = "b", description = "b", tier = RiskTier.SERIOUS)
        queue.enqueue(ap1); queue.enqueue(ap2)
        stop.engage("smoke")
        val decisions = queue.approvals.value.map { it.decision }.toSet()
        assertEquals(setOf(Approval.Decision.REJECTED_BY_EMERGENCY_STOP), decisions)
        assertTrue(
            spine.events.value.any {
                it.source == JarvisEvent.Source.EMERGENCY_STOP && it.severity == JarvisEvent.Severity.CRITICAL
            }
        )
    }
}
