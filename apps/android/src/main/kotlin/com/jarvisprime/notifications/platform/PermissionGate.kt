package com.jarvisprime.notifications.platform

enum class PermissionState {
    GRANTED,
    DENIED,
    NOT_DETERMINED,
}

/**
 * Platform abstraction for the OS notification permission. On Android 13+
 * this maps to POST_NOTIFICATIONS. On earlier versions the permission is
 * implicit and the gate reports GRANTED unless the user has disabled
 * notifications for the app in system settings.
 */
interface PermissionGate {
    fun currentState(): PermissionState

    /**
     * Triggers the OS permission prompt. Implementations MUST NOT call this
     * directly on first launch — the [NotificationPermissionEducation] flow
     * is the only authorised caller.
     */
    fun requestPermission(onResult: (PermissionState) -> Unit)
}
