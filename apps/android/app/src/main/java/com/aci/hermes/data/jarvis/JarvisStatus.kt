package com.aci.hermes.data.jarvis

/**
 * Live status types rendered on the Control screen. They are
 * plain data — no Android references — so the screen, the
 * gateway poller, and the tests share one shape.
 */

enum class ServiceState { RUNNING, STOPPED, DEGRADED }

enum class GatewayState { CONNECTED, DISCONNECTED, MOCK, UNCONFIGURED }

enum class PermissionState { GRANTED, PARTIAL, DENIED, UNKNOWN }

enum class NotificationsState { ENABLED, DISABLED, BLOCKED_BY_SYSTEM }

enum class VoiceState { ENABLED, DISABLED, UNAVAILABLE }

enum class IconState { ENABLED, DISABLED }

data class ConnectedService(
    val id: String,
    val displayName: String,
    val connected: Boolean,
)

data class AuditShortcut(
    val recentEvents: Int,
    val lastEventLabel: String?,
)

data class MemoryShortcut(
    val savedFacts: Int,
    val lastNote: String?,
)
