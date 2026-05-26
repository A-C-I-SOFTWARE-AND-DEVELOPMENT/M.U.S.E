package com.aci.hermes.ui.screens.home

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.approvals.ApprovalRepository
import com.aci.hermes.data.audit.AuditRepository
import com.aci.hermes.data.emergency.EmergencyStopController
import com.aci.hermes.data.emergency.EmergencyStopState
import com.aci.hermes.data.gateway.ConnectionState
import com.aci.hermes.data.gateway.GatewayClient
import com.aci.hermes.data.gateway.GatewayEventSpine
import com.aci.hermes.data.gateway.GatewayMode
import com.aci.hermes.data.model.AuditEvent
import com.aci.hermes.data.model.GatewayEvent
import com.aci.hermes.data.preferences.SettingsRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class HomeUiState(
    val pendingApprovals: Int = 0,
    val connection: ConnectionState = ConnectionState.Disconnected,
    val mode: GatewayMode = GatewayMode.DISCONNECTED,
    val emergency: EmergencyStopState = EmergencyStopState(),
    val notificationEducation: Boolean = true,
    val notificationsGranted: Boolean = false,
    val recentEvents: List<GatewayEvent> = emptyList(),
)

class HomeViewModel(
    private val approvals: ApprovalRepository,
    private val audit: AuditRepository,
    private val emergency: EmergencyStopController,
    private val spine: GatewayEventSpine,
    private val settings: SettingsRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(HomeUiState())
    val state: StateFlow<HomeUiState> = _state.asStateFlow()

    init {
        viewModelScope.launch {
            approvals.items.collect { list ->
                _state.update { it.copy(pendingApprovals = list.count { a -> a.isPending }) }
            }
        }
        viewModelScope.launch {
            spine.connection.collect { conn -> _state.update { it.copy(connection = conn) } }
        }
        viewModelScope.launch {
            spine.activeMode.collect { m -> _state.update { it.copy(mode = m) } }
        }
        viewModelScope.launch {
            emergency.state.collect { e -> _state.update { it.copy(emergency = e) } }
        }
        viewModelScope.launch {
            settings.notificationEducation.collect { edu ->
                _state.update { it.copy(notificationEducation = edu) }
            }
        }
        viewModelScope.launch {
            spine.events().collect { ev ->
                _state.update { current ->
                    current.copy(recentEvents = (listOf(ev) + current.recentEvents).take(10))
                }
            }
        }
    }

    fun setNotificationsGranted(value: Boolean) {
        _state.update { it.copy(notificationsGranted = value) }
    }

    fun armEmergencyStop(reason: String?): AuditEvent {
        val ev = emergency.arm(reason)
        viewModelScope.launch { settings.setEmergencyStop(true) }
        return audit.append(ev)
    }

    fun clearEmergencyStop(reason: String?): AuditEvent {
        val ev = emergency.clear(reason)
        viewModelScope.launch { settings.setEmergencyStop(false) }
        return audit.append(ev)
    }

    suspend fun dismissNotificationEducation() {
        settings.setNotificationEducation(false)
    }

    fun activeClient(): GatewayClient? = spine.current()
}
