package com.aci.hermes.data.gateway

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json

/**
 * Jarvis Prime Gateway Event Spine — Kotlin mirror of the wire contract.
 *
 * Every signal that crosses the boundary between the Android app and a
 * Jarvis Prime gateway (mock or real) flows through this sealed
 * hierarchy. The on-the-wire shape is JSON with a `type` discriminator
 * matching the [SerialName] on each subclass.
 *
 * Two design rules this file enforces:
 *
 *  1. The app emits *intents and approvals*, never destructive actions.
 *     Anything the app sends to the gateway is one of these events — it
 *     does not call a side-effecting REST endpoint.
 *  2. No event ever carries a secret. There is no field for a bearer
 *     token, OAuth refresh token, provider API key, or password. Adding
 *     one here without explicit security review is the failure mode
 *     this comment exists to prevent.
 */
@Serializable
sealed class GatewayEvent {
    /** Stable id assigned by whichever side emitted the event. */
    abstract val eventId: String

    /** ISO-8601 instant string (`2026-05-26T17:30:00Z`). */
    abstract val occurredAt: String

    /**
     * Optional id tying related events together (e.g. a user_message and
     * the jarvis_response that answers it).
     */
    abstract val correlationId: String?
}

// ─── Conversation ─────────────────────────────────────────────────────

@Serializable
@SerialName("user_message")
data class UserMessageEvent(
    @SerialName("event_id") override val eventId: String,
    @SerialName("occurred_at") override val occurredAt: String,
    @SerialName("correlation_id") override val correlationId: String? = null,
    val text: String,
    val mode: String = "text",
) : GatewayEvent()

@Serializable
@SerialName("jarvis_response")
data class JarvisResponseEvent(
    @SerialName("event_id") override val eventId: String,
    @SerialName("occurred_at") override val occurredAt: String,
    @SerialName("correlation_id") override val correlationId: String? = null,
    val text: String,
    @SerialName("response_mode") val responseMode: String = "companion",
) : GatewayEvent()

@Serializable
@SerialName("response_delta")
data class ResponseDeltaEvent(
    @SerialName("event_id") override val eventId: String,
    @SerialName("occurred_at") override val occurredAt: String,
    @SerialName("correlation_id") override val correlationId: String? = null,
    val delta: String,
    @SerialName("sequence_index") val sequenceIndex: Int = 0,
    val final: Boolean = false,
) : GatewayEvent()

// ─── Tasks ────────────────────────────────────────────────────────────

@Serializable
data class GatewayTaskSnapshot(
    @SerialName("task_id") val taskId: String,
    val title: String,
    val summary: String? = null,
    val status: String,
    @SerialName("workspace_path") val workspacePath: String? = null,
    @SerialName("worker_kind") val workerKind: String? = null,
)

@Serializable
@SerialName("task_created")
data class TaskCreatedEvent(
    @SerialName("event_id") override val eventId: String,
    @SerialName("occurred_at") override val occurredAt: String,
    @SerialName("correlation_id") override val correlationId: String? = null,
    val task: GatewayTaskSnapshot,
) : GatewayEvent()

@Serializable
@SerialName("task_updated")
data class TaskUpdatedEvent(
    @SerialName("event_id") override val eventId: String,
    @SerialName("occurred_at") override val occurredAt: String,
    @SerialName("correlation_id") override val correlationId: String? = null,
    val task: GatewayTaskSnapshot,
    val reason: String? = null,
) : GatewayEvent()

// ─── Approvals ────────────────────────────────────────────────────────

@Serializable
enum class ApprovalRiskClass {
    @SerialName("standard") STANDARD,
    @SerialName("serious") SERIOUS,
    @SerialName("critical") CRITICAL,
}

@Serializable
data class ImpactReport(
    val summary: String,
    @SerialName("blast_radius") val blastRadius: String,
    val reversibility: String,
    @SerialName("affected_resources") val affectedResources: List<String> = emptyList(),
    @SerialName("rollback_plan") val rollbackPlan: String,
)

