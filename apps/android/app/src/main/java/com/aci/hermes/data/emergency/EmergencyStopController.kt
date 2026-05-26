package com.aci.hermes.data.emergency

import com.aci.hermes.data.model.AuditEvent
import com.aci.hermes.data.model.AuditSeverity
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * In-memory kill switch shared across screens. Pure Kotlin so it's
 * trivial to test. The persistence side of the switch (so the state
 * survives a process kill) lives in [com.aci.hermes.data.preferences.SettingsRepository].
 */
class EmergencyStopController {

    private val _state = MutableStateFlow(EmergencyStopState())
    val state: StateFlow<EmergencyStopState> = _state.asStateFlow()

    fun arm(reason: String?): AuditEvent {
        val now = System.currentTimeMillis()
        _state.value = EmergencyStopState(armed = true, since = now, reason = reason?.take(180))
        return AuditEvent(
            actor = "user",
            action = "emergency_stop_arm",
            target = "global",
            payloadSummary = reason?.take(120).orEmpty(),
            severity = AuditSeverity.CRITICAL,
            createdAt = now,
            proofHash = proof("arm", now, reason),
        )
    }

    fun clear(reason: String?): AuditEvent {
        val now = System.currentTimeMillis()
        _state.value = EmergencyStopState(armed = false, since = null, reason = null)
        return AuditEvent(
            actor = "user",
            action = "emergency_stop_clear",
            target = "global",
            payloadSummary = reason?.take(120).orEmpty(),
            severity = AuditSeverity.NOTICE,
            createdAt = now,
            proofHash = proof("clear", now, reason),
        )
    }

    fun isArmed(): Boolean = _state.value.armed

    private fun proof(kind: String, at: Long, reason: String?): String {
        val seed = "$kind|$at|${reason ?: ""}".hashCode()
        return "0x" + kotlin.math.abs(seed.toLong()).toString(16).padStart(8, '0')
    }
}

data class EmergencyStopState(
    val armed: Boolean = false,
    val since: Long? = null,
    val reason: String? = null,
)
