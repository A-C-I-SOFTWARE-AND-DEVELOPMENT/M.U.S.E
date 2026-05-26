package com.aci.hermes.ui.theme

import android.view.HapticFeedbackConstants
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.platform.LocalView

/**
 * Tiny haptic vocabulary the cockpit reaches for. Each call is a one-shot
 * tap that respects the system-wide haptic-feedback-enabled setting — the
 * platform suppresses these automatically if the user has disabled
 * haptics in Sound & vibration settings, so no opt-out wiring is needed
 * here.
 */
class HermesHaptics(private val performer: (Int) -> Unit) {
    fun confirm() = performer(HapticFeedbackConstants.CONFIRM)
    fun reject() = performer(HapticFeedbackConstants.REJECT)
    fun longPress() = performer(HapticFeedbackConstants.LONG_PRESS)
    fun tick() = performer(HapticFeedbackConstants.KEYBOARD_TAP)
}

@Composable
fun rememberHermesHaptics(): HermesHaptics {
    val view = LocalView.current
    return remember(view) {
        HermesHaptics { constant -> view.performHapticFeedback(constant) }
    }
}