@Serializable
@SerialName("approval_requested")
data class ApprovalRequestedEvent(
    @SerialName("event_id") override val eventId: String,
    @SerialName("occurred_at") override val occurredAt: String,
    @SerialName("correlation_id") override val correlationId: String? = null,
    @SerialName("approval_id") val approvalId: String,
    @SerialName("action_id") val actionId: String,
    val summary: String,
    @SerialName("risk_class") val riskClass: ApprovalRiskClass = ApprovalRiskClass.STANDARD,
    @SerialName("requested_by") val requestedBy: String = "app",
    @SerialName("expires_at") val expiresAt: String? = null,
) : GatewayEvent()

@Serializable
@SerialName("approval_granted")
data class ApprovalGrantedEvent(
    @SerialName("event_id") override val eventId: String,
    @SerialName("occurred_at") override val occurredAt: String,
    @SerialName("correlation_id") override val correlationId: String? = null,
    @SerialName("approval_id") val approvalId: String,
    @SerialName("confirmation_index") val confirmationIndex: Int = 1,
    @SerialName("decided_by") val decidedBy: String = "user",
    val note: String? = null,
) : GatewayEvent()

@Serializable
@SerialName("approval_rejected")
data class ApprovalRejectedEvent(
    @SerialName("event_id") override val eventId: String,
    @SerialName("occurred_at") override val occurredAt: String,
    @SerialName("correlation_id") override val correlationId: String? = null,
    @SerialName("approval_id") val approvalId: String,
    @SerialName("decided_by") val decidedBy: String = "user",
    val reason: String? = null,
) : GatewayEvent()

@Serializable
@SerialName("serious_confirmation_required")
data class SeriousConfirmationRequiredEvent(
    @SerialName("event_id") override val eventId: String,
    @SerialName("occurred_at") override val occurredAt: String,
    @SerialName("correlation_id") override val correlationId: String? = null,
    @SerialName("approval_id") val approvalId: String,
    val summary: String,
    @SerialName("confirmations_required") val confirmationsRequired: Int = 2,
) : GatewayEvent()

@Serializable
@SerialName("critical_confirmation_required")
data class CriticalConfirmationRequiredEvent(
    @SerialName("event_id") override val eventId: String,
    @SerialName("occurred_at") override val occurredAt: String,
    @SerialName("correlation_id") override val correlationId: String? = null,
    @SerialName("approval_id") val approvalId: String,
    val summary: String,
    @SerialName("impact_report") val impactReport: ImpactReport,
) : GatewayEvent()

// ─── Memory ───────────────────────────────────────────────────────────

@Serializable
data class MemoryEntry(
    @SerialName("memory_id") val memoryId: String,
    val kind: String,
    val text: String,
    @SerialName("source") val source: String? = null,
)

@Serializable
@SerialName("memory_updated")
data class MemoryUpdatedEvent(
    @SerialName("event_id") override val eventId: String,
    @SerialName("occurred_at") override val occurredAt: String,
    @SerialName("correlation_id") override val correlationId: String? = null,
    val entry: MemoryEntry,
) : GatewayEvent()

@Serializable
@SerialName("memory_corrected")
data class MemoryCorrectedEvent(
    @SerialName("event_id") override val eventId: String,
    @SerialName("occurred_at") override val occurredAt: String,
    @SerialName("correlation_id") override val correlationId: String? = null,
    val entry: MemoryEntry,
    @SerialName("previous_text") val previousText: String,
) : GatewayEvent()

@Serializable
@SerialName("memory_deleted")
data class MemoryDeletedEvent(
    @SerialName("event_id") override val eventId: String,
    @SerialName("occurred_at") override val occurredAt: String,
    @SerialName("correlation_id") override val correlationId: String? = null,
    @SerialName("memory_id") val memoryId: String,
    val reason: String? = null,
) : GatewayEvent()

// ─── Audit ────────────────────────────────────────────────────────────

@Serializable
data class AuditRecord(
    @SerialName("record_id") val recordId: String,
    val action: String,
    val actor: String,
    val outcome: String,
    val details: Map<String, String> = emptyMap(),
)

@Serializable
@SerialName("audit_record_created")
data class AuditRecordCreatedEvent(
    @SerialName("event_id") override val eventId: String,
    @SerialName("occurred_at") override val occurredAt: String,
    @SerialName("correlation_id") override val correlationId: String? = null,
    val record: AuditRecord,
) : GatewayEvent()

// ─── Icon / presence ──────────────────────────────────────────────────

