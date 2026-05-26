package com.aci.hermes.ui.screens.orchestrator

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.BugReport
import androidx.compose.material.icons.filled.Inbox
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material.icons.filled.WarningAmber
import androidx.compose.material3.AssistChip
import androidx.compose.material3.AssistChipDefaults
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
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
import androidx.compose.material3.TopAppBarDefaults
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
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import com.aci.hermes.R
import com.aci.hermes.data.model.AiToolProfile
import com.aci.hermes.data.model.HermesTask
import com.aci.hermes.data.model.TargetTool
import com.aci.hermes.ui.theme.LocalHermesSemantics
import com.aci.hermes.ui.theme.LocalSpacing
import com.aci.hermes.ui.theme.rememberHermesHaptics

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun OrchestratorScreen(
    viewModel: OrchestratorViewModel,
    onOpenTask: (taskId: String?) -> Unit,
    onPrepareHandoff: (target: TargetTool) -> Unit,
    onOpenSettings: () -> Unit,
    onOpenDiagnostics: () -> Unit,
) {
    val state by viewModel.state.collectAsState()
    val snackbarHostState = remember { SnackbarHostState() }
    var overflowOpen by remember { mutableStateOf(false) }
    val spacing = LocalSpacing.current
    val haptics = rememberHermesHaptics()

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
                title = {
                    Column {
                        Text(stringResource(R.string.orchestrator_title))
                        Text(
                            text = stringResource(R.string.orchestrator_subtitle),
                            style = MaterialTheme.typography.labelMedium,
                            color = MaterialTheme.colorScheme.primary,
                        )
                    }
                },
                actions = {
                    IconButton(onClick = onOpenSettings) {
                        Icon(
                            Icons.Default.Settings,
                            contentDescription = stringResource(R.string.nav_settings),
                        )
                    }
                    Box {
                        IconButton(onClick = { overflowOpen = true }) {
                            Icon(
                                Icons.Default.MoreVert,
                                contentDescription = stringResource(R.string.nav_more),
                            )
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
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.background,
                ),
            )
        },
        floatingActionButton = {
            ExtendedFloatingActionButton(
                onClick = {
                    haptics.tick()
                    onOpenTask(null)
                },
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
                .padding(horizontal = spacing.screen),
            verticalArrangement = Arrangement.spacedBy(spacing.cardGap),
            contentPadding = PaddingValues(vertical = spacing.md),
        ) {
            item {
                StatusCard(
                    state = state,
                    onStart = {
                        haptics.confirm()
                        viewModel.startService()
                    },
                    onStop = {
                        haptics.reject()
                        viewModel.stopService()
                    },
                )
            }
            item { SectionTitle(stringResource(R.string.orchestrator_tools_title)) }
            item {
                Text(
                    text = stringResource(R.string.orchestrator_tools_caption),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurface,
                )
            }
            items(state.tools) { profile ->
                ToolCard(
                    profile = profile,
                    allowExternal = state.allowExternalAppOpening,
                    onPrepareHandoff = {
                        haptics.tick()
                        onPrepareHandoff(profile.targetTool)
                    },
                    onOpenTool = { viewModel.openToolFor(profile) },
                )
            }
            item { SectionTitle(stringResource(R.string.orchestrator_tasks_title)) }
            if (state.tasks.isEmpty()) {
                item { TasksEmptyState(onCreate = { onOpenTask(null) }) }
            } else {
                items(state.tasks) { task ->
                    TaskRow(
                        task = task,
                        onTap = { onOpenTask(task.id) },
                        onCopyPrompt = {
                            haptics.tick()
                            viewModel.copyPromptForTask(task)
                        },
                    )
                }
            }
            if (state.showSafetyWarnings) {
                item { SafetyBanner() }
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
    val spacing = LocalSpacing.current
    val semantics = LocalHermesSemantics.current
    val running = state.serviceRunning

    val statusColor = if (running) semantics.success else MaterialTheme.colorScheme.error
    val statusBg = if (running) semantics.successSurface else semantics.dangerSurface
    val statusLabel = stringResource(
        if (running) R.string.orchestrator_status_running
        else R.string.orchestrator_status_stopped
    )
    val statusA11y = stringResource(
        if (running) R.string.orchestrator_status_running_a11y
        else R.string.orchestrator_status_stopped_a11y
    )

    Card(
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant,
        ),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(spacing.cardPadding),
            verticalArrangement = Arrangement.spacedBy(spacing.sm),
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(spacing.sm),
                modifier = Modifier.semantics { contentDescription = statusA11y },
            ) {
                Surface(
                    shape = CircleShape,
                    color = statusBg,
                    modifier = Modifier.size(spacing.touchTarget / 2),
                ) {
                    Box(contentAlignment = Alignment.Center, modifier = Modifier.fillMaxSize()) {
                        Surface(
                            shape = CircleShape,
                            color = statusColor,
                            modifier = Modifier.size(spacing.statusDot),
                        ) {}
                    }
                }
                Text(
                    text = statusLabel,
                    style = MaterialTheme.typography.titleMedium,
                )
            }
            HorizontalDivider()
            StatusRow(
                stringResource(R.string.orchestrator_status_mode_label),
                "Local Subscription Tools",
            )
            StatusRow(
                stringResource(R.string.orchestrator_status_billing_label),
                stringResource(R.string.orchestrator_status_billing_value),
            )
            StatusRow(
                stringResource(R.string.orchestrator_status_export_label),
                stringResource(R.string.orchestrator_status_export_value),
            )
            Row(horizontalArrangement = Arrangement.spacedBy(spacing.sm)) {
                if (running) {
                    Button(
                        onClick = onStop,
                        colors = ButtonDefaults.buttonColors(
                            containerColor = MaterialTheme.colorScheme.error,
                            contentColor = MaterialTheme.colorScheme.onPrimary,
                        ),
                    ) {
                        Icon(
                            Icons.Default.Stop,
                            contentDescription = null,
                            modifier = Modifier.size(18.dp),
                        )
                        Text(
                            text = stringResource(R.string.orchestrator_emergency_stop),
                            modifier = Modifier.padding(start = spacing.xs),
                        )
                    }
                } else {
                    Button(onClick = onStart) {
                        Icon(
                            Icons.Default.PlayArrow,
                            contentDescription = null,
                            modifier = Modifier.size(18.dp),
                        )
                        Text(
                            text = stringResource(R.string.orchestrator_start_service),
                            modifier = Modifier.padding(start = spacing.xs),
                        )
                    }
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
    val spacing = LocalSpacing.current
    Text(
        text = text,
        style = MaterialTheme.typography.titleMedium,
        color = MaterialTheme.colorScheme.primary,
        modifier = Modifier.padding(top = spacing.sm),
    )
}

@Composable
private fun ToolCard(
    profile: AiToolProfile,
    allowExternal: Boolean,
    onPrepareHandoff: () -> Unit,
    onOpenTool: () -> Unit,
) {
    val spacing = LocalSpacing.current
    Card(
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
    ) {
        Column(
            modifier = Modifier.padding(spacing.cardPadding),
            verticalArrangement = Arrangement.spacedBy(spacing.xs),
        ) {
            Text(profile.displayName, style = MaterialTheme.typography.titleMedium)
            Text(profile.role, style = MaterialTheme.typography.bodyMedium)
            Text(
                profile.notes,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurface,
            )
            HorizontalDivider(modifier = Modifier.padding(vertical = spacing.xs))
            Row(horizontalArrangement = Arrangement.spacedBy(spacing.sm)) {
                Button(onClick = onPrepareHandoff) {
                    Text(stringResource(R.string.orchestrator_prepare_handoff))
                }
                if (allowExternal) {
                    OutlinedButton(onClick = onOpenTool) {
                        Text(stringResource(R.string.orchestrator_open_tool))
                    }
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
) {
    val spacing = LocalSpacing.current
    Card(
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
        onClick = onTap,
    ) {
        Column(
            modifier = Modifier.padding(spacing.cardPadding),
            verticalArrangement = Arrangement.spacedBy(spacing.xs),
        ) {
            Text(
                task.title.ifBlank { stringResource(R.string.orchestrator_untitled_task) },
                style = MaterialTheme.typography.titleMedium,
            )
            Row(
                horizontalArrangement = Arrangement.spacedBy(spacing.sm),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                AssistChip(
                    onClick = onTap,
                    label = { Text(task.taskType.name.lowercase()) },
                    colors = AssistChipDefaults.assistChipColors(),
                )
                AssistChip(
                    onClick = onTap,
                    label = { Text(task.status.name.lowercase().replace('_', ' ')) },
                )
                AssistChip(
                    onClick = onTap,
                    label = { Text(task.targetTool.name.lowercase().replace('_', ' ')) },
                )
            }
            if (task.description.isNotBlank()) {
                Text(
                    text = task.description.take(140) + if (task.description.length > 140) "…" else "",
                    style = MaterialTheme.typography.bodySmall,
                )
            }
            HorizontalDivider(modifier = Modifier.padding(vertical = spacing.xs))
            Row(horizontalArrangement = Arrangement.spacedBy(spacing.sm)) {
                OutlinedButton(onClick = onCopyPrompt) {
                    Text(stringResource(R.string.orchestrator_copy_prompt))
                }
                OutlinedButton(onClick = onTap) {
                    Text(stringResource(R.string.orchestrator_open_task))
                }
            }
        }
    }
}

@Composable
private fun TasksEmptyState(onCreate: () -> Unit) {
    val spacing = LocalSpacing.current
    Card(
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(spacing.cardPadding),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(spacing.sm),
        ) {
            Icon(
                Icons.Default.Inbox,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.primary,
                modifier = Modifier.size(40.dp),
            )
            Text(
                stringResource(R.string.orchestrator_tasks_empty),
                style = MaterialTheme.typography.titleMedium,
            )
            Text(
                stringResource(R.string.orchestrator_tasks_empty_subtitle),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurface,
            )
            OutlinedButton(onClick = onCreate, modifier = Modifier.padding(top = spacing.xs)) {
                Icon(Icons.Default.Add, contentDescription = null, modifier = Modifier.size(18.dp))
                Text(
                    text = stringResource(R.string.orchestrator_new_task),
                    modifier = Modifier.padding(start = spacing.xs),
                )
            }
        }
    }
}

@Composable
private fun SafetyBanner() {
    val spacing = LocalSpacing.current
    val semantics = LocalHermesSemantics.current
    Card(
        colors = CardDefaults.cardColors(
            containerColor = semantics.warnSurface,
            contentColor = MaterialTheme.colorScheme.onSurface,
        ),
    ) {
        Row(
            modifier = Modifier.padding(spacing.cardPadding),
            horizontalArrangement = Arrangement.spacedBy(spacing.sm),
            verticalAlignment = Alignment.Top,
        ) {
            Icon(
                Icons.Default.WarningAmber,
                contentDescription = null,
                tint = semantics.warn,
            )
            Column(verticalArrangement = Arrangement.spacedBy(spacing.xs)) {
                Text(
                    stringResource(R.string.orchestrator_safety_title),
                    style = MaterialTheme.typography.titleSmall,
                    color = semantics.warn,
                )
                Text(
                    stringResource(R.string.orchestrator_safety_body),
                    style = MaterialTheme.typography.bodySmall,
                )
            }
        }
    }
}
