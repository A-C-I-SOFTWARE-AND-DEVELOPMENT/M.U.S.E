package com.aci.hermes.gateway

import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class MockJarvisGatewayClientTest {

    @Test fun starts_offline_with_seed_workers() = runTest {
        val client = MockJarvisGatewayClient()
        val state = client.state.value
        assertEquals(GatewayState.Connectivity.OFFLINE, state.connectivity)
        assertTrue("seed workers present", state.workers.isNotEmpty())
    }

    @Test fun configure_with_enabled_url_brings_online() = runTest {
        val client = MockJarvisGatewayClient()
        client.configure(GatewayConfig(baseUrl = "http://localhost:7373", enabled = true))
        assertEquals(GatewayState.Connectivity.ONLINE, client.state.value.connectivity)
    }

    @Test fun configure_with_disabled_flag_stays_offline() = runTest {
        val client = MockJarvisGatewayClient()
        client.configure(GatewayConfig(baseUrl = "http://localhost:7373", enabled = false))
        assertEquals(GatewayState.Connectivity.OFFLINE, client.state.value.connectivity)
    }

    @Test fun shutdown_returns_to_offline() = runTest {
        val client = MockJarvisGatewayClient()
        client.configure(GatewayConfig(baseUrl = "http://localhost:7373", enabled = true))
        client.shutdown()
        assertEquals(GatewayState.Connectivity.OFFLINE, client.state.value.connectivity)
    }
}
