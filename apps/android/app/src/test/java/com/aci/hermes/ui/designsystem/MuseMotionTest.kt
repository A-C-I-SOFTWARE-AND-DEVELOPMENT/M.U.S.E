package com.aci.hermes.ui.designsystem

import androidx.compose.animation.core.TweenSpec
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Pure-JVM checks for the [museMotion] tokens — no Compose runtime needed.
 * Guards the contract other components rely on: the three named durations and
 * that the `tween` factories actually carry those durations.
 */
class museMotionTest {

    @Test
    fun `durations ascend fast to emphasized`() {
        assertEquals(150, museMotion.DurationFast)
        assertEquals(250, museMotion.DurationStandard)
        assertEquals(350, museMotion.DurationEmphasized)
        assertTrue(museMotion.DurationFast < museMotion.DurationStandard)
        assertTrue(museMotion.DurationStandard < museMotion.DurationEmphasized)
    }

    @Test
    fun `tween factories carry the matching duration`() {
        assertEquals(museMotion.DurationFast, (museMotion.fast<Float>() as TweenSpec).durationMillis)
        assertEquals(museMotion.DurationStandard, (museMotion.standard<Float>() as TweenSpec).durationMillis)
        assertEquals(museMotion.DurationEmphasized, (museMotion.emphasized<Float>() as TweenSpec).durationMillis)
    }
}
