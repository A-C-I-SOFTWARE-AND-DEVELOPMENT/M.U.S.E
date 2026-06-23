package com.aci.hermes.voice

/**
 * The full-duplex voice loop as a pure state machine. Keeping the
 * transitions free of Android/coroutine code means the "wake → listen →
 * think → speak → barge-in" behavior is exhaustively unit-testable; the
 * [com.aci.hermes.service.VoiceLoopService] is then a thin driver that
 * feeds [VoiceEvent]s in and reacts to the resulting [VoicePhase].
 */
enum class VoicePhase {
    /** Loop off entirely. */
    DORMANT,

    /** Mic open only for the wake word ("Hey muse"). */
    WAITING_FOR_WAKE,

    /** Wake word heard; streaming the user's utterance to STT. */
    LISTENING,

    /** Utterance captured; the agent is producing a reply. */
    THINKING,

    /** Speaking the reply (TTS). Barge-in returns straight to LISTENING. */
    SPEAKING,
}

/** Inputs that drive the loop. */
sealed interface VoiceEvent {
    data object Start : VoiceEvent
    data object Stop : VoiceEvent
    data object WakeWordDetected : VoiceEvent
    /** A final transcript was captured. */
    data class UtteranceFinal(val text: String) : VoiceEvent
    /** STT produced nothing usable (silence/timeout). */
    data object UtteranceEmpty : VoiceEvent
    /** The agent finished producing a reply to speak. */
    data class ReplyReady(val text: String) : VoiceEvent
    /** TTS playback finished. */
    data object SpeechDone : VoiceEvent
    /** User started talking over the reply → barge-in. */
    data object BargeIn : VoiceEvent
    /** Unrecoverable engine error; drop back to a safe phase. */
    data object EngineError : VoiceEvent
}

/**
 * Pure transition function. Returns the next phase and any side-effect
 * the driver must perform. The driver never decides phases itself.
 */
class VoiceLoop(
    /** When true, after speaking we go back to LISTENING for a hands-free
     *  back-and-forth; when false we return to WAITING_FOR_WAKE. */
    private val conversational: Boolean = true,
) {
    var phase: VoicePhase = VoicePhase.DORMANT
        private set

    /** Side-effects the service must enact for a given transition. */
    enum class Effect {
        NONE,
        START_WAKE_LISTENER,
        OPEN_MIC_FOR_STT,
        DISPATCH_TO_AGENT,
        SPEAK_REPLY,
        STOP_ALL_AUDIO,
    }

    data class Transition(val phase: VoicePhase, val effect: Effect)

    /** The last text captured/replied, exposed so the driver can route it. */
    var lastUtterance: String = ""
        private set
    var lastReply: String = ""
        private set

    fun on(event: VoiceEvent): Transition {
        val t = compute(event)
        phase = t.phase
        return t
    }

    private fun compute(event: VoiceEvent): Transition {
        // Stop and hard errors are honored from any phase.
        when (event) {
            is VoiceEvent.Stop -> return Transition(VoicePhase.DORMANT, Effect.STOP_ALL_AUDIO)
            is VoiceEvent.EngineError ->
                return Transition(VoicePhase.WAITING_FOR_WAKE, Effect.START_WAKE_LISTENER)
            else -> Unit
        }

        return when (phase) {
            VoicePhase.DORMANT -> when (event) {
                is VoiceEvent.Start -> Transition(VoicePhase.WAITING_FOR_WAKE, Effect.START_WAKE_LISTENER)
                else -> stay()
            }

            VoicePhase.WAITING_FOR_WAKE -> when (event) {
                is VoiceEvent.WakeWordDetected -> Transition(VoicePhase.LISTENING, Effect.OPEN_MIC_FOR_STT)
                else -> stay()
            }

            VoicePhase.LISTENING -> when (event) {
                is VoiceEvent.UtteranceFinal -> {
                    lastUtterance = event.text
                    Transition(VoicePhase.THINKING, Effect.DISPATCH_TO_AGENT)
                }
                is VoiceEvent.UtteranceEmpty ->
                    Transition(VoicePhase.WAITING_FOR_WAKE, Effect.START_WAKE_LISTENER)
                else -> stay()
            }

            VoicePhase.THINKING -> when (event) {
                is VoiceEvent.ReplyReady -> {
                    lastReply = event.text
                    Transition(VoicePhase.SPEAKING, Effect.SPEAK_REPLY)
                }
                else -> stay()
            }

            VoicePhase.SPEAKING -> when (event) {
                is VoiceEvent.BargeIn -> Transition(VoicePhase.LISTENING, Effect.OPEN_MIC_FOR_STT)
                is VoiceEvent.SpeechDone ->
                    if (conversational) {
                        Transition(VoicePhase.LISTENING, Effect.OPEN_MIC_FOR_STT)
                    } else {
                        Transition(VoicePhase.WAITING_FOR_WAKE, Effect.START_WAKE_LISTENER)
                    }
                else -> stay()
            }
        }
    }

    private fun stay(): Transition = Transition(phase, Effect.NONE)
}
