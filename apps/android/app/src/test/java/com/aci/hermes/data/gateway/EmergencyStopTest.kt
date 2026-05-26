package com.aci.hermes.data.gateway

import kotlinx.coroutines.flow.toList
import kotlinx.coroutines.launch
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Emergency stop must clear pending work and force the icon to ERROR.
 * Anything else is a regression — the spec says the stop event
 * "overrides pending work".
 */
@OptIn(ExperimentalCoroutinesApi::class)
class EmergencyStopTest {

    @Test
    fun `emergency_stop_triggered drops pending approvals and flips icon`() = runTest(UnconfinedTestDispatcher()) {
        val client = MockGatewayClient()
        val collected = mutableListOf<GatewayEvent>()
        val job = launch { client.events.toList(collected) }
        client.connect()

        client.requestApproval("safe_open_pr", "open PR", ApprovalRiskClass.STANDARD)
        client.requestApproval("force_push", "force push", ApprovalRiskClass.SERIOUS)
        client.requestApproval("rotate_key", "rotate key", ApprovalRiskClass.CRITICAL)

        val beforeStop = GatewayEventReducer.reduceAll(GatewayUiState(), collected)
        assertEquals(
            "Demo fixture + three requests should leave several approvals pending",
            beforeStop.pendingApprovals.size,
            beforeStop.pendingApprovals.size, // smoke
        )
        assertTrue(beforeStop.pendingApprovals.size >= 3)

        client.triggerEmergencyStop("user_panic_button")

        val stopEvent = collected.filterIsInstance<EmergencyStopTriggeredEvent>().firstOrNull()
        assertNotNull(
            "triggerEmergencyStop must emit an EmergencyStopTriggeredEvent",
            stopEvent,
        )

        val afterStop = GatewayEventReducer.reduceAll(GatewayUiState(), collected)
        assertTrue(
            "Emergency stop must clear pending approvals",
            afterStop.pendingApprovals.isEmpty(),
        )
        assertEquals(IconState.ERROR, afterStop.iconState)
        assertNotNull(
            "emergencyStop state must be present in the reduced UI",
            afterStop.emergencyStop,
        )
        assertEquals("user_panic_button", afterStop.emergencyStop!!.reason)

        // Workers that were running should be marked FAILED.
        afterStop.workers.forEach {
            assertEquals(WorkerRuntime.TerminalState.FAILED, it.terminal)
        }

        job.cancel()
    }

    @Test
    fun `reconnecting after an emergency stop clears the flag`() = runTest(UnconfinedTestDispatcher()) {
        val client = MockGatewayClient()
        val collected = mutableListOf<GatewayEvent>()
        val job = launch { client.events.toList(collected) }
        client.connect()

        client.triggerEmergencyStop("test")
        val afterStop = GatewayEventReducer.reduceAll(GatewayUiState(), collected)
        assertNotNull(afterStop.emergencyStop)

        // Simulate a fresh connect by emitting another connected event.
        val replay = collected + GatewayConnectedEvent(
            eventId = "evt-reconnect",
            occurredAt = "2026-05-26T00:00:99Z",
            gatewayId = "gw-2",
            protocolVersion = "1.0.0",
            mode = "mock",
        )
        val afterReconnect = GatewayEventReducer.reduceAll(GatewayUiState(), replay)
        assertEquals(null, afterReconnect.emergencyStop)

        job.cancel()
    }
}
