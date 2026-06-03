package com.aci.hermes.ui.screens.memory

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Badge
import androidx.compose.material3.BadgedBox
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.ScrollableTabRow
import androidx.compose.material3.Tab
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.aci.hermes.data.memory.MemoryContradiction
import com.aci.hermes.data.memory.MemoryNode
import com.aci.hermes.data.memory.TreeSync

@Composable
fun MemoryTabs(
    active: MemoryTab,
    inboxCount: Int,
    conflictCount: Int,
    onSelect: (MemoryTab) -> Unit,
) {
    ScrollableTabRow(
        selectedTabIndex = active.ordinal,
        edgePadding = 0.dp,
    ) {
        MemoryTab.values().forEach { tab ->
            val count = when (tab) {
                MemoryTab.INBOX -> inboxCount
                MemoryTab.CONTRADICTIONS -> conflictCount
                else -> 0
            }
            Tab(
                selected = active == tab,
                onClick = { onSelect(tab) },
                modifier = Modifier.testTag(MemoryScreenTags.tab(tab.name)),
                text = {
                    if (count > 0) {
                        BadgedBox(badge = { Badge { Text("$count") } }) {
                            Text(tab.display)
                        }
                    } else {
                        Text(tab.display)
                    }
                },
            )
        }
    }
}

@Composable
fun ProposedInboxSection(
    proposed: List<MemoryNode>,
    sync: TreeSync,
    onApprove: (String) -> Unit,
    onReject: (String) -> Unit,
) {
    if (proposed.isEmpty()) {
        TreeEmpty(
            tag = MemoryScreenTags.INBOX,
            message = when (sync) {
                is TreeSync.Unpaired -> "Pair a gateway to review proposed memory."
                is TreeSync.Error -> sync.message
                else -> "No proposed memory awaiting review."
            },
        )
        return
    }
    LazyColumn(
        modifier = Modifier.fillMaxSize().testTag(MemoryScreenTags.INBOX),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        items(proposed, key = { it.id }) { node ->
            ProposedCard(node = node, onApprove = { onApprove(node.id) }, onReject = { onReject(node.id) })
        }
    }
}

@Composable
private fun ProposedCard(
    node: MemoryNode,
    onApprove: () -> Unit,
    onReject: () -> Unit,
) {
    Card(
        modifier = Modifier.fillMaxWidth().testTag(MemoryScreenTags.proposedCard(node.id)),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                NamespacePill(node.namespace)
                if (node.durableWorthy) {
                    Box(
                        modifier = Modifier
                            .padding(start = 8.dp)
                            .clip(RoundedCornerShape(50))
                            .background(MaterialTheme.colorScheme.tertiaryContainer)
                            .padding(horizontal = 10.dp, vertical = 4.dp),
                    ) {
                        Text("Durable-worthy", style = MaterialTheme.typography.labelSmall)
                    }
                }
            }
            Text(
                text = node.title,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
            )
            Text(text = node.summary.ifBlank { node.content }, style = MaterialTheme.typography.bodyMedium)
            if (node.sources.isNotEmpty()) {
                Text(
                    text = "sources: " + node.sources.joinToString(", "),
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.primary,
                )
            }
            Text(
                text = "confidence ${"%.0f".format(node.confidence * 100)}% · trust ${node.trust}",
                style = MaterialTheme.typography.labelSmall,
            )
            HorizontalDivider()
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = onApprove) { Text("Approve") }
                OutlinedButton(onClick = onReject) { Text("Reject") }
            }
        }
    }
}

@Composable
fun ContradictionsSection(
    contradictions: List<MemoryContradiction>,
    onResolve: (String, String) -> Unit,
) {
    if (contradictions.isEmpty()) {
        TreeEmpty(tag = MemoryScreenTags.CONTRADICTIONS, message = "No open contradictions.")
        return
    }
    LazyColumn(
        modifier = Modifier.fillMaxSize().testTag(MemoryScreenTags.CONTRADICTIONS),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        items(contradictions, key = { it.id }) { report ->
            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.errorContainer),
            ) {
                Column(
                    modifier = Modifier.padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    Text(
                        text = "Conflict on: ${report.subject}",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold,
                    )
                    Text(text = report.reason, style = MaterialTheme.typography.bodyMedium)
                    HorizontalDivider()
                    Text("Which fact wins?", style = MaterialTheme.typography.labelMedium)
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        OutlinedButton(onClick = { onResolve(report.id, report.nodeAId) }) {
                            Text("Keep A")
                        }
                        OutlinedButton(onClick = { onResolve(report.id, report.nodeBId) }) {
                            Text("Keep B")
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun FreshnessSection(nodes: List<MemoryNode>) {
    if (nodes.isEmpty()) {
        TreeEmpty(tag = MemoryScreenTags.FRESHNESS, message = "Nothing due for a freshness review.")
        return
    }
    LazyColumn(
        modifier = Modifier.fillMaxSize().testTag(MemoryScreenTags.FRESHNESS),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        items(nodes, key = { it.id }) { node ->
            Card(modifier = Modifier.fillMaxWidth()) {
                Column(
                    modifier = Modifier.padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(4.dp),
                ) {
                    Text(node.title, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
                    Text(node.summary.ifBlank { node.content }, style = MaterialTheme.typography.bodyMedium)
                    node.freshnessDue?.let {
                        Text("due: $it", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.error)
                    }
                }
            }
        }
    }
}

@Composable
private fun NamespacePill(namespace: String) {
    Box(
        modifier = Modifier
            .clip(RoundedCornerShape(50))
            .background(MaterialTheme.colorScheme.secondaryContainer)
            .padding(horizontal = 10.dp, vertical = 4.dp),
    ) {
        Text(text = namespace, style = MaterialTheme.typography.labelMedium)
    }
}

@Composable
private fun TreeEmpty(tag: String, message: String) {
    Box(
        modifier = Modifier.fillMaxSize().testTag(tag),
        contentAlignment = Alignment.Center,
    ) {
        Text(message, style = MaterialTheme.typography.bodyMedium)
    }
}
