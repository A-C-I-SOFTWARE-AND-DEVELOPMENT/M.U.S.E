package com.aci.hermes.ui.screens.provider

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import com.aci.hermes.R
import com.aci.hermes.data.model.ConnectionState
import com.aci.hermes.data.preferences.ConnectionMode
import com.aci.hermes.util.GatewayUrl

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

            // ───────── Mode selector ─────────
            Text(
                stringResource(R.string.provider_mode_heading),
                style = MaterialTheme.typography.titleMedium
            )
            ModeSelector(state.mode, viewModel::setMode)
            ModeHelpText(state.mode)

            // ───────── Mode-specific fields ─────────
            AnimatedVisibility(visible = state.mode == ConnectionMode.DIRECT) {
                Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    DirectProviderPicker(state, viewModel)
                    if (state.providerId == "custom") {
                        OutlinedTextField(
                            value = state.gatewayUrl,
                            onValueChange = viewModel::setGatewayUrl,
                            label = { Text(stringResource(R.string.provider_custom_base_url_label)) },
                            placeholder = { Text("https://example.com/v1") },
                            singleLine = true,
                            modifier = Modifier.fillMaxWidth()
                        )
                    }
                    OutlinedTextField(
                        value = state.providerApiKey,
                        onValueChange = viewModel::setProviderApiKey,
                        label = { Text(stringResource(R.string.provider_api_key_label)) },
                        placeholder = { Text(stringResource(R.string.provider_api_key_hint)) },
                        singleLine = true,
                        visualTransformation = PasswordVisualTransformation(),
                        modifier = Modifier.fillMaxWidth()
                    )
                    ModelInput(state, viewModel)
                    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)) {
                        Text(
                            text = stringResource(R.string.provider_direct_security_note),
                            style = MaterialTheme.typography.bodyMedium,
                            modifier = Modifier.padding(12.dp)
                        )
                    }
                }
            }

            AnimatedVisibility(visible = state.mode == ConnectionMode.HERMES) {
                Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    OutlinedTextField(
                        value = state.gatewayUrl,
                        onValueChange = viewModel::setGatewayUrl,
                        label = { Text(stringResource(R.string.provider_gateway_label)) },
                        placeholder = { Text(stringResource(R.string.provider_gateway_hint)) },
                        singleLine = true,
                        isError = state.gatewayUrlWarning != null,
                        modifier = Modifier.fillMaxWidth()
                    )
                    state.gatewayUrlWarning?.let { warning ->
                        Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.errorContainer)) {
                            Text(
                                text = warning,
                                style = MaterialTheme.typography.bodyMedium,
                                color = MaterialTheme.colorScheme.onErrorContainer,
                                modifier = Modifier.padding(12.dp)
                            )
                        }
                    }
                    OutlinedTextField(
                        value = state.gatewayToken,
                        onValueChange = viewModel::setGatewayToken,
                        label = { Text(stringResource(R.string.provider_token_label)) },
                        placeholder = { Text(stringResource(R.string.provider_token_hint)) },
                        singleLine = true,
                        visualTransformation = PasswordVisualTransformation(),
                        modifier = Modifier.fillMaxWidth()
                    )
                    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)) {
                        Text(
                            text = stringResource(R.string.provider_gateway_setup_note),
                            style = MaterialTheme.typography.bodySmall,
                            modifier = Modifier.padding(12.dp)
                        )
                    }
                }
            }

            // ───────── Test + save ─────────
            Spacer(modifier = Modifier.height(4.dp))
            TextButton(onClick = viewModel::testConnection, modifier = Modifier.fillMaxWidth()) {
                Text(
                    when (state.mode) {
                        ConnectionMode.DIRECT -> stringResource(R.string.provider_test_direct_api)
                        else -> stringResource(R.string.provider_test_connection)
                    }
                )
            }
            TestResult(state.test)

            state.validationError?.let {
                Text(
                    text = it,
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.error
                )
            }

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

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ModeSelector(current: ConnectionMode, onSelect: (ConnectionMode) -> Unit) {
    val modes = ConnectionMode.entries
    SingleChoiceSegmentedButtonRow(modifier = Modifier.fillMaxWidth()) {
        modes.forEachIndexed { index, mode ->
            SegmentedButton(
                selected = mode == current,
                onClick = { onSelect(mode) },
                shape = SegmentedButtonDefaults.itemShape(index = index, count = modes.size),
                label = {
                    Text(
                        when (mode) {
                            ConnectionMode.MOCK -> stringResource(R.string.mode_mock_short)
                            ConnectionMode.DIRECT -> stringResource(R.string.mode_direct_short)
                            ConnectionMode.HERMES -> stringResource(R.string.mode_hermes_short)
                        }
                    )
                }
            )
        }
    }
}

