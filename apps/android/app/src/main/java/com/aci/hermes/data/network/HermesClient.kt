package com.aci.hermes.data.network

import com.aci.hermes.data.model.ChatMessage
import com.aci.hermes.data.model.HermesStatus
import kotlinx.coroutines.flow.Flow

/**
 * Talks to a Hermes gateway. Two implementations:
 *   * [HermesGatewayClient]  — HTTP/SSE against a running gateway.
 *   * [MockHermesClient]     — deterministic canned responses, used when
 *                              the user enables mock mode or no gateway
 *                              is configured.
 *
 * The gateway protocol intentionally tracks the existing Hermes gateway's
 * REST surface (`/v1/health`, `/v1/chat`); see
 * `apps/android/docs/ARCHITECTURE.md` for the wire format.
 */
interface HermesClient {

    /** Returns whether this client points at a real backend. */
    val isMock: Boolean

    /** One-shot health check. */
    suspend fun status(): HermesStatus

    /**
     * Sends a chat turn and emits assistant tokens (as accumulating-content
     * [ChatMessage] updates). The terminal emission has `pending = false`.
     * On error, emits a single [ChatMessage] with `errorText` set.
     */
    fun chat(history: List<ChatMessage>, prompt: String): Flow<ChatMessage>
}
