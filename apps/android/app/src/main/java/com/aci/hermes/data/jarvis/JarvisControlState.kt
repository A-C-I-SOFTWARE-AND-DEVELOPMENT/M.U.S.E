package com.aci.hermes.data.jarvis

/**
 * Aggregate state rendered by the Control screen. Built from a
 * pure projection of settings + service liveness — see
 * [JarvisControlProjector]. Everything here is plain Kotlin so the
 * Control tests can exercise the renderer without Compose.
 */
data class JarvisControlState(
    val jarvisRunning: Boolean = false,
    val service: ServiceState = ServiceState.STOPPED,
    val gateway: GatewayState = GatewayState.UNCONFIGURED,
    val gatewayEndpoint: String = "",
    val mockMode: Boolean = false,
    val autonomy: AutonomyMode = AutonomyMode.MANUAL,
    val permissions: PermissionState = PermissionState.UNKNOWN,
    val notifications: NotificationsState = NotificationsState.ENABLED,
    val voice: VoiceState = VoiceState.DISABLED,
    val icon: IconState = IconState.ENABLED,
    val emergencyStopEngaged: Boolean = false,
    val approvalsRequired: Boolean = true,
    val safetyGatesEnabled: Boolean = true,
    val connectedServices: List<ConnectedService> = emptyList(),
    val audit: AuditShortcut = AuditShortcut(recentEvents = 0, lastEventLabel = null),
    val memory: MemoryShortcut = MemoryShortcut(savedFacts = 0, lastNote = null),
    val pendingWarning: PendingWarning? = null,
) {
    val gatewayDisconnected: Boolean
        get() = gateway == GatewayState.DISCONNECTED || gateway == GatewayState.UNCONFIGURED

    val isLockdown: Boolean get() = autonomy.isLockdown
}

/**
 * A warning the UI is asking the owner to confirm before applying.
 * The screen renders the level + message and routes confirm/cancel
 * back to the ViewModel.
 */
data class PendingWarning(
    val level: WarningLevel,
    val title: String,
    val message: String,
    val confirmLabel: String,
    val action: ControlWarnings.Action,
)
