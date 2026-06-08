package com.aci.hermes.ui.screens.jobs

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.horizontalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.AlertDialog
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
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import com.aci.hermes.data.cockpit.CockpitNavigation
import com.aci.hermes.data.cockpit.JobDetail
import com.aci.hermes.data.cockpit.JobTimelineEntry
import com.aci.hermes.data.cockpit.JobWorkerRef
import com.aci.hermes.ui.components.JobStatusChip
import com.aci.hermes.ui.components.JobUiState
import com.aci.hermes.ui.designsystem.MuseButton
import com.aci.hermes.ui.designsystem.MuseButtonVariant
import com.aci.hermes.ui.designsystem.MuseCard
import com.aci.hermes.ui.designsystem.MuseSectionHeader

/**
 * Read-only job story + the full control set. The timeline, worker
 * assignments, evidence, files touched, commands run, test results, approvals,
 * and rollback come straight from the gateway's job ledger projection. The
 * control bar exposes pause/resume/cancel/rerun, owner-gated approve, "open
 * patch" (diff) and "run verification".
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun JobDetailScreen(
    viewModel: JobDetailViewModel,
    onBack: () -> Unit,
) {
    val state by viewModel.state.collectAsState()
    val snackbarHostState = remember { SnackbarHostState() }
    var showApprove by remember { mutableStateOf(false) }

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
        onDispose { lifecycleOwner.lifecycle.removeObserver(observer) }
    }

    LaunchedEffect(state.snackbar) {
        state.snackbar?.let {
            snackbarHostState.showSnackbar(it)
            viewModel.consumeSnackbar()
        }
    }

    if (showApprove) {
        OwnerApproveDialog(
            onDismiss = { showApprove = false },
            onApprove = { phrase ->
                showApprove = false
                viewModel.approve(phrase)
            },
        )
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(state.detail?.objective?.take(48) ?: "Job") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                },
            )
        },
        snackbarHost = { SnackbarHost(snackbarHostState) },
    ) { padding ->
        when {
            state.loading && state.detail == null -> Box(
                Modifier.fillMaxSize().padding(padding),
                contentAlignment = Alignment.Center,
            ) { CircularProgressIndicator() }
            state.detail == null -> Box(
                Modifier.fillMaxSize().padding(padding).padding(24.dp),
                contentAlignment = Alignment.Center,
            ) { Text(state.error ?: "Job unavailable", style = MaterialTheme.typography.bodyLarge) }
            else -> JobDetailBody(
                detail = state.detail!!,
                uiState = state.uiState,
                verifying = state.verifying,
                patchText = state.patch?.diff,
                patchLoading = state.patchLoading,
                verification = state.verification?.let { v -> v.gates.size },
                navigation = state.navigation,
                navLoading = state.navLoading,
                navLoaded = state.navLoaded,
                onPause = viewModel::pause,
                onResume = viewModel::resume,
                onCancel = viewModel::cancel,
                onRerun = { viewModel.rerun() },
                onApprove = { showApprove = true },
                onOpenPatch = viewModel::openPatch,
                onVerify = viewModel::runVerification,
                onLoadNavigation = viewModel::loadNavigation,
                modifier = Modifier.padding(padding),
            )
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun JobDetailBody(
    detail: JobDetail,
    uiState: JobUiState,
    verifying: Boolean,
    patchText: String?,
    patchLoading: Boolean,
    verification: Int?,
    navigation: CockpitNavigation?,
    navLoading: Boolean,
    navLoaded: Boolean,
    onPause: () -> Unit,
    onResume: () -> Unit,
    onCancel: () -> Unit,
    onRerun: () -> Unit,
    onApprove: () -> Unit,
    onOpenPatch: () -> Unit,
    onVerify: () -> Unit,
    onLoadNavigation: () -> Unit,
    modifier: Modifier = Modifier,
) {
    LazyColumn(
        modifier = modifier.fillMaxSize().padding(horizontal = 16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        item {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                JobStatusChip(state = uiState)
                detail.currentStep?.let { Text("Current step: $it", style = MaterialTheme.typography.bodyMedium) }
            }
        }

        item {
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                ControlButton("Pause", enabled = uiState.isActive, onClick = onPause)
                ControlButton("Resume", enabled = uiState.needsAttention || uiState == JobUiState.PAUSED, onClick = onResume)
                ControlButton("Cancel", enabled = uiState.isActive || uiState.needsAttention, onClick = onCancel, variant = MuseButtonVariant.Danger)
                ControlButton("Rerun step", enabled = uiState == JobUiState.FAILED || uiState == JobUiState.BLOCKED, onClick = onRerun)
                ControlButton("Approve", enabled = uiState.needsAttention, onClick = onApprove, variant = MuseButtonVariant.Approve)
                ControlButton("Open patch", enabled = true, onClick = onOpenPatch)
                ControlButton("Run verification", enabled = !verifying, onClick = onVerify)
                ControlButton("Navigation", enabled = !navLoading, onClick = onLoadNavigation)
            }
        }

        if (navLoading) {
            item { Box(Modifier.fillMaxWidth().padding(8.dp), contentAlignment = Alignment.Center) { CircularProgressIndicator() } }
        }
        navigation?.let { nav ->
            sectionCard("Navigation — where Jarvis looked") {
                Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    if (nav.objective.isNotBlank()) {
                        Text(nav.objective, style = MaterialTheme.typography.bodyMedium)
                    }
                    if (nav.candidateFiles.isEmpty()) {
                        Text("No candidate files recorded.", style = MaterialTheme.typography.bodySmall)
                    } else {
                        nav.candidateFiles.forEach { c ->
                            Text(
                                "#${c.rank} ${c.path}  ·  ${(c.confidence * 100).toInt()}%",
                                style = MaterialTheme.typography.bodySmall,
                                fontFamily = FontFamily.Monospace,
                            )
                            if (c.rationale.isNotBlank()) {
                                Text(c.rationale.take(160), style = MaterialTheme.typography.labelSmall)
                            }
                        }
                    }
                }
            }
        }
        if (navLoaded && navigation == null && !navLoading) {
            sectionCard("Navigation") {
                Text("This job did not record a navigation decision.", style = MaterialTheme.typography.bodySmall)
            }
        }

        if (detail.plan.isNotBlank()) {
            sectionCard("Plan") { Text(detail.plan, style = MaterialTheme.typography.bodyMedium) }
        }

        if (detail.workers.isNotEmpty()) {
            sectionCard("Workers") {
                Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    detail.workers.forEach { WorkerRow(it) }
                }
            }
        }

        verification?.let {
            sectionCard("Verification") {
                Text("$it gate(s) reported. See gate details below.", style = MaterialTheme.typography.bodyMedium)
            }
        }
        detail.testResults?.let { tr ->
            sectionCard("Test results") {
                Text("Pass ${tr.pass} · Fail ${tr.fail} · Pending ${tr.pending}",
                    style = MaterialTheme.typography.bodyMedium)
            }
        }

        if (patchLoading) {
            item { Box(Modifier.fillMaxWidth().padding(8.dp), contentAlignment = Alignment.Center) { CircularProgressIndicator() } }
        }
        patchText?.let { text ->
            sectionCard("Patch") {
                Text(
                    text = text.ifBlank { "No working-tree changes." },
                    style = MaterialTheme.typography.bodySmall,
                    fontFamily = FontFamily.Monospace,
                    modifier = Modifier.horizontalScroll(rememberScrollState()),
                )
            }
        }

        if (detail.filesTouched.isNotEmpty()) {
            sectionCard("Files touched") { BulletList(detail.filesTouched) }
        }
        if (detail.commandsRun.isNotEmpty()) {
            sectionCard("Commands run") { BulletList(detail.commandsRun) }
        }
        detail.evidence.takeIf { it.isNotEmpty() }?.let { evidence ->
            sectionCard("Evidence") {
                Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    evidence.forEach { Text("• ${it.title}: ${it.body.take(240)}", style = MaterialTheme.typography.bodySmall) }
                }
            }
        }
        if (detail.approvals.isNotEmpty()) {
            sectionCard("Approvals") {
                Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    detail.approvals.forEach { Text("• ${it.approver} — ${it.state}", style = MaterialTheme.typography.bodySmall) }
                }
            }
        }

        if (detail.timeline.isNotEmpty()) {
            sectionCard("Ledger timeline") {
                Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    detail.timeline.forEach { TimelineRow(it) }
                }
            }
        }

        detail.rollback?.let { rb ->
            sectionCard("Rollback") {
                Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text(rb.summary, style = MaterialTheme.typography.bodyMedium)
                    rb.steps.forEach { Text("• $it", style = MaterialTheme.typography.bodySmall) }
                }
            }
        }

        item { Box(Modifier.padding(8.dp)) {} }
    }
}

@Composable
private fun ControlButton(
    label: String,
    enabled: Boolean,
    onClick: () -> Unit,
    variant: MuseButtonVariant = MuseButtonVariant.Secondary,
) {
    MuseButton(onClick = onClick, text = label, variant = variant, enabled = enabled)
}

@Composable
private fun WorkerRow(worker: JobWorkerRef) {
    Column {
        Text("${worker.worker} — ${worker.status}", style = MaterialTheme.typography.bodyMedium)
        worker.error?.takeIf { it.isNotBlank() }?.let {
            Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
        }
    }
}

@Composable
private fun TimelineRow(entry: JobTimelineEntry) {
    Column {
        Text(
            text = "${entry.kind}${entry.phase?.let { " · $it" } ?: ""}  [${entry.actor}]",
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        if (entry.summary.isNotBlank()) {
            Text(entry.summary, style = MaterialTheme.typography.bodySmall)
        }
    }
}

@Composable
private fun BulletList(items: List<String>) {
    Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
        items.forEach { Text("• $it", style = MaterialTheme.typography.bodySmall) }
    }
}

private fun androidx.compose.foundation.lazy.LazyListScope.sectionCard(
    title: String,
    content: @Composable () -> Unit,
) {
    item(key = "section-$title") {
        MuseCard(modifier = Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                MuseSectionHeader(title = title)
                content()
            }
        }
    }
}

@Composable
private fun OwnerApproveDialog(onDismiss: () -> Unit, onApprove: (String) -> Unit) {
    var phrase by remember { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Owner approval") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Approving a gated phase runs real work. Type the exact owner authorization phrase to proceed.")
                OutlinedTextField(
                    value = phrase,
                    onValueChange = { phrase = it },
                    label = { Text("Authorization phrase") },
                    singleLine = true,
                )
            }
        },
        confirmButton = {
            MuseButton(onClick = { onApprove(phrase) }, text = "Approve", variant = MuseButtonVariant.Approve)
        },
        dismissButton = {
            MuseButton(onClick = onDismiss, text = "Cancel", variant = MuseButtonVariant.Secondary)
        },
    )
}
