package com.aci.hermes.learning

import com.aci.hermes.data.cockpit.CockpitHttpExecutor
import com.aci.hermes.data.cockpit.CockpitRawResponse
import com.aci.hermes.data.cockpit.CockpitRequest
import com.aci.hermes.data.cockpit.HermesCockpitClient
import com.aci.hermes.data.learning.LearningStatus
import com.aci.hermes.learning.state.LearningRepository
import com.aci.hermes.learning.state.LearningSync
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The Learning Queue repository: when paired it loads real candidates from
 * the gateway and decides them with the owner phrase; unpaired/unreachable
 * yields an honest empty list — never fabricated candidates.
 */
class LearningRepositoryTest {

    private fun client(
        token: String? = "tok",
        exec: (CockpitRequest) -> CockpitRawResponse,
    ) = HermesCockpitClient(
        endpointProvider = { "http://127.0.0.1:8765" },
        tokenProvider = { token },
        executor = CockpitHttpExecutor { exec(it) },
        ioDispatcher = Dispatchers.Unconfined,
    )

    private val listJson = """
        {"learning":[
          {"id":"abc123","title":"research answer trace","trace_type":"research_answer_trace",
           "status":"pending","labels":[],"is_negative":false,
           "quality":{"tests_passed":false,"citations_verified":true,"owner_approved":false,
                      "reviewer_passed":false,"rollback_available":false},
           "provenance":{"source_kind":"research_vault","source_uri":"https://example.org",
                         "citations":["https://example.org"]},
           "created_at":"2026-06-01T00:00:00+00:00"}
        ]}
    """.trimIndent()

    @Test
    fun `refresh loads and maps candidates when paired`() = runTest {
        val repo = LearningRepository(client { CockpitRawResponse(200, listJson) })
        repo.refresh()
        val cands = repo.candidates.value
        assertEquals(1, cands.size)
        assertEquals("research_answer_trace", cands[0].traceType)
        assertEquals(LearningStatus.PENDING, cands[0].status)
        assertTrue(cands[0].quality.citationsVerified)
        assertEquals(listOf("https://example.org"), cands[0].citations)
        assertTrue(repo.sync.value is LearningSync.Loaded)
    }

    @Test
    fun `unpaired refresh yields empty and NotPaired`() = runTest {
        val repo = LearningRepository(
            client(token = null) { error("must not hit the wire when unpaired") },
        )
        repo.refresh()
        assertEquals(LearningSync.NotPaired, repo.sync.value)
        assertTrue(repo.candidates.value.isEmpty())
    }

    @Test
    fun `gateway error surfaces honest error, never fake data`() = runTest {
        val repo = LearningRepository(client { CockpitRawResponse(500, "boom") })
        repo.refresh()
        assertTrue(repo.sync.value is LearningSync.Error)
        assertTrue(repo.candidates.value.isEmpty())
    }

    @Test
    fun `approve submits the owner phrase`() = runTest {
        var sentBody: String? = null
        val repo = LearningRepository(
            client { req ->
                if (req.method == "POST") {
                    sentBody = req.body
                    CockpitRawResponse(200, """{"id":"abc123","status":"approve"}""")
                } else {
                    CockpitRawResponse(200, """{"learning":[]}""")
                }
            },
        )
        repo.approve("abc123")
        assertTrue(sentBody?.contains("Yes, with authorization.") == true)
        assertTrue(sentBody?.contains("\"approve\"") == true)
    }

    @Test
    fun `reject sends no owner phrase`() = runTest {
        var sentBody: String? = null
        val repo = LearningRepository(
            client { req ->
                if (req.method == "POST") {
                    sentBody = req.body
                    CockpitRawResponse(200, """{"id":"abc123","status":"reject"}""")
                } else {
                    CockpitRawResponse(200, """{"learning":[]}""")
                }
            },
        )
        repo.reject("abc123")
        assertFalse(sentBody?.contains("Yes, with authorization.") == true)
        assertTrue(sentBody?.contains("\"reject\"") == true)
    }
}
