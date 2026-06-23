package com.aci.hermes.ui.designsystem

import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import com.aci.hermes.ui.theme.JarvisCyan
import com.aci.hermes.ui.theme.JarvisJade
import com.aci.hermes.ui.theme.JarvisSignalGhost

/**
 * Connection / liveness states a [museStatusDot] (and [museStatusPill]) can
 * show. Each maps to a Singularity status color.
 */
enum class museStatus {
    /** Disconnected / inert. Muted, no glow. */
    Off,

    /** Healthy / paired / all-good. Jade. */
    Ok,

    /** Actively listening / streaming. Cyan (the ring's "active" stop). */
    Live,

    /** Handshaking / reconnecting. Cyan, pulsing. */
    Connecting,
}

/** Resolve the dot/glow color for a [museStatus]. */
internal fun museStatus.color(): Color = when (this) {
    museStatus.Off -> JarvisSignalGhost
    museStatus.Ok -> JarvisJade
    museStatus.Live -> JarvisCyan
    museStatus.Connecting -> JarvisCyan
}

/**
 * A small status dot with a soft glow halo — the "is it live?" tell that sits
 * in headers, pills, and list rows.
 *
 * [museStatus.Connecting] pulses its glow (a slow breathe via [museMotion]
 * timing); every other state is static. The dot color and glow always agree,
 * so the signal reads at a glance.
 *
 * @param status which state to render.
 * @param size diameter of the solid dot (the glow extends beyond it).
 * @param animate when false, the connecting pulse is frozen (honour
 *                reduced-motion at the call site).
 */
@Composable
fun museStatusDot(
    status: museStatus,
    modifier: Modifier = Modifier,
    size: Dp = 10.dp,
    animate: Boolean = true,
) {
    val color = status.color()

    val pulse: Float = if (status == museStatus.Connecting && animate) {
        val transition = rememberInfiniteTransition(label = "muse-status-pulse")
        val value by transition.animateFloat(
            initialValue = 0.35f,
            targetValue = 1f,
            animationSpec = infiniteRepeatable(
                animation = tween(durationMillis = 900, easing = museMotion.StandardEasing),
                repeatMode = RepeatMode.Reverse,
            ),
            label = "muse-status-pulse-alpha",
        )
        value
    } else {
        1f
    }

    // Reserve room for the glow halo (1.8× the dot) so layout doesn't clip it.
    Canvas(modifier = modifier.size(size * 1.8f)) {
        val w = this.size.width
        val h = this.size.height
        val cx = w / 2f
        val cy = h / 2f
        val dotRadius = minOf(w, h) / 2f / 1.8f

        if (status != museStatus.Off) {
            // Soft glow — a single translucent halo, scaled by the pulse.
            drawCircle(
                color = color.copy(alpha = 0.30f * pulse),
                radius = dotRadius * 1.8f,
                center = androidx.compose.ui.geometry.Offset(cx, cy),
            )
        }
        drawCircle(
            color = color,
            radius = dotRadius,
            center = androidx.compose.ui.geometry.Offset(cx, cy),
        )
    }
}
