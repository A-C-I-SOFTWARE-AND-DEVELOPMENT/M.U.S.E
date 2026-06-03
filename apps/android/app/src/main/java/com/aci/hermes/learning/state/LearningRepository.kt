package com.aci.hermes.learning.state

import com.aci.hermes.approval.state.CockpitApprovalsRepository.Companion.OWNER_PHRASE
import com.aci.hermes.data.cockpit.CockpitApprovalDecisionResult
import com.aci.hermes.data.cockpit.CockpitResult
import com.aci.hermes.data.cockpit.HermesCockpitClient
import com.aci.hermes.data.learning.LearningCandidate
import com.aci.hermes.data.learning.toCandidate
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/** Sync state of the learning queue against the cockpit gateway. */
sealed interface LearningSync {
    data object Idle : LearningSync
    data object Loading : LearningSync
    /** No gateway paired — nothing real to show (no fabricated candidates). */
    data object NotPaired : LearningSync
    data class Loaded(val count: Int) : LearningSync
    data class Error(val message: String) : LearningSync
}

/**
 * Gateway-backed view of the JARVIS Learning Queue — the learning-dataset
 * candidates awaiting owner approval. Lists the real candidates and decides
 * them through the gateway.
 *
 * The owner gate is enforced honestly: [approve] submits the canonical owner
 * phrase — which the app sends only after the owner completes the on-device
 * confirmation — and the gateway still verifies it server-side (403
 * otherwise). There is no fabricated candidate: unpaired/unreachable yields
 * an empty list + an honest [sync] state.
 *
 * Mirrors `CockpitApprovalsRepository` so the Learning section reuses the
 * exact owner-gate ceremony as the rest of the cockpit.
 */
class LearningRepository(
    private val client: HermesCockpitClient,
) {
    private val _candidates = MutableStateFlow<List<LearningCandidate>>(emptyList())
    val candidates: StateFlow<List<LearningCandidate>> = _candidates.asStateFlow()

    private val _sync = MutableStateFlow<LearningSync>(LearningSync.Idle)
    val sync: StateFlow<LearningSync> = _sync.asStateFlow()

    suspend fun refresh() {
        if (!client.isPaired()) {
            _candidates.value = emptyList()
            _sync.value = LearningSync.NotPaired
            return
        }
        _sync.value = LearningSync.Loading
        when (val res = client.learningList()) {
            is CockpitResult.Success -> {
                _candidates.value = res.value.learning.map { it.toCandidate() }
                _sync.value = LearningSync.Loaded(_candidates.value.size)
            }
            is CockpitResult.Failure ->
                _sync.value = LearningSync.Error("Gateway error ${res.httpStatus}: ${res.error.message}")
            is CockpitResult.Unreachable ->
                _sync.value = LearningSync.Error(res.message)
        }
    }

    /** Approve on the gateway with the owner phrase; refreshes on success. */
    suspend fun approve(id: String): CockpitResult<CockpitApprovalDecisionResult> {
        val res = client.learningDecide(id, decision = "approve", authorization = OWNER_PHRASE)
        if (res is CockpitResult.Success) refresh()
        return res
    }

    /** Reject on the gateway (no phrase required); refreshes on success. */
    suspend fun reject(id: String, notes: String? = null): CockpitResult<CockpitApprovalDecisionResult> {
        val res = client.learningDecide(id, decision = "reject", notes = notes)
        if (res is CockpitResult.Success) refresh()
        return res
    }
}
