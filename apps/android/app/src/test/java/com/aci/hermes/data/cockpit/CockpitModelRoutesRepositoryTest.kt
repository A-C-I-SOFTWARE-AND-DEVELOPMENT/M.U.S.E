package com.aci.hermes.data.cockpit

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class CockpitModelRoutesRepositoryTest {

    private fun client(
        token: String? = "tok",
        exec: (CockpitRequest) -> CockpitRawResponse,
    ) = HermesCockpitClient(
        endpointProvider = { "http://127.0.0.1:8765" },
        tokenProvider = { token },
        executor = CockpitHttpExecutor { exec(it) },
        ioDispatcher = Dispatchers.Unconfined,
    )

    private fun route(taskClass: String, chosen: String) = """
        {"task_class":"$taskClass","chosen":"$chosen","route_tier":"local_first",
         "fallback_chain":["$chosen"],"why":"because","evidence":[],
         "local_first":true,"paid_allowed":false,"paid_enabled":false,
         "owner_override":null}
    """.trimIndent()

    @Test
    fun `refresh loads routes when paired`() = runTest {
        val repo = CockpitModelRoutesRepository(
            client {
                CockpitRawResponse(
                    200,
                    """{"routes":[${route("summarization", "local-model")}],
                        "task_classes":["summarization"],"paid_enabled":false}""",
                )
            },
        )
        repo.refresh()
        assertEquals(1, repo.routes.value.routes.size)
        assertEquals(ModelRoutesSync.Loaded(1), repo.sync.value)
    }

    @Test
    fun `unpaired refresh yields NotPaired and no fabricated routes`() = runTest {
        val repo = CockpitModelRoutesRepository(client(token = null) { error("must not hit the wire") })
        repo.refresh()
        assertEquals(ModelRoutesSync.NotPaired, repo.sync.value)
        assertTrue(repo.routes.value.routes.isEmpty())
    }

    @Test
    fun `degraded 200 payload with error surfaces as Error not empty Loaded`() = runTest {
        // Honest-empty contract: the gateway returns HTTP 200 with an `error`
        // string (and no routes) when route generation degrades. The UI must
        // see the error, not a silent Loaded(0).
        val repo = CockpitModelRoutesRepository(
            client { CockpitRawResponse(200, """{"routes":[],"error":"scorecard unavailable"}""") },
        )
        repo.refresh()
        val sync = repo.sync.value
        assertTrue(sync is ModelRoutesSync.Error)
        assertEquals("scorecard unavailable", (sync as ModelRoutesSync.Error).message)
    }

    @Test
    fun `transport failure surfaces as Error`() = runTest {
        val repo = CockpitModelRoutesRepository(
            client { CockpitRawResponse(500, """{"error":{"code":"boom","message":"server fell over"}}""") },
        )
        repo.refresh()
        assertTrue(repo.sync.value is ModelRoutesSync.Error)
    }
}
