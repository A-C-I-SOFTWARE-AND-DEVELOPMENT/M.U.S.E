package com.aci.hermes.data.gateway

import com.aci.hermes.util.LogBuffer
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

/**
 * Owns the active [GatewayClient] and applies its event stream through
 * [GatewayEventReducer] into a single [GatewayUiState].
 *
 * The controller is process-scoped (held by
 * [com.aci.hermes.di.AppContainer]) so that toggling between MOCK and
 * REAL transports in Settings tears down the old client and spins up a
 * fresh one without leaving stale subscribers in the UI tree.
 *
 * It deliberately never logs raw event payloads — only event *types* —
 * because future event subtypes may carry user content, and Logcat is
 * a system-wide sink.
 */
class GatewayController(
    private val mockFactory: () -> GatewayClient = { MockGatewayClient() },
    private val realFactory: (String) -> GatewayClient = { url -> HttpJarvisGatewayClient(url) },
    private val logBuffer: LogBuffer? = null,
    private val scope: CoroutineScope = CoroutineScope(SupervisorJob() + Dispatchers.Default),
) {

    private val _state = MutableStateFlow(GatewayUiState())
    val state: StateFlow<GatewayUiState> = _state.asStateFlow()

    private val mutex = Mutex()
    private var activeClient: GatewayClient? = null
    private var pumpJob: Job? = null
    private var connectionJob: Job? = null

    /** Currently active client, if any. Exposed so the UI can send events. */
    fun client(): GatewayClient? = activeClient

    /**
     * Tear down any active client and start a fresh one in [mode]. The
     * returned job completes when the connect attempt finishes — callers
     * usually don't await it.
     */
    suspend fun switchMode(mode: GatewayMode, baseUrl: String? = null) {
        mutex.withLock {
            pumpJob?.cancel()
            pumpJob = null
            connectionJob?.cancel()
            connectionJob = null

            runCatching { activeClient?.disconnect() }
            activeClient = null
            _state.value = GatewayUiState()

            val client = when (mode) {
                GatewayMode.MOCK -> mockFactory()
                GatewayMode.REAL -> realFactory(baseUrl.orEmpty())
            }
            activeClient = client

            pumpJob = scope.launch {
                client.events.collect { event ->
                    logBuffer?.info(TAG, "event ${event::class.simpleName}")
                    _state.update { GatewayEventReducer.reduce(it, event) }
                }
            }
            connectionJob = scope.launch {
                client.connectionState.collect { conn ->
                    _state.update { it.copy(connection = conn) }
                }
            }
            runCatching { client.connect() }.onFailure {
                logBuffer?.error(TAG, "gateway connect failed: ${it.javaClass.simpleName}")
            }
        }
    }

    suspend fun stop() {
        mutex.withLock {
            pumpJob?.cancel()
            pumpJob = null
            connectionJob?.cancel()
            connectionJob = null
            runCatching { activeClient?.disconnect() }
            activeClient = null
            _state.value = GatewayUiState()
        }
    }

    companion object {
        const val TAG = "GatewayController"
    }
}
