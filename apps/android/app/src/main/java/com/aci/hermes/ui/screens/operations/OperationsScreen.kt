package com.aci.hermes.ui.screens.operations

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
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
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.aci.hermes.R
import com.aci.hermes.events.JarvisEvent
import com.aci.hermes.gateway.GatewayState
import com.aci.hermes.ui.theme.JarvisCyan
import com.aci.hermes.ui.theme.JarvisGold
import com.aci.hermes.ui.theme.JarvisGreen
import com.aci.hermes.ui.theme.JarvisRed
import com.aci.hermes.workers.WorkerLane

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun OperationsScreen(
    viewModel: OperationsViewModel,
    onBack: () -> Unit,
) {
    val state by viewModel.state.collectAsState()
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.operations_title)) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = stringResource(R.string.action_back))
                    }
                },
                actions = {
                    IconButton(onClick = viewModel::refresh) {
                        Icon(Icons.Default.Refresh, contentDescription = null)
                    }
                },
            )
        },
    ) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
            contentPadding = PaddingValues(vertical = 12.dp),
        ) {
            item { GatewayCard(state.gateway) }
            item { Header(stringResource(R.string.operations_workers_section)) }
            if (state.lanes.isEmpty()) {
                item {
                    Text(
                        stringResource(R.string.operations_no_workers),
                        style = MaterialTheme.typography.bodyMedium,
                    )
                }
            } else {
                items(state.lanes, key = { it.id }) { WorkerCard(it) }
            }
            item { Header(stringResource(R.string.operations_events_section)) }
            if (state.recent.isEmpty()) {
                item {
                    Text(
                        "No events yet.",
                        style = MaterialTheme.typography.bodyMedium,
                    )
                }
            } else {
                items(state.recent, key = { it.id }) { EventRow(it) }
            }
        }
    }
}

@Composable
private fun Header(text: String) {
    Text(
        text = text,
        style = MaterialTheme.typography.titleSmall,
        color = MaterialTheme.colorScheme.primary,
        modifier = Modifier.padding(top = 8.dp),
    )
}

@Composable
private fun GatewayCard(gateway: GatewayState) {
    val (label, color) = when (gateway.connectivity) {
        GatewayState.Connectivity.ONLINE -> "Online" to JarvisGreen
        GatewayState.Connectivity.CONNECTING -> "Connecting…" to JarvisCyan
        GatewayState.Connectivity.DEGRADED -> "Degraded" to JarvisGold
        GatewayState.Connectivity.FAILED -> "Failed" to JarvisRed
        GatewayState.Connectivity.OFFLINE -> "Offline" to MaterialTheme.colorScheme.outline
    }
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Box(modifier = Modifier.size(12.dp).background(color, CircleShape))
                Text(text = stringResource(R.string.operations_gateway_section), style = MaterialTheme.typography.titleMedium)
                Text(text = label, style = MaterialTheme.typography.bodyMedium, color = color)
            }
            gateway.version?.let { Text("Version: $it", style = MaterialTheme.typography.bodySmall) }
            gateway.mode?.let { Text("Mode: $it", style = MaterialTheme.typography.bodySmall) }
            Text(
                "Queue: ${gateway.queue.running} running, ${gateway.queue.queued} queued, " +
                    "${gateway.queue.waitingApproval} waiting on approval",
                style = MaterialTheme.typography.bodySmall,
            )
            gateway.lastError?.let {
                Text(
                    text = it,
                    style = MaterialTheme.typography.bodySmall,
                    color = JarvisRed,
                )
            }
        }
    }
}

@Composable
private fun WorkerCard(lane: WorkerLane) {
    val dot: Color = when (lane.health) {
        WorkerLane.Health.WORKING -> JarvisCyan
        WorkerLane.Health.QUEUED -> JarvisGold
        WorkerLane.Health.IDLE -> JarvisGreen
        WorkerLane.Health.OFFLINE -> MaterialTheme.colorScheme.outline
    }
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)) {
        Row(
            modifier = Modifier.padding(16.dp).fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Box(modifier = Modifier.size(12.dp).background(dot, CircleShape))
            Column(modifier = Modifier.weight(1f)) {
                Text(lane.displayName, style = MaterialTheme.typography.titleMedium)
                Text(
                    "${lane.kind}${lane.version?.let { " · $it" } ?: ""}",
                    style = MaterialTheme.typography.bodySmall,
                )
                lane.notes?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
            }
            Text(
                text = lane.health.name.lowercase(),
                style = MaterialTheme.typography.labelMedium,
                color = dot,
            )
        }
    }
}

@Composable
private fun EventRow(event: JarvisEvent) {
    val color: Color = when (event.severity) {
        JarvisEvent.Severity.CRITICAL -> JarvisRed
        JarvisEvent.Severity.WARN -> JarvisGold
        JarvisEvent.Severity.NOTICE -> JarvisCyan
        else -> MaterialTheme.colorScheme.onSurfaceVariant
    }
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)) {
        Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(event.source.name.lowercase(), style = MaterialTheme.typography.labelSmall, color = color)
                Text(event.severity.name.lowercase(), style = MaterialTheme.typography.labelSmall, color = color)
            }
            Text(event.message, style = MaterialTheme.typography.bodySmall)
        }
    }
}
