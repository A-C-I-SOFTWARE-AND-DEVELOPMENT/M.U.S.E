package com.aci.hermes.ui.screens.live

import com.aci.hermes.data.cockpit.JobStatus
import com.aci.hermes.data.model.WorkerPhase
import com.aci.hermes.voice.VoicePhase

/**
 * Pure, Android-free projector from **real backend signals** to the activity
 * flags on [JarvisLiveUiState]. This is what makes the avatar an operational
 * surface instead of decoration: every flag it raises is derived from a live
 * signal (runtime queue, jobs, approvals, the active task's worker phase, the
 * voice loop phase, the persisted emergency stop, and backend connectivity).
 *
 * It only *sets the raw flags*; [JarvisLiveStateMapper] still owns the
 * priority resolution, so the two stay decoupled and independently testable.
 *
 * IMPORTANT: the fine-grained phases (Researching / Coding / Reviewing) are a
 * **derived approximation of UI state, not backend truth** — they are inferred
 * from the active task's [WorkerPhase] lane, which is the only on-device phase
 * signal. Unknown / unmapped phases degrade gracefully to generic Working.
 */
object JarvisLivePresenceMapper {

    /** One job's contribution to presence. */
    data class JobSignal(
        val status: JobStatus?,
        /** Count of failed validation gates for this job (0 = none). */
        val failedGates: Int = 0,
    )

    /** The aggregated, already-fetched backend snapshot. */
    data class BackendPresence(
        /** Cockpit health probe succeeded. */
        val connected: Boolean = true,
        /** The persisted global emergency-stop flag. */
        val emergencyEngaged: Boolean = false,
        /** RuntimeStatus.queue counts. */
        val running: Int = 0,
        val queued: Int = 0,
        val waitingApproval: Int = 0,
        /** Pending owner-approval cards. */
        val pendingApprovals: Int = 0,
        val jobs: List<JobSignal> = emptyList(),
        /** Active (non-terminal) task's lane, or null when nothing is active. */
        val activePhase: WorkerPhase? = null,
        val voicePhase: VoicePhase = VoicePhase.DORMANT,
    )

    /** The flag subset this mapper owns; applied onto [JarvisLiveUiState]. */
    data class PresenceFlags(
        val listening: Boolean = false,
        val thinking: Boolean = false,
        val researching: Boolean = false,
        val coding: Boolean = false,
        val reviewing: Boolean = false,
        val working: Boolean = false,
        val speaking: Boolean = false,
        val approvalNeeded: Boolean = false,
        val blocked: Boolean = false,
        val warning: Boolean = false,
        val disconnected: Boolean = false,
        val emergencyStop: Boolean = false,
    )

    fun flagsFor(p: BackendPresence): PresenceFlags {
        val approvalNeeded = p.pendingApprovals > 0 ||
            p.waitingApproval > 0 ||
            p.jobs.any { it.status == JobStatus.WAITING_FOR_APPROVAL }
        val blocked = p.jobs.any { it.status == JobStatus.BLOCKED }
        val warning = p.jobs.any { it.status == JobStatus.FAILED || it.failedGates > 0 }

        val activeWork = p.running > 0 ||
            p.jobs.any { it.status == JobStatus.RUNNING || it.status == JobStatus.PUBLISHING }

        val phase = p.activePhase
        val researching = phase == WorkerPhase.PLANNER || phase == WorkerPhase.NAVIGATOR
        val coding = phase == WorkerPhase.EDITOR || phase == WorkerPhase.EXECUTOR
        // Final synthesis reads as a review/finalize pass.
        val reviewing = phase == WorkerPhase.REVIEWER ||
            phase == WorkerPhase.JARVIS_FINAL_SYNTHESIS
        // Generic fallback: there is active work but no (mapped) phase signal.
        val working = activeWork && !researching && !coding && !reviewing

        return PresenceFlags(
            listening = p.voicePhase == VoicePhase.LISTENING,
            thinking = p.voicePhase == VoicePhase.THINKING,
            speaking = p.voicePhase == VoicePhase.SPEAKING,
            researching = researching,
            coding = coding,
            reviewing = reviewing,
            working = working,
            approvalNeeded = approvalNeeded,
            blocked = blocked,
            warning = warning,
            disconnected = !p.connected,
            emergencyStop = p.emergencyEngaged,
        )
    }
}
