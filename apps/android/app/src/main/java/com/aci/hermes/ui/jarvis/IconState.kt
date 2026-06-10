package com.aci.hermes.ui.jarvis

/**
 * Visible presence and behavior modes for the MUSE in-app icon.
 *
 * The icon is rendered inside the app (no system overlay permission is
 * requested in this wave — the floating-bubble surface ships later
 * behind an education flow). Each state has:
 *   - a primary color/ring derived in [JarvisIconColors]
 *   - a static accessibility label exposed via [accessibilityLabel]
 *   - a priority used by [IconStateMapper] to resolve which signal wins
 */
enum class IconState {
    /** Default ambient state — assistant is reachable and not doing anything. */
    IDLE,

    /** Microphone is open and capturing speech. Cyan listening glow. */
    LISTENING,

    /** Reasoning over a request, no audio in or out. */
    THINKING,

    /** Producing audio output. */
    SPEAKING,

    /** Running a non-blocking task on the user's behalf. */
    WORKING,

    /** A non-destructive action is queued and needs explicit user OK. White core + violet ring. */
    WAITING_FOR_APPROVAL,

    /** A reversible-but-serious action is pending approval. Violet core + violet ring (heightened), stronger pulse. */
    SERIOUS_ACTION_PENDING,

    /** A destructive / hard-to-reverse action is pending approval. Red ring. */
    CRITICAL_ACTION_PENDING,

    /** The agent is paused because a precondition failed (auth, network, policy). */
    BLOCKED,

    /** Non-fatal issue the user should see. */
    WARNING,

    /** A task just finished successfully — transient green flash. */
    COMPLETE,

    /** Gateway / orchestrator service is unreachable. Dim, muted. */
    OFFLINE,
}

/**
 * Stable accessibility label for each [IconState]. Returned by
 * [IconState.accessibilityLabel] and surfaced via Compose
 * `Modifier.semantics { contentDescription = ... }`.
 *
 * Labels are short, user-readable phrases — TalkBack reads them
 * verbatim when the icon receives focus.
 */
fun IconState.accessibilityLabel(): String = when (this) {
    IconState.IDLE -> "Muse idle"
    IconState.LISTENING -> "Muse listening"
    IconState.THINKING -> "Muse thinking"
    IconState.SPEAKING -> "Muse speaking"
    IconState.WORKING -> "Muse working"
    IconState.WAITING_FOR_APPROVAL -> "Muse waiting for your approval"
    IconState.SERIOUS_ACTION_PENDING -> "Muse: serious action waiting for approval"
    IconState.CRITICAL_ACTION_PENDING -> "Muse: critical action waiting for approval"
    IconState.BLOCKED -> "Muse blocked"
    IconState.WARNING -> "Muse warning"
    IconState.COMPLETE -> "Muse complete"
    IconState.OFFLINE -> "Muse offline"
}

/**
 * Higher means "this signal wins". Used by [IconStateMapper] to
 * collapse multiple concurrent inputs (e.g. listening + warning) to a
 * single visible state.
 *
 * The ordering encodes the safety story: anything the user must act on
 * outranks anything the assistant is doing of its own accord.
 */
internal fun IconState.priority(): Int = when (this) {
    IconState.OFFLINE -> 100
    IconState.CRITICAL_ACTION_PENDING -> 90
    IconState.SERIOUS_ACTION_PENDING -> 80
    IconState.BLOCKED -> 70
    IconState.WARNING -> 60
    IconState.WAITING_FOR_APPROVAL -> 50
    IconState.SPEAKING -> 40
    IconState.LISTENING -> 30
    IconState.THINKING -> 20
    IconState.WORKING -> 10
    IconState.COMPLETE -> 5
    IconState.IDLE -> 0
}
