package com.aci.hermes.ui.screens.coding

import com.aci.hermes.data.cockpit.CockpitHttpExecutor
import com.aci.hermes.data.cockpit.CockpitRawResponse
import com.aci.hermes.data.cockpit.CockpitRequest
import com.aci.hermes.data.cockpit.HermesCockpitClient
import com.aci.hermes.data.coding.CodingHandoffState
import com.aci.hermes.data.coding.CodingRepository
import com.aci.hermes.data.coding.CodingTaskStore
import com.aci.hermes.testutil.MainDispatcherRule
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import java.nio.file.Files

@OptIn(ExperimentalCoroutinesApi::class)
class NewCodingTaskViewModelTest {

    @get:Rule
    val mainDispatcherRule = MainDispatcherRule(StandardTestDispatcher())

    private fun repo(
        paired: Boolean,
        mock: Boolean,
        scope: kotlinx.coroutines.CoroutineScope,
        exec: (CockpitRequest) -> CockpitRawResponse = { error("no wire") },
    ): CodingRepository {
        val store = CodingTaskStore(
            Files.createTempDirectory("vm-new").toFile(),
            scope = scope,
            ioDispatcher = Dispatchers.Unconfined,
        )
        val client = HermesCockpitClient(
            endpointProvider = { "http://127.0.0.1:8765" },
            tokenProvider = { if (paired) "tok" else null },
            executor = CockpitHttpExecutor { exec(it) },
            ioDispatcher = Dispatchers.Unconfined,
        )
        return CodingRepository(client, store, paired = { paired }, mockMode = { mock })
    }

    @Test
    fun `mock generate produces a navigable planned demo task`() = runTest {
        val vm = mainDispatcherRule.register(NewCodingTaskViewModel(repo(paired = false, mock = true, scope = this), { false }, { true }))
        vm.updatePrompt("build a thing")
        vm.generatePacket()
        advanceUntilIdle()
        val id = vm.state.value.navigateToTaskId
        assertNotNull("Generate must always land on a task", id)
    }

    @Test
    fun `empty prompt is rejected with a message`() = runTest {
        val vm = mainDispatcherRule.register(NewCodingTaskViewModel(repo(paired = true, mock = false, scope = this), { true }, { false }))
        vm.generatePacket()
        advanceUntilIdle()
        assertTrue(vm.state.value.message!!.contains("Describe", ignoreCase = true))
        assertEquals(null, vm.state.value.navigateToTaskId)
    }

    @Test
    fun `offline generate still navigates so there is no dead end`() = runTest {
        val r = repo(paired = false, mock = false, scope = this) { error("must not hit wire") }
        val vm = mainDispatcherRule.register(NewCodingTaskViewModel(r, { false }, { false }))
        vm.updatePrompt("offline task")
        vm.generatePacket()
        advanceUntilIdle()
        val id = vm.state.value.navigateToTaskId
        assertNotNull(id)
        assertEquals(CodingHandoffState.QUEUED_OFFLINE, r.byId(id!!)?.state)
    }
}
