package com.aci.hermes.data.social

import android.content.Context
import com.aci.hermes.data.JsonStore
import com.aci.hermes.data.model.SocialPattern
import kotlinx.coroutines.flow.StateFlow

/**
 * Social Intelligence — surfaces patterns Jarvis Prime is noticing
 * across recent conversations. Read-only for the user except for
 * acknowledge / dismiss.
 */
class SocialPatternRepository(context: Context) {
    private val store = JsonStore(
        context = context,
        fileName = "jarvis_social.json",
        serializer = SocialPattern.serializer(),
        maxItems = MAX_ITEMS,
    )

    val items: StateFlow<List<SocialPattern>> = store.items

    suspend fun load() {
        store.load()
    }

    suspend fun acknowledge(id: String) {
        store.update({ it.id == id }) { it.copy(acknowledged = true) }
    }

    suspend fun dismiss(id: String) {
        store.update({ it.id == id }) { it.copy(dismissed = true) }
    }

    suspend fun seedIfEmpty(builder: () -> List<SocialPattern>) {
        store.seedIfEmpty(builder)
    }

    suspend fun clear() {
        store.clear()
    }

    companion object {
        const val MAX_ITEMS = 200
    }
}
