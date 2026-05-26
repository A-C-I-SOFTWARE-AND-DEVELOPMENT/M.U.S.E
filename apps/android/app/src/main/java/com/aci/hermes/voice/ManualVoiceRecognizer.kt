package com.aci.hermes.voice

import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow

/**
 * No-op recognizer used as a fallback when the device reports no
 * SpeechRecognizer service. The screen surfaces a manual transcript
 * text field instead of opening the microphone, so the rest of the
 * pipeline (classifier, send-to-chat, create-task) still works.
 *
 * Also useful as the trivial fake for unit tests that don't need to
 * simulate audio events.
 */
class ManualVoiceRecognizer : VoiceRecognizer {

    private val _events = MutableSharedFlow<VoiceRecognizerEvent>(
        replay = 0,
        extraBufferCapacity = 8,
        onBufferOverflow = BufferOverflow.DROP_OLDEST,
    )
    override val events: SharedFlow<VoiceRecognizerEvent> = _events

    override val isAvailable: Boolean = false

    override fun start() {
        _events.tryEmit(
            VoiceRecognizerEvent.Error(
                message = "On-device speech recognition is not available. Type the request instead.",
                recoverable = false,
            ),
        )
    }

    override fun stop() = Unit
    override fun cancel() = Unit
    override fun release() = Unit
}
