package com.aci.hermes.data.model

import com.aci.hermes.approval.model.ApprovalRiskTier
import com.aci.hermes.approval.model.ApprovalStatus
import kotlinx.serialization.builtins.ListSerializer
import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Pure-Kotlin coverage for the MUSE worker-card additions to
 * [HermesTask]: defaults, the [section] derivation across every status,
 * the Approvals / Audit deep-link predicates, and forward-compatible
 * serialization of the new fields.
 */
class HermesTaskSectionTest {

    private val json = Json {
        ignoreUnknownKeys = true
        encodeDefaults = true
        prettyPrint = false
    }

    @Test
    fun `new task carries safe worker-card defaults`() {
        val task = HermesTask()
        assertEquals(ApprovalRiskTier.LOW, task.riskTier)
        assertEquals(WorkerPhase.PLANNER, task.workerPhase)
        assertNull(task.approvalState)
        assertNull(task.evidenceSummary)
        assertNull(task.blockedReason)
        assertNull(task.rollbackSummary)
        assertNull(task.verificationResult)
        assertNull(task.proofLink)
    }

    @Test
    fun `every status resolves to a section`() {
        // No status may fall through the section() when-expression.
        TaskStatus.entries.forEach { status ->
            val section = HermesTask(status = status).section()
            assertTrue("status $status produced a section", section in TaskSection.entries)
        }
    }

    @Test
    fun `default active statuses land in ACTIVE`() {
        listOf(
            TaskStatus.DRAFT,
            TaskStatus.READY_FOR_HANDOFF,
            TaskStatus.HANDED_TO_CODEX,
            TaskStatus.HANDED_TO_CLAUDE,
            TaskStatus.IN_REVIEW,
        ).forEach { status ->
            assertEquals(
                "status $status",
                TaskSection.ACTIVE,
                HermesTask(status = status).section(),
            )
        }
    }

    @Test
    fun `complete status lands in COMPLETE and links audit`() {
        val task = HermesTask(status = TaskStatus.COMPLETE)
        assertEquals(TaskSection.COMPLETE, task.section())
        assertTrue(task.linksAudit())
        assertFalse(task.linksApprovals())
    }

    @Test
    fun `pending approval lands in WAITING_FOR_APPROVAL and links approvals`() {
        val task = HermesTask(
            status = TaskStatus.IN_REVIEW,
            approvalState = ApprovalStatus.PENDING,
        )
        assertEquals(TaskSection.WAITING_FOR_APPROVAL, task.section())
        assertTrue(task.linksApprovals())
    }

    @Test
    fun `rejected and emergency-stopped approvals land in FAILED`() {
        assertEquals(
            TaskSection.FAILED,
            HermesTask(approvalState = ApprovalStatus.REJECTED).section(),
        )
        assertEquals(
            TaskSection.FAILED,
            HermesTask(approvalState = ApprovalStatus.EMERGENCY_STOPPED).section(),
        )
    }

    @Test
    fun `blocked reason or needs-revision lands in BLOCKED and surfaces the reason`() {
        val byReason = HermesTask(blockedReason = "Waiting on credentials")
        assertEquals(TaskSection.BLOCKED, byReason.section())
        assertEquals("Waiting on credentials", byReason.blockedReason)

        val byStatus = HermesTask(status = TaskStatus.NEEDS_REVISION)
        assertEquals(TaskSection.BLOCKED, byStatus.section())
    }

    @Test
    fun `complete precedence beats a lingering blocked reason`() {
        val task = HermesTask(status = TaskStatus.COMPLETE, blockedReason = "stale")
        assertEquals(TaskSection.COMPLETE, task.section())
    }

    @Test
    fun `proof link alone is enough to link audit even mid-flight`() {
        val task = HermesTask(status = TaskStatus.IN_REVIEW, proofLink = "https://example.com/audit/7")
        assertTrue(task.linksAudit())
    }

    @Test
    fun `new fields round-trip through json with the repository config`() {
        val original = HermesTask(
            id = "rt-1",
            title = "round trip",
            status = TaskStatus.IN_REVIEW,
            riskTier = ApprovalRiskTier.SERIOUS,
            workerPhase = WorkerPhase.EXECUTOR,
            approvalState = ApprovalStatus.PENDING,
            evidenceSummary = "evidence",
            blockedReason = "blocked",
            rollbackSummary = "rollback",
            verificationResult = "verified",
            proofLink = "audit/9",
            createdAt = 1L,
            updatedAt = 2L,
        )
        val ser = ListSerializer(HermesTask.serializer())
        val decoded = json.decodeFromString(ser, json.encodeToString(ser, listOf(original)))
        assertEquals(listOf(original), decoded)
    }

    @Test
    fun `legacy json without the new fields deserializes with defaults`() {
        // A task persisted before the worker-card fields existed.
        val legacy = """[
            {
              "id": "old-1", "title": "T", "description": "D",
              "targetTool": "CODEX", "taskType": "BUILD", "status": "DRAFT",
              "createdAt": 1, "updatedAt": 2
            }
        ]"""
        val ser = ListSerializer(HermesTask.serializer())
        val decoded = json.decodeFromString(ser, legacy)
        assertEquals(1, decoded.size)
        val task = decoded.single()
        assertEquals(ApprovalRiskTier.LOW, task.riskTier)
        assertEquals(WorkerPhase.PLANNER, task.workerPhase)
        assertNull(task.approvalState)
        assertEquals(TaskSection.ACTIVE, task.section())
    }
}
