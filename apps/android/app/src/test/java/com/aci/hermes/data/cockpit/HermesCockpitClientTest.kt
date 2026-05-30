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
}
