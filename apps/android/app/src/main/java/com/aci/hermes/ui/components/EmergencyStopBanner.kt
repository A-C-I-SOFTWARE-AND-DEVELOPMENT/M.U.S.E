package com.aci.hermes.ui.components

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.PauseCircle
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import com.aci.hermes.data.emergency.EmergencyStopState

/**
 * Persistent blocked / lockdown banner. Renders only when the
 * emergency stop is engaged. Shows the level, a one-line summary of
 * what's blocked, and a shortcut to the Jarvis Control screen.
 */
@Composable
fun EmergencyStopBanner(
    state: EmergencyStopState,
    onOpenControl: () -> Unit,
    modifier: Modifier = Modifier,
) {
    if (state == EmergencyStopState.INACTIVE) return

    val tag = when (state) {
        EmergencyStopState.SOFT_PAUSE -> BANNER_SOFT_PAUSE_TAG
        EmergencyStopState.HARD_STOP -> BANNER_HARD_STOP_TAG
        EmergencyStopState.LOCKDOWN -> BANNER_LOCKDOWN_TAG
        EmergencyStopState.INACTIVE -> "" // unreachable
    }

    Card(
        modifier = modifier
            .fillMaxWidth()
            .testTag(tag),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.error,
            contentColor = MaterialTheme.colorScheme.onError,
        ),
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                Icon(
                    imageVector = state.bannerIcon(),
                    contentDescription = null,
                    tint = MaterialTheme.colorScheme.onError,
                )
                Text(
                    text = "Jarvis Prime: ${state.bannerTitle()}",
                    style = MaterialTheme.typography.titleMedium,
                )
            }
            Text(
                text = state.bannerBody(),
                style = MaterialTheme.typography.bodyMedium,
            )
            Row {
                OutlinedButton(
                    onClick = onOpenControl,
                    colors = androidx.compose.material3.ButtonDefaults.outlinedButtonColors(
                        contentColor = MaterialTheme.colorScheme.onError,
                    ),
                    border = androidx.compose.foundation.BorderStroke(
                        width = 1.dp,
                        color = MaterialTheme.colorScheme.onError.copy(alpha = 0.7f),
                    ),
                ) {
                    Text("Open Jarvis Control")
                }
            }
        }
    }
}

private fun EmergencyStopState.bannerIcon(): ImageVector = when (this) {
    EmergencyStopState.SOFT_PAUSE -> Icons.Filled.PauseCircle
    EmergencyStopState.HARD_STOP -> Icons.Filled.Stop
    EmergencyStopState.LOCKDOWN -> Icons.Filled.Lock
    EmergencyStopState.INACTIVE -> Icons.Filled.PauseCircle // unreachable
}

private fun EmergencyStopState.bannerTitle(): String = when (this) {
    EmergencyStopState.SOFT_PAUSE -> "Soft pause"
    EmergencyStopState.HARD_STOP -> "Hard stop"
    EmergencyStopState.LOCKDOWN -> "Lockdown"
    EmergencyStopState.INACTIVE -> "" // unreachable
}

private fun EmergencyStopState.bannerBody(): String = when (this) {
    EmergencyStopState.SOFT_PAUSE ->
        "New task starts are blocked. In-flight work continues. Resume requires approval."
    EmergencyStopState.HARD_STOP ->
        "Sends, deletes, pushes, and deploys are blocked. Resume requires approval."
    EmergencyStopState.LOCKDOWN ->
        "All non-read-only actions are blocked except status, audit, export, and resume. " +
            "Resume requires approval."
    EmergencyStopState.INACTIVE -> ""
}

const val BANNER_SOFT_PAUSE_TAG = "banner_soft_pause"
const val BANNER_HARD_STOP_TAG = "banner_hard_stop"
const val BANNER_LOCKDOWN_TAG = "banner_lockdown"
