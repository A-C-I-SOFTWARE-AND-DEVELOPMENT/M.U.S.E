package com.aci.hermes.data.cockpit

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class JobStatusTest {

    @Test
    fun `fromWire matches the canonical UPPER values and is case-insensitive`() {
        assertEquals(JobStatus.QUEUED, JobStatus.fromWire("QUEUED"))
        assertEquals(JobStatus.RUNNING, JobStatus.fromWire("running")) // legacy lowercase tolerated
        assertEquals(JobStatus.WAITING_FOR_APPROVAL, JobStatus.fromWire("waiting_for_approval"))
        assertNull(JobStatus.fromWire("not_a_state"))
        assertNull(JobStatus.fromWire(null))
    }

    @Test
    fun `superset execution states are present`() {
        assertEquals(JobStatus.PAUSED, JobStatus.fromWire("PAUSED"))
        assertEquals(JobStatus.BLOCKED, JobStatus.fromWire("BLOCKED"))
        assertEquals(JobStatus.DISCONNECTED, JobStatus.fromWire("DISCONNECTED"))
        assertEquals(JobStatus.COMPLETED, JobStatus.fromWire("COMPLETED"))
    }

    @Test
    fun `isTerminal covers the terminal states only`() {
        assertTrue(JobStatus.PUBLISHED.isTerminal)
        assertTrue(JobStatus.FAILED.isTerminal)
        assertTrue(JobStatus.CANCELLED.isTerminal)
        assertTrue(JobStatus.COMPLETED.isTerminal)
        assertFalse(JobStatus.RUNNING.isTerminal)
        assertFalse(JobStatus.QUEUED.isTerminal)
    }

    @Test
    fun `publish state is case-insensitive UPPER`() {
        assertEquals(PublishState.IN_PROGRESS, PublishState.fromWire("in_progress"))
        assertEquals(PublishState.SUCCEEDED, PublishState.fromWire("SUCCEEDED"))
        assertNull(PublishState.fromWire("bogus"))
    }
}
