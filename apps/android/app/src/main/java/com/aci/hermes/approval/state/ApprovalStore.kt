package com.aci.hermes.approval.state

import com.aci.hermes.approval.event.ApprovalEvent
import com.aci.hermes.approval.event.ApprovalEventSink
import com.aci.hermes.approval.model.ApprovalCard
import com.aci.hermes.approval.model.ApprovalHistoryItem
import com.aci.hermes.approval.model.ApprovalRiskTier
import com.aci.hermes.approval.model.ApprovalStatus
import com.aci.hermes.approval.model.CriticalActionState
import com.aci.hermes.approval.model.CriticalImpactReport
import com.aci.hermes.approval.model.RollbackPlan
import com.aci.hermes.approval.model.SeriousActionState

/**
 * Result returned by every store mutation so callers (UI + tests) can
 * distinguish "we updated state" from "we refused, because rules".
 */
sealed interface DecisionResult {
    val card: ApprovalCard

    data class Updated(override val card: ApprovalCard, val event: ApprovalEvent? = null) : DecisionResult
    data class Refused(override val card: ApprovalCard, val reason: Reason) : DecisionResult

    enum class Reason {
        ALREADY_DECIDED,
        EXPIRED,
        FORBIDDEN_TIER,
        SERIOUS_STEP2_BLOCKED_BEFORE_STEP1,
        CRITICAL_MISSING_IMPACT_REPORT,
        CRITICAL_MISSING_ROLLBACK,
        CRITICAL_STEP2_BLOCKED_BEFORE_STEP1
    }
}

/**
 * Source of truth for approval cards.
 *
 * This class is pure Kotlin (no Android imports) so it can be exercised by
 * plain JUnit tests on the JVM. The Compose UI observes a snapshot of state
 * and calls the mutation methods — it never executes destructive work itself.
 */
