package com.aci.hermes.ui.screens.home

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.PowerSettingsNew
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.AssistChip
import androidx.compose.material3.AssistChipDefaults
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextField
import androidx.compose.material3.TextFieldDefaults
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
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.aci.hermes.data.jarvis.ActiveTaskSnapshot
import com.aci.hermes.data.jarvis.ApprovalRisk
import com.aci.hermes.data.jarvis.GatewayStatus
import com.aci.hermes.data.jarvis.JarvisHomeState
import com.aci.hermes.data.jarvis.JarvisPresence
import com.aci.hermes.data.jarvis.MemoryPulseEntry
import com.aci.hermes.data.jarvis.PendingApproval
import com.aci.hermes.data.jarvis.SuggestedAction
import com.aci.hermes.data.jarvis.SuggestedKind
import com.aci.hermes.data.jarvis.WorkerStatus
import com.aci.hermes.ui.theme.HermesError
import com.aci.hermes.ui.theme.HermesGold
import com.aci.hermes.ui.theme.HermesGoldDeep
import com.aci.hermes.ui.theme.HermesViolet
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * Navigation contract for everything the Jarvis Prime home screen can
 * launch. Kept as a value class so the screen never depends on
 * NavController directly — that keeps the screen previewable and
 * keeps test-only callers from needing a full nav graph.
 */
data class JarvisHomeNavigation(
    val openChat: () -> Unit,
    val openVoiceCapture: () -> Unit,
    val openTasks: (taskId: String?) -> Unit,
    val openApprovals: (taskId: String?) -> Unit,
    val openMemory: () -> Unit,
    val openControl: () -> Unit,
    val openSettings: () -> Unit,
)

object JarvisHomeTestTags {
    const val PRESENCE_HEADER = "jarvis_presence_header"
    const val ICON = "jarvis_icon"
    const val ASK_BAR = "jarvis_ask_bar"
    const val VOICE_BUTTON = "jarvis_voice_button"
    const val GATEWAY_PILL = "jarvis_gateway_pill"
    const val ACTIVE_TASK = "jarvis_active_task"
    const val PENDING_APPROVAL = "jarvis_pending_approval"
    const val WORKER_STATUS = "jarvis_worker_status"
    const val MEMORY_PULSE = "jarvis_memory_pulse"
    const val EMERGENCY_STOP = "jarvis_emergency_stop"
    const val SUGGESTED_ACTION = "jarvis_suggested_action"
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun JarvisPrimeHomeScreen(
    viewModel: JarvisPrimeHomeViewModel,
    navigation: JarvisHomeNavigation,
) {
    val state by viewModel.state.collectAsState()
    LaunchedEffect(Unit) { viewModel.refreshServiceStatus() }

    JarvisPrimeHomeContent(
        state = state,
        navigation = navigation,
        onAskSubmitted = { _ ->
            viewModel.startThinking()
            navigation.openChat()
        },
        onVoiceTapped = {
            viewModel.startListening()
            navigation.openVoiceCapture()
        },
        onIconTapped = navigation.openChat,
        onEmergencyConfirmed = {
            viewModel.triggerEmergencyStop()
        },
        onDeactivateEmergencyStop = viewModel::deactivateEmergencyStop,
        onStartService = viewModel::startService,
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun JarvisPrimeHomeContent(
    state: JarvisHomeState,
    navigation: JarvisHomeNavigation,
    onAskSubmitted: (String) -> Unit,
    onVoiceTapped: () -> Unit,
    onIconTapped: () -> Unit,
    onEmergencyConfirmed: () -> Unit,
    onDeactivateEmergencyStop: () -> Unit,
    onStartService: () -> Unit,
) {
    var emergencyConfirmOpen by remember { mutableStateOf(false) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Jarvis Prime") },
                actions = {
                    IconButton(onClick = navigation.openSettings) {
                        Icon(Icons.Default.Settings, contentDescription = "Settings")
                    }
                }
            )
        }
    ) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
            contentPadding = PaddingValues(vertical = 16.dp),
        ) {
            item {
                JarvisStatusHeader(
                    presence = state.presence,
                    onIconTap = onIconTapped,
                )
            }
            item {
                AskJarvisBar(
                    enabled = state.presence != JarvisPresence.EMERGENCY_STOP_ACTIVE,
                    onSubmit = onAskSubmitted,
                    onTap = navigation.openChat,
                )
            }
            item {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(12.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    GatewayStatusPill(
                        gateway = state.gateway,
                        mockMode = state.mockMode,
                        onClick = navigation.openControl,
                        modifier = Modifier.weight(1f),
                    )
                    VoiceCaptureButton(
                        listening = state.presence == JarvisPresence.LISTENING,
                        enabled = state.presence != JarvisPresence.EMERGENCY_STOP_ACTIVE,
                        onClick = onVoiceTapped,
                    )
                }
            }
            state.suggestedNextAction?.let { suggested ->
                item {
                    SuggestedNextActionCard(
                        suggested = suggested,
                        onClick = {
                            when (suggested.kind) {
                                SuggestedKind.OPEN_APPROVAL -> navigation.openApprovals(suggested.taskId)
                                SuggestedKind.OPEN_ACTIVE_TASK -> navigation.openTasks(suggested.taskId)
                                SuggestedKind.START_SERVICE -> onStartService()
                                SuggestedKind.DEACTIVATE_EMERGENCY_STOP -> onDeactivateEmergencyStop()
                                SuggestedKind.OPEN_CHAT -> navigation.openChat()
                                SuggestedKind.OPEN_VOICE -> onVoiceTapped()
                            }
                        }
                    )
                }
            }
            state.activeTask?.let { task ->
                item {
                    ActiveTaskCard(
                        task = task,
                        onClick = { navigation.openTasks(task.taskId) },
                    )
                }
            }
            if (state.pendingApprovals.isNotEmpty()) {
                items(state.pendingApprovals) { approval ->
                    PendingApprovalCard(
                        approval = approval,
                        onClick = { navigation.openApprovals(approval.taskId) },
                    )
                }
            }
            item {
                WorkerStatusCard(
                    workers = state.workers,
                    onClick = navigation.openControl,
                )
            }
            item {
                MemoryPulseCard(
                    pulse = state.memoryPulse,
                    onClick = navigation.openMemory,
                )
            }
            item {
                EmergencyStopButton(
                    active = state.emergencyStopActive,
                    onPressed = {
                        if (state.emergencyStopActive) {
                            onDeactivateEmergencyStop()
                        } else {
                            emergencyConfirmOpen = true
                        }
                    },
                )
            }
        }
    }

    if (emergencyConfirmOpen) {
        AlertDialog(
            onDismissRequest = { emergencyConfirmOpen = false },
            title = { Text("Engage emergency stop?") },
            text = {
                Text("Halts Jarvis Prime immediately and blocks ask, voice, and worker actions until you deactivate.")
            },
            confirmButton = {
                Button(
                    onClick = {
                        emergencyConfirmOpen = false
                        onEmergencyConfirmed()
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = HermesError),
                ) { Text("Engage") }
            },
            dismissButton = {
                OutlinedButton(onClick = { emergencyConfirmOpen = false }) { Text("Cancel") }
            },
        )
    }
}

