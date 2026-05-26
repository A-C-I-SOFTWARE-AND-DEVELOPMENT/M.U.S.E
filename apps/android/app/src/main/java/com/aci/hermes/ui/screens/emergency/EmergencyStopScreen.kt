package com.aci.hermes.ui.screens.emergency

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.ContentCopy
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
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.unit.dp
import com.aci.hermes.data.emergency.EmergencyStopAuditEvent
import com.aci.hermes.data.emergency.EmergencyStopState
import com.aci.hermes.ui.components.CriticalActionCard
import com.aci.hermes.ui.components.EmergencyStopBanner
import com.aci.hermes.ui.components.EmergencyStopConfirmationDialog
import com.aci.hermes.ui.components.ResumeApprovalDialog
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

const val EMERGENCY_SCREEN_TAG = "emergency_stop_screen"
const val AUDIT_LIST_TAG = "emergency_audit_list"

/**
 * Jarvis Control screen — the dedicated entry point for emergency
 * stop. Surfaces current level, banner, audit log, and an export
 * action for the audit log.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun EmergencyStopScreen(
    viewModel: EmergencyStopViewModel,
    onBack: () -> Unit,
) {
    val state by viewModel.state.collectAsState()
    val snackbarHostState = remember { SnackbarHostState() }
    val clipboard = LocalClipboardManager.current

    LaunchedEffect(state.snackbar) {
        state.snackbar?.let {
            snackbarHostState.showSnackbar(it)
            viewModel.consumeSnackbar()
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Jarvis Prime Control") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = null)
                    }
                },
                actions = {
                    IconButton(onClick = {
                        clipboard.setText(AnnotatedString(viewModel.exportAuditJson()))
                    }) {
                        Icon(Icons.Filled.ContentCopy, contentDescription = "Export audit JSON")
                    }
                },
            )
        },
        snackbarHost = { SnackbarHost(snackbarHostState) },
    ) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 16.dp)
                .testTag(EMERGENCY_SCREEN_TAG),
            verticalArrangement = Arrangement.spacedBy(12.dp),
            contentPadding = androidx.compose.foundation.layout.PaddingValues(vertical = 12.dp),
        ) {
            item {
                EmergencyStopBanner(state = state.state, onOpenControl = { /* already here */ })
            }
            item {
                CriticalActionCard(
                    state = state.state,
                    onEngageStop = viewModel::openConfirmDialog,
                    onEscalate = viewModel::openConfirmDialog,
                    onRequestResume = { viewModel.requestResume() },
                    onOpenControl = { /* already on screen */ },
                )
            }
            item { LevelSummaryCard(state = state.state) }
            item {
                Text(
                    text = "Audit log",
                    style = MaterialTheme.typography.titleMedium,
                    modifier = Modifier.padding(top = 8.dp),
                )
            }
            if (state.audit.isEmpty()) {
                item {
                    Text(
                        text = "No events yet.",
                        style = MaterialTheme.typography.bodyMedium,
                    )
                }
            } else {
                items(state.audit) { entry -> AuditRow(entry) }
            }
            item {
                OutlinedButton(
                    onClick = { viewModel.deescalate(EmergencyStopState.SOFT_PAUSE) },
                    enabled = state.state.severity > EmergencyStopState.SOFT_PAUSE.severity,
                ) { Text("Step down to SOFT PAUSE") }
            }
        }
    }

    if (state.showConfirmDialog) {
        EmergencyStopConfirmationDialog(
            currentState = state.state,
            onDismiss = viewModel::closeConfirmDialog,
            onConfirm = { target, reason -> viewModel.engage(target, reason) },
        )
    }
    if (state.showResumeDialog) {
        ResumeApprovalDialog(
            currentState = state.state,
            requestedBy = state.pendingApproval?.requestedBy,
            onDismiss = viewModel::closeResumeDialog,
            onApprove = viewModel::approveResume,
            onDeny = viewModel::denyResume,
        )
    }
}

@Composable
private fun LevelSummaryCard(state: EmergencyStopState) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant,
        ),
    ) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(
                text = "State: ${state.name}",
                style = MaterialTheme.typography.titleSmall,
            )
            Text(
                text = when (state) {
                    EmergencyStopState.INACTIVE ->
                        "All actions allowed. Engage emergency stop from here, the dashboard, " +
                            "or the persistent icon."
                    EmergencyStopState.SOFT_PAUSE ->
                        "New task starts are blocked. In-flight work continues."
                    EmergencyStopState.HARD_STOP ->
                        "Sends, deletes, pushes, and deploys are blocked. Reads still work."
                    EmergencyStopState.LOCKDOWN ->
                        "Only status, audit, export, and resume are allowed."
                },
                style = MaterialTheme.typography.bodyMedium,
            )
        }
    }
}

@Composable
private fun AuditRow(entry: EmergencyStopAuditEvent) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .testTag(AUDIT_LIST_TAG),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant,
        ),
    ) {
        Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text(
                text = "${formatTime(entry.timestamp)}  ${entry.type.name}",
                style = MaterialTheme.typography.titleSmall,
            )
            Text(
                text = "${entry.from.name} → ${entry.to.name}",
                style = MaterialTheme.typography.bodyMedium,
            )
            Text(
                text = "source: ${entry.source}" +
                    (entry.reason?.let { " · reason: $it" } ?: ""),
                style = MaterialTheme.typography.bodySmall,
            )
        }
    }
}

private fun formatTime(ts: Long): String {
    val fmt = SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.US)
    return fmt.format(Date(ts))
}
