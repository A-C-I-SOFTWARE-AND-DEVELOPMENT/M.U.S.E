package com.aci.hermes.data.model

import kotlinx.serialization.Serializable
import java.util.UUID

/**
 * Gateway Event Spine — every push from a backing gateway (mock or
 * Termux) is normalized into one of these envelopes. Screens fan out
 * from the spine; no screen polls the gateway directly.
 */
@Serializable
enum class GatewayEventType {
    HEARTBEAT,
    APPROVAL_OPENED,
    APPROVAL_DECIDED,
    TASK_CREATED,
    TASK_UPDATED,
    MEMORY_UPDATED,
    SOCIAL_UPDATED,
    AUDIT_APPENDED,
    EMERGENCY_STOP_CHANGED,
    CONNECTION_CHANGED,
    CHAT_REPLY,
    DIAGNOSTIC,
}

@Serializable
data class GatewayEvent(
    val id: String = UUID.randomUUID().toString(),
    val type: GatewayEventType,
    val payload: String = "",
    val refId: String? = null,
    val createdAt: Long = System.currentTimeMillis(),
)
