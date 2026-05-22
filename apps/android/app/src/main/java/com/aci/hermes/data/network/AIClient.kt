package com.aci.hermes.data.network

import com.aci.hermes.data.model.ChatMessage
import com.aci.hermes.data.model.HermesStatus
import kotlinx.coroutines.flow.Flow

/**
 * Abstraction over "the thing that answers a chat turn". Four
 * implementations exist today:
 *
 *   * [MockAIClient]          — canned responses, no network.
 *   * [DirectAIClient]        — phone calls an OpenAI-compatible provider
 *                               directly (OpenRouter, OpenAI, custom
 *                               endpoint). Personal-use mode.
 *   * [HermesGatewayClient]   — phone talks to a Hermes gateway (full
 *                               agent stack: skills, memory, tools).
 *
 * Picked at runtime by [AIClientFactory] based on the user's
 * [com.aci.hermes.data.preferences.ConnectionMode] selection.
 *
 * Historical note: this interface used to be called `HermesClient`. It
 * was renamed when Direct mode landed; the abstraction is now about
 * "any AI backend" rather than specifically about Hermes.
 */
interface AIClient {

    /** Whether this client is the canned-response sandbox. */
    val isMock: Boolean

    /** Free-form name shown in Status / Diagnostics. */
    val providerName: String

    /** One-shot health check. */
    suspend fun status(): HermesStatus

    /**
     * Sends a chat turn and emits assistant tokens (as accumulating-content
     * [ChatMessage] updates). The terminal emission has `pending = false`.
     * On error, emits a single [ChatMessage] with `errorText` set.
     */
    fun chat(history: List<ChatMessage>, prompt: String): Flow<ChatMessage>
}
