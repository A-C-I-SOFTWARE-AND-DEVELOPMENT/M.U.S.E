package com.aci.hermes.data.gateway

import com.aci.hermes.data.model.Approval
import com.aci.hermes.data.model.ApprovalDecision
import com.aci.hermes.data.model.ApprovalRisk
import com.aci.hermes.data.model.AuditEvent
import com.aci.hermes.data.model.AuditSeverity
import com.aci.hermes.data.model.GatewayEvent
import com.aci.hermes.data.model.GatewayEventType
import com.aci.hermes.data.model.ImpactItem
import com.aci.hermes.data.model.ImpactReport
import com.aci.hermes.data.redaction.Redactor
import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlin.math.abs

/**
 * Deterministic in-process gateway. Powers Mock mode and serves as the
 * reference implementation for the spine — the screens consume the
 * same [GatewayEvent] envelopes whether they're driven by the fake or
 * the real Termux gateway.
 *
 * Intentionally has no coroutines launching themselves on
 * construction. Every event is published in response to an explicit
 * call, which makes the behaviour easy to assert in tests.
 */
class FakeGatewayClient : GatewayClient {

    override val mode: GatewayMode = GatewayMode.MOCK

    private val _events = MutableSharedFlow<GatewayEvent>(
        replay = 32,
        extraBufferCapacity = 64,
        onBufferOverflow = BufferOverflow.DROP_OLDEST,
    )
    override val events: Flow<GatewayEvent> = _events.asSharedFlow()

    private val _connection = MutableStateFlow<ConnectionState>(ConnectionState.Disconnected)
    override val connection: Flow<ConnectionState> = _connection.asStateFlow()

    private val mutex = Mutex()
    private var started: Boolean = false
    private var counter: Int = 0

    private val _approvals = mutableMapOf<String, Approval>()
    val approvals: List<Approval> get() = _approvals.values.toList()

    private val _audit = mutableListOf<AuditEvent>()
    val audit: List<AuditEvent> get() = _audit.toList()

    override suspend fun start() = mutex.withLock {
        started = true
        _connection.value = ConnectionState.Connected
        emit(GatewayEvent(type = GatewayEventType.CONNECTION_CHANGED, payload = "connected"))
        if (_approvals.isEmpty()) seedFixtures()
    }

    override suspend fun stop() = mutex.withLock {
        started = false
        _connection.value = ConnectionState.Disconnected
        emit(GatewayEvent(type = GatewayEventType.CONNECTION_CHANGED, payload = "disconnected"))
    }

    override suspend fun submitChat(text: String): ChatResponse = mutex.withLock {
        val (redacted, fields) = Redactor.redact(text).let { it.text to it.redactedFields }
        emit(GatewayEvent(type = GatewayEventType.CHAT_REPLY, payload = redacted))
        val title = redacted.lineSequence().firstOrNull().orEmpty().take(80)
        val approval = maybeCreateApprovalFromChat(redacted)
        if (approval != null) emit(approvalEvent(approval))
        val reply = buildString {
            append("Acknowledged. ")
            if (fields.isNotEmpty()) {
                append("Redacted fields: ${fields.joinToString()}. ")
            }
            append("Mock mode — no external action taken.")
        }
        ChatResponse(
            replyText = reply,
            suggestedTaskTitle = title.takeIf { it.isNotBlank() },
            createdApprovalId = approval?.id,
        )
    }

    override suspend fun submitVoiceTranscript(text: String): ChatResponse =
        submitChat("voice: $text")

    override suspend fun decideApproval(
        approval: Approval,
        approve: Boolean,
        notes: String?,
    ) = mutex.withLock {
        val existing = _approvals[approval.id] ?: approval
        val decided = existing.copy(
            decision = if (approve) ApprovalDecision.APPROVED else ApprovalDecision.REJECTED,
            decidedAt = System.currentTimeMillis(),
            decisionNotes = notes,
            updatedAt = System.currentTimeMillis(),
        )
        _approvals[decided.id] = decided
        emit(
            GatewayEvent(
                type = GatewayEventType.APPROVAL_DECIDED,
                payload = if (approve) "approved" else "rejected",
                refId = decided.id,
            )
        )
        appendAudit(
            AuditEvent(
                actor = "user",
                action = if (approve) "approve" else "reject",
                target = decided.title,
                payloadSummary = (notes ?: "").take(120),
                severity = severityFor(decided.risk),
                approvalId = decided.id,
                proofHash = proofHash(decided.id, approve, notes),
            )
        )
        Unit
    }

