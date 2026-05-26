package com.aci.hermes.data.gateway

import android.content.Context
import com.aci.hermes.data.JsonStore
import com.aci.hermes.data.model.GatewayConnectionState
import com.aci.hermes.data.model.GatewayEvent
import com.aci.hermes.data.model.GatewayMode
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * Event Spine — the gateway-event bus.
 *
 * Streams events from whatever source is active: a mock generator, a
 * local Termux gateway, or a remote gateway. Holds a tail of recent
 * events so the Gateway screen can render a live timeline.
 */
class GatewayEventBus(context: Context) {

    private val store = JsonStore(
        context = context,
        fileName = "jarvis_gateway_events.json",
        serializer = GatewayEvent.serializer(),
        maxItems = MAX_EVENTS,
    )

    val events: StateFlow<List<GatewayEvent>> = store.items

    private val _mode = MutableStateFlow(GatewayMode.MOCK)
    val mode: StateFlow<GatewayMode> = _mode.asStateFlow()

    private val _connection = MutableStateFlow(GatewayConnectionState.DISCONNECTED)
    val connection: StateFlow<GatewayConnectionState> = _connection.asStateFlow()

    suspend fun load() {
        store.load()
    }

    suspend fun emit(event: GatewayEvent) {
        store.add(event, atStart = true)
    }

    fun setMode(mode: GatewayMode) {
        _mode.value = mode
        _connection.value = when (mode) {
            GatewayMode.MOCK -> GatewayConnectionState.CONNECTED
            GatewayMode.TERMUX -> GatewayConnectionState.DISCONNECTED
            GatewayMode.REMOTE -> GatewayConnectionState.DISCONNECTED
        }
    }

    fun setConnection(state: GatewayConnectionState) {
        _connection.value = state
    }

    suspend fun clear() {
        store.clear()
    }

    suspend fun seedIfEmpty(builder: () -> List<GatewayEvent>) {
        store.seedIfEmpty(builder)
    }

    companion object {
        const val MAX_EVENTS = 200
    }
}
