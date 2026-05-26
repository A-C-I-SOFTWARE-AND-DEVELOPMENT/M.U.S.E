package com.aci.hermes.ui.screens.conversation

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Send
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.aci.hermes.R
import com.aci.hermes.conversation.ConversationTurn
import com.aci.hermes.ui.theme.JarvisCyan
import com.aci.hermes.ui.theme.JarvisGold
import com.aci.hermes.ui.theme.JarvisNavyElevated

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ConversationScreen(
    viewModel: ConversationViewModel,
    onBack: () -> Unit,
    onTapVoice: () -> Unit,
) {
    val state by viewModel.state.collectAsState()
    val listState = rememberLazyListState()

    LaunchedEffect(state.turns.size) {
        if (state.turns.isNotEmpty()) {
            listState.animateScrollToItem(state.turns.lastIndex)
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.conversation_title)) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = stringResource(R.string.action_back))
                    }
                },
                actions = {
                    IconButton(onClick = viewModel::clear) {
                        Icon(Icons.Default.Refresh, contentDescription = stringResource(R.string.conversation_clear))
                    }
                },
            )
        },
        bottomBar = {
            ConversationInputBar(
                input = state.input,
                onInputChange = viewModel::updateInput,
                sending = state.sending,
                onSend = viewModel::send,
                onTapVoice = onTapVoice,
            )
        },
    ) { padding ->
        if (state.turns.isEmpty()) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding),
                contentAlignment = Alignment.Center,
            ) {
                Text(
                    stringResource(R.string.conversation_empty),
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        } else {
            LazyColumn(
                state = listState,
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding)
                    .padding(horizontal = 12.dp),
                contentPadding = PaddingValues(vertical = 12.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                items(state.turns, key = { it.id }) { TurnBubble(turn = it) }
                state.error?.let { err ->
                    item {
                        Text(
                            text = err,
                            color = MaterialTheme.colorScheme.error,
                            style = MaterialTheme.typography.bodySmall,
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun TurnBubble(turn: ConversationTurn) {
    val isOwner = turn.author == ConversationTurn.Author.OWNER
    val bubbleColor: Color = when (turn.author) {
        ConversationTurn.Author.OWNER -> JarvisGold
        ConversationTurn.Author.JARVIS -> JarvisNavyElevated
        ConversationTurn.Author.SYSTEM -> MaterialTheme.colorScheme.outline
    }
    val textColor: Color = if (isOwner) MaterialTheme.colorScheme.onPrimary
        else MaterialTheme.colorScheme.onSurface

    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = if (isOwner) Arrangement.End else Arrangement.Start,
    ) {
        Box(
            modifier = Modifier
                .widthIn(max = 320.dp)
                .clip(RoundedCornerShape(16.dp))
                .background(bubbleColor)
                .padding(horizontal = 14.dp, vertical = 10.dp),
        ) {
            Column {
                Text(
                    text = turn.text,
                    color = textColor,
                    style = MaterialTheme.typography.bodyMedium,
                )
                if (turn.streaming) {
                    Text(
                        text = "…",
                        color = JarvisCyan,
                        style = MaterialTheme.typography.labelSmall,
                    )
                }
            }
        }
    }
}

@Composable
private fun ConversationInputBar(
    input: String,
    onInputChange: (String) -> Unit,
    sending: Boolean,
    onSend: () -> Unit,
    onTapVoice: () -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 12.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        OutlinedTextField(
            value = input,
            onValueChange = onInputChange,
            modifier = Modifier.weight(1f),
            placeholder = { Text(stringResource(R.string.conversation_input_placeholder)) },
            singleLine = false,
            maxLines = 4,
            enabled = !sending,
        )
        IconButton(onClick = onTapVoice) {
            Icon(Icons.Default.Mic, contentDescription = stringResource(R.string.conversation_voice), tint = JarvisCyan)
        }
        Button(onClick = onSend, enabled = input.isNotBlank() && !sending) {
            Icon(Icons.Default.Send, contentDescription = stringResource(R.string.conversation_send))
        }
    }
}
