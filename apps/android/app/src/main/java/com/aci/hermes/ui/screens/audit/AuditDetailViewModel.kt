package com.aci.hermes.ui.screens.audit

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.audit.AuditRepository
import com.aci.hermes.data.model.audit.AuditRecord
import com.aci.hermes.data.model.audit.ProofRecord
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.launch

data class AuditDetailUiState(
    val record: AuditRecord? = null,
    val proof: ProofRecord? = null,
    val notFound: Boolean = false,
)

class AuditDetailViewModel(
    private val repository: AuditRepository,
    private val auditId: String,
) : ViewModel() {

    private val _state = MutableStateFlow(AuditDetailUiState())
    val state: StateFlow<AuditDetailUiState> = _state.asStateFlow()

    init {
        viewModelScope.launch {
            repository.records
                .combine(repository.proofFor(auditId)) { records, proof ->
                    val record = records.firstOrNull { it.id == auditId }
                    AuditDetailUiState(
                        record = record,
                        proof = proof,
                        notFound = record == null,
                    )
                }
                .collect { _state.value = it }
        }
    }
}
