package com.aci.hermes.ui.screens.jobs

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/** The lifecycle-aware poll cadence policy (no coroutine / clock needed). */
class JobsPollingTest {

    @Test
    fun `fast while active and visible`() {
        assertEquals(
            JobsPolling.FAST_MS,
            JobsPolling.nextDelayMs(hasActive = true, visible = true, consecutiveErrors = 0, idleCycles = 0),
        )
    }

    @Test
    fun `slow while active but backgrounded`() {
        assertEquals(
            JobsPolling.SLOW_MS,
            JobsPolling.nextDelayMs(hasActive = true, visible = false, consecutiveErrors = 0, idleCycles = 0),
        )
    }

    @Test
    fun `slow while idle but visible (so new jobs still appear)`() {
        assertEquals(
            JobsPolling.SLOW_MS,
            JobsPolling.nextDelayMs(hasActive = false, visible = true, consecutiveErrors = 0, idleCycles = 99),
        )
    }

    @Test
    fun `stops when idle and backgrounded past the grace window`() {
        assertEquals(
            JobsPolling.STOP,
            JobsPolling.nextDelayMs(
                hasActive = false,
                visible = false,
                consecutiveErrors = 0,
                idleCycles = JobsPolling.IDLE_CYCLES_BEFORE_STOP,
            ),
        )
    }

    @Test
    fun `keeps polling when idle and backgrounded inside the grace window`() {
        val delay = JobsPolling.nextDelayMs(
            hasActive = false, visible = false, consecutiveErrors = 0, idleCycles = 1,
        )
        assertEquals(JobsPolling.SLOW_MS, delay)
    }

    @Test
    fun `errors back off exponentially up to the cap`() {
        val one = JobsPolling.nextDelayMs(true, true, consecutiveErrors = 1, idleCycles = 0)
        val two = JobsPolling.nextDelayMs(true, true, consecutiveErrors = 2, idleCycles = 0)
        assertTrue(two > one)
        val many = JobsPolling.nextDelayMs(true, true, consecutiveErrors = 20, idleCycles = 0)
        assertEquals(JobsPolling.MAX_BACKOFF_MS, many)
    }
}
