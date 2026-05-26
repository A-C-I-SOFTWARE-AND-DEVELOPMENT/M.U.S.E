package com.aci.hermes.ui.screens.settings

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
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
    val mockMode: Boolean = true,
    val termuxMode: Boolean = false,
    val emergencyStopArmed: Boolean = false,
    val notificationEducation: Boolean = true,
)

class SettingsViewModel(
    private val settings: SettingsRepository,
    private val tasks: HermesTaskRepository,
    private val logBuffer: LogBuffer,
) : ViewModel() {

    private val _state = MutableStateFlow(SettingsUiState())
    val state: StateFlow<SettingsUiState> = _state.asStateFlow()

    init {
        viewModelScope.launch { refresh() }
        viewModelScope.launch {
            settings.mockMode.collect { v -> _state.update { it.copy(mockMode = v) } }
        }
        viewModelScope.launch {
            settings.termuxMode.collect { v -> _state.update { it.copy(termuxMode = v) } }
        }
        viewModelScope.launch {
            settings.emergencyStop.collect { v -> _state.update { it.copy(emergencyStopArmed = v) } }
        }
        viewModelScope.launch {
            settings.notificationEducation.collect { v ->
                _state.update { it.copy(notificationEducation = v) }
            }
        }
    }

    private suspend fun refresh() {
        val snap = settings.snapshot()
        _state.update {
            it.copy(
                themeMode = snap.themeMode,
                preferredBuilder = snap.preferredBuilder,
                preferredReviewer = snap.preferredReviewer,
                useApiKeys = snap.useApiKeys,
                localOnlyMode = snap.localOnlyMode,
                allowExternalAppOpening = snap.allowExternalAppOpening,
                clipboardHandoffEnabled = snap.clipboardHandoffEnabled,
                showSafetyWarnings = snap.showSafetyWarnings,
            )
        }
    }

    fun setMockMode(value: Boolean) {
        _state.update { it.copy(mockMode = value) }
        viewModelScope.launch { settings.setMockMode(value) }
    }

    fun setTermuxMode(value: Boolean) {
        _state.update { it.copy(termuxMode = value) }
        viewModelScope.launch { settings.setTermuxMode(value) }
    }

    fun setEmergencyStop(value: Boolean) {
        _state.update { it.copy(emergencyStopArmed = value) }
        viewModelScope.launch { settings.setEmergencyStop(value) }
    }

    fun setNotificationEducation(value: Boolean) {
        _state.update { it.copy(notificationEducation = value) }
        viewModelScope.launch { settings.setNotificationEducation(value) }
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

    fun resetAll() {
        viewModelScope.launch {
            settings.resetAll()
            tasks.deleteAll()
            logBuffer.warn("Settings", "User reset all Jarvis Prime settings and tasks")
            refresh()
        }
    }
}
