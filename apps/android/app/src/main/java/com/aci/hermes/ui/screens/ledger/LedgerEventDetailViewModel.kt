package com.aci.hermes.ui.screens.ledger

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.ledger.LedgerRepository
import com.aci.hermes.data.model.ledger.LedgerEventDetail
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

/** Outcome of a gated rollback request, surfaced to the detail screen. */
sealed interface RollbackRequestState {
    data object Idle : RollbackRequestState
    data object Submitting : RollbackRequestState
    /** Queued for owner approval — [approvalId] is the new Approvals card. */
    data class Queued(val approvalId: String) : RollbackRequestState
    data class Failed(val message: String) : RollbackRequestState
}

data class LedgerEventDetailUiState(
    val detail: LedgerEventDetail? = null,
    val loading: Boolean = true,
    val notFound: Boolean = false,
    val rollback: RollbackRequestState = RollbackRequestState.Idle,
)

/**
 * Loads one timeline event's redacted detail and mediates the **owner-gated**
 * rollback request. The request never executes a rollback — it queues an
 * approval card the owner must approve with the exact phrase.
 *
 * [eventId] is the `"<jobId>:<index>"` id from the timeline row.
 */
class LedgerEventDetailViewModel(
    private val repository: LedgerRepository,
    private val eventId: String,
) : ViewModel() {

    private val jobId: String = eventId.substringBeforeLast(':', "")
    private val index: Int = eventId.substringAfterLast(':', "-1").toIntOrNull() ?: -1

    private val _state = MutableStateFlow(LedgerEventDetailUiState())
    val state: StateFlow<LedgerEventDetailUiState> = _state.asStateFlow()

    init {
        load()
    }

    fun load() {
        viewModelScope.launch {
            _state.value = _state.value.copy(loading = true)
            val detail = if (jobId.isNotBlank() && index >= 0) {
                repository.fetchDetail(jobId, index)
            } else {
                null
            }
            _state.value = LedgerEventDetailUiState(
                detail = detail,
                loading = false,
                notFound = detail == null,
                rollback = _state.value.rollback,
            )
        }
    }

    /** Queue an owner-gated rollback request for this event. */
    fun requestRollback(reason: String?) {
        if (jobId.isBlank() || index < 0) return
        viewModelScope.launch {
            _state.value = _state.value.copy(rollback = RollbackRequestState.Submitting)
            val approvalId = repository.requestRollback(jobId, index, reason)
            _state.value = _state.value.copy(
                rollback = if (approvalId != null) {
                    RollbackRequestState.Queued(approvalId)
                } else {
                    RollbackRequestState.Failed("Could not queue rollback (gateway unreachable or unpaired).")
                },
            )
        }
    }
}
