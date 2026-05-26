package com.aci.hermes.data.notifications

import android.content.Context
import com.aci.hermes.data.JsonStore
import com.aci.hermes.data.model.JarvisNotification
import com.aci.hermes.data.model.JarvisNotificationKind
import kotlinx.coroutines.flow.StateFlow

/**
 * In-app notification center. Distinct from OS notifications — this is
 * the inbox the user opens to triage everything Jarvis Prime wants
 * them to see.
 */
class JarvisNotificationRepository(context: Context) {
    private val store = JsonStore(
        context = context,
        fileName = "jarvis_notifications.json",
        serializer = JarvisNotification.serializer(),
        maxItems = MAX_ITEMS,
    )

    val items: StateFlow<List<JarvisNotification>> = store.items

    suspend fun load() {
        store.load()
    }

    suspend fun add(notification: JarvisNotification) {
        store.add(notification, atStart = true)
    }

    suspend fun add(
        kind: JarvisNotificationKind,
        title: String,
        body: String,
        actionTargetId: String? = null,
    ) {
        add(JarvisNotification(kind = kind, title = title, body = body, actionTargetId = actionTargetId))
    }

    suspend fun markAllRead() {
        store.update({ !it.read }) { it.copy(read = true) }
    }

    suspend fun markRead(id: String) {
        store.update({ it.id == id }) { it.copy(read = true) }
    }

    suspend fun clear() {
        store.clear()
    }

    suspend fun seedIfEmpty(builder: () -> List<JarvisNotification>) {
        store.seedIfEmpty(builder)
    }

    companion object {
        const val MAX_ITEMS = 200
    }
}
