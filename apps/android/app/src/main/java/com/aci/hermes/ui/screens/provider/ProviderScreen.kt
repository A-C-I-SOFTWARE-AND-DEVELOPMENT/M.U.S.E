package com.aci.hermes.ui.screens.provider

import androidx.compose.animation.AnimatedVisibility
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
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Clear
import androidx.compose.material.icons.filled.Visibility
import androidx.compose.material.icons.filled.VisibilityOff
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
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
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import com.aci.hermes.R
import com.aci.hermes.data.model.ConnectionState
import com.aci.hermes.data.preferences.ConnectionMode

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
                            value = state.customApiBaseUrl,
                            onValueChange = viewModel::setCustomApiBaseUrl,
                            label = { Text(stringResource(R.string.provider_custom_base_url_label)) },
                            placeholder = { Text("https://example.com/v1") },
                            singleLine = true,
                            modifier = Modifier.fillMaxWidth()
                        )
                    }
                    ApiKeyField(state, viewModel)
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
                        modifier = Modifier.fillMaxWidth()
                    )
                    OutlinedTextField(
                        value = state.gatewayToken,
                        onValueChange = viewModel::setGatewayToken,
                        label = { Text(stringResource(R.string.provider_token_label)) },
                        placeholder = { Text(stringResource(R.string.provider_token_hint)) },
                        singleLine = true,
                        visualTransformation = PasswordVisualTransformation(),
                        modifier = Modifier.fillMaxWidth()
                    )
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

@Composable
private fun ApiKeyField(state: ProviderUiState, viewModel: ProviderViewModel) {
    OutlinedTextField(
        value = state.providerApiKey,
        onValueChange = viewModel::setProviderApiKey,
        label = { Text(stringResource(R.string.provider_api_key_label)) },
        placeholder = { Text(stringResource(R.string.provider_api_key_hint)) },
        singleLine = true,
        visualTransformation = if (state.apiKeyVisible) {
            VisualTransformation.None
        } else {
            PasswordVisualTransformation()
        },
        trailingIcon = {
            Row(verticalAlignment = Alignment.CenterVertically) {
                IconButton(onClick = viewModel::toggleApiKeyVisible) {
                    Icon(
                        imageVector = if (state.apiKeyVisible) {
                            Icons.Filled.VisibilityOff
                        } else {
                            Icons.Filled.Visibility
                        },
                        contentDescription = stringResource(
                            if (state.apiKeyVisible) R.string.provider_api_key_hide
                            else R.string.provider_api_key_reveal
                        )
                    )
                }
                if (state.providerApiKey.isNotEmpty()) {
                    IconButton(onClick = viewModel::clearApiKey) {
                        Icon(
                            imageVector = Icons.Filled.Clear,
                            contentDescription = stringResource(R.string.provider_api_key_clear)
                        )
                    }
                }
            }
        },
        modifier = Modifier.fillMaxWidth()
    )
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun ModelInput(state: ProviderUiState, viewModel: ProviderViewModel) {
    Text(
        stringResource(R.string.provider_model_label),
        style = MaterialTheme.typography.titleMedium
    )
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
        Text(
            stringResource(
                R.string.provider_recommended_models_label,
                DirectProvider.byId(state.providerId).shortLabel
            ),
            style = MaterialTheme.typography.bodyMedium
        )
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
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        TextButton(onClick = viewModel::resetToRecommendedModel) {
            Text(stringResource(R.string.provider_reset_recommended_model))
        }
        if (!state.lastWorkingModel.isNullOrBlank() && state.lastWorkingModel != state.model) {
            TextButton(onClick = viewModel::useLastWorkingModel) {
                Text(
                    stringResource(
                        R.string.provider_use_last_working_model,
                        state.lastWorkingModel
                    )
                )
            }
        }
    }
    if (!state.lastWorkingModel.isNullOrBlank()) {
        Text(
            text = stringResource(R.string.provider_last_working_model, state.lastWorkingModel),
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurface
        )
    }
}

@Composable
private fun TestResult(test: ConnectionState) {
    when (test) {
        ConnectionState.Connecting ->
            Text(stringResource(R.string.provider_testing), style = MaterialTheme.typography.bodyMedium)
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
        is ConnectionState.Failed -> Text(
            "✗ ${test.reason}",
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.error
        )
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
