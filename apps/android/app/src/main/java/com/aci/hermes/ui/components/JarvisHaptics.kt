package com.aci.hermes.ui.components

import android.os.Build
import android.view.HapticFeedbackConstants
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.platform.LocalView

/**
 * Jarvis Prime haptic vocabulary.
 *
 * A tiny, deliberate set of taps so physical feedback stays consistent
 * across the command center:
 *
 *   * [confirm]  — a positive, completed action (approve, send, bring online).
 *   * [reject]   — a destructive or refusing action (reject, emergency stop, stand down).
 *   * [tick]     — a light acknowledgement (toggles, opening a confirm dialog).
 *
 * Every call routes through [android.view.View.performHapticFeedback], which
 * the platform suppresses automatically when the user has disabled haptics
 * in system settings — so there is no extra opt-out to wire here.
 *
 * `CONFIRM` / `REJECT` arrived in API 30; on the app's min SDK (26) we fall
 * back to long-standing constants that read the same to the hand.
 */
class JarvisHaptics(private val perform: (Int) -> Unit) {

    fun confirm() = perform(
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            HapticFeedbackConstants.CONFIRM
        } else {
            HapticFeedbackConstants.VIRTUAL_KEY
        }
    )

    fun reject() = perform(
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            HapticFeedbackConstants.REJECT
        } else {
            HapticFeedbackConstants.LONG_PRESS
        }
    )

    fun tick() = perform(HapticFeedbackConstants.KEYBOARD_TAP)
}

/**
 * Remembers a [JarvisHaptics] bound to the current Compose [LocalView].
 * Safe to call from any composable; the underlying view performs the
 * feedback on the UI thread.
 */
@Composable
fun rememberJarvisHaptics(): JarvisHaptics {
    val view = LocalView.current
    return remember(view) { JarvisHaptics { constant -> view.performHapticFeedback(constant) } }
}
