package com.aci.hermes.ui.screens.memory

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import com.aci.hermes.data.memory.MemoryItem

@Composable
fun CorrectMemoryDialog(
    item: MemoryItem,
    onDismiss: () -> Unit,
    onConfirm: (newContent: String, reason: String?) -> Unit,
) {
    var content by remember(item.id) { mutableStateOf(item.content) }
    var reason by remember(item.id) { mutableStateOf("") }
    val canSubmit = content.isNotBlank() && content != item.content

    AlertDialog(
        onDismissRequest = onDismiss,
        modifier = Modifier.testTag(MemoryScreenTags.CORRECT_DIALOG),
        title = { Text("Correct memory") },
        text = {
            Column(
                modifier = Modifier.fillMaxWidth(),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                Text(
                    text = item.title.ifBlank { "(untitled memory)" },
                    style = MaterialTheme.typography.labelLarge,
                )
                OutlinedTextField(
                    value = content,
                    onValueChange = { content = it },
                    label = { Text("Corrected value") },
                    modifier = Modifier.fillMaxWidth(),
                )
                OutlinedTextField(
                    value = reason,
                    onValueChange = { reason = it },
                    label = { Text("Reason (optional)") },
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        },
        confirmButton = {
            TextButton(
                onClick = { onConfirm(content, reason.ifBlank { null }) },
                enabled = canSubmit,
            ) { Text("Save correction") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } },
    )
}

@Composable
fun DeleteMemoryDialog(
    item: MemoryItem,
    onDismiss: () -> Unit,
    onConfirm: (reason: String?) -> Unit,
) {
    var reason by remember(item.id) { mutableStateOf("") }
    var confirmText by remember(item.id) { mutableStateOf("") }
    val canDelete = confirmText.trim().equals("DELETE", ignoreCase = true)

    AlertDialog(
        onDismissRequest = onDismiss,
        modifier = Modifier.testTag(MemoryScreenTags.DELETE_DIALOG),
        title = { Text("Delete memory") },
        text = {
            Column(
                modifier = Modifier.fillMaxWidth(),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                Text(
                    text = "muse will forget this memory. Deletion cannot be undone from the app.",
                    style = MaterialTheme.typography.bodyMedium,
                )
                Text(
                    text = item.title.ifBlank { "(untitled memory)" },
                    style = MaterialTheme.typography.titleSmall,
                )
                OutlinedTextField(
                    value = reason,
                    onValueChange = { reason = it },
                    label = { Text("Reason (optional)") },
                    modifier = Modifier.fillMaxWidth(),
                )
                OutlinedTextField(
                    value = confirmText,
                    onValueChange = { confirmText = it },
                    label = { Text("Type DELETE to confirm") },
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        },
        confirmButton = {
            TextButton(
                onClick = { onConfirm(reason.ifBlank { null }) },
                enabled = canDelete,
            ) { Text("Delete") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } },
    )
}
