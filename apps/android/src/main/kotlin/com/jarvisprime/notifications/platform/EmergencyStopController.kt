package com.jarvisprime.notifications.platform

/**
 * Platform abstraction for the Jarvis Prime emergency stop. The Android binding
 * issues a signed local broadcast that the running JARVIS worker is contracted
 * to honour within one second, plus a server-side cancel via the gateway.
 *
 * Emergency stop is a destructive cross-system action — implementations MUST
 * be idempotent and MUST report the active status back so the UI cannot
 * silently disagree with the worker state.
 */
interface EmergencyStopController {
    fun isActive(): Boolean
    fun trigger(reason: String): EmergencyStopResult
}

sealed class EmergencyStopResult {
    object Triggered : EmergencyStopResult()
    object AlreadyActive : EmergencyStopResult()
    data class Failed(val reason: String) : EmergencyStopResult()
}
