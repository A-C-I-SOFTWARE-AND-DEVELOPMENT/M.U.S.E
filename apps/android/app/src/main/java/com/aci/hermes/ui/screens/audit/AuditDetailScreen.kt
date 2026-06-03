package com.aci.hermes.ui.screens.audit

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.ErrorOutline
import androidx.compose.material.icons.filled.ReportProblem
import androidx.compose.material3.AssistChip
import androidx.compose.material3.AssistChipDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import com.aci.hermes.R
import com.aci.hermes.data.model.audit.ApprovalHistoryItem
import com.aci.hermes.data.model.audit.AuditRecord
import com.aci.hermes.data.model.audit.EvidenceItem
import com.aci.hermes.data.model.audit.ProofRecord
import com.aci.hermes.data.model.audit.RiskTier
import com.aci.hermes.data.model.audit.RollbackPlan
import com.aci.hermes.data.model.audit.RouteSummary
import com.aci.hermes.data.model.audit.VerificationResult
import com.aci.hermes.data.model.audit.VerificationStatus
import com.aci.hermes.data.model.audit.WorkerRun

object AuditDetailTags {
    const val ROOT = "audit-detail"
    const val PROOF = "proof-detail"
    const val FAILED_VERIFICATION = "failed-verification-card"
    const val APPROVAL_HISTORY = "approval-history-card"
    const val ROLLBACK = "rollback-card"
    const val IMPACT_REPORT = "impact-report-card"
    const val WORKER_RUNS = "worker-runs"
    const val NOT_FOUND = "audit-detail-not-found"
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AuditDetailScreen(
    viewModel: AuditDetailViewModel,
    onBack: () -> Unit,
    relatedLoader: (suspend () -> com.aci.hermes.data.cockpit.CockpitResult<com.aci.hermes.data.cockpit.RelatedItemList>)? = null,
) {
    val state by viewModel.state.collectAsState()
    val scheme = MaterialTheme.colorScheme

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.audit_detail_title)) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(
                            Icons.AutoMirrored.Filled.ArrowBack,
                            contentDescription = stringResource(R.string.action_back),
                        )
                    }
                },
            )
        },
    ) { padding ->
        val record = state.record
        if (state.notFound || record == null) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding)
                    .padding(24.dp)
                    .testTag(AuditDetailTags.NOT_FOUND),
                contentAlignment = Alignment.Center,
            ) {
                Text(
                    stringResource(R.string.audit_detail_missing),
                    style = MaterialTheme.typography.bodyLarge,
                )
            }
            return@Scaffold
        }

        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 16.dp)
                .testTag(AuditDetailTags.ROOT),
            verticalArrangement = Arrangement.spacedBy(12.dp),
            contentPadding = androidx.compose.foundation.layout.PaddingValues(vertical = 12.dp),
        ) {
            item { SummaryCard(record) }

            // GraphRAG: related files/sources/decisions for this evidence entry.
            relatedLoader?.let { loader ->
                item {
                    com.aci.hermes.ui.screens.knowledge.KnowledgeRelatedCard(
                        loader = loader,
                        title = "Related in knowledge graph",
                    )
                }
            }

            state.proof?.let { proof ->
                if (proof.verification.status == VerificationStatus.FAILED) {
                    item { FailedVerificationCard(proof.verification) }
                }
                if (record.riskTier == RiskTier.CRITICAL && proof.impactReport != null) {
                    item { ImpactReportCard(proof.impactReport) }
                }
                item { ProofDetail(proof) }
                if (proof.approvals.isNotEmpty()) {
                    item { ApprovalHistoryCard(proof.approvals, record.riskTier) }
                }
                if (proof.workerRuns.isNotEmpty()) {
                    item { WorkerRunsSection(proof.workerRuns) }
                }
                proof.rollback?.let { item { RollbackCard(it) } }
            }
        }
    }
}

@Composable
private fun SummaryCard(record: AuditRecord) {
    val scheme = MaterialTheme.colorScheme
    Card(colors = CardDefaults.cardColors(containerColor = scheme.surfaceVariant)) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Row(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Surface(
                    shape = CircleShape,
                    color = record.result.colorOn(scheme),
                    modifier = Modifier.size(12.dp),
                ) {}
                Text(
                    formatTimestamp(record.timestamp),
                    style = MaterialTheme.typography.labelMedium,
                    color = scheme.onSurfaceVariant,
                )
                Text(
                    text = record.riskTier.displayLabel(),
                    style = MaterialTheme.typography.labelLarge,
                    color = record.riskTier.colorOn(scheme),
                    modifier = Modifier.padding(start = 4.dp),
                )
            }
            Text(
                stringResource(R.string.audit_detail_user_request),
                style = MaterialTheme.typography.labelMedium,
                color = scheme.onSurfaceVariant,
            )
            Text(record.userRequest, style = MaterialTheme.typography.titleMedium)
            Text(
                stringResource(R.string.audit_detail_action),
                style = MaterialTheme.typography.labelMedium,
                color = scheme.onSurfaceVariant,
            )
            Text(record.action, style = MaterialTheme.typography.bodyMedium)
            HorizontalDivider()
            RouteRow(record.route)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                AssistChip(
                    onClick = {},
                    label = { Text(record.approvalState.displayLabel()) },
                    colors = AssistChipDefaults.assistChipColors(
                        labelColor = record.approvalState.colorOn(scheme),
                    ),
                )
                AssistChip(
                    onClick = {},
                    label = { Text(record.result.displayLabel()) },
                    colors = AssistChipDefaults.assistChipColors(
                        labelColor = record.result.colorOn(scheme),
                    ),
                )
                AssistChip(
                    onClick = {},
                    label = { Text(confidenceLabel(record.confidence)) },
                )
            }
        }
    }
}

