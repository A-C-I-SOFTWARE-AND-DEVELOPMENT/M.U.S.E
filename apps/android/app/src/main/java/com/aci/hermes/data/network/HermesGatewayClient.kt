package com.aci.hermes.data.network

import com.aci.hermes.data.model.ChatMessage
import com.aci.hermes.data.model.HermesStatus
import com.aci.hermes.data.model.Role
import com.aci.hermes.util.GatewayUrl
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
import java.util.concurrent.TimeUnit

/**
 * HTTP client for the Hermes gateway REST surface.
 *
 * Endpoints used (see `apps/android/docs/ARCHITECTURE.md`):
 *   * GET  /v1/health            → [HermesStatus]
 *   * POST /v1/chat              → SSE stream of `delta`/`done`/`error` events
 *
 * The [OkHttpClient] is supplied by [com.aci.hermes.di.AppContainer] and
 * shared across all instances so the dispatcher executor and connection
 * pool aren't leaked across navigation.
 */
class HermesGatewayClient(
    private val http: OkHttpClient,
    private val baseUrl: String,
    private val token: String?,
    private val providerApiKey: String?,
    private val providerId: String?,
    private val logBuffer: LogBuffer
) : AIClient {

    override val isMock: Boolean = false
    override val providerName: String = "Hermes gateway"

    private val json = Json {
        ignoreUnknownKeys = true
        encodeDefaults = true
        explicitNulls = false
    }

    private fun urlOf(path: String): String {
        val base = baseUrl.trimEnd('/')
        val p = if (path.startsWith('/')) path else "/$path"
        return "$base$p"
    }

    /**
     * Sets the auth + provider-key headers and the supplied `Accept` value.
     * Uses `.header()` (replace, not append) so a caller-specified Accept
     * overrides any prior value — important for the SSE stream which needs
     * `text/event-stream`.
     *
     * `provider_id` is intentionally NOT sent as a header: it travels in
     * the JSON body of `/v1/chat` instead, so we have a single source of
     * truth for which provider the request targets.
     */
    private fun authedRequest(path: String, accept: String): Request.Builder {
        val builder = Request.Builder().url(urlOf(path))
        token?.takeIf { it.isNotBlank() }?.let { builder.header("Authorization", "Bearer $it") }
        providerApiKey?.takeIf { it.isNotBlank() }?.let { builder.header("X-Hermes-Provider-Key", it) }
        builder.header("Accept", accept)
        return builder
    }

    override suspend fun status(): HermesStatus = withContext(Dispatchers.IO) {
        // Health-check uses a derived client with a hard call timeout so
        // we never sit waiting the OS-default 75-100s when the host is
        // dropping SYNs (e.g. real phone dialling the emulator-only
        // 10.0.2.2 address). The main `http` client deliberately disables
        // read timeouts for the SSE chat stream, so we can't reuse it.
        val probe = http.newBuilder()
            .connectTimeout(HEALTH_CONNECT_TIMEOUT_SEC, TimeUnit.SECONDS)
            .readTimeout(HEALTH_READ_TIMEOUT_SEC, TimeUnit.SECONDS)
            .writeTimeout(HEALTH_READ_TIMEOUT_SEC, TimeUnit.SECONDS)
            .callTimeout(HEALTH_CALL_TIMEOUT_SEC, TimeUnit.SECONDS)
            .build()
        val request = authedRequest("/v1/health", "application/json").get().build()
        try {
            probe.newCall(request).execute().use { resp: Response ->
                if (!resp.isSuccessful) {
                    val classified = GatewayUrl.classifyFailure(
                        t = null,
                        httpCode = resp.code,
                        gatewayUrl = baseUrl
                    )
                    logBuffer.warn(TAG, "Gateway HTTP ${resp.code}")
                    return@withContext HermesStatus(
                        ok = false,
                        message = classified.message,
                        failureKind = classified.kind
                    )
                }
                val body = resp.body?.string().orEmpty()
                if (body.isBlank()) {
                    return@withContext HermesStatus(ok = true, message = "Gateway returned empty body")
                }
                val parsed = runCatching { json.decodeFromString(HealthDto.serializer(), body) }
                    .onFailure { logBuffer.warn(TAG, "Health parse failed: ${it.message}") }
                    .getOrNull()
                if (parsed == null) {
                    return@withContext HermesStatus(ok = true, message = "Gateway responded (unparsed body)")
                }
                HermesStatus(
                    ok = parsed.ok ?: true,
                    version = parsed.version,
                    providerId = parsed.providerId ?: providerId,
                    model = parsed.model,
                    message = parsed.message
                )
            }
        } catch (t: Throwable) {
            val classified = GatewayUrl.classifyFailure(t = t, gatewayUrl = baseUrl)
            logBuffer.error(TAG, "Health check failed (${classified.kind}): ${t.message}")
            HermesStatus(
                ok = false,
                message = classified.message,
                failureKind = classified.kind
            )
        }
    }

    override fun chat(history: List<ChatMessage>, prompt: String): Flow<ChatMessage> = callbackFlow {
        val id = UUID.randomUUID().toString()
        val payload = ChatRequestDto(
            providerId = providerId,
            messages = (history + ChatMessage(role = Role.USER, content = prompt)).map {
                ChatTurnDto(role = it.role.serialName(), content = it.content)
            }
        )
        val body = json.encodeToString(ChatRequestDto.serializer(), payload)
            .toRequestBody("application/json".toMediaType())
        val request = authedRequest("/v1/chat", "text/event-stream").post(body).build()

        val acc = StringBuilder()
        // Once a terminal event (done/error) is emitted, ignore onClosed so
        // it cannot overwrite an error bubble with a clean one.
        var terminalEmitted = false

        val listener = object : EventSourceListener() {
            override fun onOpen(eventSource: EventSource, response: Response) {
                logBuffer.info(TAG, "SSE open: HTTP ${response.code}")
                trySend(ChatMessage(id = id, role = Role.ASSISTANT, content = "", pending = true))
            }

            override fun onEvent(eventSource: EventSource, eventId: String?, type: String?, data: String) {
                val event = runCatching { json.decodeFromString(SseEventDto.serializer(), data) }
                    .onFailure { logBuffer.warn(TAG, "SSE parse failed: ${it.message} (data=${data.take(120)})") }
                    .getOrNull() ?: return
                when (event.type) {
                    "delta" -> {
                        if (!event.text.isNullOrEmpty()) {
                            acc.append(event.text)
                            trySend(
                                ChatMessage(id = id, role = Role.ASSISTANT, content = acc.toString(), pending = true)
                            )
                        }
                    }
                    "error" -> {
                        terminalEmitted = true
                        trySend(
                            ChatMessage(
                                id = id,
                                role = Role.ASSISTANT,
                                content = acc.toString(),
                                pending = false,
                                errorText = event.message ?: "Gateway reported an error"
                            )
                        )
                    }
                    "done" -> {
                        terminalEmitted = true
                        trySend(ChatMessage(id = id, role = Role.ASSISTANT, content = acc.toString(), pending = false))
                    }
                }
            }

            override fun onClosed(eventSource: EventSource) {
                logBuffer.info(TAG, "SSE closed")
                if (!terminalEmitted) {
                    trySend(ChatMessage(id = id, role = Role.ASSISTANT, content = acc.toString(), pending = false))
                }
                close()
            }

            override fun onFailure(eventSource: EventSource, t: Throwable?, response: Response?) {
                val classified = GatewayUrl.classifyFailure(
                    t = t,
                    httpCode = response?.code,
                    gatewayUrl = baseUrl
                )
                logBuffer.error(TAG, "SSE failure (${classified.kind}): ${classified.message}")
                terminalEmitted = true
                trySend(
                    ChatMessage(
                        id = id,
                        role = Role.ASSISTANT,
                        content = acc.toString(),
                        pending = false,
                        errorText = classified.message
                    )
                )
                close()
            }
        }

        // SSE has no read-timeout (the stream is intentionally open-ended)
        // so we use the shared client. But we apply a short *connect*
        // budget — once the TCP handshake succeeds, the stream may live
        // for minutes; failing the dial in ~5s is the user-friendly
        // behaviour when the URL is wrong.
        val sseClient = http.newBuilder()
            .connectTimeout(CHAT_CONNECT_TIMEOUT_SEC, TimeUnit.SECONDS)
            .build()
        val es = EventSources.createFactory(sseClient).newEventSource(request, listener)
        awaitClose { es.cancel() }
    }.flowOn(Dispatchers.IO)

    private fun Role.serialName(): String = when (this) {
        Role.USER -> "user"
        Role.ASSISTANT -> "assistant"
        Role.SYSTEM -> "system"
        Role.TOOL -> "tool"
    }

    @Serializable
    private data class HealthDto(
        val ok: Boolean? = null,
        val version: String? = null,
        @SerialName("provider_id") val providerId: String? = null,
        val model: String? = null,
        val message: String? = null
    )

    @Serializable
    private data class ChatRequestDto(
        @SerialName("provider_id") val providerId: String? = null,
        val messages: List<ChatTurnDto>
    )

    @Serializable
    private data class ChatTurnDto(val role: String, val content: String)

    @Serializable
    private data class SseEventDto(
        val type: String,
        val text: String? = null,
        val message: String? = null
    )

    companion object {
        private const val TAG = "HermesGateway"

        // Fail-fast budget for /v1/health so the user sees a real error in
        // ~8s instead of waiting out the OS-level TCP timeout (~100s) the
        // bug report described.
        private const val HEALTH_CONNECT_TIMEOUT_SEC = 5L
        private const val HEALTH_READ_TIMEOUT_SEC = 8L
        private const val HEALTH_CALL_TIMEOUT_SEC = 8L

        // SSE chat call: short connect budget, no read timeout (stream is
        // open-ended by design).
        private const val CHAT_CONNECT_TIMEOUT_SEC = 5L
    }
}
