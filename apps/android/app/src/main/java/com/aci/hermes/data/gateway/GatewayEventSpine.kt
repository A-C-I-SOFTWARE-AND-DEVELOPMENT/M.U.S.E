package com.aci.hermes.data.gateway

import com.aci.hermes.data.model.GatewayEvent
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.shareIn
import kotlinx.coroutines.launch

/**
 * Single fan-out point for every gateway event. Hot, replay-capped to
 * a small history so late subscribers still see the most recent state
 * changes (handy for screens entering the back stack mid-session).
 *
 * The spine also publishes the active [GatewayMode] and connection
 * state so screens don't have to subscribe to the underlying client
 * directly.
 */
class GatewayEventSpine {

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)

    private val _activeClient = MutableStateFlow<GatewayClient?>(null)
    val activeMode: StateFlow<GatewayMode> = MutableStateFlow(GatewayMode.DISCONNECTED).also { state ->
        scope.launch {
            _activeClient.collect { client -> state.value = client?.mode ?: GatewayMode.DISCONNECTED }
        }
    }.asStateFlow()

    private val _connection = MutableStateFlow<ConnectionState>(ConnectionState.Disconnected)
    val connection: StateFlow<ConnectionState> = _connection.asStateFlow()

    private val _events = MutableStateFlow<GatewayEvent?>(null)
    val latest: StateFlow<GatewayEvent?> = _events.asStateFlow()

    private var eventJob: Job? = null
    private var connJob: Job? = null

    /**
     * Switch to a new gateway implementation. Cancels the previous
     * subscriptions and rewires the spine to the new client. Safe to
     * call repeatedly with the same client (no-op).
     */
    fun bind(client: GatewayClient) {
        if (_activeClient.value === client) return
        eventJob?.cancel()
        connJob?.cancel()
        _activeClient.value = client
        eventJob = scope.launch {
            client.events.collect { event -> _events.value = event }
        }
        connJob = scope.launch {
            client.connection.collect { state -> _connection.value = state }
        }
    }

    fun events(): Flow<GatewayEvent> =
        // Re-share the active client's flow so multiple screens can
        // collect without each one creating a separate subscription
        // upstream.
        kotlinx.coroutines.flow.flow<GatewayEvent> {
            val client = _activeClient.value ?: return@flow
            client.events.collect { emit(it) }
        }.shareIn(scope, SharingStarted.WhileSubscribed(5_000), replay = 8)

    fun current(): GatewayClient? = _activeClient.value
}
