package com.aci.hermes.ui.components

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Bolt
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import com.aci.hermes.data.emergency.EmergencyStopState

/**
 * Card that surfaces the most dangerous control on the dashboard so a
 * user can stop Jarvis from anywhere without hunting through menus.
 *
 * Renders one of three shapes:
 *  - Inactive: a single "Emergency Stop" primary action.
 *  - Soft pause / hard stop: shows current level + escalate + resume.
 *  - Lockdown: shows lockdown banner + request-resume only.
 */
@Composable
fun CriticalActionCard(
    state: EmergencyStopState,
    onEngageStop: () -> Unit,
    onEscalate: () -> Unit,
    onRequestResume: () -> Unit,
    onOpenControl: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Card(
        modifier = modifier
            .fillMaxWidth()
            .testTag(CRITICAL_ACTION_CARD_TAG),
        colors = CardDefaults.cardColors(
            containerColor = if (state.isActive) MaterialTheme.colorScheme.errorContainer
            else MaterialTheme.colorScheme.surfaceVariant,
        ),
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Icon(
                    imageVector = Icons.Filled.Bolt,
                    contentDescription = null,
                    tint = if (state.isActive) MaterialTheme.colorScheme.onErrorContainer
                    else MaterialTheme.colorScheme.primary,
                )
                Text(
                    text = "Critical action",
                    style = MaterialTheme.typography.titleMedium,
                )
            }
            Text(
                text = when (state) {
                    EmergencyStopState.INACTIVE ->
                        "Halts Jarvis instantly. Use Emergency Stop if anything looks wrong."
                    EmergencyStopState.SOFT_PAUSE ->
                        "Jarvis is paused. New task starts are blocked; in-flight work continues."
                    EmergencyStopState.HARD_STOP ->
                        "Jarvis is hard-stopped. Sends, deletes, pushes, and deploys are blocked."
                    EmergencyStopState.LOCKDOWN ->
                        "Jarvis is in lockdown. Only status, audit, export, and resume are allowed."
                },
                style = MaterialTheme.typography.bodyMedium,
            )

            when (state) {
                EmergencyStopState.INACTIVE -> {
                    Button(
                        onClick = onEngageStop,
                        colors = ButtonDefaults.buttonColors(
                            containerColor = MaterialTheme.colorScheme.error,
                            contentColor = MaterialTheme.colorScheme.onError,
                        ),
                        modifier = Modifier.testTag(CRITICAL_ACTION_ENGAGE_TAG),
                    ) {
                        Text("Emergency Stop")
                    }
                }
                EmergencyStopState.SOFT_PAUSE, EmergencyStopState.HARD_STOP -> {
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Button(
                            onClick = onEscalate,
                            colors = ButtonDefaults.buttonColors(
                                containerColor = MaterialTheme.colorScheme.error,
                                contentColor = MaterialTheme.colorScheme.onError,
                            ),
                            modifier = Modifier.testTag(CRITICAL_ACTION_ESCALATE_TAG),
                        ) {
                            Text("Escalate")
                        }
                        OutlinedButton(
                            onClick = onRequestResume,
                            modifier = Modifier.testTag(CRITICAL_ACTION_REQUEST_RESUME_TAG),
                        ) {
                            Text("Request resume")
                        }
                        OutlinedButton(onClick = onOpenControl) { Text("Open control") }
                    }
                }
                EmergencyStopState.LOCKDOWN -> {
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Button(
                            onClick = onRequestResume,
                            modifier = Modifier.testTag(CRITICAL_ACTION_REQUEST_RESUME_TAG),
                        ) {
                            Text("Request resume")
                        }
                        OutlinedButton(onClick = onOpenControl) { Text("Open control") }
                    }
                }
            }
        }
    }
}

const val CRITICAL_ACTION_CARD_TAG = "critical_action_card"
const val CRITICAL_ACTION_ENGAGE_TAG = "critical_action_engage"
const val CRITICAL_ACTION_ESCALATE_TAG = "critical_action_escalate"
const val CRITICAL_ACTION_REQUEST_RESUME_TAG = "critical_action_request_resume"
