package com.aci.hermes.ui.screens.live

import com.aci.hermes.data.automation.AvatarClip
import com.aci.hermes.data.life.AvatarBehavior
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class AvatarAnimationTest {

    @Test
    fun `active clip always wins over state and behavior`() {
        val inputs = AvatarAnimation.inputsFor(
            state = JarvisLiveState.Idle,
            behavior = AvatarBehavior.SLEEP,
            activeClip = AvatarClip.PUSH,
            motionEnabled = true,
        )
        assertEquals(AvatarPose.PUSH, inputs.pose)
    }

    @Test
    fun `agent work state maps to its pose when no clip is playing`() {
        val inputs = AvatarAnimation.inputsFor(
            state = JarvisLiveState.Working,
            behavior = AvatarBehavior.WANDER,
            activeClip = null,
            motionEnabled = true,
        )
        assertEquals(AvatarPose.WORK, inputs.pose)
    }

    @Test
    fun `idle defers to ambient behavior`() {
        assertEquals(
            AvatarPose.SLEEP,
            AvatarAnimation.inputsFor(JarvisLiveState.Idle, AvatarBehavior.SLEEP, null, true).pose,
        )
        assertEquals(
            AvatarPose.WANDER,
            AvatarAnimation.inputsFor(JarvisLiveState.Idle, AvatarBehavior.WANDER, null, true).pose,
        )
    }

    @Test
    fun `sleep suppresses motion even when motion enabled`() {
        val inputs = AvatarAnimation.inputsFor(JarvisLiveState.Idle, AvatarBehavior.SLEEP, null, true)
        assertFalse(inputs.motionEnabled)
    }

    @Test
    fun `emergency suppresses motion`() {
        val inputs = AvatarAnimation.inputsFor(JarvisLiveState.EmergencyStop, AvatarBehavior.IDLE, null, true)
        assertEquals(AvatarPose.EMERGENCY, inputs.pose)
        assertFalse(inputs.motionEnabled)
    }

    @Test
    fun `reduced motion clamps motion off but keeps the pose`() {
        val inputs = AvatarAnimation.inputsFor(JarvisLiveState.Working, AvatarBehavior.IDLE, null, false)
        assertEquals(AvatarPose.WORK, inputs.pose)
        assertFalse(inputs.motionEnabled)
    }

    @Test
    fun `speaking is the highest energy`() {
        val speak = AvatarAnimation.inputsFor(JarvisLiveState.Speaking, AvatarBehavior.IDLE, null, true)
        val think = AvatarAnimation.inputsFor(JarvisLiveState.Thinking, AvatarBehavior.IDLE, null, true)
        assertTrue(speak.energy > think.energy)
        assertEquals(1.0f, speak.energy)
    }
}
