package com.aci.hermes

import com.aci.hermes.data.approvals.ApprovalRepository
import com.aci.hermes.data.emergency.EmergencyStopController
import com.aci.hermes.data.model.Approval
import com.aci.hermes.data.model.ApprovalDecision
import com.aci.hermes.data.model.ApprovalRisk
import com.aci.hermes.data.model.ImpactReport
import org.junit.Assert.assertEquals
import org.junit.Assert.assertSame
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class ApprovalGatingTest {

    private lateinit var emergency: EmergencyStopController
    private lateinit var repo: ApprovalRepository

    @Before
    fun setup() {
        emergency = EmergencyStopController()
        repo = ApprovalRepository(emergency)
    }

    @Test
    fun routine_low_risk_decides_in_one_tap() {
        val a = Approval(title = "tag notes", risk = ApprovalRisk.LOW).also(repo::upsert)
        val result = repo.decide(a, approve = true)
        assertTrue(result is ApprovalRepository.DecisionResult.Decided)
        assertEquals(
            ApprovalDecision.APPROVED,
            (result as ApprovalRepository.DecisionResult.Decided).approval.decision,
        )
    }

    @Test
    fun medium_risk_decides_in_one_tap() {
        val a = Approval(title = "send digest", risk = ApprovalRisk.MEDIUM).also(repo::upsert)
        val result = repo.decide(a, approve = true)
        assertTrue(result is ApprovalRepository.DecisionResult.Decided)
    }

    @Test
    fun high_risk_requires_second_confirmation() {
        val a = Approval(title = "rewrite prompts", risk = ApprovalRisk.HIGH).also(repo::upsert)
        val first = repo.decide(a, approve = true)
        assertSame(ApprovalRepository.DecisionResult.NeedsSecondConfirmation, first)
        val second = repo.decide(a, approve = true, confirmedTwice = true)
        assertTrue(second is ApprovalRepository.DecisionResult.Decided)
    }

    @Test
    fun critical_risk_requires_impact_report_then_second_tap() {
        val a = Approval(
            title = "reset memory",
            risk = ApprovalRisk.CRITICAL,
            impact = ImpactReport(summary = "everything goes"),
        ).also(repo::upsert)

        val noReport = repo.decide(a, approve = true)
        assertSame(ApprovalRepository.DecisionResult.NeedsImpactReport, noReport)

        val reportShown = repo.decide(a, approve = true, impactReportShown = true)
        assertSame(ApprovalRepository.DecisionResult.NeedsSecondConfirmation, reportShown)

        val final = repo.decide(
            a,
            approve = true,
            impactReportShown = true,
            confirmedTwice = true,
        )
        assertTrue(final is ApprovalRepository.DecisionResult.Decided)
    }

    @Test
    fun emergency_stop_blocks_all_decisions() {
        val a = Approval(title = "x", risk = ApprovalRisk.MEDIUM).also(repo::upsert)
        emergency.arm("test")
        val result = repo.decide(a, approve = true)
        assertSame(ApprovalRepository.DecisionResult.BlockedByEmergencyStop, result)
        // High and critical too.
        val high = Approval(title = "h", risk = ApprovalRisk.HIGH).also(repo::upsert)
        assertSame(
            ApprovalRepository.DecisionResult.BlockedByEmergencyStop,
            repo.decide(high, approve = true, confirmedTwice = true),
        )
    }

    @Test
    fun reject_path_records_decision() {
        val a = Approval(title = "x", risk = ApprovalRisk.MEDIUM).also(repo::upsert)
        val out = repo.decide(a, approve = false)
        assertTrue(out is ApprovalRepository.DecisionResult.Decided)
        assertEquals(
            ApprovalDecision.REJECTED,
            (out as ApprovalRepository.DecisionResult.Decided).approval.decision,
        )
    }

    @Test
    fun already_decided_returns_already_decided() {
        val a = Approval(
            title = "x",
            risk = ApprovalRisk.MEDIUM,
            decision = ApprovalDecision.APPROVED,
        ).also(repo::upsert)
        val out = repo.decide(a, approve = true)
        assertSame(ApprovalRepository.DecisionResult.AlreadyDecided, out)
    }
}
