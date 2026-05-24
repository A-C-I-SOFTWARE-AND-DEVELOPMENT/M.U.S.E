package com.aci.hermes.ui.screens.provider

import com.aci.hermes.data.preferences.ConnectionMode
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/**
 * Pure validation rules. These tests don't touch Android, OkHttp, or
 * DataStore — they're the safety net for the four "saveable?" conditions
 * the Provider screen relies on.
 */
class ProviderFormValidatorTest {

    @Test
    fun `mock mode is always saveable even with no fields`() {
        val state = ProviderUiState(mode = ConnectionMode.MOCK)
        assertNull(ProviderFormValidator.validate(state))
    }

    @Test
    fun `mock mode is saveable even when other modes' fields are blank`() {
        // Mock should ignore API key + URL state entirely.
        val state = ProviderUiState(
            mode = ConnectionMode.MOCK,
            gatewayUrl = "",
            providerApiKey = "",
            customApiBaseUrl = "",
            model = ""
        )
        assertNull(ProviderFormValidator.validate(state))
    }

    @Test
    fun `direct mode requires an API key`() {
        val state = ProviderUiState(
            mode = ConnectionMode.DIRECT,
            providerApiKey = "",
            model = "openai/gpt-4o-mini"
        )
        assertEquals("Enter your API key before saving.", ProviderFormValidator.validate(state))
    }

    @Test
    fun `direct mode requires a model id`() {
        val state = ProviderUiState(
            mode = ConnectionMode.DIRECT,
            providerApiKey = "sk-xxx",
            model = ""
        )
        assertEquals(
            "Enter a model id (e.g. openai/gpt-4o-mini).",
            ProviderFormValidator.validate(state)
        )
    }

    @Test
    fun `direct mode with key and model is saveable for openrouter`() {
        val state = ProviderUiState(
            mode = ConnectionMode.DIRECT,
            providerId = "openrouter",
            providerApiKey = "sk-or-xxx",
            model = "openai/gpt-4o-mini"
        )
        assertNull(ProviderFormValidator.validate(state))
    }

    @Test
    fun `direct mode with custom provider requires the custom base URL`() {
        val state = ProviderUiState(
            mode = ConnectionMode.DIRECT,
            providerId = "custom",
            providerApiKey = "sk-xxx",
            model = "anything",
            customApiBaseUrl = ""
        )
        assertEquals("Custom provider needs a base URL.", ProviderFormValidator.validate(state))
    }

    @Test
    fun `direct mode with custom provider ignores gateway URL field`() {
        // The gateway URL is for Hermes mode only. Even if it's blank, a
        // direct-custom save should succeed as long as customApiBaseUrl is
        // populated.
        val state = ProviderUiState(
            mode = ConnectionMode.DIRECT,
            providerId = "custom",
            providerApiKey = "sk-xxx",
            model = "anything",
            customApiBaseUrl = "https://example.com/v1",
            gatewayUrl = ""
        )
        assertNull(ProviderFormValidator.validate(state))
    }

    @Test
    fun `hermes mode requires a gateway URL`() {
        val state = ProviderUiState(
            mode = ConnectionMode.HERMES,
            gatewayUrl = ""
        )
        assertEquals("Hermes mode needs a gateway URL.", ProviderFormValidator.validate(state))
    }

    @Test
    fun `hermes mode is saveable with just a gateway URL`() {
        val state = ProviderUiState(
            mode = ConnectionMode.HERMES,
            gatewayUrl = "https://hermes.example.com"
        )
        assertNull(ProviderFormValidator.validate(state))
    }
}
