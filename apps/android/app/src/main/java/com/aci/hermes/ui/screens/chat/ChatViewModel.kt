package com.aci.hermes.ui.screens.chat

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.audit.AuditRepository
import com.aci.hermes.data.emergency.EmergencyStopController
import com.aci.hermes.data.gateway.GatewayEventSpine
import com.aci.hermes.data.model.AuditEvent
import com.aci.hermes.data.model.AuditSeverity
import com.aci.hermes.data.redaction.Redactor
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.util.UUID

enum class ChatRole { USER, JARVIS }

data class ChatMessage(
    val id: String = UUID.randomUUID().toString(),
    val role: ChatRole,
    val text: String,
    val redactedFields: List<String> = emptyList(),
    val createdAt: Long = System.currentTimeMillis(),
)

data class ChatUiState(
    val messages: List<ChatMessage> = emptyList(),
    val draft: String = "",
    val sending: Boolean = false,
    val blockedByEmergency: Boolean = false,
    val createdApprovalId: String? = null,
)

class ChatViewModel(
    private val spine: GatewayEventSpine,
    private val emergency: EmergencyStopController,
    private val audit: AuditRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(ChatUiState())
    val state: StateFlow<ChatUiState> = _state.asStateFlow()

    init {
        viewModelScope.launch {
            emergency.state.collect { es ->
                _state.update { it.copy(blockedByEmergency = es.armed) }
            }
        }
    }

    fun onDraftChange(value: String) {
        _state.update { it.copy(draft = value) }
    }

    fun send() {
        val draft = _state.value.draft.trim()
        if (draft.isEmpty()) return
        if (emergency.isArmed()) return
        val client = spine.current() ?: return
        val redaction = Redactor.redact(draft)
        val userMsg = ChatMessage(
            role = ChatRole.USER,
            text = redaction.text,
            redactedFields = redaction.redactedFields,
        )
        _state.update { it.copy(messages = it.messages + userMsg, draft = "", sending = true) }

        viewModelScope.launch {
            val response = runCatching { client.submitChat(draft) }.getOrNull()
            val reply = response?.replyText.orEmpty()
            val replyMsg = ChatMessage(role = ChatRole.JARVIS, text = reply)
            _state.update {
                it.copy(
                    messages = it.messages + replyMsg,
                    sending = false,
                    createdApprovalId = response?.createdApprovalId,
                )
            }
            audit.append(
                AuditEvent(
                    actor = "user",
                    action = "chat_send",
                    target = "jarvis",
                    payloadSummary = redaction.text.take(120),
                    severity = AuditSeverity.INFO,
                    proofHash = "",
                )
            )
        }
    }

    fun consumeApprovalNavigation() {
        _state.update { it.copy(createdApprovalId = null) }
    }
}
