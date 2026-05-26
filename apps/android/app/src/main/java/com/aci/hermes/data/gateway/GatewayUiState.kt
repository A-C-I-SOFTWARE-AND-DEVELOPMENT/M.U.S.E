package com.aci.hermes.data.gateway

/**
 * Projection of the Jarvis Prime spine that the UI binds to.
 *
 * Built by [GatewayEventReducer] from a stream of [GatewayEvent]s. The
 * shape is deliberately *flat* — one screen state, no nested
 * sub-stores — because the events themselves are flat and Compose is
 * happiest with single sources of truth.
 *
 * No field in this class holds a secret. The mapped subset of every
 * event is the human-visible payload only.
 */
data class GatewayUiState(
    val connection: GatewayConnectionState = GatewayConnectionState.Idle,
    val iconState: IconState = IconState.OFFLINE,
    val iconDetail: String? = null,
    val transcript: List<TranscriptTurn> = emptyList(),
    val pendingDeltas: Map<String, String> = emptyMap(),
    val tasks: List<GatewayTaskSnapshot> = emptyList(),
    val pendingApprovals: List<PendingApprovalSummary> = emptyList(),
    val memory: List<MemoryEntry> = emptyList(),
    val auditLog: List<AuditRecord> = emptyList(),
    val workers: List<WorkerRuntime> = emptyList(),
    val emergencyStop: EmergencyStopState? = null,
)

data class TranscriptTurn(
    val role: Role,
    val text: String,
    val correlationId: String?,
    val occurredAt: String,
) {
    enum class Role { USER, JARVIS }
}

/**
 * UI-friendly view of an in-flight approval. Tracks how many serious
 * confirmations have been recorded so far so the screen can render
 * "1 of 2 confirmations" without re-walking the event log.
 */
data class PendingApprovalSummary(
    val approvalId: String,
    val actionId: String,
    val summary: String,
    val riskClass: ApprovalRiskClass,
    val confirmationsSeen: Int = 0,
    val confirmationsRequired: Int = 1,
    val impactReport: ImpactReport? = null,
    val expiresAt: String? = null,
)

data class WorkerRuntime(
    val workerId: String,
    val kind: String,
    val title: String,
    val taskId: String?,
    val fraction: Float = 0f,
    val message: String? = null,
    val terminal: TerminalState? = null,
) {
    enum class TerminalState { COMPLETED, FAILED }
}

data class EmergencyStopState(
    val reason: String,
    val triggeredBy: String,
    val occurredAt: String,
)
