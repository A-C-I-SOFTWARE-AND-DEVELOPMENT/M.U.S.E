package com.aci.hermes.voice

/**
 * Classifies a voice transcript into one of the three categories the
 * Phase-1 voice surface understands: safe text, an approval-required
 * action, or a cancellation. Intentionally rule-based and small —
 * any uncertainty escalates to APPROVAL_REQUIRED, never to direct
 * execution.
 *
 * Mirrors the safety semantics of [hermes_cli.voice_intake] on the
 * Python side: the wordlists below come from `voice_intake._PUBLISH_*`
 * and `voice_models` so a voice command means the same thing on the
 * phone and at the gateway.
 */
class VoiceIntentClassifier(
    private val seriousTriggers: Set<String> = DEFAULT_SERIOUS_TRIGGERS,
    private val cancelTriggers: Set<String> = DEFAULT_CANCEL_TRIGGERS,
    private val vagueMarkers: Set<String> = DEFAULT_VAGUE_MARKERS,
) {
    fun classify(rawTranscript: String): VoiceCommandClassification {
        val trimmed = rawTranscript.trim()
        if (trimmed.isEmpty()) {
            return VoiceCommandClassification(
                category = VoiceCommandCategory.SAFE_TEXT,
                reason = "empty transcript",
            )
        }

        val tokens = tokenize(trimmed)
        val lowered = trimmed.lowercase()

        // Cancellation is checked first so "never mind, delete the repo"
        // routes to cancel rather than to an approval task.
        cancelTriggers.firstOrNull { phrase ->
            lowered == phrase || lowered.startsWith("$phrase ") ||
                lowered.startsWith("$phrase,") || tokens.contains(phrase)
        }?.let { match ->
            return VoiceCommandClassification(
                category = VoiceCommandCategory.CANCEL,
                reason = "matched cancel phrase",
                matchedTrigger = match,
            )
        }

        seriousTriggers.firstOrNull { trigger ->
            tokens.contains(trigger) || lowered.contains(" $trigger ") ||
                lowered.startsWith("$trigger ") || lowered.endsWith(" $trigger") ||
                lowered == trigger
        }?.let { match ->
            return VoiceCommandClassification(
                category = VoiceCommandCategory.APPROVAL_REQUIRED,
                reason = "serious action verb detected",
                matchedTrigger = match,
            )
        }

        val vagueMatch = vagueMarkers.firstOrNull { marker -> lowered.contains(marker) }
        if (vagueMatch != null) {
            return VoiceCommandClassification(
                category = VoiceCommandCategory.APPROVAL_REQUIRED,
                reason = "ambiguous scope — needs review before action",
                matchedTrigger = vagueMatch,
            )
        }

        return VoiceCommandClassification(
            category = VoiceCommandCategory.SAFE_TEXT,
            reason = null,
        )
    }

    private fun tokenize(text: String): Set<String> =
        text.lowercase()
            .split(NON_WORD_REGEX)
            .filter { it.isNotEmpty() }
            .toSet()

    companion object {
        private val NON_WORD_REGEX = Regex("[^a-z0-9']+")

        /**
         * Action verbs that imply spend, deploy, publish, delete, or any
         * other change with real-world consequences. Always escalate to
         * approval — never executed directly from voice.
         */
        val DEFAULT_SERIOUS_TRIGGERS: Set<String> = setOf(
            "delete",
            "remove",
            "wipe",
            "destroy",
            "drop",
            "deploy",
            "publish",
            "ship",
            "release",
            "merge",
            "push",
            "force",
            "buy",
            "purchase",
            "spend",
            "pay",
            "send",
            "transfer",
            "withdraw",
            "rm",
            "shutdown",
            "shut",
            "reboot",
            "format",
            "uninstall",
            "revoke",
            "rotate",
        )

        val DEFAULT_CANCEL_TRIGGERS: Set<String> = setOf(
            "cancel",
            "abort",
            "never mind",
            "nevermind",
            "stop that",
            "forget it",
            "scratch that",
        )

        /**
         * Vague scoping that makes the request hazardous to act on even
         * if the verb itself is innocuous (e.g. "fix everything",
         * "do whatever you think is right").
         */
        val DEFAULT_VAGUE_MARKERS: Set<String> = setOf(
            "everything",
            "all of it",
            "whatever you think",
            "do whatever",
            "all my",
            "the whole thing",
            "anything you want",
        )
    }
}
