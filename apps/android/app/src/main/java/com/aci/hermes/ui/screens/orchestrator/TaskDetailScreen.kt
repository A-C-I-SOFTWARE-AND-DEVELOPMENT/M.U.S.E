package com.aci.hermes.ui.screens.orchestrator

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.ContentCopy
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.OpenInNew
import androidx.compose.material.icons.filled.Save
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
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
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import com.aci.hermes.R
import com.aci.hermes.approval.model.ApprovalRiskTier
import com.aci.hermes.approval.model.ApprovalStatus
import com.aci.hermes.data.model.TargetTool
import com.aci.hermes.data.model.TaskStatus
import com.aci.hermes.data.model.TaskType
import com.aci.hermes.data.model.WorkerPhase

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TaskDetailScreen(
    viewModel: TaskDetailViewModel,
    onBack: () -> Unit,
) {
    val state by viewModel.state.collectAsState()
    val snackbarHostState = remember { SnackbarHostState() }
    var confirmDelete by remember { mutableStateOf(false) }

    LaunchedEffect(state.snackbar) {
        state.snackbar?.let {
            snackbarHostState.showSnackbar(it)
            viewModel.consumeSnackbar()
        }
    }
    LaunchedEffect(state.dismiss) {
        if (state.dismiss) {
            viewModel.consumeDismiss()
            onBack()
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        if (state.isNew) stringResource(R.string.task_detail_new_title)
                        else stringResource(R.string.task_detail_edit_title)
                    )
                },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = null)
                    }
                },
                actions = {
                    IconButton(onClick = viewModel::save, enabled = !state.saving) {
                        Icon(Icons.Default.Save, contentDescription = stringResource(R.string.action_save))
                    }
                    if (!state.isNew) {
                        IconButton(onClick = { confirmDelete = true }) {
                            Icon(Icons.Default.Delete, contentDescription = stringResource(R.string.action_delete))
                        }
                    }
                },
            )
        },
        snackbarHost = { SnackbarHost(snackbarHostState) },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp)
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            OutlinedTextField(
                value = state.task.title,
                onValueChange = viewModel::setTitle,
                label = { Text(stringResource(R.string.task_field_title)) },
                modifier = Modifier.fillMaxWidth(),
            )
            OutlinedTextField(
                value = state.task.description,
                onValueChange = viewModel::setDescription,
                label = { Text(stringResource(R.string.task_field_description)) },
                modifier = Modifier.fillMaxWidth(),
                minLines = 4,
            )
            OutlinedTextField(
                value = state.task.workspacePath ?: "",
                onValueChange = viewModel::setWorkspacePath,
                label = { Text(stringResource(R.string.task_field_workspace_path)) },
                modifier = Modifier.fillMaxWidth(),
            )

            EnumDropdown(
                label = stringResource(R.string.task_field_task_type),
                selected = state.task.taskType,
                values = TaskType.entries,
                toLabel = { it.name.lowercase().replaceFirstChar(Char::titlecase) },
                onSelect = viewModel::setTaskType,
            )
            EnumDropdown(
                label = stringResource(R.string.task_field_target_tool),
                selected = state.task.targetTool,
                values = TargetTool.entries,
                toLabel = { it.name.lowercase().replace('_', ' ').replaceFirstChar(Char::titlecase) },
                onSelect = viewModel::setTargetTool,
            )
            EnumDropdown(
                label = stringResource(R.string.task_field_status),
                selected = state.task.status,
                values = TaskStatus.entries,
                toLabel = { it.name.lowercase().replace('_', ' ').replaceFirstChar(Char::titlecase) },
                onSelect = viewModel::setStatus,
            )

            OutlinedTextField(
                value = state.task.reviewNotes ?: "",
                onValueChange = viewModel::setReviewNotes,
                label = { Text(stringResource(R.string.task_field_review_notes)) },
                modifier = Modifier.fillMaxWidth(),
                minLines = 2,
            )
            OutlinedTextField(
                value = state.task.resultNotes ?: "",
                onValueChange = viewModel::setResultNotes,
                label = { Text(stringResource(R.string.task_field_result_notes)) },
                modifier = Modifier.fillMaxWidth(),
                minLines = 2,
            )
            OutlinedTextField(
                value = state.task.nextAction ?: "",
                onValueChange = viewModel::setNextAction,
                label = { Text(stringResource(R.string.task_field_next_action)) },
                modifier = Modifier.fillMaxWidth(),
            )

            // --- Jarvis Prime worker-card fields ---
            EnumDropdown(
                label = stringResource(R.string.task_field_risk_tier),
                selected = state.task.riskTier,
                values = ApprovalRiskTier.entries,
                toLabel = { it.name.lowercase().replaceFirstChar(Char::titlecase) },
                onSelect = viewModel::setRiskTier,
            )
            EnumDropdown(
                label = stringResource(R.string.task_field_worker_phase),
                selected = state.task.workerPhase,
                values = WorkerPhase.entries,
                toLabel = { it.name.lowercase().replace('_', ' ').replaceFirstChar(Char::titlecase) },
                onSelect = viewModel::setWorkerPhase,
            )
            EnumDropdown(
                label = stringResource(R.string.task_field_approval_state),
                selected = state.task.approvalState,
                values = approvalStateOptions,
                toLabel = { approvalStateLabel(it) },
                onSelect = viewModel::setApprovalState,
            )
            OutlinedTextField(
                value = state.task.evidenceSummary ?: "",
                onValueChange = viewModel::setEvidenceSummary,
                label = { Text(stringResource(R.string.task_field_evidence_summary)) },
                modifier = Modifier.fillMaxWidth(),
                minLines = 2,
            )
            OutlinedTextField(
                value = state.task.blockedReason ?: "",
                onValueChange = viewModel::setBlockedReason,
                label = { Text(stringResource(R.string.task_field_blocked_reason)) },
                modifier = Modifier.fillMaxWidth(),
                minLines = 2,
            )
            OutlinedTextField(
                value = state.task.rollbackSummary ?: "",
                onValueChange = viewModel::setRollbackSummary,
                label = { Text(stringResource(R.string.task_field_rollback_summary)) },
                modifier = Modifier.fillMaxWidth(),
                minLines = 2,
            )
            OutlinedTextField(
                value = state.task.verificationResult ?: "",
                onValueChange = viewModel::setVerificationResult,
                label = { Text(stringResource(R.string.task_field_verification_result)) },
                modifier = Modifier.fillMaxWidth(),
                minLines = 2,
            )
            OutlinedTextField(
                value = state.task.proofLink ?: "",
                onValueChange = viewModel::setProofLink,
                label = { Text(stringResource(R.string.task_field_proof_link)) },
                modifier = Modifier.fillMaxWidth(),
            )

            Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)) {
                Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        AssistChip(
                            onClick = viewModel::copyPrompt,
                            label = { Text(stringResource(R.string.orchestrator_copy_prompt)) },
                            leadingIcon = { Icon(Icons.Default.ContentCopy, contentDescription = null) },
                        )
                        if (state.allowExternalAppOpening) {
                            AssistChip(
                                onClick = viewModel::openTool,
                                label = { Text(stringResource(R.string.orchestrator_open_tool)) },
                                leadingIcon = { Icon(Icons.Default.OpenInNew, contentDescription = null) },
                            )
                        }
                    }
                    HorizontalDivider()
                    Text(
                        text = stringResource(R.string.task_detail_prompt_preview),
                        style = MaterialTheme.typography.titleSmall,
                        color = MaterialTheme.colorScheme.primary,
                    )
                    Text(
                        text = state.promptPreview,
                        style = MaterialTheme.typography.bodySmall.copy(fontFamily = FontFamily.Monospace),
                    )
                }
            }

            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = viewModel::markHandedOff) {
                    Text(stringResource(R.string.task_detail_mark_handed_off))
                }
                OutlinedButton(onClick = viewModel::save, enabled = !state.saving) {
                    Text(stringResource(R.string.action_save))
                }
            }
        }
    }

    if (confirmDelete) {
        AlertDialog(
            onDismissRequest = { confirmDelete = false },
            title = { Text(stringResource(R.string.action_delete)) },
            text = { Text(stringResource(R.string.task_detail_delete_confirm)) },
            confirmButton = {
                TextButton(onClick = {
                    confirmDelete = false
                    viewModel.delete()
                }) { Text(stringResource(R.string.action_delete)) }
            },
            dismissButton = {
                TextButton(onClick = { confirmDelete = false }) {
                    Text(stringResource(R.string.action_cancel))
                }
            },
        )
    }
}

