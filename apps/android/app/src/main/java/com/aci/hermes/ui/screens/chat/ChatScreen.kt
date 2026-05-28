package com.aci.hermes.ui.screens.chat

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
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ContentCopy
import androidx.compose.material.icons.filled.DeleteSweep
import androidx.compose.material.icons.filled.ExpandLess
import androidx.compose.material.icons.filled.ExpandMore
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Send
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.AssistChip
import androidx.compose.material3.AssistChipDefaults
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilledIconButton
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
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
import com.aci.hermes.ui.theme.JarvisAmber
import com.aci.hermes.ui.theme.JarvisCrimson
import com.aci.hermes.ui.theme.JarvisCyan
import com.aci.hermes.ui.theme.JarvisGold
import com.aci.hermes.ui.theme.JarvisInkDeep
import com.aci.hermes.ui.theme.JarvisInkRaised
import com.aci.hermes.ui.theme.JarvisJade
import com.aci.hermes.ui.theme.JarvisSignal
import com.aci.hermes.ui.theme.JarvisSignalDim
import com.aci.hermes.ui.theme.JarvisSignalMute
import com.aci.hermes.ui.theme.JarvisTokens

/**
 * Jarvis Prime chat surface.
 *
 * This composable is shell-friendly: it does NOT own a `TopAppBar` or
 * an outer `Scaffold`. The integrator embeds it inside the existing
 * `ShellHost` and passes `Modifier.padding(innerPadding)` so the shell
 * keeps owning the chrome (bottom-nav, top bar, emergency stop).
 *
 * The screen never reaches outside [ChatViewModel] for state — all
 * inline-card actions (promote task, approve, hold, ack critical),
 * copy, retry, stop, and transcript reset flow through the VM. That
 * keeps this file stateless beyond the local snackbar host and the
 * critical-card typed-ack input.
 */
@Composable
fun ChatScreen(
    viewModel: ChatViewModel,
    modifier: Modifier = Modifier,
    @Suppress("UNUSED_PARAMETER") onBack: () -> Unit = {},
) {
    val state by viewModel.state.collectAsState()
    val snackbarHostState = remember { SnackbarHostState() }
    val listState = rememberLazyListState()

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
        modifier = modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background),
    ) {
        Column(modifier = Modifier.fillMaxSize()) {
            GatewayHeader(
                label = state.gatewayLabel,
                mockMode = state.mockMode,
                onReset = { viewModel.clearTranscript() },
            )
            HorizontalDivider(color = JarvisInkRaised)
            LazyColumn(
                state = listState,
                modifier = Modifier
                    .fillMaxWidth()
                    .weight(1f)
                    .padding(horizontal = JarvisTokens.SpaceLg),
                contentPadding = androidx.compose.foundation.layout.PaddingValues(vertical = JarvisTokens.SpaceMd),
                verticalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm),
            ) {
                items(items = state.messages, key = { it.id }) { msg ->
                    MessageRow(
                        message = msg,
                        expanded = state.expanded.contains(msg.id),
                        ackedCritical = state.ackedCritical,
                        approved = state.approved,
                        held = state.held,
                        promotedTasks = state.promotedTasks,
                        onToggleExpand = { viewModel.toggleExpanded(msg.id) },
                        onCopy = { viewModel.copyMessage(msg.id) },
                        onRetry = { viewModel.retry() },
                        onPromoteTask = { card -> viewModel.promoteInlineTask(msg.id, card) },
                        onApprove = { card -> viewModel.approveInline(msg.id, card) },
                        onHold = { card -> viewModel.holdInline(msg.id, card) },
                        onAckCritical = { card, typed -> viewModel.ackCritical(msg.id, card, typed) },
                    )
                }
            }
            Composer(
                draft = state.draft,
                responding = state.responding,
                onDraftChange = viewModel::onDraftChange,
                onSend = viewModel::send,
                onStop = viewModel::stop,
            )
        }
        SnackbarHost(
            hostState = snackbarHostState,
            modifier = Modifier
                .align(Alignment.BottomCenter)
                .padding(bottom = 96.dp),
        )
    }
}

