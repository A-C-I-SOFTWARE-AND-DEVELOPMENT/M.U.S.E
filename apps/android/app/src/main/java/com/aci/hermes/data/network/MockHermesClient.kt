package com.aci.hermes.data.network

import com.aci.hermes.data.model.ChatMessage
import com.aci.hermes.data.model.HermesStatus
import com.aci.hermes.data.model.Role
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import java.util.UUID

/**
 * Pretend gateway. Lets the UI be exercised without any backend wired up.
 * Replies with deterministic, lightly-templated responses so the chat
 * screen has something to render during development and demos.
 */
class MockHermesClient : HermesClient {
    override val isMock: Boolean = true

    override suspend fun status(): HermesStatus = HermesStatus(
        ok = true,
        version = "mock-0.1.0",
        providerId = "mock",
        model = "hermes-mock",
        message = "Mock gateway — no network calls made."
    )

    override fun chat(history: List<ChatMessage>, prompt: String): Flow<ChatMessage> = flow {
        val id = UUID.randomUUID().toString()
        val canned = mockReplyFor(prompt)
        val words = canned.split(' ')
        val acc = StringBuilder()
        emit(ChatMessage(id = id, role = Role.ASSISTANT, content = "", pending = true))
        for ((i, w) in words.withIndex()) {
            delay(40)
            if (i > 0) acc.append(' ')
            acc.append(w)
            emit(
                ChatMessage(
                    id = id,
                    role = Role.ASSISTANT,
                    content = acc.toString(),
                    pending = i != words.lastIndex
                )
            )
        }
    }

    private fun mockReplyFor(prompt: String): String {
        val p = prompt.trim().lowercase()
        return when {
            "hello" in p || "hi" in p ->
                "Hello! This is mock mode — your UI works but no real model is being called. " +
                    "Configure a Hermes gateway in Settings to talk to a live agent."
            "status" in p || "health" in p ->
                "Mock gateway is healthy. Provider: mock. Model: hermes-mock."
            "help" in p ->
                "Mock mode: try asking 'hello', 'status', or anything else — replies are canned but streaming-style."
            else ->
                "[mock reply] I received: \"${prompt.take(120)}\". Wire up a real Hermes gateway in Settings to get an actual response."
        }
    }
}
