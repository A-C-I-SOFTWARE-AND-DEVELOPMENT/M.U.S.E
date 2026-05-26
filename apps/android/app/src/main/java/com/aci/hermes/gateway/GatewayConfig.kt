package com.aci.hermes.gateway

/**
 * Connection settings for the Jarvis Prime Gateway. Persisted in
 * DataStore by the settings module — this data class is the in-memory
 * form passed to [JarvisGatewayClient] implementations.
 *
 * The gateway itself runs outside the phone. Hosts that store a token
 * are responsible for the lifecycle of that token — Jarvis Prime never
 * mints gateway-side secrets from the device.
 */
data class GatewayConfig(
    val baseUrl: String? = null,
    /** Bearer token; nullable for unauthenticated local gateways. */
    val bearerToken: String? = null,
    /** When false, callers should refuse to make real network calls. */
    val enabled: Boolean = false,
) {
    val isConfigured: Boolean
        get() = enabled && !baseUrl.isNullOrBlank()
}
