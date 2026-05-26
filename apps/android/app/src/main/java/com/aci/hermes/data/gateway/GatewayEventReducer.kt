package com.aci.hermes.data.gateway

/**
 * Pure event-to-UI-state reducer for the Jarvis Prime spine.
 *
 * Given the previous [GatewayUiState] and a single [GatewayEvent],
 * returns the next state. The function is total — every event in the
 * spine is handled — and side-effect free, which makes it the natural
 * unit-test boundary.
 *
 * Two invariants enforced here:
 *
 *  1. [EmergencyStopTriggeredEvent] always wins. It clears pending
 *     approvals, kills in-flight worker progress, and forces the
 *     icon to ERROR. Subsequent events still update state, but the
 *     `emergencyStop` flag stays set until a fresh
 *     [GatewayConnectedEvent] arrives.
 *  2. Confirmation counts are derived from observed events, not from
 *     local optimism. If the gateway emits two
 *     [ApprovalGrantedEvent]s with `confirmation_index=1,2` for the
 *     same approval, the UI sees the count climb.
 */
object GatewayEventReducer {

    fun reduce(state: GatewayUiState, event: GatewayEvent): GatewayUiState = when (event) {
        is GatewayConnectedEvent -> state.copy(
            connection = GatewayConnectionState.Connected(
                gatewayId = event.gatewayId,
                protocolVersion = event.protocolVersion,
                mode = if (event.mode.equals("real", ignoreCase = true)) {
                    GatewayMode.REAL
                } else {
                    GatewayMode.MOCK
                },
            ),
            iconState = if (state.iconState == IconState.OFFLINE) IconState.IDLE else state.iconState,
            emergencyStop = null,
        )

        is GatewayDisconnectedEvent -> state.copy(
            connection = GatewayConnectionState.Disconnected(event.reason),
            iconState = IconState.OFFLINE,
        )

        is UserMessageEvent -> state.copy(
            transcript = state.transcript + TranscriptTurn(
                role = TranscriptTurn.Role.USER,
                text = event.text,
                correlationId = event.correlationId,
                occurredAt = event.occurredAt,
            ),
        )

        is ResponseDeltaEvent -> {
            val cid = event.correlationId ?: event.eventId
            val prior = state.pendingDeltas[cid].orEmpty()
            val merged = prior + event.delta
            if (event.final) {
                state.copy(
                    pendingDeltas = state.pendingDeltas - cid,
                    transcript = state.transcript + TranscriptTurn(
                        role = TranscriptTurn.Role.JARVIS,
                        text = merged,
                        correlationId = event.correlationId,
                        occurredAt = event.occurredAt,
                    ),
                )
            } else {
                state.copy(pendingDeltas = state.pendingDeltas + (cid to merged))
            }
        }

        is JarvisResponseEvent -> {
            val cid = event.correlationId ?: event.eventId
            // If a delta stream is still buffered for this correlation,
            // the final response replaces it.
            state.copy(
                pendingDeltas = state.pendingDeltas - cid,
                transcript = state.transcript + TranscriptTurn(
                    role = TranscriptTurn.Role.JARVIS,
                    text = event.text,
                    correlationId = event.correlationId,
                    occurredAt = event.occurredAt,
                ),
            )
        }

        is TaskCreatedEvent -> state.copy(
            tasks = (state.tasks.filterNot { it.taskId == event.task.taskId }) + event.task,
        )

        is TaskUpdatedEvent -> state.copy(
            tasks = state.tasks.map { if (it.taskId == event.task.taskId) event.task else it },
        )

        is ApprovalRequestedEvent -> {
            val required = when (event.riskClass) {
                ApprovalRiskClass.STANDARD -> 1
                ApprovalRiskClass.SERIOUS -> MockGatewayClient.REQUIRED_SERIOUS_CONFIRMATIONS
                ApprovalRiskClass.CRITICAL -> 1
            }
            val summary = PendingApprovalSummary(
                approvalId = event.approvalId,
                actionId = event.actionId,
                summary = event.summary,
                riskClass = event.riskClass,
                confirmationsRequired = required,
                expiresAt = event.expiresAt,
            )
            state.copy(
                pendingApprovals = state.pendingApprovals
                    .filterNot { it.approvalId == event.approvalId } + summary,
            )
        }

        is SeriousConfirmationRequiredEvent -> state.copy(
            pendingApprovals = state.pendingApprovals.map {
                if (it.approvalId == event.approvalId) {
                    it.copy(
                        riskClass = ApprovalRiskClass.SERIOUS,
                        confirmationsRequired = event.confirmationsRequired,
                    )
                } else it
            },
        )

        is CriticalConfirmationRequiredEvent -> state.copy(
            pendingApprovals = state.pendingApprovals.map {
                if (it.approvalId == event.approvalId) {
                    it.copy(
                        riskClass = ApprovalRiskClass.CRITICAL,
                        impactReport = event.impactReport,
                    )
                } else it
            },
        )

        is ApprovalGrantedEvent -> {
            val existing = state.pendingApprovals.firstOrNull { it.approvalId == event.approvalId }
            if (existing == null) state
            else {
                val seen = maxOf(existing.confirmationsSeen, event.confirmationIndex)
                if (seen >= existing.confirmationsRequired) {
                    state.copy(
                        pendingApprovals = state.pendingApprovals
                            .filterNot { it.approvalId == event.approvalId },
                    )
                } else {
                    state.copy(
                        pendingApprovals = state.pendingApprovals.map {
                            if (it.approvalId == event.approvalId) it.copy(confirmationsSeen = seen)
                            else it
                        },
                    )
                }
            }
        }

        is ApprovalRejectedEvent -> state.copy(
            pendingApprovals = state.pendingApprovals
                .filterNot { it.approvalId == event.approvalId },
        )

        is MemoryUpdatedEvent -> state.copy(
            memory = (state.memory.filterNot { it.memoryId == event.entry.memoryId }) + event.entry,
        )

        is MemoryCorrectedEvent -> state.copy(
            memory = state.memory.map { if (it.memoryId == event.entry.memoryId) event.entry else it },
        )

        is MemoryDeletedEvent -> state.copy(
            memory = state.memory.filterNot { it.memoryId == event.memoryId },
        )

        is AuditRecordCreatedEvent -> state.copy(
            auditLog = (state.auditLog + event.record).takeLast(MAX_AUDIT),
        )

        is IconStateChangedEvent -> state.copy(
            iconState = event.state,
            iconDetail = event.detail,
        )

        is EmergencyStopTriggeredEvent -> state.copy(
            pendingApprovals = emptyList(),
            workers = state.workers.map {
                it.copy(terminal = WorkerRuntime.TerminalState.FAILED, message = "emergency_stop")
            },
            iconState = IconState.ERROR,
            iconDetail = "emergency_stop:${event.reason}",
            emergencyStop = EmergencyStopState(
                reason = event.reason,
                triggeredBy = event.triggeredBy,
                occurredAt = event.occurredAt,
            ),
        )

        is WorkerStartedEvent -> state.copy(
            workers = (state.workers.filterNot { it.workerId == event.worker.workerId }) +
                WorkerRuntime(
                    workerId = event.worker.workerId,
                    kind = event.worker.kind,
                    title = event.worker.title,
                    taskId = event.worker.taskId,
                ),
        )

        is WorkerProgressEvent -> state.copy(
            workers = state.workers.map {
                if (it.workerId == event.workerId) {
                    it.copy(fraction = event.fraction, message = event.message)
                } else it
            },
        )

        is WorkerCompletedEvent -> state.copy(
            workers = state.workers.map {
                if (it.workerId == event.workerId) {
                    it.copy(
                        fraction = 1f,
                        message = event.summary,
                        terminal = WorkerRuntime.TerminalState.COMPLETED,
                    )
                } else it
            },
        )

        is WorkerFailedEvent -> state.copy(
            workers = state.workers.map {
                if (it.workerId == event.workerId) {
                    it.copy(
                        message = event.error,
                        terminal = WorkerRuntime.TerminalState.FAILED,
                    )
                } else it
            },
        )
    }

    fun reduceAll(initial: GatewayUiState, events: Iterable<GatewayEvent>): GatewayUiState =
        events.fold(initial, ::reduce)

    private const val MAX_AUDIT = 200
}
