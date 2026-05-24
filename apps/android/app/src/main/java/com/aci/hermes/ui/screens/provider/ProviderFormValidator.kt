package com.aci.hermes.ui.screens.provider

import com.aci.hermes.data.preferences.ConnectionMode

/**
 * Pure validation of the Provider form's current state. Extracted from
 * [ProviderViewModel] so unit tests can exercise the rules without
 * standing up a fake ViewModel + DataStore + OkHttp stack.
 */
internal object ProviderFormValidator {

    /**
     * Returns a user-visible error string when the form cannot be saved
     * for the selected mode, or null when it can.
     *
     * Rules:
     *   * Mock mode — always saveable. No keys, no URLs.
     *   * Direct mode — needs an API key and a model id. If the user
     *     picked the custom provider, the custom base URL is also
     *     required (the gateway URL is NOT consulted; the two fields
     *     are independent).
     *   * Hermes mode — needs a gateway URL. The API key / token are
     *     optional because some gateways are open or auth-via-cookie.
     */
    fun validate(state: ProviderUiState): String? = when (state.mode) {
        ConnectionMode.MOCK -> null

        ConnectionMode.DIRECT -> when {
            state.providerApiKey.isBlank() -> "Enter your API key before saving."
            state.model.isBlank() -> "Enter a model id (e.g. openai/gpt-4o-mini)."
            state.providerId == "custom" && state.customApiBaseUrl.isBlank() ->
                "Custom provider needs a base URL."
            else -> null
        }

        ConnectionMode.HERMES -> if (state.gatewayUrl.isBlank()) {
            "Hermes mode needs a gateway URL."
        } else null
    }
}
