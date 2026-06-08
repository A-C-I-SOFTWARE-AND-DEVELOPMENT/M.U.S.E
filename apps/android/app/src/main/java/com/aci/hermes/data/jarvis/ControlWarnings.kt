package com.aci.hermes.data.jarvis

/**
 * Pure mapping from an owner-controlled action to the warning level
 * the Control / Settings UI must surface before applying it. Kept
 * pure so the rule set is unit-testable without Android.
 *
 * Changing approvals or safety gates is always elevated — those
 * are the rails that keep MUSE owner-loyal.
 */
object ControlWarnings {

    /** A change the owner is attempting from Control or Settings. */
    sealed interface Action {
        data class AutonomyChange(val from: AutonomyMode, val to: AutonomyMode) : Action
        data object DisableApprovals : Action
        data object EnableApprovals : Action
        data object DisableSafetyGates : Action
        data object EnableSafetyGates : Action
        data class GatewayEndpointChange(val from: String, val to: String) : Action
        data object EmergencyStop : Action
        data object ToggleMockMode : Action
        data object ToggleTermuxGateway : Action
    }

    fun levelFor(action: Action): WarningLevel = when (action) {
        is Action.AutonomyChange -> autonomyLevel(action.from, action.to)
        Action.DisableApprovals -> WarningLevel.SERIOUS
        Action.EnableApprovals -> WarningLevel.NONE
        Action.DisableSafetyGates -> WarningLevel.CRITICAL
        Action.EnableSafetyGates -> WarningLevel.NONE
        is Action.GatewayEndpointChange ->
            if (action.from == action.to) WarningLevel.NONE else WarningLevel.NOTICE
        Action.EmergencyStop -> WarningLevel.SERIOUS
        Action.ToggleMockMode -> WarningLevel.NOTICE
        Action.ToggleTermuxGateway -> WarningLevel.NOTICE
    }

    private fun autonomyLevel(from: AutonomyMode, to: AutonomyMode): WarningLevel {
        if (from == to) return WarningLevel.NONE
        return when (to) {
            AutonomyMode.LOCKDOWN -> WarningLevel.SERIOUS
            AutonomyMode.OWNER_HIGH_AUTONOMY_CODING -> WarningLevel.SERIOUS
            AutonomyMode.TRUSTED_LOW_RISK -> WarningLevel.SERIOUS
            AutonomyMode.ASSISTED -> WarningLevel.NOTICE
            AutonomyMode.MANUAL -> WarningLevel.NONE
        }
    }
}
