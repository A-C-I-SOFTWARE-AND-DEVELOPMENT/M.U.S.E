package com.aci.hermes.ui.components

import com.aci.hermes.data.cockpit.CockpitJob
import com.aci.hermes.data.cockpit.JobStatus
import com.aci.hermes.service.JobNotifier
import com.aci.hermes.ui.screens.jobs.JobSection
import com.aci.hermes.ui.screens.jobs.sectionOf
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** Status → UI-state → list-section + notification-destination mapping. */
class JobStatusChipMappingTest {

    @Test
    fun `wire statuses map to the readable mobile vocabulary`() {
        assertEquals(JobUiState.RUNNING, JobUiState.from(JobStatus.RUNNING))
        assertEquals(JobUiState.QUEUED, JobUiState.from(JobStatus.QUEUED))
        assertEquals(JobUiState.PAUSED, JobUiState.from(JobStatus.PAUSED))
        assertEquals(JobUiState.BLOCKED, JobUiState.from(JobStatus.BLOCKED))
        assertEquals(JobUiState.BLOCKED, JobUiState.from(JobStatus.DISCONNECTED))
        assertEquals(JobUiState.WAITING_APPROVAL, JobUiState.from(JobStatus.WAITING_FOR_APPROVAL))
        assertEquals(JobUiState.COMPLETED, JobUiState.from(JobStatus.COMPLETED))
        assertEquals(JobUiState.PUBLISHED, JobUiState.from(JobStatus.PUBLISHED))
        assertEquals(JobUiState.FAILED, JobUiState.from(JobStatus.FAILED))
        assertEquals(JobUiState.CANCELLED, JobUiState.from(JobStatus.CANCELLED))
    }

    @Test
    fun `unknown wire value falls back to UNKNOWN, never crashes`() {
        assertEquals(JobUiState.UNKNOWN, JobUiState.fromWire("SOME_FUTURE_STATE"))
    }

    @Test
    fun `active and attention flags drive polling and sections`() {
        assertTrue(JobUiState.RUNNING.isActive)
        assertTrue(JobUiState.QUEUED.isActive)
        assertFalse(JobUiState.COMPLETED.isActive)
        assertTrue(JobUiState.BLOCKED.needsAttention)
        assertTrue(JobUiState.WAITING_APPROVAL.needsAttention)
        assertFalse(JobUiState.RUNNING.needsAttention)
    }

    @Test
    fun `section classification buckets every status exactly once`() {
        assertEquals(JobSection.ACTIVE, sectionOf(job("RUNNING")))
        assertEquals(JobSection.ACTIVE, sectionOf(job("QUEUED")))
        assertEquals(JobSection.ACTIVE, sectionOf(job("PAUSED")))
        assertEquals(JobSection.BLOCKED, sectionOf(job("BLOCKED")))
        assertEquals(JobSection.BLOCKED, sectionOf(job("WAITING_FOR_APPROVAL")))
        assertEquals(JobSection.COMPLETED, sectionOf(job("COMPLETED")))
        assertEquals(JobSection.COMPLETED, sectionOf(job("PUBLISHED")))
        assertEquals(JobSection.FAILED, sectionOf(job("FAILED")))
        assertEquals(JobSection.CANCELLED, sectionOf(job("CANCELLED")))
        // Unknown bucketed into ACTIVE so it stays visible, never dropped.
        assertEquals(JobSection.ACTIVE, sectionOf(job("FUTURE")))
    }

    @Test
    fun `notification destination routes blocked jobs to approvals`() {
        assertEquals(JobNotifier.DEST_APPROVALS, JobNotifier.destinationFor("WAITING_FOR_APPROVAL"))
        assertEquals(JobNotifier.DEST_APPROVALS, JobNotifier.destinationFor("BLOCKED"))
        assertEquals(JobNotifier.DEST_DETAIL, JobNotifier.destinationFor("RUNNING"))
        assertEquals(JobNotifier.DEST_DETAIL, JobNotifier.destinationFor("QUEUED"))
    }

    private fun job(status: String) = CockpitJob(
        id = "j", title = "T", workerId = "w", status = status,
        createdAt = "2026-05-30T12:00:00Z", updatedAt = "2026-05-30T12:00:00Z",
    )
}
