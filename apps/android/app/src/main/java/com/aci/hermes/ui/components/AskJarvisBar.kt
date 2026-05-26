package com.aci.hermes.ui.components

import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.IconButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.ui.unit.dp
import com.aci.hermes.R
import com.aci.hermes.ui.theme.JarvisCyan
import com.aci.hermes.ui.theme.JarvisGold
import com.aci.hermes.ui.theme.JarvisInkDeep
import com.aci.hermes.ui.theme.JarvisInkEdge
import com.aci.hermes.ui.theme.JarvisInkRaised
import com.aci.hermes.ui.theme.JarvisSignal
import com.aci.hermes.ui.theme.JarvisSignalMute
import com.aci.hermes.ui.theme.JarvisTokens

/**
 * The "Ask Jarvis" input bar.
 *
 * One text input + a microphone toggle + a send button. The bar takes
 * its visual cues from the rest of the command center: deep navy fill,
 * gold-tinged focused border, cyan accent when listening.
 *
 * Pure UI — the caller owns the value, the mic state, and the actions.
 */
@Composable
fun AskJarvisBar(
    value: String,
    onValueChange: (String) -> Unit,
    onSend: () -> Unit,
    onMicToggle: () -> Unit,
    isListening: Boolean,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
) {
    Surface(
        shape = JarvisTokens.ShapeCardLarge,
        color = JarvisInkDeep,
        modifier = modifier
            .fillMaxWidth()
            .border(
                width = JarvisTokens.BorderHairline,
                color = if (isListening) JarvisCyan.copy(alpha = 0.6f) else JarvisInkEdge,
                shape = JarvisTokens.ShapeCardLarge
            )
    ) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm),
            modifier = Modifier.padding(
                horizontal = JarvisTokens.SpaceMd,
                vertical = JarvisTokens.SpaceSm,
            )
        ) {
            OutlinedTextField(
                value = value,
                onValueChange = onValueChange,
                enabled = enabled && !isListening,
                modifier = Modifier.weight(1f, fill = true),
                placeholder = {
                    Text(
                        text = if (isListening) {
                            stringResource(R.string.ask_jarvis_listening)
                        } else {
                            stringResource(R.string.ask_jarvis_hint)
                        },
                        color = if (isListening) JarvisCyan else JarvisSignalMute,
                        style = MaterialTheme.typography.bodyMedium
                    )
                },
                singleLine = true,
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Send),
                keyboardActions = KeyboardActions(onSend = { onSend() }),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = JarvisGold.copy(alpha = 0.45f),
                    unfocusedBorderColor = JarvisInkRaised,
                    disabledBorderColor = JarvisInkEdge,
                    focusedTextColor = JarvisSignal,
                    unfocusedTextColor = JarvisSignal,
                    disabledTextColor = JarvisSignalMute,
                    cursorColor = JarvisGold,
                    focusedContainerColor = JarvisInkDeep,
                    unfocusedContainerColor = JarvisInkDeep,
                    disabledContainerColor = JarvisInkDeep,
                ),
            )
            IconButton(
                onClick = onMicToggle,
                enabled = enabled,
                colors = IconButtonDefaults.iconButtonColors(
                    contentColor = if (isListening) JarvisCyan else JarvisSignalMute
                ),
                modifier = Modifier.size(40.dp),
            ) {
                Icon(
                    imageVector = if (isListening) Icons.Filled.Stop else Icons.Filled.Mic,
                    contentDescription = stringResource(R.string.ask_jarvis_voice_cd)
                )
            }
            IconButton(
                onClick = onSend,
                enabled = enabled && value.isNotBlank() && !isListening,
                colors = IconButtonDefaults.iconButtonColors(contentColor = JarvisGold),
                modifier = Modifier.size(40.dp),
            ) {
                Icon(
                    imageVector = Icons.AutoMirrored.Filled.Send,
                    contentDescription = stringResource(R.string.ask_jarvis_send_cd)
                )
            }
        }
    }
}
