package com.aci.hermes.ui.screens.diagnostics

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.ContentCopy
import androidx.compose.material.icons.filled.DeleteSweep
import androidx.compose.material.icons.filled.ErrorOutline
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
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
import com.aci.hermes.R
import com.aci.hermes.ui.theme.LocalHermesSemantics
import com.aci.hermes.ui.theme.LocalSpacing
import com.aci.hermes.ui.theme.rememberHermesHaptics
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DiagnosticsScreen(viewModel: DiagnosticsViewModel, onBack: () -> Unit) {
    val state by viewModel.state.collectAsState()
    val clipboard = LocalClipboardManager.current
    val spacing = LocalSpacing.current
    val haptics = rememberHermesHaptics()
    val snackbarHostState = remember { SnackbarHostState() }
    val scope = rememberCoroutineScope()
    val copiedMessage = stringResource(R.string.diagnostics_logs_copied)
    val clearedMessage = stringResource(R.string.diagnostics_logs_cleared)

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
                        Icon(
                            Icons.Default.Refresh,
                            contentDescription = stringResource(R.string.diagnostics_refresh),
                        )
                    }
                    IconButton(onClick = {
                        val combined = state.logs.joinToString("\n") { it.format() }
                        clipboard.setText(AnnotatedString(combined))
                        haptics.tick()
                        scope.launch { snackbarHostState.showSnackbar(copiedMessage) }
                    }) {
                        Icon(
                            Icons.Default.ContentCopy,
                            contentDescription = stringResource(R.string.diagnostics_copy_logs),
                        )
                    }
                    IconButton(onClick = {
                        viewModel.clearLogs()
                        haptics.reject()
                        scope.launch { snackbarHostState.showSnackbar(clearedMessage) }
                    }) {
                        Icon(
                            Icons.Default.DeleteSweep,
                            contentDescription = stringResource(R.string.diagnostics_clear_logs),
                        )
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
                .padding(spacing.screen),
            verticalArrangement = Arrangement.spacedBy(spacing.cardGap),
        ) {
            DiagInfoCard(state)
            LogsCard(state)
        }
    }
}

@Composable
private fun DiagInfoCard(state: DiagnosticsUiState) {
    val spacing = LocalSpacing.current
    val semantics = LocalHermesSemantics.current
    val hasError = state.lastError != null
    Card(
        colors = CardDefaults.cardColors(
            containerColor = if (hasError) semantics.dangerSurface
            else MaterialTheme.colorScheme.surfaceVariant,
        ),
    ) {
        Column(
            modifier = Modifier.padding(spacing.cardPadding),
            verticalArrangement = Arrangement.spacedBy(spacing.sm),
        ) {
            DiagRow(stringResource(R.string.diagnostics_app_version), state.appVersion)
            HorizontalDivider()
            DiagRow(stringResource(R.string.diagnostics_build_type), state.buildType)
            HorizontalDivider()
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(spacing.xs),
                ) {
                    Icon(
                        imageVector = if (hasError) Icons.Default.ErrorOutline
                        else Icons.Default.CheckCircle,
                        contentDescription = null,
                        tint = if (hasError) MaterialTheme.colorScheme.error else semantics.success,
                    )
                    Text(
                        stringResource(R.string.diagnostics_last_error),
                        style = MaterialTheme.typography.titleMedium,
                    )
                }
                Text(
                    text = state.lastError?.message
                        ?: stringResource(R.string.diagnostics_no_error),
                    style = MaterialTheme.typography.bodyMedium,
                    color = if (hasError) MaterialTheme.colorScheme.error
                    else MaterialTheme.colorScheme.onSurface,
                )
            }
        }
    }
}

@Composable
private fun DiagRow(label: String, value: String) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
    ) {
        Text(label, style = MaterialTheme.typography.titleMedium)
        Text(value, style = MaterialTheme.typography.bodyMedium)
    }
}

@Composable
private fun LogsCard(state: DiagnosticsUiState) {
    val spacing = LocalSpacing.current
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
    ) {
        Column(modifier = Modifier.padding(spacing.md)) {
            Text(
                stringResource(R.string.diagnostics_logs),
                style = MaterialTheme.typography.titleMedium,
                color = MaterialTheme.colorScheme.primary,
                modifier = Modifier.padding(bottom = spacing.sm),
            )
            if (state.logs.isEmpty()) {
                Text(
                    stringResource(R.string.diagnostics_no_logs),
                    style = MaterialTheme.typography.bodyMedium,
                )
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
