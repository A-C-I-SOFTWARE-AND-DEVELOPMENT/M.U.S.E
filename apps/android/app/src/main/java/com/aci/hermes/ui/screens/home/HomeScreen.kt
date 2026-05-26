package com.aci.hermes.ui.screens.home

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
import androidx.compose.material.icons.automirrored.filled.Assignment
import androidx.compose.material.icons.automirrored.filled.Chat
import androidx.compose.material.icons.filled.AdminPanelSettings
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.History
import androidx.compose.material.icons.filled.Memory
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.aci.hermes.R
import com.aci.hermes.data.model.AiToolProfile
import com.aci.hermes.data.model.TargetTool
import com.aci.hermes.ui.navigation.Screen
import com.aci.hermes.ui.screens.orchestrator.OrchestratorUiState
import com.aci.hermes.ui.screens.orchestrator.OrchestratorViewModel

/**
 * Primary landing surface for Jarvis Prime. Folds in the orchestrator status
 * card and tool launcher from the original Hermes dashboard, then adds
 * deep-link cards into every other section of the navigation shell.
 */
@Composable
fun HomeScreen(
    viewModel: OrchestratorViewModel,
    paddingValues: PaddingValues,
    onNavigate: (Screen) -> Unit,
    onOpenTask: (taskId: String?) -> Unit,
    onPrepareHandoff: (target: TargetTool) -> Unit,
) {
    val state by viewModel.state.collectAsState()
    val snackbarHostState = remember { SnackbarHostState() }

    LaunchedEffect(state.snackbar) {
        state.snackbar?.let {
            snackbarHostState.showSnackbar(it)
            viewModel.consumeSnackbar()
        }
    }
    LaunchedEffect(Unit) { viewModel.refreshServiceStatus() }

    Box(modifier = Modifier.fillMaxSize().padding(paddingValues)) {
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
            contentPadding = PaddingValues(vertical = 12.dp),
        ) {
            item { GreetingCard() }
            item { StatusCard(state, viewModel::startService, viewModel::stopService) }
            item { SectionTitle(stringResource(R.string.home_quick_links)) }
            item { QuickLinksGrid(onNavigate) }
            item { SectionTitle(stringResource(R.string.orchestrator_tools_title)) }
            items(state.tools, key = { it.id }) { profile ->
                ToolCard(
                    profile = profile,
                    allowExternal = state.allowExternalAppOpening,
                    onPrepareHandoff = { onPrepareHandoff(profile.targetTool) },
                    onOpenTool = { viewModel.openToolFor(profile) },
                )
            }
            item {
                OutlinedButton(
                    onClick = { onOpenTask(null) },
                    modifier = Modifier.fillMaxWidth(),
                ) { Text(stringResource(R.string.orchestrator_new_task)) }
            }
            if (state.showSafetyWarnings) {
                item { SafetyBanner() }
            }
        }
        SnackbarHost(
            hostState = snackbarHostState,
            modifier = Modifier.align(Alignment.BottomCenter),
        )
    }
}

@Composable
private fun GreetingCard() {
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)) {
        Column(
            modifier = Modifier.fillMaxWidth().padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            Text(
                text = stringResource(R.string.home_greeting_title),
                style = MaterialTheme.typography.titleLarge,
                color = MaterialTheme.colorScheme.primary,
            )
            Text(
                text = stringResource(R.string.home_greeting_subtitle),
                style = MaterialTheme.typography.bodyMedium,
            )
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
            modifier = Modifier.fillMaxWidth().padding(16.dp),
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
            StatusRow(stringResource(R.string.orchestrator_status_mode_label), stringResource(R.string.home_status_mode_value))
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
private fun QuickLinksGrid(onNavigate: (Screen) -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
            QuickLinkCard(
                modifier = Modifier.weight(1f),
                title = stringResource(R.string.nav_tasks),
                icon = Icons.AutoMirrored.Filled.Assignment,
                onClick = { onNavigate(Screen.Tasks) },
            )
            QuickLinkCard(
                modifier = Modifier.weight(1f),
                title = stringResource(R.string.nav_chat),
                icon = Icons.AutoMirrored.Filled.Chat,
                onClick = { onNavigate(Screen.Chat) },
            )
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
            QuickLinkCard(
                modifier = Modifier.weight(1f),
                title = stringResource(R.string.nav_approvals),
                icon = Icons.Filled.CheckCircle,
                onClick = { onNavigate(Screen.Approvals) },
            )
            QuickLinkCard(
                modifier = Modifier.weight(1f),
                title = stringResource(R.string.nav_memory),
                icon = Icons.Filled.Memory,
                onClick = { onNavigate(Screen.Memory) },
            )
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
            QuickLinkCard(
                modifier = Modifier.weight(1f),
                title = stringResource(R.string.nav_audit),
                icon = Icons.Filled.History,
                onClick = { onNavigate(Screen.Audit) },
            )
            QuickLinkCard(
                modifier = Modifier.weight(1f),
                title = stringResource(R.string.nav_control),
                icon = Icons.Filled.AdminPanelSettings,
                onClick = { onNavigate(Screen.Control) },
            )
        }
    }
}

@Composable
private fun QuickLinkCard(
    modifier: Modifier = Modifier,
    title: String,
    icon: ImageVector,
    onClick: () -> Unit,
) {
    Card(
        modifier = modifier,
        onClick = onClick,
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Icon(icon, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
            Text(title, style = MaterialTheme.typography.titleSmall)
        }
    }
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
            Text(profile.notes, style = MaterialTheme.typography.bodySmall)
            HorizontalDivider()
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
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

@Composable
private fun SafetyBanner() {
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text(
                stringResource(R.string.orchestrator_safety_title),
                style = MaterialTheme.typography.titleSmall,
                color = MaterialTheme.colorScheme.primary,
            )
            Text(
                stringResource(R.string.orchestrator_safety_body),
                style = MaterialTheme.typography.bodySmall,
            )
        }
    }
}
