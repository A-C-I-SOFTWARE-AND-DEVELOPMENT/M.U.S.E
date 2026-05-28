package com.aci.hermes.ui.jarvis

import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import kotlin.math.cos
import kotlin.math.sin

/**
 * Animated wrapper around [JarvisPrimeIcon].
 *
 * Reads [JarvisLiveStatus.avatarActivity] and draws the corresponding
 * indicator on top of the base icon:
 *   - [JarvisAvatarActivity.Static]            → no extra overlay
 *   - [JarvisAvatarActivity.Subtle]            → no extra overlay (the
 *     icon's own pulse is the motion)
 *   - [JarvisAvatarActivity.AnimatedDots]      → three dots fading in
 *     sequence under the icon
 *   - [JarvisAvatarActivity.ScanRing]          → a rotating arc segment
 *   - [JarvisAvatarActivity.TaskOrbit]         → a bead orbiting the
 *     icon ring
 *   - [JarvisAvatarActivity.CheckPulse]        → an outer check-style
 *     pulse ring
 *   - [JarvisAvatarActivity.MouthPulse]        → a horizontal bar under
 *     the core that breathes with the pulse
 *   - [JarvisAvatarActivity.GoldRing]          → solid gold outer ring
 *   - [JarvisAvatarActivity.CrimsonLockedRing] → solid red outer ring
 *
 * All animated overlays are suppressed when
 * [JarvisLiveStatus.shouldPulse] is false (reduced-motion). Attention
 * rings (gold / crimson) still render — they're the legibility signal,
 * just without breathing.
 *
 * The base [JarvisPrimeIcon] is configured with gesture callbacks if
 * provided; pass no-ops to render a presentational avatar.
 */
@Composable
fun JarvisLivingAvatar(
    status: JarvisLiveStatus,
    modifier: Modifier = Modifier,
    size: Dp = 144.dp,
    onTap: () -> Unit = {},
    onHold: () -> Unit = {},
    onLongPress: () -> Unit = {},
    onDoubleTap: () -> Unit = {},
    onSwipeUp: () -> Unit = {},
) {
    val appearance = JarvisIconColors.appearanceFor(status.iconState)
    Box(
        modifier = modifier.size(size),
        contentAlignment = Alignment.Center,
    ) {
        // Outer attention rings sit behind the base icon so the icon's
        // halo blends into the ring cleanly.
        when (status.avatarActivity) {
            JarvisAvatarActivity.GoldRing -> OuterRing(
                color = JarvisPalette.Gold,
                size = size,
                breathe = status.shouldPulse,
            )
            JarvisAvatarActivity.CrimsonLockedRing -> OuterRing(
                color = JarvisPalette.Red,
                size = size,
                breathe = false,
            )
            else -> Unit
        }

        JarvisPrimeIcon(
            state = status.iconState,
            onTap = onTap,
            onHold = onHold,
            onLongPress = onLongPress,
            onDoubleTap = onDoubleTap,
            onSwipeUp = onSwipeUp,
            size = size,
            reducedMotion = !status.shouldPulse,
        )

        // Foreground activity overlays.
        when (status.avatarActivity) {
            JarvisAvatarActivity.AnimatedDots -> AnimatedDotsOverlay(
                color = appearance.ringColor,
                size = size,
                enabled = status.shouldPulse,
            )
            JarvisAvatarActivity.ScanRing -> ScanRingOverlay(
                color = appearance.ringColor,
                size = size,
                enabled = status.shouldPulse,
            )
            JarvisAvatarActivity.TaskOrbit -> TaskOrbitOverlay(
                color = appearance.ringColor,
                size = size,
                enabled = status.shouldPulse,
            )
            JarvisAvatarActivity.CheckPulse -> CheckPulseOverlay(
                color = JarvisPalette.Green,
                size = size,
                enabled = status.shouldPulse,
            )
            JarvisAvatarActivity.MouthPulse -> MouthPulseOverlay(
                color = appearance.ringColor,
                size = size,
                enabled = status.shouldPulse,
            )
            JarvisAvatarActivity.Static,
            JarvisAvatarActivity.Subtle,
            JarvisAvatarActivity.GoldRing,
            JarvisAvatarActivity.CrimsonLockedRing -> Unit
        }
    }
}

@Composable
private fun OuterRing(color: Color, size: Dp, breathe: Boolean) {
    val phase = if (breathe) infinitePhase("outer-ring") else 0f
    Canvas(modifier = Modifier.size(size)) {
        val w = this.size.minDimension
        val cx = this.size.width / 2f
        val cy = this.size.height / 2f
        val r = w * 0.48f + (phase * w * 0.02f)
        drawCircle(
            color = color,
            radius = r,
            center = Offset(cx, cy),
            style = Stroke(width = w * 0.035f),
        )
    }
}

