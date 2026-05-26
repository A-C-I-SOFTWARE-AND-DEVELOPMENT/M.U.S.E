package com.aci.hermes.ui.screens.home

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
import androidx.compose.material.icons.filled.Build
import androidx.compose.material.icons.filled.BugReport
import androidx.compose.material.icons.filled.Chat
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Description
import androidx.compose.material.icons.filled.Memory
import androidx.compose.material.icons.filled.People
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.unit.dp
import androidx.compose.foundation.gestures.detectTapGestures
import com.aci.hermes.R
import com.aci.hermes.data.gateway.ConnectionState
import com.aci.hermes.data.gateway.GatewayMode
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeScreen(
    viewModel: HomeViewModel,
    onOpenChat: () -> Unit,
    onOpenVoice: () -> Unit,
    onOpenTasks: () -> Unit,
    onOpenApprovals: () -> Unit,
    onOpenMemory: () -> Unit,
    onOpenSocial: () -> Unit,
    onOpenAudit: () -> Unit,
    onOpenDiagnostics: () -> Unit,
    onOpenSettings: () -> Unit,
    onRequestNotificationPermission: () -> Unit,
) {
    val state by viewModel.state.collectAsState()
    val scope = rememberCoroutineScope()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.home_title)) },
                actions = {
                    IconButton(onClick = onOpenDiagnostics) {
                        Icon(Icons.Default.BugReport, contentDescription = stringResource(R.string.nav_diagnostics))
                    }
                    IconButton(onClick = onOpenSettings) {
                        Icon(Icons.Default.Settings, contentDescription = stringResource(R.string.nav_settings))
                    }
                },
            )
        },
        floatingActionButton = {
            JarvisInteractiveIcon(
                onTap = onOpenChat,
                onLongPress = onOpenVoice,
            )
        },
    ) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
            contentPadding = androidx.compose.foundation.layout.PaddingValues(vertical = 12.dp),
        ) {
            item { GreetingCard(state, onAsk = onOpenChat) }
            if (state.emergency.armed) {
                item { EmergencyBanner(onClear = {
                    viewModel.clearEmergencyStop(null)
                }) }
            }
            if (state.notificationEducation && !state.notificationsGranted) {
                item {
                    NotificationEducationBanner(
                        onEnable = {
                            onRequestNotificationPermission()
                            scope.launch { viewModel.dismissNotificationEducation() }
                        },
                        onDismiss = {
                            scope.launch { viewModel.dismissNotificationEducation() }
                        },
                    )
                }
            }
            item { ConnectionRow(state) }
            item { QuickActionsGrid(
                onOpenTasks = onOpenTasks,
                onOpenApprovals = onOpenApprovals,
                onOpenMemory = onOpenMemory,
                onOpenSocial = onOpenSocial,
                onOpenAudit = onOpenAudit,
                pendingApprovals = state.pendingApprovals,
            ) }
            item {
                Text(
                    stringResource(R.string.home_recent_events),
                    style = MaterialTheme.typography.titleSmall,
                    color = MaterialTheme.colorScheme.primary,
                    modifier = Modifier.padding(top = 4.dp),
                )
            }
            if (state.recentEvents.isEmpty()) {
                item {
                    Text(
                        stringResource(R.string.home_no_events),
                        style = MaterialTheme.typography.bodySmall,
                    )
                }
            } else {
                items(state.recentEvents) { ev ->
                    Card(
                        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
                    ) {
                        Column(modifier = Modifier.padding(12.dp)) {
                            Text(ev.type.name, style = MaterialTheme.typography.bodyMedium)
                            if (ev.payload.isNotBlank()) {
                                Text(ev.payload, style = MaterialTheme.typography.bodySmall)
                            }
                        }
                    }
                }
            }
            item {
                OutlinedButton(
                    onClick = {
                        if (state.emergency.armed) viewModel.clearEmergencyStop(null)
                        else viewModel.armEmergencyStop(null)
                    },
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Icon(Icons.Default.Stop, contentDescription = null)
                    Text(
                        text = "  " + if (state.emergency.armed)
                            stringResource(R.string.home_emergency_clear)
                        else stringResource(R.string.home_emergency_stop),
                    )
                }
            }
        }
    }
}

@Composable
private fun GreetingCard(state: HomeUiState, onAsk: () -> Unit) {
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Text(stringResource(R.string.home_greeting), style = MaterialTheme.typography.titleMedium)
            Text(stringResource(R.string.home_voice_label), style = MaterialTheme.typography.bodySmall)
            OutlinedButton(onClick = onAsk) {
                Icon(Icons.Default.Chat, contentDescription = null)
                Text("  " + stringResource(R.string.home_ask))
            }
            if (state.pendingApprovals > 0) {
                AssistChip(
                    onClick = {},
                    label = {
                        Text(
                            text = stringResource(R.string.home_pending_approvals, state.pendingApprovals),
                        )
                    },
                )
            }
        }
    }
}

