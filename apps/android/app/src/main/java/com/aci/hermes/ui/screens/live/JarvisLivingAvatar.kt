package com.aci.hermes.ui.screens.live

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
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import com.aci.hermes.ui.theme.HermesCrimson
import com.aci.hermes.ui.theme.HermesCyan
import com.aci.hermes.ui.theme.HermesGold
import com.aci.hermes.ui.theme.HermesGoldDeep
import com.aci.hermes.ui.theme.HermesViolet

private data class AvatarPalette(
    val core: Color,
    val ring: Color,
    val halo: Color,
)

@Composable
fun JarvisLivingAvatar(
    state: JarvisLiveState,
    motionEnabled: Boolean,
    contentDescription: String,
    modifier: Modifier = Modifier,
) {
    val palette = paletteFor(state)
    val transition = rememberInfiniteTransition(label = "jarvis-avatar")
    val pulse by transition.animateFloat(
        initialValue = if (motionEnabled) 0.92f else 1f,
        targetValue = if (motionEnabled) 1.08f else 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(pulseDurationFor(state), easing = LinearEasing),
            repeatMode = RepeatMode.Reverse,
        ),
        label = "jarvis-pulse",
    )
    val ringSweep by transition.animateFloat(
        initialValue = 0f,
        targetValue = if (motionEnabled) 360f else 0f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = 5200, easing = LinearEasing),
            repeatMode = RepeatMode.Restart,
        ),
        label = "jarvis-sweep",
    )

    Box(
        modifier = modifier
            .size(220.dp)
            .semantics { this.contentDescription = contentDescription },
        contentAlignment = Alignment.Center,
    ) {
        Canvas(modifier = Modifier.size(220.dp)) {
            val center = Offset(size.width / 2f, size.height / 2f)
            val baseRadius = size.minDimension / 2f
            val haloRadius = baseRadius * pulse

            drawCircle(
                brush = Brush.radialGradient(
                    colors = listOf(palette.halo.copy(alpha = 0.55f), Color.Transparent),
                    center = center,
                    radius = haloRadius,
                ),
                radius = haloRadius,
                center = center,
            )

            val ringStroke = 4f
            drawCircle(
                color = palette.ring.copy(alpha = 0.65f),
                radius = baseRadius * 0.74f,
                center = center,
                style = androidx.compose.ui.graphics.drawscope.Stroke(width = ringStroke),
            )

            if (motionEnabled) {
                val arcWidth = 6f
                drawArc(
                    color = palette.ring,
                    startAngle = ringSweep,
                    sweepAngle = 90f,
                    useCenter = false,
                    topLeft = Offset(
                        center.x - baseRadius * 0.85f,
                        center.y - baseRadius * 0.85f,
                    ),
                    size = androidx.compose.ui.geometry.Size(
                        baseRadius * 1.7f,
                        baseRadius * 1.7f,
                    ),
                    style = androidx.compose.ui.graphics.drawscope.Stroke(width = arcWidth),
                )
            }

            drawCircle(
                brush = Brush.radialGradient(
                    colors = listOf(palette.core, palette.core.copy(alpha = 0.05f)),
                    center = center,
                    radius = baseRadius * 0.55f,
                ),
                radius = baseRadius * 0.55f,
                center = center,
            )
        }
    }
}

private fun paletteFor(state: JarvisLiveState): AvatarPalette = when (state) {
    JarvisLiveState.Idle -> AvatarPalette(
        core = HermesGoldDeep.copy(alpha = 0.55f),
        ring = HermesGold.copy(alpha = 0.45f),
        halo = HermesViolet.copy(alpha = 0.30f),
    )
    JarvisLiveState.Listening -> AvatarPalette(
        core = HermesCyan,
        ring = HermesCyan,
        halo = HermesCyan.copy(alpha = 0.45f),
    )
    JarvisLiveState.Thinking -> AvatarPalette(
        core = HermesGold,
        ring = HermesGoldDeep,
        halo = HermesViolet.copy(alpha = 0.55f),
    )
    JarvisLiveState.Working -> AvatarPalette(
        core = HermesGold,
        ring = HermesGold,
        halo = HermesGoldDeep.copy(alpha = 0.65f),
    )
    JarvisLiveState.Speaking -> AvatarPalette(
        core = HermesCyan,
        ring = HermesGold,
        halo = HermesCyan.copy(alpha = 0.55f),
    )
    JarvisLiveState.ApprovalNeeded -> AvatarPalette(
        core = HermesGold,
        ring = HermesGold,
        halo = HermesGold.copy(alpha = 0.55f),
    )
    JarvisLiveState.Blocked -> AvatarPalette(
        core = HermesCrimson.copy(alpha = 0.75f),
        ring = HermesGold,
        halo = HermesCrimson.copy(alpha = 0.45f),
    )
    JarvisLiveState.EmergencyStop -> AvatarPalette(
        core = HermesCrimson,
        ring = HermesCrimson,
        halo = HermesCrimson.copy(alpha = 0.65f),
    )
}

private fun pulseDurationFor(state: JarvisLiveState): Int = when (state) {
    JarvisLiveState.Idle -> 4200
    JarvisLiveState.Listening -> 1400
    JarvisLiveState.Thinking -> 1800
    JarvisLiveState.Working -> 1200
    JarvisLiveState.Speaking -> 700
    JarvisLiveState.ApprovalNeeded -> 1600
    JarvisLiveState.Blocked -> 2400
    JarvisLiveState.EmergencyStop -> 2800
}
