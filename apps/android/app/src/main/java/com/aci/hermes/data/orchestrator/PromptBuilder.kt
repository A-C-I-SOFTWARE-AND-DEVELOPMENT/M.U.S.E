package com.aci.hermes.data.orchestrator

import com.aci.hermes.data.model.AiToolProfile
import com.aci.hermes.data.model.HermesTask
import com.aci.hermes.data.model.TargetTool
import com.aci.hermes.data.model.TaskType

/**
 * Builds the structured handoff prompt the user copies into Codex /
 * Claude Code / ChatGPT / Claude. Pure Kotlin — no side effects.
 *
 * The Safety section is invariant across targets so the user can hand
 * off without worrying about whether they removed it for one provider.
 */
class PromptBuilder {

    fun build(task: HermesTask, profile: AiToolProfile?): String {
        val resolved = profile ?: AiToolProfile(
            id = "manual",
            displayName = "Manual",
            provider = "User",
            role = "Manual handoff (no target tool selected)",
            officialToolType = "User chooses where to take this",
            launchMethod = "manual",
            notes = "",
            targetTool = TargetTool.MANUAL,
        )
        val sb = StringBuilder()
        sb.appendSection("Role", roleLine(resolved))
        sb.appendSection("Goal", goalLine(task))
        sb.appendSection("Project context", projectContext(task))
        sb.appendSection("Files or workspace notes", workspaceNotes(task))
        sb.appendSection("Constraints", constraints(task, resolved))
        sb.appendSection("Safety requirements", SAFETY_BLOCK)
        sb.appendSection("Desired output", desiredOutput(resolved))
        sb.appendSection("Acceptance criteria", acceptanceCriteria(task, resolved))
        sb.appendSection("Build / test instructions", buildTestInstructions(task, resolved))
        sb.appendSection("Return format", returnFormat(resolved))
        return sb.toString().trimEnd() + "\n"
    }

    private fun roleLine(profile: AiToolProfile): String = when (profile.targetTool) {
        TargetTool.CODEX ->
            "You are acting as the Builder — Codex / OpenAI. Implement changes in the source tree, run the project's tests, iterate until they pass."
        TargetTool.CHATGPT ->
            "You are acting as the Planner — ChatGPT. Strategic planning, prompt refinement, requirements clarification, product / architecture thinking."
        TargetTool.CLAUDE_CODE ->
            "You are acting as the Reviewer — Claude Code. Audit architecture, find bugs, review the implementation, suggest a safer structure. Produce review notes and patch recommendations rather than overwriting Builder changes blindly."
        TargetTool.CLAUDE ->
            "You are acting as the Architect / Auditor — Claude. Reasoning, architecture, risk analysis, complex debugging, and code review."
        TargetTool.MANUAL ->
            "Manual handoff — no specific tool selected. ${profile.role}"
    }

    private fun goalLine(task: HermesTask): String {
        val title = task.title.takeIf { it.isNotBlank() } ?: "(untitled task)"
        return buildString {
            append(taskTypeVerb(task.taskType))
            append(": ")
            append(title)
        }
    }

    private fun projectContext(task: HermesTask): String {
        val parts = mutableListOf<String>()
        task.workspacePath?.takeIf { it.isNotBlank() }?.let { parts += "Workspace path: $it" }
        parts += "Task type: ${task.taskType.name.lowercase()}"
        parts += "Current status: ${task.status.name.lowercase()}"
        return parts.joinToString("\n")
    }

    private fun workspaceNotes(task: HermesTask): String {
        val description = task.description.trim().ifBlank { "(no description provided)" }
        val notes = listOfNotNull(
            "Description:\n$description",
            task.reviewNotes?.takeIf { it.isNotBlank() }?.let { "Prior review notes:\n$it" },
            task.resultNotes?.takeIf { it.isNotBlank() }?.let { "Prior result notes:\n$it" },
        )
        return notes.joinToString("\n\n")
    }

    private fun constraints(task: HermesTask, profile: AiToolProfile): String {
        val lines = mutableListOf(
            "Stay scoped to the goal — no incidental refactors.",
            "Do not introduce new external services or dependencies without flagging them clearly.",
            "Preserve existing public APIs unless the goal explicitly requires changing them.",
        )
        if (profile.targetTool == TargetTool.CODEX) {
            lines += "Modify source code in place and keep the diff minimal."
            lines += "Run the project's build / tests after each meaningful change."
        }
        if (profile.targetTool == TargetTool.CLAUDE_CODE) {
            lines += "Do not overwrite Builder changes blindly — describe the change you would make, then patch."
        }
        task.nextAction?.takeIf { it.isNotBlank() }?.let {
            lines += "User-supplied next action: $it"
        }
        return lines.joinToString("\n") { "- $it" }
    }

