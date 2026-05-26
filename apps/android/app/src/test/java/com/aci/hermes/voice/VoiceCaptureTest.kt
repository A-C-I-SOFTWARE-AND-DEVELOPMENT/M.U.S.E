package com.aci.hermes.voice

import org.junit.Assert.assertEquals
import org.junit.Test

class VoiceCaptureTest {

    @Test fun lifecycle_advances_through_arm_start_release() {
        val v = VoiceCapture()
        v.arm(); assertEquals(VoiceCapture.State.ARMED, v.state.value)
        v.start(); assertEquals(VoiceCapture.State.CAPTURING, v.state.value)
        v.appendPartial("hello world")
        val out = v.release()
        assertEquals("hello world", out)
        assertEquals(VoiceCapture.State.ENDED, v.state.value)
    }

    @Test fun start_without_arm_is_a_no_op() {
        val v = VoiceCapture()
        v.start()
        assertEquals(VoiceCapture.State.IDLE, v.state.value)
    }

    @Test fun append_outside_capture_is_a_no_op() {
        val v = VoiceCapture()
        v.appendPartial("ignored")
        assertEquals("", v.transcript.value)
    }

    @Test fun release_without_capture_returns_empty() {
        val v = VoiceCapture()
        val out = v.release()
        assertEquals("", out)
    }

    @Test fun reset_returns_to_idle_and_clears_transcript() {
        val v = VoiceCapture()
        v.arm(); v.start(); v.appendPartial("x"); v.release()
        v.reset()
        assertEquals(VoiceCapture.State.IDLE, v.state.value)
        assertEquals("", v.transcript.value)
    }
}
