package com.aci.hermes.events

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import java.util.UUID
import java.util.concurrent.atomic.AtomicLong

/**
 * Jarvis Prime Event Spine.
 *
 * In-process append-only event bus that fans out from every Jarvis
 * Prime subsystem to interested observers (the audit log, the
 * Operations screen, the interactive icon). The spine is intentionally
 * tiny — there is no persistence here, no replay semantics, no
 * cross-process delivery. Subsystems that need durability persist on
 * their own (the audit log persists; the dashboard does not).
 *
 * The buffer is bounded so a misbehaving subsystem cannot grow it
 * unboundedly during a flood.
 */
class EventSpine(private val capacity: Int = DEFAULT_CAPACITY) {

    private val seq = AtomicLong()

    private val _events = MutableStateFlow<List<JarvisEvent>>(emptyList())
    val events: StateFlow<List<JarvisEvent>> = _events.asStateFlow()

    /**
     * Append an event. Returns the recorded event so callers can
     * reference its id when correlating with downstream effects.
     */
    fun emit(
        source: JarvisEvent.Source,
        severity: JarvisEvent.Severity,
        message: String,
        attributes: Map<String, String> = emptyMap(),
    ): JarvisEvent {
        val event = JarvisEvent(
            id = nextId(),
            timestamp = System.currentTimeMillis(),
            source = source,
            severity = severity,
            message = message,
            attributes = attributes,
        )
        _events.update { current -> (current + event).takeLast(capacity) }
        return event
    }

    fun bySource(source: JarvisEvent.Source): List<JarvisEvent> =
        events.value.filter { it.source == source }

    fun mostSevere(): JarvisEvent.Severity? =
        events.value.maxByOrNull { it.severity.ordinal }?.severity

    private fun nextId(): String = "${seq.incrementAndGet()}-${UUID.randomUUID()}"

    companion object {
        const val DEFAULT_CAPACITY = 500
    }
}
