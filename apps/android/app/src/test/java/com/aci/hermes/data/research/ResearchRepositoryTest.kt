package com.aci.hermes.data.research

import com.aci.hermes.data.cockpit.CockpitHttpExecutor
import com.aci.hermes.data.cockpit.CockpitRawResponse
import com.aci.hermes.data.cockpit.CockpitRequest
import com.aci.hermes.data.cockpit.HermesCockpitClient
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Drives [ResearchRepository] through a faked cockpit transport. Asserts the
 * JSON↔model mapping, the unpaired honest-empty path, and that a 422 promote
 * surfaces as a policy *rejection* (not a crash).
 */
class ResearchRepositoryTest {

    private class FakeExecutor(
        private val responder: (CockpitRequest) -> CockpitRawResponse,
    ) : CockpitHttpExecutor {
        var lastRequest: CockpitRequest? = null
        override fun execute(request: CockpitRequest): CockpitRawResponse {
            lastRequest = request
            return responder(request)
        }
    }

    private fun client(executor: CockpitHttpExecutor) = HermesCockpitClient(
        endpointProvider = { "http://127.0.0.1:8765" },
        tokenProvider = { "tok" },
        executor = executor,
        ioDispatcher = Dispatchers.Unconfined,
    )

    private val reportJson = """
        {"id":"rr_1","query":"q","sub_questions":["a"],
         "cards":[{"id":"c1","title":"Doc","source_uri":"https://x","source_type":"official_doc",
                   "evidence_strength":"primary","excerpt":"QUIC over UDP","claim":"QUIC over UDP","relevance":0.5}],
         "claims":[{"text":"QUIC over UDP","supporting_card_ids":["c1"],"confidence":0.9,"uncertainty":""}],
         "contradictions":[],"final_answer":"- QUIC over UDP [https://x]","uncertainty":"pass",
         "citations":["https://x"],"notes":"","created_at":"2026-01-01T00:00:00Z"}
    """.trimIndent()

    @Test
    fun `run maps the report and marks loaded`() = runTest {
        val repo = ResearchRepository(
            client = client(FakeExecutor { CockpitRawResponse(201, reportJson) }),
            paired = { true },
        )
        repo.run("q")
        val report = repo.report.value
        assertEquals("rr_1", report?.id)
        assertEquals(1, report?.cards?.size)
        assertEquals("primary", report?.cards?.first()?.evidenceStrength)
        assertTrue(repo.sync.value is ResearchSync.Loaded)
    }

    @Test
    fun `unpaired run is honest, never fabricated`() = runTest {
        val repo = ResearchRepository(client = client(FakeExecutor { CockpitRawResponse(201, reportJson) }), paired = { false })
        repo.run("q")
        assertEquals(null, repo.report.value)
        assertTrue(repo.sync.value is ResearchSync.Unpaired)
    }

    @Test
    fun `promote stored returns Stored`() = runTest {
        var call = 0
        val exec = FakeExecutor {
            call++
            if (call == 1) CockpitRawResponse(201, reportJson)
            else CockpitRawResponse(201, """{"stored":true,"item":null}""")
        }
        val repo = ResearchRepository(client = client(exec), paired = { true })
        repo.run("q")
        assertEquals(PromoteOutcome.Stored, repo.promote("c1"))
    }

    @Test
    fun `promote 422 surfaces as a policy rejection`() = runTest {
        var call = 0
        val exec = FakeExecutor {
            call++
            if (call == 1) CockpitRawResponse(201, reportJson)
            else CockpitRawResponse(422, """{"error":{"code":"unprocessable","message":"rejected (secret-like or low confidence)"}}""")
        }
        val repo = ResearchRepository(client = client(exec), paired = { true })
        repo.run("q")
        val outcome = repo.promote("c1")
        assertTrue("expected Rejected, got $outcome", outcome is PromoteOutcome.Rejected)
    }

    @Test
    fun `createTask returns the queued job`() = runTest {
        var call = 0
        val exec = FakeExecutor {
            call++
            if (call == 1) CockpitRawResponse(201, reportJson)
            else CockpitRawResponse(
                201,
                """{"id":"job_1","title":"Research: q","worker_id":"","status":"QUEUED","created_at":"t","updated_at":"t"}""",
            )
        }
        val repo = ResearchRepository(client = client(exec), paired = { true })
        repo.run("q")
        val outcome = repo.createTask("Research: q")
        assertTrue("expected Created, got $outcome", outcome is TaskOutcome.Created)
        assertEquals("job_1", (outcome as TaskOutcome.Created).job.id)
    }
}
