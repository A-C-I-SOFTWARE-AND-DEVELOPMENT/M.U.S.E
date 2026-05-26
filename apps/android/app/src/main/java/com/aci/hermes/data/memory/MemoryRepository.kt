package com.aci.hermes.data.memory

import com.aci.hermes.data.model.MemoryItem
import com.aci.hermes.data.model.MemoryKind
import com.aci.hermes.data.redaction.Redactor
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * In-memory memory store. Personal information is redacted on the way
 * in — the raw form never sits at rest in [items]. The audit ledger is
 * the only place a correction is recorded by reference.
 */
class MemoryRepository {

    private val _items = MutableStateFlow<List<MemoryItem>>(emptyList())
    val items: StateFlow<List<MemoryItem>> = _items.asStateFlow()

    fun remember(content: String, kind: MemoryKind = MemoryKind.FACT, source: String = "user"): MemoryItem {
        val (text, redactedFields) = Redactor.redact(content).let { it.text to it.redactedFields }
        val item = MemoryItem(
            kind = kind,
            content = text,
            source = source,
            redactedFields = redactedFields,
        )
        _items.value = listOf(item) + _items.value
        return item
    }

    fun correct(id: String, newContent: String): MemoryItem? {
        val list = _items.value
        val idx = list.indexOfFirst { it.id == id }
        if (idx < 0) return null
        val (text, fields) = Redactor.redact(newContent).let { it.text to it.redactedFields }
        val updated = list[idx].copy(
            content = text,
            updatedAt = System.currentTimeMillis(),
            redactedFields = fields,
        )
        val next = list.toMutableList().also { it[idx] = updated }
        _items.value = next
        return updated
    }

    fun forget(id: String): Boolean {
        val before = _items.value
        val after = before.filterNot { it.id == id }
        _items.value = after
        return after.size != before.size
    }

    fun clear() { _items.value = emptyList() }

    fun search(query: String): List<MemoryItem> {
        if (query.isBlank()) return _items.value
        val q = query.trim().lowercase()
        return _items.value.filter { it.content.lowercase().contains(q) }
    }
}
