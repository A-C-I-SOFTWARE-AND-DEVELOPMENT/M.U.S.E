package com.aci.hermes.data.network

import com.aci.hermes.data.preferences.SettingsRepository
import com.aci.hermes.util.LogBuffer

/**
 * Chooses between the mock client and a live gateway client based on the
 * current settings snapshot. Keeps the rest of the code free of branching
 * on mock-mode / empty-URL conditions.
 */
class HermesClientFactory(
    private val settingsRepository: SettingsRepository,
    private val logBuffer: LogBuffer
) {
    suspend fun current(): HermesClient {
        val snap = settingsRepository.snapshot()
        return if (snap.mockMode || snap.gatewayUrl.isBlank()) {
            MockHermesClient()
        } else {
            HermesGatewayClient(
                baseUrl = snap.gatewayUrl,
                token = settingsRepository.gatewayToken(),
                providerApiKey = settingsRepository.providerApiKey(),
                providerId = snap.providerId,
                logBuffer = logBuffer
            )
        }
    }
}
