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
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import java.nio.file.Files

@OptIn(ExperimentalCoroutinesApi::class)
class WorkPacketDetailViewModelTest {

    @get:Rule
    val mainDispatcherRule = MainDispatcherRule(StandardTestDispatcher())

    private fun repo(
        paired: Boolean,
        mock: Boolean,
        scope: kotlinx.coroutines.CoroutineScope,
        exec: (CockpitRequest) -> CockpitRawResponse = { error("no wire") },
    ): CodingRepository {
        val store = CodingTaskStore(
            Files.createTempDirectory("vm-packet").toFile(),
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
    fun `copy prompt produces text and marks handed off`() = runTest {
        val r = repo(paired = false, mock = true, scope = this)
        val draft = r.createDraft("demo task", "")
        r.runPlan(draft.id)
        val vm = mainDispatcherRule.register(WorkPacketDetailViewModel(r, draft.id))
        advanceUntilIdle()
        vm.copyPrompt()
        advanceUntilIdle()
        assertNotNull("copyText must be produced for the screen to copy", vm.state.value.copyText)
        assertTrue(vm.state.value.copyText!!.contains("## Mission"))
        vm.consumeCopy()
        advanceUntilIdle()
        assertNull(vm.state.value.copyText)
    }

    @Test
    fun `send without phrase surfaces the owner gate`() = runTest {
        val r = repo(paired = true, mock = false, scope = this) { _ ->
            CockpitRawResponse(
                200,
                """{"status":"approval_required","authorization_required":true,
                    "authorization_hint":"Reply: Yes, with authorization.",
                    "job":{"id":"j1","status":"WAITING_FOR_APPROVAL","prompt":"x"}}""",
            )
        }
        val draft = r.createDraft("ship", "/repo")
        // Give it a packet first so Send is meaningful.
        val vm = mainDispatcherRule.register(WorkPacketDetailViewModel(r, draft.id))
        advanceUntilIdle()
        vm.sendToBackend(null)
        advanceUntilIdle()
        assertNotNull(vm.state.value.ownerGateHint)
        assertTrue(r.byId(draft.id)?.state == CodingHandoffState.BLOCKED_OWNER)
    }
}
