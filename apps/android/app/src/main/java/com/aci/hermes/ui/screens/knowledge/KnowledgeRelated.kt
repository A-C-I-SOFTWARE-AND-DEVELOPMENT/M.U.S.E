package com.aci.hermes.ui.screens.knowledge

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.AssistChip
import androidx.compose.material3.AssistChipDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import com.aci.hermes.data.cockpit.CockpitResult
import com.aci.hermes.data.cockpit.RelatedItem
import com.aci.hermes.data.cockpit.RelatedItemList
import com.aci.hermes.data.cockpit.RelatedKind

/**
 * Reusable "Knowledge / Related" panel for job and evidence screens.
 *
 * Shows related files / sources / decisions from the GraphRAG knowledge graph,
 * grouped by bucket, each labelled with its relationship and whether it is
 * source-backed. Stateless — the host passes already-loaded [items]. Honest
 * empty: when there is nothing related, it renders a short explanatory line
 * (never invented relationships).
 */
@Composable
fun KnowledgeRelatedSection(
    items: List<RelatedItem>,
    modifier: Modifier = Modifier,
    title: String = "Knowledge graph",
) {
    Card(modifier = modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier.fillMaxWidth().padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Text(title, style = MaterialTheme.typography.titleMedium)
            if (items.isEmpty()) {
                Text(
                    "No related files, sources, or decisions yet.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                return@Column
            }
            for (bucket in RELATED_BUCKET_ORDER) {
                val group = items.filter { it.bucket == bucket }
                if (group.isEmpty()) continue
                Text(
                    bucketLabel(bucket),
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.primary,
                )
                for (item in group) {
                    RelatedRow(item)
                }
            }
        }
    }
}

@Composable
private fun RelatedRow(item: RelatedItem) {
    Column(
        modifier = Modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(2.dp),
    ) {
        Text(
            item.title,
            style = MaterialTheme.typography.bodyMedium,
            fontFamily = if (item.bucket == RelatedKind.FILE) FontFamily.Monospace else FontFamily.Default,
        )
        AssistChip(
            onClick = {},
            enabled = false,
            label = {
                val flag = if (item.sourceBacked) " ✓ source-backed" else ""
                Text("${item.relation}$flag", style = MaterialTheme.typography.labelSmall)
            },
            colors = AssistChipDefaults.assistChipColors(),
        )
    }
}

/**
 * Stateful wrapper: loads related items from a [loader] (typically a
 * `CockpitGraphRepository.relatedFor*` call) and renders the section with
 * loading / error / loaded states. Host screens use this so they don't need to
 * thread graph state through their own ViewModels.
 */
@Composable
fun KnowledgeRelatedCard(
    entityKey: Any?,
    loader: suspend () -> CockpitResult<RelatedItemList>,
    modifier: Modifier = Modifier,
    title: String = "Knowledge graph",
) {
    // Key the load by the stable entity id, not the loader lambda: an inline
    // lambda has a fresh identity each recomposition, so keying LaunchedEffect
    // by it would re-fire the request on every recomposition. rememberUpdatedState
    // lets the effect call the latest loader without restarting.
    val currentLoader by rememberUpdatedState(loader)
    var items by remember(entityKey) { mutableStateOf<List<RelatedItem>?>(null) }
    var error by remember(entityKey) { mutableStateOf<String?>(null) }

    LaunchedEffect(entityKey) {
        when (val res = currentLoader()) {
            is CockpitResult.Success -> items = res.value.related
            is CockpitResult.Failure -> {
                error = "Gateway error ${res.httpStatus}"
                items = emptyList()
            }
            is CockpitResult.Unreachable -> {
                error = res.message
                items = emptyList()
            }
        }
    }

    when {
        items == null && error == null ->
            Card(modifier = modifier.fillMaxWidth()) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text(title, style = MaterialTheme.typography.titleMedium)
                    CircularProgressIndicator()
                }
            }
        else -> KnowledgeRelatedSection(items ?: emptyList(), modifier, title)
    }
}

private val RELATED_BUCKET_ORDER = listOf(RelatedKind.FILE, RelatedKind.SOURCE, RelatedKind.DECISION)

private fun bucketLabel(kind: RelatedKind): String = when (kind) {
    RelatedKind.FILE -> "Files"
    RelatedKind.SOURCE -> "Sources"
    RelatedKind.DECISION -> "Decisions"
    RelatedKind.UNKNOWN -> "Other"
}