// ---- Components ------------------------------------------------------------

@Composable
fun JarvisPrimeIcon(
    presence: JarvisPresence,
    modifier: Modifier = Modifier,
    onClick: (() -> Unit)? = null,
) {
    val tint = presence.tint()
    Box(
        modifier = modifier
            .testTag(JarvisHomeTestTags.ICON)
            .size(72.dp)
            .clip(CircleShape)
            .background(MaterialTheme.colorScheme.surfaceVariant)
            .border(2.dp, tint, CircleShape)
            .then(if (onClick != null) Modifier.clickable(onClick = onClick) else Modifier),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            text = "☤",
            color = tint,
            style = MaterialTheme.typography.headlineLarge,
        )
    }
}

@Composable
fun JarvisStatusHeader(
    presence: JarvisPresence,
    onIconTap: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Row(
        modifier = modifier
            .testTag(JarvisHomeTestTags.PRESENCE_HEADER)
            .fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        JarvisPrimeIcon(presence = presence, onClick = onIconTap)
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = "Jarvis Prime",
                style = MaterialTheme.typography.titleLarge,
                color = MaterialTheme.colorScheme.onBackground,
                fontWeight = FontWeight.SemiBold,
            )
            Text(
                text = presence.headline(),
                style = MaterialTheme.typography.bodyMedium,
                color = presence.tint(),
            )
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AskJarvisBar(
    enabled: Boolean,
    onSubmit: (String) -> Unit,
    onTap: () -> Unit,
    modifier: Modifier = Modifier,
) {
    var draft by remember { mutableStateOf("") }
    val hint = if (enabled) "Ask Jarvis anything…" else "Emergency stop active"
    Surface(
        modifier = modifier
            .testTag(JarvisHomeTestTags.ASK_BAR)
            .fillMaxWidth(),
        shape = RoundedCornerShape(28.dp),
        color = MaterialTheme.colorScheme.surfaceVariant,
        onClick = { if (enabled) onTap() },
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            TextField(
                value = draft,
                onValueChange = { draft = it },
                placeholder = { Text(hint) },
                enabled = enabled,
                singleLine = true,
                modifier = Modifier.weight(1f),
                colors = TextFieldDefaults.colors(
                    focusedContainerColor = Color.Transparent,
                    unfocusedContainerColor = Color.Transparent,
                    disabledContainerColor = Color.Transparent,
                    focusedIndicatorColor = Color.Transparent,
                    unfocusedIndicatorColor = Color.Transparent,
                    disabledIndicatorColor = Color.Transparent,
                ),
            )
            IconButton(
                enabled = enabled,
                onClick = {
                    val payload = draft
                    draft = ""
                    onSubmit(payload)
                },
            ) {
                Icon(Icons.AutoMirrored.Filled.Send, contentDescription = "Send to Jarvis")
            }
        }
    }
}

