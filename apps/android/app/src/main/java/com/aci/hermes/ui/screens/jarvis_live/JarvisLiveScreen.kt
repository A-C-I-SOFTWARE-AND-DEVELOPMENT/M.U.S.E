package com.aci.hermes.ui.screens.jarvis_live

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.PowerSettingsNew
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.aci.hermes.ui.jarvis.JarvisIconColors
import com.aci.hermes.ui.jarvis.JarvisLiveStatus
import com.aci.hermes.ui.jarvis.JarvisLivingAvatar
import com.aci.hermes.ui.jarvis.JarvisPalette
import com.aci.hermes.ui.jarvis.rememberReducedMotion

object JarvisLiveTestTags {
    const val ROOT = "jarvis_live_root"
    const val STATUS_PILL = "jarvis_live_status_pill"
    const val STATUS_LINE = "jarvis_live_status_line"
    const val DETAIL_LINE = "jarvis_live_detail_line"
    const val PROGRESS_LABEL = "jarvis_live_progress_label"
    const val AVATAR = "jarvis_live_avatar"
    const val APPROVE_BUTTON = "jarvis_live_approve"
    const val EMERGENCY_BUTTON = "jarvis_live_emergency"
    const val ASK_INPUT = "jarvis_live_ask_input"
    const val SEND_BUTTON = "jarvis_live_send"
}

