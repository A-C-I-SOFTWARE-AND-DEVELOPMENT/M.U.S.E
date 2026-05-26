package com.aci.hermes.voice

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow

/**
 * [VoiceRecognizer] backed by the platform [SpeechRecognizer]. If the
 * device reports no recognition service the constructor leaves
 * [isAvailable] = false and refuses to open the mic — the screen falls
 * back to manual transcript entry.
 */
class AndroidSpeechRecognizer(
    context: Context,
    private val languageTag: String = java.util.Locale.getDefault().toLanguageTag(),
) : VoiceRecognizer {

    private val appContext = context.applicationContext

    private val _events = MutableSharedFlow<VoiceRecognizerEvent>(
        replay = 0,
        extraBufferCapacity = 16,
        onBufferOverflow = BufferOverflow.DROP_OLDEST,
    )
    override val events: SharedFlow<VoiceRecognizerEvent> = _events

    override val isAvailable: Boolean =
        SpeechRecognizer.isRecognitionAvailable(appContext)

    private var recognizer: SpeechRecognizer? = null

    private val listener = object : RecognitionListener {
        override fun onReadyForSpeech(params: Bundle?) {
            _events.tryEmit(VoiceRecognizerEvent.Ready)
        }

        override fun onBeginningOfSpeech() {
            _events.tryEmit(VoiceRecognizerEvent.Listening)
        }

        override fun onRmsChanged(rmsdB: Float) {
            // Intentionally ignored — the waveform animation is decorative
            // in Phase 1. Wire this up if/when we want a live meter.
        }

        override fun onBufferReceived(buffer: ByteArray?) {}

        override fun onEndOfSpeech() {
            _events.tryEmit(VoiceRecognizerEvent.EndOfSpeech)
        }

        override fun onError(error: Int) {
            _events.tryEmit(VoiceRecognizerEvent.Error(describeError(error), recoverable = isRecoverable(error)))
        }

        override fun onResults(results: Bundle?) {
            val text = pickTopResult(results)
            if (text.isNotEmpty()) {
                _events.tryEmit(VoiceRecognizerEvent.Final(text))
            } else {
                _events.tryEmit(VoiceRecognizerEvent.Final(""))
            }
        }

        override fun onPartialResults(partialResults: Bundle?) {
            val text = pickTopResult(partialResults)
            if (text.isNotEmpty()) {
                _events.tryEmit(VoiceRecognizerEvent.Partial(text))
            }
        }

        override fun onEvent(eventType: Int, params: Bundle?) {}
    }

    override fun start() {
        if (!isAvailable) {
            _events.tryEmit(
                VoiceRecognizerEvent.Error(
                    message = "Speech recognition is not available on this device.",
                    recoverable = false,
                ),
            )
            return
        }
        val sr = recognizer ?: SpeechRecognizer.createSpeechRecognizer(appContext).also {
            it.setRecognitionListener(listener)
            recognizer = it
        }
        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(
                RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                RecognizerIntent.LANGUAGE_MODEL_FREE_FORM,
            )
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, languageTag)
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
            putExtra(RecognizerIntent.EXTRA_CALLING_PACKAGE, appContext.packageName)
        }
        sr.startListening(intent)
    }

    override fun stop() {
        recognizer?.stopListening()
    }

    override fun cancel() {
        recognizer?.cancel()
    }

    override fun release() {
        recognizer?.destroy()
        recognizer = null
    }

    private fun pickTopResult(bundle: Bundle?): String {
        val list = bundle?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
            ?: return ""
        return list.firstOrNull()?.trim().orEmpty()
    }

    private fun describeError(code: Int): String = when (code) {
        SpeechRecognizer.ERROR_AUDIO -> "Audio recording error"
        SpeechRecognizer.ERROR_CLIENT -> "Recognizer client error"
        SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS -> "Microphone permission missing"
        SpeechRecognizer.ERROR_NETWORK -> "Network error during recognition"
        SpeechRecognizer.ERROR_NETWORK_TIMEOUT -> "Network timeout during recognition"
        SpeechRecognizer.ERROR_NO_MATCH -> "No speech recognised"
        SpeechRecognizer.ERROR_RECOGNIZER_BUSY -> "Recognizer is busy"
        SpeechRecognizer.ERROR_SERVER -> "Recognition server error"
        SpeechRecognizer.ERROR_SPEECH_TIMEOUT -> "Speech timeout"
        else -> "Recognizer error ($code)"
    }

    private fun isRecoverable(code: Int): Boolean = when (code) {
        SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS -> false
        else -> true
    }
}
