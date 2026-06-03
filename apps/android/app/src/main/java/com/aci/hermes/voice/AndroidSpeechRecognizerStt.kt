package com.aci.hermes.voice

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import java.util.Locale
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow

/**
 * On-device speech-to-text via Android [SpeechRecognizer] — streaming partials,
 * no cloud key. Implements [SttEngine] so the [VoiceLoop] gets token-ish updates
 * (partials) and a final transcript, and can cancel for barge-in/stop.
 *
 * [SpeechRecognizer] must be created and driven on the main thread, so every
 * call hops to the main looper; the cold [Flow] tears the recognizer down on
 * cancellation.
 */
class AndroidSpeechRecognizerStt(context: Context) : SttEngine {

    override val displayName: String = "Android SpeechRecognizer"
    override val supportsPartials: Boolean = true

    private val appContext = context.applicationContext
    private val main = Handler(Looper.getMainLooper())

    override fun transcribe(): Flow<SttResult> = callbackFlow {
        var recognizer: SpeechRecognizer? = null

        val listener = object : RecognitionListener {
            override fun onResults(results: Bundle?) {
                trySend(SttResult(results?.bestText().orEmpty(), isFinal = true))
                close()
            }

            override fun onPartialResults(partialResults: Bundle?) {
                val text = partialResults?.bestText().orEmpty()
                if (text.isNotBlank()) {
                    trySend(SttResult(text, isFinal = false))
                }
            }

            override fun onError(error: Int) {
                close()
            }

            override fun onReadyForSpeech(params: Bundle?) {}
            override fun onBeginningOfSpeech() {}
            override fun onRmsChanged(rmsdB: Float) {}
            override fun onBufferReceived(buffer: ByteArray?) {}
            override fun onEndOfSpeech() {}
            override fun onEvent(eventType: Int, params: Bundle?) {}
        }

        main.post {
            val sr = SpeechRecognizer.createSpeechRecognizer(appContext)
            sr.setRecognitionListener(listener)
            recognizer = sr
            val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
                putExtra(
                    RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                    RecognizerIntent.LANGUAGE_MODEL_FREE_FORM,
                )
                putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
                putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.getDefault().toLanguageTag())
            }
            sr.startListening(intent)
        }

        awaitClose {
            main.post {
                recognizer?.stopListening()
                recognizer?.destroy()
            }
        }
    }

    private fun Bundle.bestText(): String =
        getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull().orEmpty()
}
