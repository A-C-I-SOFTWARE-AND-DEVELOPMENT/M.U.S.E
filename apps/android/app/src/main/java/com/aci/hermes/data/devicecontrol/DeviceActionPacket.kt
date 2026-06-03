package com.aci.hermes.data.devicecontrol

import com.aci.hermes.data.automation.AutomationIntent

/** How risky a device action is, which decides whether it needs confirming. */
enum class DeviceActionSensitivity {
    /** Navigation-only: scroll, page turn, home/back/recents. No content acted on. */
    STANDARD,

    /** Acts on content: launches an app or taps a specific on-screen target. */
    SENSITIVE,
}

/**
 * A bounded, self-describing device action. Built from an
 * [AutomationIntent] (the only device-driving vocabulary the app has),
 * it carries everything the [DeviceActionBroker] needs to make a
 * decision and everything the UI/ledger needs to describe it — without
 * any Android dependency, so it is fully unit-testable.
 */
data class DeviceActionPacket(
    val intent: AutomationIntent,
    val requiredCapabilities: Set<DeviceControlCapability>,
    val sensitivity: DeviceActionSensitivity,
    /** Human-readable one-liner, e.g. "Open Facebook" or "Scroll down". */
    val previewLabel: String,
) {
    companion object {
        /**
         * Build a packet for [intent]. [resolvedLabel] is the friendly
         * name of a resolved target (e.g. the matched app label) when the
         * caller has one; it only sharpens the preview text.
         */
        fun from(intent: AutomationIntent, resolvedLabel: String? = null): DeviceActionPacket =
            DeviceActionPacket(
                intent = intent,
                requiredCapabilities = DeviceControlCapability.requiredFor(intent),
                sensitivity = sensitivityOf(intent),
                previewLabel = previewLabelOf(intent, resolvedLabel),
            )

        fun sensitivityOf(intent: AutomationIntent): DeviceActionSensitivity = when (intent) {
            is AutomationIntent.OpenApp,
            is AutomationIntent.PushTarget -> DeviceActionSensitivity.SENSITIVE
            is AutomationIntent.TurnPage,
            is AutomationIntent.Scroll,
            is AutomationIntent.Navigate -> DeviceActionSensitivity.STANDARD
        }

        private fun previewLabelOf(intent: AutomationIntent, resolvedLabel: String?): String =
            when (intent) {
                is AutomationIntent.OpenApp -> "Open ${resolvedLabel ?: intent.query}"
                is AutomationIntent.PushTarget -> "Tap \"${resolvedLabel ?: intent.query}\""
                is AutomationIntent.TurnPage -> "Turn page ${intent.direction.name.lowercase()}"
                is AutomationIntent.Scroll -> "Scroll ${intent.direction.name.lowercase()}"
                is AutomationIntent.Navigate -> "Go ${intent.action.name.lowercase()}"
            }
    }
}
