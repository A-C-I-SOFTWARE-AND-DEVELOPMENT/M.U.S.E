package com.aci.hermes.ui.screens.provider

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class SuggestedModelsTest {

    @Test
    fun `recommended openrouter model uses vendor prefix`() {
        assertEquals("openai/gpt-4o-mini", SuggestedModels.recommendedForProvider("openrouter"))
    }

    @Test
    fun `recommended openai model has no vendor prefix`() {
        assertEquals("gpt-4o-mini", SuggestedModels.recommendedForProvider("openai"))
    }

    @Test
    fun `unknown provider falls back to a reasonable default`() {
        // Custom + bogus provider should still produce something usable.
        val rec = SuggestedModels.recommendedForProvider("custom")
        assertTrue(rec.isNotBlank())
    }

    @Test
    fun `forProvider returns chips for openrouter and openai`() {
        assertTrue(SuggestedModels.forProvider("openrouter").isNotEmpty())
        assertTrue(SuggestedModels.forProvider("openai").isNotEmpty())
    }

    @Test
    fun `forProvider returns empty list for custom`() {
        // Custom endpoints can be anything — we don't ship suggestions.
        assertTrue(SuggestedModels.forProvider("custom").isEmpty())
    }

    @Test
    fun `providerLooksValid rejects openrouter ids without a slash`() {
        assertFalse(SuggestedModels.providerLooksValid("openrouter", "gpt-4o-mini"))
        assertTrue(SuggestedModels.providerLooksValid("openrouter", "openai/gpt-4o-mini"))
    }

    @Test
    fun `providerLooksValid rejects openai ids with a slash`() {
        // OpenAI direct uses bare model ids; slash form is OpenRouter-shaped.
        assertFalse(SuggestedModels.providerLooksValid("openai", "openai/gpt-4o-mini"))
        assertTrue(SuggestedModels.providerLooksValid("openai", "gpt-4o-mini"))
    }

    @Test
    fun `providerLooksValid accepts anything for custom endpoints`() {
        assertTrue(SuggestedModels.providerLooksValid("custom", "anything-here"))
        assertTrue(SuggestedModels.providerLooksValid("custom", "vendor/model"))
    }
}
