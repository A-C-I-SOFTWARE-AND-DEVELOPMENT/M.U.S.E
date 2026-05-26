package com.aci.hermes.ui.screens.memory

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.audit.AuditRepository
import com.aci.hermes.data.memory.MemoryRepository
import com.aci.hermes.data.model.AuditKind
import com.aci.hermes.data.model.MemoryBranch
import com.aci.hermes.data.model.MemoryFact
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class MemoryUiState(
    val query: String = "",
    val branch: MemoryBranch? = null,
    val facts: List<MemoryFact> = emptyList(),
)

class MemoryViewModel(
    application: Application,
    private val memory: MemoryRepository,
    private val audit: AuditRepository,
) : AndroidViewModel(application) {

    private val _state = MutableStateFlow(MemoryUiState())
    val state: StateFlow<MemoryUiState> = _state.asStateFlow()

    init {
        viewModelScope.launch {
            memory.items.collect { list ->
                _state.update { it.copy(facts = list) }
            }
        }
    }

    fun setBranch(branch: MemoryBranch?) {
        _state.update { it.copy(branch = branch) }
    }

    fun setQuery(text: String) {
        _state.update { it.copy(query = text) }
    }

    fun confirm(fact: MemoryFact) {
        viewModelScope.launch {
            memory.confirm(fact.id)
            audit.record(
                kind = AuditKind.MEMORY_UPDATED,
                title = "Memory confirmed: ${fact.label}",
                detail = "Branch ${fact.branch.name.lowercase()}: ${fact.detail}",
                relatedId = fact.id,
            )
        }
    }

    fun forget(fact: MemoryFact) {
        viewModelScope.launch {
            memory.forget(fact.id)
            audit.record(
                kind = AuditKind.MEMORY_FORGOTTEN,
                title = "Memory forgotten: ${fact.label}",
                detail = "Branch ${fact.branch.name.lowercase()}: ${fact.detail}",
                relatedId = fact.id,
            )
        }
    }

    fun filtered(): List<MemoryFact> {
        val s = _state.value
        return s.facts
            .filter { f -> s.branch == null || f.branch == s.branch }
            .filter { f ->
                if (s.query.isBlank()) true
                else (f.label + " " + f.detail).contains(s.query, ignoreCase = true)
            }
    }
}
