package com.aci.hermes.memory

import com.aci.hermes.data.memory.MemoryCategory
import com.aci.hermes.data.memory.MemoryConfidence
import com.aci.hermes.data.memory.MemoryDurability
import com.aci.hermes.data.memory.MemoryItem
import com.aci.hermes.data.memory.MemoryProvenance
import com.aci.hermes.ui.screens.memory.MemoryViewModel
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class MemoryFiltersTest {

    private fun item(
        id: String,
        title: String,
        content: String,
        category: MemoryCategory,
        tags: List<String> = emptyList(),
    ) = MemoryItem(
        id = id,
        category = category,
        title = title,
        content = content,
        durability = MemoryDurability.LONG_TERM,
        confidence = MemoryConfidence.HIGH,
        provenance = MemoryProvenance(source = "test", recordedAt = 0L),
        createdAt = 0L,
        tags = tags,
    )

    private val items = listOf(
        item("a", "Preferred build", "Material 3 Compose", MemoryCategory.OWNER_PREFERENCE, listOf("android")),
        item("b", "Orchestration", "five primitives only", MemoryCategory.PROJECT_MEMORY),
        item("c", "Greeting pattern", "abstract opener", MemoryCategory.SOCIAL_SPEECH_PATTERN),
    )

    @Test
    fun `empty filter returns all items`() {
        val out = MemoryViewModel.applyFilters(items, "", null)
        assertEquals(3, out.size)
    }

    @Test
    fun `query filters by title`() {
        val out = MemoryViewModel.applyFilters(items, "greeting", null)
        assertEquals(1, out.size)
        assertEquals("c", out[0].id)
    }

    @Test
    fun `query filters by content`() {
        val out = MemoryViewModel.applyFilters(items, "primitives", null)
        assertEquals(1, out.size)
        assertEquals("b", out[0].id)
    }

    @Test
    fun `query filters by tag`() {
        val out = MemoryViewModel.applyFilters(items, "android", null)
        assertEquals(1, out.size)
        assertEquals("a", out[0].id)
    }

    @Test
    fun `category filter restricts`() {
        val out = MemoryViewModel.applyFilters(items, "", MemoryCategory.PROJECT_MEMORY)
        assertEquals(1, out.size)
        assertEquals("b", out[0].id)
    }

    @Test
    fun `category and query compose`() {
        val out = MemoryViewModel.applyFilters(items, "greeting", MemoryCategory.SOCIAL_SPEECH_PATTERN)
        assertEquals(1, out.size)
        assertTrue(out[0].category == MemoryCategory.SOCIAL_SPEECH_PATTERN)
    }
}
