package com.jarvisprime.notifications

import com.jarvisprime.notifications.platform.Clock

/**
 * Suppresses duplicate notifications fired in a short window.
 *
 * Duplicates are identified by (type, dedupeKey) where dedupeKey defaults to
 * the event id but can be overridden via the `dedupeKey` payload entry. This
 * lets a worker emit progressive updates that collapse into a single notification
 * instead of stacking three identical "task complete" alerts.
 *
 * EMERGENCY_STOP_ACTIVE bypasses the guard — we never silence a safety event.
 */
class NotificationSpamGuard(
    private val clock: Clock,
    private val windowMillis: Long = DEFAULT_WINDOW_MILLIS,
) {

    private val lastSeen = mutableMapOf<Key, Long>()

    fun allow(event: NotificationEvent): Boolean {
        if (event.type == NotificationType.EMERGENCY_STOP_ACTIVE) return true
        val key = Key(event.type, event.payload["dedupeKey"] ?: event.id)
        val now = clock.nowMillis()
        val last = lastSeen[key]
        if (last != null && (now - last) < windowMillis) {
            return false
        }
        lastSeen[key] = now
        return true
    }

    fun reset() {
        lastSeen.clear()
    }

    private data class Key(val type: NotificationType, val dedupe: String)

    companion object {
        const val DEFAULT_WINDOW_MILLIS = 30_000L
    }
}
