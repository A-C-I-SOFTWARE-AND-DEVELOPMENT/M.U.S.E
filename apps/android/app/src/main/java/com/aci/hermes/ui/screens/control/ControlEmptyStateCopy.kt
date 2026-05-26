package com.aci.hermes.ui.screens.control

import com.aci.hermes.data.jarvis.AutonomyMode
import com.aci.hermes.data.jarvis.GatewayState
import com.aci.hermes.data.jarvis.JarvisControlState
import com.aci.hermes.data.jarvis.ServiceState

/**
 * Owner-facing copy for the Control surface. Kept as a plain Kotlin
 * object so the Compose screen and the JVM tests share one source of
 * truth — a future copy edit lands here, the screen re-reads, and the
 * pinning tests catch any drift.
 */
object ControlEmptyStateCopy {

    const val GATEWAY_CONNECTED = "Gateway reachable"
    const val GATEWAY_DISCONNECTED = "Gateway unreachable — owner action required"
    const val GATEWAY_MOCK = "Mock gateway (owner-only fake responses)"
    const val GATEWAY_UNCONFIGURED = "Gateway not configured — set an endpoint in Settings"

    const val TERMUX_CONNECTED = "Termux bridge connected"
    const val TERMUX_DISCONNECTED = "Termux bridge offline"
    const val TERMUX_ABSENT = "Termux bridge not installed"

    const val SERVICE_RUNNING_OWNER = "Owner-controlled service is running. Approvals still gate destructive steps."
    const val SERVICE_STOPPED_OWNER = "Service is stopped. Jarvis will not act on its own. Tap Start when you are ready."
    const val SERVICE_LOCKDOWN =
        "Lockdown engaged — Jarvis is paused. No outbound actions, no handoffs, no automation."
    const val SERVICE_EMERGENCY_STOPPED =
        "Emergency stop engaged. Service halted by owner. Release the stop to bring Jarvis back online."

    const val EMPTY_AUDIT = "No audit events yet. Approved actions and verification results will land here."
    const val EMPTY_MEMORY = "No memory entries yet. Jarvis will only remember what you approve."
    const val EMPTY_SERVICES =
        "No connected services. Gateway, Termux bridge, and Memory will appear here once wired by the owner."

    /**
     * Pick the right owner-facing service-state summary for the
     * current [state]. Order matters: emergency stop > lockdown >
     * running > stopped. The screen renders the resulting string;
     * tests assert each branch.
     */
    fun serviceSummary(state: JarvisControlState): String = when {
        state.emergencyStopEngaged -> SERVICE_EMERGENCY_STOPPED
        state.autonomy == AutonomyMode.LOCKDOWN -> SERVICE_LOCKDOWN
        state.service == ServiceState.RUNNING -> SERVICE_RUNNING_OWNER
        else -> SERVICE_STOPPED_OWNER
    }

    fun gatewaySummary(gateway: GatewayState): String = when (gateway) {
        GatewayState.CONNECTED -> GATEWAY_CONNECTED
        GatewayState.DISCONNECTED -> GATEWAY_DISCONNECTED
        GatewayState.MOCK -> GATEWAY_MOCK
        GatewayState.UNCONFIGURED -> GATEWAY_UNCONFIGURED
    }

    fun termuxSummary(connected: Boolean, installed: Boolean): String = when {
        !installed -> TERMUX_ABSENT
        connected -> TERMUX_CONNECTED
        else -> TERMUX_DISCONNECTED
    }
}
