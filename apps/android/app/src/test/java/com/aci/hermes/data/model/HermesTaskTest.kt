package com.aci.hermes.data.model

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Pure-Kotlin tests for the Jarvis Prime task surface — defaults,
 * section/lane routing, and the Approvals / Audit deep-link helpers.
 */
class HermesTaskTest {

    @Test
    fun `new task carries Jarvis Prime defaults`() {
        val task = HermesTask()
        assertEquals(TaskStatus.DRAFT, task.status)
        assertEquals(RiskTier.LOW, task.riskTier)
        assertEquals(ApprovalState.NOT_REQUIRED, task.approvalState)
        assertEquals(WorkerPhase.PLANNER, task.workerPhase)
        assertNull(task.evidenceSummary)
        assertNull(task.blockedReason)
        assertNull(task.rollbackSummary)
        assertNull(task.verificationResult)
        assertNull(task.proofLink)
        assertFalse(task.emergencyStopActive)
    }

    @Test
    fun `every status maps to a section`() {
        // Every TaskStatus value must resolve to a section so the Tasks
        // screen never sees an UNHANDLED bucket.
        val buckets = TaskStatus.entries.associateWith { it.section() }
        assertEquals(TaskStatus.entries.size, buckets.size)

        val active = setOf(
            TaskStatus.DRAFT,
            TaskStatus.QUEUED,
            TaskStatus.PLANNING,
            TaskStatus.NAVIGATING,
            TaskStatus.EDITING,
            TaskStatus.EXECUTING,
            TaskStatus.REVIEWING,
            TaskStatus.STOPPED,
        )
        active.forEach { assertEquals(TaskSection.ACTIVE, it.section()) }
        assertEquals(TaskSection.WAITING_FOR_APPROVAL, TaskStatus.WAITING_FOR_APPROVAL.section())
        assertEquals(TaskSection.BLOCKED, TaskStatus.BLOCKED.section())
        assertEquals(TaskSection.FAILED, TaskStatus.FAILED.section())
        assertEquals(TaskSection.COMPLETE, TaskStatus.COMPLETE.section())
    }

    @Test
    fun `worker lane mapping covers every active phase`() {
        assertEquals(WorkerPhase.PLANNER, TaskStatus.PLANNING.lane())
        assertEquals(WorkerPhase.NAVIGATOR, TaskStatus.NAVIGATING.lane())
        assertEquals(WorkerPhase.EDITOR, TaskStatus.EDITING.lane())
        assertEquals(WorkerPhase.EXECUTOR, TaskStatus.EXECUTING.lane())
        assertEquals(WorkerPhase.REVIEWER, TaskStatus.REVIEWING.lane())
        assertEquals(WorkerPhase.JARVIS_FINAL_SYNTHESIS, TaskStatus.COMPLETE.lane())
        // Non-routing statuses fall back to the persisted workerPhase.
        assertNull(TaskStatus.DRAFT.lane())
        assertNull(TaskStatus.WAITING_FOR_APPROVAL.lane())
        assertNull(TaskStatus.STOPPED.lane())
    }

    @Test
    fun `blocked task surfaces the blocked reason`() {
        val task = HermesTask(
            status = TaskStatus.BLOCKED,
            blockedReason = "Waiting on credentials from ops",
        )
        assertEquals(TaskSection.BLOCKED, task.status.section())
        assertEquals("Waiting on credentials from ops", task.blockedReason)
    }

    @Test
    fun `failed task surfaces failure notes`() {
        val task = HermesTask(
            status = TaskStatus.FAILED,
            resultNotes = "Build broke on the second retry — dependency missing",
        )
        assertEquals(TaskSection.FAILED, task.status.section())
        assertNotNull(task.resultNotes)
    }

    @Test
    fun `waiting for approval task links Approvals`() {
        val task = HermesTask(
            id = "task-42",
            status = TaskStatus.WAITING_FOR_APPROVAL,
            approvalState = ApprovalState.PENDING,
        )
        assertEquals("approvals/task-42", task.approvalsRoute())
    }

    @Test
    fun `approvalsRoute returns null when no approval is required`() {
        val task = HermesTask(status = TaskStatus.EXECUTING)
        assertNull(task.approvalsRoute())
    }

    @Test
    fun `complete task prefers proof link for Audit`() {
        val task = HermesTask(
            id = "task-9",
            status = TaskStatus.COMPLETE,
            proofLink = "https://example.com/audit/9",
        )
        assertEquals("https://example.com/audit/9", task.auditRoute())
    }

    @Test
    fun `complete task without proof link falls back to internal audit route`() {
        val task = HermesTask(id = "task-9", status = TaskStatus.COMPLETE)
        assertEquals("audit/task-9", task.auditRoute())
    }

    @Test
    fun `auditRoute is null for in-flight tasks without proof link`() {
        val task = HermesTask(status = TaskStatus.EXECUTING)
        assertNull(task.auditRoute())
    }

    @Test
    fun `emergency stop carries forward as data`() {
        val task = HermesTask(emergencyStopActive = true)
        assertTrue(task.emergencyStopActive)
    }
}
