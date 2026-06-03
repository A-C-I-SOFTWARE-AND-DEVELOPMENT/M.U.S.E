package com.aci.hermes.data.cockpit

import com.aci.hermes.approval.state.CockpitApprovalsRepository
import com.aci.hermes.data.jarvis.JarvisApprovalGateway
import com.aci.hermes.data.jarvis.JarvisApprovalResult
import com.aci.hermes.data.jarvis.JarvisDispatchResult
import com.aci.hermes.data.jarvis.JarvisJobDispatcher
import com.aci.hermes.data.jarvis.JarvisRecordInspector
import com.aci.hermes.data.jarvis.JarvisRecordRef
import com.aci.hermes.data.jarvis.JarvisRecordView
import com.aci.hermes.data.model.TargetTool

/**
 * Cockpit-backed implementations of the chat view-model ports
 * ([JarvisJobDispatcher] / [JarvisApprovalGateway] / [JarvisRecordInspector]).
 *
 * These live in the cockpit data layer (not the view model) so the
 * cockpit-specific knowledge — worker ids, the owner phrase, audit/proof
 * shapes — stays out of the UI. Each is `available` only while a gateway is
 * paired, so the view model transparently falls back to its offline path.
 */

/** Maps the chat's [TargetTool] to a cockpit worker id for dispatch. */
private fun TargetTool.toWorkerId(): String = when (this) {
    TargetTool.CLAUDE_CODE -> "claude_code_builder"
    TargetTool.CLAUDE -> "claude_code_builder"
    TargetTool.CHATGPT -> "claude_code_builder"
    TargetTool.CODEX -> "codex_bounded_fix"
    TargetTool.MANUAL -> "claude_code_builder"
}

class CockpitJobDispatcher(
    private val jobs: CockpitJobsRepository,
    private val paired: () -> Boolean,
) : JarvisJobDispatcher {

    override val available: Boolean get() = paired()

    override suspend fun dispatch(
        title: String,
        prompt: String,
        targetTool: TargetTool,
    ): JarvisDispatchResult {
        if (!paired()) return JarvisDispatchResult.Unavailable
        return when (val res = jobs.dispatch(title = title, workerId = targetTool.toWorkerId(), prompt = prompt)) {
            is CockpitResult.Success -> JarvisDispatchResult.Ok(res.value.id)
            is CockpitResult.Failure -> JarvisDispatchResult.Failed(res.error.message)
            is CockpitResult.Unreachable -> JarvisDispatchResult.Failed(res.message)
        }
    }
}

class CockpitApprovalGateway(
    private val approvals: CockpitApprovalsRepository,
    private val paired: () -> Boolean,
) : JarvisApprovalGateway {

    override val available: Boolean get() = paired()

    override suspend fun approve(approvalId: String): JarvisApprovalResult {
        if (!paired()) return JarvisApprovalResult.Unavailable
        return when (val res = approvals.approve(approvalId)) {
            is CockpitResult.Success -> {
                val err = res.value.error
                if (err.isNullOrBlank()) JarvisApprovalResult.Accepted
                else JarvisApprovalResult.Rejected(res.value.hint ?: err)
            }
            is CockpitResult.Failure -> JarvisApprovalResult.Rejected(res.error.message)
            is CockpitResult.Unreachable -> JarvisApprovalResult.Rejected(res.message)
        }
    }
}

class CockpitRecordInspector(
    private val client: HermesCockpitClient,
    private val paired: () -> Boolean,
) : JarvisRecordInspector {

    override val available: Boolean get() = paired()

    override suspend fun load(ref: JarvisRecordRef): JarvisRecordView? {
        if (!paired()) return null
        return when (ref.kind) {
            JarvisRecordRef.Kind.EVIDENCE -> loadEvidence(ref)
            JarvisRecordRef.Kind.LEDGER -> loadLedger(ref)
        }
    }

    private suspend fun loadEvidence(ref: JarvisRecordRef): JarvisRecordView? {
        val proof = (client.auditProof(ref.id) as? CockpitResult.Success)?.value ?: return null
        val lines = buildList {
            if (proof.rationale.isNotBlank()) add("Rationale: ${proof.rationale}")
            proof.evidence.forEach { e -> add("• ${e.title.ifBlank { e.kind }}: ${e.body}".trim()) }
            if (proof.testsRun.isNotEmpty()) add("Tests: ${proof.testsRun.joinToString(", ")}")
            if (proof.filesChanged.isNotEmpty()) add("Files: ${proof.filesChanged.joinToString(", ")}")
            proof.verification.let { v ->
                if (v.summary.isNotBlank()) add("Verification (${v.status}): ${v.summary}")
            }
        }
        return JarvisRecordView(
            title = ref.title,
            subtitle = "Evidence • ${proof.evidence.size} item(s)",
            lines = lines.ifEmpty { listOf("No evidence recorded for this turn.") },
        )
    }

    private suspend fun loadLedger(ref: JarvisRecordRef): JarvisRecordView? {
        val list = (client.auditList() as? CockpitResult.Success)?.value ?: return null
        val record = list.records.firstOrNull { it.id == ref.id || it.proofId == ref.id }
            ?: list.records.firstOrNull()
            ?: return JarvisRecordView(ref.title, subtitle = "Decision ledger", lines = listOf("No ledger entries yet."))
        val lines = buildList {
            if (record.userRequest.isNotBlank()) add("Request: ${record.userRequest}")
            if (record.action.isNotBlank()) add("Action: ${record.action}")
            add("Risk: ${record.riskTier} • Result: ${record.result} • Approval: ${record.approvalState}")
            if (record.route.reason.isNotBlank()) add("Route: ${record.route.destination} — ${record.route.reason}")
        }
        return JarvisRecordView(title = ref.title, subtitle = "Decision ledger", lines = lines)
    }
}
