package com.aci.hermes.data.jarvis

import com.aci.hermes.data.jarvis.JarvisIntentClassifier.Intent
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.FlowCollector
import kotlinx.coroutines.flow.flow

/**
 * Streaming mock implementation of [JarvisChatGateway]. Used until a
 * real gateway client lands, and kept around afterwards as the
 * default for offline / preview / test runs.
 *
 * Behaviour matches the Jarvis Prime conversation engine spec:
 *  - casual input → quick ack, no detail, no card
 *  - task-shaped input → short reply + inline Task card
 *  - architecture input → short reply + expandable detail
 *  - approval-worthy action → formal language + inline Approval card
 *  - security-adjacent input → Serious card, slows the conversation
 *  - destructive action → Critical card with typed-ack requirement
 *  - "/error ..." → emits [JarvisChatChunk.Failure] for the retry path
 *  - "/stall ..." → emits chunks slowly so stop/abort is testable
 *
 * Token cadence is tunable via [chunkDelayMs]; tests pass `0` so the
 * flow completes instantly.
 */
class MockJarvisChatGateway(
    private val chunkDelayMs: Long = DEFAULT_CHUNK_DELAY_MS,
) : JarvisChatGateway {

    override val displayName: String = "Jarvis Prime (mock)"
    override val supportsStreaming: Boolean = true

    override fun send(history: List<JarvisChatMessage>, prompt: String): Flow<JarvisChatChunk> = flow {
        emit(JarvisChatChunk.Thinking)
        emit(JarvisChatChunk.Phase(JarvisPhase.RECEIVING))
        emit(JarvisChatChunk.Phase(JarvisPhase.THINKING))

        val classification = JarvisIntentClassifier.classify(prompt)
        emit(JarvisChatChunk.Phase(JarvisPhase.ROUTING))

        when (classification.intent) {
            Intent.ERROR_TRIGGER -> {
                tinyDelay()
                emit(
                    JarvisChatChunk.Failure(
                        message = "Gateway refused the request (mock /error).",
                        retryHint = "Try again — the mock gateway only fails on the explicit /error prefix.",
                    ),
                )
                return@flow
            }

            Intent.ABORT_TRIGGER -> {
                emit(JarvisChatChunk.Working("Running long task (waiting on remote)"))
                streamWords(
                    "Thinking out loud while the long task runs.",
                    chunkDelayMs * 4,
                ) { emit(JarvisChatChunk.Body(it)) }
                streamWords(
                    " This is the part where you can cancel me.",
                    chunkDelayMs * 8,
                ) { emit(JarvisChatChunk.Body(it)) }
                emit(JarvisChatChunk.Done)
                return@flow
            }

            Intent.CRITICAL -> {
                emit(JarvisChatChunk.Working("Drafting destructive-change preflight"))
                tinyDelay()
                emit(JarvisChatChunk.Tone(JarvisTone.CRITICAL))
                streamBody("Hold. That's destructive. I won't run it without an explicit ack.")
                streamDetail(
                    "I can stage the operation, dry-run it against a snapshot, and " +
                        "produce a rollback plan, but the live action stays paused until " +
                        "you type the ack string.",
                )
                emit(
                    JarvisChatChunk.Inline(
                        JarvisInlineCard.Critical(
                            title = "Critical: destructive action",
                            summary = summarise(prompt),
                            requiredAck = "I understand this is irreversible",
                        ),
                    ),
                )
                emit(JarvisChatChunk.Done)
            }

            Intent.APPROVAL -> {
                emit(JarvisChatChunk.Working("Preparing approval card"))
                emit(JarvisChatChunk.Tone(JarvisTone.SERIOUS))
                streamBody("Requesting your approval before I move forward.")
                streamDetail(
                    "I've staged the change locally. Once you approve I'll execute " +
                        "and follow up with a confirmation. If you hold, nothing leaves " +
                        "this device.",
                )
                emit(
                    JarvisChatChunk.Inline(
                        JarvisInlineCard.Approval(
                            title = "Approval requested",
                            summary = summarise(prompt),
                            impact = "Visible to others / hard to reverse",
                        ),
                    ),
                )
                emit(JarvisChatChunk.Done)
            }

            Intent.SERIOUS -> {
                emit(JarvisChatChunk.Tone(JarvisTone.SERIOUS))
                streamBody("Flagging this as serious. Slowing down a beat.")
                streamDetail(
                    "Security and privacy work changes the failure mode of every later " +
                        "step. I'll write out what I'd touch first and wait for you to " +
                        "confirm scope before drafting code.",
                )
                emit(
                    JarvisChatChunk.Inline(
                        JarvisInlineCard.Serious(
                            title = "Serious concern flagged",
                            summary = summarise(prompt),
                        ),
                    ),
                )
                emit(JarvisChatChunk.Done)
            }

            Intent.ARCHITECTURE -> {
                emit(JarvisChatChunk.Working("Sketching architecture"))
                streamBody("Short answer first — full sketch in the detail.")
                streamDetail(
                    "I'd split this into three layers: a stable data contract, a thin " +
                        "orchestration layer that owns transitions, and a UI that only " +
                        "reads state. The contract is the part you'll regret skimping " +
                        "on, so I'd lock that down before any UI work.",
                )
                emit(JarvisChatChunk.Done)
            }

            Intent.TASK -> {
                emit(JarvisChatChunk.Working("Drafting task card"))
                // Simulate the read-only inline tool activity the real
                // gateway streams for a code turn (compact + expandable +
                // pre-redacted), so the cockpit tool rail is demoable offline.
                emit(JarvisChatChunk.Phase(JarvisPhase.TOOL))
                emit(JarvisChatChunk.ToolCall("mock-1", "git_status", "checking working tree", JarvisToolStatus.START))
                emit(JarvisChatChunk.ToolCall("mock-1", "git_status", "main — clean", JarvisToolStatus.OK, detail = "working tree clean"))
                emit(JarvisChatChunk.ToolCall("mock-2", "repo_grep", "searching the repo", JarvisToolStatus.START))
                emit(
                    JarvisChatChunk.ToolCall(
                        "mock-2", "repo_grep", "\"${searchTerm(prompt)}\" → 3 file(s)", JarvisToolStatus.OK,
                        detail = "run_agent.py\nmodel_tools.py\ntoolsets.py",
                    ),
                )
                streamBody("Got it. Drafting a task card you can promote.")
                streamDetail(
                    "I'll target ${JarvisIntentClassifier.inferTargetTool(prompt).name.lowercase()} " +
                        "by default — flip it on the card if that's wrong.",
                )
                emit(
                    JarvisChatChunk.Inline(
                        JarvisInlineCard.Task(
                            title = deriveTaskTitle(prompt),
                            summary = summarise(prompt),
                            targetTool = JarvisIntentClassifier.inferTargetTool(prompt),
                            taskType = JarvisIntentClassifier.inferTaskType(prompt),
                        ),
                    ),
                )
                emit(JarvisChatChunk.Phase(JarvisPhase.VERIFICATION))
                emit(JarvisChatChunk.EvidenceRef("mock-audit-1", "Evidence & verification"))
                emit(JarvisChatChunk.LedgerRef("mock-audit-1", "Drafted task decision"))
                emit(JarvisChatChunk.Phase(JarvisPhase.FINAL))
                emit(JarvisChatChunk.Done)
            }

            Intent.CASUAL -> {
                streamBody(casualAck(prompt))
                emit(JarvisChatChunk.Done)
            }

            Intent.DEFAULT -> {
                streamBody("Here's the short version: ${shortAnswer(prompt)}")
                streamDetail(
                    "If you want the longer take, ask follow-up — I keep the deep " +
                        "version for when you actually need it on a small screen.",
                )
                emit(JarvisChatChunk.Done)
            }
        }
    }

    private suspend fun FlowCollector<JarvisChatChunk>.streamBody(text: String) {
        streamWords(text, chunkDelayMs) { emit(JarvisChatChunk.Body(it)) }
    }

    private suspend fun FlowCollector<JarvisChatChunk>.streamDetail(text: String) {
        streamWords(text, chunkDelayMs) { emit(JarvisChatChunk.Detail(it)) }
    }

    private suspend fun streamWords(text: String, delayMs: Long, emit: suspend (String) -> Unit) {
        // Stream by words to keep the cadence visible on a phone without
        // looking jittery character-by-character.
        val tokens = text.split(' ').filter { it.isNotEmpty() }
        for ((i, t) in tokens.withIndex()) {
            val piece = if (i == 0) t else " $t"
            emit(piece)
            if (delayMs > 0) delay(delayMs)
        }
    }

    private suspend fun tinyDelay() {
        if (chunkDelayMs > 0) delay(chunkDelayMs)
    }

    private fun summarise(prompt: String): String =
        prompt.trim().lineSequence().firstOrNull()?.take(140).orEmpty()
            .ifBlank { "(empty)" }

    private fun searchTerm(prompt: String): String =
        prompt.split(' ', '\n')
            .map { it.trim().trim('"', '\'', '`', '.', ',') }
            .firstOrNull { it.length in 4..40 && it.any(Char::isLetter) }
            ?: "repo"

    private fun deriveTaskTitle(prompt: String): String {
        val first = prompt.trim().lineSequence().firstOrNull().orEmpty()
        if (first.length <= 60) return first.ifBlank { "Untitled task" }
        return first.take(57).trimEnd() + "…"
    }

    private fun shortAnswer(prompt: String): String {
        val first = prompt.trim().lineSequence().firstOrNull().orEmpty()
        return if (first.endsWith("?")) "noted, I'd lean yes unless you tell me otherwise." else "got it."
    }

    private fun casualAck(prompt: String): String {
        val lower = prompt.lowercase().trim()
        return when {
            lower.startsWith("thanks") || lower.startsWith("thank you") || lower.startsWith("ty") ->
                "Anytime."
            lower.startsWith("good morning") -> "Morning. What's first?"
            lower.startsWith("good evening") -> "Evening. What's open?"
            else -> "Here. What do you need?"
        }
    }

    companion object {
        const val DEFAULT_CHUNK_DELAY_MS: Long = 30L
    }
}
