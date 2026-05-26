package com.aci.hermes.ui.screens.home

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.approval.ApprovalRepository
import com.aci.hermes.data.audit.AuditRepository
import com.aci.hermes.data.emergency.EmergencyStopController
import com.aci.hermes.data.gateway.GatewayEventBus
import com.aci.hermes.data.memory.MemoryRepository
import com.aci.hermes.data.model.ApprovalCard
import com.aci.hermes.data.model.ApprovalStatus
import com.aci.hermes.data.model.AuditEntry
import com.aci.hermes.data.model.GatewayConnectionState
import com.aci.hermes.data.model.HermesTask
import com.aci.hermes.data.model.JarvisNotification
import com.aci.hermes.data.model.SocialPattern
import com.aci.hermes.data.model.TaskStatus
import com.aci.hermes.data.notifications.JarvisNotificationRepository
import com.aci.hermes.data.orchestrator.HermesTaskRepository
import com.aci.hermes.data.preferences.SettingsRepository
import com.aci.hermes.data.social.SocialPatternRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.util.Calendar

enum class HomeStatus { IDLE, ACTIVE, WAITING, PAUSED }

data class HomeUiState(
    val greeting: String = "",
    val status: HomeStatus = HomeStatus.IDLE,
    val mockMode: Boolean = true,
    val pendingApprovals: List<ApprovalCard> = emptyList(),
    val activeTasks: List<HermesTask> = emptyList(),
    val unreadNotifications: List<JarvisNotification> = emptyList(),
    val recentAudit: List<AuditEntry> = emptyList(),
    val activePatterns: List<SocialPattern> = emptyList(),
    val gatewayConnection: GatewayConnectionState = GatewayConnectionState.DISCONNECTED,
    val emergencyEngaged: Boolean = false,
)

class HomeViewModel(
    application: Application,
    private val settings: SettingsRepository,
    private val approvals: ApprovalRepository,
    private val tasks: HermesTaskRepository,
    private val audit: AuditRepository,
    private val notifications: JarvisNotificationRepository,
    private val social: SocialPatternRepository,
    private val memory: MemoryRepository,
    private val gateway: GatewayEventBus,
    private val emergencyStop: EmergencyStopController,
) : AndroidViewModel(application) {

    private val _state = MutableStateFlow(HomeUiState(greeting = greetingFor(Calendar.getInstance())))
    val state: StateFlow<HomeUiState> = _state.asStateFlow()

    init {
        viewModelScope.launch {
            combine(
                approvals.items,
                tasks.tasks,
                notifications.items,
                audit.items,
                social.items,
            ) { aps, tks, nots, aud, soc ->
                Quintuple(aps, tks, nots, aud, soc)
            }.collect { (aps, tks, nots, aud, soc) ->
                _state.update {
                    it.copy(
                        pendingApprovals = aps.filter { c -> c.status == ApprovalStatus.PENDING }.take(3),
                        activeTasks = tks.filter { t ->
                            t.status != TaskStatus.COMPLETE
                        }.take(3),
                        unreadNotifications = nots.filterNot { n -> n.read }.take(3),
                        recentAudit = aud.take(3),
                        activePatterns = soc.filterNot { p -> p.dismissed }.take(2),
                    )
                }
                refreshStatus()
            }
        }
        viewModelScope.launch {
            settings.mockMode.collect { mock ->
                _state.update { it.copy(mockMode = mock) }
            }
        }
        viewModelScope.launch {
            gateway.connection.collect { state ->
                _state.update { it.copy(gatewayConnection = state) }
            }
        }
        viewModelScope.launch {
            emergencyStop.state.collect { es ->
                _state.update { it.copy(emergencyEngaged = es.engaged) }
                refreshStatus()
            }
        }
    }

    fun engageEmergencyStop(reason: String? = null) {
        emergencyStop.engage(reason)
    }

    private fun refreshStatus() {
        _state.update {
            val newStatus = when {
                it.emergencyEngaged -> HomeStatus.PAUSED
                it.pendingApprovals.isNotEmpty() -> HomeStatus.WAITING
                it.activeTasks.isNotEmpty() -> HomeStatus.ACTIVE
                else -> HomeStatus.IDLE
            }
            it.copy(status = newStatus)
        }
    }

    private fun greetingFor(cal: Calendar): String {
        val hour = cal.get(Calendar.HOUR_OF_DAY)
        return when {
            hour < 12 -> "morning"
            hour < 18 -> "afternoon"
            else -> "evening"
        }
    }
}

private data class Quintuple<A, B, C, D, E>(
    val first: A, val second: B, val third: C, val fourth: D, val fifth: E,
)
