package com.aci.hermes.data.jarvis

import kotlinx.coroutines.flow.Flow

/**
 * Routes the chat surface to the live gateway when the cockpit is paired
 * and falls back to the offline-safe mock otherwise.
 *
 * This is the chat half of the "off mocks" cutover: instead of a build-
 * time boolean, selection is evaluated per-send via [useLive], so the
 * moment the user pairs a token (Settings → Connection) the avatar
 * starts reflecting the real agent — and a fresh install, an offline
 * device, or a previewer stays on the mock with no daemon required.
 *
 * Selection is intentionally re-checked on every [send] / property read
 * (not cached) so pairing and unpairing take effect immediately without
 * rebuilding the container.
 */
class RoutingJarvisChatGateway(
    private val live: JarvisChatGateway,
    private val mock: JarvisChatGateway,
    private val useLive: () -> Boolean,
) : JarvisChatGateway {

    private fun active(): JarvisChatGateway = if (useLive()) live else mock

    override fun send(history: List<JarvisChatMessage>, prompt: String): Flow<JarvisChatChunk> =
        active().send(history, prompt)

    override val displayName: String
        get() = active().displayName

    // Streaming capability is the union — the renderer treats both as
    // streamable (the mock emits chunks too), so this stays stable across
    // a mid-session pairing change.
    override val supportsStreaming: Boolean = true
}
