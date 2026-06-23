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
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
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
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import com.aci.hermes.data.cockpit.CodingPacket
import com.aci.hermes.data.coding.SavedCodingTask
import com.aci.hermes.ui.designsystem.museButton
import com.aci.hermes.ui.designsystem.museButtonVariant
import com.aci.hermes.ui.designsystem.museCard
import com.aci.hermes.ui.designsystem.museChip
import com.aci.hermes.ui.theme.JarvisCrimson
import com.aci.hermes.ui.theme.JarvisSignal
import com.aci.hermes.ui.theme.JarvisSignalDim
import com.aci.hermes.ui.theme.JarvisTokens

/**
 * The bounded work packet, with the two handoff exits. Copy is always
 * available (offline-safe); Send to backend is a gated execute — a null phrase
 * stages the job and the gateway holds it until the owner phrase is supplied.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun WorkPacketDetailScreen(
    viewModel: WorkPacketDetailViewModel,
    onBack: () -> Unit,
) {
    val state by viewModel.state.collectAsState()
    val snackbar = remember { SnackbarHostState() }
    val clipboard = LocalClipboardManager.current

    LaunchedEffect(state.copyText) {
        state.copyText?.let {
            clipboard.setText(AnnotatedString(it))
            viewModel.consumeCopy()
            snackbar.showSnackbar("Claude Code prompt copied to clipboard")
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
                title = { Text("Work packet") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                },
            )
        },
        snackbarHost = { SnackbarHost(snackbar) },
    ) { padding ->
        val task = state.task
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(JarvisTokens.SpaceLg)
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceMd),
        ) {
            if (task == null) {
                Text("Task not found.", style = MaterialTheme.typography.bodyMedium, color = JarvisSignalDim)
                return@Column
            }

            HeaderCard(task)

            val packet = task.packet
            if (packet == null) {
                EmptyPacketCard(
                    busy = state.busy,
                    onRegenerate = viewModel::regeneratePacket,
                )
            } else {
                PacketBody(packet)
            }

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceMd),
            ) {
                museButton(
                    onClick = viewModel::copyPrompt,
                    text = "Copy Claude Code prompt",
                    variant = museButtonVariant.Secondary,
                    modifier = Modifier
                        .weight(1f)
                        .testTag(CodingTestTags.PACKET_COPY),
                )

                museButton(
                    onClick = { viewModel.sendToBackend(null) },
                    text = "Send to backend",
                    variant = museButtonVariant.Primary,
                    enabled = !state.busy && task.packet != null,
                    modifier = Modifier
                        .weight(1f)
                        .testTag(CodingTestTags.PACKET_SEND),
                )
            }

            Text(
                "Send stages a gated execute on your backend — it never runs a " +
                    "risky action without your authorization. Copy hands the packet to " +
                    "a desktop Claude Code session instead.",
                style = MaterialTheme.typography.bodySmall,
                color = JarvisSignalDim,
            )
        }
    }

    state.ownerGateHint?.let { hint ->
        OwnerGateDialog(
            hint = hint,
            onDismiss = viewModel::dismissOwnerGate,
            onAuthorize = { phrase ->
                viewModel.dismissOwnerGate()
                viewModel.sendToBackend(phrase)
            },
        )
    }
}

@Composable
private fun HeaderCard(task: SavedCodingTask) {
    museCard {
        Column(Modifier.padding(JarvisTokens.SpaceLg), verticalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm)) {
            Text(task.title, style = MaterialTheme.typography.titleMedium, color = JarvisSignal)
            Row(horizontalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm)) {
                museChip(label = task.state.label)
                task.packet?.riskClass?.takeIf { it.isNotBlank() }?.let { rc ->
                    museChip(label = rc)
                }
                if (task.demo) museChip(label = "demo")
            }
            task.note?.takeIf { it.isNotBlank() }?.let {
                Text(it, style = MaterialTheme.typography.bodySmall, color = JarvisCrimson)
            }
        }
    }
}

@Composable
private fun EmptyPacketCard(busy: Boolean, onRegenerate: () -> Unit) {
    museCard {
        Column(Modifier.padding(JarvisTokens.SpaceLg), verticalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm)) {
            Text("No packet yet", style = MaterialTheme.typography.titleSmall, color = JarvisSignal)
            Text(
                "This task is saved but hasn't been planned into a bounded packet — " +
                    "usually because no backend was reachable. You can still copy a " +
                    "prompt below, or retry planning once a gateway is paired.",
                style = MaterialTheme.typography.bodySmall,
                color = JarvisSignalDim,
            )
            museButton(onClick = onRegenerate, text = "Retry planning", variant = museButtonVariant.Secondary, enabled = !busy)
        }
    }
}

@Composable
private fun PacketBody(packet: CodingPacket) {
    Section("Mission", packet.mission)
    BulletSection("Allowed files", packet.allowedFiles)
    BulletSection("Do NOT touch", packet.forbiddenFiles)
    BulletSection("Acceptance criteria", packet.acceptanceCriteria)
    BulletSection("Verification plan", packet.verificationPlan)
    BulletSection("Rollback plan", packet.rollbackPlan)
    if (packet.ownerGates.isNotEmpty()) {
        BulletSection("Owner-gated actions", packet.ownerGates)
    }
    val route = buildList {
        packet.primaryWorker.takeIf { it.isNotBlank() }?.let { add("Worker: $it") }
        packet.modelLaneHint.takeIf { it.isNotBlank() }?.let { add("Model lane: $it") }
        packet.branch.takeIf { it.isNotBlank() }?.let { add("Branch: $it") }
    }
    if (route.isNotEmpty()) Section("Route", route.joinToString("\n"))
}

@Composable
private fun Section(label: String, body: String) {
    if (body.isBlank()) return
    museCard {
        Column(Modifier.padding(JarvisTokens.SpaceLg), verticalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceXs)) {
            Text(label, style = MaterialTheme.typography.labelMedium, color = JarvisSignalDim)
            Text(body, style = MaterialTheme.typography.bodyMedium, color = JarvisSignal, fontFamily = FontFamily.Monospace)
        }
    }
}

@Composable
private fun BulletSection(label: String, items: List<String>) {
    val clean = items.map { it.trim() }.filter { it.isNotEmpty() }
    if (clean.isEmpty()) return
    museCard {
        Column(Modifier.padding(JarvisTokens.SpaceLg), verticalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceXs)) {
            Text(label, style = MaterialTheme.typography.labelMedium, color = JarvisSignalDim)
            clean.forEach { Text("• $it", style = MaterialTheme.typography.bodyMedium, color = JarvisSignal) }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun OwnerGateDialog(
    hint: String,
    onDismiss: () -> Unit,
    onAuthorize: (String) -> Unit,
) {
    var phrase by remember { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Owner authorization required") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(hint, style = MaterialTheme.typography.bodyMedium)
                Text(
                    "Type the exact phrase to dispatch. The backend verifies it; the " +
                        "app never stores it.",
                    style = MaterialTheme.typography.bodySmall,
                )
                OutlinedTextField(
                    value = phrase,
                    onValueChange = { phrase = it },
                    label = { Text("Yes, with authorization.") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        },
        confirmButton = {
            Button(
                onClick = { onAuthorize(phrase) },
                enabled = phrase.isNotBlank(),
            ) { Text("Authorize & send") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } },
    )
}