class ApprovalStore(
    private val sink: ApprovalEventSink,
    private val clock: () -> Long = System::currentTimeMillis,
    initial: List<ApprovalCard> = emptyList(),
    initialHistory: List<ApprovalHistoryItem> = emptyList(),
    private val decidedBy: String = "owner"
) {
    private val cards = LinkedHashMap<String, ApprovalCard>().apply {
        initial.forEach { put(it.id, it) }
    }
    private val history = mutableListOf<ApprovalHistoryItem>().apply { addAll(initialHistory) }

    fun snapshot(): List<ApprovalCard> = cards.values.toList()
    fun historySnapshot(): List<ApprovalHistoryItem> = history.toList()

    fun add(card: ApprovalCard) {
        cards[card.id] = card
    }

    private fun guard(card: ApprovalCard): DecisionResult.Refused? {
        if (card.tier == ApprovalRiskTier.FORBIDDEN) {
            return DecisionResult.Refused(card, DecisionResult.Reason.FORBIDDEN_TIER)
        }
        if (card.status != ApprovalStatus.PENDING) {
            return DecisionResult.Refused(card, DecisionResult.Reason.ALREADY_DECIDED)
        }
        if (card.isExpired(clock())) {
            val expired = card.copy(status = ApprovalStatus.EXPIRED)
            cards[card.id] = expired
            return DecisionResult.Refused(expired, DecisionResult.Reason.EXPIRED)
        }
        return null
    }

    fun approveRisky(cardId: String, note: String? = null): DecisionResult {
        val card = requireCard(cardId)
        guard(card)?.let { return it }
        require(card.tier == ApprovalRiskTier.RISKY) {
            "approveRisky is only valid for RISKY tier; was ${card.tier}"
        }
        val updated = card.copy(status = ApprovalStatus.APPROVED, editedNote = note)
        cards[cardId] = updated
        val event = ApprovalEvent.Approved(cardId, card.tier, clock(), confirmations = 1, note = note)
        sink.emit(event)
        history += historyItem(updated)
        return DecisionResult.Updated(updated, event)
    }

    fun editRisky(cardId: String, newAction: String): DecisionResult {
        val card = requireCard(cardId)
        guard(card)?.let { return it }
        val updated = card.copy(proposedAction = newAction, editedNote = "edited")
        cards[cardId] = updated
        val event = ApprovalEvent.Edited(cardId, card.tier, clock(), editedAction = newAction)
        sink.emit(event)
        return DecisionResult.Updated(updated, event)
    }

    fun approveSeriousStep1(cardId: String): DecisionResult {
        val card = requireCard(cardId)
        guard(card)?.let { return it }
        require(card.tier == ApprovalRiskTier.SERIOUS)
        val updated = card.copy(seriousState = card.seriousState.copy(step1Approved = true))
        cards[cardId] = updated
        return DecisionResult.Updated(updated)
    }

    /**
     * Second (consequence) confirmation of a SERIOUS action. Refused if step1
     * has not been completed — there is no way to bypass this in the UI either.
     */
    fun approveSeriousStep2(cardId: String): DecisionResult {
        val card = requireCard(cardId)
        guard(card)?.let { return it }
        require(card.tier == ApprovalRiskTier.SERIOUS)
        if (!card.seriousState.step1Approved) {
            return DecisionResult.Refused(card, DecisionResult.Reason.SERIOUS_STEP2_BLOCKED_BEFORE_STEP1)
        }
        val finalState = card.seriousState.copy(step2Approved = true)
        val updated = card.copy(seriousState = finalState, status = ApprovalStatus.APPROVED)
        cards[cardId] = updated
        val event = ApprovalEvent.Approved(cardId, card.tier, clock(), confirmations = 2)
        sink.emit(event)
        history += historyItem(updated)
        return DecisionResult.Updated(updated, event)
    }

    fun attachImpactReport(cardId: String, report: CriticalImpactReport): DecisionResult {
        val card = requireCard(cardId)
        guard(card)?.let { return it }
        require(card.tier == ApprovalRiskTier.CRITICAL)
        val updated = card.copy(criticalState = card.criticalState.copy(impactReport = report))
        cards[cardId] = updated
        return DecisionResult.Updated(updated)
    }

    fun attachRollbackPlan(cardId: String, plan: RollbackPlan): DecisionResult {
        val card = requireCard(cardId)
        guard(card)?.let { return it }
        require(card.tier == ApprovalRiskTier.CRITICAL)
        val updated = card.copy(criticalState = card.criticalState.copy(rollbackPlan = plan))
        cards[cardId] = updated
        return DecisionResult.Updated(updated)
    }

    fun approveCriticalStep1(cardId: String): DecisionResult {
        val card = requireCard(cardId)
        guard(card)?.let { return it }
        require(card.tier == ApprovalRiskTier.CRITICAL)
        val cs = card.criticalState
        if (!cs.hasImpactReport) {
            return DecisionResult.Refused(card, DecisionResult.Reason.CRITICAL_MISSING_IMPACT_REPORT)
        }
        if (!cs.hasRollbackPlan) {
            return DecisionResult.Refused(card, DecisionResult.Reason.CRITICAL_MISSING_ROLLBACK)
        }
        val updated = card.copy(criticalState = cs.copy(step1Approved = true))
        cards[cardId] = updated
        return DecisionResult.Updated(updated)
    }

    fun approveCriticalStep2(cardId: String): DecisionResult {
        val card = requireCard(cardId)
        guard(card)?.let { return it }
        require(card.tier == ApprovalRiskTier.CRITICAL)
        val cs = card.criticalState
        if (!cs.hasImpactReport) {
            return DecisionResult.Refused(card, DecisionResult.Reason.CRITICAL_MISSING_IMPACT_REPORT)
        }
        if (!cs.hasRollbackPlan) {
            return DecisionResult.Refused(card, DecisionResult.Reason.CRITICAL_MISSING_ROLLBACK)
        }
        if (!cs.step1Approved) {
            return DecisionResult.Refused(card, DecisionResult.Reason.CRITICAL_STEP2_BLOCKED_BEFORE_STEP1)
        }
        val finalState = cs.copy(step2Approved = true)
        val updated = card.copy(criticalState = finalState, status = ApprovalStatus.APPROVED)
        cards[cardId] = updated
        val event = ApprovalEvent.Approved(cardId, card.tier, clock(), confirmations = 2)
        sink.emit(event)
        history += historyItem(updated)
        return DecisionResult.Updated(updated, event)
    }

    /** Reject is always available while the card is still pending. */
    fun reject(cardId: String, reason: String? = null): DecisionResult {
        val card = requireCard(cardId)
        if (card.status != ApprovalStatus.PENDING) {
            return DecisionResult.Refused(card, DecisionResult.Reason.ALREADY_DECIDED)
        }
        val updated = card.copy(status = ApprovalStatus.REJECTED)
        cards[cardId] = updated
        val event = ApprovalEvent.Rejected(cardId, card.tier, clock(), reason = reason)
        sink.emit(event)
        history += historyItem(updated, note = reason)
        return DecisionResult.Updated(updated, event)
    }

    /** Available for SERIOUS and CRITICAL tiers; halts further progress immediately. */
    fun emergencyStop(cardId: String): DecisionResult {
        val card = requireCard(cardId)
        require(card.showsEmergencyStop) { "emergency stop only applies to SERIOUS/CRITICAL" }
        if (card.status != ApprovalStatus.PENDING) {
            return DecisionResult.Refused(card, DecisionResult.Reason.ALREADY_DECIDED)
        }
        val updated = card.copy(status = ApprovalStatus.EMERGENCY_STOPPED)
        cards[cardId] = updated
        val event = ApprovalEvent.EmergencyStopped(cardId, card.tier, clock())
        sink.emit(event)
        history += historyItem(updated, note = "emergency stop")
        return DecisionResult.Updated(updated, event)
    }

    /**
     * Sweep currently-pending cards and mark any past expiry as EXPIRED,
     * emitting an expiry event for each one.
     */
    fun sweepExpired(): List<ApprovalCard> {
        val now = clock()
        val expired = mutableListOf<ApprovalCard>()
        cards.values.toList().forEach { card ->
            if (card.status == ApprovalStatus.PENDING && now >= card.expiresAtMillis) {
                val updated = card.copy(status = ApprovalStatus.EXPIRED)
                cards[card.id] = updated
                sink.emit(ApprovalEvent.Expired(card.id, card.tier, now))
                history += historyItem(updated, note = "expired")
                expired += updated
            }
        }
        return expired
    }

    private fun requireCard(id: String): ApprovalCard =
        cards[id] ?: error("No approval card with id=$id")

    private fun historyItem(card: ApprovalCard, note: String? = null) = ApprovalHistoryItem(
        cardId = card.id,
        title = card.title,
        tier = card.tier,
        outcome = card.status,
        decidedAtMillis = clock(),
        decidedBy = decidedBy,
        note = note ?: card.editedNote
    )

    companion object {
        fun emptySeriousState() = SeriousActionState()
        fun emptyCriticalState() = CriticalActionState()
    }
}
