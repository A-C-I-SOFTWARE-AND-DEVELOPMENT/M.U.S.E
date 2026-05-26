package com.aci.hermes.ui.screens.approvals

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
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
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.aci.hermes.R
import com.aci.hermes.data.model.ApprovalRisk

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ApprovalDetailScreen(
    viewModel: ApprovalDetailViewModel,
    onBack: () -> Unit,
) {
    val state by viewModel.state.collectAsState()
    val snackbarHostState = remember { SnackbarHostState() }
    val scroll = rememberScrollState()

    LaunchedEffect(state.message) {
        state.message?.let {
            snackbarHostState.showSnackbar(it)
            viewModel.consumeMessage()
        }
    }
    LaunchedEffect(state.finished) { if (state.finished) onBack() }
    LaunchedEffect(scroll.value, scroll.maxValue) {
        if (scroll.maxValue > 0 && scroll.value >= scroll.maxValue - 16) {
            viewModel.markImpactReportShown()
        } else if (scroll.maxValue == 0) {
            viewModel.markImpactReportShown()
        }
    }

    val approval = state.approval
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
        if (approval == null) {
            Text(
                stringResource(R.string.approvals_empty),
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding)
                    .padding(24.dp),
            )
            return@Scaffold
        }
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 16.dp, vertical = 12.dp)
                .verticalScroll(scroll),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Text(approval.title, style = MaterialTheme.typography.headlineSmall)
            Text(approval.description, style = MaterialTheme.typography.bodyMedium)
            AssistChip(onClick = {}, label = { Text(approval.risk.name) })

            if (approval.risk == ApprovalRisk.CRITICAL) {
                ImpactReportCard(approval)
            }
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                OutlinedButton(
                    onClick = { viewModel.decide(approve = true) },
                    enabled = approval.isPending,
                ) { Text(stringResource(R.string.approvals_approve)) }
                OutlinedButton(
                    onClick = { viewModel.decide(approve = false) },
                    enabled = approval.isPending,
                ) { Text(stringResource(R.string.approvals_reject)) }
            }
            if (state.secondConfirmPending) {
                Text(
                    text = stringResource(R.string.approvals_confirm_serious),
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.primary,
                )
            }
        }
    }
}

@Composable
private fun ImpactReportCard(approval: com.aci.hermes.data.model.Approval) {
    val impact = approval.impact ?: return
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.errorContainer)) {
        Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(
                stringResource(R.string.approvals_critical_impact_title),
                style = MaterialTheme.typography.titleMedium,
                color = MaterialTheme.colorScheme.onErrorContainer,
            )
            Text(
                stringResource(R.string.approvals_critical_impact_body),
                style = MaterialTheme.typography.bodyMedium,
            )
            Text(impact.summary, style = MaterialTheme.typography.bodySmall)
            impact.items.forEach { item ->
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                ) {
                    Text(item.label, style = MaterialTheme.typography.bodySmall)
                    Text(item.value, style = MaterialTheme.typography.bodySmall)
                }
            }
            Text(
                text = "Blast radius: ${impact.blastRadius}",
                style = MaterialTheme.typography.labelSmall,
            )
            Text(
                text = if (impact.reversible) "Reversible" else "Irreversible",
                style = MaterialTheme.typography.labelSmall,
            )
        }
    }
}
