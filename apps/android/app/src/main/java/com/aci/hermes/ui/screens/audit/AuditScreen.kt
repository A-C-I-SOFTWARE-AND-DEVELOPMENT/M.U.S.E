package com.aci.hermes.ui.screens.audit

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.MutableTransitionState
import androidx.compose.animation.fadeIn
import androidx.compose.animation.slideInVertically
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.ErrorOutline
import androidx.compose.material.icons.filled.Timeline
import androidx.compose.material3.AssistChip
import androidx.compose.material3.AssistChipDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
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
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.aci.hermes.R
import com.aci.hermes.data.model.audit.AuditRecord
import com.aci.hermes.ui.designsystem.MuseCard
import com.aci.hermes.ui.designsystem.MuseEmptyState
import com.aci.hermes.ui.designsystem.MuseMotion
import com.aci.hermes.ui.theme.JarvisTokens

object AuditScreenTags {
    const val LIST = "audit-list"
    const val EMPTY = "audit-list-empty"
    fun row(id: String): String = "audit-row-$id"
    fun failedBadge(id: String): String = "audit-failed-$id"
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AuditScreen(
    viewModel: AuditViewModel,
    onBack: () -> Unit,
    onOpenAudit: (String) -> Unit,
    onOpenActivity: (() -> Unit)? = null,
) {
    val records by viewModel.records.collectAsState()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.audit_title)) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(
                            Icons.AutoMirrored.Filled.ArrowBack,
                            contentDescription = stringResource(R.string.action_back),
                        )
                    }
                },
                actions = {
                    if (onOpenActivity != null) {
                        IconButton(
                            onClick = onOpenActivity,
                            modifier = Modifier.testTag("audit-open-activity"),
                        ) {
                            Icon(
                                Icons.Default.Timeline,
                                contentDescription = stringResource(R.string.audit_activity_action),
                            )
                        }
                    }
                },
            )
        },
    ) { padding ->
        if (records.isEmpty()) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding)
                    .testTag(AuditScreenTags.EMPTY),
                contentAlignment = Alignment.Center,
            ) {
                MuseEmptyState(
                    title = stringResource(R.string.audit_empty),
                    body = "Decisions and approvals will appear here once Muse acts.",
                )
            }
        } else {
            LazyColumn(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding)
                    .padding(horizontal = JarvisTokens.SpaceLg)
                    .testTag(AuditScreenTags.LIST),
                verticalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceMd),
                contentPadding = androidx.compose.foundation.layout.PaddingValues(vertical = JarvisTokens.SpaceMd),
            ) {
                items(records, key = AuditRecord::id) { record ->
                    AuditCard(
                        record = record,
                        onClick = { onOpenAudit(record.id) },
                    )
                }
            }
        }
    }
}

@Composable
fun AuditCard(
    record: AuditRecord,
    onClick: () -> Unit,
) {
    val scheme = MaterialTheme.colorScheme
    val failed = record.result.isFailureLike()

    // Subtle entrance: rows fade + rise in on the standard curve.
    val appear = remember { MutableTransitionState(false).apply { targetState = true } }
    AnimatedVisibility(
        visibleState = appear,
        enter = fadeIn(MuseMotion.standard()) +
            slideInVertically(MuseMotion.standard()) { it / 6 },
    ) {
        MuseCard(
            modifier = Modifier
                .fillMaxWidth()
                .testTag(AuditScreenTags.row(record.id))
                .clickable(onClick = onClick),
        ) {
            Column(
                modifier = Modifier.padding(JarvisTokens.SpaceLg),
                verticalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceXs),
            ) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm),
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Surface(
                        shape = CircleShape,
                        color = record.result.colorOn(scheme),
                        modifier = Modifier.size(10.dp),
                    ) {}
                    Text(
                        text = formatTimestamp(record.timestamp),
                        style = MaterialTheme.typography.labelMedium,
                        color = scheme.onSurfaceVariant,
                    )
                    Text(
                        text = record.riskTier.displayLabel(),
                        style = MaterialTheme.typography.labelMedium,
                        color = record.riskTier.colorOn(scheme),
                        modifier = Modifier.padding(start = JarvisTokens.SpaceSm),
                    )
                    if (failed) {
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceXs),
                            modifier = Modifier
                                .padding(start = JarvisTokens.SpaceSm)
                                .testTag(AuditScreenTags.failedBadge(record.id)),
                        ) {
                            Icon(
                                Icons.Default.ErrorOutline,
                                contentDescription = null,
                                tint = scheme.error,
                                modifier = Modifier.size(16.dp),
                            )
                            Text(
                                stringResource(R.string.audit_failed_badge),
                                style = MaterialTheme.typography.labelMedium,
                                color = scheme.error,
                            )
                        }
                    }
                }
                Text(
                    text = record.userRequest,
                    style = MaterialTheme.typography.titleSmall,
                )
                Text(
                    text = record.action,
                    style = MaterialTheme.typography.bodyMedium,
                )
                Row(
                    horizontalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    AssistChip(
                        onClick = onClick,
                        label = { Text(record.route.destination.displayLabel()) },
                    )
                    AssistChip(
                        onClick = onClick,
                        label = { Text(record.approvalState.displayLabel()) },
                        colors = AssistChipDefaults.assistChipColors(
                            labelColor = record.approvalState.colorOn(scheme),
                        ),
                    )
                    AssistChip(
                        onClick = onClick,
                        label = { Text(record.result.displayLabel()) },
                        colors = AssistChipDefaults.assistChipColors(
                            labelColor = record.result.colorOn(scheme),
                        ),
                    )
                }
                Text(
                    text = confidenceLabel(record.confidence),
                    style = MaterialTheme.typography.labelSmall,
                    color = scheme.onSurfaceVariant,
                )
            }
        }
    }
}
