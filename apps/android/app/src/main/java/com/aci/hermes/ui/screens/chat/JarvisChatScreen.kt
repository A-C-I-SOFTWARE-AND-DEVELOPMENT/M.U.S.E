package com.aci.hermes.ui.screens.chat

import android.app.Activity
import android.content.Intent
import android.speech.RecognizerIntent
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
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
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.ContentCopy
import androidx.compose.material.icons.filled.Description
import androidx.compose.material.icons.filled.Error
import androidx.compose.material.icons.filled.ExpandLess
import androidx.compose.material.icons.filled.ExpandMore
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material.icons.filled.WorkOutline
import androidx.compose.material3.AssistChip
import androidx.compose.material3.AssistChipDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
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
import com.aci.hermes.data.jarvis.JarvisPhase
import com.aci.hermes.data.jarvis.JarvisRecordRef
import com.aci.hermes.data.jarvis.JarvisToolCall
import com.aci.hermes.data.jarvis.JarvisToolStatus
import com.aci.hermes.data.jarvis.JarvisTone
import com.aci.hermes.ui.components.AskJarvisBar
import com.aci.hermes.ui.designsystem.museButton
import com.aci.hermes.ui.designsystem.museButtonVariant
import com.aci.hermes.ui.designsystem.museChip
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
 * The muse conversational chat surface — the "Chat" shell tab.
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
                        expandedTools = state.expandedTools,
                        approved = state.approved,
                        held = state.held,
                        ackedCritical = state.ackedCritical,
                        promotedTasks = state.promotedTasks,
                        responding = state.responding,
                        onToggleExpand = { viewModel.toggleExpanded(msg.id) },
                        onToggleTool = viewModel::toggleToolExpanded,
                        onCopy = { viewModel.copyMessage(msg.id) },
                        onContinue = viewModel::continueReply,
                        onCreateJob = { viewModel.createJob(msg.id) },
                        onInspectRecord = viewModel::inspectRecord,
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
                        putExtra(RecognizerIntent.EXTRA_PROMPT, "Speak to muse")
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

    state.recordSheet?.let { record ->
        RecordSheet(record = record, onDismiss = viewModel::dismissRecord)
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun RecordSheet(
    record: com.aci.hermes.data.jarvis.JarvisRecordView,
    onDismiss: () -> Unit,
) {
    ModalBottomSheet(onDismissRequest = onDismiss, containerColor = JarvisInkRaised) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(JarvisTokens.SpaceMd),
            verticalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm),
        ) {
            Text(record.title, style = MaterialTheme.typography.titleMedium, color = JarvisSignal)
            record.subtitle?.let {
                Text(it, style = MaterialTheme.typography.labelSmall, color = JarvisCyan)
            }
            Spacer(Modifier.height(JarvisTokens.SpaceXs))
            record.lines.forEach { line ->
                Text(line, style = MaterialTheme.typography.bodySmall, color = JarvisSignalDim)
            }
            Spacer(Modifier.height(JarvisTokens.SpaceSm))
        }
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
    expandedTools: Set<String>,
    approved: Set<String>,
    held: Set<String>,
    ackedCritical: Set<String>,
    promotedTasks: Set<String>,
    responding: Boolean,
    onToggleExpand: () -> Unit,
    onToggleTool: (String) -> Unit,
    onCopy: () -> Unit,
    onContinue: () -> Unit,
    onCreateJob: () -> Unit,
    onInspectRecord: (JarvisRecordRef) -> Unit,
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
            expandedTools = expandedTools,
            approved = approved,
            held = held,
            ackedCritical = ackedCritical,
            promotedTasks = promotedTasks,
            responding = responding,
            onToggleExpand = onToggleExpand,
            onToggleTool = onToggleTool,
            onCopy = onCopy,
            onContinue = onContinue,
            onCreateJob = onCreateJob,
            onInspectRecord = onInspectRecord,
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
    expandedTools: Set<String>,
    approved: Set<String>,
    held: Set<String>,
    ackedCritical: Set<String>,
    promotedTasks: Set<String>,
    responding: Boolean,
    onToggleExpand: () -> Unit,
    onToggleTool: (String) -> Unit,
    onCopy: () -> Unit,
    onContinue: () -> Unit,
    onCreateJob: () -> Unit,
    onInspectRecord: (JarvisRecordRef) -> Unit,
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
                if (message.phases.isNotEmpty()) {
                    PhaseRail(phases = message.phases, streaming = message.streaming)
                }
                message.toolCalls.forEach { tool ->
                    ToolCallChip(
                        tool = tool,
                        expanded = tool.id in expandedTools,
                        onToggle = { onToggleTool(tool.id) },
                    )
                }
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
                if (message.records.isNotEmpty()) {
                    RecordRow(records = message.records, onInspect = onInspectRecord)
                }
                if (!message.streaming && message.body.isNotEmpty()) {
                    MessageActions(
                        enabled = !responding,
                        onCopy = onCopy,
                        onContinue = onContinue,
                        onCreateJob = onCreateJob,
                    )
                }
            }
        }
    }
}

