package com.aci.hermes.ui.screens.live

import com.aci.hermes.data.cockpit.JobStatus
import com.aci.hermes.data.model.WorkerPhase
import com.aci.hermes.ui.screens.live.JarvisLivePresenceMapper.BackendPresence
import com.aci.hermes.ui.screens.live.JarvisLivePresenceMapper.JobSignal
import com.aci.hermes.voice.VoicePhase
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Locks the backend-signal → avatar-flag derivation. These assertions are the
 * guard rail the owner asked for: if a future WorkerPhase / JobStatus change
 * shifts the mapping, the avatar won't silently go wrong — this fails first.
 */
class JarvisLivePresenceMapperTest {

    private fun resolved(p: BackendPresence): JarvisLiveState {
        val flags = JarvisLivePresenceMapper.flagsFor(p)
        return JarvisLiveStateMapper.project(
            JarvisLiveUiState(
                listening = flags.listening,
                thinking = flags.thinking,
                researching = flags.researching,
                coding = flags.coding,
                reviewing = flags.reviewing,
                working = flags.working,
                speaking = flags.speaking,
                approvalNeeded = flags.approvalNeeded,
                blocked = flags.blocked,
                warning = flags.warning,
                disconnected = flags.disconnected,
                emergencyStop = flags.emergencyStop,
            ),
        ).state
    }

    @Test
    fun `nothing happening is idle`() {
        assertEquals(JarvisLiveState.Idle, resolved(BackendPresence()))
    }

    @Test
    fun `emergency engaged beats every other signal`() {
        val p = BackendPresence(
            emergencyEngaged = true,
            connected = false,
            running = 3,
            pendingApprovals = 2,
            jobs = listOf(JobSignal(JobStatus.BLOCKED)),
            activePhase = WorkerPhase.EDITOR,
            voicePhase = VoicePhase.SPEAKING,
        )
        assertEquals(JarvisLiveState.EmergencyStop, resolved(p))
    }

    @Test
    fun `lost connection beats work and approvals but not emergency`() {
        val p = BackendPresence(
            connected = false,
            running = 1,
            pendingApprovals = 1,
            activePhase = WorkerPhase.EDITOR,
        )
        assertEquals(JarvisLiveState.Disconnected, resolved(p))
    }

    @Test
    fun `pending approval surfaces over active coding`() {
        val p = BackendPresence(
            running = 1,
            pendingApprovals = 1,
            activePhase = WorkerPhase.EDITOR,
        )
        assertEquals(JarvisLiveState.ApprovalNeeded, resolved(p))
    }

    @Test
    fun `queue waiting-approval count also surfaces approval`() {
        assertEquals(
            JarvisLiveState.ApprovalNeeded,
            resolved(BackendPresence(waitingApproval = 1)),
        )
    }

    @Test
    fun `a blocked job shows blocked`() {
        assertEquals(
            JarvisLiveState.Blocked,
            resolved(BackendPresence(jobs = listOf(JobSignal(JobStatus.BLOCKED)))),
        )
    }

    @Test
    fun `failed job or failed gate shows warning`() {
        assertEquals(
            JarvisLiveState.Warning,
            resolved(BackendPresence(jobs = listOf(JobSignal(JobStatus.FAILED)))),
        )
        assertEquals(
            JarvisLiveState.Warning,
            resolved(
                BackendPresence(
                    running = 1,
                    jobs = listOf(JobSignal(JobStatus.RUNNING, failedGates = 2)),
                ),
            ),
        )
    }

    @Test
    fun `worker phase maps to the fine work states`() {
        fun withPhase(phase: WorkerPhase) =
            resolved(BackendPresence(running = 1, activePhase = phase))
        assertEquals(JarvisLiveState.Researching, withPhase(WorkerPhase.PLANNER))
        assertEquals(JarvisLiveState.Researching, withPhase(WorkerPhase.NAVIGATOR))
        assertEquals(JarvisLiveState.Coding, withPhase(WorkerPhase.EDITOR))
        assertEquals(JarvisLiveState.Coding, withPhase(WorkerPhase.EXECUTOR))
        assertEquals(JarvisLiveState.Reviewing, withPhase(WorkerPhase.REVIEWER))
        assertEquals(JarvisLiveState.Reviewing, withPhase(WorkerPhase.JARVIS_FINAL_SYNTHESIS))
    }

    @Test
    fun `active job with no phase degrades to generic working`() {
        assertEquals(
            JarvisLiveState.Working,
            resolved(BackendPresence(running = 1, activePhase = null)),
        )
        assertEquals(
            JarvisLiveState.Working,
            resolved(
                BackendPresence(jobs = listOf(JobSignal(JobStatus.RUNNING)), activePhase = null),
            ),
        )
    }

    @Test
    fun `voice listening and speaking outrank the work phase`() {
        assertEquals(
            JarvisLiveState.Speaking,
            resolved(
                BackendPresence(
                    running = 1,
                    activePhase = WorkerPhase.EDITOR,
                    voicePhase = VoicePhase.SPEAKING,
                ),
            ),
        )
        assertEquals(
            JarvisLiveState.Listening,
            resolved(
                BackendPresence(
                    running = 1,
                    activePhase = WorkerPhase.REVIEWER,
                    voicePhase = VoicePhase.LISTENING,
                ),
            ),
        )
    }

    @Test
    fun `flags are raw and let the projector own priority`() {
        // The mapper sets BOTH approval and coding flags; resolution is the
        // projector's job (kept decoupled and independently testable).
        val flags = JarvisLivePresenceMapper.flagsFor(
            BackendPresence(running = 1, pendingApprovals = 1, activePhase = WorkerPhase.EDITOR),
        )
        assertTrue(flags.approvalNeeded)
        assertTrue(flags.coding)
        assertFalse(flags.working)
    }
}
