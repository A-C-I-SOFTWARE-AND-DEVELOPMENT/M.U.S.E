package com.aci.hermes.ui.screens.pairing

import androidx.datastore.preferences.core.PreferenceDataStoreFactory
import androidx.test.core.app.ApplicationProvider
import com.aci.hermes.data.cockpit.CockpitHttpExecutor
import com.aci.hermes.data.cockpit.CockpitRawResponse
import com.aci.hermes.data.cockpit.CockpitRequest
import com.aci.hermes.data.cockpit.DevicePairingClient
import com.aci.hermes.data.preferences.SecureTokenStore
import com.aci.hermes.data.preferences.SettingsRepository
import com.aci.hermes.testutil.MainDispatcherRule
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import java.io.File
import java.nio.file.Files
import java.util.concurrent.atomic.AtomicInteger

/**
 * State-machine behaviour for the pairing screen. Drives the real
 * [DevicePairingViewModel] over a real [DevicePairingClient] backed by an
 * injected executor + a real [SettingsRepository], so the start→confirm→persist
 * path and the error mapping are exercised on the JVM (no socket).
 *
 * The confirmed token is asserted on [SettingsRepository.cockpitToken] — the
 * in-memory source the live cockpit client reads its bearer from — so the test
 * guards the actual bug: the UI must not reach [DevicePairingState.Paired] while
 * the live client's cached token stays null. The repository's secure store is an
 * in-memory fake (no Keystore); its DataStore is a fresh isolated file.
 */
@OptIn(ExperimentalCoroutinesApi::class)
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [33])
class DevicePairingViewModelTest {

    @get:Rule
    val mainDispatcherRule = MainDispatcherRule()

    /** In-memory stand-in for the encrypted store (mirrors its semantics). */
    private class FakeSecureTokenStore(private var value: String? = null) : SecureTokenStore {
        override fun read(): String? = value?.takeIf { it.isNotBlank() }
        override fun write(token: String) { value = token.trim() }
        override fun clear() { value = null }
    }

    /** Real repository over an isolated DataStore + in-memory secure store. */
    private fun settings(secure: SecureTokenStore = FakeSecureTokenStore()): SettingsRepository {
        val ctx = ApplicationProvider.getApplicationContext<android.content.Context>()
        val dir = Files.createTempDirectory("hermes-pairing-vm-test").toFile().also { it.deleteOnExit() }
        val store = PreferenceDataStoreFactory.create { File(dir, "settings.preferences_pb") }
        return SettingsRepository(ctx, store, secure)
    }

    private fun vm(
        settings: SettingsRepository = settings(),
        ioDispatcher: CoroutineDispatcher = Dispatchers.Unconfined,
        exec: (CockpitRequest) -> CockpitRawResponse,
    ): DevicePairingViewModel {
        val client = DevicePairingClient(
            endpointProvider = { "http://127.0.0.1:8765" },
            settingsRepository = settings,
            executor = CockpitHttpExecutor { exec(it) },
            ioDispatcher = ioDispatcher,
        )
        return DevicePairingViewModel(client)
    }

    @Test
    fun `starts Idle`() = runTest {
        val vm = vm { error("no call expected") }
        assertEquals(DevicePairingState.Idle, vm.state.value)
    }

    @Test
    fun `startPairing moves to CodeRequested with the code`() = runTest {
        val vm = vm {
            CockpitRawResponse(201, """{"pairing_code":"ABCD2345","expires_at":1717000000.0,"expires_in":300}""")
        }
        vm.startPairing("Pixel 8")
        advanceUntilIdle()
        val s = vm.state.value
        assertTrue(s is DevicePairingState.CodeRequested)
        assertEquals("ABCD2345", (s as DevicePairingState.CodeRequested).start.pairingCode)
        assertEquals(300, s.start.expiresIn)
    }

    @Test
    fun `confirm happy path moves to Paired and persists the token to the live source`() = runTest {
        val settings = settings()
        val vm = vm(settings) { req ->
            if (req.url.endsWith("/pair/start")) {
                CockpitRawResponse(201, """{"pairing_code":"ABCD2345","expires_at":0,"expires_in":300}""")
            } else {
                CockpitRawResponse(201, """{"device_id":"dev_abc","token":"tok-xyz","token_type":"Bearer"}""")
            }
        }
        vm.startPairing()
        advanceUntilIdle()
        vm.confirmPairing("ABCD2345", authorization = "Yes, with authorization.")
        advanceUntilIdle()

        val s = vm.state.value
        assertTrue(s is DevicePairingState.Paired)
        assertEquals("dev_abc", (s as DevicePairingState.Paired).confirm.deviceId)
        // Reaching Paired must mean the live client's bearer source is set, not
        // just secure storage — otherwise authenticated calls fail "Not paired".
        assertEquals("tok-xyz", settings.cockpitToken.value)
    }

