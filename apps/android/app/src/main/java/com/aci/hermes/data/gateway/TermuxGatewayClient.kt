package com.aci.hermes.data.gateway

import com.aci.hermes.data.model.Approval
import com.aci.hermes.data.model.GatewayEvent
import com.aci.hermes.data.model.GatewayEventType
import com.aci.hermes.data.termux.TermuxIntentBridge
import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * Routes gateway calls through the Termux companion when installed.
 * This is a thin façade in this phase — the actual intent dispatch and
 * polling are handled by [TermuxIntentBridge]; we only wire the spine
 * up so the UI can render a "Termux gateway" badge and disconnect
 * cleanly when Termux is unavailable.
 *
 * No network calls. No background workers. Every method that produces
 * a side-effect goes through the bridge, which the user has to have
 * granted the Termux RUN_COMMAND permission for separately.
 */
class TermuxGatewayClient(
    private val bridge: TermuxIntentBridge,
) : GatewayClient {

    override val mode: GatewayMode = GatewayMode.TERMUX

    private val _events = MutableSharedFlow<GatewayEvent>(
        replay = 32,
        extraBufferCapacity = 64,
        onBufferOverflow = BufferOverflow.DROP_OLDEST,
    )
    override val events: Flow<GatewayEvent> = _events.asSharedFlow()

    private val _connection = MutableStateFlow<ConnectionState>(ConnectionState.Disconnected)
    override val connection: Flow<ConnectionState> = _connection.asStateFlow()

    override suspend fun start() {
        val available = bridge.isTermuxInstalled()
        _connection.value = if (available) ConnectionState.Connected
        else ConnectionState.Degraded("Termux not installed")
        _events.tryEmit(
            GatewayEvent(
                type = GatewayEventType.CONNECTION_CHANGED,
                payload = if (available) "connected:termux" else "termux_unavailable",
            )
        )
    }

    override suspend fun stop() {
        _connection.value = ConnectionState.Disconnected
        _events.tryEmit(
            GatewayEvent(
                type = GatewayEventType.CONNECTION_CHANGED,
                payload = "disconnected",
            )
        )
    }

    override suspend fun submitChat(text: String): ChatResponse {
        // We never silently dispatch to Termux from the UI thread; this
        // method records the intent in the spine but returns a holding
        // reply. The dashboard surfaces a tap-to-dispatch UI for the
        // actual Termux RUN_COMMAND envelope.
        _events.tryEmit(
            GatewayEvent(
                type = GatewayEventType.DIAGNOSTIC,
                payload = "chat_held_for_user_dispatch",
            )
        )
        return ChatResponse(
            replyText = "Termux mode requires you to dispatch the request manually from the chat row.",
        )
    }

    override suspend fun submitVoiceTranscript(text: String): ChatResponse =
        submitChat("voice: $text")

    override suspend fun decideApproval(
        approval: Approval,
        approve: Boolean,
        notes: String?,
    ) {
        _events.tryEmit(
            GatewayEvent(
                type = GatewayEventType.APPROVAL_DECIDED,
                payload = if (approve) "approved" else "rejected",
                refId = approval.id,
            )
        )
    }

    override suspend fun heartbeat() {
        _events.tryEmit(GatewayEvent(type = GatewayEventType.HEARTBEAT, payload = "ok"))
    }
}
