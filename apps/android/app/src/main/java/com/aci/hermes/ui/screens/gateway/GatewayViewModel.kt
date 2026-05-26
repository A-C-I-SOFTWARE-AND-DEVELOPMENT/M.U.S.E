package com.aci.hermes.ui.screens.gateway

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.gateway.ApprovalRiskClass
import com.aci.hermes.data.gateway.GatewayController
import com.aci.hermes.data.gateway.GatewayUiState
import com.aci.hermes.data.gateway.ImpactReport
import com.aci.hermes.data.gateway.PendingApprovalSummary
import com.aci.hermes.util.LogBuffer
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.util.UUID

/**
 * Drives the demo Gateway screen. State is read straight off
 * [GatewayController] — this VM only adds a snackbar channel and the
 * dialog state for serious / critical confirmation flows.
 *
 * Two flows worth noting:
 *
 *  - "Confirm serious" is wired to call the client's
 *    [com.aci.hermes.data.gateway.GatewayClient.confirmSerious] twice,
 *    with two distinct tokens. The reducer then sees two
 *    `approval_granted` events with `confirmation_index=1,2` and the
 *    pending approval falls out of the list.
 *  - "Confirm critical" requires an [ImpactReport]. The demo screen
 *    forwards the impact report that came in on the original
 *    `critical_confirmation_required` event; the type system forbids
 *    a path that omits it.
 */
class GatewayViewModel(
    private val controller: GatewayController,
    private val logBuffer: LogBuffer,
) : ViewModel() {

    private val _snackbar = MutableStateFlow<String?>(null)
    val snackbar: StateFlow<String?> = _snackbar.asStateFlow()

    val state: StateFlow<GatewayUiState> = controller.state

    private val _userInput = MutableStateFlow("")
    val userInput: StateFlow<String> = _userInput.asStateFlow()

    init {
        // Surface emergency stop in the snackbar exactly once whenever
        // it transitions from null → set. distinctUntilChanged keeps a
        // sustained EmergencyStopState from re-firing the snackbar on
        // every unrelated event.
        viewModelScope.launch {
            controller.state
                .map { it.emergencyStop?.reason }
                .distinctUntilChanged()
                .collect { reason ->
                    if (reason != null) {
                        _snackbar.value = "Emergency stop: $reason"
                    }
                }
        }
    }

    fun onUserInputChanged(text: String) { _userInput.value = text }

    fun sendUserMessage() {
        val text = _userInput.value.trim()
        if (text.isBlank()) return
        _userInput.value = ""
        val client = controller.client() ?: run {
            _snackbar.value = "Gateway not connected"
            return
        }
        viewModelScope.launch {
            runCatching { client.sendUserMessage(text) }
                .onFailure { _snackbar.value = "sendUserMessage failed: ${it.javaClass.simpleName}" }
        }
    }

    fun grantApproval(approval: PendingApprovalSummary) {
        val client = controller.client() ?: return
        viewModelScope.launch {
            runCatching {
                when (approval.riskClass) {
                    ApprovalRiskClass.STANDARD -> client.grantApproval(approval.approvalId)
                    ApprovalRiskClass.SERIOUS -> {
                        // The screen calls this twice (with separate
                        // taps) — each tap emits one confirmation.
                        val token = UUID.randomUUID().toString()
                        client.confirmSerious(approval.approvalId, token)
                    }
                    ApprovalRiskClass.CRITICAL -> {
                        val impact = approval.impactReport
                            ?: ImpactReport(
                                summary = approval.summary,
                                blastRadius = "unknown",
                                reversibility = "unknown",
                                rollbackPlan = "Operator must define rollback before retry.",
                            )
                        client.confirmCritical(approval.approvalId, impact)
                    }
                }
            }.onFailure {
                _snackbar.value = "approval failed: ${it.javaClass.simpleName}"
            }
        }
    }

    fun rejectApproval(approval: PendingApprovalSummary) {
        val client = controller.client() ?: return
        viewModelScope.launch {
            runCatching { client.rejectApproval(approval.approvalId, "user_rejected") }
                .onFailure { _snackbar.value = "reject failed: ${it.javaClass.simpleName}" }
        }
    }

    fun triggerEmergencyStop() {
        val client = controller.client() ?: return
        viewModelScope.launch {
            runCatching { client.triggerEmergencyStop("user_panic_button") }
                .onFailure { _snackbar.value = "emergency_stop failed: ${it.javaClass.simpleName}" }
        }
    }

    fun reconnect() {
        viewModelScope.launch {
            // switchMode with the existing connection's mode is a clean
            // reconnect — the controller tears down and rebuilds.
            val mode = when (val c = controller.state.value.connection) {
                is com.aci.hermes.data.gateway.GatewayConnectionState.Connected -> c.mode
                else -> com.aci.hermes.data.gateway.GatewayMode.MOCK
            }
            controller.switchMode(mode)
        }
    }

    fun consumeSnackbar() { _snackbar.update { null } }
}
