package com.aci.hermes.ui.screens.capability

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material3.AssistChip
import androidx.compose.material3.AssistChipDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import com.aci.hermes.data.model.Capability

/**
 * Card representation of a single curated capability. Tapping the
 * card opens the route-preview / safe-invocation sheet — the card
 * itself never executes anything.
 */
@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Composable
fun SkillCard(
    capability: Capability,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Card(
        onClick = onClick,
        modifier = modifier
            .fillMaxWidth()
            .semantics { contentDescription = "Capability ${capability.name}" },
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant,
        ),
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    text = capability.name,
                    style = MaterialTheme.typography.titleMedium,
                    modifier = Modifier.weight(1f),
                )
                if (capability.ownerGated) {
                    OwnerGatedBadge()
                }
            }
            Text(
                text = capability.summary,
                style = MaterialTheme.typography.bodyMedium,
            )
            FlowRow(
                horizontalArrangement = Arrangement.spacedBy(6.dp),
                verticalArrangement = Arrangement.spacedBy(4.dp),
            ) {
                AssistChip(
                    onClick = onClick,
                    label = { Text(capability.category.displayName) },
                )
                AssistChip(
                    onClick = onClick,
                    label = { Text(capability.route.surface.displayName) },
                )
                if (capability.isAdvanced) {
                    AssistChip(
                        onClick = onClick,
                        label = { Text("Advanced") },
                    )
                }
            }
            Text(
                text = "Lane: ${capability.route.lane}",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurface,
            )
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun OwnerGatedBadge() {
    AssistChip(
        onClick = {},
        enabled = false,
        leadingIcon = {
            Icon(
                imageVector = Icons.Default.Lock,
                contentDescription = null,
            )
        },
        label = { Text("Owner-gated") },
        colors = AssistChipDefaults.assistChipColors(
            disabledContainerColor = MaterialTheme.colorScheme.errorContainer,
            disabledLabelColor = MaterialTheme.colorScheme.onErrorContainer,
            disabledLeadingIconContentColor = MaterialTheme.colorScheme.onErrorContainer,
        ),
        modifier = Modifier.semantics { contentDescription = "Owner-gated capability" },
    )
    Spacer(modifier = Modifier.width(0.dp))
}
