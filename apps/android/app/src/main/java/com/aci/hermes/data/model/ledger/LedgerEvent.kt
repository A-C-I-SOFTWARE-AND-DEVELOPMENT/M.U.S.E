package com.aci.hermes.data.model.ledger

import com.aci.hermes.data.model.audit.RiskTier

/**
 * One canonical category of activity on the JARVIS Prime timeline. Mirrors
 * the server's `LEDGER_CATEGORIES` (gateway/cockpit/contract.py). Some
 * categories (MEMORY_WRITE, EVIDENCE_PROMOTION) only appear when the
 * orchestrator actually emits such entries — the timeline never fabricates.
 */
enum class LedgerCategory {
    MODEL_CALL,
    TOOL_CALL,
    COMMAND,
    FILE_EDIT,
    WORKER_RUN,
    APPROVAL,
    MEMORY_WRITE,
    EVIDENCE_PROMOTION,
    DEPLOY_PUBLISH,
    NAVIGATION,
    VALIDATION,
    LIFECYCLE;

    companion object {
        /** Lenient parse — unknown / future server values map to LIFECYCLE. */
        fun fromWire(value: String?): LedgerCategory =
            entries.firstOrNull { it.name == value?.trim()?.uppercase() } ?: LIFECYCLE
    }
}

/**
 * One row of the Activity timeline — a redacted projection of a single
 * orchestrator ledger entry. Holds just enough to render the row and decide
 * whether to drill into [LedgerEventDetail].
 *
 * [timestamp] is the raw ISO-8601 string from the server (kept as-is so
 * ordering matches the server's lexical sort); [id] is `"<jobId>:<index>"`.
 */
data class LedgerEvent(
    val id: String,
    val jobId: String,
    val index: Int,
    val timestamp: String,
    val category: LedgerCategory,
    val kind: String,
    val worker: String?,
    val riskTier: RiskTier,
    val summary: String,
    val files: List<String>,
    val hasRollback: Boolean,
    val hasEvidence: Boolean,
    val hasDiff: Boolean,
)

/** A single piece of linked evidence on a [LedgerEventDetail]. */
data class LedgerEvidence(
    val id: String,
    val title: String,
    val body: String,
    val sourcePath: String?,
)

/** Linked diff for an event — either inline [body] or a list of [files]. */
data class LedgerDiff(
    val body: String?,
    val files: List<String>,
)

/** The rollback plan surfaced on an event detail (read-only display). */
data class LedgerRollback(
    val summary: String,
    val steps: List<String>,
)

/**
 * Full detail for one timeline event: the row fields plus the redacted
 * payload (what/why), linked evidence, linked diff, and the rollback plan.
 *
 * [rollbackAvailable] gates the "Request rollback" action; the request is
 * always owner-gated server-side, so this only controls UI affordance.
 */
data class LedgerEventDetail(
    val id: String,
    val jobId: String,
    val index: Int,
    val timestamp: String,
    val category: LedgerCategory,
    val kind: String,
    val worker: String?,
    val riskTier: RiskTier,
    val summary: String,
    val files: List<String>,
    val payload: List<Pair<String, String>>,
    val evidence: List<LedgerEvidence>,
    val diff: LedgerDiff?,
    val rollback: LedgerRollback?,
    val rollbackAvailable: Boolean,
)

/**
 * Active filter set for the timeline. Empty/blank fields mean "no filter".
 * Translated to query params by the repository. Kept as plain strings so the
 * filter UI can bind freely; the repository validates server-side.
 */
data class LedgerFilters(
    val job: String = "",
    val risk: String = "",
    val worker: String = "",
    val category: String = "",
    val file: String = "",
    val since: String = "",
    val until: String = "",
    val order: String = "desc",
) {
    fun toQuery(): Map<String, String> = buildMap {
        put("job", job)
        put("risk", risk)
        put("worker", worker)
        put("category", category)
        put("file", file)
        put("since", since)
        put("until", until)
        put("order", order)
    }

    val isEmpty: Boolean
        get() = job.isBlank() && risk.isBlank() && worker.isBlank() &&
            category.isBlank() && file.isBlank() && since.isBlank() && until.isBlank()
}
