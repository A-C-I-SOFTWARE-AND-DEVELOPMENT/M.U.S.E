package com.aci.hermes.ui.screens.gateway

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.gateway.GatewayEventBus
import com.aci.hermes.data.model.GatewayConnectionState
import com.aci.hermes.data.model.GatewayEvent
import com.aci.hermes.data.model.GatewayMode
import com.aci.hermes.data.preferences.GatewayPreference
import com.aci.hermes.data.preferences.SettingsRepository
import com.aci.hermes.data.termux.TermuxIntentBridge
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class GatewayUiState(
    val mode: GatewayMode = GatewayMode.MOCK,
    val connection: GatewayConnectionState = GatewayConnectionState.DISCONNECTED,
    val events: List<GatewayEvent> = emptyList(),
    val termuxInstalled: Boolean = false,
)

class GatewayViewModel(
    application: Application,
    private val gateway: GatewayEventBus,
    private val termux: TermuxIntentBridge,
    private val settings: SettingsRepository,
) : AndroidViewModel(application) {

    private val _state = MutableStateFlow(GatewayUiState(termuxInstalled = termux.isTermuxInstalled()))
    val state: StateFlow<GatewayUiState> = _state.asStateFlow()

    init {
        viewModelScope.launch {
            gateway.events.collect { list ->
                _state.update { it.copy(events = list) }
            }
        }
        viewModelScope.launch {
            gateway.mode.collect { mode ->
                _state.update { it.copy(mode = mode) }
            }
        }
        viewModelScope.launch {
            gateway.connection.collect { c ->
                _state.update { it.copy(connection = c) }
            }
        }
        viewModelScope.launch {
            settings.gatewayMode.collect { pref ->
                val mode = when (pref) {
                    GatewayPreference.MOCK -> GatewayMode.MOCK
                    GatewayPreference.TERMUX -> GatewayMode.TERMUX
                    GatewayPreference.REMOTE -> GatewayMode.REMOTE
                }
                gateway.setMode(mode)
            }
        }
    }

    fun setMode(mode: GatewayMode) {
        gateway.setMode(mode)
        viewModelScope.launch {
            settings.setGatewayMode(when (mode) {
                GatewayMode.MOCK -> GatewayPreference.MOCK
                GatewayMode.TERMUX -> GatewayPreference.TERMUX
                GatewayMode.REMOTE -> GatewayPreference.REMOTE
            })
        }
    }

    fun clearEvents() {
        viewModelScope.launch { gateway.clear() }
    }
}
