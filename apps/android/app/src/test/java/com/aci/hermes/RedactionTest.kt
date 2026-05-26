package com.aci.hermes

import com.aci.hermes.data.audit.AuditRepository
import com.aci.hermes.data.memory.MemoryRepository
import com.aci.hermes.data.model.AuditEvent
import com.aci.hermes.data.model.AuditSeverity
import com.aci.hermes.data.model.SocialChannel
import com.aci.hermes.data.redaction.Redactor
import com.aci.hermes.data.social.SocialIntelligenceRepository
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class RedactionTest {

    @Test
    fun email_is_redacted() {
        val out = Redactor.redact("contact me at jdoe@example.com please")
        assertTrue(out.text.contains("[redacted]"))
        assertFalse(out.text.contains("jdoe@example.com"))
        assertTrue("email" in out.redactedFields)
    }

    @Test
    fun phone_number_is_redacted() {
        val out = Redactor.redact("call +1 (415) 555-1212 tonight")
        assertTrue(out.text.contains("[redacted]"))
        assertTrue("phone" in out.redactedFields)
    }

    @Test
    fun api_key_is_redacted() {
        val out = Redactor.redact("api_key=sk-abc123def456ghi789jkl0mno")
        assertTrue(out.text.contains("[redacted]"))
    }

    @Test
    fun github_token_is_redacted() {
        val out = Redactor.redact("token ghp_abcdefghijklmnopqrstuv stays out")
        assertTrue(out.text.contains("[redacted]"))
    }

    @Test
    fun social_handle_is_redacted() {
        val out = Redactor.redact("see @alice for context")
        assertTrue(out.text.contains("[redacted]"))
        assertTrue("handle" in out.redactedFields)
    }

    @Test
    fun memory_repo_strips_email_before_persisting() {
        val mem = MemoryRepository()
        mem.remember("our PM is jdoe@example.com")
        val stored = mem.items.value.first()
        assertFalse(stored.content.contains("jdoe@example.com"))
        assertTrue("email" in stored.redactedFields)
    }

    @Test
    fun social_repo_tokenises_subject_name() {
        val social = SocialIntelligenceRepository()
        val sig = social.record("Alice Jones", SocialChannel.CHAT, "meeting prep")
        assertNotEquals("Alice Jones", sig.subjectToken)
        assertTrue(sig.subjectToken.startsWith("subject:"))
    }

    @Test
    fun audit_repo_redacts_payload_summary() {
        val audit = AuditRepository()
        audit.append(
            AuditEvent(
                actor = "user",
                action = "test",
                target = "x",
                payloadSummary = "leaked sk-abcdefghijklmnopqrstuv",
                severity = AuditSeverity.INFO,
            )
        )
        val stored = audit.events.value.first()
        assertFalse(stored.payloadSummary.contains("sk-abcdefghijklmnopqrstuv"))
    }

    @Test
    fun audit_repo_assigns_proof_hash() {
        val audit = AuditRepository()
        val out = audit.append(AuditEvent(actor = "u", action = "a", target = "t"))
        assertTrue(out.proofHash.startsWith("0x"))
        assertEquals(10, out.proofHash.length)
    }
}
