package com.aci.hermes.ui.screens.gateway

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import com.aci.hermes.data.gateway.ApprovalRiskClass
import com.aci.hermes.data.gateway.GatewayConnectionState
import com.aci.hermes.data.gateway.IconState
import com.aci.hermes.data.gateway.PendingApprovalSummary
import com.aci.hermes.data.gateway.TranscriptTurn
import com.aci.hermes.data.gateway.WorkerRuntime

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun GatewayScreen(
    viewModel: GatewayViewModel,
    onBack: () -> Unit,
) {
    val state by viewModel.state.collectAsState()
    val snackbar by viewModel.snackbar.collectAsState()
    val input by viewModel.userInput.collectAsState()
    val snackbarHostState = remember { SnackbarHostState() }

    LaunchedEffect(snackbar) {
        snackbar?.let {
            snackbarHostState.showSnackbar(it)
            viewModel.consumeSnackbar()
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Jarvis Gateway") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                },
                actions = {
                    IconButton(onClick = viewModel::reconnect) {
                        Icon(Icons.Default.Refresh, contentDescription = "Reconnect")
                    }
                    IconButton(onClick = viewModel::triggerEmergencyStop) {
                        Icon(
                            Icons.Default.Stop,
                            contentDescription = "Emergency stop",
                            tint = MaterialTheme.colorScheme.error,
                        )
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
                .padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
            contentPadding = androidx.compose.foundation.layout.PaddingValues(vertical = 12.dp),
        ) {
            item { ConnectionCard(state.connection, state.iconState, state.iconDetail) }
            state.emergencyStop?.let { stop ->
                item { EmergencyStopBanner(reason = stop.reason, by = stop.triggeredBy) }
            }

            item { SectionTitle("Transcript") }
            if (state.transcript.isEmpty() && state.pendingDeltas.isEmpty()) {
                item { EmptyText("No turns yet. Send a message below.") }
            } else {
                items(state.transcript) { turn -> TranscriptRow(turn) }
                items(state.pendingDeltas.entries.toList()) { (_, text) ->
                    TranscriptRow(
                        turn = TranscriptTurn(
                            role = TranscriptTurn.Role.JARVIS,
                            text = "$text▌",
                            correlationId = null,
                            occurredAt = "",
                        ),
                    )
                }
            }
            item { ComposeRow(input, viewModel::onUserInputChanged, viewModel::sendUserMessage) }

            item { SectionTitle("Pending approvals") }
            if (state.pendingApprovals.isEmpty()) {
                item { EmptyText("Nothing waiting on you.") }
            } else {
                items(state.pendingApprovals) { approval ->
                    ApprovalCard(
                        approval = approval,
                        onGrant = { viewModel.grantApproval(approval) },
                        onReject = { viewModel.rejectApproval(approval) },
                    )
                }
            }

            item { SectionTitle("Tasks") }
            if (state.tasks.isEmpty()) {
                item { EmptyText("No tasks on the spine.") }
            } else {
                items(state.tasks) { task ->
                    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)) {
                        Column(Modifier.padding(12.dp)) {
                            Text(task.title, style = MaterialTheme.typography.titleSmall)
                            Text(
                                "status: ${task.status}" +
                                    (task.workerKind?.let { " · worker: $it" }.orEmpty()),
                                style = MaterialTheme.typography.bodySmall,
                            )
                            task.summary?.takeIf { it.isNotBlank() }?.let {
                                Text(it, style = MaterialTheme.typography.bodySmall)
                            }
                        }
                    }
                }
            }

            item { SectionTitle("Workers") }
            if (state.workers.isEmpty()) {
                item { EmptyText("No workers running.") }
            } else {
                items(state.workers) { worker -> WorkerCard(worker) }
            }

            item { SectionTitle("Memory") }
            if (state.memory.isEmpty()) {
                item { EmptyText("No memory entries yet.") }
            } else {
                items(state.memory) { entry ->
                    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)) {
                        Column(Modifier.padding(12.dp)) {
                            Text(entry.kind, style = MaterialTheme.typography.labelMedium)
                            Text(entry.text, style = MaterialTheme.typography.bodyMedium)
                        }
                    }
                }
            }

            item { SectionTitle("Audit log") }
            if (state.auditLog.isEmpty()) {
                item { EmptyText("No audit records yet.") }
            } else {
                items(state.auditLog.takeLast(10).reversed()) { record ->
                    Text(
                        "${record.action} · ${record.actor} · ${record.outcome}",
                        style = MaterialTheme.typography.bodySmall,
                        fontFamily = FontFamily.Monospace,
                    )
                }
            }
        }
    }
}

@Composable
private fun ConnectionCard(
    connection: GatewayConnectionState,
    iconState: IconState,
    iconDetail: String?,
) {
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Surface(
                    shape = CircleShape,
                    color = colorFor(iconState),
                    modifier = Modifier.size(12.dp),
                ) {}
                Text(text = label(connection), style = MaterialTheme.typography.titleMedium)
            }
            Text("icon: ${iconState.name.lowercase()}", style = MaterialTheme.typography.bodySmall)
            iconDetail?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
        }
    }
}

