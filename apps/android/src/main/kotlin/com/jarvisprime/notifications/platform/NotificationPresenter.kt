package com.jarvisprime.notifications.platform

import com.jarvisprime.notifications.NotificationAction
import com.jarvisprime.notifications.NotificationEvent

data class PresentationSpec(
    val event: NotificationEvent,
    val channelId: String,
    val priority: Priority,
    val actions: List<NotificationAction>,
    val target: NavigationTarget,
)

enum class Priority { LOW, DEFAULT, HIGH, MAX }

/**
 * Platform abstraction for posting a system notification. The Android binding
 * builds a NotificationCompat.Builder, attaches PendingIntents for each action,
 * and posts via NotificationManagerCompat.
 */
interface NotificationPresenter {
    fun present(spec: PresentationSpec)
    fun cancel(id: String)
}
