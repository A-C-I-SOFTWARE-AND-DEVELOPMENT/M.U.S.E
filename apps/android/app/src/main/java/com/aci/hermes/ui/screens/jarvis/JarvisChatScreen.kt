package com.aci.hermes.ui.screens.jarvis

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
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.ContentCopy
import androidx.compose.material.icons.filled.ExpandLess
import androidx.compose.material.icons.filled.ExpandMore
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Send
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledIconButton
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
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
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.aci.hermes.data.jarvis.JarvisChatMessage
import com.aci.hermes.data.jarvis.JarvisInlineCard
import com.aci.hermes.data.jarvis.JarvisTone

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun JarvisChatScreen(
    viewModel: JarvisChatViewModel,
    onBack: () -> Unit,
) {
    val state by viewModel.state.collectAsState()
    val snackbarHostState = remember { SnackbarHostState() }
    val listState = rememberLazyListState()
    val context = LocalContext.current

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

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text("Jarvis Prime")
                        Text(
                            state.gatewayLabel + if (state.mockMode) " · mock mode" else "",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                },
                actions = {
                    IconButton(onClick = { viewModel.clearTranscript() }) {
                        Icon(Icons.Default.Refresh, contentDescription = "Reset chat")
                    }
                },
            )
        },
        bottomBar = {
            ChatInputBar(
                draft = state.draft,
                responding = state.responding,
                voiceCapturing = state.voiceCapturing,
                onDraftChange = viewModel::onDraftChange,
                onSend = viewModel::send,
                onStop = viewModel::stop,
                onVoice = {
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
        },
        snackbarHost = { SnackbarHost(snackbarHostState) },
    ) { padding ->
        LazyColumn(
            state = listState,
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 12.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
            contentPadding = androidx.compose.foundation.layout.PaddingValues(vertical = 12.dp),
        ) {
            items(
                state.messages,
                key = { it.id },
            ) { msg ->
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
        is JarvisChatMessage.Thinking -> ThinkingBubble()
        is JarvisChatMessage.Working -> WorkingBubble(message.label)
        is JarvisChatMessage.Error -> ErrorBubble(message, onRetry)
    }
}

@Composable
private fun UserBubble(message: JarvisChatMessage.User) {
    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
        Surface(
            color = MaterialTheme.colorScheme.primary,
            shape = RoundedCornerShape(topStart = 16.dp, topEnd = 16.dp, bottomEnd = 4.dp, bottomStart = 16.dp),
            modifier = Modifier.widthIn(max = 320.dp),
        ) {
            Text(
                text = message.text,
                color = MaterialTheme.colorScheme.onPrimary,
                modifier = Modifier.padding(horizontal = 14.dp, vertical = 10.dp),
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
        JarvisTone.NORMAL -> MaterialTheme.colorScheme.surfaceVariant
        JarvisTone.SERIOUS -> MaterialTheme.colorScheme.tertiaryContainer
        JarvisTone.CRITICAL -> MaterialTheme.colorScheme.errorContainer
    }
    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.Start) {
        Surface(
            color = accent,
            shape = RoundedCornerShape(topStart = 16.dp, topEnd = 16.dp, bottomEnd = 16.dp, bottomStart = 4.dp),
            modifier = Modifier.widthIn(max = 340.dp),
        ) {
            Column(modifier = Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                if (message.body.isNotEmpty()) {
                    Text(
                        text = message.body,
                        style = MaterialTheme.typography.bodyMedium,
                    )
                }
                if (message.streaming && message.body.isEmpty()) {
                    Text("…", style = MaterialTheme.typography.bodyMedium)
                }
                if (message.aborted) {
                    Text(
                        text = "(stopped)",
                        style = MaterialTheme.typography.labelSmall,
                        fontStyle = FontStyle.Italic,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                if (!message.detail.isNullOrBlank()) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        AssistChip(
                            onClick = onToggleExpand,
                            label = { Text(if (expanded) "Hide detail" else "Show detail") },
                            leadingIcon = {
                                Icon(
                                    if (expanded) Icons.Default.ExpandLess else Icons.Default.ExpandMore,
                                    contentDescription = null,
                                )
                            },
                        )
                    }
                    AnimatedVisibility(visible = expanded) {
                        Column(modifier = Modifier.padding(top = 4.dp)) {
                            HorizontalDivider()
                            Spacer(Modifier.height(6.dp))
                            Text(
                                text = message.detail,
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurface,
                            )
                        }
                    }
                }
                message.inline.forEachIndexed { idx, card ->
                    InlineCardView(
                        card = card,
                        promoted = "${message.id}/Task/${(card as? JarvisInlineCard.Task)?.title.orEmpty()}" in promotedTasks,
                        approved = approved.any { it.startsWith("${message.id}/Approval") },
                        held = held.any { it.startsWith("${message.id}/Approval") },
                        acked = ackedCritical.any { it.startsWith("${message.id}/Critical") },
                        onPromoteTask = onPromoteTask,
                        onApprove = onApprove,
                        onHold = onHold,
                        onAckCritical = onAckCritical,
                    )
                }
                if (!message.streaming && message.body.isNotEmpty()) {
                    Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                        IconButton(onClick = onCopy) {
                            Icon(Icons.Default.ContentCopy, contentDescription = "Copy")
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun ThinkingBubble() {
    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.Start) {
        Surface(
            color = MaterialTheme.colorScheme.surfaceVariant,
            shape = RoundedCornerShape(16.dp),
        ) {
            Row(
                modifier = Modifier.padding(horizontal = 14.dp, vertical = 10.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                CircularProgressIndicator(modifier = Modifier.size(14.dp), strokeWidth = 2.dp)
                Text("thinking…", style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}

@Composable
private fun WorkingBubble(label: String) {
    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.Start) {
        Surface(
            color = MaterialTheme.colorScheme.surfaceVariant,
            shape = RoundedCornerShape(16.dp),
        ) {
            Row(
                modifier = Modifier.padding(horizontal = 14.dp, vertical = 10.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                CircularProgressIndicator(modifier = Modifier.size(14.dp), strokeWidth = 2.dp)
                Text(label, style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}

@Composable
private fun ErrorBubble(message: JarvisChatMessage.Error, onRetry: () -> Unit) {
    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.Start) {
        Surface(
            color = MaterialTheme.colorScheme.errorContainer,
            shape = RoundedCornerShape(16.dp),
            modifier = Modifier.widthIn(max = 340.dp),
        ) {
            Column(modifier = Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    Icon(
                        Icons.Default.Warning,
                        contentDescription = null,
                        tint = MaterialTheme.colorScheme.error,
                    )
                    Text(
                        "Gateway error",
                        style = MaterialTheme.typography.titleSmall,
                        color = MaterialTheme.colorScheme.error,
                    )
                }
                Text(message.text, style = MaterialTheme.typography.bodyMedium)
                message.retryHint?.let {
                    Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                Button(onClick = onRetry) {
                    Icon(Icons.Default.Refresh, contentDescription = null)
                    Spacer(Modifier.size(6.dp))
                    Text("Retry")
                }
            }
        }
    }
}

@Composable
private fun InlineCardView(
    card: JarvisInlineCard,
    promoted: Boolean,
    approved: Boolean,
    held: Boolean,
    acked: Boolean,
    onPromoteTask: (JarvisInlineCard.Task) -> Unit,
    onApprove: (JarvisInlineCard.Approval) -> Unit,
    onHold: (JarvisInlineCard.Approval) -> Unit,
    onAckCritical: (JarvisInlineCard.Critical, String) -> Unit,
) {
    when (card) {
        is JarvisInlineCard.Task -> TaskCardView(card, promoted, onPromoteTask)
        is JarvisInlineCard.Approval -> ApprovalCardView(card, approved, held, onApprove, onHold)
        is JarvisInlineCard.Serious -> SeriousCardView(card)
        is JarvisInlineCard.Critical -> CriticalCardView(card, acked, onAckCritical)
    }
}

@Composable
private fun TaskCardView(
    card: JarvisInlineCard.Task,
    promoted: Boolean,
    onPromote: (JarvisInlineCard.Task) -> Unit,
) {
    Card(
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
    ) {
        Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("Task draft", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.primary)
            Text(card.title, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
            Text(card.summary, style = MaterialTheme.typography.bodySmall)
            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                AssistChip(onClick = {}, label = { Text(card.taskType.name.lowercase()) })
                AssistChip(onClick = {}, label = { Text(card.targetTool.name.lowercase().replace('_', ' ')) })
            }
            if (promoted) {
                Text("Added to orchestrator", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.primary)
            } else {
                FilledTonalButton(onClick = { onPromote(card) }) { Text("Add to orchestrator") }
            }
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
    Card(
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        modifier = Modifier.border(
            width = 1.dp,
            color = MaterialTheme.colorScheme.tertiary,
            shape = MaterialTheme.shapes.medium,
        ),
    ) {
        Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(
                "Approval required",
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.tertiary,
            )
            Text(card.title, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
            Text(card.summary, style = MaterialTheme.typography.bodySmall)
            Text(
                "Impact: ${card.impact}",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            when {
                approved -> Text("Approved — proceeding.", color = MaterialTheme.colorScheme.primary)
                held -> Text("Held — nothing executed.", color = MaterialTheme.colorScheme.onSurfaceVariant)
                else -> Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(onClick = { onApprove(card) }) { Text(card.approveLabel) }
                    OutlinedButton(onClick = { onHold(card) }) { Text(card.denyLabel) }
                }
            }
        }
    }
}

@Composable
private fun SeriousCardView(card: JarvisInlineCard.Serious) {
    Card(
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.tertiaryContainer),
    ) {
        Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                Icon(Icons.Default.Warning, contentDescription = null, tint = MaterialTheme.colorScheme.tertiary)
                Text("Serious", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.tertiary)
            }
            Text(card.title, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
            Text(card.summary, style = MaterialTheme.typography.bodySmall)
        }
    }
}

@Composable
private fun CriticalCardView(
    card: JarvisInlineCard.Critical,
    acked: Boolean,
    onAck: (JarvisInlineCard.Critical, String) -> Unit,
) {
    var typed by remember(card) { mutableStateOf("") }
    Card(
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.errorContainer),
        modifier = Modifier.border(
            width = 2.dp,
            color = MaterialTheme.colorScheme.error,
            shape = MaterialTheme.shapes.medium,
        ),
    ) {
        Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                Icon(Icons.Default.Warning, contentDescription = null, tint = MaterialTheme.colorScheme.error)
                Text(
                    "CRITICAL",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.error,
                    fontWeight = FontWeight.Bold,
                )
            }
            Text(card.title, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
            Text(card.summary, style = MaterialTheme.typography.bodySmall)
            if (acked) {
                Text(
                    "Acknowledged.",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.error,
                    fontWeight = FontWeight.SemiBold,
                )
            } else {
                Text(
                    "Type the ack string to continue:",
                    style = MaterialTheme.typography.bodySmall,
                )
                Text(
                    text = "\"${card.requiredAck}\"",
                    style = MaterialTheme.typography.labelSmall,
                    fontStyle = FontStyle.Italic,
                )
                OutlinedTextField(
                    value = typed,
                    onValueChange = { typed = it },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                Button(
                    onClick = { onAck(card, typed) },
                    colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.error),
                    enabled = typed.isNotBlank(),
                ) {
                    Text("Acknowledge")
                }
            }
        }
    }
}

@Composable
private fun ChatInputBar(
    draft: String,
    responding: Boolean,
    voiceCapturing: Boolean,
    onDraftChange: (String) -> Unit,
    onSend: () -> Unit,
    onStop: () -> Unit,
    onVoice: () -> Unit,
) {
    Surface(
        tonalElevation = 3.dp,
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp)) {
            if (voiceCapturing) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    modifier = Modifier.padding(bottom = 6.dp),
                ) {
                    Box(
                        modifier = Modifier
                            .size(10.dp)
                            .clip(androidx.compose.foundation.shape.CircleShape)
                            .background(MaterialTheme.colorScheme.error),
                    )
                    Text("Listening…", style = MaterialTheme.typography.labelMedium)
                }
            }
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                IconButton(
                    onClick = onVoice,
                    enabled = !responding && !voiceCapturing,
                ) {
                    Icon(Icons.Default.Mic, contentDescription = "Voice")
                }
                OutlinedTextField(
                    value = draft,
                    onValueChange = onDraftChange,
                    modifier = Modifier.weight(1f),
                    placeholder = { Text("Talk to Jarvis…") },
                    maxLines = 4,
                    enabled = !responding,
                )
                if (responding) {
                    FilledIconButton(
                        onClick = onStop,
                        colors = androidx.compose.material3.IconButtonDefaults.filledIconButtonColors(
                            containerColor = MaterialTheme.colorScheme.error,
                            contentColor = MaterialTheme.colorScheme.onError,
                        ),
                    ) {
                        Icon(Icons.Default.Stop, contentDescription = "Stop")
                    }
                } else {
                    FilledIconButton(
                        onClick = onSend,
                        enabled = draft.isNotBlank(),
                    ) {
                        Icon(Icons.Default.Send, contentDescription = "Send")
                    }
                }
            }
        }
    }
}