@Composable
private fun colorFor(state: IconState) = when (state) {
    IconState.IDLE -> MaterialTheme.colorScheme.primary
    IconState.LISTENING, IconState.THINKING, IconState.SPEAKING -> MaterialTheme.colorScheme.tertiary
    IconState.WAITING_APPROVAL -> MaterialTheme.colorScheme.secondary
    IconState.ERROR -> MaterialTheme.colorScheme.error
    IconState.OFFLINE -> MaterialTheme.colorScheme.outline
}

private fun label(state: GatewayConnectionState): String = when (state) {
    GatewayConnectionState.Idle -> "Idle"
    is GatewayConnectionState.Connecting -> "Connecting · ${state.mode.name.lowercase()}"
    is GatewayConnectionState.Connected ->
        "Connected · ${state.mode.name.lowercase()} · ${state.protocolVersion}"
    is GatewayConnectionState.Disconnected -> "Disconnected · ${state.reason}"
    is GatewayConnectionState.Failed -> "Failed · ${state.reason}"
}

@Composable
private fun EmergencyStopBanner(reason: String, by: String) {
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.errorContainer)) {
        Column(Modifier.padding(12.dp)) {
            Text("Emergency stop active", style = MaterialTheme.typography.titleSmall)
            Text("reason: $reason", style = MaterialTheme.typography.bodySmall)
            Text("by: $by", style = MaterialTheme.typography.bodySmall)
        }
    }
}

@Composable
private fun SectionTitle(text: String) {
    Text(
        text = text,
        style = MaterialTheme.typography.titleMedium,
        color = MaterialTheme.colorScheme.primary,
        modifier = Modifier.padding(top = 8.dp),
    )
}

@Composable
private fun EmptyText(text: String) {
    Text(text, style = MaterialTheme.typography.bodyMedium)
}

@Composable
private fun TranscriptRow(turn: TranscriptTurn) {
    val color = when (turn.role) {
        TranscriptTurn.Role.USER -> MaterialTheme.colorScheme.primaryContainer
        TranscriptTurn.Role.JARVIS -> MaterialTheme.colorScheme.surfaceVariant
    }
    Card(colors = CardDefaults.cardColors(containerColor = color)) {
        Column(Modifier.padding(12.dp)) {
            Text(turn.role.name, style = MaterialTheme.typography.labelMedium)
            Text(turn.text, style = MaterialTheme.typography.bodyMedium)
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ComposeRow(
    input: String,
    onChange: (String) -> Unit,
    onSend: () -> Unit,
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        OutlinedTextField(
            value = input,
            onValueChange = onChange,
            modifier = Modifier.weight(1f),
            placeholder = { Text("Say something to mock Jarvis…") },
            singleLine = true,
        )
        IconButton(onClick = onSend) {
            Icon(Icons.AutoMirrored.Filled.Send, contentDescription = "Send")
        }
    }
}

@Composable
private fun ApprovalCard(
    approval: PendingApprovalSummary,
    onGrant: () -> Unit,
    onReject: () -> Unit,
) {
    val container = when (approval.riskClass) {
        ApprovalRiskClass.STANDARD -> MaterialTheme.colorScheme.surfaceVariant
        ApprovalRiskClass.SERIOUS -> MaterialTheme.colorScheme.tertiaryContainer
        ApprovalRiskClass.CRITICAL -> MaterialTheme.colorScheme.errorContainer
    }
    Card(colors = CardDefaults.cardColors(containerColor = container)) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                AssistChip(onClick = {}, label = { Text(approval.riskClass.name.lowercase()) })
                Text(approval.actionId, style = MaterialTheme.typography.labelMedium)
            }
            Text(approval.summary, style = MaterialTheme.typography.bodyMedium)
            if (approval.confirmationsRequired > 1) {
                Text(
                    "confirmations: ${approval.confirmationsSeen}/${approval.confirmationsRequired}",
                    style = MaterialTheme.typography.bodySmall,
                )
            }
            approval.impactReport?.let { impact ->
                HorizontalDivider()
                Text("Impact report", style = MaterialTheme.typography.labelMedium)
                Text(impact.summary, style = MaterialTheme.typography.bodySmall)
                Text("blast radius: ${impact.blastRadius}", style = MaterialTheme.typography.bodySmall)
                Text("reversibility: ${impact.reversibility}", style = MaterialTheme.typography.bodySmall)
                Text("rollback: ${impact.rollbackPlan}", style = MaterialTheme.typography.bodySmall)
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = onGrant) {
                    Text(
                        when (approval.riskClass) {
                            ApprovalRiskClass.STANDARD -> "Grant"
                            ApprovalRiskClass.SERIOUS ->
                                "Confirm serious (${approval.confirmationsSeen + 1}/${approval.confirmationsRequired})"
                            ApprovalRiskClass.CRITICAL -> "Confirm critical with impact"
                        },
                    )
                }
                OutlinedButton(onClick = onReject) { Text("Reject") }
            }
        }
    }
}

@Composable
private fun WorkerCard(worker: WorkerRuntime) {
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(worker.title, style = MaterialTheme.typography.titleSmall)
            Text("kind: ${worker.kind}", style = MaterialTheme.typography.bodySmall)
            worker.terminal?.let {
                Text("state: ${it.name.lowercase()}", style = MaterialTheme.typography.bodySmall)
            }
            Box(Modifier.fillMaxWidth()) {
                LinearProgressIndicator(
                    progress = { worker.fraction.coerceIn(0f, 1f) },
                    modifier = Modifier.fillMaxWidth(),
                )
            }
            worker.message?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
        }
    }
}
