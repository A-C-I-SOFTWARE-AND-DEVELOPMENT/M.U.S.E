package com.aci.hermes.data.cockpit

import androidx.datastore.preferences.core.PreferenceDataStoreFactory
import androidx.test.core.app.ApplicationProvider
import com.aci.hermes.data.preferences.SecureTokenStore
import com.aci.hermes.data.preferences.SettingsRepository
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import java.io.File
import java.nio.file.Files

/**
 * Request/response mapping for the device-pairing handshake. Drives the real
 * [DevicePairingClient] over an injected [CockpitHttpExecutor] so the wire
 * contract — request building, the typed error envelope, and token
 * persistence — is exercised without a socket.
 *
 * Persistence is asserted through the **same source the live client reads**:
 * the [SettingsRepository.cockpitToken] StateFlow (set by `setCockpitToken`),
 * not a bare secure-store write — that is the bug this client is wired against.
 * Robolectric supplies the `Context` the repository needs; its DataStore is a
 * fresh isolated file and its secure store is an in-memory fake (no Keystore),
 * so the test is hermetic and deterministic.
 */
@OptIn(ExperimentalCoroutinesApi::class)
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [33])
class DevicePairingClientTest {

    private val seen = mutableListOf<Triple<String, String, String?>>() // method, path-suffix, body

    /** In-memory stand-in for the encrypted store; mirrors its semantics
     *  (matches FakeSecureTokenStore in SecureTokenMigrationTest). */
    private class FakeSecureTokenStore(private var value: String? = null) : SecureTokenStore {
        override fun read(): String? = value?.takeIf { it.isNotBlank() }
        override fun write(token: String) { value = token.trim() }
        override fun clear() { value = null }
    }

    /**
     * A real [SettingsRepository] over an isolated DataStore + an in-memory
     * secure store, so `setCockpitToken` writes through exactly as in
     * production but without pulling the Android Keystore into the JVM test.
     */
    private fun settings(secure: SecureTokenStore = FakeSecureTokenStore()): SettingsRepository {
        val ctx = ApplicationProvider.getApplicationContext<android.content.Context>()
        val dir = Files.createTempDirectory("hermes-pairing-test").toFile().also { it.deleteOnExit() }
        val store = PreferenceDataStoreFactory.create { File(dir, "settings.preferences_pb") }
        return SettingsRepository(ctx, store, secure)
    }

    private fun client(
        settings: SettingsRepository = settings(),
        endpoint: String = "http://127.0.0.1:8765",
        exec: (CockpitRequest) -> CockpitRawResponse,
    ) = DevicePairingClient(
        endpointProvider = { endpoint },
        settingsRepository = settings,
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
    fun `confirmPairing happy path decodes the token, carries the owner phrase, and persists via the repository`() = runTest {
        val settings = settings()
        val res = client(settings) { req ->
            // The confirm body must carry the exact owner authorization phrase.
            assertTrue(req.body!!.contains("Yes, with authorization."))
            CockpitRawResponse(201, """{"device_id":"dev_abc","token":"tok-secret-xyz","token_type":"Bearer"}""")
        }.confirmPairing("ABCD2345", authorization = "Yes, with authorization.")

        assertTrue(res is CockpitResult.Success)
        val confirm = (res as CockpitResult.Success).value
        assertEquals("dev_abc", confirm.deviceId)
        assertEquals("Bearer", confirm.tokenType)
        assertTrue(seen.any { it.first == "POST" && it.second == "/pair/confirm" })
        // Persisted through the in-memory source the live client reads from —
        // not just secure storage. This is the regression guard: a bare
        // SecureTokenStore.write would leave cockpitToken null until restart.
        assertEquals("tok-secret-xyz", settings.cockpitToken.value)
    }

    @Test
    fun `confirmPairing maps a 403 to Failure and does NOT persist a token`() = runTest {
        val settings = settings()
        val res = client(settings) {
            CockpitRawResponse(403, """{"error":{"code":"forbidden","message":"owner authorization required"}}""")
        }.confirmPairing("ABCD2345", authorization = "wrong phrase")

        assertTrue(res is CockpitResult.Failure)
        assertEquals(403, (res as CockpitResult.Failure).httpStatus)
        assertEquals("forbidden", res.error.code)
        assertNull("no token may be stored on a refused confirm", settings.cockpitToken.value)
    }

    @Test
    fun `confirmPairing maps a 401 bad-or-expired code to Failure without persisting`() = runTest {
        val settings = settings()
        val res = client(settings) {
            CockpitRawResponse(401, """{"error":"invalid or expired pairing code"}""")
        }.confirmPairing("BADCODE0")

        assertTrue(res is CockpitResult.Failure)
        assertEquals(401, (res as CockpitResult.Failure).httpStatus)
        assertNull(settings.cockpitToken.value)
    }

    @Test
    fun `a transport failure surfaces as Unreachable and stores nothing`() = runTest {
        val settings = settings()
        val res = client(settings) { throw java.io.IOException("connection refused") }
            .confirmPairing("ABCD2345", authorization = "Yes, with authorization.")

        assertTrue(res is CockpitResult.Unreachable)
        assertNull(settings.cockpitToken.value)
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
