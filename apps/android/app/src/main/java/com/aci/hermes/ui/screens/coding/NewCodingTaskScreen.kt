package com.aci.hermes.ui.screens.coding

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
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
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
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp

/**
 * Capture a plain-English coding task, preview its classification, and build a
 * bounded work packet. Offline-safe: Generate always lands on a saved task.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun NewCodingTaskScreen(
    viewModel: NewCodingTaskViewModel,
    onBack: () -> Unit,
    onOpenPacket: (taskId: String) -> Unit,
) {
    val state by viewModel.state.collectAsState()
    val snackbar = remember { SnackbarHostState() }

    LaunchedEffect(state.navigateToTaskId) {
        state.navigateToTaskId?.let { id ->
            viewModel.consumeNavigation()
            onOpenPacket(id)
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
                title = { Text("New coding task") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                },
            )
        },
        snackbarHost = { SnackbarHost(snackbar) },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp)
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            ModeBanner(paired = state.paired, mock = state.mock)

            OutlinedTextField(
                value = state.prompt,
                onValueChange = viewModel::updatePrompt,
                modifier = Modifier
                    .fillMaxWidth()
                    .testTag(CodingTestTags.NEW_PROMPT),
                label = { Text("What should JARVIS build, fix, or review?") },
                placeholder = { Text("e.g. Add a retry with backoff to the upload client and cover it with a test") },
                minLines = 3,
            )

            OutlinedTextField(
                value = state.repoRoot,
                onValueChange = viewModel::updateRepoRoot,
                modifier = Modifier.fillMaxWidth(),
                label = { Text("Repo path / context (optional)") },
                placeholder = { Text("/home/you/project  ·  or leave blank for backend default") },
                singleLine = true,
            )

            state.audit?.let { AuditPreviewCard(it) }

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                OutlinedButton(
                    onClick = viewModel::previewClassification,
                    enabled = !state.busy,
                    modifier = Modifier.weight(1f),
                ) { Text("Preview risk") }

                Button(
                    onClick = viewModel::generatePacket,
                    enabled = !state.busy,
                    modifier = Modifier
                        .weight(1f)
                        .testTag(CodingTestTags.NEW_GENERATE),
                ) {
                    if (state.busy) {
                        CircularProgressIndicator(
                            modifier = Modifier.padding(end = 8.dp),
                            strokeWidth = 2.dp,
                        )
                    }
                    Text("Generate work packet")
                }
            }

            Text(
                "Classification, packet building, and execution run on your paired " +
                    "backend. With no backend, the task is saved and queued so you can " +
                    "copy a Claude Code prompt and sync later. Mock mode shows a demo packet.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun ModeBanner(paired: Boolean, mock: Boolean) {
    val (label, detail) = when {
        mock -> "Mock mode" to "Demo packet — no backend, no network. Safe to explore."
        paired -> "Backend paired" to "Classification + packet come from your gateway."
        else -> "Offline" to "No backend paired. Tasks queue locally; copy a prompt to hand off."
    }
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)) {
        Column(Modifier.padding(12.dp)) {
            Text(label, style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.SemiBold)
            Text(detail, style = MaterialTheme.typography.bodySmall)
        }
    }
}

@Composable
private fun AuditPreviewCard(audit: com.aci.hermes.data.cockpit.CodingAuditResult) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .testTag(CodingTestTags.NEW_AUDIT_PREVIEW),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
    ) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text("Classification", style = MaterialTheme.typography.labelMedium)
            LabeledLine("Risk", audit.riskClass.ifBlank { "—" })
            LabeledLine("Worker", audit.primaryWorker.ifBlank { "—" })
            if (audit.ownerGates.isNotEmpty()) {
                LabeledLine("Owner gates", audit.ownerGates.joinToString(", "))
            }
            if (audit.rationale.isNotBlank()) {
                Text(audit.rationale, style = MaterialTheme.typography.bodySmall)
            }
            if (audit.blocked) {
                Text(
                    "Blocked: this request needs owner authorization before it can proceed.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.error,
                )
            }
        }
    }
}

@Composable
private fun LabeledLine(label: String, value: String) {
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Text("$label:", style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.SemiBold)
        Text(value, style = MaterialTheme.typography.bodySmall)
    }
}

/** Stable tags for tests / instrumentation. */
object CodingTestTags {
    const val NEW_PROMPT = "coding_new_prompt"
    const val NEW_GENERATE = "coding_new_generate"
    const val NEW_AUDIT_PREVIEW = "coding_new_audit_preview"
    const val PACKET_COPY = "coding_packet_copy"
    const val PACKET_SEND = "coding_packet_send"
    const val HUB_LIST = "coding_hub_list"
}
