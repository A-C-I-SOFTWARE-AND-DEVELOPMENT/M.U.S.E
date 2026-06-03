package com.aci.hermes.data.devicecontrol

import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import java.io.File

/**
 * Append-only, local-only ledger of every device action JARVIS Prime
 * took (or was refused). Survives process death so "what did Jarvis do
 * on my phone?" is always answerable.
 *
 * Storage mirrors [com.aci.hermes.data.emergency.EmergencyStopRepository]:
 * a single JSON file in the app's filesDir, atomically replaced on every
 * append, trimmed to [DeviceActionLogEntry.MAX_ENTRIES].
 */
class DeviceActionLedger(
    private val baseDir: File,
    private val io: CoroutineDispatcher = Dispatchers.IO,
) {

    private val file: File = File(baseDir, FILE_NAME)
    private val mutex = Mutex()

    private val _entries = MutableStateFlow<List<DeviceActionLogEntry>>(emptyList())
    val entries: StateFlow<List<DeviceActionLogEntry>> = _entries.asStateFlow()

    suspend fun load() = mutex.withLock {
        _entries.value = readSnapshot().entries
    }

    /** Append [entry], trim to the bound, and persist atomically. */
    suspend fun record(entry: DeviceActionLogEntry) = mutex.withLock {
        _entries.value = (_entries.value + entry).takeLast(DeviceActionLogEntry.MAX_ENTRIES)
        persistLocked()
    }

    /** Synchronous JSON snapshot, for an export action. */
    fun snapshotJson(): String =
        json.encodeToString(Snapshot.serializer(), Snapshot(version = 1, entries = _entries.value))

    private suspend fun persistLocked() = withContext(io) {
        val snapshot = Snapshot(version = 1, entries = _entries.value)
        runCatching {
            if (!baseDir.exists()) baseDir.mkdirs()
            val text = json.encodeToString(Snapshot.serializer(), snapshot)
            val tmp = File(baseDir, "$FILE_NAME.tmp")
            tmp.writeText(text)
            if (!tmp.renameTo(file)) {
                file.writeText(text)
                tmp.delete()
            }
        }
    }

    private suspend fun readSnapshot(): Snapshot = withContext(io) {
        if (!file.exists()) return@withContext Snapshot()
        runCatching {
            val text = file.readText()
            if (text.isBlank()) return@runCatching Snapshot()
            json.decodeFromString(Snapshot.serializer(), text)
        }.getOrElse { Snapshot() }
    }

    @Serializable
    data class Snapshot(
        val version: Int = 1,
        val entries: List<DeviceActionLogEntry> = emptyList(),
    )

    companion object {
        const val FILE_NAME = "jarvis_device_actions.json"
        private val json = Json {
            ignoreUnknownKeys = true
            encodeDefaults = true
            prettyPrint = false
        }
    }
}
