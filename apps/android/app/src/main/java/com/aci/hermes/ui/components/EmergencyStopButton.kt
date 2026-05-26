package com.aci.hermes.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.PauseCircle
import androidx.compose.material.icons.filled.PowerSettingsNew
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import com.aci.hermes.data.emergency.EmergencyStopState

/**
 * Compact emergency stop indicator. Tap → confirmation dialog (engage
 * or open the dedicated screen if already engaged). Long-press →
 * escalates one level, all the way up to LOCKDOWN.
 *
 * The icon visibly mirrors the current state so users can tell at a
 * glance from any screen whether Jarvis is paused, stopped, or
 * locked down.
 */
@Composable
fun EmergencyStopButton(
    state: EmergencyStopState,
    onTap: () -> Unit,
    onLongPressEscalate: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val descriptor = state.contentDescription()
    val icon = state.icon()
    val tint = state.iconTint()
    val containerColor = state.containerColor()

    Box(
        modifier = modifier
            .size(40.dp)
            .background(color = containerColor, shape = CircleShape)
            .pointerInput(state) {
                detectTapGestures(
                    onTap = { onTap() },
                    onLongPress = { onLongPressEscalate() },
                )
            }
            .semantics {
                role = Role.Button
                contentDescription = descriptor
            }
            .testTag(EMERGENCY_STOP_BUTTON_TAG),
        contentAlignment = Alignment.Center,
    ) {
        Icon(
            imageVector = icon,
            contentDescription = null,
            tint = tint,
            modifier = Modifier.size(22.dp),
        )
    }
}

@Composable
private fun EmergencyStopState.icon(): ImageVector = when (this) {
    EmergencyStopState.INACTIVE -> Icons.Filled.PowerSettingsNew
    EmergencyStopState.SOFT_PAUSE -> Icons.Filled.PauseCircle
    EmergencyStopState.HARD_STOP -> Icons.Filled.Stop
    EmergencyStopState.LOCKDOWN -> Icons.Filled.Lock
}

@Composable
private fun EmergencyStopState.iconTint(): Color = when (this) {
    EmergencyStopState.INACTIVE -> MaterialTheme.colorScheme.onSurface
    EmergencyStopState.SOFT_PAUSE -> MaterialTheme.colorScheme.onError
    EmergencyStopState.HARD_STOP -> MaterialTheme.colorScheme.onError
    EmergencyStopState.LOCKDOWN -> MaterialTheme.colorScheme.onError
}

@Composable
private fun EmergencyStopState.containerColor(): Color = when (this) {
    EmergencyStopState.INACTIVE -> Color.Transparent
    EmergencyStopState.SOFT_PAUSE -> MaterialTheme.colorScheme.error.copy(alpha = 0.55f)
    EmergencyStopState.HARD_STOP -> MaterialTheme.colorScheme.error
    EmergencyStopState.LOCKDOWN -> MaterialTheme.colorScheme.error
}

private fun EmergencyStopState.contentDescription(): String = when (this) {
    EmergencyStopState.INACTIVE ->
        "Emergency stop is inactive. Tap to engage, long-press to escalate."
    EmergencyStopState.SOFT_PAUSE ->
        "Jarvis is soft-paused. Tap to open controls, long-press to escalate."
    EmergencyStopState.HARD_STOP ->
        "Jarvis is hard-stopped. Tap to open controls, long-press to escalate to lockdown."
    EmergencyStopState.LOCKDOWN ->
        "Jarvis is in lockdown. Tap to open controls."
}

const val EMERGENCY_STOP_BUTTON_TAG = "emergency_stop_button"
