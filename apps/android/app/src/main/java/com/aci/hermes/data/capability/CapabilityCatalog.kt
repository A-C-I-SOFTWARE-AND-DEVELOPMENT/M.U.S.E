package com.aci.hermes.data.capability

import com.aci.hermes.data.model.Capability
import com.aci.hermes.data.model.CapabilityCategory
import com.aci.hermes.data.model.CapabilityRoute
import com.aci.hermes.data.model.RouteSurface

/**
 * Curated catalog of MUSE capabilities surfaced on mobile.
 *
 * The full agent surface is hundreds of specialist agents, council
 * members, and worker lanes. Exposing all of them on a phone would
 * be hostile UX. This catalog is the small, opinionated subset
 * Jeremiah uses day-to-day. Less-common entries are marked
 * `isAdvanced = true` and only appear when the user opts in.
 *
 * Adding a capability here does not register a new agent — it only
 * decides what is visible in the mobile picker. The underlying lane
 * has to already exist on the gateway side.
 */
object CapabilityCatalog {

    val ALL: List<Capability> = listOf(

        // ---------------- Conversation ----------------
        Capability(
            id = "conv.companion",
            name = "Companion mode",
            category = CapabilityCategory.CONVERSATION,
            summary = "Human-like check-in, encouragement, honest support.",
            examplePrompt = "JARVIS, companion mode. I want to talk through something on my mind.",
            route = CapabilityRoute(
                surface = RouteSurface.CHAT,
                lane = "jarvis-prime: companion-mode",
                requiresGateway = true,
            ),
            tags = listOf("talk", "support", "feelings", "checkin"),
        ),
        Capability(
            id = "conv.strategy",
            name = "Strategy mode",
            category = CapabilityCategory.CONVERSATION,
            summary = "Product, career, business, pricing, roadmap reasoning.",
            examplePrompt = "JARVIS, strategy mode. Help me reason through this decision.",
            route = CapabilityRoute(
                surface = RouteSurface.CHAT,
                lane = "jarvis-prime: strategy-mode",
                requiresGateway = true,
            ),
            tags = listOf("plan", "business", "roadmap", "pricing"),
        ),

        // ---------------- Build ----------------
        Capability(
            id = "build.code-planner",
            name = "Builder packet",
            category = CapabilityCategory.BUILD,
            summary = "Plan a coding change into a clean Codex / Claude Code packet.",
            examplePrompt = "JARVIS, builder mode. Prepare a build packet for: <describe the change>.",
            route = CapabilityRoute(
                surface = RouteSurface.CHAT,
                lane = "jarvis-prime: builder-mode",
                requiresGateway = true,
                notes = "Returns a structured packet. No code is written without your dispatch.",
            ),
            tags = listOf("code", "build", "packet", "implementation"),
        ),
        Capability(
            id = "build.local-verify",
            name = "Local verification plan",
            category = CapabilityCategory.BUILD,
            summary = "Suggest the smallest verify-locally steps before merging.",
            examplePrompt = "JARVIS, generate a local verification plan for: <change>.",
            route = CapabilityRoute(
                surface = RouteSurface.CHAT,
                lane = "jarvis-prime: builder-mode#verify",
                requiresGateway = true,
            ),
            isAdvanced = true,
            tags = listOf("verify", "tests", "qa"),
        ),

        // ---------------- Review ----------------
        Capability(
            id = "review.critic",
            name = "Critic mode",
            category = CapabilityCategory.REVIEW,
            summary = "Contrarian review, blind-spot detection, hard truth.",
            examplePrompt = "JARVIS, critic mode. Pressure-test this: <plan or doc>.",
            route = CapabilityRoute(
                surface = RouteSurface.CHAT,
                lane = "jarvis-prime: critic-mode",
                requiresGateway = true,
            ),
            tags = listOf("review", "redteam", "critique"),
        ),
        Capability(
            id = "review.codex-review",
            name = "Code review packet",
            category = CapabilityCategory.REVIEW,
            summary = "Stage a Claude Code reviewer packet for a diff or PR.",
            examplePrompt = "JARVIS, prepare a code review packet for: <PR or diff>.",
            route = CapabilityRoute(
                surface = RouteSurface.CHAT,
                lane = "jarvis-prime: reviewer-mode",
                requiresGateway = true,
            ),
            tags = listOf("review", "diff", "pr", "audit"),
        ),

        // ---------------- Research ----------------
        Capability(
            id = "research.scoped",
            name = "Scoped research",
            category = CapabilityCategory.RESEARCH,
            summary = "Tight research brief with sources, scope, and time box.",
            examplePrompt = "JARVIS, scoped research: <topic>. Time box <minutes>m, depth <shallow|deep>.",
            route = CapabilityRoute(
                surface = RouteSurface.CHAT,
                lane = "jarvis-prime: strategy-mode#research",
                requiresGateway = true,
            ),
            tags = listOf("research", "summary", "sources"),
        ),
        Capability(
            id = "research.evidence",
            name = "Evidence bundle",
            category = CapabilityCategory.RESEARCH,
            summary = "AOS-style evidence bundle before a major decision.",
            examplePrompt = "JARVIS, build an evidence bundle for: <decision>.",
            route = CapabilityRoute(
                surface = RouteSurface.CHAT,
                lane = "aos-council: evidence-architect",
                requiresGateway = true,
            ),
            isAdvanced = true,
            tags = listOf("aos", "evidence", "decision"),
        ),

        // ---------------- Memory ----------------
        Capability(
            id = "memory.recall",
            name = "Recall context",
            category = CapabilityCategory.MEMORY,
            summary = "Pull what you've told JARVIS about a topic or project.",
            examplePrompt = "JARVIS, recall what we know about: <topic>.",
            route = CapabilityRoute(
                surface = RouteSurface.CHAT,
                lane = "jarvis-prime: memory#recall",
                requiresGateway = true,
                notes = "Read-only. No memory is written without an explicit save action.",
            ),
            tags = listOf("memory", "recall", "history"),
        ),
        Capability(
            id = "memory.save",
            name = "Save note to memory",
            category = CapabilityCategory.MEMORY,
            summary = "Persist a fact, preference, or goal to long-term memory.",
            examplePrompt = "JARVIS, save this to memory: <fact>. Scope: <project|personal>.",
            route = CapabilityRoute(
                surface = RouteSurface.CHAT,
                lane = "jarvis-prime: memory#write",
                requiresGateway = true,
                requiresOwnerAuth = true,
                notes = "Owner-gated. JARVIS will confirm the write before persisting.",
            ),
            ownerGated = true,
            tags = listOf("memory", "save", "remember"),
        ),

        // ---------------- Mobile ----------------
        Capability(
            id = "mobile.voice-capture",
            name = "Mobile voice capture",
            category = CapabilityCategory.MOBILE,
            summary = "Short capture mode for jogging / walking / commute.",
            examplePrompt = "JARVIS, voice capture mode. Hold this thought: <idea>.",
            route = CapabilityRoute(
                surface = RouteSurface.CHAT,
                lane = "jarvis-prime: mobile-voice-mode",
                requiresGateway = true,
                notes = "Short replies suited to mobile. Expand later in focused mode.",
            ),
            tags = listOf("mobile", "voice", "quick"),
        ),

        // ---------------- Safety ----------------
        Capability(
            id = "safety.risk-check",
            name = "Risk check",
            category = CapabilityCategory.SAFETY,
            summary = "Pre-flight risk surface before a risky action lands.",
            examplePrompt = "JARVIS, risk check this action: <action>.",
            route = CapabilityRoute(
                surface = RouteSurface.CHAT,
                lane = "aos-council: assurance-risk-director",
                requiresGateway = true,
            ),
            tags = listOf("safety", "risk", "preflight"),
        ),
        Capability(
            id = "safety.owner-gate",
            name = "Owner-gated dispatch",
            category = CapabilityCategory.SAFETY,
            summary = "Authorize a previously-blocked owner-gated action.",
            examplePrompt = "Yes, with authorization. Proceed with: <action>.",
            route = CapabilityRoute(
                surface = RouteSurface.CHAT,
                lane = "jarvis-prime: owner-gate",
                requiresGateway = true,
                requiresOwnerAuth = true,
                notes = "Only used to release a pending owner-gated request.",
            ),
            ownerGated = true,
            tags = listOf("safety", "gate", "authorize"),
        ),

        // ---------------- AOS Council ----------------
        Capability(
            id = "aos.council-director",
            name = "AOS Council director",
            category = CapabilityCategory.AOS_COUNCIL,
            summary = "Run the AOS planning + review sequence for a big decision.",
            examplePrompt = "JARVIS, route this to the AOS Council: <mission>.",
            route = CapabilityRoute(
                surface = RouteSurface.CHAT,
                lane = "aos-council: aos-council-director",
                requiresGateway = true,
                notes = "Director assembles the bench. Specialists do not run unsupervised.",
            ),
            tags = listOf("aos", "council", "planning", "decision"),
        ),
        Capability(
            id = "aos.contrarian",
            name = "Contrarian reviewer",
            category = CapabilityCategory.AOS_COUNCIL,
            summary = "AOS-style contrarian review of a synthesized plan.",
            examplePrompt = "JARVIS, run contrarian review on this plan: <plan>.",
            route = CapabilityRoute(
                surface = RouteSurface.CHAT,
                lane = "aos-council: contrarian-reviewer",
                requiresGateway = true,
            ),
            isAdvanced = true,
            tags = listOf("aos", "contrarian", "review"),
        ),

        // ---------------- Worker Lane ----------------
        Capability(
            id = "worker.dispatch",
            name = "Dispatch to worker lane",
            category = CapabilityCategory.WORKER_LANE,
            summary = "Hand a narrowly-scoped task to a worker (Codex/Claude Code).",
            examplePrompt = "JARVIS, dispatch this to a worker lane with acceptance criteria: <task>.",
            route = CapabilityRoute(
                surface = RouteSurface.CHAT,
                lane = "aos-council: codex-dispatch-governor",
                requiresGateway = true,
                requiresOwnerAuth = true,
                notes = "Owner-gated. Worker will not act without your authorization message.",
            ),
            ownerGated = true,
            tags = listOf("worker", "dispatch", "codex", "claude-code"),
        ),
        Capability(
            id = "worker.status",
            name = "Worker lane status",
            category = CapabilityCategory.WORKER_LANE,
            summary = "Read-only status of in-flight worker handoffs.",
            examplePrompt = "JARVIS, status of the worker lane.",
            route = CapabilityRoute(
                surface = RouteSurface.CHAT,
                lane = "jarvis-prime: operator-mode#worker-status",
                requiresGateway = true,
            ),
            tags = listOf("worker", "status", "operator"),
        ),

        // ---------------- Social Intelligence ----------------
        Capability(
            id = "social.message-draft",
            name = "Message draft",
            category = CapabilityCategory.SOCIAL_INTELLIGENCE,
            summary = "Draft a Slack / email / DM with tone calibrated to context.",
            examplePrompt = "JARVIS, draft a message to <person> about <topic>. Tone: <plain|warm|firm>.",
            route = CapabilityRoute(
                surface = RouteSurface.CHAT,
                lane = "jarvis-prime: social-intelligence#draft",
                requiresGateway = true,
                notes = "Returns a draft for you to send. JARVIS never sends on your behalf.",
            ),
            tags = listOf("slack", "email", "draft", "tone"),
        ),
        Capability(
            id = "social.read",
            name = "Read a thread",
            category = CapabilityCategory.SOCIAL_INTELLIGENCE,
            summary = "Summarize a Slack/email thread and surface the asks.",
            examplePrompt = "JARVIS, read this thread and surface the asks: <thread or link>.",
            route = CapabilityRoute(
                surface = RouteSurface.CHAT,
                lane = "jarvis-prime: social-intelligence#read",
                requiresGateway = true,
            ),
            tags = listOf("slack", "email", "summary"),
        ),

        // ---------------- Create (unrestricted media) ----------------
        // Surfaced for the personal-tool fork: no owner gate. These map
        // to the image_gen / video_gen plugins (fal / openai / xai).
        Capability(
            id = "create.image",
            name = "Generate an image",
            category = CapabilityCategory.BUILD,
            summary = "Create an image from a prompt (FLUX 2, GPT Image, Grok, Recraft).",
            examplePrompt = "JARVIS, make an image of: <describe the image>.",
            route = CapabilityRoute(
                surface = RouteSurface.CHAT,
                lane = "image_gen",
                requiresGateway = true,
                notes = "Routes to the configured image provider (fal / openai / xai).",
            ),
            tags = listOf("image", "art", "picture", "flux", "create", "media"),
        ),
        Capability(
            id = "create.video",
            name = "Generate a video",
            category = CapabilityCategory.BUILD,
            summary = "Create a short video from a prompt (Veo 3, Kling, Wan, Grok).",
            examplePrompt = "JARVIS, make a video of: <describe the shot>.",
            route = CapabilityRoute(
                surface = RouteSurface.CHAT,
                lane = "video_gen",
                requiresGateway = true,
                notes = "Routes to the configured video provider (fal / xai).",
            ),
            tags = listOf("video", "clip", "veo", "kling", "create", "media"),
        ),
        Capability(
            id = "create.avatar",
            name = "Make me into Jarvis",
            category = CapabilityCategory.MOBILE,
            summary = "Turn an uploaded photo into your animated avatar (2D pixel, Rive, or 3D).",
            examplePrompt = "JARVIS, turn this photo into my avatar in the navy-gold style.",
            route = CapabilityRoute(
                surface = RouteSurface.CHAT,
                lane = "image_gen: avatar-convert",
                requiresGateway = true,
                notes = "2D pixel runs on-device; stylized/3D reuse the image-gen path.",
            ),
            tags = listOf("avatar", "photo", "convert", "3d", "pixel", "character"),
        ),

        // ---------------- On-screen presence (device control) ----------------
        Capability(
            id = "presence.live",
            name = "Live on my screen",
            category = CapabilityCategory.MOBILE,
            summary = "Let Jarvis float over your apps and operate the phone for you.",
            examplePrompt = "JARVIS, come live on my screen.",
            route = CapabilityRoute(
                surface = RouteSurface.LOCAL_HANDOFF,
                lane = "overlay: presence",
                requiresGateway = false,
                notes = "Starts the floating avatar (needs overlay + accessibility permissions).",
            ),
            tags = listOf("overlay", "avatar", "presence", "screen", "float"),
        ),
        Capability(
            id = "presence.operate",
            name = "Open / drive an app",
            category = CapabilityCategory.MOBILE,
            summary = "Run to an app, push it open, scroll, or turn the home-screen page.",
            examplePrompt = "JARVIS, open Facebook.",
            route = CapabilityRoute(
                surface = RouteSurface.LOCAL_HANDOFF,
                lane = "overlay: automation",
                requiresGateway = false,
                notes = "Performed by the accessibility service as a real gesture.",
            ),
            tags = listOf("open", "tap", "swipe", "page", "automation", "control"),
        ),
        Capability(
            id = "presence.voice",
            name = "Hands-free voice",
            category = CapabilityCategory.MOBILE,
            summary = "Talk to Muse through your headset — say \"Hey Muse\" for any command.",
            examplePrompt = "MUSE, start voice mode.",
            route = CapabilityRoute(
                surface = RouteSurface.LOCAL_HANDOFF,
                lane = "voice: loop",
                requiresGateway = false,
                notes = "Wake word + streaming STT + TTS over Bluetooth SCO.",
            ),
            tags = listOf("voice", "talk", "headset", "wake word", "hands-free"),
        ),
    )

    fun byId(id: String): Capability? = ALL.firstOrNull { it.id == id }

    fun byCategory(category: CapabilityCategory): List<Capability> =
        ALL.filter { it.category == category }
}
