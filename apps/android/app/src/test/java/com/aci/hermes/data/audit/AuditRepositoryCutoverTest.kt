package com.aci.hermes.data.audit

import com.aci.hermes.data.cockpit.CockpitHttpExecutor
import com.aci.hermes.data.cockpit.CockpitRawResponse
import com.aci.hermes.data.cockpit.CockpitRequest
import com.aci.hermes.data.cockpit.HermesCockpitClient
import com.aci.hermes.data.model.audit.RiskTier
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

class AuditRepositoryCutoverTest {

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
        {"records":[{"id":"a1","timestamp":"2026-05-30T12:00:00Z","user_request":"do",
          "action":"did","risk_tier":"MODERATE",
          "route":{"destination":"CODEX","model":"codex","reason":"why","duration_ms":1200},
          "approval_state":"APPROVED","result":"SUCCESS","confidence":0.9,"proof_id":"a1"}]}
    """.trimIndent()

    private val proofJson = """
        {"id":"a1","audit_id":"a1","rationale":"r","evidence":[],"tests_run":[],
         "files_changed":[],"verification":{"status":"PASSED","summary":"ok",
         "failing_checks":[],"passed_checks":["c"]},"approvals":[],"rollback":null,
         "impact_report":null,"worker_runs":[]}
    """.trimIndent()

    @Test
    fun `refresh loads live audit records when paired`() = runTest {
        val repo = AuditRepository(
            seed = EmptyAuditSeed,
            client = client { CockpitRawResponse(200, listJson) },
            paired = { true },
        )
        repo.refresh()
        assertEquals(1, repo.records.value.size)
        assertEquals(RiskTier.MODERATE, repo.records.value[0].riskTier)
        assertTrue(repo.sync.value is AuditSync.Loaded)
        assertTrue(repo.isLive)
    }

    @Test
    fun `unpaired stays mock-only and never hits the wire`() = runTest {
        val repo = AuditRepository(
            seed = EmptyAuditSeed,
            client = client(token = null) { error("must not hit the wire") },
            paired = { false },
        )
        repo.refresh()
        assertEquals(AuditSync.MockOnly, repo.sync.value)
        assertTrue(repo.records.value.isEmpty())
    }

    @Test
    fun `fetchProof fetches once and caches`() = runTest {
        var proofHits = 0
        val repo = AuditRepository(
            seed = EmptyAuditSeed,
            client = client { req ->
                if (req.url.endsWith("/proof")) {
                    proofHits++
                    CockpitRawResponse(200, proofJson)
                } else {
                    CockpitRawResponse(200, listJson)
                }
            },
            paired = { true },
        )
        assertNotNull(repo.fetchProof("a1"))
        assertNotNull(repo.fetchProof("a1"))
        assertEquals(1, proofHits) // second call served from cache
        assertEquals("a1", repo.proofSnapshot("a1")?.auditId)
    }

    @Test
    fun `gateway error is honest, never fake data`() = runTest {
        val repo = AuditRepository(
            seed = EmptyAuditSeed,
            client = client { CockpitRawResponse(500, "boom") },
            paired = { true },
        )
        repo.refresh()
        assertTrue(repo.sync.value is AuditSync.Error)
        assertTrue(repo.records.value.isEmpty())
    }
}
