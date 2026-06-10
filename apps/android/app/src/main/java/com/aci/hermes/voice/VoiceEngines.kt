package com.aci.hermes.voice

import kotlinx.coroutines.flow.Flow

/**
 * Pluggable voice backends. These mirror the [com.aci.hermes.data.jarvis.JarvisChatGateway]
 * philosophy: the [VoiceLoop] only ever talks to these interfaces, so an
 * on-device engine, a cloud engine, and a test fake are all
 * interchangeable and the loop logic stays unit-testable.
 *
 * Default impls (wired in [com.aci.hermes.di.AppContainer]):
 *  - wake word  → Picovoice Porcupine ("Hey Muse")
 *  - STT        → Vosk on-device (streaming, offline); whisper.cpp /
 *                 cloud are drop-in alternatives
 *  - TTS        → Android TextToSpeech; cloud/Piper are alternatives
 *
 * Headset I/O is handled one layer up by routing the audio through
 * Bluetooth SCO before these engines open the mic/speaker.
 */

/** Always-listening keyword spotter. Emits once per detected wake word. */
interface WakeWordEngine {
    /** Cold-stream of wake-word detections. Cancel to stop listening. */
    fun detections(): Flow<Unit>
    val keyword: String
}

interface SttEngine {
    /**
     * Open the mic and stream transcription results until the utterance
     * ends (endpoint detected) or the flow is cancelled (barge-in/stop).
     */
    fun transcribe(): Flow<SttResult>
    val displayName: String
    /** True if partials arrive token-by-token, false if one final only. */
    val supportsPartials: Boolean
}

/** A streaming transcription result. */
data class SttResult(
    val text: String,
    val isFinal: Boolean,
    val confidence: Float = 1f,
)

interface TtsEngine {
    /** Speak [text]; the returned flow completes when playback ends. */
    fun speak(text: String): Flow<TtsEvent>
    /** Stop any in-flight playback immediately (barge-in). */
    fun stop()
    val displayName: String
}

enum class TtsEvent { STARTED, DONE, ERROR }
