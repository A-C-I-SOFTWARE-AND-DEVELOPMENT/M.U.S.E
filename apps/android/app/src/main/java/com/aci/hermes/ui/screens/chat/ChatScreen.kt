package com.aci.hermes.ui.screens.chat

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.aci.hermes.R
import com.aci.hermes.data.jarvis.JarvisChatMessage
import com.aci.hermes.data.jarvis.JarvisInlineCard
import com.aci.hermes.data.jarvis.JarvisTone
import com.aci.hermes.ui.components.AskJarvisBar
import com.aci.hermes.ui.theme.JarvisCyan
import com.aci.hermes.ui.theme.JarvisGold
import com.aci.hermes.ui.theme.JarvisTokens

/**
 * Jarvis Prime Chat surface. Renders the conversation transcript and the
 * "Ask Jarvis" input bar. All conversation logic lives in [ChatViewModel];
 * this composable only draws state and forwards intents.
 */
@Composable
fun ChatScreen(
    viewModel: ChatViewModel,
    paddingValues: PaddingValues,
    onPromoteTask: (JarvisInlineCard.Task) -> Unit,
) {
    val state by viewModel.state.collectAsState()
    val listState = rememberLazyListState()

    // Keep the newest message in view as the transcript grows / streams.
    LaunchedEffect(state.messages.size, state.messages.lastOrNull()) {
        val count = state.messages.size
        if (count > 0) listState.animateScrollToItem(count - 1)
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(paddingValues),
    ) {
        if (state.messages.isEmpty()) {
            EmptyChat(modifier = Modifier.weight(1f))
        } else {
            LazyColumn(
                state = listState,
                modifier = Modifier
                    .weight(1f)
                    .fillMaxWidth()
                    .padding(horizontal = JarvisTokens.SpaceLg),
                verticalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm),
                contentPadding = PaddingValues(vertical = JarvisTokens.SpaceMd),
            ) {
                items(state.messages, key = { it.id }) { msg ->
                    MessageRow(
                        message = msg,
                        onRetry = viewModel::retry,
                        onPromoteTask = onPromoteTask,
                    )
                }
            }
        }

        AskJarvisBar(
            value = state.input,
            onValueChange = viewModel::onInputChange,
            onSend = { if (state.isStreaming) viewModel.abort() else viewModel.send() },
            onMicToggle = viewModel::onMicToggle,
            isListening = state.isListening,
            enabled = true,
            modifier = Modifier.padding(JarvisTokens.SpaceLg),
        )
    }
}

