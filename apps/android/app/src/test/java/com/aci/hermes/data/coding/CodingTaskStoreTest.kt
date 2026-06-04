package com.aci.hermes.data.coding

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.nio.file.Files

class CodingTaskStoreTest {

    private fun tempDir() = Files.createTempDirectory("coding-store").toFile()

    @Test
    fun `upsert persists and round-trips across instances`() = runTest {
        val dir = tempDir()
        val store = CodingTaskStore(dir, scope = this, ioDispatcher = Dispatchers.Unconfined)
        val saved = store.upsert(
            SavedCodingTask(id = "t1", title = "T", prompt = "do a thing"),
        )
        assertTrue(saved.createdAt > 0)
        assertEquals("t1", store.byId("t1")?.id)

        // A fresh store over the same dir must see the persisted task.
        val reloaded = CodingTaskStore(dir, scope = this, ioDispatcher = Dispatchers.Unconfined, loadEagerly = true)
        assertEquals("do a thing", reloaded.byId("t1")?.prompt)
    }

    @Test
    fun `upsert replaces existing by id without duplicating`() = runTest {
        val store = CodingTaskStore(tempDir(), scope = this, ioDispatcher = Dispatchers.Unconfined)
        store.upsert(SavedCodingTask(id = "a", title = "A", prompt = "a"))
        store.upsert(SavedCodingTask(id = "b", title = "B", prompt = "b"))
        store.upsert(SavedCodingTask(id = "a", title = "A2", prompt = "a2"))
        // Replaced in place: the title updated and there is no duplicate.
        assertEquals("A2", store.byId("a")?.title)
        assertEquals(2, store.tasks.value.size)
        assertEquals(setOf("a", "b"), store.tasks.value.map { it.id }.toSet())
    }

    @Test
    fun `delete removes a single task`() = runTest {
        val store = CodingTaskStore(tempDir(), scope = this, ioDispatcher = Dispatchers.Unconfined)
        store.upsert(SavedCodingTask(id = "x", title = "X", prompt = "x"))
        store.delete("x")
        assertNull(store.byId("x"))
    }
}
