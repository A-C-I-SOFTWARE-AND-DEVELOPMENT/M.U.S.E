package com.aci.hermes.ui.screens.chat

import android.app.Activity
import android.content.Intent
import android.speech.RecognizerIntent
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.background
import androidx.compose.foundation.border
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
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ContentCopy
import androidx.compose.material.icons.filled.ExpandLess
import androidx.compose.material.icons.filled.ExpandMore
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.AssistChip
import androidx.compose.material3.AssistChipDefaults
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.aci.hermes.data.jarvis.JarvisChatMessage
import com.aci.hermes.data.jarvis.JarvisInlineCard
import com.aci.hermes.data.jarvis.JarvisTone
import com.aci.hermes.ui.components.AskJarvisBar
import com.aci.hermes.ui.theme.JarvisAmber
import com.aci.hermes.ui.theme.JarvisCrimson
import com.aci.hermes.ui.theme.JarvisCyan
import com.aci.hermes.ui.theme.JarvisGold
import com.aci.hermes.ui.theme.JarvisInkDeep
import com.aci.hermes.ui.theme.JarvisInkEdge
import com.aci.hermes.ui.theme.JarvisInkNight
import com.aci.hermes.ui.theme.JarvisInkRaised
import com.aci.hermes.ui.theme.JarvisJade
import com.aci.hermes.ui.theme.JarvisSignal
import com.aci.hermes.ui.theme.JarvisSignalDim
import com.aci.hermes.ui.theme.JarvisSignalMute
import com.aci.hermes.ui.theme.JarvisTokens

/**
 * The Jarvis Prime conversational chat surface — the "Chat" shell tab.
 *
 * Rendered inside [com.aci.hermes.ui.navigation.JarvisShell], so it takes
 * the shell's [paddingValues] and does NOT own a Scaffold or top bar. It
 * lays out a scrolling transcript above an [AskJarvisBar] input row, with
 * a Stop control surfaced while a response is streaming.
 *
 * Conversation engine surfaces (driven by [JarvisChatViewModel]):
 *  - conversational user / Jarvis bubbles, mobile-first short replies
 *  - thinking + working indicators
 *  - expandable "detail" for deep answers
 *  - inline Task / Approval / Serious / Critical cards
 *  - gateway error bubble with retry
 *  - voice capture, copy response, stop/abort
 */
@Composable
fun JarvisChatScreen(
    viewModel: JarvisChatViewModel,
    paddingValues: PaddingValues,
) {
    val state by viewModel.state.collectAsState()
    val snackbarHostState = remember { SnackbarHostState() }
    val listState = rememberLazyListState()

    val voiceLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.StartActivityForResult(),
    ) { result ->
        if (result.resultCode == Activity.RESULT_OK) {
            val spoken = result.data
                ?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)
                ?.firstOrNull()
                .orEmpty()
            if (spoken.isNotBlank()) viewModel.onVoiceCaptureResult(spoken)
            else viewModel.onVoiceCaptureCancel()
        } else {
            viewModel.onVoiceCaptureCancel()
        }
    }

    LaunchedEffect(state.snackbar) {
        state.snackbar?.let {
            snackbarHostState.showSnackbar(it)
            viewModel.consumeSnackbar()
        }
    }

    LaunchedEffect(state.messages.size) {
        if (state.messages.isNotEmpty()) {
            listState.animateScrollToItem(state.messages.lastIndex)
        }
    }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(JarvisInkNight)
            .padding(paddingValues),
    ) {
        Column(modifier = Modifier.fillMaxSize()) {
            if (state.mockMode) {
                MockModeBanner()
            }
            LazyColumn(
                state = listState,
                modifier = Modifier
                    .weight(1f)
                    .fillMaxWidth()
                    .padding(horizontal = JarvisTokens.SpaceMd),
                verticalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm),
                contentPadding = PaddingValues(vertical = JarvisTokens.SpaceMd),
            ) {
                items(state.messages, key = { it.id }) { msg ->
                    MessageRow(
                        message = msg,
                        expanded = msg.id in state.expanded,
                        approved = state.approved,
                        held = state.held,
                        ackedCritical = state.ackedCritical,
                        promotedTasks = state.promotedTasks,
                        onToggleExpand = { viewModel.toggleExpanded(msg.id) },
                        onCopy = { viewModel.copyMessage(msg.id) },
                        onPromoteTask = { card -> viewModel.promoteInlineTask(msg.id, card) },
                        onApprove = { card -> viewModel.approveInline(msg.id, card) },
                        onHold = { card -> viewModel.holdInline(msg.id, card) },
                        onAckCritical = { card, typed -> viewModel.ackCritical(msg.id, card, typed) },
                        onRetry = viewModel::retry,
                    )
                }
            }

            ChatInputArea(
                draft = state.draft,
                responding = state.responding,
                voiceCapturing = state.voiceCapturing,
                onDraftChange = viewModel::onDraftChange,
                onSend = viewModel::send,
                onStop = viewModel::stop,
                onMicToggle = {
                    if (state.voiceCapturing) {
                        viewModel.onVoiceCaptureCancel()
                        return@ChatInputArea
                    }
                    val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
                        putExtra(
                            RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                            RecognizerIntent.LANGUAGE_MODEL_FREE_FORM,
                        )
                        putExtra(RecognizerIntent.EXTRA_PROMPT, "Speak to Jarvis Prime")
                    }
                    viewModel.onVoiceCaptureStart()
                    runCatching { voiceLauncher.launch(intent) }
                        .onFailure { viewModel.onVoiceCaptureCancel() }
                },
            )
        }

        SnackbarHost(
            hostState = snackbarHostState,
            modifier = Modifier.align(Alignment.BottomCenter),
        )
    }
}

