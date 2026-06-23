package com.aci.hermes.presence

/**
 * muse Presence Mode — the trigger arbitration brain.
 *
 * When Presence Mode is enabled the avatar lives over the launcher and the
 * conversation is **hands-free by default**: the user does not press-and-hold
 * to talk. A conversation starts from one of three triggers, chosen by a
 * strict capability fallback chain:
 *
 *   ATTENTION (camera, opt-in)  →  WAKE_WORD (+ voice activity)  →  MIC_BUTTON
 *
 * Camera attention is the most natural but requires opt-in CAMERA consent and
 * hardware; if it is unavailable we fall back to an on-device wake word; if
 * that is unavailable (no engine / RECORD_AUDIO denied) we fall back to the
 * explicit mic button. The mic button is therefore the always-honest floor,
 * never the primary interaction.
 *
 * Like [com.aci.hermes.voice.VoiceLoop] this is a *pure* state machine with no
 * Android or coroutine code, so the arming/fallback/emergency-stop behavior is
 * exhaustively unit-testable. The driver
 * ([com.aci.hermes.presence.PresenceController]) feeds [PresenceEvent]s in and
 * enacts the resulting [Effect].
 *
 * Safety invariants encoded here:
 *  - Listening is **opt-in**: nothing arms until Presence Mode is enabled.
 *  - An **emergency stop** overrides everything and disarms every trigger
 *    until explicitly released.
 *  - Disabling Presence Mode (or losing all capabilities) stops any in-flight
 *    listening immediately.
 */
enum class TriggerSource { NONE, ATTENTION, WAKE_WORD, MIC_BUTTON }

/**
 * What the device can currently offer, in priority order. Each flag folds in
 * both the hardware/engine availability and the relevant runtime consent
 * (camera permission for attention, RECORD_AUDIO for wake/mic).
 */
data class PresenceCapabilities(
    val attentionAvailable: Boolean = false,
    val wakeWordAvailable: Boolean = false,
    val micAvailable: Boolean = false,
)

/** Inputs that drive Presence Mode. */
sealed interface PresenceEvent {
    data class SetEnabled(val enabled: Boolean) : PresenceEvent
    data class CapabilitiesChanged(val capabilities: PresenceCapabilities) : PresenceEvent

    /** The camera attention detector saw the user look at the device. */
    data object AttentionDetected : PresenceEvent
    /** The on-device wake word fired ("Hey muse"). */
    data object WakeWordDetected : PresenceEvent
    /** The user tapped the explicit mic button (fallback path). */
    data object MicButtonTapped : PresenceEvent

    /** The voice loop finished a turn / went dormant — re-arm. */
    data object ConversationEnded : PresenceEvent

    /** Hard stop (long-press). Disarms every trigger. */
    data object EmergencyStop : PresenceEvent
    /** Owner released the emergency stop. */
    data object EmergencyRelease : PresenceEvent
}

class PresenceModeController {

    /** Side effects the driver must enact for a transition. */
    enum class Effect { NONE, START_VOICE_LOOP, STOP_VOICE_LOOP }

    data class Decision(
        val presenceEnabled: Boolean,
        val emergencyStopped: Boolean,
        /** Which trigger is currently armed (the head of the fallback chain). */
        val armedSource: TriggerSource,
        /** Whether a hands-free conversation is currently active. */
        val listening: Boolean,
        val effect: Effect,
    )

    private var presenceEnabled = false
    private var emergencyStopped = false
    private var capabilities = PresenceCapabilities()
    private var listening = false

    /** The currently armed trigger (the first available link in the chain). */
    val armedSource: TriggerSource get() = resolveArmed()
    val isListening: Boolean get() = listening
    val isEmergencyStopped: Boolean get() = emergencyStopped
    val isPresenceEnabled: Boolean get() = presenceEnabled

    fun on(event: PresenceEvent): Decision {
        val effect = when (event) {
            is PresenceEvent.SetEnabled -> {
                presenceEnabled = event.enabled
                if (!presenceEnabled) stopListening() else Effect.NONE
            }

            is PresenceEvent.CapabilitiesChanged -> {
                capabilities = event.capabilities
                // If we were listening via a source that just vanished, and no
                // source remains, stop. Otherwise keep the in-flight turn.
                if (listening && resolveArmed() == TriggerSource.NONE) stopListening()
                else Effect.NONE
            }

            is PresenceEvent.AttentionDetected ->
                startIf(capabilities.attentionAvailable)

            is PresenceEvent.WakeWordDetected ->
                startIf(capabilities.wakeWordAvailable)

            // The mic button is an explicit user action: honor it whenever the
            // mic is available, even if a higher-priority source is also armed.
            is PresenceEvent.MicButtonTapped ->
                startIf(capabilities.micAvailable)

            is PresenceEvent.ConversationEnded -> stopListening()

            is PresenceEvent.EmergencyStop -> {
                emergencyStopped = true
                stopListening()
            }

            is PresenceEvent.EmergencyRelease -> {
                emergencyStopped = false
                Effect.NONE
            }
        }
        return decision(effect)
    }

    /** Start a turn iff presence is on, not emergency-stopped, the source is
     *  available, and we are not already listening. */
    private fun startIf(sourceAvailable: Boolean): Effect {
        if (!presenceEnabled || emergencyStopped || !sourceAvailable || listening) {
            return Effect.NONE
        }
        listening = true
        return Effect.START_VOICE_LOOP
    }

    private fun stopListening(): Effect {
        if (!listening) return Effect.NONE
        listening = false
        return Effect.STOP_VOICE_LOOP
    }

    private fun resolveArmed(): TriggerSource {
        if (!presenceEnabled || emergencyStopped) return TriggerSource.NONE
        return when {
            capabilities.attentionAvailable -> TriggerSource.ATTENTION
            capabilities.wakeWordAvailable -> TriggerSource.WAKE_WORD
            capabilities.micAvailable -> TriggerSource.MIC_BUTTON
            else -> TriggerSource.NONE
        }
    }

    private fun decision(effect: Effect) = Decision(
        presenceEnabled = presenceEnabled,
        emergencyStopped = emergencyStopped,
        armedSource = resolveArmed(),
        listening = listening,
        effect = effect,
    )
}
