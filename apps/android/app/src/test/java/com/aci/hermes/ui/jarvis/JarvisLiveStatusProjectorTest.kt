package com.aci.hermes.ui.jarvis

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Pure-logic tests for [JarvisLiveStatusProjector]. The projector is a
 * pure function, so no mocking is required.
 *
 * The most important contract this suite pins:
 *   - every state produces non-blank pill text and status line, so the
 *     user never sees "blank UI"
 *   - safety-critical signals (emergency stop, gateway offline,
 *     blocked, approval) outrank lower-priority activity claims
 *   - reducedMotion never silences the status text, only the motion
 *     overlay
 *   - a long-running working task never looks idle
 */
class JarvisLiveStatusProjectorTest {

    @Test
    fun `every IconState produces non-blank pill and status line`() {
        IconState.values().forEach { state ->
            val status = JarvisLiveStatusProjector.project(
                JarvisLiveInputs(iconState = state),
            )
            assertTrue(
                "blank pill for $state",
                status.statusPillText.isNotBlank(),
            )
            assertTrue(
                "blank statusLine for $state",
                status.statusLine.isNotBlank(),
            )
        }
    }

    @Test
    fun `emergency stop outranks every other state`() {
        IconState.values().forEach { state ->
            val status = JarvisLiveStatusProjector.project(
                JarvisLiveInputs(
                    iconState = state,
                    emergencyStopActive = true,
                    gatewayOnline = false,
                    approvalQueueCount = 5,
                    chatStream = JarvisChatStreamState.SPEAKING,
                    workerPhase = JarvisWorkerPhase.CODING,
                ),
            )
            assertEquals("EMERGENCY STOP", status.statusPillText)
            assertEquals("Emergency stop active.", status.statusLine)
            assertEquals(
                JarvisAvatarActivity.CrimsonLockedRing,
                status.avatarActivity,
            )
            assertTrue(status.shouldShowEmergencyButton)
            assertFalse(status.shouldShowApprovalButton)
        }
    }

    @Test
    fun `gateway offline outranks every non-emergency state`() {
        IconState.values().forEach { state ->
            if (state == IconState.OFFLINE) return@forEach
            val status = JarvisLiveStatusProjector.project(
                JarvisLiveInputs(
                    iconState = state,
                    gatewayOnline = false,
                ),
            )
            assertEquals(IconState.OFFLINE, status.iconState)
            assertEquals("Offline", status.statusPillText)
            assertEquals("Gateway offline.", status.statusLine)
            assertEquals(JarvisAvatarActivity.Static, status.avatarActivity)
        }
    }

    @Test
    fun `blocked outranks working`() {
        val status = JarvisLiveStatusProjector.project(
            JarvisLiveInputs(
                iconState = IconState.BLOCKED,
                workerPhase = JarvisWorkerPhase.CODING,
            ),
        )
        assertEquals("Blocked", status.statusPillText)
        assertEquals("Blocked — action needed.", status.statusLine)
    }

    @Test
    fun `approval queue count outranks idle`() {
        val status = JarvisLiveStatusProjector.project(
            JarvisLiveInputs(
                iconState = IconState.IDLE,
                approvalQueueCount = 1,
            ),
        )
        assertEquals("Approval needed", status.statusPillText)
        assertEquals("Waiting for your approval.", status.statusLine)
        assertTrue(status.shouldShowApprovalButton)
        assertEquals(JarvisAvatarActivity.GoldRing, status.avatarActivity)
    }

    @Test
    fun `WAITING_FOR_APPROVAL maps to gold ring`() {
        val status = JarvisLiveStatusProjector.project(
            JarvisLiveInputs(iconState = IconState.WAITING_FOR_APPROVAL),
        )
        assertEquals("Approval needed", status.statusPillText)
        assertTrue(status.shouldShowApprovalButton)
        assertEquals(JarvisAvatarActivity.GoldRing, status.avatarActivity)
    }

    @Test
    fun `critical action maps to crimson ring with approval`() {
        val status = JarvisLiveStatusProjector.project(
            JarvisLiveInputs(iconState = IconState.CRITICAL_ACTION_PENDING),
        )
        assertEquals("Critical approval", status.statusPillText)
        assertEquals(
            JarvisAvatarActivity.CrimsonLockedRing,
            status.avatarActivity,
        )
        assertTrue(status.shouldShowApprovalButton)
        assertFalse(status.shouldShowEmergencyButton)
    }

