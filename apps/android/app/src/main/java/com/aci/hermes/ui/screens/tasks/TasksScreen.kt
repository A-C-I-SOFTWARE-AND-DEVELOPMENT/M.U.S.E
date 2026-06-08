package com.aci.hermes.ui.screens.tasks

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListScope
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExtendedFloatingActionButton
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
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
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.aci.hermes.R
import com.aci.hermes.data.cockpit.CockpitJob
import com.aci.hermes.data.cockpit.JobLane
import com.aci.hermes.data.cockpit.JobsSync
import com.aci.hermes.data.model.HermesTask
import com.aci.hermes.data.model.TaskSection
import com.aci.hermes.data.model.TaskStatus
import com.aci.hermes.data.model.WorkerPhase
import com.aci.hermes.data.model.linksApprovals
import com.aci.hermes.data.model.linksAudit
import com.aci.hermes.data.model.section
import com.aci.hermes.ui.screens.jobs.CockpitJobsViewModel
import com.aci.hermes.ui.screens.jobs.CockpitJobsUiState
import com.aci.hermes.ui.screens.orchestrator.OrchestratorViewModel

/**
 * Standalone Tasks tab. Owns task list + new-task FAB. Pulls state from the
 * same [OrchestratorViewModel] used by Home so changes propagate without an
 * extra refresh.
 *
 * Cards are grouped into the five MUSE sections (Active / Waiting for
 * Approval / Blocked / Failed / Complete), derived purely from each task's
 * data via [HermesTask.section]. Waiting-for-approval cards deep-link to the
 * Approvals tab; completed (and proof-carrying) cards deep-link to Audit.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TasksScreen(
    viewModel: OrchestratorViewModel,
    paddingValues: PaddingValues,
    onOpenTask: (taskId: String?) -> Unit,
    onOpenApprovals: () -> Unit = {},
    onOpenAudit: () -> Unit = {},
    jobsViewModel: CockpitJobsViewModel? = null,
) {
    val state by viewModel.state.collectAsState()
    val snackbarHostState = remember { SnackbarHostState() }

    LaunchedEffect(state.snackbar) {
        state.snackbar?.let {
            snackbarHostState.showSnackbar(it)
            viewModel.consumeSnackbar()
        }
    }

    // Backend orchestration jobs (cockpit contract §4) — only when a jobs VM is
    // wired in (production via the nav graph; null in @Preview / older callers).
    val jobsState: CockpitJobsUiState? = jobsViewModel?.ui?.collectAsState()?.value
    LaunchedEffect(jobsState?.snackbar) {
        jobsState?.snackbar?.let {
            snackbarHostState.showSnackbar(it)
            jobsViewModel?.consumeSnackbar()
        }
    }

    var showDispatch by remember { mutableStateOf(false) }
    var runTarget by remember { mutableStateOf<CockpitJob?>(null) }

    Box(modifier = Modifier.fillMaxSize().padding(paddingValues)) {
        val grouped = remember(state.tasks) { state.tasks.groupBy { it.section() } }
        LazyColumn(
            modifier = Modifier.fillMaxSize().padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
            contentPadding = PaddingValues(top = 12.dp, bottom = 96.dp),
        ) {
            if (jobsState != null) {
                backendJobsSection(
                    jobsState = jobsState,
                    onNew = { showDispatch = true },
                    onRun = { job -> runTarget = job },
                    onCancel = { job -> jobsViewModel?.cancel(job.id) },
                )
            }

            // Local handoff tasks — behavior unchanged.
            if (state.tasks.isEmpty()) {
                item(key = "local_tasks_empty") { LocalTasksEmpty() }
            } else {
                item(key = "local_tasks_header") {
                    SectionHeader(title = stringResource(R.string.orchestrator_tasks_title), count = state.tasks.size)
                }
                TaskSection.entries.forEach { sectionKey ->
                    val sectionTasks = grouped[sectionKey].orEmpty()
                    if (sectionTasks.isNotEmpty()) {
                        item(key = "header_$sectionKey") {
                            SectionHeader(
                                title = stringResource(sectionTitleRes(sectionKey)),
                                count = sectionTasks.size,
                            )
                        }
                        items(sectionTasks, key = { it.id }) { task ->
                            TaskRow(
                                task = task,
                                onTap = { onOpenTask(task.id) },
                                onCopyPrompt = { viewModel.copyPromptForTask(task) },
                                onOpenApprovals = onOpenApprovals,
                                onOpenAudit = onOpenAudit,
                            )
                        }
                    }
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

    if (showDispatch && jobsViewModel != null && jobsState != null) {
        DispatchJobDialog(
            onDismiss = { showDispatch = false },
            onDispatch = { prompt ->
                jobsViewModel.dispatch(prompt)
                showDispatch = false
            },
        )
    }

    runTarget?.let { job ->
        RunJobDialog(
            job = job,
            lanes = jobsState?.lanes.orEmpty(),
            onDismiss = { runTarget = null },
            onRun = { workerId, authorization ->
                jobsViewModel?.run(job.id, workerId, authorization)
                runTarget = null
            },
        )
    }
}

/** A friendly empty state for the local handoff task list. */
@Composable
private fun LocalTasksEmpty() {
    Column(modifier = Modifier.padding(top = 12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(
            text = stringResource(R.string.tasks_empty_title),
            style = MaterialTheme.typography.titleSmall,
            color = MaterialTheme.colorScheme.primary,
        )
        Text(
            text = stringResource(R.string.tasks_empty_body),
            style = MaterialTheme.typography.bodyMedium,
        )
    }
}

// ─── Backend orchestration jobs (cockpit §4) ──────────────────────────────

/**
 * Renders the *Backend jobs* section: header + a "new job" entry, then the real
 * jobs from the gateway. Honest empty/not-paired/error states — never a fake
 * job. Kept as a [LazyListScope] extension so it composes inline above the
 * local handoff tasks in the same scrolling list.
 */
private fun LazyListScope.backendJobsSection(
    jobsState: CockpitJobsUiState,
    onNew: () -> Unit,
    onRun: (CockpitJob) -> Unit,
    onCancel: (CockpitJob) -> Unit,
) {
    item(key = "jobs_header") {
        Row(
            modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            SectionHeader(title = stringResource(R.string.jobs_section_title), count = jobsState.jobs.size)
            OutlinedButton(onClick = onNew) { Text(stringResource(R.string.jobs_new)) }
        }
    }

    when (val sync = jobsState.sync) {
        is JobsSync.NotPaired -> item(key = "jobs_not_paired") {
            JobsNotice(stringResource(R.string.jobs_not_paired))
        }
        is JobsSync.Error -> item(key = "jobs_error") {
            JobsNotice(stringResource(R.string.jobs_error_loading, sync.message), emphasised = true)
        }
        else -> if (jobsState.jobs.isEmpty()) {
            item(key = "jobs_empty") { JobsNotice(stringResource(R.string.jobs_empty)) }
        }
    }

    items(jobsState.jobs, key = { "job_" + it.id }) { job ->
        JobRow(job = job, onRun = { onRun(job) }, onCancel = { onCancel(job) })
    }
}

@Composable
private fun JobsNotice(text: String, emphasised: Boolean = false) {
    Text(
        text = text,
        style = MaterialTheme.typography.bodyMedium,
        color = if (emphasised) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurfaceVariant,
        modifier = Modifier.padding(vertical = 4.dp),
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun JobRow(job: CockpitJob, onRun: () -> Unit, onCancel: () -> Unit) {
    val terminal = job.status.uppercase() in TERMINAL_JOB_STATUSES
    // Only orchestrator jobs (orc- ids) are runnable by job_run; JobQueue
    // entries from other surfaces show Cancel only (Run would 404).
    val runnable = CockpitJobsViewModel.isRunnable(job)
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(job.title.ifBlank { job.id }, style = MaterialTheme.typography.titleMedium)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                AssistChip(onClick = {}, label = { Text(job.status.lowercase().replace('_', ' ')) })
                if (job.workerId.isNotBlank()) {
                    AssistChip(onClick = {}, label = { Text(job.workerId.lowercase().replace('_', ' ')) })
                }
                job.validationSummary?.let { v ->
                    AssistChip(onClick = {}, label = { Text("✓${v.pass} ✗${v.fail} …${v.pending}") })
                }
            }
            job.branch?.takeIf { it.isNotBlank() }?.let {
                Text(text = it, style = MaterialTheme.typography.bodySmall)
            }
            HorizontalDivider()
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                if (runnable) {
                    Button(onClick = onRun, enabled = !terminal) { Text(stringResource(R.string.jobs_run)) }
                }
                OutlinedButton(onClick = onCancel, enabled = !terminal) { Text(stringResource(R.string.jobs_cancel)) }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun DispatchJobDialog(
    onDismiss: () -> Unit,
    onDispatch: (prompt: String) -> Unit,
) {
    var prompt by remember { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(stringResource(R.string.jobs_new)) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(stringResource(R.string.jobs_new_body), style = MaterialTheme.typography.bodySmall)
                OutlinedTextField(
                    value = prompt,
                    onValueChange = { prompt = it },
                    label = { Text(stringResource(R.string.jobs_field_prompt)) },
                )
            }
        },
        confirmButton = {
            Button(
                onClick = { onDispatch(prompt.trim()) },
                enabled = prompt.isNotBlank(),
            ) { Text(stringResource(R.string.jobs_dispatch)) }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text(stringResource(android.R.string.cancel)) } },
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun RunJobDialog(
    job: CockpitJob,
    lanes: List<JobLane>,
    onDismiss: () -> Unit,
    onRun: (workerId: String, authorization: String?) -> Unit,
) {
    // Default to the non-gated local planner when present, else the first lane.
    var workerId by remember {
        mutableStateOf(
            lanes.firstOrNull { !it.requiresApproval }?.id
                ?: lanes.firstOrNull()?.id.orEmpty(),
        )
    }
    var phrase by remember { mutableStateOf("") }
    val selectedLane = lanes.firstOrNull { it.id == workerId }
    val needsOwner = CockpitJobsViewModel.runRequiresAuthorization(selectedLane)
    val ownerPhrase = stringResource(R.string.jobs_run_owner_phrase_hint)

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(stringResource(R.string.jobs_run) + ": " + job.title.ifBlank { job.id }) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                if (lanes.isNotEmpty()) {
                    Text(stringResource(R.string.jobs_field_worker), style = MaterialTheme.typography.labelMedium)
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        lanes.forEach { lane ->
                            FilterChip(
                                selected = lane.id == workerId,
                                onClick = { workerId = lane.id },
                                label = { Text(lane.displayName.ifBlank { lane.id }) },
                            )
                        }
                    }
                }
                if (needsOwner) {
                    Text(stringResource(R.string.jobs_run_owner_title), style = MaterialTheme.typography.titleSmall, color = MaterialTheme.colorScheme.error)
                    Text(stringResource(R.string.jobs_run_owner_body), style = MaterialTheme.typography.bodySmall)
                    OutlinedTextField(
                        value = phrase,
                        onValueChange = { phrase = it },
                        label = { Text(ownerPhrase) },
                        singleLine = true,
                    )
                }
            }
        },
        confirmButton = {
            Button(
                onClick = { onRun(workerId, if (needsOwner) phrase.trim() else null) },
                // Owner gate: when authorization is required, the Run button stays
                // disabled until the exact owner phrase is typed. The gateway
                // re-checks it server-side regardless.
                enabled = workerId.isNotBlank() && (!needsOwner || phrase.trim() == ownerPhrase),
            ) { Text(stringResource(R.string.jobs_run)) }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text(stringResource(android.R.string.cancel)) } },
    )
}

