package com.aci.hermes.voice

import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow

/**
 * Test double for [VoiceRecognizer]. Records calls and lets tests
 * inject events synchronously.
 */
class FakeVoiceRecognizer(
    override val isAvailable: Boolean = true,
) : VoiceRecognizer {

    private val _events = MutableSharedFlow<VoiceRecognizerEvent>(
        replay = 0,
        extraBufferCapacity = 32,
        onBufferOverflow = BufferOverflow.DROP_OLDEST,
    )
    override val events: SharedFlow<VoiceRecognizerEvent> = _events

    var startCount: Int = 0
        private set
    var stopCount: Int = 0
        private set
    var cancelCount: Int = 0
        private set
    var releaseCount: Int = 0
        private set

    override fun start() {
        startCount++
    }

    override fun stop() {
        stopCount++
    }

    override fun cancel() {
        cancelCount++
    }

    override fun release() {
        releaseCount++
    }

    fun emit(event: VoiceRecognizerEvent) {
        check(_events.tryEmit(event)) { "Failed to emit $event — buffer overflow" }
    }
}
