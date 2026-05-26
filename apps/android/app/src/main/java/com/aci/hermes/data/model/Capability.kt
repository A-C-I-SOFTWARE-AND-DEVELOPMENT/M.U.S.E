package com.aci.hermes.data.model

/**
 * One curated JARVIS Prime capability surfaced in the mobile UI.
 *
 * JARVIS Prime is one visible assistant. The full agent surface
 * (200+ specialist agents, AOS council members, worker lanes) is
 * never exposed as a flat list. The UI presents a small curated set,
 * with everything else hidden behind an explicit "Advanced" toggle.
 *
 * Invocation is never direct from the UI — selecting a capability
 * stages a prompt that the owner reviews and dispatches through the
 * chat / gateway surface. The Android app never executes a tool on
 * its own.
 */
data class Capability(
    /** Stable id, used for search keying, persistence, and analytics. */
    val id: String,
    /** Display name shown on the SkillCard. */
    val name: String,
    /** One of ten curated categories. */
    val category: CapabilityCategory,
    /** One-line summary that fits a phone-width card. */
    val summary: String,
    /**
     * Pre-built example prompt the user can review, edit, and dispatch.
     * This is the "safe invocation" payload — the UI never bypasses
     * the chat / gateway surface to call a tool directly.
     */
    val examplePrompt: String,
    /** Routing target — see [CapabilityRoute]. */
    val route: CapabilityRoute,
    /**
     * When true, the capability requires owner authorization before
     * the underlying lane will act. The SkillCard renders an explicit
     * warning chip and the invocation sheet repeats the gate.
     */
    val ownerGated: Boolean = false,
    /**
     * When true, the capability is hidden by default and only appears
     * once the user enables the "Advanced" toggle. Used for power
     * users who actively want the long tail.
     */
    val isAdvanced: Boolean = false,
    /** Free-form search tags (lower-cased at search time). */
    val tags: List<String> = emptyList(),
)

/**
 * The ten curated categories. Categories are deliberate — they map
 * the agent surface onto a small mental model the user can hold
 * without seeing the full 200+ swarm.
 */
enum class CapabilityCategory(val displayName: String) {
    CONVERSATION("Conversation"),
    BUILD("Build"),
    REVIEW("Review"),
    RESEARCH("Research"),
    MEMORY("Memory"),
    MOBILE("Mobile"),
    SAFETY("Safety"),
    AOS_COUNCIL("AOS Council"),
    WORKER_LANE("Worker Lane"),
    SOCIAL_INTELLIGENCE("Social Intelligence");

    companion object {
        fun fromIdOrNull(id: String?): CapabilityCategory? =
            if (id == null) null else values().firstOrNull { it.name == id }
    }
}

/**
 * Describes how an invocation would flow if the user dispatched the
 * capability. The UI renders this as a "route preview" so the user
 * never wonders where their words will land.
 */
data class CapabilityRoute(
    val surface: RouteSurface,
    /** Human-readable lane name, e.g. "jarvis-prime: critic-mode". */
    val lane: String,
    /** When true, a running gateway is required for the lane to act. */
    val requiresGateway: Boolean = true,
    /** When true, the lane will refuse to act without an owner OK. */
    val requiresOwnerAuth: Boolean = false,
    /** Optional clarifying note shown under the route line. */
    val notes: String? = null,
)

enum class RouteSurface(val displayName: String) {
    /** Routes through `/v1/chat` on the gateway as a normal message. */
    CHAT("Chat"),
    /** Routes through a non-chat gateway endpoint (e.g. cron, hooks). */
    GATEWAY("Gateway"),
    /** Stays local — staged as a task / clipboard handoff, no network. */
    LOCAL_HANDOFF("Local handoff"),
}
