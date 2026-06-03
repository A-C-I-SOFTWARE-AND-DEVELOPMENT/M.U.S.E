package com.aci.hermes.data.cockpit

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class BackendReachabilityTest {

    private val ok: CockpitResult<Unit> = CockpitResult.Success(Unit)
    private val unreachable = CockpitResult.Unreachable("connection refused")
    private val failure = CockpitResult.Failure(CockpitError("backend_error", "boom"), 500)

    @Test
    fun `no endpoint is unpaired regardless of probe result`() {
        assertEquals(BackendStatus.UNPAIRED, BackendStatus.from(endpointConfigured = false, result = ok))
        assertEquals(BackendStatus.UNPAIRED, BackendStatus.from(endpointConfigured = false, result = unreachable))
        assertEquals(BackendStatus.UNPAIRED, BackendStatus.from(endpointConfigured = false, result = failure))
    }

    @Test
    fun `success maps to connected`() {
        assertEquals(BackendStatus.CONNECTED, BackendStatus.from(endpointConfigured = true, result = ok))
    }

    @Test
    fun `unreachable maps to disconnected`() {
        assertEquals(BackendStatus.DISCONNECTED, BackendStatus.from(endpointConfigured = true, result = unreachable))
    }

    @Test
    fun `non-2xx gateway answer maps to error`() {
        assertEquals(BackendStatus.ERROR, BackendStatus.from(endpointConfigured = true, result = failure))
    }

    @Test
    fun `connected is the only reachable state`() {
        assertTrue(BackendStatus.CONNECTED.isReachable)
        BackendStatus.entries.filter { it != BackendStatus.CONNECTED }
            .forEach { assertFalse(it.name, it.isReachable) }
    }

    @Test
    fun `only disconnected and error show the offline banner`() {
        assertTrue(BackendStatus.DISCONNECTED.isOffline)
        assertTrue(BackendStatus.ERROR.isOffline)
        assertFalse(BackendStatus.CHECKING.isOffline)
        assertFalse(BackendStatus.CONNECTED.isOffline)
        assertFalse(BackendStatus.UNPAIRED.isOffline)
    }
}
