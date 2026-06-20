package com.aci.hermes.ui.designsystem

import androidx.compose.animation.core.CubicBezierEasing
import androidx.compose.animation.core.Easing
import androidx.compose.animation.core.FiniteAnimationSpec
import androidx.compose.animation.core.tween

/**
 * muse motion language.
 *
 * Three deliberate durations and two easings shared by every component in
 * the design system, so animation feels like one hand drew it. Numbers and
 * curves echo Material 3's emphasized / standard motion, kept restrained for
 * the "command-console" feel of the Singularity surface (no bouncy springs;
 * the core blazes, it does not wobble).
 *
 * Honour the user's reduced-motion preference at the *call site* — these are
 * just the tokens, not a policy.
 */
object museMotion {

    // Durations, in milliseconds.
    /** Quick — pressed states, dot pulses, chip toggles. */
    const val DurationFast = 150

    /** Standard — the default for most enter/exit and color transitions. */
    const val DurationStandard = 250

    /** Deliberate — phase-rail advances, larger surface reveals. */
    const val DurationEmphasized = 350

    /**
     * Emphasized easing (Material 3 "emphasized" decelerate). Used when a
     * surface should arrive with intent — phase advances, empty-state reveals.
     */
    val EmphasizedEasing: Easing = CubicBezierEasing(0.05f, 0.7f, 0.1f, 1f)

    /**
     * Standard easing (Material 3 "standard"). The everyday curve for color
     * and small movement — even on both ends, no drama.
     */
    val StandardEasing: Easing = CubicBezierEasing(0.2f, 0f, 0f, 1f)

    /** A `tween` at [DurationFast] on [StandardEasing]. */
    fun <T> fast(): FiniteAnimationSpec<T> =
        tween(durationMillis = DurationFast, easing = StandardEasing)

    /** A `tween` at [DurationStandard] on [StandardEasing]. */
    fun <T> standard(): FiniteAnimationSpec<T> =
        tween(durationMillis = DurationStandard, easing = StandardEasing)

    /** A `tween` at [DurationEmphasized] on [EmphasizedEasing]. */
    fun <T> emphasized(): FiniteAnimationSpec<T> =
        tween(durationMillis = DurationEmphasized, easing = EmphasizedEasing)
}