/**
 * Compact progress rail: one chip per phase the turn passed through, the
 * latest highlighted while streaming. Complements (doesn't replace) the
 * thinking/working indicator — it's the glanceable "where are we" summary.
 */
@Composable
private fun PhaseRail(phases: List<JarvisPhase>, streaming: Boolean) {
    Row(
        horizontalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceXs),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        phases.forEachIndexed { index, phase ->
            val isCurrent = streaming && index == phases.lastIndex
            val color = if (isCurrent) JarvisCyan else JarvisSignalMute
            Box(
                modifier = Modifier
                    .size(6.dp)
                    .clip(CircleShape)
                    .background(color),
            )
            Text(
                text = phase.label,
                style = MaterialTheme.typography.labelSmall,
                color = color,
                fontWeight = if (isCurrent) FontWeight.SemiBold else FontWeight.Normal,
            )
        }
        if (streaming) {
            CircularProgressIndicator(modifier = Modifier.size(10.dp), strokeWidth = 1.5.dp, color = JarvisCyan)
        }
    }
}

/**
 * One tool invocation: compact one-line chip by default, expandable to the
 * redacted detail. Status drives the leading icon (running / ok / fail).
 */
@Composable
private fun ToolCallChip(
    tool: JarvisToolCall,
    expanded: Boolean,
    onToggle: () -> Unit,
) {
    val (icon, tint) = when (tool.status) {
        JarvisToolStatus.START -> Icons.Filled.PlayArrow to JarvisCyan
        JarvisToolStatus.OK -> Icons.Filled.CheckCircle to JarvisJade
        JarvisToolStatus.FAIL -> Icons.Filled.Error to JarvisCrimson
    }
    val hasDetail = !tool.detail.isNullOrBlank()
    Surface(
        color = JarvisInkNight,
        shape = JarvisTokens.ShapeCard,
        modifier = Modifier
            .fillMaxWidth()
            .border(JarvisTokens.BorderHairline, JarvisInkEdge, JarvisTokens.ShapeCard),
    ) {
        Column(modifier = Modifier.padding(horizontal = JarvisTokens.SpaceSm, vertical = JarvisTokens.SpaceXs)) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceXs),
                modifier = if (hasDetail) Modifier.fillMaxWidth().clickableNoRipple(onToggle) else Modifier.fillMaxWidth(),
            ) {
                Icon(icon, contentDescription = null, modifier = Modifier.size(14.dp), tint = tint)
                Text(tool.name, style = MaterialTheme.typography.labelMedium, color = JarvisSignal)
                Text(
                    tool.summary,
                    style = MaterialTheme.typography.labelSmall,
                    color = JarvisSignalDim,
                    modifier = Modifier.weight(1f),
                )
                if (hasDetail) {
                    Icon(
                        if (expanded) Icons.Filled.ExpandLess else Icons.Filled.ExpandMore,
                        contentDescription = if (expanded) "Hide tool detail" else "Show tool detail",
                        modifier = Modifier.size(14.dp),
                        tint = JarvisSignalMute,
                    )
                }
            }
            if (hasDetail) {
                AnimatedVisibility(visible = expanded) {
                    Text(
                        text = tool.detail.orEmpty(),
                        style = MaterialTheme.typography.bodySmall,
                        color = JarvisSignalMute,
                        modifier = Modifier.padding(top = JarvisTokens.SpaceXs),
                    )
                }
            }
        }
    }
}

