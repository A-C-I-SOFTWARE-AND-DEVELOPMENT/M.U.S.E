package com.aci.hermes.data.orchestrator

import android.content.Context
import com.aci.hermes.data.model.HermesTask
import com.aci.hermes.data.model.TaskStatus
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import kotlinx.serialization.Serializable
import kotlinx.serialization.builtins.ListSerializer
import kotlinx.serialization.json.Json
import java.io.File

/**
 * Persists [HermesTask] state to a single JSON file in the app's
 * private filesDir. Chosen over Room to keep the build minimal — the
 * dataset is small, and `kotlinx.serialization.json` is already on the
 * classpath.
 *
 * [baseDir] is the directory the backing JSON file lives in. It defaults to
 * `context.filesDir`, so production construction (`HermesTaskRepository(context)`)
 * is byte-for-byte unchanged. The parameter exists purely as a test seam:
 * under Robolectric the per-sandbox `filesDir` is recycled at test boundaries,
 * and the disk load this repo kicks off in `init { scope.launch { loadFromDisk() } }`
 * runs on `Dispatchers.IO`. A lagging actor reading a since-deleted `filesDir`
 * is a classic TOCTOU and surfaces as a bare `FileNotFoundException`. Pointing
 * [baseDir] at a JVM-stable temp dir (see `testutil.isolatedTaskRepository` in
 * the test source set) outlives every sandbox, so the file is always present
 * for both the test's own reads and any lagging actor.
 */
class HermesTaskRepository(
    context: Context,
    baseDir: File = context.filesDir,
) {

    private val file = File(baseDir, FILE_NAME)
    private val mutex = Mutex()
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    private val _tasks = MutableStateFlow<List<HermesTask>>(emptyList())
    val tasks: StateFlow<List<HermesTask>> = _tasks.asStateFlow()

    init {
        scope.launch { loadFromDisk() }
    }

    suspend fun upsert(task: HermesTask): HermesTask = mutex.withLock {
        val now = System.currentTimeMillis()
        val updated = task.copy(updatedAt = now)
        val existing = _tasks.value
        val idx = existing.indexOfFirst { it.id == updated.id }
        val next = if (idx >= 0) {
            existing.toMutableList().also { it[idx] = updated }
        } else {
            listOf(updated) + existing
        }
        _tasks.value = next
        writeToDisk(next)
        updated
    }

    suspend fun setStatus(id: String, status: TaskStatus) = mutex.withLock {
        val existing = _tasks.value
        val idx = existing.indexOfFirst { it.id == id }
        if (idx < 0) return@withLock
        val updated = existing[idx].copy(status = status, updatedAt = System.currentTimeMillis())
        val next = existing.toMutableList().also { it[idx] = updated }
        _tasks.value = next
        writeToDisk(next)
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

    fun byId(id: String): HermesTask? = _tasks.value.firstOrNull { it.id == id }

    private suspend fun loadFromDisk() = withContext(Dispatchers.IO) {
        // The whole read — existence check, open, and decode — sits inside one
        // runCatching so a concurrent delete between `exists()` and `readText()`
        // (a TOCTOU; e.g. Robolectric recycling filesDir while this IO-dispatched
        // load is still draining) is swallowed rather than escaping as a bare
        // FileNotFoundException. A missing or unreadable file simply leaves the
        // in-memory state empty, which is the correct first-run behavior.
        runCatching {
            if (!file.exists()) return@runCatching
            val text = file.readText()
            if (text.isBlank()) return@runCatching
            val envelope = json.decodeFromString(Envelope.serializer(), text)
            _tasks.value = envelope.tasks
        }
    }

    private suspend fun writeToDisk(list: List<HermesTask>) = withContext(Dispatchers.IO) {
        runCatching {
            val envelope = Envelope(version = 1, tasks = list)
            val text = json.encodeToString(Envelope.serializer(), envelope)
            val tmp = File(file.parentFile, "$FILE_NAME.tmp")
            tmp.writeText(text)
            if (!tmp.renameTo(file)) {
                // Fallback if rename fails on some FS — overwrite directly.
                file.writeText(text)
                tmp.delete()
            }
        }
    }

    @Serializable
    private data class Envelope(val version: Int = 1, val tasks: List<HermesTask> = emptyList())

    companion object {
        private const val FILE_NAME = "hermes_tasks.json"
        private val json = Json {
            ignoreUnknownKeys = true
            encodeDefaults = true
            prettyPrint = false
        }

        /** Exposed for tests / advanced uses. */
        @Suppress("unused")
        fun listSerializer() = ListSerializer(HermesTask.serializer())
    }
}
