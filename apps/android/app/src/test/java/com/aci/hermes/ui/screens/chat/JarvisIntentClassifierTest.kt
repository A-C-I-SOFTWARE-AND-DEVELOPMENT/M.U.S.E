// Lives under `ui/screens/chat/` rather than `data/jarvis/` because the
// allowed test-path constraint for this lane is `**/chat/**`. The classifier
// it covers is in `com.aci.hermes.data.jarvis`.
package com.aci.hermes.ui.screens.chat

import com.aci.hermes.data.jarvis.JarvisIntentClassifier
import com.aci.hermes.data.jarvis.JarvisIntentClassifier.Intent
import com.aci.hermes.data.jarvis.JarvisTone
import com.aci.hermes.data.model.TargetTool
import com.aci.hermes.data.model.TaskType
import org.junit.Assert.assertEquals
import org.junit.Test

class JarvisIntentClassifierTest {

    @Test
    fun `error trigger maps to ERROR_TRIGGER intent`() {
        val c = JarvisIntentClassifier.classify("/error simulate gateway failure")
        assertEquals(Intent.ERROR_TRIGGER, c.intent)
        assertEquals(JarvisTone.NORMAL, c.tone)
    }

    @Test
    fun `stall trigger maps to ABORT_TRIGGER intent`() {
        val c = JarvisIntentClassifier.classify("/stall just hold on a bit")
        assertEquals(Intent.ABORT_TRIGGER, c.intent)
    }

    @Test
    fun `destructive keyword maps to CRITICAL`() {
        val c = JarvisIntentClassifier.classify("drop table users in production")
        assertEquals(Intent.CRITICAL, c.intent)
        assertEquals(JarvisTone.CRITICAL, c.tone)
    }

    @Test
    fun `release keyword maps to APPROVAL`() {
        val c = JarvisIntentClassifier.classify("deploy gateway to prod")
        assertEquals(Intent.APPROVAL, c.intent)
        assertEquals(JarvisTone.SERIOUS, c.tone)
    }

    @Test
    fun `security keyword maps to SERIOUS`() {
        val c = JarvisIntentClassifier.classify("audit the api key handling for leaks")
        assertEquals(Intent.SERIOUS, c.intent)
        assertEquals(JarvisTone.SERIOUS, c.tone)
    }

    @Test
    fun `architecture keyword maps to ARCHITECTURE`() {
        val c = JarvisIntentClassifier.classify("walk me through the architecture")
        assertEquals(Intent.ARCHITECTURE, c.intent)
    }

    @Test
    fun `build prompt maps to TASK`() {
        val c = JarvisIntentClassifier.classify("build a chat screen for jarvis")
        assertEquals(Intent.TASK, c.intent)
    }

    @Test
    fun `greeting maps to CASUAL`() {
        val c = JarvisIntentClassifier.classify("hey there")
        assertEquals(Intent.CASUAL, c.intent)
    }

    @Test
    fun `bland question falls back to DEFAULT`() {
        val c = JarvisIntentClassifier.classify("what's the weather like?")
        assertEquals(Intent.DEFAULT, c.intent)
    }

    @Test
    fun `target tool and task type inference picks up keywords`() {
        assertEquals(TargetTool.CLAUDE_CODE, JarvisIntentClassifier.inferTargetTool("hand this to claude-code"))
        assertEquals(TargetTool.CODEX, JarvisIntentClassifier.inferTargetTool("send to codex please"))
        assertEquals(TaskType.REVIEW, JarvisIntentClassifier.inferTaskType("review this PR"))
        assertEquals(TaskType.DEBUG, JarvisIntentClassifier.inferTaskType("debug the broken test"))
        assertEquals(TaskType.REFACTOR, JarvisIntentClassifier.inferTaskType("refactor the gateway"))
        assertEquals(TaskType.PLANNING, JarvisIntentClassifier.inferTaskType("plan the migration"))
        assertEquals(TaskType.BUILD, JarvisIntentClassifier.inferTaskType("ship a new feature"))
    }
}
