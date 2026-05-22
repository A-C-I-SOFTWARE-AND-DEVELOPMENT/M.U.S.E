package com.aci.hermes.ui.screens.provider

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.model.ConnectionState
import com.aci.hermes.data.network.HermesClientFactory
import com.aci.hermes.data.network.HermesGatewayClient
import com.aci.hermes.data.preferences.SettingsRepository
import com.aci.hermes.util.LogBuffer
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class ProviderUiState(
    val gatewayUrl: String = "",
    val gatewayToken: String = "",
    val providerId: String = "openrouter",
    val providerApiKey: String = "",
    val mockMode: Boolean = false,
    val test: ConnectionState = ConnectionState.Unknown,
    val saving: Boolean = false
)

class ProviderViewModel(
    private val settings: SettingsRepository,
    private val clientFactory: HermesClientFactory,
    private val logBuffer: LogBuffer
) : ViewModel() {

    private val _state = MutableStateFlow(ProviderUiState())
    val state: StateFlow<ProviderUiState> = _state.asStateFlow()

    init {
        viewModelScope.launch {
            val snap = settings.snapshot()
            _state.value = ProviderUiState(
                gatewayUrl = snap.gatewayUrl,
                gatewayToken = settings.gatewayToken().orEmpty(),
                providerId = snap.providerId,
                providerApiKey = settings.providerApiKey().orEmpty(),
                mockMode = snap.mockMode
            )
        }
    }

    fun setGatewayUrl(v: String) = _state.update { it.copy(gatewayUrl = v) }
    fun setGatewayToken(v: String) = _state.update { it.copy(gatewayToken = v) }
    fun setProviderId(v: String) = _state.update { it.copy(providerId = v) }
    fun setProviderApiKey(v: String) = _state.update { it.copy(providerApiKey = v) }
    fun setMockMode(v: Boolean) = _state.update { it.copy(mockMode = v) }

    fun testConnection() {
        val current = _state.value
        if (current.mockMode) {
            _state.update {
                it.copy(test = ConnectionState.Connected(
                    com.aci.hermes.data.model.HermesStatus(ok = true, message = "Mock mode")
                ))
            }
            return
        }
        if (current.gatewayUrl.isBlank()) {
            _state.update { it.copy(test = ConnectionState.Failed("Gateway URL is empty")) }
            return
        }
        _state.update { it.copy(test = ConnectionState.Connecting) }
        viewModelScope.launch {
            val probe = HermesGatewayClient(
                baseUrl = current.gatewayUrl,
                token = current.gatewayToken.ifBlank { null },
                providerApiKey = current.providerApiKey.ifBlank { null },
                providerId = current.providerId.ifBlank { null },
                logBuffer = logBuffer
            )
            val status = probe.status()
            _state.update {
                if (status.ok) it.copy(test = ConnectionState.Connected(status))
                else it.copy(test = ConnectionState.Failed(status.message ?: "Unknown error"))
            }
        }
    }

    fun save(onDone: () -> Unit) {
        val current = _state.value
        _state.update { it.copy(saving = true) }
        viewModelScope.launch {
            settings.setGatewayUrl(current.gatewayUrl)
            settings.setProviderId(current.providerId)
            settings.setMockMode(current.mockMode)
            settings.setGatewayToken(current.gatewayToken.ifBlank { null })
            settings.setProviderApiKey(current.providerApiKey.ifBlank { null })
            settings.setOnboarded(true)
            logBuffer.info(TAG, "Saved connection settings (mock=${current.mockMode})")
            _state.update { it.copy(saving = false) }
            onDone()
        }
    }

    companion object {
        private const val TAG = "ProviderVM"
    }
}
