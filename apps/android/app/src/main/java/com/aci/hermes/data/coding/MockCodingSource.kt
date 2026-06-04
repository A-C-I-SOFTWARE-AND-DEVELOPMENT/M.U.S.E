package com.aci.hermes.data.coding

import com.aci.hermes.data.cockpit.CodingAuditResult
import com.aci.hermes.data.cockpit.CodingExecuteResult
import com.aci.hermes.data.cockpit.CodingPacket
import com.aci.hermes.data.cockpit.CockpitOrchestratorJob

/**
 * Deterministic demo data for **Mock mode** so a fresh sideload — no backend,
 * no network, no keys — still demonstrates the full coding flow end to end.
 *
 * Everything here is clearly marked demo (the produced [SavedCodingTask] sets
 * `demo = true`) and is never confused with live backend output. The packet
 * mirrors the real `coding/plan` shape so the Work Packet screen renders
 * identically whether the data is demo or live.
 */
object MockCodingSource {

    fun audit(prompt: String, repoRoot: String): CodingAuditResult =
        CodingAuditResult(
            intent = "implement",
            riskClass = "RC2",
            primaryWorker = "claude-code",
            reviewerWorker = "codex",
            modelLaneHint = "claude_code_worker",
            ownerGates = emptyList(),
            blocked = false,
            rationale = "Demo classification (Mock mode): scoped code change, no owner gate.",
            mission = prompt.trim().ifBlank { "Demo coding task" },
            ownerGateRequired = false,
        )

    fun packet(prompt: String, repoRoot: String): CodingPacket =
        CodingPacket(
            mission = prompt.trim().ifBlank { "Demo coding task" },
            intent = "implement",
            branch = "demo/standalone-local",
            riskClass = "RC2",
            repoRoot = repoRoot.ifBlank { "." },
            allowedFiles = listOf("src/main/**", "tests/**"),
            forbiddenFiles = listOf("**/.env", "**/secrets/**", "signing/**"),
            acceptanceCriteria = listOf(
                "The requested change compiles.",
                "Existing tests still pass; new behavior is covered.",
                "No secrets or keys are added to the repo.",
            ),
            verificationPlan = listOf(
                "Run the project's unit tests.",
                "Run the linter / formatter.",
            ),
            rollbackPlan = listOf("Revert the feature branch; no migrations to undo."),
            ownerGates = emptyList(),
            primaryWorker = "claude-code",
            modelLaneHint = "claude_code_worker",
            blocked = false,
        )

    fun execute(prompt: String): CodingExecuteResult =
        CodingExecuteResult(
            status = "approval_required",
            job = CockpitOrchestratorJob(
                id = "demo-job",
                status = "WAITING_FOR_APPROVAL",
                prompt = prompt.trim(),
            ),
            packet = packet(prompt, "."),
            workerId = "claude-code",
            riskClass = "RC2",
            authorizationRequired = true,
            authorizationHint = "Demo: a live execute would wait for \"Yes, with authorization.\"",
        )
}
