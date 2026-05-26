package com.aci.hermes.data.model

import kotlinx.serialization.Serializable
import java.util.UUID

@Serializable
enum class SocialChannel { CHAT, EMAIL, MEETING, NOTE, OTHER }

/**
 * One social-intelligence observation about a person Jarvis Prime has
 * been told about. Identifiers are stored as redaction tokens — the
 * raw name / handle never sits at rest in this object.
 */
@Serializable
data class SocialSignal(
    val id: String = UUID.randomUUID().toString(),
    val subjectToken: String = "",
    val channel: SocialChannel = SocialChannel.NOTE,
    val summary: String = "",
    val sentiment: Float = 0f,
    val createdAt: Long = System.currentTimeMillis(),
    val source: String = "user",
) {
    init {
        require(sentiment in -1f..1f) { "sentiment must be in [-1, 1]" }
    }
}
