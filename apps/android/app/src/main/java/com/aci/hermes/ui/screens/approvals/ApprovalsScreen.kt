package com.aci.hermes.ui.screens.approvals

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.aci.hermes.R
import com.aci.hermes.data.model.Approval
import com.aci.hermes.data.model.ApprovalRisk

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ApprovalsScreen(
    viewModel: ApprovalsViewModel,
    onBack: () -> Unit,
    onOpenDetail: (String) -> Unit,
) {
    val state by viewModel.state.collectAsState()
    val snackbarHostState = remember { SnackbarHostState() }

    LaunchedEffect(state.snackbar) {
        state.snackbar?.let {
            snackbarHostState.showSnackbar(it)
            viewModel.consumeSnackbar()
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.approvals_title)) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = stringResource(R.string.action_back))
                    }
                },
            )
        },
        snackbarHost = { SnackbarHost(snackbarHostState) },
    ) { padding ->
        if (state.items.isEmpty()) {
            Column(
                modifier = Modifier.fillMaxSize().padding(padding).padding(24.dp),
                verticalArrangement = Arrangement.Center,
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                Text(stringResource(R.string.approvals_empty), style = MaterialTheme.typography.bodyMedium)
            }
            return@Scaffold
        }
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
            contentPadding = androidx.compose.foundation.layout.PaddingValues(vertical = 12.dp),
        ) {
            if (state.emergency.armed) {
                item {
                    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.errorContainer)) {
                        Text(
                            text = stringResource(R.string.approvals_emergency_blocked),
                            modifier = Modifier.padding(12.dp),
                        )
                    }
                }
            }
            val pending = state.items.filter { it.isPending }
            val decided = state.items.filter { it.isDecided }
            if (pending.isNotEmpty()) {
                item { SectionLabel(stringResource(R.string.approvals_pending_section)) }
                items(pending) { item ->
                    ApprovalCard(
                        approval = item,
                        secondConfirmPending = state.pendingSecondConfirmId == item.id,
                        onOpen = { onOpenDetail(item.id) },
                        onApprove = {
                            viewModel.decide(
                                approval = item,
                                approve = true,
                                impactReportShown = item.risk != ApprovalRisk.CRITICAL,
                            )
                        },
                        onReject = {
                            viewModel.decide(approval = item, approve = false)
                        },
                    )
                }
            }
            if (decided.isNotEmpty()) {
                item { SectionLabel(stringResource(R.string.approvals_decided_section)) }
                items(decided) { item ->
                    ApprovalCard(
                        approval = item,
                        secondConfirmPending = false,
                        onOpen = { onOpenDetail(item.id) },
                        onApprove = {},
                        onReject = {},
                        readOnly = true,
                    )
                }
            }
        }
    }
}

@Composable
private fun SectionLabel(text: String) {
    Text(
        text = text,
        style = MaterialTheme.typography.titleSmall,
        color = MaterialTheme.colorScheme.primary,
        modifier = Modifier.padding(vertical = 4.dp),
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ApprovalCard(
    approval: Approval,
    secondConfirmPending: Boolean,
    onOpen: () -> Unit,
    onApprove: () -> Unit,
    onReject: () -> Unit,
    readOnly: Boolean = false,
) {
    val riskColor = when (approval.risk) {
        ApprovalRisk.LOW -> MaterialTheme.colorScheme.surfaceVariant
        ApprovalRisk.MEDIUM -> MaterialTheme.colorScheme.tertiaryContainer
        ApprovalRisk.HIGH -> MaterialTheme.colorScheme.secondaryContainer
        ApprovalRisk.CRITICAL -> MaterialTheme.colorScheme.errorContainer
    }
    val riskLabel = when (approval.risk) {
        ApprovalRisk.LOW -> stringResource(R.string.approvals_risk_low)
        ApprovalRisk.MEDIUM -> stringResource(R.string.approvals_risk_medium)
        ApprovalRisk.HIGH -> stringResource(R.string.approvals_risk_high)
        ApprovalRisk.CRITICAL -> stringResource(R.string.approvals_risk_critical)
    }
    Card(colors = CardDefaults.cardColors(containerColor = riskColor), onClick = onOpen) {
        Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text(approval.title, style = MaterialTheme.typography.titleMedium)
            Text(approval.description, style = MaterialTheme.typography.bodySmall)
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                AssistChip(onClick = onOpen, label = { Text(riskLabel) })
                AssistChip(onClick = onOpen, label = { Text(approval.decision.name.lowercase()) })
            }
            if (!readOnly) {
                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    val approveLabel = when {
                        approval.risk == ApprovalRisk.CRITICAL ->
                            stringResource(R.string.approvals_critical_impact_title)
                        secondConfirmPending -> stringResource(R.string.approvals_approve) +
                            " ⚠"
                        else -> stringResource(R.string.approvals_approve)
                    }
                    OutlinedButton(
                        onClick = if (approval.risk == ApprovalRisk.CRITICAL) onOpen else onApprove,
                    ) { Text(approveLabel) }
                    OutlinedButton(onClick = onReject) {
                        Text(stringResource(R.string.approvals_reject))
                    }
                }
                if (secondConfirmPending) {
                    Text(
                        text = stringResource(R.string.approvals_confirm_serious),
                        style = MaterialTheme.typography.labelSmall,
                    )
                }
            }
        }
    }
}
