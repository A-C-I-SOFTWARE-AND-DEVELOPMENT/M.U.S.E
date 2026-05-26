package com.aci.hermes.data.model.audit

import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Pins the audit + proof model shape. These types back the audit
 * ledger surface and are seeded both from `AuditRepository`'s mock
 * data and (eventually) from the gateway's wire format. Tests guard:
 *  - enum coverage (no silent additions / removals)
 *  - JSON round-trip fidelity (serializer is wired up correctly)
 *  - data-class `copy(...)` works on every field the redactor patches
 *  - default values are non-null lists, so renderers never need
 *    nullable-list guards
 */
class AuditTypesTest {

    private val json = Json {
        ignoreUnknownKeys = true
        encodeDefaults = true
    }

    @Test
    fun `risk tier enumerates the five governance buckets`() {
        assertEquals(
            listOf("TRIVIAL", "LOW", "MODERATE", "SERIOUS", "CRITICAL"),
            RiskTier.entries.map { it.name },
        )
    }

    @Test
    fun `route destination covers every routed surface`() {
        assertEquals(
            listOf("LOCAL_WORKER", "CODEX", "CLAUDE", "HERMES_GATEWAY", "HUMAN_ONLY"),
            RouteDestination.entries.map { it.name },
        )
    }

    @Test
    fun `approval state distinguishes owner action from automation`() {
        val byName = ApprovalState.entries.map { it.name }.toSet()
        // UNNECESSARY means below threshold; AUTO_APPROVED means a
        // standing rule cleared it. They must be distinct so the
        // audit surface can tell them apart.
        assertTrue("UNNECESSARY" in byName)
        assertTrue("AUTO_APPROVED" in byName)
        assertNotEquals(ApprovalState.UNNECESSARY, ApprovalState.AUTO_APPROVED)
    }

    @Test
    fun `action result includes terminal and blocked outcomes`() {
        val names = ActionResult.entries.map { it.name }.toSet()
        listOf("SUCCESS", "PARTIAL", "FAILED", "ROLLED_BACK", "BLOCKED").forEach {
            assertTrue("missing $it", it in names)
        }
    }

    @Test
    fun `verification status covers passed failed skipped flaky`() {
        assertEquals(
            setOf("PASSED", "FAILED", "SKIPPED", "FLAKY"),
            VerificationStatus.entries.map { it.name }.toSet(),
        )
    }

    @Test
    fun `evidence kind covers diff test log command metric doclink`() {
        assertEquals(
            setOf("DIFF", "TEST_REPORT", "LOG", "COMMAND_OUTPUT", "METRIC", "DOC_LINK"),
            EvidenceKind.entries.map { it.name }.toSet(),
        )
    }

    @Test
    fun `audit record round-trips through JSON`() {
        val record = AuditRecord(
            id = "aud_x",
            timestamp = 1_700_000_000_000L,
            userRequest = "Do the thing",
            action = "Did the thing",
            riskTier = RiskTier.MODERATE,
            route = RouteSummary(
                destination = RouteDestination.CODEX,
                model = "codex-mid",
                reason = "Cross-file refactor.",
                durationMs = 12_345L,
            ),
            approvalState = ApprovalState.APPROVED,
            result = ActionResult.SUCCESS,
            confidence = 0.91f,
            proofId = "prf_x",
        )
        val encoded = json.encodeToString(AuditRecord.serializer(), record)
        val decoded = json.decodeFromString(AuditRecord.serializer(), encoded)
        assertEquals(record, decoded)
    }

    @Test
    fun `proof record defaults to non-null empty lists`() {
        val proof = ProofRecord(
            id = "prf_y",
            auditId = "aud_y",
            rationale = "Because.",
            verification = VerificationResult(
                status = VerificationStatus.PASSED,
                summary = "All green.",
            ),
        )
        assertTrue("evidence default empty", proof.evidence.isEmpty())
        assertTrue("testsRun default empty", proof.testsRun.isEmpty())
        assertTrue("filesChanged default empty", proof.filesChanged.isEmpty())
        assertTrue("approvals default empty", proof.approvals.isEmpty())
        assertTrue("workerRuns default empty", proof.workerRuns.isEmpty())
        assertNull(proof.rollback)
        assertNull(proof.impactReport)
    }

    @Test
    fun `copy redacts a single string field without rebuilding the whole record`() {
        val record = AuditRecord(
            id = "aud_z",
            timestamp = 1L,
            userRequest = "raw secret ABC",
            action = "did it",
            riskTier = RiskTier.LOW,
            route = RouteSummary(
                destination = RouteDestination.LOCAL_WORKER,
                model = null,
                reason = "trivial",
                durationMs = 0L,
            ),
            approvalState = ApprovalState.UNNECESSARY,
            result = ActionResult.SUCCESS,
            confidence = 1f,
            proofId = "prf_z",
        )
        val redacted = record.copy(userRequest = "[REDACTED]")
        assertEquals("[REDACTED]", redacted.userRequest)
        assertEquals(record.action, redacted.action)
        assertEquals(record.route, redacted.route)
    }

    @Test
    fun `worker run carries start and finish as long timestamps`() {
        val run = WorkerRun(
            id = "wr_a",
            worker = "codex-mid",
            startedAt = 100L,
            finishedAt = 5_000L,
            status = ActionResult.SUCCESS,
            notes = "ok",
        )
        // Duration math must be Long so audit detail rendering can
        // pass it straight to `formatDuration(Long)` without coercion.
        val duration: Long = run.finishedAt - run.startedAt
        assertEquals(4_900L, duration)
    }

    @Test
    fun `verification result keeps failing and passing checks separate`() {
        val v = VerificationResult(
            status = VerificationStatus.FAILED,
            summary = "1 failure",
            failingChecks = listOf("legacyConsumersStillReceive"),
            passedChecks = listOf("lintDebug"),
        )
        assertEquals(1, v.failingChecks.size)
        assertEquals(1, v.passedChecks.size)
        assertNotEquals(v.failingChecks, v.passedChecks)
    }
}
