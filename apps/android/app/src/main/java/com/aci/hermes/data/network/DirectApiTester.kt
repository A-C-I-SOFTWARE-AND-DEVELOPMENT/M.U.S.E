package com.aci.hermes.data.network

import com.aci.hermes.util.LogBuffer
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import java.io.IOException
import java.net.ConnectException
import java.net.SocketTimeoutException
import java.net.UnknownHostException
import java.util.concurrent.TimeUnit
import javax.net.ssl.SSLException

/**
 * True end-to-end probe used by the "Test direct API connection" button in
 * [com.aci.hermes.ui.screens.provider.ProviderScreen].
 *
 * Why a dedicated tester (instead of reusing [DirectAIClient]):
 *   * The streaming chat path uses a `readTimeout=0` OkHttpClient because
 *     SSE streams stay open indefinitely. That client must NOT be used for
 *     a one-shot test — a wedged provider would hang the test button
 *     forever.
 *   * The streaming path doesn't expose a clean "did we get useful assistant
 *     text" hook; it's structured around incremental deltas.
 *   * Error mapping for a user-facing test is meaningfully different from
 *     error mapping during a live chat (e.g. 402 / "credits exhausted"
 *     should be a first-class case, not buried in a long error string).
 *
 * The probe does two things:
 *   1. `GET ${baseUrl}/models` — proves the API key + provider URL are
 *      valid before we burn tokens on a chat call.
 *   2. `POST ${baseUrl}/chat/completions` (non-streaming) with a tiny
 *      deterministic prompt. We verify the response contains a non-empty
 *      assistant message.
 *
 * Both calls run with an explicit per-Call timeout so the UI cannot hang.
 *
 * **Security:** the API key is sent only as a `Bearer` token to the
 * configured base URL. It is not logged. Error bodies are logged but only
 * the first ~200 chars and only when needed for diagnostics.
 */