@Composable
private fun MockModeBanner() {
    Surface(
        color = JarvisInkRaised,
        modifier = Modifier.fillMaxWidth(),
    ) {
        Text(
            text = "Mock mode — simulated replies, nothing touches your accounts.",
            style = MaterialTheme.typography.labelSmall,
            color = JarvisSignalMute,
            modifier = Modifier.padding(horizontal = JarvisTokens.SpaceMd, vertical = JarvisTokens.SpaceXs),
        )
    }
}

@Composable
private fun MessageRow(
    message: JarvisChatMessage,
    expanded: Boolean,
    approved: Set<String>,
    held: Set<String>,
    ackedCritical: Set<String>,
    promotedTasks: Set<String>,
    onToggleExpand: () -> Unit,
    onCopy: () -> Unit,
    onPromoteTask: (JarvisInlineCard.Task) -> Unit,
    onApprove: (JarvisInlineCard.Approval) -> Unit,
    onHold: (JarvisInlineCard.Approval) -> Unit,
    onAckCritical: (JarvisInlineCard.Critical, String) -> Unit,
    onRetry: () -> Unit,
) {
    when (message) {
        is JarvisChatMessage.User -> UserBubble(message)
        is JarvisChatMessage.Jarvis -> JarvisBubble(
            message = message,
            expanded = expanded,
            approved = approved,
            held = held,
            ackedCritical = ackedCritical,
            promotedTasks = promotedTasks,
            onToggleExpand = onToggleExpand,
            onCopy = onCopy,
            onPromoteTask = onPromoteTask,
            onApprove = onApprove,
            onHold = onHold,
            onAckCritical = onAckCritical,
        )
        is JarvisChatMessage.Thinking -> IndicatorBubble("thinking…")
        is JarvisChatMessage.Working -> IndicatorBubble(message.label)
        is JarvisChatMessage.Error -> ErrorBubble(message, onRetry)
    }
}

@Composable
private fun UserBubble(message: JarvisChatMessage.User) {
    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
        Surface(
            color = JarvisGold,
            shape = RoundedCornerShape(topStart = 16.dp, topEnd = 16.dp, bottomEnd = 4.dp, bottomStart = 16.dp),
            modifier = Modifier.widthIn(max = 320.dp),
        ) {
            Text(
                text = message.text,
                color = JarvisInkDeep,
                modifier = Modifier.padding(horizontal = JarvisTokens.SpaceMd, vertical = JarvisTokens.SpaceSm),
                style = MaterialTheme.typography.bodyMedium,
            )
        }
    }
}

