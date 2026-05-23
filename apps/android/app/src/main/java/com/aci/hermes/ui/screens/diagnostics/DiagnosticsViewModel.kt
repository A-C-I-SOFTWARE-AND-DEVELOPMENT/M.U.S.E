package com.aci.hermes.ui.screens.diagnostics

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.BuildConfig
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
    val logs: List<LogBuffer.Entry> = emptyList(),
    val lastError: LogBuffer.Entry? = null,
)

class DiagnosticsViewModel(
    private val logBuffer: LogBuffer,
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
    }

    fun refresh() {
        // Nothing to refresh now that we don't poll a backend, but kept
        // so the UI's refresh icon stays meaningful for future use.
        _state.update { it.copy() }
    }

    fun clearLogs() = logBuffer.clear()
}
