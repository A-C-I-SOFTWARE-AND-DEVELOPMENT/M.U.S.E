package com.aci.hermes.data.memory

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json

private val Context.memoryDataStore: DataStore<Preferences> by preferencesDataStore(name = "jarvis_memory_v1")

/**
 * Owns the Jarvis Prime Memory Tree state.
 *
 * Pure local — no cloud. The tree is persisted as a JSON string in
 * DataStore. In-memory writes go through [MutableStateFlow] so any
 * Compose surface observing [tree] re-renders synchronously after a
 * mutation, without waiting on the IO write to finish.
 */
class MemoryRepository(
    private val context: Context,
    private val scope: CoroutineScope = CoroutineScope(SupervisorJob() + Dispatchers.IO),
    private val seed: MemoryTree = defaultSeed(),
) {
    private val json = Json { ignoreUnknownKeys = true; prettyPrint = false }

    private val _tree = MutableStateFlow(seed)
    val tree: StateFlow<MemoryTree> = _tree.asStateFlow()

    private val key = stringPreferencesKey("memory_tree_json")

    init {
        scope.launch { hydrate() }
    }

    private suspend fun hydrate() {
        val raw = context.memoryDataStore.data.first()[key]
        if (raw.isNullOrBlank()) return
        runCatching { json.decodeFromString<MemoryTree>(raw) }
            .onSuccess { stored -> if (stored.size > 0) _tree.value = stored }
    }

    fun remember(node: MemoryNode): MemoryNode {
        val updated = _tree.value.upsert(node)
        _tree.value = updated
        persist(updated)
        return updated.get(node.id)!!
    }

    fun forget(id: String) {
        val updated = _tree.value.forget(id)
        _tree.value = updated
        persist(updated)
    }

    private fun persist(snapshot: MemoryTree) {
        scope.launch {
            val raw = json.encodeToString(snapshot)
            context.memoryDataStore.edit { it[key] = raw }
        }
    }

    companion object {
        /**
         * Seed nodes shown when Jarvis Prime launches for the first
         * time. Two roots make the Memory Tree intelligible before the
         * owner has any real history.
         */
        fun defaultSeed(): MemoryTree {
            val ownerNode = MemoryNode(
                topic = "Owner",
                body = "Anything Jarvis Prime learns about you lives under this branch.",
                tags = listOf("owner"),
                pinned = true,
            )
            val workNode = MemoryNode(
                topic = "Work in flight",
                body = "Active tasks, repositories, and deadlines.",
                tags = listOf("work"),
                pinned = true,
            )
            return MemoryTree(
                nodes = mapOf(ownerNode.id to ownerNode, workNode.id to workNode),
            )
        }
    }
}
