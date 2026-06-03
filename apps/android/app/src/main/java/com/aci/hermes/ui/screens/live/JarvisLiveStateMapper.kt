package com.aci.hermes.ui.screens.live

import com.aci.hermes.R

/**
 * Pure projector: collapses the multi-flag [JarvisLiveUiState] to a
 * single [JarvisLiveProjection]. No Android dependencies, no Compose,
 * no Context — every string is returned as a resource id so the same
 * mapper drives both the UI and the JVM unit tests.
 *
 * Priority order (highest wins):
 *   EmergencyStop > Disconnected > Blocked > ApprovalNeeded > Speaking >
 *   Listening > Reviewing > Coding > Researching > Working > Thinking > Idle.
 *
 * Safety-critical states (EmergencyStop, Disconnected, Blocked, ApprovalNeeded,
 * Warning) outrank cosmetic activity so a stray work signal can never hide a
 * problem the owner must act on.
 *
 * Reduced motion clamps both [JarvisLiveProjection.motionEnabled] and
 * [JarvisLiveProjection.particlesEnabled] to false regardless of state.
 */
object JarvisLiveStateMapper {

    fun project(state: JarvisLiveUiState): JarvisLiveProjection {
        val resolved = resolveState(state)
        // Emergency, disconnected, and sleep hold still; particles are also
        // suppressed for the "problem" states so they read as calm/serious.
        val motion = !state.reducedMotion &&
            resolved != JarvisLiveState.EmergencyStop &&
            resolved != JarvisLiveState.Disconnected
        val particles = motion &&
            resolved != JarvisLiveState.Blocked &&
            resolved != JarvisLiveState.Warning
        return JarvisLiveProjection(
            state = resolved,
            pillText = pillTextFor(resolved),
            voiceLineFallback = defaultVoiceLineFor(resolved),
            contentDescription = contentDescriptionFor(resolved),
            motionEnabled = motion,
            particlesEnabled = particles,
            showApprovalCta = resolved == JarvisLiveState.ApprovalNeeded,
            showFixCta = resolved == JarvisLiveState.Blocked,
            showWarningCta = resolved == JarvisLiveState.Warning,
            showEmergencyReleaseCta = resolved == JarvisLiveState.EmergencyStop,
        )
    }

    private fun resolveState(state: JarvisLiveUiState): JarvisLiveState = when {
        state.emergencyStop -> JarvisLiveState.EmergencyStop
        state.disconnected -> JarvisLiveState.Disconnected
        state.blocked -> JarvisLiveState.Blocked
        state.approvalNeeded -> JarvisLiveState.ApprovalNeeded
        state.warning -> JarvisLiveState.Warning
        state.speaking -> JarvisLiveState.Speaking
        state.listening -> JarvisLiveState.Listening
        state.reviewing -> JarvisLiveState.Reviewing
        state.coding -> JarvisLiveState.Coding
        state.researching -> JarvisLiveState.Researching
        state.working -> JarvisLiveState.Working
        state.thinking -> JarvisLiveState.Thinking
        else -> JarvisLiveState.Idle
    }

    private fun pillTextFor(state: JarvisLiveState): Int = when (state) {
        JarvisLiveState.Idle -> R.string.jarvis_state_idle
        JarvisLiveState.Listening -> R.string.jarvis_state_listening
        JarvisLiveState.Thinking -> R.string.jarvis_state_thinking
        JarvisLiveState.Researching -> R.string.jarvis_state_researching
        JarvisLiveState.Coding -> R.string.jarvis_state_coding
        JarvisLiveState.Reviewing -> R.string.jarvis_state_reviewing
        JarvisLiveState.Working -> R.string.jarvis_state_working
        JarvisLiveState.Speaking -> R.string.jarvis_state_speaking
        JarvisLiveState.ApprovalNeeded -> R.string.jarvis_state_approval
        JarvisLiveState.Blocked -> R.string.jarvis_state_blocked
        JarvisLiveState.Warning -> R.string.jarvis_state_warning
        JarvisLiveState.Disconnected -> R.string.jarvis_state_disconnected
        JarvisLiveState.EmergencyStop -> R.string.jarvis_state_emergency
    }

    private fun contentDescriptionFor(state: JarvisLiveState): Int = when (state) {
        JarvisLiveState.Idle -> R.string.jarvis_avatar_cd_idle
        JarvisLiveState.Listening -> R.string.jarvis_avatar_cd_listening
        JarvisLiveState.Thinking -> R.string.jarvis_avatar_cd_thinking
        JarvisLiveState.Researching -> R.string.jarvis_avatar_cd_researching
        JarvisLiveState.Coding -> R.string.jarvis_avatar_cd_coding
        JarvisLiveState.Reviewing -> R.string.jarvis_avatar_cd_reviewing
        JarvisLiveState.Working -> R.string.jarvis_avatar_cd_working
        JarvisLiveState.Speaking -> R.string.jarvis_avatar_cd_speaking
        JarvisLiveState.ApprovalNeeded -> R.string.jarvis_avatar_cd_approval
        JarvisLiveState.Blocked -> R.string.jarvis_avatar_cd_blocked
        JarvisLiveState.Warning -> R.string.jarvis_avatar_cd_warning
        JarvisLiveState.Disconnected -> R.string.jarvis_avatar_cd_disconnected
        JarvisLiveState.EmergencyStop -> R.string.jarvis_avatar_cd_emergency
    }
}
