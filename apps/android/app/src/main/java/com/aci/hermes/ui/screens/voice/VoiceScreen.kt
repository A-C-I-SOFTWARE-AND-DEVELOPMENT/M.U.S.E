package com.aci.hermes.ui.screens.voice

import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.aci.hermes.R
import com.aci.hermes.di.AppContainer
import com.aci.hermes.safety.JarvisPermission
import com.aci.hermes.safety.PermissionState
import com.aci.hermes.ui.components.JarvisIconState
import com.aci.hermes.ui.components.JarvisInteractiveIcon
import com.aci.hermes.ui.permissions.PermissionRouter
import com.aci.hermes.voice.VoiceCapture

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun VoiceScreen(
    container: AppContainer,
    viewModel: VoiceViewModel,
    onBack: () -> Unit,
) {
    val state by viewModel.state.collectAsState()
    val context = LocalContext.current

    if (state.requestMicPermission) {
        PermissionRouter(
            container = container,
            requested = JarvisPermission.MICROPHONE,
            onComplete = { viewModel.consumePermissionRequest() },
        )
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.voice_title)) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = stringResource(R.string.action_back))
                    }
                },
            )
        },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(24.dp),
            verticalArrangement = Arrangement.spacedBy(24.dp, Alignment.CenterVertically),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            val iconState = when (state.capture) {
                VoiceCapture.State.CAPTURING -> JarvisIconState.LISTENING
                else -> JarvisIconState.IDLE
            }
            JarvisInteractiveIcon(state = iconState, size = 200.dp)

            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .size(width = 240.dp, height = 64.dp)
                    .pointerInput(state.micState) {
                        detectTapGestures(
                            onPress = {
                                viewModel.onTalkPressed()
                                val released = tryAwaitRelease()
                                if (released) viewModel.onTalkReleased()
                            },
                        )
                    },
                contentAlignment = Alignment.Center,
            ) {
                Text(
                    text = when {
                        state.micState != PermissionState.GRANTED -> stringResource(R.string.voice_permission_required)
                        state.capture == VoiceCapture.State.CAPTURING -> stringResource(R.string.voice_release_to_send)
                        else -> stringResource(R.string.voice_hold_to_talk)
                    },
                    style = MaterialTheme.typography.titleMedium,
                    color = MaterialTheme.colorScheme.primary,
                )
            }

            if (state.transcript.isNotBlank()) {
                Text(
                    state.transcript,
                    style = MaterialTheme.typography.bodyLarge,
                )
            }
        }
    }
}
