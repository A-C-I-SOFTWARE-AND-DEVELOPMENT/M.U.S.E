package com.aci.hermes.data.memory

import android.content.Context
import com.aci.hermes.data.JsonStore
import com.aci.hermes.data.model.MemoryBranch
import com.aci.hermes.data.model.MemoryConfidence
import com.aci.hermes.data.model.MemoryFact
import kotlinx.coroutines.flow.StateFlow

/**
 * Memory Tree — visible memory store.
 *
 * Everything Jarvis Prime remembers about the user is surfaced here.
 * Inferences are clearly marked. The user can confirm, reject, or
 * forget any fact. No facts ever leave the device.
 */
class MemoryRepository(context: Context) {
    private val store = JsonStore(
        context = context,
        fileName = "jarvis_memory.json",
        serializer = MemoryFact.serializer(),
        maxItems = MAX_ITEMS,
    )

    val items: StateFlow<List<MemoryFact>> = store.items

    suspend fun load() {
        store.load()
    }

    suspend fun add(fact: MemoryFact) {
        store.add(fact, atStart = false)
    }

    suspend fun confirm(id: String) {
        store.update({ it.id == id }) {
            it.copy(confidence = MemoryConfidence.CONFIRMED, updatedAt = System.currentTimeMillis())
        }
    }

    suspend fun reject(id: String) {
        store.update({ it.id == id }) {
            it.copy(confidence = MemoryConfidence.REJECTED, updatedAt = System.currentTimeMillis())
        }
    }

    suspend fun forget(id: String) {
        store.remove { it.id == id }
    }

    suspend fun seedIfEmpty(builder: () -> List<MemoryFact>) {
        store.seedIfEmpty(builder)
    }

    suspend fun clear() {
        store.clear()
    }

    fun byBranch(branch: MemoryBranch): List<MemoryFact> =
        store.items.value.filter { it.branch == branch }

    companion object {
        const val MAX_ITEMS = 1000
    }
}
