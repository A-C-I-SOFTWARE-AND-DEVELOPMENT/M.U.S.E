package com.aci.hermes.ui.screens.knowledge

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
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import com.aci.hermes.data.cockpit.GraphAnswer
import com.aci.hermes.data.cockpit.GraphCommunity

/**
 * The dedicated Knowledge Graph cockpit screen.
 *
 * Lets the owner query the GraphRAG knowledge graph (local / global / coding)
 * and rebuild the cache, all from the phone. Results are source-backed and
 * inspectable; nothing is fabricated when the graph is empty or unpaired.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun KnowledgeGraphScreen(
    viewModel: KnowledgeGraphViewModel,
    onBack: () -> Unit,
) {
    val state by viewModel.state.collectAsState()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Knowledge graph") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                },
            )
        },
    ) { padding ->
        LazyColumn(
            modifier = Modifier.fillMaxSize().padding(padding).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            item {
                OutlinedTextField(
                    value = state.query,
                    onValueChange = viewModel::onQueryChange,
                    label = { Text("Ask the graph") },
                    placeholder = { Text("e.g. where is job dispatch handled?") },
                    singleLine = false,
                    modifier = Modifier.fillMaxWidth(),
                )
            }
            item {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    for (mode in GRAPH_QUERY_MODES) {
                        FilterChip(
                            selected = state.mode == mode,
                            onClick = { viewModel.onModeChange(mode) },
                            label = { Text(mode) },
                        )
                    }
                }
            }
            item {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(
                        onClick = viewModel::runQuery,
                        enabled = !state.loading && state.query.isNotBlank(),
                    ) { Text("Query") }
                    OutlinedButton(onClick = viewModel::rebuild, enabled = !state.loading) {
                        Text("Rebuild")
                    }
                }
            }
            if (state.loading) {
                item { CircularProgressIndicator() }
            }
            state.message?.let { msg ->
                item {
                    Text(msg, style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
            state.answer?.let { answer ->
                graphAnswerItems(answer)
            }
        }
    }
}

private fun androidx.compose.foundation.lazy.LazyListScope.graphAnswerItems(answer: GraphAnswer) {
    if (answer.communities.isNotEmpty()) {
        item { Text("Clusters", style = MaterialTheme.typography.titleMedium) }
        items(answer.communities) { community -> CommunityCard(community) }
    }
    if (answer.nodes.isNotEmpty()) {
        item { Text("Related nodes", style = MaterialTheme.typography.titleMedium) }
        items(answer.nodes) { node ->
            Card(modifier = Modifier.fillMaxWidth()) {
                Column(Modifier.padding(12.dp)) {
                    Text("[${node.type}] ${node.title}", style = MaterialTheme.typography.bodyMedium)
                    if (node.key.isNotBlank() && node.key != node.title) {
                        Text(node.key, style = MaterialTheme.typography.bodySmall,
                            fontFamily = FontFamily.Monospace,
                            color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
        }
    }
    if (answer.citations.isNotEmpty()) {
        item { Text("Sources", style = MaterialTheme.typography.titleMedium) }
        items(answer.citations) { src ->
            Text("• ${src.kind}: ${src.uri}", style = MaterialTheme.typography.bodySmall,
                fontFamily = FontFamily.Monospace)
        }
    }
}

@Composable
private fun CommunityCard(community: GraphCommunity) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text("cluster (${community.size} nodes)", style = MaterialTheme.typography.labelLarge)
            for (t in community.topTitles) {
                Text("• $t", style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}
