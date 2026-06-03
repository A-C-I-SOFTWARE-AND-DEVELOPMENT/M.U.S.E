package com.aci.hermes.voice

import android.content.Context
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import java.util.Locale
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow

/**
 * On-device text-to-speech via the Android [TextToSpeech] framework — no cloud,
 * no key. Implements [TtsEngine] so the [VoiceLoop] can speak replies and
 * cancel mid-utterance for barge-in.
 *
 * Voice character is left to the system voice for now; per-state prosody
 * (rate/pitch keyed to listening/thinking/speaking) is a follow-up that sets
 * [TextToSpeech.setSpeechRate] / pitch before each [speak].
 */
class AndroidTtsEngine(context: Context) : TtsEngine {

    override val displayName: String = "Android TTS"

    @Volatile
    private var ready = false

    private val engine = TextToSpeech(context.applicationContext) { status ->
        ready = status == TextToSpeech.SUCCESS
    }

    override fun speak(text: String): Flow<TtsEvent> = callbackFlow {
        if (text.isBlank()) {
            close()
            return@callbackFlow
        }
        if (ready) {
            engine.language = Locale.getDefault()
            // A calm, grounded character — a touch slower than default, natural
            // pitch. (Per-state prosody — faster/brighter when speaking, slower
            // when thinking — is a follow-up that varies these per utterance.)
            engine.setSpeechRate(0.97f)
            engine.setPitch(1.0f)
        }
        val utteranceId = "jarvis-" + System.nanoTime()
        engine.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
            override fun onStart(utteranceId: String?) {
                trySend(TtsEvent.STARTED)
            }

            override fun onDone(utteranceId: String?) {
                trySend(TtsEvent.DONE)
                close()
            }

            @Deprecated("Deprecated in Java")
            override fun onError(utteranceId: String?) {
                trySend(TtsEvent.ERROR)
                close()
            }

            override fun onError(utteranceId: String?, errorCode: Int) {
                trySend(TtsEvent.ERROR)
                close()
            }
        })
        val result = engine.speak(text, TextToSpeech.QUEUE_FLUSH, null, utteranceId)
        if (result == TextToSpeech.ERROR) {
            trySend(TtsEvent.ERROR)
            close()
        }
        awaitClose { engine.stop() }
    }

    override fun stop() {
        engine.stop()
    }
}
