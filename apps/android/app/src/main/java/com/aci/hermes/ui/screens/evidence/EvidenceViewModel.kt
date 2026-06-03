package com.aci.hermes.ui.screens.evidence

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.evidence.EvidenceItem
import com.aci.hermes.data.evidence.EvidenceRepository
import com.aci.hermes.data.evidence.EvidenceSync
import com.aci.hermes.data.evidence.EvidenceVerification
import com.aci.hermes.data.evidence.PromoteOutcome
import com.aci.hermes.util.LogBuffer
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class EvidenceUiState(
    val query: String = "",
    val items: List<EvidenceItem> = emptyList(),
    val selected: EvidenceItem? = null,
    val verification: EvidenceVerification? = null,
    val snackbar: String? = null,
    val sync: EvidenceSync = EvidenceSync.Idle,
)

/**
 * Drives the Evidence screen. Mirrors [com.aci.hermes.ui.screens.memory.MemoryViewModel]:
 * collects the repository flows, runs search/verify/promote, and exposes a
 * single immutable [EvidenceUiState]. Promotion surfaces the gateway's honest
 * rejection (owner gate / low confidence) rather than silently succeeding.
 */
class EvidenceViewModel(
    private val repository: EvidenceRepository,
    private val logBuffer: LogBuffer,
) : ViewModel() {

    private val _state = MutableStateFlow(EvidenceUiState())
    val state: StateFlow<EvidenceUiState> = _state.asStateFlow()

    init {
        viewModelScope.launch {
            repository.items.collect { items -> _state.update { it.copy(items = items) } }
        }
        viewModelScope.launch {
            repository.sync.collect { sync -> _state.update { it.copy(sync = sync) } }
        }
        refresh()
    }

    fun refresh() {
        viewModelScope.launch { repository.refresh() }
    }

    fun setQuery(q: String) {
        _state.update { it.copy(query = q) }
    }

    fun search() {
        val q = _state.value.query.trim()
        viewModelScope.launch {
            if (q.isEmpty()) repository.refresh() else repository.search(q)
        }
    }

    fun open(item: EvidenceItem) {
        _state.update { it.copy(selected = item) }
    }

    fun closeDetail() {
        _state.update { it.copy(selected = null) }
    }

    /** Verify a single claim (the selected item's summary by default). */
    fun verify(claim: String) {
        if (claim.isBlank()) return
        viewModelScope.launch {
            val result = repository.verify(listOf(claim), query = claim)
            _state.update {
                it.copy(
                    verification = result,
                    snackbar = if (result == null) "Verify needs a paired gateway" else null,
                )
            }
        }
    }

    fun clearVerification() {
        _state.update { it.copy(verification = null) }
    }

    /**
     * Promote an item to durable memory. [authorization] carries the owner
     * phrase for low-confidence promotions; a rejection is reported honestly.
     */
    fun promote(item: EvidenceItem, authorization: String? = null) {
        viewModelScope.launch {
            when (val outcome = repository.promote(item.id, authorization)) {
                is PromoteOutcome.Promoted -> {
                    logBuffer.info(TAG, "Promoted ${item.id} -> memory ${outcome.nodeId}")
                    _state.update { it.copy(snackbar = "Promoted to memory", selected = null) }
                }
                is PromoteOutcome.Rejected -> {
                    val why = outcome.reasons.firstOrNull() ?: "rejected by memory policy"
                    logBuffer.info(TAG, "Promote rejected ${item.id}: $why")
                    _state.update { it.copy(snackbar = "Not promoted: $why") }
                }
                is PromoteOutcome.Unreachable ->
                    _state.update { it.copy(snackbar = "Gateway unreachable: ${outcome.message}") }
                PromoteOutcome.NotLive ->
                    _state.update { it.copy(snackbar = "Promotion needs a paired gateway") }
            }
        }
    }

    fun consumeSnackbar() {
        _state.update { it.copy(snackbar = null) }
    }

    private companion object {
        const val TAG = "Evidence"
    }
}
