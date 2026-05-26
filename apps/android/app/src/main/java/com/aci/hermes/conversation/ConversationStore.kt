package com.aci.hermes.conversation

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import java.util.UUID

/**
 * In-memory store for the active Jarvis Prime conversation session.
 *
 * Persistence is intentionally out of scope here — conversations are
 * forwarded into the audit log + memory tree at write-time, so the raw
 * stream does not need to survive process death. Keeping it in-memory
 * also matches the safety stance: an owner who closes the app expects
 * the chat to clear.
 */
class ConversationStore {

    private val _sessionId = MutableStateFlow(UUID.randomUUID().toString())
    val sessionId: StateFlow<String> = _sessionId.asStateFlow()

    private val _turns = MutableStateFlow<List<ConversationTurn>>(emptyList())
    val turns: StateFlow<List<ConversationTurn>> = _turns.asStateFlow()

    fun append(turn: ConversationTurn) {
        _turns.update { it + turn }
    }

    /** Replace a streaming placeholder with its final immutable turn. */
    fun replace(turnId: String, finalTurn: ConversationTurn) {
        _turns.update { list ->
            list.map { if (it.id == turnId) finalTurn else it }
        }
    }

    /** Mutate the in-progress text of a streaming turn. */
    fun updateStreaming(turnId: String, text: String) {
        _turns.update { list ->
            list.map { if (it.id == turnId) it.copy(text = text, streaming = true) else it }
        }
    }

    fun newSession(): String {
        val id = UUID.randomUUID().toString()
        _sessionId.value = id
        _turns.value = emptyList()
        return id
    }
}
