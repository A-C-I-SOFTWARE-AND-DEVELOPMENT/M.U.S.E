package com.aci.hermes.data.gateway

import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.toList
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Exercises [MockGatewayClient] end-to-end on the JVM event loop. The
 * tests pin behaviour rather than implementation — they verify the
 * shape of the demo event stream so the UI demo stays informative.
 *
 * Uses [UnconfinedTestDispatcher] so that `launch { collect }`
 * subscribes synchronously before the next test-body statement runs,
 * guaranteeing that the subscriber is attached before
 * [MockGatewayClient.connect] emits the seed events.
 */
@OptIn(ExperimentalCoroutinesApi::class)
class MockGatewayClientTest {

    @Test
    fun `connect emits gateway_connected and demo fixture`() = runTest(UnconfinedTestDispatcher()) {
        val client = MockGatewayClient()
        val collected = mutableListOf<GatewayEvent>()
        val job = launch { client.events.toList(collected) }

        client.connect()

        val types = collected.map { it::class.simpleName }
        assertEquals(
            "GatewayConnectedEvent must be the first event on the spine",
            "GatewayConnectedEvent",
            types.first(),
        )

        assertTrue(
            "Expected at least one task_created event in the demo fixture",
            collected.any { it is TaskCreatedEvent },
        )
        assertTrue(
            "Expected at least one approval_requested event",
            collected.any { it is ApprovalRequestedEvent },
        )
        assertTrue(
            "Expected at least one memory_updated event",
            collected.any { it is MemoryUpdatedEvent },
        )
        assertTrue(
            "Expected at least one audit_record_created event",
            collected.any { it is AuditRecordCreatedEvent },
        )
        assertTrue(
            "Expected at least one worker_started event",
            collected.any { it is WorkerStartedEvent },
        )

        assertTrue(
            "Connection state should be Connected after connect()",
            client.connectionState.value is GatewayConnectionState.Connected,
        )

        job.cancel()
    }

    @Test
    fun `sending a user message produces a streamed response`() = runTest(UnconfinedTestDispatcher()) {
        val client = MockGatewayClient()
        val collected = mutableListOf<GatewayEvent>()
        val job = launch { client.events.toList(collected) }
        client.connect()
        val baseline = collected.size

        val intent = client.sendUserMessage("hello there")

        val newEvents = collected.drop(baseline)
        assertEquals(
            "First event emitted by sendUserMessage must be the UserMessageEvent itself",
            intent.eventId,
            newEvents.first().eventId,
        )
        assertTrue(
            "Expected at least one response_delta in the streamed reply",
            newEvents.any { it is ResponseDeltaEvent },
        )
        assertNotNull(
            "Expected a final jarvis_response capping the stream",
            newEvents.firstOrNull { it is JarvisResponseEvent },
        )
        job.cancel()
    }

    @Test
    fun `reduceAll over demo events leaves UI in a fully populated state`() = runTest(UnconfinedTestDispatcher()) {
        val client = MockGatewayClient()
        val collected = mutableListOf<GatewayEvent>()
        val job = launch { client.events.toList(collected) }
        client.connect()

        val state = GatewayEventReducer.reduceAll(GatewayUiState(), collected)

        assertTrue("tasks populated", state.tasks.isNotEmpty())
        assertTrue("memory populated", state.memory.isNotEmpty())
        assertTrue("audit populated", state.auditLog.isNotEmpty())
        assertTrue("workers populated", state.workers.isNotEmpty())
        assertTrue("approvals populated", state.pendingApprovals.isNotEmpty())
        assertTrue(
            "Demo fixture should leave the icon waiting on approvals",
            state.iconState == IconState.WAITING_APPROVAL,
        )

        job.cancel()
    }
}
