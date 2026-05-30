package com.aci.hermes.data.memory

import com.aci.hermes.data.cockpit.CockpitMemoryItem
import com.aci.hermes.data.cockpit.CockpitMemoryProvenance
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class CockpitMemoryMappingTest {

    private fun item(
        category: String = "OWNER_PREFERENCE",
        durability: String = "PERMANENT",
        confidence: String = "HIGH",
        createdAt: String? = "2026-05-30T12:00:00+00:00",
    ) = CockpitMemoryItem(
        id = "deploy_window",
        category = category,
        title = "deploy_window",
        content = "after 6pm ET",
        durability = durability,
        confidence = confidence,
        provenance = CockpitMemoryProvenance(
            source = "agent",
            sessionId = null,
            recordedAt = "2026-05-30T12:00:00+00:00",
            note = "seen in chat",
        ),
        createdAt = createdAt,
        updatedAt = "2026-05-30T12:00:00+00:00",
        lastAccessedAt = "2026-05-30T13:00:00Z",
        tags = listOf("ops"),
        redacted = false,
        hidden = false,
    )

    @Test
    fun `maps enums and fields field-for-field`() {
        val m = item().toDomain()
        assertEquals("deploy_window", m.id)
        assertEquals(MemoryCategory.OWNER_PREFERENCE, m.category)
        assertEquals(MemoryDurability.PERMANENT, m.durability)
        assertEquals(MemoryConfidence.HIGH, m.confidence)
        assertEquals("after 6pm ET", m.content)
        assertEquals("agent", m.provenance.source)
        assertEquals("seen in chat", m.provenance.note)
        assertEquals(listOf("ops"), m.tags)
        assertFalse(m.hidden)
    }

    @Test
    fun `parses both offset and Z iso forms to epoch millis`() {
        val m = item().toDomain()
        assertTrue(m.createdAt > 0L)
        // created_at is 12:00:00+00:00, last_accessed_at is 13:00:00Z → 1h apart.
        assertEquals(3_600_000L, m.lastAccessedAt!! - m.createdAt)
    }

    @Test
    fun `unknown enum values fall back honestly, never crash`() {
        val m = item(category = "TOTALLY_NEW", durability = "???", confidence = "weird").toDomain()
        assertEquals(MemoryCategory.UNCATEGORIZED, m.category)
        assertEquals(MemoryDurability.SESSION, m.durability)
        assertEquals(MemoryConfidence.MEDIUM, m.confidence)
    }

    @Test
    fun `null created_at falls back to provenance recorded_at`() {
        val m = item(createdAt = null).toDomain()
        assertTrue(m.createdAt > 0L)
        assertEquals(m.provenance.recordedAt, m.createdAt)
    }

    @Test
    fun `unparseable timestamp yields null last-accessed, not a crash`() {
        val raw = item().copy(lastAccessedAt = "not-a-date")
        assertNull(raw.toDomain().lastAccessedAt)
    }

    @Test
    fun `uncategorized round-trips`() {
        assertTrue(item(category = "UNCATEGORIZED").toDomain().category == MemoryCategory.UNCATEGORIZED)
    }
}
