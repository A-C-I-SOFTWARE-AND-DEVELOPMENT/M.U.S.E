package com.aci.hermes.ui.screens.chat

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
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.DeleteOutline
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledIconButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
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
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.aci.hermes.R
import com.aci.hermes.data.model.ChatMessage
import com.aci.hermes.data.model.ChatRole
import com.aci.hermes.data.model.ChatSuggestion
import com.aci.hermes.data.model.SuggestionKind
import com.aci.hermes.ui.icon.InteractiveIcon
import com.aci.hermes.ui.icon.InteractiveIconBadge
import com.aci.hermes.ui.navigation.Screen

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChatScreen(
    viewModel: ChatViewModel,
    onOpenVoice: () -> Unit,
    onSuggestionNavigate: (route: String) -> Unit,
) {
    val state by viewModel.state.collectAsState()
    val listState = rememberLazyListState()

    LaunchedEffect(state.messages.size) {
        if (state.messages.isNotEmpty()) {
            listState.animateScrollToItem(state.messages.size - 1)
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        InteractiveIconBadge(sizeDp = 28)
                        Spacer(modifier = Modifier.size(8.dp))
                        Text(stringResource(R.string.chat_title))
                    }
                },
                actions = {
                    IconButton(onClick = viewModel::clear) {
                        Icon(Icons.Default.DeleteOutline, contentDescription = stringResource(R.string.chat_clear))
                    }
                },
            )
        },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding),
        ) {
            if (state.mockMode) {
                MockBanner()
            }

            Box(modifier = Modifier.weight(1f).fillMaxWidth()) {
                if (state.messages.isEmpty()) {
                    EmptyChat(onOpenVoice = onOpenVoice)
                } else {
                    LazyColumn(
                        state = listState,
                        modifier = Modifier.fillMaxSize(),
                        contentPadding = PaddingValues(horizontal = 12.dp, vertical = 12.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        items(state.messages) { msg ->
                            ChatBubble(msg, onSuggestion = { sug ->
                                val target = routeFor(sug.kind)
                                when {
                                    sug.kind == SuggestionKind.START_VOICE -> onOpenVoice()
                                    target != null -> onSuggestionNavigate(target)
                                }
                            })
                        }
                    }
                }
            }

            ChatComposer(
                draft = state.draft,
                onUpdateDraft = viewModel::updateDraft,
                onSend = viewModel::sendDraft,
                onOpenVoice = onOpenVoice,
                sending = state.sending,
                disabled = state.emergencyEngaged,
            )
        }
    }
}

private fun routeFor(kind: SuggestionKind): String? = when (kind) {
    SuggestionKind.OPEN_TASKS -> Screen.Tasks.route
    SuggestionKind.OPEN_APPROVALS -> Screen.Approvals.route
    SuggestionKind.OPEN_MEMORY -> Screen.Memory.route
    SuggestionKind.OPEN_AUDIT -> Screen.Audit.route
    SuggestionKind.START_VOICE -> Screen.Voice.route
    SuggestionKind.NEW_TASK -> Screen.Tasks.route
    SuggestionKind.COPY_PROMPT -> null
}

@Composable
private fun MockBanner() {
    Surface(color = MaterialTheme.colorScheme.secondaryContainer) {
        Text(
            text = stringResource(R.string.chat_mock_banner),
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSecondaryContainer,
            modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
        )
    }
}

@Composable
private fun EmptyChat(onOpenVoice: () -> Unit) {
    Column(
        modifier = Modifier.fillMaxSize().padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        InteractiveIcon(sizeDp = 120, onClick = onOpenVoice, contentDescription = null)
        Spacer(modifier = Modifier.height(20.dp))
        Text(
            stringResource(R.string.chat_empty),
            style = MaterialTheme.typography.bodyLarge,
            color = MaterialTheme.colorScheme.onBackground,
        )
    }
}

@Composable
private fun ChatBubble(message: ChatMessage, onSuggestion: (ChatSuggestion) -> Unit) {
    val isUser = message.role == ChatRole.USER
    val isSystem = message.role == ChatRole.SYSTEM

    val alignment = if (isUser) Alignment.End else Alignment.Start
    val bubbleColor = when (message.role) {
        ChatRole.USER -> MaterialTheme.colorScheme.primaryContainer
        ChatRole.JARVIS -> MaterialTheme.colorScheme.surfaceVariant
        ChatRole.SYSTEM -> MaterialTheme.colorScheme.tertiary.copy(alpha = 0.18f)
    }
    val textColor = when (message.role) {
        ChatRole.USER -> MaterialTheme.colorScheme.onPrimaryContainer
        ChatRole.JARVIS -> MaterialTheme.colorScheme.onSurfaceVariant
        ChatRole.SYSTEM -> MaterialTheme.colorScheme.onSurface
    }

    Column(
        modifier = Modifier.fillMaxWidth(),
        horizontalAlignment = alignment,
    ) {
        Text(
            text = when (message.role) {
                ChatRole.USER -> stringResource(R.string.chat_role_user)
                ChatRole.JARVIS -> stringResource(R.string.chat_role_jarvis)
                ChatRole.SYSTEM -> stringResource(R.string.chat_role_system)
            },
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onBackground.copy(alpha = 0.6f),
            modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp),
        )
        Card(
            colors = CardDefaults.cardColors(containerColor = bubbleColor),
            shape = if (isSystem) RoundedCornerShape(8.dp)
                    else if (isUser) RoundedCornerShape(18.dp, 4.dp, 18.dp, 18.dp)
                    else RoundedCornerShape(4.dp, 18.dp, 18.dp, 18.dp),
            modifier = Modifier.widthIn(max = 320.dp),
        ) {
            Text(
                text = message.body,
                style = MaterialTheme.typography.bodyLarge,
                color = textColor,
                modifier = Modifier.padding(horizontal = 14.dp, vertical = 10.dp),
            )
        }
        message.suggestion?.let { sug ->
            AssistChip(
                onClick = { onSuggestion(sug) },
                label = { Text(sug.label) },
                modifier = Modifier.padding(top = 4.dp, start = 4.dp, end = 4.dp),
            )
        }
    }
}

@Composable
private fun ChatComposer(
    draft: String,
    onUpdateDraft: (String) -> Unit,
    onSend: () -> Unit,
    onOpenVoice: () -> Unit,
    sending: Boolean,
    disabled: Boolean,
) {
    Surface(
        color = MaterialTheme.colorScheme.background,
        tonalElevation = 4.dp,
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 8.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            IconButton(
                onClick = onOpenVoice,
                enabled = !disabled,
            ) {
                Icon(Icons.Default.Mic, contentDescription = stringResource(R.string.chat_voice))
            }
            OutlinedTextField(
                value = draft,
                onValueChange = onUpdateDraft,
                modifier = Modifier.weight(1f),
                placeholder = { Text(stringResource(R.string.chat_input_hint)) },
                enabled = !disabled,
                maxLines = 4,
            )
            FilledIconButton(
                onClick = onSend,
                enabled = !disabled && !sending && draft.isNotBlank(),
            ) {
                Icon(Icons.AutoMirrored.Filled.Send, contentDescription = stringResource(R.string.chat_send))
            }
        }
    }
}