@Composable
private fun RecordRow(records: List<JarvisRecordRef>, onInspect: (JarvisRecordRef) -> Unit) {
    Row(horizontalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceXs)) {
        records.forEach { ref ->
            val label = when (ref.kind) {
                JarvisRecordRef.Kind.EVIDENCE -> "Evidence"
                JarvisRecordRef.Kind.LEDGER -> "Ledger"
            }
            AssistChip(
                onClick = { onInspect(ref) },
                label = { Text(label) },
                leadingIcon = {
                    Icon(Icons.Filled.Description, contentDescription = null, modifier = Modifier.size(16.dp))
                },
                colors = AssistChipDefaults.assistChipColors(
                    labelColor = JarvisCyan,
                    leadingIconContentColor = JarvisCyan,
                ),
            )
        }
    }
}

@Composable
private fun MessageActions(
    enabled: Boolean,
    onCopy: () -> Unit,
    onContinue: () -> Unit,
    onCreateJob: () -> Unit,
) {
    Row(horizontalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm)) {
        ActionTextButton(Icons.Filled.ContentCopy, "Copy", enabled = true, onClick = onCopy)
        ActionTextButton(Icons.Filled.PlayArrow, "Continue", enabled = enabled, onClick = onContinue)
        ActionTextButton(Icons.Filled.WorkOutline, "Create job", enabled = enabled, onClick = onCreateJob)
    }
}

@Composable
private fun ActionTextButton(
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    label: String,
    enabled: Boolean,
    onClick: () -> Unit,
) {
    TextButton(onClick = onClick, enabled = enabled, contentPadding = PaddingValues(0.dp)) {
        Icon(icon, contentDescription = null, modifier = Modifier.size(16.dp), tint = JarvisSignalMute)
        Spacer(Modifier.size(JarvisTokens.SpaceXs))
        Text(label, style = MaterialTheme.typography.labelSmall, color = JarvisSignalMute)
    }
}

/** Click without the default ripple/indication, for chip-like rows. */
@Composable
private fun Modifier.clickableNoRipple(onClick: () -> Unit): Modifier {
    val interaction = remember { MutableInteractionSource() }
    return this.clickable(
        interactionSource = interaction,
        indication = null,
        onClick = onClick,
    )
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
                museButton(
                    onClick = onRetry,
                    text = "Retry",
                    variant = museButtonVariant.Primary,
                    leadingIcon = Icons.Filled.Refresh,
                )
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
            museChip(label = card.taskType.name.lowercase())
            museChip(label = card.targetTool.name.lowercase().replace('_', ' '))
        }
        if (promoted) {
            Text("Added to orchestrator", style = MaterialTheme.typography.labelSmall, color = JarvisJade)
        } else {
            museButton(
                onClick = { onPromote(card) },
                text = "Add to orchestrator",
                variant = museButtonVariant.Primary,
            )
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
                museButton(
                    onClick = { onApprove(card) },
                    text = card.approveLabel,
                    variant = museButtonVariant.Approve,
                )
                museButton(
                    onClick = { onHold(card) },
                    text = card.denyLabel,
                    variant = museButtonVariant.Secondary,
                )
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
            museButton(
                onClick = { onAck(card, typed) },
                text = "Acknowledge",
                variant = museButtonVariant.Danger,
                enabled = typed.isNotBlank(),
            )
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
                Text("muse is responding…", style = MaterialTheme.typography.labelSmall, color = JarvisSignalMute)
                Spacer(Modifier.weight(1f))
                museButton(
                    onClick = onStop,
                    text = "Stop",
                    variant = museButtonVariant.Danger,
                    leadingIcon = Icons.Filled.Stop,
                )
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
