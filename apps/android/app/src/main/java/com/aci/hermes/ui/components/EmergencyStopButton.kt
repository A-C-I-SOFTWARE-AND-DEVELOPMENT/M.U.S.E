package com.aci.hermes.ui.components

import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Bolt
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.aci.hermes.R
import com.aci.hermes.ui.theme.JarvisCrimson
import com.aci.hermes.ui.theme.JarvisCrimsonBright
import com.aci.hermes.ui.theme.JarvisCrimsonDeep
import com.aci.hermes.ui.theme.JarvisSignal
import com.aci.hermes.ui.theme.JarvisTokens

/**
 * Emergency stop — halt every active Jarvis task.
 *
 * One tap opens a confirmation dialog. The destructive action is never
 * one-tap; the dialog forces a deliberate second tap.
 */
@Composable
fun EmergencyStopButton(
    onConfirmed: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
) {
    var confirming by remember { mutableStateOf(false) }

    Button(
        onClick = { confirming = true },
        enabled = enabled,
        shape = JarvisTokens.ShapeButton,
        colors = ButtonDefaults.buttonColors(
            containerColor = JarvisCrimson,
            contentColor = JarvisSignal,
            disabledContainerColor = JarvisCrimsonDeep,
            disabledContentColor = JarvisSignal.copy(alpha = 0.5f),
        ),
        modifier = modifier
            .fillMaxWidth()
            .height(52.dp)
            .border(
                width = JarvisTokens.BorderHairline,
                color = JarvisCrimsonBright.copy(alpha = 0.6f),
                shape = JarvisTokens.ShapeButton,
            ),
        contentPadding = androidx.compose.foundation.layout.PaddingValues(horizontal = JarvisTokens.SpaceLg),
    ) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm),
        ) {
            Icon(
                imageVector = Icons.Filled.Bolt,
                contentDescription = null,
            )
            Text(
                text = stringResource(R.string.emergency_stop),
                style = androidx.compose.material3.MaterialTheme.typography.titleMedium,
            )
        }
    }

    if (confirming) {
        AlertDialog(
            onDismissRequest = { confirming = false },
            title = { Text(stringResource(R.string.emergency_stop_confirm_title)) },
            text = { Text(stringResource(R.string.emergency_stop_confirm_body)) },
            confirmButton = {
                TextButton(onClick = {
                    confirming = false
                    onConfirmed()
                }) {
                    Text(
                        text = stringResource(R.string.emergency_stop_confirm_yes),
                        color = JarvisCrimson,
                    )
                }
            },
            dismissButton = {
                TextButton(onClick = { confirming = false }) {
                    Text(stringResource(R.string.emergency_stop_confirm_no))
                }
            },
        )
    }
}
