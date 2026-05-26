package com.aci.hermes.ui.jarvis

import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.gestures.awaitEachGesture
import androidx.compose.foundation.gestures.awaitFirstDown
import androidx.compose.foundation.gestures.waitForUpOrCancellation
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.input.pointer.PointerEventPass
import androidx.compose.ui.input.pointer.PointerInputChange
import androidx.compose.ui.input.pointer.PointerInputScope
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.platform.LocalViewConfiguration
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.onClick
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.withTimeoutOrNull

/**
 * Gesture thresholds for the Jarvis Prime icon. Public so tests and
 * the floating-bubble surface that ships later can reuse them.
 */
object JarvisIconGestures {
    /** A press that lasts at least this long counts as a "hold". */
    const val HOLD_THRESHOLD_MS: Long = 350L

    /** A press that lasts at least this long upgrades to an emergency-stop long-press. */
    const val LONG_PRESS_THRESHOLD_MS: Long = 1500L

    /** Negative dy past this distance counts as a swipe-up. */
    val SWIPE_UP_DISTANCE: Dp = 32.dp
}

/**
 * Test tags surfaced by [JarvisPrimeIcon]. Centralized so the Compose
 * UI tests and the (future) overlay surface don't drift on string
 * literals.
 */
object JarvisIconTestTags {
    const val ROOT = "jarvis_prime_icon"
}

/**
 * In-app presence indicator and command surface for Jarvis Prime.
 *
 * Renders a circular core, a state-driven ring, and an optional pulsing
 * halo. Gesture vocabulary:
 *  - tap                                  → [onTap]   (open Chat)
 *  - press-and-hold past HOLD_THRESHOLD   → [onHold]  (start voice capture)
 *  - press-and-hold past LONG_PRESS       → [onLongPress] (emergency stop)
 *  - double tap                           → [onDoubleTap] (show current status)
 *  - swipe up                             → [onSwipeUp] (open Tasks)
 *
 * The composable does NOT request the system overlay permission — the
 * floating-bubble surface ships behind an education flow in a later
 * wave. This is an in-app component only.
 *
 * @param reducedMotion when true, the infinite pulse animation is
 *        suppressed and the icon renders at its base size with no halo
 *        breathing. Should be wired to
 *        `AccessibilityManager.isReduceMotionEnabled` / user pref.
 */
@Composable
fun JarvisPrimeIcon(
    state: IconState,
    onTap: () -> Unit,
    onHold: () -> Unit,
    onLongPress: () -> Unit,
    onDoubleTap: () -> Unit,
    onSwipeUp: () -> Unit,
    modifier: Modifier = Modifier,
    size: Dp = 72.dp,
    reducedMotion: Boolean = false,
    haptics: JarvisHaptics = JarvisHaptics(LocalHapticFeedback.current),
) {
    val appearance = JarvisIconColors.appearanceFor(state)
    val contentDesc = state.accessibilityLabel()
    val viewConfig = LocalViewConfiguration.current

    // Subtle infinite pulse. Suppressed entirely when reducedMotion is on
    // OR when this state's appearance recipe says amplitude is zero
    // (offline, blocked).
    val animateScale = !reducedMotion && appearance.pulseAmplitude > 0f
    val pulse = if (animateScale) {
        val transition = rememberInfiniteTransition(label = "jarvis-pulse")
        val value by transition.animateFloat(
            initialValue = 0f,
            targetValue = 1f,
            animationSpec = infiniteRepeatable(
                animation = tween(durationMillis = 1400, easing = LinearEasing),
                repeatMode = RepeatMode.Reverse,
            ),
            label = "jarvis-pulse-value",
        )
        value
    } else {
        0f
    }

    Box(
        modifier = modifier
            .size(size)
            .testTag(JarvisIconTestTags.ROOT)
            .alpha(if (appearance.dim) 0.5f else 1f)
            .semantics {
                contentDescription = contentDesc
                stateDescription = contentDesc
                onClick(label = "Open chat") { onTap(); true }
            }
            .pointerInput(state) {
                detectJarvisGestures(
                    doubleTapTimeoutMs = viewConfig.doubleTapTimeoutMillis,
                    swipeUpPx = JarvisIconGestures.SWIPE_UP_DISTANCE.toPx(),
                    onTap = {
                        haptics.onTap()
                        onTap()
                    },
                    onDoubleTap = {
                        haptics.onTap()
                        onDoubleTap()
                    },
                    onHold = {
                        haptics.onHoldEngaged()
                        onHold()
                    },
                    onLongPress = {
                        haptics.onLongPress()
                        onLongPress()
                    },
                    onSwipeUp = {
                        haptics.onSwipeUp()
                        onSwipeUp()
                    },
                )
            },
        contentAlignment = Alignment.Center,
    ) {
        Canvas(modifier = Modifier.size(size)) {
            val w = this.size.minDimension
            val cx = this.size.width / 2f
            val cy = this.size.height / 2f
            val center = Offset(cx, cy)
            val baseRadius = w * 0.32f
            val ringRadius = w * 0.42f
            val haloRadius = w * 0.50f + (pulse * appearance.pulseAmplitude * w * 0.06f)

            // Halo
            drawCircle(
                brush = Brush.radialGradient(
                    colors = listOf(appearance.haloColor, Color.Transparent),
                    center = center,
                    radius = haloRadius,
                ),
                radius = haloRadius,
                center = center,
            )

            // Ring
            drawCircle(
                color = appearance.ringColor,
                radius = ringRadius,
                center = center,
                style = Stroke(width = w * 0.04f),
            )

            // Core
            drawCircle(
                color = appearance.coreColor,
                radius = baseRadius,
                center = center,
            )
        }
    }
}

