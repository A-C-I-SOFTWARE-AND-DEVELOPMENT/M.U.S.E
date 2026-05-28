package com.aci.hermes.data.jarvis

import com.aci.hermes.data.jarvis.JarvisIntentClassifier.Intent
import com.aci.hermes.data.model.TargetTool
import com.aci.hermes.data.model.TaskType
import org.junit.Assert.assertEquals
import org.junit.Test

class JarvisIntentClassifierTest {

    @Test
    fun `critical destructive language is classified as critical`() {
        val cases = listOf(
            "drop table users in prod",
            "rm -rf the whole repo",
            "force push to main please",
            "delete the repo",
        )
        for (text in cases) {
            val c = JarvisIntentClassifier.classify(text)
            assertEquals("expected CRITICAL for: $text", Intent.CRITICAL, c.intent)
            assertEquals(JarvisTone.CRITICAL, c.tone)
        }
    }

    @Test
    fun `risky-but-recoverable language is classified as approval`() {
        val cases = listOf(
            "deploy the gateway to prod",
            "merge to main and tag a release",
            "ship it to staging",
            "rotate the key",
        )
        for (text in cases) {
            val c = JarvisIntentClassifier.classify(text)
            assertEquals("expected APPROVAL for: $text", Intent.APPROVAL, c.intent)
            assertEquals(JarvisTone.SERIOUS, c.tone)
        }
    }

    @Test
    fun `security adjacent topics are flagged as serious`() {
        val cases = listOf(
            "found a possible leak in the gateway",
            "review the password handling",
            "GDPR question about user records",
        )
        for (text in cases) {
            val c = JarvisIntentClassifier.classify(text)
            assertEquals("expected SERIOUS for: $text", Intent.SERIOUS, c.intent)
        }
    }

    @Test
    fun `architecture prompts route to architecture intent`() {
        val c = JarvisIntentClassifier.classify("walk me through the architecture")
        assertEquals(Intent.ARCHITECTURE, c.intent)
    }

    @Test
    fun `task-shaped prompts route to task intent`() {
        val c = JarvisIntentClassifier.classify("build a chat screen for jarvis")
        assertEquals(Intent.TASK, c.intent)
    }

    @Test
    fun `casual greetings route to casual intent`() {
        assertEquals(Intent.CASUAL, JarvisIntentClassifier.classify("hi").intent)
        assertEquals(Intent.CASUAL, JarvisIntentClassifier.classify("thanks").intent)
        assertEquals(Intent.CASUAL, JarvisIntentClassifier.classify("good morning").intent)
    }

    @Test
    fun `unrecognized input falls back to default`() {
        val c = JarvisIntentClassifier.classify("what time is it in tokyo right now")
        assertEquals(Intent.DEFAULT, c.intent)
    }

    @Test
    fun `error trigger prefix is detected`() {
        assertEquals(Intent.ERROR_TRIGGER, JarvisIntentClassifier.classify("/error simulate failure").intent)
    }

    @Test
    fun `stall trigger prefix is detected`() {
        assertEquals(Intent.ABORT_TRIGGER, JarvisIntentClassifier.classify("/stall hold on").intent)
    }

    @Test
    fun `target tool inference picks the named tool`() {
        assertEquals(TargetTool.CLAUDE_CODE, JarvisIntentClassifier.inferTargetTool("Have Claude Code review this"))
        assertEquals(TargetTool.CODEX, JarvisIntentClassifier.inferTargetTool("Use Codex to refactor it"))
        assertEquals(TargetTool.CODEX, JarvisIntentClassifier.inferTargetTool("just build the thing"))
    }

    @Test
    fun `task type inference picks the right enum`() {
        assertEquals(TaskType.REVIEW, JarvisIntentClassifier.inferTaskType("review the diff"))
        assertEquals(TaskType.DEBUG, JarvisIntentClassifier.inferTaskType("the build is broken, debug it"))
        assertEquals(TaskType.REFACTOR, JarvisIntentClassifier.inferTaskType("refactor the orchestrator"))
        assertEquals(TaskType.BUILD, JarvisIntentClassifier.inferTaskType("build a chat screen"))
    }
}
