package com.aci.hermes.ui.components

import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.size
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.rotate
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.aci.hermes.ui.theme.JarvisCyan
import com.aci.hermes.ui.theme.JarvisGold
import com.aci.hermes.ui.theme.JarvisInk
import com.aci.hermes.ui.theme.JarvisRed

/**
 * The Jarvis Prime interactive icon. The visible presence of Jarvis
 * Prime on every primary surface.
 *
 * Rendered with `Canvas` so it scales cleanly and animates without
 * pulling in a heavy dependency. The motion is intentionally subtle —
 * Jarvis Prime is meant to feel calm and present, not noisy.
 *
 * `onTap` fires on the whole hit area; callers route the tap through
 * a click modifier on the parent so the icon stays purely
 * presentational here.
 */
@Composable
fun JarvisInteractiveIcon(
    state: JarvisIconState,
    modifier: Modifier = Modifier,
    size: Dp = 96.dp,
) {
    val transition = rememberInfiniteTransition(label = "jarvis-icon")
    val pulse by transition.animateFloat(
        initialValue = 0.85f,
        targetValue = 1.05f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = 1600, easing = LinearEasing),
            repeatMode = RepeatMode.Reverse,
        ),
        label = "pulse",
    )
    val rotation by transition.animateFloat(
        initialValue = 0f,
        targetValue = 360f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = 4000, easing = LinearEasing),
            repeatMode = RepeatMode.Restart,
        ),
        label = "rotation",
    )

    Box(
        modifier = modifier.size(size),
        contentAlignment = Alignment.Center,
    ) {
        Canvas(modifier = Modifier.size(size)) {
            val center = Offset(this.size.width / 2f, this.size.height / 2f)
            val radius = this.size.minDimension / 2f
            val baseColor = colorFor(state)
            val ringStroke = Stroke(width = radius * 0.08f)

            // Soft halo (always on, varies in intensity by state).
            drawCircle(
                brush = Brush.radialGradient(
                    colors = listOf(baseColor.copy(alpha = haloAlpha(state)), Color.Transparent),
                    center = center,
                    radius = radius * pulse,
                ),
                radius = radius * pulse,
                center = center,
            )

            // Core disc.
            drawCircle(
                color = JarvisInk,
                radius = radius * 0.62f,
                center = center,
            )

            // State-specific ring decoration.
            when (state) {
                JarvisIconState.IDLE -> {
                    drawCircle(
                        color = baseColor,
                        radius = radius * 0.62f,
                        center = center,
                        style = ringStroke,
                    )
                }
                JarvisIconState.LISTENING -> {
                    // Two phased ripples.
                    drawCircle(
                        color = baseColor.copy(alpha = 0.6f),
                        radius = radius * (0.62f * pulse),
                        center = center,
                        style = ringStroke,
                    )
                    drawCircle(
                        color = baseColor.copy(alpha = 0.3f),
                        radius = radius * (0.8f * pulse),
                        center = center,
                        style = ringStroke,
                    )
                }
                JarvisIconState.WORKING -> {
                    rotate(rotation, pivot = center) {
                        drawArc(
                            color = baseColor,
                            startAngle = 0f,
                            sweepAngle = 270f,
                            useCenter = false,
                            topLeft = Offset(center.x - radius * 0.62f, center.y - radius * 0.62f),
                            size = Size(radius * 0.62f * 2f, radius * 0.62f * 2f),
                            style = ringStroke,
                        )
                    }
                }
                JarvisIconState.ALERT -> {
                    drawCircle(
                        color = baseColor,
                        radius = radius * 0.62f,
                        center = center,
                        style = Stroke(width = radius * 0.14f),
                    )
                }
                JarvisIconState.CRITICAL -> {
                    drawCircle(
                        color = baseColor,
                        radius = radius * 0.62f,
                        center = center,
                    )
                }
            }
        }
        Text(
            text = "J",
            color = when (state) {
                JarvisIconState.CRITICAL -> JarvisInk
                else -> colorFor(state)
            },
            fontSize = (size.value * 0.32f).sp,
            fontWeight = FontWeight.Bold,
            textAlign = TextAlign.Center,
        )
    }
}

internal fun colorFor(state: JarvisIconState): Color = when (state) {
    JarvisIconState.IDLE -> JarvisGold
    JarvisIconState.LISTENING -> JarvisCyan
    JarvisIconState.WORKING -> JarvisCyan
    JarvisIconState.ALERT -> JarvisGold
    JarvisIconState.CRITICAL -> JarvisRed
}

internal fun haloAlpha(state: JarvisIconState): Float = when (state) {
    JarvisIconState.IDLE -> 0.20f
    JarvisIconState.LISTENING -> 0.50f
    JarvisIconState.WORKING -> 0.40f
    JarvisIconState.ALERT -> 0.55f
    JarvisIconState.CRITICAL -> 0.70f
}