@Composable
private fun JarvisBubble(
    message: JarvisChatMessage.Jarvis,
    expanded: Boolean,
    approved: Set<String>,
    held: Set<String>,
    ackedCritical: Set<String>,
    promotedTasks: Set<String>,
    onToggleExpand: () -> Unit,
    onCopy: () -> Unit,
    onPromoteTask: (JarvisInlineCard.Task) -> Unit,
    onApprove: (JarvisInlineCard.Approval) -> Unit,
    onHold: (JarvisInlineCard.Approval) -> Unit,
    onAckCritical: (JarvisInlineCard.Critical, String) -> Unit,
) {
    val accent = when (message.tone) {
        JarvisTone.NORMAL -> JarvisInkEdge
        JarvisTone.SERIOUS -> JarvisAmber
        JarvisTone.CRITICAL -> JarvisCrimson
    }
    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.Start) {
        Surface(
            color = JarvisInkDeep,
            shape = RoundedCornerShape(topStart = 16.dp, topEnd = 16.dp, bottomEnd = 16.dp, bottomStart = 4.dp),
            modifier = Modifier
                .widthIn(max = 340.dp)
                .border(JarvisTokens.BorderHairline, accent, RoundedCornerShape(16.dp)),
        ) {
            Column(
                modifier = Modifier.padding(JarvisTokens.SpaceMd),
                verticalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm),
            ) {
                if (message.body.isNotEmpty()) {
                    Text(message.body, style = MaterialTheme.typography.bodyMedium, color = JarvisSignal)
                }
                if (message.streaming && message.body.isEmpty()) {
                    Text("…", style = MaterialTheme.typography.bodyMedium, color = JarvisSignalDim)
                }
                if (message.aborted) {
                    Text(
                        text = "(stopped)",
                        style = MaterialTheme.typography.labelSmall,
                        fontStyle = FontStyle.Italic,
                        color = JarvisSignalMute,
                    )
                }
                if (!message.detail.isNullOrBlank()) {
                    AssistChip(
                        onClick = onToggleExpand,
                        label = { Text(if (expanded) "Hide detail" else "Show detail") },
                        leadingIcon = {
                            Icon(
                                if (expanded) Icons.Filled.ExpandLess else Icons.Filled.ExpandMore,
                                contentDescription = null,
                            )
                        },
                        colors = AssistChipDefaults.assistChipColors(
                            labelColor = JarvisCyan,
                            leadingIconContentColor = JarvisCyan,
                        ),
                    )
                    AnimatedVisibility(visible = expanded) {
                        Column {
                            Spacer(Modifier.height(JarvisTokens.SpaceXs))
                            Text(
                                text = message.detail,
                                style = MaterialTheme.typography.bodySmall,
                                color = JarvisSignalDim,
                            )
                        }
                    }
                }
                message.inline.forEach { card ->
                    InlineCardView(
                        messageId = message.id,
                        card = card,
                        promotedTasks = promotedTasks,
                        approved = approved,
                        held = held,
                        ackedCritical = ackedCritical,
                        onPromoteTask = onPromoteTask,
                        onApprove = onApprove,
                        onHold = onHold,
                        onAckCritical = onAckCritical,
                    )
                }
                if (!message.streaming && message.body.isNotEmpty()) {
                    TextButton(onClick = onCopy, contentPadding = PaddingValues(0.dp)) {
                        Icon(Icons.Filled.ContentCopy, contentDescription = null, modifier = Modifier.size(16.dp), tint = JarvisSignalMute)
                        Spacer(Modifier.size(JarvisTokens.SpaceXs))
                        Text("Copy", style = MaterialTheme.typography.labelSmall, color = JarvisSignalMute)
                    }
                }
            }
        }
    }
}

@Composable
private fun IndicatorBubble(label: String) {
    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.Start) {
        Surface(color = JarvisInkDeep, shape = RoundedCornerShape(16.dp)) {
            Row(
                modifier = Modifier.padding(horizontal = JarvisTokens.SpaceMd, vertical = JarvisTokens.SpaceSm),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm),
            ) {
                CircularProgressIndicator(modifier = Modifier.size(14.dp), strokeWidth = 2.dp, color = JarvisCyan)
                Text(label, style = MaterialTheme.typography.bodySmall, color = JarvisSignalDim)
            }
        }
    }
}

