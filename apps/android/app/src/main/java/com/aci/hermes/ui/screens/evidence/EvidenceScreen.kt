package com.aci.hermes.ui.screens.evidence

import androidx.compose.foundation.clickable
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
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
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
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import com.aci.hermes.data.evidence.EvidenceItem
import com.aci.hermes.data.evidence.EvidenceSync
import com.aci.hermes.ui.designsystem.museButton
import com.aci.hermes.ui.designsystem.museButtonVariant
import com.aci.hermes.ui.designsystem.museCard
import com.aci.hermes.ui.designsystem.museChip
import com.aci.hermes.ui.designsystem.museEmptyState
import com.aci.hermes.ui.theme.JarvisTokens

object EvidenceScreenTags {
    const val ROOT = "evidence_screen"
    const val SEARCH = "evidence_search"
    const val LIST = "evidence_list"
    const val EMPTY = "evidence_empty"
    const val DETAIL = "evidence_detail"
    const val AUTH_DIALOG = "evidence_auth_dialog"
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
                .padding(horizontal = JarvisTokens.SpaceLg),
            verticalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm),
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
                    // No owner phrase on a normal tap — the gateway gates it, and an
                    // owner-gated rejection raises the explicit authorization dialog.
                    onPromote = { viewModel.promote(selected) },
                    verificationText = state.verification?.let { v ->
                        buildString {
                            append("${v.citations.count { it.supported }} cited, ")
                            append("${v.uncertain.size} uncertain, ")
                            append("${v.contradictions.size} contradiction(s)")
                        }
                    },
                )
            } else if (state.items.isEmpty()) {
                Box(
                    modifier = Modifier
                        .fillMaxSize()
                        .testTag(EvidenceScreenTags.EMPTY),
                    contentAlignment = Alignment.Center,
                ) {
                    museEmptyState(
                        title = "No evidence yet",
                        body = "Run a search above, or pair a gateway to load live evidence.",
                    )
                }
            } else {
                LazyColumn(
                    modifier = Modifier.testTag(EvidenceScreenTags.LIST),
                    verticalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm),
                ) {
                    items(state.items, key = { it.id }) { item ->
                        EvidenceCard(item = item, onClick = { viewModel.open(item) })
                    }
                }
            }
        }

        state.authPromptItem?.let { pending ->
            OwnerAuthorizationDialog(
                item = pending,
                onConfirm = viewModel::confirmAuthorizedPromote,
                onDismiss = viewModel::cancelAuthPrompt,
            )
        }
    }
}

@Composable
private fun EvidenceCard(item: EvidenceItem, onClick: () -> Unit) {
    museCard(
        modifier = Modifier
            .fillMaxWidth()
            .testTag(EvidenceScreenTags.card(item.id))
            .clickable(onClick = onClick),
    ) {
        Column(modifier = Modifier.padding(JarvisTokens.SpaceMd), verticalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceXs)) {
            Text(item.title, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
            Text(
                item.summary.ifBlank { item.excerpt },
                style = MaterialTheme.typography.bodySmall,
                maxLines = 3,
            )
            Row(horizontalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm), verticalAlignment = Alignment.CenterVertically) {
                museChip(label = item.trust.display)
                if (item.isStale()) {
                    museChip(label = "Stale")
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
    onPromote: () -> Unit,
    verificationText: String?,
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .testTag(EvidenceScreenTags.DETAIL),
        verticalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm),
    ) {
        Text(item.title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
        Text(item.sourceUri, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.primary)
        Row(horizontalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm)) {
            museChip(label = item.trust.display)
            museChip(label = if (item.isStale()) "Stale" else "Fresh")
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
        Row(horizontalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm)) {
            museButton(onClick = onVerify, text = "Verify", variant = museButtonVariant.Secondary)
            // Sends no owner phrase: the gateway promotes high-trust items and
            // rejects low-confidence/unverified ones, which raises an explicit
            // owner-authorization dialog rather than promoting on a tap.
            museButton(onClick = onPromote, text = "Promote to memory")
            museButton(onClick = onClose, text = "Close", variant = museButtonVariant.Secondary)
        }
    }
}

/**
 * Explicit owner-authorization gate for promoting low-confidence / unverified
 * evidence to durable memory. The owner phrase is only sent after this
 * deliberate confirmation — never on the Promote tap itself.
 */
@Composable
private fun OwnerAuthorizationDialog(
    item: EvidenceItem,
    onConfirm: () -> Unit,
    onDismiss: () -> Unit,
) {
    AlertDialog(
        modifier = Modifier.testTag(EvidenceScreenTags.AUTH_DIALOG),
        onDismissRequest = onDismiss,
        title = { Text("Owner authorization required") },
        text = {
            Text(
                "\"${item.title}\" is ${item.trust.display.lowercase()} / low-confidence. " +
                    "Promoting it to durable memory needs your explicit authorization.",
            )
        },
        confirmButton = {
            museButton(onClick = onConfirm, text = "Authorize & promote", variant = museButtonVariant.Approve)
        },
        dismissButton = {
            museButton(onClick = onDismiss, text = "Cancel", variant = museButtonVariant.Secondary)
        },
    )
}
