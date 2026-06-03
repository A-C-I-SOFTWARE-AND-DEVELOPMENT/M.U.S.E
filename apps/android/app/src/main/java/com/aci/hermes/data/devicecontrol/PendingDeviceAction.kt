package com.aci.hermes.data.devicecontrol

import com.aci.hermes.data.automation.AutomationIntent
import com.aci.hermes.data.automation.ResolvedTarget

/**
 * A sensitive device action held for explicit owner confirmation.
 *
 * Created by [DeviceControlController] when the broker returns
 * [BrokerDecision.NeedsConfirmation], surfaced on the Device control screen
 * with Approve / Dismiss. [intent] + [resolved] are the captured execution
 * context (so an approval runs exactly what was previewed); the UI only needs
 * [previewLabel] and [sensitivity].
 */
data class PendingDeviceAction(
    val id: String,
    val intent: AutomationIntent,
    val resolved: ResolvedTarget?,
    val previewLabel: String,
    val sensitivity: DeviceActionSensitivity,
    val requestedAt: Long,
)
