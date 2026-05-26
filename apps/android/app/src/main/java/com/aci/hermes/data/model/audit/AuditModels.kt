package com.aci.hermes.data.model.audit

import kotlinx.serialization.Serializable

/**
 * Risk tier copied from the JARVIS Prime routing matrix. Determines
 * approval requirements, verification depth, and rollback expectations.
 */
@Serializable
enum class RiskTier { TRIVIAL, LOW, MODERATE, SERIOUS, CRITICAL }

/**
 * Lifecycle state of an approval the operator was (or should have been)
 * asked for. UNNECESSARY = below the approval threshold for this tier.
 */
@Serializable
enum class ApprovalState {
    UNNECESSARY,
    PENDING,
    APPROVED,
    REJECTED,
    AUTO_APPROVED,
    EXPIRED,
}

/**
 * Outcome of the action JARVIS took on behalf of the user.
 */
@Serializable
enum class ActionResult { SUCCESS, PARTIAL, FAILED, ROLLED_BACK, BLOCKED }

/**
 * Where the request went after JARVIS classified it.
 */
@Serializable
enum class RouteDestination {
    LOCAL_WORKER,
    CODEX,
    CLAUDE,
    HERMES_GATEWAY,
    HUMAN_ONLY,
}

@Serializable
enum class EvidenceKind {
    DIFF,
    LOG,
    SCREENSHOT,
    METRIC,
    TEST_REPORT,
    DOC_LINK,
    COMMAND_OUTPUT,
}

@Serializable
enum class VerificationStatus { PASSED, FAILED, SKIPPED, FLAKY }

/**
 * One auditable thing that JARVIS did. Persisted in the local ledger
 * and shown in the AuditScreen list. All long-form material lives on
 * the linked [ProofRecord].
 */
@Serializable
data class AuditRecord(
    val id: String,
    val timestamp: Long,
    val userRequest: String,
    val action: String,
    val riskTier: RiskTier,
    val route: RouteSummary,
    val approvalState: ApprovalState,
    val result: ActionResult,
    val confidence: Float,
    val proofId: String,
)

/**
 * Detailed proof attached to a single [AuditRecord]. This is the
 * payload behind the "open proof" action and contains every detail
 * needed to reconstruct what happened and why.
 */
@Serializable
data class ProofRecord(
    val id: String,
    val auditId: String,
    val rationale: String,
    val evidence: List<EvidenceItem>,
    val testsRun: List<String>,
    val filesChanged: List<String>,
    val verification: VerificationResult,
    val approvals: List<ApprovalHistoryItem>,
    val rollback: RollbackPlan?,
    val impactReport: String?,
    val workerRuns: List<WorkerRun>,
)

@Serializable
data class EvidenceItem(
    val id: String,
    val kind: EvidenceKind,
    val title: String,
    val body: String,
    val sourcePath: String? = null,
)

@Serializable
data class RouteSummary(
    val destination: RouteDestination,
    val model: String?,
    val reason: String,
    val durationMs: Long,
)

@Serializable
data class ApprovalHistoryItem(
    val id: String,
    val timestamp: Long,
    val approver: String,
    val state: ApprovalState,
    val comment: String?,
)

@Serializable
data class RollbackPlan(
    val id: String,
    val summary: String,
    val steps: List<String>,
    val automatic: Boolean,
    val executed: Boolean,
)

@Serializable
data class VerificationResult(
    val status: VerificationStatus,
    val summary: String,
    val failingChecks: List<String>,
    val passedChecks: List<String>,
)

@Serializable
data class WorkerRun(
    val id: String,
    val worker: String,
    val startedAt: Long,
    val finishedAt: Long,
    val status: ActionResult,
    val notes: String,
)
