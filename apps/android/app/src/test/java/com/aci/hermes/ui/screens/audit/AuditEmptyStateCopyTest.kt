package com.aci.hermes.ui.screens.audit

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Pins owner-facing copy on the Audit surface and asserts the
 * screen-layer secret guard is honest. The Compose screen reads from
 * [AuditEmptyStateCopy] so a future copy edit cannot drift the
 * surface from the contract these tests assert.
 */
class AuditEmptyStateCopyTest {

    @Test
    fun `genuinely empty list shows genuinely empty copy`() {
        val out = AuditEmptyStateCopy.chooseFor(filterActive = false, totalRecords = 0)
        assertEquals(AuditEmptyStateCopy.GENUINELY_EMPTY, out)
    }

    @Test
    fun `filter hiding all records shows filter copy`() {
        val out = AuditEmptyStateCopy.chooseFor(filterActive = true, totalRecords = 5)
        assertEquals(AuditEmptyStateCopy.FILTER_HIDES_ALL, out)
    }

    @Test
    fun `empty repository wins over filter state`() {
        val out = AuditEmptyStateCopy.chooseFor(filterActive = true, totalRecords = 0)
        assertEquals(AuditEmptyStateCopy.GENUINELY_EMPTY, out)
    }

    @Test
    fun `genuinely empty copy promises owner-only history`() {
        val out = AuditEmptyStateCopy.GENUINELY_EMPTY
        assertTrue(out.contains("owner-only", ignoreCase = true))
        assertTrue(out.contains("redacted", ignoreCase = true))
    }

    @Test
    fun `owner-note explicitly redacts secrets and tokens`() {
        val out = AuditEmptyStateCopy.OWNER_NOTE_REDACTED
        assertTrue(out.contains("Secrets", ignoreCase = true))
        assertTrue(out.contains("API keys", ignoreCase = true))
        assertTrue(out.contains("tokens", ignoreCase = true))
    }

    @Test
    fun `sanitizeForDisplay strips obvious sk- tokens`() {
        val out = AuditEmptyStateCopy.sanitizeForDisplay(
            "Failed step: OPENAI_API_KEY=sk-proj-abc1234567890 returned 401",
        )
        assertFalse("must drop the raw sk- token", out.contains("sk-proj-abc"))
        assertTrue(out.contains("[REDACTED]"))
    }

    @Test
    fun `sanitizeForDisplay strips Bearer tokens`() {
        val out = AuditEmptyStateCopy.sanitizeForDisplay(
            "curl -H 'Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.payload' …",
        )
        assertFalse(out.contains("eyJhbGciOiJIUzI1NiJ9"))
        assertTrue(out.contains("[REDACTED]"))
    }

    @Test
    fun `sanitizeForDisplay strips JWT-shaped triplets`() {
        val jwt =
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9." +
                "eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4ifQ." +
                "abcdefghijklmnopqrstuvwxyz1234567890abcdef"
        val out = AuditEmptyStateCopy.sanitizeForDisplay("token=$jwt end")
        assertFalse("must drop the JWT", out.contains("eyJzdWIi"))
        assertTrue(out.contains("[REDACTED]"))
    }

    @Test
    fun `sanitizeForDisplay leaves benign strings alone`() {
        val ok = "Approved by owner at 2026-05-26T08:00Z; impact summary: 1 file changed."
        assertEquals(ok, AuditEmptyStateCopy.sanitizeForDisplay(ok))
    }

    @Test
    fun `no copy constant contains a raw secret`() {
        val all = listOf(
            AuditEmptyStateCopy.GENUINELY_EMPTY,
            AuditEmptyStateCopy.FILTER_HIDES_ALL,
            AuditEmptyStateCopy.OWNER_NOTE_REDACTED,
        )
        for (copy in all) {
            assertFalse("must not embed sk-: $copy", copy.contains("sk-"))
            assertFalse("must not embed Bearer prefix: $copy", copy.contains("Bearer "))
        }
    }
}
