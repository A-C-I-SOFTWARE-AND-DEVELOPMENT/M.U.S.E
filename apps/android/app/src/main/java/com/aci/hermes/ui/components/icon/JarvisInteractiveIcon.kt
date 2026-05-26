package com.aci.hermes.ui.components.icon

import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.gestures.detectVerticalDragGestures
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.onClick
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import com.aci.hermes.ui.jarvis.IconState
import com.aci.hermes.ui.jarvis.JarvisIconColors
import com.aci.hermes.ui.jarvis.JarvisPalette
import kotlin.math.abs

/**
 * Presence-driven, gesture-aware Jarvis Prime icon.
 *
 * This is the *interactive* sibling of the static brand glyph in
 * `ui/components/JarvisPrimeIcon.kt`. The static glyph is purely
 * decorative; this one renders the assistant's current [IconState] and
 * funnels user gestures through [JarvisIconEventHandler].
 *
 * Visual contract is owned by [JarvisIconColors] — the renderer is
 * intentionally dumb and reads `IconAppearance` rather than branching
 * on the state directly. Pulse amplitude is taken from the appearance
 * recipe, which keeps OFFLINE and BLOCKED naturally still (amplitude
 * `0f`). Setting [reducedMotion] forces the pulse off regardless.
 *
 * Lane scope: no overlay permission, no system bubble, no background
 * service touch points. The composable is reachable only when a
 * Hermes screen is on-screen.
 *
 * @param state current visible state, normally produced by
 *   `IconStateMapper.map(IconStateInputs(...))`.
 * @param onEvent funnel for all gesture events. See [JarvisIconEvent].
 * @param size square edge length.
 * @param reducedMotion when true, suppresses the infinite halo pulse.
 *   Callers should propagate the user's system-level reduced-motion
 *   preference here.
 */
@Composable
fun JarvisInteractiveIcon(
    state: IconState,
    onEvent: JarvisIconEventHandler,
    modifier: Modifier = Modifier,
    size: Dp = 72.dp,
    reducedMotion: Boolean = false,
) {
    val appearance = remember(state) { JarvisIconColors.appearanceFor(state) }
    val label = remember(state) { state.semanticLabel() }
    val hint = remember(state) { state.semanticActionHint() }

    val pulse: Float = if (reducedMotion || appearance.pulseAmplitude == 0f) {
        0f
    } else {
        val transition = rememberInfiniteTransition(label = "jarvis-icon-pulse")
        val animated by transition.animateFloat(
            initialValue = 0f,
            targetValue = 1f,
            animationSpec = infiniteRepeatable(
                animation = tween(durationMillis = 1400, easing = LinearEasing),
                repeatMode = RepeatMode.Reverse,
            ),
            label = "jarvis-icon-pulse-value",
        )
        animated * appearance.pulseAmplitude
    }

    val baseAlpha = if (appearance.dim) 0.6f else 1f
    val dragThreshold = with(androidx.compose.ui.platform.LocalDensity.current) {
        (size / 3).toPx()
    }

    Canvas(
        modifier = modifier
            .size(size)
            .alpha(baseAlpha)
            .semantics {
                contentDescription = label
                stateDescription = label
                role = Role.Button
                onClick(label = hint) {
                    onEvent.onEvent(JarvisIconEvent.Tap)
                    true
                }
            }
            .pointerInput(onEvent) {
                detectTapGestures(
                    onTap = { onEvent.onEvent(JarvisIconEvent.Tap) },
                    onLongPress = { onEvent.onEvent(JarvisIconEvent.LongPress) },
                    onDoubleTap = { onEvent.onEvent(JarvisIconEvent.DoubleTap) },
                )
            }
            .pointerInput(onEvent, dragThreshold) {
                var accumulated = 0f
                detectVerticalDragGestures(
                    onDragStart = { accumulated = 0f },
                    onDragEnd = {
                        if (abs(accumulated) >= dragThreshold) {
                            if (accumulated < 0f) {
                                onEvent.onEvent(JarvisIconEvent.SwipeUp)
                            } else {
                                onEvent.onEvent(JarvisIconEvent.SwipeDown)
                            }
                        }
                    },
                    onDragCancel = { accumulated = 0f },
                    onVerticalDrag = { _, delta -> accumulated += delta },
                )
            }
    ) {
        val w = this.size.width
        val h = this.size.height
        val centre = Offset(w / 2f, h / 2f)
        val outerRadius = (minOf(w, h) / 2f) * 0.92f
        val ringRadius = outerRadius * 0.78f
        val coreRadius = outerRadius * 0.40f
        val primeDotRadius = outerRadius * 0.10f
        val haloRadius = outerRadius * (1.0f + 0.10f * pulse)

        // Halo — alpha-baked in JarvisIconColors.appearanceFor().
        drawCircle(
            color = appearance.haloColor,
            radius = haloRadius,
            center = centre,
        )

        // Outer authority ring.
        drawCircle(
            color = appearance.ringColor,
            radius = outerRadius,
            center = centre,
            style = Stroke(width = (outerRadius * 0.045f).coerceAtLeast(1f)),
        )

        // Inner scanning ring (subtle, reuses ring color at lower stroke).
        drawCircle(
            color = appearance.ringColor,
            radius = ringRadius,
            center = centre,
            style = Stroke(width = (outerRadius * 0.022f).coerceAtLeast(0.75f)),
        )

        // Core fill — the presence dot.
        drawCircle(
            color = appearance.coreColor,
            radius = coreRadius,
            center = centre,
        )

        // Prime accent dot — gold, brand-continuous with the static glyph.
        drawCircle(
            color = JarvisPalette.Gold,
            radius = primeDotRadius,
            center = centre,
        )
    }
}
