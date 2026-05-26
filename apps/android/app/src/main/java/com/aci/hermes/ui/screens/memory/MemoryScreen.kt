package com.aci.hermes.ui.screens.memory

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.aci.hermes.R
import com.aci.hermes.data.model.MemoryItem

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MemoryScreen(
    viewModel: MemoryViewModel,
    onBack: () -> Unit,
) {
    val state by viewModel.state.collectAsState()
    var draft by remember { mutableStateOf("") }
    var editingId by remember { mutableStateOf<String?>(null) }
    var editingDraft by remember { mutableStateOf("") }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.memory_title)) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = stringResource(R.string.action_back))
                    }
                },
            )
        },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 16.dp, vertical = 12.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text(stringResource(R.string.memory_correction_hint), style = MaterialTheme.typography.bodySmall)
            OutlinedTextField(
                value = state.query,
                onValueChange = viewModel::setQuery,
                label = { Text(stringResource(R.string.memory_search)) },
                modifier = Modifier.fillMaxWidth(),
            )
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(
                    value = draft,
                    onValueChange = { draft = it },
                    placeholder = { Text("Remember…") },
                    modifier = Modifier.weight(1f),
                )
                OutlinedButton(onClick = {
                    if (draft.isNotBlank()) {
                        viewModel.remember(draft)
                        draft = ""
                    }
                }) { Text(stringResource(R.string.action_save)) }
            }
            if (state.items.isEmpty()) {
                Text(stringResource(R.string.memory_empty), style = MaterialTheme.typography.bodyMedium)
            } else {
                LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    items(state.items) { item ->
                        MemoryRow(
                            item = item,
                            editing = editingId == item.id,
                            editingDraft = editingDraft,
                            onEdit = {
                                editingId = item.id
                                editingDraft = item.content
                            },
                            onEditChange = { editingDraft = it },
                            onSave = {
                                viewModel.correct(item.id, editingDraft)
                                editingId = null
                                editingDraft = ""
                            },
                            onCancel = {
                                editingId = null
                                editingDraft = ""
                            },
                            onForget = { viewModel.forget(item.id) },
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun MemoryRow(
    item: MemoryItem,
    editing: Boolean,
    editingDraft: String,
    onEdit: () -> Unit,
    onEditChange: (String) -> Unit,
    onSave: () -> Unit,
    onCancel: () -> Unit,
    onForget: () -> Unit,
) {
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)) {
        Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            if (editing) {
                OutlinedTextField(
                    value = editingDraft,
                    onValueChange = onEditChange,
                    modifier = Modifier.fillMaxWidth(),
                )
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedButton(onClick = onSave) { Text(stringResource(R.string.action_save)) }
                    OutlinedButton(onClick = onCancel) { Text(stringResource(R.string.action_cancel)) }
                }
            } else {
                Text(item.content, style = MaterialTheme.typography.bodyMedium)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    AssistChip(onClick = {}, label = { Text(item.kind.name.lowercase()) })
                    if (item.redactedFields.isNotEmpty()) {
                        AssistChip(
                            onClick = {},
                            label = { Text(stringResource(R.string.memory_redacted_label) + ": ${item.redactedFields.size}") },
                        )
                    }
                }
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedButton(onClick = onEdit) { Text(stringResource(R.string.memory_correct)) }
                    OutlinedButton(onClick = onForget) { Text(stringResource(R.string.memory_forget)) }
                }
            }
        }
    }
}
