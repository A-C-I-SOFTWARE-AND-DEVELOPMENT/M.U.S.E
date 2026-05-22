package com.aci.hermes.ui.screens.settings

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.preferences.SettingsRepository
import com.aci.hermes.data.preferences.ThemeMode
import com.aci.hermes.util.LogBuffer
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class SettingsUiState(
    val gatewayUrl: String = "",
    val providerId: String = "",
    val mockMode: Boolean = false,
    val themeMode: ThemeMode = ThemeMode.SYSTEM
)

class SettingsViewModel(
    private val settings: SettingsRepository,
    private val logBuffer: LogBuffer
) : ViewModel() {

    private val _state = MutableStateFlow(SettingsUiState())
    val state: StateFlow<SettingsUiState> = _state.asStateFlow()

    init {
        viewModelScope.launch {
            val snap = settings.snapshot()
            _state.value = SettingsUiState(
                gatewayUrl = snap.gatewayUrl,
                providerId = snap.providerId,
                mockMode = snap.mockMode,
                themeMode = snap.themeMode
            )
        }
    }

    fun setThemeMode(mode: ThemeMode) {
        _state.update { it.copy(themeMode = mode) }
        viewModelScope.launch { settings.setThemeMode(mode) }
    }

    fun setMockMode(enabled: Boolean) {
        _state.update { it.copy(mockMode = enabled) }
        viewModelScope.launch { settings.setMockMode(enabled) }
    }

    fun resetAll() {
        viewModelScope.launch {
            settings.resetAll()
            logBuffer.warn("Settings", "User reset all settings")
            val snap = settings.snapshot()
            _state.value = SettingsUiState(
                gatewayUrl = snap.gatewayUrl,
                providerId = snap.providerId,
                mockMode = snap.mockMode,
                themeMode = snap.themeMode
            )
        }
    }
}
