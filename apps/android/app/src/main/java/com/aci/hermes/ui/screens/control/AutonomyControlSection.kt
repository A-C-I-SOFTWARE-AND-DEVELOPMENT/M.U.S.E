package com.aci.hermes.ui.screens.control

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import com.aci.hermes.data.jarvis.AutonomyMode
import com.aci.hermes.data.jarvis.JarvisControlState

/**
 * High-Autonomy Coding control surface. Renders the active autonomy level, its
 * workspace scope, the capability list (auto-approved vs. still-gated — sourced
 * from the backend `approval_policy.capabilities()`), a mode selector, and an
 * instant revoke. Pure over [JarvisControlState] + callbacks so the host screen
 * stays thin and this stays easy to reason about.
 */
@Composable
fun AutonomyControlSection(
    state: JarvisControlState,
    onSelectMode: (AutonomyMode) -> Unit,
    onWorkspaceChange: (String) -> Unit,
    onRevoke: () -> Unit,
    onConfirmWarning: () -> Unit,
    onDismissWarning: () -> Unit,
) {
    Card(
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant,
        ),
    ) {
        Column(
            modifier = Modifier.fillMaxWidth().padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Text(
                text = "Autonomy",
                style = MaterialTheme.typography.titleMedium,
                color = MaterialTheme.colorScheme.primary,
            )
            Text(
                text = "Current: ${state.autonomy.displayName}",
                style = MaterialTheme.typography.titleSmall,
            )
            Text(
                text = state.autonomy.summary,
                style = MaterialTheme.typography.bodyMedium,
            )

            HorizontalDivider()

            // Mode selector — one button per mode; the active one is filled.
            AutonomyMode.entries.forEach { mode ->
                if (mode == state.autonomy) {
                    Button(
                        onClick = { onSelectMode(mode) },
                        modifier = Modifier.fillMaxWidth(),
                    ) { Text(mode.displayName) }
                } else {
                    OutlinedButton(
                        onClick = { onSelectMode(mode) },
                        modifier = Modifier.fillMaxWidth(),
                    ) { Text(mode.displayName) }
                }
            }

            if (state.isHighAutonomyCoding) {
                HorizontalDivider()
                Text(
                    text = "Approved workspace",
                    style = MaterialTheme.typography.titleSmall,
                )
                OutlinedTextField(
                    value = state.codingWorkspaceRoot,
                    onValueChange = onWorkspaceChange,
                    singleLine = true,
                    label = { Text("Workspace path") },
                    modifier = Modifier.fillMaxWidth(),
                )
                val caps = state.autonomyCapabilities
                if (caps.autoApproved.isNotEmpty()) {
                    CapabilityLine(
                        label = "Auto-approved in workspace",
                        items = caps.autoApproved,
                    )
                }
                if (caps.requiresApproval.isNotEmpty()) {
                    CapabilityLine(
                        label = "Still requires approval",
                        items = caps.requiresApproval,
                    )
                }
                if (caps.alwaysDeny.isNotEmpty()) {
                    CapabilityLine(label = "Always denied", items = caps.alwaysDeny)
                }
            }

            HorizontalDivider()
            OutlinedButton(
                onClick = onRevoke,
                modifier = Modifier.fillMaxWidth(),
            ) { Text("Revoke → Assisted") }
        }
    }

    val warning = state.pendingWarning
    if (warning != null) {
        AlertDialog(
            onDismissRequest = onDismissWarning,
            title = { Text(warning.title) },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    if (warning.level.label.isNotEmpty()) {
                        Text(
                            text = warning.level.label,
                            style = MaterialTheme.typography.labelLarge,
                            color = MaterialTheme.colorScheme.error,
                        )
                    }
                    Text(warning.message)
                }
            },
            confirmButton = {
                TextButton(onClick = onConfirmWarning) { Text(warning.confirmLabel) }
            },
            dismissButton = {
                TextButton(onClick = onDismissWarning) { Text("Cancel") }
            },
        )
    }
}

@Composable
private fun CapabilityLine(label: String, items: List<String>) {
    Column {
        Text(text = label, style = MaterialTheme.typography.labelMedium)
        Text(
            text = items.joinToString(", "),
            style = MaterialTheme.typography.bodySmall,
            fontFamily = FontFamily.Monospace,
        )
    }
}
