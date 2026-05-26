package com.aci.hermes.data.emergency

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
 * Persists [EmergencyStopState] and a bounded audit log of transitions.
 *
 * State survives process death and is re-loaded on app start so that the
 * gate stays engaged across restarts — a hard stop / lockdown that's
 * easily forgotten across a reboot is not really a stop.
 *
 * Storage: a single JSON file in the app's filesDir, atomically replaced
 * on every mutation.
 */
class EmergencyStopRepository(
    private val baseDir: File,
    private val io: CoroutineDispatcher = Dispatchers.IO,
) {

    private val file: File = File(baseDir, FILE_NAME)
    private val mutex = Mutex()

    private val _state = MutableStateFlow(EmergencyStopState.INACTIVE)
    val state: StateFlow<EmergencyStopState> = _state.asStateFlow()

    private val _audit = MutableStateFlow<List<EmergencyStopAuditEvent>>(emptyList())
    val audit: StateFlow<List<EmergencyStopAuditEvent>> = _audit.asStateFlow()

    private val _pendingApproval = MutableStateFlow<ResumeApproval?>(null)
    val pendingApproval: StateFlow<ResumeApproval?> = _pendingApproval.asStateFlow()

    suspend fun load() = mutex.withLock {
        val snapshot = readSnapshot()
        _state.value = snapshot.state
        _audit.value = snapshot.audit
        _pendingApproval.value = snapshot.pendingApproval
    }

    suspend fun replaceState(next: EmergencyStopState) = mutex.withLock {
        _state.value = next
        persistLocked()
    }

    suspend fun appendAudit(event: EmergencyStopAuditEvent) = mutex.withLock {
        val trimmed = (_audit.value + event).takeLast(EmergencyStopAuditEvent.MAX_AUDIT_ENTRIES)
        _audit.value = trimmed
        persistLocked()
    }

    suspend fun setPendingApproval(approval: ResumeApproval?) = mutex.withLock {
        _pendingApproval.value = approval
        persistLocked()
    }

    /**
     * Combined atomic write — used when a single transition needs to
     * update state, audit, and approval in one logical commit.
     */
    suspend fun commit(
        state: EmergencyStopState? = null,
        event: EmergencyStopAuditEvent? = null,
        pendingApproval: ResumeApproval? = null,
        clearApproval: Boolean = false,
    ) = mutex.withLock {
        if (state != null) _state.value = state
        if (event != null) {
            val trimmed = (_audit.value + event).takeLast(EmergencyStopAuditEvent.MAX_AUDIT_ENTRIES)
            _audit.value = trimmed
        }
        if (clearApproval) {
            _pendingApproval.value = null
        } else if (pendingApproval != null) {
            _pendingApproval.value = pendingApproval
        }
        persistLocked()
    }

    /** Synchronous read used by audit export. */
    fun snapshotJson(): String {
        val snapshot = Snapshot(
            version = 1,
            state = _state.value,
            audit = _audit.value,
            pendingApproval = _pendingApproval.value,
        )
        return json.encodeToString(Snapshot.serializer(), snapshot)
    }

    private suspend fun persistLocked() = withContext(io) {
        val snapshot = Snapshot(
            version = 1,
            state = _state.value,
            audit = _audit.value,
            pendingApproval = _pendingApproval.value,
        )
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
        val state: EmergencyStopState = EmergencyStopState.INACTIVE,
        val audit: List<EmergencyStopAuditEvent> = emptyList(),
        val pendingApproval: ResumeApproval? = null,
    )

    companion object {
        const val FILE_NAME = "jarvis_emergency_stop.json"
        private val json = Json {
            ignoreUnknownKeys = true
            encodeDefaults = true
            prettyPrint = false
        }
    }
}
