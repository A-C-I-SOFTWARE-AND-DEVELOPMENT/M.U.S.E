package com.aci.hermes.data.conversation

import android.content.Context
import com.aci.hermes.data.JsonStore
import com.aci.hermes.data.model.ChatMessage
import com.aci.hermes.data.model.ChatRole
import kotlinx.coroutines.flow.StateFlow

/**
 * Conversation Engine — the chat history visible on the Chat screen.
 *
 * Bounded at 500 messages; oldest drop off so the JSON file stays
 * small even after years of chatting. The conversation is purely
 * local — nothing leaves the device.
 */
class ConversationRepository(context: Context) {
    private val store = JsonStore(
        context = context,
        fileName = "jarvis_conversation.json",
        serializer = ChatMessage.serializer(),
        maxItems = MAX_MESSAGES,
    )

    val messages: StateFlow<List<ChatMessage>> = store.items

    suspend fun load() {
        store.load()
    }

    suspend fun append(message: ChatMessage) {
        store.add(message, atStart = false)
    }

    suspend fun appendUser(text: String) {
        if (text.isBlank()) return
        append(ChatMessage(role = ChatRole.USER, body = text.trim()))
    }

    suspend fun appendJarvis(text: String) {
        append(ChatMessage(role = ChatRole.JARVIS, body = text.trim()))
    }

    suspend fun appendSystem(text: String) {
        append(ChatMessage(role = ChatRole.SYSTEM, body = text.trim()))
    }

    suspend fun clear() {
        store.clear()
    }

    companion object {
        const val MAX_MESSAGES = 500
    }
}
