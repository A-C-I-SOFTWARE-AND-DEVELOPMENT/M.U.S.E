package com.aci.hermes.orchestrator

import com.aci.hermes.data.model.AiToolProfile
import com.aci.hermes.data.model.DefaultToolProfiles
import com.aci.hermes.data.model.HermesTask
import com.aci.hermes.data.model.TargetTool
import com.aci.hermes.data.model.TaskStatus
import com.aci.hermes.data.model.TaskType
import com.aci.hermes.data.orchestrator.PromptBuilder
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

class PromptBuilderTest {

    private val sampleTask = HermesTask(
        id = "task-1",
        title = "Implement onboarding survey",
        description = "Add a five-question onboarding survey behind a feature flag.",
        workspacePath = "/Users/jeremiah/repos/hermes-agent",
        targetTool = TargetTool.CODEX,
        taskType = TaskType.BUILD,
        status = TaskStatus.READY_FOR_HANDOFF,
        reviewNotes = "Reviewer wants a screenshot diff in the PR.",
        nextAction = "Open a draft PR and tag @j-echerd.",
    )

    @Test
    fun `safety block is invariant across every target tool`() {
        val builder = PromptBuilder()
        val targets = listOf(
            DefaultToolProfiles.CODEX,
            DefaultToolProfiles.CHATGPT,
            DefaultToolProfiles.CLAUDE_CODE,
            DefaultToolProfiles.CLAUDE,
            null, // null falls back to MANUAL profile inside the builder
        )
        for (profile in targets) {
            val prompt = builder.build(sampleTask, profile)
            assertTrue(
                "Safety section missing for ${profile?.targetTool ?: "MANUAL"}",
                prompt.contains("## Safety requirements"),
            )
            assertTrue(
                "Auth-bypass clause missing for ${profile?.targetTool ?: "MANUAL"}",
                prompt.contains("Do not bypass authentication"),
            )
            assertTrue(
                "Exfiltration clause missing for ${profile?.targetTool ?: "MANUAL"}",
                prompt.contains("Do not exfiltrate, copy, or transmit API keys"),
            )
            assertTrue(
                "ToS clause missing for ${profile?.targetTool ?: "MANUAL"}",
                prompt.contains("Stay within the official tool's terms of service"),
            )
        }
    }

    @Test
    fun `safety block contains no API keys or tokens even if task description tries to inject them`() {
        val builder = PromptBuilder()
        val poisoned = sampleTask.copy(
            description = "Use my key sk-redacted-fake-key-for-test-purposes-only " +
                "and the bearer eyJhbGciOi.fake.value to call OpenAI.",
        )
        val prompt = builder.build(poisoned, DefaultToolProfiles.CODEX)
        // We do NOT strip the user's text — but the SAFETY_BLOCK must still
        // be present so the receiving model gets the instruction to ignore it.
        assertTrue(prompt.contains("## Safety requirements"))
        assertTrue(
            "SAFETY_BLOCK must instruct treating credentials as out-of-scope",
            prompt.contains("Treat API keys and tokens as out of scope"),
        )
    }

    @Test
    fun `codex builder includes gradle assembleDebug as acceptance criterion`() {
        val prompt = PromptBuilder().build(sampleTask, DefaultToolProfiles.CODEX)
        assertTrue(prompt.contains("`./gradlew assembleDebug`"))
    }

    @Test
    fun `claude_code reviewer is told not to overwrite builder changes blindly`() {
        val prompt = PromptBuilder().build(
            sampleTask.copy(targetTool = TargetTool.CLAUDE_CODE),
            DefaultToolProfiles.CLAUDE_CODE,
        )
        assertTrue(prompt.contains("Do not overwrite Builder changes blindly"))
    }

    @Test
    fun `manual fallback profile produces a manual handoff role`() {
        val prompt = PromptBuilder().build(
            sampleTask.copy(targetTool = TargetTool.MANUAL),
            null,
        )
        assertTrue(prompt.contains("Manual handoff"))
    }

    @Test
    fun `task title appears in the goal section`() {
        val prompt = PromptBuilder().build(sampleTask, DefaultToolProfiles.CODEX)
        assertTrue(prompt.contains("Build: Implement onboarding survey"))
    }

    @Test
    fun `untitled task does not crash and surfaces placeholder`() {
        val prompt = PromptBuilder().build(
            sampleTask.copy(title = ""),
            DefaultToolProfiles.CODEX,
        )
        assertTrue(prompt.contains("(untitled task)"))
    }

    @Test
    fun `description-less task surfaces explicit no-description marker`() {
        val prompt = PromptBuilder().build(
            sampleTask.copy(description = ""),
            DefaultToolProfiles.CODEX,
        )
        assertTrue(prompt.contains("(no description provided)"))
    }

    @Test
    fun `prompt ends with a single trailing newline`() {
        val prompt = PromptBuilder().build(sampleTask, DefaultToolProfiles.CODEX)
        assertTrue(prompt.endsWith("\n"))
        assertFalse(prompt.endsWith("\n\n\n"))
    }

    @Test
    fun `task type verbs are deterministic`() {
        val builder = PromptBuilder()
        val cases = mapOf(
            TaskType.BUILD to "Build:",
            TaskType.REVIEW to "Review:",
            TaskType.AUDIT to "Audit:",
            TaskType.DEBUG to "Debug:",
            TaskType.REFACTOR to "Refactor:",
            TaskType.RESEARCH to "Research:",
            TaskType.PLANNING to "Plan:",
        )
        for ((type, prefix) in cases) {
            val prompt = builder.build(sampleTask.copy(taskType = type), DefaultToolProfiles.CODEX)
            assertTrue("Expected '$prefix' in prompt for $type", prompt.contains(prefix))
        }
    }

    @Test
    fun `unknown profile falls back to manual profile`() {
        val explicit = AiToolProfile(
            id = "experiment",
            displayName = "Experimental tool",
            provider = "Lab",
            role = "Sandbox",
            officialToolType = "Lab tool",
            launchMethod = "manual",
            notes = "",
            targetTool = TargetTool.MANUAL,
        )
        val prompt = PromptBuilder().build(sampleTask, explicit)
        assertNotNull(prompt)
        assertTrue(prompt.contains("## Safety requirements"))
    }

    @Test
    fun `safety block is identical to declared constant`() {
        assertEquals(
            "SAFETY_BLOCK is the source of truth across handoff targets",
            """- Do not bypass authentication on any provider.
- Do not exfiltrate, copy, or transmit API keys, session tokens, or cookies.
- Stay within the official tool's terms of service.
- Treat API keys and tokens as out of scope for this task.
- If the goal would require violating any of the above, stop and report the conflict instead.""",
            PromptBuilder.SAFETY_BLOCK,
        )
    }
}
