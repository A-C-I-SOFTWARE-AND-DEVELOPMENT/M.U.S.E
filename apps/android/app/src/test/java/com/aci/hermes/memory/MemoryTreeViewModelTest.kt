package com.aci.hermes.memory

import com.aci.hermes.data.cockpit.CockpitHttpExecutor
import com.aci.hermes.data.cockpit.CockpitRawResponse
import com.aci.hermes.data.cockpit.CockpitRequest
import com.aci.hermes.data.cockpit.HermesCockpitClient
import com.aci.hermes.data.memory.MemoryRepository
import com.aci.hermes.data.memory.MemoryTreeRepository
import com.aci.hermes.ui.screens.memory.MemoryTab
import com.aci.hermes.testutil.MainDispatcherRule
import com.aci.hermes.ui.screens.memory.MemoryViewModel
import com.aci.hermes.util.LogBuffer
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test

/** Covers the Memory Tree tabs wired into [MemoryViewModel]. */
@OptIn(ExperimentalCoroutinesApi::class)
class MemoryTreeViewModelTest {

    @get:Rule
    val mainDispatcherRule = MainDispatcherRule(UnconfinedTestDispatcher())

    private class FakeExecutor(
        private val responder: (CockpitRequest) -> CockpitRawResponse,
    ) : CockpitHttpExecutor {
        override fun execute(request: CockpitRequest): CockpitRawResponse = responder(request)
    }

    private fun treeRepo(responder: (CockpitRequest) -> CockpitRawResponse): MemoryTreeRepository {
        val client = HermesCockpitClient(
            endpointProvider = { "http://127.0.0.1:8765" },
            tokenProvider = { "tok" },
            executor = FakeExecutor(responder),
            ioDispatcher = Dispatchers.Unconfined,
        )
        return MemoryTreeRepository(client, paired = { true })
    }

    @Test
    fun `selecting inbox loads proposed candidates`() = runTest {
        val tree = treeRepo { req ->
            if (req.url.endsWith("/tree/proposed")) {
                CockpitRawResponse(
                    200,
                    """{"nodes":[{"id":"n1","namespace":"jarvis/personal","layer":"session",
                       "title":"prefers dark mode","approval_state":"proposed"}]}""".trimIndent(),
                )
            } else {
                CockpitRawResponse(200, """{"nodes":[]}""")
            }
        }
        val vm = mainDispatcherRule.register(MemoryViewModel(MemoryRepository(emptyList()), LogBuffer(), tree))
        vm.selectTab(MemoryTab.INBOX)
        assertEquals(MemoryTab.INBOX, vm.state.value.tab)
        assertEquals(1, vm.state.value.proposed.size)
        assertEquals("prefers dark mode", vm.state.value.proposed.first().title)
    }

    @Test
    fun `approve surfaces a snackbar`() = runTest {
        val tree = treeRepo { req ->
            when {
                req.method == "POST" -> CockpitRawResponse(
                    200,
                    """{"decided":"approve","node":{"id":"n1","namespace":"jarvis/personal",
                       "layer":"durable","title":"x"}}""".trimIndent(),
                )
                else -> CockpitRawResponse(200, """{"nodes":[]}""")
            }
        }
        val vm = mainDispatcherRule.register(MemoryViewModel(MemoryRepository(emptyList()), LogBuffer(), tree))
        vm.approveProposed("n1")
        assertTrue(vm.state.value.snackbar != null)
    }

    @Test
    fun `viewmodel works without a tree repository`() = runTest {
        // The tree repo is optional — legacy construction must still work.
        val vm = mainDispatcherRule.register(MemoryViewModel(MemoryRepository(emptyList()), LogBuffer()))
        vm.selectTab(MemoryTab.INBOX)
        assertEquals(MemoryTab.INBOX, vm.state.value.tab)
        assertTrue(vm.state.value.proposed.isEmpty())
    }
}
