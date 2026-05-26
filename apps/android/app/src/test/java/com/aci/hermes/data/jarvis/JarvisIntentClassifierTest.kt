package com.aci.hermes.data.jarvis

import com.aci.hermes.data.jarvis.JarvisIntentClassifier.Intent
import com.aci.hermes.data.model.TargetTool
import com.aci.hermes.data.model.TaskType
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Launch gate: the classifier is the entry point to every tone +
 * approval-card decision in the chat lane. A small misclassification
 * here can quietly downgrade a destructive intent to a casual reply.
 *
 * The table below is the contract the rest of the system relies on.
 * If the classifier is retuned, this test should change in the same
 * commit.
 */
class JarvisIntentClassifierTest {

    @Test
    fun slash_error_routes_to_error_trigger() {
        val c = JarvisIntentClassifier.classify("/error please")
        assertEquals(Intent.ERROR_TRIGGER, c.intent)
        assertEquals(JarvisTone.NORMAL, c.tone)
        assertEquals(1.0, c.confidence, 0.001)
    }

    @Test
    fun slash_stall_routes_to_abort_trigger() {
        val c = JarvisIntentClassifier.classify("/stall for a while")
        assertEquals(Intent.ABORT_TRIGGER, c.intent)
        assertEquals(1.0, c.confidence, 0.001)
    }

    @Test
    fun destructive_prompts_are_classified_critical_with_critical_tone() {
        val prompts = listOf(
            "drop table users",
            "rm -rf /",
            "force push to main now",
            "delete production for me",
            "wipe the staging db",
            "truncate users table",
        )
        for (p in prompts) {
            val c = JarvisIntentClassifier.classify(p)
            assertEquals("prompt=$p", Intent.CRITICAL, c.intent)
            assertEquals("prompt=$p", JarvisTone.CRITICAL, c.tone)
            assertTrue("prompt=$p — confidence floor", c.confidence >= 0.9)
        }
    }

    @Test
    fun approval_prompts_are_classified_approval_with_serious_tone() {
        val prompts = listOf(
            "deploy to prod",
            "merge to main",
            "publish the package",
            "rotate the key",
            "open the PR",
            "ship it",
        )
        for (p in prompts) {
            val c = JarvisIntentClassifier.classify(p)
            assertEquals("prompt=$p", Intent.APPROVAL, c.intent)
            assertEquals("prompt=$p", JarvisTone.SERIOUS, c.tone)
        }
    }

    @Test
    fun serious_security_prompts_route_to_serious() {
        val prompts = listOf(
            "we may have leaked an api key",
            "potential CVE in our auth",
            "store a private key for me",
            "is this PII leak gdpr-relevant?",
        )
        for (p in prompts) {
            val c = JarvisIntentClassifier.classify(p)
            assertEquals("prompt=$p", Intent.SERIOUS, c.intent)
            assertEquals("prompt=$p", JarvisTone.SERIOUS, c.tone)
        }
    }

    @Test
    fun architecture_prompts_route_to_architecture() {
        val prompts = listOf(
            "explain how the orchestrator works",
            "walk me through the gateway flow",
            "what's the design doc for memory?",
            "system design for the audit log",
        )
        for (p in prompts) {
            val c = JarvisIntentClassifier.classify(p)
            assertEquals("prompt=$p", Intent.ARCHITECTURE, c.intent)
        }
    }

    @Test
    fun very_long_prompt_routes_to_architecture_by_length_alone() {
        // Prompt body intentionally avoids every keyword list (CRITICAL,
        // APPROVAL, SERIOUS, ARCHITECTURE, TASK, CASUAL) so the only
        // reason it should route to ARCHITECTURE is the length-only
        // fallback (`trimmed.length > 240`).
        val long = "I am pondering a quieter question — just rambling " +
            "around an idea, no verbs that map to a job. " + "x".repeat(220)
        val c = JarvisIntentClassifier.classify(long)
        assertEquals(Intent.ARCHITECTURE, c.intent)
    }

    @Test
    fun task_prompts_route_to_task() {
        val prompts = listOf(
            "build a settings screen",
            "implement a retry helper",
            "scaffold the audit detail view",
            "draft a migration",
            "rename FooBar to BazQux",
        )
        for (p in prompts) {
            val c = JarvisIntentClassifier.classify(p)
            assertEquals("prompt=$p", Intent.TASK, c.intent)
        }
    }

    @Test
    fun casual_openers_classified_casual() {
        for (p in listOf("hi", "hey", "thanks", "good morning", "ok")) {
            val c = JarvisIntentClassifier.classify(p)
            assertEquals("prompt=$p", Intent.CASUAL, c.intent)
        }
    }

    @Test
    fun unmatched_short_question_falls_back_to_default() {
        val c = JarvisIntentClassifier.classify("what time is it?")
        assertEquals(Intent.DEFAULT, c.intent)
    }

    @Test
    fun infer_task_type_covers_known_categories() {
        assertEquals(TaskType.REVIEW, JarvisIntentClassifier.inferTaskType("please review this PR"))
        assertEquals(TaskType.DEBUG, JarvisIntentClassifier.inferTaskType("the build is broken, help debug"))
        assertEquals(TaskType.REFACTOR, JarvisIntentClassifier.inferTaskType("refactor the memory store"))
        assertEquals(TaskType.RESEARCH, JarvisIntentClassifier.inferTaskType("look into rope ds"))
        assertEquals(TaskType.PLANNING, JarvisIntentClassifier.inferTaskType("plan the next sprint"))
        // Falls back to BUILD when nothing matches.
        assertEquals(TaskType.BUILD, JarvisIntentClassifier.inferTaskType("ship the settings screen"))
    }

    @Test
    fun infer_target_tool_picks_explicit_tool_then_defaults_to_codex() {
        assertEquals(TargetTool.CLAUDE_CODE, JarvisIntentClassifier.inferTargetTool("send to claude code"))
        assertEquals(TargetTool.CLAUDE, JarvisIntentClassifier.inferTargetTool("ask claude about it"))
        assertEquals(TargetTool.CODEX, JarvisIntentClassifier.inferTargetTool("hand it to codex"))
        assertEquals(TargetTool.CHATGPT, JarvisIntentClassifier.inferTargetTool("paste into chatgpt"))
        // Default fallback is CODEX (per the classifier today).
        assertEquals(TargetTool.CODEX, JarvisIntentClassifier.inferTargetTool("just do it"))
    }
}
