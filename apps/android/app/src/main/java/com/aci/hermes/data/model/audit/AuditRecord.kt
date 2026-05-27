package com.aci.hermes.data.model.audit

/**
 * Outcome of an audited action.
 *
 * - [SUCCESS] / [PARTIAL] describe the change landing in some form.
 * - [FAILED] / [ROLLED_BACK] / [BLOCKED] all mean "the user-visible
 *   state did not become what the user asked for"; see
 *   [com.aci.hermes.ui.screens.audit.isFailureLike] in the formatting
 *   helpers which treats them as failure-like for color/iconography.
 */
enum class ActionResult {
    SUCCESS,
    PARTIAL,
    FAILED,
    ROLLED_BACK,
    BLOCKED,
}

/**
 * Approval lifecycle for an audited action.
 *
 * [UNNECESSARY] is the no-approval-required floor (trivial-tier work),
 * [AUTO_APPROVED] means policy approved without a human in the loop,
 * [EXPIRED] is set when a pending approval timed out.
 */
enum class ApprovalState {
    UNNECESSARY,
    PENDING,
    APPROVED,
    REJECTED,
    AUTO_APPROVED,
    EXPIRED,
}

/** Kind of evidence attached to a [ProofRecord]. */
enum class EvidenceKind {
    DIFF,
    TEST_REPORT,
    METRIC,
    COMMAND_OUTPUT,
    LOG,
    DOC_LINK,
}

/**
 * Risk band that drives approval requirements and UI affordances.
 *
 * Ordering is intentional — higher ordinal = higher risk.
 */
enum class RiskTier {
    TRIVIAL,
    LOW,
    MODERATE,
    SERIOUS,
    CRITICAL,
}

/** Where the orchestrator routed the action. */
enum class RouteDestination {
    LOCAL_WORKER,
    CODEX,
    CLAUDE,
    HERMES_GATEWAY,
    HUMAN_ONLY,
}

/** Result of the verification gate that runs after an action completes. */
enum class VerificationStatus {
    PASSED,
    FAILED,
    SKIPPED,
    FLAKY,
}

/**
 * Routing summary attached to every audited action — explains *why*
 * the orchestrator picked a worker (or refused to route).
 *
 * [model] is nullable so HUMAN_ONLY records (no worker invoked) can
 * still produce a valid summary.
 */
data class RouteSummary(
    val destination: RouteDestination,
    val model: String?,
    val reason: String,
    val durationMs: Long,
)

/**
 * One-line entry the Audit list renders. Holds just enough context to
 * decide whether to drill in to the [ProofRecord].
 */
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
 * Single piece of evidence attached to a [ProofRecord]. Bodies may
 * contain secrets, which is why [com.aci.hermes.data.audit.SecretRedactor]
 * is applied before the repository exposes them to the UI.
 */
data class EvidenceItem(
    val id: String,
    val kind: EvidenceKind,
    val title: String,
    val body: String,
    val sourcePath: String? = null,
)

/** Outcome of the verification gate. */
data class VerificationResult(
    val status: VerificationStatus,
    val summary: String,
    val failingChecks: List<String>,
    val passedChecks: List<String>,
)

/** Audit row for one approval transition (pending/approved/rejected). */
data class ApprovalHistoryItem(
    val id: String,
    val timestamp: Long,
    val approver: String,
    val state: ApprovalState,
    val comment: String?,
)

/**
 * Rollback plan for an audited action.
 *
 * [automatic] = whether the orchestrator may execute the rollback
 * without owner consent. [executed] flips to true once the rollback
 * has actually run.
 */
data class RollbackPlan(
    val id: String,
    val summary: String,
    val steps: List<String>,
    val automatic: Boolean,
    val executed: Boolean,
)

/** Per-worker execution record inside a [ProofRecord]. */
data class WorkerRun(
    val id: String,
    val worker: String,
    val startedAt: Long,
    val finishedAt: Long,
    val status: ActionResult,
    val notes: String,
)

/**
 * Full proof bundle for an [AuditRecord]. Materialized by
 * [com.aci.hermes.data.audit.AuditRepository] and consumed by the
 * audit detail screen + tests.
 */
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
