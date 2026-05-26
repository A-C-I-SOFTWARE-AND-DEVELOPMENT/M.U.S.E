package com.aci.hermes.voice

import kotlinx.coroutines.flow.SharedFlow

/**
 * Surface-agnostic speech recognizer contract. The Android
 * implementation wraps `android.speech.SpeechRecognizer`; tests inject
 * a fake. The Phase-1 surface treats unavailability as
 * "manual transcript mode" rather than as an error.
 */
interface VoiceRecognizer {
    /** Whether STT is actually available on this device. */
    val isAvailable: Boolean

    /** Stream of recognizer events. Subscribers see all events from this point on. */
    val events: SharedFlow<VoiceRecognizerEvent>

    /**
     * Begin listening. Caller must hold RECORD_AUDIO permission; the
     * recognizer does not request it itself.
     */
    fun start()

    /** Stop listening but keep any final result delivered by the engine. */
    fun stop()

    /** Discard the current session without delivering a result. */
    fun cancel()

    /** Release native resources. */
    fun release()
}

sealed class VoiceRecognizerEvent {
    data object Ready : VoiceRecognizerEvent()
    data object Listening : VoiceRecognizerEvent()
    data object EndOfSpeech : VoiceRecognizerEvent()
    data class Partial(val text: String) : VoiceRecognizerEvent()
    data class Final(val text: String) : VoiceRecognizerEvent()
    data class Error(val message: String, val recoverable: Boolean = true) : VoiceRecognizerEvent()
}
