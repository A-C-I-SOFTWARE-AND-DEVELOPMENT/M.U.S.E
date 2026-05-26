package com.aci.hermes.data.audit

import android.content.Context
import com.aci.hermes.data.JsonStore
import com.aci.hermes.data.model.AuditEntry
import com.aci.hermes.data.model.AuditKind
import kotlinx.coroutines.flow.StateFlow

/**
 * Proof Engine — append-only history of every meaningful action.
 *
 * Every entry carries a short proof ID so the user can reference it
 * later. The log is local-only.
 */
class AuditRepository(context: Context) {
    private val store = JsonStore(
        context = context,
        fileName = "jarvis_audit.json",
        serializer = AuditEntry.serializer(),
        maxItems = MAX_ITEMS,
    )

    val items: StateFlow<List<AuditEntry>> = store.items

    suspend fun load() {
        store.load()
    }

    suspend fun record(
        kind: AuditKind,
        title: String,
        detail: String,
        relatedId: String? = null,
    ): AuditEntry {
        val entry = AuditEntry(
            kind = kind,
            title = title,
            detail = detail,
            relatedId = relatedId,
        )
        store.add(entry, atStart = true)
        return entry
    }

    suspend fun seedIfEmpty(builder: () -> List<AuditEntry>) {
        store.seedIfEmpty(builder)
    }

    suspend fun clear() {
        store.clear()
    }

    /** Serialize the audit log as a Markdown proof bundle. */
    fun exportMarkdown(): String {
        val list = store.items.value
        if (list.isEmpty()) return "# Jarvis Prime audit log\n\n_No entries._\n"
        val sb = StringBuilder()
        sb.appendLine("# Jarvis Prime audit log")
        sb.appendLine()
        sb.appendLine("Exported: ${java.time.Instant.now()}")
        sb.appendLine()
        for (entry in list) {
            sb.appendLine("## ${entry.title}")
            sb.appendLine()
            sb.appendLine("- Proof ID: `${entry.proofId}`")
            sb.appendLine("- Kind: `${entry.kind.name.lowercase()}`")
            sb.appendLine("- Timestamp: ${java.time.Instant.ofEpochMilli(entry.createdAt)}")
            if (entry.relatedId != null) sb.appendLine("- Related: `${entry.relatedId}`")
            sb.appendLine()
            sb.appendLine(entry.detail)
            sb.appendLine()
        }
        return sb.toString()
    }

    companion object {
        const val MAX_ITEMS = 1000
    }
}