@Composable
private fun GatewayHeader(
    label: String,
    mockMode: Boolean,
    onReset: () -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(JarvisInkDeep)
            .padding(horizontal = JarvisTokens.SpaceLg, vertical = JarvisTokens.SpaceSm),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = "Jarvis Prime",
                color = JarvisSignal,
                fontWeight = FontWeight.SemiBold,
                style = MaterialTheme.typography.titleMedium,
            )
            Text(
                text = label.ifBlank { "Local" },
                color = JarvisSignalMute,
                style = MaterialTheme.typography.labelSmall,
            )
        }
        if (mockMode) {
            AssistChip(
                onClick = {},
                label = { Text("MOCK", color = JarvisGold) },
                colors = AssistChipDefaults.assistChipColors(
                    containerColor = Color.Transparent,
                ),
                modifier = Modifier.padding(end = JarvisTokens.SpaceSm),
            )
        }
        IconButton(onClick = onReset) {
            Icon(
                Icons.Filled.DeleteSweep,
                contentDescription = "Reset transcript",
                tint = JarvisSignalDim,
            )
        }
    }
}

@Composable
private fun MessageRow(
    message: JarvisChatMessage,
    expanded: Boolean,
    ackedCritical: Set<String>,
    approved: Set<String>,
    held: Set<String>,
    promotedTasks: Set<String>,
    onToggleExpand: () -> Unit,
    onCopy: () -> Unit,
    onRetry: () -> Unit,
    onPromoteTask: (JarvisInlineCard.Task) -> Unit,
    onApprove: (JarvisInlineCard.Approval) -> Unit,
    onHold: (JarvisInlineCard.Approval) -> Unit,
    onAckCritical: (JarvisInlineCard.Critical, String) -> Unit,
) {
    when (message) {
        is JarvisChatMessage.User -> UserBubble(message)
        is JarvisChatMessage.Jarvis -> JarvisBubble(
            message = message,
            expanded = expanded,
            messageId = message.id,
            ackedCritical = ackedCritical,
            approved = approved,
            held = held,
            promotedTasks = promotedTasks,
            onToggleExpand = onToggleExpand,
            onCopy = onCopy,
            onPromoteTask = onPromoteTask,
            onApprove = onApprove,
            onHold = onHold,
            onAckCritical = onAckCritical,
        )
        is JarvisChatMessage.Thinking -> ThinkingBubble()
        is JarvisChatMessage.Working -> WorkingBubble(label = message.label)
        is JarvisChatMessage.Error -> ErrorBubble(message = message, onRetry = onRetry)
    }
}

@Composable
private fun UserBubble(message: JarvisChatMessage.User) {
    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
        Surface(
            shape = JarvisTokens.ShapeCard,
            color = JarvisGold.copy(alpha = 0.16f),
            border = androidx.compose.foundation.BorderStroke(JarvisTokens.BorderHairline, JarvisGold.copy(alpha = 0.5f)),
            modifier = Modifier.widthIn(max = 320.dp),
        ) {
            Text(
                text = message.text,
                color = JarvisSignal,
                modifier = Modifier.padding(
                    horizontal = JarvisTokens.SpaceMd,
                    vertical = JarvisTokens.SpaceSm,
                ),
            )
        }
    }
}

