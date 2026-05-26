package com.jarvisprime.notifications

data class NotificationEvent(
    val id: String,
    val type: NotificationType,
    val title: String,
    val body: String,
    val payload: Map<String, String> = emptyMap(),
    val timestamp: Long = 0L,
)
