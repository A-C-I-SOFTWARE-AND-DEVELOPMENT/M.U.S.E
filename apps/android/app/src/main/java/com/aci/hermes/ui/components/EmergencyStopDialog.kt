package com.aci.hermes.ui.components

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.getValue
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.unit.dp
import com.aci.hermes.data.emergency.EmergencyStopState

/**
 * Confirmation dialog used to engage or escalate the emergency stop.
 * The user picks a target level (soft pause / hard stop / lockdown)
 * and may supply an optional reason that ends up in the audit log.
 */
@Composable
fun EmergencyStopConfirmationDialog(
    currentState: EmergencyStopState,
    defaultTarget: EmergencyStopState = nextLevelFor(currentState),
    onDismiss: () -> Unit,
    onConfirm: (target: EmergencyStopState, reason: String?) -> Unit,
) {
    val choices = remember(currentState) { engageOptions(currentState) }
    var selected by remember { mutableStateOf(defaultTarget.coerceInto(choices)) }
    var reason by remember { mutableStateOf("") }

    AlertDialog(
        onDismissRequest = onDismiss,
        modifier = Modifier.testTag(EMERGENCY_STOP_DIALOG_TAG),
        title = { Text("Engage emergency stop?") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text(
                    text = if (currentState.isActive) {
                        "Currently at ${currentState.displayName()}. Escalate to:"
                    } else {
                        "Pick how aggressive this stop should be. You can " +
                            "always escalate further from the Jarvis Control screen."
                    },
                    style = MaterialTheme.typography.bodyMedium,
                )
                Column(Modifier.selectableGroup()) {
                    choices.forEach { option ->
                        TargetOptionRow(
                            option = option,
                            selected = option == selected,
                            onSelect = { selected = option },
                        )
                    }
                }
                OutlinedTextField(
                    value = reason,
                    onValueChange = { reason = it },
                    label = { Text("Reason (optional, appears in audit log)") },
                    singleLine = false,
                    minLines = 2,
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        },
        confirmButton = {
            TextButton(
                onClick = { onConfirm(selected, reason.takeIf { it.isNotBlank() }) },
                modifier = Modifier.testTag(EMERGENCY_STOP_CONFIRM_TAG),
            ) {
                Text("Engage ${selected.displayName()}")
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("Cancel") }
        },
    )
}

@Composable
private fun TargetOptionRow(
    option: EmergencyStopState,
    selected: Boolean,
    onSelect: () -> Unit,
) {
    Column(
        Modifier
            .fillMaxWidth()
            .selectable(selected = selected, role = Role.RadioButton, onClick = onSelect)
            .padding(vertical = 4.dp),
    ) {
        androidx.compose.foundation.layout.Row(
            verticalAlignment = androidx.compose.ui.Alignment.CenterVertically,
        ) {
            RadioButton(selected = selected, onClick = onSelect)
            Text(
                text = option.displayName(),
                style = MaterialTheme.typography.titleSmall,
            )
        }
        Text(
            text = option.shortDescription(),
            style = MaterialTheme.typography.bodySmall,
            modifier = Modifier.padding(start = 48.dp),
        )
    }
}

/**
 * Two-step resume confirmation. The user types/holds the approver
 * identity before confirming — this is a soft second factor so a
 * misclick doesn't yank Jarvis back online.
 */
@Composable
fun ResumeApprovalDialog(
    currentState: EmergencyStopState,
    requestedBy: String?,
    onDismiss: () -> Unit,
    onApprove: (approver: String) -> Unit,
    onDeny: (reason: String?) -> Unit,
) {
    var approver by remember { mutableStateOf("") }
    var denyReason by remember { mutableStateOf("") }

    AlertDialog(
        onDismissRequest = onDismiss,
        modifier = Modifier.testTag(RESUME_APPROVAL_DIALOG_TAG),
        title = { Text("Approve resume?") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text(
                    text = "Jarvis is currently at ${currentState.displayName()}. " +
                        "Approving will return it to INACTIVE.",
                    style = MaterialTheme.typography.bodyMedium,
                )
                if (!requestedBy.isNullOrBlank()) {
                    Text(
                        text = "Resume was requested by: $requestedBy",
                        style = MaterialTheme.typography.bodySmall,
                    )
                }
                OutlinedTextField(
                    value = approver,
                    onValueChange = { approver = it },
                    label = { Text("Approver identifier (required)") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                OutlinedTextField(
                    value = denyReason,
                    onValueChange = { denyReason = it },
                    label = { Text("Or deny with reason") },
                    singleLine = false,
                    minLines = 2,
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        },
        confirmButton = {
            TextButton(
                enabled = approver.isNotBlank(),
                onClick = { onApprove(approver.trim()) },
                modifier = Modifier.testTag(RESUME_APPROVAL_CONFIRM_TAG),
            ) {
                Text("Approve resume")
            }
        },
        dismissButton = {
            TextButton(onClick = {
                onDeny(denyReason.takeIf { it.isNotBlank() })
            }) {
                Text("Deny")
            }
        },
    )
}

private fun nextLevelFor(current: EmergencyStopState): EmergencyStopState =
    when (current) {
        EmergencyStopState.INACTIVE -> EmergencyStopState.SOFT_PAUSE
        EmergencyStopState.SOFT_PAUSE -> EmergencyStopState.HARD_STOP
        EmergencyStopState.HARD_STOP -> EmergencyStopState.LOCKDOWN
        EmergencyStopState.LOCKDOWN -> EmergencyStopState.LOCKDOWN
    }

private fun engageOptions(current: EmergencyStopState): List<EmergencyStopState> {
    val all = listOf(
        EmergencyStopState.SOFT_PAUSE,
        EmergencyStopState.HARD_STOP,
        EmergencyStopState.LOCKDOWN,
    )
    return if (current == EmergencyStopState.INACTIVE) all
    else all.filter { it.severity > current.severity }.ifEmpty { listOf(EmergencyStopState.LOCKDOWN) }
}

private fun EmergencyStopState.coerceInto(choices: List<EmergencyStopState>): EmergencyStopState =
    if (this in choices) this else choices.first()

internal fun EmergencyStopState.displayName(): String = when (this) {
    EmergencyStopState.INACTIVE -> "Inactive"
    EmergencyStopState.SOFT_PAUSE -> "Soft pause"
    EmergencyStopState.HARD_STOP -> "Hard stop"
    EmergencyStopState.LOCKDOWN -> "Lockdown"
}

internal fun EmergencyStopState.shortDescription(): String = when (this) {
    EmergencyStopState.INACTIVE -> "All actions allowed."
    EmergencyStopState.SOFT_PAUSE -> "Block new task starts. In-flight work keeps running."
    EmergencyStopState.HARD_STOP -> "Also block sends, deletes, pushes, and deploys."
    EmergencyStopState.LOCKDOWN -> "Block every non-read-only action except status, audit, export, resume."
}

const val EMERGENCY_STOP_DIALOG_TAG = "emergency_stop_dialog"
const val EMERGENCY_STOP_CONFIRM_TAG = "emergency_stop_confirm"
const val RESUME_APPROVAL_DIALOG_TAG = "resume_approval_dialog"
const val RESUME_APPROVAL_CONFIRM_TAG = "resume_approval_confirm"
