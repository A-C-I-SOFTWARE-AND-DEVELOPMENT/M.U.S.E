package com.aci.hermes.data.evidence

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
 * Evidence repository cutover: when paired it serves the real gateway list,
 * verifies/promotes through the gateway, and surfaces honest errors —
 * never fake data. Promotion rejection is reported, never silently faked.
 */
class EvidenceRepositoryTest {

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
        {"items":[
          {"id":"vllm","title":"vLLM batching","source_uri":"https://docs.vllm.ai",
           "source_type":"official_doc","evidence_strength":"primary","trust":"primary",
           "excerpt":"continuous batching","summary":"raises throughput","tags":["vllm"],
           "license_notes":"","retrieved_at":"2026-05-30T12:00:00+00:00","freshness_due":null,
           "checksum":"abc","citation_anchors":["serving.md:12"],"added_at":"2026-05-30T12:00:00+00:00"}
        ]}
    """.trimIndent()

    @Test
    fun `refresh loads and maps live items when paired`() = runTest {
        val repo = EvidenceRepository(
            seed = emptyList(),
            client = client { CockpitRawResponse(200, listJson) },
            paired = { true },
        )
        repo.refresh()
        val items = repo.items.value
        assertEquals(1, items.size)
        assertEquals(EvidenceTrust.PRIMARY, items[0].trust)
        assertEquals("serving.md:12", items[0].citationAnchors.first())
        assertTrue(repo.sync.value is EvidenceSync.Loaded)
        assertTrue(repo.isLive)
    }

    @Test
    fun `unpaired refresh stays mock-only and keeps the seed`() = runTest {
        val seed = MockEvidenceSeed.items
        val repo = EvidenceRepository(
            seed = seed,
            client = client(token = null) { error("must not hit the wire when unpaired") },
            paired = { false },
        )
        repo.refresh()
        assertEquals(EvidenceSync.MockOnly, repo.sync.value)
        assertEquals(seed.size, repo.items.value.size)
    }

    @Test
    fun `search populates ranked hits`() = runTest {
        val hitsJson = """
            {"items":[],"hits":[
              {"kind":"vault","title":"vLLM","uri":"https://docs.vllm.ai","excerpt":"batching",
               "trust":"primary","score":2.5,"artifact_id":"vllm","citation_anchors":["serving.md:12"]}
            ]}
        """.trimIndent()
        val repo = EvidenceRepository(
            seed = emptyList(),
            client = client { CockpitRawResponse(200, hitsJson) },
            paired = { true },
        )
        repo.search("batching")
        assertEquals(1, repo.hits.value.size)
        assertEquals(EvidenceTrust.PRIMARY, repo.hits.value.first().trust)
    }

    @Test
    fun `promote rejection is reported honestly`() = runTest {
        val rejectJson = """{"promoted":false,"reasons":["durable confidence 0.40 below floor"],"hint":"send authorization"}"""
        val repo = EvidenceRepository(
            seed = emptyList(),
            client = client { CockpitRawResponse(422, rejectJson) },
            paired = { true },
        )
        val outcome = repo.promote("vllm")
        assertTrue(outcome is PromoteOutcome.Rejected)
    }

    @Test
    fun `promote success returns node id`() = runTest {
        val okJson = """{"promoted":true,"node_id":"abc123"}"""
        val repo = EvidenceRepository(
            seed = emptyList(),
            client = client { CockpitRawResponse(201, okJson) },
            paired = { true },
        )
        val outcome = repo.promote("vllm", authorization = "Yes, with authorization.")
        assertTrue(outcome is PromoteOutcome.Promoted)
        assertEquals("abc123", (outcome as PromoteOutcome.Promoted).nodeId)
    }

    @Test
    fun `gateway error surfaces honest error, never fake data`() = runTest {
        val repo = EvidenceRepository(
            seed = emptyList(),
            client = client { CockpitRawResponse(500, "boom") },
            paired = { true },
        )
        repo.refresh()
        assertTrue(repo.sync.value is EvidenceSync.Error)
        assertTrue(repo.items.value.isEmpty())
    }
}
