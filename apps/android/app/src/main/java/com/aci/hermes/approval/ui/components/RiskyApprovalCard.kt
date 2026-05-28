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
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.aci.hermes.approval.model.ApprovalCard
import com.aci.hermes.approval.model.ApprovalRiskTier
import com.aci.hermes.approval.model.ApprovalStatus
import com.aci.hermes.ui.components.rememberJarvisHaptics

/**
 * Card UI for [ApprovalRiskTier.RISKY] requests.
 *
 * Buttons:
 *   Approve  — emits an Approved event with one confirmation
 *   Edit     — opens an inline editor for the proposed action
 *   Reject   — always available while pending
 */
@Composable
fun RiskyApprovalCard(
    card: ApprovalCard,
    nowMillis: Long,
    onApprove: (note: String?) -> Unit,
    onEdit: (newAction: String) -> Unit,
    onReject: (reason: String?) -> Unit,
    modifier: Modifier = Modifier
) {
    require(card.tier == ApprovalRiskTier.RISKY)

    var editing by remember { mutableStateOf(false) }
    var draft by remember { mutableStateOf(card.proposedAction) }
    val haptics = rememberJarvisHaptics()

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
            if (editing) {
                OutlinedTextField(
                    value = draft,
                    onValueChange = { draft = it },
                    label = { Text("Proposed action") },
                    modifier = Modifier.fillMaxWidth()
                )
                Row(horizontalArrangement = Arrangement.End, modifier = Modifier.fillMaxWidth()) {
                    TextButton(onClick = { editing = false; draft = card.proposedAction }) {
                        Text("Cancel")
                    }
                    Button(onClick = {
                        editing = false
                        haptics.confirm()
                        onEdit(draft)
                    }) { Text("Save edit") }
                }
            } else {
                Text("Action: ${card.proposedAction}", style = MaterialTheme.typography.bodySmall)
            }
            Spacer(Modifier.height(12.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(
                    enabled = !expired && !finished,
                    onClick = {
                        haptics.confirm()
                        onApprove(card.editedNote)
                    }
                ) { Text("Approve") }
                OutlinedButton(
                    enabled = !expired && !finished,
                    onClick = { editing = true }
                ) { Text("Edit") }
                OutlinedButton(
                    enabled = !finished,
                    colors = ButtonDefaults.outlinedButtonColors(
                        contentColor = MaterialTheme.colorScheme.error
                    ),
                    onClick = {
                        haptics.reject()
                        onReject(null)
                    }
                ) { Text("Reject") }
            }
        }
    }
}
