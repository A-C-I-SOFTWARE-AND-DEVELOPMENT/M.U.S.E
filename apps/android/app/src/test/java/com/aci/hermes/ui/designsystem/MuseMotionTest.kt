package com.aci.hermes.ui.designsystem

import androidx.compose.animation.core.TweenSpec
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Pure-JVM checks for the [MuseMotion] tokens — no Compose runtime needed.
 * Guards the contract other components rely on: the three named durations and
 * that the `tween` factories actually carry those durations.
 */
class MuseMotionTest {

    @Test
    fun `durations ascend fast to emphasized`() {
        assertEquals(150, MuseMotion.DurationFast)
        assertEquals(250, MuseMotion.DurationStandard)
        assertEquals(350, MuseMotion.DurationEmphasized)
        assertTrue(MuseMotion.DurationFast < MuseMotion.DurationStandard)
        assertTrue(MuseMotion.DurationStandard < MuseMotion.DurationEmphasized)
    }

    @Test
    fun `tween factories carry the matching duration`() {
        assertEquals(MuseMotion.DurationFast, (MuseMotion.fast<Float>() as TweenSpec).durationMillis)
        assertEquals(MuseMotion.DurationStandard, (MuseMotion.standard<Float>() as TweenSpec).durationMillis)
        assertEquals(MuseMotion.DurationEmphasized, (MuseMotion.emphasized<Float>() as TweenSpec).durationMillis)
    }
}
