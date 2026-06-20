package com.aci.hermes.ui.screens.control

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.PowerSettingsNew
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import com.aci.hermes.R
import com.aci.hermes.ui.designsystem.museButton
import com.aci.hermes.ui.designsystem.museButtonVariant
import com.aci.hermes.ui.designsystem.museCard
import com.aci.hermes.ui.designsystem.museSectionHeader
import com.aci.hermes.ui.designsystem.museStatus
import com.aci.hermes.ui.designsystem.museStatusDot
import com.aci.hermes.ui.screens.orchestrator.OrchestratorViewModel
import com.aci.hermes.ui.theme.JarvisSignal
import com.aci.hermes.ui.theme.JarvisSignalDim
import com.aci.hermes.ui.theme.JarvisTokens

/**
 * Service control surface. Folds the orchestrator start/stop controls from
 * the original Hermes dashboard into a dedicated screen, plus a prominent
 * emergency stop matching the one in the global top bar.
 */
@Composable
fun ControlScreen(
    viewModel: OrchestratorViewModel,
    paddingValues: PaddingValues,
    onEmergencyStop: () -> Unit,
    onOpenDeviceControl: () -> Unit = {},
    controlViewModel: ControlViewModel? = null,
) {
    val state by viewModel.state.collectAsState()
    val autonomyState = controlViewModel?.state?.collectAsState()
    var confirmStop by remember { mutableStateOf(false) }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(paddingValues)
            .padding(JarvisTokens.SpaceLg)
            .verticalScroll(rememberScrollState()),
        verticalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceLg),
    ) {
        museCard(modifier = Modifier.fillMaxWidth()) {
            Column(
                modifier = Modifier.fillMaxWidth().padding(JarvisTokens.SpaceLg),
                verticalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm),
            ) {
                museSectionHeader(title = stringResource(R.string.control_service_title))
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm),
                ) {
                    museStatusDot(
                        status = if (state.serviceRunning) museStatus.Ok else museStatus.Off,
                    )
                    Text(
                        text = if (state.serviceRunning) stringResource(R.string.orchestrator_status_running)
                               else stringResource(R.string.orchestrator_status_stopped),
                        style = MaterialTheme.typography.titleMedium,
                        color = JarvisSignal,
                    )
                }
                HorizontalDivider()
                Row(horizontalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm)) {
                    museButton(
                        onClick = viewModel::startService,
                        text = stringResource(R.string.orchestrator_start_service),
                        variant = museButtonVariant.Primary,
                        enabled = !state.serviceRunning,
                    )
                    museButton(
                        onClick = viewModel::stopService,
                        text = stringResource(R.string.orchestrator_stop_service),
                        variant = museButtonVariant.Secondary,
                        enabled = state.serviceRunning,
                    )
                }
            }
        }

        museCard(modifier = Modifier.fillMaxWidth()) {
            Column(
                modifier = Modifier.fillMaxWidth().padding(JarvisTokens.SpaceLg),
                verticalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm),
            ) {
                museSectionHeader(title = stringResource(R.string.device_control_title))
                Text(
                    text = stringResource(R.string.device_control_subtitle),
                    style = MaterialTheme.typography.bodyMedium,
                    color = JarvisSignalDim,
                )
                museButton(
                    onClick = onOpenDeviceControl,
                    text = stringResource(R.string.device_control_open),
                    variant = museButtonVariant.Primary,
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        }

        museCard(modifier = Modifier.fillMaxWidth()) {
            Column(
                modifier = Modifier.fillMaxWidth().padding(JarvisTokens.SpaceLg),
                verticalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm),
            ) {
                museSectionHeader(title = stringResource(R.string.emergency_stop_title))
                Text(
                    text = stringResource(R.string.emergency_stop_body),
                    style = MaterialTheme.typography.bodyMedium,
                    color = JarvisSignalDim,
                )
                museButton(
                    onClick = { confirmStop = true },
                    text = stringResource(R.string.nav_emergency_stop),
                    variant = museButtonVariant.Danger,
                    leadingIcon = Icons.Filled.PowerSettingsNew,
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        }

        // High-Autonomy Coding controls — only when the autonomy VM is wired.
        if (controlViewModel != null && autonomyState != null) {
            AutonomyControlSection(
                state = autonomyState.value,
                onSelectMode = controlViewModel::requestAutonomyMode,
                onWorkspaceChange = controlViewModel::setCodingWorkspaceRoot,
                onRevoke = controlViewModel::revokeAutonomy,
                onConfirmWarning = controlViewModel::confirmPendingWarning,
                onDismissWarning = controlViewModel::dismissPendingWarning,
            )
        }
    }

    if (confirmStop) {
        AlertDialog(
            onDismissRequest = { confirmStop = false },
            icon = {
                Icon(
                    imageVector = Icons.Filled.PowerSettingsNew,
                    contentDescription = null,
                    tint = MaterialTheme.colorScheme.error,
                )
            },
            title = { Text(stringResource(R.string.emergency_stop_title)) },
            text = { Text(stringResource(R.string.emergency_stop_body)) },
            confirmButton = {
                TextButton(onClick = {
                    confirmStop = false
                    onEmergencyStop()
                    // Also cancel backend jobs and latch autonomy to read-only.
                    controlViewModel?.emergencyStopNow()
                }) { Text(stringResource(R.string.emergency_stop_confirm)) }
            },
            dismissButton = {
                TextButton(onClick = { confirmStop = false }) {
                    Text(stringResource(R.string.action_cancel))
                }
            },
        )
    }
}
