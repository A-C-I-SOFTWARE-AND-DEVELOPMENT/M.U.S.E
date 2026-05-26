package com.aci.hermes.ui.screens.memory

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.audit.AuditRepository
import com.aci.hermes.data.memory.MemoryRepository
import com.aci.hermes.data.model.AuditEvent
import com.aci.hermes.data.model.AuditSeverity
import com.aci.hermes.data.model.MemoryItem
import com.aci.hermes.data.model.MemoryKind
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class MemoryUiState(
    val items: List<MemoryItem> = emptyList(),
    val query: String = "",
)

class MemoryViewModel(
    private val memory: MemoryRepository,
    private val audit: AuditRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(MemoryUiState())
    val state: StateFlow<MemoryUiState> = _state.asStateFlow()

    init {
        viewModelScope.launch {
            memory.items.collect { list -> _state.update { it.copy(items = list) } }
        }
    }

    fun setQuery(value: String) {
        _state.update { it.copy(query = value, items = memory.search(value)) }
    }

    fun remember(content: String, kind: MemoryKind = MemoryKind.FACT) {
        val item = memory.remember(content, kind)
        audit.append(
            AuditEvent(
                actor = "user",
                action = "memory_add",
                target = item.id,
                payloadSummary = item.content.take(120),
                severity = AuditSeverity.INFO,
                proofHash = "",
            )
        )
    }

    fun correct(id: String, newContent: String) {
        val updated = memory.correct(id, newContent) ?: return
        audit.append(
            AuditEvent(
                actor = "user",
                action = "memory_correct",
                target = updated.id,
                payloadSummary = updated.content.take(120),
                severity = AuditSeverity.NOTICE,
                proofHash = "",
            )
        )
    }

    fun forget(id: String) {
        if (memory.forget(id)) {
            audit.append(
                AuditEvent(
                    actor = "user",
                    action = "memory_forget",
                    target = id,
                    payloadSummary = "",
                    severity = AuditSeverity.NOTICE,
                    proofHash = "",
                )
            )
        }
    }
}
