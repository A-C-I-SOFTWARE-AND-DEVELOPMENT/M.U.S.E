package com.aci.hermes.ui.screens.tasks

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Assignment
import androidx.compose.material.icons.filled.Add
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
import com.aci.hermes.data.model.TaskSection
import com.aci.hermes.data.model.TaskStatus
import com.aci.hermes.data.model.WorkerPhase
import com.aci.hermes.data.model.linksApprovals
import com.aci.hermes.data.model.linksAudit
import com.aci.hermes.data.model.section
import com.aci.hermes.ui.components.ChipTone
import com.aci.hermes.ui.components.EmptyState
import com.aci.hermes.ui.components.StatusChip
import com.aci.hermes.ui.components.chipTone
import com.aci.hermes.ui.screens.orchestrator.OrchestratorViewModel

/**
 * Standalone Tasks tab. Owns task list + new-task FAB. Pulls state from the
 * same [OrchestratorViewModel] used by Home so changes propagate without an
 * extra refresh.
 *
 * Cards are grouped into the five Jarvis Prime sections (Active / Waiting for
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
            EmptyState(
                icon = Icons.AutoMirrored.Filled.Assignment,
                title = stringResource(R.string.tasks_empty_title),
                body = stringResource(R.string.tasks_empty_body),
                actionLabel = stringResource(R.string.orchestrator_new_task),
                onAction = { onOpenTask(null) },
            )
        } else {
            val grouped = remember(state.tasks) { state.tasks.groupBy { it.section() } }
            LazyColumn(
                modifier = Modifier.fillMaxSize().padding(horizontal = 16.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
                contentPadding = PaddingValues(top = 12.dp, bottom = 96.dp),
            ) {
                // Render every section in a fixed order; only non-empty ones appear.
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
}

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

@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
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
            FlowRow(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                // Status + risk are color-coded so a high-risk or stalled task
                // reads at a glance; the rest are neutral context chips. All
                // are display-only — the card owns the tap.
                StatusChip(label = taskStatusLabel(task.status), tone = task.status.chipTone())
                StatusChip(label = task.riskTier.name, tone = task.riskTier.chipTone())
                StatusChip(
                    label = task.taskType.name.lowercase().replaceFirstChar(Char::titlecase),
                    tone = ChipTone.NEUTRAL,
                )
                StatusChip(
                    label = task.targetTool.name.lowercase().replace('_', ' ').replaceFirstChar(Char::titlecase),
                    tone = ChipTone.NEUTRAL,
                )
                StatusChip(
                    label = stringResource(R.string.task_card_phase_chip, workerPhaseLabel(task.workerPhase)),
                    tone = ChipTone.NEUTRAL,
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

@Composable
private fun taskStatusLabel(status: TaskStatus): String = stringResource(
    when (status) {
        TaskStatus.DRAFT -> R.string.task_status_chip_draft
        TaskStatus.READY_FOR_HANDOFF -> R.string.task_status_chip_ready
        TaskStatus.HANDED_TO_CODEX -> R.string.task_status_chip_with_codex
        TaskStatus.HANDED_TO_CLAUDE -> R.string.task_status_chip_with_claude
        TaskStatus.IN_REVIEW -> R.string.task_status_chip_in_review
        TaskStatus.NEEDS_REVISION -> R.string.task_status_chip_needs_revision
        TaskStatus.COMPLETE -> R.string.task_status_chip_complete
    },
)
