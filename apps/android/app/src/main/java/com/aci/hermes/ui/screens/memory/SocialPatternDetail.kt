package com.aci.hermes.ui.screens.memory

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
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
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
import androidx.compose.ui.unit.dp
import com.aci.hermes.R
import com.aci.hermes.data.model.PatternProvenance
import com.aci.hermes.data.model.PrivacyRisk
import com.aci.hermes.data.model.SocialPattern
import com.aci.hermes.data.social.PrivacyRedactor

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SocialPatternDetail(
    viewModel: MemoryViewModel,
    patternId: String,
    onBack: () -> Unit,
) {
    LaunchedEffect(patternId) { viewModel.selectPattern(patternId) }
    val raw by viewModel.detailState.collectAsState()
    val pattern = raw?.let(PrivacyRedactor::sanitize)

    var confirmDelete by remember { mutableStateOf(false) }
    var editMode by remember { mutableStateOf(false) }
    var titleEdit by remember(pattern?.id) { mutableStateOf(pattern?.title.orEmpty()) }
    var summaryEdit by remember(pattern?.id) { mutableStateOf(pattern?.summary.orEmpty()) }
    var safeEdit by remember(pattern?.id) { mutableStateOf(pattern?.safeUsage.orEmpty()) }
    var unsafeEdit by remember(pattern?.id) { mutableStateOf(pattern?.unsafeUsage.orEmpty()) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.memory_detail_title)) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = null)
                    }
                },
            )
        },
    ) { padding ->
        if (pattern == null) {
            Column(
                modifier = Modifier.fillMaxSize().padding(padding).padding(16.dp),
            ) {
                Text(stringResource(R.string.memory_detail_missing))
            }
            return@Scaffold
        }

        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp)
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            HeaderCard(pattern)
            if (pattern.privacyRisk == PrivacyRisk.HIGH) {
                HighRiskBanner()
            }
            if (editMode) {
                EditCard(
                    title = titleEdit,
                    summary = summaryEdit,
                    safe = safeEdit,
                    unsafe = unsafeEdit,
                    onTitle = { titleEdit = it },
                    onSummary = { summaryEdit = it },
                    onSafe = { safeEdit = it },
                    onUnsafe = { unsafeEdit = it },
                )
            } else {
                SummaryCard(pattern)
                SafeUnsafeCard(pattern)
            }
            ProvenanceCard(pattern.provenance)
            ActionsRow(
                editMode = editMode,
                onEdit = {
                    titleEdit = pattern.title
                    summaryEdit = pattern.summary
                    safeEdit = pattern.safeUsage
                    unsafeEdit = pattern.unsafeUsage
                    editMode = true
                },
                onCancelEdit = { editMode = false },
                onSaveCorrection = {
                    viewModel.correct(
                        id = pattern.id,
                        title = titleEdit,
                        summary = summaryEdit,
                        safeUsage = safeEdit,
                        unsafeUsage = unsafeEdit,
                    )
                    editMode = false
                },
                onDelete = { confirmDelete = true },
            )
        }
    }

    val deleteTargetId = pattern?.id
    if (confirmDelete && deleteTargetId != null) {
        AlertDialog(
            onDismissRequest = { confirmDelete = false },
            title = { Text(stringResource(R.string.memory_delete_title)) },
            text = { Text(stringResource(R.string.memory_delete_body)) },
            confirmButton = {
                TextButton(onClick = {
                    confirmDelete = false
                    viewModel.delete(deleteTargetId)
                    onBack()
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

@Composable
private fun HeaderCard(pattern: SocialPattern) {
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)) {
        Column(
            modifier = Modifier.fillMaxWidth().padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Text(pattern.title.ifBlank { "(untitled pattern)" }, style = MaterialTheme.typography.titleLarge)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(pattern.kind.displayName, style = MaterialTheme.typography.bodyMedium)
                PrivacyRiskChip(pattern.privacyRisk)
            }
            if (pattern.identityFlags.isNotEmpty()) {
                Text(
                    text = "Private identity flagged: ${pattern.identityFlags.joinToString(", ")}",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.error,
                )
            }
        }
    }
}

@Composable
private fun HighRiskBanner() {
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.errorContainer)) {
        Column(modifier = Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(
                text = stringResource(R.string.memory_high_risk_title),
                style = MaterialTheme.typography.titleSmall,
                color = MaterialTheme.colorScheme.onErrorContainer,
            )
            Text(
                text = stringResource(R.string.memory_high_risk_body),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onErrorContainer,
            )
        }
    }
}

