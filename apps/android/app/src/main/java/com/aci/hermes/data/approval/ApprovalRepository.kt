package com.aci.hermes.data.approval

import android.content.Context
import com.aci.hermes.data.JsonStore
import com.aci.hermes.data.model.ApprovalCard
import com.aci.hermes.data.model.ApprovalStatus
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.MutableStateFlow

/**
 * Permission Kernel — pending and decided approvals.
 *
 * The repository never executes an action itself; it only records the
 * decision. The orchestrator / gateway watches [items] and runs the
 * actual work only when an entry transitions to APPROVED.
 */
class ApprovalRepository(context: Context) {
    private val store = JsonStore(
        context = context,
        fileName = "jarvis_approvals.json",
        serializer = ApprovalCard.serializer(),
        maxItems = MAX_ITEMS,
    )

    val items: StateFlow<List<ApprovalCard>> = store.items

    suspend fun load() {
        store.load()
    }

    suspend fun upsert(card: ApprovalCard) {
        val existing = store.items.value.firstOrNull { it.id == card.id }
        if (existing == null) {
            store.add(card, atStart = true)
        } else {
            store.update({ it.id == card.id }) { card }
        }
    }

    suspend fun approve(id: String, notes: String? = null) {
        store.update({ it.id == id && it.status == ApprovalStatus.PENDING }) {
            it.copy(
                status = ApprovalStatus.APPROVED,
                decidedAt = System.currentTimeMillis(),
                decisionNotes = notes,
            )
        }
    }

    suspend fun deny(id: String, notes: String? = null) {
        store.update({ it.id == id && it.status == ApprovalStatus.PENDING }) {
            it.copy(
                status = ApprovalStatus.DENIED,
                decidedAt = System.currentTimeMillis(),
                decisionNotes = notes,
            )
        }
    }

    /** Engaging the emergency stop transitions every pending approval. */
    suspend fun cancelAllPending(reason: String = "Emergency stop engaged") {
        val now = System.currentTimeMillis()
        store.update({ it.status == ApprovalStatus.PENDING }) {
            it.copy(
                status = ApprovalStatus.CANCELLED_BY_EMERGENCY_STOP,
                decidedAt = now,
                decisionNotes = reason,
            )
        }
    }

    suspend fun clear() {
        store.clear()
    }

    suspend fun seedIfEmpty(builder: () -> List<ApprovalCard>) {
        store.seedIfEmpty(builder)
    }

    companion object {
        const val MAX_ITEMS = 200
    }
}
