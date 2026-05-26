package com.jarvisprime.notifications.platform

import com.jarvisprime.notifications.NotificationEvent

/**
 * Platform abstraction for app navigation. The Android binding is a thin wrapper
 * around the NavController that launches the right intent or composable destination
 * for the requested screen.
 */
interface Navigator {
    fun navigateTo(target: NavigationTarget, event: NotificationEvent?)
}
