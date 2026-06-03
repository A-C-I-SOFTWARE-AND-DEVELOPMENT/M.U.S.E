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
 * On-device, **keyless** wake-word spotter built on the Android
 * [SpeechRecognizer]. It implements the existing [WakeWordEngine] contract so
 * [com.aci.hermes.service.VoiceLoopService] can arm a hands-free conversation
 * without any proprietary SDK or access key.
 *
 * It is a *software* wake word — it loops short recognition windows and emits
 * a detection when the configured [keyword] is heard. It is intentionally a
 * drop-in behind the [WakeWordEngine] interface: a dedicated low-power DSP
 * engine (Picovoice Porcupine / Vosk keyword spotting) can replace this later
 * by swapping the factory in [com.aci.hermes.di.AppContainer] — nothing else
 * changes.
 *
 * Privacy: audio never leaves the device — the system recognizer transcribes
 * locally and we only ever inspect the text for the keyword. The engine only
 * runs while Presence Mode has explicitly started the voice loop (RECORD_AUDIO
 * consent + a foreground microphone service notification), so this is never
 * silent always-on listening.
 */
class SpeechRecognizerWakeWordEngine(
    context: Context,
    override val keyword: String = DEFAULT_KEYWORD,
) : WakeWordEngine {

    private val appContext = context.applicationContext
    private val main = Handler(Looper.getMainLooper())

    // Accept the keyword plus its most common single-recognizer mishears so a
    // slightly-off transcription ("hey jervis") still arms. Matching is
    // substring + normalized, so this stays forgiving without being trigger-happy.
    private val needles: List<String> = buildList {
        add(keyword.normalizedKeyword())
        if (keyword.equals(DEFAULT_KEYWORD, ignoreCase = true)) {
            addAll(listOf("hey jarvis", "hey jervis", "a jarvis", "jarvis"))
        }
    }.distinct()

    override fun detections(): Flow<Unit> = callbackFlow {
        var recognizer: SpeechRecognizer? = null
        var closed = false

        fun startWindow() {
            if (closed) return
            recognizer?.let {
                val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
                    putExtra(
                        RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                        RecognizerIntent.LANGUAGE_MODEL_FREE_FORM,
                    )
                    putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
                    putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.getDefault().toLanguageTag())
                }
                runCatching { it.startListening(intent) }
            }
        }

        val listener = object : RecognitionListener {
            override fun onResults(results: Bundle?) {
                if (matched(results)) {
                    trySend(Unit)
                }
                // Re-arm for the next window regardless — wake spotting is
                // continuous until the flow is cancelled.
                main.post { startWindow() }
            }

            override fun onPartialResults(partialResults: Bundle?) {
                if (matched(partialResults)) {
                    trySend(Unit)
                }
            }

            override fun onError(error: Int) {
                // Transient errors (no-match / timeout) are normal between
                // windows; just re-arm. A backoff avoids a hot loop on hard
                // failures.
                main.postDelayed({ startWindow() }, REARM_DELAY_MS)
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
            startWindow()
        }

        awaitClose {
            closed = true
            main.post {
                recognizer?.stopListening()
                recognizer?.destroy()
            }
        }
    }

    private fun matched(bundle: Bundle?): Boolean {
        val hyp = bundle
            ?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
            ?.joinToString(" ")
            ?.normalizedKeyword()
            ?: return false
        if (hyp.isBlank()) return false
        return needles.any { hyp.contains(it) }
    }

    private fun String.normalizedKeyword(): String =
        lowercase(Locale.getDefault()).trim().replace(Regex("[^a-z0-9 ]"), "")

    companion object {
        const val DEFAULT_KEYWORD = "hey jarvis"
        private const val REARM_DELAY_MS = 400L
    }
}
