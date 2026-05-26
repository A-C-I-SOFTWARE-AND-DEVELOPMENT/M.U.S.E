package com.aci.hermes.approvals

import com.aci.hermes.events.EventSpine
import com.aci.hermes.events.JarvisEvent
import com.aci.hermes.safety.EmergencyStop
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update

/**
 * In-memory queue of approvals awaiting a decision from the owner.
 *
 * The queue enforces Jarvis Prime's confirmation policy:
 *
 *   * RISKY needs 1 confirmation. `approve()` decides immediately.
 *   * SERIOUS needs 2 confirmations. `confirm()` increments the
 *     count; the second `approve()` decides it.
 *   * CRITICAL also needs 2 confirmations AND requires an impact
 *     report; constructor of [Approval] enforces the report exists.
 *
 * Engaging [EmergencyStop] flips every pending approval to
 * REJECTED_BY_EMERGENCY_STOP and emits a single audit event.
 */
class ApprovalQueue(
    private val spine: EventSpine,
    emergencyStop: EmergencyStop,
) {
    private val _approvals = MutableStateFlow<List<Approval>>(emptyList())
    val approvals: StateFlow<List<Approval>> = _approvals.asStateFlow()

    init {
        emergencyStop.register { reason ->
            val cancelled = _approvals.value.count { it.decision == Approval.Decision.PENDING }
            _approvals.update { list ->
                list.map {
                    if (it.decision == Approval.Decision.PENDING) {
                        it.copy(
                            decision = Approval.Decision.REJECTED_BY_EMERGENCY_STOP,
                            decidedAt = System.currentTimeMillis(),
                            decisionReason = reason,
                        )
                    } else it
                }
            }
            if (cancelled > 0) {
                spine.emit(
                    source = JarvisEvent.Source.EMERGENCY_STOP,
                    severity = JarvisEvent.Severity.CRITICAL,
                    message = "Emergency stop cancelled $cancelled pending approval(s)",
                    attributes = mapOf("reason" to reason, "count" to cancelled.toString()),
                )
            }
        }
    }

    /** Add a new approval request to the queue. */
    fun enqueue(approval: Approval) {
        _approvals.update { it + approval }
        spine.emit(
            source = JarvisEvent.Source.APPROVAL,
            severity = JarvisEvent.Severity.NOTICE,
            message = "Approval requested: ${approval.summary}",
            attributes = mapOf("tier" to approval.tier.name, "id" to approval.id),
        )
    }

    /**
     * Record one confirmation. SERIOUS and CRITICAL approvals require
     * two before [approve] will return true. Idempotent past the
     * required threshold.
     */
    fun confirm(id: String) {
        _approvals.update { list ->
            list.map { ap ->
                if (ap.id == id && ap.decision == Approval.Decision.PENDING) {
                    val capped = minOf(ap.confirmationsCollected + 1, ap.tier.confirmationsRequired)
                    ap.copy(confirmationsCollected = capped)
                } else ap
            }
        }
    }

    /**
     * Approve the request. Returns true if the decision was applied;
     * false if the approval still needs more confirmations.
     */
    fun approve(id: String): Boolean {
        val ap = _approvals.value.firstOrNull { it.id == id } ?: return false
        if (!ap.canApprove) return false
        _approvals.update { list ->
            list.map {
                if (it.id == id) it.copy(
                    decision = Approval.Decision.APPROVED,
                    decidedAt = System.currentTimeMillis(),
                ) else it
            }
        }
        spine.emit(
            source = JarvisEvent.Source.APPROVAL,
            severity = JarvisEvent.Severity.NOTICE,
            message = "Approved: ${ap.summary}",
            attributes = mapOf("id" to id),
        )
        return true
    }

    fun reject(id: String, reason: String? = null) {
        val ap = _approvals.value.firstOrNull { it.id == id } ?: return
        if (ap.decision != Approval.Decision.PENDING) return
        _approvals.update { list ->
            list.map {
                if (it.id == id) it.copy(
                    decision = Approval.Decision.REJECTED,
                    decidedAt = System.currentTimeMillis(),
                    decisionReason = reason,
                ) else it
            }
        }
        spine.emit(
            source = JarvisEvent.Source.APPROVAL,
            severity = JarvisEvent.Severity.NOTICE,
            message = "Rejected: ${ap.summary}",
            attributes = mapOf("id" to id, "reason" to (reason ?: "")),
        )
    }

    fun pending(): List<Approval> =
        _approvals.value.filter { it.decision == Approval.Decision.PENDING }
}
