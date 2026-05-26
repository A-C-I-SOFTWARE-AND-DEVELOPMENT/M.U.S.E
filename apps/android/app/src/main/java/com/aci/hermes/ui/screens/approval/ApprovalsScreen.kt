package com.aci.hermes.ui.screens.approval

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Bolt
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.ErrorOutline
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.aci.hermes.R
import com.aci.hermes.data.model.ApprovalCard
import com.aci.hermes.data.model.ApprovalSeverity
import com.aci.hermes.data.model.ApprovalStatus
import com.aci.hermes.data.model.ImpactReport

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ApprovalsScreen(viewModel: ApprovalsViewModel) {
    val state by viewModel.state.collectAsState()
    var selected by remember { mutableStateOf<ApprovalCard?>(null) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text(stringResource(R.string.approvals_title))
                        Text(
                            stringResource(R.string.approvals_subtitle),
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                },
            )
        },
    ) { padding ->
        Column(modifier = Modifier.fillMaxSize().padding(padding)) {
            FilterRow(
                filter = state.filter,
                onChange = viewModel::setFilter,
                pendingCount = state.pending.size,
                decidedCount = state.decided.size,
            )
            val visible = when (state.filter) {
                ApprovalsFilter.PENDING -> state.pending
                ApprovalsFilter.DECIDED -> state.decided
                ApprovalsFilter.ALL -> state.pending + state.decided
            }
            if (visible.isEmpty()) {
                Column(
                    modifier = Modifier.fillMaxSize(),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.Center,
                ) {
                    Text(
                        text = stringResource(R.string.approvals_empty),
                        style = MaterialTheme.typography.bodyMedium,
                    )
                }
            } else {
                LazyColumn(
                    contentPadding = PaddingValues(horizontal = 16.dp, vertical = 12.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    items(visible) { card ->
                        ApprovalRow(
                            card = card,
                            onOpen = { selected = card },
                        )
                    }
                }
            }
        }
    }

    selected?.let { card ->
        ApprovalDialog(
            card = card,
            requireDoubleConfirmSerious = state.requireDoubleConfirmSerious,
            requireCriticalPhrase = state.requireCriticalPhrase,
            emergencyEngaged = state.emergencyEngaged,
            onDismiss = { selected = null },
            onApprove = { notes ->
                viewModel.approve(card, notes)
                selected = null
            },
            onDeny = { notes ->
                viewModel.deny(card, notes)
                selected = null
            },
        )
    }
}

@Composable
private fun FilterRow(
    filter: ApprovalsFilter,
    onChange: (ApprovalsFilter) -> Unit,
    pendingCount: Int,
    decidedCount: Int,
) {
    Row(
        modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        FilterChip(
            selected = filter == ApprovalsFilter.PENDING,
            onClick = { onChange(ApprovalsFilter.PENDING) },
            label = { Text("Pending ($pendingCount)") },
        )
        FilterChip(
            selected = filter == ApprovalsFilter.DECIDED,
            onClick = { onChange(ApprovalsFilter.DECIDED) },
            label = { Text("Decided ($decidedCount)") },
        )
        FilterChip(
            selected = filter == ApprovalsFilter.ALL,
            onClick = { onChange(ApprovalsFilter.ALL) },
            label = { Text("All") },
        )
    }
}

@Composable
private fun ApprovalRow(card: ApprovalCard, onOpen: () -> Unit) {
    Card(
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
        shape = RoundedCornerShape(14.dp),
        onClick = onOpen,
    ) {
        Column(modifier = Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                SeverityChip(card.severity)
                Surface(color = Color.Transparent, modifier = Modifier.weight(1f)) {}
                StatusBadge(card.status)
            }
            Text(card.title, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
            Text(card.summary, style = MaterialTheme.typography.bodySmall, maxLines = 3)
            if (card.impact != null) {
                AssistChip(
                    onClick = onOpen,
                    label = { Text(stringResource(R.string.approvals_inspect)) },
                    leadingIcon = { Icon(Icons.Default.Info, contentDescription = null) },
                )
            }
        }
    }
}

