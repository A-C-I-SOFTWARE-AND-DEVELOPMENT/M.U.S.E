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
import androidx.compose.material3.Switch
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
import com.aci.hermes.data.preferences.PreferredBuilder
import com.aci.hermes.data.preferences.PreferredReviewer
import com.aci.hermes.data.preferences.ThemeMode

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(
    viewModel: SettingsViewModel,
    onBack: () -> Unit,
    onOpenDiagnostics: () -> Unit,
    onOpenAvatarPicker: () -> Unit,
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
                },
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp)
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {

            SettingsSection(stringResource(R.string.settings_section_orchestrator)) {
                Text(
                    stringResource(R.string.settings_preferred_builder_label),
                    style = MaterialTheme.typography.titleSmall,
                )
                RadioRow("Codex", state.preferredBuilder == PreferredBuilder.CODEX) {
                    viewModel.setPreferredBuilder(PreferredBuilder.CODEX)
                }
                RadioRow("ChatGPT", state.preferredBuilder == PreferredBuilder.CHATGPT) {
                    viewModel.setPreferredBuilder(PreferredBuilder.CHATGPT)
                }
                RadioRow("Manual", state.preferredBuilder == PreferredBuilder.MANUAL) {
                    viewModel.setPreferredBuilder(PreferredBuilder.MANUAL)
                }

                HorizontalDivider()

                Text(
                    stringResource(R.string.settings_preferred_reviewer_label),
                    style = MaterialTheme.typography.titleSmall,
                )
                RadioRow("Claude Code", state.preferredReviewer == PreferredReviewer.CLAUDE_CODE) {
                    viewModel.setPreferredReviewer(PreferredReviewer.CLAUDE_CODE)
                }
                RadioRow("Claude", state.preferredReviewer == PreferredReviewer.CLAUDE) {
                    viewModel.setPreferredReviewer(PreferredReviewer.CLAUDE)
                }
                RadioRow("ChatGPT", state.preferredReviewer == PreferredReviewer.CHATGPT) {
                    viewModel.setPreferredReviewer(PreferredReviewer.CHATGPT)
                }
                RadioRow("Manual", state.preferredReviewer == PreferredReviewer.MANUAL) {
                    viewModel.setPreferredReviewer(PreferredReviewer.MANUAL)
                }

                HorizontalDivider()

                SwitchRow(
                    title = stringResource(R.string.settings_use_api_keys_label),
                    subtitle = stringResource(R.string.settings_use_api_keys_subtitle),
                    checked = state.useApiKeys,
                    onChange = viewModel::setUseApiKeys,
                )
                SwitchRow(
                    title = stringResource(R.string.settings_local_only_mode_label),
                    subtitle = stringResource(R.string.settings_local_only_mode_subtitle),
                    checked = state.localOnlyMode,
                    onChange = viewModel::setLocalOnlyMode,
                )
                SwitchRow(
                    title = stringResource(R.string.settings_allow_external_label),
                    subtitle = stringResource(R.string.settings_allow_external_subtitle),
                    checked = state.allowExternalAppOpening,
                    onChange = viewModel::setAllowExternalAppOpening,
                )
                SwitchRow(
                    title = stringResource(R.string.settings_clipboard_label),
                    subtitle = stringResource(R.string.settings_clipboard_subtitle),
                    checked = state.clipboardHandoffEnabled,
                    onChange = viewModel::setClipboardHandoffEnabled,
                )
                SwitchRow(
                    title = stringResource(R.string.settings_safety_warnings_label),
                    subtitle = stringResource(R.string.settings_safety_warnings_subtitle),
                    checked = state.showSafetyWarnings,
                    onChange = viewModel::setShowSafetyWarnings,
                )
            }

            SettingsSection("Personalization") {
                SettingsRow(
                    title = "Jarvis avatar",
                    subtitle = "Choose a built-in avatar or create a private pixel avatar from a photo.",
                )
                OutlinedButton(onClick = onOpenAvatarPicker, modifier = Modifier.fillMaxWidth()) {
                    Text("Open avatar picker")
                }
            }

            SettingsSection(stringResource(R.string.settings_section_appearance)) {
                RadioRow("System", state.themeMode == ThemeMode.SYSTEM) {
                    viewModel.setThemeMode(ThemeMode.SYSTEM)
                }
                RadioRow("Light", state.themeMode == ThemeMode.LIGHT) {
                    viewModel.setThemeMode(ThemeMode.LIGHT)
                }
                RadioRow("Dark", state.themeMode == ThemeMode.DARK) {
                    viewModel.setThemeMode(ThemeMode.DARK)
                }
            }

            SettingsSection(stringResource(R.string.settings_section_about)) {
                SettingsRow(
                    title = stringResource(R.string.diagnostics_app_version),
                    subtitle = "${BuildConfig.VERSION_NAME} (${BuildConfig.VERSION_CODE})",
                )
                SettingsRow(
                    title = stringResource(R.string.diagnostics_build_type),
                    subtitle = BuildConfig.BUILD_TYPE,
                )
                OutlinedButton(onClick = onOpenDiagnostics, modifier = Modifier.fillMaxWidth()) {
                    Text(stringResource(R.string.nav_diagnostics))
                }
                OutlinedButton(
                    onClick = { confirmReset = true },
                    modifier = Modifier.fillMaxWidth(),
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
            },
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
private fun RadioRow(label: String, selected: Boolean, onSelect: () -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 2.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        RadioButton(selected = selected, onClick = onSelect)
        Text(label, style = MaterialTheme.typography.bodyLarge)
    }
}

@Composable
private fun SwitchRow(
    title: String,
    subtitle: String,
    checked: Boolean,
    onChange: (Boolean) -> Unit,
) {
    Row(
        modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(modifier = Modifier.weight(1f)) {
            Text(title, style = MaterialTheme.typography.titleMedium)
            Text(subtitle, style = MaterialTheme.typography.bodySmall)
        }
        Switch(checked = checked, onCheckedChange = onChange)
    }
}
