package com.aci.hermes.ui.screens.provider

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.model.ConnectionState
import com.aci.hermes.data.model.HermesStatus
import com.aci.hermes.data.network.AIClientFactory
import com.aci.hermes.data.network.DirectAIClient
import com.aci.hermes.data.network.DirectApiTester
import com.aci.hermes.data.network.DirectTestResult
import com.aci.hermes.data.network.HermesGatewayClient
import com.aci.hermes.data.preferences.ConnectionMode
import com.aci.hermes.data.preferences.SettingsRepository
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
    val customApiBaseUrl: String = "",
    val providerId: String = "openrouter",
    val providerApiKey: String = "",
    val apiKeyVisible: Boolean = false,
    val model: String = SettingsRepository.DEFAULT_DIRECT_MODEL,
    val lastWorkingModel: String? = null,
    val test: ConnectionState = ConnectionState.Unknown,
    val saving: Boolean = false,
    val validationError: String? = null
)

class ProviderViewModel(
    private val settings: SettingsRepository,
    private val testHttp: OkHttpClient,
    private val directApiTester: DirectApiTester,
    private val logBuffer: LogBuffer
) : ViewModel() {

    private val _state = MutableStateFlow(ProviderUiState())
    val state: StateFlow<ProviderUiState> = _state.asStateFlow()

    /**
     * If a caller (e.g. the nav graph) sets the mode before our init
     * coroutine finishes loading persisted settings, we must NOT clobber
     * their choice when the snapshot arrives. This flag remembers the
     * explicit override so the init resolver picks the right value.
     */
    private var modeOverride: ConnectionMode? = null

    init {
        viewModelScope.launch {
            val snap = settings.snapshot()
            val secrets = settings.secretsSnapshot()
            val resolvedMode = modeOverride ?: snap.connectionMode
            _state.value = ProviderUiState(
                mode = resolvedMode,
                gatewayUrl = snap.gatewayUrl,
                gatewayToken = secrets.gatewayToken.orEmpty(),
                customApiBaseUrl = snap.customApiBaseUrl,
                providerId = snap.providerId,
                providerApiKey = secrets.providerApiKey.orEmpty(),
                model = snap.model,
                lastWorkingModel = snap.lastWorkingModel
            )
        }
    }

    fun setMode(m: ConnectionMode) {
        modeOverride = m
        _state.update {
            // Switching modes drops the previous test result — it's no
            // longer meaningful against the new mode's endpoint.
            it.copy(mode = m, test = ConnectionState.Unknown, validationError = null)
        }
    }
    fun setGatewayUrl(v: String) = _state.update { it.copy(gatewayUrl = v, test = ConnectionState.Unknown) }
    fun setGatewayToken(v: String) = _state.update { it.copy(gatewayToken = v, test = ConnectionState.Unknown) }
    fun setCustomApiBaseUrl(v: String) = _state.update {
        it.copy(customApiBaseUrl = v, test = ConnectionState.Unknown)
    }
    fun setProviderId(v: String) = _state.update {
        // Suggested-model chips are provider-specific — if the current
        // model id doesn't match the new provider's namespace, reset it to
        // the recommended default for that provider so the chip selection
        // makes sense. We keep the user's text if it already looks valid.
        val resetModel = if (it.model.isBlank() ||
            !SuggestedModels.providerLooksValid(v, it.model)
        ) {
            SuggestedModels.recommendedForProvider(v)
        } else it.model
        it.copy(providerId = v, model = resetModel, test = ConnectionState.Unknown)
    }
    fun setProviderApiKey(v: String) = _state.update {
        it.copy(providerApiKey = v, test = ConnectionState.Unknown)
    }
    fun toggleApiKeyVisible() = _state.update { it.copy(apiKeyVisible = !it.apiKeyVisible) }
    fun clearApiKey() = _state.update {
        it.copy(providerApiKey = "", test = ConnectionState.Unknown)
    }
    fun setModel(v: String) = _state.update { it.copy(model = v, test = ConnectionState.Unknown) }
    fun resetToRecommendedModel() = _state.update {
        it.copy(
            model = SuggestedModels.recommendedForProvider(it.providerId),
            test = ConnectionState.Unknown
        )
    }
    fun useLastWorkingModel() = _state.update {
        val last = it.lastWorkingModel
        if (last.isNullOrBlank()) it
        else it.copy(model = last, test = ConnectionState.Unknown)
    }

    fun testConnection() {
        val current = _state.value
        when (current.mode) {
            ConnectionMode.MOCK -> {
                _state.update {
                    it.copy(test = ConnectionState.Connected(HermesStatus(ok = true, message = "Mock mode")))
                }
            }

            ConnectionMode.DIRECT -> runDirectTest(current)

            ConnectionMode.HERMES -> {
                if (current.gatewayUrl.isBlank()) {
                    _state.update { it.copy(test = ConnectionState.Failed("Gateway URL is empty.")) }
                    return
                }
                _state.update { it.copy(test = ConnectionState.Connecting) }
                viewModelScope.launch {
                    val probe = HermesGatewayClient(
                        http = testHttp,
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

    private fun runDirectTest(current: ProviderUiState) {
        val key = current.providerApiKey.trim()
        if (key.isEmpty()) {
            _state.update { it.copy(test = ConnectionState.Failed("Enter an API key to test.")) }
            return
        }
        if (current.providerId == "custom" && current.customApiBaseUrl.isBlank()) {
            _state.update { it.copy(test = ConnectionState.Failed("Custom endpoint needs a base URL.")) }
            return
        }
        val model = current.model.ifBlank { SettingsRepository.DEFAULT_DIRECT_MODEL }
        _state.update { it.copy(test = ConnectionState.Connecting) }
        viewModelScope.launch {
            val result = directApiTester.run(
                baseUrl = AIClientFactory.baseUrlFor(current.providerId, current.customApiBaseUrl),
                apiKey = key,
                model = model,
                providerLabel = AIClientFactory.providerLabel(current.providerId),
                extraHeaders = if (current.providerId == "openrouter") {
                    DirectAIClient.OPENROUTER_HEADERS
                } else emptyMap()
            )
            applyDirectTestResult(result, model)
        }
    }

    private fun applyDirectTestResult(result: DirectTestResult, model: String) {
        when (result) {
            is DirectTestResult.Success -> {
                _state.update {
                    it.copy(
                        test = ConnectionState.Connected(
                            HermesStatus(
                                ok = true,
                                model = model,
                                message = result.message
                            )
                        ),
                        lastWorkingModel = model
                    )
                }
                viewModelScope.launch { settings.setLastWorkingModel(model) }
            }
            else -> _state.update { it.copy(test = ConnectionState.Failed(result.message)) }
        }
    }

    private fun applyStatus(status: HermesStatus) {
        _state.update {
            if (status.ok) it.copy(test = ConnectionState.Connected(status))
            else it.copy(test = ConnectionState.Failed(status.message ?: "Unknown error"))
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
            // Persist *both* URL fields independently. Direct mode users no
            // longer pollute the Hermes-gateway URL field by entering a
            // custom OpenAI-compatible endpoint.
            settings.setGatewayUrl(current.gatewayUrl)
            settings.setCustomApiBaseUrl(current.customApiBaseUrl)
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

    internal fun validate(s: ProviderUiState): String? = ProviderFormValidator.validate(s)

    companion object {
        private const val TAG = "ProviderVM"
    }
}
