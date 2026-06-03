package com.aci.hermes.ui.screens.evidence

import com.aci.hermes.data.cockpit.CockpitHttpExecutor
import com.aci.hermes.data.cockpit.CockpitRawResponse
import com.aci.hermes.data.cockpit.CockpitRequest
import com.aci.hermes.data.cockpit.HermesCockpitClient
import com.aci.hermes.data.evidence.EvidenceRepository
import com.aci.hermes.data.evidence.EvidenceTrust
import com.aci.hermes.data.evidence.MockEvidenceSeed
import com.aci.hermes.util.LogBuffer
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.advanceUntilIdle
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

    private fun pairedVm(exec: (CockpitRequest) -> CockpitRawResponse): EvidenceViewModel {
        val client = HermesCockpitClient(
            endpointProvider = { "http://127.0.0.1:8765" },
            tokenProvider = { "tok" },
            executor = CockpitHttpExecutor { exec(it) },
            ioDispatcher = Dispatchers.Unconfined,
        )
        val repo = EvidenceRepository(seed = emptyList(), client = client, paired = { true })
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

    @Test
    fun `search renders ranked hits not the stale list`() = runTest {
        val hitsJson = """
            {"items":[],"hits":[
              {"kind":"vault","title":"vLLM","uri":"https://docs.vllm.ai","excerpt":"batching",
               "trust":"primary","score":2.5,"artifact_id":"vllm","citation_anchors":[]}
            ]}
        """.trimIndent()
        val vm = pairedVm { CockpitRawResponse(200, hitsJson) }
        advanceUntilIdle()
        vm.setQuery("batching")
        vm.search()
        advanceUntilIdle()
        assertTrue(vm.state.value.searchActive)
        assertEquals(1, vm.state.value.items.size)
        assertEquals("vllm", vm.state.value.items.first().id)
        assertEquals(EvidenceTrust.PRIMARY, vm.state.value.items.first().trust)
    }

    @Test
    fun `owner-gated promotion never auto-authorizes — raises dialog, confirm sends phrase`() = runTest {
        val rejectJson = """{"promoted":false,"reasons":["durable confidence 0.40 below floor (owner approval required)"],"hint":"send authorization"}"""
        val okJson = """{"promoted":true,"node_id":"abc"}"""
        val vm = pairedVm { req ->
            // Promote only succeeds when the owner phrase is in the body.
            if (req.body?.contains("Yes, with authorization.") == true) {
                CockpitRawResponse(201, okJson)
            } else {
                CockpitRawResponse(422, rejectJson)
            }
        }
        advanceUntilIdle()
        val item = MockEvidenceSeed.items.first()

        // A normal Promote tap sends no phrase → owner-gated rejection raises the dialog.
        vm.promote(item)
        advanceUntilIdle()
        assertEquals(item.id, vm.state.value.authPromptItem?.id)

        // Only an explicit confirm sends the phrase and promotes.
        vm.confirmAuthorizedPromote()
        advanceUntilIdle()
        assertNull(vm.state.value.authPromptItem)
        assertEquals("Promoted to memory", vm.state.value.snackbar)
    }

    @Test
    fun `secret rejection is reported, not offered for override`() = runTest {
        val rejectJson = """{"promoted":false,"reasons":["secret-like pattern matched"],"hint":null}"""
        val vm = pairedVm { CockpitRawResponse(422, rejectJson) }
        advanceUntilIdle()
        vm.promote(MockEvidenceSeed.items.first())
        advanceUntilIdle()
        // Hard policy block — no auth dialog (the phrase can never bypass it).
        assertNull(vm.state.value.authPromptItem)
        assertTrue(vm.state.value.snackbar?.startsWith("Not promoted") == true)
    }
}
