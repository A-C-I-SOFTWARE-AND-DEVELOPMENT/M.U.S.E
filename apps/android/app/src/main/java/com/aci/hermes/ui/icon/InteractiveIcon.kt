package com.aci.hermes.ui.icon

import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.size
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.withTransform
import androidx.compose.ui.unit.dp

/**
 * Interactive Icon — the signature pulse of Jarvis Prime.
 *
 * Two concentric rings around a filled core. The outer ring breathes
 * (alpha sweep), the inner ring rotates a soft sweep gradient. Tapping
 * the icon is the universal "start something" gesture — Home uses it
 * for voice capture, Chat uses it as the send affordance.
 */
@Composable
fun InteractiveIcon(
    modifier: Modifier = Modifier,
    active: Boolean = true,
    onClick: (() -> Unit)? = null,
    sizeDp: Int = 120,
    @Suppress("UNUSED_PARAMETER") contentDescription: String? = null,
) {
    val primary = MaterialTheme.colorScheme.primary
    val secondary = MaterialTheme.colorScheme.secondary
    val onSurface = MaterialTheme.colorScheme.onSurface

    val transition = rememberInfiniteTransition(label = "jarvis-pulse")
    val pulse by transition.animateFloat(
        initialValue = 0f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = 2400),
            repeatMode = RepeatMode.Reverse,
        ),
        label = "jarvis-pulse-alpha",
    )
    val sweep by transition.animateFloat(
        initialValue = 0f,
        targetValue = 360f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = 4800),
            repeatMode = RepeatMode.Restart,
        ),
        label = "jarvis-pulse-sweep",
    )

    val clickModifier = if (onClick != null) Modifier.clickable(onClick = onClick) else Modifier

    Box(
        modifier = modifier.then(clickModifier).size(sizeDp.dp),
        contentAlignment = Alignment.Center,
    ) {
        Canvas(modifier = Modifier.size(sizeDp.dp)) {
            val s = size.minDimension
            val centre = Offset(size.width / 2, size.height / 2)

            // Outer breathing ring.
            val outerAlpha = if (active) 0.45f + 0.45f * pulse else 0.18f
            drawCircle(
                color = primary.copy(alpha = outerAlpha),
                radius = s / 2 * (0.92f + 0.04f * (if (active) pulse else 0f)),
                center = centre,
                style = Stroke(width = s * 0.04f),
            )

            // Rotating sweep ring.
            val sweepBrush = Brush.sweepGradient(
                colors = listOf(
                    primary.copy(alpha = 0f),
                    primary.copy(alpha = if (active) 0.5f else 0.15f),
                    secondary.copy(alpha = if (active) 0.6f else 0.2f),
                    primary.copy(alpha = 0f),
                ),
                center = centre,
            )
            withTransform({ rotate(degrees = sweep, pivot = centre) }) {
                drawCircle(
                    brush = sweepBrush,
                    radius = s / 2 * 0.78f,
                    center = centre,
                    style = Stroke(width = s * 0.06f),
                )
            }

            // Inner filled core.
            drawCircle(
                brush = Brush.radialGradient(
                    colors = listOf(
                        primary,
                        primary.copy(alpha = 0.7f),
                        onSurface.copy(alpha = 0f),
                    ),
                    center = centre,
                    radius = s / 2 * 0.55f,
                ),
                radius = s / 2 * 0.55f,
                center = centre,
            )

            // Tick at the centre.
            drawCircle(
                color = onSurface.copy(alpha = 0.85f),
                radius = s / 2 * 0.05f,
                center = centre,
            )
        }
    }
}

/** Smaller static badge used inline (top bar, list items). */
@Composable
fun InteractiveIconBadge(
    sizeDp: Int = 32,
    modifier: Modifier = Modifier,
) {
    val primary = MaterialTheme.colorScheme.primary
    val onSurface = MaterialTheme.colorScheme.onSurface
    Box(modifier = modifier.size(sizeDp.dp), contentAlignment = Alignment.Center) {
        Canvas(modifier = Modifier.size(sizeDp.dp)) {
            val s = size.minDimension
            val centre = Offset(size.width / 2, size.height / 2)
            drawCircle(color = primary.copy(alpha = 0.85f), radius = s / 2, center = centre)
            drawCircle(color = onSurface.copy(alpha = 0.95f), radius = s * 0.08f, center = centre)
        }
    }
}
