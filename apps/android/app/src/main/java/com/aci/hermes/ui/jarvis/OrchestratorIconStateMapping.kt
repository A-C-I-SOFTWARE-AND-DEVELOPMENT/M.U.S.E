package com.aci.hermes.ui.jarvis

import com.aci.hermes.data.model.HermesTask
import com.aci.hermes.data.model.TaskStatus

/**
 * Bridge between the orchestrator domain and the icon's
 * domain-neutral [IconStateInputs]. Lives next to [IconStateMapper] so
 * the icon module stays self-contained — orchestrator code never
 * imports the icon package directly.
 */
object OrchestratorIconStateMapping {

    /** Tasks completed within this window flash the green "complete" state. */
    const val COMPLETE_FLASH_WINDOW_MS: Long = 5_000L

    /**
     * Build [IconStateInputs] from the snapshots the orchestrator
     * already exposes. All inputs are optional so callers can pass
     * only what they have; defaults yield `IDLE`.
     *
     * @param serviceRunning whether HermesService is alive
     * @param tasks the current task list
     * @param now the current wall-clock time, injectable for tests
     * @param voiceListening voice capture session is open
     * @param voiceSpeaking TTS playback is active
     * @param thinking model is reasoning
     * @param pendingApproval a non-destructive action is queued
     * @param seriousActionPending a reversible-but-serious action is queued
     * @param criticalActionPending a destructive action is queued
     * @param blocked precondition failure
     */
    fun inputsFor(
        serviceRunning: Boolean,
        tasks: List<HermesTask>,
        now: Long = System.currentTimeMillis(),
        voiceListening: Boolean = false,
        voiceSpeaking: Boolean = false,
        thinking: Boolean = false,
        pendingApproval: Boolean = false,
        seriousActionPending: Boolean = false,
        criticalActionPending: Boolean = false,
        blocked: Boolean = false,
    ): IconStateInputs {
        val handedOff = tasks.any {
            it.status == TaskStatus.HANDED_TO_CODEX || it.status == TaskStatus.HANDED_TO_CLAUDE
        }
        val inReview = tasks.any { it.status == TaskStatus.IN_REVIEW }
        val needsRevision = tasks.any { it.status == TaskStatus.NEEDS_REVISION }
        val recentComplete = tasks.any { task ->
            task.status == TaskStatus.COMPLETE &&
                now - task.updatedAt <= COMPLETE_FLASH_WINDOW_MS
        }

        return IconStateInputs(
            gatewayOnline = serviceRunning,
            listening = voiceListening,
            thinking = thinking,
            speaking = voiceSpeaking,
            working = handedOff,
            pendingApproval = pendingApproval || inReview,
            seriousActionPending = seriousActionPending,
            criticalActionPending = criticalActionPending,
            blocked = blocked,
            warning = needsRevision,
            recentCompletion = recentComplete,
        )
    }
}
