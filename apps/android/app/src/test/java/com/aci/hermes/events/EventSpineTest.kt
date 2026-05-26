package com.aci.hermes.events

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class EventSpineTest {

    @Test fun emit_records_and_emits_event_with_unique_ids() {
        val spine = EventSpine()
        val a = spine.emit(JarvisEvent.Source.SYSTEM, JarvisEvent.Severity.INFO, "hi")
        val b = spine.emit(JarvisEvent.Source.SYSTEM, JarvisEvent.Severity.INFO, "again")
        assertEquals(2, spine.events.value.size)
        assertTrue(a.id != b.id)
    }

    @Test fun bounded_buffer_drops_oldest_entries() {
        val spine = EventSpine(capacity = 3)
        repeat(10) { i ->
            spine.emit(JarvisEvent.Source.SYSTEM, JarvisEvent.Severity.TRACE, "msg-$i")
        }
        val msgs = spine.events.value.map { it.message }
        assertEquals(listOf("msg-7", "msg-8", "msg-9"), msgs)
    }

    @Test fun by_source_filters_correctly() {
        val spine = EventSpine()
        spine.emit(JarvisEvent.Source.WORKER, JarvisEvent.Severity.INFO, "worker started")
        spine.emit(JarvisEvent.Source.APPROVAL, JarvisEvent.Severity.NOTICE, "needs approval")
        val workerEvents = spine.bySource(JarvisEvent.Source.WORKER)
        assertEquals(1, workerEvents.size)
        assertEquals("worker started", workerEvents.single().message)
    }

    @Test fun most_severe_returns_highest_ordinal() {
        val spine = EventSpine()
        spine.emit(JarvisEvent.Source.SYSTEM, JarvisEvent.Severity.INFO, "fine")
        spine.emit(JarvisEvent.Source.GATEWAY, JarvisEvent.Severity.WARN, "slow")
        spine.emit(JarvisEvent.Source.EMERGENCY_STOP, JarvisEvent.Severity.CRITICAL, "engaged")
        assertEquals(JarvisEvent.Severity.CRITICAL, spine.mostSevere())
    }

    @Test fun severity_ordering_is_locked() {
        // Audit and dashboard consumers depend on this ordering.
        val expected = listOf(
            JarvisEvent.Severity.TRACE,
            JarvisEvent.Severity.INFO,
            JarvisEvent.Severity.NOTICE,
            JarvisEvent.Severity.WARN,
            JarvisEvent.Severity.CRITICAL,
        )
        assertEquals(expected, JarvisEvent.Severity.entries.toList())
    }
}
