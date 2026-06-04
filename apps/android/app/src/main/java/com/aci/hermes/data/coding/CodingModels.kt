package com.aci.hermes.data.coding

import com.aci.hermes.data.cockpit.CodingAuditResult
import com.aci.hermes.data.cockpit.CodingPacket
import kotlinx.serialization.Serializable

/**
 * Standalone-local coding-cockpit domain models (v1.5).
 *
 * A [SavedCodingTask] is the on-device record of one coding request as it
 * moves through the local flow: draft → audit (classify/route) → plan
 * (bounded work packet) → handoff (copy a Claude Code prompt or dispatch a
 * gated backend execute). The backend wire shapes ([CodingAuditResult],
 * [CodingPacket]) are reused verbatim — there is no second copy of the work
 * packet schema to drift.
 *
 * Persisted locally (JSON, [CodingTaskStore]) so the cockpit is useful
 * offline: a draft survives with no backend, can be queued, and its prompt
 * copied for a desktop Claude Code / Codex session. Nothing here holds a
 * secret; the owner authorization phrase is never stored.
 */
@Serializable
data class SavedCodingTask(
    val id: String,
    val title: String,
    val prompt: String,
    val repoRoot: String = "",
    val state: CodingHandoffState = CodingHandoffState.DRAFT,
    /** Backend classification/route (read-only). Null until audited. */
    val audit: CodingAuditResult? = null,
    /** Bounded work packet from `coding/plan`. Null until planned. */
    val packet: CodingPacket? = null,
    /** Validation findings count from the last plan (honest packet health). */
    val validationOk: Boolean = false,
    /** The orchestrator job id once an execute is staged/dispatched. */
    val jobId: String? = null,
    /** Last error/blocker reason shown in the UI (never a secret). */
    val note: String? = null,
    /** True when this task was produced by Mock/demo mode, not a live backend. */
    val demo: Boolean = false,
    val createdAt: Long = 0L,
    val updatedAt: Long = 0L,
) {
    /** A packet good enough to hand off (planned + validated). */
    val isHandoffReady: Boolean
        get() = packet != null && validationOk && !packet.blocked
}

/**
 * Lifecycle of a coding task in the standalone-local flow. Deliberately
 * honest: nothing claims "done" or "executing" unless the backend said so.
 */
@Serializable
enum class CodingHandoffState {
    /** Captured locally; not yet classified. */
    DRAFT,

    /** Classified + routed by the backend (risk/worker/owner-gates known). */
    AUDITED,

    /** A bounded work packet has been built and validated. */
    PLANNED,

    /** Saved for handoff while no backend is reachable; will sync later. */
    QUEUED_OFFLINE,

    /** Prompt copied / handed off to a desktop coding agent (Claude Code/Codex). */
    HANDED_OFF,

    /** Execute staged but withheld pending the owner authorization phrase. */
    BLOCKED_OWNER,

    /** Backend accepted an execute dispatch (a job is running). */
    EXECUTING,

    /** Backend reported the job finished. */
    DONE,

    /** A step failed; [SavedCodingTask.note] carries the reason. */
    ERROR;

    val label: String
        get() = name.lowercase().replace('_', ' ')
}

/**
 * Outcome of a single repository step, mapped to UI without leaking
 * transport details. Distinct from a raw `CockpitResult` so the ViewModels
 * branch on intent (needs pairing vs owner gate vs failure), never on an
 * HTTP status.
 */
sealed interface CodingActionResult {
    val task: SavedCodingTask?

    data class Ok(override val task: SavedCodingTask) : CodingActionResult

    /** No gateway paired/reachable; the task was kept (queued) for later. */
    data class NeedsPairing(override val task: SavedCodingTask) : CodingActionResult

    /** Execute requires the exact owner phrase; the job is staged, not run. */
    data class OwnerGateRequired(
        override val task: SavedCodingTask,
        val hint: String,
    ) : CodingActionResult

    /** A genuine backend/validation failure (message is safe to display). */
    data class Failure(
        override val task: SavedCodingTask?,
        val message: String,
    ) : CodingActionResult
}