@Serializable
enum class IconState {
    @SerialName("idle") IDLE,
    @SerialName("listening") LISTENING,
    @SerialName("thinking") THINKING,
    @SerialName("speaking") SPEAKING,
    @SerialName("waiting_approval") WAITING_APPROVAL,
    @SerialName("error") ERROR,
    @SerialName("offline") OFFLINE,
}

@Serializable
@SerialName("icon_state_changed")
data class IconStateChangedEvent(
    @SerialName("event_id") override val eventId: String,
    @SerialName("occurred_at") override val occurredAt: String,
    @SerialName("correlation_id") override val correlationId: String? = null,
    val state: IconState,
    val detail: String? = null,
) : GatewayEvent()

// ─── Emergency stop ───────────────────────────────────────────────────

@Serializable
@SerialName("emergency_stop_triggered")
data class EmergencyStopTriggeredEvent(
    @SerialName("event_id") override val eventId: String,
    @SerialName("occurred_at") override val occurredAt: String,
    @SerialName("correlation_id") override val correlationId: String? = null,
    val reason: String,
    @SerialName("triggered_by") val triggeredBy: String = "user",
) : GatewayEvent()

// ─── Connection ───────────────────────────────────────────────────────

@Serializable
@SerialName("gateway_connected")
data class GatewayConnectedEvent(
    @SerialName("event_id") override val eventId: String,
    @SerialName("occurred_at") override val occurredAt: String,
    @SerialName("correlation_id") override val correlationId: String? = null,
    @SerialName("gateway_id") val gatewayId: String,
    @SerialName("protocol_version") val protocolVersion: String,
    val mode: String = "mock",
) : GatewayEvent()

@Serializable
@SerialName("gateway_disconnected")
data class GatewayDisconnectedEvent(
    @SerialName("event_id") override val eventId: String,
    @SerialName("occurred_at") override val occurredAt: String,
    @SerialName("correlation_id") override val correlationId: String? = null,
    val reason: String,
) : GatewayEvent()

// ─── Workers ──────────────────────────────────────────────────────────

@Serializable
data class WorkerSnapshot(
    @SerialName("worker_id") val workerId: String,
    val kind: String,
    val title: String,
    @SerialName("task_id") val taskId: String? = null,
)

@Serializable
@SerialName("worker_started")
data class WorkerStartedEvent(
    @SerialName("event_id") override val eventId: String,
    @SerialName("occurred_at") override val occurredAt: String,
    @SerialName("correlation_id") override val correlationId: String? = null,
    val worker: WorkerSnapshot,
) : GatewayEvent()

@Serializable
@SerialName("worker_progress")
data class WorkerProgressEvent(
    @SerialName("event_id") override val eventId: String,
    @SerialName("occurred_at") override val occurredAt: String,
    @SerialName("correlation_id") override val correlationId: String? = null,
    @SerialName("worker_id") val workerId: String,
    val fraction: Float,
    val message: String? = null,
) : GatewayEvent()

@Serializable
@SerialName("worker_completed")
data class WorkerCompletedEvent(
    @SerialName("event_id") override val eventId: String,
    @SerialName("occurred_at") override val occurredAt: String,
    @SerialName("correlation_id") override val correlationId: String? = null,
    @SerialName("worker_id") val workerId: String,
    val summary: String? = null,
) : GatewayEvent()

@Serializable
@SerialName("worker_failed")
data class WorkerFailedEvent(
    @SerialName("event_id") override val eventId: String,
    @SerialName("occurred_at") override val occurredAt: String,
    @SerialName("correlation_id") override val correlationId: String? = null,
    @SerialName("worker_id") val workerId: String,
    val error: String,
) : GatewayEvent()

// ─── Serialization ────────────────────────────────────────────────────

/**
 * The single Json instance used to round-trip [GatewayEvent] values.
 *
 * `classDiscriminator = "type"` matches the wire contract — every event
 * is `{"type": "user_message", ...}` not `{"user_message": {...}}`.
 *
 * `ignoreUnknownKeys` means a future gateway version that adds fields
 * won't crash an older app build; the app will simply drop the unknown
 * fields. The reverse (unknown event *types*) raises
 * `SerializationException`, which the client wraps and logs without
 * exposing the raw payload.
 */
val GatewayJson: Json = Json {
    classDiscriminator = "type"
    ignoreUnknownKeys = true
    encodeDefaults = true
    explicitNulls = false
}