@Composable
private fun AnimatedDotsOverlay(color: Color, size: Dp, enabled: Boolean) {
    val phase = if (enabled) infinitePhase("dots", durationMs = 900) else 0f
    Canvas(modifier = Modifier.size(size)) {
        val w = this.size.minDimension
        val cx = this.size.width / 2f
        val cy = this.size.height / 2f
        val radius = w * 0.04f
        val gap = w * 0.10f
        val y = cy + w * 0.50f + radius * 0.5f
        val xs = floatArrayOf(cx - gap, cx, cx + gap)
        xs.forEachIndexed { i, x ->
            val alpha = dotAlpha(phase, i)
            drawCircle(
                color = color.copy(alpha = alpha),
                radius = radius,
                center = Offset(x, y),
            )
        }
    }
}

private fun dotAlpha(phase: Float, index: Int): Float {
    val offset = index * (1f / 3f)
    val local = ((phase + offset) % 1f)
    return 0.25f + 0.75f * (1f - kotlin.math.abs(local - 0.5f) * 2f)
}

@Composable
private fun ScanRingOverlay(color: Color, size: Dp, enabled: Boolean) {
    val phase = if (enabled) infinitePhase("scan-ring", durationMs = 1500) else 0f
    Canvas(modifier = Modifier.size(size)) {
        val w = this.size.minDimension
        val cx = this.size.width / 2f
        val cy = this.size.height / 2f
        val ringRadius = w * 0.46f
        val stroke = w * 0.025f
        val sweep = 70f
        val start = phase * 360f
        drawArc(
            color = color,
            startAngle = start,
            sweepAngle = sweep,
            useCenter = false,
            topLeft = Offset(cx - ringRadius, cy - ringRadius),
            size = Size(ringRadius * 2f, ringRadius * 2f),
            style = Stroke(width = stroke),
        )
    }
}

@Composable
private fun TaskOrbitOverlay(color: Color, size: Dp, enabled: Boolean) {
    val phase = if (enabled) infinitePhase("orbit", durationMs = 2200) else 0f
    Canvas(modifier = Modifier.size(size)) {
        val w = this.size.minDimension
        val cx = this.size.width / 2f
        val cy = this.size.height / 2f
        val orbitRadius = w * 0.48f
        val beadRadius = w * 0.05f
        val angle = (phase * 2f * Math.PI).toFloat()
        val bx = cx + orbitRadius * cos(angle)
        val by = cy + orbitRadius * sin(angle)
        drawCircle(
            color = color,
            radius = beadRadius,
            center = Offset(bx, by),
        )
        drawCircle(
            color = color.copy(alpha = 0.25f),
            radius = beadRadius * 1.7f,
            center = Offset(bx, by),
        )
    }
}

@Composable
private fun CheckPulseOverlay(color: Color, size: Dp, enabled: Boolean) {
    val phase = if (enabled) infinitePhase("check-pulse", durationMs = 1600) else 0.5f
    Canvas(modifier = Modifier.size(size)) {
        val w = this.size.minDimension
        val cx = this.size.width / 2f
        val cy = this.size.height / 2f
        val r = w * (0.46f + phase * 0.04f)
        val alpha = 0.6f - phase * 0.45f
        drawCircle(
            color = color.copy(alpha = alpha.coerceAtLeast(0.15f)),
            radius = r,
            center = Offset(cx, cy),
            style = Stroke(width = w * 0.02f),
        )
    }
}

@Composable
private fun MouthPulseOverlay(color: Color, size: Dp, enabled: Boolean) {
    val phase = if (enabled) infinitePhase("mouth", durationMs = 700) else 0f
    Canvas(modifier = Modifier.size(size)) {
        val w = this.size.minDimension
        val cx = this.size.width / 2f
        val cy = this.size.height / 2f
        val baseW = w * 0.18f
        val barW = baseW + phase * w * 0.10f
        val barH = w * 0.04f
        drawRoundRect(
            color = color,
            topLeft = Offset(cx - barW / 2f, cy + w * 0.12f),
            size = Size(barW, barH),
            cornerRadius = androidx.compose.ui.geometry.CornerRadius(barH / 2f, barH / 2f),
        )
    }
}

@Composable
private fun infinitePhase(label: String, durationMs: Int = 1400): Float {
    val transition = rememberInfiniteTransition(label = label)
    val value by transition.animateFloat(
        initialValue = 0f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = durationMs, easing = LinearEasing),
            repeatMode = RepeatMode.Restart,
        ),
        label = "$label-value",
    )
    return value
}
