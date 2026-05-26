package com.aci.hermes.ui.screens.emergency

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.emergency.EmergencyStopAuditEvent
import com.aci.hermes.data.emergency.EmergencyStopController
import com.aci.hermes.data.emergency.EmergencyStopState
import com.aci.hermes.data.emergency.ResumeApproval
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class EmergencyStopUiState(
    val state: EmergencyStopState = EmergencyStopState.INACTIVE,
    val audit: List<EmergencyStopAuditEvent> = emptyList(),
    val pendingApproval: ResumeApproval? = null,
    val showConfirmDialog: Boolean = false,
    val showResumeDialog: Boolean = false,
    val snackbar: String? = null,
)

/**
 * UI-facing wrapper around [EmergencyStopController]. The controller
 * already exposes flows, so this VM mostly threads them into a single
 * UiState plus tiny one-shot side effects (snackbar, dialog visibility).
 */
class EmergencyStopViewModel(
    private val controller: EmergencyStopController,
    private val sourceTag: String = "ui:emergency_screen",
) : ViewModel() {

    private val dialogState = MutableStateFlow(DialogState())
    private val snackbar = MutableStateFlow<String?>(null)

    val state: StateFlow<EmergencyStopUiState> =
        combine(
            controller.state,
            controller.audit,
            controller.pendingApproval,
            dialogState,
            snackbar,
        ) { s, audit, pending, dialogs, snack ->
            EmergencyStopUiState(
                state = s,
                audit = audit.asReversed(),
                pendingApproval = pending,
                showConfirmDialog = dialogs.confirm,
                showResumeDialog = dialogs.resume,
                snackbar = snack,
            )
        }.stateIn(viewModelScope, SharingStarted.Eagerly, EmergencyStopUiState())

    fun openConfirmDialog() {
        dialogState.update { it.copy(confirm = true) }
    }

    fun closeConfirmDialog() {
        dialogState.update { it.copy(confirm = false) }
    }

    fun openResumeDialog() {
        dialogState.update { it.copy(resume = true) }
    }

    fun closeResumeDialog() {
        dialogState.update { it.copy(resume = false) }
    }

    fun engage(target: EmergencyStopState, reason: String?) {
        viewModelScope.launch {
            val current = controller.state.value
            if (current.isActive) {
                if (target.severity > current.severity) {
                    val ok = controller.escalate(sourceTag, target, reason)
                    snackbar.update {
                        if (ok) "Escalated to ${labelFor(target)}"
                        else "Already at or above ${labelFor(target)}"
                    }
                } else {
                    snackbar.update { "Already at ${labelFor(current)}" }
                }
            } else {
                controller.engage(sourceTag, reason, target)
                snackbar.update { "Engaged ${labelFor(target)}" }
            }
            closeConfirmDialog()
        }
    }

    fun longPressEscalate() {
        viewModelScope.launch {
            val current = controller.state.value
            val next = when (current) {
                EmergencyStopState.INACTIVE -> EmergencyStopState.SOFT_PAUSE
                EmergencyStopState.SOFT_PAUSE -> EmergencyStopState.HARD_STOP
                EmergencyStopState.HARD_STOP -> EmergencyStopState.LOCKDOWN
                EmergencyStopState.LOCKDOWN -> EmergencyStopState.LOCKDOWN
            }
            if (next == current) {
                snackbar.update { "Already at LOCKDOWN — request resume to release." }
                return@launch
            }
            if (current == EmergencyStopState.INACTIVE) {
                controller.engage(
                    source = "$sourceTag:long_press",
                    reason = "Long-press escalation",
                    target = next,
                )
            } else {
                controller.escalate(
                    source = "$sourceTag:long_press",
                    target = next,
                    reason = "Long-press escalation",
                )
            }
            snackbar.update { "Escalated to ${labelFor(next)}" }
        }
    }

    fun requestResume(reason: String? = null) {
        viewModelScope.launch {
            val approval = controller.requestResume(
                requestedBy = sourceTag,
                reason = reason,
            )
            snackbar.update {
                if (approval == null) "Nothing to resume — Jarvis is already inactive."
                else "Resume requested. Approval still required."
            }
            if (approval != null) {
                dialogState.update { it.copy(resume = true) }
            }
        }
    }

    fun approveResume(approver: String) {
        val approval = controller.pendingApproval.value ?: run {
            snackbar.update { "No pending approval to act on." }
            return
        }
        viewModelScope.launch {
            val ok = controller.approveResume(approval.id, approver)
            snackbar.update {
                if (ok) "Resume approved — Jarvis is back to INACTIVE."
                else "Approval was stale; request resume again."
            }
            closeResumeDialog()
        }
    }

    fun denyResume(reason: String?) {
        val approval = controller.pendingApproval.value ?: run {
            snackbar.update { "No pending approval to deny." }
            closeResumeDialog()
            return
        }
        viewModelScope.launch {
            controller.denyResume(approval.id, sourceTag, reason)
            snackbar.update { "Resume denied." }
            closeResumeDialog()
        }
    }

    fun deescalate(target: EmergencyStopState) {
        viewModelScope.launch {
            val ok = controller.deescalate(sourceTag, target)
            snackbar.update {
                if (ok) "Deescalated to ${labelFor(target)}"
                else "Cannot deescalate to ${labelFor(target)} from current level."
            }
        }
    }

    fun consumeSnackbar() {
        snackbar.value = null
    }

    fun exportAuditJson(): String = controller.let {
        // Defer to repository's snapshot through controller's audit
        // flow — controllers expose the snapshot via the repository.
        repositorySnapshotJson()
    }

    private fun repositorySnapshotJson(): String {
        // The repository's snapshot helper is exposed through the
        // controller via a tiny field we add below. We re-encode here
        // using the controller's exposed state to keep the VM honest
        // even if the repo path is mocked in tests.
        return controller.snapshotJsonForExport()
    }

    private data class DialogState(val confirm: Boolean = false, val resume: Boolean = false)

    companion object {
        private fun labelFor(s: EmergencyStopState): String = when (s) {
            EmergencyStopState.INACTIVE -> "INACTIVE"
            EmergencyStopState.SOFT_PAUSE -> "SOFT PAUSE"
            EmergencyStopState.HARD_STOP -> "HARD STOP"
            EmergencyStopState.LOCKDOWN -> "LOCKDOWN"
        }
    }
}