@Composable
private fun JarvisBubble(
    message: JarvisChatMessage.Jarvis,
    expanded: Boolean,
    messageId: String,
    ackedCritical: Set<String>,
    approved: Set<String>,
    held: Set<String>,
    promotedTasks: Set<String>,
    onToggleExpand: () -> Unit,
    onCopy: () -> Unit,
    onPromoteTask: (JarvisInlineCard.Task) -> Unit,
    onApprove: (JarvisInlineCard.Approval) -> Unit,
    onHold: (JarvisInlineCard.Approval) -> Unit,
    onAckCritical: (JarvisInlineCard.Critical, String) -> Unit,
) {
    val accent = when (message.tone) {
        JarvisTone.NORMAL -> JarvisCyan
        JarvisTone.SERIOUS -> JarvisAmber
        JarvisTone.CRITICAL -> JarvisCrimson
    }
    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.Start) {
        Surface(
            shape = JarvisTokens.ShapeCard,
            color = JarvisInkDeep,
            border = androidx.compose.foundation.BorderStroke(JarvisTokens.BorderHairline, accent.copy(alpha = 0.4f)),
            modifier = Modifier.widthIn(max = 360.dp),
        ) {
            Column(modifier = Modifier.padding(JarvisTokens.SpaceMd)) {
                Text(
                    text = message.body.ifBlank { if (message.streaming) "…" else "(no reply)" },
                    color = JarvisSignal,
                )
                if (message.aborted) {
                    Text(
                        text = "(stopped)",
                        color = JarvisSignalMute,
                        fontStyle = FontStyle.Italic,
                        style = MaterialTheme.typography.labelSmall,
                        modifier = Modifier.padding(top = JarvisTokens.SpaceXs),
                    )
                }
                if (!message.detail.isNullOrBlank()) {
                    Spacer(modifier = Modifier.height(JarvisTokens.SpaceXs))
                    AssistChip(
                        onClick = onToggleExpand,
                        label = {
                            Text(if (expanded) "Hide detail" else "Show detail")
                        },
                        leadingIcon = {
                            Icon(
                                if (expanded) Icons.Filled.ExpandLess else Icons.Filled.ExpandMore,
                                contentDescription = null,
                                modifier = Modifier.size(16.dp),
                            )
                        },
                        colors = AssistChipDefaults.assistChipColors(
                            containerColor = Color.Transparent,
                            labelColor = accent,
                            leadingIconContentColor = accent,
                        ),
                    )
                    AnimatedVisibility(visible = expanded) {
                        Surface(
                            shape = JarvisTokens.ShapeCard,
                            color = JarvisInkRaised,
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(top = JarvisTokens.SpaceSm),
                        ) {
                            Text(
                                text = message.detail!!,
                                color = JarvisSignalDim,
                                modifier = Modifier.padding(JarvisTokens.SpaceMd),
                            )
                        }
                    }
                }
                if (message.inline.isNotEmpty()) {
                    Spacer(modifier = Modifier.height(JarvisTokens.SpaceSm))
                    message.inline.forEach { card ->
                        when (card) {
                            is JarvisInlineCard.Task -> TaskCard(
                                card = card,
                                promoted = promotedTasks.contains(inlineKey(messageId, card)),
                                onPromote = { onPromoteTask(card) },
                            )
                            is JarvisInlineCard.Approval -> ApprovalCard(
                                card = card,
                                approved = approved.contains(inlineKey(messageId, card)),
                                held = held.contains(inlineKey(messageId, card)),
                                onApprove = { onApprove(card) },
                                onHold = { onHold(card) },
                            )
                            is JarvisInlineCard.Serious -> SeriousCard(card)
                            is JarvisInlineCard.Critical -> CriticalCard(
                                card = card,
                                acked = ackedCritical.contains(inlineKey(messageId, card)),
                                onAck = { typed -> onAckCritical(card, typed) },
                            )
                        }
                        Spacer(modifier = Modifier.height(JarvisTokens.SpaceXs))
                    }
                }
                if (!message.streaming && message.body.isNotBlank()) {
                    Spacer(modifier = Modifier.height(JarvisTokens.SpaceXs))
                    IconButton(onClick = onCopy, modifier = Modifier.size(28.dp)) {
                        Icon(
                            Icons.Filled.ContentCopy,
                            contentDescription = "Copy",
                            tint = JarvisSignalMute,
                            modifier = Modifier.size(16.dp),
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun ThinkingBubble() {
    Row(verticalAlignment = Alignment.CenterVertically) {
        CircularProgressIndicator(
            modifier = Modifier.size(14.dp),
            strokeWidth = 2.dp,
            color = JarvisCyan,
        )
        Spacer(modifier = Modifier.size(JarvisTokens.SpaceSm))
        Text(
            text = "Jarvis is thinking…",
            color = JarvisSignalMute,
            fontStyle = FontStyle.Italic,
        )
    }
}

@Composable
private fun WorkingBubble(label: String) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        CircularProgressIndicator(
            modifier = Modifier.size(14.dp),
            strokeWidth = 2.dp,
            color = JarvisCyan,
        )
        Spacer(modifier = Modifier.size(JarvisTokens.SpaceSm))
        Text(
            text = label,
            color = JarvisSignalDim,
        )
    }
}

@Composable
private fun ErrorBubble(message: JarvisChatMessage.Error, onRetry: () -> Unit) {
    Surface(
        shape = JarvisTokens.ShapeCard,
        color = JarvisCrimson.copy(alpha = 0.10f),
        border = androidx.compose.foundation.BorderStroke(JarvisTokens.BorderHairline, JarvisCrimson),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(modifier = Modifier.padding(JarvisTokens.SpaceMd)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Filled.Warning, contentDescription = null, tint = JarvisCrimson)
                Spacer(modifier = Modifier.size(JarvisTokens.SpaceSm))
                Text(text = message.text, color = JarvisSignal, fontWeight = FontWeight.SemiBold)
            }
            message.retryHint?.let {
                Text(
                    text = it,
                    color = JarvisSignalDim,
                    style = MaterialTheme.typography.labelSmall,
                    modifier = Modifier.padding(top = JarvisTokens.SpaceXs),
                )
            }
            Spacer(modifier = Modifier.height(JarvisTokens.SpaceSm))
            FilledTonalButton(
                onClick = onRetry,
                colors = ButtonDefaults.filledTonalButtonColors(
                    containerColor = JarvisCrimson.copy(alpha = 0.2f),
                    contentColor = JarvisSignal,
                ),
            ) {
                Icon(Icons.Filled.Refresh, contentDescription = null, modifier = Modifier.size(16.dp))
                Spacer(modifier = Modifier.size(JarvisTokens.SpaceXs))
                Text("Retry")
            }
        }
    }
}

@Composable
private fun TaskCard(
    card: JarvisInlineCard.Task,
    promoted: Boolean,
    onPromote: () -> Unit,
) {
    InlineCardFrame(accent = JarvisJade, title = card.title) {
        Text(text = card.summary, color = JarvisSignalDim)
        Spacer(modifier = Modifier.height(JarvisTokens.SpaceXs))
        Text(
            text = "${card.targetTool.name} · ${card.taskType.name}",
            color = JarvisSignalMute,
            style = MaterialTheme.typography.labelSmall,
        )
        Spacer(modifier = Modifier.height(JarvisTokens.SpaceSm))
        Button(
            onClick = onPromote,
            enabled = !promoted,
            colors = ButtonDefaults.buttonColors(
                containerColor = JarvisJade,
                contentColor = JarvisInkDeep,
                disabledContainerColor = JarvisJade.copy(alpha = 0.3f),
            ),
        ) {
            Text(if (promoted) "Added to orchestrator" else "Add to orchestrator")
        }
    }
}

@Composable
private fun ApprovalCard(
    card: JarvisInlineCard.Approval,
    approved: Boolean,
    held: Boolean,
    onApprove: () -> Unit,
    onHold: () -> Unit,
) {
    InlineCardFrame(accent = JarvisGold, title = card.title) {
        Text(text = card.summary, color = JarvisSignalDim)
        Spacer(modifier = Modifier.height(JarvisTokens.SpaceXs))
        Text(
            text = "Impact: ${card.impact}",
            color = JarvisSignalMute,
            style = MaterialTheme.typography.labelSmall,
        )
        Spacer(modifier = Modifier.height(JarvisTokens.SpaceSm))
        Row(horizontalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm)) {
            Button(
                onClick = onApprove,
                enabled = !approved && !held,
                colors = ButtonDefaults.buttonColors(
                    containerColor = JarvisGold,
                    contentColor = JarvisInkDeep,
                ),
            ) {
                Text(if (approved) "Approved" else card.approveLabel)
            }
            OutlinedButton(
                onClick = onHold,
                enabled = !approved && !held,
            ) {
                Text(if (held) "Held" else card.denyLabel)
            }
        }
    }
}

@Composable
private fun SeriousCard(card: JarvisInlineCard.Serious) {
    InlineCardFrame(accent = JarvisAmber, title = card.title) {
        Text(text = card.summary, color = JarvisSignalDim)
        Spacer(modifier = Modifier.height(JarvisTokens.SpaceXs))
        Text(
            text = "Slowing down — confirm scope before continuing.",
            color = JarvisSignalMute,
            fontStyle = FontStyle.Italic,
            style = MaterialTheme.typography.labelSmall,
        )
    }
}

@Composable
private fun CriticalCard(
    card: JarvisInlineCard.Critical,
    acked: Boolean,
    onAck: (String) -> Unit,
) {
    var typed by remember { mutableStateOf("") }
    InlineCardFrame(accent = JarvisCrimson, title = card.title) {
        Text(text = card.summary, color = JarvisSignalDim)
        Spacer(modifier = Modifier.height(JarvisTokens.SpaceXs))
        Text(
            text = "Type to confirm:  \"${card.requiredAck}\"",
            color = JarvisSignal,
            fontWeight = FontWeight.SemiBold,
            style = MaterialTheme.typography.labelMedium,
        )
        Spacer(modifier = Modifier.height(JarvisTokens.SpaceSm))
        OutlinedTextField(
            value = typed,
            onValueChange = { typed = it },
            enabled = !acked,
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
            placeholder = { Text("Type the ack phrase…", color = JarvisSignalMute) },
        )
        Spacer(modifier = Modifier.height(JarvisTokens.SpaceSm))
        Button(
            onClick = { onAck(typed) },
            enabled = !acked && typed.isNotBlank(),
            colors = ButtonDefaults.buttonColors(
                containerColor = JarvisCrimson,
                contentColor = JarvisSignal,
            ),
        ) {
            Text(if (acked) "Acknowledged" else "Confirm")
        }
    }
}

@Composable
private fun InlineCardFrame(
    accent: Color,
    title: String,
    content: @Composable () -> Unit,
) {
    Card(
        shape = JarvisTokens.ShapeCard,
        colors = CardDefaults.cardColors(containerColor = JarvisInkRaised),
        modifier = Modifier
            .fillMaxWidth()
            .border(
                width = JarvisTokens.BorderHairline,
                color = accent,
                shape = JarvisTokens.ShapeCard,
            ),
    ) {
        Column(modifier = Modifier.padding(JarvisTokens.SpaceMd)) {
            Text(
                text = title,
                color = accent,
                fontWeight = FontWeight.SemiBold,
                style = MaterialTheme.typography.titleSmall,
            )
            Spacer(modifier = Modifier.height(JarvisTokens.SpaceXs))
            content()
        }
    }
}

@Composable
private fun Composer(
    draft: String,
    responding: Boolean,
    onDraftChange: (String) -> Unit,
    onSend: () -> Unit,
    onStop: () -> Unit,
) {
    Surface(color = JarvisInkDeep, modifier = Modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(JarvisTokens.SpaceMd),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            OutlinedTextField(
                value = draft,
                onValueChange = onDraftChange,
                enabled = !responding,
                modifier = Modifier.weight(1f),
                placeholder = {
                    Text(
                        "Ask Jarvis…",
                        color = JarvisSignalMute,
                    )
                },
                maxLines = 4,
            )
            Spacer(modifier = Modifier.size(JarvisTokens.SpaceSm))
            if (responding) {
                FilledIconButton(
                    onClick = onStop,
                    modifier = Modifier
                        .size(48.dp)
                        .clip(JarvisTokens.ShapeButton),
                ) {
                    Icon(
                        Icons.Filled.Stop,
                        contentDescription = "Stop streaming",
                        tint = JarvisCrimson,
                    )
                }
            } else {
                FilledIconButton(
                    onClick = onSend,
                    enabled = draft.isNotBlank(),
                    modifier = Modifier
                        .size(48.dp)
                        .clip(JarvisTokens.ShapeButton),
                ) {
                    Icon(
                        Icons.Filled.Send,
                        contentDescription = "Send",
                    )
                }
            }
        }
    }
}

private fun inlineKey(messageId: String, card: JarvisInlineCard): String {
    val summary = when (card) {
        is JarvisInlineCard.Task -> card.title
        is JarvisInlineCard.Approval -> card.title
        is JarvisInlineCard.Serious -> card.title
        is JarvisInlineCard.Critical -> card.title
    }
    return "$messageId/${card::class.simpleName}/$summary"
}
