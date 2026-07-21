package com.aci.hermes.data.model

/**
 * Snapshot of one official AI tool the user already subscribes to.
 * Hermes never proxies these tools — it organizes work for them and
 * hands off via clipboard, deep links, or manual flow. Auth, billing,
 * and rate limits remain entirely on the provider's side.
 */
data class AiToolProfile(
    val id: String,
    val displayName: String,
    val provider: String,
    val role: String,
    val officialToolType: String,
    val installedStatus: InstalledStatus = InstalledStatus.UNKNOWN,
    val authStatus: AuthStatus = AuthStatus.UNKNOWN,
    val launchMethod: String,
    val notes: String,
    /** Maps this profile back to the prompt-targeting enum. */
    val targetTool: TargetTool,
    /** Best-effort Android package candidates for deep-link launching. */
    val candidatePackages: List<String> = emptyList(),
    /** Web fallback if the package isn't installed and the user opts in. */
    val webFallbackUrl: String? = null,
)

enum class InstalledStatus { UNKNOWN, INSTALLED, NOT_INSTALLED }

/**
 * Hermes deliberately does not inspect auth state for any provider. The
 * orchestrator assumes the user is already logged into their official
 * tool when they choose to hand off.
 */
enum class AuthStatus { UNKNOWN, ASSUMED_OK }

object DefaultToolProfiles {
    val CODEX = AiToolProfile(
        id = "openai_codex",
        displayName = "OpenAI Codex",
        provider = "OpenAI",
        role = "Builder / code editor / implementation agent",
        officialToolType = "Codex CLI / Codex app / ChatGPT Codex",
        launchMethod = "official_tool_or_manual_handoff",
        notes = "Uses official ChatGPT/Codex login where available. No API key required by muse.",
        targetTool = TargetTool.CODEX,
        candidatePackages = listOf("com.openai.chatgpt"),
        webFallbackUrl = "https://chatgpt.com/codex",
    )

    val CHATGPT = AiToolProfile(
        id = "openai_chatgpt",
        displayName = "ChatGPT",
        provider = "OpenAI",
        role = "Reasoning / planning / prompt refinement",
        officialToolType = "ChatGPT app/web",
        launchMethod = "manual_handoff_or_deeplink_if_available",
        notes = "Uses existing ChatGPT subscription. muse does not call the OpenAI API.",
        targetTool = TargetTool.CHATGPT,
        candidatePackages = listOf("com.openai.chatgpt"),
        webFallbackUrl = "https://chatgpt.com/",
    )

    val CLAUDE_CODE = AiToolProfile(
        id = "anthropic_claude_code",
        displayName = "Claude Code",
        provider = "Anthropic",
        role = "Reviewer / architect / complex problem solver",
        officialToolType = "Claude Code official CLI / web workflow",
        launchMethod = "official_tool_or_manual_handoff",
        notes = "Uses official Claude Code workflow where allowed. muse does not proxy Claude subscriptions.",
        targetTool = TargetTool.CLAUDE_CODE,
        candidatePackages = listOf("com.anthropic.claude"),
        webFallbackUrl = "https://claude.com/claude-code",
    )

    val CLAUDE = AiToolProfile(
        id = "anthropic_claude",
        displayName = "Claude",
        provider = "Anthropic",
        role = "Review / reasoning / architecture",
        officialToolType = "Claude app/web",
        launchMethod = "manual_handoff_or_deeplink_if_available",
        notes = "Uses existing Claude subscription. muse does not call the Anthropic API.",
        targetTool = TargetTool.CLAUDE,
        candidatePackages = listOf("com.anthropic.claude"),
        webFallbackUrl = "https://claude.ai/",
    )

    val all: List<AiToolProfile> = listOf(CODEX, CHATGPT, CLAUDE_CODE, CLAUDE)

    fun byTargetTool(target: TargetTool): AiToolProfile? = when (target) {
        TargetTool.CODEX -> CODEX
        TargetTool.CHATGPT -> CHATGPT
        TargetTool.CLAUDE_CODE -> CLAUDE_CODE
        TargetTool.CLAUDE -> CLAUDE
        TargetTool.MANUAL -> null
    }
}
