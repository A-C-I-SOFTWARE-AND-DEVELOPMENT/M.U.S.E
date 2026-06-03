package com.aci.hermes.ui.screens.ledger

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import com.aci.hermes.data.model.ledger.LedgerEventDetail
import com.aci.hermes.ui.screens.audit.displayLabel

object LedgerDetailTags {
    const val ROOT = "ledger-detail"
    const val NOT_FOUND = "ledger-detail-not-found"
    const val ROLLBACK_BUTTON = "ledger-rollback-request"
    const val ROLLBACK_QUEUED = "ledger-rollback-queued"
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun LedgerEventDetailScreen(
    viewModel: LedgerEventDetailViewModel,
    onBack: () -> Unit,
) {
    val state by viewModel.state.collectAsState()
    var showRollbackDialog by remember { mutableStateOf(false) }

    Scaffold(
        topBar = {
            androidx.compose.material3.TopAppBar(
                title = { Text("Event") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                },
            )
        },
    ) { padding ->
        val detail = state.detail
        when {
            state.loading -> Box(
                modifier = Modifier.fillMaxSize().padding(padding),
                contentAlignment = Alignment.Center,
            ) { Text("Loading…") }

            detail == null -> Box(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding)
                    .testTag(LedgerDetailTags.NOT_FOUND),
                contentAlignment = Alignment.Center,
            ) { Text("Event not found.") }

            else -> DetailBody(
                detail = detail,
                rollbackState = state.rollback,
                onRequestRollback = { showRollbackDialog = true },
                modifier = Modifier.padding(padding),
            )
        }
    }

    if (showRollbackDialog) {
        RollbackDialog(
            onDismiss = { showRollbackDialog = false },
            onConfirm = { reason ->
                viewModel.requestRollback(reason)
                showRollbackDialog = false
            },
        )
    }
}

@Composable
private fun DetailBody(
    detail: LedgerEventDetail,
    rollbackState: RollbackRequestState,
    onRequestRollback: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp)
            .testTag(LedgerDetailTags.ROOT),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Section(title = "What happened") {
            Text(detail.summary.ifBlank { detail.kind }, style = MaterialTheme.typography.bodyMedium)
            Text(
                "${detail.category.displayLabel()} · ${detail.riskTier.displayLabel()} · " +
                    formatLedgerTimestamp(detail.timestamp) +
                    (detail.worker?.let { " · $it" } ?: ""),
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Text(
                "Job ${detail.jobId}",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }

        if (detail.payload.isNotEmpty()) {
            Section(title = "Details (redacted)") {
                detail.payload.forEach { (k, v) ->
                    Text(
                        "$k: $v",
                        style = MaterialTheme.typography.bodySmall,
                    )
                }
            }
        }

        if (detail.files.isNotEmpty()) {
            Section(title = "Files") {
                detail.files.forEach { Text(it, style = MaterialTheme.typography.bodySmall) }
            }
        }

        detail.diff?.let { diff ->
            Section(title = "Linked diff") {
                diff.body?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
                diff.files.forEach { Text(it, style = MaterialTheme.typography.bodySmall) }
            }
        }

        if (detail.evidence.isNotEmpty()) {
            Section(title = "Linked evidence") {
                detail.evidence.forEach { ev ->
                    Text(ev.title, style = MaterialTheme.typography.titleSmall)
                    if (ev.body.isNotBlank()) {
                        Text(ev.body, style = MaterialTheme.typography.bodySmall)
                    }
                    ev.sourcePath?.let {
                        Text(
                            it,
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
            }
        }

        detail.rollback?.let { rb ->
            Section(title = "Rollback plan") {
                if (rb.summary.isNotBlank()) {
                    Text(rb.summary, style = MaterialTheme.typography.bodyMedium)
                }
                rb.steps.forEach { Text("• $it", style = MaterialTheme.typography.bodySmall) }
            }
        }

        // Owner-gated rollback request.
        when (val rs = rollbackState) {
            is RollbackRequestState.Queued -> Text(
                "Rollback requested — pending owner approval (Approvals → ${rs.approvalId}).",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.primary,
                modifier = Modifier.testTag(LedgerDetailTags.ROLLBACK_QUEUED),
            )
            is RollbackRequestState.Failed -> Text(
                rs.message,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.error,
            )
            is RollbackRequestState.Submitting -> Text(
                "Submitting rollback request…",
                style = MaterialTheme.typography.bodyMedium,
            )
            RollbackRequestState.Idle -> if (detail.rollbackAvailable) {
                OutlinedButton(
                    onClick = onRequestRollback,
                    modifier = Modifier
                        .fillMaxWidth()
                        .testTag(LedgerDetailTags.ROLLBACK_BUTTON),
                ) { Text("Request rollback") }
            }
        }
    }
}

@Composable
private fun Section(title: String, content: @Composable () -> Unit) {
    Card(colors = CardDefaults.cardColors()) {
        Column(
            modifier = Modifier.fillMaxWidth().padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Text(
                title,
                style = MaterialTheme.typography.labelLarge,
                color = MaterialTheme.colorScheme.primary,
            )
            content()
        }
    }
}

@Composable
private fun RollbackDialog(onDismiss: () -> Unit, onConfirm: (String?) -> Unit) {
    var reason by remember { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Request rollback") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(
                    "This queues an owner-gated approval. Nothing is rolled back until " +
                        "you approve it with your owner phrase in Approvals.",
                    style = MaterialTheme.typography.bodySmall,
                )
                OutlinedTextField(
                    value = reason,
                    onValueChange = { reason = it },
                    label = { Text("Reason (optional)") },
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        },
        confirmButton = {
            Button(onClick = { onConfirm(reason.ifBlank { null }) }) { Text("Queue request") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } },
    )
}
