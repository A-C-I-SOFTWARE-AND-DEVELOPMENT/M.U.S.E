package com.aci.hermes.ui.screens.audit

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ContentCopy
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
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
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.aci.hermes.R
import com.aci.hermes.data.model.AuditEntry
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AuditScreen(viewModel: AuditViewModel) {
    val state by viewModel.state.collectAsState()
    val snackbarHostState = remember { SnackbarHostState() }

    LaunchedEffect(state.snackbar) {
        state.snackbar?.let {
            snackbarHostState.showSnackbar(it)
            viewModel.consumeSnackbar()
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text(stringResource(R.string.audit_title))
                        Text(
                            stringResource(R.string.audit_subtitle),
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                },
                actions = {
                    IconButton(onClick = viewModel::exportToClipboard) {
                        Icon(Icons.Default.ContentCopy, contentDescription = stringResource(R.string.audit_export))
                    }
                },
            )
        },
        snackbarHost = { SnackbarHost(snackbarHostState) },
    ) { padding ->
        Column(modifier = Modifier.fillMaxSize().padding(padding)) {
            Row(
                modifier = Modifier
                    .horizontalScroll(rememberScrollState())
                    .padding(horizontal = 16.dp, vertical = 8.dp),
                horizontalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                FilterChip(
                    selected = state.filter == AuditFilter.ALL,
                    onClick = { viewModel.setFilter(AuditFilter.ALL) },
                    label = { Text(stringResource(R.string.audit_filter_all)) },
                )
                FilterChip(
                    selected = state.filter == AuditFilter.ACTIONS,
                    onClick = { viewModel.setFilter(AuditFilter.ACTIONS) },
                    label = { Text(stringResource(R.string.audit_filter_actions)) },
                )
                FilterChip(
                    selected = state.filter == AuditFilter.APPROVALS,
                    onClick = { viewModel.setFilter(AuditFilter.APPROVALS) },
                    label = { Text(stringResource(R.string.audit_filter_approvals)) },
                )
                FilterChip(
                    selected = state.filter == AuditFilter.OVERRIDES,
                    onClick = { viewModel.setFilter(AuditFilter.OVERRIDES) },
                    label = { Text(stringResource(R.string.audit_filter_overrides)) },
                )
                FilterChip(
                    selected = state.filter == AuditFilter.STOPS,
                    onClick = { viewModel.setFilter(AuditFilter.STOPS) },
                    label = { Text(stringResource(R.string.audit_filter_stops)) },
                )
            }

            val visible = viewModel.filtered()
            if (visible.isEmpty()) {
                Text(
                    stringResource(R.string.audit_empty),
                    style = MaterialTheme.typography.bodyMedium,
                    modifier = Modifier.padding(16.dp),
                )
            } else {
                LazyColumn(
                    contentPadding = PaddingValues(horizontal = 16.dp, vertical = 12.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    items(visible) { entry -> AuditRow(entry) }
                }
            }
        }
    }
}

@Composable
private fun AuditRow(entry: AuditEntry) {
    val timestamp = remember(entry.createdAt) {
        SimpleDateFormat("MMM d • HH:mm:ss", Locale.getDefault()).format(Date(entry.createdAt))
    }
    Card(
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
        shape = RoundedCornerShape(12.dp),
    ) {
        Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text(entry.title, style = MaterialTheme.typography.titleSmall)
                Text(timestamp, style = MaterialTheme.typography.labelSmall)
            }
            Text(entry.detail, style = MaterialTheme.typography.bodySmall)
            Text(
                "${stringResource(R.string.audit_proof_id)}: ${entry.proofId}",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}
