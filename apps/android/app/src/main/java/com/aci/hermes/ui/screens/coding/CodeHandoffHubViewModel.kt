package com.aci.hermes.ui.screens.coding

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.coding.CodingActionResult
import com.aci.hermes.data.coding.CodingHandoffState
import com.aci.hermes.data.coding.CodingRepository
import com.aci.hermes.data.coding.SavedCodingTask
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/**
 * Code Handoff Hub — every saved coding task grouped by where it is in the
 * flow (queued offline, planned, handed off, blocked on the owner gate,
 * executing, done). Retry/resume re-runs the appropriate step; delete clears
 * a task. The hub is the place to pick a queued task back up once a backend
 * comes online.
 */
class CodeHandoffHubViewModel(
    private val repository: CodingRepository,
) : ViewModel() {

    data class Group(val state: CodingHandoffState, val tasks: List<SavedCodingTask>)

    data class UiState(
        val groups: List<Group> = emptyList(),
        val total: Int = 0,
        val busyId: String? = null,
        val message: String? = null,
        /** One-shot prompt text to copy. */
        val copyText: String? = null,
    )

    private val _ui = MutableStateFlow(UiState())

    val state: StateFlow<UiState> =
        combine(repository.tasks, _ui) { tasks, ui ->
            ui.copy(groups = group(tasks), total = tasks.size)
        }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), UiState())

    /** Re-run the next step for a task: plan if not yet planned, else nothing. */
    fun retry(id: String) {
        val task = repository.byId(id) ?: return
        viewModelScope.launch {
            _ui.update { it.copy(busyId = id, message = null) }
            try {
                val result = when (task.state) {
                    CodingHandoffState.DRAFT,
                    CodingHandoffState.QUEUED_OFFLINE,
                    CodingHandoffState.AUDITED,
                    CodingHandoffState.ERROR,
                    -> repository.runPlan(id)
                    else -> CodingActionResult.Ok(task)
                }
                if (result is CodingActionResult.NeedsPairing) {
                    _ui.update { it.copy(message = "Still no backend — kept queued. Copy a prompt to hand off now.") }
                } else if (result is CodingActionResult.Failure) {
                    _ui.update { it.copy(message = result.message) }
                }
            } finally {
                _ui.update { it.copy(busyId = null) }
            }
        }
    }

    fun copyPrompt(id: String) {
        val task = repository.byId(id) ?: return
        viewModelScope.launch {
            _ui.update { it.copy(copyText = repository.promptFor(task)) }
            repository.markHandedOff(id)
        }
    }

    fun consumeCopy() = _ui.update { it.copy(copyText = null) }

    fun clearMessage() = _ui.update { it.copy(message = null) }

    fun delete(id: String) = viewModelScope.launch { repository.delete(id) }

    private fun group(tasks: List<SavedCodingTask>): List<Group> =
        ORDER.mapNotNull { st ->
            tasks.filter { it.state == st }
                .takeIf { it.isNotEmpty() }
                ?.let { Group(st, it.sortedByDescending { t -> t.updatedAt }) }
        }

    private companion object {
        // Surfacing order: things needing attention first.
        val ORDER = listOf(
            CodingHandoffState.BLOCKED_OWNER,
            CodingHandoffState.QUEUED_OFFLINE,
            CodingHandoffState.ERROR,
            CodingHandoffState.EXECUTING,
            CodingHandoffState.PLANNED,
            CodingHandoffState.AUDITED,
            CodingHandoffState.DRAFT,
            CodingHandoffState.HANDED_OFF,
            CodingHandoffState.DONE,
        )
    }
}
