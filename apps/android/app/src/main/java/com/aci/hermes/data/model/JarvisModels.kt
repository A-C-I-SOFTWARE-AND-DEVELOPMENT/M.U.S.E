package com.aci.hermes.data.model

import kotlinx.serialization.Serializable
import java.util.UUID

// ============================================================================
// Conversation Engine
// ============================================================================

/** Who authored a chat message. */
@Serializable
enum class ChatRole { USER, JARVIS, SYSTEM }

@Serializable
data class ChatMessage(
    val id: String = UUID.randomUUID().toString(),
    val role: ChatRole,
    val body: String,
    val createdAt: Long = System.currentTimeMillis(),
    /** Optional structured suggestion the user can act on. */
    val suggestion: ChatSuggestion? = null,
    /** Set when this message is a draft of, or refers to, an approval. */
    val approvalId: String? = null,
)

@Serializable
data class ChatSuggestion(
    val label: String,
    val kind: SuggestionKind,
    val payload: String? = null,
)

@Serializable
enum class SuggestionKind { OPEN_TASKS, OPEN_APPROVALS, OPEN_MEMORY, OPEN_AUDIT, START_VOICE, COPY_PROMPT, NEW_TASK }

// ============================================================================
// Permission Kernel — approval cards
// ============================================================================

@Serializable
enum class ApprovalSeverity {
    ROUTINE,    // logged, no confirmation
    RISKY,      // single tap to confirm
    SERIOUS,    // double-confirm
    CRITICAL,   // impact report + typed authorization phrase
}

@Serializable
enum class ApprovalStatus {
    PENDING,
    APPROVED,
    DENIED,
    EXPIRED,
    CANCELLED_BY_EMERGENCY_STOP,
}

@Serializable
data class ApprovalCard(
    val id: String = UUID.randomUUID().toString(),
    val title: String,
    val summary: String,
    val severity: ApprovalSeverity = ApprovalSeverity.ROUTINE,
    val status: ApprovalStatus = ApprovalStatus.PENDING,
    val createdAt: Long = System.currentTimeMillis(),
    val decidedAt: Long? = null,
    val decisionNotes: String? = null,
    /** Only present for SERIOUS / CRITICAL. */
    val impact: ImpactReport? = null,
    /** Source job / task / event that requested approval. */
    val source: String? = null,
)

@Serializable
data class ImpactReport(
    val summary: String,
    val risks: List<String> = emptyList(),
    val affectedSurfaces: List<String> = emptyList(),
    val rollbackPlan: String? = null,
    val estimatedBlastRadius: BlastRadius = BlastRadius.LOCAL,
)

@Serializable
enum class BlastRadius { LOCAL, ACCOUNT, EXTERNAL, IRREVERSIBLE }

// ============================================================================
// Memory Tree — transparency layer
// ============================================================================

@Serializable
enum class MemoryBranch { FACTS, PREFERENCES, GOALS, HISTORY, INFERENCES }

@Serializable
enum class MemoryConfidence { INFERRED, CONFIRMED, REJECTED }

@Serializable
data class MemoryFact(
    val id: String = UUID.randomUUID().toString(),
    val branch: MemoryBranch,
    val label: String,
    val detail: String,
    val confidence: MemoryConfidence = MemoryConfidence.INFERRED,
    val createdAt: Long = System.currentTimeMillis(),
    val updatedAt: Long = System.currentTimeMillis(),
    val expiresAt: Long? = null,
    val source: String? = null,
)

// ============================================================================
// Social Intelligence — patterns Jarvis Prime notices
// ============================================================================

@Serializable
enum class SocialPatternKind {
    COMMUNICATION_STYLE,
    SCHEDULE,
    TONE,
    RELATIONSHIP,
    REPEATING_THEME,
}

@Serializable
data class SocialPattern(
    val id: String = UUID.randomUUID().toString(),
    val kind: SocialPatternKind,
    val title: String,
    val observation: String,
    /** 0..1, how strong the signal is. */
    val signalStrength: Float = 0.5f,
    val createdAt: Long = System.currentTimeMillis(),
    val acknowledged: Boolean = false,
    val dismissed: Boolean = false,
)

// ============================================================================
// Audit / Proof history
// ============================================================================

@Serializable
enum class AuditKind {
    ACTION_TAKEN,
    APPROVAL_GRANTED,
    APPROVAL_DENIED,
    OVERRIDE_USED,
    EMERGENCY_STOP_ENGAGED,
    EMERGENCY_STOP_RELEASED,
    MEMORY_UPDATED,
    MEMORY_FORGOTTEN,
    GATEWAY_EVENT,
    SYSTEM,
}

@Serializable
data class AuditEntry(
    val id: String = UUID.randomUUID().toString(),
    val kind: AuditKind,
    val title: String,
    val detail: String,
    val createdAt: Long = System.currentTimeMillis(),
    val proofId: String = UUID.randomUUID().toString().take(8),
    val relatedId: String? = null,
)

// ============================================================================
// Gateway / Event Spine
// ============================================================================

@Serializable
enum class GatewayMode { MOCK, TERMUX, REMOTE }

@Serializable
enum class GatewayConnectionState { DISCONNECTED, CONNECTING, CONNECTED, ERROR }

@Serializable
enum class GatewayEventKind {
    JOB_STARTED,
    JOB_COMPLETED,
    JOB_FAILED,
    APPROVAL_REQUESTED,
    MESSAGE_RECEIVED,
    SYSTEM_NOTE,
    HEARTBEAT,
}

@Serializable
data class GatewayEvent(
    val id: String = UUID.randomUUID().toString(),
    val kind: GatewayEventKind,
    val source: String,
    val message: String,
    val createdAt: Long = System.currentTimeMillis(),
    val severity: String = "info",
)

// ============================================================================
// Notification Command Center (in-app inbox, not OS notifications)
// ============================================================================

@Serializable
enum class JarvisNotificationKind {
    INFO,
    SUCCESS,
    WARNING,
    APPROVAL_NEEDED,
    GATEWAY_EVENT,
    EMERGENCY,
}

@Serializable
data class JarvisNotification(
    val id: String = UUID.randomUUID().toString(),
    val kind: JarvisNotificationKind,
    val title: String,
    val body: String,
    val createdAt: Long = System.currentTimeMillis(),
    val read: Boolean = false,
    val actionTargetId: String? = null,
)

// ============================================================================
// Skills / Capabilities
// ============================================================================

@Serializable
data class SkillDescriptor(
    val id: String,
    val displayName: String,
    val description: String,
    val category: String,
    val enabled: Boolean = true,
    val requiresApproval: ApprovalSeverity = ApprovalSeverity.ROUTINE,
)

// ============================================================================
// Emergency Stop state
// ============================================================================

@Serializable
data class EmergencyStopState(
    val engaged: Boolean = false,
    val engagedAt: Long? = null,
    val reason: String? = null,
    val releasedAt: Long? = null,
)
