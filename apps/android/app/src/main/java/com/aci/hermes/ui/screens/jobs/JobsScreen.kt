package com.aci.hermes.ui.screens.jobs

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
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.aci.hermes.R
import com.aci.hermes.data.cockpit.CockpitJob
import com.aci.hermes.data.cockpit.JobsSync
import com.aci.hermes.ui.components.GatewayStatusPill
import com.aci.hermes.ui.components.GatewayStatus

object JobsScreenTags {
    const val LIST = "jobs-list"
    const val EMPTY = "jobs-empty"
    const val NOT_PAIRED = "jobs-not-paired"
    const val LOADING = "jobs-loading"
    const val ERROR = "jobs-error"
    fun row(id: String): String = "jobs-row-$id"
}

/**
 * Cockpit orchestration Jobs screen, rendered inside [JarvisShell] (so the
 * shell owns the top bar + globally-visible emergency stop). Status-first:
 * a [GatewayStatusPill] reflects the live [JobsSync] state before the list
 * paints. Honest empty / not-paired / loading / error+retry states — never a
 * fabricated job.
 *
 * Backed by [JobsViewModel] → `CockpitJobsRepository` → `/v1/cockpit/jobs`.
 * Cancel is a destructive action gated behind a confirmation dialog.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun JobsScreen(
    viewModel: JobsViewModel,
    paddingValues: PaddingValues,
) {
    val jobs by viewModel.jobs.collectAsState()
    val sync by viewModel.sync.collectAsState()
    val message by viewModel.message.collectAsState()

    var pendingCancel by remember { mutableStateOf<CockpitJob?>(null) }
    val snackbarHostState = remember { SnackbarHostState() }

    // Surface a failed cancel (e.g. 404 for an /orchestrate job not in the
    // JobQueue, or a 409 terminal conflict) so the action is never silently
    // dropped after the dialog closes.
    val cancelFailedTemplate = stringResource(R.string.jobs_cancel_failed)
    LaunchedEffect(message) {
        message?.let {
            snackbarHostState.showSnackbar(String.format(cancelFailedTemplate, it))
            viewModel.consumeMessage()
        }
    }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .padding(paddingValues),
    ) {
        Column(modifier = Modifier.fillMaxSize()) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 12.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    text = stringResource(R.string.jobs_title),
                    style = MaterialTheme.typography.titleMedium,
                    color = MaterialTheme.colorScheme.primary,
                )
                GatewayStatusPill(status = sync.toGatewayStatus())
            }

            when (val s = sync) {
                is JobsSync.Error -> ErrorState(message = s.message, onRetry = viewModel::refresh)
                JobsSync.NotPaired -> NotPairedState()
                JobsSync.Loading -> if (jobs.isEmpty()) LoadingState() else JobList(jobs) { pendingCancel = it }
                JobsSync.Idle,
                is JobsSync.Loaded -> if (jobs.isEmpty()) EmptyState(onRetry = viewModel::refresh) else JobList(jobs) { pendingCancel = it }
            }
        }

        SnackbarHost(
            hostState = snackbarHostState,
            modifier = Modifier.align(Alignment.BottomCenter),
        )
    }

    pendingCancel?.let { job ->
        AlertDialog(
            onDismissRequest = { pendingCancel = null },
            title = { Text(stringResource(R.string.jobs_cancel_title)) },
            text = { Text(stringResource(R.string.jobs_cancel_body, job.title.ifBlank { job.id })) },
            confirmButton = {
                TextButton(onClick = {
                    viewModel.cancel(job.id)
                    pendingCancel = null
                }) { Text(stringResource(R.string.jobs_cancel_confirm)) }
            },
            dismissButton = {
                TextButton(onClick = { pendingCancel = null }) {
                    Text(stringResource(R.string.action_cancel))
                }
            },
        )
    }
}

@Composable
private fun JobList(jobs: List<CockpitJob>, onCancel: (CockpitJob) -> Unit) {
    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .padding(horizontal = 16.dp)
            .testTag(JobsScreenTags.LIST),
        verticalArrangement = Arrangement.spacedBy(12.dp),
        contentPadding = PaddingValues(bottom = 24.dp),
    ) {
        items(jobs, key = CockpitJob::id) { job ->
            JobCard(job = job, onCancel = { onCancel(job) })
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun JobCard(job: CockpitJob, onCancel: () -> Unit) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .testTag(JobsScreenTags.row(job.id)),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Text(
                text = job.title.ifBlank { job.id },
                style = MaterialTheme.typography.titleMedium,
            )
            Row(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                AssistChip(onClick = {}, label = { Text(job.status.lowercase().replace('_', ' ')) })
                AssistChip(onClick = {}, label = { Text(job.workerId) })
            }
            job.branch?.takeIf { it.isNotBlank() }?.let {
                Text(
                    text = stringResource(R.string.jobs_branch_label, it),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            job.validationSummary?.let { v ->
                Text(
                    text = stringResource(R.string.jobs_validation_label, v.pass, v.fail, v.pending),
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            if (!job.isTerminal()) {
                OutlinedButton(onClick = onCancel) {
                    Text(stringResource(R.string.jobs_cancel_action))
                }
            }
        }
    }
}

@Composable
private fun NotPairedState() {
    CenteredMessage(
        tag = JobsScreenTags.NOT_PAIRED,
        title = stringResource(R.string.jobs_not_paired_title),
        body = stringResource(R.string.jobs_not_paired_body),
    )
}

@Composable
private fun EmptyState(onRetry: () -> Unit) {
    CenteredMessage(
        tag = JobsScreenTags.EMPTY,
        title = stringResource(R.string.jobs_empty_title),
        body = stringResource(R.string.jobs_empty_body),
        actionLabel = stringResource(R.string.action_retry),
        onAction = onRetry,
    )
}

@Composable
private fun ErrorState(message: String, onRetry: () -> Unit) {
    CenteredMessage(
        tag = JobsScreenTags.ERROR,
        title = stringResource(R.string.jobs_error_title),
        body = message,
        actionLabel = stringResource(R.string.action_retry),
        onAction = onRetry,
    )
}

@Composable
private fun LoadingState() {
    Box(
        modifier = Modifier
            .fillMaxSize()
            .testTag(JobsScreenTags.LOADING),
        contentAlignment = Alignment.Center,
    ) {
        CircularProgressIndicator()
    }
}

@Composable
private fun CenteredMessage(
    tag: String,
    title: String,
    body: String,
    actionLabel: String? = null,
    onAction: (() -> Unit)? = null,
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(32.dp)
            .testTag(tag),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(
            text = title,
            style = MaterialTheme.typography.titleMedium,
            color = MaterialTheme.colorScheme.primary,
        )
        Text(
            text = body,
            style = MaterialTheme.typography.bodyMedium,
            modifier = Modifier.padding(top = 8.dp),
        )
        if (actionLabel != null && onAction != null) {
            Button(onClick = onAction, modifier = Modifier.padding(top = 16.dp)) {
                Text(actionLabel)
            }
        }
    }
}

private fun JobsSync.toGatewayStatus(): GatewayStatus = when (this) {
    is JobsSync.Loaded -> GatewayStatus.ONLINE
    JobsSync.Loading -> GatewayStatus.WORKING
    JobsSync.Idle -> GatewayStatus.WORKING
    JobsSync.NotPaired -> GatewayStatus.MOCK
    is JobsSync.Error -> GatewayStatus.DISCONNECTED
}

/** Terminal jobs can't be cancelled; hide the cancel affordance. */
private fun CockpitJob.isTerminal(): Boolean =
    status.uppercase() in setOf("COMPLETED", "COMPLETE", "FAILED", "CANCELLED", "CANCELED", "MERGED", "DONE")