    override suspend fun heartbeat() {
        emit(GatewayEvent(type = GatewayEventType.HEARTBEAT, payload = "ok"))
    }

    /** Fixtures the on-boarding scenarios reference. Idempotent. */
    private suspend fun seedFixtures() {
        val routine = Approval(
            title = "Tag 12 incoming notes",
            description = "Auto-tag inbound notes captured this morning.",
            proposedAction = "tag-batch",
            risk = ApprovalRisk.LOW,
        )
        val risky = Approval(
            title = "Send daily digest to your inbox",
            description = "Compile and send today's digest to the on-device inbox.",
            proposedAction = "send-digest",
            risk = ApprovalRisk.MEDIUM,
        )
        val serious = Approval(
            title = "Rewrite local prompt library",
            description = "Bulk update prompt library entries to the new schema.",
            proposedAction = "rewrite-prompts",
            risk = ApprovalRisk.HIGH,
        )
        val critical = Approval(
            title = "Reset local memory store",
            description = "Reset Jarvis Prime's on-device memory and audit ledger.",
            proposedAction = "reset-memory",
            risk = ApprovalRisk.CRITICAL,
            impact = ImpactReport(
                summary = "This will permanently delete remembered facts, preferences and audit entries on this device.",
                items = listOf(
                    ImpactItem("Memory entries", "≈42", ApprovalRisk.HIGH),
                    ImpactItem("Audit entries", "≈108", ApprovalRisk.CRITICAL),
                    ImpactItem("Reversible", "No", ApprovalRisk.CRITICAL),
                ),
                reversible = false,
                blastRadius = "single device",
            ),
        )
        listOf(routine, risky, serious, critical).forEach {
            _approvals[it.id] = it
            emit(approvalEvent(it))
        }
    }

    private fun severityFor(risk: ApprovalRisk): AuditSeverity = when (risk) {
        ApprovalRisk.LOW -> AuditSeverity.INFO
        ApprovalRisk.MEDIUM -> AuditSeverity.NOTICE
        ApprovalRisk.HIGH -> AuditSeverity.WARNING
        ApprovalRisk.CRITICAL -> AuditSeverity.CRITICAL
    }

    private fun maybeCreateApprovalFromChat(redactedText: String): Approval? {
        val lower = redactedText.lowercase()
        return when {
            "delete" in lower || "wipe" in lower || "reset" in lower ->
                Approval(
                    title = "Confirm destructive action",
                    description = redactedText.take(200),
                    proposedAction = "destructive-from-chat",
                    risk = ApprovalRisk.CRITICAL,
                    impact = ImpactReport(
                        summary = "Chat input suggested a destructive action. Held for review.",
                        reversible = false,
                    ),
                ).also { _approvals[it.id] = it }
            "send" in lower || "publish" in lower ->
                Approval(
                    title = "Send / publish from chat",
                    description = redactedText.take(200),
                    proposedAction = "send-from-chat",
                    risk = ApprovalRisk.MEDIUM,
                ).also { _approvals[it.id] = it }
            else -> null
        }
    }

    private fun approvalEvent(approval: Approval): GatewayEvent = GatewayEvent(
        type = if (approval.isPending) GatewayEventType.APPROVAL_OPENED else GatewayEventType.APPROVAL_DECIDED,
        payload = approval.risk.name,
        refId = approval.id,
    )

    private fun appendAudit(event: AuditEvent) {
        _audit += event
        emit(
            GatewayEvent(
                type = GatewayEventType.AUDIT_APPENDED,
                payload = event.action,
                refId = event.id,
            )
        )
    }

    private fun emit(event: GatewayEvent) {
        counter += 1
        _events.tryEmit(event)
    }

    private fun proofHash(approvalId: String, approve: Boolean, notes: String?): String {
        // Deterministic, dependency-free fingerprint. Not a cryptographic
        // claim — the spec says "proof hash" surfaces tamper evidence on
        // an inspector screen, and we render it as a labelled value.
        val seed = "$approvalId|$approve|${notes ?: ""}".hashCode()
        return "0x" + abs(seed.toLong()).toString(16).padStart(8, '0')
    }
}
