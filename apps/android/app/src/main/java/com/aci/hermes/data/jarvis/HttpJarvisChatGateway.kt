package com.aci.hermes.data.jarvis

import com.aci.hermes.util.LogBuffer
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOn
import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedReader
import java.net.HttpURLConnection
import java.net.URL
import kotlin.coroutines.coroutineContext

/**
 * Live gateway client: streams a reply from the local Hermes gateway
 * (default `http://127.0.0.1:8765`, see
 * [com.aci.hermes.data.preferences.SettingsRepository.DEFAULT_GATEWAY_ENDPOINT]).
 *
 * Wire format is newline-delimited JSON ("JSONL"), one object per line,
 * matching the local chat endpoint in `gateway/jarvis_local_http.py`:
 *
 *   {"type":"thinking"}
 *   {"type":"working","label":"Searching the repo"}
 *   {"type":"tone","tone":"SERIOUS"}
 *   {"type":"body","text":"On it."}
 *   {"type":"detail","text":"Here's the longer reasoning…"}
 *   {"type":"done"}
 *   {"type":"error","message":"…","retryHint":"…"}
 *
 * Implemented over the JDK's [HttpURLConnection] (no third-party HTTP
 * dependency) so the app stays self-contained. Cancelling the collecting
 * coroutine (the user's Stop) is honored between lines via [ensureActive],
 * which closes the connection on the way out.
 *
 * [MockJarvisChatGateway] stays the default for tests / offline; this
 * gateway is selected when an endpoint is configured.
 */
class HttpJarvisChatGateway(
    private val endpointProvider: () -> String,
    private val logBuffer: LogBuffer,
    private val tokenProvider: () -> String? = { null },
) : JarvisChatGateway {

    override val displayName: String = "muse gateway"
    override val supportsStreaming: Boolean = true

    override fun send(history: List<JarvisChatMessage>, prompt: String): Flow<JarvisChatChunk> = flow {
        val url = endpointProvider().trimEnd('/') + CHAT_PATH
        val payload = JSONObject().apply {
            put("prompt", prompt)
            put("history", historyJson(history))
        }.toString()

        val connection = runCatching { openConnection(url, payload) }
            .getOrElse {
                logBuffer.warn("gateway", "Gateway call failed: ${it.message}")
                emit(JarvisChatChunk.Failure("Couldn't reach muse at $url", "Check the gateway is running."))
                return@flow
            }

        try {
            val code = connection.responseCode
            if (code !in 200..299) {
                val (msg, hint) = when (code) {
                    401 -> "Gateway rejected the pairing token" to "Re-pair in Settings → Connection."
                    403 -> "Gateway refused the request" to "Check the gateway is loopback-only."
                    else -> "Gateway returned $code" to "Check the gateway logs."
                }
                emit(JarvisChatChunk.Failure(msg, hint))
                return@flow
            }
            val reader: BufferedReader = connection.inputStream.bufferedReader()
            reader.use { r ->
                while (true) {
                    coroutineContext.ensureActive() // honor Stop / abort
                    val line = r.readLine() ?: break
                    if (line.isBlank()) continue
                    parseLine(line)?.let { emit(it) }
                }
            }
        } finally {
            connection.disconnect()
        }
    }.flowOn(Dispatchers.IO)

    private fun openConnection(url: String, payload: String): HttpURLConnection =
        (URL(url).openConnection() as HttpURLConnection).apply {
            requestMethod = "POST"
            doOutput = true
            connectTimeout = 5_000
            readTimeout = 0 // streaming: no read timeout
            setRequestProperty("Content-Type", "application/json; charset=utf-8")
            setRequestProperty("Accept", "application/x-ndjson")
            // The cockpit chat route is bearer-authenticated; attach the
            // paired token when present. Unpaired (token null) keeps the
            // legacy unauthenticated jarvis_local_http path working.
            tokenProvider()?.takeIf { it.isNotBlank() }?.let {
                setRequestProperty("Authorization", "Bearer $it")
            }
            outputStream.use { it.write(payload.toByteArray(Charsets.UTF_8)) }
        }

    private fun parseLine(line: String): JarvisChatChunk? = runCatching {
        val obj = JSONObject(line)
        when (obj.getString("type")) {
            "thinking" -> JarvisChatChunk.Thinking
            "working" -> JarvisChatChunk.Working(obj.optString("label"))
            "tone" -> JarvisChatChunk.Tone(toneOf(obj.optString("tone")))
            "body" -> JarvisChatChunk.Body(obj.optString("text"))
            "detail" -> JarvisChatChunk.Detail(obj.optString("text"))
            "phase" -> JarvisPhase.fromWire(obj.optString("phase"))
                ?.let { JarvisChatChunk.Phase(it) }
            "tool_call" -> JarvisChatChunk.ToolCall(
                id = obj.optString("id"),
                name = obj.optString("name"),
                summary = obj.optString("summary"),
                status = JarvisToolStatus.fromWire(obj.optString("status")),
                detail = obj.optString("detail").ifBlank { null },
            )
            "evidence" -> JarvisChatChunk.EvidenceRef(
                auditId = obj.optString("auditId"),
                title = obj.optString("title").ifBlank { "Evidence" },
            )
            "ledger" -> JarvisChatChunk.LedgerRef(
                ledgerId = obj.optString("ledgerId"),
                title = obj.optString("title").ifBlank { "Decision" },
            )
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
    }
}
