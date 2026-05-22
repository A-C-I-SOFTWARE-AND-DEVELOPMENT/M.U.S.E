package com.aci.hermes.ui.screens.status

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.model.ConnectionState
import com.aci.hermes.data.network.AIClientFactory
import com.aci.hermes.data.preferences.ConnectionMode
import com.aci.hermes.data.preferences.SettingsRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class StatusUiState(
    val mode: ConnectionMode = ConnectionMode.MOCK,
    val gatewayUrl: String = "",
    val providerId: String = "",
    val model: String = "",
    val connection: ConnectionState = ConnectionState.Unknown
)

class StatusViewModel(
    private val settings: SettingsRepository,
    private val clientFactory: AIClientFactory
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
                    mode = snap.connectionMode,
                    gatewayUrl = snap.gatewayUrl,
                    providerId = snap.providerId,
                    model = snap.model
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
