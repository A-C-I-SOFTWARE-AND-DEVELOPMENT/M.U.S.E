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
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
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
import com.aci.hermes.ui.designsystem.MuseButton
import com.aci.hermes.ui.designsystem.MuseButtonVariant
import com.aci.hermes.ui.designsystem.MuseCard
import com.aci.hermes.ui.theme.JarvisCrimson
import com.aci.hermes.ui.theme.JarvisSignal
import com.aci.hermes.ui.theme.JarvisSignalDim
import com.aci.hermes.ui.theme.JarvisTokens

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
                .padding(JarvisTokens.SpaceLg)
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceMd),
        ) {
            ModeBanner(paired = state.paired, mock = state.mock)

            OutlinedTextField(
                value = state.prompt,
                onValueChange = viewModel::updatePrompt,
                modifier = Modifier
                    .fillMaxWidth()
                    .testTag(CodingTestTags.NEW_PROMPT),
                label = { Text("What should MUSE build, fix, or review?") },
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
                horizontalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceMd),
            ) {
                MuseButton(
                    onClick = viewModel::previewClassification,
                    text = "Preview risk",
                    variant = MuseButtonVariant.Secondary,
                    enabled = !state.busy,
                    modifier = Modifier.weight(1f),
                )

                Button(
                    onClick = viewModel::generatePacket,
                    enabled = !state.busy,
                    modifier = Modifier
                        .weight(1f)
                        .testTag(CodingTestTags.NEW_GENERATE),
                ) {
                    if (state.busy) {
                        CircularProgressIndicator(
                            modifier = Modifier.padding(end = JarvisTokens.SpaceSm),
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
                color = JarvisSignalDim,
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
    MuseCard {
        Column(Modifier.padding(JarvisTokens.SpaceMd)) {
            Text(label, style = MaterialTheme.typography.labelLarge, color = JarvisSignal, fontWeight = FontWeight.SemiBold)
            Text(detail, style = MaterialTheme.typography.bodySmall, color = JarvisSignalDim)
        }
    }
}

@Composable
private fun AuditPreviewCard(audit: com.aci.hermes.data.cockpit.CodingAuditResult) {
    MuseCard(
        modifier = Modifier
            .fillMaxWidth()
            .testTag(CodingTestTags.NEW_AUDIT_PREVIEW),
    ) {
        Column(Modifier.padding(JarvisTokens.SpaceLg), verticalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceXs)) {
            Text("Classification", style = MaterialTheme.typography.labelMedium, color = JarvisSignalDim)
            LabeledLine("Risk", audit.riskClass.ifBlank { "—" })
            LabeledLine("Worker", audit.primaryWorker.ifBlank { "—" })
            if (audit.ownerGates.isNotEmpty()) {
                LabeledLine("Owner gates", audit.ownerGates.joinToString(", "))
            }
            if (audit.rationale.isNotBlank()) {
                Text(audit.rationale, style = MaterialTheme.typography.bodySmall, color = JarvisSignalDim)
            }
            if (audit.blocked) {
                Text(
                    "Blocked: this request needs owner authorization before it can proceed.",
                    style = MaterialTheme.typography.bodySmall,
                    color = JarvisCrimson,
                )
            }
        }
    }
}

@Composable
private fun LabeledLine(label: String, value: String) {
    Row(horizontalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm)) {
        Text("$label:", style = MaterialTheme.typography.bodySmall, color = JarvisSignalDim, fontWeight = FontWeight.SemiBold)
        Text(value, style = MaterialTheme.typography.bodySmall, color = JarvisSignal)
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
