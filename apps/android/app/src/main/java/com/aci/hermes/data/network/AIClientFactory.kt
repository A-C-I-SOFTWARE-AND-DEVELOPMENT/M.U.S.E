package com.aci.hermes.data.network

import com.aci.hermes.data.preferences.ConnectionMode
import com.aci.hermes.data.preferences.SettingsRepository
import com.aci.hermes.util.LogBuffer
import okhttp3.OkHttpClient

/**
 * Picks an [AIClient] based on the user's current connection mode +
 * stored credentials.
 *
 *   * [ConnectionMode.MOCK]    → [MockAIClient]
 *   * [ConnectionMode.DIRECT]  → [DirectAIClient] pointed at the chosen
 *                                provider (OpenRouter / OpenAI / custom)
 *                                with the user's API key as the Bearer
 *                                token. Falls back to [MockAIClient] if
 *                                the API key is missing — so the UI is
 *                                never wedged.
 *   * [ConnectionMode.HERMES]  → [HermesGatewayClient]. Falls back to
 *                                [MockAIClient] if the gateway URL is
 *                                blank.
 *
 * The [http] client is supplied by [com.aci.hermes.di.AppContainer] so
 * the dispatcher + connection pool are shared across the whole app.
 */
class AIClientFactory(
    private val settingsRepository: SettingsRepository,
    private val http: OkHttpClient,
    private val logBuffer: LogBuffer
) {
    suspend fun current(): AIClient {
        val snap = settingsRepository.snapshot()
        return when (snap.connectionMode) {
            ConnectionMode.MOCK -> MockAIClient()

            ConnectionMode.DIRECT -> {
                val secrets = settingsRepository.secretsSnapshot()
                val key = secrets.providerApiKey
                if (key.isNullOrBlank()) {
                    logBuffer.warn(TAG, "Direct mode selected but no API key — falling back to mock")
                    MockAIClient()
                } else {
                    DirectAIClient(
                        http = http,
                        baseUrl = baseUrlFor(snap.providerId, snap.gatewayUrl),
                        apiKey = key,
                        model = snap.model.ifBlank { SettingsRepository.DEFAULT_DIRECT_MODEL },
                        providerLabel = providerLabel(snap.providerId),
                        extraHeaders = if (snap.providerId == "openrouter") {
                            DirectAIClient.OPENROUTER_HEADERS
                        } else emptyMap(),
                        logBuffer = logBuffer
                    )
                }
            }

            ConnectionMode.HERMES -> {
                if (snap.gatewayUrl.isBlank()) {
                    logBuffer.warn(TAG, "Hermes mode selected but gateway URL blank — falling back to mock")
                    MockAIClient()
                } else {
                    val secrets = settingsRepository.secretsSnapshot()
                    HermesGatewayClient(
                        http = http,
                        baseUrl = snap.gatewayUrl,
                        token = secrets.gatewayToken,
                        providerApiKey = secrets.providerApiKey,
                        providerId = snap.providerId,
                        logBuffer = logBuffer
                    )
                }
            }
        }
    }

    companion object {
        private const val TAG = "AIClientFactory"

        /**
         * In direct mode, `gateway_url` is reused as the "custom base URL"
         * field — the user enters it on the Provider screen when they pick
         * the "custom" provider.
         */
        fun baseUrlFor(providerId: String, customBaseUrl: String): String = when (providerId) {
            "openrouter" -> DirectAIClient.OPENROUTER_BASE_URL
            "openai" -> DirectAIClient.OPENAI_BASE_URL
            "custom" -> customBaseUrl.trim().ifBlank { DirectAIClient.OPENROUTER_BASE_URL }
            else -> DirectAIClient.OPENROUTER_BASE_URL
        }

        fun providerLabel(providerId: String): String = when (providerId) {
            "openrouter" -> "OpenRouter"
            "openai" -> "OpenAI"
            "custom" -> "Custom"
            else -> providerId.replaceFirstChar { it.uppercase() }
        }
    }
}
