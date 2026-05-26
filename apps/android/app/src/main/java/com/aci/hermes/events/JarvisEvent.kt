package com.aci.hermes.events

import kotlinx.serialization.Serializable

/**
 * Single entry on the Jarvis Prime Event Spine.
 *
 * Events are immutable, append-only, and carry the minimum metadata
 * the audit log and the dashboards need. Severity drives both UI
 * tinting and whether the audit module surfaces the entry by default.
 */
@Serializable
data class JarvisEvent(
    val id: String,
    val timestamp: Long,
    val source: Source,
    val severity: Severity,
    val message: String,
    val attributes: Map<String, String> = emptyMap(),
) {
    @Serializable
    enum class Source {
        SYSTEM,
        CONVERSATION,
        MEMORY,
        APPROVAL,
        WORKER,
        GATEWAY,
        EMERGENCY_STOP,
    }

    @Serializable
    enum class Severity { TRACE, INFO, NOTICE, WARN, CRITICAL }
}