@Composable
private fun RouteRow(route: RouteSummary) {
    val scheme = MaterialTheme.colorScheme
    Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
        Text(
            stringResource(R.string.audit_detail_route),
            style = MaterialTheme.typography.labelMedium,
            color = scheme.onSurfaceVariant,
        )
        val routeText = buildString {
            append(route.destination.displayLabel())
            route.model?.let { append(" · "); append(it) }
            if (route.durationMs > 0) {
                append(" · ")
                append(formatDuration(route.durationMs))
            }
        }
        Text(routeText, style = MaterialTheme.typography.bodyMedium)
        if (route.reason.isNotBlank()) {
            Text(
                route.reason,
                style = MaterialTheme.typography.bodySmall,
                color = scheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
fun ProofDetail(proof: ProofRecord) {
    val scheme = MaterialTheme.colorScheme
    Card(
        colors = CardDefaults.cardColors(containerColor = scheme.surfaceVariant),
        modifier = Modifier
            .fillMaxWidth()
            .testTag(AuditDetailTags.PROOF),
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Text(
                stringResource(R.string.audit_proof_rationale),
                style = MaterialTheme.typography.labelMedium,
                color = scheme.onSurfaceVariant,
            )
            Text(proof.rationale, style = MaterialTheme.typography.bodyMedium)

            if (proof.filesChanged.isNotEmpty()) {
                HorizontalDivider()
                LabeledList(
                    label = stringResource(R.string.audit_proof_files),
                    items = proof.filesChanged,
                )
            }

            if (proof.testsRun.isNotEmpty()) {
                HorizontalDivider()
                LabeledList(
                    label = stringResource(R.string.audit_proof_tests),
                    items = proof.testsRun,
                )
            }

            if (proof.evidence.isNotEmpty()) {
                HorizontalDivider()
                Text(
                    stringResource(R.string.audit_proof_evidence),
                    style = MaterialTheme.typography.labelMedium,
                    color = scheme.onSurfaceVariant,
                )
                proof.evidence.forEach { EvidenceRow(it) }
            }
        }
    }
}

@Composable
private fun EvidenceRow(item: EvidenceItem) {
    val scheme = MaterialTheme.colorScheme
    Column(
        verticalArrangement = Arrangement.spacedBy(2.dp),
        modifier = Modifier.padding(top = 6.dp),
    ) {
        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            AssistChip(onClick = {}, label = { Text(item.kind.name.lowercase()) })
            Text(item.title, style = MaterialTheme.typography.titleSmall)
        }
        item.sourcePath?.let {
            Text(
                it,
                style = MaterialTheme.typography.labelSmall,
                color = scheme.onSurfaceVariant,
            )
        }
        Text(
            item.body,
            style = MaterialTheme.typography.bodySmall.copy(fontFamily = FontFamily.Monospace),
        )
    }
}

@Composable
private fun LabeledList(label: String, items: List<String>) {
    val scheme = MaterialTheme.colorScheme
    Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
        Text(label, style = MaterialTheme.typography.labelMedium, color = scheme.onSurfaceVariant)
        items.forEach { item ->
            Text(
                "• $item",
                style = MaterialTheme.typography.bodySmall.copy(fontFamily = FontFamily.Monospace),
            )
        }
    }
}

@Composable
fun FailedVerificationCard(verification: VerificationResult) {
    val scheme = MaterialTheme.colorScheme
    Card(
        colors = CardDefaults.cardColors(containerColor = scheme.errorContainer),
        modifier = Modifier
            .fillMaxWidth()
            .testTag(AuditDetailTags.FAILED_VERIFICATION),
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Icon(
                    Icons.Default.ErrorOutline,
                    contentDescription = null,
                    tint = scheme.error,
                )
                Text(
                    stringResource(R.string.audit_failed_verification_title),
                    style = MaterialTheme.typography.titleMedium,
                    color = scheme.error,
                )
            }
            Text(
                verification.summary,
                style = MaterialTheme.typography.bodyMedium,
                color = scheme.onErrorContainer,
            )
            if (verification.failingChecks.isNotEmpty()) {
                Text(
                    stringResource(R.string.audit_failed_verification_failing),
                    style = MaterialTheme.typography.labelMedium,
                    color = scheme.error,
                )
                verification.failingChecks.forEach { check ->
                    Text(
                        "• $check",
                        style = MaterialTheme.typography.bodySmall.copy(fontFamily = FontFamily.Monospace),
                        color = scheme.onErrorContainer,
                    )
                }
            }
        }
    }
}

