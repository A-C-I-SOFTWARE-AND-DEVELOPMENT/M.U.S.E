package com.aci.hermes.approvals

import com.aci.hermes.safety.RiskTier
import kotlinx.serialization.Serializable
import java.util.UUID

/**
 * A pending request for Jarvis Prime to take an action that affects
 * the owner's systems. Every action Jarvis Prime performs through a
 * worker goes through this — the app itself never executes
 * destructive actions directly.
 *
 * The [ImpactReport] is required for [RiskTier.CRITICAL] approvals and
 * carries a rollback plan the owner must acknowledge.
 */
@Serializable
data class Approval(
    val id: String = UUID.randomUUID().toString(),
    val summary: String,
    val description: String,
    val tier: RiskTier,
    val jobId: String? = null,
    val createdAt: Long = System.currentTimeMillis(),
    val impact: ImpactReport? = null,
    val decision: Decision = Decision.PENDING,
    val confirmationsCollected: Int = 0,
    val decidedAt: Long? = null,
    val decisionReason: String? = null,
) {
    init {
        if (tier == RiskTier.CRITICAL) {
            requireNotNull(impact) { "CRITICAL approvals must carry an ImpactReport" }
        }
    }

    @Serializable
    enum class Decision { PENDING, APPROVED, REJECTED, REJECTED_BY_EMERGENCY_STOP, EXPIRED }

    val canApprove: Boolean
        get() = decision == Decision.PENDING && confirmationsCollected >= tier.confirmationsRequired

    @Serializable
    data class ImpactReport(
        val summary: String,
        val affectedSurfaces: List<String>,
        val rollback: String,
        val estimatedDurationSeconds: Int? = null,
    )
}
