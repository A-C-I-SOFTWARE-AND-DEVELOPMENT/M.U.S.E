package com.aci.hermes.data.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import java.util.UUID

@Serializable
enum class Role {
    @SerialName("user") USER,
    @SerialName("assistant") ASSISTANT,
    @SerialName("system") SYSTEM,
    @SerialName("tool") TOOL
}

@Serializable
data class ChatMessage(
    val id: String = UUID.randomUUID().toString(),
    val role: Role,
    val content: String,
    val createdAt: Long = System.currentTimeMillis(),
    val pending: Boolean = false,
    val errorText: String? = null
)
