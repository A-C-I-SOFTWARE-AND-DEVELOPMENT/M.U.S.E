package com.aci.hermes.memory

import com.aci.hermes.data.memory.MemoryAction
import com.aci.hermes.data.memory.MemoryCategory
import com.aci.hermes.data.memory.MemoryConfidence
import com.aci.hermes.data.memory.MemoryDurability
import com.aci.hermes.data.memory.MemoryItem
import com.aci.hermes.data.memory.MemoryProvenance
import com.aci.hermes.data.memory.MemoryRepository
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class MemoryRepositoryTest {

    private fun seed() = listOf(
        item("a", "Title A", "content a", MemoryCategory.OWNER_PREFERENCE),
        item("b", "Title B", "content b", MemoryCategory.PROJECT_MEMORY),
    )

    private fun item(
        id: String,
        title: String,
        content: String,
        category: MemoryCategory,
    ) = MemoryItem(
        id = id,
        category = category,
        title = title,
        content = content,
        durability = MemoryDurability.LONG_TERM,
        confidence = MemoryConfidence.HIGH,
        provenance = MemoryProvenance(source = "test", recordedAt = 0L),
        createdAt = 0L,
    )

    @Test
    fun `visible returns sanitized non-hidden items`() {
        val repo = MemoryRepository(seed())
        val visible = repo.visible()
        assertEquals(2, visible.size)
    }

    @Test
    fun `correct updates content and emits action`() = runBlocking {
        val repo = MemoryRepository(seed())
        coroutineScope {
            val deferred = async(start = CoroutineStart.UNDISPATCHED) {
                repo.actions.first()
            }
            repo.correct("a", "new content", "fix typo")
            val action = deferred.await()
            assertTrue(action is MemoryAction.Correct)
            action as MemoryAction.Correct
            assertEquals("a", action.itemId)
            assertEquals("new content", action.newContent)
            assertEquals("fix typo", action.reason)
        }
        val updated = repo.byId("a")
        assertNotNull(updated)
        assertEquals("new content", updated!!.content)
        assertEquals(MemoryConfidence.CONFIRMED, updated.confidence)
    }

    @Test
    fun `delete removes the item and emits action`() = runBlocking {
        val repo = MemoryRepository(seed())
        coroutineScope {
            val deferred = async(start = CoroutineStart.UNDISPATCHED) {
                repo.actions.first()
            }
            repo.delete("b", "no longer relevant")
            val action = deferred.await()
            assertTrue(action is MemoryAction.Delete)
        }
        assertNull(repo.byId("b"))
        assertEquals(1, repo.visible().size)
    }
}
