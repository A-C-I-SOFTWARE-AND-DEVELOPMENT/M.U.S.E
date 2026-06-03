package com.aci.hermes.ui.screens.voice

import android.app.Activity
import android.content.Intent
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.aci.hermes.R

object VoiceCaptureTestTags {
    const val MIC_BUTTON = "voice_mic_button"
    const val TRANSCRIPT = "voice_transcript"
    const val SAVE_TASK = "voice_save_task"
}

/**
 * Hands-free capture screen. Tapping the mic launches the system speech
 * recognizer (no RECORD_AUDIO permission — the system Activity owns the
 * mic); the returned transcript can be promoted into a draft task that
 * lands on the Tasks screen.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun VoiceCaptureScreen(
    viewModel: VoiceCaptureViewModel,
    onBack: () -> Unit,
    onTaskCreated: (taskId: String) -> Unit,
) {
    val state by viewModel.state.collectAsState()
    val context = LocalContext.current

    val launcher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.StartActivityForResult(),
    ) { result ->
        if (result.resultCode == Activity.RESULT_OK) {
            val spoken = result.data
                ?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)
                ?.firstOrNull()
                .orEmpty()
            viewModel.onTranscript(spoken)
        } else {
            viewModel.onListeningCancelled()
        }
    }

    LaunchedEffect(state.savedTaskId) {
        state.savedTaskId?.let { id ->
            viewModel.consumeSavedTask()
            onTaskCreated(id)
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.voice_title)) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(
                            Icons.AutoMirrored.Filled.ArrowBack,
                            contentDescription = stringResource(R.string.action_back),
                        )
                    }
                },
            )
        },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp)
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(16.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text(
                text = stringResource(R.string.voice_privacy_note),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )

            Surface(
                modifier = Modifier
                    .size(96.dp)
                    .testTag(VoiceCaptureTestTags.MIC_BUTTON),
                shape = CircleShape,
                color = if (state.listening) MaterialTheme.colorScheme.primary
                        else MaterialTheme.colorScheme.secondaryContainer,
                onClick = {
                    if (!SpeechRecognizer.isRecognitionAvailable(context)) {
                        viewModel.onRecognizerUnavailable()
                        return@Surface
                    }
                    viewModel.onListeningStart()
                    val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
                        putExtra(
                            RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                            RecognizerIntent.LANGUAGE_MODEL_FREE_FORM,
                        )
                        putExtra(
                            RecognizerIntent.EXTRA_PROMPT,
                            context.getString(R.string.voice_prompt),
                        )
                    }
                    runCatching { launcher.launch(intent) }
                        .onFailure { viewModel.onRecognizerUnavailable() }
                },
            ) {
                Column(
                    modifier = Modifier.fillMaxSize(),
                    verticalArrangement = Arrangement.Center,
                    horizontalAlignment = Alignment.CenterHorizontally,
                ) {
                    Icon(
                        imageVector = Icons.Filled.Mic,
                        contentDescription = stringResource(R.string.voice_start),
                        modifier = Modifier.size(40.dp),
                    )
                }
            }

            Text(
                text = if (state.listening) stringResource(R.string.voice_listening)
                       else stringResource(R.string.voice_tap_to_speak),
                style = MaterialTheme.typography.titleSmall,
            )

            state.error?.let { err ->
                Text(
                    text = err,
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.error,
                )
            }

            if (state.transcript.isNotBlank()) {
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.surfaceVariant,
                    ),
                ) {
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(16.dp),
                        verticalArrangement = Arrangement.spacedBy(12.dp),
                    ) {
                        Text(
                            text = state.transcript,
                            style = MaterialTheme.typography.bodyLarge,
                            modifier = Modifier.testTag(VoiceCaptureTestTags.TRANSCRIPT),
                        )
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(8.dp),
                        ) {
                            Button(
                                onClick = viewModel::saveAsTask,
                                enabled = !state.saving,
                                modifier = Modifier
                                    .weight(1f)
                                    .testTag(VoiceCaptureTestTags.SAVE_TASK),
                            ) {
                                Text(stringResource(R.string.voice_save_task))
                            }
                            OutlinedButton(
                                onClick = viewModel::clearTranscript,
                                enabled = !state.saving,
                                modifier = Modifier.weight(1f),
                            ) {
                                Text(stringResource(R.string.voice_clear))
                            }
                        }
                    }
                }
            }
        }
    }
}
