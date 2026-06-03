package com.aci.hermes.approval.voice

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class VoiceApprovalCoordinatorTest {

    private fun begun(): VoiceApprovalCoordinator {
        val c = VoiceApprovalCoordinator()
        c.on(VoiceApprovalEvent.Begin("appr-1", "deploy web to production"))
        return c
    }

    private fun readyForConfirmation(): VoiceApprovalCoordinator {
        val c = begun()
        c.on(VoiceApprovalEvent.ReadbackSpoken)
        return c
    }

    @Test
    fun `begin speaks a read-back that names the action`() {
        val c = VoiceApprovalCoordinator()
        val d = c.on(VoiceApprovalEvent.Begin("appr-1", "deploy web to production"))
        assertEquals(VoiceApprovalPhase.READING_BACK, d.phase)
        assertEquals(VoiceApprovalCoordinator.Effect.SPEAK_READBACK, d.effect)
        assertTrue(d.readback.contains("deploy web to production"))
        assertTrue(d.readback.contains("with authorization"))
    }

    @Test
    fun `cannot approve before the action is read back`() {
        val c = begun() // still READING_BACK, readback not spoken yet
        val d = c.on(VoiceApprovalEvent.Phrase("yes, with authorization"))
        assertEquals(VoiceApprovalCoordinator.Effect.NONE, d.effect)
        assertEquals(VoiceApprovalPhase.READING_BACK, d.phase)
    }

    @Test
    fun `explicit authorization phrase approves and submits`() {
        val c = readyForConfirmation()
        val d = c.on(VoiceApprovalEvent.Phrase("yes, with authorization"))
        assertEquals(VoiceApprovalPhase.APPROVED, d.phase)
        assertEquals(VoiceApprovalCoordinator.Effect.SUBMIT_APPROVAL, d.effect)
        assertEquals("appr-1", d.approvalId)
    }

    @Test
    fun `bare yes is insufficient and never approves`() {
        val c = readyForConfirmation()
        listOf("yes", "yeah", "ok", "sure", "uh huh").forEach { reply ->
            val d = c.on(VoiceApprovalEvent.Phrase(reply))
            assertEquals(
                "reply '$reply' must not approve",
                VoiceApprovalCoordinator.Effect.NONE,
                d.effect,
            )
            assertEquals(VoiceApprovalPhase.AWAITING_CONFIRMATION, d.phase)
        }
    }

    @Test
    fun `confirm and approve verbs are accepted`() {
        listOf("confirm", "approve", "approved", "I approve").forEach { reply ->
            val d = readyForConfirmation().on(VoiceApprovalEvent.Phrase(reply))
            assertEquals(
                "reply '$reply' should approve",
                VoiceApprovalCoordinator.Effect.SUBMIT_APPROVAL,
                d.effect,
            )
        }
    }

    @Test
    fun `negative reply abandons`() {
        val c = readyForConfirmation()
        val d = c.on(VoiceApprovalEvent.Phrase("no, cancel that"))
        assertEquals(VoiceApprovalPhase.CANCELLED, d.phase)
        assertEquals(VoiceApprovalCoordinator.Effect.ABANDON, d.effect)
    }

    @Test
    fun `timeout abandons without approving`() {
        val c = readyForConfirmation()
        val d = c.on(VoiceApprovalEvent.Timeout)
        assertEquals(VoiceApprovalPhase.CANCELLED, d.phase)
        assertEquals(VoiceApprovalCoordinator.Effect.ABANDON, d.effect)
    }
}
