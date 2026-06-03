package com.aci.hermes.ui.screens.diagnostics

import com.aci.hermes.data.cockpit.CockpitHttpExecutor
import com.aci.hermes.data.cockpit.CockpitRawResponse
import com.aci.hermes.data.cockpit.HermesCockpitClient
import com.aci.hermes.util.LogBuffer
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class DiagnosticsViewModelTest {

    private val testDispatcher = StandardTestDispatcher()

    @Before fun setUp() { Dispatchers.setMain(testDispatcher) }
    @After fun tearDown() { Dispatchers.resetMain() }

    private fun client(
        token: String? = "tok",
        exec: (com.aci.hermes.data.cockpit.CockpitRequest) -> CockpitRawResponse,
    ) = HermesCockpitClient(
        endpointProvider = { "http://127.0.0.1:8765" },
        tokenProvider = { token },
        executor = CockpitHttpExecutor { exec(it) },
        ioDispatcher = Dispatchers.Unconfined,
    )

    @Test
    fun `loads the backend report when paired`() = runTest {
        val vm = DiagnosticsViewModel(
            LogBuffer(),
            client { CockpitRawResponse(200, """{"ok":true,"checks":[{"name":"memory","status":"pass","detail":"ok"}]}""") },
        )
        advanceUntilIdle()
        val backend = vm.state.value.backend
        assertTrue(backend is BackendDiagnosticsSync.Loaded)
        assertTrue((backend as BackendDiagnosticsSync.Loaded).report.ok)
    }

    @Test
    fun `unpaired reports NotPaired, never a faked report`() = runTest {
        val vm = DiagnosticsViewModel(
            LogBuffer(),
            client(token = null) { error("must not hit the wire") },
        )
        advanceUntilIdle()
        assertEquals(BackendDiagnosticsSync.NotPaired, vm.state.value.backend)
    }

    @Test
    fun `no client leaves backend idle (offline-safe)`() = runTest {
        val vm = DiagnosticsViewModel(LogBuffer())
        advanceUntilIdle()
        assertEquals(BackendDiagnosticsSync.Idle, vm.state.value.backend)
    }
}
