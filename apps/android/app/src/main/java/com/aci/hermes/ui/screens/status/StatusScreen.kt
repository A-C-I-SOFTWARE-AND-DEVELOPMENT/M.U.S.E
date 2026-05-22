package com.aci.hermes.ui.screens.status

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Refresh
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
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.aci.hermes.R
import com.aci.hermes.data.model.ConnectionState

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun StatusScreen(viewModel: StatusViewModel, onBack: () -> Unit) {
    val state by viewModel.state.collectAsState()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.status_title)) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = null)
                    }
                },
                actions = {
                    IconButton(onClick = viewModel::refresh) {
                        Icon(Icons.Default.Refresh, contentDescription = "Refresh")
                    }
                }
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            StatusCard(state = state)
            DetailsCard(state = state)
        }
    }
}

@Composable
private fun StatusCard(state: StatusUiState) {
    val (label, color) = when (val c = state.connection) {
        is ConnectionState.Connected -> stringResource(R.string.status_connected) to MaterialTheme.colorScheme.primary
        is ConnectionState.Failed -> "${stringResource(R.string.status_disconnected)} — ${c.reason}" to MaterialTheme.colorScheme.error
        ConnectionState.Connecting -> "Checking…" to MaterialTheme.colorScheme.onSurface
        ConnectionState.Unknown -> stringResource(R.string.status_unknown) to MaterialTheme.colorScheme.onSurface
    }
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(16.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Surface(
                color = color,
                shape = CircleShape,
                modifier = Modifier.size(14.dp)
            ) {}
            Column {
                Text(stringResource(R.string.status_gateway), style = MaterialTheme.typography.titleMedium)
                Text(label, color = color, style = MaterialTheme.typography.bodyMedium)
            }
        }
    }
}

@Composable
private fun DetailsCard(state: StatusUiState) {
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Detail(stringResource(R.string.diagnostics_gateway_url), state.gatewayUrl.ifBlank { "(not set)" })
            HorizontalDivider()
            Detail(stringResource(R.string.status_provider), state.providerId.ifBlank { "(unset)" })
            HorizontalDivider()
            Detail(
                stringResource(R.string.status_mock_label),
                if (state.mockMode) stringResource(R.string.status_mock_on)
                else stringResource(R.string.status_mock_off)
            )
            val c = state.connection
            if (c is ConnectionState.Connected) {
                HorizontalDivider()
                c.status.version?.let { Detail("Gateway version", it) }
                c.status.model?.let { Detail("Model", it) }
                c.status.message?.let { Detail("Message", it) }
            }
        }
    }
}

@Composable
private fun Detail(label: String, value: String) {
    Column(modifier = Modifier.fillMaxWidth()) {
        Text(label, style = MaterialTheme.typography.titleMedium)
        Text(value, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurface)
    }
}
