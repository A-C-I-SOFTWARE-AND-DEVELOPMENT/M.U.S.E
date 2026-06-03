package com.aci.hermes.ui.screens.jobs

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.ExperimentalMaterial3Api
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
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp

private const val OWNER_PHRASE = "Yes, with authorization."

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun JobsScreen(
    viewModel: JobsViewModel,
    onBack: () -> Unit,
) {
    val state by viewModel.state.collectAsState()
    var prompt by remember { mutableStateOf("") }
    var phrase by remember { mutableStateOf("") }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Jobs") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                },
            )
        },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            OutlinedTextField(
                value = prompt,
                onValueChange = { prompt = it },
                modifier = Modifier.fillMaxWidth(),
                label = { Text("Give JARVIS a job") },
                placeholder = { Text("e.g. add a worker-runs view to the cockpit") },
                enabled = !state.busy,
                singleLine = true,
            )
            Button(
                onClick = { viewModel.submit(prompt); prompt = "" },
                enabled = !state.busy && prompt.isNotBlank(),
            ) { Text(if (state.busy) "Working…" else "Submit job") }

            OutlinedTextField(
                value = phrase,
                onValueChange = { phrase = it },
                modifier = Modifier.fillMaxWidth(),
                label = { Text("Owner phrase (for execute lanes)") },
                placeholder = { Text(OWNER_PHRASE) },
                singleLine = true,
            )

            if (state.message.isNotBlank()) {
                Text(
                    state.message,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.primary,
                )
            }
            if (state.notPaired) {
                Text(
                    "Not connected to a runtime — pair in Settings to manage jobs.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.error,
                )
            }

            LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                items(state.jobs, key = { it.id }) { job ->
                    Card(modifier = Modifier.fillMaxWidth()) {
                        Column(
                            modifier = Modifier.padding(12.dp),
                            verticalArrangement = Arrangement.spacedBy(6.dp),
                        ) {
                            Text(job.title, fontWeight = FontWeight.SemiBold)
                            Text(
                                "status: ${job.status}" +
                                    (if (job.workerId.isNotBlank()) " · ${job.workerId}" else ""),
                                style = MaterialTheme.typography.labelSmall,
                            )
                            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                OutlinedButton(
                                    onClick = { viewModel.run(job.id, "hermes-local-planner", null) },
                                    enabled = !state.busy,
                                ) { Text("Plan") }
                                OutlinedButton(
                                    onClick = { viewModel.run(job.id, "codex-execute", phrase) },
                                    enabled = !state.busy,
                                ) { Text("Codex") }
                                OutlinedButton(
                                    onClick = { viewModel.run(job.id, "claude-execute", phrase) },
                                    enabled = !state.busy,
                                ) { Text("Claude") }
                            }
                        }
                    }
                }
            }
        }
    }
}
