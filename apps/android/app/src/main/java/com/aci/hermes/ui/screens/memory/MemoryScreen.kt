package com.aci.hermes.ui.screens.memory

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.DeleteOutline
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
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
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.aci.hermes.R
import com.aci.hermes.data.model.MemoryBranch
import com.aci.hermes.data.model.MemoryConfidence
import com.aci.hermes.data.model.MemoryFact

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MemoryScreen(viewModel: MemoryViewModel, onBack: () -> Unit) {
    val state by viewModel.state.collectAsState()

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text(stringResource(R.string.memory_title))
                        Text(
                            stringResource(R.string.memory_subtitle),
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = null)
                    }
                },
            )
        },
    ) { padding ->
        Column(modifier = Modifier.fillMaxSize().padding(padding)) {
            OutlinedTextField(
                value = state.query,
                onValueChange = viewModel::setQuery,
                placeholder = { Text(stringResource(R.string.memory_search_hint)) },
                modifier = Modifier.fillMaxWidth().padding(16.dp),
                singleLine = true,
            )
            Row(
                modifier = Modifier
                    .horizontalScroll(rememberScrollState())
                    .padding(horizontal = 16.dp),
                horizontalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                FilterChip(
                    selected = state.branch == null,
                    onClick = { viewModel.setBranch(null) },
                    label = { Text("All") },
                )
                MemoryBranch.entries.forEach { branch ->
                    FilterChip(
                        selected = state.branch == branch,
                        onClick = { viewModel.setBranch(branch) },
                        label = { Text(branchLabel(branch)) },
                    )
                }
            }
            val visible = viewModel.filtered()
            if (visible.isEmpty()) {
                Column(
                    modifier = Modifier.fillMaxSize(),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.Center,
                ) { Text(stringResource(R.string.memory_empty), style = MaterialTheme.typography.bodyMedium) }
            } else {
                LazyColumn(
                    contentPadding = PaddingValues(horizontal = 16.dp, vertical = 12.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    items(visible) { fact ->
                        FactCard(
                            fact = fact,
                            onConfirm = { viewModel.confirm(fact) },
                            onForget = { viewModel.forget(fact) },
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun branchLabel(branch: MemoryBranch): String = when (branch) {
    MemoryBranch.FACTS -> stringResource(R.string.memory_branch_facts)
    MemoryBranch.PREFERENCES -> stringResource(R.string.memory_branch_preferences)
    MemoryBranch.GOALS -> stringResource(R.string.memory_branch_goals)
    MemoryBranch.HISTORY -> stringResource(R.string.memory_branch_history)
    MemoryBranch.INFERENCES -> stringResource(R.string.memory_branch_inferences)
}

@Composable
private fun FactCard(fact: MemoryFact, onConfirm: () -> Unit, onForget: () -> Unit) {
    Card(
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
        shape = RoundedCornerShape(14.dp),
    ) {
        Column(modifier = Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                AssistChip(
                    onClick = {},
                    label = { Text(branchLabel(fact.branch), style = MaterialTheme.typography.labelSmall) },
                )
                Text(
                    text = confidenceLabel(fact.confidence),
                    style = MaterialTheme.typography.labelSmall,
                    color = confidenceColor(fact.confidence),
                    modifier = Modifier.padding(start = 8.dp),
                )
            }
            Text(fact.label, style = MaterialTheme.typography.titleSmall)
            Text(fact.detail, style = MaterialTheme.typography.bodyMedium)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                if (fact.confidence != MemoryConfidence.CONFIRMED) {
                    OutlinedButton(onClick = onConfirm) {
                        Icon(Icons.Default.Check, contentDescription = null)
                        Text(stringResource(R.string.memory_confirm), modifier = Modifier.padding(start = 4.dp))
                    }
                }
                OutlinedButton(onClick = onForget) {
                    Icon(Icons.Default.DeleteOutline, contentDescription = null)
                    Text(stringResource(R.string.memory_forget), modifier = Modifier.padding(start = 4.dp))
                }
            }
        }
    }
}

@Composable
private fun confidenceLabel(confidence: MemoryConfidence): String = when (confidence) {
    MemoryConfidence.CONFIRMED -> stringResource(R.string.memory_confirmed_label)
    MemoryConfidence.INFERRED -> stringResource(R.string.memory_inferred_label)
    MemoryConfidence.REJECTED -> "Rejected"
}

@Composable
private fun confidenceColor(confidence: MemoryConfidence) = when (confidence) {
    MemoryConfidence.CONFIRMED -> MaterialTheme.colorScheme.tertiary
    MemoryConfidence.INFERRED -> MaterialTheme.colorScheme.primary
    MemoryConfidence.REJECTED -> MaterialTheme.colorScheme.error
}
