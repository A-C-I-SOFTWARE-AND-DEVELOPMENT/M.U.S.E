package com.aci.hermes.ui.screens.pairing

import com.aci.hermes.data.cockpit.CockpitHttpExecutor
import com.aci.hermes.data.cockpit.CockpitRawResponse
import com.aci.hermes.data.cockpit.CockpitRequest
import com.aci.hermes.data.cockpit.DevicePairingClient
import com.aci.hermes.data.preferences.SecureTokenStore
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/**
 * State-machine behaviour for the pairing screen. Drives the real
 * [DevicePairingViewModel] over a real [DevicePairingClient] backed by an
 * injected executor + in-memory token store, so the start→confirm→persist path
 * and the error mapping are exercised on the JVM (no emulator, no socket) —
 * the same shape as ModelRouteViewModelTest.
 */
@OptIn(ExperimentalCoroutinesApi::class)
class DevicePairingViewModelTest {

    private val testDispatcher = StandardTestDispatcher()

    @Before fun setUp() = Dispatchers.setMain(testDispatcher)
    @After fun tearDown() = Dispatchers.resetMain()

    /** In-memory stand-in for the encrypted store (mirrors its semantics). */
    private class FakeSecureTokenStore(private var value: String? = null) : SecureTokenStore {
        override fun read(): String? = value?.takeIf { it.isNotBlank() }
        override fun write(token: String) { value = token.trim() }
        override fun clear() { value = null }
    }

    private fun vm(
        store: SecureTokenStore = FakeSecureTokenStore(),
        exec: (CockpitRequest) -> CockpitRawResponse,
    ): DevicePairingViewModel {
        val client = DevicePairingClient(
            endpointProvider = { "http://127.0.0.1:8765" },
            tokenStore = store,
            executor = CockpitHttpExecutor { exec(it) },
            ioDispatcher = Dispatchers.Unconfined,
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
    fun `confirm happy path moves to Paired and persists the token`() = runTest {
        val store = FakeSecureTokenStore()
        val vm = vm(store) { req ->
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
        assertEquals("tok-xyz", store.read())
    }

    @Test
    fun `confirm with the wrong owner phrase is a non-retryable Error and stores nothing`() = runTest {
        val store = FakeSecureTokenStore()
        val vm = vm(store) {
            CockpitRawResponse(403, """{"error":"owner authorization required"}""")
        }
        vm.confirmPairing("ABCD2345", authorization = "nope")
        advanceUntilIdle()

        val s = vm.state.value
        assertTrue(s is DevicePairingState.Error)
        assertTrue((s as DevicePairingState.Error).message.contains("authorization", ignoreCase = true))
        assertEquals(false, s.retryable)
        assertNull(store.read())
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
