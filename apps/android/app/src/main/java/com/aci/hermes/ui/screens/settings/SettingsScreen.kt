package com.aci.hermes.ui.screens.settings

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.aci.hermes.BuildConfig
import com.aci.hermes.R
import com.aci.hermes.data.preferences.ThemeMode

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(
    viewModel: SettingsViewModel,
    onBack: () -> Unit,
    onEditConnection: () -> Unit,
    onOpenDiagnostics: () -> Unit
) {
    val state by viewModel.state.collectAsState()
    var confirmReset by remember { mutableStateOf(false) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.settings_title)) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = null)
                    }
                }
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp)
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {

            SettingsSection(stringResource(R.string.settings_section_connection)) {
                val modeLabel = when (state.mode) {
                    com.aci.hermes.data.preferences.ConnectionMode.MOCK -> stringResource(R.string.mode_mock_short)
                    com.aci.hermes.data.preferences.ConnectionMode.DIRECT -> stringResource(R.string.mode_direct_short)
                    com.aci.hermes.data.preferences.ConnectionMode.HERMES -> stringResource(R.string.mode_hermes_short)
                }
                SettingsRow(title = "Connection mode", subtitle = modeLabel)
                if (state.mode != com.aci.hermes.data.preferences.ConnectionMode.MOCK) {
                    SettingsRow(title = "Provider", subtitle = state.providerId)
                    if (state.mode == com.aci.hermes.data.preferences.ConnectionMode.DIRECT) {
                        SettingsRow(title = "Model", subtitle = state.model.ifBlank { "(unset)" })
                    }
                    if (state.gatewayUrl.isNotBlank()) {
                        SettingsRow(
                            title = if (state.mode == com.aci.hermes.data.preferences.ConnectionMode.HERMES)
                                "Gateway URL" else "Base URL",
                            subtitle = state.gatewayUrl
                        )
                    }
                }
                OutlinedButton(onClick = onEditConnection, modifier = Modifier.fillMaxWidth()) {
                    Text("Edit connection")
                }
            }

            SettingsSection(stringResource(R.string.settings_section_appearance)) {
                ThemeChoice("System", state.themeMode == ThemeMode.SYSTEM) {
                    viewModel.setThemeMode(ThemeMode.SYSTEM)
                }
                ThemeChoice("Light", state.themeMode == ThemeMode.LIGHT) {
                    viewModel.setThemeMode(ThemeMode.LIGHT)
                }
                ThemeChoice("Dark", state.themeMode == ThemeMode.DARK) {
                    viewModel.setThemeMode(ThemeMode.DARK)
                }
            }

            SettingsSection(stringResource(R.string.settings_section_about)) {
                SettingsRow(
                    title = stringResource(R.string.diagnostics_app_version),
                    subtitle = "${BuildConfig.VERSION_NAME} (${BuildConfig.VERSION_CODE})"
                )
                SettingsRow(
                    title = stringResource(R.string.diagnostics_build_type),
                    subtitle = BuildConfig.BUILD_TYPE
                )
                OutlinedButton(onClick = onOpenDiagnostics, modifier = Modifier.fillMaxWidth()) {
                    Text(stringResource(R.string.nav_diagnostics))
                }
                OutlinedButton(
                    onClick = { confirmReset = true },
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text(stringResource(R.string.settings_reset))
                }
            }
        }
    }

    if (confirmReset) {
        AlertDialog(
            onDismissRequest = { confirmReset = false },
            title = { Text(stringResource(R.string.settings_reset)) },
            text = { Text(stringResource(R.string.settings_reset_confirm)) },
            confirmButton = {
                TextButton(onClick = {
                    confirmReset = false
                    viewModel.resetAll()
                }) { Text(stringResource(R.string.action_ok)) }
            },
            dismissButton = {
                TextButton(onClick = { confirmReset = false }) {
                    Text(stringResource(R.string.action_cancel))
                }
            }
        )
    }
}

@Composable
private fun SettingsSection(title: String, content: @Composable () -> Unit) {
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(text = title, style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.primary)
            HorizontalDivider()
            content()
        }
    }
}

@Composable
private fun SettingsRow(title: String, subtitle: String) {
    Column(modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp)) {
        Text(title, style = MaterialTheme.typography.titleMedium)
        Text(subtitle, style = MaterialTheme.typography.bodyMedium)
    }
}

@Composable
private fun ThemeChoice(label: String, selected: Boolean, onSelect: () -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 2.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        RadioButton(selected = selected, onClick = onSelect)
        Text(label, style = MaterialTheme.typography.bodyLarge)
    }
}
