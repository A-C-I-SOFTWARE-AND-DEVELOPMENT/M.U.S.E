package com.aci.hermes.memory

import com.aci.hermes.data.memory.MemoryCategory
import com.aci.hermes.data.memory.MemoryConfidence
import com.aci.hermes.data.memory.MemoryDurability
import com.aci.hermes.data.memory.MemoryItem
import com.aci.hermes.data.memory.MemoryProvenance
import com.aci.hermes.data.memory.MemoryRedactor
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class MemoryRedactorTest {

    private fun item(
        category: MemoryCategory = MemoryCategory.TASK_CONTEXT,
        title: String = "Item",
        content: String = "Content",
        durability: MemoryDurability = MemoryDurability.LONG_TERM,
    ) = MemoryItem(
        id = "id",
        category = category,
        title = title,
        content = content,
        durability = durability,
        confidence = MemoryConfidence.MEDIUM,
        provenance = MemoryProvenance(source = "test", recordedAt = 0L),
        createdAt = 0L,
    )

    @Test
    fun `secret-like content is redacted`() {
        val raw = item(content = "api_key=sk-AbCdEfGhIjKlMnOpQrStUvWxYz0123456789")
        val sanitized = MemoryRedactor.sanitize(raw)
        assertTrue(sanitized.redacted)
        assertNotEquals(raw.content, sanitized.content)
        // The literal token must not be present in the rendered content.
        assertFalse(sanitized.content.contains("sk-AbCdEfGhIjKlMnOp"))
    }

    @Test
    fun `non-secret content is left alone`() {
        val raw = item(content = "Plain English memory about owner preferences.")
        val sanitized = MemoryRedactor.sanitize(raw)
        assertFalse(sanitized.redacted)
        assertEquals(raw.content, sanitized.content)
    }

    @Test
    fun `social pattern strips username`() {
        val raw = item(
            category = MemoryCategory.SOCIAL_SPEECH_PATTERN,
            title = "Greeting pattern",
            content = "username: jdoe — opens with status",
        )
        val sanitized = MemoryRedactor.sanitize(raw)
        assertFalse(sanitized.content.contains("jdoe"))
        assertTrue(sanitized.content.contains("[identity]"))
    }

    @Test
    fun `social pattern strips email and phone`() {
        val raw = item(
            category = MemoryCategory.SOCIAL_SPEECH_PATTERN,
            content = "Owner: alice@example.com, +1 415 555 0199 — terse opener.",
        )
        val sanitized = MemoryRedactor.sanitize(raw)
        assertFalse(sanitized.content.contains("alice@example.com"))
        assertFalse(sanitized.content.contains("415 555"))
    }

    @Test
    fun `temporary emotion is demoted to ephemeral`() {
        val raw = item(
            category = MemoryCategory.SESSION_MEMORY,
            title = "Mood: frustrated",
            content = "Owner was angry about merge conflicts.",
            durability = MemoryDurability.LONG_TERM,
        )
        val sanitized = MemoryRedactor.sanitize(raw)
        assertEquals(MemoryDurability.EPHEMERAL, sanitized.durability)
    }

    @Test
    fun `non-emotional long-term memory keeps its durability`() {
        val raw = item(
            content = "Owner prefers single-Activity Compose with hand-rolled DI.",
            durability = MemoryDurability.LONG_TERM,
        )
        val sanitized = MemoryRedactor.sanitize(raw)
        assertEquals(MemoryDurability.LONG_TERM, sanitized.durability)
    }

    @Test
    fun `stripIdentities flags when masking occurs`() {
        val (out, changed) = MemoryRedactor.stripIdentities("ping @jdoe at jdoe@example.com")
        assertTrue(changed)
        assertFalse(out.contains("@jdoe"))
        assertFalse(out.contains("jdoe@example.com"))
    }

    @Test
    fun `looksLikeSecret detects bearer header`() {
        assertTrue(MemoryRedactor.looksLikeSecret("Authorization: Bearer abcdef0123456789ABCDEF0123456789ABCDEF"))
    }

    @Test
    fun `looksLikeSecret ignores normal sentences`() {
        assertFalse(MemoryRedactor.looksLikeSecret("Owner prefers Material 3."))
    }
}
