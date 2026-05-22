package com.aci.hermes.data.network

import com.aci.hermes.data.model.ChatMessage
import com.aci.hermes.data.model.HermesStatus
import com.aci.hermes.data.model.Role
import com.aci.hermes.util.LogBuffer
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
import kotlinx.coroutines.flow.flowOn
import kotlinx.coroutines.withContext
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import okhttp3.sse.EventSource
import okhttp3.sse.EventSourceListener
import okhttp3.sse.EventSources
import java.util.UUID

/**
 * Direct OpenAI-compatible client. Used by **Direct Personal API Mode**:
 * the phone talks straight to the provider with a user-supplied API key.
 * No Hermes gateway in the loop.
 *
 * Wire format is the standard OpenAI chat-completions surface:
 *
 *   * GET  ${baseUrl}/models               — auth check used by `status()`
 *   * POST ${baseUrl}/chat/completions     — streaming chat
 *
 * Both OpenRouter (`https://openrouter.ai/api/v1`) and OpenAI
 * (`https://api.openai.com/v1`) speak this. Custom OpenAI-compatible
 * endpoints work the same way — pass their base URL.
 *
 * **Security:** the API key never leaves the device except as a Bearer
 * token on these two HTTPS endpoints. It is *not* logged. Personal-use
 * mode only — see the warning text in `ProviderScreen`.
 */
