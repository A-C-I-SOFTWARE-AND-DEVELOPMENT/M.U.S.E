package com.aci.hermes.data.cockpit

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test

/**
 * Drives [HermesCockpitClient] through a fake [CockpitHttpExecutor] so
 * request-building (bearer, URL, method) and every [CockpitResult]
 * branch are covered without a real socket.
 */
class HermesCockpitClientTest {

    /** Records the last request and returns a scripted response (or throws). */
    private class FakeExecutor(
        private val responder: (CockpitRequest) -> CockpitRawResponse,
    ) : CockpitHttpExecutor {
        var lastRequest: CockpitRequest? = null
        override fun execute(request: CockpitRequest): CockpitRawResponse {
            lastRequest = request
            return responder(request)
        }
    }

    private fun client(
        executor: CockpitHttpExecutor,
        endpoint: String = "http://127.0.0.1:8765",
        token: String? = "tok",
    ) = HermesCockpitClient(
        endpointProvider = { endpoint },
        tokenProvider = { token },
        executor = executor,
        ioDispatcher = Dispatchers.Unconfined,
    )

    @Test
    fun `runtimeStatus parses a 200 body and attaches bearer`() = runTest {
        val fake = FakeExecutor {
            CockpitRawResponse(
                200,
                """
                {"gateway":{"version":"0.1.0","started_at":"t","pid":7,"mode":"local"},
                 "host":{"platform":"Linux","arch":"x86_64","hostname":"h"},
                 "queue":{"running":2,"queued":1,"waiting_approval":0}}
                """.trimIndent(),
            )
        }
        val result = client(fake).runtimeStatus()
        if (result !is CockpitResult.Success) {
            fail("expected Success, got $result"); return@runTest
        }
        assertEquals(2, result.value.queue.running)
        assertEquals("Linux", result.value.host.platform)
        // request shape
        assertEquals("GET", fake.lastRequest?.method)
        assertEquals("http://127.0.0.1:8765/v1/cockpit/runtime/status", fake.lastRequest?.url)
        assertEquals("Bearer tok", fake.lastRequest?.headers?.get("Authorization"))
    }

    @Test
    fun `runtimeWorkers parses the worker list`() = runTest {
        val fake = FakeExecutor {
            CockpitRawResponse(
                200,
                """{"workers":[{"id":"claude_code","display_name":"Claude Code","kind":"external_cli","available":false,"notes":"Not installed."}]}""",
            )
        }
        val result = client(fake).runtimeWorkers()
        if (result !is CockpitResult.Success) {
            fail("expected Success, got $result"); return@runTest
        }
        val workers = result.value.workers
        assertEquals(1, workers.size)
        assertEquals("claude_code", workers[0].id)
        assertFalse(workers[0].available)
        assertNull(workers[0].version)
    }

    @Test
    fun `health is unauthenticated and works without a token`() = runTest {
        val fake = FakeExecutor {
            CockpitRawResponse(200, """{"ok":true,"service":"hermes-cockpit","gateway_version":"0.14.0"}""")
        }
        val result = client(fake, token = null).health()
        if (result !is CockpitResult.Success) {
            fail("expected Success, got $result"); return@runTest
        }
        assertEquals("0.14.0", result.value.resolvedVersion)
        // No Authorization header on the health probe.
        assertNull(fake.lastRequest?.headers?.get("Authorization"))
        // Short probe timeout (contract §12).
        assertEquals(CockpitHttp.HEALTH_TIMEOUT_MS, fake.lastRequest?.readTimeoutMs)
    }

    @Test
    fun `a non-2xx becomes a typed Failure with the envelope code`() = runTest {
        val fake = FakeExecutor {
            CockpitRawResponse(401, """{"error":{"code":"unauthorized","message":"missing token"}}""")
        }
        val result = client(fake).runtimeStatus()
        if (result !is CockpitResult.Failure) {
            fail("expected Failure, got $result"); return@runTest
        }
        assertEquals(401, result.httpStatus)
        assertEquals("unauthorized", result.error.code)
    }

    @Test
    fun `an authenticated route without a token short-circuits to Unreachable`() = runTest {
        val fake = FakeExecutor { error("should not be called") }
        val result = client(fake, token = null).runtimeStatus()
        assertTrue(result is CockpitResult.Unreachable)
        assertNull(fake.lastRequest) // never hit the wire
    }

    @Test
    fun `a transport throwable becomes Unreachable`() = runTest {
        val fake = FakeExecutor { throw java.net.ConnectException("Connection refused") }
        val result = client(fake).runtimeStatus()
        if (result !is CockpitResult.Unreachable) {
            fail("expected Unreachable, got $result"); return@runTest
        }
        assertTrue(result.message.contains("refused", ignoreCase = true))
    }

