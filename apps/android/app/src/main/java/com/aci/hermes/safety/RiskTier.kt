package com.aci.hermes.safety

/**
 * Jarvis Prime risk classification for any action that can be taken
 * on the user's behalf. Drives the confirmation flow Jarvis Prime
 * requires before executing — the app itself never bypasses these.
 *
 * The rule set is fixed by product policy and asserted in unit tests:
 *
 *   SAFE     → no confirmation, just do it (read-only, idempotent UI).
 *   RISKY    → ask once.
 *   SERIOUS  → ask twice (two explicit confirmations).
 *   CRITICAL → impact report + rollback plan + two confirmations.
 */
enum class RiskTier(val confirmationsRequired: Int, val requiresImpactReport: Boolean) {
    SAFE(confirmationsRequired = 0, requiresImpactReport = false),
    RISKY(confirmationsRequired = 1, requiresImpactReport = false),
    SERIOUS(confirmationsRequired = 2, requiresImpactReport = false),
    CRITICAL(confirmationsRequired = 2, requiresImpactReport = true);

    /** True when the action requires the user to also acknowledge a rollback plan. */
    val requiresRollbackPlan: Boolean
        get() = this == CRITICAL
}
