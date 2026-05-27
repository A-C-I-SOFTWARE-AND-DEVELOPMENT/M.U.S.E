package com.aci.hermes.ui.components

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import com.aci.hermes.ui.theme.JarvisCyan
import com.aci.hermes.ui.theme.JarvisGold
import com.aci.hermes.ui.theme.JarvisGoldGlow

/**
 * Jarvis Prime brand glyph for in-app use (splash, headers, empty states).
 *
 * Two concentric rings (gold + cyan) around a luminous gold "prime dot"
 * — the watchful eye. Vector-drawn so it scales cleanly at any density.
 *
 * @param size square edge length
 * @param showGlow when true, draws a soft gold halo behind the rings.
 *                 Honour the user's reduced-motion preference at the
 *                 call site; the glyph itself is static.
 */
@Composable
fun JarvisPrimeIcon(
    size: Dp = 64.dp,
    showGlow: Boolean = true,
    modifier: Modifier = Modifier,
) {
    Canvas(
        modifier = modifier.size(size)
    ) {
        val w = this.size.width
        val h = this.size.height
        val centre = Offset(w / 2f, h / 2f)
        val outerRadius = (minOf(w, h) / 2f) * 0.92f
        val innerRadius = outerRadius * 0.78f
        val dotRadius   = outerRadius * 0.10f

        // Soft authority glow — single drawCircle, no animation cost.
        if (showGlow) {
            drawCircle(
                color = JarvisGoldGlow,
                radius = outerRadius * 1.06f,
                center = centre
            )
        }

        // Outer authority ring (gold)
        drawCircle(
            color = JarvisGold,
            radius = outerRadius,
            center = centre,
            style = Stroke(width = (outerRadius * 0.045f).coerceAtLeast(1f))
        )

        // Inner scanning ring (cyan, thinner)
        drawCircle(
            color = JarvisCyan,
            radius = innerRadius,
            center = centre,
            style = Stroke(width = (outerRadius * 0.022f).coerceAtLeast(0.75f))
        )

        // Prime dot (the watchful eye)
        drawCircle(
            color = JarvisGold,
            radius = dotRadius,
            center = centre
        )
    }
}