class DirectAIClient(
    private val http: OkHttpClient,
    private val baseUrl: String,
    private val apiKey: String,
    private val model: String,
    private val providerLabel: String,
    private val extraHeaders: Map<String, String> = emptyMap(),
    private val logBuffer: LogBuffer
) : AIClient {

    override val isMock: Boolean = false
    override val providerName: String = "$providerLabel ($model)"

    private val json = Json {
        ignoreUnknownKeys = true
        explicitNulls = false
    }

    private fun urlOf(path: String): String {
        val base = baseUrl.trimEnd('/')
        val p = if (path.startsWith('/')) path else "/$path"
        return "$base$p"
    }

    private fun authedRequest(path: String, accept: String): Request.Builder {
        val builder = Request.Builder().url(urlOf(path))
            .header("Authorization", "Bearer $apiKey")
            .header("Accept", accept)
        extraHeaders.forEach { (k, v) -> builder.header(k, v) }
        return builder
    }

    /**
     * Touches `${baseUrl}/models` to verify the key + connectivity. We don't
     * parse the model list — a 200 is enough to know the credential works
     * and the model name (which is just a string in the chat request) is
     * the user's responsibility.
     */
    override suspend fun status(): HermesStatus = withContext(Dispatchers.IO) {
        val req = authedRequest("/models", "application/json").get().build()
        try {
            http.newCall(req).execute().use { resp ->
                if (resp.isSuccessful) {
                    HermesStatus(
                        ok = true,
                        providerId = providerLabel.lowercase(),
                        model = model,
                        message = "${resp.code} OK from $providerLabel"
                    )
                } else {
                    val body = resp.body?.string().orEmpty().take(200)
                    val msg = "$providerLabel returned HTTP ${resp.code}${if (body.isNotBlank()) ": $body" else ""}"
                    logBuffer.warn(TAG, msg)
                    HermesStatus(ok = false, providerId = providerLabel.lowercase(), model = model, message = msg)
                }
            }
        } catch (t: Throwable) {
            logBuffer.error(TAG, "Direct API status failed: ${t.message}")
            HermesStatus(
                ok = false,
                providerId = providerLabel.lowercase(),
                model = model,
                message = friendlyNetworkError(t)
            )
        }
    }

    override fun chat(history: List<ChatMessage>, prompt: String): Flow<ChatMessage> = callbackFlow {
        val id = UUID.randomUUID().toString()
        val turns = buildList {
            // Inject a small system prompt so empty histories still feel
            // grounded. The user can override by adding their own
            // SYSTEM-role messages to history.
            if (history.none { it.role == Role.SYSTEM }) {
                add(OpenAiTurnDto(role = "system", content = "You are a helpful assistant."))
            }
            history.forEach { add(OpenAiTurnDto(role = it.role.openAiName(), content = it.content)) }
            add(OpenAiTurnDto(role = "user", content = prompt))
        }
        val payload = OpenAiChatRequestDto(
            model = model,
            messages = turns,
            temperature = 0.7,
            stream = true
        )
        val body = json.encodeToString(OpenAiChatRequestDto.serializer(), payload)
            .toRequestBody("application/json".toMediaType())
        val request = authedRequest("/chat/completions", "text/event-stream").post(body).build()

        val acc = StringBuilder()
        var terminalEmitted = false

        val listener = object : EventSourceListener() {
            override fun onOpen(eventSource: EventSource, response: Response) {
                logBuffer.info(TAG, "$providerLabel SSE open: HTTP ${response.code}")
                trySend(ChatMessage(id = id, role = Role.ASSISTANT, content = "", pending = true))
            }

            override fun onEvent(eventSource: EventSource, eventId: String?, type: String?, data: String) {
                // OpenAI uses `data: [DONE]` as the terminator.
                if (data.trim() == "[DONE]") {
                    terminalEmitted = true
                    trySend(ChatMessage(id = id, role = Role.ASSISTANT, content = acc.toString(), pending = false))
                    return
                }
                val chunk = runCatching { json.decodeFromString(OpenAiChunkDto.serializer(), data) }
                    .onFailure { logBuffer.warn(TAG, "SSE parse failed: ${it.message} (data=${data.take(120)})") }
                    .getOrNull() ?: return
                val piece = chunk.choices.firstOrNull()?.delta?.content
                if (!piece.isNullOrEmpty()) {
                    acc.append(piece)
                    trySend(ChatMessage(id = id, role = Role.ASSISTANT, content = acc.toString(), pending = true))
                }
            }

            override fun onClosed(eventSource: EventSource) {
                if (!terminalEmitted) {
                    trySend(ChatMessage(id = id, role = Role.ASSISTANT, content = acc.toString(), pending = false))
                }
                close()
            }

            override fun onFailure(eventSource: EventSource, t: Throwable?, response: Response?) {
                val httpCode = response?.code
                val httpBody = response?.body?.string()?.take(200).orEmpty()
                val reason = when {
                    httpCode != null -> "HTTP $httpCode${if (httpBody.isNotBlank()) ": $httpBody" else ""}"
                    t != null -> friendlyNetworkError(t)
                    else -> "stream failed"
                }
                logBuffer.error(TAG, "$providerLabel SSE failure: $reason")
                terminalEmitted = true
                trySend(
                    ChatMessage(
                        id = id,
                        role = Role.ASSISTANT,
                        content = acc.toString(),
                        pending = false,
                        errorText = reason
                    )
                )
                close()
            }
        }

        val es = EventSources.createFactory(http).newEventSource(request, listener)
        awaitClose { es.cancel() }
    }.flowOn(Dispatchers.IO)

    private fun Role.openAiName(): String = when (this) {
        Role.USER -> "user"
        Role.ASSISTANT -> "assistant"
        Role.SYSTEM -> "system"
        Role.TOOL -> "tool"
    }

    @Serializable
    private data class OpenAiChatRequestDto(
        val model: String,
        val messages: List<OpenAiTurnDto>,
        val temperature: Double = 0.7,
        val stream: Boolean = true
    )

    @Serializable
    private data class OpenAiTurnDto(val role: String, val content: String)

    @Serializable
    private data class OpenAiChunkDto(
        val id: String? = null,
        @SerialName("object") val obj: String? = null,
        val choices: List<OpenAiChoiceDto> = emptyList()
    )

    @Serializable
    private data class OpenAiChoiceDto(
        val index: Int? = null,
        val delta: OpenAiDeltaDto? = null,
        @SerialName("finish_reason") val finishReason: String? = null
    )

    @Serializable
    private data class OpenAiDeltaDto(
        val role: String? = null,
        val content: String? = null
    )

    companion object {
        private const val TAG = "DirectAI"

        const val OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
        const val OPENAI_BASE_URL = "https://api.openai.com/v1"

        /** Recommended-default headers for OpenRouter requests (per their docs). */
        val OPENROUTER_HEADERS: Map<String, String> = mapOf(
            "HTTP-Referer" to "app-local-personal-use",
            "X-OpenRouter-Title" to "Hermes Personal Mobile"
        )

        private fun friendlyNetworkError(t: Throwable): String {
            val msg = t.message.orEmpty()
            return when {
                "UnknownHost" in t::class.java.simpleName ->
                    "Can't resolve the API host. Check your internet connection."
                "ConnectException" in t::class.java.simpleName ->
                    "Couldn't connect to the API. Check your connection."
                "SocketTimeout" in t::class.java.simpleName ->
                    "Request timed out. Try again."
                "SSL" in t::class.java.simpleName ->
                    "TLS handshake failed: $msg"
                msg.isNotBlank() -> msg
                else -> t::class.java.simpleName
            }
        }
    }
}
