package com.aci.hermes.ui.screens.live

import com.aci.hermes.R

/**
 * Pure projector: collapses the multi-flag [JarvisLiveUiState] to a
 * single [JarvisLiveProjection]. No Android dependencies, no Compose,
 * no Context — every string is returned as a resource id so the same
 * mapper drives both the UI and the JVM unit tests.
 *
 * Priority order (highest wins):
 *   EmergencyStop > Blocked > ApprovalNeeded > Speaking > Working >
 *   Thinking > Listening > Idle.
 *
 * Reduced motion clamps both [JarvisLiveProjection.motionEnabled] and
 * [JarvisLiveProjection.particlesEnabled] to false regardless of state.
 */
object JarvisLiveStateMapper {

    fun project(state: JarvisLiveUiState): JarvisLiveProjection {
        val resolved = resolveState(state)
        val motion = !state.reducedMotion && resolved != JarvisLiveState.EmergencyStop
        val particles = !state.reducedMotion && resolved != JarvisLiveState.EmergencyStop &&
            resolved != JarvisLiveState.Blocked
        return JarvisLiveProjection(
            state = resolved,
            pillText = pillTextFor(resolved),
            voiceLineFallback = defaultVoiceLineFor(resolved),
            contentDescription = contentDescriptionFor(resolved),
            motionEnabled = motion,
            particlesEnabled = particles,
            showApprovalCta = resolved == JarvisLiveState.ApprovalNeeded,
            showFixCta = resolved == JarvisLiveState.Blocked,
            showEmergencyReleaseCta = resolved == JarvisLiveState.EmergencyStop,
        )
    }

    private fun resolveState(state: JarvisLiveUiState): JarvisLiveState = when {
        state.emergencyStop -> JarvisLiveState.EmergencyStop
        state.blocked -> JarvisLiveState.Blocked
        state.approvalNeeded -> JarvisLiveState.ApprovalNeeded
        state.speaking -> JarvisLiveState.Speaking
        state.working -> JarvisLiveState.Working
        state.thinking -> JarvisLiveState.Thinking
        state.listening -> JarvisLiveState.Listening
        else -> JarvisLiveState.Idle
    }

    private fun pillTextFor(state: JarvisLiveState): Int = when (state) {
        JarvisLiveState.Idle -> R.string.jarvis_state_idle
        JarvisLiveState.Listening -> R.string.jarvis_state_listening
        JarvisLiveState.Thinking -> R.string.jarvis_state_thinking
        JarvisLiveState.Working -> R.string.jarvis_state_working
        JarvisLiveState.Speaking -> R.string.jarvis_state_speaking
        JarvisLiveState.ApprovalNeeded -> R.string.jarvis_state_approval
        JarvisLiveState.Blocked -> R.string.jarvis_state_blocked
        JarvisLiveState.EmergencyStop -> R.string.jarvis_state_emergency
    }

    private fun contentDescriptionFor(state: JarvisLiveState): Int = when (state) {
        JarvisLiveState.Idle -> R.string.jarvis_avatar_cd_idle
        JarvisLiveState.Listening -> R.string.jarvis_avatar_cd_listening
        JarvisLiveState.Thinking -> R.string.jarvis_avatar_cd_thinking
        JarvisLiveState.Working -> R.string.jarvis_avatar_cd_working
        JarvisLiveState.Speaking -> R.string.jarvis_avatar_cd_speaking
        JarvisLiveState.ApprovalNeeded -> R.string.jarvis_avatar_cd_approval
        JarvisLiveState.Blocked -> R.string.jarvis_avatar_cd_blocked
        JarvisLiveState.EmergencyStop -> R.string.jarvis_avatar_cd_emergency
    }
}
