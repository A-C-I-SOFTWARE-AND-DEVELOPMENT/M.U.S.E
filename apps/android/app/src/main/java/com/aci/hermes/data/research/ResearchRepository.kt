package com.aci.hermes.data.research

import com.aci.hermes.data.cockpit.CockpitJob
import com.aci.hermes.data.cockpit.CockpitResult
import com.aci.hermes.data.cockpit.CreateResearchTaskRequest
import com.aci.hermes.data.cockpit.HermesCockpitClient
import com.aci.hermes.data.cockpit.ManualSource
import com.aci.hermes.data.cockpit.PromoteFindingRequest
import com.aci.hermes.data.cockpit.ResearchReport
import com.aci.hermes.data.cockpit.RunResearchRequest
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/** Sync state of Research Mode against the cockpit gateway. */
sealed interface ResearchSync {
    /** Nothing run yet. */
    data object Idle : ResearchSync
    /** A research run / fetch is in flight. */
    data object Loading : ResearchSync
    /** No gateway paired — Research Mode needs a live backend. */
    data object Unpaired : ResearchSync
    /** A report is loaded (id of the current report). */
    data class Loaded(val reportId: String) : ResearchSync
    /** Paired but the gateway couldn't serve the request — honest, no fake data. */
    data class Error(val message: String) : ResearchSync
}

/** Outcome of promoting one evidence card to the Memory Tree. */
sealed interface PromoteOutcome {
    data object Stored : PromoteOutcome
    /** The store rejected it (secret-like / low confidence) — honest, not a bug. */
    data class Rejected(val reason: String) : PromoteOutcome
    data class Failed(val message: String) : PromoteOutcome
}

/** Outcome of turning a report into a coding task. */
sealed interface TaskOutcome {
    data class Created(val job: CockpitJob) : TaskOutcome
    data class Failed(val message: String) : TaskOutcome
    /** Not paired — there is no backend to enqueue against. */
    data object Unpaired : TaskOutcome
}

/**
 * Drives Research Mode off the cockpit gateway.
 *
 * Research is inherently a *live* feature: it needs the backend Evidence
 * Engine (web-search providers, the Research Vault, the memory gate). So unlike
 * [com.aci.hermes.data.memory.MemoryRepository] there is **no mock seed** — an
 * unpaired app reports [ResearchSync.Unpaired] rather than inventing findings.
 * Nothing fabricated ever reaches the user; an empty result with [notes] is the
 * gateway honestly saying it had no source-backed evidence.
 */
class ResearchRepository(
    private val client: HermesCockpitClient? = null,
    private val paired: () -> Boolean = { false },
) {
    private val _report = MutableStateFlow<ResearchReport?>(null)
    val report: StateFlow<ResearchReport?> = _report.asStateFlow()

    private val _history = MutableStateFlow<List<ResearchReport>>(emptyList())
    val history: StateFlow<List<ResearchReport>> = _history.asStateFlow()

    private val _sync = MutableStateFlow<ResearchSync>(ResearchSync.Idle)
    val sync: StateFlow<ResearchSync> = _sync.asStateFlow()

    val isLive: Boolean get() = client != null && paired()

    /** Run a research query. [manualSources] are optional user-pasted sources. */
    suspend fun run(query: String, manualSources: List<ManualSource> = emptyList()) {
        val c = client
        if (c == null || !paired()) {
            _sync.value = ResearchSync.Unpaired
            return
        }
        _sync.value = ResearchSync.Loading
        when (val res = c.researchRun(RunResearchRequest(query = query, manualSources = manualSources))) {
            is CockpitResult.Success -> {
                _report.value = res.value
                _sync.value = ResearchSync.Loaded(res.value.id)
            }
            is CockpitResult.Failure ->
                _sync.value = ResearchSync.Error("Gateway error ${res.httpStatus}: ${res.error.message}")
            is CockpitResult.Unreachable ->
                _sync.value = ResearchSync.Error(res.message)
        }
    }

    /** Pull past reports for the history list. Leaves [sync] untouched on error. */
    suspend fun refreshHistory() {
        val c = client ?: return
        if (!paired()) return
        when (val res = c.researchList()) {
            is CockpitResult.Success -> _history.value = res.value.reports
            is CockpitResult.Failure -> Unit
            is CockpitResult.Unreachable -> Unit
        }
    }

    /** Load one past report into the foreground. */
    suspend fun open(reportId: String) {
        val c = client
        if (c == null || !paired()) {
            _sync.value = ResearchSync.Unpaired
            return
        }
        _sync.value = ResearchSync.Loading
        when (val res = c.researchGet(reportId)) {
            is CockpitResult.Success -> {
                _report.value = res.value
                _sync.value = ResearchSync.Loaded(res.value.id)
            }
            is CockpitResult.Failure ->
                _sync.value = ResearchSync.Error("Gateway error ${res.httpStatus}: ${res.error.message}")
            is CockpitResult.Unreachable ->
                _sync.value = ResearchSync.Error(res.message)
        }
    }

    /** Promote one evidence card to memory — through the gateway's gate. */
    suspend fun promote(cardId: String): PromoteOutcome {
        val c = client ?: return PromoteOutcome.Failed("Not paired with a gateway")
        val reportId = _report.value?.id ?: return PromoteOutcome.Failed("No report loaded")
        return when (val res = c.researchPromote(reportId, PromoteFindingRequest(cardId))) {
            is CockpitResult.Success ->
                if (res.value.stored) PromoteOutcome.Stored
                else PromoteOutcome.Rejected(res.value.reason ?: "rejected by memory policy")
            is CockpitResult.Failure ->
                // 422 carries the honest rejection reason in the body, surfaced
                // as a Failure by the client; treat it as a policy rejection.
                if (res.httpStatus == 422) PromoteOutcome.Rejected(res.error.message)
                else PromoteOutcome.Failed("Gateway error ${res.httpStatus}: ${res.error.message}")
            is CockpitResult.Unreachable -> PromoteOutcome.Failed(res.message)
        }
    }

    /** Turn the current report into a queued coding task. */
    suspend fun createTask(title: String? = null): TaskOutcome {
        val c = client ?: return TaskOutcome.Unpaired
        if (!paired()) return TaskOutcome.Unpaired
        val reportId = _report.value?.id ?: return TaskOutcome.Failed("No report loaded")
        return when (val res = c.researchCreateTask(reportId, CreateResearchTaskRequest(title = title))) {
            is CockpitResult.Success -> TaskOutcome.Created(res.value)
            is CockpitResult.Failure ->
                TaskOutcome.Failed("Gateway error ${res.httpStatus}: ${res.error.message}")
            is CockpitResult.Unreachable -> TaskOutcome.Failed(res.message)
        }
    }
}
