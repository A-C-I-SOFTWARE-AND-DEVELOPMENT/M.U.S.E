package com.aci.hermes.data.cockpit

import kotlinx.serialization.json.Json
import java.io.BufferedReader
import java.net.HttpURLConnection
import java.net.URL

/**
 * Transport primitives for the Hermes cockpit API.
 *
 * Everything in this file is deliberately free of Android types so the
 * request-building and response-mapping logic is unit-testable on a
 * plain JVM (no Robolectric, no socket). [HermesCockpitClient] wires
 * these together; production traffic flows through [JdkHttpExecutor],
 * while tests inject a fake [CockpitHttpExecutor].
 *
 * The wire format is the contract in
 * docs/android/hermes-apk-api-contract.md (§1 conventions, §12 SDK
 * shape). This layer owns three of the four client responsibilities
 * that doc assigns to the client: attaching the bearer token, decoding
 * the error envelope into a typed [CockpitError], and enforcing the
 * short health-probe timeout. (SSE reconnect lives with the streaming
 * surfaces, not here.)
 */

/** A raw HTTP request. Pure data — no Android, no JDK connection state. */
data class CockpitRequest(
    val method: String,
    val url: String,
    val headers: Map<String, String>,
    val body: String? = null,
    val connectTimeoutMs: Int,
    val readTimeoutMs: Int,
)

/** A raw HTTP response. [body] is the decoded text (possibly empty). */
data class CockpitRawResponse(
    val status: Int,
    val body: String,
)

/**
 * Pluggable HTTP executor. The production binding ([JdkHttpExecutor])
 * runs over the JDK's [HttpURLConnection] — no third-party HTTP
 * dependency, Termux-safe. Tests pass a fake so the client's
 * request-building and response-mapping are exercised without a socket.
 *
 * Implementations throw on a transport failure (DNS, refused, timeout);
 * the client turns the throwable into [CockpitResult.Unreachable].
 */
fun interface CockpitHttpExecutor {
    fun execute(request: CockpitRequest): CockpitRawResponse
}

/**
 * Typed outcome of a cockpit call.
 *
 * - [Success] — a 2xx with a body that decoded into [T].
 * - [Failure] — the gateway answered with a non-2xx; the error envelope
 *   was decoded (or synthesized from the status) into a [CockpitError].
 *   Screens branch on [CockpitError.code], never the human message.
 * - [Unreachable] — the gateway could not be reached, no token/endpoint
 *   was configured, or the 2xx body was unparseable.
 */
sealed interface CockpitResult<out T> {
    data class Success<T>(val value: T) : CockpitResult<T>
    data class Failure(val error: CockpitError, val httpStatus: Int) : CockpitResult<Nothing>
    data class Unreachable(val message: String) : CockpitResult<Nothing>
}

/** Pure helpers shared by the client and its tests. */
object CockpitHttp {

    /** Short probe timeout for `/v1/health` so the UI shows "unreachable" fast (contract §12). */
    const val HEALTH_TIMEOUT_MS: Int = 8_000

    /** Default connect/read timeout for the buffered (non-streaming) routes. */
    const val DEFAULT_CONNECT_TIMEOUT_MS: Int = 8_000
    const val DEFAULT_READ_TIMEOUT_MS: Int = 15_000

    /** Research runs gather + rank + synthesize server-side; allow a longer read window. */
    const val RESEARCH_TIMEOUT_MS: Int = 60_000

    /**
     * Tolerant JSON: the gateway and the cockpit may be at different
     * contract revisions, so unknown keys are ignored and absent nullable
     * fields stay null rather than crashing deserialisation.
     */
    val json: Json = Json {
        ignoreUnknownKeys = true
        isLenient = true
        explicitNulls = false
        coerceInputValues = true
    }

    /** Join a configured base URL and a route path without doubling slashes. */
    fun joinUrl(base: String, path: String): String {
        val b = base.trim().trimEnd('/')
        val p = if (path.startsWith("/")) path else "/$path"
        return b + p
    }

    /**
     * Headers for a request. The bearer token is attached only when
     * non-blank; `/v1/health` is called with [token] = null so an
     * unpaired cockpit can still probe liveness.
     */
    fun headers(token: String?): Map<String, String> {
        val h = linkedMapOf(
            "Accept" to "application/json",
            "Content-Type" to "application/json; charset=utf-8",
        )
        if (!token.isNullOrBlank()) {
            h["Authorization"] = "Bearer $token"
        }
        return h
    }

    /**
     * Decode the contract error envelope (`{"error":{"code","message","details"}}`).
     * Falls back to a synthetic [CockpitError] keyed off the HTTP status
     * class so the UI always has a stable `code` to branch on, even when
     * the gateway returns a bare or malformed body.
     */
    fun parseError(json: Json, status: Int, body: String): CockpitError {
        val decoded = runCatching {
            json.decodeFromString(CockpitErrorEnvelope.serializer(), body).error
        }.getOrNull()
        if (decoded != null && decoded.code.isNotBlank()) return decoded
        return CockpitError(code = codeForStatus(status), message = fallbackMessage(status, body))
    }

    private fun codeForStatus(status: Int): String = when (status) {
        401 -> "unauthorized"
        403 -> "forbidden"
        404 -> "not_found"
        409 -> "conflict"
        422 -> "unprocessable"
        in 400..499 -> "validation_failed"
        in 500..599 -> "backend_error"
        else -> "unexpected_status"
    }

    private fun fallbackMessage(status: Int, body: String): String {
        val trimmed = body.trim()
        return if (trimmed.isNotEmpty() && trimmed.length <= 200) trimmed else "Gateway returned HTTP $status"
    }
}

/**
 * Production [CockpitHttpExecutor] over [HttpURLConnection]. No
 * third-party HTTP client, so the app stays self-contained on Termux.
 * Buffered (non-streaming) only — the chat stream keeps its own
 * connection handling in `HttpJarvisChatGateway`.
 */
object JdkHttpExecutor : CockpitHttpExecutor {
    override fun execute(request: CockpitRequest): CockpitRawResponse {
        val connection = (URL(request.url).openConnection() as HttpURLConnection).apply {
            requestMethod = request.method
            connectTimeout = request.connectTimeoutMs
            readTimeout = request.readTimeoutMs
            instanceFollowRedirects = false
            useCaches = false
            request.headers.forEach { (k, v) -> setRequestProperty(k, v) }
            if (request.body != null) {
                doOutput = true
                outputStreamuse { it.write(request.body.toByteArray(Charsets.UTF_8)) }
            }
        }
        try {
            val status = connection.responseCode
            val stream = if (status in 200..299) connection.inputStream else connection.errorStream
            val text = stream?.bufferedReader()?.use(BufferedReader::readText).orEmpty()
            return CockpitRawResponse(status, text)
        } finally {
            connection.disconnect()
        }
    }
}
