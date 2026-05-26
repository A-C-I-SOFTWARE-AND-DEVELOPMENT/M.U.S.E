package com.aci.hermes.ui.screens.settings

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.orchestrator.HermesTaskRepository
import com.aci.hermes.data.preferences.GatewayPreference
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
    val gatewayMode: GatewayPreference = GatewayPreference.MOCK,
    val statusNotificationOptIn: Boolean = false,
    val doubleConfirmSerious: Boolean = true,
    val criticalPhraseRequired: Boolean = true,
    val voiceTapRequired: Boolean = true,
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
            refreshFromSnapshot()
        }
    }

    private suspend fun refreshFromSnapshot() {
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
            mockMode = snap.mockMode,
            gatewayMode = snap.gatewayMode,
            statusNotificationOptIn = snap.statusNotificationOptIn,
            doubleConfirmSerious = snap.doubleConfirmSerious,
            criticalPhraseRequired = snap.criticalPhraseRequired,
            voiceTapRequired = snap.voiceTapRequired,
        )
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

    fun setMockMode(value: Boolean) {
        _state.update { it.copy(mockMode = value) }
        viewModelScope.launch { settings.setMockMode(value) }
    }

    fun setGatewayMode(value: GatewayPreference) {
        _state.update { it.copy(gatewayMode = value) }
        viewModelScope.launch { settings.setGatewayMode(value) }
    }

    fun setStatusNotificationOptIn(value: Boolean) {
        _state.update { it.copy(statusNotificationOptIn = value) }
        viewModelScope.launch { settings.setStatusNotificationOptIn(value) }
    }

    fun setDoubleConfirmSerious(value: Boolean) {
        _state.update { it.copy(doubleConfirmSerious = value) }
        viewModelScope.launch { settings.setDoubleConfirmSerious(value) }
    }

    fun setCriticalPhraseRequired(value: Boolean) {
        _state.update { it.copy(criticalPhraseRequired = value) }
        viewModelScope.launch { settings.setCriticalPhraseRequired(value) }
    }

    fun replayOnboarding() {
        viewModelScope.launch { settings.setOnboarded(false) }
    }

    fun resetAll() {
        viewModelScope.launch {
            settings.resetAll()
            tasks.deleteAll()
            logBuffer.warn("Settings", "User reset all settings and tasks")
            refreshFromSnapshot()
        }
    }
}
