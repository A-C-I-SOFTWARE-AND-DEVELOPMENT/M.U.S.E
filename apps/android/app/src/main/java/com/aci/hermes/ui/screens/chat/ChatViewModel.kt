package com.aci.hermes.ui.screens.chat

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.model.ChatMessage
import com.aci.hermes.data.model.Role
import com.aci.hermes.data.network.AIClientFactory
import com.aci.hermes.data.preferences.ConnectionMode
import com.aci.hermes.data.preferences.SettingsRepository
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class ChatUiState(
    val messages: List<ChatMessage> = emptyList(),
    val input: String = "",
    val sending: Boolean = false,
    val mode: ConnectionMode = ConnectionMode.MOCK,
    val gatewayConfigured: Boolean = false,
    val directConfigured: Boolean = false,
    val model: String = "",
    /** Bumped on `newConversation()` — chunks tagged with a stale epoch are dropped. */
    val conversationEpoch: Int = 0
)

class ChatViewModel(
    private val settings: SettingsRepository,
    private val clientFactory: AIClientFactory
) : ViewModel() {

    private val _state = MutableStateFlow(ChatUiState())
    val state: StateFlow<ChatUiState> = _state.asStateFlow()
    private var inflight: Job? = null

    init {
        viewModelScope.launch {
            val snap = settings.snapshot()
            val secrets = settings.secretsSnapshot()
            _state.update {
                it.copy(
                    mode = snap.connectionMode,
                    gatewayConfigured = snap.gatewayUrl.isNotBlank(),
                    directConfigured = !secrets.providerApiKey.isNullOrBlank(),
                    model = snap.model
                )
            }
        }
    }

    fun setInput(v: String) = _state.update { it.copy(input = v) }

    fun send() {
        val prompt = _state.value.input.trim()
        if (prompt.isEmpty() || _state.value.sending) return
        val userMsg = ChatMessage(role = Role.USER, content = prompt)
        val epoch = _state.value.conversationEpoch
        _state.update {
            it.copy(
                messages = it.messages + userMsg,
                input = "",
                sending = true
            )
        }
        inflight = viewModelScope.launch {
            try {
                val client = clientFactory.current()
                val history = _state.value.messages.dropLast(1)
                client.chat(history, prompt).collect { chunk ->
                    if (_state.value.conversationEpoch != epoch) return@collect
                    _state.update { current ->
                        val existingIdx = current.messages.indexOfFirst { it.id == chunk.id }
                        val updated = if (existingIdx == -1) {
                            current.messages + chunk
                        } else {
                            current.messages.toMutableList().also { it[existingIdx] = chunk }
                        }
                        current.copy(messages = updated, sending = chunk.pending)
                    }
                }
            } finally {
                if (_state.value.conversationEpoch == epoch) {
                    _state.update { it.copy(sending = false) }
                }
            }
        }
    }

    fun newConversation() {
        inflight?.cancel()
        _state.update {
            it.copy(
                messages = emptyList(),
                sending = false,
                conversationEpoch = it.conversationEpoch + 1
            )
        }
    }
}
