package com.aci.hermes.data.model

/**
 * Local workflow roles Hermes uses to organize handoff. These are
 * labels in the UI, not autonomous agents — Hermes never executes
 * actions on the user's behalf.
 */
enum class HermesRole(val displayName: String, val description: String) {
    ORCHESTRATOR(
        displayName = "Orchestrator",
        description = "Owns task state, splits work, chooses the target tool, tracks results."
    ),
    BUILDER(
        displayName = "Builder",
        description = "Codex / OpenAI. Implements code changes."
    ),
    REVIEWER(
        displayName = "Reviewer",
        description = "Claude Code / Claude. Reviews code and architecture."
    ),
    PLANNER(
        displayName = "Planner",
        description = "ChatGPT / Claude. Creates plans and prompts."
    ),
    AUDITOR(
        displayName = "Auditor",
        description = "Claude / ChatGPT. Checks risks, missing steps, acceptance criteria."
    ),
}
