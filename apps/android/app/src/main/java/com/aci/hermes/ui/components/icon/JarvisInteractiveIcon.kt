package com.aci.hermes.ui.components.icon

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import com.aci.hermes.ui.jarvis.IconState
import com.aci.hermes.ui.jarvis.JarvisIconColors
import com.aci.hermes.ui.jarvis.JarvisPalette

/**
 * Presence-driven Jarvis Prime icon, interactive sibling of the static
 * brand glyph in `ui/components/JarvisPrimeIcon.kt`.
 *
 * Renders the assistant's current [IconState] and emits gesture events
 * through [JarvisIconEventHandler]. This first-pass version covers the
 * Tap event only; long-press, double-tap and swipe gestures land in a
 * follow-up commit once the lane is green on CI.
 *
 * Visual contract is owned by [JarvisIconColors] — the renderer reads
 * the `IconAppearance` recipe rather than branching on the state. The
 * `dim` flag drops alpha for OFFLINE; pulse animation is intentionally
 * deferred to keep this commit minimal.
 */
@Composable
fun JarvisInteractiveIcon(
    state: IconState,
    onEvent: JarvisIconEventHandler,
    modifier: Modifier = Modifier,
    size: Dp = 72.dp,
    @Suppress("UNUSED_PARAMETER") reducedMotion: Boolean = false,
) {
    val appearance = remember(state) { JarvisIconColors.appearanceFor(state) }
    val label = remember(state) { state.semanticLabel() }
    val baseAlpha: Float = if (appearance.dim) 0.6f else 1f

    Canvas(
        modifier = modifier
            .size(size)
            .alpha(baseAlpha)
            .semantics { contentDescription = label }
            .clickable { onEvent.onEvent(JarvisIconEvent.Tap) }
    ) {
        val canvasSize = this.size
        val w = canvasSize.width
        val h = canvasSize.height
        val centre = Offset(w / 2f, h / 2f)
        val outerRadius = (minOf(w, h) / 2f) * 0.92f
        val ringRadius = outerRadius * 0.78f
        val coreRadius = outerRadius * 0.40f
        val primeDotRadius = outerRadius * 0.10f

        drawCircle(
            color = appearance.haloColor,
            radius = outerRadius * 1.06f,
            center = centre,
        )

        drawCircle(
            color = appearance.ringColor,
            radius = outerRadius,
            center = centre,
            style = Stroke(width = (outerRadius * 0.045f).coerceAtLeast(1f)),
        )

        drawCircle(
            color = appearance.ringColor,
            radius = ringRadius,
            center = centre,
            style = Stroke(width = (outerRadius * 0.022f).coerceAtLeast(0.75f)),
        )

        drawCircle(
            color = appearance.coreColor,
            radius = coreRadius,
            center = centre,
        )

        drawCircle(
            color = JarvisPalette.Gold,
            radius = primeDotRadius,
            center = centre,
        )
    }
}
