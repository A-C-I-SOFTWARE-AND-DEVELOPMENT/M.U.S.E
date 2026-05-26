package com.aci.hermes.ui.screens.settings

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.gateway.GatewayController
import com.aci.hermes.data.orchestrator.HermesTaskRepository
import com.aci.hermes.data.preferences.GatewayModePref
import com.aci.hermes.data.preferences.PreferredBuilder
import com.aci.hermes.data.preferences.PreferredReviewer
import com.aci.hermes.data.preferences.SettingsRepository
import com.aci.hermes.data.preferences.ThemeMode
import com.aci.hermes.di.toGatewayMode
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
    val gatewayMode: GatewayModePref = GatewayModePref.MOCK,
)

class SettingsViewModel(
    private val settings: SettingsRepository,
    private val tasks: HermesTaskRepository,
    private val gatewayController: GatewayController,
    private val logBuffer: LogBuffer,
) : ViewModel() {

    private val _state = MutableStateFlow(SettingsUiState())
    val state: StateFlow<SettingsUiState> = _state.asStateFlow()

    init {
        viewModelScope.launch {
            _state.value = settings.snapshot().toUi()
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

    fun setGatewayMode(value: GatewayModePref) {
        _state.update { it.copy(gatewayMode = value) }
        viewModelScope.launch {
            settings.setGatewayMode(value)
            gatewayController.switchMode(value.toGatewayMode())
            logBuffer.info("Settings", "Gateway mode set to ${value.name}")
        }
    }

    fun resetAll() {
        viewModelScope.launch {
            settings.resetAll()
            tasks.deleteAll()
            logBuffer.warn("Settings", "User reset all orchestrator settings and tasks")
            _state.value = settings.snapshot().toUi()
            gatewayController.switchMode(_state.value.gatewayMode.toGatewayMode())
        }
    }

    private fun SettingsRepository.Snapshot.toUi(): SettingsUiState = SettingsUiState(
        themeMode = themeMode,
        preferredBuilder = preferredBuilder,
        preferredReviewer = preferredReviewer,
        useApiKeys = useApiKeys,
        localOnlyMode = localOnlyMode,
        allowExternalAppOpening = allowExternalAppOpening,
        clipboardHandoffEnabled = clipboardHandoffEnabled,
        showSafetyWarnings = showSafetyWarnings,
        gatewayMode = gatewayMode,
    )
}
