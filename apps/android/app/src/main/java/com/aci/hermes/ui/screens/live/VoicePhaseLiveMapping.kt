package com.aci.hermes.ui.screens.live

import com.aci.hermes.voice.VoicePhase

/**
 * Projects the real [VoicePhase] published by
 * [com.aci.hermes.service.VoiceLoopService] onto the avatar's voice flags.
 *
 * This is the seam that replaced the old "demo" behavior where the screen
 * faked `thinking = true` on send: the avatar now animates from the genuine
 * voice-loop phase. Kept as a pure function (no Android types instantiated)
 * so it is unit-testable, and it only touches the voice-related flags —
 * `working` (job state), `approvalNeeded`, `blocked`, and `emergencyStop`
 * are owned elsewhere and left untouched.
 *
 * While a turn is being spoken back the live transcript is surfaced as the
 * voice line so the user can read what JARVIS heard/says.
 */
fun JarvisLiveUiState.withVoicePhase(phase: VoicePhase, transcript: String = ""): JarvisLiveUiState =
    when (phase) {
        VoicePhase.DORMANT, VoicePhase.WAITING_FOR_WAKE ->
            copy(listening = false, thinking = false, speaking = false)
        VoicePhase.LISTENING ->
            copy(
                listening = true,
                thinking = false,
                speaking = false,
                voiceLine = transcript.ifBlank { voiceLine },
            )
        VoicePhase.THINKING ->
            copy(listening = false, thinking = true, speaking = false)
        VoicePhase.SPEAKING ->
            copy(listening = false, thinking = false, speaking = true)
    }