class DirectApiTester(
    private val http: OkHttpClient,
    private val logBuffer: LogBuffer,
    private val callTimeoutMillis: Long = DEFAULT_CALL_TIMEOUT_MS
) {

    private val json = Json {
        ignoreUnknownKeys = true
        explicitNulls = false
    }

    /**
     * Runs the two-stage test and returns a [DirectTestResult]. Never
     * throws — all exceptions are caught and mapped to a result variant.
     */
    suspend fun run(
        baseUrl: String,
        apiKey: String,
        model: String,
        providerLabel: String,
        extraHeaders: Map<String, String> = emptyMap()
    ): DirectTestResult = withContext(Dispatchers.IO) {

        if (apiKey.isBlank()) {
            return@withContext DirectTestResult.InvalidKey(
                "Enter your $providerLabel API key first."
            )
        }
        if (model.isBlank()) {
            return@withContext DirectTestResult.ModelNotFound(
                "Enter a model id (e.g. openai/gpt-4o-mini)."
            )
        }
        if (baseUrl.isBlank()) {
            return@withContext DirectTestResult.NetworkError(
                "Provider base URL is empty."
            )
        }

        // Stage 1 — auth probe via GET /models.
        when (val models = getModels(baseUrl, apiKey, providerLabel, extraHeaders)) {
            is StageOutcome.HardFailure -> return@withContext models.result
            is StageOutcome.Ok -> Unit
        }

        // Stage 2 — small non-streaming chat round-trip.
        return@withContext postTestChat(baseUrl, apiKey, model, providerLabel, extraHeaders)
    }

    private suspend fun getModels(
        baseUrl: String,
        apiKey: String,
        providerLabel: String,
        extraHeaders: Map<String, String>
    ): StageOutcome = withContext(Dispatchers.IO) {
        val req = buildRequest(
            url = joinUrl(baseUrl, "/models"),
            apiKey = apiKey,
            accept = "application/json",
            extraHeaders = extraHeaders
        ).get().build()
        executeAndMap(req, providerLabel, isChatStage = false)?.let {
            StageOutcome.HardFailure(it)
        } ?: StageOutcome.Ok
    }

    private suspend fun postTestChat(
        baseUrl: String,
        apiKey: String,
        model: String,
        providerLabel: String,
        extraHeaders: Map<String, String>
    ): DirectTestResult = withContext(Dispatchers.IO) {
        val payload = TestChatRequestDto(
            model = model,
            messages = listOf(
                TestChatTurnDto(role = "system", content = "You are a test responder."),
                TestChatTurnDto(role = "user", content = TEST_PROMPT)
            ),
            temperature = 0.0,
            max_tokens = 32,
            stream = false
        )
        val body = json.encodeToString(TestChatRequestDto.serializer(), payload)
            .toRequestBody("application/json".toMediaType())
        val req = buildRequest(
            url = joinUrl(baseUrl, "/chat/completions"),
            apiKey = apiKey,
            accept = "application/json",
            extraHeaders = extraHeaders
        ).post(body).build()

        val call = http.newCall(req).apply {
            timeout().timeout(callTimeoutMillis, TimeUnit.MILLISECONDS)
        }
        try {
            call.execute().use { resp ->
                val raw = resp.body?.string().orEmpty()
                if (!resp.isSuccessful) {
                    return@withContext mapHttpStatus(
                        code = resp.code,
                        body = raw,
                        providerLabel = providerLabel,
                        model = model,
                        isChatStage = true
                    )
                }
                val parsed = runCatching {
                    json.decodeFromString(TestChatResponseDto.serializer(), raw)
                }.getOrElse { e ->
                    logBuffer.warn(TAG, "$providerLabel chat response parse failed: ${e.message}")
                    return@withContext DirectTestResult.Unknown(
                        "$providerLabel responded but the body was not valid JSON."
                    )
                }
                val reply = parsed.choices.firstOrNull()?.message?.content?.trim().orEmpty()
                if (reply.isEmpty()) {
                    return@withContext DirectTestResult.Unknown(
                        "$providerLabel returned no assistant text. Try a different model."
                    )
                }
                DirectTestResult.Success(
                    message = "Connected to $providerLabel — $model replied OK.",
                    reply = reply
                )
            }
        } catch (t: Throwable) {
            mapNetworkError(t, providerLabel, isChatStage = true)
        }
    }

    /**
     * Execute a one-shot request and, if the response is a hard failure
     * (non-2xx) or a thrown exception, return the mapped [DirectTestResult].
     * On a 2xx response returns null so the caller can keep going.
     */
    private fun executeAndMap(
        request: Request,
        providerLabel: String,
        isChatStage: Boolean
    ): DirectTestResult? {
        val call = http.newCall(request).apply {
            timeout().timeout(callTimeoutMillis, TimeUnit.MILLISECONDS)
        }
        return try {
            call.execute().use { resp ->
                if (resp.isSuccessful) {
                    null
                } else {
                    val body = resp.body?.string().orEmpty()
                    mapHttpStatus(
                        code = resp.code,
                        body = body,
                        providerLabel = providerLabel,
                        model = null,
                        isChatStage = isChatStage
                    )
                }
            }
        } catch (t: Throwable) {
            mapNetworkError(t, providerLabel, isChatStage = isChatStage)
        }
    }

    private fun buildRequest(
        url: String,
        apiKey: String,
        accept: String,
        extraHeaders: Map<String, String>
    ): Request.Builder {
        val b = Request.Builder()
            .url(url)
            .header("Authorization", "Bearer $apiKey")
            .header("Accept", accept)
        extraHeaders.forEach { (k, v) -> b.header(k, v) }
        return b
    }

    private fun joinUrl(baseUrl: String, path: String): String {
        val base = baseUrl.trimEnd('/')
        val p = if (path.startsWith('/')) path else "/$path"
        return "$base$p"
    }

    private fun mapHttpStatus(
        code: Int,
        body: String,
        providerLabel: String,
        model: String?,
        isChatStage: Boolean
    ): DirectTestResult {
        val trimmedBody = body.take(200)
        val lowerBody = body.lowercase()
        logBuffer.warn(
            TAG,
            "$providerLabel HTTP $code at ${if (isChatStage) "chat" else "models"} stage" +
                if (trimmedBody.isNotBlank()) ": $trimmedBody" else ""
        )
        return when {
            code == 401 || code == 403 -> DirectTestResult.InvalidKey(
                "$providerLabel rejected the API key (HTTP $code). Double-check the key, " +
                    "and make sure it's for $providerLabel."
            )

            code == 402 ||
                "credit" in lowerBody ||
                "insufficient_quota" in lowerBody ||
                "payment_required" in lowerBody ||
                "billing" in lowerBody -> DirectTestResult.PaymentRequired(
                "$providerLabel says the account needs credits or a billing update (HTTP $code)."
            )

            code == 404 -> {
                val modelHint = if (model != null && isChatStage) {
                    "Model \"$model\" was not found on $providerLabel, or the endpoint URL is wrong."
                } else {
                    "$providerLabel endpoint not found (HTTP 404). Check the base URL."
                }
                DirectTestResult.ModelNotFound(modelHint)
            }

            code == 429 -> DirectTestResult.RateLimited(
                "$providerLabel rate-limited the request (HTTP 429). Wait a moment and retry."
            )

            code in 500..599 -> DirectTestResult.ProviderOutage(
                "$providerLabel is having problems (HTTP $code). Try again later."
            )

            else -> DirectTestResult.Unknown(
                "$providerLabel returned HTTP $code." +
                    if (trimmedBody.isNotBlank()) " Details: $trimmedBody" else ""
            )
        }
    }

    private fun mapNetworkError(
        t: Throwable,
        providerLabel: String,
        @Suppress("UNUSED_PARAMETER") isChatStage: Boolean
    ): DirectTestResult {
        val name = t::class.java.simpleName
        logBuffer.error(TAG, "$providerLabel network error ($name): ${t.message}")
        return when (t) {
            is UnknownHostException -> DirectTestResult.NetworkError(
                "Can't reach $providerLabel — phone network problem or wrong base URL."
            )
            is ConnectException -> DirectTestResult.NetworkError(
                "Couldn't connect to $providerLabel. Check Wi-Fi or mobile data."
            )
            is SocketTimeoutException -> DirectTestResult.NetworkError(
                "$providerLabel didn't respond in time. Check your connection and retry."
            )
            is SSLException -> DirectTestResult.NetworkError(
                "TLS handshake with $providerLabel failed. Date/time on the phone correct?"
            )
            is IOException -> {
                // OkHttp throws plain IOException when its per-call timeout
                // fires. Surface that as a network problem so the user knows
                // to check connectivity rather than blaming the provider.
                val msg = t.message.orEmpty()
                if ("timeout" in msg.lowercase() || "canceled" in msg.lowercase()) {
                    DirectTestResult.NetworkError(
                        "$providerLabel didn't respond in time. Check your connection and retry."
                    )
                } else {
                    DirectTestResult.NetworkError(
                        "Network problem talking to $providerLabel: ${msg.ifBlank { name }}"
                    )
                }
            }
            else -> DirectTestResult.Unknown(
                "Unexpected error talking to $providerLabel: ${t.message ?: name}"
            )
        }
    }

    private sealed class StageOutcome {
        data object Ok : StageOutcome()
        data class HardFailure(val result: DirectTestResult) : StageOutcome()
    }

    @Serializable
    private data class TestChatRequestDto(
        val model: String,
        val messages: List<TestChatTurnDto>,
        val temperature: Double = 0.0,
        @SerialName("max_tokens") val max_tokens: Int = 32,
        val stream: Boolean = false
    )

    @Serializable
    private data class TestChatTurnDto(val role: String, val content: String)

    @Serializable
    private data class TestChatResponseDto(
        val choices: List<TestChatChoiceDto> = emptyList()
    )

    @Serializable
    private data class TestChatChoiceDto(
        val message: TestChatMessageDto? = null
    )

    @Serializable
    private data class TestChatMessageDto(
        val role: String? = null,
        val content: String? = null
    )

    companion object {
        private const val TAG = "DirectApiTester"

        const val DEFAULT_CALL_TIMEOUT_MS: Long = 15_000

        /**
         * Tiny, non-dangerous test prompt. Deterministic temperature and a
         * cap on `max_tokens` keep the test cheap.
         */
        const val TEST_PROMPT: String =
            "Reply with exactly: Hermes direct mode is working."
    }
}

/**
 * Categorical result of a direct-API end-to-end probe. The UI dispatches on
 * the variant so it can show actionable text (e.g. "needs credits") instead
 * of a raw HTTP code.
 */
sealed class DirectTestResult {
    abstract val message: String

    data class Success(override val message: String, val reply: String) : DirectTestResult()

    /** 401/403 — bad API key or wrong provider for that key. */
    data class InvalidKey(override val message: String) : DirectTestResult()

    /** 402 or provider-specific "out of credits / billing" body. */
    data class PaymentRequired(override val message: String) : DirectTestResult()

    /** 404 — model id unknown to the provider, or wrong base URL. */
    data class ModelNotFound(override val message: String) : DirectTestResult()

    /** 429 — provider throttled the request. */
    data class RateLimited(override val message: String) : DirectTestResult()

    /** 5xx — provider outage. */
    data class ProviderOutage(override val message: String) : DirectTestResult()

    /** UnknownHost / ConnectException / SocketTimeout / SSL — phone network problem. */
    data class NetworkError(override val message: String) : DirectTestResult()

    /** Anything we couldn't categorise. Surface the raw text. */
    data class Unknown(override val message: String) : DirectTestResult()
}
