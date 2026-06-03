package com.aci.hermes.ui.screens.memory

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material3.AssistChip
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.aci.hermes.data.memory.MemoryCategory
import com.aci.hermes.data.memory.MemoryItem
import com.aci.hermes.data.model.PrivacyRisk
import com.aci.hermes.data.social.PrivacyRedactor

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MemoryDetail(
    item: MemoryItem,
    onDismiss: () -> Unit,
    onCorrect: () -> Unit,
    onDelete: () -> Unit,
    relatedLoader: (suspend (String) -> com.aci.hermes.data.cockpit.CockpitResult<com.aci.hermes.data.cockpit.RelatedItemList>)? = null,
) {
    val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = sheetState,
        modifier = Modifier.testTag(MemoryScreenTags.DETAIL),
    ) {
        Column(
            modifier = Modifier
                .padding(horizontal = 24.dp, vertical = 16.dp)
                .fillMaxWidth()
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text(item.category.display, style = MaterialTheme.typography.labelLarge,
                color = MaterialTheme.colorScheme.primary)
            Text(
                text = item.title.ifBlank { "(untitled memory)" },
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.SemiBold,
            )
            if (item.redacted) {
                Text(
                    text = "This memory contained a value that looked like a secret. The content is hidden from view.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.error,
                )
            }

            if (item.category == MemoryCategory.SOCIAL_SPEECH_PATTERN) {
                SocialPatternDetailSection(item)
            } else {
                Text(text = item.content, style = MaterialTheme.typography.bodyLarge)
            }

            HorizontalDivider()

            DetailRow("Durability", item.durability.display)
            DetailRow("Confidence", item.confidence.display)
            DetailRow("Source", item.provenance.source)
            item.provenance.sessionId?.let { DetailRow("Session", it) }
            DetailRow("Recorded", formatTimestamp(item.provenance.recordedAt))
            DetailRow("Created", formatTimestamp(item.createdAt))
            DetailRow("Updated", formatTimestamp(item.updatedAt))
            item.lastAccessedAt?.let { DetailRow("Last accessed", formatTimestamp(it)) }

            if (item.tags.isNotEmpty()) {
                HorizontalDivider()
                Text("Tags", style = MaterialTheme.typography.labelLarge)
                Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    item.tags.forEach { tag ->
                        AssistChip(onClick = {}, label = { Text(tag) })
                    }
                }
            }

            // GraphRAG: related files/sources/decisions for this memory entry.
            relatedLoader?.let { loader ->
                HorizontalDivider()
                com.aci.hermes.ui.screens.knowledge.KnowledgeRelatedCard(
                    loader = { loader(item.id) },
                    title = "Related in knowledge graph",
                )
            }

            HorizontalDivider()

            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = onCorrect) {
                    Icon(Icons.Default.Edit, contentDescription = null)
                    Text("Correct", modifier = Modifier.padding(start = 4.dp))
                }
                OutlinedButton(onClick = onDelete) {
                    Icon(Icons.Default.Delete, contentDescription = null)
                    Text("Delete", modifier = Modifier.padding(start = 4.dp))
                }
                TextButton(onClick = onDismiss) { Text("Close") }
            }
        }
    }
}

/**
 * Rich Social Speech Pattern body. Surfaces the privacy-risk label,
 * the inferred pattern kind, the abstract summary (hidden when
 * identity was detected), explicit safe / unsafe usage, the
 * "private identity flagged" notice, and public-source provenance.
 */
@Composable
private fun SocialPatternDetailSection(item: MemoryItem) {
    val pattern = PrivacyRedactor.sanitize(SocialPatternProjection.from(item))

    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        AssistChip(onClick = {}, label = { Text(pattern.kind.displayName) })
        PrivacyRiskChip(pattern.privacyRisk)
    }

    if (pattern.identityFlags.isNotEmpty()) {
        Text(
            text = "Private identity flagged: ${pattern.identityFlags.joinToString(", ")}",
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.error,
        )
    }

    SocialSectionLabel("Pattern summary")
    Text(
        text = if (pattern.privacyRisk == PrivacyRisk.HIGH) {
            "Summary hidden because identity was detected. Correct or delete this pattern to continue."
        } else {
            pattern.summary
        },
        style = MaterialTheme.typography.bodyLarge,
    )

    SocialSectionLabel("Safe usage")
    Text(text = pattern.safeUsage, style = MaterialTheme.typography.bodyMedium)

    SocialSectionLabel("Unsafe usage — never do this")
    Text(
        text = pattern.unsafeUsage,
        style = MaterialTheme.typography.bodyMedium,
        color = MaterialTheme.colorScheme.error,
    )

    if (pattern.provenance.isNotEmpty()) {
        SocialSectionLabel("Provenance (public sources)")
        pattern.provenance.forEach { entry ->
            Column {
                Text(entry.sourceTitle, style = MaterialTheme.typography.bodyMedium)
                Text(
                    entry.sourceKind.displayName,
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                entry.note?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
            }
        }
    }
}

@Composable
private fun SocialSectionLabel(text: String) {
    Text(
        text = text,
        style = MaterialTheme.typography.labelLarge,
        color = MaterialTheme.colorScheme.primary,
    )
}

@Composable
private fun DetailRow(label: String, value: String) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
    ) {
        Text(label, style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value, style = MaterialTheme.typography.bodyMedium)
    }
}
