package com.aci.hermes.ui.jarvis

import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.hapticfeedback.HapticFeedback
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalHapticFeedback

/**
 * Haptic feedback for the primary muse touch points.
 *
 * Compose only surfaces two platform haptic constants today
 * ([HapticFeedbackType.TextHandleMove] for light ticks,
 * [HapticFeedbackType.LongPress] for a firmer confirm). We map the
 * app's interaction vocabulary onto them in one place ([feedbackType])
 * so the mapping is unit-testable and so a future richer haptic API
 * only has to change here.
 *
 * "Where available" is honoured two ways: the [HapticFeedback] handle
 * may be null (tests, previews), and the platform itself no-ops when
 * the device has no vibrator or the user disabled touch feedback.
 */
enum class JarvisHapticEvent {
    /** A primary tap — e.g. tapping the presence icon to open chat. */
    TAP,

    /** A deliberate confirm — e.g. engaging the emergency stop. */
    CONFIRM,

    /** A cautionary cue — e.g. a serious/critical action surfacing. */
    WARN,
}

/**
 * Pure mapping from a Jarvis interaction to a Compose haptic constant.
 * Kept separate from [JarvisHaptics] so it can be asserted in a plain
 * unit test without a running composition.
 */
fun JarvisHapticEvent.feedbackType(): HapticFeedbackType = when (this) {
    JarvisHapticEvent.TAP -> HapticFeedbackType.TextHandleMove
    JarvisHapticEvent.CONFIRM -> HapticFeedbackType.LongPress
    JarvisHapticEvent.WARN -> HapticFeedbackType.LongPress
}

/**
 * Thin wrapper over [HapticFeedback]. The handle is nullable so call
 * sites in tests/previews can pass `null` and get a safe no-op.
 */
class JarvisHaptics(private val haptic: HapticFeedback?) {

    fun perform(event: JarvisHapticEvent) {
        haptic?.performHapticFeedback(event.feedbackType())
    }

    fun tap() = perform(JarvisHapticEvent.TAP)
    fun confirm() = perform(JarvisHapticEvent.CONFIRM)
    fun warn() = perform(JarvisHapticEvent.WARN)
}

/**
 * Composition-scoped [JarvisHaptics] bound to the current
 * [LocalHapticFeedback]. Remembered so the wrapper isn't reallocated
 * on every recomposition.
 */
@Composable
fun rememberJarvisHaptics(): JarvisHaptics {
    val haptic = LocalHapticFeedback.current
    return remember(haptic) { JarvisHaptics(haptic) }
}