@Composable
private fun EmptyChat(modifier: Modifier = Modifier) {
    Box(modifier = modifier.fillMaxWidth(), contentAlignment = Alignment.Center) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm),
            modifier = Modifier.padding(JarvisTokens.SpaceXxl),
        ) {
            Text(
                text = stringResource(R.string.chat_title),
                style = MaterialTheme.typography.titleLarge,
                color = MaterialTheme.colorScheme.primary,
            )
            Text(
                text = stringResource(R.string.chat_empty_hint),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun MessageRow(
    message: JarvisChatMessage,
    onRetry: () -> Unit,
    onPromoteTask: (JarvisInlineCard.Task) -> Unit,
) {
    when (message) {
        is JarvisChatMessage.User -> UserBubble(message)
        is JarvisChatMessage.Jarvis -> JarvisBubble(message, onPromoteTask)
        is JarvisChatMessage.Thinking -> TransientBubble(stringResource(R.string.ask_jarvis_thinking))
        is JarvisChatMessage.Working -> TransientBubble(message.label)
        is JarvisChatMessage.Error -> ErrorBubble(message, onRetry)
    }
}

@Composable
private fun UserBubble(message: JarvisChatMessage.User) {
    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
        Surface(
            shape = JarvisTokens.ShapeCard,
            color = MaterialTheme.colorScheme.primary,
            modifier = Modifier.fillMaxWidth(0.85f),
        ) {
            Text(
                text = message.text,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onPrimary,
                modifier = Modifier.padding(JarvisTokens.SpaceMd),
            )
        }
    }
}

@Composable
private fun JarvisBubble(
    message: JarvisChatMessage.Jarvis,
    onPromoteTask: (JarvisInlineCard.Task) -> Unit,
) {
    var expanded by rememberSaveable(message.id) { mutableStateOf(false) }
    val accent = when (message.tone) {
        JarvisTone.CRITICAL -> MaterialTheme.colorScheme.error
        JarvisTone.SERIOUS -> JarvisGold
        JarvisTone.NORMAL -> JarvisCyan
    }

    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.Start) {
        Surface(
            shape = JarvisTokens.ShapeCard,
            color = MaterialTheme.colorScheme.surfaceVariant,
            modifier = Modifier.fillMaxWidth(0.92f),
        ) {
            Column(
                modifier = Modifier.padding(JarvisTokens.SpaceMd),
                verticalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceXs),
            ) {
                Text(
                    text = message.body + if (message.streaming) " ▍" else "",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurface,
                )
                if (!message.detail.isNullOrBlank()) {
                    TextButton(
                        onClick = { expanded = !expanded },
                        contentPadding = PaddingValues(0.dp),
                    ) {
                        Text(
                            text = stringResource(
                                if (expanded) R.string.chat_hide_detail else R.string.chat_show_detail,
                            ),
                            color = accent,
                            style = MaterialTheme.typography.labelMedium,
                        )
                    }
                    AnimatedVisibility(visible = expanded) {
                        Text(
                            text = message.detail,
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
                message.inline.forEach { card ->
                    InlineCard(card = card, accent = accent, onPromoteTask = onPromoteTask)
                }
                if (message.aborted) {
                    Text(
                        text = stringResource(R.string.chat_aborted_note),
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }
    }
}

@Composable
private fun InlineCard(
    card: JarvisInlineCard,
    accent: androidx.compose.ui.graphics.Color,
    onPromoteTask: (JarvisInlineCard.Task) -> Unit,
) {
    Card(
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(
            modifier = Modifier.padding(JarvisTokens.SpaceMd),
            verticalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceXs),
        ) {
            when (card) {
                is JarvisInlineCard.Task -> {
                    Text(card.title, style = MaterialTheme.typography.titleSmall, color = accent, fontWeight = FontWeight.SemiBold)
                    Text(card.summary, style = MaterialTheme.typography.bodySmall)
                    Text(
                        text = stringResource(
                            R.string.chat_card_task_target,
                            card.targetTool.name.lowercase().replace('_', ' '),
                        ),
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    TextButton(onClick = { onPromoteTask(card) }) {
                        Text(stringResource(R.string.chat_card_task_promote))
                    }
                }
                is JarvisInlineCard.Approval -> {
                    Text(card.title, style = MaterialTheme.typography.titleSmall, color = JarvisGold, fontWeight = FontWeight.SemiBold)
                    Text(card.summary, style = MaterialTheme.typography.bodySmall)
                    Text(card.impact, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                is JarvisInlineCard.Serious -> {
                    Text(card.title, style = MaterialTheme.typography.titleSmall, color = JarvisGold, fontWeight = FontWeight.SemiBold)
                    Text(card.summary, style = MaterialTheme.typography.bodySmall)
                }
                is JarvisInlineCard.Critical -> {
                    Text(card.title, style = MaterialTheme.typography.titleSmall, color = MaterialTheme.colorScheme.error, fontWeight = FontWeight.SemiBold)
                    Text(card.summary, style = MaterialTheme.typography.bodySmall)
                    Text(
                        text = stringResource(R.string.chat_card_critical_ack, card.requiredAck),
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.error,
                    )
                }
            }
        }
    }
}

@Composable
private fun TransientBubble(label: String) {
    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.Start) {
        Surface(
            shape = JarvisTokens.ShapeCard,
            color = MaterialTheme.colorScheme.surfaceVariant,
        ) {
            Text(
                text = label,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(JarvisTokens.SpaceMd),
            )
        }
    }
}

@Composable
private fun ErrorBubble(message: JarvisChatMessage.Error, onRetry: () -> Unit) {
    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.Start) {
        Surface(
            shape = JarvisTokens.ShapeCard,
            color = MaterialTheme.colorScheme.errorContainer,
            modifier = Modifier.fillMaxWidth(0.92f),
        ) {
            Column(
                modifier = Modifier.padding(JarvisTokens.SpaceMd),
                verticalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceXs),
            ) {
                Text(
                    text = message.text,
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onErrorContainer,
                )
                if (!message.retryHint.isNullOrBlank()) {
                    Text(
                        text = message.retryHint,
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onErrorContainer,
                    )
                }
                TextButton(onClick = onRetry) {
                    Text(stringResource(R.string.chat_retry))
                }
            }
        }
    }
}
