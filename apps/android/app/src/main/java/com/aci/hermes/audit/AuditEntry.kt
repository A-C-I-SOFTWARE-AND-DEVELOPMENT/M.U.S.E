package com.aci.hermes.audit

import com.aci.hermes.events.JarvisEvent
import kotlinx.serialization.Serializable
import java.util.UUID

/**
 * One row in the Jarvis Prime audit history.
 *
 * Entries are immutable, append-only, and persisted. They are the
 * durable equivalent of [JarvisEvent] — events feed audit; audit
 * survives a process restart.
 */
@Serializable
data class AuditEntry(
    val id: String = UUID.randomUUID().toString(),
    val timestamp: Long = System.currentTimeMillis(),
    val source: JarvisEvent.Source,
    val severity: JarvisEvent.Severity,
    val message: String,
    val attributes: Map<String, String> = emptyMap(),
    /**
     * The body the owner saw at decision time, for approvals. For
     * non-approval entries this is empty.
     */
    val proofSnapshot: String = "",
) {
    companion object {
        fun fromEvent(event: JarvisEvent, proofSnapshot: String = ""): AuditEntry =
            AuditEntry(
                timestamp = event.timestamp,
                source = event.source,
                severity = event.severity,
                message = event.message,
                attributes = event.attributes,
                proofSnapshot = proofSnapshot,
            )
    }
}
