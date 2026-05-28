package com.aci.hermes.voice

import org.junit.Assert.assertEquals
import org.junit.Test

class VoiceLoopTest {

    @Test
    fun `start arms the wake listener`() {
        val loop = VoiceLoop()
        val t = loop.on(VoiceEvent.Start)
        assertEquals(VoicePhase.WAITING_FOR_WAKE, t.phase)
        assertEquals(VoiceLoop.Effect.START_WAKE_LISTENER, t.effect)
    }

    @Test
    fun `full happy path wake to speak`() {
        val loop = VoiceLoop(conversational = true)
        loop.on(VoiceEvent.Start)

        assertEquals(VoiceLoop.Effect.OPEN_MIC_FOR_STT, loop.on(VoiceEvent.WakeWordDetected).effect)
        assertEquals(VoicePhase.LISTENING, loop.phase)

        val toThink = loop.on(VoiceEvent.UtteranceFinal("open facebook"))
        assertEquals(VoicePhase.THINKING, toThink.phase)
        assertEquals(VoiceLoop.Effect.DISPATCH_TO_AGENT, toThink.effect)
        assertEquals("open facebook", loop.lastUtterance)

        val toSpeak = loop.on(VoiceEvent.ReplyReady("Done."))
        assertEquals(VoicePhase.SPEAKING, toSpeak.phase)
        assertEquals(VoiceLoop.Effect.SPEAK_REPLY, toSpeak.effect)
        assertEquals("Done.", loop.lastReply)
    }

    @Test
    fun `conversational loop returns to listening after speaking`() {
        val loop = VoiceLoop(conversational = true)
        loop.on(VoiceEvent.Start)
        loop.on(VoiceEvent.WakeWordDetected)
        loop.on(VoiceEvent.UtteranceFinal("hi"))
        loop.on(VoiceEvent.ReplyReady("Hey."))
        val after = loop.on(VoiceEvent.SpeechDone)
        assertEquals(VoicePhase.LISTENING, after.phase)
        assertEquals(VoiceLoop.Effect.OPEN_MIC_FOR_STT, after.effect)
    }

    @Test
    fun `non-conversational loop returns to wake after speaking`() {
        val loop = VoiceLoop(conversational = false)
        loop.on(VoiceEvent.Start)
        loop.on(VoiceEvent.WakeWordDetected)
        loop.on(VoiceEvent.UtteranceFinal("hi"))
        loop.on(VoiceEvent.ReplyReady("Hey."))
        val after = loop.on(VoiceEvent.SpeechDone)
        assertEquals(VoicePhase.WAITING_FOR_WAKE, after.phase)
    }

    @Test
    fun `barge-in during speech reopens the mic immediately`() {
        val loop = VoiceLoop()
        loop.on(VoiceEvent.Start)
        loop.on(VoiceEvent.WakeWordDetected)
        loop.on(VoiceEvent.UtteranceFinal("tell me a story"))
        loop.on(VoiceEvent.ReplyReady("Once upon a time…"))
        val barge = loop.on(VoiceEvent.BargeIn)
        assertEquals(VoicePhase.LISTENING, barge.phase)
        assertEquals(VoiceLoop.Effect.OPEN_MIC_FOR_STT, barge.effect)
    }

    @Test
    fun `empty utterance falls back to wake listening`() {
        val loop = VoiceLoop()
        loop.on(VoiceEvent.Start)
        loop.on(VoiceEvent.WakeWordDetected)
        val empty = loop.on(VoiceEvent.UtteranceEmpty)
        assertEquals(VoicePhase.WAITING_FOR_WAKE, empty.phase)
    }

    @Test
    fun `stop from any phase goes dormant and kills audio`() {
        val loop = VoiceLoop()
        loop.on(VoiceEvent.Start)
        loop.on(VoiceEvent.WakeWordDetected)
        val stop = loop.on(VoiceEvent.Stop)
        assertEquals(VoicePhase.DORMANT, stop.phase)
        assertEquals(VoiceLoop.Effect.STOP_ALL_AUDIO, stop.effect)
    }

    @Test
    fun `engine error recovers to wake listening`() {
        val loop = VoiceLoop()
        loop.on(VoiceEvent.Start)
        loop.on(VoiceEvent.WakeWordDetected)
        val err = loop.on(VoiceEvent.EngineError)
        assertEquals(VoicePhase.WAITING_FOR_WAKE, err.phase)
        assertEquals(VoiceLoop.Effect.START_WAKE_LISTENER, err.effect)
    }
}
