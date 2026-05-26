package com.aci.hermes.approvals

import com.aci.hermes.safety.RiskTier

/**
 * Jarvis Prime Proof Engine.
 *
 * Renders the impact-report block the owner sees before approving a
 * CRITICAL action. The intent is that the rendered text is also what
 * gets written into the audit log alongside the decision, so the
 * record always shows exactly what the owner was looking at.
 *
 * Pure Kotlin — no view dependencies.
 */
object ProofEngine {

    fun render(approval: Approval): String {
        val sb = StringBuilder()
        sb.appendLine("Action: ${approval.summary}")
        sb.appendLine("Tier: ${approval.tier.name}")
        sb.appendLine("Confirmations required: ${approval.tier.confirmationsRequired}")
        if (approval.tier.requiresImpactReport) {
            val impact = approval.impact
                ?: throw IllegalStateException("CRITICAL approval missing impact report")
            sb.appendLine()
            sb.appendLine("── Impact ──")
            sb.appendLine(impact.summary)
            sb.appendLine()
            if (impact.affectedSurfaces.isNotEmpty()) {
                sb.appendLine("Affected:")
                impact.affectedSurfaces.forEach { sb.appendLine("  - $it") }
                sb.appendLine()
            }
            sb.appendLine("── Rollback plan ──")
            sb.appendLine(impact.rollback)
            impact.estimatedDurationSeconds?.let {
                sb.appendLine()
                sb.appendLine("Estimated duration: ${it}s")
            }
        } else if (approval.tier == RiskTier.SERIOUS) {
            sb.appendLine()
            sb.appendLine("This is a SERIOUS action. Jarvis Prime will not proceed until you confirm twice.")
        }
        return sb.toString().trimEnd()
    }
}
