package com.aci.hermes.data.gateway

import kotlinx.serialization.SerializationException
import kotlinx.serialization.encodeToString
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test

/**
 * Round-trip every event variant through the wire format and back, and
 * verify that the `type` discriminator on the wire exactly matches the
 * spec list.
 *
 * If anyone adds, removes, or renames an event in [GatewayEvent.kt],
 * the [SPEC_TYPES] set is the place to update — these tests fail loud
 * on accidental drift.
 */
class GatewayEventSerializationTest {

    private val sampleImpact = ImpactReport(
        summary = "rotate signing key",
        blastRadius = "all_releases",
        reversibility = "irreversible",
        affectedResources = listOf("play_store"),
        rollbackPlan = "open emergency support ticket",
    )

    private val samples: List<Pair<String, GatewayEvent>> = listOf(
        "user_message" to UserMessageEvent("e1", "2026-05-26T00:00:00Z", "c1", "hi"),
        "jarvis_response" to JarvisResponseEvent("e2", "2026-05-26T00:00:01Z", "c1", "hello"),
        "response_delta" to ResponseDeltaEvent("e3", "2026-05-26T00:00:02Z", "c1", "he", 0, false),
        "task_created" to TaskCreatedEvent(
            "e4", "2026-05-26T00:00:03Z", null,
            GatewayTaskSnapshot("t1", "title", null, "drafting"),
        ),
        "task_updated" to TaskUpdatedEvent(
            "e5", "2026-05-26T00:00:04Z", null,
            GatewayTaskSnapshot("t1", "title", null, "running"),
            reason = "worker_started",
        ),
        "approval_requested" to ApprovalRequestedEvent(
            "e6", "2026-05-26T00:00:05Z", null,
            "a1", "open_pr", "Open draft PR", ApprovalRiskClass.STANDARD,
        ),
        "approval_granted" to ApprovalGrantedEvent(
            "e7", "2026-05-26T00:00:06Z", null,
            "a1", 1,
        ),
        "approval_rejected" to ApprovalRejectedEvent(
            "e8", "2026-05-26T00:00:07Z", null,
            "a1", reason = "user_rejected",
        ),
        "serious_confirmation_required" to SeriousConfirmationRequiredEvent(
            "e9", "2026-05-26T00:00:08Z", null,
            "a2", "Force push", confirmationsRequired = 2,
        ),
        "critical_confirmation_required" to CriticalConfirmationRequiredEvent(
            "e10", "2026-05-26T00:00:09Z", null,
            "a3", "Rotate signing key", sampleImpact,
        ),
        "memory_updated" to MemoryUpdatedEvent(
            "e11", "2026-05-26T00:00:10Z", null,
            MemoryEntry("m1", "preference", "short responses"),
        ),
        "memory_corrected" to MemoryCorrectedEvent(
            "e12", "2026-05-26T00:00:11Z", null,
            MemoryEntry("m1", "preference", "very short"), previousText = "short responses",
        ),
        "memory_deleted" to MemoryDeletedEvent(
            "e13", "2026-05-26T00:00:12Z", null,
            memoryId = "m1", reason = "user_deleted",
        ),
        "audit_record_created" to AuditRecordCreatedEvent(
            "e14", "2026-05-26T00:00:13Z", null,
            AuditRecord("r1", "task_created", "user", "ok"),
        ),
        "icon_state_changed" to IconStateChangedEvent(
            "e15", "2026-05-26T00:00:14Z", null,
            IconState.WAITING_APPROVAL, detail = "1 pending",
        ),
        "emergency_stop_triggered" to EmergencyStopTriggeredEvent(
            "e16", "2026-05-26T00:00:15Z", null,
            reason = "user_panic_button",
        ),
        "gateway_connected" to GatewayConnectedEvent(
            "e17", "2026-05-26T00:00:16Z", null,
            gatewayId = "gw-1", protocolVersion = "1.0.0", mode = "mock",
        ),
        "gateway_disconnected" to GatewayDisconnectedEvent(
            "e18", "2026-05-26T00:00:17Z", null,
            reason = "network_dropped",
        ),
        "worker_started" to WorkerStartedEvent(
            "e19", "2026-05-26T00:00:18Z", null,
            WorkerSnapshot("w1", "builder", "Refactor"),
        ),
        "worker_progress" to WorkerProgressEvent(
            "e20", "2026-05-26T00:00:19Z", null,
            workerId = "w1", fraction = 0.5f, message = "halfway",
        ),
        "worker_completed" to WorkerCompletedEvent(
            "e21", "2026-05-26T00:00:20Z", null,
            workerId = "w1", summary = "done",
        ),
        "worker_failed" to WorkerFailedEvent(
            "e22", "2026-05-26T00:00:21Z", null,
            workerId = "w1", error = "test failure",
        ),
    )

    @Test
    fun `every event round-trips through wire JSON`() {
        for ((expectedType, event) in samples) {
            val json = GatewayJson.encodeToString<GatewayEvent>(event)
            assertTrue(
                "Expected discriminator type=\"$expectedType\" in $json",
                json.contains("\"type\":\"$expectedType\""),
            )
            val parsed = GatewayJson.decodeFromString<GatewayEvent>(json)
            assertEquals(
                "Round-trip for $expectedType lost a field",
                event,
                parsed,
            )
        }
    }

    @Test
    fun `spec list matches kotlin sealed hierarchy`() {
        val kotlinTypes = samples.map { it.first }.toSet()
        assertEquals(
            "Add or remove the type from both SPEC_TYPES and the sample list",
            SPEC_TYPES,
            kotlinTypes,
        )
    }

    @Test
    fun `unknown event type fails fast`() {
        val bogus = """{"type":"made_up_event","event_id":"e1","occurred_at":"now"}"""
        try {
            GatewayJson.decodeFromString<GatewayEvent>(bogus)
            fail("Expected SerializationException for unknown event type")
        } catch (_: SerializationException) {
            // expected — caller (the real transport) wraps and logs
            // *type only*, never the body.
        }
    }

    @Test
    fun `ignoreUnknownKeys lets the gateway add fields without breaking the app`() {
        val withExtra = """
        {"type":"user_message","event_id":"e1","occurred_at":"2026-05-26T00:00:00Z",
         "text":"hi","mode":"text","future_field":"someday"}
        """.trimIndent()
        val parsed = GatewayJson.decodeFromString<GatewayEvent>(withExtra) as UserMessageEvent
        assertEquals("hi", parsed.text)
    }

    companion object {
        private val SPEC_TYPES = setOf(
            "user_message",
            "jarvis_response",
            "response_delta",
            "task_created",
            "task_updated",
            "approval_requested",
            "approval_granted",
            "approval_rejected",
            "serious_confirmation_required",
            "critical_confirmation_required",
            "memory_updated",
            "memory_corrected",
            "memory_deleted",
            "audit_record_created",
            "icon_state_changed",
            "emergency_stop_triggered",
            "gateway_connected",
            "gateway_disconnected",
            "worker_started",
            "worker_progress",
            "worker_completed",
            "worker_failed",
        )
    }
}
