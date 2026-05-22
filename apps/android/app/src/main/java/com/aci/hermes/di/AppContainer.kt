package com.aci.hermes.di

import android.content.Context
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import com.aci.hermes.BuildConfig
import com.aci.hermes.data.network.AIClientFactory
import com.aci.hermes.data.preferences.SecureKeyStore
import com.aci.hermes.data.preferences.SettingsRepository
import com.aci.hermes.ui.screens.chat.ChatViewModel
import com.aci.hermes.ui.screens.diagnostics.DiagnosticsViewModel
import com.aci.hermes.ui.screens.provider.ProviderViewModel
import com.aci.hermes.ui.screens.settings.SettingsViewModel
import com.aci.hermes.ui.screens.status.StatusViewModel
import com.aci.hermes.util.LogBuffer
import okhttp3.OkHttpClient
import java.util.concurrent.TimeUnit

/**
 * Hand-rolled DI container. We deliberately avoid Hilt / Koin here:
 *   * Keeps the build configuration small (no annotation processors).
 *   * Makes the wiring obvious to anyone landing in the Android module
 *     without prior Hilt experience.
 *
 * Held by [com.aci.hermes.HermesApplication] for the lifetime of the
 * process. ViewModel factories pull dependencies out of this container.
 */
class AppContainer(context: Context) {
    val logBuffer: LogBuffer = LogBuffer()

    private val secureKeyStore = SecureKeyStore(context)

    val settingsRepository: SettingsRepository = SettingsRepository(
        context = context,
        secureKeyStore = secureKeyStore,
        defaultGatewayUrl = BuildConfig.DEFAULT_GATEWAY_URL,
        defaultMockMode = BuildConfig.ENABLE_MOCK_DEFAULT
    )

    // Singleton: dispatcher executor + connection pool live for the
    // process. Read timeout is 0 because /v1/chat is an open SSE stream.
    val httpClient: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(0, TimeUnit.MILLISECONDS)
        .writeTimeout(10, TimeUnit.SECONDS)
        .build()

    val clientFactory: AIClientFactory = AIClientFactory(settingsRepository, httpClient, logBuffer)

    fun providerVmFactory(): ViewModelProvider.Factory = factory { ProviderViewModel(settingsRepository, httpClient, logBuffer) }
    fun chatVmFactory(): ViewModelProvider.Factory = factory { ChatViewModel(settingsRepository, clientFactory) }
    fun settingsVmFactory(): ViewModelProvider.Factory = factory { SettingsViewModel(settingsRepository, logBuffer) }
    fun diagnosticsVmFactory(): ViewModelProvider.Factory = factory { DiagnosticsViewModel(settingsRepository, clientFactory, logBuffer) }
    fun statusVmFactory(): ViewModelProvider.Factory = factory { StatusViewModel(settingsRepository, clientFactory) }

    private inline fun <reified VM : ViewModel> factory(crossinline build: () -> VM): ViewModelProvider.Factory =
        object : ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST")
            override fun <T : ViewModel> create(modelClass: Class<T>): T = build() as T
        }
}
