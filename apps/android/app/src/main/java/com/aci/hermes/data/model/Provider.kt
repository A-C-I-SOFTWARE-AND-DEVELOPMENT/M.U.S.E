package com.aci.hermes.data.model

/**
 * Subset of the Hermes-supported model providers exposed in the Android
 * companion app. The full set lives in the Python core; we expose the
 * ones an end user is most likely to want to point at directly.
 */
data class ProviderOption(
    val id: String,
    val displayName: String,
    val apiKeyUrl: String?,
    val notes: String
)

object Providers {
    val OPENROUTER = ProviderOption(
        id = "openrouter",
        displayName = "OpenRouter (200+ models)",
        apiKeyUrl = "https://openrouter.ai/keys",
        notes = "Recommended default — one key, many models."
    )
    val NOUS_PORTAL = ProviderOption(
        id = "nous",
        displayName = "Nous Portal",
        apiKeyUrl = "https://portal.nousresearch.com",
        notes = "First-party Nous Research endpoint."
    )
    val OPENAI = ProviderOption(
        id = "openai",
        displayName = "OpenAI",
        apiKeyUrl = "https://platform.openai.com/api-keys",
        notes = "GPT models."
    )
    val NOVITA = ProviderOption(
        id = "novita",
        displayName = "NovitaAI",
        apiKeyUrl = "https://novita.ai",
        notes = "AI-native cloud."
    )
    val CUSTOM = ProviderOption(
        id = "custom",
        displayName = "Custom OpenAI-compatible endpoint",
        apiKeyUrl = null,
        notes = "Configure on the gateway side; the app forwards the key."
    )

    val all = listOf(OPENROUTER, NOUS_PORTAL, OPENAI, NOVITA, CUSTOM)

    fun byId(id: String): ProviderOption = all.firstOrNull { it.id == id } ?: OPENROUTER
}