@Composable
private fun ConnectionRow(state: HomeUiState) {
    val statusRes = when (state.connection) {
        is ConnectionState.Connected -> R.string.home_status_connected
        else -> R.string.home_status_disconnected
    }
    val modeRes = when (state.mode) {
        GatewayMode.MOCK -> R.string.home_status_mock
        GatewayMode.TERMUX -> R.string.home_status_termux
        GatewayMode.DISCONNECTED -> R.string.home_status_disconnected
    }
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(12.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Surface(
                shape = CircleShape,
                color = if (state.connection is ConnectionState.Connected) MaterialTheme.colorScheme.primary
                        else MaterialTheme.colorScheme.error,
                modifier = Modifier.size(10.dp),
            ) {}
            Text(stringResource(statusRes), style = MaterialTheme.typography.bodyMedium)
            AssistChip(onClick = {}, label = { Text(stringResource(modeRes)) })
        }
    }
}

@Composable
private fun NotificationEducationBanner(onEnable: () -> Unit, onDismiss: () -> Unit) {
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.tertiaryContainer)) {
        Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(stringResource(R.string.home_notification_banner), style = MaterialTheme.typography.bodyMedium)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = onEnable) {
                    Text(stringResource(R.string.home_notification_banner_action))
                }
                OutlinedButton(onClick = onDismiss) {
                    Text(stringResource(R.string.action_cancel))
                }
            }
        }
    }
}

@Composable
private fun EmergencyBanner(onClear: () -> Unit) {
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.errorContainer)) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(12.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            Text(stringResource(R.string.home_emergency_banner), style = MaterialTheme.typography.bodyMedium)
            OutlinedButton(onClick = onClear) {
                Text(stringResource(R.string.home_emergency_clear))
            }
        }
    }
}

@Composable
private fun QuickActionsGrid(
    onOpenTasks: () -> Unit,
    onOpenApprovals: () -> Unit,
    onOpenMemory: () -> Unit,
    onOpenSocial: () -> Unit,
    onOpenAudit: () -> Unit,
    pendingApprovals: Int,
) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(
            stringResource(R.string.home_quick_actions),
            style = MaterialTheme.typography.titleSmall,
            color = MaterialTheme.colorScheme.primary,
        )
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
            QuickAction(
                label = stringResource(R.string.home_open_tasks),
                icon = Icons.Default.Build,
                onClick = onOpenTasks,
                modifier = Modifier.weight(1f),
            )
            QuickAction(
                label = stringResource(R.string.home_open_approvals),
                icon = Icons.Default.CheckCircle,
                onClick = onOpenApprovals,
                modifier = Modifier.weight(1f),
                badge = if (pendingApprovals > 0) pendingApprovals.toString() else null,
            )
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
            QuickAction(
                label = stringResource(R.string.home_open_memory),
                icon = Icons.Default.Memory,
                onClick = onOpenMemory,
                modifier = Modifier.weight(1f),
            )
            QuickAction(
                label = stringResource(R.string.home_open_social),
                icon = Icons.Default.People,
                onClick = onOpenSocial,
                modifier = Modifier.weight(1f),
            )
            QuickAction(
                label = stringResource(R.string.home_open_audit),
                icon = Icons.Default.Description,
                onClick = onOpenAudit,
                modifier = Modifier.weight(1f),
            )
        }
    }
}

@Composable
private fun QuickAction(
    label: String,
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    badge: String? = null,
) {
    Card(
        modifier = modifier,
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
        onClick = onClick,
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(icon, contentDescription = null)
                if (badge != null) {
                    Surface(
                        color = MaterialTheme.colorScheme.primary,
                        shape = CircleShape,
                        modifier = Modifier.padding(start = 6.dp),
                    ) {
                        Text(
                            text = badge,
                            modifier = Modifier.padding(horizontal = 6.dp, vertical = 1.dp),
                            color = MaterialTheme.colorScheme.onPrimary,
                            style = MaterialTheme.typography.labelSmall,
                        )
                    }
                }
            }
            Text(label, style = MaterialTheme.typography.bodyMedium)
        }
    }
}

/**
 * Interactive Jarvis icon. Tap → open chat, long press → open voice
 * capture. Wraps a [FloatingActionButton] so the surface keeps the
 * Material FAB affordance.
 */
@Composable
fun JarvisInteractiveIcon(onTap: () -> Unit, onLongPress: () -> Unit) {
    Box(
        modifier = Modifier
            .size(64.dp)
            .semantics { contentDescription = "Jarvis Prime icon" }
            .pointerInput(Unit) {
                detectTapGestures(
                    onTap = { onTap() },
                    onLongPress = { onLongPress() },
                )
            },
        contentAlignment = Alignment.Center,
    ) {
        FloatingActionButton(onClick = onTap) {
            Icon(Icons.Default.Chat, contentDescription = null)
        }
    }
}