    @Test
    fun `a malformed 2xx body becomes Unreachable, never a crash`() = runTest {
        val fake = FakeExecutor { CockpitRawResponse(200, "not json at all") }
        val result = client(fake).runtimeStatus()
        assertTrue(result is CockpitResult.Unreachable)
    }

    @Test
    fun `isPaired reflects token and endpoint presence`() {
        val fake = FakeExecutor { CockpitRawResponse(200, "{}") }
        assertTrue(client(fake, token = "t").isPaired())
        assertFalse(client(fake, token = null).isPaired())
        assertFalse(client(fake, endpoint = "", token = "t").isPaired())
    }

    @Test
    fun `getRaw returns the raw object for not-yet-typed routes`() = runTest {
        val fake = FakeExecutor { CockpitRawResponse(200, """{"approvals":[]}""") }
        val result = client(fake).getRaw("/v1/cockpit/approvals")
        if (result !is CockpitResult.Success) {
            fail("expected Success, got $result"); return@runTest
        }
        assertTrue(result.value.containsKey("approvals"))
    }

    // ─── New cockpit endpoints ───────────────────────────────────────────

    @Test
    fun `capabilities parses subsystems and execute guard`() = runTest {
        val fake = FakeExecutor {
            CockpitRawResponse(
                200,
                """{"api_version":"1.0.0","gateway_version":"0.14.0",
                    "subsystems":{"memory":true,"coding":true},
                    "available_workers":[{"id":"claude-execute","requires_approval":true}],
                    "detected_clis":["claude_code_builder"],
                    "execute_allowed":true,"owner_gate_required":true}""",
            )
        }
        val result = client(fake).capabilities()
        if (result !is CockpitResult.Success) {
            fail("expected Success, got $result"); return@runTest
        }
        assertEquals("http://127.0.0.1:8765/v1/cockpit/capabilities", fake.lastRequest?.url)
        assertTrue(result.value.subsystems["coding"] == true)
        assertTrue(result.value.executeAllowed)
        assertEquals("claude-execute", result.value.availableWorkers.first().id)
        assertTrue(result.value.availableWorkers.first().requiresApproval)
    }

    @Test
    fun `jobPause and jobResume post to the right routes`() = runTest {
        val fake = FakeExecutor {
            CockpitRawResponse(
                200,
                """{"id":"j1","title":"t","worker_id":"w","status":"PAUSED",
                    "created_at":"a","updated_at":"b"}""",
            )
        }
        val paused = client(fake).jobPause("j1", "hold")
        assertTrue(paused is CockpitResult.Success)
        assertEquals("POST", fake.lastRequest?.method)
        assertEquals("http://127.0.0.1:8765/v1/cockpit/jobs/j1/pause", fake.lastRequest?.url)

        client(fake).jobResume("j1")
        assertEquals("http://127.0.0.1:8765/v1/cockpit/jobs/j1/resume", fake.lastRequest?.url)
    }

    @Test
    fun `emergencyStop parses the halt counts`() = runTest {
        val fake = FakeExecutor {
            CockpitRawResponse(
                200,
                """{"reason":"panic","tick_disabled":true,"branch_leases_cleared":2,
                    "jobs_paused":1,"jobs_paused_ids":["j1"]}""",
            )
        }
        val result = client(fake).emergencyStop("panic")
        if (result !is CockpitResult.Success) {
            fail("expected Success, got $result"); return@runTest
        }
        assertEquals("http://127.0.0.1:8765/v1/cockpit/emergency-stop", fake.lastRequest?.url)
        assertTrue(result.value.tickDisabled)
        assertEquals(1, result.value.jobsPaused)
        assertEquals("j1", result.value.jobsPausedIds.first())
    }

