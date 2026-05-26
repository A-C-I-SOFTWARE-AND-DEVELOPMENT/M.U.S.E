package com.aci.hermes.voice

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * Jarvis Prime voice capture surface.
 *
 * Phase 1 is hold-to-talk only. Always-listening is explicitly out of
 * scope. The capture controller exposes a small state machine:
 *
 *   IDLE       → not currently capturing.
 *   ARMED      → mic permission granted, control is pressed, recording
 *                 about to start.
 *   CAPTURING  → audio is being captured.
 *   ENDED      → release was detected; transcript ready (or empty).
 *
 * The actual recorder implementation lands when the gateway-backed
 * voice pipeline is wired. This controller already enforces the
 * lifecycle so the UI can be built and verified against it.
 */
class VoiceCapture {
    enum class State { IDLE, ARMED, CAPTURING, ENDED }

    private val _state = MutableStateFlow(State.IDLE)
    val state: StateFlow<State> = _state.asStateFlow()

    private val _transcript = MutableStateFlow("")
    val transcript: StateFlow<String> = _transcript.asStateFlow()

    /** Called after the Permission Kernel reports RECORD_AUDIO granted. */
    fun arm() {
        if (_state.value == State.IDLE || _state.value == State.ENDED) {
            _state.value = State.ARMED
        }
    }

    /** Called when the user begins pressing the talk control. */
    fun start() {
        if (_state.value == State.ARMED) {
            _state.value = State.CAPTURING
            _transcript.value = ""
        }
    }

    /** Stub: append partial transcript from the engine. */
    fun appendPartial(text: String) {
        if (_state.value != State.CAPTURING) return
        _transcript.value = text
    }

    /** Called when the user releases the talk control. */
    fun release(): String {
        if (_state.value != State.CAPTURING) return ""
        _state.value = State.ENDED
        return _transcript.value
    }

    fun reset() {
        _state.value = State.IDLE
        _transcript.value = ""
    }
}
