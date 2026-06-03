package com.aci.hermes.ui.screens.research

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Check
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import com.aci.hermes.R
import com.aci.hermes.data.cockpit.ResearchCard
import com.aci.hermes.data.cockpit.ResearchContradiction
import com.aci.hermes.data.cockpit.ResearchReport
import com.aci.hermes.data.research.ResearchSync

object ResearchTestTags {
    const val QUERY = "research_query"
    const val RUN = "research_run"
    const val ANSWER = "research_answer"
    const val CREATE_TASK = "research_create_task"
}

/**
 * Research Mode — a mobile-native window onto the backend Evidence Engine.
 * Full-screen push (reached from Home/Chat). Shows the query, ranked sources,
 * evidence cards, the cited answer with its uncertainty, and any contradictions.
 * Findings can be promoted to memory (through the gateway's gate) or spun into a
 * coding task. Nothing here is fabricated — an empty result is shown honestly.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ResearchScreen(
    viewModel: ResearchViewModel,
    onBack: () -> Unit,
    onTaskCreated: (taskId: String) -> Unit,
) {
    val state by viewModel.state.collectAsState()
    val snackbarHost = remember { SnackbarHostState() }

    LaunchedEffect(state.createdTaskId) {
        state.createdTaskId?.let { id ->
            viewModel.consumeCreatedTask()
            onTaskCreated(id)
        }
    }
    LaunchedEffect(state.snackbar) {
        state.snackbar?.let {
            snackbarHost.showSnackbar(it)
            viewModel.consumeSnackbar()
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.research_title)) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = null)
                    }
                },
            )
        },
        snackbarHost = { SnackbarHost(snackbarHost) },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp)
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            val running = state.sync is ResearchSync.Loading
            OutlinedTextField(
                value = state.query,
                onValueChange = viewModel::setQuery,
                modifier = Modifier
                    .fillMaxWidth()
                    .testTag(ResearchTestTags.QUERY),
                label = { Text(stringResource(R.string.research_query_hint)) },
                singleLine = false,
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                keyboardActions = KeyboardActions(onSearch = { viewModel.run() }),
                enabled = !running,
            )
            Button(
                onClick = viewModel::run,
                enabled = !running,
                modifier = Modifier
                    .fillMaxWidth()
                    .testTag(ResearchTestTags.RUN),
            ) {
                if (running) {
                    CircularProgressIndicator(modifier = Modifier.size(18.dp), strokeWidth = 2.dp)
                } else {
                    Text(stringResource(R.string.research_run))
                }
            }

            when (val sync = state.sync) {
                is ResearchSync.Unpaired ->
                    HintCard(stringResource(R.string.research_unpaired))
                is ResearchSync.Error ->
                    HintCard(sync.message, error = true)
                is ResearchSync.Idle ->
                    HintCard(stringResource(R.string.research_empty_hint))
                else -> Unit
            }

            state.report?.let { report ->
                ReportBody(
                    report = report,
                    promotingCardId = state.promotingCardId,
                    promotedCardIds = state.promotedCardIds,
                    creatingTask = state.creatingTask,
                    onPromote = viewModel::promote,
                    onCreateTask = viewModel::createTask,
                )
            }
        }
    }
}

@Composable
private fun ReportBody(
    report: ResearchReport,
    promotingCardId: String?,
    promotedCardIds: Set<String>,
    creatingTask: Boolean,
    onPromote: (String) -> Unit,
    onCreateTask: () -> Unit,
) {
    // Honest empty state: the engine returned no source-backed evidence.
    if (report.cards.isEmpty()) {
        HintCard(report.notes.ifBlank { stringResource(R.string.research_no_sources) })
        if (report.finalAnswer.isNotBlank()) {
            Text(report.finalAnswer, style = MaterialTheme.typography.bodyMedium)
        }
        return
    }

    // Final answer + uncertainty.
    SectionTitle(stringResource(R.string.research_section_answer))
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(
                report.finalAnswer,
                style = MaterialTheme.typography.bodyLarge,
                modifier = Modifier.testTag(ResearchTestTags.ANSWER),
            )
            if (report.uncertainty.isNotBlank()) {
                AssistChip(
                    onClick = {},
                    label = { Text("${stringResource(R.string.research_uncertainty)}: ${report.uncertainty}") },
                )
            }
        }
    }

    Button(
        onClick = onCreateTask,
        enabled = !creatingTask,
        modifier = Modifier.fillMaxWidth().testTag(ResearchTestTags.CREATE_TASK),
    ) {
        Text(stringResource(R.string.research_create_task))
    }

    // Evidence cards (each promotable to memory).
    SectionTitle("${stringResource(R.string.research_section_evidence)} (${report.cards.size})")
    report.cards.forEach { card ->
        EvidenceCardView(
            card = card,
            promoting = promotingCardId == card.id,
            promoted = card.id in promotedCardIds,
            onPromote = { onPromote(card.id) },
        )
    }

    // Contradictions.
    if (report.contradictions.isNotEmpty()) {
        SectionTitle("${stringResource(R.string.research_section_contradictions)} (${report.contradictions.size})")
        report.contradictions.forEach { ContradictionView(it) }
    }
}

@Composable
private fun EvidenceCardView(
    card: ResearchCard,
    promoting: Boolean,
    promoted: Boolean,
    onPromote: () -> Unit,
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant,
        ),
    ) {
        Column(Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(card.title, style = MaterialTheme.typography.titleSmall)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                AssistChip(onClick = {}, label = { Text(card.evidenceStrength) })
                AssistChip(onClick = {}, label = { Text(card.sourceType) })
            }
            if (card.excerpt.isNotBlank()) {
                Text(card.excerpt, style = MaterialTheme.typography.bodyMedium, maxLines = 4)
            }
            Text(
                card.sourceUri,
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.primary,
            )
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
                if (promoted) {
                    TextButton(onClick = {}, enabled = false) {
                        Icon(Icons.Filled.Check, contentDescription = null, modifier = Modifier.size(16.dp))
                        Text(" " + stringResource(R.string.research_saved))
                    }
                } else {
                    OutlinedButton(onClick = onPromote, enabled = !promoting) {
                        if (promoting) {
                            CircularProgressIndicator(modifier = Modifier.size(16.dp), strokeWidth = 2.dp)
                        } else {
                            Text(stringResource(R.string.research_save_to_memory))
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun ContradictionView(c: ResearchContradiction) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.errorContainer,
        ),
    ) {
        Column(Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text(c.subject, style = MaterialTheme.typography.titleSmall)
            Text("• ${c.claimA}", style = MaterialTheme.typography.bodyMedium)
            Text("• ${c.claimB}", style = MaterialTheme.typography.bodyMedium)
            Text(c.reason, style = MaterialTheme.typography.labelSmall)
        }
    }
}

@Composable
private fun SectionTitle(text: String) {
    Text(text, style = MaterialTheme.typography.titleMedium)
}

@Composable
private fun HintCard(text: String, error: Boolean = false) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = if (error) MaterialTheme.colorScheme.errorContainer
                             else MaterialTheme.colorScheme.surfaceVariant,
        ),
    ) {
        Text(
            text,
            modifier = Modifier.padding(16.dp),
            style = MaterialTheme.typography.bodyMedium,
        )
    }
}
