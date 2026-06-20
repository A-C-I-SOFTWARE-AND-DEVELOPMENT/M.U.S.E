package com.aci.hermes.ui.screens.jobs

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.MutableTransitionState
import androidx.compose.animation.fadeIn
import androidx.compose.animation.slideInVertically
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.MaterialTheme
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
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import com.aci.hermes.data.cockpit.CockpitJob
import com.aci.hermes.data.cockpit.JobsSync
import com.aci.hermes.ui.components.JobStatusChip
import com.aci.hermes.ui.components.JobUiState
import com.aci.hermes.ui.designsystem.museButton
import com.aci.hermes.ui.designsystem.museButtonVariant
import com.aci.hermes.ui.designsystem.museCard
import com.aci.hermes.ui.designsystem.museChip
import com.aci.hermes.ui.designsystem.museEmptyState
import com.aci.hermes.ui.designsystem.museMotion
import com.aci.hermes.ui.designsystem.museSectionHeader
import com.aci.hermes.ui.theme.JarvisSignal
import com.aci.hermes.ui.theme.JarvisTokens

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
            state.sync is JobsSync.NotPaired -> JobsEmptyState(
                title = "No gateway paired",
                body = "Pair a gateway in Settings → Connection to see your jobs.",
                tag = JobsScreenTags.NOT_PAIRED,
            )
            state.isEmpty && state.sync is JobsSync.Error ->
                JobsEmptyState(
                    title = "Couldn't reach the gateway",
                    body = (state.sync as JobsSync.Error).message,
                    tag = JobsScreenTags.EMPTY,
                )
            state.isEmpty -> JobsEmptyState(
                title = "No jobs yet",
                body = "Dispatch an orchestrated job and it will show up here with live phases.",
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
        modifier = Modifier.fillMaxSize().padding(horizontal = JarvisTokens.SpaceLg),
        verticalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm),
        contentPadding = PaddingValues(vertical = JarvisTokens.SpaceMd),
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
        museSectionHeader(
            title = title,
            modifier = Modifier.padding(top = JarvisTokens.SpaceSm),
            trailing = { museChip(label = "${jobs.size}") },
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
    // Subtle entrance: rows fade + rise in on the standard curve.
    val appear = remember { MutableTransitionState(false).apply { targetState = true } }
    AnimatedVisibility(
        visibleState = appear,
        enter = fadeIn(museMotion.standard()) +
            slideInVertically(museMotion.standard()) { it / 6 },
    ) {
        museCard(
            modifier = Modifier
                .fillMaxWidth()
                .testTag(JobsScreenTags.row(job.id))
                .clickable(onClick = onClick),
        ) {
            Column(
                modifier = Modifier.padding(JarvisTokens.SpaceLg),
                verticalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm),
            ) {
                Text(text = job.title, style = MaterialTheme.typography.titleSmall, color = JarvisSignal)
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
                    museButton(
                        onClick = if (waiting) onClick else onResume,
                        text = if (waiting) "Review / approve" else "Resume",
                        variant = if (waiting) museButtonVariant.Approve else museButtonVariant.Secondary,
                        modifier = Modifier.testTag(JobsScreenTags.unblock(job.id)),
                    )
                }
            }
        }
    }
}

@Composable
private fun JobsEmptyState(title: String, body: String, tag: String) {
    Box(
        modifier = Modifier.fillMaxSize().testTag(tag),
        contentAlignment = Alignment.Center,
    ) {
        museEmptyState(title = title, body = body)
    }
}
