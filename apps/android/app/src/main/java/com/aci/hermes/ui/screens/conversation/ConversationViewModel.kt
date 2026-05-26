package com.aci.hermes.ui.screens.conversation

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.conversation.ConversationEngine
import com.aci.hermes.conversation.ConversationStore
import com.aci.hermes.conversation.ConversationTurn
import com.aci.hermes.util.LogBuffer
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class ConversationUiState(
    val sessionId: String = "",
    val turns: List<ConversationTurn> = emptyList(),
    val input: String = "",
    val sending: Boolean = false,
    val error: String? = null,
)

class ConversationViewModel(
    private val engine: ConversationEngine,
    private val store: ConversationStore,
    private val logBuffer: LogBuffer,
) : ViewModel() {

    private val input = MutableStateFlow("")
    private val sending = MutableStateFlow(false)
    private val error = MutableStateFlow<String?>(null)

    private val _state = MutableStateFlow(ConversationUiState())
    val state: StateFlow<ConversationUiState> = _state.asStateFlow()

    init {
        viewModelScope.launch {
            combine(store.sessionId, store.turns, input, sending, error) { session, turns, draft, isSending, err ->
                ConversationUiState(
                    sessionId = session,
                    turns = turns,
                    input = draft,
                    sending = isSending,
                    error = err,
                )
            }.collect { _state.value = it }
        }
    }

    fun updateInput(value: String) {
        input.value = value
    }

    fun clear() {
        store.newSession()
        input.value = ""
        error.value = null
    }

    fun send() {
        val text = input.value.trim()
        if (text.isEmpty() || sending.value) return
        val session = store.sessionId.value
        val ownerTurn = ConversationTurn(
            sessionId = session,
            author = ConversationTurn.Author.OWNER,
            text = text,
        )
        store.append(ownerTurn)
        input.value = ""
        sending.value = true
        error.value = null

        viewModelScope.launch {
            var placeholderId: String? = null
            engine.submit(session, text).collect { event ->
                when (event) {
                    is ConversationEngine.Event.Chunk -> {
                        if (placeholderId == null) {
                            placeholderId = event.turnId
                            store.append(
                                ConversationTurn(
                                    id = event.turnId,
                                    sessionId = session,
                                    author = ConversationTurn.Author.JARVIS,
                                    text = event.text,
                                    streaming = true,
                                )
                            )
                        } else {
                            store.updateStreaming(event.turnId, event.text)
                        }
                    }
                    is ConversationEngine.Event.Complete -> {
                        store.replace(event.turn.id, event.turn)
                        sending.update { false }
                    }
                    is ConversationEngine.Event.Error -> {
                        logBuffer.error("ConversationEngine", event.message)
                        error.value = event.message
                        sending.update { false }
                    }
                }
            }
        }
    }
}
