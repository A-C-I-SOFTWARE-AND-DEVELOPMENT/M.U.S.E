package com.aci.hermes.data.social

import com.aci.hermes.data.model.PatternProvenance
import com.aci.hermes.data.model.PrivacyRisk
import com.aci.hermes.data.model.ProvenanceKind
import com.aci.hermes.data.model.SocialPattern
import com.aci.hermes.data.model.SocialPatternKind
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class PrivacyRedactorTest {

    @Test
    fun `username-like strings are redacted`() {
        val text = "Look at what @alice and u/charlie posted on twitter.com/dan_dev today"
        val redacted = PrivacyRedactor.redactIdentity(text)
        assertFalse("handle should be stripped", redacted.contains("@alice"))
        assertFalse("reddit handle should be stripped", redacted.contains("u/charlie"))
        assertFalse("platform handle should be stripped", redacted.contains("twitter.com/dan_dev"))
        assertTrue(redacted.contains(PrivacyRedactor.REDACTION_TOKEN))
    }

    @Test
    fun `email and phone are redacted`() {
        val text = "Contact bob@example.com or +1 555 010 2000 for details"
        val redacted = PrivacyRedactor.redactIdentity(text)
        assertFalse(redacted.contains("bob@example.com"))
        assertFalse(redacted.contains("555 010 2000"))
    }

    @Test
    fun `real-name-shaped tokens are redacted but place names are kept`() {
        val text = "Jane Doe wrote a guide; she lives in New York"
        val redacted = PrivacyRedactor.redactIdentity(text)
        assertFalse("real name should be stripped", redacted.contains("Jane Doe"))
        assertTrue("place name should be kept", redacted.contains("New York"))
    }

    @Test
    fun `flag list covers each identity kind`() {
        val flags = PrivacyRedactor.identityFlagsIn(
            "@alice u/bob bob@example.com Jane Doe twitter.com/eve +1 555 010 9999",
        )
        assertTrue(flags.contains("handle"))
        assertTrue(flags.contains("platform_handle"))
        assertTrue(flags.contains("platform_url"))
        assertTrue(flags.contains("email"))
        assertTrue(flags.contains("phone"))
        assertTrue(flags.contains("real_name"))
    }

    @Test
    fun `private identity is flagged at HIGH risk`() {
        val pattern = SocialPattern(
            title = "How @alice replies",
            kind = SocialPatternKind.MOBILE_REPLY,
            summary = "Reach out to bob@example.com",
            safeUsage = "n/a",
            unsafeUsage = "n/a",
        )
        val sanitized = PrivacyRedactor.sanitize(pattern)
        assertEquals(PrivacyRisk.HIGH, sanitized.privacyRisk)
        assertTrue(sanitized.identityFlags.contains("handle"))
        assertTrue(sanitized.identityFlags.contains("email"))
        assertFalse(sanitized.title.contains("@alice"))
        assertFalse(sanitized.summary.contains("bob@example.com"))
    }

    @Test
    fun `only real name yields MEDIUM risk`() {
        val pattern = SocialPattern(
            title = "Jane Doe replies",
            kind = SocialPatternKind.COMMUNICATION,
            summary = "n/a",
            safeUsage = "n/a",
            unsafeUsage = "n/a",
        )
        val sanitized = PrivacyRedactor.sanitize(pattern)
        assertEquals(PrivacyRisk.MEDIUM, sanitized.privacyRisk)
    }

    @Test
    fun `clean abstract pattern is LOW risk and renders without identity`() {
        val pattern = SocialPattern(
            title = "Engineers reply short on mobile",
            kind = SocialPatternKind.MOBILE_REPLY,
            summary = "Phones invite brevity; responders drop punctuation.",
            safeUsage = "Mirror brevity when replying from your phone.",
            unsafeUsage = "Never impersonate any specific person.",
        )
        val sanitized = PrivacyRedactor.sanitize(pattern)
        assertEquals(PrivacyRisk.LOW, sanitized.privacyRisk)
        assertTrue(sanitized.identityFlags.isEmpty())
        // Render path: sanitized text never carries identity.
        assertFalse(PrivacyRedactor.containsIdentity(sanitized.title))
        assertFalse(PrivacyRedactor.containsIdentity(sanitized.summary))
        assertFalse(PrivacyRedactor.containsIdentity(sanitized.safeUsage))
        assertFalse(PrivacyRedactor.containsIdentity(sanitized.unsafeUsage))
    }

    @Test
    fun `provenance with auth-walled or platform-profile URL is dropped`() {
        val provenance = listOf(
            PatternProvenance(
                sourceTitle = "Public style guide",
                sourceUrl = "https://example.com/style",
                sourceKind = ProvenanceKind.STYLE_GUIDE,
            ),
            PatternProvenance(
                sourceTitle = "Private DM",
                sourceUrl = "https://example.com/dm/inbox?token=abc",
                sourceKind = ProvenanceKind.PUBLIC_DOC,
            ),
            PatternProvenance(
                sourceTitle = "GitHub profile",
                sourceUrl = "https://github.com/some-user",
                sourceKind = ProvenanceKind.PUBLIC_DOC,
            ),
        )
        val cleaned = PrivacyRedactor.sanitizeProvenance(provenance)
        assertEquals(1, cleaned.size)
        assertEquals("Public style guide", cleaned.first().sourceTitle)
    }

    @Test
    fun `provenance free-form text is redacted but kept`() {
        val provenance = listOf(
            PatternProvenance(
                sourceTitle = "Notes from Jane Doe",
                sourceUrl = "https://example.com/notes",
                sourceKind = ProvenanceKind.PUBLIC_BLOG,
                note = "Saw @alice reply quickly",
            ),
        )
        val cleaned = PrivacyRedactor.sanitizeProvenance(provenance)
        assertEquals(1, cleaned.size)
        assertFalse(cleaned.first().sourceTitle.contains("Jane Doe"))
        assertNotNull(cleaned.first().note)
        assertFalse(cleaned.first().note!!.contains("@alice"))
    }

    @Test
    fun `blank text is safe and yields no flags`() {
        assertEquals("", PrivacyRedactor.redactIdentity(""))
        assertTrue(PrivacyRedactor.identityFlagsIn("").isEmpty())
        assertEquals(PrivacyRisk.LOW, PrivacyRedactor.classifyRisk(emptyList()))
    }

    @Test
    fun `sanitize is idempotent`() {
        val pattern = SocialPattern(
            title = "How @alice replies",
            kind = SocialPatternKind.MOBILE_REPLY,
            summary = "Talked to bob@example.com",
            safeUsage = "x",
            unsafeUsage = "y",
        )
        val once = PrivacyRedactor.sanitize(pattern)
        val twice = PrivacyRedactor.sanitize(once)
        assertEquals(once.title, twice.title)
        assertEquals(once.summary, twice.summary)
        // After one pass the identity is gone, so the second pass classifies LOW.
        assertEquals(PrivacyRisk.LOW, twice.privacyRisk)
        assertNull(twice.identityFlags.firstOrNull { it == "handle" || it == "email" })
    }
}