@Composable
private fun SeverityChip(severity: ApprovalSeverity) {
    val (text, color) = when (severity) {
        ApprovalSeverity.ROUTINE -> stringResource(R.string.approvals_severity_routine) to MaterialTheme.colorScheme.secondary
        ApprovalSeverity.RISKY -> stringResource(R.string.approvals_severity_risky) to MaterialTheme.colorScheme.tertiary
        ApprovalSeverity.SERIOUS -> stringResource(R.string.approvals_severity_serious) to MaterialTheme.colorScheme.primary
        ApprovalSeverity.CRITICAL -> stringResource(R.string.approvals_severity_critical) to MaterialTheme.colorScheme.error
    }
    Surface(color = color.copy(alpha = 0.18f), shape = RoundedCornerShape(50)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Surface(color = color, shape = CircleShape, modifier = Modifier.padding(start = 8.dp).size(8.dp)) {}
            Text(
                text,
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurface,
                modifier = Modifier.padding(start = 6.dp, end = 10.dp, top = 4.dp, bottom = 4.dp),
            )
        }
    }
}

@Composable
private fun StatusBadge(status: ApprovalStatus) {
    val text = when (status) {
        ApprovalStatus.PENDING -> "Pending"
        ApprovalStatus.APPROVED -> "Approved"
        ApprovalStatus.DENIED -> "Denied"
        ApprovalStatus.EXPIRED -> "Expired"
        ApprovalStatus.CANCELLED_BY_EMERGENCY_STOP -> "E-stop"
    }
    Text(
        text = text,
        style = MaterialTheme.typography.labelSmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
    )
}

