package com.aci.hermes.data.jarvis

/**
 * One incremental update emitted by a [JarvisChatGateway] while a reply
 * is being produced. Modelled as a Kotlin sealed interface so the view
 * model can pattern-match without parsing any wire format itself.
 *
 * Gateways that don't support real streaming (e.g. a synchronous HTTP
 * call) still emit a single Body + Done pair so the renderer code path
 * stays identical.
 */
sealed interface JarvisChatChunk {

    /** Initial "..." before a working label is known. */
    data object Thinking : JarvisChatChunk

    /** Named long-running step. Replaces any prior working label. */
    data class Working(val label: String) : JarvisChatChunk

    /** Tone hint for the in-progress reply. Last value wins. */
    data class Tone(val tone: JarvisTone) : JarvisChatChunk

    /** Streamed body token — appended to the short mobile reply. */
    data class Body(val text: String) : JarvisChatChunk

    /** Streamed detail token — appended to the expandable detail. */
    data class Detail(val text: String) : JarvisChatChunk

    /** Structured card attached to the in-progress reply. */
    data class Inline(val card: JarvisInlineCard) : JarvisChatChunk

    /**
     * Reply finished cleanly. The view model uses this to drop any
     * thinking/working indicator and stop the abort timer.
     */
    data object Done : JarvisChatChunk

    /**
     * Gateway-level failure. The view model converts this to a
     * [JarvisChatMessage.Error] with a retry affordance.
     */
    data class Failure(val message: String, val retryHint: String? = null) : JarvisChatChunk
}