    @Test
    fun `confirm with the wrong owner phrase is a non-retryable Error and stores nothing`() = runTest {
        val settings = settings()
        val vm = vm(settings) {
            CockpitRawResponse(403, """{"error":"owner authorization required"}""")
        }
        vm.confirmPairing("ABCD2345", authorization = "nope")
        advanceUntilIdle()

        val s = vm.state.value
        assertTrue(s is DevicePairingState.Error)
        assertTrue((s as DevicePairingState.Error).message.contains("authorization", ignoreCase = true))
        assertEquals(false, s.retryable)
        assertNull(settings.cockpitToken.value)
    }

    @Test
    fun `confirm with an expired code is a retryable Error`() = runTest {
        val vm = vm {
            CockpitRawResponse(401, """{"error":"invalid or expired pairing code"}""")
        }
        vm.confirmPairing("BADCODE0")
        advanceUntilIdle()

        val s = vm.state.value
        assertTrue(s is DevicePairingState.Error)
        assertEquals(true, (s as DevicePairingState.Error).retryable)
    }

    @Test
    fun `a re-entrant confirm while one is in flight is ignored - one request, ends Paired`() = runTest {
        // Bind the client's IO to the test scheduler so the first confirm
        // suspends in flight (isSubmitting stays true) until advanceUntilIdle().
        val calls = AtomicInteger(0)
        val settings = settings()
        val vm = vm(settings, ioDispatcher = StandardTestDispatcher(testScheduler)) {
            calls.incrementAndGet()
            CockpitRawResponse(201, """{"device_id":"dev_abc","token":"tok-xyz","token_type":"Bearer"}""")
        }
        // Double-tap before the first network call returns.
        vm.confirmPairing("ABCD2345", authorization = "Yes, with authorization.")
        assertTrue("first confirm should mark the VM as submitting", vm.isSubmitting.value)
        vm.confirmPairing("ABCD2345", authorization = "Yes, with authorization.")
        advanceUntilIdle()

        assertEquals("the second tap must be ignored while one is in flight", 1, calls.get())
        assertTrue(vm.state.value is DevicePairingState.Paired)
        assertTrue("submitting clears once the result arrives", !vm.isSubmitting.value)
    }

    @Test
    fun `a late failed confirm after success does not overwrite Paired`() = runTest {
        // Model the race outcome directly: succeed first (gateway consumes the
        // code + persists the token), then a duplicate request 401s after the
        // success. The terminal Paired state must survive the late failure.
        val settings = settings()
        var confirmCalls = 0
        val vm = vm(settings) { req ->
            if (req.url.endsWith("/pair/confirm")) {
                confirmCalls++
                if (confirmCalls == 1) {
                    CockpitRawResponse(201, """{"device_id":"dev_abc","token":"tok-xyz","token_type":"Bearer"}""")
                } else {
                    CockpitRawResponse(401, """{"error":"invalid or expired pairing code"}""")
                }
            } else {
                error("only confirm expected")
            }
        }
        vm.confirmPairing("ABCD2345", authorization = "Yes, with authorization.")
        advanceUntilIdle()
        assertTrue(vm.state.value is DevicePairingState.Paired)

        // The late duplicate (e.g. a retried tap whose response lost the race)
        // resolves to a 401 — it must NOT demote the already-persisted pairing.
        vm.confirmPairing("ABCD2345", authorization = "Yes, with authorization.")
        advanceUntilIdle()

        assertTrue("a late failure must not overwrite Paired", vm.state.value is DevicePairingState.Paired)
        assertEquals("dev_abc", (vm.state.value as DevicePairingState.Paired).confirm.deviceId)
        // The token persisted on the first success is still the live bearer.
        assertEquals("tok-xyz", settings.cockpitToken.value)
    }

    @Test
    fun `an unreachable gateway surfaces as Error`() = runTest {
        val vm = vm { throw java.io.IOException("connection refused") }
        vm.startPairing()
        advanceUntilIdle()
        assertTrue(vm.state.value is DevicePairingState.Error)
    }

    @Test
    fun `reset returns to Idle`() = runTest {
        val vm = vm {
            CockpitRawResponse(201, """{"pairing_code":"ABCD2345","expires_at":0,"expires_in":300}""")
        }
        vm.startPairing()
        advanceUntilIdle()
        assertTrue(vm.state.value is DevicePairingState.CodeRequested)
        vm.reset()
        assertEquals(DevicePairingState.Idle, vm.state.value)
    }

    @Test
    fun `confirm defaults to the exact owner authorization phrase`() = runTest {
        var body: String? = null
        val vm = vm { req ->
            body = req.body
            CockpitRawResponse(201, """{"device_id":"dev_abc","token":"tok-xyz","token_type":"Bearer"}""")
        }
        vm.confirmPairing("ABCD2345") // no explicit phrase → uses the default
        advanceUntilIdle()
        assertTrue(body!!.contains("Yes, with authorization."))
    }
}
