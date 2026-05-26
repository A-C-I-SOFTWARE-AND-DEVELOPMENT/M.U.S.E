package com.aci.hermes.data.gateway

/**
 * Single source of truth for whether the app considers itself attached
 * to a Jarvis Prime gateway. The screen, status indicators, and runtime
 * permission kernel all derive from this — they never poll the client
 * directly.
 *
 * Mapped from [GatewayConnectedEvent] and [GatewayDisconnectedEvent] by
 * [GatewayEventReducer]; intermediate [Connecting] is driven by the
 * client when it starts an attach attempt.
 */
sealed class GatewayConnectionState {
    /** Nothing has tried to connect yet. */
    data object Idle : GatewayConnectionState()

    /** An attach attempt is in flight. */
    data class Connecting(val mode: GatewayMode) : GatewayConnectionState()

    /** Spine is live and emitting events. */
    data class Connected(
        val gatewayId: String,
        val protocolVersion: String,
        val mode: GatewayMode,
    ) : GatewayConnectionState()

    /**
     * Spine dropped. `reason` is a short human label, never a stack
     * trace or token — strings here render in the diagnostics UI.
     */
    data class Disconnected(val reason: String) : GatewayConnectionState()

    /**
     * Connect attempt failed. Treated like [Disconnected] for UI
     * purposes, but kept separate so the diagnostics screen can show
     * a different banner.
     */
    data class Failed(val reason: String) : GatewayConnectionState()
}

enum class GatewayMode { MOCK, REAL }
