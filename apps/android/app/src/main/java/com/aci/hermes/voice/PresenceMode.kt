package com.aci.hermes.voice

/**
 * Pure, Android-free logic for hands-free **Presence Mode** — the policy
 * that decides *how* MUSE starts listening and *what* the presence
 * surface should show. The Android glue ([PresenceModeController]) only
 * enacts these decisions, so the behavior stays unit-testable.
 */

/** What the user sees the presence surface doing. */
enum class PresenceState {
    /** Presence Mode is off. */
    OFF,

    /** On and waiting for a trigger (wake word armed, or idle awaiting a tap). */
    ARMED,

    /** Capturing the user's utterance. */
    LISTENING,

    /** The agent is producing a reply. */
    THINKING,

    /** Speaking the reply. */
    SPEAKING,
}

/**
 * How conversation is triggered, chosen by the available capabilities.
 * The owner's degradation chain is: camera attention (opt-in, gated) →
 * wake word + voice activity → mic-button / tap-to-talk fallback.
 */
enum class PresenceTrigger {
    /** Camera-based attention (opt-in, gated behind CAMERA — not yet shipped). */
    CAMERA_ATTENTION,

    /** Always-listening wake word ("muse"). */
    WAKE_WORD,

    /** Manual: the mic button or a tap on the avatar (always available). */
    MIC_FALLBACK,
}

object PresenceModePolicy {

    /**
     * Pick the best available trigger. Camera is opt-in and gated; if it is
     * unavailable we fall back to the wake word, and if that is unavailable
     * we fall back to the always-present mic / tap-to-talk.
     */
    fun trigger(
        wakeWordAvailable: Boolean,
        cameraAttentionAvailable: Boolean = false,
    ): PresenceTrigger = when {
        cameraAttentionAvailable -> PresenceTrigger.CAMERA_ATTENTION
        wakeWordAvailable -> PresenceTrigger.WAKE_WORD
        else -> PresenceTrigger.MIC_FALLBACK
    }

    /** Project the voice-loop phase onto the user-facing presence state. */
    fun stateFor(enabled: Boolean, phase: VoicePhase): PresenceState {
        if (!enabled) return PresenceState.OFF
        return when (phase) {
            VoicePhase.DORMANT, VoicePhase.WAITING_FOR_WAKE -> PresenceState.ARMED
            VoicePhase.LISTENING -> PresenceState.LISTENING
            VoicePhase.THINKING -> PresenceState.THINKING
            VoicePhase.SPEAKING -> PresenceState.SPEAKING
        }
    }
}

/**
 * Pure wake-word matcher used by the keyless on-device engine. Kept
 * separate so the (finicky) recognizer glue carries no logic worth
 * testing, and the matching rules are pinned by unit tests.
 *
 * Matches on a whole-word, case/punctuation-insensitive basis so
 * "Hey, Muse!" trips "muse" but "museum" does not.
 */
object WakeWordMatcher {
    fun matches(keyword: String, transcript: String): Boolean {
        val key = keyword.trim().lowercase()
        if (key.isEmpty()) return false
        val words = transcript.lowercase().split(Regex("[^a-z0-9]+")).filter { it.isNotEmpty() }
        return words.contains(key)
    }
}
