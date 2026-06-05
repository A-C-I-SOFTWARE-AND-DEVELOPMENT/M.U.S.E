package com.aci.hermes.data.cockpit

import com.aci.hermes.data.preferences.SecureTokenStore
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Request/response mapping for the device-pairing handshake. Drives the real
 * [DevicePairingClient] over an injected [CockpitHttpExecutor] so the wire
 * contract — request building, the typed error envelope, and token
 * persistence — is exercised without a socket, on the plain JVM.
 */
class DevicePairingClientTest {

    private val seen = mutableListOf<Triple<String, String, String?>>() // method, path-suffix, body

    /** In-memory stand-in for the encrypted store; mirrors its semantics
     *  (matches FakeSecureTokenStore in SecureTokenMigrationTest). */
    private class FakeSecureTokenStore(private var value: String? = null) : SecureTokenStore {
        override fun read(): String? = value?.takeIf { it.isNotBlank() }
        override fun write(token: String) { value = token.trim() }
        override fun clear() { value = null }
    }

    private fun client(
        store: SecureTokenStore = FakeSecureTokenStore(),
        endpoint: String = "http://127.0.0.1:8765",
        exec: (CockpitRequest) -> CockpitRawResponse,
    ) = DevicePairingClient(
        endpointProvider = { endpoint },
        tokenStore = store,
        executor = CockpitHttpExecutor { req ->
            seen += Triple(req.method, req.url.substringAfter("/v1/cockpit"), req.body)
            exec(req)
        },
        ioDispatcher = Dispatchers.Unconfined,
    )

    @Test
    fun `startPairing posts to pair start and decodes the code`() = runTest {
        val res = client {
            CockpitRawResponse(201, """{"pairing_code":"ABCD2345","expires_at":1717000000.0,"expires_in":300}""")
        }.startPairing("Pixel 8")

        assertTrue(res is CockpitResult.Success)
        val start = (res as CockpitResult.Success).value
        assertEquals("ABCD2345", start.pairingCode)
        assertEquals(300, start.expiresIn)
        assertEquals(1717000000.0, start.expiresAt, 0.0)
        assertTrue(seen.any { it.first == "POST" && it.second == "/pair/start" })
        // The optional device name is carried in the body.
        assertTrue(seen.first { it.second == "/pair/start" }.third!!.contains("Pixel 8"))
    }

    @Test
    fun `startPairing maps a 429 refusal to a typed Failure`() = runTest {
        val res = client {
            CockpitRawResponse(429, """{"error":"pairing temporarily unavailable"}""")
        }.startPairing()

        assertTrue(res is CockpitResult.Failure)
        assertEquals(429, (res as CockpitResult.Failure).httpStatus)
    }

    @Test
    fun `confirmPairing happy path decodes the token, carries the owner phrase, and persists`() = runTest {
        val store = FakeSecureTokenStore()
        val res = client(store) { req ->
            // The confirm body must carry the exact owner authorization phrase.
            assertTrue(req.body!!.contains("Yes, with authorization."))
            CockpitRawResponse(201, """{"device_id":"dev_abc","token":"tok-secret-xyz","token_type":"Bearer"}""")
        }.confirmPairing("ABCD2345", authorization = "Yes, with authorization.")

        assertTrue(res is CockpitResult.Success)
        val confirm = (res as CockpitResult.Success).value
        assertEquals("dev_abc", confirm.deviceId)
        assertEquals("Bearer", confirm.tokenType)
        assertTrue(seen.any { it.first == "POST" && it.second == "/pair/confirm" })
        // Token persisted on success — the gateway returns it exactly once.
        assertEquals("tok-secret-xyz", store.read())
    }

    @Test
    fun `confirmPairing maps a 403 to Failure and does NOT persist a token`() = runTest {
        val store = FakeSecureTokenStore()
        val res = client(store) {
            CockpitRawResponse(403, """{"error":{"code":"forbidden","message":"owner authorization required"}}""")
        }.confirmPairing("ABCD2345", authorization = "wrong phrase")

        assertTrue(res is CockpitResult.Failure)
        assertEquals(403, (res as CockpitResult.Failure).httpStatus)
        assertEquals("forbidden", res.error.code)
        assertNull("no token may be stored on a refused confirm", store.read())
    }

    @Test
    fun `confirmPairing maps a 401 bad-or-expired code to Failure without persisting`() = runTest {
        val store = FakeSecureTokenStore()
        val res = client(store) {
            CockpitRawResponse(401, """{"error":"invalid or expired pairing code"}""")
        }.confirmPairing("BADCODE0")

        assertTrue(res is CockpitResult.Failure)
        assertEquals(401, (res as CockpitResult.Failure).httpStatus)
        assertNull(store.read())
    }

    @Test
    fun `a transport failure surfaces as Unreachable and stores nothing`() = runTest {
        val store = FakeSecureTokenStore()
        val res = client(store) { throw java.io.IOException("connection refused") }
            .confirmPairing("ABCD2345", authorization = "Yes, with authorization.")

        assertTrue(res is CockpitResult.Unreachable)
        assertNull(store.read())
    }

    @Test
    fun `a blank endpoint is Unreachable before any wire call`() = runTest {
        val res = client(endpoint = "  ") { error("must not hit the wire") }.startPairing()
        assertTrue(res is CockpitResult.Unreachable)
        assertTrue(seen.isEmpty())
    }

    @Test
    fun `the owner authorization phrase is the exact server gate`() {
        assertEquals("Yes, with authorization.", DevicePairingClient.OWNER_AUTHORIZATION_PHRASE)
    }
}
