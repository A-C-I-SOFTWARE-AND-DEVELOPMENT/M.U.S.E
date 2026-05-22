package com.aci.hermes.ui.screens.chat

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.model.ChatMessage
import com.aci.hermes.data.model.Role
import com.aci.hermes.data.network.HermesClientFactory
import com.aci.hermes.data.preferences.SettingsRepository
import com.aci.hermes.util.LogBuffer
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
    val mockMode: Boolean = false,
    val gatewayConfigured: Boolean = false
)

class ChatViewModel(
    private val settings: SettingsRepository,
    private val clientFactory: HermesClientFactory,
    private val logBuffer: LogBuffer
) : ViewModel() {

    private val _state = MutableStateFlow(ChatUiState())
    val state: StateFlow<ChatUiState> = _state.asStateFlow()
    private var inflight: Job? = null

    init {
        viewModelScope.launch {
            val snap = settings.snapshot()
            _state.update {
                it.copy(
                    mockMode = snap.mockMode,
                    gatewayConfigured = snap.gatewayUrl.isNotBlank()
                )
            }
        }
    }

    fun setInput(v: String) = _state.update { it.copy(input = v) }

    fun send() {
        val prompt = _state.value.input.trim()
        if (prompt.isEmpty() || _state.value.sending) return
        val userMsg = ChatMessage(role = Role.USER, content = prompt)
        _state.update {
            it.copy(
                messages = it.messages + userMsg,
                input = "",
                sending = true
            )
        }
        inflight = viewModelScope.launch {
            val client = clientFactory.current()
            val history = _state.value.messages.dropLast(1) // exclude the just-added user msg
            client.chat(history, prompt).collect { chunk ->
                _state.update { current ->
                    val existingIdx = current.messages.indexOfFirst { it.id == chunk.id }
                    val updated = if (existingIdx == -1) {
                        current.messages + chunk
                    } else {
                        current.messages.toMutableList().also { it[existingIdx] = chunk }
                    }
                    current.copy(
                        messages = updated,
                        sending = chunk.pending
                    )
                }
            }
            _state.update { it.copy(sending = false) }
        }
    }

    fun newConversation() {
        inflight?.cancel()
        _state.update { it.copy(messages = emptyList(), sending = false) }
    }
}
