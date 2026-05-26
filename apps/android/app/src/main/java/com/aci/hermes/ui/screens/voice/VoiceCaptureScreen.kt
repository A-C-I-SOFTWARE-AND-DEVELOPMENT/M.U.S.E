package com.aci.hermes.ui.screens.voice

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import com.aci.hermes.R
import com.aci.hermes.ui.icon.InteractiveIcon

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun VoiceCaptureScreen(viewModel: VoiceCaptureViewModel, onBack: () -> Unit) {
    val state by viewModel.state.collectAsState()
    val context = LocalContext.current

    val launcher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        viewModel.onPermissionResult(granted)
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text(stringResource(R.string.voice_title))
                        Text(
                            stringResource(R.string.voice_subtitle),
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = null)
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
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(20.dp),
        ) {
            Spacer(modifier = Modifier.height(20.dp))
            InteractiveIcon(
                active = state.state == VoiceCaptureState.Recording || state.state == VoiceCaptureState.Transcribing,
                sizeDp = 160,
                onClick = {
                    when (state.state) {
                        VoiceCaptureState.Idle, VoiceCaptureState.Captured, VoiceCaptureState.Denied -> {
                            val granted = ContextCompat.checkSelfPermission(
                                context, Manifest.permission.RECORD_AUDIO,
                            ) == PackageManager.PERMISSION_GRANTED
                            if (granted) {
                                viewModel.onPermissionResult(true)
                            } else {
                                launcher.launch(Manifest.permission.RECORD_AUDIO)
                            }
                        }
                        VoiceCaptureState.Recording -> viewModel.stopCapture()
                        VoiceCaptureState.Transcribing -> {} // wait
                    }
                },
                contentDescription = null,
            )

            Text(
                text = when (state.state) {
                    VoiceCaptureState.Idle -> stringResource(R.string.voice_tap_to_start)
                    VoiceCaptureState.Recording -> stringResource(R.string.voice_recording)
                    VoiceCaptureState.Transcribing -> "Transcribing…"
                    VoiceCaptureState.Captured -> stringResource(R.string.voice_transcript_label)
                    VoiceCaptureState.Denied -> stringResource(R.string.voice_permission_title)
                },
                style = MaterialTheme.typography.titleMedium,
            )

            if (state.state == VoiceCaptureState.Captured) {
                Card(
                    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
                    shape = RoundedCornerShape(14.dp),
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text(
                        text = state.transcript,
                        modifier = Modifier.padding(16.dp),
                        style = MaterialTheme.typography.bodyLarge,
                    )
                }
                OutlinedButton(onClick = viewModel::reset, modifier = Modifier.fillMaxWidth()) {
                    Text("Capture again")
                }
            }

            if (state.state == VoiceCaptureState.Denied) {
                Text(stringResource(R.string.voice_permission_body), style = MaterialTheme.typography.bodyMedium)
                Button(
                    onClick = { launcher.launch(Manifest.permission.RECORD_AUDIO) },
                    modifier = Modifier.fillMaxWidth(),
                ) { Text(stringResource(R.string.voice_permission_grant)) }
            }
        }
    }
}
