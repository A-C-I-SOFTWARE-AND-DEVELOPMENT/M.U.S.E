package com.aci.hermes.ui.screens.control

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.PowerSettingsNew
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
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
import androidx.compose.ui.unit.dp
import com.aci.hermes.R
import com.aci.hermes.data.jarvis.ConnectedService
import com.aci.hermes.data.jarvis.GatewayState
import com.aci.hermes.data.jarvis.JarvisControlState
import com.aci.hermes.data.jarvis.ServiceState
import com.aci.hermes.ui.screens.orchestrator.OrchestratorViewModel

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
) {
    val state by viewModel.state.collectAsState()
    var confirmStop by remember { mutableStateOf(false) }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(paddingValues)
            .padding(16.dp)
            .verticalScroll(rememberScrollState()),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)) {
            Column(
                modifier = Modifier.fillMaxWidth().padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Text(
                    text = stringResource(R.string.control_service_title),
                    style = MaterialTheme.typography.titleMedium,
                    color = MaterialTheme.colorScheme.primary,
                )
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    Surface(
                        shape = CircleShape,
                        color = if (state.serviceRunning) MaterialTheme.colorScheme.primary
                                else MaterialTheme.colorScheme.error,
                        modifier = Modifier.size(12.dp),
                    ) {}
                    Text(
                        text = if (state.serviceRunning) stringResource(R.string.orchestrator_status_running)
                               else stringResource(R.string.orchestrator_status_stopped),
                        style = MaterialTheme.typography.titleMedium,
                    )
                }
                HorizontalDivider()
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(
                        onClick = viewModel::startService,
                        enabled = !state.serviceRunning,
                    ) { Text(stringResource(R.string.orchestrator_start_service)) }
                    OutlinedButton(
                        onClick = viewModel::stopService,
                        enabled = state.serviceRunning,
                    ) { Text(stringResource(R.string.orchestrator_stop_service)) }
                }
                Text(
                    text = ControlEmptyStateCopy.serviceSummary(orchestratorAsControlState(state.serviceRunning)),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }

        ConnectedServicesSection(state = orchestratorAsControlState(state.serviceRunning))

        Card(
            colors = CardDefaults.cardColors(
                containerColor = MaterialTheme.colorScheme.errorContainer,
            ),
        ) {
            Column(
                modifier = Modifier.fillMaxWidth().padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Text(
                    text = stringResource(R.string.emergency_stop_title),
                    style = MaterialTheme.typography.titleMedium,
                    color = MaterialTheme.colorScheme.error,
                )
                Text(
                    text = stringResource(R.string.emergency_stop_body),
                    style = MaterialTheme.typography.bodyMedium,
                )
                Button(
                    onClick = { confirmStop = true },
                    colors = ButtonDefaults.buttonColors(
                        containerColor = MaterialTheme.colorScheme.error,
                        contentColor = MaterialTheme.colorScheme.onError,
                    ),
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Icon(Icons.Filled.PowerSettingsNew, contentDescription = null)
                    Text(
                        text = stringResource(R.string.nav_emergency_stop),
                        modifier = Modifier.padding(start = 8.dp),
                    )
                }
            }
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
            text = {
                Text(
                    "Owner action: Jarvis Prime will halt the orchestrator " +
                        "service and decline any further outbound action until " +
                        "you release the stop. Pending tasks stay saved.",
                )
            },
            confirmButton = {
                TextButton(onClick = {
                    confirmStop = false
                    onEmergencyStop()
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

/**
 * Until [com.aci.hermes.ui.screens.control.ControlViewModel] is fully
 * wired (it depends on settings fields that don't ship on this branch
 * yet), the screen projects what the orchestrator already exposes —
 * service liveness — into a [JarvisControlState] so the new
 * [ConnectedServicesSection] surface has something honest to render.
 * The rest of the state stays at its safe defaults: gateway
 * unconfigured, no connected services, autonomy MANUAL, emergency
 * stop released. When the upstream settings/projector land, this
 * helper goes away and the real projector replaces it.
 */
internal fun orchestratorAsControlState(serviceRunning: Boolean): JarvisControlState =
    JarvisControlState(
        jarvisRunning = serviceRunning,
        service = if (serviceRunning) ServiceState.RUNNING else ServiceState.STOPPED,
        gateway = GatewayState.UNCONFIGURED,
        connectedServices = listOf(
            ConnectedService(id = "termux", displayName = "Termux bridge", connected = false),
        ),
    )

