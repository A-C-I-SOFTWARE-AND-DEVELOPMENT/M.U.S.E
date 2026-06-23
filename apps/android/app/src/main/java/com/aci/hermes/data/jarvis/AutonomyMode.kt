package com.aci.hermes.data.jarvis

/**
 * Owner-controlled autonomy level for muse
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
    OWNER_HIGH_AUTONOMY_CODING,
    LOCKDOWN;

    val displayName: String
        get() = when (this) {
            MANUAL -> "Manual"
            ASSISTED -> "Assisted"
            TRUSTED_LOW_RISK -> "Trusted (low risk)"
            OWNER_HIGH_AUTONOMY_CODING -> "High-Autonomy Coding"
            LOCKDOWN -> "Lockdown"
        }

    val summary: String
        get() = when (this) {
            MANUAL -> "Jarvis only acts when you tap a step."
            ASSISTED -> "Jarvis proposes; each action waits for owner approval."
            TRUSTED_LOW_RISK -> "Jarvis runs low-risk steps; destructive actions still require approval."
            OWNER_HIGH_AUTONOMY_CODING ->
                "Jarvis runs coding work (edits, tests, builds, commits) inside the approved " +
                    "workspace without asking. Deploy, publish, merge, credentials, purchases, " +
                    "and anything outside the workspace still require approval."
            LOCKDOWN -> "Jarvis is paused. No external actions, no handoffs, no automation."
        }

    /**
     * Lockdown disables every outbound action, including emergency
     * stop side effects that depend on the gateway. The Control
     * screen uses this to grey out controls.
     */
    val isLockdown: Boolean get() = this == LOCKDOWN

    /** Friction-reduced coding mode — Control surfaces workspace scope + capabilities. */
    val isHighAutonomyCoding: Boolean get() = this == OWNER_HIGH_AUTONOMY_CODING

    /** Wire value for the cockpit `/v1/cockpit/autonomy` endpoint (matches approval_policy). */
    val wireValue: String
        get() = when (this) {
            MANUAL -> "read_only"
            ASSISTED -> "assisted"
            TRUSTED_LOW_RISK -> "autonomous"
            OWNER_HIGH_AUTONOMY_CODING -> "owner_high_autonomy_coding"
            LOCKDOWN -> "read_only"
        }

    companion object {
        fun fromName(name: String?): AutonomyMode =
            entries.firstOrNull { it.name == name } ?: MANUAL

        /**
         * Map a backend autonomy wire value to a mode. Only the coding mode
         * round-trips 1:1; the other backend levels collapse onto the closest
         * owner-facing mode (read_only → Manual, yolo → Trusted).
         */
        fun fromWire(wire: String?): AutonomyMode = when (wire?.trim()?.lowercase()) {
            "owner_high_autonomy_coding" -> OWNER_HIGH_AUTONOMY_CODING
            "assisted" -> ASSISTED
            "autonomous", "yolo" -> TRUSTED_LOW_RISK
            "read_only" -> MANUAL
            else -> MANUAL
        }
    }
}
