package com.aci.hermes.ui.screens.provider

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import com.aci.hermes.R
import com.aci.hermes.data.model.ConnectionState
import com.aci.hermes.data.model.Providers

@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Composable
fun ProviderScreen(
    viewModel: ProviderViewModel,
    onSaved: () -> Unit
) {
    val state by viewModel.state.collectAsState()

    Scaffold(
        topBar = { TopAppBar(title = { Text(stringResource(R.string.provider_title)) }) }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 16.dp, vertical = 12.dp)
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {

            // Mock toggle
            Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(16.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column(modifier = Modifier.weight(1f)) {
                        Text(
                            text = stringResource(R.string.provider_mock_toggle),
                            style = MaterialTheme.typography.titleMedium
                        )
                        Text(
                            text = "Lets you explore the UI without a running gateway.",
                            style = MaterialTheme.typography.bodyMedium
                        )
                    }
                    Switch(checked = state.mockMode, onCheckedChange = viewModel::setMockMode)
                }
            }

            // Gateway
            OutlinedTextField(
                value = state.gatewayUrl,
                onValueChange = viewModel::setGatewayUrl,
                label = { Text(stringResource(R.string.provider_gateway_label)) },
                placeholder = { Text(stringResource(R.string.provider_gateway_hint)) },
                singleLine = true,
                enabled = !state.mockMode,
                modifier = Modifier.fillMaxWidth()
            )
            OutlinedTextField(
                value = state.gatewayToken,
                onValueChange = viewModel::setGatewayToken,
                label = { Text(stringResource(R.string.provider_token_label)) },
                placeholder = { Text(stringResource(R.string.provider_token_hint)) },
                singleLine = true,
                enabled = !state.mockMode,
                visualTransformation = PasswordVisualTransformation(),
                modifier = Modifier.fillMaxWidth()
            )

            // Provider picker
            Text(
                text = stringResource(R.string.provider_provider_label),
                style = MaterialTheme.typography.titleMedium
            )
            FlowRow(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalArrangement = Arrangement.spacedBy(4.dp),
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(vertical = 4.dp)
            ) {
                Providers.all.forEach { p ->
                    AssistChip(
                        onClick = { viewModel.setProviderId(p.id) },
                        label = { Text(p.displayName.substringBefore(" ")) },
                        enabled = !state.mockMode
                    )
                }
            }
            Text(
                text = Providers.byId(state.providerId).notes,
                style = MaterialTheme.typography.bodyMedium
            )
            OutlinedTextField(
                value = state.providerApiKey,
                onValueChange = viewModel::setProviderApiKey,
                label = { Text(stringResource(R.string.provider_api_key_label)) },
                placeholder = { Text(stringResource(R.string.provider_api_key_hint)) },
                singleLine = true,
                enabled = !state.mockMode,
                visualTransformation = PasswordVisualTransformation(),
                modifier = Modifier.fillMaxWidth()
            )

            // Test connection
            Spacer(modifier = Modifier.height(4.dp))
            TextButton(onClick = viewModel::testConnection, modifier = Modifier.fillMaxWidth()) {
                Text(stringResource(R.string.provider_test_connection))
            }
            when (val t = state.test) {
                is ConnectionState.Connecting ->
                    Text("Connecting…", style = MaterialTheme.typography.bodyMedium)
                is ConnectionState.Connected -> {
                    val s = t.status
                    Text(
                        "✓ Reachable" + (s.version?.let { " — gateway $it" } ?: ""),
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.primary
                    )
                }
                is ConnectionState.Failed -> Text(
                    "✗ ${t.reason}",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.error
                )
                ConnectionState.Unknown -> Unit
            }

            Spacer(modifier = Modifier.height(8.dp))
            Button(
                onClick = { viewModel.save(onSaved) },
                enabled = !state.saving,
                modifier = Modifier.fillMaxWidth()
            ) {
                Text(stringResource(R.string.provider_save))
            }
            Spacer(modifier = Modifier.height(24.dp))
        }
    }
}
