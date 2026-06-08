package com.aci.hermes.data.ledger

import com.aci.hermes.data.audit.SecretRedactor
import com.aci.hermes.data.cockpit.CockpitResult
import com.aci.hermes.data.cockpit.HermesCockpitClient
import com.aci.hermes.data.model.ledger.LedgerEvent
import com.aci.hermes.data.model.ledger.LedgerEventDetail
import com.aci.hermes.data.model.ledger.LedgerFilters
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/** Sync state of the Activity timeline against the cockpit gateway. */
sealed interface LedgerSync {
    data object Idle : LedgerSync
    data object Loading : LedgerSync
    /** No gateway paired — nothing live to show (the timeline is empty). */
    data object NotPaired : LedgerSync
    data class Loaded(val count: Int) : LedgerSync
    data class Error(val message: String) : LedgerSync
}

/**
 * Read access to the MUSE Activity timeline — the redacted
 * projection of the orchestrator event ledger (`GET /v1/cockpit/ledger`).
 *
 * - **Paired**: [refresh] pulls the live timeline for the current [filters];
 *   [fetchDetail] loads one event on demand. Server already redacts; this
 *   repository re-applies [SecretRedactor] as defense in depth so a secret
 *   can never reach the UI even if a server-side pattern is missed.
 * - **Unpaired / tests**: the timeline is empty (no fabricated data) and
 *   [sync] reports [LedgerSync.NotPaired].
 *
 * The gated rollback request is owner-gated server-side; [requestRollback]
 * just forwards it and returns whether the request was queued.
 */
class LedgerRepository(
    private val client: HermesCockpitClient? = null,
    private val paired: () -> Boolean = { false },
) {

    private val eventsState: MutableStateFlow<List<LedgerEvent>> = MutableStateFlow(emptyList())
    val events: StateFlow<List<LedgerEvent>> = eventsState.asStateFlow()

    private val filtersState: MutableStateFlow<LedgerFilters> = MutableStateFlow(LedgerFilters())
    val filters: StateFlow<LedgerFilters> = filtersState.asStateFlow()

    private val _sync: MutableStateFlow<LedgerSync> = MutableStateFlow(LedgerSync.Idle)
    val sync: StateFlow<LedgerSync> = _sync.asStateFlow()

    val isLive: Boolean get() = client != null && paired()

    /** Replace the active filters and immediately re-pull. */
    suspend fun applyFilters(filters: LedgerFilters) {
        filtersState.value = filters
        refresh()
    }

    /** Pull the live timeline for the current filters when paired. */
    suspend fun refresh() {
        val c = client
        if (c == null || !paired()) {
            eventsState.value = emptyList()
            _sync.value = LedgerSync.NotPaired
            return
        }
        _sync.value = LedgerSync.Loading
        when (val res = c.ledgerTimeline(filtersState.value.toQuery())) {
            is CockpitResult.Success -> {
                eventsState.value = res.value.events.map { it.toDomain().redactedForDisplay() }
                _sync.value = LedgerSync.Loaded(eventsState.value.size)
            }
            is CockpitResult.Failure ->
                _sync.value = LedgerSync.Error("Gateway error ${res.httpStatus}: ${res.error.message}")
            is CockpitResult.Unreachable ->
                _sync.value = LedgerSync.Error(res.message)
        }
    }

    /** Fetch (and redact) the detail for one event; null when unavailable. */
    suspend fun fetchDetail(jobId: String, index: Int): LedgerEventDetail? {
        val c = client ?: return null
        if (!paired()) return null
        val res = c.ledgerEvent(jobId, index)
        return if (res is CockpitResult.Success) res.value.toDomain().redactedForDisplay() else null
    }

    /**
     * Raise an owner-gated rollback request. Returns the approval card id on
     * success (the rollback only runs after the owner approves it), or null.
     */
    suspend fun requestRollback(jobId: String, index: Int, reason: String?): String? {
        val c = client ?: return null
        if (!paired()) return null
        val res = c.ledgerRollbackRequest(jobId, index, reason)
        return if (res is CockpitResult.Success) res.value.id else null
    }
}

// ─── on-device redaction (defense in depth) ───────────────────────────────

private fun LedgerEvent.redactedForDisplay(): LedgerEvent = copy(
    summary = SecretRedactor.redact(summary),
    worker = worker?.let(SecretRedactor::redact),
    files = files.map(SecretRedactor::redact),
)

private fun LedgerEventDetail.redactedForDisplay(): LedgerEventDetail = copy(
    summary = SecretRedactor.redact(summary),
    worker = worker?.let(SecretRedactor::redact),
    files = files.map(SecretRedactor::redact),
    payload = payload.map { (k, v) -> k to SecretRedactor.redact(v) },
    evidence = evidence.map {
        it.copy(
            title = SecretRedactor.redact(it.title),
            body = SecretRedactor.redact(it.body),
            sourcePath = it.sourcePath?.let(SecretRedactor::redact),
        )
    },
    diff = diff?.copy(
        body = diff.body?.let(SecretRedactor::redact),
        files = diff.files.map(SecretRedactor::redact),
    ),
    rollback = rollback?.copy(
        summary = SecretRedactor.redact(rollback.summary),
        steps = rollback.steps.map(SecretRedactor::redact),
    ),
)