@Composable
private fun ModeHelpText(mode: ConnectionMode) {
    val text = when (mode) {
        ConnectionMode.MOCK -> stringResource(R.string.mode_mock_description)
        ConnectionMode.DIRECT -> stringResource(R.string.mode_direct_description)
        ConnectionMode.HERMES -> stringResource(R.string.mode_hermes_description)
    }
    Text(text, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurface)
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun DirectProviderPicker(state: ProviderUiState, viewModel: ProviderViewModel) {
    Text(
        stringResource(R.string.provider_provider_label),
        style = MaterialTheme.typography.titleMedium
    )
    FlowRow(
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        verticalArrangement = Arrangement.spacedBy(4.dp),
        modifier = Modifier.fillMaxWidth()
    ) {
        DirectProvider.entries.forEach { p ->
            FilterChip(
                selected = state.providerId == p.id,
                onClick = { viewModel.setProviderId(p.id) },
                label = { Text(p.shortLabel) }
            )
        }
    }
    Text(
        text = DirectProvider.byId(state.providerId).description,
        style = MaterialTheme.typography.bodyMedium
    )
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun ModelInput(state: ProviderUiState, viewModel: ProviderViewModel) {
    OutlinedTextField(
        value = state.model,
        onValueChange = viewModel::setModel,
        label = { Text(stringResource(R.string.provider_model_label)) },
        placeholder = { Text("openai/gpt-4o-mini") },
        singleLine = true,
        modifier = Modifier.fillMaxWidth()
    )
    val suggestions = SuggestedModels.forProvider(state.providerId)
    if (suggestions.isNotEmpty()) {
        FlowRow(
            horizontalArrangement = Arrangement.spacedBy(6.dp),
            verticalArrangement = Arrangement.spacedBy(4.dp),
            modifier = Modifier.fillMaxWidth()
        ) {
            suggestions.forEach { m ->
                FilterChip(
                    selected = state.model == m,
                    onClick = { viewModel.setModel(m) },
                    label = { Text(m) }
                )
            }
        }
    }
}

@Composable
private fun TestResult(test: ConnectionState) {
    when (test) {
        ConnectionState.Connecting ->
            Text(stringResource(R.string.status_connecting), style = MaterialTheme.typography.bodyMedium)
        is ConnectionState.Connected -> {
            val s = test.status
            Text(
                buildString {
                    append("✓ ")
                    append(s.message ?: "Reachable")
                    s.model?.let { append(" — model: $it") }
                },
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.primary
            )
        }
        is ConnectionState.Failed -> {
            val headline = when (test.kind) {
                GatewayUrl.FailureKind.UNREACHABLE -> stringResource(R.string.status_backend_unreachable)
                GatewayUrl.FailureKind.WRONG_URL -> stringResource(R.string.status_wrong_url)
                GatewayUrl.FailureKind.TLS -> stringResource(R.string.status_tls_error)
                GatewayUrl.FailureKind.HTTP -> stringResource(R.string.status_http_error)
                GatewayUrl.FailureKind.UNKNOWN -> stringResource(R.string.status_disconnected)
            }
            Column {
                Text(
                    "✗ $headline",
                    style = MaterialTheme.typography.titleMedium,
                    color = MaterialTheme.colorScheme.error
                )
                Text(
                    test.reason,
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.error
                )
            }
        }
        ConnectionState.Unknown -> Unit
    }
}

/** Providers exposed in Direct mode. Order = chip order in the picker. */
private enum class DirectProvider(
    val id: String,
    val shortLabel: String,
    val description: String
) {
    OPENROUTER(
        "openrouter",
        "OpenRouter",
        "OpenRouter (200+ models behind one key). Recommended — model ids look like \"openai/gpt-4o-mini\"."
    ),
    OPENAI(
        "openai",
        "OpenAI",
        "OpenAI direct. Use model ids like \"gpt-4o-mini\" (no provider prefix)."
    ),
    CUSTOM(
        "custom",
        "Custom",
        "Any OpenAI-compatible endpoint. Enter the base URL below (no trailing slash)."
    );

    companion object {
        fun byId(id: String): DirectProvider = entries.firstOrNull { it.id == id } ?: OPENROUTER
    }
}

private object SuggestedModels {
    fun forProvider(providerId: String): List<String> = when (providerId) {
        "openrouter" -> listOf(
            "openai/gpt-4o-mini",
            "anthropic/claude-3.5-haiku",
            "google/gemini-flash-1.5",
            "meta-llama/llama-3.1-70b-instruct"
        )
        "openai" -> listOf("gpt-4o-mini", "gpt-4o", "gpt-4.1-mini")
        else -> emptyList()
    }
}
