package com.aci.hermes.ui.screens.provider

/**
 * Lightweight catalogue of recommended models per provider. Keeps the chip
 * picker, the "reset to recommended" button and the provider-id heuristic
 * all reading from the same list.
 *
 * Not authoritative — providers add and retire models all the time. The
 * UI must NOT block on whether a suggested model is currently live; it's
 * just a starting point. The actual model id is whatever the user has in
 * the text field, and the end-to-end test surface in
 * [com.aci.hermes.data.network.DirectApiTester] is responsible for
 * surfacing "model not found" cleanly when the user picks something that
 * doesn't exist.
 */
internal object SuggestedModels {

    /** Provider-specific recommended-default model. Always first in the chip row. */
    fun recommendedForProvider(providerId: String): String = when (providerId) {
        "openrouter" -> "openai/gpt-4o-mini"
        "openai" -> "gpt-4o-mini"
        else -> "openai/gpt-4o-mini"
    }

    fun forProvider(providerId: String): List<String> = when (providerId) {
        "openrouter" -> listOf(
            "openai/gpt-4o-mini",
            "anthropic/claude-3.5-haiku",
            "google/gemini-flash-1.5",
            "meta-llama/llama-3.1-70b-instruct"
        )
        "openai" -> listOf(
            "gpt-4o-mini",
            "gpt-4o",
            "gpt-4.1-mini"
        )
        else -> emptyList()
    }

    /**
     * Returns true if `modelId` looks plausibly addressed at `providerId`,
     * based on prefix conventions. Used to avoid silently rewriting a
     * user-typed model when they switch providers if their model already
     * fits the new provider's namespace.
     */
    fun providerLooksValid(providerId: String, modelId: String): Boolean = when (providerId) {
        // OpenRouter requires "<vendor>/<model>" form.
        "openrouter" -> modelId.contains('/')
        // OpenAI direct uses bare ids (no slash).
        "openai" -> !modelId.contains('/')
        // Custom endpoints can accept anything.
        "custom" -> true
        else -> true
    }
}
