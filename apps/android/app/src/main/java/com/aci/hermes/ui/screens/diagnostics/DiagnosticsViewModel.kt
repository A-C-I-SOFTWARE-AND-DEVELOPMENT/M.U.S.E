package com.aci.hermes.ui.screens.diagnostics

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.BuildConfig
import com.aci.hermes.data.cockpit.CockpitDiagnostics
import com.aci.hermes.data.cockpit.CockpitResult
import com.aci.hermes.data.cockpit.HermesCockpitClient
import com.aci.hermes.util.LogBuffer
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/** Sync state of the backend launch-readiness report (honest, never faked). */
sealed interface BackendDiagnosticsSync {
    data object Idle : BackendDiagnosticsSync
    data object Loading : BackendDiagnosticsSync
    data object NotPaired : BackendDiagnosticsSync
    data class Loaded(val report: CockpitDiagnostics) : BackendDiagnosticsSync
    data class Error(val message: String) : BackendDiagnosticsSync
}

data class DiagnosticsUiState(
    val appVersion: String = "${BuildConfig.VERSION_NAME} (${BuildConfig.VERSION_CODE})",
    val buildType: String = BuildConfig.BUILD_TYPE,
    val logs: List<LogBuffer.Entry> = emptyList(),
    val lastError: LogBuffer.Entry? = null,
    val backend: BackendDiagnosticsSync = BackendDiagnosticsSync.Idle,
)

class DiagnosticsViewModel(
    private val logBuffer: LogBuffer,
    private val cockpitClient: HermesCockpitClient? = null,
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

    /** Pull the backend's launch-readiness report; honest states, never faked. */
    fun refresh() {
        val client = cockpitClient ?: return
        viewModelScope.launch {
            if (!client.isPaired()) {
                _state.update { it.copy(backend = BackendDiagnosticsSync.NotPaired) }
                return@launch
            }
            _state.update { it.copy(backend = BackendDiagnosticsSync.Loading) }
            val next = when (val res = client.diagnostics()) {
                is CockpitResult.Success -> BackendDiagnosticsSync.Loaded(res.value)
                is CockpitResult.Failure ->
                    BackendDiagnosticsSync.Error("Gateway error ${res.httpStatus}: ${res.error.message}")
                is CockpitResult.Unreachable -> BackendDiagnosticsSync.Error(res.message)
            }
            _state.update { it.copy(backend = next) }
        }
    }

    fun clearLogs() = logBuffer.clear()
}
