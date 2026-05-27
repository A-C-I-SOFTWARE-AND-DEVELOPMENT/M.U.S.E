package com.aci.hermes.ui.screens.live

import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.drawscope.Stroke
import com.aci.hermes.ui.theme.HermesCyan
import com.aci.hermes.ui.theme.HermesGold
import kotlin.math.cos
import kotlin.math.sin

@Composable
fun JarvisLiveParticles(
    enabled: Boolean,
    modifier: Modifier = Modifier,
) {
    if (!enabled) return
    val transition = rememberInfiniteTransition(label = "jarvis-particles")
    val rotation by transition.animateFloat(
        initialValue = 0f,
        targetValue = 360f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = 24_000, easing = LinearEasing),
            repeatMode = RepeatMode.Restart,
        ),
        label = "jarvis-particles-rotation",
    )

    Canvas(modifier = modifier.fillMaxSize()) {
        val cx = size.width / 2f
        val cy = size.height / 2.6f
        val radius = size.minDimension * 0.42f
        val count = 28
        repeat(count) { i ->
            val angle = Math.toRadians((rotation + (360.0 / count) * i)).toFloat()
            val rr = radius * (0.6f + (i % 5) * 0.08f)
            val x = cx + cos(angle) * rr
            val y = cy + sin(angle) * rr
            val color = if (i % 3 == 0) HermesCyan.copy(alpha = 0.18f)
                        else HermesGold.copy(alpha = 0.12f)
            drawCircle(
                color = color,
                radius = 2.4f,
                center = Offset(x, y),
            )
        }
        drawCircle(
            color = HermesGold.copy(alpha = 0.06f),
            radius = radius,
            center = Offset(cx, cy),
            style = Stroke(width = 1.2f),
        )
    }
}
