package com.aci.hermes.ui.screens.coding

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.coding.CodingActionResult
import com.aci.hermes.data.coding.CodingHandoffState
import com.aci.hermes.data.coding.CodingRepository
import com.aci.hermes.data.coding.SavedCodingTask
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/**
 * Work Packet detail — the bounded packet (mission, risk, allowed/forbidden
 * files, acceptance, verification, rollback, owner gates, route) with two
 * exits: **Copy Claude Code prompt** (offline-safe handoff) and **Send to
 * backend** (a gated execute that never runs without the owner phrase). The
 * task is observed live from the store so re-plan / execute updates reflect
 * immediately.
 */
class WorkPacketDetailViewModel(
    private val repository: CodingRepository,
    private val taskId: String,
) : ViewModel() {

    data class UiState(
        val task: SavedCodingTask? = null,
        val busy: Boolean = false,
        val message: String? = null,
        /** When non-null, the UI prompts for the owner authorization phrase. */
        val ownerGateHint: String? = null,
        /** One-shot: the prompt text the screen should copy to the clipboard. */
        val copyText: String? = null,
    )

    // Transient UI flags (busy / messages / one-shot copy + gate).
    private val _ui = MutableStateFlow(UiState())

    // Public state = stored task merged with the transient flags, kept live.
    private val _state = MutableStateFlow(UiState(task = repository.byId(taskId)))
    val state: StateFlow<UiState> = _state.asStateFlow()

    init {
        viewModelScope.launch {
            combine(repository.tasks, _ui) { tasks, ui ->
                ui.copy(task = tasks.firstOrNull { it.id == taskId })
            }.collect { _state.value = it }
        }
    }

    fun regeneratePacket() = withBusy {
        when (val r = repository.runPlan(taskId)) {
            is CodingActionResult.Ok -> _ui.update { it.copy(message = null) }
            is CodingActionResult.NeedsPairing ->
                _ui.update { it.copy(message = "No backend reachable — kept offline. Copy a prompt instead.") }
            is CodingActionResult.Failure -> _ui.update { it.copy(message = r.message) }
            is CodingActionResult.OwnerGateRequired -> Unit
        }
    }

    /** Build the Claude Code prompt, hand it to the screen to copy, mark handed off. */
    fun copyPrompt() = viewModelScope.launch {
        val task = repository.byId(taskId) ?: return@launch
        _ui.update { it.copy(copyText = repository.promptFor(task)) }
        repository.markHandedOff(taskId)
    }

    fun consumeCopy() = _ui.update { it.copy(copyText = null) }

    /** Stage/dispatch an execute. Null phrase ⇒ the gateway stages and gates it. */
    fun sendToBackend(authorization: String? = null) = withBusy {
        when (val r = repository.runExecute(taskId, authorization)) {
            is CodingActionResult.Ok ->
                _ui.update { it.copy(message = "Dispatched to the backend.", ownerGateHint = null) }
            is CodingActionResult.OwnerGateRequired ->
                _ui.update { it.copy(ownerGateHint = r.hint) }
            is CodingActionResult.NeedsPairing ->
                _ui.update { it.copy(message = "No backend reachable. Pair a gateway in Settings.") }
            is CodingActionResult.Failure ->
                _ui.update { it.copy(message = r.message, ownerGateHint = null) }
        }
    }

    fun dismissOwnerGate() = _ui.update { it.copy(ownerGateHint = null) }

    fun clearMessage() = _ui.update { it.copy(message = null) }

    /** True when the task carries a packet ready to hand off. */
    fun isReady(): Boolean = repository.byId(taskId)?.isHandoffReady == true

    /** True when execute makes sense (planned and not already running/done). */
    fun canExecute(): Boolean {
        val s = repository.byId(taskId)?.state ?: return false
        return s == CodingHandoffState.PLANNED || s == CodingHandoffState.BLOCKED_OWNER ||
            s == CodingHandoffState.AUDITED
    }

    private fun withBusy(block: suspend () -> Unit) {
        viewModelScope.launch {
            _ui.update { it.copy(busy = true, message = null) }
            try {
                block()
            } finally {
                _ui.update { it.copy(busy = false) }
            }
        }
    }
}
