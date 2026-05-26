package com.aci.hermes.data.emergency

import com.aci.hermes.data.approval.ApprovalRepository
import com.aci.hermes.data.audit.AuditRepository
import com.aci.hermes.data.gateway.GatewayEventBus
import com.aci.hermes.data.model.AuditKind
import com.aci.hermes.data.model.EmergencyStopState
import com.aci.hermes.data.model.GatewayConnectionState
import com.aci.hermes.data.model.JarvisNotificationKind
import com.aci.hermes.data.notifications.JarvisNotificationRepository
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

/**
 * Emergency Stop — single source of truth for "halt everything".
 *
 * When engaged:
 *  - all pending approvals are cancelled
 *  - the gateway is marked disconnected
 *  - the audit log records the engagement
 *  - the in-app notification center pings the user
 *
 * Released by an explicit user action only.
 */
class EmergencyStopController(
    private val approvalRepository: ApprovalRepository,
    private val gateway: GatewayEventBus,
    private val audit: AuditRepository,
    private val notifications: JarvisNotificationRepository,
) {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    private val _state = MutableStateFlow(EmergencyStopState())
    val state: StateFlow<EmergencyStopState> = _state.asStateFlow()

    fun engage(reason: String? = null) {
        if (_state.value.engaged) return
        val now = System.currentTimeMillis()
        _state.value = EmergencyStopState(
            engaged = true,
            engagedAt = now,
            reason = reason,
        )
        scope.launch {
            approvalRepository.cancelAllPending(reason ?: "Emergency stop engaged")
            gateway.setConnection(GatewayConnectionState.DISCONNECTED)
            audit.record(
                kind = AuditKind.EMERGENCY_STOP_ENGAGED,
                title = "Emergency stop engaged",
                detail = reason ?: "User engaged the emergency stop. All pending approvals cancelled. Gateway disconnected.",
            )
            notifications.add(
                kind = JarvisNotificationKind.EMERGENCY,
                title = "Emergency stop engaged",
                body = "Jarvis Prime has paused all work. Release when ready.",
            )
        }
    }

    fun release() {
        if (!_state.value.engaged) return
        val now = System.currentTimeMillis()
        _state.value = _state.value.copy(
            engaged = false,
            releasedAt = now,
        )
        scope.launch {
            audit.record(
                kind = AuditKind.EMERGENCY_STOP_RELEASED,
                title = "Emergency stop released",
                detail = "User released the emergency stop. Operations resumed.",
            )
            notifications.add(
                kind = JarvisNotificationKind.INFO,
                title = "Emergency stop released",
                body = "Jarvis Prime is operational again.",
            )
        }
    }
}
