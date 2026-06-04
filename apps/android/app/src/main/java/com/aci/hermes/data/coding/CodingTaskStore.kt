package com.aci.hermes.data.coding

import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import java.io.File

/**
 * Persists [SavedCodingTask] records to a single JSON file in the app's
 * private storage. Mirrors
 * [com.aci.hermes.data.orchestrator.HermesTaskRepository] (small dataset,
 * `kotlinx.serialization` already on the classpath, no Room) and takes a
 * plain [File] directory so it is unit-tested on the JVM with a temp dir —
 * no Android `Context`, no Robolectric.
 */
class CodingTaskStore(
    dir: File,
    private val scope: CoroutineScope = CoroutineScope(SupervisorJob() + Dispatchers.IO),
    // Injectable so unit tests run disk I/O on a deterministic dispatcher
    // (the test scheduler / Unconfined) instead of the real IO pool.
    private val ioDispatcher: CoroutineDispatcher = Dispatchers.IO,
    /** Load synchronously on construction (deterministic for tests). */
    loadEagerly: Boolean = false,
) {
    private val file = File(dir, FILE_NAME)
    private val mutex = Mutex()

    private val _tasks = MutableStateFlow<List<SavedCodingTask>>(emptyList())
    val tasks: StateFlow<List<SavedCodingTask>> = _tasks.asStateFlow()

    init {
        if (loadEagerly) runBlocking { loadFromDisk() } else scope.launch { loadFromDisk() }
    }

    fun byId(id: String): SavedCodingTask? = _tasks.value.firstOrNull { it.id == id }

    /** Insert or replace a task (newest-first ordering preserved). */
    suspend fun upsert(task: SavedCodingTask): SavedCodingTask = mutex.withLock {
        val now = System.currentTimeMillis()
        val withTime = task.copy(
            createdAt = if (task.createdAt == 0L) now else task.createdAt,
            updatedAt = now,
        )
        val existing = _tasks.value
        val idx = existing.indexOfFirst { it.id == withTime.id }
        val next = if (idx >= 0) {
            existing.toMutableList().also { it[idx] = withTime }
        } else {
            listOf(withTime) + existing
        }
        _tasks.value = next
        writeToDisk(next)
        withTime
    }

    suspend fun delete(id: String) = mutex.withLock {
        val next = _tasks.value.filterNot { it.id == id }
        _tasks.value = next
        writeToDisk(next)
    }

    suspend fun deleteAll() = mutex.withLock {
        _tasks.value = emptyList()
        writeToDisk(emptyList())
    }

    private suspend fun loadFromDisk() = withContext(ioDispatcher) {
        if (!file.exists()) return@withContext
        runCatching {
            val text = file.readText()
            if (text.isBlank()) return@runCatching
            _tasks.value = json.decodeFromString(Envelope.serializer(), text).tasks
        }
    }

    private suspend fun writeToDisk(list: List<SavedCodingTask>) = withContext(ioDispatcher) {
        runCatching {
            val text = json.encodeToString(Envelope.serializer(), Envelope(tasks = list))
            val tmp = File(file.parentFile, "$FILE_NAME.tmp")
            tmp.writeText(text)
            if (!tmp.renameTo(file)) {
                file.writeText(text)
                tmp.delete()
            }
        }
    }

    @Serializable
    private data class Envelope(val version: Int = 1, val tasks: List<SavedCodingTask> = emptyList())

    companion object {
        private const val FILE_NAME = "hermes_coding_tasks.json"
        private val json = Json {
            ignoreUnknownKeys = true
            encodeDefaults = true
            prettyPrint = false
        }
    }
}
