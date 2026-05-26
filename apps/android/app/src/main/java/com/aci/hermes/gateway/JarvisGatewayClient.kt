package com.aci.hermes.gateway

import kotlinx.coroutines.flow.StateFlow

/**
 * Jarvis Prime Gateway client interface.
 *
 * The gateway is the brain; the phone is the body. This client is the
 * narrowest interface between them — enough for the UI to show the
 * current state and ask the gateway to refresh, but nothing that would
 * let the app bypass the Permission Kernel or directly execute
 * destructive actions. Destructive operations always go through the
 * approval flow, which is owned by a separate module.
 */
interface JarvisGatewayClient {

    /** Latest known state. Always-on StateFlow so the UI can collect once. */
    val state: StateFlow<GatewayState>

    /** Apply new connection settings. Triggers a refresh. */
    suspend fun configure(config: GatewayConfig)

    /** Force a refresh now. Suspends until the next state emission. */
    suspend fun refresh()

    /** Stop any in-flight polling and mark the connection offline. */
    suspend fun shutdown()
}
