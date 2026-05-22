package com.aci.hermes.ui.screens.provider

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.model.ConnectionState
import com.aci.hermes.data.model.HermesStatus
import com.aci.hermes.data.network.AIClientFactory
import com.aci.hermes.data.network.DirectAIClient
import com.aci.hermes.data.network.HermesGatewayClient
import com.aci.hermes.data.preferences.ConnectionMode
import com.aci.hermes.data.preferences.SettingsRepository
import com.aci.hermes.util.GatewayUrl
import com.aci.hermes.util.LogBuffer
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import okhttp3.OkHttpClient

data class ProviderUiState(
    val mode: ConnectionMode = ConnectionMode.DIRECT,
    val gatewayUrl: String = "",
    val gatewayToken: String = "",
    val providerId: String = "openrouter",
    val providerApiKey: String = "",
    val model: String = SettingsRepository.DEFAULT_DIRECT_MODEL,
    val test: ConnectionState = ConnectionState.Unknown,
    val saving: Boolean = false,
    val validationError: String? = null,
    // Inline hint shown under the gateway URL field when the URL is
    // plausibly wrong (e.g. 10.0.2.2 on a real phone, http:// on a
    // public host). Computed from the URL — not a network probe.
    val gatewayUrlWarning: String? = null
)

class ProviderViewModel(
    private val settings: SettingsRepository,
    private val http: OkHttpClient,
    private val logBuffer: LogBuffer
) : ViewModel() {

    private val _state = MutableStateFlow(ProviderUiState())
    val state: StateFlow<ProviderUiState> = _state.asStateFlow()

    init {
        viewModelScope.launch {
            val snap = settings.snapshot()
            val secrets = settings.secretsSnapshot()
            _state.value = ProviderUiState(
                mode = snap.connectionMode,
                gatewayUrl = snap.gatewayUrl,
                gatewayToken = secrets.gatewayToken.orEmpty(),
                providerId = snap.providerId,
                providerApiKey = secrets.providerApiKey.orEmpty(),
                model = snap.model,
                gatewayUrlWarning = GatewayUrl.warningFor(snap.gatewayUrl)
            )
        }
    }

    fun setMode(m: ConnectionMode) = _state.update {
        // Switching modes drops the previous test result — it's no longer
        // meaningful against the new mode's endpoint.
        it.copy(mode = m, test = ConnectionState.Unknown, validationError = null)
    }
    fun setGatewayUrl(v: String) = _state.update {
        it.copy(
            gatewayUrl = v,
            test = ConnectionState.Unknown,
            gatewayUrlWarning = GatewayUrl.warningFor(v)
        )
    }
    fun setGatewayToken(v: String) = _state.update { it.copy(gatewayToken = v, test = ConnectionState.Unknown) }
    fun setProviderId(v: String) = _state.update { it.copy(providerId = v, test = ConnectionState.Unknown) }
    fun setProviderApiKey(v: String) = _state.update { it.copy(providerApiKey = v, test = ConnectionState.Unknown) }
    fun setModel(v: String) = _state.update { it.copy(model = v, test = ConnectionState.Unknown) }

    fun testConnection() {
        val current = _state.value
        when (current.mode) {
            ConnectionMode.MOCK -> {
                _state.update {
                    it.copy(test = ConnectionState.Connected(HermesStatus(ok = true, message = "Mock mode")))
                }
            }

            ConnectionMode.DIRECT -> {
                val key = current.providerApiKey.trim()
                if (key.isEmpty()) {
                    _state.update {
                        it.copy(
                            test = ConnectionState.Failed(
                                reason = "Enter an API key to test.",
                                kind = GatewayUrl.FailureKind.WRONG_URL
                            )
                        )
                    }
                    return
                }
                if (current.providerId == "custom" && current.gatewayUrl.isBlank()) {
                    _state.update {
                        it.copy(
                            test = ConnectionState.Failed(
                                reason = "Custom endpoint needs a base URL.",
                                kind = GatewayUrl.FailureKind.WRONG_URL
                            )
                        )
                    }
                    return
                }
                _state.update { it.copy(test = ConnectionState.Connecting) }
                viewModelScope.launch {
                    val probe = DirectAIClient(
                        http = http,
                        baseUrl = AIClientFactory.baseUrlFor(current.providerId, current.gatewayUrl),
                        apiKey = key,
                        model = current.model.ifBlank { SettingsRepository.DEFAULT_DIRECT_MODEL },
                        providerLabel = AIClientFactory.providerLabel(current.providerId),
                        extraHeaders = if (current.providerId == "openrouter") {
                            DirectAIClient.OPENROUTER_HEADERS
                        } else emptyMap(),
                        logBuffer = logBuffer
                    )
                    applyStatus(probe.status())
                }
            }

            ConnectionMode.HERMES -> {
                if (current.gatewayUrl.isBlank()) {
                    _state.update {
                        it.copy(
                            test = ConnectionState.Failed(
                                reason = "Gateway URL is empty.",
                                kind = GatewayUrl.FailureKind.WRONG_URL
                            )
                        )
                    }
                    return
                }
                // Catch the "10.0.2.2 on a real phone" misconfig before we
                // even open a socket — it would otherwise eat the full
                // connect-timeout window and look like a generic outage.
                if (GatewayUrl.isEmulatorOnlyHost(current.gatewayUrl) && !GatewayUrl.isProbablyEmulator) {
                    _state.update {
                        it.copy(
                            test = ConnectionState.Failed(
                                reason = "10.0.2.2 only works in the Android emulator. " +
                                    "On a real phone, use the gateway's LAN IP (e.g. " +
                                    "http://192.168.1.42:8080), an ngrok / Cloudflare " +
                                    "tunnel, or a public HTTPS URL.",
                                kind = GatewayUrl.FailureKind.WRONG_URL
                            )
                        )
                    }
                    return
                }
                _state.update { it.copy(test = ConnectionState.Connecting) }
                viewModelScope.launch {
                    val probe = HermesGatewayClient(
                        http = http,
                        baseUrl = current.gatewayUrl,
                        token = current.gatewayToken.ifBlank { null },
                        providerApiKey = current.providerApiKey.ifBlank { null },
                        providerId = current.providerId.ifBlank { null },
                        logBuffer = logBuffer
                    )
                    applyStatus(probe.status())
                }
            }
        }
    }

    private fun applyStatus(status: HermesStatus) {
        _state.update {
            if (status.ok) {
                it.copy(test = ConnectionState.Connected(status))
            } else {
                it.copy(
                    test = ConnectionState.Failed(
                        reason = status.message ?: "Unknown error",
                        kind = status.failureKind ?: GatewayUrl.FailureKind.UNKNOWN
                    )
                )
            }
        }
    }

    /**
     * Validates the current form for the selected mode and persists it.
     * Returns a user-visible error string (also stashed in
     * `validationError`) if the form is incomplete; null on success.
     */
    fun save(onDone: () -> Unit) {
        val current = _state.value
        val err = validate(current)
        if (err != null) {
            _state.update { it.copy(validationError = err) }
            return
        }
        _state.update { it.copy(saving = true, validationError = null) }
        viewModelScope.launch {
            settings.setConnectionMode(current.mode)
            settings.setGatewayUrl(current.gatewayUrl)
            settings.setProviderId(current.providerId)
            settings.setModel(current.model)
            settings.setGatewayToken(current.gatewayToken.ifBlank { null })
            settings.setProviderApiKey(current.providerApiKey.ifBlank { null })
            settings.setOnboarded(true)
            logBuffer.info(TAG, "Saved connection settings (mode=${current.mode})")
            _state.update { it.copy(saving = false) }
            onDone()
        }
    }

    private fun validate(s: ProviderUiState): String? = when (s.mode) {
        ConnectionMode.MOCK -> null
        ConnectionMode.DIRECT -> when {
            s.providerApiKey.isBlank() -> "Enter your API key before saving."
            s.model.isBlank() -> "Enter a model id (e.g. openai/gpt-4o-mini)."
            s.providerId == "custom" && s.gatewayUrl.isBlank() ->
                "Custom provider needs a base URL."
            else -> null
        }
        ConnectionMode.HERMES -> if (s.gatewayUrl.isBlank()) {
            "Hermes mode needs a gateway URL."
        } else null
    }

    companion object {
        private const val TAG = "ProviderVM"
    }
}
