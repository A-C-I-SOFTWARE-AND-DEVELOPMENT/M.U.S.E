package com.aci.hermes.learning.state

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.learning.LearningCandidate
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class LearningUiState(
    val candidates: List<LearningCandidate> = emptyList(),
    val sync: LearningSync = LearningSync.Idle,
)

/**
 * Drives the cockpit Learning Queue section. Loads real candidates from the
 * gateway and decides them through [LearningRepository], which enforces the
 * owner-gate phrase on approve.
 */
class LearningViewModel(
    private val repository: LearningRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(LearningUiState())
    val state: StateFlow<LearningUiState> = _state.asStateFlow()

    init {
        viewModelScope.launch {
            repository.candidates.collect { cands ->
                _state.value = _state.value.copy(candidates = cands)
            }
        }
        viewModelScope.launch {
            repository.sync.collect { s ->
                _state.value = _state.value.copy(sync = s)
            }
        }
        refresh()
    }

    fun refresh() {
        viewModelScope.launch { repository.refresh() }
    }

    /** Approve a candidate. The repository submits the owner phrase; the
     *  gateway still verifies it server-side. */
    fun approve(id: String) {
        viewModelScope.launch { repository.approve(id) }
    }

    fun reject(id: String, notes: String? = null) {
        viewModelScope.launch { repository.reject(id, notes) }
    }
}
