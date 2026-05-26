package com.aci.hermes.data.jarvis

import com.aci.hermes.data.model.TargetTool
import com.aci.hermes.data.model.TaskType

/**
 * Pure classification logic for incoming user prompts. Lives in the
 * data layer so the mock gateway and the unit tests can share it
 * without dragging Compose or coroutines into the test classpath.
 *
 * The classifier never claims to be doing real NLU — it's a tight,
 * deterministic ruleset that maps a prompt to the response shape
 * Jarvis Prime should produce. Tuning happens here, in one place.
 */
object JarvisIntentClassifier {

    enum class Intent {
        ERROR_TRIGGER,      // "/error ..." — gateway failure for tests/demos
        ABORT_TRIGGER,      // "/stall ..." — long stream, useful for stop tests
        CRITICAL,           // prod / destructive / irreversible
        APPROVAL,           // risky-but-recoverable, owner-gated
        SERIOUS,            // security/privacy adjacent, not destructive
        ARCHITECTURE,       // deep technical answer expected
        TASK,               // task-shaped voice/text intake
        CASUAL,             // greeting, small talk, thanks
        DEFAULT,            // ordinary question
    }

    data class Classification(
        val intent: Intent,
        val tone: JarvisTone,
        val confidence: Double,
    )

    fun classify(prompt: String): Classification {
        val trimmed = prompt.trim()
        val lower = trimmed.lowercase()

        if (lower.startsWith("/error")) {
            return Classification(Intent.ERROR_TRIGGER, JarvisTone.NORMAL, 1.0)
        }
        if (lower.startsWith("/stall")) {
            return Classification(Intent.ABORT_TRIGGER, JarvisTone.NORMAL, 1.0)
        }

        if (containsAny(lower, CRITICAL_KEYWORDS)) {
            return Classification(Intent.CRITICAL, JarvisTone.CRITICAL, 0.95)
        }
        if (containsAny(lower, APPROVAL_KEYWORDS)) {
            return Classification(Intent.APPROVAL, JarvisTone.SERIOUS, 0.9)
        }
        if (containsAny(lower, SERIOUS_KEYWORDS)) {
            return Classification(Intent.SERIOUS, JarvisTone.SERIOUS, 0.8)
        }
        if (containsAny(lower, ARCHITECTURE_KEYWORDS) || trimmed.length > 240) {
            return Classification(Intent.ARCHITECTURE, JarvisTone.NORMAL, 0.7)
        }
        if (containsAny(lower, TASK_KEYWORDS)) {
            return Classification(Intent.TASK, JarvisTone.NORMAL, 0.85)
        }
        if (isCasual(lower)) {
            return Classification(Intent.CASUAL, JarvisTone.NORMAL, 0.9)
        }
        return Classification(Intent.DEFAULT, JarvisTone.NORMAL, 0.5)
    }

    fun inferTaskType(prompt: String): TaskType {
        val lower = prompt.lowercase()
        return when {
            containsAny(lower, listOf("review", "audit")) -> TaskType.REVIEW
            containsAny(lower, listOf("debug", "fix the bug", "broken")) -> TaskType.DEBUG
            containsAny(lower, listOf("refactor", "clean up", "tidy")) -> TaskType.REFACTOR
            containsAny(lower, listOf("research", "look into", "compare")) -> TaskType.RESEARCH
            containsAny(lower, listOf("plan", "design", "architecture")) -> TaskType.PLANNING
            containsAny(lower, listOf("audit", "security audit")) -> TaskType.AUDIT
            else -> TaskType.BUILD
        }
    }

    fun inferTargetTool(prompt: String): TargetTool {
        val lower = prompt.lowercase()
        return when {
            "claude code" in lower || "claude-code" in lower -> TargetTool.CLAUDE_CODE
            "claude" in lower -> TargetTool.CLAUDE
            "codex" in lower -> TargetTool.CODEX
            "chatgpt" in lower -> TargetTool.CHATGPT
            else -> TargetTool.CODEX
        }
    }

    private fun containsAny(haystack: String, needles: List<String>): Boolean =
        needles.any { it in haystack }

    private fun isCasual(lower: String): Boolean {
        if (lower.length <= 24) {
            val casualOpeners = listOf(
                "hi", "hey", "hello", "yo", "sup", "what's up", "whats up",
                "good morning", "good evening", "thanks", "thank you", "ty",
                "cheers", "ok", "okay", "cool", "nice",
            )
            if (casualOpeners.any { lower == it || lower.startsWith("$it ") || lower.startsWith("$it,") }) {
                return true
            }
        }
        return false
    }

    private val CRITICAL_KEYWORDS = listOf(
        "drop table", "delete production", "wipe", "rm -rf", "force push to main",
        "force-push main", "reset --hard origin/main", "delete the repo", "delete repo",
        "purge prod", "drop database", "truncate users", "delete all users",
    )

    private val APPROVAL_KEYWORDS = listOf(
        "deploy", "release", "merge to main", "merge into main", "push to prod",
        "publish", "ship it", "promote to prod", "rotate the key", "rotate secret",
        "open the pr", "open pr", "force push", "rebase main",
    )

    private val SERIOUS_KEYWORDS = listOf(
        "security", "breach", "leak", "vulnerability", "cve", "exploit",
        "password", "secret", "credential", "api key", "private key",
        "pii", "gdpr", "compliance",
    )

    private val ARCHITECTURE_KEYWORDS = listOf(
        "architecture", "deep dive", "explain how", "walk me through",
        "how does it work", "trade-off", "tradeoff", "design doc",
        "rfc", "system design",
    )

    private val TASK_KEYWORDS = listOf(
        "build", "add", "implement", "wire", "scaffold", "ship", "make",
        "create a", "set up", "draft", "spike", "prototype", "fix",
        "refactor", "rename", "rewrite", "port",
    )
}
