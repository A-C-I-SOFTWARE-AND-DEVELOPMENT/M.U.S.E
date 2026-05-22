package com.aci.hermes.data.network

import com.aci.hermes.data.preferences.SettingsRepository
import com.aci.hermes.util.LogBuffer
import okhttp3.OkHttpClient

/**
 * Chooses between the mock client and a live gateway client based on the
 * current settings snapshot. Keeps the rest of the code free of branching
 * on mock-mode / empty-URL conditions.
 *
 * The [http] client is supplied by the application's
 * [com.aci.hermes.di.AppContainer] so gateway clients share a single
 * dispatcher executor and connection pool across the app's lifetime.
 */
class HermesClientFactory(
    private val settingsRepository: SettingsRepository,
    private val http: OkHttpClient,
    private val logBuffer: LogBuffer
) {
    suspend fun current(): HermesClient {
        val snap = settingsRepository.snapshot()
        return if (snap.mockMode || snap.gatewayUrl.isBlank()) {
            MockHermesClient()
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
