package com.aci.hermes.ui.screens.releasecenter

import com.aci.hermes.data.cockpit.CockpitHttpExecutor
import com.aci.hermes.data.cockpit.CockpitRawResponse
import com.aci.hermes.data.cockpit.CockpitRequest
import com.aci.hermes.data.cockpit.HermesCockpitClient
import com.aci.hermes.testutil.MainDispatcherRule
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

@OptIn(ExperimentalCoroutinesApi::class)
class ReleaseCenterViewModelTest {

    @get:Rule
    val mainDispatcherRule = MainDispatcherRule(StandardTestDispatcher())

    private fun vm(
        token: String? = "tok",
        exec: (CockpitRequest) -> CockpitRawResponse,
    ): ReleaseCenterViewModel {
        val client = HermesCockpitClient(
            endpointProvider = { "http://127.0.0.1:8765" },
            tokenProvider = { token },
            executor = CockpitHttpExecutor { exec(it) },
            ioDispatcher = Dispatchers.Unconfined,
        )
        return mainDispatcherRule.register(ReleaseCenterViewModel(client, appVersion = "0.1.0", buildType = "debug", applicationId = "com.aci.hermes.debug"))
    }

    @Test
    fun `build facts come from the constructor, not the network`() {
        val m = vm(token = null) { error("must not hit the wire") }
        assertEquals("0.1.0", m.appVersion)
        assertEquals("debug", m.buildType)
        // The four signing secret names are surfaced by name only.
        assertTrue(m.signingSecretNames.contains("ANDROID_KEYSTORE_BASE64"))
        assertEquals(4, m.signingSecretNames.size)
        assertTrue(m.downloadUrl.endsWith("jarvis-prime-android.apk"))
    }

    @Test
    fun `capabilities load when paired`() = runTest {
        val m = vm { CockpitRawResponse(200, """{"api_version":"1","gateway_version":"1.2.3","execute_allowed":false,"owner_gate_required":true}""") }
        advanceUntilIdle()
        assertEquals("1.2.3", m.state.value.capabilities?.gatewayVersion)
        assertNull(m.state.value.backendUnavailable)
    }

    @Test
    fun `unpaired backend degrades to an honest hint, no fabricated capabilities`() = runTest {
        val m = vm(token = null) { error("must not hit the wire") }
        advanceUntilIdle()
        assertNull(m.state.value.capabilities)
        assertTrue(m.state.value.backendUnavailable != null)
    }
}
