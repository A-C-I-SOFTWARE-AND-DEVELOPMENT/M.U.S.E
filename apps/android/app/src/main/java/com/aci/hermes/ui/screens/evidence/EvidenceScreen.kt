package com.aci.hermes.ui.screens.evidence

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.AssistChip
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
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.aci.hermes.data.evidence.EvidenceItem
import com.aci.hermes.data.evidence.EvidenceSync

object EvidenceScreenTags {
    const val ROOT = "evidence_screen"
    const val SEARCH = "evidence_search"
    const val LIST = "evidence_list"
    const val EMPTY = "evidence_empty"
    const val DETAIL = "evidence_detail"
    fun card(id: String) = "evidence_card_$id"
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun EvidenceScreen(
    viewModel: EvidenceViewModel,
    onBack: () -> Unit,
) {
    val state by viewModel.state.collectAsState()
    val snackbarHostState = remember { SnackbarHostState() }

    LaunchedEffect(state.snackbar) {
        state.snackbar?.let {
            snackbarHostState.showSnackbar(it)
            viewModel.consumeSnackbar()
        }
    }

    Scaffold(
        modifier = Modifier.testTag(EvidenceScreenTags.ROOT),
        topBar = {
            TopAppBar(
                title = { Text("Evidence") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
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
                .padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            OutlinedTextField(
                value = state.query,
                onValueChange = viewModel::setQuery,
                modifier = Modifier
                    .fillMaxWidth()
                    .testTag(EvidenceScreenTags.SEARCH),
                singleLine = true,
                label = { Text("Search evidence") },
                trailingIcon = {
                    IconButton(onClick = viewModel::search) {
                        Icon(Icons.Filled.Search, contentDescription = "Search")
                    }
                },
            )

            if (state.sync is EvidenceSync.MockOnly) {
                Text(
                    "Preview data — pair a gateway to load live evidence.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.outline,
                )
            }
            (state.sync as? EvidenceSync.Error)?.let {
                Text(it.message, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
            }

            val selected = state.selected
            if (selected != null) {
                EvidenceDetail(
                    item = selected,
                    onClose = viewModel::closeDetail,
                    onVerify = { viewModel.verify(selected.summary.ifBlank { selected.title }) },
                    onPromote = { auth -> viewModel.promote(selected, auth) },
                    verificationText = state.verification?.let { v ->
                        buildString {
                            append("${v.citations.count { it.supported }} cited, ")
                            append("${v.uncertain.size} uncertain, ")
                            append("${v.contradictions.size} contradiction(s)")
                        }
                    },
                )
            } else if (state.items.isEmpty()) {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Text("No evidence yet.", modifier = Modifier.testTag(EvidenceScreenTags.EMPTY))
                }
            } else {
                LazyColumn(
                    modifier = Modifier.testTag(EvidenceScreenTags.LIST),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    items(state.items, key = { it.id }) { item ->
                        EvidenceCard(item = item, onClick = { viewModel.open(item) })
                    }
                }
            }
        }
    }
}

@Composable
private fun EvidenceCard(item: EvidenceItem, onClick: () -> Unit) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .testTag(EvidenceScreenTags.card(item.id)),
        onClick = onClick,
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
    ) {
        Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(item.title, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
            Text(
                item.summary.ifBlank { item.excerpt },
                style = MaterialTheme.typography.bodySmall,
                maxLines = 3,
            )
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                AssistChip(onClick = {}, label = { Text(item.trust.display) })
                if (item.isStale()) {
                    AssistChip(
                        onClick = {},
                        label = { Text("Stale") },
                        leadingIcon = { Icon(Icons.Filled.Warning, contentDescription = null) },
                    )
                }
            }
        }
    }
}

@Composable
private fun EvidenceDetail(
    item: EvidenceItem,
    onClose: () -> Unit,
    onVerify: () -> Unit,
    onPromote: (String?) -> Unit,
    verificationText: String?,
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .testTag(EvidenceScreenTags.DETAIL),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Text(item.title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
        Text(item.sourceUri, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.primary)
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            AssistChip(onClick = {}, label = { Text(item.trust.display) })
            AssistChip(onClick = {}, label = { Text(if (item.isStale()) "Stale" else "Fresh") })
        }
        HorizontalDivider()
        Text(item.excerpt, style = MaterialTheme.typography.bodyMedium)
        if (item.licenseNotes.isNotBlank()) {
            Text("License: ${item.licenseNotes}", style = MaterialTheme.typography.bodySmall)
        }
        if (item.citationAnchors.isNotEmpty()) {
            Text("Citations: ${item.citationAnchors.joinToString(", ")}", style = MaterialTheme.typography.bodySmall)
        }
        verificationText?.let {
            Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.secondary)
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(onClick = onVerify) { Text("Verify") }
            // Owner phrase is supplied here for low-confidence promotions; high-trust
            // items pass the server policy without it. The gateway is the gate.
            Button(onClick = { onPromote("Yes, with authorization.") }) { Text("Promote to memory") }
            OutlinedButton(onClick = onClose) { Text("Close") }
        }
    }
}
