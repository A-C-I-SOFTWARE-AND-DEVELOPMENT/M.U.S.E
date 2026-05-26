package com.aci.hermes.data

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import kotlinx.serialization.KSerializer
import kotlinx.serialization.builtins.ListSerializer
import kotlinx.serialization.json.Json
import java.io.File

/**
 * Tiny JSON-backed repository helper. Holds a list of [T] in a
 * [StateFlow], persists to a JSON file under the app's filesDir, and
 * coalesces writes under a single mutex so concurrent writers cannot
 * corrupt the file.
 *
 * Used by all the new Jarvis Prime data modules (chat, approvals,
 * memory, audit, social, gateway events, notifications). The dataset
 * is small and bounded by user lifetime — Room would be overkill.
 */
class JsonStore<T>(
    context: Context,
    fileName: String,
    private val serializer: KSerializer<T>,
    initial: List<T> = emptyList(),
    /** Hard cap; null = no cap. Older entries get dropped first. */
    private val maxItems: Int? = null,
) {

    private val file: File = File(context.filesDir, fileName)
    private val mutex = Mutex()

    private val _items = MutableStateFlow(initial)
    val items: StateFlow<List<T>> = _items.asStateFlow()

    private val listSerializer = ListSerializer(serializer)

    suspend fun load(): List<T> = withContext(Dispatchers.IO) {
        mutex.withLock {
            if (!file.exists()) return@withLock emptyList<T>()
            runCatching {
                val text = file.readText()
                if (text.isBlank()) emptyList()
                else json.decodeFromString(listSerializer, text)
            }.getOrDefault(emptyList()).also { _items.value = it }
        }
    }

    suspend fun replace(items: List<T>) = mutex.withLock {
        val capped = if (maxItems != null && items.size > maxItems) {
            items.takeLast(maxItems)
        } else items
        _items.value = capped
        persist(capped)
    }

    suspend fun add(item: T, atStart: Boolean = true) = mutex.withLock {
        val combined = if (atStart) listOf(item) + _items.value else _items.value + item
        val capped = if (maxItems != null && combined.size > maxItems) {
            if (atStart) combined.take(maxItems) else combined.takeLast(maxItems)
        } else combined
        _items.value = capped
        persist(capped)
    }

    suspend fun update(predicate: (T) -> Boolean, transform: (T) -> T) = mutex.withLock {
        var changed = false
        val next = _items.value.map { item ->
            if (predicate(item)) {
                changed = true
                transform(item)
            } else item
        }
        if (changed) {
            _items.value = next
            persist(next)
        }
    }

    suspend fun remove(predicate: (T) -> Boolean) = mutex.withLock {
        val next = _items.value.filterNot(predicate)
        if (next.size != _items.value.size) {
            _items.value = next
            persist(next)
        }
    }

    suspend fun clear() = mutex.withLock {
        _items.value = emptyList()
        persist(emptyList())
    }

    /** Seed the store only if it has never been written. */
    suspend fun seedIfEmpty(builder: () -> List<T>) = mutex.withLock {
        if (file.exists() && _items.value.isNotEmpty()) return@withLock
        val seeded = builder()
        _items.value = seeded
        persist(seeded)
    }

    private suspend fun persist(list: List<T>) = withContext(Dispatchers.IO) {
        runCatching {
            val text = json.encodeToString(listSerializer, list)
            val tmp = File(file.parentFile, "${file.name}.tmp")
            tmp.writeText(text)
            if (!tmp.renameTo(file)) {
                file.writeText(text)
                tmp.delete()
            }
        }
    }

    companion object {
        val json = Json {
            ignoreUnknownKeys = true
            encodeDefaults = true
            prettyPrint = false
        }
    }
}
