package com.aci.hermes.gateway

import com.aci.hermes.data.cockpit.DetectedWorker
import com.aci.hermes.data.cockpit.QueueSnapshot
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update

/**
 * Offline, deterministic [JarvisGatewayClient] for development and
 * tests. Returns a believable set of workers + queue counts so the
 * Operations screen demonstrates its layout without a real gateway.
 *
 * Never performs network IO. Real wiring lives in
 * `OkHttpJarvisGatewayClient` (lands in a follow-up wave); the contract
 * stays the same so the UI does not branch on which client is bound.
 */
class MockJarvisGatewayClient : JarvisGatewayClient {

    private val _state = MutableStateFlow(seed())
    override val state: StateFlow<GatewayState> = _state.asStateFlow()

    override suspend fun configure(config: GatewayConfig) {
        _state.update { current ->
            if (!config.isConfigured) {
                current.copy(connectivity = GatewayState.Connectivity.OFFLINE, lastError = null)
            } else {
                current.copy(connectivity = GatewayState.Connectivity.ONLINE, lastError = null)
            }
        }
    }

    override suspend fun refresh() {
        _state.update { it.copy(lastError = null) }
    }

    override suspend fun shutdown() {
        _state.update { it.copy(connectivity = GatewayState.Connectivity.OFFLINE) }
    }

    private fun seed(): GatewayState = GatewayState(
        connectivity = GatewayState.Connectivity.OFFLINE,
        version = "mock-1.0.0",
        mode = "local_subscription_tools",
        queue = QueueSnapshot(running = 0, queued = 0, waitingApproval = 0),
        workers = listOf(
            DetectedWorker(
                id = "codex",
                displayName = "OpenAI Codex",
                kind = "subscription",
                available = false,
                notes = "Not detected — connect gateway to populate.",
            ),
            DetectedWorker(
                id = "claude-code",
                displayName = "Claude Code",
                kind = "cli",
                available = false,
                notes = "Not detected — connect gateway to populate.",
            ),
        ),
    )
}
