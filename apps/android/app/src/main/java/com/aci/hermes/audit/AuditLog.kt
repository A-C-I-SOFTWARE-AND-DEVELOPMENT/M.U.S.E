package com.aci.hermes.audit

import android.content.Context
import com.aci.hermes.events.EventSpine
import com.aci.hermes.events.JarvisEvent
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import java.io.File

/**
 * Append-only, persisted audit log for Jarvis Prime.
 *
 * Backing file is `<filesDir>/jarvis_audit/audit.jsonl` — newline-
 * delimited JSON, one [AuditEntry] per line. The log subscribes to the
 * [EventSpine] at construction and forwards every event into a row,
 * so every Jarvis Prime subsystem gets durable recording without
 * needing to know about this module.
 *
 * On startup the existing file is replayed into the in-memory list so
 * the Audit screen can render history without any other module
 * touching the file.
 */
class AuditLog(
    context: Context,
    private val spine: EventSpine,
    private val scope: CoroutineScope = CoroutineScope(SupervisorJob() + Dispatchers.IO),
) {
    private val json = Json { ignoreUnknownKeys = true }
    private val dir = File(context.filesDir, AUDIT_DIR).apply { mkdirs() }
    private val file = File(dir, AUDIT_FILE)
    private var lastEventCount = 0

    private val _entries = MutableStateFlow<List<AuditEntry>>(emptyList())
    val entries: StateFlow<List<AuditEntry>> = _entries.asStateFlow()

    init {
        scope.launch { replay() }
        scope.launch {
            spine.events.collect { events ->
                val newOnes = events.drop(lastEventCount)
                if (newOnes.isNotEmpty()) {
                    lastEventCount = events.size
                    newOnes.forEach { recordEvent(it) }
                }
            }
        }
    }

    /**
     * Persist an event-derived entry. Public so subsystems can attach
     * a [proofSnapshot] when they know one — for approvals this is the
     * full Proof Engine render the owner saw at decision time.
     */
    fun record(entry: AuditEntry) {
        _entries.update { it + entry }
        scope.launch { file.appendText(json.encodeToString(entry) + "\n") }
    }

    private fun recordEvent(event: JarvisEvent) {
        record(AuditEntry.fromEvent(event))
    }

    private suspend fun replay() {
        if (!file.exists()) return
        val parsed = runCatching {
            file.readLines().mapNotNull { line ->
                if (line.isBlank()) null
                else runCatching { json.decodeFromString<AuditEntry>(line) }.getOrNull()
            }
        }.getOrDefault(emptyList())
        if (parsed.isNotEmpty()) _entries.update { parsed }
    }

    /**
     * Render the full log as a single export string (newline-delimited
     * JSON). Used by the Audit screen's Export action.
     */
    fun exportAsJsonl(): String = entries.value.joinToString("\n") { json.encodeToString(it) }

    companion object {
        const val AUDIT_DIR = "jarvis_audit"
        const val AUDIT_FILE = "audit.jsonl"
    }
}