    private fun desiredOutput(profile: AiToolProfile): String = when (profile.targetTool) {
        TargetTool.CODEX ->
            """
            - Source-file edits applied to the workspace.
            - A summary of files changed and why.
            - Test / build output showing the change is green.
            """.trimIndent()
        TargetTool.CHATGPT ->
            """
            - A short plan (numbered steps, 3–8 items).
            - Open questions you would want answered before execution.
            - A refined version of the prompt that would be safe to hand to Codex / Claude Code.
            """.trimIndent()
        TargetTool.CLAUDE_CODE ->
            """
            - Review notes covering correctness, architecture, and risk.
            - Suggested patches with file paths and rationale.
            - Explicit callouts for anything the Builder should redo.
            """.trimIndent()
        TargetTool.CLAUDE ->
            """
            - Reasoning summary covering the architecture and risk surface.
            - Specific bug / regression hypotheses ranked by likelihood.
            - Suggested code-level fixes where applicable.
            """.trimIndent()
        TargetTool.MANUAL ->
            "Whatever the user has asked for in the goal section above."
    }

    private fun acceptanceCriteria(task: HermesTask, profile: AiToolProfile): String {
        val lines = mutableListOf(
            "The goal stated above is met.",
            "No new failing tests; no new compiler warnings introduced.",
            "Any safety or terms-of-service concerns are flagged explicitly rather than silently worked around.",
        )
        if (profile.targetTool == TargetTool.CODEX) {
            lines += "`./gradlew assembleDebug` (or the project's equivalent) completes successfully."
        }
        if (task.taskType == TaskType.REVIEW || task.taskType == TaskType.AUDIT) {
            lines += "Each finding is reproducible and references a specific file / line."
        }
        return lines.joinToString("\n") { "- $it" }
    }

    private fun buildTestInstructions(task: HermesTask, profile: AiToolProfile): String {
        return when (profile.targetTool) {
            TargetTool.CODEX -> buildString {
                appendLine("- Run the project's standard build and tests before claiming completion.")
                appendLine("- Re-run them after each meaningful edit until they pass.")
                task.workspacePath?.takeIf { it.isNotBlank() }?.let {
                    appendLine("- Run from: $it")
                }
            }.trimEnd()
            TargetTool.CLAUDE_CODE ->
                "- Do not run tests destructively. If you propose a patch, describe how to verify it."
            else ->
                "- N/A — this handoff does not include build / test execution."
        }
    }

    private fun returnFormat(profile: AiToolProfile): String = when (profile.targetTool) {
        TargetTool.CODEX ->
            "Final message: a short summary, the list of files changed, and the build / test output. Edits applied in-place."
        TargetTool.CHATGPT ->
            "Markdown: numbered plan, open questions, refined prompt."
        TargetTool.CLAUDE_CODE ->
            "Markdown: review notes, then a Suggested Patches section with file paths and code blocks."
        TargetTool.CLAUDE ->
            "Markdown: reasoning summary, ranked findings, suggested fixes."
        TargetTool.MANUAL ->
            "Whatever format suits the goal."
    }

    private fun taskTypeVerb(type: TaskType): String = when (type) {
        TaskType.BUILD -> "Build"
        TaskType.REVIEW -> "Review"
        TaskType.AUDIT -> "Audit"
        TaskType.DEBUG -> "Debug"
        TaskType.REFACTOR -> "Refactor"
        TaskType.RESEARCH -> "Research"
        TaskType.PLANNING -> "Plan"
    }

    private fun StringBuilder.appendSection(label: String, body: String) {
        append("## ")
        append(label)
        append("\n")
        append(body.trim())
        append("\n\n")
    }

    companion object {
        const val SAFETY_BLOCK = """- Do not bypass authentication on any provider.
- Do not exfiltrate, copy, or transmit API keys, session tokens, or cookies.
- Stay within the official tool's terms of service.
- Treat API keys and tokens as out of scope for this task.
- If the goal would require violating any of the above, stop and report the conflict instead."""
    }
}
