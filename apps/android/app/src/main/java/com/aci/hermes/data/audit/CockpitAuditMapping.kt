package com.aci.hermes.data.audit

import com.aci.hermes.data.cockpit.CockpitApprovalHistoryItem
import com.aci.hermes.data.cockpit.CockpitAuditRecord
import com.aci.hermes.data.cockpit.CockpitEvidenceItem
import com.aci.hermes.data.cockpit.CockpitProofRecord
import com.aci.hermes.data.cockpit.CockpitRollbackPlan
import com.aci.hermes.data.cockpit.CockpitRouteSummary
import com.aci.hermes.data.cockpit.CockpitVerificationResult
import com.aci.hermes.data.cockpit.CockpitWorkerRun
import com.aci.hermes.data.model.audit.ActionResult
import com.aci.hermes.data.model.audit.ApprovalHistoryItem
import com.aci.hermes.data.model.audit.ApprovalState
import com.aci.hermes.data.model.audit.AuditRecord
import com.aci.hermes.data.model.audit.EvidenceItem
import com.aci.hermes.data.model.audit.EvidenceKind
import com.aci.hermes.data.model.audit.ProofRecord
import com.aci.hermes.data.model.audit.RiskTier
import com.aci.hermes.data.model.audit.RollbackPlan
import com.aci.hermes.data.model.audit.RouteDestination
import com.aci.hermes.data.model.audit.RouteSummary
import com.aci.hermes.data.model.audit.VerificationResult
import com.aci.hermes.data.model.audit.VerificationStatus
import com.aci.hermes.data.model.audit.WorkerRun
import java.time.Instant
import java.time.OffsetDateTime

/**
 * Maps the cockpit audit wire models to the rich domain models in
 * `data.model.audit`. Enum-like wire strings map by constant name with an
 * honest fallback (unknown → a safe default, never a crash); ISO-8601
 * timestamps become epoch-millis (0 when absent).
 */

fun CockpitAuditRecord.toDomain(): AuditRecord = AuditRecord(
    id = id,
    timestamp = auditMillis(timestamp),
    userRequest = userRequest,
    action = action,
    riskTier = auditEnum(riskTier, RiskTier.LOW),
    route = route.toDomain(),
    approvalState = auditEnum(approvalState, ApprovalState.UNNECESSARY),
    result = auditEnum(result, ActionResult.SUCCESS),
    confidence = confidence,
    proofId = proofId,
)

fun CockpitRouteSummary.toDomain(): RouteSummary = RouteSummary(
    destination = auditEnum(destination, RouteDestination.HUMAN_ONLY),
    model = model,
    reason = reason,
    durationMs = durationMs,
)

fun CockpitProofRecord.toDomain(): ProofRecord = ProofRecord(
    id = id,
    auditId = auditId,
    rationale = rationale,
    evidence = evidence.map { it.toDomain() },
    testsRun = testsRun,
    filesChanged = filesChanged,
    verification = verification.toDomain(),
    approvals = approvals.map { it.toDomain() },
    rollback = rollback?.toDomain(),
    impactReport = impactReport,
    workerRuns = workerRuns.map { it.toDomain() },
)

private fun CockpitEvidenceItem.toDomain(): EvidenceItem = EvidenceItem(
    id = id,
    kind = auditEnum(kind, EvidenceKind.LOG),
    title = title,
    body = body,
    sourcePath = sourcePath,
)

private fun CockpitVerificationResult.toDomain(): VerificationResult = VerificationResult(
    status = auditEnum(status, VerificationStatus.SKIPPED),
    summary = summary,
    failingChecks = failingChecks,
    passedChecks = passedChecks,
)

private fun CockpitApprovalHistoryItem.toDomain(): ApprovalHistoryItem = ApprovalHistoryItem(
    id = id,
    timestamp = auditMillis(timestamp),
    approver = approver,
    state = auditEnum(state, ApprovalState.PENDING),
    comment = comment,
)

private fun CockpitRollbackPlan.toDomain(): RollbackPlan = RollbackPlan(
    id = id,
    summary = summary,
    steps = steps,
    automatic = automatic,
    executed = executed,
)

private fun CockpitWorkerRun.toDomain(): WorkerRun = WorkerRun(
    id = id,
    worker = worker,
    startedAt = auditMillis(startedAt),
    finishedAt = auditMillis(finishedAt),
    status = auditEnum(status, ActionResult.SUCCESS),
    notes = notes,
)

/** Parse an ISO-8601 timestamp (offset or `Z`) to epoch millis, or 0. */
internal fun auditMillis(iso: String?): Long {
    if (iso.isNullOrBlank()) return 0L
    return runCatching { OffsetDateTime.parse(iso).toInstant().toEpochMilli() }
        .recoverCatching { Instant.parse(iso).toEpochMilli() }
        .getOrDefault(0L)
}

internal inline fun <reified E : Enum<E>> auditEnum(name: String?, default: E): E =
    enumValues<E>().firstOrNull { it.name.equals(name?.trim(), ignoreCase = true) } ?: default
