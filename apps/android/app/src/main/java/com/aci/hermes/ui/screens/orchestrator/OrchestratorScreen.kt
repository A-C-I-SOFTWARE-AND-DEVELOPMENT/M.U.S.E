package com.aci.hermes.ui.screens.orchestrator

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
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.BugReport
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Add
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
import com.aci.hermes.data.model.HermesTask
import com.aci.hermes.data.model.TargetTool

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun OrchestratorScreen(
    viewModel: OrchestratorViewModel,
    onOpenTask: (taskId: String?) -> Unit,
    onPrepareHandoff: (target: TargetTool) -> Unit,
    onOpenSettings: () -> Unit,
    onOpenDiagnostics: () -> Unit,
    onOpenJarvisLive: () -> Unit = {},
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
            item { StatusCard(state, viewModel::startService, viewModel::stopService) }
            item { JarvisLiveEntryCard(onClick = onOpenJarvisLive) }
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
            item { SectionTitle(stringResource(R.string.orchestrator_tasks_title)) }
            if (state.tasks.isEmpty()) {
                item {
                    Text(
                        text = stringResource(R.string.orchestrator_tasks_empty),
                        style = MaterialTheme.typography.bodyMedium,
                        modifier = Modifier.padding(vertical = 8.dp),
                    )
                }
            } else {
                items(state.tasks) { task ->
                    TaskRow(
                        task = task,
                        onTap = { onOpenTask(task.id) },
                        onCopyPrompt = { viewModel.copyPromptForTask(task) },
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
) {
    Card(
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
        onClick = onTap,
    ) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(task.title.ifBlank { stringResource(R.string.orchestrator_untitled_task) },
                style = MaterialTheme.typography.titleMedium)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                AssistChip(onClick = onTap, label = { Text(task.taskType.name.lowercase()) })
                AssistChip(onClick = onTap, label = { Text(task.status.name.lowercase().replace('_', ' ')) })
                AssistChip(onClick = onTap, label = { Text(task.targetTool.name.lowercase().replace('_', ' ')) })
            }
            if (task.description.isNotBlank()) {
                Text(
                    text = task.description.take(140) + if (task.description.length > 140) "…" else "",
                    style = MaterialTheme.typography.bodySmall,
                )
            }
            HorizontalDivider()
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = onCopyPrompt) { Text(stringResource(R.string.orchestrator_copy_prompt)) }
                OutlinedButton(onClick = onTap) { Text(stringResource(R.string.orchestrator_open_task)) }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun JarvisLiveEntryCard(onClick: () -> Unit) {
    Card(
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
        onClick = onClick,
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Icon(
                Icons.Default.AutoAwesome,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.primary,
            )
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    stringResource(R.string.jarvis_live_entry_title),
                    style = MaterialTheme.typography.titleMedium,
                )
                Text(
                    stringResource(R.string.jarvis_live_entry_subtitle),
                    style = MaterialTheme.typography.bodySmall,
                )
            }
        }
    }
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
