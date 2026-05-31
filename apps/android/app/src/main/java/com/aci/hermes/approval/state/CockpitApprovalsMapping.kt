package com.aci.hermes.approval.state

import com.aci.hermes.approval.model.ApprovalCard
import com.aci.hermes.approval.model.ApprovalRiskTier
import com.aci.hermes.approval.model.ApprovalStatus
import com.aci.hermes.data.cockpit.CockpitApprovalCard
import java.time.Instant
import java.time.OffsetDateTime

/**
 * Maps the cockpit canonical approval-card wire model to the domain
 * [ApprovalCard]. Enum-like wire strings map by constant name with an
 * honest fallback; ISO-8601 timestamps become epoch-millis. A null
 * `expires_at` means "never expires" (self-update proposals don't time
 * out) → [Long.MAX_VALUE], so `isExpired` stays false. Multi-step
 * serious/critical state is UI-runtime and left at its defaults.
 */
fun CockpitApprovalCard.toCard(): ApprovalCard = ApprovalCard(
    id = id,
    title = title,
    summary = summary,
    requester = requester,
    tier = approvalEnum(tier, ApprovalRiskTier.RISKY),
    status = approvalEnum(status, ApprovalStatus.PENDING),
    createdAtMillis = approvalMillis(createdAt),
    expiresAtMillis = expiresAt?.let { approvalMillis(it) } ?: Long.MAX_VALUE,
    proposedAction = proposedAction,
    editedNote = editedNote,
)

internal fun approvalMillis(iso: String?): Long {
    if (iso.isNullOrBlank()) return 0L
    return runCatching { OffsetDateTime.parse(iso).toInstant().toEpochMilli() }
        .recoverCatching { Instant.parse(iso).toEpochMilli() }
        .getOrDefault(0L)
}

internal inline fun <reified E : Enum<E>> approvalEnum(name: String?, default: E): E =
    enumValues<E>().firstOrNull { it.name.equals(name?.trim(), ignoreCase = true) } ?: default
