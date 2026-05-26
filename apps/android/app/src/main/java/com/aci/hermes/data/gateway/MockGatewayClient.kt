package com.aci.hermes.data.gateway

import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import java.util.UUID
import java.util.concurrent.atomic.AtomicLong

/**
 * In-process [GatewayClient] used for demos, tests, and offline
 * navigation of the Android UI.
 *
 * What it does:
 *
 *  - Replays a fake-but-realistic event sequence on [connect] so the
 *    full UI is exercisable without a backend.
 *  - Tracks pending approvals so the serious/critical confirmation
 *    invariants can be enforced and tested.
 *  - Emits outbound events on [events] *before* `send*`/`confirm*`
 *    methods return, so a UI subscriber and a unit test see the same
 *    causal order.
 *
 * What it does **not** do:
 *
 *  - Talk to the network.
 *  - Persist anything beyond the in-memory event log.
 *  - Hold any secret. No bearer tokens, no provider keys.
 */
class MockGatewayClient(
    private val clock: () -> Long = { System.currentTimeMillis() },
    private val idFactory: () -> String = { UUID.randomUUID().toString() },
) : GatewayClient {

    private val _events = MutableSharedFlow<GatewayEvent>(
        replay = 0,
        extraBufferCapacity = 256,
    )
    override val events: Flow<GatewayEvent> = _events.asSharedFlow()

    private val _connectionState =
        MutableStateFlow<GatewayConnectionState>(GatewayConnectionState.Idle)
    override val connectionState: StateFlow<GatewayConnectionState> =
        _connectionState.asStateFlow()

    private val mutex = Mutex()
    private val seq = AtomicLong(0)

    /**
     * `approvalId → set of confirmation tokens already accepted`.
     * Used to enforce the serious-action two-confirm invariant.
     */
    private val seriousConfirmations = mutableMapOf<String, MutableSet<String>>()

    /** Approvals known to be critical-class. */
    private val criticalApprovals = mutableSetOf<String>()

    override suspend fun connect() = mutex.withLock {
        if (_connectionState.value is GatewayConnectionState.Connected) return@withLock
        _connectionState.value = GatewayConnectionState.Connecting(GatewayMode.MOCK)
        val event = GatewayConnectedEvent(
            eventId = nextId(),
            occurredAt = nowIso(),
            gatewayId = "mock-${idFactory().take(8)}",
            protocolVersion = JarvisGatewayProtocol.VERSION,
            mode = "mock",
        )
        _events.emit(event)
        _connectionState.value = GatewayConnectionState.Connected(
            gatewayId = event.gatewayId,
            protocolVersion = event.protocolVersion,
            mode = GatewayMode.MOCK,
        )
        replayFakeData()
    }

    override suspend fun disconnect() = mutex.withLock {
        if (_connectionState.value is GatewayConnectionState.Disconnected) return@withLock
        val event = GatewayDisconnectedEvent(
            eventId = nextId(),
            occurredAt = nowIso(),
            reason = "user_disconnect",
        )
        _events.emit(event)
        _connectionState.value = GatewayConnectionState.Disconnected("user_disconnect")
    }

    override suspend fun sendUserMessage(text: String, correlationId: String?): UserMessageEvent {
        require(text.isNotBlank()) { "user_message text cannot be blank" }
        val cid = correlationId ?: idFactory()
        val event = UserMessageEvent(
            eventId = nextId(),
            occurredAt = nowIso(),
            correlationId = cid,
            text = text,
        )
        _events.emit(event)
        // Mirror a streaming response so the UI has something to render.
        emitFakeResponse(cid, text)
        return event
    }

    override suspend fun requestApproval(
        actionId: String,
        summary: String,
        riskClass: ApprovalRiskClass,
    ): ApprovalRequestedEvent {
        val approvalId = "approval-${idFactory()}"
        val event = ApprovalRequestedEvent(
            eventId = nextId(),
            occurredAt = nowIso(),
            approvalId = approvalId,
            actionId = actionId,
            summary = summary,
            riskClass = riskClass,
        )
        _events.emit(event)
        when (riskClass) {
            ApprovalRiskClass.STANDARD -> { /* nothing extra */ }
            ApprovalRiskClass.SERIOUS -> {
                _events.emit(
                    SeriousConfirmationRequiredEvent(
                        eventId = nextId(),
                        occurredAt = nowIso(),
                        correlationId = event.correlationId,
                        approvalId = approvalId,
                        summary = summary,
                    )
                )
                seriousConfirmations[approvalId] = mutableSetOf()
            }
            ApprovalRiskClass.CRITICAL -> {
                _events.emit(
                    CriticalConfirmationRequiredEvent(
                        eventId = nextId(),
                        occurredAt = nowIso(),
                        correlationId = event.correlationId,
                        approvalId = approvalId,
                        summary = summary,
                        impactReport = ImpactReport(
                            summary = "Mock: $summary",
                            blastRadius = "single-workspace",
                            reversibility = "manual_rollback_only",
                            affectedResources = listOf(actionId),
                            rollbackPlan = "Restore from latest snapshot; replay last 24h of events.",
                        ),
                    )
                )
                criticalApprovals += approvalId
            }
        }
        return event
    }

    override suspend fun grantApproval(approvalId: String, note: String?): ApprovalGrantedEvent {
        check(approvalId !in seriousConfirmations) {
            "Approval $approvalId is serious-class; use confirmSerious() twice."
        }
        check(approvalId !in criticalApprovals) {
            "Approval $approvalId is critical-class; use confirmCritical() with an impact report."
        }
        val event = ApprovalGrantedEvent(
            eventId = nextId(),
            occurredAt = nowIso(),
            approvalId = approvalId,
            confirmationIndex = 1,
            note = note,
        )
        _events.emit(event)
        return event
    }

    override suspend fun rejectApproval(approvalId: String, reason: String?): ApprovalRejectedEvent {
        val event = ApprovalRejectedEvent(
            eventId = nextId(),
            occurredAt = nowIso(),
            approvalId = approvalId,
            reason = reason,
        )
        _events.emit(event)
        seriousConfirmations.remove(approvalId)
        criticalApprovals.remove(approvalId)
        return event
    }

    override suspend fun confirmSerious(
        approvalId: String,
        confirmationToken: String,
    ): ApprovalGrantedEvent {
        require(confirmationToken.isNotBlank()) {
            "Serious confirmation token cannot be blank."
        }
        val tokens = seriousConfirmations[approvalId]
            ?: throw IllegalStateException(
                "Approval $approvalId is not awaiting serious confirmation."
            )
        check(confirmationToken !in tokens) {
            "Serious confirmation token already used for $approvalId."
        }
        tokens += confirmationToken
        val event = ApprovalGrantedEvent(
            eventId = nextId(),
            occurredAt = nowIso(),
            approvalId = approvalId,
            confirmationIndex = tokens.size,
            note = "serious_confirmation",
        )
        _events.emit(event)
        if (tokens.size >= REQUIRED_SERIOUS_CONFIRMATIONS) {
            // Action would now execute on the gateway side.
            seriousConfirmations.remove(approvalId)
        }
        return event
    }

    override suspend fun confirmCritical(
        approvalId: String,
        impactReport: ImpactReport,
    ): ApprovalGrantedEvent {
        require(impactReport.summary.isNotBlank()) {
            "Impact report summary cannot be blank for a critical action."
        }
        require(impactReport.rollbackPlan.isNotBlank()) {
            "Impact report rollback_plan cannot be blank for a critical action."
        }
        check(approvalId in criticalApprovals) {
            "Approval $approvalId is not awaiting critical confirmation."
        }
        val event = ApprovalGrantedEvent(
            eventId = nextId(),
            occurredAt = nowIso(),
            approvalId = approvalId,
            confirmationIndex = 1,
            note = "critical_confirmation:${impactReport.blastRadius}",
        )
        _events.emit(event)
        criticalApprovals.remove(approvalId)
        return event
    }

    override suspend fun triggerEmergencyStop(reason: String): EmergencyStopTriggeredEvent {
        require(reason.isNotBlank()) { "Emergency stop requires a reason." }
        val event = EmergencyStopTriggeredEvent(
            eventId = nextId(),
            occurredAt = nowIso(),
            reason = reason,
        )
        _events.emit(event)
        _events.emit(
            IconStateChangedEvent(
                eventId = nextId(),
                occurredAt = nowIso(),
                state = IconState.ERROR,
                detail = "emergency_stop",
            )
        )
        // Wipe outstanding confirmations — the gateway side would do
        // the same on receiving the event.
        seriousConfirmations.clear()
        criticalApprovals.clear()
        return event
    }

    // ── Internal helpers ────────────────────────────────────────────

    private suspend fun replayFakeData() {
        for (event in FakeData.demoEvents(clock, idFactory)) {
            _events.emit(event)
        }
    }

    private suspend fun emitFakeResponse(correlationId: String, prompt: String) {
        _events.emit(
            IconStateChangedEvent(
                eventId = nextId(),
                occurredAt = nowIso(),
                correlationId = correlationId,
                state = IconState.THINKING,
            )
        )
        val chunks = fakeReply(prompt).chunked(24)
        chunks.forEachIndexed { index, chunk ->
            _events.emit(
                ResponseDeltaEvent(
                    eventId = nextId(),
                    occurredAt = nowIso(),
                    correlationId = correlationId,
                    delta = chunk,
                    sequenceIndex = index,
                    final = index == chunks.lastIndex,
                )
            )
        }
        _events.emit(
            JarvisResponseEvent(
                eventId = nextId(),
                occurredAt = nowIso(),
                correlationId = correlationId,
                text = chunks.joinToString(""),
                responseMode = "companion",
            )
        )
        _events.emit(
            IconStateChangedEvent(
                eventId = nextId(),
                occurredAt = nowIso(),
                correlationId = correlationId,
                state = IconState.IDLE,
            )
        )
    }

    private fun fakeReply(prompt: String): String {
        val trimmed = prompt.trim()
        return "I hear you. Mock mode acknowledges: \"" +
            trimmed.take(80) +
            (if (trimmed.length > 80) "…\"" else "\"") +
            " — no real action taken."
    }

    private fun nextId(): String = "evt-${seq.incrementAndGet()}-${idFactory().take(8)}"

    private fun nowIso(): String = isoFormat(clock())

    companion object {
        const val REQUIRED_SERIOUS_CONFIRMATIONS = 2
    }
}

internal object JarvisGatewayProtocol {
    const val VERSION = "1.0.0-spine"
}

internal fun isoFormat(epochMillis: Long): String {
    val instant = java.time.Instant.ofEpochMilli(epochMillis)
    return java.time.format.DateTimeFormatter.ISO_INSTANT.format(instant)
}
