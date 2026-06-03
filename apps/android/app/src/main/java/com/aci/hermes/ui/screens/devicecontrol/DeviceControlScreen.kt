package com.aci.hermes.ui.screens.devicecontrol

import android.Manifest
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.provider.Settings
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.result.contract.ActivityResultContracts.StartActivityForResult
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import com.aci.hermes.data.devicecontrol.DeviceActionLogEntry
import com.aci.hermes.data.devicecontrol.DeviceControlCapability
import com.aci.hermes.ui.components.CardTier
import com.aci.hermes.ui.components.CommandCard
import com.aci.hermes.ui.components.EmergencyStopButton
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * Device control — the consent + awareness surface for letting JARVIS
 * Prime operate the phone. Reached from the Control tab.
 *
 * It is the owner's single place to: enable/disable device control,
 * grant or revoke each capability, decide whether sensitive actions need
 * confirming, see at a glance whether control is active right now, halt
 * everything, and read the log of every device action Jarvis took.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DeviceControlScreen(
    viewModel: DeviceControlViewModel,
    onBack: () -> Unit,
) {
    val state by viewModel.state.collectAsState()
    val context = androidx.compose.ui.platform.LocalContext.current

    // Read OS grant status on first show. Returning from a system settings
    // page or a runtime prompt refreshes again via the launcher callbacks
    // below, so the granted/​not-granted chips stay accurate.
    LaunchedEffect(Unit) { viewModel.refresh() }

    // Runtime permission launchers + system-settings deep links, reusing the
    // same approach as JarvisLiveScreen.
    val micLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) { viewModel.refresh() }
    val notifLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) { viewModel.refresh() }
    val settingsLauncher = rememberLauncherForActivityResult(StartActivityForResult()) {
        viewModel.refresh()
    }

    val onGrant: (DeviceControlCapability) -> Unit = { cap ->
        when (cap) {
            DeviceControlCapability.ACCESSIBILITY ->
                settingsLauncher.launch(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
            DeviceControlCapability.OVERLAY ->
                settingsLauncher.launch(
                    Intent(
                        Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                        Uri.parse("package:" + context.packageName),
                    ),
                )
            DeviceControlCapability.MICROPHONE ->
                micLauncher.launch(Manifest.permission.RECORD_AUDIO)
            DeviceControlCapability.NOTIFICATIONS ->
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                    notifLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
                } else {
                    settingsLauncher.launch(
                        Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS)
                            .putExtra(Settings.EXTRA_APP_PACKAGE, context.packageName),
                    )
                }
            DeviceControlCapability.PACKAGE_VISIBILITY,
            DeviceControlCapability.BACKEND_CONNECTION ->
                settingsLauncher.launch(
                    Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS)
                        .setData(Uri.parse("package:" + context.packageName)),
                )
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Device control") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
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
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            ActiveIndicator(activeNow = state.activeNow, halted = state.halted)

            // Master switch + sensitive-action posture.
            CommandCard(
                title = "Let Jarvis operate this phone",
                subtitle = "Master switch. While off, no device action runs — every request " +
                    "is logged and refused.",
                tier = if (state.enabled) CardTier.ACTIVE else CardTier.INFO,
            ) {
                ToggleRow(
                    label = "Device control",
                    checked = state.enabled,
                    onCheckedChange = viewModel::setEnabled,
                )
                HorizontalDivider()
                ToggleRow(
                    label = "Confirm sensitive actions",
                    sublabel = "Launching an app or tapping a target waits for your OK. " +
                        "Turn off for hands-free high-power mode (still logged).",
                    checked = state.confirmSensitive,
                    onCheckedChange = viewModel::requestConfirmSensitive,
                )
            }

            // The six capabilities.
            CommandCard(
                title = "Capabilities",
                subtitle = "Enable each capability you want Jarvis to use. You can revoke " +
                    "consent here instantly; the action layer honors it immediately.",
            ) {
                state.capabilities.forEachIndexed { index, row ->
                    if (index > 0) HorizontalDivider()
                    CapabilityRow(
                        capability = row.capability,
                        consented = row.consented,
                        granted = row.granted,
                        onConsentChange = { viewModel.setCapabilityConsent(row.capability, it) },
                        onGrant = { onGrant(row.capability) },
                    )
                }
            }

            // Emergency stop / release.
            CommandCard(
                title = "Emergency stop",
                subtitle = "Drops every gesture, stops the floating avatar and the voice loop, " +
                    "and refuses new device actions until you release it.",
                tier = CardTier.CRITICAL,
            ) {
                if (state.halted) {
                    Text(
                        "Device control is halted.",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.error,
                    )
                    OutlinedButton(
                        onClick = viewModel::releaseEmergencyStop,
                        modifier = Modifier.fillMaxWidth(),
                    ) { Text("Release halt") }
                } else {
                    EmergencyStopButton(onConfirmed = viewModel::engageEmergencyStop)
                }
            }

            // Action log.
            CommandCard(
                title = "Recent device actions",
                subtitle = "Every action Jarvis took or was refused, newest first.",
                tier = CardTier.MEMORY,
            ) {
                if (state.recent.isEmpty()) {
                    Text(
                        "No device actions yet.",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                } else {
                    state.recent.forEach { entry ->
                        ActionLogRow(entry)
                    }
                }
            }

            Spacer(Modifier.size(8.dp))
        }
    }

    if (state.confirmDisableSensitive) {
        AlertDialog(
            onDismissRequest = viewModel::dismissDisableSensitive,
            title = { Text("Turn off confirmation?") },
            text = {
                Text(
                    "Jarvis will launch apps and tap targets immediately, without asking " +
                        "first. Every action is still logged, and the emergency stop still " +
                        "halts everything. Only do this if you want hands-free high-power mode.",
                )
            },
            confirmButton = {
                TextButton(onClick = viewModel::confirmDisableSensitiveProceed) {
                    Text("Turn off", color = MaterialTheme.colorScheme.error)
                }
            },
            dismissButton = {
                TextButton(onClick = viewModel::dismissDisableSensitive) { Text("Keep on") }
            },
        )
    }
}