/** Approval-state options for the dropdown; null = "Not required". */
private val approvalStateOptions: List<ApprovalStatus?> = listOf<ApprovalStatus?>(null) + ApprovalStatus.entries

private fun approvalStateLabel(state: ApprovalStatus?): String = when (state) {
    null -> "Not required"
    else -> state.name.lowercase().replace('_', ' ').replaceFirstChar(Char::titlecase)
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun <T> EnumDropdown(
    label: String,
    selected: T,
    values: List<T>,
    toLabel: (T) -> String,
    onSelect: (T) -> Unit,
) {
    var expanded by remember { mutableStateOf(false) }
    ExposedDropdownMenuBox(expanded = expanded, onExpandedChange = { expanded = it }) {
        OutlinedTextField(
            value = toLabel(selected),
            onValueChange = {},
            readOnly = true,
            label = { Text(label) },
            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = expanded) },
            modifier = Modifier
                .fillMaxWidth()
                .menuAnchor(),
        )
        ExposedDropdownMenu(
            expanded = expanded,
            onDismissRequest = { expanded = false },
        ) {
            values.forEach { value ->
                DropdownMenuItem(
                    text = { Text(toLabel(value)) },
                    onClick = {
                        onSelect(value)
                        expanded = false
                    },
                )
            }
        }
    }
}
