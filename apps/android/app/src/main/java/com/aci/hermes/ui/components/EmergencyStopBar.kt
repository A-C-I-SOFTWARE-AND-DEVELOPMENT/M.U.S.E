package com.aci.hermes.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.aci.hermes.R
import com.aci.hermes.safety.EmergencyStop
import com.aci.hermes.ui.theme.JarvisRed

/**
 * The always-reachable emergency-stop control. Engineered to be the
 * loudest interactive element on the screen — red, persistent, never
 * collapsed into a menu — and to never engage without the owner
 * confirming once. The Emergency Stop itself is idempotent, but
 * one-tap engage from a misclick is exactly the wrong shape for a
 * critical action.
 */
@Composable
fun EmergencyStopBar(
    emergencyStop: EmergencyStop,
    modifier: Modifier = Modifier,
    reason: String = "owner_tap",
    onEngaged: (() -> Unit)? = null,
) {
    var confirming by remember { mutableStateOf(false) }

    Row(
        modifier = modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(12.dp))
            .background(MaterialTheme.colorScheme.surfaceVariant)
            .padding(horizontal = 12.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.SpaceBetween,
    ) {
        Text(
            stringResource(R.string.emergency_stop_label),
            style = MaterialTheme.typography.titleMedium,
        )
        Button(
            onClick = { confirming = true },
            colors = ButtonDefaults.buttonColors(containerColor = JarvisRed),
        ) {
            Icon(Icons.Default.Stop, contentDescription = null)
            Text(
                text = "STAND DOWN",
                modifier = Modifier.padding(start = 6.dp),
            )
        }
    }

    if (confirming) {
        AlertDialog(
            onDismissRequest = { confirming = false },
            title = { Text(stringResource(R.string.emergency_stop_label)) },
            text = { Text("Stand Jarvis Prime down? Every running worker is signalled to stop and every pending approval is rejected.") },
            confirmButton = {
                Button(
                    onClick = {
                        emergencyStop.engage(reason)
                        confirming = false
                        onEngaged?.invoke()
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = JarvisRed),
                ) {
                    Text("Stand down")
                }
            },
            dismissButton = {
                TextButton(onClick = { confirming = false }) {
                    Text(stringResource(R.string.action_cancel))
                }
            },
        )
    }
}
