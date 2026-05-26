package com.aci.hermes.ui.screens.settings

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.jarvis.AutonomyMode
import com.aci.hermes.data.jarvis.ControlWarnings
import com.aci.hermes.data.jarvis.PendingWarning
import com.aci.hermes.data.jarvis.ResponseLength
import com.aci.hermes.data.jarvis.WarningLevel
import com.aci.hermes.data.orchestrator.HermesTaskRepository
import com.aci.hermes.data.preferences.PreferredBuilder
import com.aci.hermes.data.preferences.PreferredReviewer
import com.aci.hermes.data.preferences.SettingsRepository
import com.aci.hermes.data.preferences.ThemeMode
import com.aci.hermes.util.LogBuffer
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class SettingsUiState(
    val themeMode: ThemeMode = ThemeMode.SYSTEM,
    val preferredBuilder: PreferredBuilder = PreferredBuilder.CODEX,
    val preferredReviewer: PreferredReviewer = PreferredReviewer.CLAUDE_CODE,
    val useApiKeys: Boolean = false,
    val localOnlyMode: Boolean = true,
    val allowExternalAppOpening: Boolean = false,
    val clipboardHandoffEnabled: Boolean = true,
    val showSafetyWarnings: Boolean = true,
    val responseLength: ResponseLength = ResponseLength.BALANCED,
    val mobileMode: Boolean = true,
    val notificationsEnabled: Boolean = true,
    val voiceEnabled: Boolean = false,
    val interactiveIconEnabled: Boolean = true,
    val gatewayEndpoint: String = SettingsRepository.DEFAULT_GATEWAY_ENDPOINT,
    val mockMode: Boolean = false,
    val termuxGatewayMode: Boolean = false,
    val approvalsRequired: Boolean = true,
    val privacyLocalOnlyMemory: Boolean = true,
    val autonomyMode: AutonomyMode = AutonomyMode.MANUAL,
    val pendingWarning: PendingWarning? = null,
    val pendingGatewayEndpoint: String? = null,
)

