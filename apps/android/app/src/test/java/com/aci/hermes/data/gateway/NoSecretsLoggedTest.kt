package com.aci.hermes.data.gateway

import com.aci.hermes.util.LogBuffer
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.encodeToString
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Two complementary guards:
 *
 * 1. Static guard: scan the entire serialized JSON shape of every
 *    event class for any field name that looks secret-shaped
 *    (`token`, `api_key`, `password`, etc.). The wire contract must
 *    not give a real transport a place to stash credentials.
 * 2. Runtime guard: drive [GatewayController] through a session that
 *    sends user messages, approvals, and emergency stops; assert that
 *    the [LogBuffer] never captures the message bodies — only event
 *    type names.
 */
@OptIn(ExperimentalCoroutinesApi::class)
class NoSecretsLoggedTest {

    @Test
    fun `no event class exposes a secret-shaped field`() {
        val forbidden = listOf(
            "token", "bearer", "password", "api_key", "secret",
            "session_id", "cookie", "refresh_token", "access_token",
            "private_key", "client_secret",
        )

        // Sample one event per type so the JSON contains every field
        // path, then scan all field names.
        val samples: List<GatewayEvent> = listOf(
            UserMessageEvent("e", "t", null, "x"),
            JarvisResponseEvent("e", "t", null, "x"),
            ResponseDeltaEvent("e", "t", null, "x"),
            TaskCreatedEvent("e", "t", null, GatewayTaskSnapshot("t1", "x", null, "draft")),
            TaskUpdatedEvent("e", "t", null, GatewayTaskSnapshot("t1", "x", null, "draft")),
            ApprovalRequestedEvent("e", "t", null, "a", "x", "x", ApprovalRiskClass.STANDARD),
            ApprovalGrantedEvent("e", "t", null, "a"),
            ApprovalRejectedEvent("e", "t", null, "a"),
            SeriousConfirmationRequiredEvent("e", "t", null, "a", "x"),
            CriticalConfirmationRequiredEvent(
                "e", "t", null, "a", "x",
                ImpactReport("s", "br", "rev", emptyList(), "rb"),
            ),
            MemoryUpdatedEvent("e", "t", null, MemoryEntry("m", "k", "x")),
            MemoryCorrectedEvent("e", "t", null, MemoryEntry("m", "k", "x"), "y"),
            MemoryDeletedEvent("e", "t", null, "m"),
            AuditRecordCreatedEvent("e", "t", null, AuditRecord("r", "a", "u", "ok")),
            IconStateChangedEvent("e", "t", null, IconState.IDLE),
            EmergencyStopTriggeredEvent("e", "t", null, "x"),
            GatewayConnectedEvent("e", "t", null, "gw", "v"),
            GatewayDisconnectedEvent("e", "t", null, "x"),
            WorkerStartedEvent("e", "t", null, WorkerSnapshot("w", "k", "x")),
            WorkerProgressEvent("e", "t", null, "w", 0f),
            WorkerCompletedEvent("e", "t", null, "w"),
            WorkerFailedEvent("e", "t", null, "w", "x"),
        )

        for (event in samples) {
            val json = GatewayJson.encodeToString<GatewayEvent>(event).lowercase()
            for (word in forbidden) {
                assertFalse(
                    "Event ${event::class.simpleName} surfaces forbidden field name " +
                        "\"$word\": $json",
                    json.contains("\"$word\""),
                )
            }
        }
    }

    @Test
    fun `GatewayController never logs raw event bodies`() = runTest(UnconfinedTestDispatcher()) {
        val logBuffer = LogBuffer()
        val controller = GatewayController(
            mockFactory = { MockGatewayClient() },
            logBuffer = logBuffer,
            scope = backgroundScope,
        )

        controller.switchMode(GatewayMode.MOCK)

        controller.client()!!.sendUserMessage(
            "super-secret-password-hunter2-do-not-log-me",
        )

        controller.client()!!.triggerEmergencyStop(
            "this-reason-string-must-not-leak-into-logcat",
        )

        val collected = logBuffer.entries.value
        val joined = collected.joinToString("\n") { it.format() }

        assertFalse(
            "User message text must not leak into log entries: " +
                "size=${collected.size} joined=$joined",
            joined.contains("hunter2"),
        )
        assertFalse(
            "Emergency stop reason must not leak into log entries: " +
                "size=${collected.size} joined=$joined",
            joined.contains("leak-into-logcat"),
        )
        assertTrue(
            "Log entries should still be emitted — they just contain only event type names. " +
                "size=${collected.size} joined=$joined",
            collected.any { it.message.startsWith("event ") },
        )

        controller.stop()
    }
}