/**
 * Flagship Jarvis presence screen. Always shows:
 *  - a status pill naming the current state
 *  - the living avatar in the center
 *  - a one-line status sentence under the avatar
 *  - optional detail and progress lines
 *  - approval / emergency buttons when relevant
 *  - a minimal "Ask Jarvis" input row
 *
 * Producer wiring (chat stream, worker phase) flows into
 * [JarvisLiveViewModel] from later branches. This screen treats those
 * signals as ambient — if they are present, the avatar reflects them
 * immediately.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun JarvisLiveScreen(
    viewModel: JarvisLiveViewModel,
    onOpenSettings: () -> Unit,
) {
    val state by viewModel.state.collectAsState()
    val reducedMotion = rememberReducedMotion()
    val status = remember(state, reducedMotion) { viewModel.projectStatus(reducedMotion) }
    val snackbarHostState = remember { SnackbarHostState() }

    var confirmEmergency by remember { mutableStateOf(false) }

    LaunchedEffect(state.snackbar) {
        state.snackbar?.let {
            snackbarHostState.showSnackbar(it)
            viewModel.consumeSnackbar()
        }
    }

    LaunchedEffect(Unit) { viewModel.refreshServiceStatus() }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Jarvis") },
                actions = {
                    IconButton(onClick = onOpenSettings) {
                        Icon(Icons.Default.Settings, contentDescription = "Settings")
                    }
                },
            )
        },
        snackbarHost = { SnackbarHost(snackbarHostState) },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 16.dp)
                .testTag(JarvisLiveTestTags.ROOT),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Spacer(Modifier.height(8.dp))
            StatusPill(status)
            Spacer(Modifier.height(24.dp))
            JarvisLivingAvatar(
                status = status,
                size = 168.dp,
                modifier = Modifier.testTag(JarvisLiveTestTags.AVATAR),
            )
            Spacer(Modifier.height(20.dp))
            Text(
                text = status.statusLine,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
                modifier = Modifier.testTag(JarvisLiveTestTags.STATUS_LINE),
            )
            status.detailLine?.let { detail ->
                Spacer(Modifier.height(4.dp))
                Text(
                    text = detail,
                    style = MaterialTheme.typography.bodyMedium,
                    modifier = Modifier
                        .alpha(0.75f)
                        .testTag(JarvisLiveTestTags.DETAIL_LINE),
                )
            }
            status.progressLabel?.let { progress ->
                Spacer(Modifier.height(2.dp))
                Text(
                    text = progress,
                    style = MaterialTheme.typography.labelSmall,
                    modifier = Modifier
                        .alpha(0.6f)
                        .testTag(JarvisLiveTestTags.PROGRESS_LABEL),
                )
            }
            Spacer(Modifier.height(20.dp))
            AttentionButtons(
                status = status,
                onApprove = viewModel::acknowledgeApproval,
                onEmergency = { confirmEmergency = true },
            )
            Spacer(Modifier.weight(1f))
            AskJarvisBar(
                draft = state.draft,
                onDraftChange = viewModel::updateDraft,
                onSend = viewModel::sendDraft,
            )
            Spacer(Modifier.height(12.dp))
        }
    }

    if (confirmEmergency) {
        AlertDialog(
            onDismissRequest = { confirmEmergency = false },
            title = { Text("Stop Jarvis?") },
            text = {
                Text(
                    "Activating emergency stop halts all in-flight work and pauses approvals.",
                )
            },
            confirmButton = {
                Button(
                    onClick = {
                        confirmEmergency = false
                        viewModel.setEmergencyStop(true)
                        viewModel.triggerEmergencyStop()
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = JarvisPalette.Red),
                ) { Text("Emergency stop") }
            },
            dismissButton = {
                Button(onClick = { confirmEmergency = false }) { Text("Cancel") }
            },
        )
    }
}

@Composable
private fun StatusPill(status: JarvisLiveStatus) {
    val appearance = JarvisIconColors.appearanceFor(status.iconState)
    Surface(
        color = appearance.haloColor,
        contentColor = Color.White,
        shape = RoundedCornerShape(percent = 50),
        modifier = Modifier
            .widthIn(min = 96.dp)
            .testTag(JarvisLiveTestTags.STATUS_PILL),
    ) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier.padding(horizontal = 14.dp, vertical = 6.dp),
        ) {
            Box(
                Modifier
                    .size(8.dp)
                    .background(appearance.ringColor, RoundedCornerShape(50)),
            )
            Spacer(Modifier.size(8.dp))
            Text(
                text = status.statusPillText,
                style = MaterialTheme.typography.labelLarge,
                fontWeight = FontWeight.Bold,
                color = appearance.ringColor,
            )
        }
    }
}

@Composable
private fun AttentionButtons(
    status: JarvisLiveStatus,
    onApprove: () -> Unit,
    onEmergency: () -> Unit,
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(12.dp, Alignment.CenterHorizontally),
    ) {
        if (status.shouldShowApprovalButton) {
            Button(
                onClick = onApprove,
                colors = ButtonDefaults.buttonColors(
                    containerColor = JarvisPalette.Gold,
                    contentColor = Color.Black,
                ),
                modifier = Modifier.testTag(JarvisLiveTestTags.APPROVE_BUTTON),
            ) { Text("Review approval") }
        }
        if (status.shouldShowEmergencyButton) {
            Button(
                onClick = onEmergency,
                colors = ButtonDefaults.buttonColors(
                    containerColor = JarvisPalette.Red,
                    contentColor = Color.White,
                ),
                modifier = Modifier.testTag(JarvisLiveTestTags.EMERGENCY_BUTTON),
            ) {
                Icon(Icons.Default.PowerSettingsNew, contentDescription = null)
                Spacer(Modifier.size(6.dp))
                Text("Stop")
            }
        }
    }
}

@Composable
private fun AskJarvisBar(
    draft: String,
    onDraftChange: (String) -> Unit,
    onSend: () -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 4.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        OutlinedTextField(
            value = draft,
            onValueChange = onDraftChange,
            placeholder = { Text("Ask Jarvis…") },
            singleLine = true,
            modifier = Modifier
                .weight(1f)
                .testTag(JarvisLiveTestTags.ASK_INPUT),
        )
        Spacer(Modifier.size(8.dp))
        IconButton(
            onClick = onSend,
            enabled = draft.isNotBlank(),
            modifier = Modifier.testTag(JarvisLiveTestTags.SEND_BUTTON),
        ) {
            Icon(Icons.AutoMirrored.Filled.Send, contentDescription = "Send")
        }
    }
}
