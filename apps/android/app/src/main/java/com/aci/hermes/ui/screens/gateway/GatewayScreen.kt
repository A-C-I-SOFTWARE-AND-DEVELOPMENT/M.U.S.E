package com.aci.hermes.ui.screens.gateway

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
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.DeleteSweep
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
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
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.aci.hermes.R
import com.aci.hermes.data.model.GatewayConnectionState
import com.aci.hermes.data.model.GatewayEvent
import com.aci.hermes.data.model.GatewayMode
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun GatewayScreen(viewModel: GatewayViewModel, onBack: () -> Unit) {
    val state by viewModel.state.collectAsState()
    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text(stringResource(R.string.gateway_title))
                        Text(
                            stringResource(R.string.gateway_subtitle),
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
                actions = {
                    IconButton(onClick = viewModel::clearEvents) {
                        Icon(Icons.Default.DeleteSweep, contentDescription = stringResource(R.string.gateway_clear))
                    }
                },
            )
        },
    ) { padding ->
        Column(modifier = Modifier.fillMaxSize().padding(padding)) {
            ModeAndStatus(state = state, onSelectMode = viewModel::setMode)
            HorizontalDivider()
            if (state.events.isEmpty()) {
                Column(
                    modifier = Modifier.fillMaxSize(),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.Center,
                ) { Text(stringResource(R.string.gateway_empty), style = MaterialTheme.typography.bodyMedium) }
            } else {
                LazyColumn(
                    contentPadding = PaddingValues(horizontal = 16.dp, vertical = 12.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    items(state.events) { event -> EventRow(event) }
                }
            }
        }
    }
}

@Composable
private fun ModeAndStatus(state: GatewayUiState, onSelectMode: (GatewayMode) -> Unit) {
    Column(
        modifier = Modifier.fillMaxWidth().padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(6.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Surface(
                color = connectionColor(state.connection),
                shape = CircleShape,
                modifier = Modifier.size(12.dp),
            ) {}
            Text(
                text = connectionText(state.connection),
                style = MaterialTheme.typography.titleSmall,
                modifier = Modifier.padding(start = 4.dp),
            )
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            FilterChip(
                selected = state.mode == GatewayMode.MOCK,
                onClick = { onSelectMode(GatewayMode.MOCK) },
                label = { Text(stringResource(R.string.gateway_mode_mock)) },
            )
            FilterChip(
                selected = state.mode == GatewayMode.TERMUX,
                onClick = { onSelectMode(GatewayMode.TERMUX) },
                label = { Text(stringResource(R.string.gateway_mode_termux)) },
            )
            FilterChip(
                selected = state.mode == GatewayMode.REMOTE,
                onClick = { onSelectMode(GatewayMode.REMOTE) },
                label = { Text("Remote") },
            )
        }
        if (state.mode == GatewayMode.TERMUX && !state.termuxInstalled) {
            Text(stringResource(R.string.gateway_termux_install_hint), style = MaterialTheme.typography.bodySmall)
        }
    }
}

@Composable
private fun connectionColor(c: GatewayConnectionState) = when (c) {
    GatewayConnectionState.CONNECTED -> MaterialTheme.colorScheme.tertiary
    GatewayConnectionState.CONNECTING -> MaterialTheme.colorScheme.primary
    GatewayConnectionState.ERROR -> MaterialTheme.colorScheme.error
    GatewayConnectionState.DISCONNECTED -> MaterialTheme.colorScheme.onSurfaceVariant
}

@Composable
private fun connectionText(c: GatewayConnectionState): String = when (c) {
    GatewayConnectionState.CONNECTED -> stringResource(R.string.gateway_status_connected)
    GatewayConnectionState.CONNECTING -> "Connecting…"
    GatewayConnectionState.ERROR -> "Error"
    GatewayConnectionState.DISCONNECTED -> stringResource(R.string.gateway_status_disconnected)
}

@Composable
private fun EventRow(event: GatewayEvent) {
    val ts = remember(event.createdAt) {
        SimpleDateFormat("HH:mm:ss", Locale.getDefault()).format(Date(event.createdAt))
    }
    Card(
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
        shape = RoundedCornerShape(10.dp),
    ) {
        Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text(event.kind.name.lowercase().replace('_', ' '), style = MaterialTheme.typography.labelLarge)
                Text(ts, style = MaterialTheme.typography.labelSmall)
            }
            Text(event.message, style = MaterialTheme.typography.bodySmall)
            Text("Source: ${event.source}", style = MaterialTheme.typography.labelSmall)
        }
    }
}
