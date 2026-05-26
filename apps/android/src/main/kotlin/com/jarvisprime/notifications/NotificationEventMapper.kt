package com.jarvisprime.notifications

import com.jarvisprime.notifications.platform.NavigationTarget
import com.jarvisprime.notifications.platform.Priority

/**
 * Maps a [NotificationType] to its presentation spec: the channel it lives on,
 * the priority it deserves, the screen it should open, and the actions the
 * user is allowed to take inline.
 *
 * Centralising this mapping means routing and presentation can never disagree:
 * if a notification arrives, [NotificationActionRouter] handles its actions
 * using the same target this mapper declares.
 */
class NotificationEventMapper {

    fun channelId(type: NotificationType): String = when (type) {
        NotificationType.APPROVAL_NEEDED,
        NotificationType.SERIOUS_ACTION_PENDING,
        NotificationType.CRITICAL_ACTION_PENDING -> CHANNEL_APPROVALS
        NotificationType.TASK_COMPLETE -> CHANNEL_TASKS
        NotificationType.WORKER_FAILED,
        NotificationType.GATEWAY_DISCONNECTED -> CHANNEL_SYSTEM
        NotificationType.EMERGENCY_STOP_ACTIVE -> CHANNEL_EMERGENCY
        NotificationType.MEMORY_CORRECTED -> CHANNEL_MEMORY
    }

    fun priority(type: NotificationType): Priority = when (type) {
        NotificationType.CRITICAL_ACTION_PENDING,
        NotificationType.EMERGENCY_STOP_ACTIVE -> Priority.MAX
        NotificationType.APPROVAL_NEEDED,
        NotificationType.SERIOUS_ACTION_PENDING,
        NotificationType.WORKER_FAILED,
        NotificationType.GATEWAY_DISCONNECTED -> Priority.HIGH
        NotificationType.TASK_COMPLETE -> Priority.DEFAULT
        NotificationType.MEMORY_CORRECTED -> Priority.LOW
    }

    fun target(type: NotificationType): NavigationTarget = when (type) {
        NotificationType.APPROVAL_NEEDED,
        NotificationType.SERIOUS_ACTION_PENDING,
        NotificationType.CRITICAL_ACTION_PENDING -> NavigationTarget.APPROVALS
        NotificationType.TASK_COMPLETE,
        NotificationType.WORKER_FAILED -> NavigationTarget.TASKS
        NotificationType.GATEWAY_DISCONNECTED -> NavigationTarget.GATEWAY_STATUS
        NotificationType.EMERGENCY_STOP_ACTIVE -> NavigationTarget.EMERGENCY_STOP
        NotificationType.MEMORY_CORRECTED -> NavigationTarget.MEMORY_LOG
    }

    fun actions(type: NotificationType): List<NotificationAction> = when (type) {
        NotificationType.APPROVAL_NEEDED ->
            listOf(NotificationAction.OPEN_APPROVAL, NotificationAction.DISMISS)
        NotificationType.SERIOUS_ACTION_PENDING ->
            listOf(NotificationAction.OPEN_APPROVAL, NotificationAction.OPEN_AUDIT, NotificationAction.DISMISS)
        NotificationType.CRITICAL_ACTION_PENDING ->
            listOf(
                NotificationAction.OPEN_APPROVAL,
                NotificationAction.OPEN_AUDIT,
                NotificationAction.EMERGENCY_STOP,
            )
        NotificationType.TASK_COMPLETE ->
            listOf(NotificationAction.OPEN_TASK, NotificationAction.DISMISS)
        NotificationType.WORKER_FAILED ->
            listOf(NotificationAction.OPEN_TASK, NotificationAction.OPEN_AUDIT, NotificationAction.DISMISS)
        NotificationType.GATEWAY_DISCONNECTED ->
            listOf(NotificationAction.OPEN_AUDIT, NotificationAction.DISMISS)
        NotificationType.EMERGENCY_STOP_ACTIVE ->
            listOf(NotificationAction.OPEN_AUDIT, NotificationAction.DISMISS)
        NotificationType.MEMORY_CORRECTED ->
            listOf(NotificationAction.OPEN_AUDIT, NotificationAction.DISMISS)
    }

    companion object {
        const val CHANNEL_APPROVALS = "jarvis_approvals"
        const val CHANNEL_TASKS = "jarvis_tasks"
        const val CHANNEL_SYSTEM = "jarvis_system"
        const val CHANNEL_EMERGENCY = "jarvis_emergency"
        const val CHANNEL_MEMORY = "jarvis_memory"
    }
}
