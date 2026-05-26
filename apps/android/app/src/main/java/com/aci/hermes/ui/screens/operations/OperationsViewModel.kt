package com.aci.hermes.ui.screens.operations

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.events.EventSpine
import com.aci.hermes.events.JarvisEvent
import com.aci.hermes.gateway.GatewayState
import com.aci.hermes.gateway.JarvisGatewayClient
import com.aci.hermes.workers.WorkerLane
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.launch

data class OperationsUiState(
    val gateway: GatewayState = GatewayState(),
    val lanes: List<WorkerLane> = emptyList(),
    val recent: List<JarvisEvent> = emptyList(),
    val refreshing: Boolean = false,
)

class OperationsViewModel(
    private val client: JarvisGatewayClient,
    private val spine: EventSpine,
) : ViewModel() {

    private val _state = MutableStateFlow(OperationsUiState())
    val state: StateFlow<OperationsUiState> = _state.asStateFlow()

    init {
        viewModelScope.launch {
            combine(client.state, spine.events) { gw, events ->
                OperationsUiState(
                    gateway = gw,
                    lanes = gw.workers.map { WorkerLane.fromDetected(it) },
                    recent = events.takeLast(15).asReversed(),
                )
            }.collect { _state.value = it }
        }
    }

    fun refresh() {
        viewModelScope.launch {
            _state.value = _state.value.copy(refreshing = true)
            client.refresh()
            _state.value = _state.value.copy(refreshing = false)
        }
    }
}
