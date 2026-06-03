package com.aci.hermes.ui.screens.diagnostics

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

@OptIn(ExperimentalCoroutinesApi::class)
class DiagnosticsViewModelTest {

    private val dispatcher = UnconfinedTestDispatcher()

    @Before
    fun setUp() {
        Dispatchers.setMain(dispatcher)
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    @Test
    fun `initial state carries build identity and existing logs`() {
        val log = LogBuffer()
        log.info("Boot", "started")
        val vm = DiagnosticsViewModel(log)
        val state = vm.state.value
        assertTrue("app version should be populated", state.appVersion.isNotBlank())
        assertTrue(state.logs.any { it.message == "started" })
    }

    @Test
    fun `new log entries flow into state and last error is surfaced`() {
        val log = LogBuffer()
        val vm = DiagnosticsViewModel(log)
        assertNull(vm.state.value.lastError)
        log.error("Net", "boom")
        val state = vm.state.value
        assertNotNull("an error should surface as lastError", state.lastError)
        assertEquals("boom", state.lastError?.message)
        assertTrue(state.logs.any { it.message == "boom" })
    }

    @Test
    fun `clearLogs empties the buffer`() {
        val log = LogBuffer()
        log.info("X", "a")
        val vm = DiagnosticsViewModel(log)
        assertTrue(vm.state.value.logs.isNotEmpty())
        vm.clearLogs()
        assertTrue(vm.state.value.logs.isEmpty())
    }
}
