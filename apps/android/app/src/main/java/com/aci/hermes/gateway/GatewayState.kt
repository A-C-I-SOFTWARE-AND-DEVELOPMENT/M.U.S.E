package com.aci.hermes.gateway

import com.aci.hermes.data.cockpit.DetectedWorker
import com.aci.hermes.data.cockpit.QueueSnapshot

/**
 * Snapshot of what the Jarvis Prime Gateway is currently reporting.
 *
 * This is the read-model the UI consumes. Production wiring populates
 * it from the gateway's `/v1/runtime` and `/v1/workers` endpoints; the
 * mock client populates it deterministically for offline / test use.
 */
data class GatewayState(
    val connectivity: Connectivity = Connectivity.OFFLINE,
    val version: String? = null,
    val mode: String? = null,
    val queue: QueueSnapshot = QueueSnapshot(running = 0, queued = 0, waitingApproval = 0),
    val workers: List<DetectedWorker> = emptyList(),
    val lastError: String? = null,
) {
    enum class Connectivity {
        OFFLINE,        // not configured or explicitly disabled
        CONNECTING,
        ONLINE,
        DEGRADED,       // partial / unhealthy response
        FAILED,         // last call returned an error
    }
}