class SettingsViewModel(
    private val settings: SettingsRepository,
    private val tasks: HermesTaskRepository,
    private val logBuffer: LogBuffer,
) : ViewModel() {

    private val _state = MutableStateFlow(SettingsUiState())
    val state: StateFlow<SettingsUiState> = _state.asStateFlow()

    init {
        viewModelScope.launch {
            val snap = settings.snapshot()
            _state.value = SettingsUiState(
                themeMode = snap.themeMode,
                preferredBuilder = snap.preferredBuilder,
                preferredReviewer = snap.preferredReviewer,
                useApiKeys = snap.useApiKeys,
                localOnlyMode = snap.localOnlyMode,
                allowExternalAppOpening = snap.allowExternalAppOpening,
                clipboardHandoffEnabled = snap.clipboardHandoffEnabled,
                showSafetyWarnings = snap.showSafetyWarnings,
                responseLength = snap.responseLength,
                mobileMode = snap.mobileMode,
                notificationsEnabled = snap.notificationsEnabled,
                voiceEnabled = snap.voiceEnabled,
                interactiveIconEnabled = snap.interactiveIconEnabled,
                gatewayEndpoint = snap.gatewayEndpoint,
                mockMode = snap.mockMode,
                termuxGatewayMode = snap.termuxGatewayMode,
                approvalsRequired = snap.approvalsRequired,
                privacyLocalOnlyMemory = snap.privacyLocalOnlyMemory,
                autonomyMode = snap.autonomyMode,
            )
        }
    }

    fun setThemeMode(mode: ThemeMode) {
        _state.update { it.copy(themeMode = mode) }
        viewModelScope.launch { settings.setThemeMode(mode) }
    }

    fun setPreferredBuilder(value: PreferredBuilder) {
        _state.update { it.copy(preferredBuilder = value) }
        viewModelScope.launch { settings.setPreferredBuilder(value) }
    }

    fun setPreferredReviewer(value: PreferredReviewer) {
        _state.update { it.copy(preferredReviewer = value) }
        viewModelScope.launch { settings.setPreferredReviewer(value) }
    }

    fun setUseApiKeys(value: Boolean) {
        _state.update { it.copy(useApiKeys = value) }
        viewModelScope.launch { settings.setUseApiKeys(value) }
    }

    fun setLocalOnlyMode(value: Boolean) {
        _state.update { it.copy(localOnlyMode = value) }
        viewModelScope.launch { settings.setLocalOnlyMode(value) }
    }

    fun setAllowExternalAppOpening(value: Boolean) {
        _state.update { it.copy(allowExternalAppOpening = value) }
        viewModelScope.launch { settings.setAllowExternalAppOpening(value) }
    }

    fun setClipboardHandoffEnabled(value: Boolean) {
        _state.update { it.copy(clipboardHandoffEnabled = value) }
        viewModelScope.launch { settings.setClipboardHandoffEnabled(value) }
    }

    fun setShowSafetyWarnings(value: Boolean) {
        _state.update { it.copy(showSafetyWarnings = value) }
        viewModelScope.launch { settings.setShowSafetyWarnings(value) }
    }

    fun setResponseLength(value: ResponseLength) {
        _state.update { it.copy(responseLength = value) }
        viewModelScope.launch { settings.setResponseLength(value) }
    }

    fun setMobileMode(value: Boolean) {
        _state.update { it.copy(mobileMode = value) }
        viewModelScope.launch { settings.setMobileMode(value) }
    }

    fun setNotificationsEnabled(value: Boolean) {
        _state.update { it.copy(notificationsEnabled = value) }
        viewModelScope.launch { settings.setNotificationsEnabled(value) }
    }

    fun setVoiceEnabled(value: Boolean) {
        _state.update { it.copy(voiceEnabled = value) }
        viewModelScope.launch { settings.setVoiceEnabled(value) }
    }

    fun setInteractiveIconEnabled(value: Boolean) {
        _state.update { it.copy(interactiveIconEnabled = value) }
        viewModelScope.launch { settings.setInteractiveIconEnabled(value) }
    }

    fun setMockMode(value: Boolean) {
        if (value == _state.value.mockMode) return
        val action = ControlWarnings.Action.ToggleMockMode
        val level = ControlWarnings.levelFor(action)
        if (level == WarningLevel.NONE) {
            commitMockMode(value)
        } else {
            _state.update {
                it.copy(
                    pendingWarning = PendingWarning(
                        level = level,
                        title = if (value) "Turn on mock mode?" else "Turn off mock mode?",
                        message = "Mock mode short-circuits the gateway with a local stub. " +
                            "Useful for development; live gateways stay disconnected while it is on.",
                        confirmLabel = if (value) "Enable mock mode" else "Disable mock mode",
                        action = action,
                    ),
                )
            }
        }
    }

    private fun commitMockMode(value: Boolean) {
        _state.update { it.copy(mockMode = value, pendingWarning = null) }
        viewModelScope.launch {
            settings.setMockMode(value)
            logBuffer.warn(TAG, "Mock mode = $value")
        }
    }

    fun setTermuxGatewayMode(value: Boolean) {
        if (value == _state.value.termuxGatewayMode) return
        val action = ControlWarnings.Action.ToggleTermuxGateway
        val level = ControlWarnings.levelFor(action)
        if (level == WarningLevel.NONE) {
            commitTermuxGatewayMode(value)
        } else {
            _state.update {
                it.copy(
                    pendingWarning = PendingWarning(
                        level = level,
                        title = if (value) "Use Termux gateway?" else "Disable Termux gateway?",
                        message = "Termux gateway mode routes Jarvis through a local Python process " +
                            "instead of an HTTP endpoint. Use only when running Hermes on the device.",
                        confirmLabel = if (value) "Use Termux gateway" else "Use HTTP gateway",
                        action = action,
                    ),
                )
            }
        }
    }

    private fun commitTermuxGatewayMode(value: Boolean) {
        _state.update { it.copy(termuxGatewayMode = value, pendingWarning = null) }
        viewModelScope.launch {
            settings.setTermuxGatewayMode(value)
            logBuffer.warn(TAG, "Termux gateway mode = $value")
        }
    }

    fun requestGatewayEndpointChange(newEndpoint: String) {
        val current = _state.value.gatewayEndpoint
        val trimmed = newEndpoint.trim()
        if (trimmed == current) return
        val action = ControlWarnings.Action.GatewayEndpointChange(from = current, to = trimmed)
        val level = ControlWarnings.levelFor(action)
        if (level == WarningLevel.NONE) {
            commitGatewayEndpoint(trimmed)
        } else {
            _state.update {
                it.copy(
                    pendingGatewayEndpoint = trimmed,
                    pendingWarning = PendingWarning(
                        level = level,
                        title = "Change gateway endpoint?",
                        message = "Jarvis will reconnect to $trimmed and drop the existing session. " +
                            "Make sure the new endpoint is one you control.",
                        confirmLabel = "Use new endpoint",
                        action = action,
                    ),
                )
            }
        }
    }

    private fun commitGatewayEndpoint(value: String) {
        _state.update {
            it.copy(gatewayEndpoint = value, pendingGatewayEndpoint = null, pendingWarning = null)
        }
        viewModelScope.launch {
            settings.setGatewayEndpoint(value)
            logBuffer.warn(TAG, "Gateway endpoint changed to $value")
        }
    }

    fun requestApprovalsRequired(value: Boolean) {
        if (value == _state.value.approvalsRequired) return
        val action = if (value) ControlWarnings.Action.EnableApprovals
        else ControlWarnings.Action.DisableApprovals
        val level = ControlWarnings.levelFor(action)
        if (level == WarningLevel.NONE) {
            commitApprovalsRequired(value)
        } else {
            _state.update {
                it.copy(
                    pendingWarning = PendingWarning(
                        level = level,
                        title = "Disable owner approvals?",
                        message = "Jarvis will run multi-step work without asking first. " +
                            "Destructive steps still need explicit owner consent in the moment.",
                        confirmLabel = "Disable approvals",
                        action = action,
                    ),
                )
            }
        }
    }

    private fun commitApprovalsRequired(value: Boolean) {
        _state.update { it.copy(approvalsRequired = value, pendingWarning = null) }
        viewModelScope.launch {
            settings.setApprovalsRequired(value)
            logBuffer.warn(TAG, "Approvals required = $value")
        }
    }

    fun setPrivacyLocalOnlyMemory(value: Boolean) {
        _state.update { it.copy(privacyLocalOnlyMemory = value) }
        viewModelScope.launch { settings.setPrivacyLocalOnlyMemory(value) }
    }

    fun confirmPendingWarning() {
        val pending = _state.value.pendingWarning ?: return
        when (val action = pending.action) {
            ControlWarnings.Action.DisableApprovals -> commitApprovalsRequired(false)
            ControlWarnings.Action.EnableApprovals -> commitApprovalsRequired(true)
            ControlWarnings.Action.ToggleMockMode -> commitMockMode(!_state.value.mockMode)
            ControlWarnings.Action.ToggleTermuxGateway -> commitTermuxGatewayMode(!_state.value.termuxGatewayMode)
            is ControlWarnings.Action.GatewayEndpointChange -> {
                val target = _state.value.pendingGatewayEndpoint ?: action.to
                commitGatewayEndpoint(target)
            }
            else -> dismissPendingWarning()
        }
    }

    fun dismissPendingWarning() {
        _state.update { it.copy(pendingWarning = null, pendingGatewayEndpoint = null) }
    }

    fun resetAll() {
        viewModelScope.launch {
            settings.resetAll()
            tasks.deleteAll()
            logBuffer.warn("Settings", "User reset all orchestrator settings and tasks")
            val snap = settings.snapshot()
            _state.value = SettingsUiState(
                themeMode = snap.themeMode,
                preferredBuilder = snap.preferredBuilder,
                preferredReviewer = snap.preferredReviewer,
                useApiKeys = snap.useApiKeys,
                localOnlyMode = snap.localOnlyMode,
                allowExternalAppOpening = snap.allowExternalAppOpening,
                clipboardHandoffEnabled = snap.clipboardHandoffEnabled,
                showSafetyWarnings = snap.showSafetyWarnings,
                responseLength = snap.responseLength,
                mobileMode = snap.mobileMode,
                notificationsEnabled = snap.notificationsEnabled,
                voiceEnabled = snap.voiceEnabled,
                interactiveIconEnabled = snap.interactiveIconEnabled,
                gatewayEndpoint = snap.gatewayEndpoint,
                mockMode = snap.mockMode,
                termuxGatewayMode = snap.termuxGatewayMode,
                approvalsRequired = snap.approvalsRequired,
                privacyLocalOnlyMemory = snap.privacyLocalOnlyMemory,
                autonomyMode = snap.autonomyMode,
            )
        }
    }

    companion object {
        const val TAG = "SettingsVm"
    }
}
