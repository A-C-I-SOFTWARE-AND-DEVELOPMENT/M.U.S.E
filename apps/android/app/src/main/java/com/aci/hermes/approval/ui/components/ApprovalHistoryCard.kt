package com.aci.hermes.approval.ui.components

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.aci.hermes.approval.model.ApprovalHistoryItem
import java.text.DateFormat
import java.util.Date

@Composable
fun ApprovalHistoryCard(item: ApprovalHistoryItem, modifier: Modifier = Modifier) {
    Card(
        modifier = modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)
    ) {
        Column(Modifier.padding(12.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                TierBadge(item.tier)
                Spacer(Modifier.height(0.dp).fillMaxWidth().weight(1f))
                StatusBadge(item.outcome)
            }
            Spacer(Modifier.height(6.dp))
            Text(item.title, style = MaterialTheme.typography.titleSmall)
            Text(
                "${item.decidedBy} · ${DateFormat.getDateTimeInstance().format(Date(item.decidedAtMillis))}",
                style = MaterialTheme.typography.bodySmall
            )
            item.note?.takeIf { it.isNotBlank() }?.let {
                Spacer(Modifier.height(4.dp))
                Text("Note: $it", style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}
