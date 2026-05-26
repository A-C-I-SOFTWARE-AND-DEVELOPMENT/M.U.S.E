package com.aci.hermes.ui.screens.approvals

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.aci.hermes.R
import com.aci.hermes.approvals.Approval
import com.aci.hermes.safety.RiskTier
import com.aci.hermes.ui.theme.JarvisCyan
import com.aci.hermes.ui.theme.JarvisGold
import com.aci.hermes.ui.theme.JarvisRed

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ApprovalsScreen(
    viewModel: ApprovalsViewModel,
    onBack: () -> Unit,
) {
    val state by viewModel.state.collectAsState()
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.approvals_title)) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = stringResource(R.string.action_back))
                    }
                },
            )
        },
    ) { padding ->
        val pending = state.approvals.filter { it.decision == Approval.Decision.PENDING }
        if (pending.isEmpty()) {
            Column(
                modifier = Modifier.fillMaxSize().padding(padding).padding(24.dp),
                horizontalAlignment = androidx.compose.ui.Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.Center,
            ) {
                Text(
                    stringResource(R.string.approvals_empty),
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        } else {
            LazyColumn(
                modifier = Modifier.fillMaxSize().padding(padding).padding(horizontal = 16.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
                contentPadding = PaddingValues(vertical = 12.dp),
            ) {
                items(pending, key = { it.id }) { approval ->
                    ApprovalCard(
                        approval = approval,
                        onReviewImpact = { viewModel.openProof(approval) },
                        onConfirm = { viewModel.confirm(approval) },
                        onApprove = { viewModel.approve(approval) },
                        onReject = { viewModel.reject(approval) },
                    )
                }
            }
        }

        state.openedProof?.let { proof ->
            AlertDialog(
                onDismissRequest = viewModel::closeProof,
                title = { Text(stringResource(R.string.approvals_review_changes)) },
                text = { Text(proof, style = MaterialTheme.typography.bodySmall) },
                confirmButton = {
                    TextButton(onClick = viewModel::closeProof) { Text(stringResource(R.string.action_ok)) }
                },
            )
        }
    }
}

@Composable
private fun ApprovalCard(
    approval: Approval,
    onReviewImpact: () -> Unit,
    onConfirm: () -> Unit,
    onApprove: () -> Unit,
    onReject: () -> Unit,
) {
    val tierColor: Color = when (approval.tier) {
        RiskTier.SAFE -> MaterialTheme.colorScheme.outline
        RiskTier.RISKY -> JarvisCyan
        RiskTier.SERIOUS -> JarvisGold
        RiskTier.CRITICAL -> JarvisRed
    }
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)) {
        Column(modifier = Modifier.padding(16.dp).fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                AssistChip(
                    onClick = {},
                    label = { Text(approval.tier.name) },
                )
                Text(
                    "needs ${approval.tier.confirmationsRequired} confirmation${if (approval.tier.confirmationsRequired == 1) "" else "s"}",
                    style = MaterialTheme.typography.labelSmall,
                    color = tierColor,
                )
            }
            Text(approval.summary, style = MaterialTheme.typography.titleMedium)
            if (approval.description.isNotBlank()) {
                Text(approval.description, style = MaterialTheme.typography.bodyMedium)
            }
            if (approval.tier.requiresImpactReport) {
                OutlinedButton(onClick = onReviewImpact) {
                    Text(stringResource(R.string.approvals_review_changes))
                }
            }
            val remaining = approval.tier.confirmationsRequired - approval.confirmationsCollected
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                if (remaining > 1) {
                    Button(onClick = onConfirm, colors = ButtonDefaults.buttonColors(containerColor = tierColor)) {
                        Text("Confirm ($remaining remaining)")
                    }
                } else {
                    Button(
                        onClick = onApprove,
                        enabled = approval.canApprove || approval.tier.confirmationsRequired == 1,
                        colors = ButtonDefaults.buttonColors(containerColor = tierColor),
                    ) {
                        Text(stringResource(R.string.approvals_approve))
                    }
                }
                OutlinedButton(onClick = onReject) {
                    Text(stringResource(R.string.approvals_reject))
                }
            }
            if (approval.confirmationsCollected > 0 && approval.tier.confirmationsRequired > 1) {
                Text(
                    "${approval.confirmationsCollected} of ${approval.tier.confirmationsRequired} confirmations recorded",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}
