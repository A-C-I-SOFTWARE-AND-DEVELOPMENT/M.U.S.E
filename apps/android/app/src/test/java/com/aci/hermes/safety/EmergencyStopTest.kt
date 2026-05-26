package com.aci.hermes.safety

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.util.concurrent.atomic.AtomicInteger

class EmergencyStopTest {

    @Test fun engage_notifies_each_listener_once_with_reason() {
        val stop = EmergencyStop()
        val reasons = mutableListOf<String>()
        stop.register { reasons += it }
        val notified = stop.engage("user_tap")
        assertEquals(1, notified)
        assertEquals(listOf("user_tap"), reasons)
        assertTrue(stop.engaged.value)
        assertEquals("user_tap", stop.lastReason.value)
    }

    @Test fun engage_is_idempotent() {
        val stop = EmergencyStop()
        val count = AtomicInteger()
        stop.register { count.incrementAndGet() }
        stop.engage("first")
        stop.engage("second")
        assertEquals(1, count.get())
        assertEquals("first", stop.lastReason.value)
    }

    @Test fun reset_clears_state_and_lets_engage_fire_again() {
        val stop = EmergencyStop()
        val count = AtomicInteger()
        stop.register { count.incrementAndGet() }
        stop.engage("first")
        stop.reset()
        assertFalse(stop.engaged.value)
        assertNull(stop.lastReason.value)
        stop.engage("second")
        assertEquals(2, count.get())
    }

    @Test fun a_failing_listener_does_not_block_subsequent_listeners() {
        val stop = EmergencyStop()
        var secondCalled = false
        stop.register { throw RuntimeException("boom") }
        stop.register { secondCalled = true }
        val notified = stop.engage("test")
        assertTrue(secondCalled)
        // Only the successful listener counts.
        assertEquals(1, notified)
    }

    @Test fun unregistered_listener_is_not_invoked() {
        val stop = EmergencyStop()
        var called = false
        val listener = EmergencyStop.Listener { called = true }
        stop.register(listener)
        stop.unregister(listener)
        stop.engage("test")
        assertFalse(called)
    }
}
