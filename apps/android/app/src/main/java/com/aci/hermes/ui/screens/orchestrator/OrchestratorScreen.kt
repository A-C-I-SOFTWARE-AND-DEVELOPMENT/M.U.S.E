package com.aci.hermes.ui.screens.orchestrator

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.BugReport
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExtendedFloatingActionButton
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
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
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.aci.hermes.R
import com.aci.hermes.data.model.AiToolProfile
import com.aci.hermes.data.model.ApprovalState
import com.aci.hermes.data.model.HermesTask
import com.aci.hermes.data.model.RiskTier
import com.aci.hermes.data.model.TargetTool
import com.aci.hermes.data.model.TaskSection
import com.aci.hermes.data.model.TaskStatus
import com.aci.hermes.data.model.WorkerPhase
import com.aci.hermes.data.model.approvalsRoute
import com.aci.hermes.data.model.auditRoute

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun OrchestratorScreen(
    viewModel: OrchestratorViewModel,
    onOpenTask: (taskId: String?) -> Unit,
    onPrepareHandoff: (target: TargetTool) -> Unit,
    onOpenSettings: () -> Unit,
    onOpenDiagnostics: () -> Unit,
    onOpenApprovals: (taskId: String) -> Unit = onOpenTask,
    onOpenAudit: (route: String) -> Unit = { onOpenTask(it) },
) {
    val state by viewModel.state.collectAsState()
    val snackbarHostState = remember { SnackbarHostState() }
    var overflowOpen by remember { mutableStateOf(false) }

    LaunchedEffect(state.snackbar) {
        state.snackbar?.let {
            snackbarHostState.showSnackbar(it)
            viewModel.consumeSnackbar()
        }
    }

    LaunchedEffect(Unit) {
        viewModel.refreshServiceStatus()
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.orchestrator_title)) },
                actions = {
                    IconButton(onClick = onOpenSettings) {
                        Icon(Icons.Default.Settings, contentDescription = stringResource(R.string.nav_settings))
                    }
                    Box {
                        IconButton(onClick = { overflowOpen = true }) {
                            Icon(Icons.Default.MoreVert, contentDescription = null)
                        }
                        DropdownMenu(
                            expanded = overflowOpen,
                            onDismissRequest = { overflowOpen = false },
                        ) {
                            DropdownMenuItem(
                                text = { Text(stringResource(R.string.nav_diagnostics)) },
                                onClick = {
                                    overflowOpen = false
                                    onOpenDiagnostics()
                                },
                                leadingIcon = {
                                    Icon(Icons.Default.BugReport, contentDescription = null)
                                },
                            )
                        }
                    }
                },
            )
        },
        floatingActionButton = {
            ExtendedFloatingActionButton(
                onClick = { onOpenTask(null) },
                icon = { Icon(Icons.Default.Add, contentDescription = null) },
                text = { Text(stringResource(R.string.orchestrator_new_task)) },
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
            if (state.emergencyStopActive) {
                item { EmergencyStopBanner(onClear = viewModel::clearEmergencyStop) }
            }
            item { StatusCard(state, viewModel::startService, viewModel::stopService) }

            item { SectionTitle(stringResource(R.string.orchestrator_worker_lanes_title)) }
            item { WorkerLanesCard(state.workerLanes) }

            item {
                SectionTitle(stringResource(R.string.orchestrator_tools_title))
            }
            items(state.tools) { profile ->
                ToolCard(
                    profile = profile,
                    allowExternal = state.allowExternalAppOpening,
                    onPrepareHandoff = { onPrepareHandoff(profile.targetTool) },
                    onOpenTool = { viewModel.openToolFor(profile) },
                )
            }

            // Each Tasks-screen section is rendered in a fixed order so the user
            // sees the same shape every time even when a bucket is empty.
            TaskSection.entries.forEach { sectionKey ->
                item {
                    SectionTitle(stringResource(sectionTitleRes(sectionKey)))
                }
                val sectionTasks = state.sections[sectionKey].orEmpty()
                if (sectionTasks.isEmpty()) {
                    item {
                        Text(
                            text = stringResource(sectionEmptyRes(sectionKey)),
                            style = MaterialTheme.typography.bodyMedium,
                            modifier = Modifier.padding(vertical = 4.dp),
                        )
                    }
                } else {
                    items(sectionTasks, key = { it.id }) { task ->
                        TaskRow(
                            task = task,
                            onTap = { onOpenTask(task.id) },
                            onCopyPrompt = { viewModel.copyPromptForTask(task) },
                            onOpenApprovals = onOpenApprovals,
                            onOpenAudit = onOpenAudit,
                        )
                    }
                }
            }

            if (state.showSafetyWarnings) {
                item { SafetyBanner() }
            }
        }
    }
}

private fun sectionTitleRes(section: TaskSection): Int = when (section) {
    TaskSection.ACTIVE -> R.string.orchestrator_section_active
    TaskSection.WAITING_FOR_APPROVAL -> R.string.orchestrator_section_waiting_for_approval
    TaskSection.BLOCKED -> R.string.orchestrator_section_blocked
    TaskSection.FAILED -> R.string.orchestrator_section_failed
    TaskSection.COMPLETE -> R.string.orchestrator_section_complete
}

