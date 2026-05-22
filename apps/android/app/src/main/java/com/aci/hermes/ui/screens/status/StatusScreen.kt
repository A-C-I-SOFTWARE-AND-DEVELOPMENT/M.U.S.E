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
import com.aci.hermes.util.GatewayUrl

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
    val connection = state.connection
    val headline: String
    val detail: String?
    val color: Color
    when (connection) {
        is ConnectionState.Connected -> {
            headline = stringResource(R.string.status_connected)
            detail = null
            color = MaterialTheme.colorScheme.primary
        }
        is ConnectionState.Failed -> {
            headline = when (connection.kind) {
                GatewayUrl.FailureKind.UNREACHABLE -> stringResource(R.string.status_backend_unreachable)
                GatewayUrl.FailureKind.WRONG_URL -> stringResource(R.string.status_wrong_url)
                GatewayUrl.FailureKind.TLS -> stringResource(R.string.status_tls_error)
                GatewayUrl.FailureKind.HTTP -> stringResource(R.string.status_http_error)
                GatewayUrl.FailureKind.UNKNOWN -> stringResource(R.string.status_disconnected)
            }
            detail = connection.reason
            color = MaterialTheme.colorScheme.error
        }
        ConnectionState.Connecting -> {
            headline = stringResource(R.string.status_connecting)
            detail = null
            color = MaterialTheme.colorScheme.onSurface
        }
        ConnectionState.Unknown -> {
            headline = stringResource(R.string.status_unknown)
            detail = null
            color = MaterialTheme.colorScheme.onSurface
        }
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
                Text(headline, color = color, style = MaterialTheme.typography.bodyMedium)
                if (detail != null) {
                    Text(
                        text = detail,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurface
                    )
                }
            }
        }
    }
}

@Composable
private fun DetailsCard(state: StatusUiState) {
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            val modeLabel = when (state.mode) {
                com.aci.hermes.data.preferences.ConnectionMode.MOCK -> stringResource(R.string.mode_mock_short)
                com.aci.hermes.data.preferences.ConnectionMode.DIRECT -> stringResource(R.string.mode_direct_short)
                com.aci.hermes.data.preferences.ConnectionMode.HERMES -> stringResource(R.string.mode_hermes_short)
            }
            Detail(stringResource(R.string.status_mode_label), modeLabel)
            HorizontalDivider()
            Detail(stringResource(R.string.status_provider), state.providerId.ifBlank { "(unset)" })
            HorizontalDivider()
            Detail(stringResource(R.string.status_model), state.model.ifBlank { "(unset)" })
            HorizontalDivider()
            Detail(stringResource(R.string.diagnostics_gateway_url), state.gatewayUrl.ifBlank { "(not set)" })
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
