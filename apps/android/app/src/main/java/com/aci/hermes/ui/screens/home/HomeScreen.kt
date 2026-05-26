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
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Chat
import androidx.compose.material.icons.filled.Bolt
import androidx.compose.material.icons.filled.History
import androidx.compose.material.icons.filled.Hub
import androidx.compose.material.icons.filled.Insights
import androidx.compose.material.icons.filled.LibraryBooks
import androidx.compose.material.icons.filled.Memory
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.RuleFolder
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material.icons.filled.TaskAlt
import androidx.compose.material3.AssistChip
import androidx.compose.material3.AssistChipDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.aci.hermes.R
import com.aci.hermes.data.model.ApprovalCard
import com.aci.hermes.data.model.GatewayConnectionState
import com.aci.hermes.ui.icon.InteractiveIcon

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeScreen(
    viewModel: HomeViewModel,
    onOpenChat: () -> Unit,
    onOpenVoice: () -> Unit,
    onOpenTasks: () -> Unit,
    onOpenApprovals: () -> Unit,
    onOpenAudit: () -> Unit,
    onOpenMemory: () -> Unit,
    onOpenSocial: () -> Unit,
    onOpenGateway: () -> Unit,
    onOpenNotifications: () -> Unit,
    onOpenSkills: () -> Unit,
    onOpenEmergencyStop: () -> Unit,
    onOpenSettings: () -> Unit,
) {
    val state by viewModel.state.collectAsState()
    var emergencyConfirmOpen by remember { mutableStateOf(false) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.app_name)) },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.background,
                ),
                actions = {
                    IconButton(onClick = onOpenNotifications) {
                        Icon(Icons.Default.Notifications, contentDescription = stringResource(R.string.nav_notifications))
                    }
                    IconButton(onClick = onOpenSettings) {
                        Icon(Icons.Default.Settings, contentDescription = stringResource(R.string.nav_settings))
                    }
                    IconButton(onClick = onOpenEmergencyStop) {
                        Icon(
                            Icons.Default.Stop,
                            contentDescription = stringResource(R.string.nav_emergency_stop),
                            tint = if (state.emergencyEngaged) MaterialTheme.colorScheme.error
                                   else MaterialTheme.colorScheme.error.copy(alpha = 0.65f),
                        )
                    }
                },
            )
        },
    ) { padding ->
        Box(modifier = Modifier.fillMaxSize().padding(padding)) {
            LazyColumn(
                modifier = Modifier.fillMaxSize(),
                contentPadding = PaddingValues(horizontal = 16.dp, vertical = 12.dp),
                verticalArrangement = Arrangement.spacedBy(14.dp),
            ) {
                item { HeroCard(state, onOpenVoice = onOpenVoice, onOpenChat = onOpenChat) }
                item { StatusStrip(state) }
                if (state.mockMode) item { MockBanner() }
                item {
                    SectionHeader(stringResource(R.string.home_section_quick_actions))
                }
                item {
                    QuickActionsRow(
                        actions = listOf(
                            QuickAction(Icons.AutoMirrored.Filled.Chat, R.string.home_open_chat, onOpenChat),
                            QuickAction(Icons.Default.Mic, R.string.home_start_voice, onOpenVoice),
                            QuickAction(Icons.Default.RuleFolder, R.string.home_review_approvals, onOpenApprovals),
                            QuickAction(Icons.Default.TaskAlt, R.string.home_view_tasks, onOpenTasks),
                        ),
                    )
                }
                item {
                    QuickActionsRow(
                        actions = listOf(
                            QuickAction(Icons.Default.Memory, R.string.home_view_memory, onOpenMemory),
                            QuickAction(Icons.Default.Person, R.string.home_view_social, onOpenSocial),
                            QuickAction(Icons.Default.Hub, R.string.home_view_gateway, onOpenGateway),
                            QuickAction(Icons.Default.History, R.string.home_view_audit, onOpenAudit),
                        ),
                    )
                }
                item {
                    QuickActionsRow(
                        actions = listOf(
                            QuickAction(Icons.Default.Notifications, R.string.home_view_notifications, onOpenNotifications),
                            QuickAction(Icons.Default.LibraryBooks, R.string.home_view_skills, onOpenSkills),
                            QuickAction(Icons.Default.Stop, R.string.home_emergency_stop, { emergencyConfirmOpen = true }),
                            QuickAction(Icons.Default.Settings, R.string.nav_settings, onOpenSettings),
                        ),
                    )
                }
                item { SectionHeader(stringResource(R.string.home_section_pending)) }
                if (state.pendingApprovals.isEmpty()) {
                    item {
                        Text(
                            stringResource(R.string.home_no_pending),
                            style = MaterialTheme.typography.bodyMedium,
                        )
                    }
                } else {
                    items(state.pendingApprovals) { approval ->
                        PendingApprovalRow(approval, onOpen = onOpenApprovals)
                    }
                }

                item { SectionHeader(stringResource(R.string.home_section_pulse)) }
                if (state.recentAudit.isEmpty()) {
                    item { Text(stringResource(R.string.audit_empty), style = MaterialTheme.typography.bodyMedium) }
                } else {
                    items(state.recentAudit) { entry ->
                        AuditPulseRow(title = entry.title, detail = entry.detail)
                    }
                }
            }
        }
    }

    if (emergencyConfirmOpen) {
        androidx.compose.material3.AlertDialog(
            onDismissRequest = { emergencyConfirmOpen = false },
            title = { Text(stringResource(R.string.emergency_stop_confirm_title)) },
            text = { Text(stringResource(R.string.emergency_stop_confirm_body)) },
            confirmButton = {
                androidx.compose.material3.TextButton(onClick = {
                    emergencyConfirmOpen = false
                    viewModel.engageEmergencyStop("Triggered from Home")
                    onOpenEmergencyStop()
                }) { Text(stringResource(R.string.emergency_stop_engage_cta)) }
            },
            dismissButton = {
                androidx.compose.material3.TextButton(onClick = { emergencyConfirmOpen = false }) {
                    Text(stringResource(R.string.action_cancel))
                }
            },
        )
    }
}

