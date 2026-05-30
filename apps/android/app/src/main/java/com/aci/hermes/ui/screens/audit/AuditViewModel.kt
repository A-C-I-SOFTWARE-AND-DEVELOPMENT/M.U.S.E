package com.aci.hermes.ui.screens.audit

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.audit.AuditRepository
import com.aci.hermes.data.model.audit.AuditRecord
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

class AuditViewModel(
    private val repository: AuditRepository,
) : ViewModel() {

    val records: StateFlow<List<AuditRecord>> = repository.records
        .stateIn(
            scope = viewModelScope,
            started = SharingStarted.Eagerly,
            initialValue = repository.records.value,
        )

    init {
        // Pull the live audit list when paired (no-op / mock when not).
        viewModelScope.launch { repository.refresh() }
    }
}
