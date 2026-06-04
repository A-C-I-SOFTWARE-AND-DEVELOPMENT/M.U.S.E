package com.aci.hermes.testutil

import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test

class AwaitTest {

    @Test
    fun `default budget is positive and generous`() {
        // Covers contended-CI scheduling latency (env override aside).
        assertTrue(DEFAULT_AWAIT_TIMEOUT_MS > 0)
    }

    @Test
    fun `awaitUntil returns once the condition holds`() {
        var ticks = 0
        awaitUntil(timeoutMs = 1_000, intervalMs = 1, message = "ticks reach 3") {
            ticks += 1
            ticks >= 3
        }
        assertTrue(ticks >= 3)
    }

    @Test
    fun `awaitUntil throws a bounded failure when the condition never holds`() {
        val err = assertThrows(AssertionError::class.java) {
            awaitUntil(timeoutMs = 30, intervalMs = 5, message = "never true") { false }
        }
        assertTrue(err.message!!.contains("never true"))
    }

    @Test
    fun `awaitValue returns the suspend block result`() {
        assertEquals(42, awaitValue(timeoutMs = 1_000) { 42 })
    }
}