private data class QuickAction(
    val icon: ImageVector,
    val labelRes: Int,
    val onClick: () -> Unit,
)

@Composable
private fun HeroCard(
    state: HomeUiState,
    onOpenVoice: () -> Unit,
    onOpenChat: () -> Unit,
) {
    val greetingText = when (state.greeting) {
        "morning" -> stringResource(R.string.home_greeting_morning)
        "afternoon" -> stringResource(R.string.home_greeting_afternoon)
        else -> stringResource(R.string.home_greeting_evening)
    }
    Card(
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
        shape = RoundedCornerShape(20.dp),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(20.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(20.dp),
        ) {
            InteractiveIcon(
                active = state.status != HomeStatus.PAUSED,
                sizeDp = 88,
                onClick = onOpenVoice,
                contentDescription = stringResource(R.string.home_start_voice),
            )
            Column(modifier = Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text(
                    text = "$greetingText.",
                    style = MaterialTheme.typography.titleMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Text(
                    text = stringResource(R.string.app_name),
                    style = MaterialTheme.typography.headlineMedium,
                    fontWeight = FontWeight.SemiBold,
                )
                Text(
                    text = stringResource(R.string.app_tagline),
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                AssistChip(
                    onClick = onOpenChat,
                    label = { Text(stringResource(R.string.home_open_chat)) },
                    leadingIcon = { Icon(Icons.AutoMirrored.Filled.Chat, contentDescription = null) },
                    colors = AssistChipDefaults.assistChipColors(
                        containerColor = MaterialTheme.colorScheme.primaryContainer,
                    ),
                )
            }
        }
    }
}

@Composable
private fun StatusStrip(state: HomeUiState) {
    val (label, color) = when (state.status) {
        HomeStatus.IDLE -> stringResource(R.string.home_status_idle) to MaterialTheme.colorScheme.secondary
        HomeStatus.ACTIVE -> stringResource(R.string.home_status_active) to MaterialTheme.colorScheme.tertiary
        HomeStatus.WAITING -> stringResource(R.string.home_status_waiting) to MaterialTheme.colorScheme.primary
        HomeStatus.PAUSED -> stringResource(R.string.home_status_paused) to MaterialTheme.colorScheme.error
    }
    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Surface(color = color, shape = CircleShape, modifier = Modifier.size(10.dp)) {}
        Text(label, style = MaterialTheme.typography.titleSmall)
        Surface(
            color = MaterialTheme.colorScheme.surfaceVariant,
            shape = RoundedCornerShape(50),
            modifier = Modifier.padding(start = 8.dp),
        ) {
            Text(
                text = when (state.gatewayConnection) {
                    GatewayConnectionState.CONNECTED -> stringResource(R.string.gateway_status_connected)
                    GatewayConnectionState.CONNECTING -> "Connecting…"
                    GatewayConnectionState.ERROR -> "Gateway error"
                    GatewayConnectionState.DISCONNECTED -> stringResource(R.string.gateway_status_disconnected)
                },
                style = MaterialTheme.typography.labelSmall,
                modifier = Modifier.padding(horizontal = 10.dp, vertical = 4.dp),
            )
        }
    }
}

@Composable
private fun MockBanner() {
    Card(
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.secondaryContainer),
        shape = RoundedCornerShape(12.dp),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(12.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Icon(Icons.Default.Insights, contentDescription = null, tint = MaterialTheme.colorScheme.onSecondaryContainer)
            Text(
                text = stringResource(R.string.chat_mock_banner),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSecondaryContainer,
            )
        }
    }
}

@Composable
private fun SectionHeader(text: String) {
    Text(
        text = text,
        style = MaterialTheme.typography.titleMedium,
        color = MaterialTheme.colorScheme.primary,
        modifier = Modifier.padding(top = 4.dp, bottom = 2.dp),
    )
}

@Composable
private fun QuickActionsRow(actions: List<QuickAction>) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        actions.forEach { action ->
            QuickActionTile(action = action, modifier = Modifier.weight(1f))
        }
    }
}

@Composable
private fun QuickActionTile(action: QuickAction, modifier: Modifier = Modifier) {
    Card(
        modifier = modifier,
        shape = RoundedCornerShape(14.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
        onClick = action.onClick,
    ) {
        Column(
            modifier = Modifier.fillMaxWidth().padding(vertical = 14.dp, horizontal = 8.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Icon(action.icon, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
            Text(
                text = stringResource(action.labelRes),
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun PendingApprovalRow(approval: ApprovalCard, onOpen: () -> Unit) {
    Card(
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
        shape = RoundedCornerShape(12.dp),
        onClick = onOpen,
    ) {
        Column(modifier = Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Default.Bolt, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
                Text(
                    text = approval.title,
                    style = MaterialTheme.typography.titleSmall,
                    modifier = Modifier.padding(start = 6.dp).weight(1f),
                )
            }
            Text(approval.summary, style = MaterialTheme.typography.bodySmall, maxLines = 2)
        }
    }
}

@Composable
private fun AuditPulseRow(title: String, detail: String) {
    Card(
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
        shape = RoundedCornerShape(12.dp),
    ) {
        Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text(title, style = MaterialTheme.typography.titleSmall)
            Text(detail, style = MaterialTheme.typography.bodySmall, maxLines = 2)
        }
    }
}
