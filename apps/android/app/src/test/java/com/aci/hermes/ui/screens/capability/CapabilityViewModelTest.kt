package com.aci.hermes.ui.screens.capability

import android.app.Application
import androidx.test.core.app.ApplicationProvider
import com.aci.hermes.data.capability.CapabilityRepository
import com.aci.hermes.util.LogBuffer
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@OptIn(ExperimentalCoroutinesApi::class)
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [33])
class CapabilityViewModelTest {

    private val dispatcher = UnconfinedTestDispatcher()

    private fun newVm(): CapabilityViewModel {
        val app = ApplicationProvider.getApplicationContext<Application>()
        return CapabilityViewModel(app, CapabilityRepository(), LogBuffer())
    }

    @Before
    fun setUp() {
        Dispatchers.setMain(dispatcher)
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    @Test
    fun `initial load surfaces the non-advanced catalog`() {
        val vm = newVm()
        val state = vm.state.value
        assertTrue("catalog should not be empty", state.results.isNotEmpty())
        assertTrue(state.totalCount >= state.results.size)
        assertTrue("default view hides advanced capabilities", state.results.none { it.isAdvanced })
    }

    @Test
    fun `including advanced widens the result set`() {
        val vm = newVm()
        val basic = vm.state.value.results.size
        vm.setIncludeAdvanced(true)
        assertTrue(vm.state.value.results.size >= basic)
    }

    @Test
    fun `selecting a capability builds a route preview`() {
        val vm = newVm()
        val first = vm.state.value.results.first()
        vm.select(first)
        assertEquals(first.id, vm.state.value.selected?.id)
        assertNotNull(vm.state.value.preview)
        vm.select(null)
        assertNull(vm.state.value.selected)
        assertNull(vm.state.value.preview)
    }
}
