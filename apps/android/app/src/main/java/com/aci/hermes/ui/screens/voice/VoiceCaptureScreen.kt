package com.aci.hermes.ui.screens.voice

import android.content.Intent
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
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
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.aci.hermes.R

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun VoiceCaptureScreen(
    viewModel: VoiceCaptureViewModel,
    onBack: () -> Unit,
    onTaskCreated: (String) -> Unit,
) {
    val state by viewModel.state.collectAsState()
    val context = LocalContext.current

    LaunchedEffect(Unit) {
        viewModel.setRecognizerAvailable(SpeechRecognizer.isRecognitionAvailable(context))
    }

    LaunchedEffect(state.createdTaskId) {
        state.createdTaskId?.let {
            onTaskCreated(it)
            viewModel.consumeCreatedTask()
        }
    }

    val launcher = rememberLauncherForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { result ->
        viewModel.setListening(false)
        if (result.resultCode == android.app.Activity.RESULT_OK) {
            val text = result.data
                ?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)
                ?.firstOrNull()
                .orEmpty()
            if (text.isNotEmpty()) viewModel.onTranscript(text)
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.voice_title)) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = stringResource(R.string.action_back))
                    }
                },
            )
        },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 16.dp, vertical = 12.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            if (state.permissionEducationShown) {
                Card(
                    colors = CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.tertiaryContainer,
                    ),
                ) {
                    Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        Text(
                            stringResource(R.string.voice_permission_education),
                            style = MaterialTheme.typography.bodyMedium,
                        )
                        OutlinedButton(onClick = { viewModel.dismissEducation() }) {
                            Text(stringResource(R.string.action_ok))
                        }
                    }
                }
            }
            Text(
                stringResource(R.string.voice_hint),
                style = MaterialTheme.typography.bodySmall,
            )
            if (!state.recognizerAvailable) {
                Text(
                    stringResource(R.string.voice_recognizer_unavailable),
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.error,
                )
            }
            Button(
                onClick = {
                    val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
                        putExtra(
                            RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                            RecognizerIntent.LANGUAGE_MODEL_FREE_FORM,
                        )
                        putExtra(RecognizerIntent.EXTRA_PROMPT, context.getString(R.string.voice_title))
                    }
                    viewModel.setListening(true)
                    runCatching { launcher.launch(intent) }
                        .onFailure { viewModel.setListening(false) }
                },
                enabled = state.recognizerAvailable && !state.listening,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Icon(Icons.Default.Mic, contentDescription = null)
                Text("  " + stringResource(R.string.voice_start))
            }
            if (state.redacted.isNotBlank()) {
                Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)) {
                    Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        Text(state.redacted, style = MaterialTheme.typography.bodyMedium)
                        if (state.redactedFields.isNotEmpty()) {
                            Text(
                                "redacted: ${state.redactedFields.joinToString()}",
                                style = MaterialTheme.typography.labelSmall,
                            )
                        }
                        Button(onClick = viewModel::saveAsTask, modifier = Modifier.fillMaxWidth()) {
                            Text(stringResource(R.string.voice_to_task))
                        }
                    }
                }
            }
        }
    }
}
