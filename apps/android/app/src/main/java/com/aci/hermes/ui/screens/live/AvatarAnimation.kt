package com.aci.hermes.ui.screens.live

import com.aci.hermes.data.automation.AvatarClip
import com.aci.hermes.data.life.AvatarBehavior

/**
 * Pure mapping from "what Jarvis is doing" to the renderer-neutral
 * animation inputs every avatar renderer understands. The Rive, sprite,
 * and Filament renderers all consume an [AvatarInputs] so the same
 * blend logic drives every body — and so it's unit-testable without any
 * Android/graphics dependency.
 *
 * Precedence: an active device-driving [AvatarClip] (run/push/page-turn)
 * always wins because it's a literal performance the user asked for.
 * Otherwise the agent work state wins over ambient life, except SLEEP,
 * which only shows when the agent is idle.
 *
 * The input names here are the canonical contract documented in
 * `docs/avatar/rive-state-contract.md`; the `.riv` artboard must expose
 * a state-machine input for each [AvatarPose].
 */
enum class AvatarPose {
    IDLE, LISTEN, THINK, WORK, SPEAK, APPROVE, BLOCKED, EMERGENCY,
    RUN, PUSH, PAGE_TURN, SCROLL, POINT,
    WANDER, SLEEP, WAKE, RECOMMEND,
}

data class AvatarInputs(
    val pose: AvatarPose,
    /** 0f..1f intensity — pulses faster/brighter at higher energy. */
    val energy: Float,
    /** Renderer should suppress looping motion (reduced motion / sleep). */
    val motionEnabled: Boolean,
)

object AvatarAnimation {

    fun inputsFor(
        state: JarvisLiveState,
        behavior: AvatarBehavior,
        activeClip: AvatarClip?,
        motionEnabled: Boolean,
    ): AvatarInputs {
        activeClip?.let { clip ->
            return AvatarInputs(
                pose = clip.toPose(),
                energy = 0.9f,
                motionEnabled = motionEnabled,
            )
        }

        // The finer work phases (Researching/Coding/Reviewing) and the two new
        // attention states (Warning/Disconnected) reuse EXISTING poses so the
        // Rive `pose` ordinal contract (docs/avatar/rive-state-contract.md) is
        // untouched. Their differentiation lives in the non-animation channels
        // (pill text, color, voice line, content description). Energy still
        // varies per state below.
        val pose = when (state) {
            JarvisLiveState.EmergencyStop -> AvatarPose.EMERGENCY
            JarvisLiveState.Blocked -> AvatarPose.BLOCKED
            JarvisLiveState.Warning -> AvatarPose.BLOCKED
            JarvisLiveState.ApprovalNeeded -> AvatarPose.APPROVE
            JarvisLiveState.Speaking -> AvatarPose.SPEAK
            JarvisLiveState.Coding, JarvisLiveState.Reviewing,
            JarvisLiveState.Working -> AvatarPose.WORK
            JarvisLiveState.Researching, JarvisLiveState.Thinking -> AvatarPose.THINK
            JarvisLiveState.Listening -> AvatarPose.LISTEN
            JarvisLiveState.Disconnected -> AvatarPose.IDLE
            JarvisLiveState.Idle -> idlePoseFor(behavior)
        }
        return AvatarInputs(
            pose = pose,
            energy = energyFor(state, behavior),
            // Sleep and emergency hold still even when motion is otherwise on;
            // disconnected freezes too — nothing it shows is live.
            motionEnabled = motionEnabled &&
                pose != AvatarPose.SLEEP &&
                pose != AvatarPose.EMERGENCY &&
                state != JarvisLiveState.Disconnected,
        )
    }

    private fun idlePoseFor(behavior: AvatarBehavior): AvatarPose = when (behavior) {
        AvatarBehavior.IDLE -> AvatarPose.IDLE
        AvatarBehavior.WANDER -> AvatarPose.WANDER
        AvatarBehavior.SLEEP -> AvatarPose.SLEEP
        AvatarBehavior.WAKE -> AvatarPose.WAKE
        AvatarBehavior.AMBIENT_TASK -> AvatarPose.WANDER
        AvatarBehavior.RECOMMEND -> AvatarPose.RECOMMEND
    }

    private fun energyFor(state: JarvisLiveState, behavior: AvatarBehavior): Float = when (state) {
        JarvisLiveState.Speaking -> 1.0f
        JarvisLiveState.Coding -> 0.9f
        JarvisLiveState.Working -> 0.85f
        JarvisLiveState.Listening -> 0.8f
        JarvisLiveState.Reviewing -> 0.7f
        JarvisLiveState.Researching -> 0.65f
        JarvisLiveState.Thinking -> 0.6f
        JarvisLiveState.ApprovalNeeded, JarvisLiveState.Blocked,
        JarvisLiveState.Warning -> 0.5f
        JarvisLiveState.EmergencyStop, JarvisLiveState.Disconnected -> 0.3f
        JarvisLiveState.Idle -> when (behavior) {
            AvatarBehavior.SLEEP -> 0.1f
            AvatarBehavior.WANDER, AvatarBehavior.AMBIENT_TASK -> 0.45f
            AvatarBehavior.RECOMMEND -> 0.7f
            else -> 0.3f
        }
    }

    private fun AvatarClip.toPose(): AvatarPose = when (this) {
        AvatarClip.RUN -> AvatarPose.RUN
        AvatarClip.PUSH -> AvatarPose.PUSH
        AvatarClip.PAGE_TURN -> AvatarPose.PAGE_TURN
        AvatarClip.SCROLL -> AvatarPose.SCROLL
        AvatarClip.POINT -> AvatarPose.POINT
        AvatarClip.SETTLE -> AvatarPose.IDLE
    }
}
