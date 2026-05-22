package com.aci.hermes.ui.screens.diagnostics

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.BuildConfig
import com.aci.hermes.data.model.ConnectionState
import com.aci.hermes.data.network.AIClientFactory
import com.aci.hermes.data.preferences.ConnectionMode
import com.aci.hermes.data.preferences.SettingsRepository
import com.aci.hermes.util.LogBuffer
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class DiagnosticsUiState(
    val appVersion: String = "${BuildConfig.VERSION_NAME} (${BuildConfig.VERSION_CODE})",
    val buildType: String = BuildConfig.BUILD_TYPE,
    val mode: ConnectionMode = ConnectionMode.MOCK,
    val providerId: String = "",
    val gatewayUrl: String = "",
    val customApiBaseUrl: String = "",
    val connection: ConnectionState = ConnectionState.Unknown,
    val logs: List<LogBuffer.Entry> = emptyList(),
    val lastError: LogBuffer.Entry? = null
)

class DiagnosticsViewModel(
    private val settings: SettingsRepository,
    private val clientFactory: AIClientFactory,
    private val logBuffer: LogBuffer
) : ViewModel() {

    private val _state = MutableStateFlow(DiagnosticsUiState())
    val state: StateFlow<DiagnosticsUiState> = _state.asStateFlow()

    init {
        viewModelScope.launch {
            logBuffer.entries.combine(logBuffer.lastError) { entries, err -> entries to err }
                .collect { (entries, err) ->
                    _state.update { it.copy(logs = entries, lastError = err) }
                }
        }
        refresh()
    }

    fun refresh() {
        _state.update { it.copy(connection = ConnectionState.Connecting) }
        viewModelScope.launch {
            val snap = settings.snapshot()
            _state.update {
                it.copy(
                    mode = snap.connectionMode,
                    providerId = snap.providerId,
                    gatewayUrl = snap.gatewayUrl,
                    customApiBaseUrl = snap.customApiBaseUrl
                )
            }
            val client = clientFactory.current()
            val status = client.status()
            _state.update {
                if (status.ok) it.copy(connection = ConnectionState.Connected(status))
                else it.copy(connection = ConnectionState.Failed(status.message ?: "Unknown error"))
            }
        }
    }

    fun clearLogs() = logBuffer.clear()
}
