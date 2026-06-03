package com.aci.hermes.ui.screens.ledger

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.ledger.LedgerRepository
import com.aci.hermes.data.ledger.LedgerSync
import com.aci.hermes.data.model.ledger.LedgerEvent
import com.aci.hermes.data.model.ledger.LedgerFilters
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch

/**
 * Drives the Activity timeline screen: the live (redacted) event list, the
 * current filter set, and the sync state. Filter changes re-pull the
 * timeline server-side so paging/ordering stay authoritative.
 */
class LedgerTimelineViewModel(
    private val repository: LedgerRepository,
) : ViewModel() {

    val events: StateFlow<List<LedgerEvent>> = repository.events
    val filters: StateFlow<LedgerFilters> = repository.filters
    val sync: StateFlow<LedgerSync> = repository.sync

    init {
        viewModelScope.launch { repository.refresh() }
    }

    fun refresh() {
        viewModelScope.launch { repository.refresh() }
    }

    fun applyFilters(filters: LedgerFilters) {
        viewModelScope.launch { repository.applyFilters(filters) }
    }

    fun clearFilters() {
        viewModelScope.launch { repository.applyFilters(LedgerFilters()) }
    }
}
