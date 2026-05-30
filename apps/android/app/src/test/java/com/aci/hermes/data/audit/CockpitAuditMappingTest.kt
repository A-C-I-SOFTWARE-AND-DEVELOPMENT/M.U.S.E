package com.aci.hermes.data.audit

import com.aci.hermes.data.cockpit.CockpitApprovalHistoryItem
import com.aci.hermes.data.cockpit.CockpitAuditRecord
import com.aci.hermes.data.cockpit.CockpitEvidenceItem
import com.aci.hermes.data.cockpit.CockpitProofRecord
import com.aci.hermes.data.cockpit.CockpitRollbackPlan
import com.aci.hermes.data.cockpit.CockpitRouteSummary
import com.aci.hermes.data.cockpit.CockpitVerificationResult
import com.aci.hermes.data.cockpit.CockpitWorkerRun
import com.aci.hermes.data.model.audit.ActionResult
import com.aci.hermes.data.model.audit.ApprovalState
import com.aci.hermes.data.model.audit.EvidenceKind
import com.aci.hermes.data.model.audit.RiskTier
import com.aci.hermes.data.model.audit.RouteDestination
import com.aci.hermes.data.model.audit.VerificationStatus
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

class CockpitAuditMappingTest {

    @Test
    fun `record maps enums, route and iso timestamp`() {
        val m = CockpitAuditRecord(
            id = "a1",
            timestamp = "2026-05-30T12:00:00Z",
            userRequest = "do x",
            action = "did x",
            riskTier = "MODERATE",
            route = CockpitRouteSummary("CODEX", "codex-mid", "why", 1500),
            approvalState = "APPROVED",
            result = "SUCCESS",
            confidence = 0.9f,
            proofId = "a1",
        ).toDomain()
        assertEquals("a1", m.id)
        assertTrue(m.timestamp > 0L)
        assertEquals(RiskTier.MODERATE, m.riskTier)
        assertEquals(RouteDestination.CODEX, m.route.destination)
        assertEquals("codex-mid", m.route.model)
        assertEquals(1500L, m.route.durationMs)
        assertEquals(ApprovalState.APPROVED, m.approvalState)
        assertEquals(ActionResult.SUCCESS, m.result)
        assertEquals(0.9f, m.confidence, 0.001f)
        assertEquals("a1", m.proofId)
    }

    @Test
    fun `unknown enums fall back and null timestamp becomes zero`() {
        val m = CockpitAuditRecord(
            id = "a",
            riskTier = "???",
            approvalState = "nope",
            result = "huh",
            route = CockpitRouteSummary(destination = "???"),
        ).toDomain()
        assertEquals(RiskTier.LOW, m.riskTier)
        assertEquals(ApprovalState.UNNECESSARY, m.approvalState)
        assertEquals(ActionResult.SUCCESS, m.result)
        assertEquals(RouteDestination.HUMAN_ONLY, m.route.destination)
        assertEquals(0L, m.timestamp)
    }

    @Test
    fun `proof maps the full nested graph`() {
        val m = CockpitProofRecord(
            id = "p1",
            auditId = "a1",
            rationale = "because",
            evidence = listOf(CockpitEvidenceItem("e1", "DIFF", "t", "b", "src/x")),
            testsRun = listOf("t1"),
            filesChanged = listOf("f1"),
            verification = CockpitVerificationResult("PASSED", "ok", emptyList(), listOf("c")),
            approvals = listOf(
                CockpitApprovalHistoryItem("ap1", "2026-05-30T12:00:00Z", "owner", "APPROVED", "ok"),
            ),
            rollback = CockpitRollbackPlan("rb", "revert", listOf("s1"), automatic = true, executed = false),
            impactReport = "impact",
            workerRuns = listOf(
                CockpitWorkerRun("w", "codex", "2026-05-30T12:00:00Z", "2026-05-30T12:01:00Z", "SUCCESS", "n"),
            ),
        ).toDomain()
        assertEquals("a1", m.auditId)
        assertEquals(EvidenceKind.DIFF, m.evidence[0].kind)
        assertEquals("src/x", m.evidence[0].sourcePath)
        assertEquals(VerificationStatus.PASSED, m.verification.status)
        assertEquals(listOf("c"), m.verification.passedChecks)
        assertEquals(ApprovalState.APPROVED, m.approvals[0].state)
        assertNotNull(m.rollback)
        assertTrue(m.rollback!!.automatic)
        assertEquals(ActionResult.SUCCESS, m.workerRuns[0].status)
        assertTrue(m.workerRuns[0].finishedAt > m.workerRuns[0].startedAt)
    }

    @Test
    fun `null rollback stays null, never fabricated`() {
        val m = CockpitProofRecord(auditId = "a1", rollback = null).toDomain()
        assertEquals(null, m.rollback)
        assertEquals(emptyList<String>(), m.filesChanged)
    }
}