@Composable
private fun SummaryCard(pattern: SocialPattern) {
    SectionCard(stringResource(R.string.memory_section_summary)) {
        Text(
            text = if (pattern.privacyRisk == PrivacyRisk.HIGH) {
                stringResource(R.string.memory_high_risk_summary_hidden)
            } else {
                pattern.summary
            },
            style = MaterialTheme.typography.bodyMedium,
        )
    }
}

@Composable
private fun SafeUnsafeCard(pattern: SocialPattern) {
    SectionCard(stringResource(R.string.memory_section_safe_usage)) {
        Text(pattern.safeUsage, style = MaterialTheme.typography.bodyMedium)
    }
    SectionCard(stringResource(R.string.memory_section_unsafe_usage)) {
        Text(pattern.unsafeUsage, style = MaterialTheme.typography.bodyMedium)
    }
}

@Composable
private fun ProvenanceCard(provenance: List<PatternProvenance>) {
    SectionCard(stringResource(R.string.memory_section_provenance)) {
        if (provenance.isEmpty()) {
            Text(stringResource(R.string.memory_provenance_empty), style = MaterialTheme.typography.bodyMedium)
            return@SectionCard
        }
        provenance.forEach { entry ->
            Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                Text(entry.sourceTitle, style = MaterialTheme.typography.titleSmall)
                Text(entry.sourceKind.displayName, style = MaterialTheme.typography.bodySmall)
                entry.sourceUrl?.let {
                    Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.primary)
                }
                entry.note?.let {
                    Text(it, style = MaterialTheme.typography.bodySmall)
                }
            }
            HorizontalDivider()
        }
    }
}

@Composable
private fun EditCard(
    title: String,
    summary: String,
    safe: String,
    unsafe: String,
    onTitle: (String) -> Unit,
    onSummary: (String) -> Unit,
    onSafe: (String) -> Unit,
    onUnsafe: (String) -> Unit,
) {
    SectionCard(stringResource(R.string.memory_section_correct)) {
        OutlinedTextField(
            value = title,
            onValueChange = onTitle,
            label = { Text(stringResource(R.string.memory_field_title)) },
            modifier = Modifier.fillMaxWidth(),
        )
        OutlinedTextField(
            value = summary,
            onValueChange = onSummary,
            label = { Text(stringResource(R.string.memory_field_summary)) },
            modifier = Modifier.fillMaxWidth(),
            minLines = 3,
        )
        OutlinedTextField(
            value = safe,
            onValueChange = onSafe,
            label = { Text(stringResource(R.string.memory_field_safe_usage)) },
            modifier = Modifier.fillMaxWidth(),
            minLines = 2,
        )
        OutlinedTextField(
            value = unsafe,
            onValueChange = onUnsafe,
            label = { Text(stringResource(R.string.memory_field_unsafe_usage)) },
            modifier = Modifier.fillMaxWidth(),
            minLines = 2,
        )
    }
}

@Composable
private fun ActionsRow(
    editMode: Boolean,
    onEdit: () -> Unit,
    onCancelEdit: () -> Unit,
    onSaveCorrection: () -> Unit,
    onDelete: () -> Unit,
) {
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        if (editMode) {
            Button(onClick = onSaveCorrection) {
                Text(stringResource(R.string.memory_action_save_correction))
            }
            OutlinedButton(onClick = onCancelEdit) {
                Text(stringResource(R.string.action_cancel))
            }
        } else {
            OutlinedButton(onClick = onEdit) {
                Text(stringResource(R.string.memory_action_correct))
            }
            OutlinedButton(onClick = onDelete) {
                Text(stringResource(R.string.action_delete))
            }
        }
    }
}

@Composable
private fun SectionCard(title: String, content: @Composable () -> Unit) {
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)) {
        Column(
            modifier = Modifier.fillMaxWidth().padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Text(title, style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.primary)
            HorizontalDivider()
            content()
        }
    }
}
