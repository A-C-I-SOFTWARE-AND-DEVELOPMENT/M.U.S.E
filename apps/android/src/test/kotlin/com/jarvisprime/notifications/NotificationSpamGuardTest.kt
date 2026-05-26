package com.jarvisprime.notifications

import kotlin.test.Test
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class NotificationSpamGuardTest {

    @Test
    fun `repeated events within the window are blocked`() {
        val clock = FakeClock()
        val guard = NotificationSpamGuard(clock, windowMillis = 1_000L)
        val e = event(NotificationType.TASK_COMPLETE, id = "abc")

        assertTrue(guard.allow(e))
        clock.advance(500)
        assertFalse(guard.allow(e))
    }

    @Test
    fun `events outside the window are allowed`() {
        val clock = FakeClock()
        val guard = NotificationSpamGuard(clock, windowMillis = 1_000L)
        val e = event(NotificationType.TASK_COMPLETE, id = "abc")

        assertTrue(guard.allow(e))
        clock.advance(1_500)
        assertTrue(guard.allow(e))
    }

    @Test
    fun `dedupe key collapses progressive updates`() {
        val clock = FakeClock()
        val guard = NotificationSpamGuard(clock, windowMillis = 10_000L)
        val a = event(NotificationType.WORKER_FAILED, id = "evt-1", payload = mapOf("dedupeKey" to "worker-42"))
        val b = event(NotificationType.WORKER_FAILED, id = "evt-2", payload = mapOf("dedupeKey" to "worker-42"))

        assertTrue(guard.allow(a))
        assertFalse(guard.allow(b))
    }

    @Test
    fun `emergency stop bypasses the spam guard`() {
        val clock = FakeClock()
        val guard = NotificationSpamGuard(clock, windowMillis = 10_000L)
        val e = event(NotificationType.EMERGENCY_STOP_ACTIVE, id = "stop-1")

        assertTrue(guard.allow(e))
        assertTrue(guard.allow(e), "EMERGENCY_STOP_ACTIVE must never be silenced by the guard")
    }
}
