package com.aci.hermes.ui.screens.live

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.spring
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import kotlin.math.min
import kotlin.math.sin

/**
 * Renders a [PixelSprite] as crisp pixel art and makes it **breathe**: a slow
 * vertical bob + a soft aura whose tempo/strength track [AvatarInputs.energy],
 * so the character reads as alive (calm when idle, livelier when speaking).
 * Holds still under reduced motion / sleep. Same input contract as every other
 * avatar body, so it's a drop-in for the live screen and the shell presence.
 */
@Composable
fun PixelSpriteAvatar(
    sprite: PixelSprite,
    inputs: AvatarInputs,
    contentDescription: String,
    modifier: Modifier = Modifier,
) {
    val energy = inputs.energy.coerceIn(0f, 1f)
    val periodMs = (1700 - energy * 1100f).toInt().coerceAtLeast(420)
    val transition = rememberInfiniteTransition(label = "sprite-breath")
    val phase by transition.animateFloat(
        initialValue = 0f,
        targetValue = (2f * Math.PI).toFloat(),
        animationSpec = infiniteRepeatable(
            animation = tween(periodMs, easing = FastOutSlowInEasing),
            repeatMode = RepeatMode.Restart,
        ),
        label = "sprite-phase",
    )
    val breathing = inputs.motionEnabled
    val bob = if (breathing) sin(phase) else 0f

    // Physics: a damped spring gives the body weight. Every state/character
    // change kicks an upward impulse that falls back and bounces to rest under
    // a gravity-like settle, so motion feels physical, not canned.
    val bounce = remember { Animatable(0f) }
    LaunchedEffect(inputs.pose, sprite.id, inputs.motionEnabled) {
        if (inputs.motionEnabled) {
            bounce.snapTo(-0.20f)
            bounce.animateTo(
                targetValue = 0f,
                animationSpec = spring(
                    dampingRatio = Spring.DampingRatioMediumBouncy,
                    stiffness = Spring.StiffnessLow,
                ),
            )
        } else {
            bounce.snapTo(0f)
        }
    }
    val springOffset = bounce.value

    Canvas(
        modifier = modifier.semantics { this.contentDescription = contentDescription },
    ) {
        val rows = sprite.rows
        val cols = rows.maxOfOrNull { it.length } ?: return@Canvas
        if (cols == 0 || rows.isEmpty()) return@Canvas

        // Soft aura behind the sprite — gentle "alive" glow scaled by energy.
        val auraR = (min(size.width, size.height) / 2f) * (0.62f + 0.06f * (0.5f + bob / 2f))
        drawCircle(
            color = Color(0xFF36D6E7).copy(alpha = 0.08f + 0.10f * energy),
            radius = auraR,
            center = Offset(size.width / 2f, size.height / 2f),
        )

        // Fit the grid as square cells, centred; bob shifts it ~half a cell.
        val cell = min(size.width / cols, size.height / rows.size)
        val gridW = cell * cols
        val gridH = cell * rows.size
        val originX = (size.width - gridW) / 2f
        val bobPx = bob * cell * 0.5f
        val physicsPx = springOffset * gridH // spring/gravity displacement
        val originY = (size.height - gridH) / 2f + bobPx + physicsPx

        for (r in rows.indices) {
            val row = rows[r]
            for (c in row.indices) {
                val key = row[c]
                if (key == ' ') continue
                val argb = sprite.palette[key] ?: continue
                drawRect(
                    color = Color(argb),
                    topLeft = Offset(originX + c * cell, originY + r * cell),
                    // +0.6 overdraw avoids hairline gaps between cells.
                    size = Size(cell + 0.6f, cell + 0.6f),
                )
            }
        }
    }
}
