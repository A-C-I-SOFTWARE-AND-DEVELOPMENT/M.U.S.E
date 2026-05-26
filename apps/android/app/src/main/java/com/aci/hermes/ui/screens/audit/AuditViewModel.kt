package com.aci.hermes.ui.screens.audit

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.audit.AuditEntry
import com.aci.hermes.audit.AuditLog
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class AuditUiState(
    val entries: List<AuditEntry> = emptyList(),
)

class AuditViewModel(
    private val audit: AuditLog,
) : ViewModel() {

    private val _state = MutableStateFlow(AuditUiState())
    val state: StateFlow<AuditUiState> = _state.asStateFlow()

    init {
        viewModelScope.launch {
            audit.entries.collect { list ->
                _state.value = AuditUiState(entries = list.asReversed())
            }
        }
    }

    fun exportAsJsonl(): String = audit.exportAsJsonl()
}
