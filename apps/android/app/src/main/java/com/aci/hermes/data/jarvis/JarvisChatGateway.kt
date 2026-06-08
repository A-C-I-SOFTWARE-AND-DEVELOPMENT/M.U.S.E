package com.aci.hermes.data.jarvis

import kotlinx.coroutines.flow.Flow

/**
 * Pluggable backend for the MUSE chat surface.
 *
 * The chat screen never calls anything outside this interface. That's
 * how mock mode, eventual streaming HTTP, and unit tests stay
 * interchangeable: every implementation just returns a [Flow] of
 * [JarvisChatChunk] values.
 *
 * Implementations should:
 *  - emit [JarvisChatChunk.Thinking] eagerly so the UI bubble appears
 *  - emit [JarvisChatChunk.Done] exactly once on clean completion
 *  - emit [JarvisChatChunk.Failure] instead of throwing for gateway
 *    errors so the renderer can offer a Retry button
 *  - honour flow cancellation as the user's "stop" / abort action
 */
interface JarvisChatGateway {
    fun send(history: List<JarvisChatMessage>, prompt: String): Flow<JarvisChatChunk>

    /** Stable identifier used for snackbars and diagnostics. */
    val displayName: String

    /** True if this gateway streams (token-by-token); false if monolithic. */
    val supportsStreaming: Boolean
}
