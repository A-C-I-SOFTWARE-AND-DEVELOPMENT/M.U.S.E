package com.aci.hermes.ui.screens.memory

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Pins owner-facing copy on the Memory surface and asserts that no
 * private identifier ever ends up in the copy. The Compose screen
 * reads from [MemoryEmptyStateCopy] so a future copy edit cannot
 * drift the surface from the contract these tests assert.
 */
class MemoryEmptyStateCopyTest {

    @Test
    fun `genuinely empty list shows genuinely empty copy`() {
        val out = MemoryEmptyStateCopy.chooseFor(filterActive = false, totalItems = 0)
        assertEquals(MemoryEmptyStateCopy.GENUINELY_EMPTY, out)
    }

    @Test
    fun `filter hiding all items shows filter copy`() {
        val out = MemoryEmptyStateCopy.chooseFor(filterActive = true, totalItems = 12)
        assertEquals(MemoryEmptyStateCopy.FILTER_HIDES_ALL, out)
    }

    @Test
    fun `empty repository wins over filter state`() {
        // totalItems = 0 with filter active still means "genuinely empty"
        // — the owner doesn't have any memory yet.
        val out = MemoryEmptyStateCopy.chooseFor(filterActive = true, totalItems = 0)
        assertEquals(MemoryEmptyStateCopy.GENUINELY_EMPTY, out)
    }

    @Test
    fun `genuinely empty copy mentions owner approval and correction`() {
        val out = MemoryEmptyStateCopy.GENUINELY_EMPTY
        assertTrue("must mention approve", out.contains("approve", ignoreCase = true))
        assertTrue("must mention correct/forget", out.contains("correct") || out.contains("forget"))
    }

    @Test
    fun `owner-note announces redaction`() {
        val out = MemoryEmptyStateCopy.OWNER_NOTE_REDACTED
        assertTrue(out.contains("Secrets", ignoreCase = true))
        assertTrue(out.contains("redacted", ignoreCase = true))
    }

    @Test
    fun `delete warning names owner and DELETE keyword`() {
        val out = MemoryEmptyStateCopy.DELETE_OWNER_WARNING
        assertTrue("must name owner action", out.contains("Owner action", ignoreCase = false))
        assertTrue("must reference the DELETE keyword", out.contains("DELETE"))
        assertTrue("must call out permanence", out.contains("permanent", ignoreCase = true))
    }

    @Test
    fun `correct note names owner action and explains drop of original`() {
        val out = MemoryEmptyStateCopy.CORRECT_OWNER_NOTE
        assertTrue(out.contains("Owner action"))
        assertTrue(out.contains("dropped", ignoreCase = true) || out.contains("replace", ignoreCase = true))
    }

    @Test
    fun `no copy string contains a raw private identifier`() {
        // Memory must never echo a private identifier into UI copy.
        // The test repo seed exposes "jdoe" + a sk- token; pin that
        // neither shows up in any copy constant on this surface.
        val all = listOf(
            MemoryEmptyStateCopy.GENUINELY_EMPTY,
            MemoryEmptyStateCopy.FILTER_HIDES_ALL,
            MemoryEmptyStateCopy.OWNER_NOTE_REDACTED,
            MemoryEmptyStateCopy.DELETE_OWNER_WARNING,
            MemoryEmptyStateCopy.CORRECT_OWNER_NOTE,
        )
        for (copy in all) {
            assertFalse("copy must not contain 'jdoe': $copy", copy.contains("jdoe"))
            assertFalse("copy must not contain 'sk-' token: $copy", copy.contains("sk-"))
            assertFalse("copy must not contain 'Bearer ': $copy", copy.contains("Bearer "))
            assertFalse("copy must not contain '@gmail.com': $copy", copy.contains("@gmail.com"))
        }
    }
}
