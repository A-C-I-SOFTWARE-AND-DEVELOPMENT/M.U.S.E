package com.aci.hermes.safety

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update

/**
 * Jarvis Prime Emergency Stop.
 *
 * Always reachable. Triggering it must:
 *
 *   1. Halt any in-flight worker run by signalling the gateway.
 *   2. Cancel every pending approval (mark as REJECTED_BY_EMERGENCY_STOP).
 *   3. Stop the foreground service.
 *   4. Record a single tombstone entry in the audit log.
 *
 * The controller itself is platform-agnostic — it accepts a list of
 * [Listener]s wired up at startup. The Service, the approval store,
 * and the audit log each register one listener. This means the stop
 * surface in the UI does not have to know about every subsystem; new
 * listeners can be added without touching the UI.
 */
class EmergencyStop {

    /**
     * A subsystem that needs to wind down when the stop is engaged.
     * Listeners are called sequentially in registration order; failure
     * of one listener does not block subsequent listeners.
     */
    fun interface Listener {
        fun onEmergencyStop(reason: String)
    }

    private val listeners = mutableListOf<Listener>()

    private val _engaged = MutableStateFlow(false)
    val engaged: StateFlow<Boolean> = _engaged.asStateFlow()

    private val _lastReason = MutableStateFlow<String?>(null)
    val lastReason: StateFlow<String?> = _lastReason.asStateFlow()

    @Synchronized
    fun register(listener: Listener) {
        listeners += listener
    }

    @Synchronized
    fun unregister(listener: Listener) {
        listeners -= listener
    }

    /**
     * Engage the stop. Idempotent — engaging while already engaged is a
     * no-op so accidental double-taps cannot multi-fire listeners.
     *
     * @return the count of listeners notified.
     */
    @Synchronized
    fun engage(reason: String): Int {
        if (_engaged.value) return 0
        _engaged.update { true }
        _lastReason.update { reason }
        var notified = 0
        for (listener in listeners.toList()) {
            try {
                listener.onEmergencyStop(reason)
                notified++
            } catch (t: Throwable) {
                // Swallow — Emergency Stop must not itself crash the app.
                // The audit listener will record the failure separately.
            }
        }
        return notified
    }

    /** Reset for tests and for the user to re-arm Jarvis Prime after a stop. */
    @Synchronized
    fun reset() {
        _engaged.update { false }
        _lastReason.update { null }
    }
}
