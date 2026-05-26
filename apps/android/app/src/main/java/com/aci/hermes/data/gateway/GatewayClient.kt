package com.aci.hermes.data.gateway

import com.aci.hermes.data.model.Approval
import com.aci.hermes.data.model.GatewayEvent
import kotlinx.coroutines.flow.Flow

/**
 * Gateway abstraction. Both the in-process [FakeGatewayClient] (mock
 * mode) and the [TermuxGatewayClient] implement it. The UI never
 * branches on which implementation is active — it consumes the spine
 * via [events] and posts intent through the request methods below.
 */
interface GatewayClient {

    val mode: GatewayMode

    val events: Flow<GatewayEvent>

    val connection: Flow<ConnectionState>

    suspend fun start()

    suspend fun stop()

    suspend fun submitChat(text: String): ChatResponse

    suspend fun submitVoiceTranscript(text: String): ChatResponse

    suspend fun decideApproval(approval: Approval, approve: Boolean, notes: String?)

    suspend fun heartbeat()
}

enum class GatewayMode { MOCK, TERMUX, DISCONNECTED }

sealed interface ConnectionState {
    data object Connected : ConnectionState
    data object Disconnected : ConnectionState
    data class Degraded(val reason: String) : ConnectionState
}

data class ChatResponse(
    val replyText: String,
    val suggestedTaskTitle: String? = null,
    val createdApprovalId: String? = null,
)
