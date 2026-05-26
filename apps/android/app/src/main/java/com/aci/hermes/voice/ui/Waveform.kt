package com.aci.hermes.voice.ui

import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import kotlin.math.PI
import kotlin.math.sin

/**
 * Decorative animated waveform shown while the recognizer is
 * listening. Placeholder — does not visualise real RMS levels yet.
 */
@Composable
fun ListeningWaveform(
    modifier: Modifier = Modifier,
    bars: Int = 24,
    color: Color = MaterialTheme.colorScheme.primary,
) {
    val infinite = rememberInfiniteTransition(label = "voice-waveform")
    val phase by infinite.animateFloat(
        initialValue = 0f,
        targetValue = (2f * PI).toFloat(),
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = 1100, easing = LinearEasing),
            repeatMode = RepeatMode.Restart,
        ),
        label = "voice-waveform-phase",
    )

    Canvas(
        modifier = modifier
            .fillMaxWidth()
            .height(56.dp),
    ) {
        val barWidth = size.width / (bars * 1.6f)
        val gap = barWidth * 0.6f
        val centerY = size.height / 2f
        for (i in 0 until bars) {
            val t = i.toFloat() / bars
            val amplitude = (0.30f + 0.70f * (0.5f + 0.5f * sin(phase + t * (2f * PI).toFloat() * 1.5f)))
            val h = size.height * amplitude
            val x = i * (barWidth + gap)
            drawRect(
                color = color,
                topLeft = Offset(x = x, y = centerY - h / 2f),
                size = androidx.compose.ui.geometry.Size(width = barWidth, height = h),
            )
        }
    }
}
