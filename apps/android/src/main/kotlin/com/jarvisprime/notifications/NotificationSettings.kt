package com.jarvisprime.notifications

/**
 * User-controlled notification toggles. EMERGENCY_STOP_ACTIVE cannot be silenced
 * — Jarvis Prime's safety contract requires the owner to always see when the
 * emergency stop fires, even if every other channel is muted.
 */
data class NotificationSettings(
    val masterEnabled: Boolean = true,
    val perType: Map<NotificationType, Boolean> = defaultPerType(),
) {

    fun isAllowed(type: NotificationType): Boolean {
        if (type == NotificationType.EMERGENCY_STOP_ACTIVE) return true
        if (!masterEnabled) return false
        return perType[type] ?: true
    }

    fun withType(type: NotificationType, enabled: Boolean): NotificationSettings {
        if (type == NotificationType.EMERGENCY_STOP_ACTIVE && !enabled) {
            return this
        }
        return copy(perType = perType.toMutableMap().also { it[type] = enabled })
    }

    fun withMaster(enabled: Boolean): NotificationSettings = copy(masterEnabled = enabled)

    companion object {
        fun defaultPerType(): Map<NotificationType, Boolean> =
            NotificationType.entries.associateWith { true }
    }
}

/**
 * Persistence boundary. The Android binding is backed by DataStore; tests can
 * supply an in-memory implementation.
 */
interface NotificationSettingsStore {
    fun load(): NotificationSettings
    fun save(settings: NotificationSettings)
}

class InMemoryNotificationSettingsStore(
    initial: NotificationSettings = NotificationSettings(),
) : NotificationSettingsStore {
    private var current: NotificationSettings = initial
    override fun load(): NotificationSettings = current
    override fun save(settings: NotificationSettings) {
        current = settings
    }
}