@Composable
fun ApprovalHistoryCard(
    items: List<ApprovalHistoryItem>,
    riskTier: RiskTier,
) {
    val scheme = MaterialTheme.colorScheme
    val highlight = riskTier == RiskTier.SERIOUS || riskTier == RiskTier.CRITICAL

    Card(
        colors = CardDefaults.cardColors(
            containerColor = if (highlight) scheme.secondaryContainer else scheme.surfaceVariant,
        ),
        modifier = Modifier
            .fillMaxWidth()
            .testTag(AuditDetailTags.APPROVAL_HISTORY),
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(
                    stringResource(R.string.audit_approval_history_title),
                    style = MaterialTheme.typography.titleMedium,
                )
                if (highlight) {
                    AssistChip(
                        onClick = {},
                        label = { Text(stringResource(R.string.audit_approval_history_required)) },
                        colors = AssistChipDefaults.assistChipColors(
                            labelColor = scheme.error,
                        ),
                    )
                }
            }
            items.forEach { item ->
                Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                    Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        Text(
                            formatTimestamp(item.timestamp),
                            style = MaterialTheme.typography.labelMedium,
                            color = scheme.onSurfaceVariant,
                        )
                        Text(
                            item.approver,
                            style = MaterialTheme.typography.labelMedium,
                        )
                        Text(
                            item.state.displayLabel(),
                            style = MaterialTheme.typography.labelMedium,
                            color = item.state.colorOn(scheme),
                        )
                    }
                    item.comment?.let {
                        Text(it, style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
        }
    }
}

@Composable
fun WorkerRunCard(run: WorkerRun) {
    val scheme = MaterialTheme.colorScheme
    Card(
        colors = CardDefaults.cardColors(containerColor = scheme.surfaceVariant),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(
            modifier = Modifier.padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Surface(
                    shape = CircleShape,
                    color = run.status.colorOn(scheme),
                    modifier = Modifier.size(10.dp),
                ) {}
                Text(run.worker, style = MaterialTheme.typography.titleSmall)
                Text(
                    run.status.displayLabel(),
                    style = MaterialTheme.typography.labelMedium,
                    color = run.status.colorOn(scheme),
                )
            }
            val duration = (run.finishedAt - run.startedAt).coerceAtLeast(0)
            Text(
                "${formatTimestamp(run.startedAt)} · ${formatDuration(duration)}",
                style = MaterialTheme.typography.labelSmall,
                color = scheme.onSurfaceVariant,
            )
            if (run.notes.isNotBlank()) {
                Text(run.notes, style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}

@Composable
private fun WorkerRunsSection(runs: List<WorkerRun>) {
    Column(
        verticalArrangement = Arrangement.spacedBy(8.dp),
        modifier = Modifier
            .fillMaxWidth()
            .testTag(AuditDetailTags.WORKER_RUNS),
    ) {
        Text(
            stringResource(R.string.audit_worker_runs_title),
            style = MaterialTheme.typography.titleMedium,
        )
        runs.forEach { WorkerRunCard(it) }
    }
}

@Composable
fun RollbackCard(plan: RollbackPlan) {
    val scheme = MaterialTheme.colorScheme
    Card(
        colors = CardDefaults.cardColors(containerColor = scheme.surfaceVariant),
        modifier = Modifier
            .fillMaxWidth()
            .testTag(AuditDetailTags.ROLLBACK),
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(
                    stringResource(R.string.audit_rollback_title),
                    style = MaterialTheme.typography.titleMedium,
                )
                AssistChip(
                    onClick = {},
                    label = {
                        Text(
                            if (plan.executed) stringResource(R.string.audit_rollback_executed)
                            else if (plan.automatic) stringResource(R.string.audit_rollback_armed)
                            else stringResource(R.string.audit_rollback_manual),
                        )
                    },
                )
            }
            Text(plan.summary, style = MaterialTheme.typography.bodyMedium)
            plan.steps.forEachIndexed { i, step ->
                Text(
                    "${i + 1}. $step",
                    style = MaterialTheme.typography.bodySmall.copy(fontFamily = FontFamily.Monospace),
                )
            }
        }
    }
}

@Composable
private fun ImpactReportCard(report: String) {
    val scheme = MaterialTheme.colorScheme
    Card(
        colors = CardDefaults.cardColors(containerColor = scheme.tertiaryContainer),
        modifier = Modifier
            .fillMaxWidth()
            .testTag(AuditDetailTags.IMPACT_REPORT),
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Icon(
                    Icons.Default.ReportProblem,
                    contentDescription = null,
                    tint = scheme.error,
                )
                Text(
                    stringResource(R.string.audit_impact_report_title),
                    style = MaterialTheme.typography.titleMedium,
                )
            }
            Text(report, style = MaterialTheme.typography.bodyMedium)
        }
    }
}

private fun formatDuration(ms: Long): String {
    if (ms <= 0) return "—"
    val totalSeconds = ms / 1000
    if (totalSeconds < 60) return "${totalSeconds}s"
    val minutes = totalSeconds / 60
    val seconds = totalSeconds % 60
    return "${minutes}m ${seconds}s"
}
