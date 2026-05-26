package com.aci.hermes.ui.jarvis

import androidx.compose.ui.hapticfeedback.HapticFeedback
import androidx.compose.ui.hapticfeedback.HapticFeedbackType

/**
 * Thin shim over [HapticFeedback] so the composable doesn't have to
 * spell out feedback-type guards inline, and so unit tests can swap a
 * fake.
 *
 * Compose only exposes two haptic types today (LongPress,
 * TextHandleMove). We map our richer gesture vocabulary onto them; if
 * the platform later grows real "tap" / "success" types we change them
 * here in one place.
 */
class JarvisHaptics(private val hapticFeedback: HapticFeedback?) {

    fun onTap() {
        hapticFeedback?.performHapticFeedback(HapticFeedbackType.TextHandleMove)
    }

    fun onHoldEngaged() {
        hapticFeedback?.performHapticFeedback(HapticFeedbackType.LongPress)
    }

    fun onLongPress() {
        hapticFeedback?.performHapticFeedback(HapticFeedbackType.LongPress)
    }

    fun onSwipeUp() {
        hapticFeedback?.performHapticFeedback(HapticFeedbackType.TextHandleMove)
    }
}
