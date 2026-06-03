package com.aci.hermes.ui.screens.jobs

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import com.aci.hermes.data.cockpit.CockpitJob
import com.aci.hermes.data.cockpit.JobsSync
import com.aci.hermes.ui.components.JobStatusChip
import com.aci.hermes.ui.components.JobUiState

object JobsScreenTags {
    const val EMPTY = "jobs-empty"
    const val NOT_PAIRED = "jobs-not-paired"
    fun row(id: String): String = "jobs-row-$id"
    fun unblock(id: String): String = "jobs-unblock-$id"
}

/**
 * The Jobs cockpit list. Every backend job (JobQueue + orchestrator, merged by
 * the gateway) bucketed into Active / Blocked / Completed / Failed / Cancelled,
 * with readable status chips and a clear unblock action on every blocked row.
 * No fake jobs: an unpaired gateway shows an honest empty state.
 */
@Composable
fun JobsScreen(
    viewModel: JobsViewModel,
    paddingValues: PaddingValues,
    onOpenJob: (String) -> Unit,
) {
    val state by viewModel.state.collectAsState()
    val snackbarHostState = remember { SnackbarHostState() }

    // Lifecycle-aware polling: fast while resumed, paused on background.
    val lifecycleOwner = LocalLifecycleOwner.current
    DisposableEffect(lifecycleOwner) {
        val observer = LifecycleEventObserver { _, event ->
            when (event) {
                Lifecycle.Event.ON_RESUME -> viewModel.onVisibilityChanged(true)
                Lifecycle.Event.ON_PAUSE -> viewModel.onVisibilityChanged(false)
                else -> Unit
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        viewModel.onVisibilityChanged(true)
        onDispose {
            lifecycleOwner.lifecycle.removeObserver(observer)
            viewModel.onVisibilityChanged(false)
            viewModel.stopPolling()
        }
    }

    LaunchedEffect(state.snackbar) {
        state.snackbar?.let {
            snackbarHostState.showSnackbar(it)
            viewModel.consumeSnackbar()
        }
    }

    Box(modifier = Modifier.fillMaxSize().padding(paddingValues)) {
        when {
            state.sync is JobsSync.NotPaired -> EmptyState(
                text = "Pair a gateway in Settings → Connection to see your jobs.",
                tag = JobsScreenTags.NOT_PAIRED,
            )
            state.isEmpty && state.sync is JobsSync.Error ->
                EmptyState(text = (state.sync as JobsSync.Error).message, tag = JobsScreenTags.EMPTY)
            state.isEmpty -> EmptyState(
                text = "No jobs yet. Dispatch one to get started.",
                tag = JobsScreenTags.EMPTY,
            )
            else -> JobsList(state = state, onOpenJob = onOpenJob, onResume = viewModel::resume)
        }
        SnackbarHost(
            hostState = snackbarHostState,
            modifier = Modifier.align(Alignment.BottomCenter),
        )
    }
}

@Composable
private fun JobsList(
    state: JobsUiState,
    onOpenJob: (String) -> Unit,
    onResume: (String) -> Unit,
) {
    LazyColumn(
        modifier = Modifier.fillMaxSize().padding(horizontal = 16.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
        contentPadding = PaddingValues(vertical = 12.dp),
    ) {
        section("Active", state.active, onOpenJob, onResume)
        section("Blocked", state.blocked, onOpenJob, onResume)
        section("Completed", state.completed, onOpenJob, onResume)
        section("Failed", state.failed, onOpenJob, onResume)
        section("Cancelled", state.cancelled, onOpenJob, onResume)
    }
}

private fun androidx.compose.foundation.lazy.LazyListScope.section(
    title: String,
    jobs: List<CockpitJob>,
    onOpenJob: (String) -> Unit,
    onResume: (String) -> Unit,
) {
    if (jobs.isEmpty()) return
    item(key = "header-$title") {
        Text(
            text = "$title (${jobs.size})",
            style = MaterialTheme.typography.titleSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.padding(top = 8.dp, bottom = 2.dp),
        )
    }
    items(jobs, key = { it.id }) { job ->
        JobRow(job = job, onClick = { onOpenJob(job.id) }, onResume = { onResume(job.id) })
    }
}

@Composable
private fun JobRow(
    job: CockpitJob,
    onClick: () -> Unit,
    onResume: () -> Unit,
) {
    val state = JobUiState.fromWire(job.status)
    Card(
        onClick = onClick,
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
        modifier = Modifier.fillMaxWidth().testTag(JobsScreenTags.row(job.id)),
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Text(text = job.title, style = MaterialTheme.typography.titleSmall)
            JobStatusChip(state = state)
            if (job.workerId.isNotBlank()) {
                Text(
                    text = "Worker: ${job.workerId}",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            if (state.needsAttention) {
                // Waiting-for-approval needs the owner phrase → send to detail;
                // a plain blocked/disconnected job can be resumed inline.
                val waiting = state == JobUiState.WAITING_APPROVAL
                OutlinedButton(
                    onClick = if (waiting) onClick else onResume,
                    modifier = Modifier.testTag(JobsScreenTags.unblock(job.id)),
                ) {
                    Text(if (waiting) "Review / approve" else "Resume")
                }
            }
        }
    }
}

@Composable
private fun EmptyState(text: String, tag: String) {
    Box(
        modifier = Modifier.fillMaxSize().padding(24.dp).testTag(tag),
        contentAlignment = Alignment.Center,
    ) {
        Text(text = text, style = MaterialTheme.typography.bodyLarge)
    }
}