@Composable
private fun ApprovalDialog(
    card: ApprovalCard,
    requireDoubleConfirmSerious: Boolean,
    requireCriticalPhrase: Boolean,
    emergencyEngaged: Boolean,
    onDismiss: () -> Unit,
    onApprove: (notes: String?) -> Unit,
    onDeny: (notes: String?) -> Unit,
) {
    var notes by remember { mutableStateOf("") }
    var confirmStep by remember { mutableStateOf(0) }
    var typedPhrase by remember { mutableStateOf("") }

    val phrase = stringResource(R.string.approvals_authorize_phrase)
    val needsDouble = card.severity == ApprovalSeverity.SERIOUS && requireDoubleConfirmSerious ||
        card.severity == ApprovalSeverity.CRITICAL
    val needsPhrase = card.severity == ApprovalSeverity.CRITICAL && requireCriticalPhrase

    val canApprove = !emergencyEngaged && card.status == ApprovalStatus.PENDING && when {
        needsPhrase -> typedPhrase.trim() == phrase
        needsDouble -> confirmStep >= 1
        else -> true
    }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = {
            Column {
                SeverityChip(card.severity)
                Text(
                    card.title,
                    style = MaterialTheme.typography.titleMedium,
                    modifier = Modifier.padding(top = 6.dp),
                )
            }
        },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(card.summary, style = MaterialTheme.typography.bodyMedium)
                if (card.impact != null) ImpactReportBlock(card.impact)
                if (card.severity == ApprovalSeverity.CRITICAL) {
                    Surface(
                        color = MaterialTheme.colorScheme.errorContainer,
                        shape = RoundedCornerShape(8.dp),
                    ) {
                        Row(modifier = Modifier.padding(10.dp), verticalAlignment = Alignment.CenterVertically) {
                            Icon(Icons.Default.Warning, contentDescription = null, tint = MaterialTheme.colorScheme.error)
                            Text(
                                text = stringResource(R.string.approvals_critical_warning),
                                style = MaterialTheme.typography.bodySmall,
                                modifier = Modifier.padding(start = 8.dp),
                                color = MaterialTheme.colorScheme.onErrorContainer,
                            )
                        }
                    }
                }
                if (needsPhrase) {
                    OutlinedTextField(
                        value = typedPhrase,
                        onValueChange = { typedPhrase = it },
                        label = { Text(stringResource(R.string.approvals_authorize_hint)) },
                        placeholder = { Text(phrase) },
                        modifier = Modifier.fillMaxWidth(),
                    )
                }
                if (card.status == ApprovalStatus.PENDING) {
                    OutlinedTextField(
                        value = notes,
                        onValueChange = { notes = it },
                        label = { Text("Notes (optional)") },
                        modifier = Modifier.fillMaxWidth(),
                    )
                }
                if (needsDouble && card.status == ApprovalStatus.PENDING) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Default.ErrorOutline, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
                        Text(
                            text = if (confirmStep == 0) "Tap Approve once, then again to confirm."
                            else "Tap Approve a second time to authorize.",
                            modifier = Modifier.padding(start = 8.dp),
                            style = MaterialTheme.typography.bodySmall,
                        )
                    }
                }
            }
        },
        confirmButton = {
            if (card.status == ApprovalStatus.PENDING) {
                Button(
                    onClick = {
                        if (needsDouble && confirmStep == 0) {
                            confirmStep = 1
                        } else if (canApprove) {
                            onApprove(notes.ifBlank { null })
                        }
                    },
                    enabled = !emergencyEngaged && (
                        needsDouble && confirmStep == 0 || canApprove
                    ),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = MaterialTheme.colorScheme.primary,
                    ),
                ) {
                    Icon(Icons.Default.Check, contentDescription = null)
                    Text(
                        text = if (needsDouble && confirmStep == 0) stringResource(R.string.approvals_confirm_again)
                        else stringResource(R.string.approvals_approve),
                        modifier = Modifier.padding(start = 6.dp),
                    )
                }
            } else {
                TextButton(onClick = onDismiss) { Text(stringResource(R.string.action_close)) }
            }
        },
        dismissButton = {
            if (card.status == ApprovalStatus.PENDING) {
                OutlinedButton(onClick = { onDeny(notes.ifBlank { null }) }) {
                    Icon(Icons.Default.Close, contentDescription = null)
                    Text(stringResource(R.string.approvals_deny), modifier = Modifier.padding(start = 6.dp))
                }
            }
        },
    )
}

@Composable
private fun ImpactReportBlock(impact: ImpactReport) {
    Card(
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        shape = RoundedCornerShape(10.dp),
    ) {
        Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(
                stringResource(R.string.approvals_impact_title),
                style = MaterialTheme.typography.titleSmall,
                color = MaterialTheme.colorScheme.primary,
            )
            HorizontalDivider()
            Text(stringResource(R.string.approvals_impact_summary), style = MaterialTheme.typography.labelLarge)
            Text(impact.summary, style = MaterialTheme.typography.bodySmall)
            if (impact.risks.isNotEmpty()) {
                Text(stringResource(R.string.approvals_impact_risks), style = MaterialTheme.typography.labelLarge)
                impact.risks.forEach {
                    Row(verticalAlignment = Alignment.Top) {
                        Icon(Icons.Default.Bolt, contentDescription = null, tint = MaterialTheme.colorScheme.error)
                        Text(it, style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(start = 6.dp))
                    }
                }
            }
            impact.rollbackPlan?.let { plan ->
                Text(stringResource(R.string.approvals_impact_rollback), style = MaterialTheme.typography.labelLarge)
                Text(plan, style = MaterialTheme.typography.bodySmall)
            }
            if (impact.affectedSurfaces.isNotEmpty()) {
                Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                    impact.affectedSurfaces.forEach { surface ->
                        AssistChip(onClick = {}, label = { Text(surface, style = MaterialTheme.typography.labelSmall) })
                    }
                }
            }
            Text(
                text = "Blast radius: ${impact.estimatedBlastRadius.name.lowercase()}",
                style = MaterialTheme.typography.labelSmall,
            )
        }
    }
}
