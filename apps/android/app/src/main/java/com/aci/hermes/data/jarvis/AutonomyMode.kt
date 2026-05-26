package com.aci.hermes.data.jarvis

/**
 * Owner-controlled autonomy level for Jarvis Prime.
 *
 * The mode gates whether Jarvis runs steps directly, asks first,
 * or refuses any external action at all (Lockdown). It is read by
 * the Control screen, the gateway bridge, and any future automation
 * surface. Changing the mode is always a deliberate owner action
 * — never reset implicitly by the runtime.
 */
enum class AutonomyMode {
    MANUAL,
    ASSISTED,
    TRUSTED_LOW_RISK,
    LOCKDOWN;

    val displayName: String
        get() = when (this) {
            MANUAL -> "Manual"
            ASSISTED -> "Assisted"
            TRUSTED_LOW_RISK -> "Trusted (low risk)"
            LOCKDOWN -> "Lockdown"
        }

    val summary: String
        get() = when (this) {
            MANUAL -> "Jarvis only acts when you tap a step."
            ASSISTED -> "Jarvis proposes; each action waits for owner approval."
            TRUSTED_LOW_RISK -> "Jarvis runs low-risk steps; destructive actions still require approval."
            LOCKDOWN -> "Jarvis is paused. No external actions, no handoffs, no automation."
        }

    /**
     * Lockdown disables every outbound action, including emergency
     * stop side effects that depend on the gateway. The Control
     * screen uses this to grey out controls.
     */
    val isLockdown: Boolean get() = this == LOCKDOWN

    companion object {
        fun fromName(name: String?): AutonomyMode =
            entries.firstOrNull { it.name == name } ?: MANUAL
    }
}