@Composable
private fun ErrorBubble(message: JarvisChatMessage.Error, onRetry: () -> Unit) {
    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.Start) {
        Surface(
            color = JarvisInkDeep,
            shape = RoundedCornerShape(16.dp),
            modifier = Modifier
                .widthIn(max = 340.dp)
                .border(JarvisTokens.BorderHairline, JarvisCrimson, RoundedCornerShape(16.dp)),
        ) {
            Column(
                modifier = Modifier.padding(JarvisTokens.SpaceMd),
                verticalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm),
            ) {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceXs)) {
                    Icon(Icons.Filled.Warning, contentDescription = null, tint = JarvisCrimson)
                    Text("Gateway error", style = MaterialTheme.typography.titleSmall, color = JarvisCrimson)
                }
                Text(message.text, style = MaterialTheme.typography.bodyMedium, color = JarvisSignal)
                message.retryHint?.let {
                    Text(it, style = MaterialTheme.typography.bodySmall, color = JarvisSignalMute)
                }
                Button(
                    onClick = onRetry,
                    colors = ButtonDefaults.buttonColors(containerColor = JarvisGold, contentColor = JarvisInkDeep),
                ) {
                    Icon(Icons.Filled.Refresh, contentDescription = null)
                    Spacer(Modifier.size(JarvisTokens.SpaceXs))
                    Text("Retry")
                }
            }
        }
    }
}

@Composable
private fun InlineCardView(
    messageId: String,
    card: JarvisInlineCard,
    promotedTasks: Set<String>,
    approved: Set<String>,
    held: Set<String>,
    ackedCritical: Set<String>,
    onPromoteTask: (JarvisInlineCard.Task) -> Unit,
    onApprove: (JarvisInlineCard.Approval) -> Unit,
    onHold: (JarvisInlineCard.Approval) -> Unit,
    onAckCritical: (JarvisInlineCard.Critical, String) -> Unit,
) {
    when (card) {
        is JarvisInlineCard.Task -> TaskCardView(
            card = card,
            promoted = "$messageId/Task/${card.title}" in promotedTasks,
            onPromote = onPromoteTask,
        )
        is JarvisInlineCard.Approval -> ApprovalCardView(
            card = card,
            approved = approved.any { it.startsWith("$messageId/Approval") },
            held = held.any { it.startsWith("$messageId/Approval") },
            onApprove = onApprove,
            onHold = onHold,
        )
        is JarvisInlineCard.Serious -> SeriousCardView(card)
        is JarvisInlineCard.Critical -> CriticalCardView(
            card = card,
            acked = ackedCritical.any { it.startsWith("$messageId/Critical") },
            onAck = onAckCritical,
        )
    }
}

@Composable
private fun InlineCardFrame(
    accent: Color,
    content: @Composable androidx.compose.foundation.layout.ColumnScope.() -> Unit,
) {
    Surface(
        color = JarvisInkNight,
        shape = JarvisTokens.ShapeCard,
        modifier = Modifier
            .fillMaxWidth()
            .border(JarvisTokens.BorderHairline, accent, JarvisTokens.ShapeCard),
    ) {
        Column(
            modifier = Modifier.padding(JarvisTokens.SpaceMd),
            verticalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceXs),
            content = content,
        )
    }
}

@Composable
private fun TaskCardView(
    card: JarvisInlineCard.Task,
    promoted: Boolean,
    onPromote: (JarvisInlineCard.Task) -> Unit,
) {
    InlineCardFrame(JarvisCyan) {
        Text("Task draft", style = MaterialTheme.typography.labelMedium, color = JarvisCyan)
        Text(card.title, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold, color = JarvisSignal)
        Text(card.summary, style = MaterialTheme.typography.bodySmall, color = JarvisSignalDim)
        Row(horizontalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceXs)) {
            AssistChip(onClick = {}, label = { Text(card.taskType.name.lowercase()) })
            AssistChip(onClick = {}, label = { Text(card.targetTool.name.lowercase().replace('_', ' ')) })
        }
        if (promoted) {
            Text("Added to orchestrator", style = MaterialTheme.typography.labelSmall, color = JarvisJade)
        } else {
            Button(
                onClick = { onPromote(card) },
                colors = ButtonDefaults.buttonColors(containerColor = JarvisCyan, contentColor = JarvisInkDeep),
            ) { Text("Add to orchestrator") }
        }
    }
}

