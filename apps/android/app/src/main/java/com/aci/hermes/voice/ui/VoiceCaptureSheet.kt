package com.aci.hermes.voice.ui

import android.Manifest
import android.app.Activity
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Cancel
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.AlertDialogDefaults
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import com.aci.hermes.R
import com.aci.hermes.voice.VoiceCaptureStep
import com.aci.hermes.voice.VoiceCaptureUiState
import com.aci.hermes.voice.VoiceCaptureViewModel
import com.aci.hermes.voice.VoiceCommandCategory

/**
 * Modal sheet that walks the user through the JARVIS Prime voice
 * capture flow: education → permission → listening → transcript →
 * route to chat/task. Lives on top of the orchestrator dashboard so
 * a transcript can become either a chat draft or a draft task.
 *
 * The sheet is the **only** place in the app that ever asks for
 * RECORD_AUDIO. It does not request the permission until the user
 * taps "Allow microphone" on the education panel.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun VoiceCaptureSheet(
    viewModel: VoiceCaptureViewModel,
    onMessage: (String) -> Unit,
    onDismiss: () -> Unit,
) {
    val state by viewModel.state.collectAsState()
    if (state.step is VoiceCaptureStep.Idle) return

    val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    val context = LocalContext.current

    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) { granted ->
        val activity = context as? Activity
        val permanentlyDenied = if (!granted && activity != null) {
            !activity.shouldShowRequestPermissionRationale(Manifest.permission.RECORD_AUDIO)
        } else {
            false
        }
        viewModel.onPermissionResult(granted = granted, permanentlyDenied = permanentlyDenied)
    }

    LaunchedEffect(state.step) {
        if (state.step is VoiceCaptureStep.RequestingPermission) {
            val already = ContextCompat.checkSelfPermission(
                context,
                Manifest.permission.RECORD_AUDIO,
            ) == PackageManager.PERMISSION_GRANTED
            if (already) {
                viewModel.onPermissionResult(granted = true)
            } else {
                permissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
            }
        }
    }

    LaunchedEffect(state.message) {
        state.message?.let {
            onMessage(it)
            viewModel.consumeMessage()
        }
    }

    LaunchedEffect(state.dismiss) {
        if (state.dismiss) {
            viewModel.consumeDismiss()
            onDismiss()
        }
    }

    ModalBottomSheet(
        onDismissRequest = { viewModel.cancel() },
        sheetState = sheetState,
    ) {
        VoiceCaptureSheetContent(
            state = state,
            onAcknowledge = viewModel::acknowledgeEducation,
            onRetryPermission = { permissionLauncher.launch(Manifest.permission.RECORD_AUDIO) },
            onStop = viewModel::stop,
            onCancel = viewModel::cancel,
            onEditTranscript = viewModel::editTranscript,
            onManualTranscriptChange = viewModel::setManualTranscript,
            onAcceptManualTranscript = viewModel::acceptCapturedTranscript,
            onSendToChat = viewModel::sendToChat,
            onCreateTask = viewModel::createTask,
        )
    }
}

@Composable
private fun VoiceCaptureSheetContent(
    state: VoiceCaptureUiState,
    onAcknowledge: () -> Unit,
    onRetryPermission: () -> Unit,
    onStop: () -> Unit,
    onCancel: () -> Unit,
    onEditTranscript: (String) -> Unit,
    onManualTranscriptChange: (String) -> Unit,
    onAcceptManualTranscript: () -> Unit,
    onSendToChat: () -> Unit,
    onCreateTask: () -> Unit,
) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 24.dp, vertical = 16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Header(state.step)
        when (val step = state.step) {
            VoiceCaptureStep.Idle -> Unit
            VoiceCaptureStep.Education -> EducationPanel(
                sttAvailable = state.sttAvailable,
                onAllow = onAcknowledge,
                onCancel = onCancel,
            )
            VoiceCaptureStep.RequestingPermission -> RequestingPermissionPanel(onCancel = onCancel)
            VoiceCaptureStep.PermissionDenied -> PermissionDeniedPanel(
                permanentlyDenied = state.permissionPermanentlyDenied,
                onRetry = onRetryPermission,
                onCancel = onCancel,
            )
            VoiceCaptureStep.Listening -> ListeningPanel(
                partial = state.partialTranscript,
                onStop = onStop,
                onCancel = onCancel,
            )
            VoiceCaptureStep.Captured -> CapturedPanel(
                transcript = state.finalTranscript,
                approvalRequired = state.classification?.category == VoiceCommandCategory.APPROVAL_REQUIRED,
                approvalReason = state.classification?.reason,
                matchedTrigger = state.classification?.matchedTrigger,
                onEdit = onEditTranscript,
                onSendToChat = onSendToChat,
                onCreateTask = onCreateTask,
                onCancel = onCancel,
            )
            VoiceCaptureStep.ManualEntry -> ManualEntryPanel(
                transcript = state.finalTranscript,
                onChange = onManualTranscriptChange,
                onAccept = onAcceptManualTranscript,
                onCancel = onCancel,
            )
            is VoiceCaptureStep.Error -> ErrorPanel(
                message = step.message,
                onRetry = onAcknowledge,
                onCancel = onCancel,
            )
        }
    }
}

@Composable
private fun Header(step: VoiceCaptureStep) {
    val title = when (step) {
        VoiceCaptureStep.Education -> stringResource(R.string.voice_education_title)
        VoiceCaptureStep.RequestingPermission -> stringResource(R.string.voice_requesting_permission_title)
        VoiceCaptureStep.PermissionDenied -> stringResource(R.string.voice_permission_denied_title)
        VoiceCaptureStep.Listening -> stringResource(R.string.voice_listening_title)
        VoiceCaptureStep.Captured -> stringResource(R.string.voice_captured_title)
        VoiceCaptureStep.ManualEntry -> stringResource(R.string.voice_manual_entry_title)
        is VoiceCaptureStep.Error -> stringResource(R.string.voice_error_title)
        VoiceCaptureStep.Idle -> ""
    }
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Icon(imageVector = Icons.Default.Mic, contentDescription = null)
        Text(text = title, style = MaterialTheme.typography.titleLarge)
    }
}

@Composable
private fun EducationPanel(
    sttAvailable: Boolean,
    onAllow: () -> Unit,
    onCancel: () -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(stringResource(R.string.voice_education_body), style = MaterialTheme.typography.bodyMedium)
        Text(
            text = stringResource(R.string.voice_education_invariants),
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        if (!sttAvailable) {
            Text(
                text = stringResource(R.string.voice_education_no_stt),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.error,
            )
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = onAllow) {
                Text(stringResource(R.string.voice_allow_microphone))
            }
            OutlinedButton(onClick = onCancel) {
                Text(stringResource(R.string.action_cancel))
            }
        }
    }
}

@Composable
private fun RequestingPermissionPanel(onCancel: () -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(stringResource(R.string.voice_requesting_permission_body))
        OutlinedButton(onClick = onCancel) { Text(stringResource(R.string.action_cancel)) }
    }
}

@Composable
private fun PermissionDeniedPanel(
    permanentlyDenied: Boolean,
    onRetry: () -> Unit,
    onCancel: () -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(
            text = if (permanentlyDenied) {
                stringResource(R.string.voice_permission_denied_permanent)
            } else {
                stringResource(R.string.voice_permission_denied_body)
            },
            style = MaterialTheme.typography.bodyMedium,
        )
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            if (!permanentlyDenied) {
                Button(onClick = onRetry) { Text(stringResource(R.string.voice_retry_permission)) }
            }
            OutlinedButton(onClick = onCancel) { Text(stringResource(R.string.action_cancel)) }
        }
    }
}

@Composable
private fun ListeningPanel(
    partial: String,
    onStop: () -> Unit,
    onCancel: () -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        ListeningWaveform()
        Text(
            text = partial.ifBlank { stringResource(R.string.voice_listening_hint) },
            style = MaterialTheme.typography.bodyMedium,
        )
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = onStop) {
                Icon(imageVector = Icons.Default.Stop, contentDescription = null)
                Text(stringResource(R.string.voice_stop))
            }
            OutlinedButton(onClick = onCancel) {
                Icon(imageVector = Icons.Default.Cancel, contentDescription = null)
                Text(stringResource(R.string.action_cancel))
            }
        }
    }
}

@Composable
private fun CapturedPanel(
    transcript: String,
    approvalRequired: Boolean,
    approvalReason: String?,
    matchedTrigger: String?,
    onEdit: (String) -> Unit,
    onSendToChat: () -> Unit,
    onCreateTask: () -> Unit,
    onCancel: () -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        OutlinedTextField(
            value = transcript,
            onValueChange = onEdit,
            label = { Text(stringResource(R.string.voice_transcript_label)) },
            modifier = Modifier.fillMaxWidth(),
            minLines = 3,
        )
        if (approvalRequired) {
            ApprovalBanner(reason = approvalReason, matchedTrigger = matchedTrigger)
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = onSendToChat) {
                Icon(imageVector = Icons.Default.Check, contentDescription = null)
                Text(stringResource(R.string.voice_send_to_chat))
            }
            OutlinedButton(onClick = onCreateTask) {
                Icon(imageVector = Icons.Default.Edit, contentDescription = null)
                Text(stringResource(R.string.voice_create_task))
            }
            TextButton(onClick = onCancel) {
                Text(stringResource(R.string.action_cancel))
            }
        }
    }
}

@Composable
private fun ApprovalBanner(reason: String?, matchedTrigger: String?) {
    Card(
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.errorContainer,
        ),
        shape = RoundedCornerShape(12.dp),
    ) {
        Row(
            verticalAlignment = Alignment.Top,
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            modifier = Modifier.padding(12.dp),
        ) {
            Icon(
                imageVector = Icons.Default.Warning,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.onErrorContainer,
            )
            Column {
                Text(
                    text = stringResource(R.string.voice_approval_banner_title),
                    style = MaterialTheme.typography.titleSmall,
                    color = MaterialTheme.colorScheme.onErrorContainer,
                )
                val detail = buildString {
                    append(stringResource(R.string.voice_approval_banner_body))
                    if (!matchedTrigger.isNullOrBlank()) {
                        append(" (matched: \"$matchedTrigger\")")
                    }
                    if (!reason.isNullOrBlank()) {
                        append(" — $reason")
                    }
                }
                Text(
                    text = detail,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onErrorContainer,
                )
            }
        }
    }
}

@Composable
private fun ManualEntryPanel(
    transcript: String,
    onChange: (String) -> Unit,
    onAccept: () -> Unit,
    onCancel: () -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text(
            text = stringResource(R.string.voice_manual_entry_body),
            style = MaterialTheme.typography.bodyMedium,
        )
        OutlinedTextField(
            value = transcript,
            onValueChange = onChange,
            label = { Text(stringResource(R.string.voice_transcript_label)) },
            modifier = Modifier.fillMaxWidth(),
            minLines = 3,
        )
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = onAccept, enabled = transcript.isNotBlank()) {
                Text(stringResource(R.string.voice_accept_transcript))
            }
            OutlinedButton(onClick = onCancel) { Text(stringResource(R.string.action_cancel)) }
        }
    }
}

@Composable
private fun ErrorPanel(message: String, onRetry: () -> Unit, onCancel: () -> Unit) {
    Surface(
        color = AlertDialogDefaults.containerColor,
        shape = RoundedCornerShape(12.dp),
    ) {
        Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(message, style = MaterialTheme.typography.bodyMedium)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(
                    onClick = onRetry,
                    colors = ButtonDefaults.buttonColors(),
                ) { Text(stringResource(R.string.voice_retry)) }
                OutlinedButton(onClick = onCancel) { Text(stringResource(R.string.action_cancel)) }
            }
        }
    }
}
