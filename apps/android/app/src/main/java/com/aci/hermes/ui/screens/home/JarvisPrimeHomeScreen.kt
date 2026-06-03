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
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextField
import androidx.compose.material3.TextFieldDefaults
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
import com.aci.hermes.data.jarvis.AuditEventSummary
import com.aci.hermes.data.jarvis.DeviceCapabilitySummary
import com.aci.hermes.data.jarvis.EvidenceSummary
import com.aci.hermes.data.jarvis.GatewayStatus
import com.aci.hermes.data.jarvis.HomeBackendSync
import com.aci.hermes.data.jarvis.JarvisHomeState
import com.aci.hermes.data.jarvis.JarvisPresence
import com.aci.hermes.data.jarvis.JobSummary
import com.aci.hermes.data.jarvis.MemoryPulseEntry
import com.aci.hermes.data.jarvis.ModelRouterSummary
import com.aci.hermes.data.jarvis.PendingApproval
import com.aci.hermes.data.jarvis.SuggestedAction
import com.aci.hermes.data.jarvis.SuggestedKind
import com.aci.hermes.data.jarvis.WorkerStatus
import com.aci.hermes.voice.VoicePhase
import com.aci.hermes.ui.jarvis.rememberJarvisHaptics
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
    val openTasksList: () -> Unit,
    val openApprovals: (taskId: String?) -> Unit,
    val openMemory: () -> Unit,
    val openControl: () -> Unit,
    val openSettings: () -> Unit,
    val openAudit: () -> Unit,
    val openDiagnostics: () -> Unit,
    val openNewTask: () -> Unit,
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
    const val BACKEND_BANNER = "jarvis_backend_banner"
    const val MODEL_ROUTER = "jarvis_model_router"
    const val JOBS = "jarvis_jobs"
    const val AUDIT_EVENTS = "jarvis_audit_events"
    const val EVIDENCE = "jarvis_evidence"
    const val DEVICE_CAPABILITY = "jarvis_device_capability"
    const val VOICE_STATE = "jarvis_voice_state"
    const val QUICK_ACTIONS = "jarvis_quick_actions"
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun JarvisPrimeHomeScreen(
    viewModel: JarvisPrimeHomeViewModel,
    navigation: JarvisHomeNavigation,
    paddingValues: PaddingValues = PaddingValues(),
) {
    val state by viewModel.state.collectAsState()
    LaunchedEffect(Unit) {
        viewModel.refreshServiceStatus()
        viewModel.refreshBackend()
    }

    JarvisPrimeHomeContent(
        state = state,
        navigation = navigation,
        paddingValues = paddingValues,
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
        onRetryBackend = viewModel::refreshBackend,
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
    paddingValues: PaddingValues = PaddingValues(),
    onRetryBackend: () -> Unit = {},
) {
    var emergencyConfirmOpen by remember { mutableStateOf(false) }
    val haptics = rememberJarvisHaptics()

    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .padding(paddingValues)
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
            if (state.backendSync == HomeBackendSync.NOT_PAIRED ||
                state.backendSync == HomeBackendSync.OFFLINE
            ) {
                item {
                    BackendUnavailableBanner(
                        sync = state.backendSync,
                        message = state.backendMessage,
                        onRetry = onRetryBackend,
                        onPair = navigation.openSettings,
                    )
                }
            }
            item {
                AskJarvisBar(
                    enabled = state.presence != JarvisPresence.EMERGENCY_STOP_ACTIVE,
                    onSubmit = onAskSubmitted,
                    onTap = navigation.openChat,
                )
            }
            item {
                QuickActionsCard(
                    enabled = state.presence != JarvisPresence.EMERGENCY_STOP_ACTIVE,
                    onAction = { action ->
                        when (action) {
                            QuickAction.ASK -> navigation.openChat()
                            QuickAction.AUDIT_REPO -> navigation.openNewTask()
                            QuickAction.CONTINUE_CODING -> navigation.openTasksList()
                            QuickAction.RUN_TESTS -> navigation.openNewTask()
                            QuickAction.REVIEW_PATCH -> navigation.openApprovals(null)
                            QuickAction.OPEN_APPROVALS -> navigation.openApprovals(null)
                            QuickAction.OPEN_MEMORY -> navigation.openMemory()
                            QuickAction.START_VOICE -> onVoiceTapped()
                            QuickAction.STOP_ALL -> { /* handled by emergency button below */ }
                        }
                    },
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
            state.modelRouter?.let { router ->
                item {
                    ModelRouterCard(router = router, onClick = navigation.openControl)
                }
            }
            if (state.cockpitJobs.isNotEmpty()) {
                item {
                    JobsCard(jobs = state.cockpitJobs, onClick = navigation.openTasksList)
                }
            }
            item {
                MemoryPulseCard(
                    pulse = state.memoryPulse,
                    onClick = navigation.openMemory,
                )
            }
            if (state.evidence.isNotEmpty()) {
                item {
                    EvidenceCard(evidence = state.evidence, onClick = navigation.openAudit)
                }
            }
            if (state.auditEvents.isNotEmpty()) {
                item {
                    AuditEventsCard(events = state.auditEvents, onClick = navigation.openAudit)
                }
            }
            item {
                VoiceStateCard(phase = state.voicePhase, onClick = onVoiceTapped)
            }
            state.deviceCapability?.let { cap ->
                item {
                    DeviceCapabilityCard(capability = cap, onClick = navigation.openDiagnostics)
                }
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
                        haptics.confirm()
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
    val haptics = rememberJarvisHaptics()
    val label = "Jarvis Prime — ${presence.headline()}"
    Box(
        modifier = modifier
            .testTag(JarvisHomeTestTags.ICON)
            .size(72.dp)
            .clip(CircleShape)
            .background(MaterialTheme.colorScheme.surfaceVariant)
            .border(2.dp, tint, CircleShape)
            .then(
                if (onClick != null) {
                    Modifier.clickable {
                        haptics.tap()
                        onClick()
                    }
                } else {
                    Modifier
                },
            )
            .semantics { contentDescription = label },
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

@Composable
fun BackendUnavailableBanner(
    sync: HomeBackendSync,
    message: String?,
    onRetry: () -> Unit,
    onPair: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val notPaired = sync == HomeBackendSync.NOT_PAIRED
    val title = if (notPaired) "Backend not paired" else "Backend unreachable"
    val body = when {
        notPaired -> "Pair a gateway in Settings to see live jobs, approvals, " +
            "workers, memory, and audit. Local controls still work."
        else -> message ?: "Showing last-known local state. Tap retry once the gateway is up."
    }
    Card(
        modifier = modifier
            .testTag(JarvisHomeTestTags.BACKEND_BANNER)
            .fillMaxWidth()
            .border(2.dp, HermesGoldDeep, RoundedCornerShape(12.dp)),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
    ) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(title, style = MaterialTheme.typography.titleMedium, color = HermesGoldDeep)
            Text(body, style = MaterialTheme.typography.bodySmall)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                if (notPaired) {
                    Button(onClick = onPair) { Text("Open Settings") }
                } else {
                    Button(onClick = onRetry) { Text("Retry") }
                }
            }
        }
    }
}

enum class QuickAction {
    ASK, AUDIT_REPO, CONTINUE_CODING, RUN_TESTS, REVIEW_PATCH,
    OPEN_APPROVALS, OPEN_MEMORY, START_VOICE, STOP_ALL,
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun QuickActionsCard(
    enabled: Boolean,
    onAction: (QuickAction) -> Unit,
    modifier: Modifier = Modifier,
) {
    // Stop-all is intentionally omitted here — it is the dedicated emergency
    // button at the foot of the screen, so it cannot be triggered by a stray tap.
    val actions = listOf(
        QuickAction.ASK to "Ask JARVIS",
        QuickAction.AUDIT_REPO to "Audit repo",
        QuickAction.CONTINUE_CODING to "Continue coding",
        QuickAction.RUN_TESTS to "Run tests",
        QuickAction.REVIEW_PATCH to "Review patch",
        QuickAction.OPEN_APPROVALS to "Approvals",
        QuickAction.OPEN_MEMORY to "Memory",
        QuickAction.START_VOICE to "Start voice",
    )
    Card(
        modifier = modifier
            .testTag(JarvisHomeTestTags.QUICK_ACTIONS)
            .fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
    ) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Quick actions", style = MaterialTheme.typography.labelMedium, color = HermesGold)
            actions.chunked(2).forEach { row ->
                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    row.forEach { (action, label) ->
                        OutlinedButton(
                            onClick = { onAction(action) },
                            enabled = enabled,
                            modifier = Modifier.weight(1f),
                        ) { Text(label, style = MaterialTheme.typography.labelLarge) }
                    }
                    if (row.size == 1) Spacer(Modifier.weight(1f))
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ModelRouterCard(
    router: ModelRouterSummary,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Card(
        modifier = modifier
            .testTag(JarvisHomeTestTags.MODEL_ROUTER)
            .fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
        onClick = onClick,
    ) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text("Model / router", style = MaterialTheme.typography.labelMedium, color = HermesGold)
            Text(router.headline, style = MaterialTheme.typography.titleMedium)
            Text(router.detail, style = MaterialTheme.typography.bodySmall)
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun JobsCard(
    jobs: List<JobSummary>,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Card(
        modifier = modifier
            .testTag(JarvisHomeTestTags.JOBS)
            .fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
        onClick = onClick,
    ) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            val active = jobs.count { it.active }
            Text(
                "Jobs · $active active / ${jobs.size} total",
                style = MaterialTheme.typography.labelMedium,
                color = HermesGold,
            )
            jobs.take(4).forEach { job ->
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(
                        job.title,
                        style = MaterialTheme.typography.bodyMedium,
                        modifier = Modifier.weight(1f),
                    )
                    Text(
                        job.statusLabel,
                        style = MaterialTheme.typography.bodySmall,
                        color = if (job.active) HermesGold else MaterialTheme.colorScheme.onSurface,
                    )
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AuditEventsCard(
    events: List<AuditEventSummary>,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Card(
        modifier = modifier
            .testTag(JarvisHomeTestTags.AUDIT_EVENTS)
            .fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
        onClick = onClick,
    ) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("Audit / ledger", style = MaterialTheme.typography.labelMedium, color = HermesViolet)
            events.forEach { event ->
                val time = event.timestamp?.let { formatTime(it) } ?: event.level
                Text(
                    text = "$time · ${event.message}",
                    style = MaterialTheme.typography.bodySmall,
                )
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun EvidenceCard(
    evidence: List<EvidenceSummary>,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Card(
        modifier = modifier
            .testTag(JarvisHomeTestTags.EVIDENCE)
            .fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
        onClick = onClick,
    ) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("Evidence / research", style = MaterialTheme.typography.labelMedium, color = HermesViolet)
            evidence.forEach { item ->
                Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                    Text(
                        "${item.title} · ${item.strength}",
                        style = MaterialTheme.typography.bodyMedium,
                    )
                    if (item.summary.isNotBlank()) {
                        Text(item.summary, style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun VoiceStateCard(
    phase: VoicePhase,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val label = when (phase) {
        VoicePhase.DORMANT -> "Voice idle"
        VoicePhase.WAITING_FOR_WAKE -> "Listening for “Hey Jarvis”"
        VoicePhase.LISTENING -> "Listening…"
        VoicePhase.THINKING -> "Thinking…"
        VoicePhase.SPEAKING -> "Speaking…"
    }
    Card(
        modifier = modifier
            .testTag(JarvisHomeTestTags.VOICE_STATE)
            .fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
        onClick = onClick,
    ) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text("Voice", style = MaterialTheme.typography.labelMedium, color = HermesGold)
            Text(label, style = MaterialTheme.typography.titleMedium)
            Text("Tap to start voice capture.", style = MaterialTheme.typography.bodySmall)
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DeviceCapabilityCard(
    capability: DeviceCapabilitySummary,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Card(
        modifier = modifier
            .testTag(JarvisHomeTestTags.DEVICE_CAPABILITY)
            .fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
        onClick = onClick,
    ) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text("Device", style = MaterialTheme.typography.labelMedium, color = HermesGold)
            Text(capability.headline, style = MaterialTheme.typography.titleMedium)
            Text(capability.detail, style = MaterialTheme.typography.bodySmall)
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
