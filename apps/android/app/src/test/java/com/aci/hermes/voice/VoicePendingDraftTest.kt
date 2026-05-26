package com.aci.hermes.voice

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class VoicePendingDraftTest {

    @Test fun `pending starts null and consume returns null`() {
        val draft = VoicePendingDraft()
        assertNull(draft.peek())
        assertNull(draft.pending.value)
        assertNull(draft.consume())
    }

    @Test fun `publish updates state flow`() {
        val draft = VoicePendingDraft()
        val payload = VoicePendingDraft.Draft(
            transcript = "draft a status update",
            requiresApproval = false,
        )
        draft.publish(payload)
        assertEquals(payload, draft.pending.value)
        assertEquals(payload, draft.peek())
    }

    @Test fun `consume returns and clears the draft`() {
        val draft = VoicePendingDraft()
        val payload = VoicePendingDraft.Draft(
            transcript = "delete the staging cluster",
            requiresApproval = true,
            reason = "serious action verb detected",
        )
        draft.publish(payload)
        val consumed = draft.consume()
        assertEquals(payload, consumed)
        assertNull(draft.pending.value)
        assertNull(draft.peek())
        assertTrue(consumed!!.requiresApproval)
        assertFalse(consumed.transcript.isBlank())
    }
}
