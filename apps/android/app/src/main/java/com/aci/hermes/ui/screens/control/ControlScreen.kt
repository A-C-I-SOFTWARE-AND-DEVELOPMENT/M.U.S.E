package com.aci.hermes.ui.screens.control

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import com.aci.hermes.data.jarvis.AutonomyMode
import com.aci.hermes.data.jarvis.GatewayState
import com.aci.hermes.data.jarvis.IconState
import com.aci.hermes.data.jarvis.JarvisControlState
import com.aci.hermes.data.jarvis.NotificationsState
import com.aci.hermes.data.jarvis.PermissionState
import com.aci.hermes.data.jarvis.PendingWarning
import com.aci.hermes.data.jarvis.ServiceState
import com.aci.hermes.data.jarvis.VoiceState
import com.aci.hermes.data.jarvis.WarningLevel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ControlScreen(
    viewModel: ControlViewModel,
    onBack: () -> Unit,
    onOpenSettings: () -> Unit,
    onOpenAudit: () -> Unit,
    onOpenMemory: () -> Unit,
) {
    val state by viewModel.state.collectAsState()

    LaunchedEffect(Unit) { viewModel.refresh() }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Jarvis Prime control") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = null)
                    }
                },
                actions = {
                    IconButton(
                        onClick = { viewModel.requestEmergencyStop() },
                    ) {
                        Icon(
                            Icons.Default.Stop,
                            contentDescription = "Emergency stop",
                            tint = MaterialTheme.colorScheme.error,
                        )
                    }
                },
            )
        },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp)
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            JarvisStatusCard(state)
            EmergencyStopCard(state, viewModel)
            AutonomyCard(state, viewModel)
            GatewayCard(state, onOpenSettings)
            PermissionsCard(state, onOpenSettings)
            NotificationsCard(state, onOpenSettings)
            VoiceCard(state, onOpenSettings)
            IconCard(state, onOpenSettings)
            SafetyCard(state, viewModel)
            ConnectedServicesCard(state)
            ShortcutsRow(state, onOpenAudit, onOpenMemory)
        }
    }

    state.pendingWarning?.let { warning ->
        WarningDialog(
            warning = warning,
            onConfirm = { viewModel.confirmPendingWarning() },
            onDismiss = { viewModel.dismissPendingWarning() },
        )
    }
}

@Composable
private fun JarvisStatusCard(state: JarvisControlState) {
    SectionCard(title = "Jarvis status") {
        StatusDotRow(
            label = if (state.jarvisRunning) "Jarvis is online" else "Jarvis is offline",
            ok = state.jarvisRunning,
        )
        Text(
            text = when (state.service) {
                ServiceState.RUNNING -> "HermesService is running."
                ServiceState.STOPPED -> "HermesService is stopped."
                ServiceState.DEGRADED -> "HermesService is degraded."
            },
            style = MaterialTheme.typography.bodyMedium,
        )
    }
}

@Composable
private fun EmergencyStopCard(state: JarvisControlState, viewModel: ControlViewModel) {
    val red = MaterialTheme.colorScheme.errorContainer
    Card(
        colors = CardDefaults.cardColors(containerColor = red),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(
                text = "Emergency stop",
                style = MaterialTheme.typography.titleMedium,
                color = MaterialTheme.colorScheme.onErrorContainer,
            )
            Text(
                text = if (state.emergencyStopEngaged)
                    "Engaged. Jarvis is paused and will not initiate any outbound action."
                else
                    "Always visible. Halts Jarvis and any pending automation.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onErrorContainer,
            )
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                if (state.emergencyStopEngaged) {
                    OutlinedButton(onClick = { viewModel.releaseEmergencyStop() }) {
                        Text("Release stop")
                    }
                } else {
                    Button(
                        onClick = { viewModel.requestEmergencyStop() },
                        colors = ButtonDefaults.buttonColors(
                            containerColor = MaterialTheme.colorScheme.error,
                            contentColor = MaterialTheme.colorScheme.onError,
                        ),
                    ) { Text("Engage emergency stop") }
                }
            }
        }
    }
}

@Composable
private fun AutonomyCard(state: JarvisControlState, viewModel: ControlViewModel) {
    SectionCard(title = "Autonomy mode") {
        Text(state.autonomy.summary, style = MaterialTheme.typography.bodyMedium)
        if (state.isLockdown) {
            Text(
                text = "Lockdown engaged — every outbound action is refused.",
                color = MaterialTheme.colorScheme.error,
                style = MaterialTheme.typography.bodySmall,
            )
        }
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            AutonomyMode.entries.forEach { mode ->
                FilterChip(
                    selected = state.autonomy == mode,
                    onClick = { viewModel.requestAutonomyMode(mode) },
                    label = { Text(mode.displayName) },
                )
            }
        }
    }
}

@Composable
private fun GatewayCard(state: JarvisControlState, onOpenSettings: () -> Unit) {
    SectionCard(title = "Gateway") {
        val ok = state.gateway == GatewayState.CONNECTED || state.gateway == GatewayState.MOCK
        StatusDotRow(
            label = when (state.gateway) {
                GatewayState.CONNECTED -> "Connected to ${state.gatewayEndpoint}"
                GatewayState.DISCONNECTED -> "Disconnected — ${state.gatewayEndpoint}"
                GatewayState.MOCK -> "Mock gateway active"
                GatewayState.UNCONFIGURED -> "Gateway endpoint not configured"
            },
            ok = ok,
        )
        OutlinedButton(onClick = onOpenSettings) { Text("Edit gateway settings") }
    }
}

