package com.aci.hermes.ui.jarvis

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Asserts every [IconState] has a usable accessibility label — this is
 * the surface TalkBack reads when the icon is focused.
 */
class IconStateAccessibilityTest {

    @Test
    fun `every state has a non-blank accessibility label`() {
        IconState.values().forEach { state ->
            val label = state.accessibilityLabel()
            assertNotNull("label missing for $state", label)
            assertTrue("label blank for $state", label.isNotBlank())
        }
    }

    @Test
    fun `accessibility labels are unique across states`() {
        val labels = IconState.values().map { it.accessibilityLabel() }
        assertEquals(
            "states and labels must be 1:1",
            labels.size,
            labels.toSet().size,
        )
    }

    @Test
    fun `serious and critical labels are visually distinguishable`() {
        // Labels are what blind users hear — they must not be the same.
        assertNotEquals(
            IconState.SERIOUS_ACTION_PENDING.accessibilityLabel(),
            IconState.CRITICAL_ACTION_PENDING.accessibilityLabel(),
        )
    }

    @Test
    fun `serious and critical have distinct appearance colors`() {
        val serious = JarvisIconColors.appearanceFor(IconState.SERIOUS_ACTION_PENDING)
        val critical = JarvisIconColors.appearanceFor(IconState.CRITICAL_ACTION_PENDING)
        assertNotEquals(serious.ringColor, critical.ringColor)
        assertNotEquals(serious.coreColor, critical.coreColor)
    }

    @Test
    fun `offline state is the only state marked dim`() {
        IconState.values().forEach { state ->
            val appearance = JarvisIconColors.appearanceFor(state)
            if (state == IconState.OFFLINE) {
                assertTrue("offline must be dim", appearance.dim)
            } else {
                assertTrue("$state must not be dim", !appearance.dim)
            }
        }
    }

    @Test
    fun `offline and blocked have zero pulse amplitude`() {
        assertEquals(0f, JarvisIconColors.appearanceFor(IconState.OFFLINE).pulseAmplitude)
        assertEquals(0f, JarvisIconColors.appearanceFor(IconState.BLOCKED).pulseAmplitude)
    }

    @Test
    fun `listening glow uses cyan`() {
        val appearance = JarvisIconColors.appearanceFor(IconState.LISTENING)
        assertEquals(JarvisPalette.Cyan, appearance.coreColor)
        assertEquals(JarvisPalette.Cyan, appearance.ringColor)
    }

    @Test
    fun `approval ring uses violet`() {
        // FU-17b: the attention states use the violet spectral ring
        // (--ring-2) rather than the retired gold. Both approval states
        // share the violet ring; SERIOUS escalates by also taking a violet
        // core (asserted separately), keeping the two perceivably distinct.
        assertEquals(
            JarvisPalette.Violet,
            JarvisIconColors.appearanceFor(IconState.WAITING_FOR_APPROVAL).ringColor,
        )
        assertEquals(
            JarvisPalette.Violet,
            JarvisIconColors.appearanceFor(IconState.SERIOUS_ACTION_PENDING).ringColor,
        )
    }

    @Test
    fun `waiting and serious are perceivably distinct`() {
        // FU-17b: with the gold→white→violet remap, the two attention states
        // must not collapse into one another. They share the violet ring but
        // differ in the core (white for WAITING, violet for SERIOUS).
        val waiting = JarvisIconColors.appearanceFor(IconState.WAITING_FOR_APPROVAL)
        val serious = JarvisIconColors.appearanceFor(IconState.SERIOUS_ACTION_PENDING)
        assertNotEquals(waiting.coreColor, serious.coreColor)
    }

    @Test
    fun `critical ring uses red`() {
        assertEquals(
            JarvisPalette.Red,
            JarvisIconColors.appearanceFor(IconState.CRITICAL_ACTION_PENDING).ringColor,
        )
    }

    @Test
    fun `completion flash uses green`() {
        val appearance = JarvisIconColors.appearanceFor(IconState.COMPLETE)
        assertEquals(JarvisPalette.Green, appearance.coreColor)
        assertEquals(JarvisPalette.Green, appearance.ringColor)
    }
}
