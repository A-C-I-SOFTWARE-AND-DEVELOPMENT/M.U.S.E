package com.aci.hermes.data.jarvis

/**
 * Tool-activity vocabulary shared by the chat chunks
 * ([JarvisChatChunk.Phase] / [JarvisChatChunk.ToolCall]) and the rendered
 * transcript ([JarvisChatMessage.Jarvis.phases] / `.toolCalls`).
 *
 * Kept 1:1 with the Python wire contract in
 * `gateway/jarvis_local_http.py` (`PHASES` / `TOOL_STATUSES`). Both ends
 * tolerate unknown values: the gateway upper-cases anything it doesn't
 * recognise, and [JarvisPhase.fromWire] / [JarvisToolStatus.fromWire] fall
 * back rather than crash, so a newer backend never breaks an older app.
 */
enum class JarvisPhase(val wire: String, val label: String) {
    RECEIVING("RECEIVING", "Receiving"),
    THINKING("THINKING", "Thinking"),
    ROUTING("ROUTING", "Routing"),
    TOOL("TOOL", "Tool use"),
    CODING("CODING", "Coding"),
    RESEARCH("RESEARCH", "Research"),
    VERIFICATION("VERIFICATION", "Verifying"),
    FINAL("FINAL", "Final answer");

    companion object {
        fun fromWire(value: String?): JarvisPhase? =
            entries.firstOrNull { it.wire.equals(value, ignoreCase = true) }
    }
}

enum class JarvisToolStatus(val wire: String) {
    START("START"),
    OK("OK"),
    FAIL("FAIL");

    val isTerminal: Boolean get() = this != START

    companion object {
        fun fromWire(value: String?): JarvisToolStatus =
            entries.firstOrNull { it.wire.equals(value, ignoreCase = true) } ?: START
    }
}

/**
 * One tool invocation as rendered in the transcript. Distinct from the
 * streamed [JarvisChatChunk.ToolCall]: the chunk arrives twice (START then
 * a terminal status) and the view model folds both into a single, updating
 * [JarvisToolCall] keyed by [id]. [summary]/[detail] are gateway-redacted.
 */
data class JarvisToolCall(
    val id: String,
    val name: String,
    val summary: String,
    val status: JarvisToolStatus,
    val detail: String? = null,
)

/** A reference the user can tap to inspect evidence or the decision ledger. */
data class JarvisRecordRef(
    val id: String,
    val title: String,
    val kind: Kind,
) {
    enum class Kind { EVIDENCE, LEDGER }
}
