package com.aci.hermes.voice.ui

import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.width
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.Icon
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.aci.hermes.R

/**
 * Entry button for the JARVIS Prime voice surface. Lives on the
 * orchestrator dashboard; tapping it opens the education sheet, which
 * is the only place that ever asks for the mic permission.
 */
@Composable
fun VoiceCaptureButton(
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    filled: Boolean = true,
) {
    if (filled) {
        FilledTonalButton(onClick = onClick, modifier = modifier) {
            Icon(imageVector = Icons.Default.Mic, contentDescription = null)
            Spacer(Modifier.width(8.dp))
            Text(stringResource(R.string.voice_capture_button))
        }
    } else {
        OutlinedButton(onClick = onClick, modifier = modifier) {
            Icon(imageVector = Icons.Default.Mic, contentDescription = null)
            Spacer(Modifier.width(8.dp))
            Text(stringResource(R.string.voice_capture_button))
        }
    }
}
