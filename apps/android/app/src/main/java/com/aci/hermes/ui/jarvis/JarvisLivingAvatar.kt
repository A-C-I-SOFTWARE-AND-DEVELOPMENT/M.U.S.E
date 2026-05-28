package com.aci.hermes.ui.jarvis

import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp

/**
 * Composition-local for the device's reduced-motion preference.
 *
 * The platform's accessibility setting (`Settings.Global.ANIMATOR_DURATION_SCALE
 * == 0f`, or Android 13+ `AccessibilityManager.isReducedMotionEnabled`)
 * is resolved once in the screen layer and pushed down through this
 * composition-local. Tests use the default (`false`) or override
 * directly.
 */
val LocalReduceMotion = staticCompositionLocalOf { false }

/**
 * The living avatar composable.
 *
 * Renders the [AvatarRenderSpec] as a breathing/pulsing pictogram with
 * a status string underneath. Honors `reducedMotion` by collapsing
 * the breathing animation to a static frame.
 *
 * Accessibility: the composable exposes the status string as the
 * content description and the icon-state name as the state
 * description, so TalkBack users hear "Jarvis is thinking. THINKING."
 * not just an opaque shape.
 *
 * @param spec the resolved render spec from [AvatarStateMapper.map].
 * @param size diameter of the avatar canvas. Defaults to 192 dp,
 *             which fits the full-screen `JarvisLiveScreen` cleanly.
 * @param modifier external layout modifiers.
 */
@Composable
fun JarvisLivingAvatar(
    spec: AvatarRenderSpec,
    size: Dp = 192.dp,
    modifier: Modifier = Modifier,
) {
    val statusText = stringResource(spec.statusStringResId)
    val stateName = spec.iconState.name

    val animatedPulse: Float = if (spec.reducedMotion || spec.appearance.pulseAmplitude == 0f) {
        // Static frame: hold the resting amplitude (which is `pulseAmplitude`
        // by definition, see `IconAppearance`).
        spec.appearance.pulseAmplitude
    } else {
        val transition = rememberInfiniteTransition(label = "jarvis-avatar-pulse")
        val value by transition.animateFloat(
            initialValue = 0f,
            targetValue = spec.appearance.pulseAmplitude,
            animationSpec = infiniteRepeatable(
                animation = tween(durationMillis = 1800, easing = LinearEasing),
                repeatMode = RepeatMode.Reverse,
            ),
            label = "jarvis-avatar-pulse-value",
        )
        value
    }

    Canvas(
        modifier = modifier
            .size(size)
            .alpha(if (spec.appearance.dim) 0.55f else 1f)
            .semantics {
                contentDescription = statusText
                stateDescription = stateName
            },
    ) {
        val radius = this.size.minDimension / 2f
        val center = Offset(this.size.width / 2f, this.size.height / 2f)
        val pulseRadius = radius * (1f + animatedPulse * 0.08f)

        // Halo
        drawCircle(
            color = spec.appearance.haloColor,
            radius = pulseRadius,
            center = center,
        )
        // Ring
        drawCircle(
            color = spec.appearance.ringColor,
            radius = radius * 0.85f,
            center = center,
            style = Stroke(width = radius * 0.06f),
        )
        // Core
        drawCircle(
            color = spec.appearance.coreColor,
            radius = radius * 0.55f,
            center = center,
        )
    }
}

/**
 * Diameter constants used by [JarvisLivingAvatar] consumers. Kept
 * here so the live-screen and a future home-cockpit thumbnail share
 * one source of truth.
 */
object JarvisLivingAvatarDimens {
    val FullScreen: Dp = 192.dp
    val Cockpit: Dp = 96.dp
    val Inline: Dp = 56.dp
}
