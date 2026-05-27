package com.aci.hermes.approval.ui.components

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.aci.hermes.approval.model.ApprovalCard
import com.aci.hermes.approval.model.ApprovalRiskTier
import com.aci.hermes.approval.model.ApprovalStatus

/**
 * Card UI for [ApprovalRiskTier.CRITICAL] requests.
 *
 * Requires:
 *   * an impact report describing blast radius and reversibility
 *   * a rollback plan with steps + estimated duration
 *   * step 1 approval
 *   * step 2 approval
 *
 * Approve buttons are structurally disabled until each precondition is met.
 */
@Composable
fun CriticalActionCard(
    card: ApprovalCard,
    nowMillis: Long,
    onApproveStep1: () -> Unit,
    onApproveStep2: () -> Unit,
    onReject: (reason: String?) -> Unit,
    onEmergencyStop: () -> Unit,
    modifier: Modifier = Modifier
) {
    require(card.tier == ApprovalRiskTier.CRITICAL)
    val cs = card.criticalState
    val expired = card.isExpired(nowMillis)
    val finished = card.status != ApprovalStatus.PENDING

    Card(
        modifier = modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)
    ) {
        Column(Modifier.padding(16.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                TierBadge(card.tier)
                Spacer(Modifier.height(0.dp).fillMaxWidth().weight(1f))
                StatusBadge(if (expired && !finished) ApprovalStatus.EXPIRED else card.status)
            }
            Spacer(Modifier.height(8.dp))
            Text(card.title, style = MaterialTheme.typography.titleMedium)
            Text(card.summary, style = MaterialTheme.typography.bodyMedium)
            Spacer(Modifier.height(8.dp))
            Text("Action: ${card.proposedAction}", style = MaterialTheme.typography.bodySmall)

            Spacer(Modifier.height(12.dp))
            HorizontalDivider()
            Spacer(Modifier.height(8.dp))

            Text("Impact report", style = MaterialTheme.typography.labelLarge)
            val report = cs.impactReport
            if (report != null) {
                Text(report.summary, style = MaterialTheme.typography.bodySmall)
                Text(
                    "Surfaces: ${report.impactedSurfaces.joinToString(", ")}",
                    style = MaterialTheme.typography.bodySmall
                )
                Text(
                    "Blast radius: ${report.blastRadius} · " +
                        if (report.reversible) "reversible" else "NOT reversible",
                    style = MaterialTheme.typography.bodySmall
                )
            } else {
                Text(
                    "Impact report required before approval.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.error
                )
            }

            Spacer(Modifier.height(8.dp))
            Text("Rollback plan", style = MaterialTheme.typography.labelLarge)
            val plan = cs.rollbackPlan
            if (plan != null) {
                plan.steps.forEachIndexed { i, step ->
                    Text("${i + 1}. $step", style = MaterialTheme.typography.bodySmall)
                }
                Text(
                    "Est duration: ${plan.estimatedDurationSeconds}s · " +
                        if (plan.verified) "verified" else "UNVERIFIED",
                    style = MaterialTheme.typography.bodySmall
                )
            } else {
                Text(
                    "Rollback plan required before approval.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.error
                )
            }

            Spacer(Modifier.height(12.dp))

            Text(
                "Step 1: approve" + if (cs.step1Approved) " ✓" else "",
                style = MaterialTheme.typography.labelLarge
            )
            Spacer(Modifier.height(4.dp))
            Button(
                enabled = !expired && !finished && cs.canApproveStep1 && !cs.step1Approved,
                onClick = onApproveStep1,
                modifier = Modifier.fillMaxWidth()
            ) { Text("Approve") }

            Spacer(Modifier.height(12.dp))
            Text(
                "Step 2: final confirmation" + if (cs.step2Approved) " ✓" else "",
                style = MaterialTheme.typography.labelLarge
            )
            Spacer(Modifier.height(4.dp))
            Button(
                enabled = !expired && !finished && cs.canApproveStep2 && !cs.step2Approved,
                onClick = onApproveStep2,
                modifier = Modifier.fillMaxWidth()
            ) { Text("Final confirmation") }

            Spacer(Modifier.height(12.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(
                    enabled = !finished,
                    colors = ButtonDefaults.outlinedButtonColors(
                        contentColor = MaterialTheme.colorScheme.error
                    ),
                    onClick = { onReject(null) }
                ) { Text("Reject") }
                OutlinedButton(
                    enabled = !finished,
                    colors = ButtonDefaults.outlinedButtonColors(
                        contentColor = MaterialTheme.colorScheme.error
                    ),
                    onClick = onEmergencyStop
                ) { Text("Emergency stop") }
            }
        }
    }
}
