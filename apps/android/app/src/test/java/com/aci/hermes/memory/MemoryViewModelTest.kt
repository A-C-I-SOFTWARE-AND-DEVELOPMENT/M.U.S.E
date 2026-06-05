package com.aci.hermes.memory

import com.aci.hermes.data.memory.MemoryCategory
import com.aci.hermes.data.memory.MemoryConfidence
import com.aci.hermes.data.memory.MemoryDurability
import com.aci.hermes.data.memory.MemoryItem
import com.aci.hermes.data.memory.MemoryProvenance
import com.aci.hermes.data.memory.MemoryRepository
import com.aci.hermes.data.memory.MockMemorySeed
import com.aci.hermes.testutil.MainDispatcherRule
import com.aci.hermes.ui.screens.memory.MemoryViewModel
import com.aci.hermes.util.LogBuffer
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class MemoryViewModelTest {

    @get:Rule
    val mainDispatcherRule = MainDispatcherRule(UnconfinedTestDispatcher())

    private fun newVm(items: List<MemoryItem> = MockMemorySeed.items): MemoryViewModel {
        val repo = MemoryRepository(items)
        return MemoryViewModel(repo, LogBuffer())
    }

    @Test
    fun `list renders sanitized items`() {
        val vm = newVm()
        val visible = vm.state.value.visibleItems
        assertTrue(visible.isNotEmpty())
        val leakedToken = visible.firstOrNull { it.id == "leaked-token" }
        assertNull("leaked-token entry should be hidden from the list", leakedToken)
    }

    @Test
    fun `social pattern in seed has no username`() {
        val vm = newVm()
        val social = vm.state.value.visibleItems
            .firstOrNull { it.category == MemoryCategory.SOCIAL_SPEECH_PATTERN }
        assertNotNull(social)
        assertFalse(
            "social pattern must not contain raw username",
            social!!.content.contains("jdoe"),
        )
    }

    @Test
    fun `temporary emotion in seed is demoted to ephemeral`() {
        val vm = newVm()
        val mood = vm.state.value.visibleItems.firstOrNull { it.id == "mood-spike" }
        assertNotNull(mood)
        assertEquals(MemoryDurability.EPHEMERAL, mood!!.durability)
    }

    @Test
    fun `search filters the visible list`() {
        val vm = newVm()
        vm.setQuery("orchestration")
        val out = vm.state.value.visibleItems
        assertTrue(out.isNotEmpty())
        assertTrue(out.all {
            it.title.contains("orchestration", ignoreCase = true) ||
                it.content.contains("orchestration", ignoreCase = true) ||
                it.tags.any { tag -> tag.contains("orchestration", ignoreCase = true) }
        })
    }

    @Test
    fun `filter by category narrows the visible list`() {
        val vm = newVm()
        vm.setCategory(MemoryCategory.DECISION_RECORD)
        val out = vm.state.value.visibleItems
        assertTrue(out.isNotEmpty())
        assertTrue(out.all { it.category == MemoryCategory.DECISION_RECORD })
    }

    @Test
    fun `detail opens on open and closes`() {
        val vm = newVm()
        val first = vm.state.value.visibleItems.first()
        vm.open(first)
        assertEquals(first.id, vm.state.value.selectedItem?.id)
        vm.closeDetail()
        assertNull(vm.state.value.selectedItem)
    }

    @Test
    fun `correct flow updates content`() = runTest {
        val vm = newVm(listOf(item("c1", "Title", "old", MemoryCategory.OWNER_PREFERENCE)))
        val target = vm.state.value.visibleItems.first()
        vm.beginCorrect(target)
        assertEquals(target.id, vm.state.value.correctingItem?.id)
        vm.confirmCorrect("new", "owner override")
        advanceUntilIdle()
        val updated = vm.state.value.visibleItems.firstOrNull { it.id == "c1" }
        assertNotNull(updated)
        assertEquals("new", updated!!.content)
        assertNull(vm.state.value.correctingItem)
    }

    @Test
    fun `delete flow removes item`() = runTest {
        val vm = newVm(
            listOf(
                item("d1", "Title 1", "x", MemoryCategory.OWNER_PREFERENCE),
                item("d2", "Title 2", "y", MemoryCategory.PROJECT_MEMORY),
            )
        )
        val target = vm.state.value.visibleItems.first { it.id == "d2" }
        vm.beginDelete(target)
        assertEquals("d2", vm.state.value.deletingItem?.id)
        vm.confirmDelete("not relevant anymore")
        advanceUntilIdle()
        val remaining = vm.state.value.visibleItems.map { it.id }
        assertFalse(remaining.contains("d2"))
        assertNull(vm.state.value.deletingItem)
    }

    @Test
    fun `delete dialog can be cancelled`() {
        val vm = newVm()
        val target = vm.state.value.visibleItems.first()
        vm.beginDelete(target)
        assertNotNull(vm.state.value.deletingItem)
        vm.cancelDelete()
        assertNull(vm.state.value.deletingItem)
    }

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

}
