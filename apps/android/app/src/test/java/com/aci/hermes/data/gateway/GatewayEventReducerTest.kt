package com.aci.hermes.data.gateway

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Spot tests on the pure reducer. The end-to-end behaviour is covered
 * by [MockGatewayClientTest] and friends; these tests pin specific
 * edge cases — task upsert, delta buffering, memory correction —
 * that are easy to regress without noticing.
 */
class GatewayEventReducerTest {

    @Test
    fun `task_created followed by task_updated leaves a single record`() {
        val snap = GatewayTaskSnapshot("t1", "title", "summary", "draft")
        val updated = snap.copy(status = "running", summary = "now running")

        val state = GatewayEventReducer.reduceAll(
            GatewayUiState(),
            listOf(
                TaskCreatedEvent("e1", "t", null, snap),
                TaskUpdatedEvent("e2", "t", null, updated, reason = "started"),
            ),
        )

        assertEquals(1, state.tasks.size)
        assertEquals("running", state.tasks.first().status)
    }

    @Test
    fun `streaming response_delta accumulates and final flushes to transcript`() {
        val deltas = listOf(
            ResponseDeltaEvent("e1", "t", "c1", "Hel", 0, false),
            ResponseDeltaEvent("e2", "t", "c1", "lo, ", 1, false),
            ResponseDeltaEvent("e3", "t", "c1", "world!", 2, true),
        )
        val state = GatewayEventReducer.reduceAll(GatewayUiState(), deltas)

        assertTrue("pendingDeltas must drain on final", state.pendingDeltas.isEmpty())
        assertEquals(1, state.transcript.size)
        assertEquals("Hello, world!", state.transcript.first().text)
        assertEquals(TranscriptTurn.Role.JARVIS, state.transcript.first().role)
    }

    @Test
    fun `partial deltas survive without a final and stay buffered`() {
        val state = GatewayEventReducer.reduceAll(
            GatewayUiState(),
            listOf(
                ResponseDeltaEvent("e1", "t", "c1", "Hel", 0, false),
                ResponseDeltaEvent("e2", "t", "c1", "lo", 1, false),
            ),
        )
        assertTrue(state.transcript.isEmpty())
        assertEquals("Hello", state.pendingDeltas["c1"])
    }

    @Test
    fun `memory_corrected replaces the entry text but keeps the id`() {
        val original = MemoryEntry("m1", "preference", "short responses")
        val fix = original.copy(text = "very short responses")

        val state = GatewayEventReducer.reduceAll(
            GatewayUiState(),
            listOf(
                MemoryUpdatedEvent("e1", "t", null, original),
                MemoryCorrectedEvent("e2", "t", null, fix, previousText = original.text),
            ),
        )
        assertEquals(1, state.memory.size)
        assertEquals("very short responses", state.memory.first().text)
    }

    @Test
    fun `memory_deleted removes the entry by id`() {
        val a = MemoryEntry("m1", "p", "a")
        val b = MemoryEntry("m2", "p", "b")
        val state = GatewayEventReducer.reduceAll(
            GatewayUiState(),
            listOf(
                MemoryUpdatedEvent("e1", "t", null, a),
                MemoryUpdatedEvent("e2", "t", null, b),
                MemoryDeletedEvent("e3", "t", null, "m1", reason = "user"),
            ),
        )
        assertEquals(1, state.memory.size)
        assertEquals("m2", state.memory.first().memoryId)
    }

    @Test
    fun `worker progression then completion marks the worker terminal`() {
        val worker = WorkerSnapshot("w1", "builder", "Build", "t1")
        val state = GatewayEventReducer.reduceAll(
            GatewayUiState(),
            listOf(
                WorkerStartedEvent("e1", "t", null, worker),
                WorkerProgressEvent("e2", "t", null, "w1", 0.25f, "starting"),
                WorkerProgressEvent("e3", "t", null, "w1", 0.75f, "almost"),
                WorkerCompletedEvent("e4", "t", null, "w1", "done"),
            ),
        )
        val w = state.workers.single()
        assertEquals(1f, w.fraction, 0.001f)
        assertEquals(WorkerRuntime.TerminalState.COMPLETED, w.terminal)
    }

    @Test
    fun `approval_rejected removes the pending approval`() {
        val state = GatewayEventReducer.reduceAll(
            GatewayUiState(),
            listOf(
                ApprovalRequestedEvent(
                    "e1", "t", null, "a1", "x", "x", ApprovalRiskClass.STANDARD,
                ),
                ApprovalRejectedEvent("e2", "t", null, "a1", reason = "no"),
            ),
        )
        assertNull(state.pendingApprovals.firstOrNull { it.approvalId == "a1" })
    }

    @Test
    fun `gateway_disconnected forces icon back to offline`() {
        val state = GatewayEventReducer.reduceAll(
            GatewayUiState(),
            listOf(
                GatewayConnectedEvent("e1", "t", null, "gw", "v"),
                IconStateChangedEvent("e2", "t", null, IconState.WAITING_APPROVAL),
                GatewayDisconnectedEvent("e3", "t", null, "network_dropped"),
            ),
        )
        assertEquals(IconState.OFFLINE, state.iconState)
        assertTrue(state.connection is GatewayConnectionState.Disconnected)
    }

    @Test
    fun `gateway_connected mode wire field decides Mock vs Real`() {
        val mock = GatewayEventReducer.reduce(
            GatewayUiState(),
            GatewayConnectedEvent("e1", "t", null, "gw", "v", "mock"),
        )
        val real = GatewayEventReducer.reduce(
            GatewayUiState(),
            GatewayConnectedEvent("e2", "t", null, "gw", "v", "real"),
        )
        assertEquals(
            GatewayMode.MOCK,
            (mock.connection as GatewayConnectionState.Connected).mode,
        )
        assertEquals(
            GatewayMode.REAL,
            (real.connection as GatewayConnectionState.Connected).mode,
        )
        assertNotNull(mock.connection)
    }
}