/**
 * Single unified gesture detector for the Jarvis Prime icon.
 *
 * One press can transition through several states without lifting:
 * down → (movement: swipe-up consumes the gesture) → (350ms: hold
 * fires, voice capture begins) → (1500ms: long press fires, emergency
 * stop overrides). On release before any threshold, we wait briefly
 * for a second tap to disambiguate tap vs double-tap.
 *
 * All callbacks are mutually exclusive within a single press — once a
 * non-tap path fires (swipe, hold, long press), the tap callback is
 * suppressed for that gesture.
 */
internal suspend fun PointerInputScope.detectJarvisGestures(
    doubleTapTimeoutMs: Long,
    swipeUpPx: Float,
    onTap: () -> Unit,
    onDoubleTap: () -> Unit,
    onHold: () -> Unit,
    onLongPress: () -> Unit,
    onSwipeUp: () -> Unit,
) {
    awaitEachGesture {
        val down = awaitFirstDown(requireUnconsumed = false, pass = PointerEventPass.Main)

        var totalDy = 0f
        var swipedUp = false
        var holdFired = false
        var longPressFired = false
        var released = false
        val startTime = System.currentTimeMillis()

        // Phase loop. We race "time remaining to next threshold"
        // against the next pointer event. Movement, release, and time
        // can all end a phase.
        while (!released) {
            val deadlineMs: Long = when {
                !holdFired -> JarvisIconGestures.HOLD_THRESHOLD_MS -
                    (System.currentTimeMillis() - startTime)
                !longPressFired -> JarvisIconGestures.LONG_PRESS_THRESHOLD_MS -
                    (System.currentTimeMillis() - startTime)
                else -> Long.MAX_VALUE
            }

            val event = if (deadlineMs >= Long.MAX_VALUE / 2) {
                awaitPointerEvent()
            } else {
                val wait = deadlineMs.coerceAtLeast(1L)
                withTimeoutOrNull(wait) { awaitPointerEvent() }
            }

            if (event == null) {
                // Threshold hit without a pointer event.
                if (!holdFired && !swipedUp) {
                    holdFired = true
                    onHold()
                } else if (!longPressFired && !swipedUp) {
                    longPressFired = true
                    onLongPress()
                }
                continue
            }

            val change: PointerInputChange = event.changes.firstOrNull { it.id == down.id }
                ?: continue

            // Update drag tracking.
            val dy = change.position.y - change.previousPosition.y
            totalDy += dy
            if (!swipedUp && !holdFired && -totalDy >= swipeUpPx) {
                swipedUp = true
                onSwipeUp()
                drainUntilUp(down.id)
                released = true
                continue
            }

            if (!change.pressed) {
                released = true
            }
        }

        // If nothing else fired, classify the release as tap vs double-tap.
        if (!swipedUp && !holdFired && !longPressFired) {
            val second = withTimeoutOrNull(doubleTapTimeoutMs) {
                awaitFirstDown(requireUnconsumed = false, pass = PointerEventPass.Main)
            }
            if (second == null) {
                onTap()
            } else {
                waitForUpOrCancellation()
                onDoubleTap()
            }
        }
    }
}

/** Drain pointer events for the given pointer until it lifts. */
private suspend fun androidx.compose.ui.input.pointer.AwaitPointerEventScope.drainUntilUp(
    pointerId: androidx.compose.ui.input.pointer.PointerId,
) {
    while (true) {
        val event = awaitPointerEvent()
        val change = event.changes.firstOrNull { it.id == pointerId }
        if (change == null || !change.pressed) return
    }
}
