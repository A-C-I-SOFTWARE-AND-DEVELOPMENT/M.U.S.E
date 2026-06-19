package com.aci.hermes.data.cockpit

import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * Aggregating, read-only repository behind the muse command-center
 * home screen. A single [refresh] fans out (concurrently) to every cockpit
 * read the home screen needs — runtime status, model/router policy, worker
 * detection, jobs, owner approvals, recent memory, ledger events, and
 * Research Vault evidence — and folds the results into one
 * [CockpitHomeSnapshot].
 *
 * It mirrors the contract followed by [CockpitJobsRepository]: an unpaired
 * or unreachable gateway yields an **empty** snapshot plus an honest [sync]
 * state, never fabricated data. Each leg degrades independently — a single
 * failing endpoint leaves the rest of the snapshot populated, so the home
 * screen stays useful even when one subsystem is down.
 *
 * Detail screens keep their own repositories ([MemoryRepository],
 * [AuditRepository], [CockpitApprovalsRepository], [CockpitJobsRepository]).
 * This repository only powers the glanceable home overlay; it does not
 * replace them.
 */
class CockpitHomeRepository(
    private val client: HermesCockpitClient,
) {
    private val _snapshot = MutableStateFlow(CockpitHomeSnapshot())
    val snapshot: StateFlow<CockpitHomeSnapshot> = _snapshot.asStateFlow()

    private val _sync = MutableStateFlow<HomeSync>(HomeSync.Idle)
    val sync: StateFlow<HomeSync> = _sync.asStateFlow()

    /**
     * Refresh every home read. Safe to call on screen launch and on
     * pull-to-refresh. Never throws; failures land in [sync] / per-leg
     * nulls.
     */
    suspend fun refresh() {
        if (!client.isPaired()) {
            _snapshot.value = CockpitHomeSnapshot()
            _sync.value = HomeSync.NotPaired
            return
        }
        _sync.value = HomeSync.Loading

        val result = coroutineScope {
            val runtime = async { client.runtimeStatus() }
            val models = async { client.modelPolicy() }
            val workers = async { client.runtimeWorkers() }
            val jobs = async { client.jobsList() }
            val approvals = async { client.approvalsList() }
            val memory = async { client.memoryList() }
            val audit = async { client.auditList() }
            val research = async { client.research(limit = RESEARCH_LIMIT) }

            CockpitHomeSnapshot(
                runtime = runtime.await().valueOrNull(),
                models = models.await().valueOrNull(),
                workers = workers.await().valueOrNull(),
                jobs = jobs.await().valueOrNull(),
                approvals = approvals.await().valueOrNull(),
                memory = memory.await().valueOrNull(),
                audit = audit.await().valueOrNull(),
                research = research.await().valueOrNull(),
            )
        }

        _snapshot.value = result
        // If every leg failed the gateway is effectively unreachable; report
        // it honestly rather than showing an all-empty "loaded" home.
        _sync.value = if (result.isEmpty) {
            HomeSync.Error("Gateway unreachable or returned no data")
        } else {
            HomeSync.Loaded
        }
    }

    private fun <T> CockpitResult<T>.valueOrNull(): T? =
        (this as? CockpitResult.Success)?.value

    companion object {
        const val RESEARCH_LIMIT = 10
    }
}

/** Sync state of the aggregated home reads against the cockpit gateway. */
sealed interface HomeSync {
    data object Idle : HomeSync
    data object Loading : HomeSync
    /** No gateway paired — nothing real to show (no fabricated data). */
    data object NotPaired : HomeSync
    data object Loaded : HomeSync
    data class Error(val message: String) : HomeSync
}

/**
 * Immutable snapshot of every cockpit read the home screen overlays. Each
 * leg is null when that endpoint was unreachable or not yet loaded, so the
 * deriver can prefer live data field-by-field and fall back gracefully.
 */
data class CockpitHomeSnapshot(
    val runtime: RuntimeStatus? = null,
    val models: ModelPolicy? = null,
    val workers: WorkerDetectionList? = null,
    val jobs: JobList? = null,
    val approvals: CockpitApprovalCardList? = null,
    val memory: CockpitMemoryList? = null,
    val audit: CockpitAuditList? = null,
    val research: CockpitResearchList? = null,
) {
    /** True when no leg returned data (unpaired/unreachable everywhere). */
    val isEmpty: Boolean
        get() = runtime == null && models == null && workers == null &&
            jobs == null && approvals == null && memory == null &&
            audit == null && research == null
}
