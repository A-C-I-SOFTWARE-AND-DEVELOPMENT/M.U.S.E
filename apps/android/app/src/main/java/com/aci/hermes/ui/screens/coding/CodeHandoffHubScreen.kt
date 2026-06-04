package com.aci.hermes.ui.screens.coding

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
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.unit.dp
import com.aci.hermes.data.coding.SavedCodingTask

/**
 * Code Handoff Hub — every saved coding task grouped by where it is in the
 * flow. The place to pick a queued task back up, copy its prompt, retry
 * planning once a backend is online, or open the packet.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CodeHandoffHubScreen(
    viewModel: CodeHandoffHubViewModel,
    onBack: () -> Unit,
    onOpenPacket: (taskId: String) -> Unit,
    onNewTask: () -> Unit,
) {
    val state by viewModel.state.collectAsState()
    val snackbar = remember { SnackbarHostState() }
    val clipboard = LocalClipboardManager.current

    LaunchedEffect(state.copyText) {
        state.copyText?.let {
            clipboard.setText(AnnotatedString(it))
            viewModel.consumeCopy()
            snackbar.showSnackbar("Prompt copied to clipboard")
        }
    }
    LaunchedEffect(state.message) {
        state.message?.let {
            snackbar.showSnackbar(it)
            viewModel.clearMessage()
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Code handoff") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                },
            )
        },
        snackbarHost = { SnackbarHost(snackbar) },
    ) { padding ->
        if (state.total == 0) {
            EmptyHub(modifier = Modifier.padding(padding), onNewTask = onNewTask)
            return@Scaffold
        }
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 16.dp)
                .testTag(CodingTestTags.HUB_LIST),
            verticalArrangement = Arrangement.spacedBy(8.dp),
            contentPadding = androidx.compose.foundation.layout.PaddingValues(vertical = 16.dp),
        ) {
            state.groups.forEach { group ->
                item(key = "h-${group.state.name}") {
                    Text(
                        "${group.state.label} · ${group.tasks.size}",
                        style = MaterialTheme.typography.labelLarge,
                        modifier = Modifier.padding(top = 8.dp),
                    )
                }
                items(group.tasks, key = { it.id }) { task ->
                    HandoffCard(
                        task = task,
                        busy = state.busyId == task.id,
                        onOpen = { onOpenPacket(task.id) },
                        onCopy = { viewModel.copyPrompt(task.id) },
                        onRetry = { viewModel.retry(task.id) },
                        onDelete = { viewModel.delete(task.id) },
                    )
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun HandoffCard(
    task: SavedCodingTask,
    busy: Boolean,
    onOpen: () -> Unit,
    onCopy: () -> Unit,
    onRetry: () -> Unit,
    onDelete: () -> Unit,
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
        onClick = onOpen,
    ) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(task.title, style = MaterialTheme.typography.titleSmall)
            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                task.packet?.riskClass?.takeIf { it.isNotBlank() }?.let {
                    AssistChip(onClick = onOpen, label = { Text(it) })
                }
                if (task.demo) AssistChip(onClick = onOpen, label = { Text("demo") })
            }
            task.note?.takeIf { it.isNotBlank() }?.let {
                Text(it, style = MaterialTheme.typography.bodySmall)
            }
            Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                TextButton(onClick = onCopy) { Text("Copy prompt") }
                TextButton(onClick = onRetry, enabled = !busy) { Text("Retry") }
                TextButton(onClick = onDelete) { Text("Delete") }
            }
        }
    }
}

@Composable
private fun EmptyHub(modifier: Modifier, onNewTask: () -> Unit) {
    Column(
        modifier = modifier
            .fillMaxSize()
            .padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("No coding tasks yet", style = MaterialTheme.typography.titleMedium)
        Text(
            "Create a coding task to generate a bounded work packet, copy a Claude " +
                "Code prompt, or dispatch a gated backend execute. Queued tasks show up " +
                "here so you can pick them back up.",
            style = MaterialTheme.typography.bodyMedium,
        )
        TextButton(onClick = onNewTask) { Text("New coding task") }
    }
}
