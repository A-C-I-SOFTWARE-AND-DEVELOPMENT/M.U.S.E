package com.aci.hermes.data.ledger

import com.aci.hermes.data.cockpit.CockpitHttpExecutor
import com.aci.hermes.data.cockpit.CockpitRawResponse
import com.aci.hermes.data.cockpit.CockpitRequest
import com.aci.hermes.data.cockpit.HermesCockpitClient
import com.aci.hermes.data.model.ledger.LedgerFilters
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Drives [LedgerRepository] through a fake executor: verifies live timeline
 * load, filter→query translation, and — critically — that on-device
 * [com.aci.hermes.data.audit.SecretRedactor] scrubs anything that slipped
 * through (defense in depth).
 */
class LedgerRepositoryTest {

    private class FakeExecutor(
        private val responder: (CockpitRequest) -> CockpitRawResponse,
    ) : CockpitHttpExecutor {
        var lastRequest: CockpitRequest? = null
        override fun execute(request: CockpitRequest): CockpitRawResponse {
            lastRequest = request
            return responder(request)
        }
    }

    private fun repo(executor: CockpitHttpExecutor): LedgerRepository {
        val client = HermesCockpitClient(
            endpointProvider = { "http://127.0.0.1:8765" },
            tokenProvider = { "tok" },
            executor = executor,
            ioDispatcher = Dispatchers.Unconfined,
        )
        return LedgerRepository(client = client, paired = { true })
    }

    @Test
    fun `refresh loads events and re-redacts a leaked secret on device`() = runTest {
        // Server response that (hypothetically) failed to redact a token.
        val leaked = "sk-live-abcdef0123456789abcdef0123"
        val fake = FakeExecutor {
            CockpitRawResponse(
                200,
                """{"events":[
                   {"id":"job1:0","job_id":"job1","index":0,"timestamp":"2026-06-01T09:00:00+00:00",
                    "category":"WORKER_RUN","kind":"worker_result","worker":"codex-execute",
                    "risk_tier":"MODERATE","summary":"output token=$leaked","files":[]}
                 ]}""".trimIndent(),
            )
        }
        val r = repo(fake)
        r.refresh()
        val events = r.events.value
        assertEquals(1, events.size)
        assertFalse("secret must not survive on-device redaction", events[0].summary.contains(leaked))
        assertTrue(events[0].summary.contains("[REDACTED]"))
        assertTrue(r.sync.value is LedgerSync.Loaded)
    }

    @Test
    fun `applyFilters forwards non-blank filters as query params`() = runTest {
        val fake = FakeExecutor { CockpitRawResponse(200, """{"events":[]}""") }
        val r = repo(fake)
        r.applyFilters(LedgerFilters(job = "job_beta", risk = "SERIOUS", file = "app.py"))
        val url = fake.lastRequest?.url.orEmpty()
        assertTrue(url, url.contains("job=job_beta"))
        assertTrue(url, url.contains("risk=SERIOUS"))
        assertTrue(url, url.contains("file=app.py"))
    }

    @Test
    fun `unpaired repository shows nothing and reports NotPaired`() = runTest {
        val fake = FakeExecutor { CockpitRawResponse(200, """{"events":[]}""") }
        val client = HermesCockpitClient(
            endpointProvider = { "http://127.0.0.1:8765" },
            tokenProvider = { "tok" },
            executor = fake,
            ioDispatcher = Dispatchers.Unconfined,
        )
        val r = LedgerRepository(client = client, paired = { false })
        r.refresh()
        assertTrue(r.events.value.isEmpty())
        assertTrue(r.sync.value is LedgerSync.NotPaired)
    }

    @Test
    fun `rollback request returns the approval card id`() = runTest {
        val fake = FakeExecutor {
            CockpitRawResponse(201, """{"id":"abc123","title":"Self-update","status":"PENDING"}""")
        }
        val r = repo(fake)
        val id = r.requestRollback("job1", 0, "premature publish")
        assertNotNull(id)
        assertEquals("abc123", id)
        assertEquals("POST", fake.lastRequest?.method)
        assertTrue(fake.lastRequest?.url.orEmpty().endsWith("/v1/cockpit/ledger/job1/0/rollback"))
    }
}
