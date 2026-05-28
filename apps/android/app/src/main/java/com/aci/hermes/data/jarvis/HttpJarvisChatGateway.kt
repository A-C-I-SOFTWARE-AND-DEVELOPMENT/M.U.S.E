package com.aci.hermes.data.jarvis

import com.aci.hermes.util.LogBuffer
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOn
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.TimeUnit
import kotlin.coroutines.coroutineContext

/**
 * Live gateway client: streams a reply from the local Hermes gateway
 * (default `http://127.0.0.1:8765`, see
 * [com.aci.hermes.data.preferences.SettingsRepository.DEFAULT_GATEWAY_ENDPOINT]).
 *
 * Wire format is newline-delimited JSON ("JSONL"), one object per line,
 * matching the local chat endpoint added to `gateway/platforms/webhook.py`:
 *
 *   {"type":"thinking"}
 *   {"type":"working","label":"Searching the repo"}
 *   {"type":"tone","tone":"SERIOUS"}
 *   {"type":"body","text":"On it."}
 *   {"type":"detail","text":"Here's the longer reasoning…"}
 *   {"type":"done"}
 *   {"type":"error","message":"…","retryHint":"…"}
 *
 * Cancelling the collecting coroutine (the user's Stop) closes the
 * response, which the loop honors via [ensureActive].
 *
 * [MockJarvisChatGateway] stays the default for tests / offline; this
 * gateway is selected when an endpoint is configured.
 */
class HttpJarvisChatGateway(
    private val endpointProvider: () -> String,
    private val logBuffer: LogBuffer,
    private val client: OkHttpClient = defaultClient(),
) : JarvisChatGateway {

    override val displayName: String = "Hermes gateway"
    override val supportsStreaming: Boolean = true

    override fun send(history: List<JarvisChatMessage>, prompt: String): Flow<JarvisChatChunk> = flow {
        val url = endpointProvider().trimEnd('/') + CHAT_PATH
        val payload = JSONObject().apply {
            put("prompt", prompt)
            put("history", historyJson(history))
        }.toString()

        val request = Request.Builder()
            .url(url)
            .post(payload.toRequestBody(JSON))
            .build()

        val response = runCatching { client.newCall(request).execute() }
            .getOrElse {
                logBuffer.append("Gateway call failed: ${it.message}")
                emit(JarvisChatChunk.Failure("Couldn't reach Hermes at $url", "Check the gateway is running."))
                return@flow
            }

        response.use { resp ->
            if (!resp.isSuccessful) {
                emit(JarvisChatChunk.Failure("Gateway returned ${resp.code}", "Check the gateway logs."))
                return@flow
            }
            val source = resp.body?.source() ?: run {
                emit(JarvisChatChunk.Failure("Empty gateway response"))
                return@flow
            }
            while (!source.exhausted()) {
                coroutineContext.ensureActive() // honor Stop / abort
                val line = source.readUtf8Line() ?: break
                if (line.isBlank()) continue
                parseLine(line)?.let { emit(it) }
            }
        }
    }.flowOn(Dispatchers.IO)

    private fun parseLine(line: String): JarvisChatChunk? = runCatching {
        val obj = JSONObject(line)
        when (obj.getString("type")) {
            "thinking" -> JarvisChatChunk.Thinking
            "working" -> JarvisChatChunk.Working(obj.optString("label"))
            "tone" -> JarvisChatChunk.Tone(toneOf(obj.optString("tone")))
            "body" -> JarvisChatChunk.Body(obj.optString("text"))
            "detail" -> JarvisChatChunk.Detail(obj.optString("text"))
            "done" -> JarvisChatChunk.Done
            "error" -> JarvisChatChunk.Failure(
                obj.optString("message", "Gateway error"),
                obj.optString("retryHint").ifBlank { null },
            )
            else -> null
        }
    }.getOrNull()

    private fun toneOf(raw: String): JarvisTone = when (raw.uppercase()) {
        "SERIOUS" -> JarvisTone.SERIOUS
        "CRITICAL" -> JarvisTone.CRITICAL
        else -> JarvisTone.NORMAL
    }

    private fun historyJson(history: List<JarvisChatMessage>): JSONArray {
        val arr = JSONArray()
        history.forEach { msg ->
            val (role, text) = when (msg) {
                is JarvisChatMessage.User -> "user" to msg.text
                is JarvisChatMessage.Jarvis -> "assistant" to msg.body
                else -> return@forEach
            }
            arr.put(JSONObject().put("role", role).put("text", text))
        }
        return arr
    }

    companion object {
        private const val CHAT_PATH = "/v1/jarvis/chat"
        private val JSON = "application/json; charset=utf-8".toMediaType()

        private fun defaultClient(): OkHttpClient = OkHttpClient.Builder()
            .connectTimeout(5, TimeUnit.SECONDS)
            .readTimeout(0, TimeUnit.SECONDS) // streaming: no read timeout
            .build()
    }
}
