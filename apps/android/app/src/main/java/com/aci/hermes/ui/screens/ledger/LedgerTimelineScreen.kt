package com.aci.hermes.ui.screens.ledger

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.FilterList
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.aci.hermes.data.ledger.LedgerSync
import com.aci.hermes.data.model.ledger.LedgerEvent
import com.aci.hermes.data.model.ledger.LedgerFilters
import com.aci.hermes.ui.screens.audit.colorOn
import com.aci.hermes.ui.screens.audit.displayLabel

object LedgerScreenTags {
    const val LIST = "ledger-list"
    const val EMPTY = "ledger-list-empty"
    const val FILTERS = "ledger-filters"
    fun row(id: String): String = "ledger-row-$id"
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Composable
fun LedgerTimelineScreen(
    viewModel: LedgerTimelineViewModel,
    onBack: () -> Unit,
    onOpenEvent: (String) -> Unit,
) {
    val events by viewModel.events.collectAsState()
    val filters by viewModel.filters.collectAsState()
    val sync by viewModel.sync.collectAsState()

    var showFilters by remember { mutableStateOf(false) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Activity") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                },
                actions = {
                    IconButton(onClick = { showFilters = !showFilters }) {
                        Icon(Icons.Default.FilterList, contentDescription = "Filters")
                    }
                    IconButton(onClick = { viewModel.refresh() }) {
                        Icon(Icons.Default.Refresh, contentDescription = "Refresh")
                    }
                },
            )
        },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding),
        ) {
            if (showFilters) {
                LedgerFilterPanel(
                    filters = filters,
                    onApply = { viewModel.applyFilters(it) },
                    onClear = { viewModel.clearFilters() },
                )
            }

            val statusLine = when (val s = sync) {
                is LedgerSync.NotPaired -> "Pair a gateway to see activity."
                is LedgerSync.Loading -> "Loading…"
                is LedgerSync.Error -> s.message
                else -> null
            }
            if (statusLine != null) {
                Text(
                    statusLine,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(horizontal = 16.dp, vertical = 6.dp),
                )
            }

            if (events.isEmpty()) {
                Box(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(24.dp)
                        .testTag(LedgerScreenTags.EMPTY),
                    contentAlignment = Alignment.Center,
                ) {
                    Text(
                        "No activity yet.",
                        style = MaterialTheme.typography.bodyLarge,
                    )
                }
            } else {
                LazyColumn(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(horizontal = 16.dp)
                        .testTag(LedgerScreenTags.LIST),
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                    contentPadding = androidx.compose.foundation.layout.PaddingValues(vertical = 12.dp),
                ) {
                    items(events, key = LedgerEvent::id) { event ->
                        LedgerRow(event = event, onClick = { onOpenEvent(event.id) })
                    }
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Composable
private fun LedgerFilterPanel(
    filters: LedgerFilters,
    onApply: (LedgerFilters) -> Unit,
    onClear: () -> Unit,
) {
    var draft by remember(filters) { mutableStateOf(filters) }

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 8.dp)
            .testTag(LedgerScreenTags.FILTERS),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Text("Risk", style = MaterialTheme.typography.labelMedium)
        FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            RISK_FILTER_OPTIONS.forEach { risk ->
                FilterChip(
                    selected = draft.risk == risk,
                    onClick = {
                        draft = draft.copy(risk = if (draft.risk == risk) "" else risk)
                    },
                    label = { Text(risk.lowercase().replaceFirstChar { it.uppercase() }) },
                )
            }
        }
        OutlinedTextField(
            value = draft.worker,
            onValueChange = { draft = draft.copy(worker = it) },
            label = { Text("Worker") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
        )
        OutlinedTextField(
            value = draft.file,
            onValueChange = { draft = draft.copy(file = it) },
            label = { Text("File contains") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
        )
        OutlinedTextField(
            value = draft.job,
            onValueChange = { draft = draft.copy(job = it) },
            label = { Text("Job id") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
        )
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            OutlinedTextField(
                value = draft.since,
                onValueChange = { draft = draft.copy(since = it) },
                label = { Text("Since (YYYY-MM-DD)") },
                singleLine = true,
                modifier = Modifier.weight(1f),
            )
            OutlinedTextField(
                value = draft.until,
                onValueChange = { draft = draft.copy(until = it) },
                label = { Text("Until (YYYY-MM-DD)") },
                singleLine = true,
                modifier = Modifier.weight(1f),
            )
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            TextButton(onClick = { onApply(draft) }) { Text("Apply") }
            TextButton(onClick = {
                draft = LedgerFilters()
                onClear()
            }) { Text("Clear") }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Composable
private fun LedgerRow(event: LedgerEvent, onClick: () -> Unit) {
    val scheme = MaterialTheme.colorScheme
    Card(
        onClick = onClick,
        colors = CardDefaults.cardColors(containerColor = scheme.surfaceVariant),
        modifier = Modifier
            .fillMaxWidth()
            .testTag(LedgerScreenTags.row(event.id)),
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                modifier = Modifier.fillMaxWidth(),
            ) {
                Surface(
                    shape = CircleShape,
                    color = event.category.colorOn(scheme),
                    modifier = Modifier.size(10.dp),
                ) {}
                Text(
                    text = formatLedgerTimestamp(event.timestamp),
                    style = MaterialTheme.typography.labelMedium,
                    color = scheme.onSurfaceVariant,
                )
                Text(
                    text = event.category.displayLabel(),
                    style = MaterialTheme.typography.labelMedium,
                    color = event.category.colorOn(scheme),
                    modifier = Modifier.padding(start = 8.dp),
                )
                Text(
                    text = event.riskTier.displayLabel(),
                    style = MaterialTheme.typography.labelMedium,
                    color = event.riskTier.colorOn(scheme),
                    modifier = Modifier.padding(start = 8.dp),
                )
            }
            Text(
                text = event.summary.ifBlank { event.kind },
                style = MaterialTheme.typography.bodyMedium,
                maxLines = 3,
                overflow = TextOverflow.Ellipsis,
            )
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                event.worker?.let { AssistChip(onClick = onClick, label = { Text(it) }) }
                if (event.hasDiff) AssistChip(onClick = onClick, label = { Text("Diff") })
                if (event.hasEvidence) AssistChip(onClick = onClick, label = { Text("Evidence") })
                if (event.hasRollback) AssistChip(onClick = onClick, label = { Text("Rollback") })
            }
        }
    }
}
