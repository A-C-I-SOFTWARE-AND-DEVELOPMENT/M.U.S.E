package com.aci.hermes.approval

import com.aci.hermes.approval.event.ApprovalEvent
import com.aci.hermes.approval.event.RecordingApprovalEventSink
import com.aci.hermes.approval.model.ApprovalCard
import com.aci.hermes.approval.model.ApprovalRiskTier
import com.aci.hermes.approval.model.ApprovalStatus
import com.aci.hermes.approval.model.CriticalActionState
import com.aci.hermes.approval.model.CriticalImpactReport
import com.aci.hermes.approval.model.RollbackPlan
import com.aci.hermes.approval.state.ApprovalStore
import com.aci.hermes.approval.state.DecisionResult
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ApprovalStoreTest {

    private fun card(
        id: String,
        tier: ApprovalRiskTier,
        expiresAt: Long = 10_000L,
        crit: CriticalActionState = CriticalActionState()
    ) = ApprovalCard(
        id = id,
        title = "t",
        summary = "s",
        requester = "tester",
        tier = tier,
        createdAtMillis = 0L,
        expiresAtMillis = expiresAt,
        proposedAction = "noop",
        criticalState = crit
    )

    @Test
    fun risky_approval_emits_single_confirmation_event() {
        val sink = RecordingApprovalEventSink()
        val store = ApprovalStore(sink = sink, clock = { 1000L }, initial = listOf(card("a", ApprovalRiskTier.RISKY)))

        val result = store.approveRisky("a", note = "ship it")

        assertTrue(result is DecisionResult.Updated)
        assertEquals(ApprovalStatus.APPROVED, store.snapshot().first().status)
        val ev = sink.events.single()
        assertTrue(ev is ApprovalEvent.Approved)
        assertEquals(1, (ev as ApprovalEvent.Approved).confirmations)
        assertEquals("ship it", ev.note)
    }

    @Test
    fun serious_step2_blocked_before_step1() {
        val sink = RecordingApprovalEventSink()
        val store = ApprovalStore(sink = sink, clock = { 1000L }, initial = listOf(card("s", ApprovalRiskTier.SERIOUS)))

        val refusal = store.approveSeriousStep2("s")

        assertTrue(refusal is DecisionResult.Refused)
        assertEquals(
            DecisionResult.Reason.SERIOUS_STEP2_BLOCKED_BEFORE_STEP1,
            (refusal as DecisionResult.Refused).reason
        )
        assertEquals(ApprovalStatus.PENDING, store.snapshot().first().status)
        assertTrue(sink.events.isEmpty())
    }

    @Test
    fun serious_completes_after_two_steps_and_emits_two_confirmation_event() {
        val sink = RecordingApprovalEventSink()
        val store = ApprovalStore(sink = sink, clock = { 1000L }, initial = listOf(card("s", ApprovalRiskTier.SERIOUS)))

        assertTrue(store.approveSeriousStep1("s") is DecisionResult.Updated)
        val final = store.approveSeriousStep2("s")

        assertTrue(final is DecisionResult.Updated)
        assertEquals(ApprovalStatus.APPROVED, store.snapshot().first().status)
        val ev = sink.events.single { it is ApprovalEvent.Approved } as ApprovalEvent.Approved
        assertEquals(2, ev.confirmations)
    }

    @Test
    fun critical_blocked_without_impact_report() {
        val sink = RecordingApprovalEventSink()
        val noReportCard = card(
            "c",
            ApprovalRiskTier.CRITICAL,
            crit = CriticalActionState(
                impactReport = null,
                rollbackPlan = RollbackPlan(listOf("step"), 60, true)
            )
        )
        val store = ApprovalStore(sink = sink, clock = { 1000L }, initial = listOf(noReportCard))

        val refusal = store.approveCriticalStep1("c")

        assertTrue(refusal is DecisionResult.Refused)
        assertEquals(
            DecisionResult.Reason.CRITICAL_MISSING_IMPACT_REPORT,
            (refusal as DecisionResult.Refused).reason
        )
        assertTrue(sink.events.isEmpty())
    }

    @Test
    fun critical_blocked_without_rollback_plan() {
        val sink = RecordingApprovalEventSink()
        val noPlanCard = card(
            "c",
            ApprovalRiskTier.CRITICAL,
            crit = CriticalActionState(
                impactReport = CriticalImpactReport("s", listOf("svc"), "br", true),
                rollbackPlan = null
            )
        )
        val store = ApprovalStore(sink = sink, clock = { 1000L }, initial = listOf(noPlanCard))

        val refusal = store.approveCriticalStep1("c")

        assertTrue(refusal is DecisionResult.Refused)
        assertEquals(
            DecisionResult.Reason.CRITICAL_MISSING_ROLLBACK,
            (refusal as DecisionResult.Refused).reason
        )
    }

    @Test
    fun critical_complete_after_report_plan_and_two_steps() {
        val sink = RecordingApprovalEventSink()
        val ready = card(
            "c",
            ApprovalRiskTier.CRITICAL,
            crit = CriticalActionState(
                impactReport = CriticalImpactReport("s", listOf("svc"), "br", false),
                rollbackPlan = RollbackPlan(listOf("step"), 60, true)
            )
        )
        val store = ApprovalStore(sink = sink, clock = { 1000L }, initial = listOf(ready))

        store.approveCriticalStep1("c")
        store.approveCriticalStep2("c")

        assertEquals(ApprovalStatus.APPROVED, store.snapshot().first().status)
        val ev = sink.events.last { it is ApprovalEvent.Approved } as ApprovalEvent.Approved
        assertEquals(2, ev.confirmations)
    }

    @Test
    fun critical_step2_blocked_before_step1() {
        val sink = RecordingApprovalEventSink()
        val ready = card(
            "c",
            ApprovalRiskTier.CRITICAL,
            crit = CriticalActionState(
                impactReport = CriticalImpactReport("s", listOf("svc"), "br", true),
                rollbackPlan = RollbackPlan(listOf("step"), 60, true)
            )
        )
        val store = ApprovalStore(sink = sink, clock = { 1000L }, initial = listOf(ready))

        val refusal = store.approveCriticalStep2("c")

        assertTrue(refusal is DecisionResult.Refused)
        assertEquals(
            DecisionResult.Reason.CRITICAL_STEP2_BLOCKED_BEFORE_STEP1,
            (refusal as DecisionResult.Refused).reason
        )
    }

    @Test
    fun reject_works_for_every_pending_tier() {
        val sink = RecordingApprovalEventSink()
        val cards = listOf(
            card("r", ApprovalRiskTier.RISKY),
            card("s", ApprovalRiskTier.SERIOUS),
            card("c", ApprovalRiskTier.CRITICAL,
                crit = CriticalActionState(
                    impactReport = CriticalImpactReport("s", listOf("svc"), "br", true),
                    rollbackPlan = RollbackPlan(listOf("step"), 60, true)
                )
            )
        )
        val store = ApprovalStore(sink = sink, clock = { 1000L }, initial = cards)

        store.reject("r", reason = "no")
        store.reject("s")
        store.reject("c", reason = "bad time")

        val rejected = store.snapshot().filter { it.status == ApprovalStatus.REJECTED }
        assertEquals(3, rejected.size)
        assertEquals(3, sink.events.count { it is ApprovalEvent.Rejected })
    }

    @Test
    fun expired_approval_is_blocked() {
        val sink = RecordingApprovalEventSink()
        val store = ApprovalStore(
            sink = sink,
            clock = { 99_999L },
            initial = listOf(card("a", ApprovalRiskTier.RISKY, expiresAt = 5_000L))
        )

        val refusal = store.approveRisky("a")

        assertTrue(refusal is DecisionResult.Refused)
        assertEquals(DecisionResult.Reason.EXPIRED, (refusal as DecisionResult.Refused).reason)
        assertEquals(ApprovalStatus.EXPIRED, store.snapshot().first().status)
        assertTrue(sink.events.none { it is ApprovalEvent.Approved })
    }

    @Test
    fun sweep_marks_pending_past_expiry_and_emits_expired_event() {
        val sink = RecordingApprovalEventSink()
        var now = 1_000L
        val store = ApprovalStore(
            sink = sink,
            clock = { now },
            initial = listOf(card("a", ApprovalRiskTier.RISKY, expiresAt = 5_000L))
        )
        now = 6_000L

        val swept = store.sweepExpired()

        assertEquals(1, swept.size)
        assertEquals(ApprovalStatus.EXPIRED, swept.first().status)
        assertTrue(sink.events.any { it is ApprovalEvent.Expired })
    }

    @Test
    fun emergency_stop_visible_only_for_serious_and_critical() {
        val risky = card("r", ApprovalRiskTier.RISKY)
        val serious = card("s", ApprovalRiskTier.SERIOUS)
        val critical = card("c", ApprovalRiskTier.CRITICAL)
        assertFalse(risky.showsEmergencyStop)
        assertTrue(serious.showsEmergencyStop)
        assertTrue(critical.showsEmergencyStop)
    }

    @Test
    fun emergency_stop_marks_card_and_emits_event() {
        val sink = RecordingApprovalEventSink()
        val store = ApprovalStore(sink = sink, clock = { 1000L }, initial = listOf(card("s", ApprovalRiskTier.SERIOUS)))

        store.approveSeriousStep1("s")
        val result = store.emergencyStop("s")

        assertTrue(result is DecisionResult.Updated)
        assertEquals(ApprovalStatus.EMERGENCY_STOPPED, store.snapshot().first().status)
        assertTrue(sink.events.last() is ApprovalEvent.EmergencyStopped)
    }

    @Test
    fun second_decision_on_same_card_is_refused() {
        val sink = RecordingApprovalEventSink()
        val store = ApprovalStore(sink = sink, clock = { 1000L }, initial = listOf(card("a", ApprovalRiskTier.RISKY)))
        store.approveRisky("a")

        val refusal = store.reject("a", reason = "too late")

        assertTrue(refusal is DecisionResult.Refused)
        assertEquals(
            DecisionResult.Reason.ALREADY_DECIDED,
            (refusal as DecisionResult.Refused).reason
        )
    }

    @Test
    fun edited_risky_card_records_event() {
        val sink = RecordingApprovalEventSink()
        val store = ApprovalStore(sink = sink, clock = { 1000L }, initial = listOf(card("a", ApprovalRiskTier.RISKY)))

        store.editRisky("a", "POST /keys/rotate { env: dev }")

        assertEquals("POST /keys/rotate { env: dev }", store.snapshot().first().proposedAction)
        assertTrue(sink.events.last() is ApprovalEvent.Edited)
    }
}
