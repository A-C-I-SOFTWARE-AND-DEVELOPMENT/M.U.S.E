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
 * A **keyless, on-device** wake-word engine built on Android
 * [SpeechRecognizer]. It continuously listens and emits once the spoken
 * text contains the keyword ("jarvis"), re-arming itself after every
 * non-match so it keeps spotting until the collector cancels.
 *
 * This is the no-key fallback that makes hands-free Presence Mode work
 * without any cloud credential or bundled model. It is best-effort:
 * continuous recognition is battery-heavy and accuracy varies by device.
 * A dedicated keyword spotter (e.g. Picovoice Porcupine) is the intended
 * drop-in upgrade — it would need an access key, which must not live in
 * source (see SettingsRepository / `~/.hermes/.env`).
 *
 * The match logic lives in the pure [WakeWordMatcher] so it is unit-tested;
 * this class is only the recognizer glue.
 */
class KeywordSpeechWakeWordEngine(
    context: Context,
    override val keyword: String = "jarvis",
) : WakeWordEngine {

    private val appContext = context.applicationContext
    private val main = Handler(Looper.getMainLooper())

    override fun detections(): Flow<Unit> = callbackFlow {
        var recognizer: SpeechRecognizer? = null
        var closed = false

        fun startListening() {
            if (closed) return
            val sr = recognizer ?: return
            val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
                putExtra(
                    RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                    RecognizerIntent.LANGUAGE_MODEL_FREE_FORM,
                )
                putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
                putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.getDefault().toLanguageTag())
            }
            runCatching { sr.startListening(intent) }
        }

        // Re-arm after a short pause so a fast ERROR_NO_MATCH can't spin.
        fun rearm() {
            if (closed) return
            main.postDelayed({ startListening() }, REARM_DELAY_MS)
        }

        fun fireIfMatch(bundle: Bundle?): Boolean {
            val text = bundle.bestText()
            return if (WakeWordMatcher.matches(keyword, text)) {
                trySend(Unit)
                true
            } else {
                false
            }
        }

        val listener = object : RecognitionListener {
            override fun onPartialResults(partialResults: Bundle?) {
                // Trigger as early as possible on a partial hit.
                if (fireIfMatch(partialResults)) close()
            }

            override fun onResults(results: Bundle?) {
                if (fireIfMatch(results)) close() else rearm()
            }

            override fun onError(error: Int) {
                rearm()
            }

            override fun onReadyForSpeech(params: Bundle?) {}
            override fun onBeginningOfSpeech() {}
            override fun onRmsChanged(rmsdB: Float) {}
            override fun onBufferReceived(buffer: ByteArray?) {}
            override fun onEndOfSpeech() {}
            override fun onEvent(eventType: Int, params: Bundle?) {}
        }

        main.post {
            if (!SpeechRecognizer.isRecognitionAvailable(appContext)) {
                close()
                return@post
            }
            val sr = SpeechRecognizer.createSpeechRecognizer(appContext)
            sr.setRecognitionListener(listener)
            recognizer = sr
            startListening()
        }

        awaitClose {
            closed = true
            main.post {
                runCatching { recognizer?.stopListening() }
                runCatching { recognizer?.destroy() }
            }
        }
    }

    private fun Bundle?.bestText(): String =
        this?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull().orEmpty()

    private companion object {
        const val REARM_DELAY_MS = 400L
    }
}
