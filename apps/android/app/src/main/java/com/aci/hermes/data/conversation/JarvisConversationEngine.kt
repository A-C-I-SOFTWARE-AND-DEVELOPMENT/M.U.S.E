package com.aci.hermes.data.conversation

import com.aci.hermes.data.model.ChatMessage
import com.aci.hermes.data.model.ChatRole
import com.aci.hermes.data.model.ChatSuggestion
import com.aci.hermes.data.model.SuggestionKind

/**
 * Local conversational reply engine for Jarvis Prime in mock mode.
 *
 * The phone never calls a model — the runtime that does that lives in
 * `hermes_cli/jarvis_prime/` on whatever host (Termux, gateway, etc.)
 * the user wires up. Here we provide a small intent-classified reply
 * tree that matches the persona surfaced in the runtime: direct,
 * plain, owner-gated, never sycophantic.
 *
 * The engine is intentionally rule-based so behaviour is predictable
 * during onboarding and demos, and so we have something the
 * unit tests can pin to.
 */
class JarvisConversationEngine {

    /** Produce the assistant's reply to [userText]. */
    fun reply(userText: String): ChatMessage {
        val lower = userText.lowercase().trim()
        val (body, suggestion) = classifyAndAnswer(lower)
        return ChatMessage(role = ChatRole.JARVIS, body = body, suggestion = suggestion)
    }

    private fun classifyAndAnswer(text: String): Pair<String, ChatSuggestion?> {
        if (text.isBlank()) {
            return "Tell me what you need. I will plan, draft, or ask for approval before I act." to null
        }
        return when {
            text.matchesAny(GREETING_KEYWORDS) ->
                "Hello. I am ready when you are." to null

            text.matchesAny(HELP_KEYWORDS) ->
                ("I can plan tasks, draft prompts for Codex/Claude, ask for approvals on serious actions, " +
                    "and keep a visible record of everything I touch. Try voice, or ask me to make a task.") to
                    ChatSuggestion("Start voice", SuggestionKind.START_VOICE)

            text.matchesAny(APPROVAL_KEYWORDS) ->
                "Approvals queue is in the Approvals tab — routine items log themselves, risky asks confirm once, " +
                    "serious asks confirm twice, and critical asks need a typed authorization phrase." to
                    ChatSuggestion("Open approvals", SuggestionKind.OPEN_APPROVALS)

            text.matchesAny(MEMORY_KEYWORDS) ->
                "Memory is open in the Memory tab. Inferences are clearly marked. You can confirm, reject, or forget." to
                    ChatSuggestion("Open memory", SuggestionKind.OPEN_MEMORY)

            text.matchesAny(AUDIT_KEYWORDS) ->
                "Every action and approval is in the Audit tab with a short proof ID." to
                    ChatSuggestion("Open audit", SuggestionKind.OPEN_AUDIT)

            text.matchesAny(TASK_KEYWORDS) ->
                "I will spin a draft task. Tap to refine — I will ask before handoff." to
                    ChatSuggestion("New task", SuggestionKind.NEW_TASK)

            text.matchesAny(VOICE_KEYWORDS) ->
                "Voice is one-shot. The mic only opens when you tap capture — no always-listening." to
                    ChatSuggestion("Start voice", SuggestionKind.START_VOICE)

            text.matchesAny(STOP_KEYWORDS) ->
                ("Engaging the emergency stop pauses every running worker, cancels every pending approval, " +
                    "and disconnects the gateway. Reach for it from any screen.") to null

            text.matchesAny(RISKY_KEYWORDS) ->
                ("Critical actions need an impact report, a rollback plan, and the typed authorization phrase " +
                    "\"Yes, with authorization.\" before I touch anything.") to
                    ChatSuggestion("Open approvals", SuggestionKind.OPEN_APPROVALS)

            text.matchesAny(THANK_KEYWORDS) ->
                "Acknowledged. Standing by." to null

            else ->
                ("Got it. I will work on \"${capitalize(text)}\" and surface the next steps as a task. " +
                    "If anything risky comes up I will ask first.") to
                    ChatSuggestion("New task", SuggestionKind.NEW_TASK)
        }
    }

    private fun String.matchesAny(words: List<String>): Boolean = words.any { contains(it) }

    private fun capitalize(text: String): String =
        if (text.isEmpty()) text else text[0].uppercaseChar() + text.substring(1)

    companion object {
        private val GREETING_KEYWORDS = listOf("hello", "hi", "hey", "good morning", "good evening", "good afternoon")
        private val HELP_KEYWORDS = listOf("help", "what can you do", "capabilities", "skills")
        private val APPROVAL_KEYWORDS = listOf("approve", "approval", "permission", "consent")
        private val MEMORY_KEYWORDS = listOf("remember", "memory", "recall", "forget")
        private val AUDIT_KEYWORDS = listOf("audit", "history", "proof", "log")
        private val TASK_KEYWORDS = listOf("task", "todo", "plan", "draft")
        private val VOICE_KEYWORDS = listOf("voice", "mic", "speak", "listen")
        private val STOP_KEYWORDS = listOf("emergency", "stop", "halt", "pause")
        private val RISKY_KEYWORDS = listOf("deploy", "delete", "push", "release", "production")
        private val THANK_KEYWORDS = listOf("thank", "thanks", "appreciate")
    }
}