@Composable
fun VoiceCaptureButton(
    listening: Boolean,
    enabled: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val container = when {
        !enabled -> MaterialTheme.colorScheme.surfaceVariant
        listening -> HermesGold
        else -> HermesViolet
    }
    Surface(
        modifier = modifier
            .testTag(JarvisHomeTestTags.VOICE_BUTTON)
            .size(56.dp),
        shape = CircleShape,
        color = container,
        onClick = onClick,
        enabled = enabled,
    ) {
        Box(contentAlignment = Alignment.Center) {
            Icon(
                imageVector = Icons.Default.Mic,
                contentDescription = if (listening) "Listening" else "Start voice capture",
                tint = MaterialTheme.colorScheme.onPrimary,
            )
        }
    }
}

@Composable
fun GatewayStatusPill(
    gateway: GatewayStatus,
    mockMode: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val (label, color) = when {
        mockMode && gateway != GatewayStatus.DISCONNECTED -> "Mock mode" to HermesViolet
        gateway == GatewayStatus.CONNECTED -> "Gateway connected" to HermesGold
        gateway == GatewayStatus.DEGRADED -> "Gateway degraded" to HermesGoldDeep
        else -> "Gateway disconnected" to HermesError
    }
    AssistChip(
        modifier = modifier.testTag(JarvisHomeTestTags.GATEWAY_PILL),
        onClick = onClick,
        label = { Text(label) },
        leadingIcon = {
            Box(
                modifier = Modifier
                    .size(10.dp)
                    .clip(CircleShape)
                    .background(color),
            )
        },
        colors = AssistChipDefaults.assistChipColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant,
        ),
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ActiveTaskCard(
    task: ActiveTaskSnapshot,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Card(
        modifier = modifier
            .testTag(JarvisHomeTestTags.ACTIVE_TASK)
            .fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
        onClick = onClick,
    ) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("Active task", style = MaterialTheme.typography.labelMedium, color = HermesGold)
            Text(task.title, style = MaterialTheme.typography.titleMedium)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                AssistChip(onClick = onClick, label = { Text(task.target.name.lowercase().replace('_', ' ')) })
                AssistChip(onClick = onClick, label = { Text(task.status.name.lowercase().replace('_', ' ')) })
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PendingApprovalCard(
    approval: PendingApproval,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val border = when (approval.risk) {
        ApprovalRisk.CRITICAL -> HermesError
        ApprovalRisk.SERIOUS -> HermesGoldDeep
        ApprovalRisk.LOW -> HermesViolet
    }
    Card(
        modifier = modifier
            .testTag(JarvisHomeTestTags.PENDING_APPROVAL)
            .fillMaxWidth()
            .border(2.dp, border, RoundedCornerShape(12.dp)),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
        onClick = onClick,
    ) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Approval needed", style = MaterialTheme.typography.labelMedium, color = border)
                AssistChip(
                    onClick = onClick,
                    label = { Text(approval.risk.name.lowercase()) },
                )
            }
            Text(approval.title, style = MaterialTheme.typography.titleMedium)
            Text(approval.reason, style = MaterialTheme.typography.bodySmall)
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun WorkerStatusCard(
    workers: List<WorkerStatus>,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Card(
        modifier = modifier
            .testTag(JarvisHomeTestTags.WORKER_STATUS)
            .fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
        onClick = onClick,
    ) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("Workers", style = MaterialTheme.typography.labelMedium, color = HermesGold)
            if (workers.isEmpty()) {
                Text("No workers configured.", style = MaterialTheme.typography.bodySmall)
            } else {
                workers.forEach { worker ->
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            Box(
                                modifier = Modifier
                                    .size(8.dp)
                                    .clip(CircleShape)
                                    .background(if (worker.busy) HermesGold else MaterialTheme.colorScheme.outline),
                            )
                            Text(worker.displayName, style = MaterialTheme.typography.bodyMedium)
                        }
                        Text(
                            text = if (worker.busy) "busy" else "idle",
                            style = MaterialTheme.typography.bodySmall,
                            color = if (worker.busy) HermesGold else MaterialTheme.colorScheme.onSurface,
                        )
                    }
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MemoryPulseCard(
    pulse: List<MemoryPulseEntry>,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Card(
        modifier = modifier
            .testTag(JarvisHomeTestTags.MEMORY_PULSE)
            .fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
        onClick = onClick,
    ) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("Memory pulse", style = MaterialTheme.typography.labelMedium, color = HermesViolet)
            if (pulse.isEmpty()) {
                Text("Nothing recent. Memory will fill as Jarvis works.",
                    style = MaterialTheme.typography.bodySmall)
            } else {
                pulse.forEach { entry ->
                    Text(
                        text = "${formatTime(entry.timestamp)} · ${entry.label}",
                        style = MaterialTheme.typography.bodySmall,
                    )
                }
            }
        }
    }
}

@Composable
fun EmergencyStopButton(
    active: Boolean,
    onPressed: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val container = if (active) MaterialTheme.colorScheme.surfaceVariant else HermesError
    val label = if (active) "Deactivate emergency stop" else "Emergency stop"
    Button(
        onClick = onPressed,
        modifier = modifier
            .testTag(JarvisHomeTestTags.EMERGENCY_STOP)
            .fillMaxWidth()
            .height(56.dp)
            .semantics { contentDescription = label },
        colors = ButtonDefaults.buttonColors(containerColor = container),
    ) {
        Icon(Icons.Default.PowerSettingsNew, contentDescription = null)
        Spacer(Modifier.width(8.dp))
        Text(label)
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SuggestedNextActionCard(
    suggested: SuggestedAction,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Card(
        modifier = modifier
            .testTag(JarvisHomeTestTags.SUGGESTED_ACTION)
            .fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
        onClick = onClick,
    ) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text("Suggested next action", style = MaterialTheme.typography.labelMedium, color = HermesGold)
            Text(suggested.label, style = MaterialTheme.typography.titleMedium)
        }
    }
}

// ---- helpers ---------------------------------------------------------------

private fun JarvisPresence.tint(): Color = when (this) {
    JarvisPresence.IDLE -> HermesGold
    JarvisPresence.LISTENING -> HermesViolet
    JarvisPresence.THINKING -> HermesViolet
    JarvisPresence.WORKING -> HermesGold
    JarvisPresence.WAITING_FOR_APPROVAL -> HermesGoldDeep
    JarvisPresence.SERIOUS_ACTION_PENDING -> HermesGoldDeep
    JarvisPresence.CRITICAL_ACTION_PENDING -> HermesError
    JarvisPresence.GATEWAY_DISCONNECTED -> HermesError
    JarvisPresence.SERVICE_STOPPED -> HermesError
    JarvisPresence.EMERGENCY_STOP_ACTIVE -> HermesError
    JarvisPresence.OFFLINE_MOCK -> HermesViolet
}

private fun JarvisPresence.headline(): String = when (this) {
    JarvisPresence.IDLE -> "Standing by."
    JarvisPresence.LISTENING -> "Listening…"
    JarvisPresence.THINKING -> "Thinking…"
    JarvisPresence.WORKING -> "Working on it."
    JarvisPresence.WAITING_FOR_APPROVAL -> "Waiting for your approval."
    JarvisPresence.SERIOUS_ACTION_PENDING -> "Serious action pending."
    JarvisPresence.CRITICAL_ACTION_PENDING -> "Critical action pending."
    JarvisPresence.GATEWAY_DISCONNECTED -> "Gateway disconnected."
    JarvisPresence.SERVICE_STOPPED -> "HermesService is stopped."
    JarvisPresence.EMERGENCY_STOP_ACTIVE -> "Emergency stop engaged."
    JarvisPresence.OFFLINE_MOCK -> "Offline / mock mode."
}

private fun formatTime(ms: Long): String =
    SimpleDateFormat("HH:mm", Locale.US).format(Date(ms))
