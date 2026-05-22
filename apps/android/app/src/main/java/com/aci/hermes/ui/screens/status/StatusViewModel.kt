package com.aci.hermes.ui.screens.status

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.model.ConnectionState
import com.aci.hermes.data.network.HermesClientFactory
import com.aci.hermes.data.preferences.SettingsRepository
import com.aci.hermes.util.LogBuffer
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class StatusUiState(
    val gatewayUrl: String = "",
    val providerId: String = "",
    val mockMode: Boolean = false,
    val connection: ConnectionState = ConnectionState.Unknown
)

class StatusViewModel(
    private val settings: SettingsRepository,
    private val clientFactory: HermesClientFactory,
    private val logBuffer: LogBuffer
) : ViewModel() {

    private val _state = MutableStateFlow(StatusUiState())
    val state: StateFlow<StatusUiState> = _state.asStateFlow()

    init { refresh() }

    fun refresh() {
        _state.update { it.copy(connection = ConnectionState.Connecting) }
        viewModelScope.launch {
            val snap = settings.snapshot()
            _state.update {
                it.copy(
                    gatewayUrl = snap.gatewayUrl,
                    providerId = snap.providerId,
                    mockMode = snap.mockMode
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
}
