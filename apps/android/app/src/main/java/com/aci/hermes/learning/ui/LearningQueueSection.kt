package com.aci.hermes.learning.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.AssistChip
import androidx.compose.material3.AssistChipDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Button
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.aci.hermes.data.learning.LearningCandidate
import com.aci.hermes.data.learning.LearningStatus
import com.aci.hermes.learning.state.LearningSync
import com.aci.hermes.learning.state.LearningViewModel

/**
 * The Learning Queue section, rendered as a tab inside the Approvals screen.
 *
 * Shows validated learning-dataset candidates awaiting owner review. Each
 * card is provenance-first: trace type, source, citations and the quality
 * gates it has cleared, plus Approve / Reject. Approve routes through the
 * owner-gate phrase (handled by the repository + gateway).
 */
@Composable
fun LearningQueueSection(viewModel: LearningViewModel) {
    val state by viewModel.state.collectAsState()

    val pending = state.candidates.filter { it.status == LearningStatus.PENDING }

    Column(Modifier.fillMaxSize()) {
        SyncBanner(state.sync)
        if (pending.isEmpty()) {
            Text(
                text = when (state.sync) {
                    is LearningSync.NotPaired ->
                        "Pair a muse gateway to review learning candidates."
                    is LearningSync.Error ->
                        "Couldn't load the learning queue. Pull to retry."
                    else -> "No learning candidates awaiting approval."
                },
                modifier = Modifier.padding(24.dp),
                style = MaterialTheme.typography.bodyLarge,
            )
            return@Column
        }
        LazyColumn(
            contentPadding = PaddingValues(12.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
            modifier = Modifier.fillMaxSize(),
        ) {
            items(pending, key = { it.id }) { cand ->
                LearningCandidateCard(
                    candidate = cand,
                    onApprove = { viewModel.approve(cand.id) },
                    onReject = { viewModel.reject(cand.id) },
                )
            }
        }
    }
}

@Composable
private fun SyncBanner(sync: LearningSync) {
    val text = when (sync) {
        is LearningSync.Loading -> "Loading…"
        is LearningSync.Loaded -> null
        is LearningSync.NotPaired -> null
        is LearningSync.Error -> sync.message
        LearningSync.Idle -> null
    } ?: return
    Text(
        text = text,
        modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
        style = MaterialTheme.typography.bodySmall,
        color = MaterialTheme.colorScheme.error,
    )
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun LearningCandidateCard(
    candidate: LearningCandidate,
    onApprove: () -> Unit,
    onReject: () -> Unit,
) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(candidate.title, style = MaterialTheme.typography.titleMedium)
            Text(
                "trace: ${candidate.traceType}" +
                    if (candidate.isNegative) "  • negative example" else "",
                style = MaterialTheme.typography.bodySmall,
            )
            val src = candidate.sourceUri.ifBlank { candidate.sourceKind }
            if (src.isNotBlank()) {
                Text("source: $src", style = MaterialTheme.typography.bodySmall)
            }
            if (candidate.citations.isNotEmpty()) {
                Text(
                    "citations: ${candidate.citations.size}",
                    style = MaterialTheme.typography.bodySmall,
                )
            }
            val chips = candidate.quality.passedLabels
            if (chips.isNotEmpty()) {
                FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    chips.forEach { label ->
                        AssistChip(
                            onClick = {},
                            enabled = false,
                            label = { Text(label) },
                            colors = AssistChipDefaults.assistChipColors(),
                        )
                    }
                }
            }
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = onApprove) { Text("Approve") }
                OutlinedButton(onClick = onReject) { Text("Reject") }
            }
        }
    }
}
