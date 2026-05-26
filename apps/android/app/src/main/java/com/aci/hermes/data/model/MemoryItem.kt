package com.aci.hermes.data.model

import kotlinx.serialization.Serializable
import java.util.UUID

@Serializable
enum class MemoryKind { FACT, PREFERENCE, ASPIRATION, SOCIAL, AUDIT_NOTE }

@Serializable
data class MemoryItem(
    val id: String = UUID.randomUUID().toString(),
    val kind: MemoryKind = MemoryKind.FACT,
    val content: String = "",
    val confidence: Float = 0.7f,
    val createdAt: Long = System.currentTimeMillis(),
    val updatedAt: Long = System.currentTimeMillis(),
    val source: String = "user",
    val redactedFields: List<String> = emptyList(),
) {
    init {
        require(confidence in 0f..1f) { "confidence must be in [0, 1]" }
    }
}
