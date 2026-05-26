package com.aci.hermes.handoff

import com.aci.hermes.data.model.DefaultToolProfiles
import com.aci.hermes.data.model.HermesTask
import com.aci.hermes.data.model.TargetTool
import com.aci.hermes.data.model.TaskType
import com.aci.hermes.data.orchestrator.PromptBuilder
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Cross-target invariants for the handoff contract.
 *
 * Most of these are negative-path / privacy guarantees: the prompt
 * builder must NEVER embed our own API keys (we don't have any), must
 * NEVER fabricate provider auth headers, and must NEVER drop the
 * safety block — even on weird task shapes.
 */
class HandoffSafetyContractTest {

    private val builder = PromptBuilder()

    private fun task(
        title: String = "Test task",
        description: String = "Test description",
        targetTool: TargetTool = TargetTool.CODEX,
    ) = HermesTask(
        id = "t",
        title = title,
        description = description,
        targetTool = targetTool,
        taskType = TaskType.BUILD,
    )

    @Test
    fun `prompt never embeds a fabricated bearer token`() {
        val prompt = builder.build(task(), DefaultToolProfiles.CODEX)
        // None of these auth-shaped strings should appear in the prompt
        // unless the user themselves typed them. The builder must not
        // introduce them on its own.
        val forbidden = listOf(
            "Authorization: Bearer",
            "X-Hermes-Provider-Key",
            "OPENAI_API_KEY=",
            "ANTHROPIC_API_KEY=",
        )
        for (f in forbidden) {
            assertFalse(
                "Prompt unexpectedly contains '$f' — handoff must never fabricate auth.",
                prompt.contains(f),
            )
        }
    }

    @Test
    fun `prompt never includes a gateway URL`() {
        val prompt = builder.build(task(), DefaultToolProfiles.CODEX)
        // The app is local-only. Gateway URLs would indicate the chat /
        // gateway architecture leaked back in.
        val forbidden = listOf(
            "/v1/chat",
            "/v1/health",
            "http://10.0.2.2",
            "ws://",
            "wss://",
        )
        for (f in forbidden) {
            assertFalse(
                "Prompt unexpectedly contains '$f' — app is local-only.",
                prompt.contains(f),
            )
        }
    }

    @Test
    fun `every default profile renders without exception or null fields`() {
        for (profile in DefaultToolProfiles.all) {
            val prompt = builder.build(task(targetTool = profile.targetTool), profile)
            assertNotNull("Prompt null for ${profile.targetTool}", prompt)
            assertTrue("Prompt empty for ${profile.targetTool}", prompt.isNotBlank())
            assertTrue(
                "Role line missing for ${profile.targetTool}",
                prompt.contains("## Role"),
            )
        }
    }

    @Test
    fun `manual target with null profile still produces a usable prompt`() {
        val prompt = builder.build(task(targetTool = TargetTool.MANUAL), null)
        assertTrue(prompt.contains("Manual handoff"))
        assertTrue(prompt.contains("## Safety requirements"))
    }

    @Test
    fun `every default profile has a web fallback URL we can audit`() {
        for (profile in DefaultToolProfiles.all) {
            val fallback = profile.webFallbackUrl
            assertNotNull("Web fallback missing for ${profile.id}", fallback)
            // We only ship official provider domains as fallbacks.
            val ok = fallback!!.startsWith("https://chatgpt.com") ||
                fallback.startsWith("https://claude.com") ||
                fallback.startsWith("https://claude.ai")
            assertTrue(
                "Web fallback for ${profile.id} is not an official provider domain: $fallback",
                ok,
            )
        }
    }

    @Test
    fun `byTargetTool resolves every non-manual target deterministically`() {
        assertEquals(DefaultToolProfiles.CODEX, DefaultToolProfiles.byTargetTool(TargetTool.CODEX))
        assertEquals(DefaultToolProfiles.CHATGPT, DefaultToolProfiles.byTargetTool(TargetTool.CHATGPT))
        assertEquals(DefaultToolProfiles.CLAUDE_CODE, DefaultToolProfiles.byTargetTool(TargetTool.CLAUDE_CODE))
        assertEquals(DefaultToolProfiles.CLAUDE, DefaultToolProfiles.byTargetTool(TargetTool.CLAUDE))
        assertEquals(null, DefaultToolProfiles.byTargetTool(TargetTool.MANUAL))
    }
}