@Composable
private fun PermissionsCard(state: JarvisControlState, onOpenSettings: () -> Unit) {
    SectionCard(title = "Permissions") {
        Text(
            when (state.permissions) {
                PermissionState.GRANTED -> "All required permissions granted."
                PermissionState.PARTIAL -> "Some permissions are missing."
                PermissionState.DENIED -> "Permissions denied. Jarvis features will be limited."
                PermissionState.UNKNOWN -> "Permission status not yet checked."
            },
            style = MaterialTheme.typography.bodyMedium,
        )
        OutlinedButton(onClick = onOpenSettings) { Text("Manage permissions") }
    }
}

@Composable
private fun NotificationsCard(state: JarvisControlState, onOpenSettings: () -> Unit) {
    SectionCard(title = "Notifications") {
        Text(
            when (state.notifications) {
                NotificationsState.ENABLED -> "Notifications enabled."
                NotificationsState.DISABLED -> "Notifications disabled."
                NotificationsState.BLOCKED_BY_SYSTEM -> "Blocked at the system level."
            },
            style = MaterialTheme.typography.bodyMedium,
        )
        OutlinedButton(onClick = onOpenSettings) { Text("Notification settings") }
    }
}

@Composable
private fun VoiceCard(state: JarvisControlState, onOpenSettings: () -> Unit) {
    SectionCard(title = "Voice") {
        Text(
            when (state.voice) {
                VoiceState.ENABLED -> "Voice enabled."
                VoiceState.DISABLED -> "Voice disabled."
                VoiceState.UNAVAILABLE -> "Voice unavailable on this device."
            },
            style = MaterialTheme.typography.bodyMedium,
        )
        OutlinedButton(onClick = onOpenSettings) { Text("Voice settings") }
    }
}

@Composable
private fun IconCard(state: JarvisControlState, onOpenSettings: () -> Unit) {
    SectionCard(title = "Interactive icon") {
        Text(
            when (state.icon) {
                IconState.ENABLED -> "Jarvis Prime icon is enabled."
                IconState.DISABLED -> "Jarvis Prime icon is disabled."
            },
            style = MaterialTheme.typography.bodyMedium,
        )
        OutlinedButton(onClick = onOpenSettings) { Text("Icon settings") }
    }
}

@Composable
private fun SafetyCard(state: JarvisControlState, viewModel: ControlViewModel) {
    SectionCard(title = "Safety rails") {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            AssistChip(
                onClick = { viewModel.requestApprovalsRequired(!state.approvalsRequired) },
                label = {
                    Text(if (state.approvalsRequired) "Approvals: required" else "Approvals: off")
                },
            )
            AssistChip(
                onClick = { viewModel.requestSafetyGatesEnabled(!state.safetyGatesEnabled) },
                label = {
                    Text(if (state.safetyGatesEnabled) "Safety gates: on" else "Safety gates: off")
                },
            )
        }
        Text(
            "Tap a chip to toggle. Disabling either is gated by a serious or critical warning.",
            style = MaterialTheme.typography.bodySmall,
        )
    }
}

@Composable
private fun ConnectedServicesCard(state: JarvisControlState) {
    SectionCard(title = "Connected services") {
        if (state.connectedServices.isEmpty()) {
            Text("Connected services will appear here.", style = MaterialTheme.typography.bodySmall)
        } else {
            state.connectedServices.forEach { svc ->
                StatusDotRow(label = svc.displayName, ok = svc.connected)
            }
            Text(
                "Placeholder — live wiring lands with the gateway poller.",
                style = MaterialTheme.typography.bodySmall,
            )
        }
    }
}

@Composable
private fun ShortcutsRow(
    state: JarvisControlState,
    onOpenAudit: () -> Unit,
    onOpenMemory: () -> Unit,
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        OutlinedButton(onClick = onOpenAudit, modifier = Modifier.weight(1f)) {
            Text("Audit (${state.audit.recentEvents})")
        }
        OutlinedButton(onClick = onOpenMemory, modifier = Modifier.weight(1f)) {
            Text("Memory (${state.memory.savedFacts})")
        }
    }
}

@Composable
private fun SectionCard(title: String, content: @Composable () -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
    ) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(title, style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.primary)
            HorizontalDivider()
            content()
        }
    }
}

@Composable
private fun StatusDotRow(label: String, ok: Boolean) {
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Surface(
            shape = CircleShape,
            color = if (ok) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.error,
            modifier = Modifier.size(12.dp),
        ) {}
        Text(label, style = MaterialTheme.typography.bodyMedium)
    }
}

@Composable
private fun WarningDialog(
    warning: PendingWarning,
    onConfirm: () -> Unit,
    onDismiss: () -> Unit,
) {
    val titleColor = when (warning.level) {
        WarningLevel.CRITICAL -> MaterialTheme.colorScheme.error
        WarningLevel.SERIOUS -> MaterialTheme.colorScheme.error
        WarningLevel.NOTICE -> MaterialTheme.colorScheme.primary
        WarningLevel.NONE -> Color.Unspecified
    }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = {
            Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(warning.level.label, style = MaterialTheme.typography.labelMedium, color = titleColor)
                Text(warning.title, style = MaterialTheme.typography.titleMedium)
            }
        },
        text = { Text(warning.message) },
        confirmButton = {
            TextButton(onClick = onConfirm) { Text(warning.confirmLabel) }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("Cancel") }
        },
    )
}
