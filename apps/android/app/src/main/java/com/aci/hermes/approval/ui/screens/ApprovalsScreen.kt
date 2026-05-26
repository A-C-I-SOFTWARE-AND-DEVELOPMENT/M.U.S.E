package com.aci.hermes.approval.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Tab
import androidx.compose.material3.TabRow
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.aci.hermes.R
import com.aci.hermes.approval.model.ApprovalRiskTier
import com.aci.hermes.approval.state.ApprovalViewModel
import com.aci.hermes.approval.ui.components.ApprovalHistoryCard
import com.aci.hermes.approval.ui.components.CriticalActionCard
import com.aci.hermes.approval.ui.components.RiskyApprovalCard
import com.aci.hermes.approval.ui.components.SeriousActionCard

/**
 * Top-level Approvals screen, reachable from the cockpit overflow menu.
 *
 * Two tabs: Pending (cards awaiting decisions) and History (decided items).
 * Dispatches each pending card to the right card composable based on its tier.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ApprovalsScreen(
    viewModel: ApprovalViewModel,
    onBack: () -> Unit,
    nowMillis: Long = System.currentTimeMillis(),
    modifier: Modifier = Modifier
) {
    val state by viewModel.state.collectAsState()
    var tab by remember { mutableIntStateOf(0) }
    val tabs = listOf("Pending", "History")
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.approvals_title)) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = null)
                    }
                }
            )
        },
        modifier = modifier
    ) { padding ->
        Column(Modifier.padding(padding).fillMaxSize()) {
            TabRow(selectedTabIndex = tab) {
                tabs.forEachIndexed { i, label ->
                    Tab(
                        selected = tab == i,
                        onClick = { tab = i },
                        text = { Text(label) }
                    )
                }
            }
            when (tab) {
                0 -> PendingTab(viewModel, state.cards, nowMillis)
                else -> HistoryTab(state.history)
            }
        }
    }
}

@Composable
private fun PendingTab(
    viewModel: ApprovalViewModel,
    cards: List<com.aci.hermes.approval.model.ApprovalCard>,
    nowMillis: Long
) {
    if (cards.isEmpty()) {
        Text(
            stringResource(R.string.approvals_empty_pending),
            modifier = Modifier.padding(24.dp),
            style = MaterialTheme.typography.bodyLarge
        )
        return
    }
    LazyColumn(
        contentPadding = PaddingValues(12.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
        modifier = Modifier.fillMaxSize()
    ) {
        items(cards, key = { it.id }) { card ->
            when (card.tier) {
                ApprovalRiskTier.RISKY -> RiskyApprovalCard(
                    card = card,
                    nowMillis = nowMillis,
                    onApprove = { note -> viewModel.approveRisky(card.id, note) },
                    onEdit = { newAction -> viewModel.editRisky(card.id, newAction) },
                    onReject = { reason -> viewModel.reject(card.id, reason) }
                )
                ApprovalRiskTier.SERIOUS -> SeriousActionCard(
                    card = card,
                    nowMillis = nowMillis,
                    onApproveStep1 = { viewModel.approveSeriousStep1(card.id) },
                    onApproveStep2 = { viewModel.approveSeriousStep2(card.id) },
                    onReject = { reason -> viewModel.reject(card.id, reason) },
                    onEmergencyStop = { viewModel.emergencyStop(card.id) }
                )
                ApprovalRiskTier.CRITICAL -> CriticalActionCard(
                    card = card,
                    nowMillis = nowMillis,
                    onApproveStep1 = { viewModel.approveCriticalStep1(card.id) },
                    onApproveStep2 = { viewModel.approveCriticalStep2(card.id) },
                    onReject = { reason -> viewModel.reject(card.id, reason) },
                    onEmergencyStop = { viewModel.emergencyStop(card.id) }
                )
                // SAFE/LOW are runtime-only — they should not appear here.
                // FORBIDDEN must be refused upstream and never reach the UI.
                else -> Unit
            }
        }
    }
}

@Composable
private fun HistoryTab(items: List<com.aci.hermes.approval.model.ApprovalHistoryItem>) {
    if (items.isEmpty()) {
        Text(
            stringResource(R.string.approvals_empty_history),
            modifier = Modifier.padding(24.dp),
            style = MaterialTheme.typography.bodyLarge
        )
        return
    }
    LazyColumn(
        contentPadding = PaddingValues(12.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
        modifier = Modifier.fillMaxSize()
    ) {
        items(items, key = { it.cardId + it.decidedAtMillis }) { ApprovalHistoryCard(it) }
    }
}
