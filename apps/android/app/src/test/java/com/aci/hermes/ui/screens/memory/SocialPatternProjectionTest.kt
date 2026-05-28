package com.aci.hermes.ui.screens.memory

import com.aci.hermes.data.memory.MemoryConfidence
import com.aci.hermes.data.memory.MemoryDurability
import com.aci.hermes.data.memory.MemoryItem
import com.aci.hermes.data.memory.MemoryProvenance
import com.aci.hermes.data.memory.MemoryRedactor
import com.aci.hermes.data.memory.MemoryCategory
import com.aci.hermes.data.model.PrivacyRisk
import com.aci.hermes.data.model.SocialPatternKind
import com.aci.hermes.data.social.PrivacyRedactor
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class SocialPatternProjectionTest {

    private fun socialItem(
        id: String = "p1",
        title: String,
        content: String,
        tags: List<String> = emptyList(),
        source: String = "companion-mode",
    ) = MemoryItem(
        id = id,
        category = MemoryCategory.SOCIAL_SPEECH_PATTERN,
        title = title,
        content = content,
        durability = MemoryDurability.LONG_TERM,
        confidence = MemoryConfidence.MEDIUM,
        provenance = MemoryProvenance(source = source, recordedAt = 0L),
        createdAt = 0L,
        tags = tags,
    )

    @Test
    fun `clean abstract pattern renders without identity at low risk`() {
        val item = socialItem(
            title = "Engineers reply short on mobile",
            content = "On phones, responders drop punctuation and keep it terse.",
        )
        val pattern = PrivacyRedactor.sanitize(SocialPatternProjection.from(item))
        assertEquals(PrivacyRisk.LOW, pattern.privacyRisk)
        assertTrue(pattern.identityFlags.isEmpty())
        assertFalse(PrivacyRedactor.containsIdentity(pattern.summary))
        assertFalse(PrivacyRedactor.containsIdentity(pattern.title))
    }

    @Test
    fun `username-like strings are redacted and private identity flagged`() {
        // Mirrors the seed item: identity in the raw store is stripped
        // by MemoryRedactor before it ever reaches the projection.
        val raw = socialItem(
            title = "Morning greeting pattern",
            content = "username: jdoe — Owner opens the day with a short status sentence.",
        )
        val sanitizedItem = MemoryRedactor.sanitize(raw)
        val pattern = PrivacyRedactor.sanitize(SocialPatternProjection.from(sanitizedItem))

        assertFalse("raw username must not survive", pattern.summary.contains("jdoe"))
        assertTrue("identity must be flagged", pattern.identityFlags.contains("identity"))
        assertEquals(PrivacyRisk.HIGH, pattern.privacyRisk)
    }

    @Test
    fun `handle markers are flagged`() {
        val raw = socialItem(
            title = "Reply cadence",
            content = "Mirrors @someone fast acknowledgement style.",
        )
        val sanitizedItem = MemoryRedactor.sanitize(raw)
        val flags = SocialPatternProjection.identityFlags(sanitizedItem)
        assertTrue(flags.contains("handle"))
    }

    @Test
    fun `kind is inferred from tags first`() {
        val item = socialItem(
            title = "Disagreement is calm",
            content = "Short replies on the go.",
            tags = listOf("MOBILE_REPLY"),
        )
        assertEquals(SocialPatternKind.MOBILE_REPLY, SocialPatternProjection.from(item).kind)
    }

    @Test
    fun `kind is inferred from text when no tag`() {
        val item = socialItem(
            title = "Calm disagreement",
            content = "State pushback on the idea without conflict with the person.",
        )
        assertEquals(SocialPatternKind.DISAGREEMENT, SocialPatternProjection.from(item).kind)
    }

    @Test
    fun `unsafe usage is the universal boundary`() {
        val item = socialItem(title = "Any pattern", content = "Anything.")
        val pattern = SocialPatternProjection.from(item)
        assertEquals(SocialPatternProjection.UNSAFE_USAGE, pattern.unsafeUsage)
        assertTrue(pattern.unsafeUsage.contains("Never impersonate"))
    }

    @Test
    fun `provenance is mapped from the item source`() {
        val item = socialItem(
            title = "Pattern",
            content = "Abstract.",
            source = "Google developer style guide",
        )
        val pattern = SocialPatternProjection.from(item)
        assertEquals(1, pattern.provenance.size)
        assertEquals("Google developer style guide", pattern.provenance.first().sourceTitle)
    }

    @Test
    fun `safe usage is non-empty for every kind`() {
        SocialPatternKind.entries.forEach { kind ->
            val item = socialItem(title = kind.displayName, content = "x", tags = listOf(kind.name))
            val pattern = SocialPatternProjection.from(item)
            assertEquals(kind, pattern.kind)
            assertTrue("safe usage should be present for $kind", pattern.safeUsage.isNotBlank())
        }
    }
}
