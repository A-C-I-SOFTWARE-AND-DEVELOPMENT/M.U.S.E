package com.aci.hermes.ui.screens.control

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.aci.hermes.data.jarvis.AutonomyMode
import com.aci.hermes.data.jarvis.GatewayState
import com.aci.hermes.data.jarvis.JarvisControlState
import com.aci.hermes.data.jarvis.ServiceState

object ConnectedServicesTags {
    const val ROOT = "control_connected_services"
    const val GATEWAY = "control_gateway_state"
    const val MOCK = "control_mock_badge"
    const val TERMUX = "control_termux_state"
    const val LOCKDOWN = "control_lockdown_banner"
    const val EMERGENCY_BANNER = "control_emergency_stop_engaged"
    const val SERVICE_SUMMARY = "control_service_summary"
}

/**
 * Read-only surface that turns [JarvisControlState] into owner-facing
 * pills + banners. The screen pulls a state from whichever wiring is
 * available (orchestrator, projector, future gateway poller); this
 * composable only renders. All copy comes from [ControlEmptyStateCopy]
 * so a single source of truth backs both UI and tests.
 */
@Composable
fun ConnectedServicesSection(
    state: JarvisControlState,
    modifier: Modifier = Modifier,
) {
    val scheme = MaterialTheme.colorScheme

    Card(
        modifier = modifier
            .fillMaxWidth()
            .testTag(ConnectedServicesTags.ROOT),
        colors = CardDefaults.cardColors(containerColor = scheme.surfaceVariant),
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Text(
                text = "Connected services",
                style = MaterialTheme.typography.titleMedium,
                color = scheme.primary,
            )
            Text(
                text = ControlEmptyStateCopy.serviceSummary(state),
                style = MaterialTheme.typography.bodyMedium,
                modifier = Modifier.testTag(ConnectedServicesTags.SERVICE_SUMMARY),
            )

            if (state.emergencyStopEngaged) {
                Banner(
                    text = ControlEmptyStateCopy.SERVICE_EMERGENCY_STOPPED,
                    container = scheme.errorContainer,
                    onContainer = scheme.onErrorContainer,
                    testTag = ConnectedServicesTags.EMERGENCY_BANNER,
                )
            }
            if (state.autonomy == AutonomyMode.LOCKDOWN) {
                Banner(
                    text = ControlEmptyStateCopy.SERVICE_LOCKDOWN,
                    container = scheme.errorContainer,
                    onContainer = scheme.onErrorContainer,
                    testTag = ConnectedServicesTags.LOCKDOWN,
                )
            }

            Pill(
                text = ControlEmptyStateCopy.gatewaySummary(state.gateway),
                connected = state.gateway == GatewayState.CONNECTED ||
                    state.gateway == GatewayState.MOCK,
                testTag = ConnectedServicesTags.GATEWAY,
            )
            if (state.mockMode) {
                Pill(
                    text = ControlEmptyStateCopy.GATEWAY_MOCK,
                    connected = true,
                    testTag = ConnectedServicesTags.MOCK,
                )
            }

            val termux = state.connectedServices.firstOrNull { it.id == "termux" }
            Pill(
                text = ControlEmptyStateCopy.termuxSummary(
                    connected = termux?.connected == true,
                    installed = termux != null,
                ),
                connected = termux?.connected == true,
                testTag = ConnectedServicesTags.TERMUX,
            )

            if (state.service != ServiceState.RUNNING &&
                !state.emergencyStopEngaged &&
                state.autonomy != AutonomyMode.LOCKDOWN &&
                state.connectedServices.isEmpty()
            ) {
                Text(
                    text = ControlEmptyStateCopy.EMPTY_SERVICES,
                    style = MaterialTheme.typography.bodySmall,
                    color = scheme.onSurfaceVariant,
                )
            }
        }
    }
}

@Composable
private fun Pill(
    text: String,
    connected: Boolean,
    testTag: String,
) {
    val scheme = MaterialTheme.colorScheme
    val tint = if (connected) scheme.primary else scheme.error
    Row(
        modifier = Modifier
            .clip(RoundedCornerShape(50))
            .background(scheme.surface)
            .padding(horizontal = 12.dp, vertical = 6.dp)
            .testTag(testTag),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Surface(shape = CircleShape, color = tint, modifier = Modifier.size(10.dp)) {}
        Text(
            text = text,
            style = MaterialTheme.typography.labelMedium,
            fontWeight = FontWeight.Medium,
        )
    }
}

@Composable
private fun Banner(
    text: String,
    container: androidx.compose.ui.graphics.Color,
    onContainer: androidx.compose.ui.graphics.Color,
    testTag: String,
) {
    Surface(
        shape = RoundedCornerShape(8.dp),
        color = container,
        contentColor = onContainer,
        modifier = Modifier
            .fillMaxWidth()
            .testTag(testTag),
    ) {
        Text(
            text = text,
            style = MaterialTheme.typography.bodyMedium,
            fontWeight = FontWeight.SemiBold,
            modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp),
        )
    }
}
