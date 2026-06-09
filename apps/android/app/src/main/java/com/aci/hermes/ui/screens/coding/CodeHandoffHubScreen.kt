package com.aci.hermes.ui.screens.coding

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.AnnotatedString
import com.aci.hermes.data.coding.SavedCodingTask
import com.aci.hermes.ui.designsystem.MuseButton
import com.aci.hermes.ui.designsystem.MuseButtonVariant
import com.aci.hermes.ui.designsystem.MuseCard
import com.aci.hermes.ui.designsystem.MuseChip
import com.aci.hermes.ui.designsystem.MuseEmptyState
import com.aci.hermes.ui.designsystem.MuseSectionHeader
import com.aci.hermes.ui.theme.JarvisSignal
import com.aci.hermes.ui.theme.JarvisSignalDim
import com.aci.hermes.ui.theme.JarvisTokens

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
                .padding(horizontal = JarvisTokens.SpaceLg)
                .testTag(CodingTestTags.HUB_LIST),
            verticalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm),
            contentPadding = PaddingValues(vertical = JarvisTokens.SpaceLg),
        ) {
            state.groups.forEach { group ->
                item(key = "h-${group.state.name}") {
                    MuseSectionHeader(
                        title = group.state.label,
                        modifier = Modifier.padding(top = JarvisTokens.SpaceSm),
                        trailing = { MuseChip(label = "${group.tasks.size}") },
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

@Composable
private fun HandoffCard(
    task: SavedCodingTask,
    busy: Boolean,
    onOpen: () -> Unit,
    onCopy: () -> Unit,
    onRetry: () -> Unit,
    onDelete: () -> Unit,
) {
    MuseCard(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onOpen),
    ) {
        Column(Modifier.padding(JarvisTokens.SpaceLg), verticalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm)) {
            Text(task.title, style = MaterialTheme.typography.titleSmall, color = JarvisSignal)
            Row(horizontalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm)) {
                task.packet?.riskClass?.takeIf { it.isNotBlank() }?.let {
                    MuseChip(label = it, onClick = onOpen)
                }
                if (task.demo) MuseChip(label = "demo", onClick = onOpen)
            }
            task.note?.takeIf { it.isNotBlank() }?.let {
                Text(it, style = MaterialTheme.typography.bodySmall, color = JarvisSignalDim)
            }
            Row(horizontalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm)) {
                MuseButton(onClick = onCopy, text = "Copy prompt", variant = MuseButtonVariant.Secondary)
                MuseButton(onClick = onRetry, text = "Retry", variant = MuseButtonVariant.Secondary, enabled = !busy)
                MuseButton(onClick = onDelete, text = "Delete", variant = MuseButtonVariant.Danger)
            }
        }
    }
}

@Composable
private fun EmptyHub(modifier: Modifier, onNewTask: () -> Unit) {
    Box(
        modifier = modifier.fillMaxSize(),
        contentAlignment = Alignment.Center,
    ) {
        MuseEmptyState(
            title = "No coding tasks yet",
            body = "Create a coding task to generate a bounded work packet, copy a Claude " +
                "Code prompt, or dispatch a gated backend execute. Queued tasks show up " +
                "here so you can pick them back up.",
            actionLabel = "New coding task",
            onAction = onNewTask,
        )
    }
}
