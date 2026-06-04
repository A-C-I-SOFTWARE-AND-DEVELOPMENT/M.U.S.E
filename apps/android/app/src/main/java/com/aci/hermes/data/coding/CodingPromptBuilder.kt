package com.aci.hermes.data.coding

import com.aci.hermes.data.cockpit.CodingPacket
import com.aci.hermes.data.orchestrator.PromptBuilder

/**
 * Renders a bounded [CodingPacket] into a ready-to-paste **Claude Code**
 * prompt for a desktop coding session. Pure Kotlin — no side effects, no
 * Android types — so it is unit-tested on the JVM.
 *
 * The packet is the source of truth (mission, risk, allowed/forbidden files,
 * acceptance, verification, rollback, owner gates). The invariant
 * [PromptBuilder.SAFETY_BLOCK] is appended verbatim so a copied prompt always
 * carries the same guardrails as the legacy handoff flow — the owner phrase
 * is never embedded, and execution stays the operator's explicit choice.
 */
object CodingPromptBuilder {

    fun build(prompt: String, packet: CodingPacket?): String {
        val sb = StringBuilder()
        section(sb, "Role", ROLE_LINE)
        section(sb, "Mission", (packet?.mission?.takeIf { it.isNotBlank() } ?: prompt).trim())

        if (packet != null) {
            val ctx = buildList {
                packet.intent.takeIf { it.isNotBlank() }?.let { add("Intent: $it") }
                packet.riskClass.takeIf { it.isNotBlank() }?.let { add("Risk class: $it") }
                packet.repoRoot.takeIf { it.isNotBlank() }?.let { add("Repo root: $it") }
                packet.branch.takeIf { it.isNotBlank() }?.let { add("Branch: $it") }
                packet.primaryWorker.takeIf { it.isNotBlank() }?.let { add("Suggested worker: $it") }
                packet.modelLaneHint.takeIf { it.isNotBlank() }?.let { add("Model lane: $it") }
            }
            if (ctx.isNotEmpty()) section(sb, "Context", ctx.joinToString("\n"))

            bulletSection(sb, "Allowed files", packet.allowedFiles)
            bulletSection(sb, "Do NOT touch", packet.forbiddenFiles)
            bulletSection(sb, "Acceptance criteria", packet.acceptanceCriteria)
            bulletSection(sb, "Verification plan", packet.verificationPlan)
            bulletSection(sb, "Rollback plan", packet.rollbackPlan)
            if (packet.ownerGates.isNotEmpty()) {
                section(
                    sb,
                    "Owner-gated actions",
                    "These require Jeremiah's explicit authorization before you perform them:\n" +
                        packet.ownerGates.joinToString("\n") { "- $it" } +
                        "\nIf the task needs one of these, stop and report it — do not proceed.",
                )
            }
        }

        section(sb, "Safety requirements", PromptBuilder.SAFETY_BLOCK)
        section(
            sb,
            "Return format",
            "Apply minimal in-place edits, run the verification plan, then report: " +
                "files changed, tests run + results, and anything that hit an owner gate.",
        )
        return sb.toString().trimEnd() + "\n"
    }

    private const val ROLE_LINE =
        "You are acting as the Builder/Reviewer in Claude Code. Implement the mission " +
            "below within the allowed files only, keep the diff minimal, and verify before " +
            "claiming completion."

    private fun section(sb: StringBuilder, label: String, body: String) {
        if (body.isBlank()) return
        sb.append("## ").append(label).append('\n')
        sb.append(body.trim()).append("\n\n")
    }

    private fun bulletSection(sb: StringBuilder, label: String, items: List<String>) {
        val clean = items.map { it.trim() }.filter { it.isNotEmpty() }
        if (clean.isEmpty()) return
        section(sb, label, clean.joinToString("\n") { "- $it" })
    }
}