    @Test
    fun `reducedMotion disables shouldPulse for every state`() {
        IconState.values().forEach { state ->
            val status = JarvisLiveStatusProjector.project(
                JarvisLiveInputs(iconState = state, reducedMotion = true),
            )
            assertFalse(
                "shouldPulse must be false for $state under reducedMotion",
                status.shouldPulse,
            )
        }
    }

    @Test
    fun `reducedMotion still produces correct pill and status line`() {
        val a = JarvisLiveStatusProjector.project(
            JarvisLiveInputs(
                iconState = IconState.WORKING,
                workerPhase = JarvisWorkerPhase.TESTING,
                reducedMotion = false,
            ),
        )
        val b = JarvisLiveStatusProjector.project(
            JarvisLiveInputs(
                iconState = IconState.WORKING,
                workerPhase = JarvisWorkerPhase.TESTING,
                reducedMotion = true,
            ),
        )
        assertEquals(a.statusPillText, b.statusPillText)
        assertEquals(a.statusLine, b.statusLine)
        // Motion overlay collapsed to Static when reduced.
        assertEquals(JarvisAvatarActivity.CheckPulse, a.avatarActivity)
        assertEquals(JarvisAvatarActivity.Static, b.avatarActivity)
    }

    @Test
    fun `reducedMotion preserves attention rings`() {
        val gold = JarvisLiveStatusProjector.project(
            JarvisLiveInputs(
                iconState = IconState.WAITING_FOR_APPROVAL,
                reducedMotion = true,
            ),
        )
        assertEquals(JarvisAvatarActivity.GoldRing, gold.avatarActivity)
        val crimson = JarvisLiveStatusProjector.project(
            JarvisLiveInputs(
                iconState = IconState.IDLE,
                emergencyStopActive = true,
                reducedMotion = true,
            ),
        )
        assertEquals(
            JarvisAvatarActivity.CrimsonLockedRing,
            crimson.avatarActivity,
        )
    }

    @Test
    fun `long-running working task does not look idle`() {
        val status = JarvisLiveStatusProjector.project(
            JarvisLiveInputs(
                iconState = IconState.WORKING,
                workerPhase = JarvisWorkerPhase.CODING,
                activeTaskTitle = "Refactor auth module",
                activeTaskStepLabel = "Updating session manager",
                activeTaskStepIndex = 3,
                activeTaskStepTotal = 5,
            ),
        )
        assertEquals("Coding", status.statusPillText)
        assertEquals("Editing the files.", status.statusLine)
        assertEquals(JarvisAvatarActivity.TaskOrbit, status.avatarActivity)
        assertEquals("Refactor auth module", status.detailLine)
        assertNotNull(status.progressLabel)
        assertTrue(
            "progress must mention step",
            status.progressLabel!!.contains("Step 3 of 5"),
        )
        assertTrue(status.progressLabel!!.contains("Updating session manager"))
    }

    @Test
    fun `worker phase TESTING produces check pulse`() {
        val status = JarvisLiveStatusProjector.project(
            JarvisLiveInputs(
                iconState = IconState.WORKING,
                workerPhase = JarvisWorkerPhase.TESTING,
            ),
        )
        assertEquals("Testing", status.statusPillText)
        assertEquals("Running checks.", status.statusLine)
        assertEquals(JarvisAvatarActivity.CheckPulse, status.avatarActivity)
    }

    @Test
    fun `worker phase REVIEWING produces scan ring`() {
        val status = JarvisLiveStatusProjector.project(
            JarvisLiveInputs(
                iconState = IconState.WORKING,
                workerPhase = JarvisWorkerPhase.REVIEWING,
            ),
        )
        assertEquals("Reviewing", status.statusPillText)
        assertEquals("Reviewing the result.", status.statusLine)
        assertEquals(JarvisAvatarActivity.ScanRing, status.avatarActivity)
    }