private fun sectionEmptyRes(section: TaskSection): Int = when (section) {
    TaskSection.ACTIVE -> R.string.orchestrator_section_active_empty
    TaskSection.WAITING_FOR_APPROVAL -> R.string.orchestrator_section_waiting_empty
    TaskSection.BLOCKED -> R.string.orchestrator_section_blocked_empty
    TaskSection.FAILED -> R.string.orchestrator_section_failed_empty
    TaskSection.COMPLETE -> R.string.orchestrator_section_complete_empty
}

@Composable
private fun EmergencyStopBanner(onClear: () -> Unit) {
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.errorContainer)) {
        Row(
            modifier = Modifier.padding(16.dp).fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Icon(
                Icons.Default.Warning,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.onErrorContainer,
            )
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    stringResource(R.string.orchestrator_emergency_stop_title),
                    style = MaterialTheme.typography.titleSmall,
                    color = MaterialTheme.colorScheme.onErrorContainer,
                )
                Text(
                    stringResource(R.string.orchestrator_emergency_stop_body),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onErrorContainer,
                )
            }
            OutlinedButton(onClick = onClear) {
                Text(stringResource(R.string.orchestrator_emergency_stop_clear))
            }
        }
    }
}

@Composable
private fun StatusCard(
    state: OrchestratorUiState,
    onStart: () -> Unit,
    onStop: () -> Unit,
) {
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Surface(
                    shape = CircleShape,
                    color = if (state.serviceRunning) MaterialTheme.colorScheme.primary
                            else MaterialTheme.colorScheme.error,
                    modifier = Modifier.size(12.dp),
                ) {}
                Text(
                    text = if (state.serviceRunning) stringResource(R.string.orchestrator_status_running)
                           else stringResource(R.string.orchestrator_status_stopped),
                    style = MaterialTheme.typography.titleMedium,
                )
            }
            StatusRow(stringResource(R.string.orchestrator_status_mode_label), "Local Subscription Tools")
            StatusRow(stringResource(R.string.orchestrator_status_billing_label), stringResource(R.string.orchestrator_status_billing_value))
            StatusRow(stringResource(R.string.orchestrator_status_export_label), stringResource(R.string.orchestrator_status_export_value))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                if (state.serviceRunning) {
                    OutlinedButton(onClick = onStop) { Text(stringResource(R.string.orchestrator_stop_service)) }
                } else {
                    Button(onClick = onStart) { Text(stringResource(R.string.orchestrator_start_service)) }
                }
            }
        }
    }
}

@Composable
private fun StatusRow(label: String, value: String) {
    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
        Text(label, style = MaterialTheme.typography.bodyMedium)
        Text(value, style = MaterialTheme.typography.bodyMedium)
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
private fun WorkerLanesCard(lanes: List<WorkerLaneState>) {
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(
                stringResource(R.string.orchestrator_worker_lanes_subtitle),
                style = MaterialTheme.typography.bodySmall,
            )
            LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                items(lanes) { lane ->
                    WorkerLaneCard(lane)
                }
            }
        }
    }
}

@Composable
private fun WorkerLaneCard(lane: WorkerLaneState) {
    val container = if (lane.isBusy) MaterialTheme.colorScheme.primaryContainer
                    else MaterialTheme.colorScheme.surface
    Card(
        colors = CardDefaults.cardColors(containerColor = container),
        modifier = Modifier.width(160.dp),
    ) {
        Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text(workerPhaseLabel(lane.phase), style = MaterialTheme.typography.titleSmall)
            Text(
                text = if (lane.isBusy) {
                    stringResource(R.string.orchestrator_worker_lane_active, lane.activeTasks.size)
                } else {
                    stringResource(R.string.orchestrator_worker_lane_idle)
                },
                style = MaterialTheme.typography.bodySmall,
            )
            val preview = lane.activeTasks.firstOrNull()
            if (preview != null) {
                Text(
                    text = preview.title.ifBlank { stringResource(R.string.orchestrator_untitled_task) },
                    style = MaterialTheme.typography.bodySmall,
                    maxLines = 2,
                )
            }
        }
    }
}

private fun workerPhaseLabel(phase: WorkerPhase): String = when (phase) {
    WorkerPhase.PLANNER -> "Planner"
    WorkerPhase.NAVIGATOR -> "Navigator"
    WorkerPhase.EDITOR -> "Editor"
    WorkerPhase.EXECUTOR -> "Executor"
    WorkerPhase.REVIEWER -> "Reviewer"
    WorkerPhase.JARVIS_FINAL_SYNTHESIS -> "Jarvis Final Synthesis"
}

