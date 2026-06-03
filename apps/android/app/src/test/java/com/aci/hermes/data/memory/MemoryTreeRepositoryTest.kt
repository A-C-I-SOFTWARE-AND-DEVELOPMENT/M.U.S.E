package com.aci.hermes.data.memory

import com.aci.hermes.data.cockpit.CockpitHttpExecutor
import com.aci.hermes.data.cockpit.CockpitRawResponse
import com.aci.hermes.data.cockpit.CockpitRequest
import com.aci.hermes.data.cockpit.HermesCockpitClient
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Drives [MemoryTreeRepository] through the real [HermesCockpitClient] over a
 * fake executor — request shape and every decision path are covered without a
 * socket. The proposed inbox is the owner gate that turns a captured candidate
 * into durable memory, so these paths matter for safety.
 */
class MemoryTreeRepositoryTest {

    private class FakeExecutor(
        private val responder: (CockpitRequest) -> CockpitRawResponse,
    ) : CockpitHttpExecutor {
        var lastRequest: CockpitRequest? = null
        val requests = mutableListOf<CockpitRequest>()
        override fun execute(request: CockpitRequest): CockpitRawResponse {
            lastRequest = request
            requests.add(request)
            return responder(request)
        }

        /** A decision/resolve POST fires a follow-up GET refresh, so assert the
         *  POST happened among all requests rather than that it was last. */
        fun posted(url: String): Boolean =
            requests.any { it.method == "POST" && it.url == url }
    }

    private fun client(executor: CockpitHttpExecutor) = HermesCockpitClient(
        endpointProvider = { "http://127.0.0.1:8765" },
        tokenProvider = { "tok" },
        executor = executor,
        ioDispatcher = Dispatchers.Unconfined,
    )

    private fun repo(executor: CockpitHttpExecutor, paired: Boolean = true) =
        MemoryTreeRepository(client(executor), paired = { paired })

    @Test
    fun `refreshProposed maps nodes and reports loaded`() = runTest {
        val fake = FakeExecutor {
            CockpitRawResponse(
                200,
                """{"nodes":[{"id":"n1","namespace":"jarvis/decisions","layer":"session",
                   "title":"deploy","summary":"deploy Monday","sources":["docs/x.md"],
                   "confidence":0.6,"approval_state":"proposed"}]}""".trimIndent(),
            )
        }
        val r = repo(fake)
        r.refreshProposed()
        assertEquals(1, r.proposed.value.size)
        val node = r.proposed.value.first()
        assertEquals("deploy", node.title)
        assertTrue(node.durableWorthy) // jarvis/decisions
        assertEquals(listOf("docs/x.md"), node.sources)
        assertTrue(r.sync.value is TreeSync.Loaded)
        assertEquals("GET", fake.lastRequest?.method)
        assertEquals(
            "http://127.0.0.1:8765/v1/cockpit/memory/tree/proposed",
            fake.lastRequest?.url,
        )
    }

    @Test
    fun `unpaired refresh does not call the gateway`() = runTest {
        val fake = FakeExecutor { error("should not be called") }
        val r = repo(fake, paired = false)
        r.refreshProposed()
        assertEquals(TreeSync.Unpaired, r.sync.value)
        assertNull(fake.lastRequest)
    }

    @Test
    fun `approve posts a decision and returns Ok`() = runTest {
        val fake = FakeExecutor { req ->
            if (req.method == "POST") {
                CockpitRawResponse(
                    200,
                    """{"decided":"approve","node":{"id":"n1","namespace":"jarvis/decisions",
                       "layer":"durable","title":"deploy","approval_state":"owner_approved"}}""".trimIndent(),
                )
            } else {
                CockpitRawResponse(200, """{"nodes":[]}""")
            }
        }
        val r = repo(fake)
        val outcome = r.approve("n1")
        assertEquals(DecisionOutcome.Ok, outcome)
        // The decision POST fires before the follow-up proposed-inbox refresh.
        assertTrue(fake.posted("http://127.0.0.1:8765/v1/cockpit/memory/tree/n1/decision"))
    }

    @Test
    fun `approve conflict surfaces a contradiction outcome`() = runTest {
        val fake = FakeExecutor { req ->
            if (req.method == "POST") {
                CockpitRawResponse(
                    200,
                    """{"decided":"approve","node":{"id":"n1","namespace":"jarvis/decisions",
                       "layer":"durable","title":"deploy"},
                       "contradiction":{"id":"c1","subject":"deploy","node_a_id":"a","node_b_id":"n1",
                       "reason":"conflict","status":"contested"}}""".trimIndent(),
                )
            } else if (req.url.endsWith("/contradictions")) {
                CockpitRawResponse(200, """{"contradictions":[]}""")
            } else {
                CockpitRawResponse(200, """{"nodes":[]}""")
            }
        }
        val r = repo(fake)
        val outcome = r.approve("n1")
        assertTrue(outcome is DecisionOutcome.Conflict)
        assertEquals("deploy", (outcome as DecisionOutcome.Conflict).contradiction.subject)
    }

    @Test
    fun `resolveContradiction posts winner and refreshes`() = runTest {
        val fake = FakeExecutor { req ->
            if (req.method == "POST") {
                CockpitRawResponse(
                    200,
                    """{"resolved":{"id":"c1","node_a_id":"a","node_b_id":"b","status":"resolved"}}""",
                )
            } else {
                CockpitRawResponse(200, """{"contradictions":[]}""")
            }
        }
        val r = repo(fake)
        val outcome = r.resolveContradiction("c1", "b", note = "b wins")
        assertEquals(DecisionOutcome.Ok, outcome)
        // The resolve POST fires before the follow-up contradictions refresh.
        assertTrue(fake.posted("http://127.0.0.1:8765/v1/cockpit/memory/contradictions/c1/resolve"))
    }

    @Test
    fun `gateway failure becomes an honest error outcome`() = runTest {
        val fake = FakeExecutor { CockpitRawResponse(500, """{"error":{"code":"boom","message":"nope"}}""") }
        val r = repo(fake)
        val outcome = r.reject("n1")
        assertTrue(outcome is DecisionOutcome.Error)
    }
}
