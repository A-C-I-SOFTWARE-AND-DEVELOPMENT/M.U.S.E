package com.aci.hermes.ui.screens.audit

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.audit.AuditRepository
import com.aci.hermes.data.model.AuditEvent
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class AuditUiState(val events: List<AuditEvent> = emptyList())

class AuditViewModel(private val audit: AuditRepository) : ViewModel() {
    private val _state = MutableStateFlow(AuditUiState())
    val state: StateFlow<AuditUiState> = _state.asStateFlow()
    init {
        viewModelScope.launch {
            audit.events.collect { list -> _state.update { it.copy(events = list) } }
        }
    }
    fun byId(id: String): AuditEvent? = audit.byId(id)
}

class AuditDetailViewModel(
    private val auditId: String,
    private val audit: AuditRepository,
) : ViewModel() {
    val event: AuditEvent? get() = audit.byId(auditId)
}