@Composable
private fun ToolCard(
    profile: AiToolProfile,
    allowExternal: Boolean,
    onPrepareHandoff: () -> Unit,
    onOpenTool: () -> Unit,
) {
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(profile.displayName, style = MaterialTheme.typography.titleMedium)
            Text(profile.role, style = MaterialTheme.typography.bodyMedium)
            Text(profile.notes, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurface)
            HorizontalDivider()
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = onPrepareHandoff) { Text(stringResource(R.string.orchestrator_prepare_handoff)) }
                if (allowExternal) {
                    OutlinedButton(onClick = onOpenTool) { Text(stringResource(R.string.orchestrator_open_tool)) }
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun TaskRow(
    task: HermesTask,
    onTap: () -> Unit,
    onCopyPrompt: () -> Unit,
    onOpenApprovals: (taskId: String) -> Unit,
    onOpenAudit: (route: String) -> Unit,
) {
    Card(
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
        onClick = onTap,
    ) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(
                task.title.ifBlank { stringResource(R.string.orchestrator_untitled_task) },
                style = MaterialTheme.typography.titleMedium,
            )
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                AssistChip(onClick = onTap, label = { Text(task.taskType.name.lowercase()) })
                AssistChip(
                    onClick = onTap,
                    label = { Text(task.status.name.lowercase().replace('_', ' ')) },
                )
                AssistChip(onClick = onTap, label = { Text(task.targetTool.name.lowercase().replace('_', ' ')) })
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                AssistChip(
                    onClick = onTap,
                    label = { Text(stringResource(R.string.task_card_risk_chip, riskTierLabel(task.riskTier))) },
                )
                AssistChip(
                    onClick = onTap,
                    label = { Text(stringResource(R.string.task_card_phase_chip, workerPhaseLabel(task.workerPhase))) },
                )
                if (task.approvalState != ApprovalState.NOT_REQUIRED) {
                    AssistChip(
                        onClick = onTap,
                        label = { Text(stringResource(R.string.task_card_approval_chip, approvalStateLabel(task.approvalState))) },
                    )
                }
            }
            if (task.description.isNotBlank()) {
                Text(
                    text = task.description.take(140) + if (task.description.length > 140) "…" else "",
                    style = MaterialTheme.typography.bodySmall,
                )
            }
            if (task.evidenceSummary != null) {
                CardField(label = stringResource(R.string.task_card_evidence_label), body = task.evidenceSummary)
            }
            if (task.status == TaskStatus.BLOCKED && task.blockedReason != null) {
                CardField(
                    label = stringResource(R.string.task_card_blocked_label),
                    body = task.blockedReason,
                    emphasised = true,
                )
            }
            if (task.status == TaskStatus.FAILED) {
                CardField(
                    label = stringResource(R.string.task_card_failure_label),
                    body = task.resultNotes ?: stringResource(R.string.task_card_failure_unspecified),
                    emphasised = true,
                )
            }
            if (task.rollbackSummary != null) {
                CardField(label = stringResource(R.string.task_card_rollback_label), body = task.rollbackSummary)
            }
            if (task.verificationResult != null) {
                CardField(
                    label = stringResource(R.string.task_card_verification_label),
                    body = task.verificationResult,
                )
            }
            if (task.nextAction != null) {
                CardField(label = stringResource(R.string.task_card_next_action_label), body = task.nextAction)
            }
            HorizontalDivider()
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = onCopyPrompt) { Text(stringResource(R.string.orchestrator_copy_prompt)) }
                OutlinedButton(onClick = onTap) { Text(stringResource(R.string.orchestrator_open_task)) }
                task.approvalsRoute()?.let { _ ->
                    OutlinedButton(onClick = { onOpenApprovals(task.id) }) {
                        Text(stringResource(R.string.task_card_open_approvals))
                    }
                }
                task.auditRoute()?.let { route ->
                    OutlinedButton(onClick = { onOpenAudit(route) }) {
                        Text(stringResource(R.string.task_card_open_audit))
                    }
                }
            }
        }
    }
}

@Composable
private fun CardField(label: String, body: String, emphasised: Boolean = false) {
    Column {
        Text(
            text = label,
            style = MaterialTheme.typography.labelMedium,
            color = if (emphasised) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.primary,
        )
        Text(
            text = body,
            style = MaterialTheme.typography.bodySmall,
        )
    }
}

private fun riskTierLabel(tier: RiskTier): String = when (tier) {
    RiskTier.LOW -> "Low"
    RiskTier.MEDIUM -> "Medium"
    RiskTier.HIGH -> "High"
    RiskTier.CRITICAL -> "Critical"
}

private fun approvalStateLabel(state: ApprovalState): String = when (state) {
    ApprovalState.NOT_REQUIRED -> "Not required"
    ApprovalState.PENDING -> "Pending"
    ApprovalState.APPROVED -> "Approved"
    ApprovalState.REJECTED -> "Rejected"
}

@Composable
private fun SafetyBanner() {
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text(stringResource(R.string.orchestrator_safety_title),
                style = MaterialTheme.typography.titleSmall,
                color = MaterialTheme.colorScheme.primary)
            Text(stringResource(R.string.orchestrator_safety_body),
                style = MaterialTheme.typography.bodySmall)
        }
    }
}