    @Test
    fun `chatStream THINKING with iconState IDLE produces animated dots`() {
        val status = JarvisLiveStatusProjector.project(
            JarvisLiveInputs(
                iconState = IconState.IDLE,
                chatStream = JarvisChatStreamState.THINKING,
            ),
        )
        assertEquals("Thinking", status.statusPillText)
        assertEquals("Thinking through it.", status.statusLine)
        assertEquals(JarvisAvatarActivity.AnimatedDots, status.avatarActivity)
    }

    @Test
    fun `chatStream SPEAKING produces mouth pulse even when iconState is IDLE`() {
        val status = JarvisLiveStatusProjector.project(
            JarvisLiveInputs(
                iconState = IconState.IDLE,
                chatStream = JarvisChatStreamState.SPEAKING,
            ),
        )
        assertEquals("Speaking", status.statusPillText)
        assertEquals("Talking it through.", status.statusLine)
        assertEquals(JarvisAvatarActivity.MouthPulse, status.avatarActivity)
    }

    @Test
    fun `LISTENING reports listening`() {
        val status = JarvisLiveStatusProjector.project(
            JarvisLiveInputs(iconState = IconState.LISTENING),
        )
        assertEquals("Listening", status.statusPillText)
        assertEquals("Listening.", status.statusLine)
        assertEquals(JarvisAvatarActivity.Subtle, status.avatarActivity)
    }

    @Test
    fun `COMPLETE flashes done`() {
        val status = JarvisLiveStatusProjector.project(
            JarvisLiveInputs(iconState = IconState.COMPLETE),
        )
        assertEquals("Done", status.statusPillText)
        assertEquals("Done. Ready when you are.", status.statusLine)
        assertEquals(JarvisAvatarActivity.CheckPulse, status.avatarActivity)
    }

    @Test
    fun `WARNING surfaces heads-up`() {
        val status = JarvisLiveStatusProjector.project(
            JarvisLiveInputs(iconState = IconState.WARNING),
        )
        assertEquals("Heads up", status.statusPillText)
        assertEquals("Heads up — non-fatal issue.", status.statusLine)
        assertEquals(JarvisAvatarActivity.Subtle, status.avatarActivity)
    }

    @Test
    fun `progress label omitted when no step info provided`() {
        val status = JarvisLiveStatusProjector.project(
            JarvisLiveInputs(iconState = IconState.IDLE),
        )
        assertNull(status.progressLabel)
    }

    @Test
    fun `progress label built from step index and total alone`() {
        val status = JarvisLiveStatusProjector.project(
            JarvisLiveInputs(
                iconState = IconState.WORKING,
                workerPhase = JarvisWorkerPhase.PLANNING,
                activeTaskStepIndex = 2,
                activeTaskStepTotal = 4,
            ),
        )
        assertEquals("Step 2 of 4", status.progressLabel)
    }

    @Test
    fun `no state combination returns blank UI`() {
        val phases = JarvisWorkerPhase.values()
        val streams = JarvisChatStreamState.values()
        IconState.values().forEach { state ->
            phases.forEach { phase ->
                streams.forEach { stream ->
                    listOf(false, true).forEach { reduced ->
                        listOf(false, true).forEach { online ->
                            val status = JarvisLiveStatusProjector.project(
                                JarvisLiveInputs(
                                    iconState = state,
                                    workerPhase = phase,
                                    chatStream = stream,
                                    reducedMotion = reduced,
                                    gatewayOnline = online,
                                ),
                            )
                            assertTrue(
                                "blank pill ($state/$phase/$stream/reduced=$reduced/online=$online)",
                                status.statusPillText.isNotBlank(),
                            )
                            assertTrue(
                                "blank statusLine ($state/$phase/$stream/reduced=$reduced/online=$online)",
                                status.statusLine.isNotBlank(),
                            )
                        }
                    }
                }
            }
        }
    }

    @Test
    fun `idle is the floor`() {
        val status = JarvisLiveStatusProjector.project(
            JarvisLiveInputs(iconState = IconState.IDLE),
        )
        assertEquals("Idle", status.statusPillText)
        assertEquals("Ready when you are.", status.statusLine)
        assertEquals(JarvisAvatarActivity.Subtle, status.avatarActivity)
        assertFalse(status.shouldShowApprovalButton)
        assertFalse(status.shouldShowEmergencyButton)
    }
}
