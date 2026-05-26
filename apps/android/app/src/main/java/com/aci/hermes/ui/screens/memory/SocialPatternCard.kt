package com.aci.hermes.ui.screens.memory

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.AssistChip
import androidx.compose.material3.AssistChipDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import com.aci.hermes.data.model.PrivacyRisk
import com.aci.hermes.data.model.SocialPattern
import com.aci.hermes.data.social.PrivacyRedactor

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SocialPatternCard(
    pattern: SocialPattern,
    onTap: () -> Unit,
) {
    val safePattern = PrivacyRedactor.sanitize(pattern)
    Card(
        onClick = onTap,
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
    ) {
        Column(
            modifier = Modifier.fillMaxWidth().padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Text(
                    text = safePattern.title.ifBlank { "(untitled pattern)" },
                    style = MaterialTheme.typography.titleMedium,
                    modifier = Modifier.weight(1f),
                )
                PrivacyRiskChip(safePattern.privacyRisk)
            }
            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                AssistChip(
                    onClick = onTap,
                    label = { Text(safePattern.kind.displayName) },
                    colors = AssistChipDefaults.assistChipColors(),
                )
                if (safePattern.correctedFrom != null) {
                    AssistChip(
                        onClick = onTap,
                        label = { Text("corrected") },
                    )
                }
            }
            HorizontalDivider()
            Text(
                text = previewSummary(safePattern),
                style = MaterialTheme.typography.bodyMedium,
            )
            if (safePattern.identityFlags.isNotEmpty()) {
                Text(
                    text = "Private identity flagged: ${safePattern.identityFlags.joinToString(", ")}",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.error,
                )
            }
        }
    }
}

private fun previewSummary(pattern: SocialPattern): String {
    val raw = if (pattern.privacyRisk == PrivacyRisk.HIGH) {
        "Pattern hidden until you delete or correct it. Identity was detected in the source."
    } else {
        pattern.summary
    }
    return if (raw.length > 180) raw.take(180) + "…" else raw
}

@Composable
fun PrivacyRiskChip(risk: PrivacyRisk) {
    val (label, container, content) = when (risk) {
        PrivacyRisk.LOW -> Triple(
            risk.label,
            MaterialTheme.colorScheme.secondaryContainer,
            MaterialTheme.colorScheme.onSecondaryContainer,
        )
        PrivacyRisk.MEDIUM -> Triple(
            risk.label,
            MaterialTheme.colorScheme.tertiaryContainer,
            MaterialTheme.colorScheme.onTertiaryContainer,
        )
        PrivacyRisk.HIGH -> Triple(
            risk.label,
            MaterialTheme.colorScheme.errorContainer,
            MaterialTheme.colorScheme.onErrorContainer,
        )
    }
    AssistChip(
        onClick = {},
        label = { Text(label) },
        colors = AssistChipDefaults.assistChipColors(
            containerColor = container,
            labelColor = content,
            disabledContainerColor = container,
            disabledLabelColor = content,
            leadingIconContentColor = Color.Unspecified,
            trailingIconContentColor = Color.Unspecified,
            disabledLeadingIconContentColor = Color.Unspecified,
            disabledTrailingIconContentColor = Color.Unspecified,
        ),
    )
}
