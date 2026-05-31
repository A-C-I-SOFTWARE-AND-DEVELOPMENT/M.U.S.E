package com.aci.hermes.approval.state

import com.aci.hermes.approval.model.ApprovalCard
import com.aci.hermes.data.cockpit.CockpitApprovalDecisionResult
import com.aci.hermes.data.cockpit.CockpitResult
import com.aci.hermes.data.cockpit.HermesCockpitClient
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/** Sync state of the approval queue against the cockpit gateway. */
sealed interface ApprovalsSync {
    data object Idle : ApprovalsSync
    data object Loading : ApprovalsSync
    /** No gateway paired — nothing real to show (no fabricated cards). */
    data object NotPaired : ApprovalsSync
    data class Loaded(val count: Int) : ApprovalsSync
    data class Error(val message: String) : ApprovalsSync
}

/**
 * Gateway-backed view of the owner-approval queue (contract §10c). Lists
 * the real pending cards and decides them through the gateway.
 *
 * `decide` enforces the owner gate honestly: [approve] submits the canonical
 * owner phrase — which the app sends only after the owner completes the
 * on-device confirmation — and the gateway still verifies it server-side
 * (403 otherwise). There is no fabricated card: unpaired/unreachable yields
 * an empty list + an honest [sync] state.
 */
class CockpitApprovalsRepository(
    private val client: HermesCockpitClient,
) {
    private val _cards = MutableStateFlow<List<ApprovalCard>>(emptyList())
    val cards: StateFlow<List<ApprovalCard>> = _cards.asStateFlow()

    private val _sync = MutableStateFlow<ApprovalsSync>(ApprovalsSync.Idle)
    val sync: StateFlow<ApprovalsSync> = _sync.asStateFlow()

    suspend fun refresh() {
        if (!client.isPaired()) {
            _cards.value = emptyList()
            _sync.value = ApprovalsSync.NotPaired
            return
        }
        _sync.value = ApprovalsSync.Loading
        when (val res = client.approvalsList()) {
            is CockpitResult.Success -> {
                _cards.value = res.value.approvals.map { it.toCard() }
                _sync.value = ApprovalsSync.Loaded(_cards.value.size)
            }
            is CockpitResult.Failure ->
                _sync.value = ApprovalsSync.Error("Gateway error ${res.httpStatus}: ${res.error.message}")
            is CockpitResult.Unreachable ->
                _sync.value = ApprovalsSync.Error(res.message)
        }
    }

    /** Approve on the gateway with the owner phrase; refreshes on success. */
    suspend fun approve(id: String): CockpitResult<CockpitApprovalDecisionResult> {
        val res = client.approvalsDecide(id, decision = "approve", authorization = OWNER_PHRASE)
        if (res is CockpitResult.Success) refresh()
        return res
    }

    /** Reject on the gateway (no phrase required); refreshes on success. */
    suspend fun reject(id: String, notes: String? = null): CockpitResult<CockpitApprovalDecisionResult> {
        val res = client.approvalsDecide(id, decision = "reject", notes = notes)
        if (res is CockpitResult.Success) refresh()
        return res
    }

    companion object {
        /**
         * The cockpit owner-gate phrase (mirrors the server's
         * `owner_auth.AUTHORIZATION_PHRASE`). The app submits it only after
         * the owner completes the on-device approval confirmation; the
         * gateway still enforces it server-side, so this is the ceremony
         * token, not a bypass.
         */
        const val OWNER_PHRASE: String = "Yes, with authorization."
    }
}
