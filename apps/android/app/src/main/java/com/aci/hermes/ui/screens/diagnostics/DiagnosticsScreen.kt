package com.aci.hermes.ui.screens.diagnostics

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.ContentCopy
import androidx.compose.material.icons.filled.DeleteSweep
import androidx.compose.material.icons.filled.ErrorOutline
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.unit.dp
import com.aci.hermes.R
import com.aci.hermes.ui.designsystem.museCard
import com.aci.hermes.ui.designsystem.museSectionHeader
import com.aci.hermes.ui.theme.JarvisJade
import com.aci.hermes.ui.theme.JarvisTokens
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DiagnosticsScreen(viewModel: DiagnosticsViewModel, onBack: () -> Unit) {
    val state by viewModel.state.collectAsState()
    val clipboard = LocalClipboardManager.current
    val snackbarHostState = remember { SnackbarHostState() }
    val scope = rememberCoroutineScope()
    val copiedMsg = stringResource(R.string.diagnostics_logs_copied)
    val clearedMsg = stringResource(R.string.diagnostics_logs_cleared)

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.diagnostics_title)) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(
                            Icons.AutoMirrored.Filled.ArrowBack,
                            contentDescription = stringResource(R.string.action_back),
                        )
                    }
                },
                actions = {
                    IconButton(onClick = viewModel::refresh) {
                        Icon(Icons.Default.Refresh, contentDescription = stringResource(R.string.diagnostics_refresh))
                    }
                    IconButton(onClick = {
                        val combined = state.logs.joinToString("\n") { it.format() }
                        clipboard.setText(AnnotatedString(combined))
                        scope.launch { snackbarHostState.showSnackbar(copiedMsg) }
                    }) {
                        Icon(Icons.Default.ContentCopy, contentDescription = stringResource(R.string.diagnostics_copy_logs))
                    }
                    IconButton(onClick = {
                        viewModel.clearLogs()
                        scope.launch { snackbarHostState.showSnackbar(clearedMsg) }
                    }) {
                        Icon(Icons.Default.DeleteSweep, contentDescription = stringResource(R.string.diagnostics_clear_logs))
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
                .padding(JarvisTokens.SpaceLg),
            verticalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceMd),
        ) {
            DiagInfoCard(state)
            BackendReadinessCard(state.backend)
            RecentSessionsCard(state.sessions)
            LogsCard(state)
        }
    }
}

@Composable
private fun BackendReadinessCard(sync: BackendDiagnosticsSync) {
    museCard(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(JarvisTokens.SpaceLg), verticalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm)) {
            museSectionHeader(title = stringResource(R.string.diagnostics_backend_title))
            when (sync) {
                is BackendDiagnosticsSync.NotPaired ->
                    Text(stringResource(R.string.diagnostics_backend_not_paired), style = MaterialTheme.typography.bodyMedium)
                is BackendDiagnosticsSync.Error ->
                    Text(sync.message, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.error)
                is BackendDiagnosticsSync.Loading, BackendDiagnosticsSync.Idle ->
                    Text(stringResource(R.string.diagnostics_backend_loading), style = MaterialTheme.typography.bodyMedium)
                is BackendDiagnosticsSync.Loaded -> {
                    val report = sync.report
                    val summary = if (report.ok) {
                        stringResource(R.string.diagnostics_backend_ready)
                    } else {
                        stringResource(R.string.diagnostics_backend_not_ready)
                    }
                    DiagRow(summary, "${report.checks.count { it.status == "pass" }}/${report.checks.size}")
                    report.checks.forEach { check ->
                        HorizontalDivider()
                        val glyph = when (check.status) {
                            "pass" -> "✓"
                            "warn" -> "▲"
                            else -> "✗"
                        }
                        DiagRow("$glyph ${check.name}", check.detail.take(60))
                    }
                    report.error?.takeIf { it.isNotBlank() }?.let {
                        Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
                    }
                }
            }
        }
    }
}

@Composable
private fun RecentSessionsCard(sessions: List<com.aci.hermes.data.cockpit.CockpitSession>) {
    // Only render when the backend reported activity — keeps the screen clean
    // when unpaired/empty (no fabricated rows).
    if (sessions.isEmpty()) return
    museCard(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(JarvisTokens.SpaceLg), verticalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm)) {
            museSectionHeader(title = stringResource(R.string.diagnostics_sessions_title))
            sessions.take(10).forEach { s ->
                DiagRow(s.id, stringResource(R.string.diagnostics_sessions_count, s.decisionCount))
            }
        }
    }
}

@Composable
private fun DiagInfoCard(state: DiagnosticsUiState) {
    val hasError = state.lastError != null
    museCard(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(JarvisTokens.SpaceLg), verticalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm)) {
            DiagRow(stringResource(R.string.diagnostics_app_version), state.appVersion)
            HorizontalDivider()
            DiagRow(stringResource(R.string.diagnostics_build_type), state.buildType)
            HorizontalDivider()
            // The error row carries its own valence: a green check when clean,
            // an error icon + error color when something was logged.
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm),
            ) {
                Icon(
                    imageVector = if (hasError) Icons.Filled.ErrorOutline else Icons.Filled.CheckCircle,
                    contentDescription = null,
                    tint = if (hasError) MaterialTheme.colorScheme.error else JarvisJade,
                    modifier = Modifier.size(20.dp),
                )
                Text(
                    text = stringResource(R.string.diagnostics_last_error),
                    style = MaterialTheme.typography.titleMedium,
                    modifier = Modifier.weight(1f),
                )
                Text(
                    text = state.lastError?.message ?: stringResource(R.string.diagnostics_no_error),
                    style = MaterialTheme.typography.bodyMedium,
                    color = if (hasError) MaterialTheme.colorScheme.error
                            else MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

@Composable
private fun DiagRow(label: String, value: String) {
    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
        Text(label, style = MaterialTheme.typography.titleMedium)
        Text(value, style = MaterialTheme.typography.bodyMedium)
    }
}

@Composable
private fun LogsCard(state: DiagnosticsUiState) {
    museCard(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(JarvisTokens.SpaceMd)) {
            museSectionHeader(
                title = stringResource(R.string.diagnostics_logs),
                modifier = Modifier.padding(bottom = JarvisTokens.SpaceSm),
            )
            if (state.logs.isEmpty()) {
                Text(stringResource(R.string.diagnostics_no_logs), style = MaterialTheme.typography.bodyMedium)
            } else {
                LazyColumn(modifier = Modifier.fillMaxWidth()) {
                    items(state.logs) { entry ->
                        Text(entry.format(), style = MaterialTheme.typography.labelSmall)
                    }
                }
            }
        }
    }
}
