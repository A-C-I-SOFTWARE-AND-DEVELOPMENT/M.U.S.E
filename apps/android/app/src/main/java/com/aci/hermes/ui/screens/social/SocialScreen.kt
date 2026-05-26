package com.aci.hermes.ui.screens.social

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
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
import com.aci.hermes.data.model.SocialPattern
import com.aci.hermes.data.model.SocialPatternKind

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SocialScreen(viewModel: SocialViewModel, onBack: () -> Unit) {
    val state by viewModel.state.collectAsState()
    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text(stringResource(R.string.social_title))
                        Text(
                            stringResource(R.string.social_subtitle),
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
        if (state.patterns.isEmpty()) {
            Column(
                modifier = Modifier.fillMaxSize().padding(padding),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.Center,
            ) { Text(stringResource(R.string.social_empty), style = MaterialTheme.typography.bodyMedium) }
        } else {
            LazyColumn(
                modifier = Modifier.fillMaxSize().padding(padding),
                contentPadding = PaddingValues(16.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                items(state.patterns) { pattern ->
                    PatternRow(
                        pattern = pattern,
                        onAcknowledge = { viewModel.acknowledge(pattern) },
                        onDismiss = { viewModel.dismiss(pattern) },
                    )
                }
            }
        }
    }
}

@Composable
private fun PatternRow(pattern: SocialPattern, onAcknowledge: () -> Unit, onDismiss: () -> Unit) {
    Card(
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
        shape = RoundedCornerShape(14.dp),
    ) {
        Column(modifier = Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            AssistChip(
                onClick = {},
                label = { Text(kindLabel(pattern.kind), style = MaterialTheme.typography.labelSmall) },
            )
            Text(pattern.title, style = MaterialTheme.typography.titleSmall)
            Text(pattern.observation, style = MaterialTheme.typography.bodySmall)
            Text(stringResource(R.string.social_signal_strength), style = MaterialTheme.typography.labelSmall)
            LinearProgressIndicator(
                progress = { pattern.signalStrength.coerceIn(0f, 1f) },
                modifier = Modifier.fillMaxWidth(),
            )
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                OutlinedButton(onClick = onAcknowledge) { Text(stringResource(R.string.social_acknowledge)) }
                OutlinedButton(onClick = onDismiss) { Text(stringResource(R.string.social_dismiss)) }
            }
        }
    }
}

private fun kindLabel(kind: SocialPatternKind): String = when (kind) {
    SocialPatternKind.COMMUNICATION_STYLE -> "Communication style"
    SocialPatternKind.SCHEDULE -> "Schedule"
    SocialPatternKind.TONE -> "Tone"
    SocialPatternKind.RELATIONSHIP -> "Relationship"
    SocialPatternKind.REPEATING_THEME -> "Repeating theme"
}