@Composable
private fun ActiveIndicator(activeNow: Boolean, halted: Boolean) {
    val (dotColor, label) = when {
        halted -> MaterialTheme.colorScheme.error to "Halted — device control stopped"
        activeNow -> MaterialTheme.colorScheme.primary to "Active — Jarvis can operate this phone"
        else -> MaterialTheme.colorScheme.onSurfaceVariant to "Idle — device control not active"
    }
    Row(
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Surface(shape = CircleShape, color = dotColor, modifier = Modifier.size(12.dp)) {}
        Text(label, style = MaterialTheme.typography.titleSmall)
    }
}

@Composable
private fun ToggleRow(
    label: String,
    checked: Boolean,
    onCheckedChange: (Boolean) -> Unit,
    sublabel: String? = null,
) {
    Row(
        verticalAlignment = Alignment.CenterVertically,
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(modifier = Modifier.weight(1f)) {
            Text(label, style = MaterialTheme.typography.bodyLarge)
            if (sublabel != null) {
                Text(
                    sublabel,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
        Switch(checked = checked, onCheckedChange = onCheckedChange)
    }
}

@Composable
private fun CapabilityRow(
    capability: DeviceControlCapability,
    consented: Boolean,
    granted: Boolean,
    onConsentChange: (Boolean) -> Unit,
    onGrant: () -> Unit,
) {
    Column(
        modifier = Modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth()) {
            Column(modifier = Modifier.weight(1f)) {
                Text(capability.title, style = MaterialTheme.typography.bodyLarge)
                Text(
                    capability.explanation,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Switch(checked = consented, onCheckedChange = onConsentChange)
        }
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            val statusColor =
                if (granted) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.error
            Surface(shape = CircleShape, color = statusColor, modifier = Modifier.size(8.dp)) {}
            Text(
                if (granted) "Granted by system" else "Not granted",
                style = MaterialTheme.typography.labelMedium,
                color = statusColor,
            )
            if (!granted) {
                TextButton(onClick = onGrant) { Text("Grant") }
            }
        }
    }
}

@Composable
private fun ActionLogRow(entry: DeviceActionLogEntry) {
    Row(
        modifier = Modifier.fillMaxWidth().padding(vertical = 2.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        val color = when (entry.outcome) {
            DeviceActionLogEntry.Outcome.EXECUTED,
            DeviceActionLogEntry.Outcome.APPROVED -> MaterialTheme.colorScheme.primary
            DeviceActionLogEntry.Outcome.NEEDS_CONFIRMATION -> MaterialTheme.colorScheme.tertiary
            DeviceActionLogEntry.Outcome.BLOCKED,
            DeviceActionLogEntry.Outcome.EXECUTION_FAILED -> MaterialTheme.colorScheme.error
        }
        Surface(shape = CircleShape, color = color, modifier = Modifier.size(8.dp)) {}
        Column(modifier = Modifier.weight(1f)) {
            Text(entry.intentLabel, style = MaterialTheme.typography.bodyMedium)
            Text(
                buildString {
                    append(entry.outcome.name.lowercase().replace('_', ' '))
                    entry.reason?.let { append(" · ").append(it.replace('_', ' ')) }
                },
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        Text(
            TIME_FORMAT.format(Date(entry.timestamp)),
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            fontFamily = FontFamily.Monospace,
        )
    }
}

private val TIME_FORMAT = SimpleDateFormat("HH:mm:ss", Locale.getDefault())
