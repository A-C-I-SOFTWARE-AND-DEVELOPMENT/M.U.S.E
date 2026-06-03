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
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.foundation.BorderStroke
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.aci.hermes.R
import com.aci.hermes.approval.model.ApprovalCard
import com.aci.hermes.approval.model.ApprovalRiskTier
import com.aci.hermes.approval.model.ApprovalStatus
import com.aci.hermes.ui.components.rememberJarvisHaptics
import com.aci.hermes.ui.theme.JarvisAmber
import com.aci.hermes.ui.theme.JarvisTokens

/**
 * Card UI for [ApprovalRiskTier.SERIOUS] requests.
 *
 * Two-step approval: step 2 (the consequence confirmation) is structurally
 * disabled until step 1 has been completed.
 *
 * Reject is always available while pending; an Emergency Stop button is
 * always visible for SERIOUS and CRITICAL tiers.
 */
@Composable
fun SeriousActionCard(
    card: ApprovalCard,
    nowMillis: Long,
    onApproveStep1: () -> Unit,
    onApproveStep2: () -> Unit,
    onReject: (reason: String?) -> Unit,
    onEmergencyStop: () -> Unit,
    modifier: Modifier = Modifier
) {
    require(card.tier == ApprovalRiskTier.SERIOUS)
    val state = card.seriousState
    val expired = card.isExpired(nowMillis)
    val finished = card.status != ApprovalStatus.PENDING
    val haptics = rememberJarvisHaptics()

    Card(
        modifier = modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        // Serious (meaningful but not irreversible) gets an amber frame —
        // loud, but a step below the critical crimson.
        border = BorderStroke(JarvisTokens.BorderFocus, JarvisAmber),
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
            Text(
                stringResource(R.string.approval_label_action, card.proposedAction),
                style = MaterialTheme.typography.bodySmall,
            )
            Spacer(Modifier.height(12.dp))

            Text(
                stringResource(R.string.approval_step1) + if (state.step1Approved) " ✓" else "",
                style = MaterialTheme.typography.labelLarge
            )
            Spacer(Modifier.height(4.dp))
            Button(
                enabled = !expired && !finished && !state.step1Approved,
                onClick = {
                    haptics.confirm()
                    onApproveStep1()
                },
                modifier = Modifier.fillMaxWidth()
            ) { Text(stringResource(R.string.approval_action_approve)) }

            Spacer(Modifier.height(12.dp))
            Text(
                stringResource(R.string.approval_step2_serious) + if (state.step2Approved) " ✓" else "",
                style = MaterialTheme.typography.labelLarge,
                color = if (state.canConfirmStep2) MaterialTheme.colorScheme.onSurface
                        else MaterialTheme.colorScheme.onSurfaceVariant
            )
            Spacer(Modifier.height(4.dp))
            Button(
                enabled = !expired && !finished && state.canConfirmStep2 && !state.step2Approved,
                onClick = {
                    haptics.confirm()
                    onApproveStep2()
                },
                modifier = Modifier.fillMaxWidth()
            ) { Text(stringResource(R.string.approval_action_confirm_consequences)) }

            Spacer(Modifier.height(12.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(
                    enabled = !finished,
                    colors = ButtonDefaults.outlinedButtonColors(
                        contentColor = MaterialTheme.colorScheme.error
                    ),
                    onClick = {
                        haptics.reject()
                        onReject(null)
                    }
                ) { Text(stringResource(R.string.approval_action_reject)) }
                OutlinedButton(
                    enabled = !finished,
                    colors = ButtonDefaults.outlinedButtonColors(
                        contentColor = MaterialTheme.colorScheme.error
                    ),
                    onClick = {
                        haptics.reject()
                        onEmergencyStop()
                    }
                ) { Text(stringResource(R.string.approval_action_emergency_stop)) }
            }
        }
    }
}
