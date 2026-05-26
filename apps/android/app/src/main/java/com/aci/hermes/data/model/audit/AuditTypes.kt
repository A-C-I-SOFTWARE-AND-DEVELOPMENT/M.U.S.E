package com.aci.hermes.data.model.audit

import kotlinx.serialization.Serializable

/**
 * Plain-data audit + proof model for the Jarvis Prime audit ledger.
 *
 * Every record the operator sees on the Audit / Audit Detail screens
 * is built from these shapes. The model is deliberately narrow and
 * Android-free so:
 *   - the renderer under `ui/screens/audit/` can be exercised in pure
 *     JVM tests with no Robolectric,
 *   - the seed data in `data/audit/AuditRepository.kt` and any future
 *     wire-format from the gateway can populate the same types,
 *   - the redactor (`data/audit/SecretRedactor.kt`) can sanitize
 *     specific string fields in-place via `copy(...)`.
 *
 * All collection fields are non-nullable lists (use `emptyList()` for
 * absence) so the renderer never needs nullable-list guards.
 */

/** Risk classification used to size the visual treatment + governance. */
enum class RiskTier { TRIVIAL, LOW, MODERATE, SERIOUS, CRITICAL }

/** Where a request was routed for execution. */
enum class RouteDestination {
    /** Local worker handled the change entirely on-device. */
    LOCAL_WORKER,
    /** Routed to Codex (mid / heavy diff work). */
    CODEX,
    /** Routed to Claude (reasoning, schema design, careful work). */
    CLAUDE,
    /** Routed to the Hermes gateway (policy / infra). */
    HERMES_GATEWAY,
    /** No automated route — held for human action. */
    HUMAN_ONLY,
}

/**
 * Owner-gate state for a single audit record. `UNNECESSARY` means the
 * change was below the approval threshold; `AUTO_APPROVED` means a
 * standing rule cleared it without explicit owner input.
 */
enum class ApprovalState {
    UNNECESSARY,
    PENDING,
    APPROVED,
    AUTO_APPROVED,
    REJECTED,
    EXPIRED,
}

/** Terminal status for the attempted action. */
enum class ActionResult { SUCCESS, PARTIAL, FAILED, ROLLED_BACK, BLOCKED }

/** Outcome of the verification gate that ran after the action. */
enum class VerificationStatus { PASSED, FAILED, SKIPPED, FLAKY }

/** Kind of evidence captured in [EvidenceItem]. */
enum class EvidenceKind {
    DIFF,
    TEST_REPORT,
    LOG,
    COMMAND_OUTPUT,
    METRIC,
    DOC_LINK,
}

/**
 * The audit row the operator scans on the Audit list screen.
 *
 * @param proofId points at the matching [ProofRecord] (1:1). The
 *   indirection is intentional: list rendering only needs this shape,
 *   while detail rendering pulls the heavier proof on demand.
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

/** What route the request took, and why. */
@Serializable
data class RouteSummary(
    val destination: RouteDestination,
    val model: String?,
    val reason: String,
    val durationMs: Long,
)

/**
 * Proof bundle for an [AuditRecord]: rationale, evidence, tests,
 * verification outcome, approval history, rollback plan and the
 * worker run-log. Owner reads this to decide whether to trust the
 * change and whether to roll it back.
 */
@Serializable
data class ProofRecord(
    val id: String,
    val auditId: String,
    val rationale: String,
    val evidence: List<EvidenceItem> = emptyList(),
    val testsRun: List<String> = emptyList(),
    val filesChanged: List<String> = emptyList(),
    val verification: VerificationResult,
    val approvals: List<ApprovalHistoryItem> = emptyList(),
    val rollback: RollbackPlan? = null,
    val impactReport: String? = null,
    val workerRuns: List<WorkerRun> = emptyList(),
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
data class VerificationResult(
    val status: VerificationStatus,
    val summary: String,
    val failingChecks: List<String> = emptyList(),
    val passedChecks: List<String> = emptyList(),
)

@Serializable
data class ApprovalHistoryItem(
    val id: String,
    val timestamp: Long,
    val approver: String,
    val state: ApprovalState,
    val comment: String? = null,
)

/**
 * Rollback plan attached to a [ProofRecord]. `automatic = true` means
 * the runtime can execute the rollback without owner input;
 * `executed = true` records that it has already run.
 */
@Serializable
data class RollbackPlan(
    val id: String,
    val summary: String,
    val steps: List<String> = emptyList(),
    val automatic: Boolean = false,
    val executed: Boolean = false,
)

/** A single worker invocation that contributed to the audit record. */
@Serializable
data class WorkerRun(
    val id: String,
    val worker: String,
    val startedAt: Long,
    val finishedAt: Long,
    val status: ActionResult,
    val notes: String = "",
)
