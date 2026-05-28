package com.aci.hermes.ui.jarvis

import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Test

/**
 * Unit coverage for the pure haptic mapping. The composition-bound
 * [JarvisHaptics] / [rememberJarvisHaptics] paths are exercised on a
 * device; here we only assert the event → constant mapping, which is
 * where the real decision lives.
 */
class JarvisHapticsTest {

    @Test
    fun `tap maps to a light text-handle tick`() {
        assertEquals(
            HapticFeedbackType.TextHandleMove,
            JarvisHapticEvent.TAP.feedbackType(),
        )
    }

    @Test
    fun `confirm maps to a firmer long-press`() {
        assertEquals(
            HapticFeedbackType.LongPress,
            JarvisHapticEvent.CONFIRM.feedbackType(),
        )
    }

    @Test
    fun `warn maps to a firmer long-press`() {
        assertEquals(
            HapticFeedbackType.LongPress,
            JarvisHapticEvent.WARN.feedbackType(),
        )
    }

    @Test
    fun `a primary tap feels different from a deliberate confirm`() {
        assertNotEquals(
            JarvisHapticEvent.TAP.feedbackType(),
            JarvisHapticEvent.CONFIRM.feedbackType(),
        )
    }

    @Test
    fun `every event has a mapping`() {
        // Guards against a new event being added without a haptic.
        JarvisHapticEvent.values().forEach { event ->
            // feedbackType() is exhaustive; this throws if a branch is missing.
            event.feedbackType()
        }
    }

    @Test
    fun `null handle is a safe no-op`() {
        // "Where available" — a device without a haptic handle must not crash.
        val haptics = JarvisHaptics(haptic = null)
        haptics.tap()
        haptics.confirm()
        haptics.warn()
    }
}