@Composable
private fun ApprovalCardView(
    card: JarvisInlineCard.Approval,
    approved: Boolean,
    held: Boolean,
    onApprove: (JarvisInlineCard.Approval) -> Unit,
    onHold: (JarvisInlineCard.Approval) -> Unit,
) {
    InlineCardFrame(JarvisGold) {
        Text("Approval required", style = MaterialTheme.typography.labelMedium, color = JarvisGold)
        Text(card.title, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold, color = JarvisSignal)
        Text(card.summary, style = MaterialTheme.typography.bodySmall, color = JarvisSignalDim)
        Text("Impact: ${card.impact}", style = MaterialTheme.typography.bodySmall, color = JarvisSignalMute)
        when {
            approved -> Text("Approved — proceeding.", color = JarvisJade, style = MaterialTheme.typography.labelMedium)
            held -> Text("Held — nothing executed.", color = JarvisSignalMute, style = MaterialTheme.typography.labelMedium)
            else -> Row(horizontalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm)) {
                Button(
                    onClick = { onApprove(card) },
                    colors = ButtonDefaults.buttonColors(containerColor = JarvisJade, contentColor = JarvisInkDeep),
                ) { Text(card.approveLabel) }
                OutlinedButton(onClick = { onHold(card) }) { Text(card.denyLabel) }
            }
        }
    }
}

@Composable
private fun SeriousCardView(card: JarvisInlineCard.Serious) {
    InlineCardFrame(JarvisAmber) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceXs)) {
            Icon(Icons.Filled.Warning, contentDescription = null, tint = JarvisAmber)
            Text("Serious", style = MaterialTheme.typography.labelMedium, color = JarvisAmber)
        }
        Text(card.title, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold, color = JarvisSignal)
        Text(card.summary, style = MaterialTheme.typography.bodySmall, color = JarvisSignalDim)
    }
}

@Composable
private fun CriticalCardView(
    card: JarvisInlineCard.Critical,
    acked: Boolean,
    onAck: (JarvisInlineCard.Critical, String) -> Unit,
) {
    var typed by remember(card) { mutableStateOf("") }
    InlineCardFrame(JarvisCrimson) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceXs)) {
            Icon(Icons.Filled.Warning, contentDescription = null, tint = JarvisCrimson)
            Text("CRITICAL", style = MaterialTheme.typography.labelMedium, color = JarvisCrimson, fontWeight = FontWeight.Bold)
        }
        Text(card.title, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold, color = JarvisSignal)
        Text(card.summary, style = MaterialTheme.typography.bodySmall, color = JarvisSignalDim)
        if (acked) {
            Text("Acknowledged.", style = MaterialTheme.typography.labelMedium, color = JarvisCrimson, fontWeight = FontWeight.SemiBold)
        } else {
            Text("Type the ack string to continue:", style = MaterialTheme.typography.bodySmall, color = JarvisSignalDim)
            Text("\"${card.requiredAck}\"", style = MaterialTheme.typography.labelSmall, fontStyle = FontStyle.Italic, color = JarvisSignalMute)
            OutlinedTextField(
                value = typed,
                onValueChange = { typed = it },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
            Button(
                onClick = { onAck(card, typed) },
                enabled = typed.isNotBlank(),
                colors = ButtonDefaults.buttonColors(containerColor = JarvisCrimson, contentColor = JarvisSignal),
            ) { Text("Acknowledge") }
        }
    }
}

@Composable
private fun ChatInputArea(
    draft: String,
    responding: Boolean,
    voiceCapturing: Boolean,
    onDraftChange: (String) -> Unit,
    onSend: () -> Unit,
    onStop: () -> Unit,
    onMicToggle: () -> Unit,
) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(JarvisTokens.SpaceMd),
        verticalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceXs),
    ) {
        if (responding) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm)) {
                Box(
                    modifier = Modifier
                        .size(8.dp)
                        .clip(CircleShape)
                        .background(JarvisCyan),
                )
                Text("Jarvis is responding…", style = MaterialTheme.typography.labelSmall, color = JarvisSignalMute)
                Spacer(Modifier.weight(1f))
                OutlinedButton(onClick = onStop) {
                    Icon(Icons.Filled.Stop, contentDescription = null, modifier = Modifier.size(16.dp))
                    Spacer(Modifier.size(JarvisTokens.SpaceXs))
                    Text("Stop")
                }
            }
        }
        AskJarvisBar(
            value = draft,
            onValueChange = onDraftChange,
            onSend = onSend,
            onMicToggle = onMicToggle,
            isListening = voiceCapturing,
            enabled = !responding,
        )
    }
}
