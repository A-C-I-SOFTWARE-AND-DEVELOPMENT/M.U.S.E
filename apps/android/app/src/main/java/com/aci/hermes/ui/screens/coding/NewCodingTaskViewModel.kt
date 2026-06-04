package com.aci.hermes.ui.screens.coding

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.cockpit.CodingAuditResult
import com.aci.hermes.data.coding.CodingActionResult
import com.aci.hermes.data.coding.CodingRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/**
 * "New Coding Task" — capture a plain-English request, preview its
 * classification (risk / worker / owner gates) from the backend, and build a
 * bounded work packet. Stays useful offline: Generate always produces a saved
 * task (drafted/queued) the user can open, so there is never a dead end.
 */
class NewCodingTaskViewModel(
    private val repository: CodingRepository,
    private val isPaired: () -> Boolean,
    private val isMock: () -> Boolean,
) : ViewModel() {

    data class UiState(
        val prompt: String = "",
        val repoRoot: String = "",
        val busy: Boolean = false,
        val audit: CodingAuditResult? = null,
        val message: String? = null,
        val paired: Boolean = false,
        val mock: Boolean = false,
        /** Set when a task is ready to open in Work Packet detail (one-shot). */
        val navigateToTaskId: String? = null,
    )

    private val _state = MutableStateFlow(UiState(paired = isPaired(), mock = isMock()))
    val state: StateFlow<UiState> = _state.asStateFlow()

    fun updatePrompt(value: String) = _state.update { it.copy(prompt = value) }

    fun updateRepoRoot(value: String) = _state.update { it.copy(repoRoot = value) }

    /** Classify only (read-only) — shows the risk/worker/owner-gate preview. */
    fun previewClassification() {
        val prompt = _state.value.prompt.trim()
        if (prompt.isEmpty()) {
            _state.update { it.copy(message = "Describe the coding task first.") }
            return
        }
        run { task ->
            when (val r = repository.runAudit(task.id)) {
                is CodingActionResult.Ok -> _state.update { it.copy(audit = r.task.audit) }
                is CodingActionResult.NeedsPairing ->
                    _state.update { it.copy(message = "Saved offline — pair a gateway to classify.") }
                is CodingActionResult.Failure -> _state.update { it.copy(message = r.message) }
                is CodingActionResult.OwnerGateRequired -> Unit
            }
        }
    }

    /** Build a bounded work packet, then open it (or the saved draft offline). */
    fun generatePacket() {
        val prompt = _state.value.prompt.trim()
        if (prompt.isEmpty()) {
            _state.update { it.copy(message = "Describe the coding task first.") }
            return
        }
        run { task ->
            // Audit first (best-effort) so the packet screen has the route preview.
            repository.runAudit(task.id)
            when (val r = repository.runPlan(task.id)) {
                is CodingActionResult.Ok ->
                    _state.update { it.copy(navigateToTaskId = r.task.id) }
                is CodingActionResult.NeedsPairing ->
                    _state.update {
                        it.copy(
                            message = "No backend reachable — saved as a queued draft. Open it to copy a prompt.",
                            navigateToTaskId = r.task.id,
                        )
                    }
                is CodingActionResult.Failure ->
                    _state.update { it.copy(message = r.message, navigateToTaskId = r.task?.id) }
                is CodingActionResult.OwnerGateRequired ->
                    _state.update { it.copy(navigateToTaskId = r.task.id) }
            }
        }
    }

    fun consumeNavigation() = _state.update { it.copy(navigateToTaskId = null) }

    fun clearMessage() = _state.update { it.copy(message = null) }

    /**
     * Shared prelude: refresh mode flags, create the draft, mark busy, run
     * [block] with the created task, then clear busy. The draft is created once
     * per Generate/Preview press (each press starts a fresh task).
     */
    private fun run(block: suspend (com.aci.hermes.data.coding.SavedCodingTask) -> Unit) {
        viewModelScope.launch {
            _state.update { it.copy(busy = true, message = null, paired = isPaired(), mock = isMock()) }
            try {
                val task = repository.createDraft(
                    prompt = _state.value.prompt,
                    repoRoot = _state.value.repoRoot,
                )
                block(task)
            } finally {
                _state.update { it.copy(busy = false) }
            }
        }
    }
}
