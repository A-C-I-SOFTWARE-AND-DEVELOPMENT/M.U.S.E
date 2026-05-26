package com.aci.hermes

import com.aci.hermes.data.model.Approval
import com.aci.hermes.data.model.ApprovalDecision
import com.aci.hermes.data.model.ApprovalRisk
import com.aci.hermes.data.model.AuditEvent
import com.aci.hermes.data.model.AuditSeverity
import com.aci.hermes.data.model.GatewayEvent
import com.aci.hermes.data.model.GatewayEventType
import com.aci.hermes.data.model.HermesTask
import com.aci.hermes.data.model.MemoryItem
import com.aci.hermes.data.model.MemoryKind
import com.aci.hermes.data.model.SocialChannel
import com.aci.hermes.data.model.SocialSignal
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import kotlinx.serialization.json.Json

class ModelTests {

    private val json = Json { ignoreUnknownKeys = true }

    @Test
    fun approval_isPending_defaults_to_true() {
        val a = Approval(title = "x")
        assertTrue(a.isPending)
        assertFalse(a.isDecided)
        assertEquals(ApprovalRisk.MEDIUM, a.risk)
        assertEquals(ApprovalDecision.PENDING, a.decision)
    }

    @Test
    fun approval_roundtrips_through_json() {
        val a = Approval(title = "send digest", risk = ApprovalRisk.HIGH)
        val text = json.encodeToString(Approval.serializer(), a)
        val parsed = json.decodeFromString(Approval.serializer(), text)
        assertEquals(a.id, parsed.id)
        assertEquals(ApprovalRisk.HIGH, parsed.risk)
    }

    @Test
    fun memory_item_clamps_confidence() {
        val ok = MemoryItem(content = "x", confidence = 0.3f)
        assertEquals(0.3f, ok.confidence, 0.0001f)
        try {
            MemoryItem(content = "x", confidence = 2f)
        } catch (_: IllegalArgumentException) { return }
        error("expected IllegalArgumentException")
    }

    @Test
    fun social_signal_clamps_sentiment() {
        try {
            SocialSignal(subjectToken = "x", channel = SocialChannel.NOTE, summary = "y", sentiment = 2f)
        } catch (_: IllegalArgumentException) { return }
        error("expected IllegalArgumentException")
    }

    @Test
    fun audit_event_carries_severity() {
        val ev = AuditEvent(action = "approve", severity = AuditSeverity.WARNING)
        assertEquals(AuditSeverity.WARNING, ev.severity)
    }

    @Test
    fun gateway_event_types_cover_spine_contract() {
        val types = GatewayEventType.values().map { it.name }
        listOf(
            "HEARTBEAT",
            "APPROVAL_OPENED",
            "APPROVAL_DECIDED",
            "TASK_CREATED",
            "TASK_UPDATED",
            "MEMORY_UPDATED",
            "SOCIAL_UPDATED",
            "AUDIT_APPENDED",
            "EMERGENCY_STOP_CHANGED",
            "CONNECTION_CHANGED",
            "CHAT_REPLY",
            "DIAGNOSTIC",
        ).forEach { assertTrue("missing $it", it in types) }
    }

    @Test
    fun gateway_event_ids_are_unique_by_default() {
        val a = GatewayEvent(type = GatewayEventType.HEARTBEAT)
        val b = GatewayEvent(type = GatewayEventType.HEARTBEAT)
        assertNotEquals(a.id, b.id)
    }

    @Test
    fun memory_kind_values() {
        assertTrue(MemoryKind.values().toList().containsAll(
            listOf(MemoryKind.FACT, MemoryKind.PREFERENCE, MemoryKind.ASPIRATION, MemoryKind.SOCIAL, MemoryKind.AUDIT_NOTE),
        ))
    }

    @Test
    fun hermes_task_roundtrips_through_json() {
        val task = HermesTask(title = "build x")
        val text = json.encodeToString(HermesTask.serializer(), task)
        val parsed = json.decodeFromString(HermesTask.serializer(), text)
        assertEquals(task.id, parsed.id)
        assertEquals("build x", parsed.title)
    }
}
