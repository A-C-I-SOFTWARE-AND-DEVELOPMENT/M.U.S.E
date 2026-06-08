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
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.Bolt
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.History
import androidx.compose.material.icons.filled.Memory
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.Science
import androidx.compose.material.icons.filled.Work
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
import com.aci.hermes.ui.components.BackendOfflineBanner
import com.aci.hermes.ui.components.BackendStatusPill
import com.aci.hermes.ui.navigation.Screen
import com.aci.hermes.ui.screens.orchestrator.OrchestratorUiState
import com.aci.hermes.ui.screens.orchestrator.OrchestratorViewModel

/**
 * Primary landing surface for MUSE. Folds in the orchestrator status
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
    onOpenJarvisLive: () -> Unit = {},
    onOpenVoice: () -> Unit = {},
    onOpenDiagnostics: () -> Unit = {},
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
            item {
                BackendOfflineBanner(
                    status = state.backendStatus,
                    onRetry = viewModel::retryBackend,
                    onOpenDiagnostics = onOpenDiagnostics,
                )
            }
            item { StatusCard(state, viewModel::startService, viewModel::stopService) }
            item { JarvisLiveEntryCard(onClick = onOpenJarvisLive) }
            item { SectionTitle(stringResource(R.string.home_quick_links)) }
            item { QuickLinksGrid(onNavigate = onNavigate, onOpenVoice = onOpenVoice) }
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
                    text = if (state.serviceRunning) stringResource(R.string.service_status_running)
                           else stringResource(R.string.service_status_stopped),
                    style = MaterialTheme.typography.titleMedium,
                    modifier = Modifier.weight(1f),
                )
                // Backend reachability is a separate signal from the local
                // service above — show it side-by-side so neither is implied
                // by the other.
                BackendStatusPill(status = state.backendStatus)
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

/**
 * Quick-link grid rendered from [Screen.homeQuickLinks] — the single source
 * of truth for which shell destinations have a Home entry point. Driving the
 * grid off that list (rather than hand-listing cards) is what guarantees a
 * shell route can't silently become deep-link-only (the bug that hid the
 * Capability screen). Voice is appended separately because it is a
 * full-screen push reached via [onOpenVoice], not a shell route.
 */
@Composable
private fun QuickLinksGrid(onNavigate: (Screen) -> Unit, onOpenVoice: () -> Unit) {
    val cells: List<QuickLinkCell> =
        Screen.homeQuickLinks.map { screen ->
            QuickLinkCell(screen.quickLinkLabelRes(), screen.quickLinkIcon()) { onNavigate(screen) }
        } + QuickLinkCell(R.string.nav_voice, Icons.Filled.Mic, onOpenVoice)

    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        cells.chunked(2).forEach { rowCells ->
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
                rowCells.forEach { cell ->
                    QuickLinkCard(
                        modifier = Modifier.weight(1f),
                        title = stringResource(cell.labelRes),
                        icon = cell.icon,
                        onClick = cell.onClick,
                    )
                }
                // Keep the last odd card half-width by padding the row.
                if (rowCells.size == 1) Box(modifier = Modifier.weight(1f))
            }
        }
    }
}

private data class QuickLinkCell(
    val labelRes: Int,
    val icon: ImageVector,
    val onClick: () -> Unit,
)

private fun Screen.quickLinkLabelRes(): Int = when (this) {
    Screen.Tasks -> R.string.nav_tasks
    Screen.Jobs -> R.string.nav_jobs
    Screen.Chat -> R.string.nav_chat
    Screen.Approvals -> R.string.nav_approvals
    Screen.Memory -> R.string.nav_memory
    Screen.Audit -> R.string.nav_audit
    Screen.Capability -> R.string.nav_capability
    Screen.Evidence -> R.string.nav_evidence
    Screen.Control -> R.string.nav_control
    else -> R.string.app_name
}

private fun Screen.quickLinkIcon(): ImageVector = when (this) {
    Screen.Tasks -> Icons.AutoMirrored.Filled.Assignment
    Screen.Jobs -> Icons.Filled.Work
    Screen.Chat -> Icons.AutoMirrored.Filled.Chat
    Screen.Approvals -> Icons.Filled.CheckCircle
    Screen.Memory -> Icons.Filled.Memory
    Screen.Audit -> Icons.Filled.History
    Screen.Capability -> Icons.Filled.Bolt
    Screen.Evidence -> Icons.Filled.Science
    Screen.Control -> Icons.Filled.AdminPanelSettings
    else -> Icons.Filled.AutoAwesome
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
                Icons.Filled.AutoAwesome,
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
