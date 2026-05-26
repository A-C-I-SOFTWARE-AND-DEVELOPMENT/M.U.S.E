package com.aci.hermes.data.jarvis

import com.aci.hermes.data.preferences.SettingsRepository

/**
 * Pure projection from settings + service liveness to the Control
 * screen state. Kept Android-free so tests can drive every code
 * path without spinning up Robolectric.
 */
object JarvisControlProjector {

    fun project(
        snapshot: SettingsRepository.Snapshot,
        serviceRunning: Boolean,
        gatewayReachable: Boolean,
        connectedServices: List<ConnectedService> = emptyList(),
        audit: AuditShortcut = AuditShortcut(recentEvents = 0, lastEventLabel = null),
        memory: MemoryShortcut = MemoryShortcut(savedFacts = 0, lastNote = null),
    ): JarvisControlState {
        val gateway = when {
            snapshot.mockMode -> GatewayState.MOCK
            snapshot.gatewayEndpoint.isBlank() -> GatewayState.UNCONFIGURED
            gatewayReachable -> GatewayState.CONNECTED
            else -> GatewayState.DISCONNECTED
        }
        val service = when {
            snapshot.emergencyStopEngaged -> ServiceState.STOPPED
            serviceRunning -> ServiceState.RUNNING
            else -> ServiceState.STOPPED
        }
        val notifications =
            if (snapshot.notificationsEnabled) NotificationsState.ENABLED
            else NotificationsState.DISABLED
        val voice =
            if (snapshot.voiceEnabled) VoiceState.ENABLED
            else VoiceState.DISABLED
        val icon =
            if (snapshot.interactiveIconEnabled) IconState.ENABLED
            else IconState.DISABLED
        return JarvisControlState(
            jarvisRunning = service == ServiceState.RUNNING,
            service = service,
            gateway = gateway,
            gatewayEndpoint = snapshot.gatewayEndpoint,
            mockMode = snapshot.mockMode,
            autonomy = snapshot.autonomyMode,
            permissions = PermissionState.GRANTED,
            notifications = notifications,
            voice = voice,
            icon = icon,
            emergencyStopEngaged = snapshot.emergencyStopEngaged,
            approvalsRequired = snapshot.approvalsRequired,
            safetyGatesEnabled = snapshot.safetyGatesEnabled,
            connectedServices = connectedServices,
            audit = audit,
            memory = memory,
        )
    }
}
