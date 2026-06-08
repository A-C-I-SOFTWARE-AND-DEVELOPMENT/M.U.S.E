package com.aci.hermes.ui.jarvis

/**
 * Pure, side-effect-free signals that drive the MUSE icon.
 *
 * One [IconStateInputs] snapshot resolves to exactly one [IconState]
 * via [IconStateMapper.map]. The mapper is the single source of truth
 * for how concurrent signals collapse — UI code must never branch on
 * raw flags itself.
 *
 * Naming follows the in-app surfaces:
 *  - `gateway*` reflects the local orchestrator service health
 *  - `voice*` / `speaking` reflects the voice-capture pipeline
 *  - `*Pending` flags come off the approval queue
 *  - `blocked` / `warning` come off the policy / preconditions checks
 *  - `recentCompletion` is a transient green-flash trigger
 */
data class IconStateInputs(
    /** True when the orchestrator service is running and reachable. */
    val gatewayOnline: Boolean = true,
    /** Voice capture session has the mic open. */
    val listening: Boolean = false,
    /** Model is reasoning, no audio in flight. */
    val thinking: Boolean = false,
    /** TTS / voice output is playing. */
    val speaking: Boolean = false,
    /** At least one background task is in-flight. */
    val working: Boolean = false,
    /** Non-destructive action waiting on user OK. */
    val pendingApproval: Boolean = false,
    /** Reversible-but-serious action waiting on user OK. */
    val seriousActionPending: Boolean = false,
    /** Destructive / hard-to-reverse action waiting on user OK. */
    val criticalActionPending: Boolean = false,
    /** Auth, policy, or precondition failure — agent cannot proceed. */
    val blocked: Boolean = false,
    /** Non-fatal issue the user should see. */
    val warning: Boolean = false,
    /** A task just finished — flash green briefly. */
    val recentCompletion: Boolean = false,
)

/**
 * Collapses [IconStateInputs] into a single visible [IconState].
 *
 * Resolution rules:
 *  1. If the orchestrator is offline, that overrides every other
 *     signal — we cannot honestly claim to be "thinking" or "working".
 *  2. Otherwise we pick the highest [priority] state whose flag is set.
 *  3. `IDLE` is the floor — returned when nothing else applies.
 *
 * The mapper is intentionally a pure function so the same logic drives
 * the in-app icon today and the floating-bubble overlay later.
 */
object IconStateMapper {

    fun map(inputs: IconStateInputs): IconState {
        if (!inputs.gatewayOnline) return IconState.OFFLINE

        val active = buildList {
            if (inputs.criticalActionPending) add(IconState.CRITICAL_ACTION_PENDING)
            if (inputs.seriousActionPending) add(IconState.SERIOUS_ACTION_PENDING)
            if (inputs.blocked) add(IconState.BLOCKED)
            if (inputs.warning) add(IconState.WARNING)
            if (inputs.pendingApproval) add(IconState.WAITING_FOR_APPROVAL)
            if (inputs.speaking) add(IconState.SPEAKING)
            if (inputs.listening) add(IconState.LISTENING)
            if (inputs.thinking) add(IconState.THINKING)
            if (inputs.working) add(IconState.WORKING)
            if (inputs.recentCompletion) add(IconState.COMPLETE)
        }

        return active.maxByOrNull { it.priority() } ?: IconState.IDLE
    }
}
