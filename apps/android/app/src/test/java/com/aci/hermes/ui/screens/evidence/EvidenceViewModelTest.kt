package com.aci.hermes.ui.screens.evidence

import com.aci.hermes.data.evidence.EvidenceRepository
import com.aci.hermes.data.evidence.MockEvidenceSeed
import com.aci.hermes.util.LogBuffer
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class EvidenceViewModelTest {

    private val dispatcher = UnconfinedTestDispatcher()

    @Before
    fun setUp() {
        Dispatchers.setMain(dispatcher)
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    private fun newVm(): EvidenceViewModel {
        // Unpaired repository → renders the mock seed, no network.
        val repo = EvidenceRepository(seed = MockEvidenceSeed.items)
        return EvidenceViewModel(repo, LogBuffer())
    }

    @Test
    fun `seed items render`() {
        val vm = newVm()
        assertTrue(vm.state.value.items.isNotEmpty())
    }

    @Test
    fun `open and close detail`() {
        val vm = newVm()
        val item = vm.state.value.items.first()
        vm.open(item)
        assertEquals(item.id, vm.state.value.selected?.id)
        vm.closeDetail()
        assertNull(vm.state.value.selected)
    }

    @Test
    fun `promote without paired gateway reports needs-gateway`() = runTest {
        val vm = newVm()
        vm.promote(vm.state.value.items.first())
        assertTrue(vm.state.value.snackbar?.contains("paired gateway") == true)
    }

    @Test
    fun `query updates state`() {
        val vm = newVm()
        vm.setQuery("batching")
        assertEquals("batching", vm.state.value.query)
    }
}