    @Test
    fun `codingAudit and codingPlan hit the coding lanes`() = runTest {
        val auditFake = FakeExecutor {
            CockpitRawResponse(
                200,
                """{"intent":"test","risk_class":"RC1","primary_worker":"claude",
                    "owner_gate_required":false}""",
            )
        }
        val audit = client(auditFake).codingAudit(CodingRequest(prompt = "add a test"))
        if (audit !is CockpitResult.Success) {
            fail("expected Success, got $audit"); return@runTest
        }
        assertEquals("http://127.0.0.1:8765/v1/cockpit/coding/audit", auditFake.lastRequest?.url)
        assertEquals("test", audit.value.intent)

        val planFake = FakeExecutor {
            CockpitRawResponse(
                200,
                """{"packet":{"mission":"m","branch":"jarvis/x","risk_class":"RC2"},
                    "validation":{"ok":true,"findings":[]},"markdown":"# Packet"}""",
            )
        }
        val plan = client(planFake).codingPlan(CodingRequest(prompt = "refactor x"))
        if (plan !is CockpitResult.Success) {
            fail("expected Success, got $plan"); return@runTest
        }
        assertEquals("http://127.0.0.1:8765/v1/cockpit/coding/plan", planFake.lastRequest?.url)
        assertTrue(plan.value.validation.ok)
        assertEquals("jarvis/x", plan.value.packet.branch)
    }

    @Test
    fun `codingExecute parses the staged approval response`() = runTest {
        val fake = FakeExecutor {
            CockpitRawResponse(
                200,
                """{"status":"approval_required","worker_id":"claude-execute",
                    "authorization_required":true,
                    "authorization_hint":"send authorization exactly: 'Yes, with authorization.'",
                    "job":{"id":"orc-1","status":"queued","prompt":"p"},
                    "packet":{"mission":"m","risk_class":"RC3"}}""",
            )
        }
        val result = client(fake).codingExecute(CodingRequest(prompt = "deploy"))
        if (result !is CockpitResult.Success) {
            fail("expected Success, got $result"); return@runTest
        }
        assertEquals("http://127.0.0.1:8765/v1/cockpit/coding/execute", fake.lastRequest?.url)
        assertEquals("approval_required", result.value.status)
        assertTrue(result.value.authorizationRequired)
        assertEquals("orc-1", result.value.job?.id)
    }

    @Test
    fun `evidenceSearch encodes the query and parses artifacts`() = runTest {
        val searchFake = FakeExecutor {
            CockpitRawResponse(
                200,
                """{"items":[{"id":"a","title":"PEP 659","source_uri":"https://x",
                    "evidence_strength":"primary"}]}""",
            )
        }
        val search = client(searchFake).evidenceSearch("adaptive interpreter")
        if (search !is CockpitResult.Success) {
            fail("expected Success, got $search"); return@runTest
        }
        assertTrue(searchFake.lastRequest?.url?.contains("/v1/cockpit/evidence/search?q=") == true)
        assertEquals("PEP 659", search.value.items.first().title)
    }

    @Test
    fun `autonomyGet parses level scope and capabilities`() = runTest {
        val fake = FakeExecutor {
            CockpitRawResponse(
                200,
                """
                {"level":"owner_high_autonomy_coding","display_name":"High-Autonomy Coding",
                 "workspace_root":"/home/me/project","updated_at":1.0,"set_by":"cockpit",
                 "revocable":true,
                 "capabilities":{"auto_approved":["local_command","safe_local_write"],
                   "requires_approval":["vercel_deploy"],"always_deny":["github_force_push"],
                   "workspace_scoped":["safe_local_write","code_worker_exec"]}}
                """.trimIndent(),
            )
        }
        val result = client(fake).autonomyGet()
        if (result !is CockpitResult.Success) {
            fail("expected Success, got $result"); return@runTest
        }
        assertEquals("owner_high_autonomy_coding", result.value.level)
        assertEquals("/home/me/project", result.value.workspaceRoot)
        assertTrue(result.value.capabilities.autoApproved.contains("local_command"))
        assertTrue(result.value.capabilities.alwaysDeny.contains("github_force_push"))
        assertEquals("GET", fake.lastRequest?.method)
        assertEquals("http://127.0.0.1:8765/v1/cockpit/autonomy", fake.lastRequest?.url)
    }

    @Test
    fun `autonomySet sends level and workspace in the body`() = runTest {
        val fake = FakeExecutor {
            CockpitRawResponse(200, """{"level":"owner_high_autonomy_coding","workspace_root":"/w"}""")
        }
        val result = client(fake).autonomySet("owner_high_autonomy_coding", workspacePath = "/w")
        assertTrue(result is CockpitResult.Success)
        assertEquals("POST", fake.lastRequest?.method)
        val body = fake.lastRequest?.body ?: ""
        assertTrue(body.contains("owner_high_autonomy_coding"))
        assertTrue(body.contains("/w"))
    }

    @Test
    fun `autonomyRevoke sends revoke true`() = runTest {
        val fake = FakeExecutor { CockpitRawResponse(200, """{"level":"assisted"}""") }
        client(fake).autonomyRevoke()
        assertTrue((fake.lastRequest?.body ?: "").contains("revoke"))
    }

}
