package com.aci.hermes.ui.screens.tasks

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExtendedFloatingActionButton
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.aci.hermes.R
import com.aci.hermes.data.model.HermesTask
import com.aci.hermes.ui.screens.orchestrator.OrchestratorViewModel

/**
 * Standalone Tasks tab. Owns task list + new-task FAB. Pulls state from the
 * same [OrchestratorViewModel] used by Home so changes propagate without an
 * extra refresh.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TasksScreen(
    viewModel: OrchestratorViewModel,
    paddingValues: PaddingValues,
    onOpenTask: (taskId: String?) -> Unit,
) {
    val state by viewModel.state.collectAsState()
    val snackbarHostState = remember { SnackbarHostState() }

    LaunchedEffect(state.snackbar) {
        state.snackbar?.let {
            snackbarHostState.showSnackbar(it)
            viewModel.consumeSnackbar()
        }
    }

    Box(modifier = Modifier.fillMaxSize().padding(paddingValues)) {
        if (state.tasks.isEmpty()) {
            Column(
                modifier = Modifier.fillMaxSize().padding(32.dp),
                verticalArrangement = Arrangement.Center,
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                Text(
                    text = stringResource(R.string.tasks_empty_title),
                    style = MaterialTheme.typography.titleMedium,
                    color = MaterialTheme.colorScheme.primary,
                )
                Text(
                    text = stringResource(R.string.tasks_empty_body),
                    style = MaterialTheme.typography.bodyMedium,
                    modifier = Modifier.padding(top = 8.dp),
                )
            }
        } else {
            LazyColumn(
                modifier = Modifier.fillMaxSize().padding(horizontal = 16.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
                contentPadding = PaddingValues(top = 12.dp, bottom = 96.dp),
            ) {
                items(state.tasks, key = { it.id }) { task ->
                    TaskRow(
                        task = task,
                        onTap = { onOpenTask(task.id) },
                        onCopyPrompt = { viewModel.copyPromptForTask(task) },
                    )
                }
            }
        }

        ExtendedFloatingActionButton(
            onClick = { onOpenTask(null) },
            icon = { Icon(Icons.Filled.Add, contentDescription = null) },
            text = { Text(stringResource(R.string.orchestrator_new_task)) },
            modifier = Modifier
                .align(Alignment.BottomEnd)
                .padding(16.dp),
        )

        SnackbarHost(
            hostState = snackbarHostState,
            modifier = Modifier.align(Alignment.BottomCenter),
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun TaskRow(
    task: HermesTask,
    onTap: () -> Unit,
    onCopyPrompt: () -> Unit,
) {
    Card(
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
        onClick = onTap,
    ) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(
                task.title.ifBlank { stringResource(R.string.orchestrator_untitled_task) },
                style = MaterialTheme.typography.titleMedium,
            )
            Row(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                AssistChip(onClick = onTap, label = { Text(task.taskType.name.lowercase()) })
                AssistChip(onClick = onTap, label = { Text(task.status.name.lowercase().replace('_', ' ')) })
                AssistChip(onClick = onTap, label = { Text(task.targetTool.name.lowercase().replace('_', ' ')) })
            }
            if (task.description.isNotBlank()) {
                Text(
                    text = task.description.take(140) + if (task.description.length > 140) "…" else "",
                    style = MaterialTheme.typography.bodySmall,
                )
            }
            HorizontalDivider()
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = onCopyPrompt) { Text(stringResource(R.string.orchestrator_copy_prompt)) }
                OutlinedButton(onClick = onTap) { Text(stringResource(R.string.orchestrator_open_task)) }
            }
        }
    }
}