private val TERMINAL_JOB_STATUSES =
    setOf("PUBLISHED", "FAILED", "CANCELLED", "COMPLETED")

private fun sectionTitleRes(section: TaskSection): Int = when (section) {
    TaskSection.ACTIVE -> R.string.tasks_section_active
    TaskSection.WAITING_FOR_APPROVAL -> R.string.tasks_section_waiting_for_approval
    TaskSection.BLOCKED -> R.string.tasks_section_blocked
    TaskSection.FAILED -> R.string.tasks_section_failed
    TaskSection.COMPLETE -> R.string.tasks_section_complete
}

@Composable
private fun SectionHeader(title: String, count: Int) {
    Text(
        text = "$title · $count",
        style = MaterialTheme.typography.titleSmall,
        color = MaterialTheme.colorScheme.primary,
        modifier = Modifier.padding(top = 8.dp),
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun TaskRow(
    task: HermesTask,
    onTap: () -> Unit,
    onCopyPrompt: () -> Unit,
    onOpenApprovals: () -> Unit,
    onOpenAudit: () -> Unit,
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
            Row(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                AssistChip(
                    onClick = onTap,
                    label = { Text(stringResource(R.string.task_card_risk_chip, task.riskTier.name.lowercase())) },
                )
                AssistChip(
                    onClick = onTap,
                    label = { Text(stringResource(R.string.task_card_phase_chip, workerPhaseLabel(task.workerPhase))) },
                )
            }
            if (task.description.isNotBlank()) {
                Text(
                    text = task.description.take(140) + if (task.description.length > 140) "…" else "",
                    style = MaterialTheme.typography.bodySmall,
                )
            }
            task.evidenceSummary?.takeIf { it.isNotBlank() }?.let {
                CardField(stringResource(R.string.task_card_evidence_label), it)
            }
            if (task.status == TaskStatus.NEEDS_REVISION || task.blockedReason != null) {
                task.blockedReason?.takeIf { it.isNotBlank() }?.let {
                    CardField(stringResource(R.string.task_card_blocked_label), it, emphasised = true)
                }
            }
            task.rollbackSummary?.takeIf { it.isNotBlank() }?.let {
                CardField(stringResource(R.string.task_card_rollback_label), it)
            }
            task.verificationResult?.takeIf { it.isNotBlank() }?.let {
                CardField(stringResource(R.string.task_card_verification_label), it)
            }
            task.nextAction?.takeIf { it.isNotBlank() }?.let {
                CardField(stringResource(R.string.task_card_next_action_label), it)
            }
            HorizontalDivider()
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = onCopyPrompt) { Text(stringResource(R.string.orchestrator_copy_prompt)) }
                OutlinedButton(onClick = onTap) { Text(stringResource(R.string.orchestrator_open_task)) }
                if (task.linksApprovals()) {
                    OutlinedButton(onClick = onOpenApprovals) {
                        Text(stringResource(R.string.task_card_open_approvals))
                    }
                }
                if (task.linksAudit()) {
                    OutlinedButton(onClick = onOpenAudit) {
                        Text(stringResource(R.string.task_card_open_audit))
                    }
                }
            }
        }
    }
}

@Composable
private fun CardField(label: String, body: String, emphasised: Boolean = false) {
    Column {
        Text(
            text = label,
            style = MaterialTheme.typography.labelMedium,
            color = if (emphasised) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.primary,
        )
        Text(text = body, style = MaterialTheme.typography.bodySmall)
    }
}

private fun workerPhaseLabel(phase: WorkerPhase): String = when (phase) {
    WorkerPhase.PLANNER -> "Planner"
    WorkerPhase.NAVIGATOR -> "Navigator"
    WorkerPhase.EDITOR -> "Editor"
    WorkerPhase.EXECUTOR -> "Executor"
    WorkerPhase.REVIEWER -> "Reviewer"
    WorkerPhase.JARVIS_FINAL_SYNTHESIS -> "Jarvis Final Synthesis"
}
