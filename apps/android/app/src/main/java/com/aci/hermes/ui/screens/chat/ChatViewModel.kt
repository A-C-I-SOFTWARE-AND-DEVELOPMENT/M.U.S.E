package com.aci.hermes.ui.screens.chat

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.audit.AuditRepository
import com.aci.hermes.data.conversation.ConversationRepository
import com.aci.hermes.data.conversation.JarvisConversationEngine
import com.aci.hermes.data.emergency.EmergencyStopController
import com.aci.hermes.data.model.AuditKind
import com.aci.hermes.data.model.ChatMessage
import com.aci.hermes.data.preferences.SettingsRepository
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class ChatUiState(
    val draft: String = "",
    val messages: List<ChatMessage> = emptyList(),
    val mockMode: Boolean = true,
    val emergencyEngaged: Boolean = false,
    val sending: Boolean = false,
)

class ChatViewModel(
    application: Application,
    private val settings: SettingsRepository,
    private val conversations: ConversationRepository,
    private val engine: JarvisConversationEngine,
    private val audit: AuditRepository,
    private val emergencyStop: EmergencyStopController,
) : AndroidViewModel(application) {

    private val _state = MutableStateFlow(ChatUiState())
    val state: StateFlow<ChatUiState> = _state.asStateFlow()

    init {
        viewModelScope.launch {
            conversations.messages.collect { list ->
                _state.update { it.copy(messages = list) }
            }
        }
        viewModelScope.launch {
            settings.mockMode.collect { mock ->
                _state.update { it.copy(mockMode = mock) }
            }
        }
        viewModelScope.launch {
            emergencyStop.state.collect { es ->
                _state.update { it.copy(emergencyEngaged = es.engaged) }
            }
        }
    }

    fun updateDraft(text: String) {
        _state.update { it.copy(draft = text) }
    }

    fun sendDraft() {
        val text = _state.value.draft.trim()
        if (text.isEmpty() || _state.value.sending) return
        if (_state.value.emergencyEngaged) {
            viewModelScope.launch {
                conversations.appendSystem("Emergency stop engaged. Release it to resume chatting.")
            }
            return
        }
        viewModelScope.launch {
            _state.update { it.copy(sending = true) }
            conversations.appendUser(text)
            _state.update { it.copy(draft = "") }
            // Light "thinking" delay so the UI feels alive without
            // blocking. Mock mode only — when a real gateway is wired,
            // this is where dispatch happens.
            delay(250)
            val reply = engine.reply(text)
            conversations.append(reply)
            audit.record(
                kind = AuditKind.SYSTEM,
                title = "Chat exchange",
                detail = "User: \"${text.take(60)}\"\nJarvis: \"${reply.body.take(120)}\"",
            )
            _state.update { it.copy(sending = false) }
        }
    }

    fun clear() {
        viewModelScope.launch {
            conversations.clear()
            audit.record(
                kind = AuditKind.SYSTEM,
                title = "Chat cleared",
                detail = "User cleared the conversation history.",
            )
        }
    }
}
