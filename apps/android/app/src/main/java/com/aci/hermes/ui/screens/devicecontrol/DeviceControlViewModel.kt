package com.aci.hermes.ui.screens.devicecontrol

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.devicecontrol.DeviceActionLogEntry
import com.aci.hermes.data.devicecontrol.DeviceControlCapability
import com.aci.hermes.data.devicecontrol.DeviceControlController
import com.aci.hermes.data.devicecontrol.PendingDeviceAction
import com.aci.hermes.data.preferences.SettingsRepository
import com.aci.hermes.util.LogBuffer
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.launchIn
import kotlinx.coroutines.flow.onEach
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/** One capability row: explanation + owner consent + live OS grant. */
data class DeviceCapabilityRow(
    val capability: DeviceControlCapability,
    val consented: Boolean,
    val granted: Boolean,
)

data class DeviceControlUiState(
    val enabled: Boolean = false,
    val confirmSensitive: Boolean = true,
    val halted: Boolean = false,
    val capabilities: List<DeviceCapabilityRow> = emptyList(),
    /** True when control is enabled, not halted, and the hands are connected. */
    val activeNow: Boolean = false,
    val recent: List<DeviceActionLogEntry> = emptyList(),
    /** A sensitive action held for explicit Approve / Dismiss, if any. */
    val pending: PendingDeviceAction? = null,
    /** Owner-gate dialog flag for turning sensitive-action confirmation OFF. */
    val confirmDisableSensitive: Boolean = false,
)

/**
 * Drives the Device control screen. Presentation only: it reads consent
 * from [SettingsRepository], live grant + halt state from
 * [DeviceControlController], and the action history from the controller's
 * ledger. It never dispatches a device action itself — that path is the
 * broker, reached from voice/automation.
 */
class DeviceControlViewModel(
    application: Application,
    private val settings: SettingsRepository,
    private val controller: DeviceControlController,
    private val logBuffer: LogBuffer,
) : AndroidViewModel(application) {

    private val grantedState = MutableStateFlow(controller.grantedCapabilities())

    private val _state = MutableStateFlow(DeviceControlUiState())
    val state: StateFlow<DeviceControlUiState> = _state.asStateFlow()

    init {
        combine(
            settings.deviceControlEnabled,
            settings.deviceConfirmSensitive,
            settings.deviceConsentedCapabilities,
            controller.halted,
            controller.log,
        ) { enabled, confirm, consentedIds, halted, log ->
            project(enabled, confirm, consentedIds, halted, log, grantedState.value)
        }.combine(controller.pending) { state, pending ->
            state.copy(pending = pending)
        }.onEach { projected -> _state.value = projected }.launchIn(viewModelScope)

        // Recompute the projection when the live grant set changes.
        grantedState.onEach { refreshProjection() }.launchIn(viewModelScope)
    }

    /** Re-read OS grant status (call when the screen resumes). */
    fun refresh() {
        grantedState.value = controller.grantedCapabilities()
    }

    fun setEnabled(value: Boolean) {
        viewModelScope.launch {
            settings.setDeviceControlEnabled(value)
            logBuffer.info(TAG, "Device control enabled = $value")
        }
    }

    fun setCapabilityConsent(capability: DeviceControlCapability, value: Boolean) {
        viewModelScope.launch {
            settings.setCapabilityConsent(capability.id, value)
            logBuffer.info(TAG, "Consent ${capability.id} = $value")
        }
    }

    /**
     * Turning confirmation OFF is an owner-gated, high-power choice, so it
     * raises a confirmation dialog. Turning it back ON is immediate.
     */
    fun requestConfirmSensitive(value: Boolean) {
        if (!value) {
            _state.update { it.copy(confirmDisableSensitive = true) }
        } else {
            commitConfirmSensitive(true)
        }
    }

    fun confirmDisableSensitiveProceed() {
        _state.update { it.copy(confirmDisableSensitive = false) }
        commitConfirmSensitive(false)
    }

    fun dismissDisableSensitive() {
        _state.update { it.copy(confirmDisableSensitive = false) }
    }

    private fun commitConfirmSensitive(value: Boolean) {
        viewModelScope.launch {
            settings.setDeviceConfirmSensitive(value)
            logBuffer.warn(TAG, "Confirm sensitive actions = $value")
        }
    }

    /** Owner confirms a held sensitive action — it runs now. */
    fun approvePending(id: String) {
        controller.approvePending(id)
    }

    /** Owner declines a held sensitive action — it never runs. */
    fun dismissPending(id: String) {
        controller.dismissPending(id)
    }

    fun engageEmergencyStop() {
        controller.engageEmergencyStop()
    }

    fun releaseEmergencyStop() {
        controller.releaseEmergencyStop()
    }

    private fun refreshProjection() {
        val s = _state.value
        _state.value = project(
            enabled = s.enabled,
            confirm = s.confirmSensitive,
            consentedIds = s.capabilities.filter { it.consented }.map { it.capability.id }.toSet(),
            halted = s.halted,
            log = s.recent,
            granted = grantedState.value,
        )
    }

    private fun project(
        enabled: Boolean,
        confirm: Boolean,
        consentedIds: Set<String>,
        halted: Boolean,
        log: List<DeviceActionLogEntry>,
        granted: Set<DeviceControlCapability>,
    ): DeviceControlUiState {
        val rows = DeviceControlCapability.entries.map { cap ->
            DeviceCapabilityRow(
                capability = cap,
                consented = cap.id in consentedIds,
                granted = cap in granted,
            )
        }
        return DeviceControlUiState(
            enabled = enabled,
            confirmSensitive = confirm,
            halted = halted,
            capabilities = rows,
            activeNow = enabled && !halted && DeviceControlCapability.ACCESSIBILITY in granted,
            recent = log.takeLast(MAX_RECENT).reversed(),
            // Preserved across grant-only reprojections; the live combine with
            // controller.pending re-applies the authoritative value.
            pending = _state.value.pending,
            confirmDisableSensitive = _state.value.confirmDisableSensitive,
        )
    }

    companion object {
        const val TAG = "DeviceControlVm"
        private const val MAX_RECENT = 30
    }
}
