package com.aci.hermes.notify

import com.aci.hermes.data.cockpit.JobStatus
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Pure-logic tests for [WorkEventDetector]. No Android, no network — covers
 * each of the nine event transitions plus the calmness guarantees
 * (baseline-first, edge-triggered, no steady-state spam).
 */
class WorkEventDetectorTest {

    private fun job(
        id: String,
        status: JobStatus,
        testsFailed: Int = 0,
        isResearch: Boolean = false,
        title: String = id,
    ) = JobSnap(id = id, title = title, status = status, testsFailed = testsFailed, isResearch = isResearch)

    @Test
    fun `baseline tick emits nothing`() {
        val current = WorkSnapshot(
            jobs = listOf(job("j1", JobStatus.RUNNING)),
            approvalIds = setOf("a1"),
        )
        assertTrue(WorkEventDetector.detect(previous = null, current = current).isEmpty())
    }

    @Test
    fun `new live job is a JobStarted`() {
        val prev = WorkSnapshot()
        val cur = WorkSnapshot(jobs = listOf(job("j1", JobStatus.QUEUED, title = "Build app")))
        val events = WorkEventDetector.detect(prev, cur)
        assertEquals(listOf(WorkEvent.JobStarted("j1", "Build app")), events)
    }

    @Test
    fun `job already terminal on first sighting does not notify`() {
        val prev = WorkSnapshot()
        val cur = WorkSnapshot(jobs = listOf(job("j1", JobStatus.COMPLETED)))
        assertTrue(WorkEventDetector.detect(prev, cur).isEmpty())
    }

    @Test
    fun `running to waiting-for-approval is JobBlocked`() {
        val prev = WorkSnapshot(jobs = listOf(job("j1", JobStatus.RUNNING)))
        val cur = WorkSnapshot(jobs = listOf(job("j1", JobStatus.WAITING_FOR_APPROVAL)))
        assertEquals(listOf(WorkEvent.JobBlocked("j1", "j1")), WorkEventDetector.detect(prev, cur))
    }

    @Test
    fun `running to completed is JobCompleted`() {
        val prev = WorkSnapshot(jobs = listOf(job("j1", JobStatus.RUNNING)))
        val cur = WorkSnapshot(jobs = listOf(job("j1", JobStatus.COMPLETED)))
        assertEquals(listOf(WorkEvent.JobCompleted("j1", "j1")), WorkEventDetector.detect(prev, cur))
    }

    @Test
    fun `research job completing is ResearchComplete`() {
        val prev = WorkSnapshot(jobs = listOf(job("j1", JobStatus.RUNNING, isResearch = true)))
        val cur = WorkSnapshot(jobs = listOf(job("j1", JobStatus.COMPLETED, isResearch = true)))
        assertEquals(listOf(WorkEvent.ResearchComplete("j1", "j1")), WorkEventDetector.detect(prev, cur))
    }

    @Test
    fun `running to failed is JobFailed`() {
        val prev = WorkSnapshot(jobs = listOf(job("j1", JobStatus.RUNNING)))
        val cur = WorkSnapshot(jobs = listOf(job("j1", JobStatus.FAILED)))
        assertEquals(listOf(WorkEvent.JobFailed("j1", "j1")), WorkEventDetector.detect(prev, cur))
    }

    @Test
    fun `job disconnect is WorkerNeedsAttention`() {
        val prev = WorkSnapshot(jobs = listOf(job("j1", JobStatus.RUNNING)))
        val cur = WorkSnapshot(jobs = listOf(job("j1", JobStatus.DISCONNECTED)))
        assertEquals(
            listOf(WorkEvent.WorkerNeedsAttention("j1", "j1")),
            WorkEventDetector.detect(prev, cur),
        )
    }

    @Test
    fun `tests crossing zero is TestsFailed`() {
        val prev = WorkSnapshot(jobs = listOf(job("j1", JobStatus.RUNNING, testsFailed = 0)))
        val cur = WorkSnapshot(jobs = listOf(job("j1", JobStatus.RUNNING, testsFailed = 3)))
        assertEquals(
            listOf(WorkEvent.TestsFailed("j1", "j1", 3)),
            WorkEventDetector.detect(prev, cur),
        )
    }

    @Test
    fun `new approval card is ApprovalRequired`() {
        val prev = WorkSnapshot(approvalIds = emptySet())
        val cur = WorkSnapshot(approvalIds = setOf("a1"))
        assertEquals(
            listOf(WorkEvent.ApprovalRequired("a1", "")),
            WorkEventDetector.detect(prev, cur),
        )
    }

    @Test
    fun `worker going unavailable is WorkerNeedsAttention`() {
        val prev = WorkSnapshot(workers = listOf(WorkerSnap("w1", "Codex", available = true)))
        val cur = WorkSnapshot(workers = listOf(WorkerSnap("w1", "Codex", available = false)))
        assertEquals(
            listOf(WorkEvent.WorkerNeedsAttention("w1", "Codex")),
            WorkEventDetector.detect(prev, cur),
        )
    }

    @Test
    fun `emergency engaging is EmergencyStopTriggered`() {
        val prev = WorkSnapshot(emergencyActive = false)
        val cur = WorkSnapshot(emergencyActive = true)
        assertEquals(
            listOf(WorkEvent.EmergencyStopTriggered("")),
            WorkEventDetector.detect(prev, cur),
        )
    }

    @Test
    fun `steady state emits nothing`() {
        val snap = WorkSnapshot(
            jobs = listOf(job("j1", JobStatus.RUNNING, testsFailed = 2)),
            approvalIds = setOf("a1"),
            workers = listOf(WorkerSnap("w1", "Codex", available = false)),
            emergencyActive = true,
        )
        assertTrue(WorkEventDetector.detect(snap, snap).isEmpty())
    }

    @Test
    fun `terminal job does not re-notify on a later poll`() {
        val prev = WorkSnapshot(jobs = listOf(job("j1", JobStatus.COMPLETED)))
        val cur = WorkSnapshot(jobs = listOf(job("j1", JobStatus.COMPLETED)))
        assertTrue(WorkEventDetector.detect(prev, cur).isEmpty())
    }

    @Test
    fun `hasActiveWork true for pending approval`() {
        assertTrue(WorkEventDetector.hasActiveWork(WorkSnapshot(approvalIds = setOf("a1"))))
    }

    @Test
    fun `hasActiveWork true for running job, false when all terminal`() {
        assertTrue(
            WorkEventDetector.hasActiveWork(WorkSnapshot(jobs = listOf(job("j1", JobStatus.RUNNING)))),
        )
        assertFalse(
            WorkEventDetector.hasActiveWork(WorkSnapshot(jobs = listOf(job("j1", JobStatus.COMPLETED)))),
        )
    }
}
